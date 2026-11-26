"""Layer 10: the codec, its input domains and diagnostics (contract 13).

Decoding runs six stages; the first failure wins and is the only
``DecodeError`` raised. ``decode_bytes`` runs stages 1–6 and
``decode_state`` stages 4–6. Exactly three exception types are caught:
``UnicodeDecodeError`` around the one decode call, ``json.JSONDecodeError``
around the one ``json.loads`` call, and ``InvalidValue``/``InvalidState``
around construction in stage 6. Everything else propagates unchanged.
"""

import json
import math
import re
from fractions import Fraction

from .canon import SCHEMA, canonical_bytes_of, project_fields, sha256_hex
from .errors import DecodeError, InvalidState, InvalidValue, Violation
from .ids import valid_token
from .invariants import ROOT_SPEC
from .records import STATE_FIELDS
from .state import V00, BattleState, state_values
from .values import (
    SPECS, Bool, EnumK, Fixed, Frac, Hex, IdK, Int, Opt, RecK, Str, Var, keyed_increasing,
)

MAX_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_NODES = 100_000
MAX_INT = 2 ** 63 - 1
MAX_STRING = 1_024
MAX_INT_DIGITS = 19

_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:[.][0-9]+)?(?:[eE][+-]?[0-9]+)?")
_RATIONAL = re.compile(r"(0|-?[1-9][0-9]*)/([1-9][0-9]*)")
_SURROGATE = re.compile("[\ud800-\udfff]")
_JSON_WS = " \t\r\n"
_CANDIDATE_BEFORE = " \t\r\n[{,:"
_CANDIDATE_END = " \t\r\n,]}"
_DIGITS = "0123456789"


def _fail(code, path="", detail="", offset=None, violations=()):
    return DecodeError(code, path, detail, offset, violations)


def _escape(component):
    return component.replace("~", "~0").replace("/", "~1")


# --------------------------------------------------------------------------
# Encoding


def _require_state(s):
    if type(s) is not BattleState:
        raise InvalidValue(V00[0].clause, "state", V00[0].detail)


def encode_state(s):
    """A fresh canonical primitive tree on every call (13.5)."""
    _require_state(s)
    return project_fields(state_values(s))


def canonical_bytes(s):
    _require_state(s)
    return canonical_bytes_of(project_fields(state_values(s)))


def digest(s):
    """Full digest F: SHA-256 of the canonical bytes, lowercase hex."""
    return sha256_hex(canonical_bytes(s))


# --------------------------------------------------------------------------
# Stage 1: bytes


def _stage1(data):
    if type(data) is not bytes:
        raise _fail("BYTES_TYPE", detail="expected bytes")
    if len(data) > MAX_BYTES:
        raise _fail("BYTES_LIMIT", detail="input above 1,048,576 bytes")
    offset = None
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        offset = error.start
    if offset is not None:
        raise _fail("UTF8", detail="invalid UTF-8", offset=offset)
    return text


# --------------------------------------------------------------------------
# Stage 2: pre-scan (E08, Q-F)


def _stage2(text):
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    escaped = False
    while i < n:
        c = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "[" or c == "{":
            depth += 1
            if depth > MAX_DEPTH:
                raise _fail("DEPTH", detail="nesting above 32", offset=i)
            i += 1
            continue
        if c == "]" or c == "}":
            depth -= 1
            i += 1
            continue
        if (c == "-" or c in _DIGITS) and (i == 0 or text[i - 1] in _CANDIDATE_BEFORE):
            j = i
            while j < n and text[j] not in _CANDIDATE_END:
                j += 1
            candidate = text[i:j]
            if _NUMBER.fullmatch(candidate) is not None:
                if "." not in candidate and "e" not in candidate and "E" not in candidate:
                    digits = len(candidate) - (1 if candidate[0] == "-" else 0)
                    if digits > MAX_INT_DIGITS:
                        raise _fail("INTEGER_LIMIT", detail="integer above 19 digits", offset=i)
            i = j
            continue
        i += 1


