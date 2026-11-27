"""Layer E0c: exertion marks, the MP21/N01 fatigue mapping and the safety
checkpoint (P4 contract rev 0.1 sections 6 and 8.6, unchanged in rev 0.2).

Pure functions on P1 values and dicts of candidate field values; nothing
here constructs a state.
"""

import dataclasses

from imperium.battle.profile import step_cap
from imperium.battle.queries import Fields, movement_mode, on_battlefield, recovery_safe_now

STEP_MARKS = 1
PIVOT_MARKS = 1          # per increment
GROUP_MARKS = 1          # per member, step or pivot
WITHDRAW_MARKS = 2
EVACUATE_MARKS = 2
RESPONSE_MARKS = 1       # defensive pivot


def map_marks(condition, marks, threshold):
    """``condition`` after ``marks`` exertion marks (MP21 with N01 carry).

    E += m; while E >= T and F < 2: F += 1, E -= T; at F2, E = E mod T.
    Cohesion and morale are unchanged.
    """
    e = condition.exertion + marks
    f = condition.fatigue
    while e >= threshold and f < 2:
        f += 1
        e -= threshold
    if f == 2:
        e %= threshold
    return dataclasses.replace(condition, fatigue=f, exertion=e)


def nominal_cap(fields, fid):
    """The mover's mode cap: heavy 2, light 2, mounted 3, mixed foot 2."""
    mode = movement_mode(fields, fid)
    return step_cap(mode, fields.roster[fid].template)


def cap_for(condition, nominal):
    """The actual translation cap: 1 at C2 or F2, else the mode cap (A09)."""
    if condition.cohesion == 2 or condition.fatigue == 2:
        return 1
    return nominal


def actual_cap(fields, fid):
    return cap_for(fields.fmap[fid].condition, nominal_cap(fields, fid))



def mark(values, fid, marks):
    """Field values after ``marks`` on ``fid``: condition by MP21 and the
    round's ``exerted`` flag set (6.2). ``values`` is a dict."""
    threshold = values["scenario"].profile.exertion_threshold
    out = dict(values)
    out["formations"] = tuple(
        dataclasses.replace(f, condition=map_marks(f.condition, marks, threshold))
        if f.formation == fid else f for f in values["formations"])
    ledger = values["ledger"]
    out["ledger"] = dataclasses.replace(ledger, formations=tuple(
        dataclasses.replace(fr, exerted=True) if fr.formation == fid else fr
        for fr in ledger.formations))
    return out


def checkpoint(values):
    """The safety checkpoint after a physical stage (8.6, D6): every
    battlefield formation keeps ``safe_latch`` only while recovery-safe;
    off-battlefield latches are unchanged and no latch turns true."""
    fields = Fields(**values)
    ledger = values["ledger"]
    rounds = []
    changed = False
    for fr in ledger.formations:
        f = fields.fmap[fr.formation]
        if fr.safe_latch and on_battlefield(f) and not recovery_safe_now(fields, fr.formation):
            fr = dataclasses.replace(fr, safe_latch=False)
            changed = True
        rounds.append(fr)
    if not changed:
        return values
    out = dict(values)
    out["ledger"] = dataclasses.replace(ledger, formations=tuple(rounds))
    return out
