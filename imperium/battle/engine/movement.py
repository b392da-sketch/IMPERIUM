"""Layer E3a: admission and physical stage effects for the six P4 principal
orders (P4 contract rev 0.2 sections 7 and 8, ER01, ER07, ER08, E06).

Admission works on one ``Fields`` snapshot and returns the first fault in
the frozen order. Stage functions map dicts of candidate field values to new
dicts plus the stage's event data; nothing here constructs a state. The
admitted plan (declared path, members, reservation) lives in the command and
the caller, outside P1 state values (7.7).
"""

import dataclasses

from imperium.battle.board import cell_on_board, entry_cost
from imperium.battle.profile import movement_cost_kind
from imperium.battle.queries import (
    Fields, activation, effort_remaining, exit_distance, in_contact, movement_mode,
    recovery_safe_now,
)
from imperium.battle.records import (
    AtExit, Evacuate, GroupPivot, GroupStep, InFormation, Leg, Move, OpportunityUse, Pivot,
    Withdraw,
)
from imperium.battle.scenario import end_of, exit_row
from imperium.battle.values import (
    Activation, Assignment, Authority, Custody, Disposition, MoveEnd, PersonnelStatus, Posture, Recovery,
    UseKind, direction_of, front_directions, rear_directions, step,
)

from .commands import (
    P4_DETAIL, EvacuateOrder, GroupMoveOrder, GroupPivotOrder, MoveOrder, PivotOrder,
    RejectCode, Stage, WithdrawOrder,
)
from .exertion import (
    EVACUATE_MARKS, GROUP_MARKS, PIVOT_MARKS, STEP_MARKS, WITHDRAW_MARKS, actual_cap, cap_for,
    checkpoint, map_marks, mark, nominal_cap,
)
from .geometry import connected, exit_progress, hostile_sources, occupant

DO_ENGAGED_WITHDRAWAL = "DO-P4-01"
STEP_KINDS = (Stage.STEP1, Stage.STEP2, Stage.STEP3)


class _Fault(Exception):
    """The first admission fault: code, path and detail."""

    def __init__(self, code, path, detail=None):
        super().__init__(code.name)
        self.code = code
        self.path = path
        self.detail = P4_DETAIL[code] if detail is None else detail


def _fail(code, path, detail=None):
    raise _Fault(code, path, detail)


def _side_posture(fields, side):
    for s in fields.sides:
        if s.side is side:
            return s.posture
    raise LookupError(side)


def _cost_kind(fields, fid):
    return movement_cost_kind(movement_mode(fields, fid), fields.roster[fid].template)


def _entry(fields, fid, origin, destination):
    return entry_cost(fields.scenario.board, origin, destination, _cost_kind(fields, fid))


def _occupied_by_other(fields, cell, allowed=()):
    who = occupant(fields, cell)
    return who is not None and who not in allowed


# --------------------------------------------------------------------------
# Admission (section 7, ER07, E06)


def _individual_prefix(fields, command):
    fid = command.formation
    entry = fields.roster.get(fid)
    if entry is None:
        _fail(RejectCode.UNKNOWN_FORMATION, "/formation", "formation is not in the roster")
    if entry.side is not command.side:
        _fail(RejectCode.NOT_OWN_FORMATION, "/formation",
              "formation does not belong to the command side")
    act = activation(fields, fid)
    if act is not Activation.READY:
        _fail(RejectCode.NOT_READY, "/formation", act.name)
    if fields.fmap[fid].disposition is not Disposition.ORGANIZED:
        _fail(RejectCode.NOT_ORGANIZED, "/formation")
    return fid


