"""Layer E0: P2 command records, result records, stage and rejection
tokens, and the canonical command document (P2 contract 3, 3.1).

No command carries a cost, charge, effort, ledger, use, flag or state
fragment; every expenditure is derived by ``step``. Records validate
exact field types in ``__post_init__`` and are frozen with slots.
"""

import json
from dataclasses import dataclass
from enum import Enum

from imperium.battle import BattleState, FixtureId, FormationId, GroupId, InvalidValue, Side
from imperium.battle.canon import canonical_bytes_of, sha256_hex
from imperium.battle.ids import valid_token
from imperium.battle.values import EnumK, Hex, IdK, Int, Str

COMMAND_SCHEMA = "imperium.battle-command/1"


class Stage(Enum):
    INITIAL_CHECK = "INITIAL_CHECK"
    ROOT = "ROOT"
    IMMEDIATE_CHECK = "IMMEDIATE_CHECK"
    CLOSURE_DISPLACEMENT = "CLOSURE_DISPLACEMENT"
    CLOSURE_CHECK = "CLOSURE_CHECK"
    RECOVERY = "RECOVERY"
    ADVANCE = "ADVANCE"
    END_CHECK = "END_CHECK"
    OPEN_ROUND = "OPEN_ROUND"
    TERMINAL = "TERMINAL"
    # P4 principal-root kinds (contract rev 0.2 section 10.1); never draw-bearing.
    STEP1 = "STEP1"
    STEP2 = "STEP2"
    STEP3 = "STEP3"
    WITHDRAW = "WITHDRAW"
    GROUP_STEP = "GROUP_STEP"
    PIVOT = "PIVOT"
    GROUP_PIVOT = "GROUP_PIVOT"
    EVACUATE = "EVACUATE"
    WINDOW = "WINDOW"
    RESPONSE = "RESPONSE"


P2_STAGES = (Stage.INITIAL_CHECK, Stage.ROOT, Stage.IMMEDIATE_CHECK, Stage.CLOSURE_DISPLACEMENT,
             Stage.CLOSURE_CHECK, Stage.RECOVERY, Stage.ADVANCE, Stage.END_CHECK,
             Stage.OPEN_ROUND, Stage.TERMINAL)
P4_STAGES = (Stage.STEP1, Stage.STEP2, Stage.STEP3, Stage.WITHDRAW, Stage.GROUP_STEP,
             Stage.PIVOT, Stage.GROUP_PIVOT, Stage.EVACUATE, Stage.WINDOW, Stage.RESPONSE)
STEP_STAGES = (Stage.STEP1, Stage.STEP2, Stage.STEP3)


class RejectCode(Enum):
    PHASE = "PHASE"
    WRONG_SIDE = "WRONG_SIDE"
    UNKNOWN_FORMATION = "UNKNOWN_FORMATION"
    NOT_OWN_FORMATION = "NOT_OWN_FORMATION"
    NOT_READY = "NOT_READY"
    ALREADY_WITHDRAWING = "ALREADY_WITHDRAWING"
    NO_ONMAP_AVAILABLE = "NO_ONMAP_AVAILABLE"
    # P4 (contract rev 0.2 section 4.5, E06)
    NOT_ORGANIZED = "NOT_ORGANIZED"
    CONDITION = "CONDITION"
    ENGAGED = "ENGAGED"
    THREATENED_ORIGIN = "THREATENED_ORIGIN"
    PIVOT_RESTRICTED = "PIVOT_RESTRICTED"
    BAD_VALUE = "BAD_VALUE"
    OFF_BOARD = "OFF_BOARD"
    REPEATED_CELL = "REPEATED_CELL"
    NOT_ADJACENT = "NOT_ADJACENT"
    NOT_FRONT = "NOT_FRONT"
    NOT_REAR = "NOT_REAR"
    IMPASSABLE = "IMPASSABLE"
    OCCUPIED = "OCCUPIED"
    THREATENED_DESTINATION = "THREATENED_DESTINATION"
    OVER_CAP = "OVER_CAP"
    OVER_EFFORT = "OVER_EFFORT"
    PAST_STOP = "PAST_STOP"
    NO_EXIT_PROGRESS = "NO_EXIT_PROGRESS"
    NOT_ON_EXIT = "NOT_ON_EXIT"
    EXIT_UNSAFE = "EXIT_UNSAFE"
    UNKNOWN_GROUP = "UNKNOWN_GROUP"
    NOT_OWN_GROUP = "NOT_OWN_GROUP"
    NO_AUTHORITY = "NO_AUTHORITY"
    NOT_IN_GROUP = "NOT_IN_GROUP"
    NOT_CONNECTED = "NOT_CONNECTED"
    PENDING_WINDOW = "PENDING_WINDOW"
    STALE_WINDOW = "STALE_WINDOW"
    NOT_OFFERED = "NOT_OFFERED"


