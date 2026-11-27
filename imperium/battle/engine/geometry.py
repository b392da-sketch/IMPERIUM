"""Layer E0b: pure P4 geometry reads (P4 contract rev 0.2 section 5, ER04).

Every read takes the field bundle of one snapshot, or plain cells for the
line-of-sight seam; nothing is cached or stored in state. Threat is P1
``threat_sources``; occupancy is P1 ``on_battlefield``. Line of sight is
decided by exact rational clipping in the scaled embedding
``(x, y) = (2q + r, 3r)``, where each cell is the closed region
``|x| <= 1, |x + y| <= 2, |x - y| <= 2`` about its centre.
"""

from fractions import Fraction

from imperium.battle.board import cell_on_board
from imperium.battle.queries import exit_distance, on_battlefield, threat_sources
from imperium.battle.values import Hex, distance, opponent

# The six vertices of a cell about its centre, in the scaled embedding.
VERTICES = ((0, 2), (1, 1), (1, -1), (0, -2), (-1, -1), (-1, 1))
# The six closed half-planes ``a*x + b*y <= bound`` of a cell about its centre.
_HALF_PLANES = ((1, 0, 1), (-1, 0, 1), (1, 1, 2), (-1, -1, 2), (1, -1, 2), (-1, 1, 2))


def centre(cell):
    """The exact scaled centre ``(2q + r, 3r)`` of ``(q, r)``."""
    q, r = cell
    return (2 * q + r, 3 * r)


def _pair(cell):
    return (cell.q, cell.r) if type(cell) is Hex else tuple(cell)


# --------------------------------------------------------------------------
# Occupancy, threat and adjacency (5.2, 5.3, 5.6)


def occupant(fields, cell):
    """The battlefield formation on ``cell``, or None (R3.3-02)."""
    for f in fields.formations:
        if on_battlefield(f) and f.cell == cell:
            return f.formation
    return None


def occupied_cells(fields):
    return frozenset((f.cell.q, f.cell.r) for f in fields.formations if on_battlefield(f))


def hostile_sources(fields, cell, side):
    """Formations of ``side``'s opponent threatening ``cell`` (R3.3-09, A09)."""
    return threat_sources(fields, cell, opponent(side))


def hostile_adjacent(fields, fid):
    """Battlefield formations of the other side at distance 1, ascending."""
    me = fields.fmap[fid]
    side = fields.roster[fid].side
    out = [
        f.formation for f in fields.formations
        if on_battlefield(f) and fields.roster[f.formation].side is not side
        and distance(f.cell, me.cell) == 1
    ]
    out.sort(key=lambda x: x.token)
    return tuple(out)


def newly_adjacent(pre, post, defender, mover):
    """True iff ``mover`` is adjacent to ``defender`` in ``post`` but not in
    ``pre``, the snapshots either side of the triggering stage (D10)."""
    return (distance(post.fmap[mover].cell, post.fmap[defender].cell) == 1
            and distance(pre.fmap[mover].cell, pre.fmap[defender].cell) != 1)


def exit_progress(scenario, side, origin, destination):
    """True iff the step strictly reduces the logical exit distance (R3.6-05)."""
    return exit_distance(scenario, side, destination) < exit_distance(scenario, side, origin)


def connected(cells):
    """True iff the cells form one component under hex adjacency."""
    cells = list(cells)
    if not cells:
        return False
    seen = {0}
    frontier = [0]
    while frontier:
        i = frontier.pop()
        for j, c in enumerate(cells):
            if j not in seen and distance(cells[i], c) == 1:
                seen.add(j)
                frontier.append(j)
    return len(seen) == len(cells)


# --------------------------------------------------------------------------
# Line of sight (5.5, ER04)


