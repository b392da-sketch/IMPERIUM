"""Layer 7: field-level derived reads (contract 7.2, 8.3, 9, 12.4).

Every function here takes typed field values (records, tuples,
``Scenario``, ``Board``) or a ``Fields`` bundle of them, never a battle
state object, and this module imports no state module. The validator
(``invariants``) and the public facade (``api``) both call these
functions, so each derived value has exactly one definition.
"""

from .board import entry_cost
from .profile import TEMPLATES, mode_compatible, movement_cost_kind
from .records import (
    Assault, AtExit, AwaitingPrincipal, Evacuate, GroupPivot, GroupStep, Hold, Missile,
    Move, ObjectiveStatus, Opening, Pivot, Rally, Response, Rest, SideTotals, Terminal,
    Withdraw,
)
from .scenario import end_of, exit_row
from .values import (
    Activation, Assignment, Disposition, MovementMode, ObjectiveKind, PersonnelStatus,
    ResponseKind, Serviceability, Side, TemplateKind, UseKind, direction_of, distance,
    front_directions, in_front_sector, opponent,
)

BATTLEFIELD = frozenset((Disposition.ORGANIZED, Disposition.REFORMING, Disposition.ROUTING))
ORGANIZED_OR_REFORMING = frozenset((Disposition.ORGANIZED, Disposition.REFORMING))
OFFBOARD_OR_LOST = frozenset((
    Disposition.ROUTING, Disposition.WITHDRAWN, Disposition.DEPLETED, Disposition.SURRENDERED,
))


class Fields:
    """The eleven state field values, with lookup tables built once.

    A plain bundle of typed field values; it is not a state and performs
    no validation.
    """

    __slots__ = (
        "scenario", "phase", "clock", "sides", "formations", "authority", "personnel",
        "mounts", "ammunition", "contacts", "ledger", "roster", "fmap", "fround",
    )

    def __init__(self, scenario, phase, clock, sides, formations, authority, personnel,
                 mounts, ammunition, contacts, ledger):
        self.scenario = scenario
        self.phase = phase
        self.clock = clock
        self.sides = sides
        self.formations = formations
        self.authority = authority
        self.personnel = personnel
        self.mounts = mounts
        self.ammunition = ammunition
        self.contacts = contacts
        self.ledger = ledger
        roster = {}
        for entry in scenario.roster:
            roster.setdefault(entry.formation, entry)
        self.roster = roster
        fmap = {}
        for f in formations:
            fmap.setdefault(f.formation, f)
        self.fmap = fmap
        fround = {}
        if ledger is not None:
            for fr in ledger.formations:
                fround.setdefault(fr.formation, fr)
        self.fround = fround


# --------------------------------------------------------------------------
# Scenario and template reads


def template_of(scenario, kind):
    for t in scenario.profile.templates:
        if t.kind is kind:
            return t
    return TEMPLATES[kind]


def entry_of(fields, fid):
    return fields.roster.get(fid)


def side_of(fields, fid):
    return fields.roster[fid].side


def template_for(fields, fid):
    return template_of(fields.scenario, fields.roster[fid].template)


def exit_distance(scenario, side, cell):
    """Hex distance to the side's exit row (7.6, Q-E)."""
    return abs(cell.r - exit_row(end_of(scenario, side)))


# --------------------------------------------------------------------------
# Personnel, mounts and ammunition (8.2–8.4)


def lots_of(fields, fid):
    return tuple(l for l in fields.personnel if l.lineage == fid)


def status_sum(fields, fid, status):
    return sum(l.count for l in fields.personnel if l.lineage == fid and l.status is status)


def available(fields, fid):
    return status_sum(fields, fid, PersonnelStatus.AVAILABLE)


def wounded(fields, fid):
    return status_sum(fields, fid, PersonnelStatus.WOUNDED)


def dead(fields, fid):
    return status_sum(fields, fid, PersonnelStatus.DEAD)


