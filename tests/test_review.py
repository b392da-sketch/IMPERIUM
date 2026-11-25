import tempfile
import unittest
import json
from dataclasses import asdict
from pathlib import Path

from imperium.__main__ import (
    dump_rows, paired_report, replay_run, report, simulate, summarize,
)
from imperium.events import jsonl
from imperium.experiments import CONFIRMATION, MIRROR, POLICY, SCREENING, Run
from imperium.fixture import FIXTURE_VERSION
from imperium.profiles import PROFILE_VERSION, PROFILES
from imperium.provenance import EARLY_EXIT, EP08, FROZEN, H32
from imperium.scheduler import Action, Battle


def identity(seed=20000, profile="F6", **overrides):
    return {"run": asdict(Run(profile, seed, ("AGG", "AGG"))), "stream": EP08,
            "resolver_variant": FROZEN, "fixture_version": FIXTURE_VERSION,
            "profile_version": PROFILE_VERSION, "initial_fixture": "default", **overrides}


class AggregationReviewTests(unittest.TestCase):
    def test_mixed_streams_and_duplicate_observations(self):
        for operation in (report, lambda rows: paired_report(rows, "F6")):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "incompatible"):
                    operation([identity(), identity(seed=20001, stream=H32)])
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    operation([identity(), identity()])

    def test_rejects_orientation_version_and_resolver_mixing(self):
        original = identity()
        for variant in (
            identity(stream=H32, resolver_variant=EARLY_EXIT),
            identity(fixture_version="earlier-fixture"),
            identity(profile_version="earlier-profile"),
            identity(initial_fixture="explicit"),
            {**identity(), "run": {**original["run"], "mirrored": True}},
        ):
            with self.subTest(row=variant), self.assertRaises(ValueError):
                report([original, variant])
        with self.assertRaisesRegex(ValueError, "incompatible"):
            report([identity(stream=H32), identity(stream=H32, resolver_variant=EARLY_EXIT)])

    def test_paired_requires_exact_seed_sets_and_one_matchup(self):
        baseline = [identity(seed=s) for s in (20000, 20001)]
        comparison = [identity(seed=s, profile="R0") for s in (20000, 20002)]
        with self.assertRaisesRegex(ValueError, "unmatched seeds"):
            paired_report(baseline + comparison, "F6")
        comparison[1]["run"]["policies"] = ("AGG", "RES")
        with self.assertRaisesRegex(ValueError, "one policy matchup"):
            paired_report(baseline + comparison, "F6")


class MatrixReviewTests(unittest.TestCase):
    def test_exact_expected_membership(self):
        def members(profiles, seeds, matchups):
            return {Run(p, s, m) for p in profiles for s in seeds for m in matchups}
        expected = (
            (SCREENING, members(("R0", "F6", "C", "J", "O", "N", "CJON", "LOW"),
                                range(20000, 20128), (("AGG", "AGG"),))),
            (CONFIRMATION, members(("R0", "F6", "CJON", "LOW"),
                                   range(21000, 21512), (("AGG", "AGG"),))),
            (POLICY, members(("F6",), range(20000, 20128),
                             (("ADV", "PASS"), ("AGG", "RES"), ("ADV", "RES"), ("AGG", "ADV")))),
        )
        for actual, expected_members in expected:
            self.assertEqual(set(actual), expected_members)
            self.assertEqual(len(actual), len(expected_members))
        self.assertEqual(MIRROR, tuple(
            (Run("F6", s, ("AGG", "RES")), Run("F6", s, ("AGG", "RES"), True))
            for s in range(20000, 20128)
        ))

    def test_matrix_writer_rejects_equal_cardinality_substitution(self):
        from imperium.execution import validate_completion

        with self.assertRaisesRegex(ValueError, "planned identity"):
            validate_completion(identity(20000), identity(20001), 1)