def _clip(first, last, cell):
    """The positive-length parameter interval of the centre segment inside
    the closed cell, or None."""
    x0, y0 = centre(first)
    x1, y1 = centre(last)
    cx, cy = centre(cell)
    px, py = x0 - cx, y0 - cy
    dx, dy = x1 - x0, y1 - y0
    low, high = Fraction(0), Fraction(1)
    for a, b, bound in _HALF_PLANES:
        rate = a * dx + b * dy
        slack = bound - a * px - b * py
        if rate == 0:
            if slack < 0:
                return None
            continue
        t = Fraction(slack, rate)
        if rate > 0:
            if t < high:
                high = t
        elif t > low:
            low = t
        if low >= high:
            return None
    return (low, high)


def intermediate_cells(first, last):
    """Every non-endpoint cell whose closed hexagon meets the segment between
    the two centres in positive length (R3.3-13, A04)."""
    first, last = _pair(first), _pair(last)
    if first == last:
        return frozenset()
    q_lo, q_hi = min(first[0], last[0]) - 1, max(first[0], last[0]) + 1
    r_lo, r_hi = min(first[1], last[1]) - 1, max(first[1], last[1]) + 1
    out = set()
    for q in range(q_lo, q_hi + 1):
        for r in range(r_lo, r_hi + 1):
            cell = (q, r)
            if cell != first and cell != last and _clip(first, last, cell) is not None:
                out.add(cell)
    return frozenset(out)


def shared_edge(a, b):
    """The two exact vertices of the common edge of adjacent cells, sorted."""
    a, b = _pair(a), _pair(b)
    ax, ay = centre(a)
    bx, by = centre(b)
    common = ({(ax + x, ay + y) for x, y in VERTICES}
              & {(bx + x, by + y) for x, y in VERTICES})
    if len(common) != 2:
        raise ValueError("cells are not adjacent")
    return tuple(sorted(common))


def _cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def edge_blocks(first, last, a, b):
    """True iff the centre segment crosses the common edge of ``a`` and ``b``
    in its relative interior or overlaps it in positive length."""
    p0 = centre(_pair(first))
    p1 = centre(_pair(last))
    e0, e1 = shared_edge(a, b)
    ray = (p1[0] - p0[0], p1[1] - p0[1])
    edge = (e1[0] - e0[0], e1[1] - e0[1])
    gap = (e0[0] - p0[0], e0[1] - p0[1])
    det = _cross(ray, edge)
    if det != 0:
        t = Fraction(_cross(gap, edge), det)
        u = Fraction(_cross(gap, ray), det)
        return 0 < t < 1 and 0 < u < 1
    if ray == (0, 0) or _cross(gap, ray) != 0:
        return False
    axis = 0 if ray[0] != 0 else 1
    t0 = Fraction(e0[axis] - p0[axis], ray[axis])
    t1 = Fraction(e1[axis] - p0[axis], ray[axis])
    lo, hi = min(t0, t1), max(t0, t1)
    return max(lo, Fraction(0)) < min(hi, Fraction(1))


def sight_clear(first, last, allowed, occupied=frozenset(), opaque_cells=frozenset(),
                opaque_edges=()):
    """The pure line-of-sight seam over cell classifications (ER04).

    ``allowed`` is the set of on-board cells; ``opaque_edges`` lists
    unordered adjacent pairs whose common edge is opaque. Endpoint
    occupancy never blocks; an off-board endpoint gives False.
    """
    first, last = _pair(first), _pair(last)
    if first not in allowed or last not in allowed:
        return False
    between = intermediate_cells(first, last)
    for cell in between:
        if cell not in allowed or cell in occupied or cell in opaque_cells:
            return False
    return not any(edge_blocks(first, last, a, b) for a, b in opaque_edges)


def board_cells(board):
    return frozenset((q, r) for q in range(board.width) for r in range(board.height))


def los_clear(fields, source, target):
    """Line of sight between two cells in one snapshot (5.5)."""
    board = fields.scenario.board
    if not cell_on_board(board, source) or not cell_on_board(board, target):
        return False
    edges = tuple(((e.source.q, e.source.r), (e.destination.q, e.destination.r))
                  for e in board.edges if e.opaque)
    return sight_clear(source, target, board_cells(board), occupied_cells(fields),
                       frozenset(), edges)
