"""Layer E3b: the single movement response window (P4 contract rev 0.2
section 9, ER02, E02, E05; rev 0.1 sections 9.1-9.3 unchanged).

Window options, the ER02 context token, the suspended root and its three
results, decision admission and the defensive pivot's effects. Nothing here
constructs a state: a suspended root holds the stable base and a stage
snapshot only.
"""

import dataclasses
from dataclasses import dataclass

from imperium.battle import FormationId, InvalidValue, Side
from imperium.battle.canon import canonical_bytes_of, sha256_hex
from imperium.battle.queries import (
    account_of, in_contact, response_possible, template_for,
)
from imperium.battle.records import Response
from imperium.battle.values import (
    ResponseKind, direction_of, distance, front_directions, in_front_sector,
)

from .commands import (
    DECISION_CLASSES, P4_DETAIL, REJECT_TEXT, GroupMoveOrder, MoveOrder, RejectCode,
    RespondMissile, RespondPivot, WithdrawOrder, is_decision, is_state, window_token_ok,
)
from .events import StageSnapshot, stage_kind_of
from .exertion import RESPONSE_MARKS, checkpoint, mark
from .geometry import hostile_adjacent, los_clear, newly_adjacent

WINDOW_TAG = "IMPERIUM-P4-window-1"
DO_MISSILE = "DO-P4-02"
TRIGGER_KINDS = ("STEP1", "STEP2", "STEP3", "WITHDRAW", "GROUP_STEP")
SUSPENDING_CLASSES = (MoveOrder, WithdrawOrder, GroupMoveOrder)
_KIND_OF = {RespondPivot: ResponseKind.DEFENSIVE_PIVOT, RespondMissile: ResponseKind.DEFENSIVE_MISSILE}


def _fail(code, path, detail):
    raise InvalidValue(code, path, detail)


def _exact(value, cls, path):
    if type(value) is not cls:
        _fail("T15", path, f"expected {cls.__name__}")


def _exact_tuple(value, cls, path):
    if type(value) is not tuple:
        _fail("T15", path, "expected tuple")
    for i, item in enumerate(value):
        if type(item) is not cls:
            _fail("T15", f"{path}/{i}", f"expected {cls.__name__}")


# --------------------------------------------------------------------------
# Records (4.3, E05)


@dataclass(frozen=True, slots=True)
class ResponseOption:
    formation: FormationId
    kind: ResponseKind
    target: FormationId

    def __post_init__(self):
        _exact(self.formation, FormationId, "formation")
        _exact(self.kind, ResponseKind, "kind")
        _exact(self.target, FormationId, "target")


def option_key(option):
    return (option.formation.token, option.kind.name, option.target.token)


@dataclass(frozen=True, slots=True)
class ResponseWindow:
    side: Side
    window_id: str
    after: str
    movers: tuple
    options: tuple

    def __post_init__(self):
        _exact(self.side, Side, "side")
        _exact(self.window_id, str, "window_id")
        _exact(self.after, str, "after")
        _exact_tuple(self.movers, FormationId, "movers")
        _exact_tuple(self.options, ResponseOption, "options")
        if not window_token_ok(self.window_id):
            _fail("T16", "window_id", "expected a lowercase SHA-256 hex token")
        if stage_kind_of(self.after) not in TRIGGER_KINDS:
            _fail("T16", "after", "not a movement stage id")
        tokens = [m.token for m in self.movers]
        if not tokens or any(a >= b for a, b in zip(tokens, tokens[1:])):
            _fail("T16", "movers", "expected sorted unique movers")
        keys = [option_key(o) for o in self.options]
        if not keys or any(a >= b for a, b in zip(keys, keys[1:])):
            _fail("T16", "options", "expected a nonempty canonical option tuple")


@dataclass(frozen=True, slots=True)
class SuspendedRoot:
    base: object
    command: object
    stage: StageSnapshot
    window: ResponseWindow

    def __post_init__(self):
        if not is_state(self.base):
            _fail("T15", "base", "expected BattleState")
        if type(self.command) not in SUSPENDING_CLASSES:
            _fail("T15", "command", "expected a movement order")
        _exact(self.stage, StageSnapshot, "stage")
        _exact(self.window, ResponseWindow, "window")


@dataclass(frozen=True, slots=True)
class Suspended:
    root: SuspendedRoot

    def __post_init__(self):
        _exact(self.root, SuspendedRoot, "root")


@dataclass(frozen=True, slots=True)
class WindowRejected:
    root: SuspendedRoot
    code: RejectCode
    path: str
    detail: str

    def __post_init__(self):
        _exact(self.root, SuspendedRoot, "root")
        _exact(self.code, RejectCode, "code")
        _exact(self.path, str, "path")
        _exact(self.detail, str, "detail")


