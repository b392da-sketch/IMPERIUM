"""Layer 8: the clause register and the internal field validator
(contract 10, 4.1 E05).

``validate_fields`` takes candidate field values, never a state object,
and returns every violation sorted by ``(clause, path)``. It re-runs every
local T clause first; when any fails, the cross-record clauses are
skipped, so one bad field does not cascade. Implications whose
prerequisite failed are skipped too. There is no ``try``/``except``.
"""

from .board import F01_BOARDS, entry_cost, statically_traversable
from .canon import full_digest, normalized_digest, opening_projection_digest
from .descriptors import DEFENSIVE_FIXTURE_ID, find_descriptor
from .errors import Violation, violation_key
from .ids import GroupId
from .profile import PROFILES, mode_compatible, movement_cost_kind, step_cap
from .queries import (
    BATTLEFIELD, ORGANIZED_OR_REFORMING, Fields, available, discharges, exit_available,
    exit_distance, mount_stock, objective_status, on_battlefield, onmap_available,
    assault_ok, missile_ok, recovery_safe_now, response_ok, round_first_side, template_for,
    viable_count, work_charge, works_of,
)
from .records import (
    AmmunitionAccount, Assault, AtExit, AwaitingPrincipal, Clock, Contact, Evacuate, Formation,
    GroupPivot, GroupStep, Hold, InFormation, Missile, MountLot, Move, OnCell, Opening,
    PHASE_CLASSES, PersonnelLot, Pivot, Rally, Rest, RoundLedger, SideState, Terminal,
    Withdraw,
)
from .scenario import (
    F01_GROUPS, F01_ROSTER, PROFILE_ID, RULES_BASELINE, SCENARIO_ID, SCENARIO_VERSION,
    SOURCES, Scenario,
)
from .values import (
    SPECS, Assignment, Authority, CapturedCondition, Custody, DefeatClass, Disposition, EnumK,
    Fixed, FixtureClass, Hex, IdK, MoveEnd, MovementMode, ObjectiveKind, Opt, PersonnelStatus,
    Posture, RecK, Recovery, ResultKind, Serviceability, Side,
    TemplateKind, TerminalReason, TerminationPoint, UseKind, Var, direction_of, distance,
    field_values, first_failure, front_directions, opponent,
    rear_directions,
)

# The state's own fields (6.2), in declared order.
ROOT_SPEC = (
    ("scenario", RecK((Scenario,))),
    ("phase", RecK(PHASE_CLASSES)),
    ("clock", RecK((Clock,))),
    ("sides", Fixed((RecK((SideState,)), RecK((SideState,))), key=(("side",),))),
    ("formations", Var(RecK((Formation,)))),
    ("authority", Var(Fixed((IdK(GroupId), EnumK(Authority))))),
    ("personnel", Var(RecK((PersonnelLot,)), key=(("lot",),))),
    ("mounts", Var(RecK((MountLot,)), key=(("lot",),))),
    ("ammunition", Var(RecK((AmmunitionAccount,)), key=(("formation",),))),
    ("contacts", Var(RecK((Contact,)), key=(("low",), ("high",)))),
    ("ledger", Opt(RecK((RoundLedger,)))),
)

ZERO_VIABILITY = frozenset((
    TerminalReason.ZERO_VIABILITY_UNILATERAL,
    TerminalReason.ZERO_VIABILITY_MUTUAL_LOSS,
    TerminalReason.ZERO_VIABILITY_MUTUAL_ABANDONMENT,
))
DEADLINE = frozenset((
    TerminalReason.DEADLINE_ABANDONMENT,
    TerminalReason.DEADLINE_MUTUAL_WITHDRAWAL,
    TerminalReason.DEADLINE_OBJECTIVE_VICTORY,
    TerminalReason.DEADLINE_OBJECTIVE_UNRESOLVED,
))
INITIAL_REASONS = frozenset((
    TerminalReason.ZERO_VIABILITY_UNILATERAL,
    TerminalReason.ZERO_VIABILITY_MUTUAL_LOSS,
    TerminalReason.MUTUAL_CAPITULATION,
))
EXERTING_WORK = (Move, Pivot, Assault, Missile, Withdraw, Evacuate, GroupStep, GroupPivot)
MOVEMENT_WORK = (Move, Withdraw, GroupStep)
MODE_ORDER = {MovementMode.MIXED_FOOT: 0, MovementMode.MOUNTED: 1, MovementMode.FOOT: 0}
SIDE_INDEX = {Side.S0: 0, Side.S1: 1}


# --------------------------------------------------------------------------
# Local re-validation (10.0: validate_state re-runs every T clause)


def _walk_local(kind, value, pointer, out):
    t = type(kind)
    if t is RecK:
        failure = first_failure(type(value), field_values(value))
        if failure is not None:
            clause, local, detail = failure
            out.append(Violation(clause, f"{pointer}/{local}", detail))
            return
        for name, sub in SPECS[type(value)][0]:
            _walk_local(sub, object.__getattribute__(value, name), f"{pointer}/{name}", out)
    elif t is Opt:
        if value is not None:
            _walk_local(kind.inner, value, pointer, out)
    elif t is Var:
        for i, x in enumerate(value):
            _walk_local(kind.elem, x, f"{pointer}/{i}", out)
    elif t is Fixed:
        for i, (sub, x) in enumerate(zip(kind.elems, value)):
            _walk_local(sub, x, f"{pointer}/{i}", out)


def local_violations(values):
    out = []
    for (name, kind), value in zip(ROOT_SPEC, values):
        failure = kind.check(value, name)
        if failure is not None:
            clause, local, detail = failure
            out.append(Violation(clause, "/" + local, detail))
            continue
        _walk_local(kind, value, "/" + name, out)
    return out


