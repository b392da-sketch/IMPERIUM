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
USES = ("ledger", "uses")
CUSTODY = ("formations", "personnel", "mounts", "ammunition", "contacts")


def permitted(stage, segments, trace, command, pre):
    """Whether one effect path may appear in this stage for this command (5.3).

    ROOT is command-scoped: Hold and Pass append a ledger use, Withdrawal also
    sets the acting side's posture, and Capitulate changes custody fields
    only. ``pre`` is the verified stable predecessor document.
    """
    seg = tuple(segments)
    if stage == "INITIAL_CHECK":
        return seg == CURSOR
    if stage == "ROOT":
        if seg == CURSOR:
            return True
        kind = command["kind"]
        if kind == "Capitulate":
            return len(seg) >= 1 and seg[0] in CUSTODY
        if seg == USES:
            return True
        if kind == "DeclareWithdrawal" and len(seg) == 3 and seg[0] == "sides" \
                and seg[2] == "posture" and type(seg[1]) is int:
            return pre["sides"][seg[1]]["side"] == command["side"]
        return False
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


_INDEX = re.compile(r"0|[1-9][0-9]{0,18}")


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
            # ASCII canonical decimal only, bounded before conversion.
            if _INDEX.fullmatch(s) is None:
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


# --------------------------------------------------------------------------
# Audit v2: P4 orders, stages and window decisions (P4 contract rev 0.2
# sections 10.3-10.5, ER05, ER06, E03, E04). Re-derived independently of the
# engine.

AUDIT_SCHEMA_V2 = "imperium.battle-audit/2"
EVENT_SCHEMA_V1 = "imperium.battle-event/1"
EVENT_SCHEMA_V2 = "imperium.battle-event/2"
P4_ORDERS = {
    "MoveOrder": ("side", "formation", "path"),
    "PivotOrder": ("side", "formation", "turn", "steps"),
    "WithdrawOrder": ("side", "formation", "destination"),
    "EvacuateOrder": ("side", "formation"),
    "GroupMoveOrder": ("side", "group", "members", "direction"),
    "GroupPivotOrder": ("side", "group", "members", "turn"),
}
DECISIONS = {
    "RespondPivot": ("side", "window_id", "formation", "target"),
    "RespondMissile": ("side", "window_id", "formation", "target"),
    "DeclineResponse": ("side", "window_id"),
}
COMMAND_KEYS_V2 = dict(COMMAND_KEYS, **P4_ORDERS)
for _kind in P4_ORDERS:
    USE_KIND[_kind] = "GROUP" if _kind.startswith("Group") else "INDIVIDUAL"
del _kind
P4_STAGE_NAMES = ("STEP1", "STEP2", "STEP3", "WITHDRAW", "GROUP_STEP", "PIVOT", "GROUP_PIVOT",
                  "EVACUATE", "WINDOW", "RESPONSE")
STAGES_V2 = STAGES + P4_STAGE_NAMES
STAGE_ORDER_V2 = tuple(sorted(STAGES_V2))
STEPS = ("STEP1", "STEP2", "STEP3")
TRIGGERS = STEPS + ("WITHDRAW", "GROUP_STEP")
FIRST_PHYSICAL = {"MoveOrder": "STEP1", "WithdrawOrder": "WITHDRAW", "GroupMoveOrder": "GROUP_STEP",
                  "PivotOrder": "PIVOT", "GroupPivotOrder": "GROUP_PIVOT",
                  "EvacuateOrder": "EVACUATE"}
TAILS = {
    ("IMMEDIATE_CHECK",): "AwaitingPrincipal",
    ("IMMEDIATE_CHECK", "TERMINAL"): "Terminal",
    ("IMMEDIATE_CHECK",) + CLOSURE + ("OPEN_ROUND",): "AwaitingPrincipal",
    ("IMMEDIATE_CHECK",) + CLOSURE + ("TERMINAL",): "Terminal",
}
WINDOW_TAG = "IMPERIUM-P4-window-1"
DIRS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
_P4_ID = re.compile(r"r([1-9][0-9]*):(S[01])\.o([1-9][0-9]*):(" + "|".join(P4_STAGE_NAMES) + ")")


def id_kind_v2(text):
    """The kind of a well-formed v2 stage id, or None: the ten P4 kinds only
    on the principal form within BK-1's round and ordinal domain."""
    if type(text) is not str or len(text) > 64:
        return None
    m = _P4_ID.fullmatch(text)
    if m is not None:
        if 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(3)) <= 4:
            return m.group(4)
        return None
    return p2_id_kind(text)


def _cell_ok(value):
    return type(value) is list and len(value) == 2 and all(type(v) is int for v in value)


def _token_ok(value):
    return type(value) is str and TOKEN.fullmatch(value) is not None