def captured(fields, fid):
    return status_sum(fields, fid, PersonnelStatus.CAPTURED)


def mounts_of(fields, fid):
    return tuple(m for m in fields.mounts if m.formation == fid)


def account_of(fields, fid):
    for a in fields.ammunition:
        if a.formation == fid:
            return a
    return None


def contacts_of(fields, fid):
    return tuple(c for c in fields.contacts if c.low == fid or c.high == fid)


def serviceable_assigned_mounts(fields, fid):
    return sum(
        m.count for m in fields.mounts
        if m.formation == fid and m.serviceability is Serviceability.SERVICEABLE
        and m.assignment is Assignment.ASSIGNED
    )


def mount_stock(fields, fid):
    """S (8.3): every SERVICEABLE lot of fid, whatever its assignment."""
    return sum(
        m.count for m in fields.mounts
        if m.formation == fid and m.serviceability is Serviceability.SERVICEABLE
    )


def on_battlefield(formation):
    return formation.disposition in BATTLEFIELD


def movement_mode(fields, fid):
    """Present movement mode (8.3); None off the battlefield."""
    f = fields.fmap[fid]
    if not on_battlefield(f):
        return None
    kind = fields.roster[fid].template
    if kind is not TemplateKind.MOUNTED:
        return MovementMode.FOOT
    if available(fields, fid) <= serviceable_assigned_mounts(fields, fid):
        return MovementMode.MOUNTED
    return MovementMode.MIXED_FOOT


def in_contact(fields, fid):
    for c in fields.contacts:
        if c.low == fid or c.high == fid:
            return True
    return False


def side_totals(fields, side):
    av = wd = dd = cp = 0
    for l in fields.personnel:
        entry = fields.roster.get(l.lineage)
        if entry is None or entry.side is not side:
            continue
        if l.status is PersonnelStatus.AVAILABLE:
            av += l.count
        elif l.status is PersonnelStatus.WOUNDED:
            wd += l.count
        elif l.status is PersonnelStatus.DEAD:
            dd += l.count
        else:
            cp += l.count
    mounts = sum(
        m.count for m in fields.mounts
        if fields.roster.get(m.formation) is not None and fields.roster[m.formation].side is side
    )
    ammo = sum(
        a.carried for a in fields.ammunition
        if fields.roster.get(a.formation) is not None and fields.roster[a.formation].side is side
    )
    return SideTotals(av, wd, dd, cp, mounts, ammo)


# --------------------------------------------------------------------------
# Threat, safety, viability and the objective (9.3, 12.4)


def is_threat_source(fields, formation, cell):
    if formation.disposition is not Disposition.ORGANIZED:
        return False
    fid = formation.formation
    if available(fields, fid) <= 0:
        return False
    template = template_for(fields, fid)
    if not template.melee_capable:
        return False
    c = formation.condition
    if c.cohesion > 1 or c.morale > 1:
        return False
    if direction_of(formation.cell, cell) not in front_directions(formation.facing):
        return False
    mode = movement_mode(fields, fid)
    kind = movement_cost_kind(mode, template.kind)
    return entry_cost(fields.scenario.board, formation.cell, cell, kind) is not None


def threat_sources(fields, cell, side=None):
    board = fields.scenario.board
    if not (0 <= cell.q < board.width and 0 <= cell.r < board.height):
        return ()
    out = []
    for f in fields.formations:
        if side is not None and fields.roster[f.formation].side is not side:
            continue
        if is_threat_source(fields, f, cell):
            out.append(f.formation)
    out.sort(key=lambda fid: fid.token)
    return tuple(out)


def recovery_safe_now(fields, fid):
    f = fields.fmap[fid]
    if not on_battlefield(f):
        return False
    side = fields.roster[fid].side
    for g in fields.formations:
        if g.formation == fid or not on_battlefield(g):
            continue
        if fields.roster[g.formation].side is side:
            continue
        if distance(g.cell, f.cell) == 1:
            return False
    if threat_sources(fields, f.cell, opponent(side)):
        return False
    return not in_contact(fields, fid)