class ReplayReviewTests(unittest.TestCase):
    def record(self, directory, variant, legacy):
        config = Run("F6", 20000, ("AGG", "RES"))
        battle, counts = simulate(config, variant=variant, legacy=legacy)
        trace = jsonl(battle.events)
        (directory / "events.jsonl").write_text(trace)
        dump_rows(directory / "actions.jsonl", map(asdict, battle.actions))
        summary = summarize(config, battle, counts, trace)
        dump_rows(directory / "summary.json", [summary])
        return summary, len(battle.events)

    def test_tampered_summary_rejected_even_when_trace_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            summary, _ = self.record(folder, FROZEN, False)
            for field, tampered in (("winner", 1), ("preferred_choices", []), ("trace_sha256", "0"*64)):
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                    dump_rows(folder / "summary.json", [{**summary, field: tampered}])
                    replay_run(folder)

    def test_exact_comparator_replay_and_variant_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            summary, roots = self.record(folder, EARLY_EXIT, True)
            self.assertEqual(replay_run(folder, EARLY_EXIT), (roots, EARLY_EXIT))
            dump_rows(folder / "summary.json", [{**summary, "resolver_variant": FROZEN}])
            with self.assertRaisesRegex(ValueError, "trace mismatch"):
                replay_run(folder)


class InvariantReviewTests(unittest.TestCase):
    def test_invalid_injected_stable_states(self):
        def exhausted(b):
            b.used[0] = 5

        def invalid_effort(b):
            b.effort[0] = 4

        def phantom_opportunity(b):
            b.used[0] = 1

        def duplicate_activation(b):
            b.resolve(Action("hold", 0))
            b.units[0].principal_eligibility = True

        def withdrawn_on_board(b):
            b.units[0].disposition = "withdrawn"

        def depleted_on_board(b):
            unit = b.units[0]
            unit.disposition = "depleted"
            unit.available_personnel = 0
            unit.killed_personnel = 240

        def router_off_board(b):
            b.units[0].disposition = "routing"
            b.units[0].position = None

        for corruption in (exhausted, invalid_effort, phantom_opportunity, duplicate_activation,
                           withdrawn_on_board, depleted_on_board, router_off_board):
            with self.subTest(corruption=corruption.__name__):
                battle = Battle(PROFILES["F6"], 20000)
                corruption(battle)
                with self.assertRaises(AssertionError):
                    battle.assert_invariants()

    def test_link_persists_across_closure_then_legal_withdrawal_removes_it(self):
        from tests.test_scheduler import setup

        battle = setup((0, (4, 6), "organized"), (6, (3, 6), "organized", 4))
        battle.encounter.contacts.add((0, 6))
        battle.resolve(Action("pass"))
        battle.resolve(Action("pass"))
        self.assertEqual(battle.round, 2)
        self.assertEqual(battle.encounter.contacts, {(0, 6)})
        battle.resolve(Action("pass"))
        battle.resolve(Action("withdraw", 0, path=((3, 7),)))
        self.assertEqual(battle.encounter.contacts, set())
        self.assertEqual(battle.units[0].activity_marks, 2)
        self.assertEqual(battle.units[0].position, (3, 7))
        self.assertEqual(battle.units[6].position, (3, 6))