def _iter_hexes(kind, value, pointer):
    t = type(kind)
    if t is RecK:
        if type(value) is Hex:
            yield pointer, value
            return
        for name, sub in SPECS[type(value)][0]:
            yield from _iter_hexes(sub, object.__getattribute__(value, name), f"{pointer}/{name}")
    elif t is Opt:
        if value is not None:
            yield from _iter_hexes(kind.inner, value, pointer)
    elif t is Var:
        for i, x in enumerate(value):
            yield from _iter_hexes(kind.elem, x, f"{pointer}/{i}")
    elif t is Fixed:
        for i, (sub, x) in enumerate(zip(kind.elems, value)):
            yield from _iter_hexes(sub, x, f"{pointer}/{i}")


# --------------------------------------------------------------------------
# The validator


class _Collector:
    __slots__ = ("items",)

    def __init__(self):
        self.items = []

    def add(self, clause, path, detail):
        self.items.append(Violation(clause, path, detail))


def validate_fields(scenario, phase, clock, sides, formations, authority, personnel, mounts,
                    ammunition, contacts, ledger):
    """All violations of the candidate field values, sorted (10.0)."""
    values = (scenario, phase, clock, sides, formations, authority, personnel, mounts,
              ammunition, contacts, ledger)
    local = local_violations(values)
    if local:
        return tuple(sorted(local, key=violation_key))
    v = _Collector()
    fields = Fields(*values)
    structural_ok = _check_scenario(fields, v)
    _check_provenance(fields, values, v)
    if structural_ok:
        _check_dynamic(fields, v)
    return tuple(sorted(v.items, key=violation_key))


# ---- scenario, provenance, genesis (10.3)


def _check_scenario(fields, v):
    sc = fields.scenario
    ok = True
    registered = PROFILES.get(sc.profile.profile_id)
    if registered is None or sc.profile != registered:
        v.add("P01", "/scenario/profile", "profile differs from the registered profile")
        ok = False
    prov = sc.provenance
    base = "/scenario/provenance"
    if prov.scenario_id != SCENARIO_ID:
        v.add("P02", base + "/scenario_id", "wrong scenario id")
    if prov.scenario_version != SCENARIO_VERSION:
        v.add("P02", base + "/scenario_version", "wrong scenario version")
    if prov.profile_id != PROFILE_ID:
        v.add("P02", base + "/profile_id", "wrong profile id")
    if prov.rules_baseline != RULES_BASELINE:
        v.add("P02", base + "/rules_baseline", "wrong rules baseline")
    if prov.sources != SOURCES:
        v.add("P02", base + "/sources", "wrong source digests")
    if sc.board != F01_BOARDS[prov.variant]:
        v.add("P03", "/scenario/board", "board differs from the variant's board")
        ok = False
    if sc.roster != F01_ROSTER:
        v.add("P04", "/scenario/roster", "roster differs from the F01 roster")
        ok = False
    if sc.groups != F01_GROUPS:
        v.add("P05", "/scenario/groups", "groups differ from the F01 groups")
        ok = False
    if sc.first_side is not Side.S0:
        v.add("P06", "/scenario/first_side", "first side must be S0")
    return ok


def _check_provenance(fields, values, v):
    prov = fields.scenario.provenance
    cls = prov.fixture_class
    d = find_descriptor(prov.fixture_id)
    base = "/scenario/provenance"
    if cls is FixtureClass.ADVERSARIAL_TEST:
        if not prov.fixture_id.token.startswith("ADV-") or d is not None:
            v.add("P09", base + "/fixture_id", "adversarial id must start ADV- and be unregistered")
    else:
        clause = "P07" if cls is FixtureClass.CANONICAL_OPENING else "P08"
        if (d is None or d.fixture_class is not cls or d.variant is not prov.variant
                or d.orientation is not prov.orientation or d.profile_id != prov.profile_id):
            v.add(clause, base + "/fixture_id", "no matching registered descriptor")
            d = None
        elif prov.origin_digest != d.normalized_genesis_digest:
            v.add(clause, base + "/origin_digest", "origin digest differs from the descriptor")
        if d is not None:
            phase = fields.phase
            if type(phase) is Opening:
                if normalized_digest(values) != d.normalized_genesis_digest:
                    v.add("P10", "", "state differs from its registered genesis")
            elif (type(phase) is Terminal and phase.record.point is TerminationPoint.INITIAL_CHECK
                  and d.genesis_phase == "OPENING"):
                if opening_projection_digest(values) != d.normalized_genesis_digest:
                    v.add("P10", "", "initial terminal differs from its registered genesis")
    if prov.fixture_id == DEFENSIVE_FIXTURE_ID:
        d8 = find_descriptor(DEFENSIVE_FIXTURE_ID)
        if full_digest(values) != d8.full_genesis_digest:
            v.add("P10", "", "defensive fixture differs from its registered genesis")


# ---- dynamic clauses


def _check_dynamic(fields, v):
    for pointer, cell in _iter_dynamic_hexes(fields):
        if not (0 <= cell.q < fields.scenario.board.width and 0 <= cell.r < fields.scenario.board.height):
            v.add("B01", pointer, "cell off the board")
    if not _check_formations_roster(fields, v):
        return
    _check_formations(fields, v)
    _check_personnel(fields, v)
    _check_assets(fields, v)
    _check_authority(fields, v)
    _check_contacts(fields, v)
    _check_phase(fields, v)


def _iter_dynamic_hexes(fields):
    for name, kind in ROOT_SPEC[1:]:
        yield from _iter_hexes(kind, getattr(fields, name), "/" + name)


def _check_formations_roster(fields, v):
    roster = fields.scenario.roster
    formations = fields.formations
    if len(formations) != len(roster):
        v.add("F01", "/formations", "one formation per roster entry")
        return False
    ok = True
    for i, (f, e) in enumerate(zip(formations, roster)):
        if f.formation != e.formation:
            v.add("F01", f"/formations/{i}/formation", "formation out of roster order")
            ok = False
    return ok


