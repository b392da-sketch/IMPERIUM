"""Audit-side rule tables, written independently of the producer (P3 5, 8.2).

Stage traces, contextual stage ids, the effect whitelist, the canonical
diff, command shapes and the BK-1 grammar are re-derived here. Nothing is
imported from ``imperium.battle.engine``.
"""

import hashlib
import json
import re

from imperium.battle.canon import canonical_bytes_of
from imperium.battle.descriptors import DESCRIPTORS
from imperium.battle.values import FixtureClass

COMMAND_SCHEMA = "imperium.battle-command/1"
COMMAND_KEYS = {
    "OpenBattle": (),
    "HoldOrder": ("side", "formation"),
    "PassOrder": ("side",),
    "DeclareWithdrawal": ("side",),
    "Capitulate": ("side",),
}
USE_KIND = {"HoldOrder": "INDIVIDUAL", "PassOrder": "PASS",
            "DeclareWithdrawal": "POSTURE_WITHDRAWAL", "Capitulate": None}
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
SIDES = ("S0", "S1")

STAGES = ("INITIAL_CHECK", "ROOT", "IMMEDIATE_CHECK", "CLOSURE_DISPLACEMENT", "CLOSURE_CHECK",
          "RECOVERY", "ADVANCE", "END_CHECK", "OPEN_ROUND", "TERMINAL")
STAGE_ORDER = tuple(sorted(STAGES))
CLOSURE = ("CLOSURE_DISPLACEMENT", "CLOSURE_CHECK", "RECOVERY", "ADVANCE", "END_CHECK")

# The six frozen P2 traces: (stages, predecessor phase kind, successor phase kind).
T_OPEN = ("INITIAL_CHECK", "OPEN_ROUND")
T_OPEN_TERMINAL = ("INITIAL_CHECK", "TERMINAL")
T_ROOT = ("ROOT", "IMMEDIATE_CHECK")
T_ROOT_TERMINAL = ("ROOT", "IMMEDIATE_CHECK", "TERMINAL")
T_CLOSE = T_ROOT + CLOSURE + ("OPEN_ROUND",)
T_CLOSE_TERMINAL = T_ROOT + CLOSURE + ("TERMINAL",)
TRACES = {
    T_OPEN: ("Opening", "AwaitingPrincipal"),
    T_OPEN_TERMINAL: ("Opening", "Terminal"),
    T_ROOT: ("AwaitingPrincipal", "AwaitingPrincipal"),
    T_ROOT_TERMINAL: ("AwaitingPrincipal", "Terminal"),
    T_CLOSE: ("AwaitingPrincipal", "AwaitingPrincipal"),
    T_CLOSE_TERMINAL: ("AwaitingPrincipal", "Terminal"),
}


def traces_for(kind):
    if kind == "OpenBattle":
        return (T_OPEN, T_OPEN_TERMINAL)
    if kind == "Capitulate":
        return (T_ROOT_TERMINAL,)
    return (T_ROOT, T_ROOT_TERMINAL, T_CLOSE, T_CLOSE_TERMINAL)


CHECK_POINT = {"INITIAL_CHECK": "INITIAL_CHECK", "IMMEDIATE_CHECK": "AFTER_ROOT",
               "CLOSURE_CHECK": "AFTER_CLOSURE_DISPLACEMENT", "END_CHECK": "ROUND_END"}

CURSOR = ("clock", "event_cursor")
COMPLETED = ("clock", "completed_rounds")
ROOT_FIELDS = ("sides", "ledger", "formations", "personnel", "mounts", "ammunition", "contacts")


def permitted(stage, segments, trace):
    """Whether one effect path may appear in this stage (5.3)."""
    seg = tuple(segments)
    if stage == "INITIAL_CHECK":
        return seg == CURSOR
    if stage == "ROOT":
        return seg == CURSOR or (len(seg) >= 1 and seg[0] in ROOT_FIELDS)
    if stage == "IMMEDIATE_CHECK":
        return trace == T_ROOT and seg == ("phase", "side")
    if stage == "ADVANCE":
        return seg == COMPLETED
    if stage in ("OPEN_ROUND", "TERMINAL"):
        return len(seg) >= 1 and seg[0] in ("phase", "ledger")
    return False


# --------------------------------------------------------------------------
# Contextual stage ids


_P2_ID = re.compile(r"r(0|[1-9][0-9]*):(IN|CL|S[01]\.o[1-9][0-9]*):([A-Z_]+)")
_PACKET_ID = re.compile(
    r"r([1-9][0-9]*):(S[01])\.o([1-9][0-9]*):(MELEE|MISSILE):(S[01]\.[A-Z][0-9]+):"
    r"(S[01]\.[A-Z][0-9]+):(S[01]\.[A-Z][0-9]+|-)")
ROSTER = frozenset(f"{s}.{f}" for s in SIDES
                   for f in ("C1", "H1", "H2", "H3", "H4", "H5", "H6", "L1"))


def p2_id_kind(text):
    """The kind of a well-formed P2 stage id, or None."""
    m = _P2_ID.fullmatch(text) if len(text) <= 64 else None
    return m.group(3) if m else None