def is_viable(fields, formation):
    return (formation.disposition in ORGANIZED_OR_REFORMING
            and available(fields, formation.formation) > 0)


def viable_count(fields, side):
    return sum(
        1 for f in fields.formations
        if fields.roster[f.formation].side is side and is_viable(fields, f)
    )


def onmap_available(fields, side):
    return sum(
        available(fields, f.formation) for f in fields.formations
        if fields.roster[f.formation].side is side and on_battlefield(f)
    )


def exit_available(fields, side):
    return sum(
        l.count for l in fields.personnel
        if l.status is PersonnelStatus.AVAILABLE and type(l.place) is AtExit
        and fields.roster.get(l.lineage) is not None and fields.roster[l.lineage].side is side
    )


def objective_status(fields):
    """R3.6-02 in its stated order (9.3)."""
    objective = fields.scenario.board.objective
    occupant = None
    for f in fields.formations:
        if on_battlefield(f) and f.cell == objective:
            occupant = f
            break
    if occupant is None:
        return ObjectiveStatus(ObjectiveKind.UNHELD, None)
    fid = occupant.formation
    side = fields.roster[fid].side
    hostile = bool(threat_sources(fields, objective, opponent(side)))
    contact = in_contact(fields, fid)
    c = occupant.condition
    if (occupant.disposition is Disposition.ORGANIZED and available(fields, fid) > 0
            and c.cohesion <= 1 and c.morale <= 1 and not hostile and not contact):
        return ObjectiveStatus(ObjectiveKind.SECURE, side)
    if hostile or contact:
        return ObjectiveStatus(ObjectiveKind.CONTESTED, side)
    return ObjectiveStatus(ObjectiveKind.INSECURE, side)


# --------------------------------------------------------------------------
# Charges (7.2)


def _leg_cost(board, template_kind, leg):
    if not mode_compatible(leg.mode, template_kind):
        return None
    return entry_cost(board, leg.origin, leg.destination, movement_cost_kind(leg.mode, template_kind))


def work_charge(scenario, entry, work):
    """The one effort calculation (7.2); None if a leg has no entry cost.

    It prices initiated effort only. It decides nothing about admission,
    targets, current eligibility or ledger membership.
    """
    t = type(work)
    board = scenario.board
    kind = entry.template
    if t is Hold:
        return 0
    if t is Move:
        total = 0
        for leg in work.legs:
            cost = _leg_cost(board, kind, leg)
            if cost is None:
                return None
            total += cost
        return total
    if t is Withdraw:
        cost = _leg_cost(board, kind, work.leg)
        if cost is None:
            return None
        return 2 + (cost - 1)
    if t is GroupStep:
        return _leg_cost(board, kind, work.leg)
    if t is Pivot:
        return work.steps
    if t is Assault:
        return 2
    if t is Missile:
        return 1
    if t is Rally or t is Rest or t is Evacuate:
        return 2
    if t is GroupPivot:
        return 1
    if t is Response:
        return 1
    return None


# --------------------------------------------------------------------------
# Ledger reads (9.1, 9.2); every function is phase-aware


def phase_kind(fields):
    return type(fields.phase)


def round_number(clock):
    return clock.completed_rounds + 1


def round_first_side(clock):
    return Side.S0 if round_number(clock) % 2 == 1 else Side.S1


def ledger_entries(ledger):
    """``(use_index, use, member, work)`` for every member's work record."""
    for ui, use in enumerate(ledger.uses):
        for member, work in zip(use.members, use.work):
            yield ui, use, member, work


def works_of(ledger, fid):
    return [work for _, _, member, work in ledger_entries(ledger) if member == fid]


