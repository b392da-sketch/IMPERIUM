"""Deterministic F01 development policy, replay, and executable manifest."""

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from statistics import mean

from ..events import canonical_json
from ..execution import Journal, load_journal
from ..geometry import OBJECTIVE, distance, front, step
from ..reporting import describe
from .fixture import FIXTURE_VERSION, PROFILE_VERSION
from .resolver import F01, TERRAINS, Order, Reaction

EXECUTION_SCHEMA = "F01-execution-v1"
POLICY = "centre-contest-v1"
MANIFEST = tuple({"variant": variant, "seed": seed, "mirrored": mirrored, "policy": POLICY}
                 for variant in TERRAINS for seed in range(22000, 22016) for mirrored in (False, True))


def choose_order(view, legal):
    positions = {u.identifier: u.position for u in view.formations}

    def rank(order):
        k = order.kind
        if k == "assault":
            return 0, distance(positions[order.target], OBJECTIVE)
        if k == "missile":
            return 1, distance(positions[order.target], OBJECTIVE)
        if k in ("group-move", "move"):
            if k == "group-move":
                changes = [(positions[i], step(positions[i], order.turn)) for i in order.members]
            else:
                changes = [(positions[order.members[0]], order.path[-1])]
            gains = [distance(start, OBJECTIVE) - distance(end, OBJECTIVE) for start, end in changes]
            if min(gains) > 0:
                return 2, -sum(gains)
        if k == "rally":
            return 3, distance(positions[order.members[0]], OBJECTIVE)
        if k == "rest":
            return 4, distance(positions[order.members[0]], OBJECTIVE)
        if k == "pivot":
            u = next(u for u in view.formations if u.identifier == order.members[0])
            before = min(distance(step(u.position, d), OBJECTIVE) for d in front(u.facing))
            after = min(distance(step(u.position, d), OBJECTIVE) for d in front(u.facing + order.turn))
            if after < before:
                return 5, after, abs(order.turn)
        if k == "withdraw":
            return 6, distance(order.path[0], OBJECTIVE)
        if k == "pass":
            return (7,)
        return (8,)

    ranks = [(rank(order), order) for order in legal]
    best = min(score for score, _ in ranks)
    preferred = tuple(order for score, order in ranks if score == best)
    return preferred[0], len(preferred)


def choose_reaction(view, options):
    return min(options, key=lambda r: (r.kind != "missile", r.source, r.target, r.turn))


def serialized(events):
    return "".join(canonical_json(event) + "\n" for event in events)


def summary(config, battle, choices):
    killed = sum(lot.casualties.killed for u in battle.units.values() for lot in u.losses)
    wounded = sum(lot.casualties.wounded for u in battle.units.values() for lot in u.losses)
    closures = [o for o in battle.objectives if o["stage"] == "closure"]
    streaks, longest, totals = [0, 0], [0, 0], [0, 0]
    for root in closures:
        for side in (0, 1):
            secure = root["secure"] == side
            totals[side] += secure
            streaks[side] = streaks[side] + 1 if secure else 0
            longest[side] = max(longest[side], streaks[side])
    return {
        "run": config, "fixture": FIXTURE_VERSION, "profile": PROFILE_VERSION,
        "stream": "D4-SHA256-v1", "trace_sha256": sha256(serialized(battle.events).encode()).hexdigest(),
        "terminal_state_sha256": battle.digest(), "rounds": battle.round, "elapsed": battle.elapsed,
        "terminal": battle.terminal, "objective": battle.objective(), "killed": killed, "wounded": wounded,
        "metrics": dict(battle.metrics), "round_three_exhaustion": battle.round_three_exhaustion,
        "secure_closures": totals, "longest_secure_streak": longest, "choices": choices,
    }


def simulate(config, expected=None, on_failure=None):
    if config.get("policy") != POLICY:
        raise ValueError("unknown F01 policy")
    battle = F01(config["seed"], config["variant"], mirrored=config["mirrored"])
    counts = []
    if expected is not None and (not expected or canonical_json(battle.events[0]) != canonical_json(expected[0])):
        raise ValueError("F01 initial state mismatch")
    while not battle.terminal:
        legal = battle.legal_orders()
        order, preferred = choose_order(battle.observe(battle.side), legal)
        counts.append((len(legal), preferred))
        react = choose_reaction
        if expected is not None:
            if len(expected) <= len(battle.events):
                raise ValueError("incomplete F01 replay")
            event = expected[len(battle.events)]
            if canonical_json(event["order"]) != canonical_json(battle.normalized_order(order)):
                raise ValueError("F01 replay order mismatch")
            responses = [stage["decision"] for stage in event["stages"] if stage["kind"] == "reaction"]

            def react(view, options):
                if not responses:
                    raise ValueError("missing F01 response")
                decision = responses.pop(0)
                selected = Reaction(**decision) if decision is not None else None
                if canonical_json(decision) != canonical_json(vars(choose_reaction(view, options))):
                    raise ValueError("F01 replay response mismatch")
                return selected

        try:
            battle.resolve(order, react)
        except BaseException:
            if on_failure is not None:
                on_failure(battle, order)
            raise
        if expected is not None and canonical_json(battle.events[-1]) != canonical_json(event):
            raise ValueError(f"F01 replay event mismatch at root {battle.root}")
    if expected is not None and len(expected) != len(battle.events):
        raise ValueError("extra F01 replay roots")
    return summary(config, battle, counts), battle.events


