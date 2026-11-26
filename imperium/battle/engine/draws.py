"""Layer E0a: the BK-1 draw-key registry on the unchanged EP08-v1 formula
(P3 contract rev 0.3 section 4, errata ER04).

``ep08_numerator`` is the raw EP08 primitive: it validates only exact types,
the P1 integer domain and ASCII text, and is used for fixed evidence and by
``draw_numerator``. ``draw_numerator`` is the validated BK-1 entry point.
No P3 gameplay path calls either (audit v1 journals are draw-free).
"""

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum

from imperium.battle import DESCRIPTORS, FixtureDescriptor, FixtureClass, FormationId, InvalidValue, Side
from imperium.battle.values import INT_DOMAIN

RNG_VERSION = "D4-SHA256-v1"
REGISTRY = "IMPERIUM-BK-1"
ROUNDS = 12
ORDINALS = 4
INDEX_MAX = 63
NUMERATOR_LIMIT = 2 ** 53
ID_MAX = 64

ROSTER = {
    Side.S0: ("S0.C1", "S0.H1", "S0.H2", "S0.H3", "S0.H4", "S0.H5", "S0.H6", "S0.L1"),
    Side.S1: ("S1.C1", "S1.H1", "S1.H2", "S1.H3", "S1.H4", "S1.H5", "S1.H6", "S1.L1"),
}
_SIDE_OF = {token: side for side, tokens in ROSTER.items() for token in tokens}

P2_KINDS = (
    "INITIAL_CHECK", "ROOT", "IMMEDIATE_CHECK", "CLOSURE_DISPLACEMENT", "CLOSURE_CHECK",
    "RECOVERY", "ADVANCE", "END_CHECK", "OPEN_ROUND", "TERMINAL",
)
PACKET_KINDS = ("MELEE", "MISSILE")
ROOT_KINDS = {
    "IN": ("INITIAL_CHECK", "OPEN_ROUND", "TERMINAL"),
    "CL": ("CLOSURE_DISPLACEMENT", "CLOSURE_CHECK", "RECOVERY", "ADVANCE", "END_CHECK",
           "OPEN_ROUND", "TERMINAL"),
    "P": ("ROOT", "IMMEDIATE_CHECK", "TERMINAL", "MELEE", "MISSILE"),
}


class Channel(Enum):
    injury = "injury"
    fatal = "fatal"
    cohesion = "cohesion"
    morale = "morale"
    couple = "couple"
    latent = "latent"
    policy = "policy"


def _fail(code, path, detail):
    raise InvalidValue(code, path, detail)


def _exact_int(value, path, low=0, high=INT_DOMAIN):
    if type(value) is not int:
        _fail("T15", path, "expected int")
    if not low <= value <= high:
        _fail("T10", path, f"outside {low}..{high}")


def _exact_str(value, path):
    if type(value) is not str:
        _fail("T15", path, "expected str")


# --------------------------------------------------------------------------
# EP08 primitive


def ep08_numerator(seed, pair, replicate, stage, channel, index):
    """The first 53 most significant bits of SHA-256 over the EP08 array."""
    for name, value in (("seed", seed), ("pair", pair), ("replicate", replicate),
                        ("stage", stage), ("channel", channel), ("index", index)):
        if name in ("seed", "replicate", "index"):
            _exact_int(value, name)
        else:
            _exact_str(value, name)
            if not value.isascii():
                _fail("T16", name, "expected ASCII")
    payload = json.dumps([RNG_VERSION, seed, pair, replicate, stage, channel, index],
                         separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:7], "big") >> 3


# --------------------------------------------------------------------------
# Run identity and fixture pairs


@dataclass(frozen=True, slots=True)
class RunKey:
    seed: int
    replicate: int

    def __post_init__(self):
        _exact_int(self.seed, "seed")
        _exact_int(self.replicate, "replicate")


def _pair_of(d):
    if d.fixture_class is FixtureClass.CANONICAL_OPENING:
        return f"{d.scenario_version}-{d.variant.name.lower()}"
    return d.fixture_id.token


PAIRS = tuple(sorted({_pair_of(d) for d in DESCRIPTORS}))


def fixture_pair(descriptor):
    """The logical pair token of one of the eight frozen descriptors (4.2)."""
    if type(descriptor) is not FixtureDescriptor:
        _fail("T15", "descriptor", "expected a FixtureDescriptor")
    for d in DESCRIPTORS:
        if d == descriptor:
            return _pair_of(d)
    _fail("T16", "descriptor.fixture_id", "not a frozen descriptor")


# --------------------------------------------------------------------------
# Stage ids