# --------------------------------------------------------------------------
# Stage 3: parse with inert, non-raising, non-converting hooks (E08)


class _Pairs:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items


class _Number:
    __slots__ = ("lexeme", "kind")

    def __init__(self, lexeme, kind):
        self.lexeme = lexeme
        self.kind = kind


def _int_marker(lexeme):
    return _Number(lexeme, "int")


def _float_marker(lexeme):
    return _Number(lexeme, "float")


def _constant_marker(lexeme):
    return _Number(lexeme, "constant")


def _stage3(text):
    offset = None
    try:
        inert = json.loads(text, object_pairs_hook=_Pairs, parse_float=_float_marker,
                           parse_int=_int_marker, parse_constant=_constant_marker)
    except json.JSONDecodeError as error:
        offset = error.pos
    if offset is not None:
        raise _fail("SYNTAX", detail="invalid JSON", offset=offset)
    nonfinite = duplicate = fraction = None
    stack = [inert]
    while stack:
        node = stack.pop()
        t = type(node)
        if t is _Number:
            if node.kind == "constant":
                if nonfinite is None:
                    nonfinite = node
            elif node.kind == "float" and fraction is None:
                fraction = node
        elif t is _Pairs:
            seen = set()
            for key, _ in node.items:
                if key in seen and duplicate is None:
                    duplicate = key
                seen.add(key)
            for _, value in reversed(node.items):
                stack.append(value)
        elif t is list:
            for value in reversed(node):
                stack.append(value)
    if nonfinite is not None:
        raise _fail("NONFINITE", detail="NaN or infinity")
    if duplicate is not None:
        raise _fail("DUPLICATE_KEY", detail="duplicate key: " + duplicate)
    if fraction is not None:
        raise _fail("NOT_INTEGER", detail="number with a fraction or exponent")
    return _plain(inert)


def _plain(node):
    t = type(node)
    if t is _Number:
        return int(node.lexeme)
    if t is _Pairs:
        return {key: _plain(value) for key, value in node.items}
    if t is list:
        return [_plain(value) for value in node]
    return node


# --------------------------------------------------------------------------
# Stage 4: the tree domain (13.2)


def _stage4(tree):
    count = 0
    ancestors = set()
    stack = [(0, tree, "", 1)]
    while stack:
        task = stack.pop()
        op = task[0]
        if op == 1:
            ancestors.discard(task[1])
            continue
        if op == 2:
            _, d, key, pointer, depth = task
            key_pointer = pointer + "/" + _escape(key)
            if len(key) > MAX_STRING:
                raise _fail("STRING_LIMIT", key_pointer, "string above 1,024 code points")
            if _SURROGATE.search(key) is not None:
                raise _fail("SURROGATE", pointer, "lone surrogate in a key")
            stack.append((0, d[key], key_pointer, depth))
            continue
        _, x, pointer, depth = task
        t = type(x)
        if not (t is dict or t is list or t is str or t is int or t is bool or t is float
                or t is type(None)):
            raise _fail("DOMAIN_TYPE", pointer, "unsupported input type")
        container = t is dict or t is list
        if container:
            if id(x) in ancestors:
                raise _fail("CYCLE", pointer, "container is its own ancestor")
            if depth > MAX_DEPTH:
                raise _fail("DEPTH", pointer, "nesting above 32")
        count += 1
        if count > MAX_NODES:
            raise _fail("NODE_LIMIT", pointer, "more than 100,000 nodes")
        if t is int:
            if x > MAX_INT or x < -MAX_INT:
                raise _fail("INTEGER_LIMIT", pointer, "integer magnitude above 2^63 - 1")
        elif t is str:
            if len(x) > MAX_STRING:
                raise _fail("STRING_LIMIT", pointer, "string above 1,024 code points")
            if _SURROGATE.search(x) is not None:
                raise _fail("SURROGATE", pointer, "lone surrogate")
        elif t is float:
            if math.isnan(x) or math.isinf(x):
                raise _fail("NONFINITE", pointer, "NaN or infinity")
            raise _fail("NOT_INTEGER", pointer, "float value")
        elif t is list:
            ancestors.add(id(x))
            stack.append((1, id(x)))
            for i in range(len(x) - 1, -1, -1):
                stack.append((0, x[i], f"{pointer}/{i}", depth + 1))
        elif t is dict:
            for key in x:
                if type(key) is not str:
                    raise _fail("DOMAIN_TYPE", pointer, "unsupported input type")
            keys = sorted(x)
            ancestors.add(id(x))
            stack.append((1, id(x)))
            for key in reversed(keys):
                stack.append((2, x, key, pointer, depth + 1))