def _terminal_record(fields):
    if type(fields.phase) is Terminal:
        return fields.phase.record
    return None


def _capitulation_loser(fields):
    """The losing side of a CAPITULATION terminal, else None."""
    rec = _terminal_record(fields)
    if rec is None or rec.reason is not TerminalReason.CAPITULATION or rec.winner is None:
        return None
    return opponent(rec.winner)


def _is_capitulation(fields):
    rec = _terminal_record(fields)
    return rec is not None and rec.reason is TerminalReason.CAPITULATION


def _check_formations(fields, v):
    seen = {}
    loser = _capitulation_loser(fields)
    for i, f in enumerate(fields.formations):
        p = f"/formations/{i}"
        entry = fields.roster[f.formation]
        side = entry.side
        if on_battlefield(f):
            key = (f.cell.q, f.cell.r)
            if key in seen:
                v.add("F02", p + "/cell", "two battlefield formations on one cell")
            seen[key] = i
        c = f.condition
        if c.exertion >= fields.scenario.profile.exertion_threshold:
            v.add("F03", p + "/condition/exertion", "exertion at or above the threshold")
        if f.disposition is Disposition.ORGANIZED and c.cohesion == 2 and c.morale == 2:
            v.add("F04", p + "/condition", "organized at C2 and M2")
        if f.disposition is Disposition.WITHDRAWN:
            if exit_distance(fields.scenario, side, f.cell) != 0:
                v.add("F05", p + "/cell", "withdrawn formation off its exit row")
        avail = available(fields, f.formation)
        if f.disposition in BATTLEFIELD or f.disposition is Disposition.WITHDRAWN:
            if avail < 1:
                v.add("F06", p + "/disposition", "no available personnel")
        elif avail != 0:
            v.add("F06", p + "/disposition", "available personnel on a lost formation")
        if f.disposition is Disposition.SURRENDERED:
            if loser is None or side is not loser:
                v.add("F07", p + "/disposition", "surrendered outside a capitulation loss")
        if loser is not None and side is loser and on_battlefield(f):
            v.add("F08", p + "/disposition", "capitulated side still on the map")


def _check_personnel(fields, v):
    loser = _capitulation_loser(fields)
    capitulation = _is_capitulation(fields)
    totals = {}
    seen = set()
    for i, lot in enumerate(fields.personnel):
        p = f"/personnel/{i}"
        entry = fields.roster.get(lot.lineage)
        if entry is None:
            v.add("L01", p + "/lineage", "lineage is not a roster formation")
            continue
        totals[lot.lineage] = totals.get(lot.lineage, 0) + lot.count
        side = entry.side
        f = fields.fmap[lot.lineage]
        place = lot.place
        status = lot.status
        if status is PersonnelStatus.AVAILABLE:
            if f.disposition in BATTLEFIELD:
                if place != InFormation(lot.lineage):
                    v.add("L03", p + "/place", "available lot not with its formation")
            elif f.disposition is Disposition.WITHDRAWN:
                if place != AtExit(side):
                    v.add("L03", p + "/place", "withdrawn survivors not at the own exit")
            else:
                v.add("L03", p + "/status", "available lot of a lost formation")
            if lot.custodian is not side:
                v.add("L03", p + "/custodian", "available lot not in own custody")
            if lot.origin is not None:
                v.add("L03", p + "/origin", "available lot with an origin")
        elif status is PersonnelStatus.WOUNDED:
            if type(place) is not OnCell:
                v.add("L04", p + "/place", "wounded lot not on a cell")
            if lot.custodian is not side:
                v.add("L04", p + "/custodian", "wounded lot not in own custody")
        elif status is PersonnelStatus.DEAD:
            if type(place) is not OnCell:
                v.add("L05", p + "/place", "dead lot not on a cell")
        else:
            if type(place) is not OnCell:
                v.add("L06", p + "/place", "captured lot not on a cell")
            if lot.custodian is not opponent(side):
                v.add("L06", p + "/custodian", "captured lot not in opponent custody")
            if not capitulation:
                v.add("L06", p + "/status", "captured lot outside a capitulation terminal")
            elif loser is None or side is not loser:
                v.add("L06", p + "/lineage", "captured lot of the winning side")
            if lot.captured is CapturedCondition.FIT:
                if f.disposition is not Disposition.SURRENDERED or place != OnCell(f.cell):
                    v.add("L07", p + "/place", "captured fit lot not at its surrendered formation")
        if loser is not None and side is loser:
            if status is PersonnelStatus.WOUNDED:
                v.add("L08", p + "/status", "loser's wounded not transferred")
            if status is PersonnelStatus.AVAILABLE and type(place) is InFormation:
                v.add("L08", p + "/status", "loser's available personnel not captured")
        key = (lot.lineage.token, status.name, lot.captured.name if lot.captured else None,
               _place_key(place), lot.custodian.name if lot.custodian else None,
               lot.origin.token if lot.origin else None)
        if key in seen:
            v.add("L09", p, "duplicate lot classification")
        seen.add(key)
    for e in fields.scenario.roster:
        expected = template_for(fields, e.formation).personnel
        if totals.get(e.formation, 0) != expected:
            v.add("L02", "/personnel", f"personnel of {e.formation.token} do not sum to its template")


def _place_key(place):
    t = type(place)
    if t is InFormation:
        return ("InFormation", place.formation.token)
    if t is OnCell:
        return ("OnCell", place.cell.q, place.cell.r)
    return ("AtExit", place.side.name)