def _digest_ok(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def order_shape(command, table):
    """None if ``command`` is a well-formed document of ``table``, else a path.

    Accepted P4 orders also satisfy their value ranges (ER07).
    """
    if type(command) is not dict:
        return "/command"
    kind = command.get("kind")
    if type(kind) is not str or kind not in table:
        return "/command/kind"
    if command.get("schema") != COMMAND_SCHEMA:
        return "/command/schema"
    if set(command) != {"schema", "kind", *table[kind]}:
        return "/command"
    if "side" in command and command["side"] not in SIDES:
        return "/command/side"
    for key in ("formation", "group", "target"):
        if key in command and not _token_ok(command[key]):
            return f"/command/{key}"
    if "window_id" in command and not _digest_ok(command["window_id"]):
        return "/command/window_id"
    if "path" in command:
        path = command["path"]
        if type(path) is not list or not 1 <= len(path) <= 3 or not all(map(_cell_ok, path)):
            return "/command/path"
    if "destination" in command and not _cell_ok(command["destination"]):
        return "/command/destination"
    if "members" in command:
        m = command["members"]
        if (type(m) is not list or not 2 <= len(m) <= 3 or not all(map(_token_ok, m))
                or any(a >= b for a, b in zip(m, m[1:]))):
            return "/command/members"
    for key, ok in (("turn", (-1, 1)), ("steps", (1, 2, 3)), ("direction", range(6))):
        if key in command and (type(command[key]) is not int or command[key] not in ok):
            return f"/command/{key}"
    return None


def command_shape_v2(command):
    return order_shape(command, COMMAND_KEYS_V2)


def decision_shape(command):
    return order_shape(command, DECISIONS)


def p4_family(kind, stages):
    """Static AU09 check of a P4 trace: True iff ``stages`` is a member of
    the selected family (E03: sequence, ordering and predecessors only)."""
    if not stages or stages[0] != "ROOT":
        return False
    i = 1
    first = FIRST_PHYSICAL[kind]
    windows = 0
    if kind == "MoveOrder":
        k = 0
        while i < len(stages) and stages[i] in STEPS:
            if stages[i] != STEPS[k]:
                return False
            k += 1
            i += 1
            if i < len(stages) and stages[i] == "WINDOW":
                windows += 1
                i += 1
                if i < len(stages) and stages[i] == "RESPONSE":
                    i += 1
        if k == 0:
            return False
    else:
        if i >= len(stages) or stages[i] != first:
            return False
        i += 1
        if first in TRIGGERS and i < len(stages) and stages[i] == "WINDOW":
            windows += 1
            i += 1
            if i < len(stages) and stages[i] == "RESPONSE":
                i += 1
    if windows > 1:
        return False
    return tuple(stages[i:]) in TAILS


def p4_permitted(stage, typed, ctx):
    """Whether one effect path may appear in a P4 stage (ER06 whitelist)."""
    seg = tuple(typed)
    if stage == "ROOT":
        return seg == CURSOR
    if stage == "WINDOW":
        return False
    actors = ctx["actors"]
    first = stage == ctx["first"]
    if seg == USES:
        return first
    n = len(seg)
    if n >= 3 and seg[0] == "formations" and type(seg[1]) is int:
        who = ctx["formation_at"](seg[1])
        if who not in actors:
            return False
        field = seg[2]
        if field == "condition":
            return n == 4 and seg[3] in ("exertion", "fatigue")
        if field == "cell":
            return n <= 4 and stage in TRIGGERS
        if field == "facing":
            return n == 3 and stage in ("PIVOT", "GROUP_PIVOT", "RESPONSE")
        if field == "disposition":
            return n == 3 and stage == "EVACUATE"
        return False
    if n == 4 and seg[:2] == ("ledger", "formations") and type(seg[2]) is int:
        if seg[3] == "safe_latch":
            return True
        who = ctx["round_at"](seg[2])
        if seg[3] == "exerted":
            return who in actors
        if seg[3] == "response":
            return stage == "RESPONSE" and who in actors
        return False
    if stage in ("STEP2", "STEP3") and n == 6 and seg[:2] == USES and seg[2] == ctx["use_index"] \
            and seg[3:5] == ("work", 0) and seg[5] in ("legs", "end"):
        return True
    if stage == "EVACUATE" and n == 3 and seg[0] in ("personnel", "mounts", "ammunition") \
            and type(seg[1]) is int:
        return ctx["evacuable"](seg[0], seg[1], seg[2])
    return False


def window_id(previous, command, after):
    command_digest = hashlib.sha256(canonical_bytes_of(command)).hexdigest()
    return hashlib.sha256(canonical_bytes_of([WINDOW_TAG, previous, command_digest, after])
                          ).hexdigest()


def map_marks(condition, marks, threshold=6):
    """MP21 with N01 carry, re-derived for the audit (P4 6.2)."""
    e = condition["exertion"] + marks
    f = condition["fatigue"]
    while e >= threshold and f < 2:
        f += 1
        e -= threshold
    if f == 2:
        e %= threshold
    return f, e