# --------------------------------------------------------------------------
# Stage 5: shape (13.4–13.6)


class _RecPlan:
    __slots__ = ("cls", "pointer", "items")

    def __init__(self, cls, pointer, items):
        self.cls = cls
        self.pointer = pointer
        self.items = items


class _TuplePlan:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items


def _plan_get(node, step):
    t = type(node)
    if t is _TuplePlan:
        return node.items[step]
    if t is _RecPlan:
        for name, value in node.items:
            if name == step:
                return value
    return object.__getattribute__(node, step)


_ENUM_MEMBERS = {}


def _members(cls):
    table = _ENUM_MEMBERS.get(cls)
    if table is None:
        table = {member.name: member for member in cls}
        _ENUM_MEMBERS[cls] = table
    return table


def _digits_to_int(digits):
    value = 0
    for start in range(0, len(digits), 18):
        chunk = digits[start:start + 18]
        value = value * 10 ** len(chunk) + int(chunk)
    return value


def _rational(text, pointer):
    m = _RATIONAL.fullmatch(text)
    if m is None:
        raise _fail("NONCANONICAL", pointer, "not a canonical rational")
    numerator_text = m.group(1)
    negative = numerator_text.startswith("-")
    numerator = _digits_to_int(numerator_text[1:] if negative else numerator_text)
    denominator = _digits_to_int(m.group(2))
    if math.gcd(numerator, denominator) != 1:
        raise _fail("NONCANONICAL", pointer, "rational not reduced")
    return Fraction(-numerator if negative else numerator, denominator)


def _shape(kind, node, pointer):
    t = type(kind)
    nt = type(node)
    if t is Int:
        if nt is not int:
            raise _fail("JSON_TYPE", pointer, "expected integer")
        return node
    if t is Bool:
        if nt is not bool:
            raise _fail("JSON_TYPE", pointer, "expected boolean")
        return node
    if t is Str:
        if nt is not str:
            raise _fail("JSON_TYPE", pointer, "expected string")
        return node
    if t is Frac:
        if nt is not str:
            raise _fail("JSON_TYPE", pointer, "expected rational string")
        return _rational(node, pointer)
    if t is EnumK:
        if nt is not str:
            raise _fail("JSON_TYPE", pointer, "expected enumeration token")
        member = _members(kind.cls).get(node)
        if member is None:
            raise _fail("TOKEN", pointer, "unknown enumeration token")
        return member
    if t is IdK:
        if nt is not str:
            raise _fail("JSON_TYPE", pointer, "expected identifier token")
        if not valid_token(node):
            raise _fail("TOKEN", pointer, "invalid identifier token")
        return kind.cls(node)
    if t is Opt:
        if node is None:
            return None
        return _shape(kind.inner, node, pointer)
    if t is Var:
        if nt is not list:
            raise _fail("JSON_TYPE", pointer, "expected array")
        items = [_shape(kind.elem, x, f"{pointer}/{i}") for i, x in enumerate(node)]
        if kind.key is not None and not keyed_increasing(items, kind.key, _plan_get):
            raise _fail("NONCANONICAL", pointer, "keyed array out of order or duplicated")
        return _TuplePlan(items)
    if t is Fixed:
        if nt is not list:
            raise _fail("JSON_TYPE", pointer, "expected array")
        if len(node) != len(kind.elems):
            raise _fail("JSON_TYPE", pointer, "wrong array length")
        items = [_shape(sub, x, f"{pointer}/{i}") for i, (sub, x) in enumerate(zip(kind.elems, node))]
        if kind.key is not None and not keyed_increasing(items, kind.key, _plan_get):
            raise _fail("NONCANONICAL", pointer, "keyed array out of order or duplicated")
        return _TuplePlan(items)
    if t is RecK:
        return _shape_record(kind, node, pointer)
    raise AssertionError("unknown field kind")