def _admit_move(fields, command):
    fid = _individual_prefix(fields, command)
    me = fields.fmap[fid]
    side = command.side
    path = command.path
    board = fields.scenario.board
    if in_contact(fields, fid):
        _fail(RejectCode.ENGAGED, "/formation")
    if not 1 <= len(path) <= 3:
        _fail(RejectCode.BAD_VALUE, "/path")
    if hostile_sources(fields, me.cell, side):
        _fail(RejectCode.THREATENED_ORIGIN, "/formation")
    costs = []
    prev = me.cell
    seen = [me.cell]
    front = front_directions(me.facing)
    for i, cell in enumerate(path):
        at = f"/path/{i}"
        if not cell_on_board(board, cell):
            _fail(RejectCode.OFF_BOARD, at)
        if cell in seen:
            _fail(RejectCode.REPEATED_CELL, at)
        d = direction_of(prev, cell)
        if d is None:
            _fail(RejectCode.NOT_ADJACENT, at)
        if d not in front:
            _fail(RejectCode.NOT_FRONT, at)
        cost = _entry(fields, fid, prev, cell)
        if cost is None:
            _fail(RejectCode.IMPASSABLE, at)
        if _occupied_by_other(fields, cell):
            _fail(RejectCode.OCCUPIED, at)
        costs.append(cost)
        seen.append(cell)
        prev = cell
    if len(path) > actual_cap(fields, fid):
        _fail(RejectCode.OVER_CAP, "/path")
    if sum(costs) > effort_remaining(fields, fid):
        _fail(RejectCode.OVER_EFFORT, "/path")
    # PAST_STOP (A05): the smallest k >= 1 with a stop predicted after step k
    # and step k + 1 declared; the mover cannot change enemy threat.
    threshold = fields.scenario.profile.exertion_threshold
    nominal = nominal_cap(fields, fid)
    condition = me.condition
    for k in range(1, len(path)):
        condition = map_marks(condition, STEP_MARKS, threshold)
        if hostile_sources(fields, path[k - 1], side) or k >= cap_for(condition, nominal):
            _fail(RejectCode.PAST_STOP, f"/path/{k}")
    if _side_posture(fields, side) is Posture.WITHDRAWING:
        prev = me.cell
        for i, cell in enumerate(path):
            if not exit_progress(fields.scenario, side, prev, cell):
                _fail(RejectCode.NO_EXIT_PROGRESS, f"/path/{i}")
            prev = cell


def _admit_pivot(fields, command):
    fid = _individual_prefix(fields, command)
    if command.turn not in (-1, 1):
        _fail(RejectCode.BAD_VALUE, "/turn")
    if not 1 <= command.steps <= 3:
        _fail(RejectCode.BAD_VALUE, "/steps")
    if in_contact(fields, fid):
        _fail(RejectCode.ENGAGED, "/formation")
    sources = hostile_sources(fields, fields.fmap[fid].cell, command.side)
    if len(sources) >= 2:
        _fail(RejectCode.PIVOT_RESTRICTED, "/formation")
    if len(sources) == 1 and command.steps > 1:
        _fail(RejectCode.PIVOT_RESTRICTED, "/steps")
    if command.steps > effort_remaining(fields, fid):
        _fail(RejectCode.OVER_EFFORT, "/steps")


def withdraw_debit(entry):
    """Controlled withdrawal debit: 2 + (entry cost - 1) (P1 7.2)."""
    return 2 + (entry - 1)


def _admit_withdraw(fields, command):
    fid = _individual_prefix(fields, command)
    me = fields.fmap[fid]
    dest = command.destination
    board = fields.scenario.board
    if not cell_on_board(board, dest):
        _fail(RejectCode.OFF_BOARD, "/destination")
    d = direction_of(me.cell, dest)
    if d is None:
        _fail(RejectCode.NOT_ADJACENT, "/destination")
    if d not in rear_directions(me.facing):
        _fail(RejectCode.NOT_REAR, "/destination")
    cost = _entry(fields, fid, me.cell, dest)
    if cost is None:
        _fail(RejectCode.IMPASSABLE, "/destination")
    if _occupied_by_other(fields, dest):
        _fail(RejectCode.OCCUPIED, "/destination")
    if hostile_sources(fields, dest, command.side):
        _fail(RejectCode.THREATENED_DESTINATION, "/destination")
    if withdraw_debit(cost) > effort_remaining(fields, fid):
        _fail(RejectCode.OVER_EFFORT, "/destination")
    if in_contact(fields, fid):
        return (DO_ENGAGED_WITHDRAWAL,)
    return None


def _admit_evacuate(fields, command):
    fid = _individual_prefix(fields, command)
    me = fields.fmap[fid]
    if exit_distance(fields.scenario, command.side, me.cell) != 0:
        _fail(RejectCode.NOT_ON_EXIT, "/formation")
    if not recovery_safe_now(fields, fid):
        _fail(RejectCode.EXIT_UNSAFE, "/formation")
    if effort_remaining(fields, fid) < EVACUATE_MARKS:
        _fail(RejectCode.OVER_EFFORT, "/formation")