# Fixed (path, detail) of every rejection except NOT_READY, whose detail is
# the activation name (contract 3).
REJECT_TEXT = {
    RejectCode.PHASE: ("", "command is not admissible in this phase"),
    RejectCode.WRONG_SIDE: ("/side", "side does not have the current opportunity"),
    RejectCode.UNKNOWN_FORMATION: ("/formation", "formation is not in the roster"),
    RejectCode.NOT_OWN_FORMATION: ("/formation", "formation does not belong to the command side"),
    RejectCode.ALREADY_WITHDRAWING: ("/side", "side is already withdrawing"),
    RejectCode.NO_ONMAP_AVAILABLE: ("/side", "side has no on-map available personnel"),
}
NOT_READY_PATH = "/formation"

# Exact P4 details (REJECTION_ORACLES.json, E06); the path varies by field
# and index and is chosen at admission.
P4_DETAIL = {
    RejectCode.NOT_ORGANIZED: "formation is not organized",
    RejectCode.CONDITION: "group member exceeds the condition gate",
    RejectCode.ENGAGED: "formation is engaged",
    RejectCode.THREATENED_ORIGIN: "formation starts in hostile threat",
    RejectCode.PIVOT_RESTRICTED: "pivot restricted by hostile threat",
    RejectCode.BAD_VALUE: "invalid command value",
    RejectCode.OFF_BOARD: "cell is not on the board",
    RejectCode.REPEATED_CELL: "path repeats a cell",
    RejectCode.NOT_ADJACENT: "cell is not adjacent",
    RejectCode.NOT_FRONT: "step is not in the front directions",
    RejectCode.NOT_REAR: "step is not in the rear directions",
    RejectCode.IMPASSABLE: "directed entry is not traversable",
    RejectCode.OCCUPIED: "cell is occupied",
    RejectCode.THREATENED_DESTINATION: "destination is in hostile threat",
    RejectCode.OVER_CAP: "path exceeds the step cap",
    RejectCode.OVER_EFFORT: "planned debit exceeds remaining effort",
    RejectCode.PAST_STOP: "path continues past a predicted stop",
    RejectCode.NO_EXIT_PROGRESS: "step does not reduce exit distance",
    RejectCode.NOT_ON_EXIT: "formation is not on its exit row",
    RejectCode.EXIT_UNSAFE: "exit is not recovery-safe",
    RejectCode.UNKNOWN_GROUP: "group is not in the scenario",
    RejectCode.NOT_OWN_GROUP: "group does not belong to the command side",
    RejectCode.NO_AUTHORITY: "group authority is not active",
    RejectCode.NOT_IN_GROUP: "formation is not a member of the group",
    RejectCode.NOT_CONNECTED: "selected members are not connected",
    RejectCode.PENDING_WINDOW: "a response window is pending",
    RejectCode.STALE_WINDOW: "decision is bound to another window",
    RejectCode.NOT_OFFERED: "decision is not an offered option",
}


def _check(kind, value, path):
    failure = kind.check(value, path)
    if failure is not None:
        raise InvalidValue(*failure)


_SIDE = EnumK(Side)
_FID = IdK(FormationId)


