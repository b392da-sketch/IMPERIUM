"""Layer E4: ``step``, the single P2 transition (P2 contract 5, 6, 8, 10).

Order: argument types, phase, side, command prerequisites, the pure
deferral decision, the cursor bound, then exactly one ``BattleState``
construction through P1's validating constructor. This is the only engine
module that constructs a state.
"""

import dataclasses

from imperium.battle.queries import (
    Fields, activation, ledger_side_finished, onmap_available,
)
from imperium.battle.records import (
    STATE_FIELDS, AwaitingPrincipal, Clock, Hold, Opening, OpportunityUse, Terminal,
)
from imperium.battle.state import BattleState, state_values
from imperium.battle.values import (
    INT_DOMAIN, Activation, Posture, TerminationPoint, UseKind,
)
from imperium.battle.errors import InvalidValue

from .commands import (
    NOT_READY_PATH, REJECT_TEXT, Accepted, Capitulate, DeclareWithdrawal, Deferred, HoldOrder,
    OpenBattle, PassOrder, RejectCode, Rejected, Stage, check_command, check_state,
)
from .custody import capitulate
from .rounds import both_finished, closure_deferral, next_to_move, open_round
from .terminal import immediate_outcome, round_end_outcome

CLOSURE_STAGES = (
    Stage.CLOSURE_DISPLACEMENT, Stage.CLOSURE_CHECK, Stage.RECOVERY, Stage.ADVANCE,
    Stage.END_CHECK,
)


def _reject(state, code, detail=None):
    if code is RejectCode.NOT_READY:
        return Rejected(state, code, NOT_READY_PATH, detail)
    path, text = REJECT_TEXT[code]
    return Rejected(state, code, path, text)


def _terminal(values, record):
    out = dict(values)
    out["phase"] = Terminal(record)
    out["ledger"] = None
    return out


def _with_clock(values, completed=None):
    clock = values["clock"]
    out = dict(values)
    out["clock"] = Clock(
        completed_rounds=clock.completed_rounds if completed is None else completed,
        event_cursor=clock.event_cursor + 1)
    return out


def _admissible(state, fields, command):
    """The first rule failure as a ``Rejected``, or None (6, steps 2–4)."""
    phase = type(fields.phase)
    if type(command) is OpenBattle:
        return None if phase is Opening else _reject(state, RejectCode.PHASE)
    if phase is not AwaitingPrincipal:
        return _reject(state, RejectCode.PHASE)
    side = command.side
    if side is not fields.phase.side:
        return _reject(state, RejectCode.WRONG_SIDE)
    t = type(command)
    if t is HoldOrder:
        entry = fields.roster.get(command.formation)
        if entry is None:
            return _reject(state, RejectCode.UNKNOWN_FORMATION)
        if entry.side is not side:
            return _reject(state, RejectCode.NOT_OWN_FORMATION)
        act = activation(fields, command.formation)
        if act is not Activation.READY:
            return _reject(state, RejectCode.NOT_READY, act.name)
    elif t is DeclareWithdrawal:
        if _posture(fields, side) is not Posture.CONTESTING:
            return _reject(state, RejectCode.ALREADY_WITHDRAWING)
    elif t is Capitulate:
        if onmap_available(fields, side) <= 0:
            return _reject(state, RejectCode.NO_ONMAP_AVAILABLE)
    return None


def _posture(fields, side):
    for s in fields.sides:
        if s.side is side:
            return s.posture
    raise LookupError(side)


def _use_of(command):
    t = type(command)
    if t is HoldOrder:
        return OpportunityUse(command.side, UseKind.INDIVIDUAL, None, (command.formation,), (Hold(),))
    if t is PassOrder:
        return OpportunityUse(command.side, UseKind.PASS, None, (), ())
    return OpportunityUse(command.side, UseKind.POSTURE_WITHDRAWAL, None, (), ())


