"""TA-G01–G04: production P3 is draw-free; the isolated draw-record validator
(contract rev 0.3 section 10, ER03).

The structural draw-path cases below never build an audit-wire event.
"""

import importlib
import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import DrawRecordError, check_draw_records, verify
from tests.audit.support import (
    CARRIERS, RUN0, S1, WALK_SEEDS, allowed_seed, ep08, journals, session, trees, walk,
)
from tests.audit.test_keys import p2_ids
from tests.engine.test_boundary import VARIANTS, closing
from tests.support.battle_builder import build

D = importlib.import_module("imperium.battle.engine.draws")
rules = importlib.import_module("imperium.battle.audit.rules")
drawcheck = importlib.import_module("imperium.battle.audit.drawcheck")
STAGE = "r1:S0.o1:MELEE:S0.H1:S1.H1:-"
PAIR = "F01-v1-open"


class Counter:
    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def __call__(self, *a, **k):
        self.calls += 1
        return self.fn(*a, **k)


class NoDraws(unittest.TestCase):

    def test_g01_g02_counters(self):
        counters = {name: Counter(getattr(mod, name)) for mod, name in
                    ((D, "ep08_numerator"), (D, "draw_numerator"), (rules, "ep08"))}
        with mock.patch.object(D, "ep08_numerator", counters["ep08_numerator"]), \
                mock.patch.object(D, "draw_numerator", counters["draw_numerator"]), \
                mock.patch.object(E, "draw_numerator", counters["draw_numerator"]), \
                mock.patch.object(rules, "ep08", counters["ep08"]):
            exports = []
            for name in CARRIERS:
                s = session(name)
                E.replay(s.export_audit())
                s.submit(E.OpenBattle())  # rejected in every carrier after genesis/opening
                exports += [s.export_audit(), s.export_audit(seal=False)]
            for seed in WALK_SEEDS:
                s = walk(seed, interleave=True)[0]
                exports.append(s.export_audit())
                for r in s._records:
                    for e in r.events:
                        self.assertEqual(e.draws, ())
            for name, (kw, stage, obligations) in VARIANTS.items():
                r = E.resolve(build(closing("G-" + name, **kw)), E.PassOrder(S1))
                self.assertIs(type(r), E.Deferred)
            for data in exports:
                r = verify(data, require_sealed=False)
                self.assertEqual(r.draws, 0)
                for t in trees(data)[1:]:
                    if t["kind"] == "trailer":
                        self.assertEqual(t["draws"], 0)
                    else:
                        self.assertTrue(all(e["draws"] == [] for e in t["events"]))
        self.assertEqual({k: c.calls for k, c in counters.items()},
                         {"ep08_numerator": 0, "draw_numerator": 0, "ep08": 0})

    def test_g03_p2_kind_rejected_before_hashing(self):
        with mock.patch.object(D.hashlib, "sha256", side_effect=AssertionError("hashed")):
            for stage in p2_ids():
                with self.assertRaises(B.InvalidValue) as cm:
                    E.draw_numerator(RUN0, PAIR, stage, E.Channel.injury, 0)
                self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "stage_id"))


