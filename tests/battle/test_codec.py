"""14.9 codec and input domains (AT-C01–C20) and the malformed register."""

import copy
import dataclasses
import json
import unittest
from fractions import Fraction
from unittest import mock

import imperium.battle as B
from imperium.battle import invariants
from tests.battle.common import BattleCase, a1, canon, dumps
from tests.battle.malformed_register import BASES, REGISTER
from tests.battle.scenarios import capitulation, collapse
from tests.support.battle_builder import as_adversarial, build, opening_document

OPEN = opening_document()


def run(data):
    if type(data) is dict or type(data) is list:
        return B.decode_state(data)
    if type(data) is bytes:
        return B.decode_bytes(data)
    return B.decode_bytes(data)


class RegisterTests(unittest.TestCase):
    def test_at_c01_register(self):
        codes = set()
        for rid, base, edit, code, path, clause in REGISTER:
            with self.subTest(rid=rid):
                data = edit(BASES[base]())
                if code is None:
                    self.assertEqual(B.canonical_bytes(run(data)), canon(OPEN))
                    continue
                codes.add(code)
                with self.assertRaises(B.DecodeError) as cm:
                    run(data)
                e = cm.exception
                self.assertEqual(e.code, code, msg=str(e))
                if path is not None:
                    self.assertEqual(e.path, path)
                if clause is not None:
                    self.assertIn(clause, [v.clause for v in e.violations])
        expected = {"BYTES_TYPE", "BYTES_LIMIT", "UTF8", "DEPTH", "INTEGER_LIMIT", "SYNTAX",
                    "NONFINITE", "DUPLICATE_KEY", "NOT_INTEGER", "DOMAIN_TYPE", "CYCLE",
                    "NODE_LIMIT", "STRING_LIMIT", "SURROGATE", "JSON_TYPE", "SCHEMA", "UNION_TAG",
                    "KEYS", "TOKEN", "NONCANONICAL", "CLAUSE"}
        self.assertEqual(codes, expected)