def _plan(values, command):
    """``("deferred", stage, obligations)`` or ``("accepted", values, stages)``.

    Pure: works on field values only. The returned values still hold the
    input clock; the caller advances the cursor.
    """
    fields = Fields(**values)
    clock = fields.clock
    t = type(command)
    if t is OpenBattle:
        record = immediate_outcome(fields, TerminationPoint.INITIAL_CHECK, 0)
        if record is not None:
            return "accepted", _terminal(values, record), (Stage.INITIAL_CHECK, Stage.TERMINAL)
        return "accepted", open_round(values), (Stage.INITIAL_CHECK, Stage.OPEN_ROUND)
    charged = clock.completed_rounds + 1
    if t is Capitulate:
        after = capitulate(values, command.side)
        record = immediate_outcome(Fields(**after), TerminationPoint.AFTER_ROOT, charged,
                                   capitulator=command.side)
        return "accepted", _terminal(after, record), (Stage.ROOT, Stage.IMMEDIATE_CHECK, Stage.TERMINAL)
    # ROOT: append the ledger-bearing use.
    after = dict(values)
    if t is DeclareWithdrawal:
        after["sides"] = tuple(
            dataclasses.replace(s, posture=Posture.WITHDRAWING) if s.side is command.side else s
            for s in fields.sides)
    ledger = fields.ledger
    ledger = dataclasses.replace(ledger, uses=ledger.uses + (_use_of(command),))
    after["ledger"] = ledger
    root = (Stage.ROOT, Stage.IMMEDIATE_CHECK)
    # IMMEDIATE_CHECK
    record = immediate_outcome(Fields(**after), TerminationPoint.AFTER_ROOT, charged)
    if record is not None:
        return "accepted", _terminal(after, record), root + (Stage.TERMINAL,)
    scenario = fields.scenario
    if not both_finished(scenario, ledger):
        after["phase"] = AwaitingPrincipal(next_to_move(scenario, clock, ledger))
        return "accepted", after, root
    deferral = closure_deferral(after)
    if deferral is not None:
        return ("deferred",) + deferral
    # CLOSURE_DISPLACEMENT is a verified no-op in the supported subset (10.1).
    # CLOSURE_CHECK: the immediate predicate on the post-displacement fields,
    # with the pre-advance clock; no positive is reachable in P2.
    record = immediate_outcome(Fields(**after), TerminationPoint.AFTER_CLOSURE_DISPLACEMENT, charged)
    if record is not None:
        return "accepted", _terminal(after, record), root + (
            Stage.CLOSURE_DISPLACEMENT, Stage.CLOSURE_CHECK, Stage.TERMINAL)
    # RECOVERY is a verified no-op; ADVANCE; END_CHECK.
    completed = clock.completed_rounds + 1
    after["clock"] = Clock(completed_rounds=completed, event_cursor=clock.event_cursor)
    record = round_end_outcome(Fields(**after), completed, scenario.profile.rounds)
    if record is not None:
        return "accepted", _terminal(after, record), root + CLOSURE_STAGES + (Stage.TERMINAL,)
    return "accepted", open_round(after), root + CLOSURE_STAGES + (Stage.OPEN_ROUND,)


def step(state, command):
    """Apply one command to one stable state; return Accepted, Rejected or Deferred."""
    check_state(state)
    check_command(command)
    values = dict(zip(STATE_FIELDS, state_values(state)))
    rejected = _admissible(state, Fields(**values), command)
    if rejected is not None:
        return rejected
    outcome = _plan(values, command)
    if outcome[0] == "deferred":
        return Deferred(state, command, outcome[1], outcome[2])
    _, after, stages = outcome
    if state.clock.event_cursor >= INT_DOMAIN:
        raise InvalidValue("T10", "state.clock.event_cursor",
                           "successor cursor exceeds the P1 integer domain")
    after = _with_clock(after, after["clock"].completed_rounds)
    return Accepted(BattleState(**after), stages)


__all__ = ["step"]