# --------------------------------------------------------------------------
# Commands


@dataclass(frozen=True, slots=True)
class OpenBattle:
    """The initial assessment; admissible only in Opening."""


@dataclass(frozen=True, slots=True)
class HoldOrder:
    side: Side
    formation: FormationId

    def __post_init__(self):
        _check(_SIDE, self.side, "side")
        _check(_FID, self.formation, "formation")


@dataclass(frozen=True, slots=True)
class PassOrder:
    side: Side

    def __post_init__(self):
        _check(_SIDE, self.side, "side")


@dataclass(frozen=True, slots=True)
class DeclareWithdrawal:
    side: Side

    def __post_init__(self):
        _check(_SIDE, self.side, "side")


@dataclass(frozen=True, slots=True)
class Capitulate:
    side: Side

    def __post_init__(self):
        _check(_SIDE, self.side, "side")


# --------------------------------------------------------------------------
# P4 principal orders and window decisions (contract rev 0.2 sections 4.1,
# 4.2). Constructors check exact types only, T15 at the field or
# ``field/index``; ranges and order are admission rules (BAD_VALUE).


def _t15(path, detail):
    raise InvalidValue("T15", path, detail)


def _exact(value, cls, path):
    if type(value) is not cls:
        _t15(path, f"expected {cls.__name__}")


def _exact_tuple(value, cls, path):
    if type(value) is not tuple:
        _t15(path, "expected tuple")
    for i, item in enumerate(value):
        if type(item) is not cls:
            _t15(f"{path}/{i}", f"expected {cls.__name__}")


@dataclass(frozen=True, slots=True)
class MoveOrder:
    side: Side
    formation: FormationId
    path: tuple

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.formation, FormationId, "formation")
        _exact_tuple(self.path, Hex, "path")


@dataclass(frozen=True, slots=True)
class PivotOrder:
    side: Side
    formation: FormationId
    turn: int
    steps: int

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.formation, FormationId, "formation")
        _exact(self.turn, int, "turn")
        _exact(self.steps, int, "steps")


@dataclass(frozen=True, slots=True)
class WithdrawOrder:
    side: Side
    formation: FormationId
    destination: Hex

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.formation, FormationId, "formation")
        _exact(self.destination, Hex, "destination")


@dataclass(frozen=True, slots=True)
class EvacuateOrder:
    side: Side
    formation: FormationId

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.formation, FormationId, "formation")


@dataclass(frozen=True, slots=True)
class GroupMoveOrder:
    side: Side
    group: GroupId
    members: tuple
    direction: int

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.group, GroupId, "group")
        _exact_tuple(self.members, FormationId, "members")
        _exact(self.direction, int, "direction")


@dataclass(frozen=True, slots=True)
class GroupPivotOrder:
    side: Side
    group: GroupId
    members: tuple
    turn: int

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.group, GroupId, "group")
        _exact_tuple(self.members, FormationId, "members")
        _exact(self.turn, int, "turn")


@dataclass(frozen=True, slots=True)
class RespondPivot:
    side: Side
    window_id: str
    formation: FormationId
    target: FormationId

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.window_id, str, "window_id")
        _exact(self.formation, FormationId, "formation")
        _exact(self.target, FormationId, "target")


@dataclass(frozen=True, slots=True)
class RespondMissile:
    side: Side
    window_id: str
    formation: FormationId
    target: FormationId

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.window_id, str, "window_id")
        _exact(self.formation, FormationId, "formation")
        _exact(self.target, FormationId, "target")


@dataclass(frozen=True, slots=True)
class DeclineResponse:
    side: Side
    window_id: str

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.window_id, str, "window_id")


P2_COMMAND_CLASSES = (OpenBattle, HoldOrder, PassOrder, DeclareWithdrawal, Capitulate)
P4_PRINCIPAL_CLASSES = (MoveOrder, PivotOrder, WithdrawOrder, EvacuateOrder, GroupMoveOrder,
                        GroupPivotOrder)
