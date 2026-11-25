"""Independent edge traversal and exact line of sight in axial coordinates."""

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from ..geometry import DIRECTIONS, HEIGHT, WIDTH, Hex, distance, front, in_bounds, mirror
from .fixture import Formation

CELLS = tuple((q, r) for q in range(WIDTH) for r in range(HEIGHT))


@dataclass(frozen=True)
class Edge:
    source: Hex
    destination: Hex
    traversable: bool = True
    opaque: bool = False
    surcharge: int = 0


@dataclass(frozen=True)
class Terrain:
    rough: frozenset[Hex] = frozenset()
    impassable: frozenset[Hex] = frozenset()
    opaque: frozenset[Hex] = frozenset()
    edges: tuple[Edge, ...] = ()

    def edge(self, source, destination):
        return next((edge for edge in self.edges if (edge.source, edge.destination)
                     == (source, destination)), None)

    def entry_cost(self, unit: Formation, source: Hex, destination: Hex) -> int | None:
        if (not in_bounds(destination) or distance(source, destination) != 1
                or destination in self.impassable):
            return None
        edge = self.edge(source, destination)
        if edge is not None and not edge.traversable:
            return None
        ground = unit.movement_template.rough_cost if destination in self.rough else 1
        return ground + (edge.surcharge if edge else 0)

    def line_of_sight(self, source: Hex, target: Hex, occupied: frozenset[Hex]) -> bool:
        if not in_bounds(source) or not in_bounds(target) or source == target:
            return False
        intersections = {
            cell: interval for cell in CELLS
            if (interval := clip_hex(source, target, cell)) is not None
        }
        covered = Fraction(0)
        for start, end in sorted(intersections.values()):
            if start > covered:
                return False
            covered = max(covered, end)
        if covered < 1:
            return False
        for cell, (start, end) in intersections.items():
            if start < end and cell not in (source, target) and cell in (occupied | self.opaque):
                return False
        opaque_pairs = {(edge.source, edge.destination) for edge in self.edges if edge.opaque}
        for a, b in combinations(intersections, 2):
            if (a, b) not in opaque_pairs and (b, a) not in opaque_pairs:
                continue
            start = max(intersections[a][0], intersections[b][0])
            end = min(intersections[a][1], intersections[b][1])
            if start < end:
                return False
            if start == end:
                q = source[0] + start * (target[0] - source[0]) - a[0]
                r = source[1] + start * (target[1] - source[1]) - a[1]
                if sum(abs(value) == 1 for value in projections(q, r)) == 1:
                    direction = (a, b) if intersections[a][0] < start else (b, a)
                    if direction in opaque_pairs:
                        return False
        return True


def projections(q, r):
    return 2*q + r, q + 2*r, q - r


def clip_hex(source: Hex, target: Hex, cell: Hex):
    """Closed segment parameter interval inside the cell's Voronoi hex."""
    offsets = projections(source[0] - cell[0], source[1] - cell[1])
    deltas = projections(target[0] - source[0], target[1] - source[1])
    lower, upper = Fraction(0), Fraction(1)
    for offset, delta in zip(offsets, deltas, strict=True):
        if delta == 0:
            if abs(offset) > 1:
                return None
            continue
        a, b = sorted((Fraction(-1 - offset, delta), Fraction(1 - offset, delta)))
        lower, upper = max(lower, a), min(upper, b)
        if lower > upper:
            return None
    return lower, upper


def in_front_sector(source: Hex, target: Hex, facing: int) -> bool:
    first, last = (DIRECTIONS[d] for d in front(facing))
    q, r = target[0] - source[0], target[1] - source[1]
    return (source != target and first[0]*r - first[1]*q >= 0
            and q*last[1] - r*last[0] >= 0)


OPEN = Terrain()
ROUGH = Terrain(rough=frozenset({(2, 4), (8, 4)}))
# Original development edges, independently distinct from HF02.
_edge = ((3, 4), (4, 4))
_edges = (_edge, tuple(map(mirror, _edge)))
BARRIER = Terrain(edges=tuple(Edge(a, b, traversable=False)
                             for left, right in _edges for a, b in ((left, right), (right, left))))
