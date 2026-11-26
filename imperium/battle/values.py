"""Layer 2: enumerations, ``Hex``, ``Condition``, strict value checks and
hex geometry (contract 5.1, 5.3, 5.4, 5.6, 5.7).

The field-kind classes below describe every record field once. The same
description drives the local (T clause) checks of every record and the
shape stage of the decoder, so the two channels cannot drift apart.
"""

import re
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from .errors import InvalidValue
from .ids import ID_CLASSES, valid_token


# --------------------------------------------------------------------------
# Enumerations (all closed, plain ``Enum``; member names are wire tokens)


class Side(Enum):
    S0 = "S0"
    S1 = "S1"


class End(Enum):
    RED = "RED"
    BLUE = "BLUE"


class Orientation(Enum):
    STANDARD = "STANDARD"
    MIRRORED = "MIRRORED"


class Variant(Enum):
    OPEN = "OPEN"
    ROUGH = "ROUGH"
    BARRIER = "BARRIER"


class Terrain(Enum):
    OPEN = "OPEN"
    ROUGH = "ROUGH"


class TemplateKind(Enum):
    HEAVY = "HEAVY"
    LIGHT = "LIGHT"
    MOUNTED = "MOUNTED"


class FixtureClass(Enum):
    CANONICAL_OPENING = "CANONICAL_OPENING"
    SUPPLIED_VALIDATION = "SUPPLIED_VALIDATION"
    ADVERSARIAL_TEST = "ADVERSARIAL_TEST"


class Disposition(Enum):
    ORGANIZED = "ORGANIZED"
    REFORMING = "REFORMING"
    ROUTING = "ROUTING"
    WITHDRAWN = "WITHDRAWN"
    SURRENDERED = "SURRENDERED"
    DEPLETED = "DEPLETED"


class PersonnelStatus(Enum):
    AVAILABLE = "AVAILABLE"
    WOUNDED = "WOUNDED"
    DEAD = "DEAD"
    CAPTURED = "CAPTURED"


class CapturedCondition(Enum):
    FIT = "FIT"
    WOUNDED = "WOUNDED"


class Serviceability(Enum):
    SERVICEABLE = "SERVICEABLE"
    UNSERVICEABLE = "UNSERVICEABLE"


class Assignment(Enum):
    ASSIGNED = "ASSIGNED"
    UNASSIGNED_RECORDED = "UNASSIGNED_RECORDED"


class Custody(Enum):
    OWN = "OWN"
    SURRENDERED_INVENTORY = "SURRENDERED_INVENTORY"


