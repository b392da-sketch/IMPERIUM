"""Layer 10: the F01 boards, scenarios, the six canonical openings, the two
supplied validation fixtures and the mirror map (contract 11.3, 11.5,
12.3). Every state is built from literal data through the one validating
constructor."""

from .board import F01_BOARDS
from .descriptors import (
    DEFENSIVE_FIXTURE_ID, SHORTFALL_FIXTURE_ID, find_descriptor,
)
from .errors import InvalidValue, UnknownId
from .ids import FixtureId, FormationId, LotId
from .profile import D4_RP_0_1, TEMPLATES
from .records import (
    AmmunitionAccount, Clock, Formation, InFormation, MountLot, ObjectiveStatus, Opening,
    PersonnelLot, SideState, Terminal, TerminalRecord,
)
from .scenario import (
    F01_GROUPS, F01_ROSTER, PROFILE_ID, RULES_BASELINE, SCENARIO_ID,
    SCENARIO_VERSION, SOURCES, Provenance, Scenario,
)
from .state import BattleState, V00, state_values
from .values import (
    Assignment, Authority, Condition, Custody, DefeatClass, Disposition, EnumK, FixtureClass,
    Hex, IdK, ObjectiveKind, Orientation, PersonnelStatus, Posture, Recovery, ResultKind,
    Serviceability, Side, TerminalReason, TerminationPoint, Variant, mirror_facing,
    mirror_hex,
)

# 11.5: standard S0 cells in table order; S1 is the point mirror.
S0_STANDARD_CELLS = {
    "H1": (2, 6), "H2": (3, 6), "H3": (4, 6), "H4": (5, 6),
    "H5": (3, 7), "H6": (4, 7), "L1": (4, 5), "C1": (1, 6),
}
FACINGS = {
    (Orientation.STANDARD, Side.S0): 4, (Orientation.STANDARD, Side.S1): 1,
    (Orientation.MIRRORED, Side.S0): 1, (Orientation.MIRRORED, Side.S1): 4,
}


def _check_arg(kind, value, name):
    failure = kind.check(value, name)
    if failure is not None:
        raise InvalidValue(*failure)


def _canonical_id(variant, orientation):
    return FixtureId(f"F01-v1-{variant.name.lower()}-{orientation.name.lower()}")


def f01_board(variant):
    _check_arg(EnumK(Variant), variant, "variant")
    return F01_BOARDS[variant]


def _scenario(variant, orientation, fixture_class, fixture_id, origin_digest):
    provenance = Provenance(
        scenario_id=SCENARIO_ID,
        scenario_version=SCENARIO_VERSION,
        variant=variant,
        orientation=orientation,
        profile_id=PROFILE_ID,
        rules_baseline=RULES_BASELINE,
        sources=SOURCES,
        fixture_class=fixture_class,
        fixture_id=fixture_id,
        origin_digest=origin_digest,
    )
    return Scenario(provenance, D4_RP_0_1, F01_BOARDS[variant], F01_ROSTER, F01_GROUPS, Side.S0)


def f01_scenario(variant, orientation):
    _check_arg(EnumK(Variant), variant, "variant")
    _check_arg(EnumK(Orientation), orientation, "orientation")
    fid = _canonical_id(variant, orientation)
    d = find_descriptor(fid)
    return _scenario(variant, orientation, FixtureClass.CANONICAL_OPENING, fid,
                     d.normalized_genesis_digest)


def _cell(side, position, orientation):
    q, r = S0_STANDARD_CELLS[position]
    standard = Hex(q, r) if side is Side.S0 else mirror_hex(Hex(q, r))
    return mirror_hex(standard) if orientation is Orientation.MIRRORED else standard


def _opening_fields(scenario):
    orientation = scenario.provenance.orientation
    template_of = {e.formation: e.template for e in F01_ROSTER}
    formations = []
    personnel = []
    mounts = []
    ammunition = []
    for entry in F01_ROSTER:
        fid = entry.formation
        side = entry.side
        position = fid.token.split(".", 1)[1]
        formations.append(Formation(
            fid, Disposition.ORGANIZED, _cell(side, position, orientation),
            FACINGS[(orientation, side)], Condition(0, 0, 0, 0)))
        template = TEMPLATES[template_of[fid]]
        personnel.append(PersonnelLot(
            LotId(f"{fid.token}:P0"), fid, template.personnel, PersonnelStatus.AVAILABLE,
            None, InFormation(fid), side, None))
        if template.mounts:
            mounts.append(MountLot(
                LotId(f"{fid.token}:M0"), fid, template.mounts, Serviceability.SERVICEABLE,
                Assignment.ASSIGNED, InFormation(fid), side, Custody.OWN,
                Recovery.NOT_APPLICABLE))
        if template.ammunition:
            ammunition.append(AmmunitionAccount(
                fid, template.ammunition, 0, Assignment.ASSIGNED, InFormation(fid), side,
                Custody.OWN, Recovery.NOT_APPLICABLE))
    personnel.sort(key=lambda l: l.lot.token)
    mounts.sort(key=lambda m: m.lot.token)
    ammunition.sort(key=lambda a: a.formation.token)
    return dict(
        scenario=scenario,
        phase=Opening(),
        clock=Clock(0, 0),
        sides=(SideState(Side.S0, Posture.CONTESTING), SideState(Side.S1, Posture.CONTESTING)),
        formations=tuple(formations),
        authority=tuple((g.group, Authority.ACTIVE) for g in F01_GROUPS),
        personnel=tuple(personnel),
        mounts=tuple(mounts),
        ammunition=tuple(ammunition),
        contacts=(),
        ledger=None,
    )