DECISION_CLASSES = (RespondPivot, RespondMissile, DeclineResponse)
PRINCIPAL_CLASSES = P2_COMMAND_CLASSES + P4_PRINCIPAL_CLASSES
COMMAND_CLASSES = PRINCIPAL_CLASSES + DECISION_CLASSES
Command = (OpenBattle | HoldOrder | PassOrder | DeclareWithdrawal | Capitulate | MoveOrder
           | PivotOrder | WithdrawOrder | EvacuateOrder | GroupMoveOrder | GroupPivotOrder
           | RespondPivot | RespondMissile | DeclineResponse)
GROUP_CLASSES = (GroupMoveOrder, GroupPivotOrder)

# Variant keys of the command document, in declaration order (3.1; P4 10.4).
_COMMAND_KEYS = (
    (OpenBattle, ()),
    (HoldOrder, ("side", "formation")),
    (PassOrder, ("side",)),
    (DeclareWithdrawal, ("side",)),
    (Capitulate, ("side",)),
    (MoveOrder, ("side", "formation", "path")),
    (PivotOrder, ("side", "formation", "turn", "steps")),
    (WithdrawOrder, ("side", "formation", "destination")),
    (EvacuateOrder, ("side", "formation")),
    (GroupMoveOrder, ("side", "group", "members", "direction")),
    (GroupPivotOrder, ("side", "group", "members", "turn")),
    (RespondPivot, ("side", "window_id", "formation", "target")),
    (RespondMissile, ("side", "window_id", "formation", "target")),
    (DeclineResponse, ("side", "window_id")),
)


def check_command(command):
    """Raise T15 at ``command`` unless it is exactly one of the fourteen classes."""
    t = type(command)
    for cls in COMMAND_CLASSES:
        if t is cls:
            return
    raise InvalidValue("T15", "command", "not a command")


def is_p4_principal(command):
    return type(command) in P4_PRINCIPAL_CLASSES


def is_decision(command):
    return type(command) in DECISION_CLASSES


def is_state(value):
    return type(value) is BattleState


def check_state(state):
    """Raise V00 at ``state`` unless it is exactly a ``BattleState``."""
    if type(state) is not BattleState:
        raise InvalidValue("V00", "state", "not a BattleState")


def _token(value):
    t = type(value)
    if t is Side:
        return value.name
    if t is Hex:
        return [value.q, value.r]
    if t is tuple:
        return [_token(v) for v in value]
    if t is int or t is str:
        return value
    return value.token


def encode_command(command):
    """A fresh primitive document of ``command`` (3.1)."""
    check_command(command)
    t = type(command)
    doc = {"schema": COMMAND_SCHEMA, "kind": t.__name__}
    for cls, keys in _COMMAND_KEYS:
        if t is cls:
            break
    for name in keys:
        doc[name] = _token(getattr(command, name))
    return doc


def command_bytes(command):
    """Canonical P1 13.4 JSON bytes of the command document."""
    return canonical_bytes_of(encode_command(command))


def command_digest(command):
    """Lowercase-hex SHA-256 of the canonical command bytes."""
    return sha256_hex(command_bytes(command))


COMMAND_MAX_BYTES = 1024


def _no_duplicates(items):
    out = {}
    for k, v in items:
        if k in out:
            raise ValueError("duplicate key")
        out[k] = v
    return out


def _no_float(token):
    raise ValueError("float")


def decode_command(data):
    """The command whose canonical bytes are exactly ``data`` (P3 6).

    Anything else, including a wrong argument type, raises T15 at
    ``command``. No fixture-legality check is made.
    """
    def bad(detail):
        raise InvalidValue("T15", "command", detail)

    if type(data) is not bytes:
        bad("expected bytes")
    if len(data) > COMMAND_MAX_BYTES:
        bad("command body exceeds 1 KiB")
    try:
        doc = json.loads(data.decode("ascii"), object_pairs_hook=_no_duplicates,
                         parse_float=_no_float, parse_constant=_no_float)
    except (ValueError, UnicodeDecodeError, RecursionError):
        bad("not canonical command JSON")
    if type(doc) is not dict or doc.get("schema") != COMMAND_SCHEMA:
        bad("not a command document")
    for cls, keys in _COMMAND_KEYS:
        if doc.get("kind") == cls.__name__:
            break
    else:
        bad("unknown command kind")
    if set(doc) != {"schema", "kind", *keys}:
        bad("wrong command keys")
    args = {}
    for name in keys:
        args[name] = _decode_field(name, doc[name], bad)
    command = cls(**args)
    if command_bytes(command) != data:
        bad("not the canonical command bytes")
    return command