def _members_ok(members):
    if not 2 <= len(members) <= 3:
        return False
    tokens = [m.token for m in members]
    return all(a < b for a, b in zip(tokens, tokens[1:]))


def _admit_group_prefix(fields, command, pivot):
    side = command.side
    groups = {g.group: g for g in fields.scenario.groups}
    spec = groups.get(command.group)
    if spec is None:
        _fail(RejectCode.UNKNOWN_GROUP, "/group")
    if spec.side is not side:
        _fail(RejectCode.NOT_OWN_GROUP, "/group")
    authority = dict(fields.authority)
    if authority.get(command.group) is not Authority.ACTIVE:
        _fail(RejectCode.NO_AUTHORITY, "/group")
    for i, fid in enumerate(command.members):
        at = f"/members/{i}"
        if fid not in spec.members:
            _fail(RejectCode.NOT_IN_GROUP, at)
        act = activation(fields, fid)
        if act is not Activation.READY:
            _fail(RejectCode.NOT_READY, at, act.name)
        f = fields.fmap[fid]
        if f.disposition is not Disposition.ORGANIZED:
            _fail(RejectCode.NOT_ORGANIZED, at)
        c = f.condition
        if c.cohesion > 1 or c.morale > 1 or c.fatigue > 1:
            _fail(RejectCode.CONDITION, at)
        if in_contact(fields, fid):
            _fail(RejectCode.ENGAGED, at)
        sources = hostile_sources(fields, f.cell, side)
        if pivot:
            if len(sources) >= 2:
                _fail(RejectCode.PIVOT_RESTRICTED, at)
        elif sources:
            _fail(RejectCode.THREATENED_ORIGIN, at)
    if not connected([fields.fmap[fid].cell for fid in command.members]):
        _fail(RejectCode.NOT_CONNECTED, "/members")


def _admit_group_move(fields, command):
    if not 0 <= command.direction <= 5:
        _fail(RejectCode.BAD_VALUE, "/direction")
    if not _members_ok(command.members):
        _fail(RejectCode.BAD_VALUE, "/members")
    _admit_group_prefix(fields, command, pivot=False)
    board = fields.scenario.board
    selected = command.members
    for i, fid in enumerate(selected):
        at = f"/members/{i}"
        f = fields.fmap[fid]
        dest = step(f.cell, command.direction)
        if command.direction not in front_directions(f.facing):
            _fail(RejectCode.NOT_FRONT, at)
        if not cell_on_board(board, dest):
            _fail(RejectCode.OFF_BOARD, at)
        cost = _entry(fields, fid, f.cell, dest)
        if cost is None:
            _fail(RejectCode.IMPASSABLE, at)
        if _occupied_by_other(fields, dest, selected):
            _fail(RejectCode.OCCUPIED, at)
        if cost > effort_remaining(fields, fid):
            _fail(RejectCode.OVER_EFFORT, at)
    if _side_posture(fields, command.side) is Posture.WITHDRAWING:
        for i, fid in enumerate(selected):
            f = fields.fmap[fid]
            if not exit_progress(fields.scenario, command.side, f.cell,
                                 step(f.cell, command.direction)):
                _fail(RejectCode.NO_EXIT_PROGRESS, f"/members/{i}")


def _admit_group_pivot(fields, command):
    if command.turn not in (-1, 1):
        _fail(RejectCode.BAD_VALUE, "/turn")
    if not _members_ok(command.members):
        _fail(RejectCode.BAD_VALUE, "/members")
    _admit_group_prefix(fields, command, pivot=True)
    for i, fid in enumerate(command.members):
        if effort_remaining(fields, fid) < GROUP_MARKS:
            _fail(RejectCode.OVER_EFFORT, f"/members/{i}")


_ADMIT = {
    MoveOrder: _admit_move,
    PivotOrder: _admit_pivot,
    WithdrawOrder: _admit_withdraw,
    EvacuateOrder: _admit_evacuate,
    GroupMoveOrder: _admit_group_move,
    GroupPivotOrder: _admit_group_pivot,
}

