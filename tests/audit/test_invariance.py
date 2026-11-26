"""TA-F01–F06: invariance of the audit journal (contract rev 0.3 section 14 F, ER05).

F06(a), the P2 terminal/custody sibling-order check, is retained unchanged
as ``tests.engine.test_cross.Determinism.test_x05_hash_seeds_and_import_orders``.
"""

import importlib
import json
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import verify
from tests.audit.support import (
    CARRIERS, RUN0, S0, S1, WALK_SEEDS, cjson, journals, session, sha, trees, walk,
)
from tests.audit.test_events import EXPECTED_IDS

ROOT = pathlib.Path(__file__).resolve().parents[2]
events_module = importlib.import_module("imperium.battle.engine.events")
rules = importlib.import_module("imperium.battle.audit.rules")

HASH_SCRIPT = r"""
import sys
sys.path.insert(0, ".")
from tests.audit.support import CARRIERS, journals, sha
for name in sorted(CARRIERS):
    sealed, prefix = journals(name)
    print(name, sha(sealed), sha(prefix))
"""

POISON = r"""
import sys
class Poison:
    def find_spec(self, name, path=None, target=None):
        if name == "imperium.battle.engine" or name.startswith("imperium.battle.engine."):
            raise ImportError("engine loading is poisoned: " + name)
        return None
sys.meta_path.insert(0, Poison())
"""

ORDER_SCRIPT = r"""
import json, sys
sys.path.insert(0, ".")
mode, path = sys.argv[1:]
if mode == "audit-first":
""" + "\n".join("    " + line for line in POISON.strip().splitlines()) + r"""
    from imperium.battle.audit import verify
else:
    import imperium.battle.engine as E
    from imperium.battle.audit import verify
before = sorted(k for k in sys.modules if k.startswith("imperium"))
reports = []
for data in json.load(open(path))["journals"]:
    r = verify(bytes.fromhex(data))
    reports.append([r.fixture, r.pair, list(r.run) if r.run else None, r.sealed, r.roots,
                    r.cursor, r.final, r.terminal, [list(s) for s in r.stages], r.draws,
                    r.final_chain])
loaded = sorted(k for k in sys.modules if k.startswith("imperium"))
print(json.dumps({"reports": reports, "before": before, "loaded": loaded}))
"""


def clean_env(**extra):
    env = {"PATH": os.environ.get("PATH", "")}
    env.update(extra)
    return env


def shuffled(tree, rng):
    """The same JSON value with randomly permuted dict insertion order."""
    if type(tree) is dict:
        keys = list(tree)
        rng.shuffle(keys)
        return {k: shuffled(tree[k], rng) for k in keys}
    if type(tree) is list:
        return [shuffled(v, rng) for v in tree]
    return tree


