"""Pure order prevalidation for the open-information F01 fixture."""

from ..condition import exert
from ..geometry import Hex, distance, front, step
from ..profiles import F6
from .fixture import Formation, initial_groups
from .terrain import Terrain


def path_cost(unit: Formation, path: tuple[Hex, ...], terrain: Terrain,
              occupied: frozenset[Hex], hostile_threat: frozenset[Hex],
              engaged: bool, effort: int) -> int:
    """Validate a full known individual path without spending anything."""
    origin = unit.position
    if (origin is None or unit.disposition != "organized" or engaged or origin in hostile_threat
            or not 1 <= len(path) <= unit.movement_cap):
        raise ValueError("ineligible movement origin or path length")
    visited = {origin}
    fatigue, remainder = unit.fatigue, unit.exertion
    total = 0
    for index, destination in enumerate(path, 1):
        if (destination in visited or destination in occupied
                or destination not in tuple(step(origin, d) for d in front(unit.facing))):
            raise ValueError("occupied or nonfrontal path")
        cost = terrain.entry_cost(unit, origin, destination)
        if cost is None:
            raise ValueError("impassable path")
        total += cost
        if total > effort:
            raise ValueError("insufficient effort for path")
        fatigue, remainder = exert(fatigue, remainder, 1, F6)
        if index < len(path) and (destination in hostile_threat or fatigue == 2):
            raise ValueError("path extends beyond a known stop")
        visited.add(destination)
        origin = destination
    return total


def group_translation(side: int, members: tuple[int, ...], direction: int,
                      formations: dict[int, Formation], terrain: Terrain,
                      eligible: frozenset[int], effort: dict[int, int],
                      engaged: frozenset[int], hostile_threat: frozenset[Hex]):
    """Return simultaneous destinations and individual costs after validation."""
    selected = set(members)
    if (len(selected) != len(members) or len(selected) not in (2, 3)
            or direction not in range(6)
            or not selected <= eligible
            or not any(group.logical_side == side and selected <= set(group.members)
                       for group in initial_groups())):
        raise ValueError("invalid group membership or readiness")
    units = [formations[member] for member in sorted(selected)]
    if any(unit.position is None or unit.disposition != "organized" or unit.available <= 0
           or max(unit.cohesion, unit.morale, unit.fatigue) > 1
           or unit.identity.id in engaged or unit.position in hostile_threat
           or direction not in front(unit.facing) for unit in units):
        raise ValueError("group formation cannot translate")
    cells = {unit.position for unit in units}
    connected = {units[0].position}
    for _ in range(len(units) - 1):
        connected |= {cell for cell in cells if any(distance(cell, other) == 1
                                                    for other in connected)}
    if connected != cells:
        raise ValueError("disconnected group")
    stationary = {unit.position for identifier, unit in formations.items() if identifier not in selected}
    proposals = {}
    for unit in units:
        destination = step(unit.position, direction)
        cost = terrain.entry_cost(unit, unit.position, destination)
        if destination in stationary or cost is None or cost > effort[unit.identity.id]:
            raise ValueError("blocked or unaffordable group translation")
        proposals[unit.identity.id] = destination, cost
    return proposals