def get_plan(header):
    if header.get("schema") != EXECUTION_SCHEMA or header.get("matrix") != "development":
        raise ValueError("unknown F01 execution journal")
    return list(MANIFEST)


def validate(entry, row, roots):
    if (canonical_json(entry) != canonical_json(row.get("run")) or type(roots) is not int
            or roots < 1 or row.get("fixture") != FIXTURE_VERSION or row.get("profile") != PROFILE_VERSION
            or row.get("stream") != "D4-SHA256-v1" or not row.get("terminal")):
        raise ValueError("invalid F01 observation provenance")


def verify(directory):
    execution = load_journal(directory / "development.execution.jsonl", get_plan, validate)
    if not execution.complete:
        raise ValueError("incomplete F01 execution")
    rows = execution.observations()
    for row in rows:
        archived = (directory / trace_name(row["run"])).read_bytes()
        if sha256(archived).hexdigest() != row["trace_sha256"]:
            raise ValueError(f"F01 trace digest mismatch: {row['run']}")
    for left, right in zip(rows[::2], rows[1::2], strict=True):
        if left["trace_sha256"] != right["trace_sha256"] or (
            left["terminal_state_sha256"] != right["terminal_state_sha256"]
        ):
            raise AssertionError(f"F01 physical mirror divergence: {left['run']}")
    return execution


def run_matrix(directory):
    directory.mkdir(parents=True, exist_ok=True)
    journal = Journal.create_for(directory / "development.execution.jsonl",
                                 {"schema": EXECUTION_SCHEMA, "matrix": "development"}, list(MANIFEST))

    def worker(config):
        def failed(battle, order):
            (directory / (trace_name(config) + ".failure")).write_text(serialized([
                *battle.events, {"kind": "failed-root", "root": battle.root,
                                 "order": battle.normalized_order(order),
                                 "stages": battle.stages, "state": battle.digest()},
            ]))

        row, events = simulate(config, on_failure=failed)
        (directory / trace_name(config)).write_text(serialized(events))
        return row, len(events) - 1

    for index, config in enumerate(MANIFEST):
        journal.execute(index, config, worker, validate)
        if index % 2:
            execution = load_journal(journal.path, get_plan, validate)
            original, transformed = [execution.completed[i]["observation"] for i in (index-1, index)]
            if original["trace_sha256"] != transformed["trace_sha256"]:
                raise AssertionError(f"F01 mirror divergence: {config}")
    execution = verify(directory)
    (directory / "report.json").write_text(json.dumps(aggregate(execution), indent=2, sort_keys=True) + "\n")


def trace_name(config):
    return f"{config['variant']}-{config['seed']}-{int(config['mirrored'])}.jsonl"


def aggregate(execution):
    result = {}
    for variant in TERRAINS:
        indices = [i for i, run in enumerate(execution.plan)
                   if run["variant"] == variant and not run["mirrored"]]
        group = [execution.completed[i]["observation"] for i in indices]
        n = len(group)
        unresolved = sum(row["terminal"]["reason"] == "unresolved" for row in group)
        p = unresolved / n
        z = 1.959963984540054
        center = (p + z*z/(2*n)) / (1 + z*z/n)
        margin = z * (p*(1-p)/n + z*z/(4*n*n))**.5 / (1 + z*z/n)
        result[variant] = {
            **execution.counts(indices), "unresolved": unresolved,
            "terminal_reasons": dict(Counter(row["terminal"]["reason"] for row in group)),
            "winners": dict(Counter(str(row["terminal"]["winner"]) for row in group)),
            "objective_classification": dict(Counter(row["objective"]["classification"] for row in group)),
            "mean_rounds": mean(row["rounds"] for row in group),
            "metrics": {metric: sum(row["metrics"].get(metric, 0) for row in group)
                        for metric in sorted({key for row in group for key in row["metrics"]})},
            "unresolved_wilson95": [max(0, center - margin), min(1, center + margin)],
            "bm07_warning": p > .75,
            "losses": describe(row["killed"] + row["wounded"] for row in group),
            "mean_legal_choices": mean(value[0] for row in group for value in row["choices"]),
            "mean_preferred_choices": mean(value[1] for row in group for value in row["choices"]),
        }
    return result


def replay(directory):
    for archived in verify(directory).observations():
        expected = [json.loads(line) for line in (directory / trace_name(archived["run"])).read_text().splitlines()]
        rerun, _ = simulate(archived["run"], expected)
        if canonical_json(rerun) != canonical_json(archived):
            raise ValueError(f"F01 replay summary mismatch: {archived['run']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("matrix", "verify", "replay"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.operation == "matrix":
        run_matrix(args.directory)
    elif args.operation == "verify":
        print(f"verified {len(verify(args.directory).completed)} executions")
    else:
        replay(args.directory)
        print("verified F01 journals and deterministic summaries")


if __name__ == "__main__":
    main()
