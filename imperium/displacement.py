"""Order-independent arbitration for a frozen compulsory displacement batch."""

from dataclasses import dataclass
from typing import Mapping

from .fixture import Encounter
from .geometry import Hex, front, in_bounds, step


@dataclass(frozen=True)
class ProposalRound:
    proposals: tuple[tuple[int, Hex], ...]
    conflicts: tuple[Hex, ...]


@dataclass(frozen=True)
class Arbitration:
    assignments: tuple[tuple[int, Hex], ...]
    rounds: tuple[ProposalRound, ...]


def arbitrate(occupied: frozenset[Hex], candidates: Mapping[int, tuple[Hex, ...]]) -> Arbitration:
    """Resolve ranked, otherwise eligible cells using the original occupancy.

    Exiting formations have no candidate list, while their original cells remain
    in occupied. The caller generates candidates using snapshot passability and
    threat, and owns exits, actual commit, and shared attempt accounting.
    """
    remaining = {
        mover: iter(dict.fromkeys(cell for cell in ranked if cell not in occupied))
        for mover, ranked in candidates.items()
    }
    reserved: set[Hex] = set()
    assignments: dict[int, Hex] = {}
    rounds = []

    while remaining:
        by_cell: dict[Hex, list[int]] = {}
        for mover, choices in tuple(remaining.items()):
            for cell in choices:
                if cell not in reserved:
                    by_cell.setdefault(cell, []).append(mover)
                    break
            else:
                del remaining[mover]

        if not by_cell:
            break

        proposals = []
        conflicts = []
        for cell, movers in by_cell.items():
            proposals.extend((mover, cell) for mover in movers)
            if len(movers) > 1:
                conflicts.append(cell)
                continue
            mover = movers[0]
            assignments[mover] = cell
            reserved.add(cell)
            del remaining[mover]
        rounds.append(ProposalRound(tuple(sorted(proposals)), tuple(sorted(conflicts))))

    return Arbitration(tuple(sorted(assignments.items())), tuple(rounds))


@dataclass(frozen=True)
class FrozenField:
    """Read-only primary and projected-threat sets for one displacement batch."""

    occupied: frozenset[Hex]
    threatened_by_side: tuple[frozenset[Hex], frozenset[Hex]]

    @classmethod
    def capture(cls, encounter: "Encounter") -> "FrozenField":
        occupied: set[Hex] = set()
        threats: tuple[set[Hex], set[Hex]] = (set(), set())
        for formation in encounter.formations:
            position = formation.position
            if position is None:
                continue
            occupied.add(position)
            if (formation.disposition == "organized" and formation.available_personnel > 0
                    and max(formation.cohesion, formation.morale) <= 1):
                for direction in front(formation.facing):
                    cell = step(position, direction)
                    if in_bounds(cell):
                        threats[formation.physical_side].add(cell)
        return cls(frozenset(occupied), (frozenset(threats[0]), frozenset(threats[1])))

    def destinations(self, side: int, ranked: tuple[Hex, ...]) -> tuple[Hex, ...]:
        """Filter pre-ranked adjacent cells on the open-land fixture."""
        hostile_threat = self.threatened_by_side[1 - side]
        return tuple(cell for cell in ranked if in_bounds(cell)
                     and cell not in self.occupied and cell not in hostile_threat)