def is_member(ledger, fid):
    for use in ledger.uses:
        for m in use.members:
            if m == fid:
                return True
    return False


def non_pass_uses(ledger, side):
    return sum(1 for u in ledger.uses if u.side is side and u.kind is not UseKind.PASS)


def has_pass(ledger, side):
    return any(u.side is side and u.kind is UseKind.PASS for u in ledger.uses)


def ledger_side_finished(scenario, ledger, side):
    return has_pass(ledger, side) or non_pass_uses(ledger, side) >= scenario.profile.opportunities


def opened_effort(scenario, fround):
    return scenario.profile.effort if fround.opened_eligible else 0


def round_charge(fields, fid):
    """Sum of fid's work charges and response this round, or None."""
    entry = fields.roster[fid]
    total = 0
    for work in works_of(fields.ledger, fid):
        c = work_charge(fields.scenario, entry, work)
        if c is None:
            return None
        total += c
    fr = fields.fround[fid]
    if fr.response is not None:
        total += work_charge(fields.scenario, entry, fr.response)
    return total


def _awaiting(fields):
    return type(fields.phase) is AwaitingPrincipal and fields.ledger is not None


def side_finished(fields, side):
    t = type(fields.phase)
    if t is Opening:
        return False
    if t is Terminal:
        return True
    return ledger_side_finished(fields.scenario, fields.ledger, side)


def usable_opportunities(fields, side):
    if not _awaiting(fields):
        return 0
    if side_finished(fields, side):
        return 0
    return fields.scenario.profile.opportunities - non_pass_uses(fields.ledger, side)


def capacity_remaining(fields, side):
    if not _awaiting(fields):
        return None
    return fields.scenario.profile.opportunities - non_pass_uses(fields.ledger, side)


def projected_capacity(fields, side):
    if type(fields.phase) is Terminal:
        return None
    return fields.scenario.profile.opportunities


def next_side(fields):
    if type(fields.phase) is AwaitingPrincipal:
        return fields.phase.side
    return None


def effort_charged(fields, fid):
    if not _awaiting(fields):
        return None
    return round_charge(fields, fid)


def effort_remaining(fields, fid):
    if not _awaiting(fields):
        return None
    charged = round_charge(fields, fid)
    if charged is None:
        return None
    return opened_effort(fields.scenario, fields.fround[fid]) - charged


def would_open_eligible(fields, fid):
    f = fields.fmap[fid]
    return f.disposition in ORGANIZED_OR_REFORMING and available(fields, fid) > 0


def projected_opening_effort(fields, fid):
    t = type(fields.phase)
    if t is Opening:
        return fields.scenario.profile.effort if would_open_eligible(fields, fid) else 0
    if t is Terminal:
        return None
    return opened_effort(fields.scenario, fields.fround[fid])


def activation(fields, fid):
    if not _awaiting(fields):
        return Activation.CLOSED
    fr = fields.fround[fid]
    if not fr.opened_eligible:
        return Activation.INELIGIBLE
    if is_member(fields.ledger, fid):
        return Activation.SPENT
    f = fields.fmap[fid]
    side = fields.roster[fid].side
    if (ledger_side_finished(fields.scenario, fields.ledger, side) or fr.displacement_attempted
            or f.disposition not in ORGANIZED_OR_REFORMING or available(fields, fid) == 0):
        return Activation.FORFEITED
    return Activation.READY


def response_allowance_unused(fields, fid):
    if not _awaiting(fields):
        return False
    fr = fields.fround[fid]
    f = fields.fmap[fid]
    return (fr.opened_eligible and fr.response is None and available(fields, fid) > 0
            and f.disposition not in OFFBOARD_OR_LOST)


def response_possible(fields, fid):
    if not response_allowance_unused(fields, fid):
        return False
    remaining = effort_remaining(fields, fid)
    f = fields.fmap[fid]
    return (remaining is not None and remaining >= 1
            and f.disposition is Disposition.ORGANIZED
            and f.condition.cohesion <= 1 and not in_contact(fields, fid))


