"""Audit wire framing: LF-delimited canonical ASCII JSON lines (P3 7, ER01).

Independent of the engine. Uses only the stdlib and P1 canonical bytes.
"""

import json

from imperium.battle.canon import canonical_bytes_of

from .errors import AuditError

MAX_INPUT = 256 * 1024 * 1024
MAX_LINE = 1024 * 1024
MAX_DEPTH = 32
INT_LOW = -(2 ** 63)
INT_HIGH = 2 ** 63 - 1
HEX = frozenset("0123456789abcdef")


class _Reject(ValueError):
    pass


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise _Reject("duplicate key")
        out[k] = v
    return out


def _reject_float(token):
    raise _Reject("float or exponent")


def _reject_constant(token):
    raise _Reject("non-finite token")


def _depth_ok(raw):
    """String-aware nesting pre-scan; the root object has depth 1."""
    depth = 0
    in_string = escape = False
    for b in raw:
        if in_string:
            if escape:
                escape = False
            elif b == 0x5C:
                escape = True
            elif b == 0x22:
                in_string = False
        elif b == 0x22:
            in_string = True
        elif b in (0x7B, 0x5B):
            depth += 1
            if depth > MAX_DEPTH:
                return False
        elif b in (0x7D, 0x5D):
            depth -= 1
    return True


def _has_surrogate(text):
    return any(0xD800 <= ord(c) <= 0xDFFF for c in text)


def _values_ok(tree):
    """P1 signed integers only, and no lone surrogates in strings or keys."""
    stack = [tree]
    while stack:
        v = stack.pop()
        t = type(v)
        if t is int and not INT_LOW <= v <= INT_HIGH:
            return False
        if t is str and _has_surrogate(v):
            return False
        if t is list:
            stack.extend(v)
        elif t is dict:
            if any(_has_surrogate(k) for k in v):
                return False
            stack.extend(v.values())
    return True


def is_digest(value):
    return type(value) is str and len(value) == 64 and all(c in HEX for c in value)


def lines(data):
    """Yield ``(line_number, raw_bytes)``; AU01 for framing faults, raised
    only when the faulty line is reached."""
    if len(data) > MAX_INPUT:
        raise AuditError("AU01", 1, "", "input exceeds 256 MiB")
    if not data:
        raise AuditError("AU01", 1, "", "empty input")
    start = 0
    number = 0
    while start < len(data):
        number += 1
        end = data.find(b"\n", start)
        if end < 0:
            raise AuditError("AU01", number, "", "incomplete final line")
        yield number, data[start:end]
        start = end + 1


def parse(number, raw):
    """The canonical JSON object of one line; AU01 on any lexical fault."""
    def bad(detail):
        raise AuditError("AU01", number, "", detail)

    if not raw:
        bad("empty line")
    if len(raw) > MAX_LINE:
        bad("line exceeds 1 MiB")
    if not raw.isascii() or b"\r" in raw:
        bad("non-ASCII or CR byte")
    if not _depth_ok(raw):
        bad("nesting deeper than 32")
    try:
        tree = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                          parse_float=_reject_float, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        bad("malformed JSON")
    if type(tree) is not dict:
        bad("a line is one JSON object")
    if not _values_ok(tree):
        bad("integer outside the P1 signed domain or a lone surrogate")
    if canonical_bytes_of(tree) != raw:
        bad("not canonical")
    if not is_digest(tree.get("chain")):
        raise AuditError("AU01", number, "/chain", "missing or malformed chain token")
    return tree


def body(tree):
    out = dict(tree)
    del out["chain"]
    return canonical_bytes_of(out)
