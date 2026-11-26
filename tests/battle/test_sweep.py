"""Corruption sweep and seeded multi-edits (16.1, 16.2, AT-C11).

Single edits are applied to the encoded document of every registered
fixture and of the adversarial A1, collapse and capitulation states. The
pass condition is total: an edit either decodes to a valid state that
round-trips and conserves personnel, mounts and ammunition, or raises
``DecodeError``. An edit designed to be invalid must raise. Any other
exception fails the test.

Workload: the per-push run edits every ``STRIDE``-th node of each base
document with every applicable edit kind; ``IMPERIUM_FULL_SWEEP=1`` edits
every node. Seeds 0-999 drive the multi-edit run (test-only seeds; no
holdout range is used).
"""

import copy
import json
import os
import random
import re
import unittest

import imperium.battle as B
from imperium.battle.values import ENUM_CLASSES
from tests.battle.common import a1
from tests.battle.scenarios import capitulation, collapse

STRIDE = 1 if os.environ.get("IMPERIUM_FULL_SWEEP") == "1" else 17
SEEDS = range(1000)
RATIONAL = re.compile(r"^(0|-?[1-9][0-9]*)/([1-9][0-9]*)$")
TOKENS = sorted({m.name for e in ENUM_CLASSES for m in e})


def bases():
    out = []
    for d in B.DESCRIPTORS:
        if d.fixture_id in B.supplied_ids():
            s = B.f01_supplied(d.fixture_id)
        else:
            s = B.f01_opening(d.variant, d.orientation)
        out.append((d.fixture_id.token, B.encode_state(s)))
    out += [("A1", a1()), ("COLLAPSE", collapse()), ("CAPITULATION", capitulation())]
    return out


def nodes(tree, parts=()):
    yield parts, tree
    if type(tree) is dict:
        for k in sorted(tree):
            yield from nodes(tree[k], parts + (k,))
    elif type(tree) is list:
        for i, item in enumerate(tree):
            yield from nodes(item, parts + (i,))


def at(tree, parts):
    for p in parts:
        tree = tree[p]
    return tree


def replaced(doc, parts, value):
    out = copy.deepcopy(doc)
    if not parts:
        return value
    at(out, parts[:-1])[parts[-1]] = value
    return out


def deleted(doc, parts):
    out = copy.deepcopy(doc)
    container = at(out, parts[:-1])
    del container[parts[-1]]
    return out


def dump(tree, target=None, mode=None, parts=()):
    """Canonical-style JSON text; at ``target`` escape the string or duplicate the key."""
    if type(tree) is dict:
        members = []
        for k in sorted(tree):
            member = json.dumps(k) + ":" + dump(tree[k], target, mode, parts + (k,))
            members.append(member)
            if mode == "duplicate" and parts + (k,) == target:
                members.append(member)
        return "{" + ",".join(members) + "}"
    if type(tree) is list:
        return "[" + ",".join(dump(x, target, mode, parts + (i,)) for i, x in enumerate(tree)) + "]"
    if mode == "escape" and parts == target and type(tree) is str and tree:
        return '"' + "".join(f"\\u{ord(c):04x}" for c in tree) + '"'
    return json.dumps(tree, ensure_ascii=True)


def type_changed(value):
    t = type(value)
    if t is bool:
        return "true"
    if t is int:
        return str(value)
    if t is str:
        return 1
    if t is list:
        return {}
    if t is dict:
        return []
    return []


