"""Independent exact LOS oracle for pointy axial hexes, stdlib only."""
from fractions import Fraction as Q
from itertools import product

VERTICES = ((0, 2), (1, 1), (1, -1), (0, -2), (-1, -1), (-1, 1))
DIRS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))

def centre(cell):
    q, r = cell
    return 2 * q + r, 3 * r

def clip(first, last, cell):
    """Positive-length intersection of a centre segment and a closed hex."""
    x, y = centre(first)
    tx, ty = centre(last)
    cx, cy = centre(cell)
    x, y, dx, dy = x - cx, y - cy, tx - x, ty - y
    low, high = Q(0), Q(1)
    for a, b, bound in ((1, 0, 1), (-1, 0, 1), (1, 1, 2), (-1, -1, 2),
                       (1, -1, 2), (-1, 1, 2)):
        speed, room = a * dx + b * dy, bound - a * x - b * y
        if speed == 0:
            if room < 0:
                return None
        elif speed > 0:
            high = min(high, Q(room, speed))
        else:
            low = max(low, Q(room, speed))
        if low >= high:
            return None
    return low, high

def intermediate(first, last):
    if first == last:
        return frozenset()
    q0, q1 = sorted((first[0], last[0]))
    r0, r1 = sorted((first[1], last[1]))
    cells = product(range(q0 - 1, q1 + 2), range(r0 - 1, r1 + 2))
    return frozenset(cell for cell in cells if cell not in (first, last) and clip(first, last, cell))

def sub(a, b):
    return a[0] - b[0], a[1] - b[1]

def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]

def edge_vertices(c, d):
    """Two exact vertices of the common edge, for neighboring axial cells."""
    cx, cy = centre(c)
    dx, dy = centre(d)
    shared = set((cx + x, cy + y) for x, y in VERTICES) & set((dx + x, dy + y) for x, y in VERTICES)
    if len(shared) != 2:
        raise ValueError("expected adjacent cells")
    return sorted(shared)

def edge_blocks(first, last, c, d):
    a, b = centre(first), centre(last)
    p, q = edge_vertices(c, d)
    ray, edge, delta = sub(b, a), sub(q, p), sub(p, a)
    determinant = cross(ray, edge)
    if determinant:
        t, u = Q(cross(delta, edge), determinant), Q(cross(delta, ray), determinant)
        return 0 < t < 1 and 0 < u < 1
    if ray == (0, 0) or cross(delta, ray):
        return False
    axis = int(ray[0] == 0)
    t, u = sorted(Q(point[axis] - a[axis], ray[axis]) for point in (p, q))
    return max(t, 0) < min(u, 1)

def clear(first, last, board, occupied=(), opaque=(), edges=()):
    if first not in board or last not in board:
        return False
    between = intermediate(first, last)
    return not (between - board or between.intersection(occupied) or between.intersection(opaque)
                or any(edge_blocks(first, last, c, d) for c, d in edges))

def axial_sample(first, last):
    """The draft sample approximation, with two exact rational nudges."""
    a = (*first, -sum(first))
    b = (*last, -sum(last))
    distance = max(abs(y - x) for x, y in zip(a, b))
    out = set()
    for i in range(1, distance):
        for sign in (-1, 1):
            pt = [Q(x * (distance - i) + y * i, distance) + Q(sign * n, 10**6)
                  for x, y, n in zip(a, b, (1, 2, -3))]
            rounded = [round(x) for x in pt]
            largest = max(range(3), key=lambda j: abs(rounded[j] - pt[j]))
            rounded[largest] = -sum(rounded[j] for j in range(3) if j != largest)
            out.add(tuple(rounded[:2]))
    return frozenset(out - {first, last})

if __name__ == "__main__":
    board = frozenset(product(range(11), range(9)))
    misses = []
    all_intermediate_onboard = True
    census = {}
    for a, b in product(sorted(board), repeat=2):
        # Translation invariance lets the exhaustive F01 census cache deltas.
        d = sub(b, a)
        if d not in census:
            census[d] = (intermediate((0, 0), d), axial_sample((0, 0), d))
        expected, proposed = (frozenset((x + a[0], y + a[1]) for x, y in s) for s in census[d])
        all_intermediate_onboard &= expected <= board
        if expected != proposed:
            misses.append((a, b, sorted(expected - proposed), sorted(proposed - expected)))
    assert misses and all_intermediate_onboard
    for (q, r), (forward, _) in census.items():
        backward, _ = census[(-q, -r)]
        assert forward == frozenset((x + q, y + r) for x, y in backward)
    witness = next(row for row in misses if row[2] and not row[3])
    a, b, missing, _ = witness
    print("F01 ordered pairs (including self):", len(board) ** 2)
    print("Draft discrete-sample disagreements:", len(misses))
    print("Counterexample a, b, missed:", a, b, missing)
    print("Missed cell positive interval:", clip(a, b, missing[0]))
    assert not clear(a, b, board, occupied={missing[0]})
    assert not clear(b, a, board, occupied={missing[0]})
    print("Off-board intermediate with on-board endpoints on full F01 rectangle:", not all_intermediate_onboard)
    a, b = (0, 0), (2, -1)
    assert intermediate(a, b) == {(1, 0), (1, -1)}
    assert edge_blocks(a, b, (1, 0), (1, -1))
    assert not edge_blocks(a, b, (0, 0), (1, 0))  # vertex hit
    print("Shared edge both intermediate:", sorted(intermediate(a, b)), "; a vertex-only edge is transparent")
    a, b = (0, 0), (2, 0)
    assert edge_blocks(a, b, (0, 0), (1, 0))
    assert not clear(a, b, board - {(1, 0)})
    assert clear(a, b, board, occupied={a, b})
    print("Interior opaque-edge crossing, masked intermediate and occupied endpoints checked")
