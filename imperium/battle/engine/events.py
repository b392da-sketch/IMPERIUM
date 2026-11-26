"""Layer E4a: immutable P3 event records, stage snapshots, the canonical
effect diff and canonical stage data (P3 contract rev 0.3 section 5,
errata ER02 and ER04).

Records hold only immutable values: canonical JSON bytes for data and
effect values, exact tuples of exact records, and P1 values in snapshots.
Nothing here constructs or validates a stable state.
"""

import json
from dataclasses import dataclass

from imperium.battle import InvalidValue
from imperium.battle.canon import SCHEMA, canonical_bytes_of, project, project_fields
from imperium.battle.invariants import ROOT_SPEC
from imperium.battle.records import STATE_FIELDS
from imperium.battle.values import INT_DOMAIN, TerminationPoint

from .commands import (
    Accepted, Capitulate, DeclareWithdrawal, HoldOrder, OpenBattle, PassOrder, Stage,
    check_command, command_digest,
)
from .draws import INDEX_MAX, NUMERATOR_LIMIT, Channel, parse_stage_id

EVENT_SCHEMA = "imperium.battle-event/1"

CHECK_POINTS = {
    Stage.INITIAL_CHECK: TerminationPoint.INITIAL_CHECK,
    Stage.IMMEDIATE_CHECK: TerminationPoint.AFTER_ROOT,
    Stage.CLOSURE_CHECK: TerminationPoint.AFTER_CLOSURE_DISPLACEMENT,
    Stage.END_CHECK: TerminationPoint.ROUND_END,
}
NO_OP_STAGES = (Stage.CLOSURE_DISPLACEMENT, Stage.RECOVERY)
CLOSURE_KINDS = (Stage.CLOSURE_DISPLACEMENT, Stage.CLOSURE_CHECK, Stage.RECOVERY,
                 Stage.ADVANCE, Stage.END_CHECK)
USE_OF = {HoldOrder: "INDIVIDUAL", PassOrder: "PASS", DeclareWithdrawal: "POSTURE_WITHDRAWAL",
          Capitulate: None}


def _fail(code, path, detail):
    raise InvalidValue(code, path, detail)


# --------------------------------------------------------------------------
# Canonical JSON values


def _reject_constant(token):
    raise ValueError(f"non-finite token {token}")


def _reject_float(token):
    raise ValueError(f"float token {token}")


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise ValueError("duplicate key")
        out[k] = v
    return out


def _in_domain(tree):
    stack = [tree]
    while stack:
        v = stack.pop()
        t = type(v)
        if t is int and not -INT_DOMAIN - 1 <= v <= INT_DOMAIN:
            return False
        if t is list:
            stack.extend(v)
        elif t is dict:
            stack.extend(v.values())
    return True