@dataclass(frozen=True, slots=True)
class WindowDeferred:
    root: SuspendedRoot
    decision: object
    obligations: tuple

    def __post_init__(self):
        _exact(self.root, SuspendedRoot, "root")
        if type(self.decision) not in DECISION_CLASSES:
            _fail("T15", "decision", "expected a window decision")
        _exact_tuple(self.obligations, str, "obligations")
        if not self.obligations:
            _fail("T16", "obligations", "expected a nonempty tuple")


# --------------------------------------------------------------------------
# Context token and options (9.2, ER02)


def window_token(base_digest, principal_digest, after):
    """Lowercase SHA-256 of ``["IMPERIUM-P4-window-1", F(base),
    command_digest(principal), triggering_stage_id]`` (ER02)."""
    return sha256_hex(canonical_bytes_of([WINDOW_TAG, base_digest, principal_digest, after]))


def pivot_turn(defender, mover_cell):
    """The determined one-step fix toward ``mover_cell``, or None (J02)."""
    d = direction_of(defender.cell, mover_cell)
    f = defender.facing
    if d is None or d in front_directions(f):
        return None
    if d == (f + 2) % 6:
        return 1
    if d == (f - 1) % 6:
        return -1
    return None


def _missile_ok(fields, defender, mover):
    template = template_for(fields, defender.formation)
    rng = template.missile_range
    if rng is None:
        return False
    account = account_of(fields, defender.formation)
    if account is None or account.carried < 1:
        return False
    if in_contact(fields, mover.formation):
        return False
    if not 1 <= distance(defender.cell, mover.cell) <= rng:
        return False
    if not in_front_sector(defender.cell, mover.cell, defender.facing):
        return False
    return los_clear(fields, defender.cell, mover.cell)


def window_options(pre, post, side, movers):
    """Canonical unique options for the defending side after one stage."""
    out = set()
    for entry in post.scenario.roster:
        fid = entry.formation
        if entry.side is side or not response_possible(post, fid):
            continue
        defender = post.fmap[fid]
        for m in movers:
            mover = post.fmap[m]
            if (newly_adjacent(pre, post, fid, m) and hostile_adjacent(post, fid) == (m,)
                    and pivot_turn(defender, mover.cell) is not None):
                out.add(ResponseOption(fid, ResponseKind.DEFENSIVE_PIVOT, m))
            if _missile_ok(post, defender, mover):
                out.add(ResponseOption(fid, ResponseKind.DEFENSIVE_MISSILE, m))
    return tuple(sorted(out, key=option_key))


def option_tree(option):
    return {"formation": option.formation.token, "kind": option.kind.name,
            "target": option.target.token}


# --------------------------------------------------------------------------
# Decision admission (9.4, ER02)


def admit_decision(root, command):
    """``("reject", code, path)``, ``("defer", obligations)`` or None.

    Runs after the genuine-root check; a principal command is
    PENDING_WINDOW.
    """
    window = root.window
    if not is_decision(command):
        return ("reject", RejectCode.PENDING_WINDOW, "")
    if command.side is not window.side:
        return ("reject", RejectCode.WRONG_SIDE, "/side")
    if not window_token_ok(command.window_id):
        return ("reject", RejectCode.BAD_VALUE, "/window_id")
    if command.window_id != window.window_id:
        return ("reject", RejectCode.STALE_WINDOW, "/window_id")
    kind = _KIND_OF.get(type(command))
    if kind is not None:
        if ResponseOption(command.formation, kind, command.target) not in window.options:
            return ("reject", RejectCode.NOT_OFFERED, "/formation")
        if kind is ResponseKind.DEFENSIVE_MISSILE:
            return ("defer", (DO_MISSILE,))
    return None


def rejection_detail(code):
    if code is RejectCode.WRONG_SIDE:
        return REJECT_TEXT[code][1]
    return P4_DETAIL[code]


# --------------------------------------------------------------------------
# The defensive pivot (9.4)


def response_stage(values, fields, decision):
    """RESPONSE: one-step turn toward the mover, the response record, one
    mark, ``exerted`` and the checkpoint. Returns ``(values, data)``."""
    fid, target = decision.formation, decision.target
    defender = fields.fmap[fid]
    turn = pivot_turn(defender, fields.fmap[target].cell)
    before = defender.facing
    after = (before + turn) % 6
    out = dict(values)
    out["formations"] = tuple(
        dataclasses.replace(f, facing=after) if f.formation == fid else f
        for f in values["formations"])
    ledger = values["ledger"]
    out["ledger"] = dataclasses.replace(ledger, formations=tuple(
        dataclasses.replace(fr, response=Response(ResponseKind.DEFENSIVE_PIVOT, target))
        if fr.formation == fid else fr for fr in ledger.formations))
    out = checkpoint(mark(out, fid, RESPONSE_MARKS))
    data = {"formation": fid.token, "kind": ResponseKind.DEFENSIVE_PIVOT.name,
            "target": target.token, "from": before, "to": after}
    return out, data