def effort_usable(fields, fid):
    if not _awaiting(fields):
        return 0
    if activation(fields, fid) is Activation.READY or response_possible(fields, fid):
        remaining = effort_remaining(fields, fid)
        return remaining if remaining is not None else 0
    return 0


def rest_order_exists(fields, fid):
    if not _awaiting(fields):
        return None
    return any(type(w) is Rest for w in works_of(fields.ledger, fid))


def full_safe_interval(fields, fid):
    if not _awaiting(fields):
        return None
    fr = fields.fround[fid]
    return (fr.safe_latch and not fr.incoming and not fr.exerted and not fr.displaced
            and on_battlefield(fields.fmap[fid]))


def rest_benefit_pending(fields, fid):
    if not _awaiting(fields):
        return False
    fr = fields.fround[fid]
    return (rest_order_exists(fields, fid) and full_safe_interval(fields, fid)
            and not fr.exerted and not fr.displaced and not fr.incoming
            and fields.fmap[fid].condition.fatigue >= 1)


def elapsed_minutes(fields):
    t = type(fields.phase)
    minutes = fields.scenario.profile.round_minutes
    if t is Opening:
        return 0
    if t is Terminal:
        return minutes * fields.phase.record.charged_rounds
    return minutes * fields.clock.completed_rounds


def current_round(fields):
    if type(fields.phase) is AwaitingPrincipal:
        return round_number(fields.clock)
    return None


def discharges(fields, fid):
    """This round's discharges of fid: Missile work plus a missile response."""
    n = sum(1 for w in works_of(fields.ledger, fid) if type(w) is Missile)
    fr = fields.fround.get(fid)
    if fr is not None and fr.response is not None and fr.response.kind is ResponseKind.DEFENSIVE_MISSILE:
        n += 1
    return n



# --------------------------------------------------------------------------
# Shared record predicates (R20, R21(b), R21(c)); used by the validator and
# by the public charge facade


def _cell_on(board, cell):
    return 0 <= cell.q < board.width and 0 <= cell.r < board.height


def response_ok(scenario, roster, fid, response):
    """R20: a distinct opposing roster target; a missile needs a missile template."""
    own = roster.get(fid)
    target = roster.get(response.target)
    if own is None or target is None or response.target == fid or target.side is own.side:
        return False
    if response.kind is ResponseKind.DEFENSIVE_MISSILE:
        return template_of(scenario, own.template).missile_range is not None
    return True


def assault_ok(scenario, roster, fid, assault):
    """R21(b) on the recorded geometry; the mode pair must already suit the template."""
    own = roster.get(fid)
    target = roster.get(assault.target)
    board = scenario.board
    if own is None or target is None or assault.target == fid or target.side is own.side:
        return False
    if not (_cell_on(board, assault.origin) and _cell_on(board, assault.target_cell)):
        return False
    if not template_of(scenario, own.template).melee_capable:
        return False
    if direction_of(assault.origin, assault.target_cell) not in front_directions(assault.facing):
        return False
    if not mode_compatible(assault.mode, own.template):
        return True
    kind = movement_cost_kind(assault.mode, own.template)
    return entry_cost(board, assault.origin, assault.target_cell, kind) is not None


def missile_ok(scenario, roster, fid, missile):
    """R21(c) on the recorded geometry and front sector."""
    own = roster.get(fid)
    target = roster.get(missile.target)
    board = scenario.board
    if own is None or target is None or missile.target == fid or target.side is own.side:
        return False
    if not (_cell_on(board, missile.origin) and _cell_on(board, missile.target_cell)):
        return False
    rng = template_of(scenario, own.template).missile_range
    if rng is None or not 1 <= distance(missile.origin, missile.target_cell) <= rng:
        return False
    return in_front_sector(missile.origin, missile.target_cell, missile.facing)
