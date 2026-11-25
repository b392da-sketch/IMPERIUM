import json
import unittest

from imperium.events import canonical_json
from imperium.f01.research import MANIFEST, simulate, validate
from imperium.f01.resolver import F01, Order

from .test_f01_resolver import fixture


class ResearchTests(unittest.TestCase):
    def test_policy_replay_mirror_and_strict_type(self):
        original, reflected = MANIFEST[:2]
        row, trace = simulate(original)
        archived = json.loads(canonical_json(trace))
        verified, events = simulate(original, archived)
        self.assertEqual(canonical_json(verified), canonical_json(row))
        mirror, _ = simulate(reflected, archived)
        self.assertEqual(mirror["trace_sha256"], row["trace_sha256"])
        self.assertEqual(mirror["terminal_state_sha256"], row["terminal_state_sha256"])
        self.assertEqual(len(events) - 1, len(row["choices"]))
        archived[1]["round"] = True
        with self.assertRaisesRegex(ValueError, "event mismatch"):
            simulate(original, archived)
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate(original, row, True)

    def test_exact_development_manifest(self):
        self.assertEqual(
            {(e["variant"], e["seed"], e["mirrored"]) for e in MANIFEST},
            {(variant, seed, mirrored) for variant in ("open", "rough", "barrier")
             for seed in range(22000, 22016) for mirrored in (False, True)},
        )
        self.assertEqual(len(MANIFEST), 96)

    def test_deadline_o0_and_completed_rest(self):
        units = fixture((0, (5, 4), 4), (8, (9, 1), 1))
        units[0].fatigue = 2
        units[0].exertion = 4
        battle = F01(22000, formations=units)
        battle.resolve(Order("rest", (0,)))
        battle.resolve(Order("pass"))
        battle.resolve(Order("pass"))
        self.assertEqual((battle.units[0].fatigue, battle.units[0].exertion), (1, 0))
        battle.units[0].fatigue = 2
        while not battle.terminal:
            battle.resolve(Order("pass"))
        self.assertEqual((battle.terminal["winner"], battle.terminal["reason"]), (0, "objective"))
        self.assertEqual(battle.elapsed, 120)

    def test_terminal_root_skips_pending_recovery(self):
        units = fixture((0, (2, 6), 4), (8, (9, 1), 1))
        units[0].fatigue = 2
        battle = F01(22000, formations=units)
        battle.resolve(Order("rest", (0,)))
        battle.resolve(Order("capitulate"))
        self.assertEqual(battle.units[0].fatigue, 2)
        self.assertEqual(battle.elapsed, 10)
