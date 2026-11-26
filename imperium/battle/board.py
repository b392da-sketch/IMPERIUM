"""Layer 3: the board, directed edge rules, terrain and entry costs, and the
three F01 boards as literal data (contract 5.4, 6.1, 7.3, 11.5)."""

from dataclasses import dataclass

from .values import (
    Bool, EnumK, Fixed, Hex, Int, RecK, TemplateKind, Terrain, Var, Variant,
    direction_of, register, validate_record,
)


@dataclass(frozen=True, slots=True)
class EdgeRule:
    source: Hex
    destination: Hex
    traversable: bool
    opaque: bool
    surcharge: int

    def __post_init__(self):
        validate_record(self)


register(EdgeRule, (
    ("source", RecK((Hex,))),
    ("destination", RecK((Hex,))),
    ("traversable", Bool()),
    ("opaque", Bool()),
    ("surcharge", Int("T10", 0)),
))


@dataclass(frozen=True, slots=True)
class Board:
    width: int
    height: int
    terrain: tuple
    edges: tuple
    objective: Hex

    def __post_init__(self):
        validate_record(self)


register(Board, (
    ("width", Int()),
    ("height", Int()),
    ("terrain", Var(Fixed((RecK((Hex,)), EnumK(Terrain))), key=((0,),))),
    ("edges", Var(RecK((EdgeRule,)), key=(("source",), ("destination",)))),
    ("objective", RecK((Hex,))),
))


# Terrain cost per cost kind (R3.3-04): OPEN 1; ROUGH heavy 2, light 1, mounted 3.
_ROUGH_COST = {TemplateKind.HEAVY: 2, TemplateKind.LIGHT: 1, TemplateKind.MOUNTED: 3}


def cell_on_board(board, cell):
    return 0 <= cell.q < board.width and 0 <= cell.r < board.height


def terrain_at(board, cell):
    """The terrain token of ``cell``, or None if it is not on the board."""
    if not cell_on_board(board, cell):
        return None
    terrain = board.terrain
    i = cell.q * board.height + cell.r
    if 0 <= i < len(terrain) and terrain[i][0] == cell:
        return terrain[i][1]
    for h, t in terrain:
        if h == cell:
            return t
    return None


def edge_rule(board, origin, destination):
    for rule in board.edges:
        if rule.source == origin and rule.destination == destination:
            return rule
    return None


def statically_traversable(board, origin, destination):
    """The directed edge has no rule or a traversable rule."""
    rule = edge_rule(board, origin, destination)
    return rule is None or rule.traversable


def terrain_cost(board, cell, kind):
    """Cost of the terrain at ``cell`` for cost kind ``kind`` (7.3)."""
    t = terrain_at(board, cell)
    if t is None:
        return None
    if t is Terrain.OPEN:
        return 1
    return _ROUGH_COST[kind]


def entry_cost(board, origin, destination, kind):
    """Cost of a legal directed entry, or None (7.3)."""
    if not cell_on_board(board, origin) or not cell_on_board(board, destination):
        return None
    if direction_of(origin, destination) is None:
        return None
    rule = edge_rule(board, origin, destination)
    if rule is not None and not rule.traversable:
        return None
    cost = terrain_cost(board, destination, kind)
    if cost is None:
        return None
    return cost + (rule.surcharge if rule is not None else 0)


# --------------------------------------------------------------------------
# The three F01 boards (11.5), as literal data

F01_WIDTH = 11
F01_HEIGHT = 9
F01_OBJECTIVE = (5, 4)
ROUGH_CELLS = ((2, 4), (8, 4))
BARRIER_RULES = (((3, 4), (4, 4)), ((4, 4), (3, 4)), ((6, 4), (7, 4)), ((7, 4), (6, 4)))


def build_f01_board(variant):
    rough = ROUGH_CELLS if variant is Variant.ROUGH else ()
    terrain = tuple(
        (Hex(q, r), Terrain.ROUGH if (q, r) in rough else Terrain.OPEN)
        for q in range(F01_WIDTH)
        for r in range(F01_HEIGHT)
    )
    edges = ()
    if variant is Variant.BARRIER:
        edges = tuple(
            EdgeRule(Hex(*s), Hex(*d), False, False, 0) for s, d in BARRIER_RULES
        )
    return Board(F01_WIDTH, F01_HEIGHT, terrain, edges, Hex(*F01_OBJECTIVE))


F01_BOARDS = {v: build_f01_board(v) for v in Variant}
