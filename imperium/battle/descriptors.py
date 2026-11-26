"""Layer 4: immutable fixture descriptors (contract 11.1).

Exactly eight literal constants and the tuple ``DESCRIPTORS``. Nothing is
computed at import and nothing registers at runtime. The digest values
were recorded from the independently written primitive oracle documents
(``tests/battle/oracle.py``, contract 11.4), never from the builder.
"""

from dataclasses import dataclass

from .ids import FixtureId
from .values import (
    EnumK, FixtureClass, IdK, Opt, Orientation, Str, TerminationPoint, Variant,
    register, validate_record,
)


@dataclass(frozen=True, slots=True)
class FixtureDescriptor:
    fixture_id: FixtureId
    fixture_class: FixtureClass
    genesis_phase: str
    genesis_point: TerminationPoint | None
    scenario_version: str
    rules_baseline: str
    profile_id: str
    variant: Variant
    orientation: Orientation
    normalized_genesis_digest: str
    full_genesis_digest: str

    def __post_init__(self):
        validate_record(self)


register(FixtureDescriptor, (
    ("fixture_id", IdK(FixtureId)),
    ("fixture_class", EnumK(FixtureClass)),
    ("genesis_phase", Str()),
    ("genesis_point", Opt(EnumK(TerminationPoint))),
    ("scenario_version", Str()),
    ("rules_baseline", Str()),
    ("profile_id", Str()),
    ("variant", EnumK(Variant)),
    ("orientation", EnumK(Orientation)),
    ("normalized_genesis_digest", Str(digest=True)),
    ("full_genesis_digest", Str(digest=True)),
))


F01_V1_OPEN_STANDARD = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-open-standard"),
    fixture_class=FixtureClass.CANONICAL_OPENING,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.OPEN,
    orientation=Orientation.STANDARD,
    normalized_genesis_digest="84b518d2f83581d2c410cf40dc68764d2415a27384ee179075ee285b1155ced5",
    full_genesis_digest="c810920dff7d83ea9a246f9c82e8ac1082615db8feb945c8cbfcfd30e885978e",
)

F01_V1_OPEN_MIRRORED = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-open-mirrored"),
    fixture_class=FixtureClass.CANONICAL_OPENING,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.OPEN,
    orientation=Orientation.MIRRORED,
    normalized_genesis_digest="91ba718863743f97ade1321f91d4bf800f04e85cea7219c160bb682adcf6ae5c",
    full_genesis_digest="f3ee9fbfdad5daef931ef1586173971bde32fb2580e0fa5287c320e932aa767f",
)

F01_V1_ROUGH_STANDARD = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-rough-standard"),
    fixture_class=FixtureClass.CANONICAL_OPENING,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.ROUGH,
    orientation=Orientation.STANDARD,
    normalized_genesis_digest="d9ba56e8fa5150f2adaac8d89270be57045393fa6ee852d3632479ec74d98c3e",
    full_genesis_digest="1efef34dec136fcd0bccc9d7b0048fd13251c3409359265e5ba44d1d423ce848",
)

F01_V1_ROUGH_MIRRORED = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-rough-mirrored"),
    fixture_class=FixtureClass.CANONICAL_OPENING,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.ROUGH,
    orientation=Orientation.MIRRORED,
    normalized_genesis_digest="4c0814d64ea7da938733be52b26031aef2c66abac9a96d8f612ef1eab19e6a45",
    full_genesis_digest="3f8890dc223c440a787c776c1309a39f3c88467329a49d2da2298e2b07fd792c",
)

F01_V1_BARRIER_STANDARD = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-barrier-standard"),
    fixture_class=FixtureClass.CANONICAL_OPENING,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.BARRIER,
    orientation=Orientation.STANDARD,
    normalized_genesis_digest="49209f9a3b5a3465ddcc5b90d9ea91ca6b0546d848a8003db1e1c7c5e5d3fb7e",
    full_genesis_digest="e42a51c9b07e8b7280ed6f69bcbf3bf9c77110da7f93dfe78a3ed8dbd5984ba0",
)

F01_V1_BARRIER_MIRRORED = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-barrier-mirrored"),
    fixture_class=FixtureClass.CANONICAL_OPENING,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.BARRIER,
    orientation=Orientation.MIRRORED,
    normalized_genesis_digest="8ddb6fefad222712904124e88613960c3aa95823b4b2581d8a4281287d686195",
    full_genesis_digest="fd5078388543eed5a3adfc7c1c9e06b25d3c133632625407a44685365d90d948",
)

F01_V1_OPEN_STANDARD_MOUNT_SHORTFALL = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-open-standard-mount-shortfall"),
    fixture_class=FixtureClass.SUPPLIED_VALIDATION,
    genesis_phase="OPENING",
    genesis_point=None,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.OPEN,
    orientation=Orientation.STANDARD,
    normalized_genesis_digest="9abd67ed3d8f861744c57fb1a6bb2fdd1014ca5b2bc4ac6e09b17144f7cf72e6",
    full_genesis_digest="5e73410b10305f1109a3426403dfe441d50bff4b2a4c764fa9b486f845fe0ce6",
)

F01_V1_DEFENSIVE_MUTUAL_CAPITULATION = FixtureDescriptor(
    fixture_id=FixtureId("F01-v1-defensive-mutual-capitulation"),
    fixture_class=FixtureClass.SUPPLIED_VALIDATION,
    genesis_phase="TERMINAL",
    genesis_point=TerminationPoint.INITIAL_CHECK,
    scenario_version="F01-v1",
    rules_baseline="D3-v0.2+A01-A25",
    profile_id="D4-RP-0.1",
    variant=Variant.OPEN,
    orientation=Orientation.STANDARD,
    normalized_genesis_digest="32493376a74735248ed23d98d2e3e8157b497d6c3a2305ae2870fd5b27f5fe3f",
    full_genesis_digest="10590eea2ae4e524c3e2478d98d7adb2b4ead2e3a9e6475b46f05dcece5ea5dd",
)

DESCRIPTORS = (
    F01_V1_OPEN_STANDARD,
    F01_V1_OPEN_MIRRORED,
    F01_V1_ROUGH_STANDARD,
    F01_V1_ROUGH_MIRRORED,
    F01_V1_BARRIER_STANDARD,
    F01_V1_BARRIER_MIRRORED,
    F01_V1_OPEN_STANDARD_MOUNT_SHORTFALL,
    F01_V1_DEFENSIVE_MUTUAL_CAPITULATION,
)

DEFENSIVE_FIXTURE_ID = FixtureId("F01-v1-defensive-mutual-capitulation")
SHORTFALL_FIXTURE_ID = FixtureId("F01-v1-open-standard-mount-shortfall")


def find_descriptor(fixture_id):
    """The registered descriptor with ``fixture_id``, or None."""
    for d in DESCRIPTORS:
        if d.fixture_id == fixture_id:
            return d
    return None
