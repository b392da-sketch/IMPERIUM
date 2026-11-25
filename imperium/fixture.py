"""Canonical opening state for EF09-RH1."""

from dataclasses import dataclass, field
from typing import Literal

from .geometry import Hex, mirror
from .profiles import Profile

FIXTURE_VERSION = "EF09-RH1"
RED_POSITIONS = ((2, 6), (3, 6), (4, 6), (5, 6), (3, 7), (4, 7))
ROUND_LIMIT = 12
INTERVAL_MINUTES = 10
HEX_SPACING_METRES = 65
Disposition = Literal["organized", "routing", "reforming", "withdrawn", "depleted"]


@dataclass(frozen=True)
class Identity:
    logical_side: int
    local_role: int

    @property
    def formation_id(self) -> int:
        return self.logical_side * 6 + self.local_role


@dataclass
class Formation:
    identity: Identity
    physical_side: int
    position: Hex | None
    facing: int
    initial_personnel: int = 240
    available_personnel: int = 240
    killed_personnel: int = 0
    wounded_unavailable_personnel: int = 0
    cohesion: int = 0
    morale: int = 0
    fatigue: int = 0
    exertion_remainder: int = 0
    disposition: Disposition = "organized"
    principal_eligibility: bool = False
    mandatory_displacement_attempted: bool = False
    forced_stop: bool = False
    full_interval_safety: bool = False
    incoming_effect_flag: bool = False
    pending_rest: bool = False
    activity_marks: int = 0


@dataclass
class Encounter:
    formations: tuple[Formation, ...]
    # Each reciprocal edge is represented once as the sorted pair of endpoint IDs.
    contacts: set[tuple[int, int]] = field(default_factory=set)


def initial_encounter(profile: Profile, mirrored: bool = False) -> Encounter:
    formations = []
    for logical_side in (0, 1):
        physical_side = logical_side ^ int(mirrored)
        for role, red_position in enumerate(RED_POSITIONS):
            formations.append(Formation(
                Identity(logical_side, role),
                physical_side,
                mirror(red_position) if physical_side else red_position,
                1 if physical_side else 4,
                fatigue=profile.initial_fatigue,
            ))
    return Encounter(tuple(formations))