class Invariance(unittest.TestCase):

    def test_f01_hash_seeds(self):
        expected = "\n".join(f"{n} {sha(journals(n)[0])} {sha(journals(n)[1])}"
                             for n in sorted(CARRIERS))
        for seed in ("0", "1", "4242", "random"):
            with self.subTest(seed=seed):
                out = subprocess.run([sys.executable, "-s", "-c", HASH_SCRIPT], cwd=ROOT,
                                     env=clean_env(PYTHONHASHSEED=seed), capture_output=True,
                                     text=True, check=True).stdout
                self.assertEqual(out.strip(), expected)

    def test_f02_rejections_and_mid_run_exports(self):
        for seed in WALK_SEEDS[::5]:
            noisy, commands, rejections = walk(seed, interleave=True)
            self.assertTrue(rejections, seed)
            self.assertTrue(all(t is E.Rejected and got is want for _, t, got, want in rejections),
                            seed)
            fixture = B.FixtureId(trees(noisy.export_audit())[0]["fixture"])
            clean = E.BattleSession.open(fixture, RUN0)
            for c in commands:
                self.assertIs(type(clean.submit(c)), E.Accepted)
            self.assertEqual(noisy.export_audit(), clean.export_audit(), seed)
            self.assertEqual(noisy.export_audit(seal=False), clean.export_audit(seal=False), seed)
        fixture, commands = CARRIERS["G4"]
        s = E.BattleSession.open(fixture, RUN0)
        for c in commands():
            s.export_audit()
            s.export_audit(seal=False)
            if type(s.state.phase) is not B.Opening:
                self.assertIs(type(s.submit(E.OpenBattle())), E.Rejected)
            self.assertIs(type(s.submit(c)), E.Accepted)
        self.assertEqual(s.export_audit(), journals("G4")[0])

    def test_f02_bare_resolve(self):
        state = E.BattleSession.open(CARRIERS["G1"][0]).state
        for c in CARRIERS["G1"][1]():
            a, b = E.resolve(state, c), E.resolve(state, c)
            self.assertEqual(a, b)
            self.assertEqual(a.record, b.record)
            self.assertEqual(a.snapshots, b.snapshots)
            self.assertEqual([cjson(x.document()) for x in a.snapshots],
                             [cjson(x.document()) for x in b.snapshots])
            state = a.accepted.state

    def test_f03_permutation(self):
        rng = random.Random(3)
        s = session("G1")
        docs = [json.loads(B.canonical_bytes(s.state))]
        for seed in WALK_SEEDS[:20]:
            docs.append(json.loads(B.canonical_bytes(walk(seed)[0].state)))
        for a in docs:
            for b in docs[:6]:
                ref_e = [(p, cjson(o), cjson(n)) for p, o, n in events_module.diff(a, b)]
                ref_a = [(tuple(p), cjson(o), cjson(n)) for p, o, n in rules.canonical_diff(a, b)]
                for _ in range(3):
                    pa, pb = shuffled(a, rng), shuffled(b, rng)
                    self.assertEqual([(p, cjson(o), cjson(n)) for p, o, n in
                                      events_module.diff(pa, pb)], ref_e)
                    self.assertEqual([(tuple(p), cjson(o), cjson(n)) for p, o, n in
                                      rules.canonical_diff(pa, pb)], ref_a)
                self.assertEqual([tuple(p) for p, _, _ in ref_e], [p for p, _, _ in ref_a])
        # Type-sensitive comparison: 0/false and 1/true are different values.
        for x, y in ((0, False), (1, True), (1, 1.0)):
            self.assertEqual(len(events_module.diff({"a": x}, {"a": y})), 1)
        self.assertEqual(len(rules.canonical_diff({"a": 0}, {"a": False})), 1)
        self.assertEqual(len(rules.canonical_diff({"a": 1}, {"a": True})), 1)

    def test_f04_mirror(self):
        commands = [E.OpenBattle(), E.PassOrder(S0), E.PassOrder(S1)]
        for variant in ("open", "rough", "barrier"):
            ids, digests, pairs = [], [], []
            for orientation in ("standard", "mirrored"):
                s = E.BattleSession.open(B.FixtureId(f"F01-v1-{variant}-{orientation}"), RUN0)
                first = s.state.scenario.first_side if hasattr(s.state.scenario, "first_side") \
                    else None
                seq = commands if first in (None, S0) else [E.OpenBattle(), E.PassOrder(S1),
                                                            E.PassOrder(S0)]
                for c in seq:
                    self.assertIs(type(s.submit(c)), E.Accepted)
                ids.append([[e.stage_id for e in r.events] for r in s.records])
                digests.append(B.digest(s.state))
                pairs.append(trees(s.export_audit())[0]["pair"])
            with self.subTest(variant=variant):
                self.assertEqual(pairs[0], pairs[1])
                self.assertEqual(len(ids[0]), len(ids[1]))
                self.assertEqual([len(r) for r in ids[0]], [len(r) for r in ids[1]])
                self.assertNotEqual(digests[0], digests[1])
                stage = "r1:S0.o1:MELEE:S0.H1:S1.H1:-"
                self.assertEqual(
                    E.draw_numerator(RUN0, pairs[0], stage, E.Channel.injury, 0),
                    E.draw_numerator(RUN0, pairs[1], stage, E.Channel.injury, 0))

    def test_f05_frozen_ids(self):
        for name, roots in EXPECTED_IDS.items():
            got = [[e["id"] for e in t["events"]] for t in trees(journals(name)[0])[1:-1]]
            self.assertEqual(got, roots, name)

    def test_f06_module_load_orders(self):
        payload = {"journals": [journals(n)[0].hex() for n in sorted(CARRIERS)]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "journals.json")
            with open(path, "w") as fh:
                json.dump(payload, fh)
            outs = {}
            for mode in ("audit-first", "engine-first"):
                out = subprocess.run([sys.executable, "-s", "-c", ORDER_SCRIPT, mode, path],
                                     cwd=ROOT, env=clean_env(PYTHONHASHSEED="0"),
                                     capture_output=True, text=True, check=True).stdout
                outs[mode] = json.loads(out)
        a, e = outs["audit-first"], outs["engine-first"]
        self.assertEqual(a["reports"], e["reports"])
        self.assertEqual(len(a["reports"]), len(CARRIERS))
        self.assertFalse([m for m in a["loaded"] if m.startswith("imperium.battle.engine")])
        self.assertIn("imperium.battle.audit", a["loaded"])
        self.assertIn("imperium.battle.engine", e["before"])
        self.assertIn("imperium.battle.engine.session", e["loaded"])
        local = [[r.fixture, r.pair, list(r.run) if r.run else None, r.sealed, r.roots, r.cursor,
                  r.final, r.terminal, [list(x) for x in r.stages], r.draws, r.final_chain]
                 for r in (verify(journals(n)[0]) for n in sorted(CARRIERS))]
        self.assertEqual(a["reports"], local)
        print(f"\nF06 audit-first loaded {len(a['loaded'])} imperium modules, none under engine; "
              f"engine-first loaded {len(e['loaded'])}", end="")


if __name__ == "__main__":
    unittest.main()