def admit(fields, command):
    """``("reject", code, path, detail)``, ``("defer", obligations)`` or None.

    Runs after P2's types, PHASE and WRONG_SIDE; the first fault wins.
    """
    try:
        deferral = _ADMIT[type(command)](fields, command)
    except _Fault as fault:
        return ("reject", fault.code, fault.path, fault.detail)
    if deferral is not None:
        return ("defer", deferral)
    return None


# --------------------------------------------------------------------------
# Physical stages (section 8, ER01, ER08)


def _replace_formation(values, fid, **changes):
    out = dict(values)
    out["formations"] = tuple(
        dataclasses.replace(f, **changes) if f.formation == fid else f
        for f in values["formations"])
    return out


def _append_use(values, use):
    out = dict(values)
    ledger = values["ledger"]
    out["ledger"] = dataclasses.replace(ledger, uses=ledger.uses + (use,))
    return out


def _replace_last_work(values, work):
    out = dict(values)
    ledger = values["ledger"]
    last = ledger.uses[-1]
    use = dataclasses.replace(last, work=(work,))
    out["ledger"] = dataclasses.replace(ledger, uses=ledger.uses[:-1] + (use,))
    return out


def _cell(h):
    return [h.q, h.r]


def _leg(fields, fid, destination):
    f = fields.fmap[fid]
    return Leg(f.cell, destination, f.facing, movement_mode(fields, fid))


def move_step(values, command, k):
    """STEPk of a Move: ``(stage, values, data, threatened)`` (8.3).

    STEP1 appends the use with ``Move(declared, (leg,), end)``; a later step
    appends one leg and updates ``end``. The caller has revalidated.
    """
    fields = Fields(**values)
    fid = command.formation
    dest = command.path[k - 1]
    leg = _leg(fields, fid, dest)
    cost = _entry(fields, fid, leg.origin, dest)
    threatened = bool(hostile_sources(fields, dest, command.side))
    end = MoveEnd.COMPLETED if k == len(command.path) else MoveEnd.STOPPED
    if k == 1:
        work = Move(command.path, (leg,), end)
        out = _append_use(values, OpportunityUse(command.side, UseKind.INDIVIDUAL, None,
                                                 (fid,), (work,)))
    else:
        prior = values["ledger"].uses[-1].work[0]
        out = _replace_last_work(values, Move(prior.declared, prior.legs + (leg,), end))
    out = _replace_formation(out, fid, cell=dest)
    out = checkpoint(mark(out, fid, STEP_MARKS))
    data = {"formation": fid.token, "from": _cell(leg.origin), "to": _cell(dest),
            "mode": leg.mode.name, "cost": cost, "marks": STEP_MARKS, "threatened": threatened}
    return STEP_KINDS[k - 1], out, data, threatened


def move_continues(values, command, k, latched):
    """Revalidate STEPk, k >= 2, from the committed context (8.3, ER07).

    False ends the move STOPPED with the remaining steps uncharged.
    """
    fields = Fields(**values)
    fid = command.formation
    f = fields.fmap[fid]
    if f.disposition is not Disposition.ORGANIZED or in_contact(fields, fid):
        return False
    if latched or hostile_sources(fields, f.cell, command.side):
        return False
    if k > actual_cap(fields, fid):
        return False
    dest = command.path[k - 1]
    if direction_of(f.cell, dest) not in front_directions(f.facing):
        return False
    cost = _entry(fields, fid, f.cell, dest)
    if cost is None or _occupied_by_other(fields, dest):
        return False
    return cost <= effort_remaining(fields, fid)


def withdraw_stage(values, command):
    fields = Fields(**values)
    fid = command.formation
    dest = command.destination
    leg = _leg(fields, fid, dest)
    debit = withdraw_debit(_entry(fields, fid, leg.origin, dest))
    threatened = bool(hostile_sources(fields, dest, command.side))
    out = _append_use(values, OpportunityUse(command.side, UseKind.INDIVIDUAL, None, (fid,),
                                             (Withdraw(leg),)))
    out = _replace_formation(out, fid, cell=dest)
    out = checkpoint(mark(out, fid, WITHDRAW_MARKS))
    data = {"formation": fid.token, "from": _cell(leg.origin), "to": _cell(dest),
            "mode": leg.mode.name, "cost": debit, "marks": WITHDRAW_MARKS,
            "threatened": threatened}
    return Stage.WITHDRAW, out, data


