"""Durable per-attempt accounting for EF09-RH1 matrix executions."""

import fcntl
import json
import os
import re
from dataclasses import asdict, dataclass

from .events import canonical_json
from .experiments import CONFIRMATION, MIRROR, POLICY, SCREENING
from .fixture import FIXTURE_VERSION
from .profiles import PROFILE_VERSION
from .provenance import EARLY_EXIT, EP08, FROZEN, H32, observation

SCHEMA = "EF09-RH1-execution-v1"
PRINCIPAL = {"screening": SCREENING, "confirmation": CONFIRMATION, "policy": POLICY}


def matrix_plan(matrix, legacy):
    if matrix in PRINCIPAL:
        entries = [(run, H32 if legacy else EP08, FROZEN) for run in PRINCIPAL[matrix]]
    elif matrix == "mirror" and not legacy:
        entries = [(run, EP08, FROZEN) for pair in MIRROR for run in pair]
    elif matrix == "legacy-displacement" and not legacy:
        entries = [(run, H32, variant) for run in SCREENING if run.profile == "F6"
                   for variant in (FROZEN, EARLY_EXIT)]
    else:
        raise ValueError("invalid matrix and stream combination")
    return [{"run": asdict(run), "stream": stream, "resolver_variant": variant,
             "fixture_version": FIXTURE_VERSION, "profile_version": PROFILE_VERSION,
             "initial_fixture": "default"} for run, stream, variant in entries]


def identity(row):
    if row.get("initial_fixture") != "default":
        raise ValueError("execution requires the default fixture")
    return observation(row)


def validate_terminal(row):
    reason, winner = row.get("reason"), row.get("winner")
    if ((reason in ("mutual", "unresolved") and winner is None)
            or (reason in ("military", "objective") and type(winner) is int and winner in (0, 1))):
        return
    raise ValueError("observation is not a successful terminal battle")


def validate_completion(entry, row, roots):
    if identity(row) != identity(entry) or type(roots) is not int or roots < 1:
        raise ValueError("completed observation does not match planned identity")
    validate_terminal(row)
    for key in ("trace_sha256", "terminal_state_sha256"):
        if not isinstance(row.get(key), str) or re.fullmatch("[0-9a-f]{64}", row[key]) is None:
            raise ValueError(f"completed observation lacks a valid {key}")


class Journal:
    def __init__(self, path):
        self.path = path

    @classmethod
    def create(cls, path, matrix, legacy):
        plan = matrix_plan(matrix, legacy)
        return cls.create_for(path, {"schema": SCHEMA, "matrix": matrix, "legacy": legacy}, plan), plan

    @classmethod
    def create_for(cls, path, header, plan):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as output:
            output.write(canonical_json({**header, "plan": plan}) + "\n")
            output.flush()
            os.fsync(output.fileno())
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return cls(path)

    def append(self, record):
        with self.path.open("a+b") as output:
            fcntl.flock(output, fcntl.LOCK_EX)
            output.seek(-1, os.SEEK_END)
            if output.read(1) != b"\n":
                raise ValueError("execution journal has an unfinished trailing record")
            output.write((canonical_json(record) + "\n").encode())
            output.flush()
            os.fsync(output.fileno())

    def execute(self, index, entry, worker, validate=validate_completion):
        self.append({"event": "attempted", "index": index})
        try:
            row, roots = worker(entry)
            validate(entry, row, roots)
        except Exception as error:
            self.append({"event": "technical_stop", "index": index,
                         "reason": f"{type(error).__name__}: {error}"})
            raise
        self.append({"event": "completed", "index": index, "observation": row, "roots": roots})


