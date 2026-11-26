"""Opening state and templates for the standalone Plain of the Crossing."""

from dataclasses import dataclass
from types import MappingProxyType

from ..physical import Casualties

from ..geometry import Hex, mirror

FIXTURE_VERSION = "F01-v1"
PROFILE_VERSION = "D4-RP-0.1"
ROLES = ("H1", "H2", "H3", "H4", "H5", "H6", "L1", "C1")
RED_CELLS = ((2, 6), (3, 6), (4, 6), (5, 6), (3, 7), (4, 7), (4, 5), (1, 6))
GROUP_ROLES = ((0, 1, 4), (2, 3, 5))


@dataclass(frozen=True)
class Template:
    personnel: int
    mounts: int
    ammunition: int
    frontage_metres: int
    pitch_half_metres: int
    edge_capacity: int
    missile_range: int
    steps: int
    rough_cost: int

    @property
    def slots(self) -> int:
        return 2 * self.frontage_metres // self.pitch_half_metres


TEMPLATES = MappingProxyType({
    "H": Template(240, 0, 2, 60, 3, 24, 1, 2, 2),
    "L": Template(120, 0, 4, 45, 4, 18, 2, 2, 1),
    "C": Template(80, 80, 0, 60, 6, 12, 0, 3, 3),
})


@dataclass(frozen=True)
class Identity:
    logical_side: int
    role: str

    @property
    def id(self) -> int:
        return self.logical_side * len(ROLES) + ROLES.index(self.role)

    @property
    def template(self) -> Template:
        return TEMPLATES[self.role[0]]


@dataclass(frozen=True)
class LossLot:
    formation: Identity
    stage: str
    cell: Hex
    casualties: Casualties


@dataclass
class Formation:
    identity: Identity
    physical_side: int
    position: Hex | None
    facing: int
    available: int
    mounts: int
    ammunition: int
    cohesion: int = 0
    morale: int = 0
    fatigue: int = 0
    exertion: int = 0
    disposition: str = "organized"
    losses: tuple[LossLot, ...] = ()

    def record_losses(self, stage: str, casualties: Casualties) -> None:
        """Debit available personnel and retain both casualty pools at the actual cell."""
        counts = (casualties.killed, casualties.wounded)
        if (self.position is None or any(type(count) is not int or count < 0 for count in counts)
                or sum(counts) > self.available or any(lot.stage == stage for lot in self.losses)):
            raise ValueError("invalid or duplicate loss transfer")
        if not sum(counts):
            return
        self.losses += (LossLot(self.identity, stage, self.position, casualties),)
        self.available -= sum(counts)

    @property
    def movement_template(self) -> Template:
        if self.identity.role == "C1" and self.mounts < self.available:
            return TEMPLATES["H"]
        return self.identity.template

    @property
    def movement_cap(self) -> int:
        return 1 if max(self.cohesion, self.fatigue) == 2 else self.movement_template.steps


@dataclass(frozen=True)
class Group:
    logical_side: int
    name: str
    members: tuple[int, ...]


def initial_formations(mirrored: bool = False) -> tuple[Formation, ...]:
    units = []
    for side in (0, 1):
        physical = side ^ int(mirrored)
        for role, red_cell in zip(ROLES, RED_CELLS, strict=True):
            identity = Identity(side, role)
            template = identity.template
            units.append(Formation(identity, physical, mirror(red_cell) if physical else red_cell,
                                   1 if physical else 4, template.personnel,
                                   template.mounts, template.ammunition))
    return tuple(units)


def initial_groups() -> tuple[Group, ...]:
    return tuple(Group(side, f"G{number}", tuple(side * len(ROLES) + role for role in roles))
                 for side in (0, 1) for number, roles in enumerate(GROUP_ROLES, 1))