@dataclass(frozen=True, slots=True)
class StageKey:
    round: int
    root: str
    side: Side | None
    ordinal: int | None
    kind: str
    actor: FormationId | None
    target: FormationId | None
    source: FormationId | None

    def __post_init__(self):
        for name, ok in (
            ("round", type(self.round) is int),
            ("root", type(self.root) is str),
            ("side", self.side is None or type(self.side) is Side),
            ("ordinal", self.ordinal is None or type(self.ordinal) is int),
            ("kind", type(self.kind) is str),
            ("actor", self.actor is None or type(self.actor) is FormationId),
            ("target", self.target is None or type(self.target) is FormationId),
            ("source", self.source is None or type(self.source) is FormationId),
        ):
            if not ok:
                _fail("T15", name, "wrong type")
        if self.root not in ROOT_KINDS:
            _fail("T16", "stage_id", "unknown root")
        if self.root == "IN":
            if self.round != 0:
                _fail("T10", "round", "IN requires round 0")
        elif not 1 <= self.round <= ROUNDS:
            _fail("T10", "round", f"outside 1..{ROUNDS}")
        if self.root == "P":
            if self.side is None or self.ordinal is None:
                _fail("T16", "stage_id", "principal root needs side and ordinal")
            if not 1 <= self.ordinal <= ORDINALS:
                _fail("T10", "ordinal", f"outside 1..{ORDINALS}")
        elif self.side is not None or self.ordinal is not None:
            _fail("T16", "stage_id", "side and ordinal only on a principal root")
        if self.kind not in ROOT_KINDS[self.root]:
            _fail("T16", "stage_id", "kind not permitted for this root")
        if self.kind in PACKET_KINDS:
            if self.actor is None or self.target is None:
                _fail("T16", "stage_id", "packet kind needs actor, target and source")
            for f in (self.actor, self.target) + ((self.source,) if self.source else ()):
                if f.token not in _SIDE_OF:
                    _fail("T16", "stage_id", "not an F01 roster token")
            if _SIDE_OF[self.actor.token] is _SIDE_OF[self.target.token]:
                _fail("T16", "stage_id", "actor and target on the same side")
        elif (self.actor, self.target, self.source) != (None, None, None):
            _fail("T16", "stage_id", "suffix only on a packet kind")


def format_stage_id(key):
    if type(key) is not StageKey:
        _fail("T15", "key", "expected a StageKey")
    if key.root == "P":
        root = f"{key.side.name}.o{key.ordinal}"
    else:
        root = key.root
    text = f"r{key.round}:{root}:{key.kind}"
    if key.kind in PACKET_KINDS:
        source = key.source.token if key.source is not None else "-"
        text += f":{key.actor.token}:{key.target.token}:{source}"
    return text


_ID = re.compile(
    r"r(0|[1-9][0-9]*):(IN|CL|(S[01])\.o([1-9][0-9]*)):([A-Z_]+)"
    r"(?::(S[01]\.[A-Z][0-9]+):(S[01]\.[A-Z][0-9]+):(S[01]\.[A-Z][0-9]+|-))?")


def parse_stage_id(text):
    """The ``StageKey`` of a BK-1 id; T16 at ``stage_id`` for anything else."""
    _exact_str(text, "stage_id")
    if len(text) > ID_MAX or not text.isascii():
        _fail("T16", "stage_id", "too long or not ASCII")
    m = _ID.fullmatch(text)
    if m is None:
        _fail("T16", "stage_id", "malformed stage id")
    rnd, root, side, ordinal, kind, actor, target, source = m.groups()
    try:
        key = StageKey(
            round=int(rnd),
            root="P" if side else root,
            side=Side[side] if side else None,
            ordinal=int(ordinal) if ordinal else None,
            kind=kind,
            actor=FormationId(actor) if actor else None,
            target=FormationId(target) if target else None,
            source=FormationId(source) if source and source != "-" else None,
        )
    except InvalidValue as exc:
        raise InvalidValue("T16", "stage_id", f"invalid stage id ({exc})") from None
    if format_stage_id(key) != text:
        _fail("T16", "stage_id", "non-canonical spelling")
    return key


def draw_numerator(run, pair, stage_id, channel, index):
    """The validated BK-1 draw: argument types, pair, packet stage id, index."""
    for name, ok in (("run", type(run) is RunKey), ("pair", type(pair) is str),
                     ("stage_id", type(stage_id) is str), ("channel", type(channel) is Channel),
                     ("index", type(index) is int)):
        if not ok:
            _fail("T15", name, "wrong type")
    if pair not in PAIRS:
        _fail("T16", "pair", "unregistered fixture pair")
    key = parse_stage_id(stage_id)
    if key.kind not in PACKET_KINDS:
        _fail("T16", "stage_id", "stage kind does not draw")
    if not 0 <= index <= INDEX_MAX:
        _fail("T10", "index", f"outside 0..{INDEX_MAX}")
    return ep08_numerator(run.seed, pair, run.replicate, stage_id, channel.value, index)