def _expected_asset(fields, f, side):
    """(assignment, place, custodian, custody, recovery) per table 8.5."""
    d = f.disposition
    if d in BATTLEFIELD:
        return (Assignment.ASSIGNED, InFormation(f.formation), side, Custody.OWN, Recovery.NOT_APPLICABLE)
    if d is Disposition.WITHDRAWN:
        return (Assignment.ASSIGNED, AtExit(side), side, Custody.OWN, Recovery.NOT_APPLICABLE)
    if d is Disposition.DEPLETED:
        return (Assignment.UNASSIGNED_RECORDED, OnCell(f.cell), side, Custody.OWN, Recovery.UNRESOLVED)
    return (Assignment.UNASSIGNED_RECORDED, OnCell(f.cell), opponent(side),
            Custody.SURRENDERED_INVENTORY, Recovery.NOT_APPLICABLE)


def _check_asset_record(fields, record, pointer, v):
    f = fields.fmap[record.formation]
    side = fields.roster[record.formation].side
    expected = _expected_asset(fields, f, side)
    actual = (record.assignment, record.place, record.custodian, record.custody, record.recovery)
    names = ("assignment", "place", "custodian", "custody", "recovery")
    for name, a, e in zip(names, actual, expected):
        if a != e:
            v.add("A03", f"{pointer}/{name}", "asset record disagrees with table 8.5")
            break


def _check_assets(fields, v):
    by_formation = {}
    allowed_unserviceable = fields.scenario.provenance.fixture_class is not FixtureClass.CANONICAL_OPENING
    for i, m in enumerate(fields.mounts):
        p = f"/mounts/{i}"
        if m.formation not in fields.roster:
            v.add("A01", p + "/formation", "mount lot of an unknown formation")
            continue
        by_formation.setdefault(m.formation, []).append(m)
        _check_asset_record(fields, m, p, v)
        if m.serviceability is Serviceability.UNSERVICEABLE and not allowed_unserviceable:
            v.add("A04", p + "/serviceability", "unserviceable mounts in a canonical state")
    for e in fields.scenario.roster:
        lots = by_formation.get(e.formation, [])
        template = template_for(fields, e.formation)
        if template.mounts == 0:
            if lots:
                v.add("A01", "/mounts", f"mount lot on {e.formation.token}, which has no mounts")
            continue
        kinds = [m.serviceability for m in lots]
        if (not 1 <= len(lots) <= 2 or len(set(kinds)) != len(kinds)
                or sum(m.count for m in lots) != template.mounts):
            v.add("A01", "/mounts", f"mount lots of {e.formation.token} are malformed")
    seen = set()
    for i, a in enumerate(fields.ammunition):
        p = f"/ammunition/{i}"
        if a.formation not in fields.roster:
            v.add("A02", p + "/formation", "account of an unknown formation")
            continue
        seen.add(a.formation)
        template = template_for(fields, a.formation)
        if template.ammunition == 0:
            v.add("A02", p, "account for a template without ammunition")
            continue
        if a.carried + a.expended != template.ammunition:
            v.add("A02", p + "/carried", "carried plus expended differs from the template")
        _check_asset_record(fields, a, p, v)
    for e in fields.scenario.roster:
        if template_for(fields, e.formation).ammunition and e.formation not in seen:
            v.add("A02", "/ammunition", f"missing account for {e.formation.token}")


def _check_authority(fields, v):
    groups = fields.scenario.groups
    authority = fields.authority
    if len(authority) != len(groups):
        v.add("G01", "/authority", "one authority entry per scenario group")
        return
    for i, ((gid, _), spec) in enumerate(zip(authority, groups)):
        if gid != spec.group:
            v.add("G01", f"/authority/{i}", "authority out of scenario group order")


def _check_contacts(fields, v):
    board = fields.scenario.board
    for i, c in enumerate(fields.contacts):
        p = f"/contacts/{i}"
        low = fields.roster.get(c.low)
        high = fields.roster.get(c.high)
        if low is None or high is None or not c.low.token < c.high.token or low.side is high.side:
            v.add("K01", p, "contact parties must be ordered opposing roster formations")
            continue
        fl = fields.fmap[c.low]
        fh = fields.fmap[c.high]
        if fl.disposition not in ORGANIZED_OR_REFORMING or fh.disposition not in ORGANIZED_OR_REFORMING:
            v.add("K02", p, "a contact party is not organized or reforming")
        if distance(fl.cell, fh.cell) != 1 or c.edge != (fl.cell, fh.cell):
            v.add("K03", p + "/edge", "contact edge is not the parties' adjacent cells")
        elif not (statically_traversable(board, fl.cell, fh.cell)
                  or statically_traversable(board, fh.cell, fl.cell)):
            v.add("K04", p + "/edge", "contact edge is closed in both directions")


# ---- phases (10.9–10.11)


def _check_phase(fields, v):
    t = type(fields.phase)
    clock = fields.clock
    postures = tuple(s.posture for s in fields.sides)
    if (fields.ledger is not None) != (t is AwaitingPrincipal):
        v.add("R01", "/ledger", "ledger present iff awaiting a principal order")
    if t is Opening:
        if clock.completed_rounds != 0 or clock.event_cursor != 0:
            v.add("H01", "/clock", "opening clock must be zero")
        if any(p is not Posture.CONTESTING for p in postures):
            v.add("H01", "/sides", "opening postures must be contesting")
    elif t is AwaitingPrincipal:
        if clock.completed_rounds > fields.scenario.profile.rounds - 1:
            v.add("H02", "/clock/completed_rounds", "no round remains")
        if viable_count(fields, Side.S0) < 1 or viable_count(fields, Side.S1) < 1:
            v.add("H02", "/formations", "a side has no viable formation")
        if fields.ledger is not None:
            _check_ledger(fields, v)
    else:
        _check_terminal(fields, v)