class Recovery(Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNRESOLVED = "UNRESOLVED"


class MovementMode(Enum):
    FOOT = "FOOT"
    MOUNTED = "MOUNTED"
    MIXED_FOOT = "MIXED_FOOT"


class Posture(Enum):
    CONTESTING = "CONTESTING"
    WITHDRAWING = "WITHDRAWING"


class Authority(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Activation(Enum):
    READY = "READY"
    SPENT = "SPENT"
    FORFEITED = "FORFEITED"
    INELIGIBLE = "INELIGIBLE"
    CLOSED = "CLOSED"


class UseKind(Enum):
    INDIVIDUAL = "INDIVIDUAL"
    GROUP = "GROUP"
    POSTURE_WITHDRAWAL = "POSTURE_WITHDRAWAL"
    PASS = "PASS"


class MoveEnd(Enum):
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"


class AssaultOutcome(Enum):
    CONTACT = "CONTACT"
    ABORTED = "ABORTED"


class ResponseKind(Enum):
    DEFENSIVE_MISSILE = "DEFENSIVE_MISSILE"
    DEFENSIVE_PIVOT = "DEFENSIVE_PIVOT"


class TerminalReason(Enum):
    ZERO_VIABILITY_UNILATERAL = "ZERO_VIABILITY_UNILATERAL"
    ZERO_VIABILITY_MUTUAL_LOSS = "ZERO_VIABILITY_MUTUAL_LOSS"
    ZERO_VIABILITY_MUTUAL_ABANDONMENT = "ZERO_VIABILITY_MUTUAL_ABANDONMENT"
    CAPITULATION = "CAPITULATION"
    MUTUAL_CAPITULATION = "MUTUAL_CAPITULATION"
    DEADLINE_ABANDONMENT = "DEADLINE_ABANDONMENT"
    DEADLINE_MUTUAL_WITHDRAWAL = "DEADLINE_MUTUAL_WITHDRAWAL"
    DEADLINE_OBJECTIVE_VICTORY = "DEADLINE_OBJECTIVE_VICTORY"
    DEADLINE_OBJECTIVE_UNRESOLVED = "DEADLINE_OBJECTIVE_UNRESOLVED"


class ResultKind(Enum):
    VICTORY = "VICTORY"
    DRAW = "DRAW"
    UNRESOLVED = "UNRESOLVED"


class DefeatClass(Enum):
    COLLAPSE = "COLLAPSE"
    DEPARTURE = "DEPARTURE"
    DEPLETION_MIXED = "DEPLETION_MIXED"
    CAPITULATED = "CAPITULATED"
    ABANDONMENT = "ABANDONMENT"


class TerminationPoint(Enum):
    INITIAL_CHECK = "INITIAL_CHECK"
    AFTER_ROOT = "AFTER_ROOT"
    AFTER_CLOSURE_DISPLACEMENT = "AFTER_CLOSURE_DISPLACEMENT"
    ROUND_END = "ROUND_END"


class ObjectiveKind(Enum):
    UNHELD = "UNHELD"
    SECURE = "SECURE"
    CONTESTED = "CONTESTED"
    INSECURE = "INSECURE"


ENUM_CLASSES = (
    Side, End, Orientation, Variant, Terrain, TemplateKind, FixtureClass, Disposition,
    PersonnelStatus, CapturedCondition, Serviceability, Assignment, Custody, Recovery,
    MovementMode, Posture, Authority, Activation, UseKind, MoveEnd, AssaultOutcome,
    ResponseKind, TerminalReason, ResultKind, DefeatClass, TerminationPoint, ObjectiveKind,
)

# Declaration index of every member, for keyed order by enum declaration.
_ENUM_INDEX = {}
for _cls in ENUM_CLASSES:
    for _i, _member in enumerate(_cls):
        _ENUM_INDEX[_member] = _i
del _cls, _i, _member


def opponent(side):
    return Side.S1 if side is Side.S0 else Side.S0


# --------------------------------------------------------------------------
# Field kinds: one description per field, used by records and the decoder

DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


INT_DOMAIN = 2 ** 63 - 1  # the codec's integer limit (13.1, 13.2)


class Int:
    """Exact ``int`` (T01), optionally range-checked under ``clause``.

    A range-checked kind with no stated upper bound is capped at the codec's
    integer domain, so that every validated state encodes to a document both
    decoders accept (13.1, 13.4).
    """

    __slots__ = ("clause", "low", "high", "choices")

    def __init__(self, clause=None, low=None, high=None, choices=None):
        self.clause = clause
        self.low = low
        self.high = INT_DOMAIN if clause is not None and choices is None and high is None else high
        self.choices = choices

    def check(self, v, path):
        if type(v) is not int:
            return ("T01", path, "expected int")
        if self.clause is not None:
            if self.choices is not None:
                if v not in self.choices:
                    return (self.clause, path, "value out of range")
            elif (self.low is not None and v < self.low) or (self.high is not None and v > self.high):
                return (self.clause, path, "value out of range")
        return None


class Bool:
    __slots__ = ()

    def check(self, v, path):
        if type(v) is not bool:
            return ("T02", path, "expected bool")
        return None


class Str:
    """A plain string (T16), or a 64-hex lowercase digest string."""

    __slots__ = ("digest",)

    def __init__(self, digest=False):
        self.digest = digest

    def check(self, v, path):
        if type(v) is not str:
            return ("T16", path, "expected str")
        if self.digest and DIGEST_PATTERN.fullmatch(v) is None:
            return ("T16", path, "invalid digest")
        return None


class Frac:
    __slots__ = ()

    def check(self, v, path):
        if type(v) is not Fraction:
            return ("T06", path, "expected Fraction")
        return None


class EnumK:
    __slots__ = ("cls",)

    def __init__(self, cls):
        self.cls = cls

    def check(self, v, path):
        if type(v) is not self.cls:
            return ("T03", path, "expected " + self.cls.__name__)
        return None


class IdK:
    __slots__ = ("cls",)

    def __init__(self, cls):
        self.cls = cls

    def check(self, v, path):
        if type(v) is not self.cls or not valid_token(v.token):
            return ("T07", path, "expected " + self.cls.__name__)
        return None


class RecK:
    """A record, or a union of record classes (more than one class)."""

    __slots__ = ("classes", "clause")

    def __init__(self, classes, clause="T15"):
        self.classes = classes
        self.clause = clause

    @property
    def is_union(self):
        return len(self.classes) > 1

    def check(self, v, path):
        t = type(v)
        for cls in self.classes:
            if t is cls:
                return None
        return (self.clause, path, "unexpected record type")


class Opt:
    __slots__ = ("inner",)

    def __init__(self, inner):
        self.inner = inner

    def check(self, v, path):
        if v is None:
            return None
        return self.inner.check(v, path)


class Var:
    """A variable-length tuple, optionally keyed (T05)."""

    __slots__ = ("elem", "key")

    def __init__(self, elem, key=None):
        self.elem = elem
        self.key = key

    def check(self, v, path):
        if type(v) is not tuple:
            return ("T04", path, "expected tuple")
        for i, x in enumerate(v):
            f = self.elem.check(x, f"{path}/{i}")
            if f is not None:
                return f
        if self.key is not None and not keyed_increasing(v, self.key, attr_get):
            return ("T05", path, "not strictly increasing")
        return None


class Fixed:
    """A fixed-length tuple: type and length first (T04), then elements."""

    __slots__ = ("elems", "key")

    def __init__(self, elems, key=None):
        self.elems = elems
        self.key = key

    def check(self, v, path):
        if type(v) is not tuple:
            return ("T04", path, "expected tuple")
        if len(v) != len(self.elems):
            return ("T04", path, "wrong length")
        for i, (kind, x) in enumerate(zip(self.elems, v)):
            f = kind.check(x, f"{path}/{i}")
            if f is not None:
                return f
        if self.key is not None and not keyed_increasing(v, self.key, attr_get):
            return ("T05", path, "not strictly increasing")
        return None


def attr_get(obj, step):
    if type(step) is int:
        if type(obj) is not tuple or step >= len(obj):
            return _NO_KEY
        return obj[step]
    try:
        return object.__getattribute__(obj, step)
    except AttributeError:
        return _NO_KEY


class _NoKey:
    __slots__ = ()


_NO_KEY = _NoKey()


def comparable(leaf):
    """A safe comparable for one key leaf, or ``_NO_KEY``.

    Only exact P1 values are converted; anything else yields ``_NO_KEY`` so
    that no foreign method is ever called while ordering is checked.
    """
    t = type(leaf)
    if t in ID_CLASSES:
        token = leaf.token
        return token if type(token) is str else _NO_KEY
    if t is Hex:
        q, r = leaf.q, leaf.r
        if type(q) is int and type(r) is int:
            return (q, r)
        return _NO_KEY
    if t in ENUM_CLASSES:
        return _ENUM_INDEX[leaf]
    return _NO_KEY


def key_of(element, key, getter):
    """Key of one element; ``key`` is a tuple of access paths."""
    parts = []
    for steps in key:
        node = element
        for step in steps:
            node = getter(node, step)
            if node is _NO_KEY:
                return _NO_KEY
        c = comparable(node)
        if c is _NO_KEY:
            return _NO_KEY
        parts.append(c)
    return tuple(parts)


def keyed_increasing(items, key, getter):
    """True if keys strictly increase, or if any key is not computable."""
    previous = None
    for i, x in enumerate(items):
        k = key_of(x, key, getter)
        if k is _NO_KEY:
            return True
        if i and not previous < k:
            return False
        previous = k
    return True


# Registry of record specifications: class -> (fields, extra check).
SPECS = {}


def register(cls, fields, extra=None):
    SPECS[cls] = (fields, extra)
    return cls


def first_failure(cls, values):
    """First local failure of a record of ``cls`` with field ``values``."""
    fields, extra = SPECS[cls]
    for (name, kind), v in zip(fields, values):
        f = kind.check(v, name)
        if f is not None:
            return f
    if extra is not None:
        return extra(*values)
    return None


def field_values(obj):
    fields, _ = SPECS[type(obj)]
    return [object.__getattribute__(obj, name) for name, _ in fields]


def validate_record(obj):
    """Run the local clauses of ``obj``; raise ``InvalidValue`` on failure."""
    f = first_failure(type(obj), field_values(obj))
    if f is not None:
        raise InvalidValue(*f)


# --------------------------------------------------------------------------
# Hex and Condition


@dataclass(frozen=True, slots=True)
class Hex:
    q: int
    r: int

    def __post_init__(self):
        validate_record(self)


register(Hex, (("q", Int()), ("r", Int())))


@dataclass(frozen=True, slots=True)
class Condition:
    cohesion: int
    morale: int
    fatigue: int
    exertion: int

    def __post_init__(self):
        validate_record(self)


register(Condition, (
    ("cohesion", Int("T09", 0, 2)),
    ("morale", Int("T09", 0, 2)),
    ("fatigue", Int("T09", 0, 2)),
    ("exertion", Int("T09", 0, 5)),
))


# --------------------------------------------------------------------------
# Hex geometry (5.4, A04)

DIRECTIONS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
BOARD_WIDTH = 11
BOARD_HEIGHT = 9


def direction_of(origin, destination):
    """The unique d with destination = origin + vec(d), or None."""
    dq = destination.q - origin.q
    dr = destination.r - origin.r
    for d, (vq, vr) in enumerate(DIRECTIONS):
        if dq == vq and dr == vr:
            return d
    return None


def step(cell, direction):
    vq, vr = DIRECTIONS[direction % 6]
    return Hex(cell.q + vq, cell.r + vr)


def distance(a, b):
    dq = a.q - b.q
    dr = a.r - b.r
    return max(abs(dq), abs(dr), abs(dq + dr))


def front_directions(facing):
    return (facing % 6, (facing + 1) % 6)


def rear_directions(facing):
    return ((facing + 3) % 6, (facing + 4) % 6)


def in_front_sector(origin, target, facing):
    """True iff target − origin = a·vec(f) + b·vec(f+1), a, b ≥ 0 integers."""
    dq = target.q - origin.q
    dr = target.r - origin.r
    v1 = DIRECTIONS[facing % 6]
    v2 = DIRECTIONS[(facing + 1) % 6]
    det = v1[0] * v2[1] - v1[1] * v2[0]
    a_num = dq * v2[1] - dr * v2[0]
    b_num = v1[0] * dr - v1[1] * dq
    if a_num % det or b_num % det:
        return False
    return a_num // det >= 0 and b_num // det >= 0


def on_board(cell, width=BOARD_WIDTH, height=BOARD_HEIGHT):
    return 0 <= cell.q < width and 0 <= cell.r < height


def mirror_hex(cell):
    return Hex(BOARD_WIDTH - 1 - cell.q, BOARD_HEIGHT - 1 - cell.r)


def mirror_facing(facing):
    return (facing + 3) % 6