def _shape_record(kind, node, pointer):
    nt = type(node)
    if kind.classes == (Hex,):
        if nt is not list:
            raise _fail("JSON_TYPE", pointer, "expected [q, r]")
        if len(node) != 2:
            raise _fail("JSON_TYPE", pointer, "wrong array length")
        for i in (0, 1):
            if type(node[i]) is not int:
                raise _fail("JSON_TYPE", f"{pointer}/{i}", "expected integer")
        return Hex(node[0], node[1])
    if nt is not dict:
        raise _fail("JSON_TYPE", pointer, "expected object")
    if kind.is_union:
        tag = node.get("kind")
        cls = None
        if type(tag) is str:
            for candidate in kind.classes:
                if candidate.__name__ == tag:
                    cls = candidate
        if cls is None:
            raise _fail("UNION_TAG", pointer, "missing or unknown kind")
        required = ("kind",) + tuple(name for name, _ in SPECS[cls][0])
    else:
        cls = kind.classes[0]
        required = tuple(name for name, _ in SPECS[cls][0])
    _check_keys(node, required, pointer)
    items = [
        (name, _shape(sub, node[name], f"{pointer}/{name}")) for name, sub in SPECS[cls][0]
    ]
    return _RecPlan(cls, pointer, items)


def _check_keys(node, required, pointer):
    for name in required:
        if name not in node:
            raise _fail("KEYS", pointer, name)
    extras = sorted(key for key in node if key not in required)
    if extras:
        raise _fail("KEYS", pointer, extras[0])


def _stage5(tree):
    if type(tree) is not dict:
        raise _fail("JSON_TYPE", "", "expected object")
    schema = tree.get("schema")
    if type(schema) is not str or schema != SCHEMA:
        raise _fail("SCHEMA", "/schema", "missing or unsupported schema")
    _check_keys(tree, ("schema",) + STATE_FIELDS, "")
    return [_shape(kind, tree[name], "/" + name) for name, kind in ROOT_SPEC]


# --------------------------------------------------------------------------
# Stage 6: construction


def _build(plan):
    t = type(plan)
    if t is _RecPlan:
        values = [_build(value) for _, value in plan.items]
        failure = None
        try:
            return plan.cls(*values)
        except InvalidValue as error:
            failure = error
        local = failure.path
        path = plan.pointer + "/" + "/".join(_escape(p) for p in local.split("/"))
        raise _fail("CLAUSE", path, failure.detail, None,
                    (_violation(failure.clause, path, failure.detail),))
    if t is _TuplePlan:
        return tuple(_build(x) for x in plan.items)
    return plan


def _violation(clause, path, detail):
    return Violation(clause, path, detail)


def _stage6(plans):
    values = [_build(plan) for plan in plans]
    failure = None
    try:
        return BattleState(*values)
    except InvalidValue as error:
        failure = ("value", error)
    except InvalidState as error:
        failure = ("state", error)
    kind, error = failure
    if kind == "value":
        path = "/" + error.path
        raise _fail("CLAUSE", path, error.detail, None, (_violation(error.clause, path, error.detail),))
    first = error.violations[0]
    raise _fail("CLAUSE", first.path, first.detail, None, error.violations)


# --------------------------------------------------------------------------
# Public entry points


def decode_state(tree):
    """Stages 4–6 on a Python tree."""
    _stage4(tree)
    return _stage6(_stage5(tree))


def decode_bytes(data):
    """Stages 1–6 on raw bytes."""
    text = _stage1(data)
    _stage2(text)
    tree = _stage3(text)
    return decode_state(tree)