def f01_opening(variant, orientation):
    scenario = f01_scenario(variant, orientation)
    return BattleState(**_opening_fields(scenario))


def _shortfall():
    d = find_descriptor(SHORTFALL_FIXTURE_ID)
    scenario = _scenario(Variant.OPEN, Orientation.STANDARD, FixtureClass.SUPPLIED_VALIDATION,
                         SHORTFALL_FIXTURE_ID, d.normalized_genesis_digest)
    fields = _opening_fields(scenario)
    c1 = FormationId("S0.C1")
    others = [m for m in fields["mounts"] if m.formation != c1]
    split = [
        MountLot(LotId("S0.C1:M0"), c1, 70, Serviceability.SERVICEABLE, Assignment.ASSIGNED,
                 InFormation(c1), Side.S0, Custody.OWN, Recovery.NOT_APPLICABLE),
        MountLot(LotId("S0.C1:M1"), c1, 10, Serviceability.UNSERVICEABLE, Assignment.ASSIGNED,
                 InFormation(c1), Side.S0, Custody.OWN, Recovery.NOT_APPLICABLE),
    ]
    fields["mounts"] = tuple(sorted(others + split, key=lambda m: m.lot.token))
    return BattleState(**fields)


def _defensive():
    d = find_descriptor(DEFENSIVE_FIXTURE_ID)
    scenario = _scenario(Variant.OPEN, Orientation.STANDARD, FixtureClass.SUPPLIED_VALIDATION,
                         DEFENSIVE_FIXTURE_ID, d.normalized_genesis_digest)
    fields = _opening_fields(scenario)
    fields["phase"] = Terminal(TerminalRecord(
        reason=TerminalReason.MUTUAL_CAPITULATION,
        result=ResultKind.UNRESOLVED,
        winner=None,
        defeat=(DefeatClass.CAPITULATED, DefeatClass.CAPITULATED),
        point=TerminationPoint.INITIAL_CHECK,
        charged_rounds=0,
        objective=ObjectiveStatus(ObjectiveKind.UNHELD, None),
        postures=(Posture.CONTESTING, Posture.CONTESTING),
        viable=(8, 8),
        onmap_available=(1640, 1640),
        exit_available=(0, 0),
    ))
    return BattleState(**fields)


def f01_supplied(fixture_id):
    _check_arg(IdK(FixtureId), fixture_id, "fixture_id")
    if fixture_id == SHORTFALL_FIXTURE_ID:
        return _shortfall()
    if fixture_id == DEFENSIVE_FIXTURE_ID:
        return _defensive()
    raise UnknownId(fixture_id)


def mirror_state(s):
    """The registered mirror of a canonical Opening genesis state (M01)."""
    if type(s) is not BattleState:
        raise InvalidValue(V00[0].clause, "state", V00[0].detail)
    prov = s.scenario.provenance
    if prov.fixture_class is not FixtureClass.CANONICAL_OPENING or type(s.phase) is not Opening:
        raise InvalidValue("P10", "state", "not a canonical opening genesis")
    orientation = (Orientation.MIRRORED if prov.orientation is Orientation.STANDARD
                   else Orientation.STANDARD)
    target = find_descriptor(_canonical_id(prov.variant, orientation))
    scenario = _scenario(prov.variant, orientation, FixtureClass.CANONICAL_OPENING,
                         target.fixture_id, target.normalized_genesis_digest)
    values = dict(zip(
        ("scenario", "phase", "clock", "sides", "formations", "authority", "personnel",
         "mounts", "ammunition", "contacts", "ledger"), state_values(s)))
    values["scenario"] = scenario
    values["formations"] = tuple(
        Formation(f.formation, f.disposition, mirror_hex(f.cell), mirror_facing(f.facing),
                  f.condition)
        for f in s.formations)
    return BattleState(**values)

