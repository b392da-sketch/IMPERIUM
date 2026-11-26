"""Layer 4: the static scenario records, physical ends, and the F01 roster
and groups as literal data (contract 5.3, 5.5, 6.1, 11.5)."""

from dataclasses import dataclass

from .board import Board
from .ids import FixtureId, FormationId, GroupId
from .profile import Profile
from .values import (
    End, EnumK, Fixed, FixtureClass, IdK, Orientation, RecK, Side, Str, TemplateKind,
    Var, Variant, register, validate_record,
)


@dataclass(frozen=True, slots=True)
class Provenance:
    scenario_id: str
    scenario_version: str
    variant: Variant
    orientation: Orientation
    profile_id: str
    rules_baseline: str
    sources: tuple
    fixture_class: FixtureClass
    fixture_id: FixtureId
    origin_digest: str

    def __post_init__(self):
        validate_record(self)


_DIGEST = Str(digest=True)

register(Provenance, (
    ("scenario_id", Str()),
    ("scenario_version", Str()),
    ("variant", EnumK(Variant)),
    ("orientation", EnumK(Orientation)),
    ("profile_id", Str()),
    ("rules_baseline", Str()),
    ("sources", Fixed((_DIGEST, _DIGEST, _DIGEST))),
    ("fixture_class", EnumK(FixtureClass)),
    ("fixture_id", IdK(FixtureId)),
    ("origin_digest", _DIGEST),
))


@dataclass(frozen=True, slots=True)
class RosterEntry:
    formation: FormationId
    side: Side
    template: TemplateKind

    def __post_init__(self):
        validate_record(self)


register(RosterEntry, (
    ("formation", IdK(FormationId)),
    ("side", EnumK(Side)),
    ("template", EnumK(TemplateKind)),
))


@dataclass(frozen=True, slots=True)
class GroupSpec:
    group: GroupId
    side: Side
    members: tuple

    def __post_init__(self):
        validate_record(self)


register(GroupSpec, (
    ("group", IdK(GroupId)),
    ("side", EnumK(Side)),
    ("members", Var(IdK(FormationId), key=((),))),
))


@dataclass(frozen=True, slots=True)
class Scenario:
    provenance: Provenance
    profile: Profile
    board: Board
    roster: tuple
    groups: tuple
    first_side: Side

    def __post_init__(self):
        validate_record(self)


register(Scenario, (
    ("provenance", RecK((Provenance,))),
    ("profile", RecK((Profile,))),
    ("board", RecK((Board,))),
    ("roster", Var(RecK((RosterEntry,)), key=(("formation",),))),
    ("groups", Var(RecK((GroupSpec,)), key=(("group",),))),
    ("first_side", EnumK(Side)),
))


def end_of(scenario, side):
    """Physical end of logical ``side`` (5.3): S0 is RED when standard."""
    mirrored = scenario.provenance.orientation is Orientation.MIRRORED
    if (side is Side.S0) != mirrored:
        return End.RED
    return End.BLUE


def exit_row(end):
    """RED exits on row 8, BLUE on row 0 (R3.6-01)."""
    return 8 if end is End.RED else 0


# --------------------------------------------------------------------------
# F01 literal data (11.5)

SCENARIO_ID = "F01"
SCENARIO_VERSION = "F01-v1"
PROFILE_ID = "D4-RP-0.1"
RULES_BASELINE = "D3-v0.2+A01-A25"
SOURCES = (
    "6a831d4a08db660e0e6cd15e0d023fd585e83bd7d1387cac6405d4981e382da5",
    "d01c2bb10f0f1074f7f18f0270e434fb9548867a4e007215b6daefcc73a72534",
    "a89fea614e1b9e76c7b5add120a4b0359aef2cf87a0938c5e0dc133162b70e7e",
)

# Position names and templates in the 11.5 table order.
POSITIONS = (
    ("H1", TemplateKind.HEAVY), ("H2", TemplateKind.HEAVY), ("H3", TemplateKind.HEAVY),
    ("H4", TemplateKind.HEAVY), ("H5", TemplateKind.HEAVY), ("H6", TemplateKind.HEAVY),
    ("L1", TemplateKind.LIGHT), ("C1", TemplateKind.MOUNTED),
)
GROUP_POSITIONS = (("G1", ("H1", "H2", "H5")), ("G2", ("H3", "H4", "H6")))


def _roster():
    entries = [
        RosterEntry(FormationId(f"{side.name}.{pos}"), side, template)
        for side in Side
        for pos, template in POSITIONS
    ]
    entries.sort(key=lambda e: e.formation.token)
    return tuple(entries)


def _groups():
    return tuple(
        GroupSpec(
            GroupId(f"{side.name}.{g}"),
            side,
            tuple(FormationId(f"{side.name}.{m}") for m in members),
        )
        for side in Side
        for g, members in GROUP_POSITIONS
    )


F01_ROSTER = _roster()
F01_GROUPS = _groups()