def _check_terminal(fields, v):
    rec = fields.phase.record
    clock = fields.clock
    base = "/phase/record"
    point = rec.point
    charged = rec.charged_rounds
    completed = clock.completed_rounds
    rounds = fields.scenario.profile.rounds
    # H03
    if point is TerminationPoint.INITIAL_CHECK:
        ok = charged == 0 and completed == 0
    elif point is TerminationPoint.ROUND_END:
        ok = charged == completed and charged >= 1
    else:
        ok = charged == completed + 1
    if not ok or charged > rounds:
        v.add("H03", base + "/charged_rounds", "charged rounds disagree with the point and clock")
    # X01
    derived_postures = tuple(s.posture for s in fields.sides)
    viable = (viable_count(fields, Side.S0), viable_count(fields, Side.S1))
    if rec.postures != derived_postures:
        v.add("X01", base + "/postures", "stored postures disagree")
    if rec.viable != viable:
        v.add("X01", base + "/viable", "stored viability disagrees")
    if rec.objective != objective_status(fields):
        v.add("X01", base + "/objective", "stored objective status disagrees")
    if rec.onmap_available != (onmap_available(fields, Side.S0), onmap_available(fields, Side.S1)):
        v.add("X01", base + "/onmap_available", "stored on-map counts disagree")
    if rec.exit_available != (exit_available(fields, Side.S0), exit_available(fields, Side.S1)):
        v.add("X01", base + "/exit_available", "stored exit counts disagree")
    reason = rec.reason
    captured_lots = [l for l in fields.personnel if l.status is PersonnelStatus.CAPTURED]
    if reason is TerminalReason.CAPITULATION:
        _check_capitulation(fields, rec, base, v)
    elif reason in ZERO_VIABILITY:
        _check_zero_viability(fields, rec, viable, derived_postures, captured_lots, base, v)
    elif reason in DEADLINE:
        _check_deadline(fields, rec, viable, derived_postures, captured_lots, base, rounds, v)
    else:
        _check_mutual_capitulation(fields, rec, captured_lots, base, v)
    # X06
    if point is TerminationPoint.INITIAL_CHECK:
        if reason not in INITIAL_REASONS:
            v.add("X06", base + "/reason", "reason not allowed at the initial check")
        if any(p is not Posture.CONTESTING for p in derived_postures):
            v.add("X06", "/sides", "withdrawing posture at the initial check")
    if point is TerminationPoint.ROUND_END and charged < rounds and reason not in ZERO_VIABILITY:
        v.add("X06", base + "/reason", "only zero-viability reasons before the deadline")
    if reason in DEADLINE and not (point is TerminationPoint.ROUND_END and charged == rounds):
        v.add("X06", base + "/point", "deadline reason before the deadline")
    if reason is TerminalReason.CAPITULATION and point is not TerminationPoint.AFTER_ROOT:
        v.add("X06", base + "/point", "capitulation only after a root")


def _check_capitulation(fields, rec, base, v):
    ok = rec.result is ResultKind.VICTORY and rec.winner is not None
    if ok:
        loser = opponent(rec.winner)
        li, wi = SIDE_INDEX[loser], SIDE_INDEX[rec.winner]
        if rec.defeat[li] is not DefeatClass.CAPITULATED or rec.defeat[wi] is not None:
            ok = False
    if not ok:
        v.add("X02", base + "/defeat", "capitulation needs one capitulated loser and a victor")
        return
    if rec.point is not TerminationPoint.AFTER_ROOT or rec.charged_rounds < 1:
        v.add("X02", base + "/point", "capitulation only after a root, charged at least 1")
    fit = [
        l for l in fields.personnel
        if l.status is PersonnelStatus.CAPTURED and l.captured is CapturedCondition.FIT
        and fields.roster.get(l.lineage) is not None and fields.roster[l.lineage].side is loser
    ]
    if not fit:
        v.add("X02", "/personnel", "capitulation with nothing captured")


def _defeat_class(fields, side):
    mine = [f for f in fields.formations if fields.roster[f.formation].side is side]
    if any(f.disposition is Disposition.ROUTING for f in mine):
        return DefeatClass.COLLAPSE
    withdrawn = any(f.disposition is Disposition.WITHDRAWN for f in mine)
    depleted = any(f.disposition is Disposition.DEPLETED for f in mine)
    if withdrawn and not depleted:
        return DefeatClass.DEPARTURE
    return DefeatClass.DEPLETION_MIXED


def _check_zero_viability(fields, rec, viable, postures, captured_lots, base, v):
    if captured_lots:
        v.add("X03", "/personnel", "captured lots in a zero-viability terminal")
    for side in Side:
        i = SIDE_INDEX[side]
        expected = _defeat_class(fields, side) if viable[i] == 0 else None
        if rec.defeat[i] is not expected:
            v.add("X03", f"{base}/defeat/{i}", "defeat class disagrees with the board")
    zero = [s for s in Side if viable[SIDE_INDEX[s]] == 0]
    reason = rec.reason
    if reason is TerminalReason.ZERO_VIABILITY_MUTUAL_LOSS:
        if len(zero) != 2 or rec.result is not ResultKind.DRAW:
            v.add("X03", base + "/result", "mutual loss needs both sides at zero and a draw")
        return
    if len(zero) != 1:
        v.add("X03", base + "/viable", "exactly one side must be at zero viability")
        return
    other = opponent(zero[0])
    other_posture = postures[SIDE_INDEX[other]]
    if reason is TerminalReason.ZERO_VIABILITY_UNILATERAL:
        if (other_posture is not Posture.CONTESTING or rec.result is not ResultKind.VICTORY
                or rec.winner is not other):
            v.add("X03", base + "/result", "unilateral zero viability is the contesting opponent's victory")
    else:
        if other_posture is not Posture.WITHDRAWING or rec.result is not ResultKind.DRAW:
            v.add("X03", base + "/result", "mutual abandonment needs a withdrawing opponent and a draw")