def packet_id(text):
    """The groups of a valid BK-1 packet id within the supported domain, or None."""
    if type(text) is not str or len(text) > 64:
        return None
    m = _PACKET_ID.fullmatch(text)
    if m is None:
        return None
    rnd, side, ordinal, kind, actor, target, source = m.groups()
    if not (1 <= int(rnd) <= 12 and 1 <= int(ordinal) <= 4):
        return None
    if actor not in ROSTER or target not in ROSTER or (source != "-" and source not in ROSTER):
        return None
    if actor[:2] == target[:2]:
        return None
    return m.groups()


def expected_ids(pre, command, stages):
    """The contextual id of each declared stage, from the pre-root document."""
    kind = command["kind"]
    if kind == "OpenBattle":
        return [f"r0:IN:{s}" for s in stages]
    rnd = pre["clock"]["completed_rounds"] + 1
    side = command["side"]
    ordinal = sum(1 for u in pre["ledger"]["uses"] if u["side"] == side) + 1
    out, closing = [], False
    for s in stages:
        if s in CLOSURE or s == "OPEN_ROUND":
            closing = True
        out.append(f"r{rnd}:CL:{s}" if closing else f"r{rnd}:{side}.o{ordinal}:{s}")
    return out


def expected_use(command):
    kind = command["kind"]
    work = [{"kind": "Hold"}] if kind == "HoldOrder" else []
    members = [command["formation"]] if kind == "HoldOrder" else []
    return {"side": command["side"], "kind": USE_KIND[kind], "group": None,
            "members": members, "work": work}


def command_shape(command):
    """None if ``command`` is a well-typed P2 command document, else a path."""
    if type(command) is not dict:
        return "/command"
    kind = command.get("kind")
    if type(kind) is not str or kind not in COMMAND_KEYS:
        return "/command/kind"
    if command.get("schema") != COMMAND_SCHEMA:
        return "/command/schema"
    if set(command) != {"schema", "kind", *COMMAND_KEYS[kind]}:
        return "/command"
    if "side" in command and command["side"] not in SIDES:
        return "/command/side"
    if "formation" in command:
        f = command["formation"]
        if type(f) is not str or TOKEN.fullmatch(f) is None:
            return "/command/formation"
    return None


# --------------------------------------------------------------------------
# Pointers, paths and the canonical diff


def split(text):
    """Typed segments of an RFC 6901 pointer: str keys or canonical int
    indices are resolved later against the document. None if malformed."""
    if type(text) is not str or not text.startswith("/"):
        return None
    out = []
    for raw in text[1:].split("/"):
        i = raw.find("~")
        while i >= 0:
            if raw[i + 1:i + 2] not in ("0", "1"):
                return None
            i = raw.find("~", i + 2)
        out.append(raw.replace("~1", "/").replace("~0", "~"))
    return out


def resolve(doc, raw_segments):
    """Typed segments for an existing location, or None."""
    node = doc
    typed = []
    for s in raw_segments:
        if type(node) is dict:
            if s not in node:
                return None
            typed.append(s)
            node = node[s]
        elif type(node) is list:
            if not (s.isdigit() and (s == "0" or s[0] != "0")):
                return None
            i = int(s)
            if i >= len(node):
                return None
            typed.append(i)
            node = node[i]
        else:
            return None
    return typed


def get(doc, typed):
    node = doc
    for s in typed:
        node = node[s]
    return node


def put(doc, typed, value):
    """A copy-on-write update: containers along the path are copied."""
    if not typed:
        return value
    head, rest = typed[0], typed[1:]
    if type(doc) is dict:
        out = dict(doc)
    else:
        out = list(doc)
    out[head] = put(doc[head], rest, value)
    return out


def order_key(typed):
    return tuple((0, s, "") if type(s) is int else (1, 0, s) for s in typed)


def cbytes(value):
    return canonical_bytes_of(value)


def canonical_diff(a, b, typed=()):
    if a is b:
        return []
    if type(a) is dict and type(b) is dict and a.keys() == b.keys():
        out = []
        for k in sorted(a):
            out.extend(canonical_diff(a[k], b[k], typed + (k,)))
        return out
    if type(a) is list and type(b) is list and len(a) == len(b):
        out = []
        for i in range(len(a)):
            out.extend(canonical_diff(a[i], b[i], typed + (i,)))
        return out
    if cbytes(a) == cbytes(b):
        return []
    return [(typed, a, b)]


def pointer(typed):
    return "".join("/" + (str(s) if type(s) is int else s.replace("~", "~0").replace("/", "~1"))
                   for s in typed)


# --------------------------------------------------------------------------
# Pairs and the EP08 formula (audit's own implementation)


def _pair(d):
    if d.fixture_class is FixtureClass.CANONICAL_OPENING:
        return f"{d.scenario_version}-{d.variant.name.lower()}"
    return d.fixture_id.token


PAIR_OF = {d.fixture_id.token: _pair(d) for d in DESCRIPTORS}
PAIRS = frozenset(PAIR_OF.values())
DESCRIPTOR_OF = {d.fixture_id.token: d for d in DESCRIPTORS}


def ep08(seed, pair, replicate, stage, channel, index):
    payload = json.dumps(["D4-SHA256-v1", seed, pair, replicate, stage, channel, index],
                         separators=(",", ":")).encode("ascii")
    return int(hashlib.sha256(payload).hexdigest()[:14], 16) >> 3