@dataclass
class Execution:
    matrix: str
    plan: list
    attempted: set
    completed: dict
    stops: dict
    torn_tail: bool

    @property
    def complete(self):
        return not self.torn_tail and len(self.completed) == len(self.plan)

    @property
    def status(self):
        if self.torn_tail:
            return "torn_tail"
        return "complete" if self.complete else "partial"

    def observations(self):
        return [self.completed[i]["observation"] for i in sorted(self.completed)]

    def counts(self, indices):
        scope = set(indices)
        attempted = self.attempted & scope
        completed = self.completed.keys() & scope
        stopped = self.stops.keys() & scope
        return {
            "planned_runs": len(scope), "attempted_runs": len(attempted),
            "completed_runs": len(completed), "technical_stops": len(stopped),
            "unfinished_attempts": len(attempted - completed - stopped),
            "not_attempted_runs": len(scope - attempted),
        }

    def groups(self, rows):
        if self.matrix not in PRINCIPAL:
            raise ValueError("battle reports require a principal matrix execution")
        recorded = {identity(row): canonical_json(row) for row in self.observations()}
        supplied = {}
        for row in rows:
            key = identity(row)
            if key in supplied:
                raise ValueError("duplicate observation in execution reconciliation")
            supplied[key] = canonical_json(row)
        if supplied != recorded:
            raise ValueError("observations do not exactly reconcile with execution completions")
        groups = {}
        for i, entry in enumerate(self.plan):
            run, _ = identity(entry)
            groups.setdefault((run.profile, "/".join(run.policies)), []).append(i)
        return {group: self.counts(indices) for group, indices in groups.items()}

    def materialize(self):
        if not self.complete:
            raise ValueError("cannot publish an incomplete matrix")
        observations = self.observations()
        if self.matrix in PRINCIPAL:
            return observations
        pairs = []
        for i in range(0, len(observations), 2):
            left, right = observations[i:i+2]
            seed = left["run"]["seed"]
            if self.matrix == "legacy-displacement":
                pairs.append({"seed": seed, "frozen": left, "early_exit": right})
                continue
            if (left["trace_sha256"] != right["trace_sha256"]
                    or left["terminal_state_sha256"] != right["terminal_state_sha256"]
                    or self.completed[i]["roots"] != self.completed[i+1]["roots"]):
                raise ValueError(f"mirror divergence at seed {seed}")
            pairs.append({"seed": seed, "roots": self.completed[i]["roots"],
                          "trace_sha256": left["trace_sha256"]})
        return pairs


def reduced_plan(header):
    if (header.get("schema") != SCHEMA or type(header.get("legacy")) is not bool
            or not isinstance(header.get("matrix"), str)):
        raise ValueError("unsupported execution schema")
    return matrix_plan(header["matrix"], header["legacy"])


def load_execution(path):
    return load_journal(path, reduced_plan, validate_completion)


def load_journal(path, get_plan, validate):
    with path.open("rb") as source:
        fcntl.flock(source, fcntl.LOCK_SH)
        records = source.read().splitlines(keepends=True)
    if not records or not records[0].endswith(b"\n"):
        raise ValueError("missing execution plan")
    header = json.loads(records[0])
    if not isinstance(header, dict):
        raise ValueError("invalid execution header")
    plan = get_plan(header)
    if canonical_json(header.get("plan")) != canonical_json(plan):
        raise ValueError("execution plan differs from the declared matrix")
    attempted, completed, stops = set(), {}, {}
    torn_tail = not records[-1].endswith(b"\n")
    for line in records[1:-1] if torn_tail else records[1:]:
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("invalid execution record")
        index, event = record.get("index"), record.get("event")
        if type(index) is not int or not 0 <= index < len(plan):
            raise ValueError("unknown execution identity")
        if event == "attempted":
            if index in attempted:
                raise ValueError("duplicate attempt in one execution")
            attempted.add(index)
            continue
        if index not in attempted or index in completed or index in stops:
            raise ValueError("outcome without exactly one outstanding attempt")
        if event == "completed":
            if not isinstance(record.get("observation"), dict):
                raise ValueError("missing completed observation")
            validate(plan[index], record["observation"], record.get("roots"))
            completed[index] = record
        elif event == "technical_stop" and isinstance(record.get("reason"), str) and record["reason"]:
            stops[index] = record["reason"]
        else:
            raise ValueError("invalid execution outcome")
    return Execution(header["matrix"], plan, attempted, completed, stops, torn_tail)