class ByteAndTreeTests(BattleCase):
    def test_at_c02(self):
        d = copy.deepcopy(OPEN)
        d["clock"]["completed_rounds"] = True
        self.decode_code(d, "JSON_TYPE", "/clock/completed_rounds")
        d = copy.deepcopy(OPEN)
        d["scenario"]["profile"]["templates"][0]["melee_capable"] = 1
        self.decode_code(d, "JSON_TYPE", "/scenario/profile/templates/0/melee_capable")

    def test_at_c03(self):
        data = canon(OPEN)
        e = self.bytes_code(b'{"schema":1,' + data[1:], "DUPLICATE_KEY", None, "")
        self.assertIn("schema", e.detail)
        text = data.decode("ascii")
        lot = '"count":80,'
        self.assertIn(lot, text)
        e = self.bytes_code(text.replace(lot, lot + lot, 1).encode(), "DUPLICATE_KEY", None, "")
        self.assertIn("count", e.detail)
        e = self.bytes_code(b'{"a":1,"\\u0061":2}', "DUPLICATE_KEY", None, "")
        self.assertIn("a", e.detail)

    def test_at_c03b(self):
        self.bytes_code(b"[1.5,NaN]", "NONFINITE")
        self.bytes_code(b"[NaN,1.5]", "NONFINITE")
        self.bytes_code(b'{"a":1,"a":1,"b":1.5}', "DUPLICATE_KEY")
        e = self.bytes_code(b'{"a":1.5', "SYNTAX")
        self.assertEqual(e.offset, 8)
        self.bytes_code(b'{"b":[1,12345678901234567890],"a":1,"a":2}', "INTEGER_LIMIT", 8)
        self.bytes_code(b'{"a":0.' + b"1" * 5000 + b"}", "NOT_INTEGER", None)
        self.bytes_code(b'{"a":1e999999}', "NOT_INTEGER", None)

    def test_at_c04_limits(self):
        self.bytes_code(b"[" * 32 + b"]" * 32, "JSON_TYPE", None, "")
        self.decode_code([0] * 99_999, "JSON_TYPE", "")
        self.bytes_code(b"[" * 33 + b"]" * 33, "DEPTH", 32, "")
        nested = []
        for _ in range(32):
            nested = [nested]
        self.decode_code(nested, "DEPTH", "/0" * 32)
        self.decode_code([0] * 100_000, "NODE_LIMIT", "/99999")
        self.bytes_code(json.dumps([0] * 100_000).encode(), "NODE_LIMIT", None, "/99999")
        for value, code in ((2 ** 63 - 1, "KEYS"), (-(2 ** 63 - 1), "KEYS"),
                            (2 ** 63, "INTEGER_LIMIT"), (-(2 ** 63), "INTEGER_LIMIT"),
                            ("a" * 1024, "KEYS"), ("a" * 1025, "STRING_LIMIT")):
            doc = {"schema": B.SCHEMA, "x": value}
            path = "" if code == "KEYS" else "/x"
            self.decode_code(doc, code, path)
            self.bytes_code(dumps(doc), code, None, path)
        data = canon(OPEN)
        exact = data[:-1] + b" " * (1_048_576 - len(data)) + data[-1:]
        self.assertEqual(len(exact), 1_048_576)
        self.assertEqual(B.canonical_bytes(B.decode_bytes(exact)), data)
        self.bytes_code(exact + b" ", "BYTES_LIMIT", None, "")

    def test_at_c05(self):
        text = canon(OPEN).decode("ascii")
        for spelling in ("4.0", "1.0"):
            bad = text.replace('"event_cursor":0', '"event_cursor":' + spelling)
            self.bytes_code(bad.encode(), "NOT_INTEGER", None, "")
            d = copy.deepcopy(OPEN)
            d["clock"]["event_cursor"] = float(spelling)
            self.decode_code(d, "NOT_INTEGER", "/clock/event_cursor")
        for value in (float("nan"), float("inf"), float("-inf")):
            d = copy.deepcopy(OPEN)
            d["clock"]["event_cursor"] = value
            self.decode_code(d, "NONFINITE", "/clock/event_cursor")

        class F(float):
            pass

        d = copy.deepcopy(OPEN)
        d["clock"]["event_cursor"] = F(1.0)
        self.decode_code(d, "DOMAIN_TYPE", "/clock/event_cursor")
        d = copy.deepcopy(OPEN)
        d["scenario"]["profile"]["packet"]["melee_p0"] = "2/4"
        self.decode_code(d, "NONCANONICAL", "/scenario/profile/packet/melee_p0")
        d = copy.deepcopy(OPEN)
        d["formations"][0], d["formations"][1] = d["formations"][1], d["formations"][0]
        e = self.decode_code(d, "CLAUSE")
        self.assertIn("F01", [v.clause for v in e.violations])
        d = copy.deepcopy(OPEN)
        d["personnel"][0], d["personnel"][1] = d["personnel"][1], d["personnel"][0]
        self.decode_code(d, "NONCANONICAL", "/personnel")

    def test_at_c06(self):
        e = self.bytes_code(b'{"a":"\xc3\x28"}', "UTF8", 6, "")
        self.assertEqual(e.offset, 6)
        self.bytes_code(canon(OPEN)[:100], "SYNTAX")
        self.bytes_code(b"NaN", "NONFINITE")
        self.bytes_code(b'{"x":[12345678901234567890]}', "INTEGER_LIMIT", 6)
        doc = {"schema": B.SCHEMA, "x": "\ud800"}
        self.bytes_code(b'{"schema":"imperium.battle-state/1","x":"\\ud800"}', "SURROGATE", None, "/x")
        self.decode_code(doc, "SURROGATE", "/x")
        self.bytes_code(b'{"schema":"imperium.battle-state/1","\\udc00":1}', "SURROGATE", None, "")
        self.bytes_code(b'{"schema":"imperium.battle-state/1","x":"\\ud83d\\ude00"}', "KEYS", None, "")
        cyclic = []
        cyclic.append(cyclic)
        self.decode_code(cyclic, "CYCLE", "/0")

    def test_at_c07(self):
        calls = []

        class Sentinel:
            def __getattribute__(self, name):
                calls.append(name)
                raise RuntimeError(name)

            def __eq__(self, other):
                raise RuntimeError("eq")

            def __hash__(self):
                raise RuntimeError("hash")

        class D(dict):
            pass

        class I(int):
            pass

        class Fl(float):
            pass

        for value in ((1, 2), {1, 2}, D(), I(3), Fl(1.5), Sentinel()):
            d = copy.deepcopy(OPEN)
            d["clock"]["event_cursor"] = value
            e = self.decode_code(d, "DOMAIN_TYPE", "/clock/event_cursor")
            self.assertEqual(e.detail, "unsupported input type")
        self.assertEqual(calls, [])

    def test_at_c07b(self):
        class Meta(type):
            def __getattribute__(cls, name):
                if name in ("__qualname__", "__name__"):
                    raise RuntimeError(name)
                return super().__getattribute__(name)

        class Odd(metaclass=Meta):
            pass

        d = copy.deepcopy(OPEN)
        d["clock"]["event_cursor"] = Odd()
        self.decode_code(d, "DOMAIN_TYPE", "/clock/event_cursor")

        class Key:
            armed = False

            def __hash__(self):
                if Key.armed:
                    raise RuntimeError("hash")
                return 7

            def __eq__(self, other):
                if Key.armed:
                    raise RuntimeError("eq")
                return self is other

            def __lt__(self, other):
                raise RuntimeError("lt")

        d = copy.deepcopy(OPEN)
        d["clock"][Key()] = 1
        Key.armed = True
        try:
            self.decode_code(d, "DOMAIN_TYPE", "/clock")
        finally:
            Key.armed = False

    def test_at_c08(self):
        for exc in (RuntimeError("boom"), ValueError("unrelated")):
            with mock.patch.object(invariants, "validate_fields", side_effect=exc):
                with self.assertRaises(type(exc)) as cm:
                    B.decode_state(copy.deepcopy(OPEN))
                self.assertIs(cm.exception, exc)
                with self.assertRaises(type(exc)):
                    B.decode_bytes(canon(OPEN))
        d = copy.deepcopy(OPEN)
        d["formations"][3]["facing"] = 7
        e = self.decode_code(d, "CLAUSE", "/formations/3/facing")
        self.assertEqual(len(e.violations), 1)
        d = as_adversarial(OPEN, "C08")
        d["formations"][2]["cell"] = list(d["formations"][3]["cell"])
        e = self.decode_code(d, "CLAUSE")
        self.assertEqual(list(e.violations), sorted(e.violations, key=lambda v: (v.clause, v.path)))
        self.assertEqual(e.path, e.violations[0].path)
        self.assertGreaterEqual(len(e.violations), 1)

    def test_at_c09_c10(self):
        docs = [opening_document(v.name, o.name) for v in B.Variant for o in B.Orientation]
        docs += [B.encode_state(B.f01_supplied(i)) for i in B.supplied_ids()]
        docs += [a1(), collapse(), capitulation()]
        for d in docs:
            s = build(d)
            once = B.encode_state(s)
            self.assertEqual(B.canonical_bytes(B.decode_state(once)), canon(once))
            with self.assertRaises(dataclasses.FrozenInstanceError):
                s.clock = None
            with self.assertRaises(dataclasses.FrozenInstanceError):
                s.formations[0].facing = 1
            with self.assertRaises(dataclasses.FrozenInstanceError):
                s.scenario.profile.effort = 4

    def test_at_c12(self):
        d = copy.deepcopy(OPEN)
        del d["schema"]
        self.decode_code(d, "SCHEMA")
        for value in ("imperium.battle-state/2", 1):
            d = copy.deepcopy(OPEN)
            d["schema"] = value
            self.decode_code(d, "SCHEMA")
        self.decode_code([], "JSON_TYPE", "")

    def test_at_c13(self):
        d = copy.deepcopy(OPEN)
        d["personnel"][0]["place"] = {"kind": "Elsewhere", "formation": "S0.C1", "extra": 1}
        self.decode_code(d, "UNION_TAG", "/personnel/0/place")
        d = copy.deepcopy(OPEN)
        d["personnel"][0]["place"] = {"kind": "OnCell", "formation": "S0.C1"}
        self.decode_code(d, "KEYS", "/personnel/0/place")
        d = copy.deepcopy(OPEN)
        d["sides"][0]["posture"] = "RETREATING"
        self.decode_code(d, "TOKEN", "/sides/0/posture")
        d = a1()
        d["ledger"]["formations"][0]["response"] = {"kind": "DEFENSIVE_CHARGE", "target": "S1.H1"}
        self.decode_code(d, "TOKEN", "/ledger/formations/0/response/kind")
        d = copy.deepcopy(OPEN)
        d["scenario"]["roster"][0]["formation"] = "S0 H1"
        self.decode_code(d, "TOKEN", "/scenario/roster/0/formation")
        d = copy.deepcopy(OPEN)
        lot = d["personnel"][0]
        del lot["origin"]
        lot["zzz"] = 1
        lot["count"] = 0
        e = self.decode_code(d, "KEYS", "/personnel/0")
        self.assertIn("origin", e.detail)

    def test_at_c14(self):
        for value in ("[" * 40, 'a"[b', "a\\b"):
            d = copy.deepcopy(OPEN)
            d["extra"] = value
            e = self.bytes_code(canon(d), "KEYS", None, "")
            self.assertIn("extra", e.detail)

    def test_at_c15(self):
        text = json.dumps(OPEN, indent=3, sort_keys=False)
        text = text.replace('"S0.H1"', '"\\u0053\\u0030.H1"')
        reordered = json.dumps(dict(reversed(list(json.loads(text).items()))), indent=1)
        for data in (text, reordered):
            self.assertEqual(B.canonical_bytes(B.decode_bytes(data.encode())), canon(OPEN))

    def test_at_c16(self):
        s = build(OPEN)
        self.assertEqual(B.validate_state(object()), (B.Violation("V00", "", "not a BattleState"),))
        cases = ((lambda: B.available(object(), B.FormationId("S0.H1")), "V00", "state"),
                 (lambda: B.available(s, "S0.H1"), "T07", "fid"),
                 (lambda: B.available(s, B.GroupId("S0.G1")), "T07", "fid"))
        for call, clause, path in cases:
            with self.assertRaises(B.InvalidValue) as cm:
                call()
            self.assertEqual((cm.exception.clause, cm.exception.path), (clause, path))
        with self.assertRaises(B.UnknownId):
            B.available(s, B.FormationId("S9.X1"))

    def test_at_c17_c18(self):
        s = build(OPEN)
        out = B.encode_state(s)
        out["formations"][0]["facing"] = 9
        out["clock"]["event_cursor"] = 5
        self.assertEqual(B.encode_state(s), OPEN)
        d = copy.deepcopy(OPEN)
        s = B.decode_state(d)
        d["formations"][0]["cell"][0] = 9
        self.assertEqual(B.encode_state(s), OPEN)
        d = as_adversarial(OPEN, "C18")
        shared = [5, 4]
        d["formations"][f_index(d, "S0.H1")]["cell"] = shared
        d["phase"] = {"kind": "Opening"}
        d["scenario"]["board"]["objective"] = shared
        s = B.decode_state(d)
        shared[0] = 1
        self.assertEqual(s.formations[f_index(d, "S0.H1")].cell, B.Hex(5, 4))
        self.assertEqual(s.scenario.board.objective, B.Hex(5, 4))

    def test_at_c19(self):
        d = copy.deepcopy(OPEN)
        self.assertEqual(d["scenario"]["profile"]["packet"]["missile_pressure"][0], "3/25")
        self.accept(as_adversarial(d, "C19"))
        for spelling in ("-0/1", "1/0", "01/2", "1/-2"):
            d = copy.deepcopy(OPEN)
            d["scenario"]["profile"]["packet"]["melee_p0"] = spelling
            self.decode_code(d, "NONCANONICAL", "/scenario/profile/packet/melee_p0")
        d = as_adversarial(OPEN, "C19B")
        d["scenario"]["profile"]["packet"]["melee_p0"] = "1/9"
        self.reject(d, "P01")
        with self.assertRaises(B.InvalidValue) as cm:
            B.PacketParameters(**{**_packet_kwargs(), "melee_p0": 0.1})
        self.assertEqual(cm.exception.clause, "T06")
        self.assertIsInstance(build(OPEN).scenario.profile.packet.melee_p0, Fraction)

    def test_at_c20(self):
        d = copy.deepcopy(OPEN)
        d["clock"]["a/b~c"] = 1
        e = self.decode_code(d, "KEYS", "/clock")
        self.assertIn("a/b~c", e.detail)
        d = copy.deepcopy(OPEN)
        d["clock"]["a/b"] = "x" * 1025
        self.decode_code(d, "STRING_LIMIT", "/clock/a~1b")
        d = as_adversarial(OPEN, "C20")
        d["formations"][0]["facing"] = 6
        d["formations"][1]["cell"] = list(d["formations"][2]["cell"])
        e = self.decode_code(d, "CLAUSE", "/formations/0/facing")
        self.assertEqual([v.clause for v in e.violations], ["T08"])


def f_index(d, fid):
    return [x["formation"] for x in d["formations"]].index(fid)


def _packet_kwargs():
    p = build(OPEN).scenario.profile.packet
    return {x.name: getattr(p, x.name) for x in dataclasses.fields(p)}



