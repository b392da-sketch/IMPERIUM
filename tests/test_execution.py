import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from imperium.__main__ import report, run_matrix
from imperium.execution import Journal, load_execution, matrix_plan


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        self.output = folder / "screen.jsonl"
        self.journal = folder / "screen.execution.jsonl"
        full = matrix_plan("screening", False)
        self.plan = [full[0], full[1], full[128]]
        patcher = patch("imperium.execution.matrix_plan", return_value=self.plan)
        patcher.start()
        self.addCleanup(patcher.stop)

    def succeed(self, entry):
        # A completed observation deliberately represents a draw so that counts
        # verify that technical outcomes never enter the battle denominator.
        return ({**entry, "reason": "unresolved", "winner": None, "metrics": {},
                 "round_three_exhaustion": None, "personnel": {"killed": 1, "wounded": 2},
                 "preferred_choices": [2], "defeat_subreasons": {},
                 "objective": {"classification": "none"}, "charged_rounds": 12,
                 "trace_sha256": "a" * 64, "terminal_state_sha256": "b" * 64}, 2)

    def run_with(self, worker, journal=None):
        run_matrix("screening", False, self.output, journal or self.journal, 1, worker)

    def test_successful_matrix_reconciles_and_publishes(self):
        self.run_with(self.succeed)
        evidence = load_execution(self.journal)
        rows = list(map(json.loads, self.output.read_text().splitlines()))
        self.assertTrue(evidence.complete)
        self.assertEqual(evidence.materialize(), rows)
        result = report(rows, evidence)
        self.assertEqual(result["R0 AGG/AGG"]["attempted_runs"], 2)
        self.assertEqual(result["F6 AGG/AGG"]["completed_runs"], 1)
        self.assertEqual(result["F6 AGG/AGG"]["technical_stops"], 0)

    def test_failure_before_first_completion(self):
        def fail(entry):
            # Verify the attempted identity is durable before entering the worker.
            self.assertEqual(load_execution(self.journal).attempted, {0})
            raise RuntimeError("worker diagnostic")

        with self.assertRaisesRegex(RuntimeError, "worker diagnostic"):
            self.run_with(fail)
        evidence = load_execution(self.journal)
        self.assertFalse(self.output.exists())
        self.assertEqual(evidence.stops, {0: "RuntimeError: worker diagnostic"})
        result = report([], evidence)
        red = result["R0 AGG/AGG"]
        self.assertEqual((red["attempted_runs"], red["completed_runs"], red["technical_stops"],
                          red["not_attempted_runs"], red["unresolved_denominator"]), (1, 0, 1, 1, 0))
        self.assertEqual(red["wins_draws"], {})
        self.assertIsNone(red["bm07_warning"])
        self.assertEqual(result["F6 AGG/AGG"]["attempted_runs"], 0)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            evidence.materialize()

    def test_second_attempt_failure_leaves_first_observation_recoverable(self):
        def fail_second(entry):
            if entry == self.plan[1]:
                raise ValueError("second simulation failed")
            return self.succeed(entry)

        with self.assertRaisesRegex(ValueError, "second simulation failed"):
            self.run_with(fail_second)
        evidence = load_execution(self.journal)
        self.assertFalse(self.output.exists())
        self.assertFalse(evidence.complete)
        rows = evidence.observations()
        self.assertEqual(len(rows), 1)
        partial_file = self.output.with_suffix(".partial")
        partial_file.write_text(json.dumps(rows[0]) + "\n")
        group = report(map(json.loads, partial_file.read_text().splitlines()), evidence)["R0 AGG/AGG"]
        self.assertEqual((group["attempted_runs"], group["completed_runs"],
                          group["technical_stops"], group["unresolved_denominator"]), (2, 1, 1, 1))
        self.assertEqual(group["terminal_reasons"], {"unresolved": 1})

    def test_interrupt_keeps_unfinished_distinct(self):
        def interrupt(_):
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.run_with(interrupt)
        evidence = load_execution(self.journal)
        self.assertFalse(self.output.exists())
        stats = evidence.counts(range(len(self.plan)))
        self.assertEqual((stats["attempted_runs"], stats["unfinished_attempts"],
                          stats["technical_stops"], stats["not_attempted_runs"]), (1, 1, 0, 2))

    def test_standalone_partial_rows_have_unknown_attempt_counts(self):
        group = report([self.succeed(self.plan[0])[0]])["R0 AGG/AGG"]
        self.assertIsNone(group["attempted_runs"])
        self.assertIsNone(group["technical_stops"])
        self.assertIsNone(group["planned_runs"])
        self.assertEqual(group["completed_runs"], 1)
        with self.assertRaisesRegex(ValueError, "successful terminal"):
            report([{**self.succeed(self.plan[0])[0], "reason": "technical_stop"}])

    def test_missing_record_and_inconsistent_reconciliation(self):
        with self.assertRaises(FileNotFoundError):
            load_execution(self.journal)
        self.run_with(self.succeed)
        evidence = load_execution(self.journal)
        rows = evidence.observations()
        for supplied in (rows[:-1], rows + [rows[0]], [{**rows[0], "winner": 0}, *rows[1:]]):
            with self.subTest(size=len(supplied)), self.assertRaises(ValueError):
                report(supplied, evidence)
        lines = self.journal.read_bytes().splitlines(keepends=True)
        self.journal.write_bytes(b"".join([lines[0], *lines[2:]]))
        with self.assertRaisesRegex(ValueError, "outstanding attempt"):
            load_execution(self.journal)

    def test_duplicate_terminal_and_attempt_records_are_rejected(self):
        self.run_with(self.succeed)
        lines = self.journal.read_bytes().splitlines(keepends=True)
        for duplicate, pattern in ((lines[1], "duplicate attempt"), (lines[2], "outstanding attempt")):
            with self.subTest(pattern=pattern):
                self.journal.write_bytes(b"".join([*lines, duplicate]))
                with self.assertRaisesRegex(ValueError, pattern):
                    load_execution(self.journal)

    def test_retry_requires_new_journal_and_does_not_pool_counts(self):
        def fail(_):
            raise RuntimeError("first execution")

        with self.assertRaises(RuntimeError):
            self.run_with(fail)
        with self.assertRaises(FileExistsError):
            self.run_with(self.succeed)
        retry = self.journal.with_name("retry.execution.jsonl")
        self.run_with(self.succeed, retry)
        self.assertEqual(load_execution(self.journal).stops, {0: "RuntimeError: first execution"})
        evidence = load_execution(retry)
        self.assertEqual(evidence.counts(range(len(self.plan)))["attempted_runs"], 3)
        self.assertEqual(evidence.counts(range(len(self.plan)))["completed_runs"], 3)

    def test_torn_record_cannot_be_published_or_extended(self):
        journal, plan = Journal.create(self.journal, "screening", False)
        journal.append({"event": "attempted", "index": 0})
        with self.journal.open("ab") as output:
            output.write(b'{"event":"completed"')
        evidence = load_execution(self.journal)
        self.assertTrue(evidence.torn_tail)
        self.assertEqual(evidence.counts(range(len(self.plan)))["unfinished_attempts"], 1)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            evidence.materialize()
        with self.assertRaisesRegex(ValueError, "unfinished trailing"):
            journal.execute(1, plan[1], self.succeed)

    def test_cli_rejects_boolean_substitution_for_integer_observation(self):
        from imperium.__main__ import main

        def decisive(entry):
            row, roots = self.succeed(entry)
            return {**row, "reason": "objective", "winner": 1}, roots

        self.run_with(decisive)
        with patch("sys.argv", ["imperium", "verify-execution", str(self.journal),
                                "--observations", str(self.output)]):
            rows = list(map(json.loads, self.output.read_text().splitlines()))
            rows[0]["winner"] = True
            self.output.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "differs from execution completions"):
                main()
