"""Layer E0: P2 command records, result records, stage and rejection
tokens, and the canonical command document (P2 contract 3, 3.1).

No command carries a cost, charge, effort, ledger, use, flag or state
fragment; every expenditure is derived by ``step``. Records validate
exact field types in ``__post_init__`` and are frozen with slots.
"""

from dataclasses import dataclass
from enum import Enum

from imperium.battle import BattleState, FixtureId, FormationId, InvalidValue, Side
from imperium.battle.canon import canonical_bytes_of, sha256_hex
from imperium.battle.values import EnumK, IdK, Int, Str

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


class RejectCode(Enum):
    PHASE = "PHASE"
    WRONG_SIDE = "WRONG_SIDE"
    UNKNOWN_FORMATION = "UNKNOWN_FORMATION"
    NOT_OWN_FORMATION = "NOT_OWN_FORMATION"
    NOT_READY = "NOT_READY"
    ALREADY_WITHDRAWING = "ALREADY_WITHDRAWING"
    NO_ONMAP_AVAILABLE = "NO_ONMAP_AVAILABLE"


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


COMMAND_CLASSES = (OpenBattle, HoldOrder, PassOrder, DeclareWithdrawal, Capitulate)
Command = OpenBattle | HoldOrder | PassOrder | DeclareWithdrawal | Capitulate

# Variant keys of the command document, in declaration order (3.1).
_COMMAND_KEYS = {
    OpenBattle: (),
    HoldOrder: ("side", "formation"),
    PassOrder: ("side",),
    DeclareWithdrawal: ("side",),
    Capitulate: ("side",),
}


def check_command(command):
    """Raise T15 at ``command`` unless it is exactly one of the five classes."""
    if type(command) not in COMMAND_CLASSES:
        raise InvalidValue("T15", "command", "not a P2 command")


def check_state(state):
    """Raise V00 at ``state`` unless it is exactly a ``BattleState``."""
    if type(state) is not BattleState:
        raise InvalidValue("V00", "state", "not a BattleState")


def _token(value):
    if type(value) is Side:
        return value.name
    return value.token


def encode_command(command):
    """A fresh primitive document of ``command`` (3.1)."""
    check_command(command)
    t = type(command)
    doc = {"schema": COMMAND_SCHEMA, "kind": t.__name__}
    for name in _COMMAND_KEYS[t]:
        doc[name] = _token(getattr(command, name))
    return doc


def command_bytes(command):
    """Canonical P1 13.4 JSON bytes of the command document."""
    return canonical_bytes_of(encode_command(command))


def command_digest(command):
    """Lowercase-hex SHA-256 of the canonical command bytes."""
    return sha256_hex(command_bytes(command))


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
