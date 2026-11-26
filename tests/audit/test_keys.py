"""TA-A01–A07: the BK-1 draw-key registry on EP08-v1 (contract rev 0.3 section 4)."""

import ast
import hashlib
import importlib
import pathlib
import random
import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import check_draw_records
from imperium.randomness import DrawKey, melee_stage
from tests.audit.support import allowed_seed, ep08, fid, oracles, sha

D = importlib.import_module("imperium.battle.engine.draws")
ROOT = pathlib.Path(__file__).resolve().parents[2]
ORACLE_SHA = "8a9bbde3653d0572de6def39b1a3ed94bd128d278a4d179bb2b772901b983b8e"
CHANNELS = [c.value for c in E.Channel]
S0_IDS = ["S0.C1", "S0.H1", "S0.H2", "S0.H3", "S0.H4", "S0.H5", "S0.H6", "S0.L1"]
S1_IDS = [t.replace("S0", "S1") for t in S0_IDS]


def key_ids():
    """The 4.4 reserved packet-id domain, generated test-side."""
    for rnd in range(1, 13):
        for side in ("S0", "S1"):
            for o in range(1, 5):
                for kind in ("MELEE", "MISSILE"):
                    for actor in S0_IDS + S1_IDS:
                        targets = S1_IDS if actor.startswith("S0") else S0_IDS
                        for target in targets:
                            for source in S0_IDS + S1_IDS + ["-"]:
                                yield f"r{rnd}:{side}.o{o}:{kind}:{actor}:{target}:{source}"


def p2_ids():
    for k in ("INITIAL_CHECK", "OPEN_ROUND", "TERMINAL"):
        yield f"r0:IN:{k}"
    for rnd in range(1, 13):
        for k in ("CLOSURE_DISPLACEMENT", "CLOSURE_CHECK", "RECOVERY", "ADVANCE", "END_CHECK",
                  "OPEN_ROUND", "TERMINAL"):
            yield f"r{rnd}:CL:{k}"
        for side in ("S0", "S1"):
            for o in range(1, 5):
                for k in ("ROOT", "IMMEDIATE_CHECK", "TERMINAL"):
                    yield f"r{rnd}:{side}.o{o}:{k}"


class Vectors(unittest.TestCase):

    def test_a01_bound_oracle_vectors(self):
        with open(ROOT / "tests" / "audit" / "reference_oracles.json", "rb") as fh:
            self.assertEqual(sha(fh.read()), ORACLE_SHA)
        o = oracles()
        self.assertEqual(len(o["bk1_vectors"]), 7)
        self.assertEqual(len(o["legacy_vectors"]), 4)
        for seed, pair, rep, stage, channel, index, n in o["bk1_vectors"]:
            with self.subTest(stage=stage, channel=channel):
                self.assertEqual(E.draw_numerator(E.RunKey(seed, rep), pair, stage,
                                                  E.Channel(channel), index), n)
                self.assertEqual(ep08(seed, pair, rep, stage, channel, index), n)
        for seed, pair, rep, stage, channel, index, n in o["legacy_vectors"]:
            with self.subTest(legacy=stage):
                self.assertEqual(D.ep08_numerator(seed, pair, rep, stage, channel, index), n)
                self.assertEqual(DrawKey(seed, pair, rep, stage, channel, index).integer(), n)
                with self.assertRaises(B.InvalidValue):
                    E.draw_numerator(E.RunKey(seed, rep), pair, stage, E.Channel(channel), index)

    def test_a02_differential(self):
        rng = random.Random(2)
        ids = list(key_ids())
        for _ in range(10 ** 4):  # A02 key count (not a seed)
            seed, rep = allowed_seed(rng.randrange(1000)), rng.randrange(1000)
            pair = rng.choice(D.PAIRS)
            stage = rng.choice(ids)
            channel = rng.choice(CHANNELS)
            index = rng.randrange(64)
            n = E.draw_numerator(E.RunKey(seed, rep), pair, stage, E.Channel(channel), index)
            self.assertEqual(n, DrawKey(seed, pair, rep, stage, channel, index).integer())
            self.assertEqual(n, ep08(seed, pair, rep, stage, channel, index))
            check_draw_records((seed, rep), pair, stage, ((channel, index, n),))