def _check_deadline(fields, rec, viable, postures, captured_lots, base, rounds, v):
    if rec.point is not TerminationPoint.ROUND_END or rec.charged_rounds != rounds:
        v.add("X04", base + "/point", "deadline reasons only at the final round end")
    if viable[0] < 1 or viable[1] < 1:
        v.add("X04", base + "/viable", "deadline with a side at zero viability")
    if captured_lots:
        v.add("X04", "/personnel", "captured lots in a deadline terminal")
    withdrawing = [s for s in Side if postures[SIDE_INDEX[s]] is Posture.WITHDRAWING]
    reason = rec.reason
    if reason is TerminalReason.DEADLINE_MUTUAL_WITHDRAWAL:
        ok = len(withdrawing) == 2 and rec.result is ResultKind.DRAW and rec.defeat == (None, None)
    elif reason is TerminalReason.DEADLINE_ABANDONMENT:
        ok = len(withdrawing) == 1
        if ok:
            w = withdrawing[0]
            expected = [None, None]
            expected[SIDE_INDEX[w]] = DefeatClass.ABANDONMENT
            ok = (rec.result is ResultKind.VICTORY and rec.winner is opponent(w)
                  and rec.defeat == tuple(expected))
    else:
        objective = objective_status(fields)
        if reason is TerminalReason.DEADLINE_OBJECTIVE_VICTORY:
            ok = (not withdrawing and objective.kind is ObjectiveKind.SECURE
                  and rec.result is ResultKind.VICTORY and rec.winner is objective.side
                  and rec.defeat == (None, None))
        else:
            ok = (not withdrawing and objective.kind is not ObjectiveKind.SECURE
                  and rec.result is ResultKind.DRAW and rec.defeat == (None, None))
    if not ok:
        v.add("X04", base + "/result", "deadline result disagrees with postures and objective")


def _check_mutual_capitulation(fields, rec, captured_lots, base, v):
    prov = fields.scenario.provenance
    ok = (prov.fixture_class is FixtureClass.SUPPLIED_VALIDATION
          and prov.fixture_id == DEFENSIVE_FIXTURE_ID
          and rec.point is TerminationPoint.INITIAL_CHECK
          and rec.result is ResultKind.UNRESOLVED and rec.winner is None
          and rec.defeat == (DefeatClass.CAPITULATED, DefeatClass.CAPITULATED)
          and not captured_lots
          and not any(f.disposition is Disposition.SURRENDERED for f in fields.formations))
    if not ok:
        v.add("X05", base + "/reason", "mutual capitulation only as the defensive supplied fixture")


# ---- round ledger (10.9)


def _check_ledger(fields, v):
    ledger = fields.ledger
    roster = fields.scenario.roster
    if len(ledger.formations) != len(roster) or any(
            fr.formation != e.formation for fr, e in zip(ledger.formations, roster)):
        v.add("R02", "/ledger/formations", "one formation round per roster formation, roster order")
        return
    _check_uses(fields, v)
    _check_alternation(fields, v)
    _check_rounds(fields, v)
    _check_work(fields, v)


def _member_pointer(ui, k):
    return f"/ledger/uses/{ui}/members/{k}"


def _check_uses(fields, v):
    ledger = fields.ledger
    groups = {g.group: g for g in fields.scenario.groups}
    used = set()
    passes = {Side.S0: None, Side.S1: None}
    non_pass = {Side.S0: 0, Side.S1: 0}
    posture_uses = {Side.S0: 0, Side.S1: 0}
    postures = {s.side: s.posture for s in fields.sides}
    for ui, use in enumerate(ledger.uses):
        p = f"/ledger/uses/{ui}"
        side = use.side
        for k, m in enumerate(use.members):
            entry = fields.roster.get(m)
            if entry is None or entry.side is not side:
                v.add("R03", _member_pointer(ui, k), "member does not belong to the use's side")
        if use.kind is UseKind.GROUP:
            spec = groups.get(use.group)
            if spec is None or spec.side is not side or any(m not in spec.members for m in use.members):
                v.add("R03", p + "/group", "group use does not match a group of that side")
        for k, m in enumerate(use.members):
            if m in used:
                v.add("R04", _member_pointer(ui, k), "formation is a member of two uses")
            used.add(m)
            fr = fields.fround.get(m)
            if fr is not None and not fr.opened_eligible:
                v.add("R05", _member_pointer(ui, k), "member was not eligible at round opening")
        # R06
        if use.kind is UseKind.INDIVIDUAL:
            if use.work and type(use.work[0]) in (GroupStep, GroupPivot):
                v.add("R06", p + "/work/0", "individual use holds group work")
        elif use.kind is UseKind.GROUP:
            types = {type(w) for w in use.work}
            if types == {GroupPivot}:
                if len({w.turn for w in use.work}) != 1:
                    v.add("R06", p + "/work", "group pivot turns differ")
            elif types != {GroupStep}:
                v.add("R06", p + "/work", "group use mixes or holds non-group work")
        # R08, R09, R10 counters
        if passes[side] is not None:
            v.add("R08", p, "use after the side's pass")
        if use.kind is UseKind.PASS:
            if passes[side] is None:
                passes[side] = ui
        else:
            non_pass[side] += 1
            if non_pass[side] > fields.scenario.profile.opportunities:
                v.add("R09", p, "more than four non-pass uses")
        if use.kind is UseKind.POSTURE_WITHDRAWAL:
            posture_uses[side] += 1
            if posture_uses[side] > 1:
                v.add("R10", p, "two posture withdrawals")
            if postures[side] is not Posture.WITHDRAWING:
                v.add("R10", p, "posture withdrawal while contesting")
    _check_withdrawing(fields, v, postures)


