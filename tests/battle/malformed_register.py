"""Malformed-document register (contract 16.1).

Each entry is ``(id, base fixture, edit, expected code, expected path,
expected clause or None)``. ``edit`` receives a fresh primitive copy of
the base fixture and returns either a tree (run through ``decode_state``)
or ``bytes`` (run through ``decode_bytes``). Every code of 13.1 and every
limit at and beyond its boundary appears at least once. Expected values are
written literally from the contract; none is computed from package code.
"""

import json

from tests.support.battle_builder import as_adversarial, opening_document, remove

BASES = {
    "open-standard": lambda: opening_document(),
    "adversarial": lambda: as_adversarial(opening_document(), "REG"),
}
LIMIT = 1_048_576
I63 = 2 ** 63 - 1


def canon(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def put(pointer_parts, value):
    def edit(d):
        node = d
        for p in pointer_parts[:-1]:
            node = node[p]
        node[pointer_parts[-1]] = value
        return d
    return edit


def extra(value, key="x"):
    def edit(d):
        d[key] = value
        return d
    return edit


def nested(depth):
    out = []
    for _ in range(depth - 1):
        out = [out]
    return out


def padded(extra_bytes):
    def edit(d):
        data = canon(d)
        return data + b" " * (LIMIT - len(data) + extra_bytes)
    return edit


REGISTER = [
    # stage 1
    ("BT1", "open-standard", lambda d: bytearray(canon(d)), "BYTES_TYPE", "", None),
    ("BT2", "open-standard", lambda d: canon(d).decode("ascii"), "BYTES_TYPE", "", None),
    ("BT3", "open-standard", lambda d: memoryview(canon(d)), "BYTES_TYPE", "", None),
    ("BL1", "open-standard", padded(0), None, None, None),
    ("BL2", "open-standard", padded(1), "BYTES_LIMIT", "", None),
    ("U81", "open-standard", lambda d: b'{"a":"\xff"}', "UTF8", "", None),
    # stage 2
    ("DP1", "open-standard", lambda d: b"[" * 32 + b"]" * 32, "JSON_TYPE", "", None),
    ("DP2", "open-standard", lambda d: b"[" * 33 + b"]" * 33, "DEPTH", "", None),
    ("DP3", "open-standard", lambda d: b'{"schema":"imperium.battle-state/1","a":"' + b"[" * 40 + b'"}',
     "KEYS", "", None),
    ("IL1", "open-standard", lambda d: b'{"a":12345678901234567890}', "INTEGER_LIMIT", "", None),
    ("IL2", "open-standard", lambda d: b'{"a":-12345678901234567890}', "INTEGER_LIMIT", "", None),
    ("IL3", "open-standard", lambda d: b'{"a":1234567890123456789}', "SCHEMA", "/schema", None),
    # stage 3
    ("SY1", "open-standard", lambda d: canon(d)[:-1], "SYNTAX", "", None),
    ("SY2", "open-standard", lambda d: canon(d) + b"x", "SYNTAX", "", None),
    ("SY3", "open-standard", lambda d: b"\xef\xbb\xbf" + canon(d), "SYNTAX", "", None),
    ("NF1", "open-standard", lambda d: b'{"a":NaN}', "NONFINITE", "", None),
    ("NF2", "open-standard", lambda d: b'{"a":-Infinity}', "NONFINITE", "", None),
    ("DK1", "open-standard", lambda d: b'{"a":1,"a":2}', "DUPLICATE_KEY", "", None),
    ("NI1", "open-standard", lambda d: b'{"a":1.5}', "NOT_INTEGER", "", None),
    ("NI2", "open-standard", lambda d: b'{"a":1e5}', "NOT_INTEGER", "", None),
    # stage 4
    ("DT1", "open-standard", put(["clock", "event_cursor"], (0,)), "DOMAIN_TYPE",
     "/clock/event_cursor", None),
    ("DT2", "open-standard", put(["clock", 5], 1), "DOMAIN_TYPE", "/clock", None),
    ("CY1", "open-standard", lambda d: (lambda x: (x.append(x), d.update(x=x), d)[2])([]),
     "CYCLE", "/x/0", None),
    ("DP4", "open-standard", lambda d: nested(33), "DEPTH", "/0" * 32, None),
    ("DP5", "open-standard", lambda d: nested(32), "JSON_TYPE", "", None),
    ("NL1", "open-standard", lambda d: [0] * 99_999, "JSON_TYPE", "", None),
    ("NL2", "open-standard", lambda d: [0] * 100_000, "NODE_LIMIT", "/99999", None),
    ("IL4", "open-standard", extra(I63), "KEYS", "", None),
    ("IL5", "open-standard", extra(-I63), "KEYS", "", None),
    ("IL6", "open-standard", extra(I63 + 1), "INTEGER_LIMIT", "/x", None),
    ("IL7", "open-standard", extra(-I63 - 1), "INTEGER_LIMIT", "/x", None),
    ("SL1", "open-standard", extra("a" * 1024), "KEYS", "", None),
    ("SL2", "open-standard", extra("a" * 1025), "STRING_LIMIT", "/x", None),
    ("SL3", "open-standard", extra(1, "k" * 1025), "STRING_LIMIT", "/" + "k" * 1025, None),
    ("SG1", "open-standard", extra("\ud800"), "SURROGATE", "/x", None),
    ("SG2", "open-standard", extra(1, "\udc00"), "SURROGATE", "", None),
    ("FL1", "open-standard", put(["clock", "event_cursor"], 4.0), "NOT_INTEGER",
     "/clock/event_cursor", None),
    ("FL2", "open-standard", put(["clock", "event_cursor"], float("inf")), "NONFINITE",
     "/clock/event_cursor", None),
    # stage 5
    ("JT1", "open-standard", lambda d: [d], "JSON_TYPE", "", None),
    ("JT2", "open-standard", put(["clock", "event_cursor"], True), "JSON_TYPE",
     "/clock/event_cursor", None),
    ("JT3", "open-standard", put(["formations", 0, "cell"], [1, 6, 0]), "JSON_TYPE",
     "/formations/0/cell", None),
    ("SC1", "open-standard", lambda d: remove(d, "/schema"), "SCHEMA", "/schema", None),
    ("SC2", "open-standard", put(["schema"], "imperium.battle-state/2"), "SCHEMA", "/schema", None),
    ("SC3", "open-standard", put(["schema"], 1), "SCHEMA", "/schema", None),
    ("UT1", "open-standard", put(["phase"], {"kind": "Opened"}), "UNION_TAG", "/phase", None),
    ("UT2", "open-standard", put(["phase"], {"side": "S0"}), "UNION_TAG", "/phase", None),
    ("KY1", "open-standard", extra(1), "KEYS", "", None),
    ("KY2", "open-standard", lambda d: remove(d, "/clock/event_cursor"), "KEYS", "/clock", None),
    ("KY3", "open-standard", put(["phase"], {"kind": "Opening", "side": "S0"}), "KEYS", "/phase",
     None),
    ("TK1", "open-standard", put(["formations", 0, "disposition"], "BANANA"), "TOKEN",
     "/formations/0/disposition", None),
    ("TK2", "open-standard", put(["formations", 0, "formation"], "S0 C1"), "TOKEN",
     "/formations/0/formation", None),
    ("NC1", "open-standard", put(["scenario", "profile", "packet", "melee_p0"], "2/20"),
     "NONCANONICAL", "/scenario/profile/packet/melee_p0", None),
    ("NC2", "open-standard", lambda d: (d["personnel"].reverse(), d)[1], "NONCANONICAL",
     "/personnel", None),
    # stage 6
    ("CL1", "open-standard", put(["formations", 0, "facing"], 6), "CLAUSE", "/formations/0/facing",
     "T08"),
    ("CL2", "open-standard", put(["formations", 0, "condition", "cohesion"], 3), "CLAUSE",
     "/formations/0/condition/cohesion", "T09"),
    ("CL3", "adversarial", put(["formations", 1, "cell"], [1, 6]), "CLAUSE", None, "F02"),
]
