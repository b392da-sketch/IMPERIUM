"""Layer E3: round opening, the alternation replay and the closure
support boundary (P2 contract 7, 8, 10).

Functions take and return dicts of candidate field values; nothing here
constructs a state.
"""

from imperium.battle.queries import (
    Fields, ORGANIZED_OR_REFORMING, available, ledger_side_finished, on_battlefield,
    recovery_safe_now, round_first_side,
)
from imperium.battle.records import AwaitingPrincipal, FormationRound, Rest, RoundLedger
from imperium.battle.values import Disposition, Side, UseKind, opponent

from .commands import Stage

SIDES = (Side.S0, Side.S1)
DO_DISPLACEMENT = "DO-P2-01"
DO_RECOVERY = "DO-P2-02"


def open_round(values):
    """The AwaitingPrincipal phase and fresh ledger for round completed + 1 (7).

    ``values['clock']`` must already hold the completed-round count.
    Condition, exertion residue (N01), postures and contacts are unchanged.
    """
    fields = Fields(**values)
    rounds = []
    for entry in fields.scenario.roster:
        fid = entry.formation
        f = fields.fmap[fid]
        eligible = f.disposition in ORGANIZED_OR_REFORMING and available(fields, fid) > 0
        safe = recovery_safe_now(fields, fid) if on_battlefield(f) else False
        rounds.append(FormationRound(
            formation=fid, opened_eligible=eligible, response=None,
            displacement_attempted=False, safe_latch=safe, incoming=False,
            incoming_since_rally=False, exerted=False, displaced=False))
    out = dict(values)
    out["phase"] = AwaitingPrincipal(round_first_side(fields.clock))
    out["ledger"] = RoundLedger(uses=(), formations=tuple(rounds))
    return out


def both_finished(scenario, ledger):
    return all(ledger_side_finished(scenario, ledger, s) for s in SIDES)


def next_to_move(scenario, clock, ledger):
    """The side to move per P1 R11's replay; meaningful while one side is unfinished."""
    expected = round_first_side(clock)
    finished = {Side.S0: False, Side.S1: False}
    counts = {Side.S0: 0, Side.S1: 0}
    for use in ledger.uses:
        x = use.side
        if use.kind is UseKind.PASS:
            finished[x] = True
        else:
            counts[x] += 1
            if counts[x] >= scenario.profile.opportunities:
                finished[x] = True
        expected = x if finished[opponent(x)] else opponent(x)
    return expected


def closure_deferral(values):
    """``(stage, obligations)`` if closure needs P6/P7 mechanics, else None (10.2).

    Conservative: any battlefield router defers at CLOSURE_DISPLACEMENT;
    otherwise a reformer or a Rest work record defers at RECOVERY.
    """
    fields = Fields(**values)
    if any(f.disposition is Disposition.ROUTING for f in fields.formations):
        return Stage.CLOSURE_DISPLACEMENT, (DO_DISPLACEMENT, DO_RECOVERY)
    reformer = any(f.disposition is Disposition.REFORMING for f in fields.formations)
    rest = any(type(w) is Rest for use in fields.ledger.uses for w in use.work)
    if reformer or rest:
        return Stage.RECOVERY, (DO_RECOVERY,)
    return None