def _check_withdrawing(fields, v, postures):
    ledger = fields.ledger
    for side in Side:
        restricted = postures[side] is Posture.WITHDRAWING and not any(
            u.side is side and u.kind is UseKind.POSTURE_WITHDRAWAL for u in ledger.uses)
        for ui, use in enumerate(ledger.uses):
            if use.side is not side:
                continue
            if use.kind is UseKind.POSTURE_WITHDRAWAL:
                restricted = True
                continue
            if not restricted:
                continue
            for k, work in enumerate(use.work):
                p = f"/ledger/uses/{ui}/work/{k}"
                t = type(work)
                if t is Missile or t is Assault:
                    v.add("R10", p, "attack in a restricted withdrawing use")
                elif t is Move:
                    ok = all(
                        exit_distance(fields.scenario, side, leg.destination)
                        < exit_distance(fields.scenario, side, leg.origin) for leg in work.legs)
                    ok = ok and (exit_distance(fields.scenario, side, work.declared[-1])
                                 < exit_distance(fields.scenario, side, work.legs[0].origin))
                    if not ok:
                        v.add("R10", p, "withdrawing move without exit progress")
                elif t is GroupStep:
                    leg = work.leg
                    if not (exit_distance(fields.scenario, side, leg.destination)
                            < exit_distance(fields.scenario, side, leg.origin)):
                        v.add("R10", p, "withdrawing group step without exit progress")


def _check_alternation(fields, v):
    ledger = fields.ledger
    scenario = fields.scenario
    expected = round_first_side(fields.clock)
    finished = {Side.S0: False, Side.S1: False}
    counts = {Side.S0: 0, Side.S1: 0}
    for ui, use in enumerate(ledger.uses):
        if use.side is not expected:
            v.add("R11", f"/ledger/uses/{ui}/side", "use out of alternation")
        x = use.side
        if use.kind is UseKind.PASS:
            finished[x] = True
        else:
            counts[x] += 1
            if counts[x] >= scenario.profile.opportunities:
                finished[x] = True
        expected = x if finished[opponent(x)] else opponent(x)
    if fields.phase.side is not expected or finished[fields.phase.side]:
        v.add("R11", "/phase/side", "next side disagrees with the replayed alternation")


def _check_rounds(fields, v):
    ledger = fields.ledger
    for j, fr in enumerate(ledger.formations):
        p = f"/ledger/formations/{j}"
        fid = fr.formation
        f = fields.fmap[fid]
        works = works_of(ledger, fid)
        types = [type(w) for w in works]
        if not fr.opened_eligible and fr.response is not None:
            v.add("R12", p + "/response", "response by a formation ineligible at opening")
        if f.disposition is Disposition.ROUTING and fr.opened_eligible and not fr.displacement_attempted:
            v.add("R13", p + "/displacement_attempted", "router without a displacement attempt")
        if f.disposition is Disposition.REFORMING:
            if fr.response is not None or any(t not in (Hold, Rally, Rest) for t in types):
                v.add("R14", p, "reforming formation moved or responded")
        if Rest in types and f.condition.fatigue < 1:
            v.add("R16", p, "rest at fatigue 0")
        if fr.safe_latch and on_battlefield(f) and not recovery_safe_now(fields, fid):
            v.add("R17", p + "/safe_latch", "safe latch while not recovery-safe")
        if (any(t in EXERTING_WORK for t in types) or fr.response is not None or fr.displaced) \
                and not fr.exerted:
            v.add("R18", p + "/exerted", "exerting history without the exerted flag")
        if fr.incoming_since_rally and not fr.incoming:
            v.add("R19", p + "/incoming_since_rally", "since-rally incoming without incoming")
        elif Rally not in types and fr.incoming_since_rally != fr.incoming:
            v.add("R19", p + "/incoming_since_rally", "since-rally flag differs without a rally")
        if fr.displaced and not fr.displacement_attempted:
            v.add("R20", p + "/displaced", "displaced without a displacement attempt")
        if fr.response is not None and not response_ok(fields.scenario, fields.roster, fid, fr.response):
            v.add("R20", p + "/response", "response target or kind is invalid")
        if f.disposition in ORGANIZED_OR_REFORMING and not fr.opened_eligible:
            v.add("R22", p + "/opened_eligible", "viable actor ineligible at opening")
        account = None
        for a in fields.ammunition:
            if a.formation == fid:
                account = a
        if discharges(fields, fid) > (account.expended if account is not None else 0):
            v.add("A05", p, "more discharges than expended ammunition")


def _record_modes(work):
    t = type(work)
    if t is Move:
        return [leg.mode for leg in work.legs]
    if t is Withdraw or t is GroupStep:
        return [work.leg.mode]
    if t is Assault:
        return [work.mode]
    return []


def _check_work(fields, v):
    ledger = fields.ledger
    scenario = fields.scenario
    for ui, use in enumerate(ledger.uses):
        for k, (member, work) in enumerate(zip(use.members, use.work)):
            entry = fields.roster.get(member)
            if entry is None:
                continue
            p = f"/ledger/uses/{ui}/work/{k}"
            pairs_ok = _check_modes(fields, member, entry, work, p, v)
            _check_geometry(fields, member, entry, work, p, pairs_ok, v)
            if type(work) is Evacuate:
                f = fields.fmap[member]
                if f.disposition is not Disposition.WITHDRAWN or work.cell != f.cell:
                    v.add("R15", p, "evacuation by a formation not withdrawn from that cell")
        if use.kind is UseKind.GROUP and use.work and all(type(w) is GroupStep for w in use.work):
            _check_group_translation(use, f"/ledger/uses/{ui}", v)
    # R07
    for j, fr in enumerate(ledger.formations):
        fid = fr.formation
        entry = fields.roster[fid]
        works = works_of(ledger, fid)
        if any(not all(mode_compatible(m, entry.template) for m in _record_modes(w)) for w in works):
            continue
        charges = [work_charge(scenario, entry, w) for w in works]
        if any(c is None for c in charges):
            continue
        total = sum(charges)
        if fr.response is not None:
            total += work_charge(scenario, entry, fr.response)
        opened = scenario.profile.effort if fr.opened_eligible else 0
        if total > opened:
            v.add("R07", f"/ledger/formations/{j}", "effort charged exceeds the opened effort")