def edits(doc, parts, value):
    """``(kind, data, must_reject)`` for one node."""
    if parts:
        parent = at(doc, parts[:-1])
        if type(parent) is dict:
            yield "delete", deleted(doc, parts), True
            yield "duplicate", dump(doc, parts, "duplicate").encode("ascii"), True
    if type(value) is dict:
        yield "add", replaced(doc, parts, dict(value, zz_extra=0)), True
    yield "type", replaced(doc, parts, type_changed(value)), True
    if type(value) is int and type(value) is not bool:
        yield "plus", replaced(doc, parts, value + 1), False
        yield "minus", replaced(doc, parts, value - 1), False
    if type(value) is list and len(value) >= 2 and value[0] != value[1]:
        swapped = [value[1], value[0]] + value[2:]
        yield "swap", replaced(doc, parts, swapped), False
    if type(value) is str:
        if value in TOKENS:
            other = TOKENS[(TOKENS.index(value) + 1) % len(TOKENS)]
            yield "enum", replaced(doc, parts, other), False
        m = RATIONAL.match(value)
        if m:
            yield "rational", replaced(doc, parts, f"{2 * int(m[1])}/{2 * int(m[2])}"
                                       if m[1] != "0" else "0/2"), True
        yield "escape", dump(doc, parts, "escape").encode("ascii"), False


def decode(data):
    if type(data) is bytes:
        return B.decode_bytes(data)
    return B.decode_state(data)


class SweepCase(unittest.TestCase):
    def check_valid(self, s):
        self.assertEqual(B.validate_state(s), ())
        again = B.decode_bytes(B.canonical_bytes(s))
        self.assertEqual(again, s)
        self.assertEqual(B.canonical_bytes(again), B.canonical_bytes(s))
        templates = {t.kind: t for t in s.scenario.profile.templates}
        for entry in s.scenario.roster:
            t = templates[entry.template]
            people = sum(l.count for l in s.personnel if l.lineage == entry.formation)
            mounts = sum(m.count for m in s.mounts if m.formation == entry.formation)
            ammo = [a.carried + a.expended for a in s.ammunition if a.formation == entry.formation]
            self.assertEqual(people, t.personnel)
            self.assertEqual(mounts, t.mounts)
            self.assertEqual(sum(ammo), t.ammunition)

    def outcome(self, data, must_reject, label):
        try:
            s = decode(data)
        except B.DecodeError:
            return "rejected"
        self.assertFalse(must_reject, f"designed-invalid edit accepted: {label}")
        self.check_valid(s)
        return "accepted"


class CorruptionSweepTests(SweepCase):
    def test_at_c11_single_edits(self):
        counts = {"accepted": 0, "rejected": 0}
        for name, doc in bases():
            original = B.canonical_bytes(B.decode_state(doc))
            for index, (parts, value) in enumerate(nodes(doc)):
                if index % STRIDE:
                    continue
                for kind, data, must_reject in edits(doc, parts, value):
                    label = f"{name} {kind} {parts}"
                    result = self.outcome(data, must_reject, label)
                    counts[result] += 1
                    if kind == "escape":
                        self.assertEqual(result, "accepted", label)
                        self.assertEqual(B.canonical_bytes(B.decode_bytes(data)), original, label)
        self.assertGreater(counts["rejected"], 0)
        self.assertGreater(counts["accepted"], 0)


class SeededMultiEditTests(SweepCase):
    def test_seeded_multi_edits(self):
        docs = bases()
        node_lists = [(name, doc, list(nodes(doc))) for name, doc in docs]
        for seed in SEEDS:
            rng = random.Random(seed)
            name, doc, node_list = node_lists[rng.randrange(len(node_lists))]
            current = copy.deepcopy(doc)
            log = []
            for _ in range(rng.randint(1, 3)):
                parts, _ = node_list[rng.randrange(len(node_list))]
                try:
                    value = at(current, parts)
                except (KeyError, IndexError, TypeError):
                    continue
                options = [e for e in edits(current, parts, value) if type(e[1]) is not bytes]
                if not options:
                    continue
                kind, current, _ = options[rng.randrange(len(options))]
                log.append((kind, parts))
                if type(current) is not dict:
                    break
            with self.subTest(seed=seed, base=name, edits=log):
                self.outcome(current, False, f"seed {seed}: {log}")
