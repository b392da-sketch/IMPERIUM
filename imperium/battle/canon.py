"""Layer 6: the pure primitive projection, canonical bytes and the two
SHA-256 digests (contract 11.2, 13.4, 13.5).

It walks declared fields only. It never constructs, decodes or
validates, and it needs no ``BattleState``: it works on field values.
"""

import hashlib
import json
from fractions import Fraction

from .ids import ID_CLASSES
from .records import STATE_FIELDS, UNION_CLASSES
from .values import ENUM_CLASSES, SPECS, Hex

SCHEMA = "imperium.battle-state/1"
ZERO_DIGEST = "0" * 64

_ENUMS = frozenset(ENUM_CLASSES)
_IDS = frozenset(ID_CLASSES)


def project(value):
    """The primitive JSON tree of one P1 value (13.5)."""
    t = type(value)
    if value is None or t is bool or t is int or t is str:
        return value
    if t is Fraction:
        return f"{value.numerator}/{value.denominator}"
    if t in _ENUMS:
        return value.name
    if t in _IDS:
        return value.token
    if t is Hex:
        return [value.q, value.r]
    if t is tuple:
        return [project(x) for x in value]
    spec = SPECS.get(t)
    if spec is None:
        raise TypeError("not a P1 value")
    tree = {name: project(object.__getattribute__(value, name)) for name, _ in spec[0]}
    if t in UNION_CLASSES:
        tree["kind"] = t.__name__
    return tree


def project_fields(fields):
    """The root document of a state given its field values, in 6.2 order."""
    tree = {"schema": SCHEMA}
    for name, value in zip(STATE_FIELDS, fields):
        tree[name] = project(value)
    return tree


def canonical_bytes_of(tree):
    return json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def full_digest(fields):
    """F: SHA-256 of the canonical bytes as they are (11.2)."""
    return sha256_hex(canonical_bytes_of(project_fields(fields)))


def normalized_tree(tree):
    """A shallow-rebuilt copy of ``tree`` with ``origin_digest`` zeroed."""
    out = dict(tree)
    scenario = dict(out["scenario"])
    provenance = dict(scenario["provenance"])
    provenance["origin_digest"] = ZERO_DIGEST
    scenario["provenance"] = provenance
    out["scenario"] = scenario
    return out


def normalized_digest(fields):
    """N: SHA-256 of the canonical bytes with ``origin_digest`` zeroed (11.2)."""
    return sha256_hex(canonical_bytes_of(normalized_tree(project_fields(fields))))


def opening_projection_digest(fields):
    """P10(c): phase replaced by ``Opening`` and ``origin_digest`` zeroed."""
    tree = normalized_tree(project_fields(fields))
    tree["phase"] = {"kind": "Opening"}
    return sha256_hex(canonical_bytes_of(tree))