_HEX_DIGITS = frozenset("0123456789abcdef")


def window_token_ok(text):
    """Exactly 64 lowercase ASCII hex characters (ER02)."""
    return type(text) is str and len(text) == 64 and all(c in _HEX_DIGITS for c in text)


def _decode_cell(value, bad):
    if type(value) is not list or len(value) != 2 or any(type(v) is not int for v in value):
        bad("a cell is a two-element integer array")
    return Hex(value[0], value[1])


def _decode_field(name, value, bad):
    if name in ("turn", "steps", "direction"):
        if type(value) is not int:
            bad(f"{name} must be an integer")
        return value
    if name == "path":
        if type(value) is not list:
            bad("path must be an array")
        return tuple(_decode_cell(v, bad) for v in value)
    if name == "destination":
        return _decode_cell(value, bad)
    if name == "members":
        if type(value) is not list:
            bad("members must be an array")
        out = []
        for v in value:
            if not valid_token(v):
                bad("invalid member token")
            out.append(FormationId(v))
        return tuple(out)
    if type(value) is not str:
        bad(f"{name} must be a string")
    if name == "side":
        if value not in Side.__members__:
            bad("unknown side")
        return Side[value]
    if name == "window_id":
        if not window_token_ok(value):
            bad("malformed window token")
        return value
    if not valid_token(value):
        bad(f"invalid {name} token")
    return GroupId(value) if name == "group" else FormationId(value)


# --------------------------------------------------------------------------
# Results


def _check_stage_tuple(stages, path):
    if type(stages) is not tuple or not stages:
        raise InvalidValue("T04", path, "expected a nonempty tuple")
    for i, s in enumerate(stages):
        _check(EnumK(Stage), s, f"{path}/{i}")


@dataclass(frozen=True, slots=True)
class Accepted:
    state: BattleState
    stages: tuple

    def __post_init__(self):
        check_state(self.state)
        _check_stage_tuple(self.stages, "stages")


@dataclass(frozen=True, slots=True)
class Rejected:
    state: BattleState
    code: RejectCode
    path: str
    detail: str

    def __post_init__(self):
        check_state(self.state)
        _check(EnumK(RejectCode), self.code, "code")
        _check(Str(), self.path, "path")
        _check(Str(), self.detail, "detail")


@dataclass(frozen=True, slots=True)
class Deferred:
    state: BattleState
    command: object
    stage: Stage
    obligations: tuple

    def __post_init__(self):
        check_state(self.state)
        check_command(self.command)
        _check(EnumK(Stage), self.stage, "stage")
        if type(self.obligations) is not tuple or not self.obligations:
            raise InvalidValue("T04", "obligations", "expected a nonempty tuple")
        for i, o in enumerate(self.obligations):
            _check(Str(), o, f"obligations/{i}")


RESULT_CLASSES = (Accepted, Rejected, Deferred)
Result = Accepted | Rejected | Deferred


@dataclass(frozen=True, slots=True)
class JournalEntry:
    cursor: int
    command_digest: str
    previous: str
    current: str

    def __post_init__(self):
        _check(Int("T10", 0), self.cursor, "cursor")
        _check(Str(digest=True), self.command_digest, "command_digest")
        _check(Str(digest=True), self.previous, "previous")
        _check(Str(digest=True), self.current, "current")


_FIXTURE_ID = IdK(FixtureId)


def check_fixture_id(fixture_id):
    _check(_FIXTURE_ID, fixture_id, "fixture_id")