def _check_modes(fields, fid, entry, work, p, v):
    """R24; returns True iff every recorded mode suits the template."""
    modes = _record_modes(work)
    if not modes:
        return True
    kind = entry.template
    if not all(mode_compatible(m, kind) for m in modes):
        v.add("R24", p, "mode incompatible with the template")
        return False
    if type(work) is Move and any(MODE_ORDER[a] > MODE_ORDER[b] for a, b in zip(modes, modes[1:])):
        v.add("R24", p, "mode order decreases within a move")
    if kind is TemplateKind.MOUNTED:
        stock = mount_stock(fields, fid)
        avail = available(fields, fid)
        full = template_for(fields, fid).mounts
        for m in modes:
            if m is MovementMode.MOUNTED and (stock < 1 or stock < avail):
                v.add("R24", p, "mounted record exceeds the mount stock bound")
                break
            if m is MovementMode.MIXED_FOOT and stock >= full:
                v.add("R24", p, "mixed foot record with full serviceable stock")
                break
    return True


def _leg_ok(board, kind_of_leg, leg, rear):
    d = direction_of(leg.origin, leg.destination)
    if d is None:
        return False
    allowed = rear_directions(leg.facing) if rear else front_directions(leg.facing)
    if d not in allowed:
        return False
    if kind_of_leg is None:
        return True
    return entry_cost(board, leg.origin, leg.destination, kind_of_leg) is not None


def _check_geometry(fields, fid, entry, work, p, pairs_ok, v):
    board = fields.scenario.board
    template = entry.template
    t = type(work)

    def cost_kind(mode):
        return movement_cost_kind(mode, template) if pairs_ok else None

    if t is Withdraw or t is GroupStep:
        if not _leg_ok(board, cost_kind(work.leg.mode), work.leg, rear=(t is Withdraw)):
            v.add("R21", p, "leg is not a legal unit step")
    elif t is Move:
        if not _move_ok(fields, template, work, pairs_ok):
            v.add("R21", p, "move path is not statically legal")
    elif t is Assault:
        if not assault_ok(fields.scenario, fields.roster, fid, work):
            v.add("R21", p, "assault geometry or target is invalid")
    elif t is Missile:
        if not missile_ok(fields.scenario, fields.roster, fid, work):
            v.add("R21", p, "missile geometry or target is invalid")


def _cell_on(board, cell):
    return 0 <= cell.q < board.width and 0 <= cell.r < board.height


def _move_ok(fields, template, move, pairs_ok):
    board = fields.scenario.board
    legs = move.legs
    declared = move.declared
    facing = legs[0].facing
    # items 1-3 and 10: every leg a unit front step with an entry; one facing
    for leg in legs:
        if leg.facing != facing:
            return False
        kind = movement_cost_kind(leg.mode, template) if pairs_ok else None
        if not _leg_ok(board, kind, leg, rear=False):
            return False
    # item 8: prefix
    for i, leg in enumerate(legs):
        if leg.destination != declared[i]:
            return False
        if i and leg.origin != legs[i - 1].destination:
            return False
    # item 9: end
    complete = len(legs) == len(declared)
    if (move.end is MoveEnd.COMPLETED) != complete:
        return False
    # items 5-7: the complete declared chain
    chain = (legs[0].origin,) + declared
    keys = [(c.q, c.r) for c in chain]
    if len(set(keys)) != len(keys) or not all(_cell_on(board, c) for c in chain):
        return False
    for a, b in zip(chain, chain[1:]):
        if direction_of(a, b) not in front_directions(facing):
            return False
        if not statically_traversable(board, a, b):
            return False
    if not pairs_ok:
        return True
    # item 11: declared cap and planned debit of the first mode
    m0 = legs[0].mode
    if len(declared) > step_cap(m0, template):
        return False
    k0 = movement_cost_kind(m0, template)
    debit = 0
    for a, b in zip(chain, chain[1:]):
        cost = entry_cost(board, a, b, k0)
        if cost is None:
            return False
        debit += cost
    if debit > fields.scenario.profile.effort:
        return False
    # item 12: each leg within its own mode's cap
    for i, leg in enumerate(legs, start=1):
        if i > step_cap(leg.mode, template):
            return False
    return True


def _check_group_translation(use, p, v):
    legs = [w.leg for w in use.work]
    directions = [direction_of(l.origin, l.destination) for l in legs]
    ok = len(set(directions)) == 1 and directions[0] is not None
    ok = ok and all(directions[0] in front_directions(l.facing) for l in legs)
    origins = [(l.origin.q, l.origin.r) for l in legs]
    destinations = [(l.destination.q, l.destination.r) for l in legs]
    ok = ok and len(set(origins)) == len(origins) and len(set(destinations)) == len(destinations)
    ok = ok and all(l.destination != l.origin for l in legs)
    if ok:
        reached = {origins[0]}
        frontier = [legs[0].origin]
        while frontier:
            cell = frontier.pop()
            for l in legs:
                key = (l.origin.q, l.origin.r)
                if key not in reached and distance(cell, l.origin) == 1:
                    reached.add(key)
                    frontier.append(l.origin)
        ok = len(reached) == len(origins)
    if not ok:
        v.add("R23", p + "/work", "group translation is not a common connected step")

