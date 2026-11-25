"""Axial geometry for the open-land EF09-RH1 board."""

from typing import TypeAlias

Hex: TypeAlias = tuple[int, int]
DIRECTIONS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
WIDTH, HEIGHT = 11, 9
OBJECTIVE = (5, 4)


def step(cell: Hex, direction: int) -> Hex:
    dq, dr = DIRECTIONS[direction % 6]
    return cell[0] + dq, cell[1] + dr


def distance(a: Hex, b: Hex) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def in_bounds(cell: Hex) -> bool:
    return 0 <= cell[0] < WIDTH and 0 <= cell[1] < HEIGHT


def front(facing: int) -> tuple[int, int]:
    return facing % 6, (facing + 1) % 6


def rear(facing: int) -> tuple[int, int]:
    return front(facing + 3)


def mirror(cell: Hex) -> Hex:
    return WIDTH - 1 - cell[0], HEIGHT - 1 - cell[1]