class Grammar(unittest.TestCase):

    def test_a03_round_trip_and_matrix(self):
        count = 0
        for text in list(key_ids()) + list(p2_ids()):
            k = E.parse_stage_id(text)
            self.assertEqual(E.format_stage_id(k), text)
            self.assertIsInstance(B.EventRef(text), B.EventRef)
            count += 1
        self.assertEqual(count, 417792 + 3 + 12 * 7 + 12 * 8 * 3)

    def test_a03_negatives(self):
        bad = [
            "r00:IN:INITIAL_CHECK", "r1:IN:INITIAL_CHECK", "r0:CL:ADVANCE", "r13:CL:ADVANCE",
            "r1:S0.o0:ROOT", "r1:S0.o5:ROOT", "r1:S0.o01:ROOT", "r1:S2.o1:ROOT", "r1:IN:ROOT",
            "r1:CL:ROOT", "r1:S0.o1:ADVANCE", "r1:S0.o1:FOO", "r1/S0.o1/ROOT",
            "r1:S0.o1:ROOT:S0.H1:S1.H1:-", "r1:S0.o1:MELEE", "r1:S0.o1:MELEE:S0.H1:S0.H2:-",
            "r1:S0.o1:MELEE:S0.H1:S1.X9:-", "r1:S0.o1:MELEE:S0.H1:S1.H1:S9.H1",
            "r0:IN:MELEE:S0.H1:S1.H1:-", "r1:CL:MISSILE:S0.H1:S1.H1:-", "r1:S0.o1:melee:S0.H1:S1.H1:-",
            "r1:S0.o1:MELEE:S0.H1:S1.H1:S0.H1:x", "r1:S0.o1:ROOT ", "", "r1:S0.o1:ROOTé",
            "r1:S0.o1:MELEE:S0.H1:S1.H1:" + "S" * 40,
        ]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.parse_stage_id(text)
                self.assertEqual(cm.exception.violations[0].clause if hasattr(cm.exception, "violations")
                                 else cm.exception.args[0], "T16")
        with self.assertRaises(B.InvalidValue) as cm:
            E.parse_stage_id(b"r0:IN:INITIAL_CHECK")
        self.assertEqual(cm.exception.args[0], "T15")
        with self.assertRaises(B.InvalidValue) as cm:
            E.format_stage_id("r0:IN:INITIAL_CHECK")
        self.assertEqual(cm.exception.args[0], "T15")

    def test_a03_stagekey_diagnostics(self):
        ok = dict(round=1, root="P", side=B.Side.S0, ordinal=1, kind="ROOT", actor=None,
                  target=None, source=None)
        cases = [
            (dict(round=True), "T15", "round"), (dict(root=1), "T15", "root"),
            (dict(side="S0"), "T15", "side"), (dict(ordinal=1.0), "T15", "ordinal"),
            (dict(actor="S0.H1"), "T15", "actor"), (dict(round=13), "T10", "round"),
            (dict(ordinal=5), "T10", "ordinal"), (dict(root="XX"), "T16", "stage_id"),
            (dict(kind="ADVANCE"), "T16", "stage_id"),
            (dict(kind="MELEE", actor=fid("S0.H1"), target=fid("S0.H2")), "T16", "stage_id"),
            (dict(actor=fid("S0.H1")), "T16", "stage_id"),
        ]
        for change, code, path in cases:
            with self.subTest(change=change):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.StageKey(**{**ok, **change})
                self.assertEqual(cm.exception.args[:2], (code, path))