class InitialTerminalReviewTests(unittest.TestCase):
    def fixture(self, red, blue):
        from imperium.fixture import Encounter, Formation, Identity

        dispositions = (red, blue)
        formations = []
        for side, disposition in enumerate(dispositions):
            position = (4, 6) if side == 0 else (4, 5)
            if disposition in ("withdrawn", "depleted"):
                position = None
            depleted = disposition == "depleted"
            formations.append(Formation(
                Identity(side, 0), side, position, 4 if side == 0 else 1,
                available_personnel=0 if depleted else 240,
                killed_personnel=240 if depleted else 0, disposition=disposition,
            ))
        return Encounter(tuple(formations))

    def test_initial_states_terminal_before_round_opening(self):
        cases = (
            ("organized", "organized", None, {}),
            ("reforming", "organized", None, {}),
            ("organized", "routing", (0, "military"), {"1": "collapse"}),
            ("routing", "reforming", (1, "military"), {"0": "collapse"}),
            ("depleted", "withdrawn", (None, "mutual"),
             {"0": "depletion_or_mixed_loss", "1": "orderly_departure"}),
        )
        for red, blue, outcome, reasons in cases:
            with self.subTest(red=red, blue=blue):
                battle = Battle(PROFILES["F6"], 20000, encounter=self.fixture(red, blue))
                self.assertEqual(battle.terminal, outcome)
                self.assertEqual(battle.defeat_subreasons, reasons)
                if outcome is None:
                    self.assertEqual(battle.round, 1)
                    self.assertTrue(all(battle.effort.values()))
                    continue
                self.assertEqual((battle.round, battle.root, battle.actions), (0, 0, []))
                self.assertEqual((battle.used, sum(battle.effort.values())), ([0, 0], 0))
                self.assertEqual(battle.events[0].event_kind, "initial_terminal")
                self.assertEqual(battle.events[0].state_before_digest, battle.initial_state_digest)
                self.assertEqual(battle.events[0].state_after_digest, battle.digest())
                for unit in battle.ordered():
                    if unit.disposition == "routing":
                        self.assertIsNotNone(unit.position)
                    self.assertFalse(unit.principal_eligibility)
                with self.assertRaisesRegex(ValueError, "no side opportunity"):
                    battle.resolve(Action("pass"))
                self.assertEqual(battle.events[0].state_after_digest, battle.digest())

    def test_defeat_subreason_uses_dispositions(self):
        initial = self.fixture("organized", "withdrawn")
        battle = Battle(PROFILES["F6"], 20000, encounter=initial)
        self.assertEqual(battle.defeat_subreasons, {"1": "orderly_departure"})

        from imperium.fixture import Encounter, Formation, Identity
        mixed = Encounter(initial.formations + (Formation(
            Identity(1, 1), 1, None, 1, available_personnel=0, killed_personnel=240,
            disposition="depleted",
        ),))
        battle = Battle(PROFILES["F6"], 20000, encounter=mixed)
        self.assertEqual(battle.defeat_subreasons, {"1": "depletion_or_mixed_loss"})

    def test_zero_action_artifact_round_trips(self):
        from imperium.__main__ import write_run

        initial = self.fixture("routing", "reforming")
        config = Run("F6", 20000, ("AGG", "RES"))
        battle, counts = simulate(config, encounter=initial)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            write_run(path, config, battle, counts, initial=initial)
            self.assertEqual((path / "actions.jsonl").read_bytes(), b"")
            summary = json.loads((path / "summary.json").read_text())
            self.assertEqual((summary["charged_rounds"], summary["elapsed_minutes"]), (0, 0))
            self.assertEqual(summary["initial_state_sha256"], battle.initial_state_digest)
            self.assertEqual(summary["terminal_state_sha256"], battle.digest())
            self.assertEqual(replay_run(path, FROZEN), (0, FROZEN))
            with self.assertRaisesRegex(ValueError, "variant mismatch"):
                replay_run(path, EARLY_EXIT)


class StatisticalReviewTests(unittest.TestCase):
    def test_known_student_critical_values_and_interval(self):
        from imperium.reporting import paired_continuous, t_critical_95

        for df, expected in ((1, 12.7062047364), (4, 2.7764451052), (9, 2.2621571629),
                             (29, 2.0452296421)):
            self.assertAlmostEqual(t_critical_95(df), expected, places=8)
        result = paired_continuous([1, 2, 3, 4, 5])
        self.assertAlmostEqual(result["student_t_95"][0], 1.03675684, places=7)
        self.assertAlmostEqual(result["student_t_95"][1], 4.96324316, places=7)
        self.assertAlmostEqual(result["sample_sd"], 2.5**.5)

    def test_quantiles_and_small_or_constant_samples(self):
        from imperium.reporting import describe, paired_continuous

        self.assertEqual(describe([1, 2, 3, 4, 5])["p10"], 1.4)
        self.assertEqual(describe([1, 2, 3, 4, 5])["p90"], 4.6)
        self.assertIsNone(describe([])["mean"])
        self.assertIsNone(paired_continuous([5])["student_t_95"])
        self.assertEqual(paired_continuous([5, 5])["student_t_95"], [5, 5])