def canonical_tree(data, path, require_object=False):
    """The primitive tree of exact canonical JSON bytes; T15/T16 at ``path``."""
    if type(data) is not bytes:
        _fail("T15", path, "expected bytes")
    try:
        tree = json.loads(data.decode("ascii"), object_pairs_hook=_pairs,
                          parse_float=_reject_float, parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        _fail("T16", path, "not canonical JSON")
    if require_object and type(tree) is not dict:
        _fail("T16", path, "expected a JSON object")
    if not _in_domain(tree) or canonical_bytes_of(tree) != data:
        _fail("T16", path, "not canonical JSON")
    return tree


def value_bytes(tree):
    return canonical_bytes_of(tree)


# --------------------------------------------------------------------------
# JSON pointers and the canonical diff (5.2)


def escape(segment):
    return segment.replace("~", "~0").replace("/", "~1")


def pointer(segments):
    return "".join("/" + (escape(s) if type(s) is str else str(s)) for s in segments)


def split_pointer(text):
    """Typed segments of a canonical pointer, or None if malformed."""
    if text == "" or not text.startswith("/"):
        return None
    out = []
    for raw in text[1:].split("/"):
        i = 0
        while True:
            i = raw.find("~", i)
            if i < 0:
                break
            if raw[i + 1:i + 2] not in ("0", "1"):
                return None
            i += 2
        out.append(raw.replace("~1", "/").replace("~0", "~"))
    return out


def same(a, b):
    """Type-sensitive equality by canonical bytes."""
    return a is b or canonical_bytes_of(a) == canonical_bytes_of(b)


def diff(a, b, segments=()):
    """Canonical effects turning tree ``a`` into tree ``b``: a list of
    ``(segments, old, new)`` in typed-segment order."""
    if a is b:
        return []
    ta, tb = type(a), type(b)
    if ta is dict and tb is dict and a.keys() == b.keys():
        out = []
        for k in sorted(a):
            out.extend(diff(a[k], b[k], segments + (k,)))
        return out
    if ta is list and tb is list and len(a) == len(b):
        out = []
        for i in range(len(a)):
            out.extend(diff(a[i], b[i], segments + (i,)))
        return out
    if same(a, b):
        return []
    return [(segments, a, b)]


def _segment_key(segments):
    """Typed order: canonical decimal segments numerically, others by ASCII."""
    out = []
    for s in segments:
        if type(s) is int:
            out.append((0, s, ""))
        elif s.isdigit() and (s == "0" or s[0] != "0"):
            out.append((0, int(s), ""))
        else:
            out.append((1, 0, s))
    return tuple(out)


# --------------------------------------------------------------------------
# Records


@dataclass(frozen=True, slots=True)
class Effect:
    path: str
    old: bytes
    new: bytes

    def __post_init__(self):
        if type(self.path) is not str:
            _fail("T15", "path", "expected str")
        if split_pointer(self.path) is None:
            _fail("T16", "path", "not a canonical JSON pointer")
        canonical_tree(self.old, "old")
        canonical_tree(self.new, "new")
        if self.old == self.new:
            _fail("T16", "new", "no-op replacement")


@dataclass(frozen=True, slots=True)
class DrawRecord:
    channel: Channel
    index: int
    numerator: int

    def __post_init__(self):
        if type(self.channel) is not Channel:
            _fail("T15", "channel", "expected Channel")
        for name, value, high in (("index", self.index, INDEX_MAX),
                                  ("numerator", self.numerator, NUMERATOR_LIMIT - 1)):
            if type(value) is not int:
                _fail("T15", name, "expected int")
            if not 0 <= value <= high:
                _fail("T10", name, f"outside 0..{high}")


def _check_id(stage, stage_id):
    if type(stage) is not Stage:
        _fail("T15", "stage", "expected Stage")
    if type(stage_id) is not str:
        _fail("T15", "stage_id", "expected str")
    try:
        key = parse_stage_id(stage_id)
    except InvalidValue:
        _fail("T16", "stage_id", "malformed stage id")
    if key.kind != stage.name:
        _fail("T16", "stage_id", "stage and id disagree")


def _check_members(value, cls, path):
    if type(value) is not tuple:
        _fail("T15", path, "expected tuple")
    for i, item in enumerate(value):
        if type(item) is not cls:
            _fail("T15", f"{path}/{i}", f"expected {cls.__name__}")


@dataclass(frozen=True, slots=True)
class StageEvent:
    stage: Stage
    stage_id: str
    data: bytes
    effects: tuple
    draws: tuple

    def __post_init__(self):
        _check_id(self.stage, self.stage_id)
        canonical_tree(self.data, "data", require_object=True)
        _check_members(self.effects, Effect, "effects")
        _check_members(self.draws, DrawRecord, "draws")
        keys = [_segment_key(split_pointer(e.path)) for e in self.effects]
        for i in range(1, len(keys)):
            prev, cur = keys[i - 1], keys[i]
            if not prev < cur or cur[:len(prev)] == prev:
                _fail("T16", "effects", "effects not in canonical order or overlapping")
        if self.draws:
            _fail("T16", "draws", "audit v1 events carry no draws")


@dataclass(frozen=True, slots=True)
class StageSnapshot:
    stage: Stage
    stage_id: str
    values: tuple

    def __post_init__(self):
        _check_id(self.stage, self.stage_id)
        if type(self.values) is not tuple:
            _fail("T15", "values", "expected tuple")
        if len(self.values) != len(STATE_FIELDS):
            _fail("T04", "values", f"expected {len(STATE_FIELDS)} field values")
        for (name, kind), value in zip(ROOT_SPEC, self.values):
            failure = kind.check(value, f"values/{name}")
            if failure is not None:
                raise InvalidValue(*failure)

    def document(self):
        """A fresh primitive document of the snapshot (P1 13.5 projection)."""
        return project_fields(self.values)


def _digest(value, path):
    if type(value) is not str:
        _fail("T15", path, "expected str")
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        _fail("T16", path, "expected a lowercase SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class RootRecord:
    cursor: int
    command: object
    command_digest: str
    previous: str
    current: str
    events: tuple

    def __post_init__(self):
        if type(self.cursor) is not int:
            _fail("T15", "cursor", "expected int")
        if not 1 <= self.cursor <= INT_DOMAIN:
            _fail("T10", "cursor", "outside 1..INT_DOMAIN")
        check_command(self.command)
        for name in ("command_digest", "previous", "current"):
            _digest(getattr(self, name), name)
        if self.command_digest != command_digest(self.command):
            _fail("T16", "command_digest", "does not match the command")
        _check_members(self.events, StageEvent, "events")
        if not self.events:
            _fail("T16", "events", "a root has at least one event")
        ids = [e.stage_id for e in self.events]
        if len(set(ids)) != len(ids):
            _fail("T16", "events", "repeated stage id")


@dataclass(frozen=True, slots=True)
class Resolved:
    accepted: Accepted
    record: RootRecord
    snapshots: tuple

    def __post_init__(self):
        if type(self.accepted) is not Accepted:
            _fail("T15", "accepted", "expected Accepted")
        if type(self.record) is not RootRecord:
            _fail("T15", "record", "expected RootRecord")
        _check_members(self.snapshots, StageSnapshot, "snapshots")
        events = self.record.events
        if len(events) != len(self.snapshots) or any(
                (e.stage, e.stage_id) != (s.stage, s.stage_id)
                for e, s in zip(events, self.snapshots)):
            _fail("T16", "snapshots", "snapshots and events disagree")
        if tuple(s.stage for s in self.snapshots) != self.accepted.stages:
            _fail("T16", "snapshots", "snapshots and accepted stages disagree")


# --------------------------------------------------------------------------
# Producer: stage ids, data and records from planned stage values


def _side_uses(ledger, side):
    return sum(1 for u in ledger.uses if u.side is side)


def stage_ids(values, command, stages):
    """Contextual BK-1 ids, all from the pre-root values (4.3)."""
    clock = values["clock"]
    if type(command) is OpenBattle:
        return tuple(f"r0:IN:{s.name}" for s in stages)
    rnd = clock.completed_rounds + 1
    principal = f"r{rnd}:{command.side.name}.o{_side_uses(values['ledger'], command.side) + 1}"
    closure = f"r{rnd}:CL"
    out = []
    in_closure = False
    for s in stages:
        if s in CLOSURE_KINDS:
            in_closure = True
        if s is Stage.OPEN_ROUND:
            in_closure = True
        out.append(f"{closure if in_closure else principal}:{s.name}")
    return tuple(out)


def _data(stage, command, after, next_stage):
    if stage in CHECK_POINTS:
        doc = {"point": CHECK_POINTS[stage].name,
               "result": "TERMINAL" if next_stage is Stage.TERMINAL else "CONTINUE"}
    elif stage is Stage.ROOT:
        t = type(command)
        doc = {"kind": t.__name__, "side": command.side.name,
               "formation": command.formation.token if t is HoldOrder else None,
               "use": USE_OF[t]}
    elif stage in NO_OP_STAGES:
        doc = {"applied": []}
    elif stage is Stage.ADVANCE:
        doc = {"completed": after["clock"].completed_rounds}
    elif stage is Stage.OPEN_ROUND:
        doc = {"round": after["clock"].completed_rounds + 1, "first": after["phase"].side.name}
    else:  # TERMINAL
        doc = {"record": project(after["phase"].record)}
    return canonical_bytes_of(doc)


class _Projector:
    """Per-field projection reusing identical field values (identity)."""

    def __init__(self):
        self._cache = {}

    def document(self, values):
        doc = {"schema": SCHEMA}
        for name in STATE_FIELDS:
            value = values[name]
            hit = self._cache.get(name)
            if hit is not None and hit[0] is value:
                doc[name] = hit[1]
            else:
                tree = project(value)
                self._cache[name] = (value, tree)
                doc[name] = tree
        return doc


def build_root(before, command, stages, stage_values, previous, current):
    """The ``RootRecord`` and snapshots of one accepted root.

    ``before`` and every ``stage_values`` entry are dicts of the eleven
    field values; every stage value already carries the new cursor.
    """
    ids = stage_ids(before, command, stages)
    projector = _Projector()
    prev_doc = projector.document(before)
    events, snapshots = [], []
    for i, (stage, sid, values) in enumerate(zip(stages, ids, stage_values)):
        doc = projector.document(values)
        effects = tuple(Effect(pointer(seg), canonical_bytes_of(old), canonical_bytes_of(new))
                        for seg, old, new in diff(prev_doc, doc))
        nxt = stages[i + 1] if i + 1 < len(stages) else None
        events.append(StageEvent(stage, sid, _data(stage, command, values, nxt), effects, ()))
        snapshots.append(StageSnapshot(stage, sid, tuple(values[n] for n in STATE_FIELDS)))
        prev_doc = doc
    record = RootRecord(
        cursor=stage_values[-1]["clock"].event_cursor, command=command,
        command_digest=command_digest(command), previous=previous, current=current,
        events=tuple(events))
    return record, tuple(snapshots)