class Domain(unittest.TestCase):

    def test_a04_census(self):
        ids = list(key_ids())
        self.assertEqual(len(set(ids)), 417792)
        payloads = set()
        outputs = {}
        equal_pairs = 0
        for stage in ids:
            for channel in CHANNELS:
                for index in (0, 1):
                    p = (stage, channel, index)
                    payloads.add(p)
                    n = D.ep08_numerator(0, "F01-v1-open", 0, stage, channel, index)
                    if n in outputs:
                        equal_pairs += 1
                    outputs[n] = p
        self.assertEqual(len(payloads), 5849088)
        # Equal outputs from distinct payloads are valid and reported, not errors.
        print(f"\nA04 census: 5,849,088 payloads, {equal_pairs} equal-output pairs")

    def test_a04_equal_output_is_not_a_duplicate(self):
        stage = "r1:S0.o1:MELEE:S0.H1:S1.H1:-"
        with mock.patch.object(D, "ep08_numerator", return_value=123):
            a = E.draw_numerator(E.RunKey(0, 0), "F01-v1-open", stage, E.Channel.injury, 0)
            b = E.draw_numerator(E.RunKey(0, 0), "F01-v1-open", stage, E.Channel.fatal, 0)
        self.assertEqual(a, b)
        records = (E.DrawRecord(E.Channel.fatal, 0, a), E.DrawRecord(E.Channel.injury, 0, b))
        self.assertEqual(len(set((r.channel, r.index) for r in records)), 2)

    def test_a05_types_and_ranges(self):
        stage = "r1:S0.o1:MELEE:S0.H1:S1.H1:-"
        for index in (2, 3, 63):
            E.draw_numerator(E.RunKey(0, 0), "F01-v1-open", stage, E.Channel.policy, index)
        cases = [
            ((("x", 0), "F01-v1-open", stage, E.Channel.injury, 0), "T15", "run"),
            ((E.RunKey(0, 0), 1, stage, E.Channel.injury, 0), "T15", "pair"),
            ((E.RunKey(0, 0), "F01-v1-open", 1, E.Channel.injury, 0), "T15", "stage_id"),
            ((E.RunKey(0, 0), "F01-v1-open", stage, "injury", 0), "T15", "channel"),
            ((E.RunKey(0, 0), "F01-v1-open", stage, E.Channel.injury, True), "T15", "index"),
            ((E.RunKey(0, 0), "F01-v1-nope", stage, E.Channel.injury, 0), "T16", "pair"),
            ((E.RunKey(0, 0), "F01-v1-open", "r1:S0.o1:ROOT", E.Channel.injury, 0), "T16", "stage_id"),
            ((E.RunKey(0, 0), "F01-v1-open", stage, E.Channel.injury, 64), "T10", "index"),
        ]
        for args, code, path in cases:
            with self.subTest(path=path, code=code):
                with mock.patch.object(D.hashlib, "sha256", side_effect=AssertionError("hashed")):
                    with self.assertRaises(B.InvalidValue) as cm:
                        E.draw_numerator(*args)
                self.assertEqual(cm.exception.args[:2], (code, path))
        for kw, code in ((dict(seed=True, replicate=0), "T15"), (dict(seed=-1, replicate=0), "T10"),
                         (dict(seed=0, replicate=2 ** 63), "T10")):
            with self.assertRaises(B.InvalidValue) as cm:
                E.RunKey(**kw)
            self.assertEqual(cm.exception.args[0], code)
        for args, code in (((True, "p", 0, "s", "c", 0), "T15"), ((0, "p", -1, "s", "c", 0), "T10"),
                           ((0, "pé", 0, "s", "c", 0), "T16")):
            with self.assertRaises(B.InvalidValue) as cm:
                D.ep08_numerator(*args)
            self.assertEqual(cm.exception.args[0], code)
        self.assertEqual([c.value for c in E.Channel], [c.name for c in E.Channel])
        self.assertEqual(len(E.Channel), 7)

    def test_a05_fixture_pair(self):
        import dataclasses
        expected = {"F01-v1-open-standard": "F01-v1-open", "F01-v1-open-mirrored": "F01-v1-open",
                    "F01-v1-rough-standard": "F01-v1-rough", "F01-v1-rough-mirrored": "F01-v1-rough",
                    "F01-v1-barrier-standard": "F01-v1-barrier",
                    "F01-v1-barrier-mirrored": "F01-v1-barrier",
                    "F01-v1-open-standard-mount-shortfall": "F01-v1-open-standard-mount-shortfall",
                    "F01-v1-defensive-mutual-capitulation": "F01-v1-defensive-mutual-capitulation"}
        for d in B.DESCRIPTORS:
            self.assertEqual(E.fixture_pair(d), expected[d.fixture_id.token])
            self.assertEqual(E.fixture_pair(dataclasses.replace(d)), expected[d.fixture_id.token])
        changed = dataclasses.replace(B.DESCRIPTORS[0], profile_id="other")
        with self.assertRaises(B.InvalidValue) as cm:
            E.fixture_pair(changed)
        self.assertEqual(cm.exception.args[:2], ("T16", "descriptor.fixture_id"))
        with self.assertRaises(B.InvalidValue) as cm:
            E.fixture_pair("F01-v1-open-standard")
        self.assertEqual(cm.exception.args[:2], ("T15", "descriptor"))

    def test_a06_legacy_disjoint(self):
        legacy = {"A-to-B", "B-to-A"}
        for r in range(1, 13):
            for s in (0, 1):
                for o in range(1, 5):
                    for a in range(12):
                        for t in range(12):
                            legacy.add(melee_stage(r, s, o, a, t, a))
        for text in legacy:
            with self.assertRaises(B.InvalidValue):
                E.parse_stage_id(text)


class CallGuard(unittest.TestCase):

    def test_a07_no_gameplay_draw_calls(self):
        engine = ROOT / "imperium" / "battle" / "engine"
        for path in engine.glob("*.py"):
            if path.stem in ("draws", "__init__"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, ("draw_numerator", "ep08_numerator"), path.stem)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("draw_numerator", "ep08_numerator"), path.stem)


if __name__ == "__main__":
    unittest.main()