class Records(unittest.TestCase):

    def good(self, seed=0, rep=0, channel="injury", index=0):
        return (channel, index, ep08(allowed_seed(seed), PAIR, rep, STAGE, channel, index))

    def code(self, run, pair, stage, records):
        with mock.patch.object(drawcheck.rules, "ep08", wraps=rules.ep08) as hashed:
            with self.assertRaises(DrawRecordError) as cm:
                check_draw_records(run, pair, stage, records)
        return cm.exception.code, cm.exception.path, hashed.call_count

    def test_g04_valid_witnesses(self):
        for channel in ("cohesion", "couple", "fatal", "injury", "latent", "morale", "policy"):
            for index in (0, 1, 63):
                self.assertIsNone(check_draw_records((0, 0), PAIR, STAGE,
                                                     (self.good(channel=channel, index=index),)))
        self.assertIsNone(check_draw_records((7, 2), "F01-v1-rough", "r12:S1.o4:MISSILE:S1.L1:S0.C1:S0.H6",
                                             (("fatal", 0, ep08(7, "F01-v1-rough", 2,
                                               "r12:S1.o4:MISSILE:S1.L1:S0.C1:S0.H6", "fatal", 0)),
                                              ("fatal", 1, ep08(7, "F01-v1-rough", 2,
                                               "r12:S1.o4:MISSILE:S1.L1:S0.C1:S0.H6", "fatal", 1)))))

    def test_g04_first_fault_order(self):
        g = self.good()
        n = g[2]
        cases = [
            # DR07 beats everything else
            ((None, 1, 2, [g]), ("DR07", "/records", 0)),
            (((0, 0), PAIR, STAGE, ()), ("DR07", "/records", 0)),
            ((None, 1, 2, (g, ("injury", 1))), ("DR07", "/records/1", 0)),
            ((None, 1, 2, (["injury", 0, n],)), ("DR07", "/records/0", 0)),
            # DR03 run
            ((None, 1, 2, (g,)), ("DR03", "/run", 0)),
            (((True, 0), 1, 2, (g,)), ("DR03", "/run", 0)),
            (((0, -1), 1, 2, (g,)), ("DR03", "/run", 0)),
            (((0, 2 ** 63), PAIR, STAGE, (g,)), ("DR03", "/run", 0)),
            (([0, 0], PAIR, STAGE, (g,)), ("DR03", "/run", 0)),
            (((0, 0, 0), PAIR, STAGE, (g,)), ("DR03", "/run", 0)),
            # DR01 pair
            (((0, 0), 1, 2, (g,)), ("DR01", "/pair", 0)),
            (((0, 0), "F01-v1-open-standard", 2, (g,)), ("DR01", "/pair", 0)),
            # DR02 stage id
            (((0, 0), PAIR, 2, (("x", 0, n),)), ("DR02", "/stage_id", 0)),
            (((0, 0), PAIR, "r1:S0.o1:ROOT", (g,)), ("DR02", "/stage_id", 0)),
            (((0, 0), PAIR, "r1/s0/o1/a0/t0/src0", (g,)), ("DR02", "/stage_id", 0)),
            # DR01 channel / index, record order, channel before index
            (((0, 0), PAIR, STAGE, (("Injury", 99, n),)), ("DR01", "/records/0/0", 0)),
            (((0, 0), PAIR, STAGE, ((E.Channel.injury, 0, n),)), ("DR01", "/records/0/0", 0)),
            (((0, 0), PAIR, STAGE, (("injury", True, n),)), ("DR01", "/records/0/1", 0)),
            (((0, 0), PAIR, STAGE, (("injury", 64, n),)), ("DR01", "/records/0/1", 0)),
            (((0, 0), PAIR, STAGE, (g, ("injury", -1, "x"))), ("DR01", "/records/1/1", 0)),
            # DR04 ordering, including duplicates with equal numerators
            (((0, 0), PAIR, STAGE, (g, g)), ("DR04", "/records/1", 0)),
            (((0, 0), PAIR, STAGE, (self.good(index=1), g)), ("DR04", "/records/1", 0)),
            (((0, 0), PAIR, STAGE, (g, self.good(channel="fatal"))), ("DR04", "/records/1", 0)),
            (((0, 0), PAIR, STAGE, (self.good(index=10), ("injury", 2, "x"))),
             ("DR04", "/records/1", 0)),
            # DR05 numerator domain
            (((0, 0), PAIR, STAGE, (("injury", 0, True),)), ("DR05", "/records/0/2", 0)),
            (((0, 0), PAIR, STAGE, (("injury", 0, 2 ** 53),)), ("DR05", "/records/0/2", 0)),
            (((0, 0), PAIR, STAGE, (("injury", 0, -1),)), ("DR05", "/records/0/2", 0)),
            (((0, 0), PAIR, STAGE, (g, ("injury", 1, 1.0))), ("DR05", "/records/1/2", 0)),
            # DR06 recomputation
            (((0, 0), PAIR, STAGE, (("injury", 0, n ^ 1),)), ("DR06", "/records/0/2", 1)),
            (((0, 0), PAIR, STAGE, (g, ("injury", 1, n))), ("DR06", "/records/1/2", 2)),
        ]
        for args, want in cases:
            with self.subTest(args=args, want=want[:2]):
                self.assertEqual(self.code(*args), want)

    def test_g04_independent_of_engine_types(self):
        import ast
        with open(drawcheck.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        used |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        used |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(used & {"RunKey", "Channel", "StageKey", "DrawRecord", "engine",
                                 "draws", "draw_numerator", "ep08_numerator"}, used)
        with self.assertRaises(DrawRecordError) as cm:
            check_draw_records(E.RunKey(0, 0), PAIR, STAGE, (self.good(),))
        self.assertEqual(cm.exception.code, "DR03")


if __name__ == "__main__":
    unittest.main()
