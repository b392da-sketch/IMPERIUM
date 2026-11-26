"""Layer E1: immediate and deadline predicates, outcome precedence,
zero-viability classification and the terminal record (P2 contract 9.1,
9.2).

Everything here reads a ``Fields`` bundle of candidate field values and
returns a ``TerminalRecord`` or None. Nothing constructs a state.
"""

from imperium.battle.queries import (
    exit_available, objective_status, onmap_available, viable_count,
)
from imperium.battle.records import TerminalRecord
from imperium.battle.values import (
    DefeatClass, Disposition, ObjectiveKind, Posture, ResultKind, Side, TerminalReason,
    TerminationPoint, opponent,
)

SIDES = (Side.S0, Side.S1)


def _index(side):
    return 0 if side is Side.S0 else 1


def posture_of(fields, side):
    for s in fields.sides:
        if s.side is side:
            return s.posture
    raise LookupError(side)


def defeat_class(fields, side):
    """X03: COLLAPSE, else DEPARTURE, else DEPLETION_MIXED."""
    mine = [f for f in fields.formations if fields.roster[f.formation].side is side]
    if any(f.disposition is Disposition.ROUTING for f in mine):
        return DefeatClass.COLLAPSE
    withdrawn = any(f.disposition is Disposition.WITHDRAWN for f in mine)
    depleted = any(f.disposition is Disposition.DEPLETED for f in mine)
    if withdrawn and not depleted:
        return DefeatClass.DEPARTURE
    return DefeatClass.DEPLETION_MIXED


def _record(fields, reason, result, winner, defeat, point, charged):
    return TerminalRecord(
        reason=reason,
        result=result,
        winner=winner,
        defeat=defeat,
        point=point,
        charged_rounds=charged,
        objective=objective_status(fields),
        postures=tuple(posture_of(fields, s) for s in SIDES),
        viable=tuple(viable_count(fields, s) for s in SIDES),
        onmap_available=tuple(onmap_available(fields, s) for s in SIDES),
        exit_available=tuple(exit_available(fields, s) for s in SIDES),
    )


def immediate_outcome(fields, point, charged, capitulator=None):
    """Rows 1–3 of the precedence (9.2), or None if the battle continues.

    ``capitulator`` is the side that capitulated in this root; the custody
    transform must already be applied to ``fields``.
    """
    if capitulator is not None:
        defeat = [None, None]
        defeat[_index(capitulator)] = DefeatClass.CAPITULATED
        return _record(fields, TerminalReason.CAPITULATION, ResultKind.VICTORY,
                       opponent(capitulator), tuple(defeat), point, charged)
    zero = [s for s in SIDES if viable_count(fields, s) == 0]
    if len(zero) == 2:
        defeat = tuple(defeat_class(fields, s) for s in SIDES)
        return _record(fields, TerminalReason.ZERO_VIABILITY_MUTUAL_LOSS, ResultKind.DRAW,
                       None, defeat, point, charged)
    if len(zero) == 1:
        z = zero[0]
        other = opponent(z)
        defeat = [None, None]
        defeat[_index(z)] = defeat_class(fields, z)
        if posture_of(fields, other) is Posture.CONTESTING:
            return _record(fields, TerminalReason.ZERO_VIABILITY_UNILATERAL, ResultKind.VICTORY,
                           other, tuple(defeat), point, charged)
        return _record(fields, TerminalReason.ZERO_VIABILITY_MUTUAL_ABANDONMENT, ResultKind.DRAW,
                       None, tuple(defeat), point, charged)
    return None


def deadline_outcome(fields, charged):
    """Row 4 of the precedence, at ROUND_END with charged equal to the rounds."""
    withdrawing = [s for s in SIDES if posture_of(fields, s) is Posture.WITHDRAWING]
    point = TerminationPoint.ROUND_END
    if len(withdrawing) == 2:
        return _record(fields, TerminalReason.DEADLINE_MUTUAL_WITHDRAWAL, ResultKind.DRAW,
                       None, (None, None), point, charged)
    if len(withdrawing) == 1:
        w = withdrawing[0]
        defeat = [None, None]
        defeat[_index(w)] = DefeatClass.ABANDONMENT
        return _record(fields, TerminalReason.DEADLINE_ABANDONMENT, ResultKind.VICTORY,
                       opponent(w), tuple(defeat), point, charged)
    objective = objective_status(fields)
    if objective.kind is ObjectiveKind.SECURE:
        return _record(fields, TerminalReason.DEADLINE_OBJECTIVE_VICTORY, ResultKind.VICTORY,
                       objective.side, (None, None), point, charged)
    return _record(fields, TerminalReason.DEADLINE_OBJECTIVE_UNRESOLVED, ResultKind.DRAW,
                   None, (None, None), point, charged)


def round_end_outcome(fields, charged, rounds):
    """END_CHECK: the immediate predicate first, then the deadline."""
    record = immediate_outcome(fields, TerminationPoint.ROUND_END, charged)
    if record is not None:
        return record
    if charged == rounds:
        return deadline_outcome(fields, charged)
    return None