def group_step_stage(values, command):
    fields = Fields(**values)
    work, moves = [], []
    for fid in command.members:
        f = fields.fmap[fid]
        dest = step(f.cell, command.direction)
        leg = _leg(fields, fid, dest)
        work.append(GroupStep(leg))
        moves.append({"formation": fid.token, "from": _cell(f.cell), "to": _cell(dest),
                      "mode": leg.mode.name, "cost": _entry(fields, fid, f.cell, dest)})
    out = _append_use(values, OpportunityUse(command.side, UseKind.GROUP, command.group,
                                             command.members, tuple(work)))
    # One simultaneous translation: every selected member vacates and enters.
    for fid, w in zip(command.members, work):
        out = _replace_formation(out, fid, cell=w.leg.destination)
    for fid in command.members:
        out = mark(out, fid, GROUP_MARKS)
    out = checkpoint(out)
    return Stage.GROUP_STEP, out, {"direction": command.direction, "moves": moves}


def pivot_stage(values, command):
    fields = Fields(**values)
    fid = command.formation
    before = fields.fmap[fid].facing
    after = (before + command.turn * command.steps) % 6
    out = _append_use(values, OpportunityUse(command.side, UseKind.INDIVIDUAL, None, (fid,),
                                             (Pivot(before, command.turn, command.steps),)))
    out = _replace_formation(out, fid, facing=after)
    out = checkpoint(mark(out, fid, PIVOT_MARKS * command.steps))
    data = {"formation": fid.token, "from": before, "to": after, "steps": command.steps}
    return Stage.PIVOT, out, data


def group_pivot_stage(values, command):
    fields = Fields(**values)
    work = tuple(GroupPivot(fields.fmap[fid].facing, command.turn) for fid in command.members)
    out = _append_use(values, OpportunityUse(command.side, UseKind.GROUP, command.group,
                                             command.members, work))
    for fid, w in zip(command.members, work):
        out = _replace_formation(out, fid, facing=(w.facing_before + command.turn) % 6)
        out = mark(out, fid, GROUP_MARKS)
    out = checkpoint(out)
    data = {"turn": command.turn, "members": [m.token for m in command.members]}
    return Stage.GROUP_PIVOT, out, data


def _withdrawn_asset(record, side):
    """P1 table 8.5, WITHDRAWN row."""
    return dataclasses.replace(record, assignment=Assignment.ASSIGNED, place=AtExit(side),
                               custodian=side, custody=Custody.OWN,
                               recovery=Recovery.NOT_APPLICABLE)


def evacuate_stage(values, command):
    """EVACUATE (ER08): WITHDRAWN on the retained exit cell; only AVAILABLE
    lots and the actor's mounts and ammunition move to the own exit."""
    fields = Fields(**values)
    fid = command.formation
    side = command.side
    cell = fields.fmap[fid].cell
    out = _append_use(values, OpportunityUse(side, UseKind.INDIVIDUAL, None, (fid,),
                                             (Evacuate(cell),)))
    out = _replace_formation(out, fid, disposition=Disposition.WITHDRAWN)
    out["personnel"] = tuple(
        dataclasses.replace(lot, place=AtExit(side))
        if lot.lineage == fid and lot.status is PersonnelStatus.AVAILABLE
        and type(lot.place) is InFormation else lot
        for lot in values["personnel"])
    out["mounts"] = tuple(_withdrawn_asset(m, side) if m.formation == fid else m
                          for m in values["mounts"])
    out["ammunition"] = tuple(_withdrawn_asset(a, side) if a.formation == fid else a
                              for a in values["ammunition"])
    out = checkpoint(mark(out, fid, EVACUATE_MARKS))
    data = {"formation": fid.token, "cell": _cell(cell), "exit_side": side.name,
            "exit_row": exit_row(end_of(fields.scenario, side)),
            "round": fields.clock.completed_rounds + 1}
    return Stage.EVACUATE, out, data


def movers_of(command):
    if type(command) is GroupMoveOrder:
        return command.members
    return (command.formation,)
