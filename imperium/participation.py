"""Bounded reservations, with the selected edge first."""

from typing import Literal

NOMINAL_FRONTAGE_METRES = 60
PARTICIPATION_PITCH_METRES = 1.5
WHOLE_CAPACITY = int(NOMINAL_FRONTAGE_METRES // PARTICIPATION_PITCH_METRES)
EDGE_CAPACITY = 24


def allocate(available: int, contacts: int, model: Literal["B", "C"],
             *, routing: bool = False) -> tuple[int, ...]:
    if min(available, contacts) < 0 or model not in ("B", "C"):
        raise ValueError("invalid participation input")
    if routing or contacts == 0:
        return (0,) * contacts

    capacity = min(available, WHOLE_CAPACITY)
    if model == "B":
        return (min(EDGE_CAPACITY, capacity // contacts),) * contacts

    selected = min(EDGE_CAPACITY, capacity, (2 * capacity + contacts) // (contacts + 1))
    if contacts == 1:
        return (selected,)
    other = min(EDGE_CAPACITY, (capacity - selected) // (contacts - 1))
    return (selected,) + (other,) * (contacts - 1)
