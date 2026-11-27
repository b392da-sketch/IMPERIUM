"""TA-P4-M01: the diff against the accepted base 60ce22a stays inside the
contract's section 3 paths and the section 13.2 accepted-test files."""

import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "60ce22a2adcbc06f9eaea643e115894a56d166a2"
RUNTIME = {
    "imperium/battle/engine/geometry.py", "imperium/battle/engine/exertion.py",
    "imperium/battle/engine/movement.py", "imperium/battle/engine/window.py",
    "imperium/battle/engine/commands.py", "imperium/battle/engine/step.py",
    "imperium/battle/engine/session.py", "imperium/battle/engine/events.py",
    "imperium/battle/engine/draws.py", "imperium/battle/engine/replay.py",
    "imperium/battle/engine/__init__.py", "imperium/battle/audit/rules.py",
    "imperium/battle/audit/refold.py", "imperium/battle/audit/wire.py",
    "imperium/battle/audit/__init__.py",
}
ACCEPTED_TESTS = {
    "tests/engine/test_architecture.py", "tests/audit/test_keys.py",
    "tests/audit/test_journal.py", "tests/audit/test_review_pr6.py",
    "tests/audit/test_preservation.py",
}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


class M01Diff(unittest.TestCase):

    def setUp(self):
        try:
            git("cat-file", "-e", BASE + "^{commit}")
        except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
            self.skipTest(f"git history unavailable: {exc}")

    def changed(self):
        out = set(git("diff", "--name-only", BASE).split())
        out |= set(git("diff", "--name-only", BASE, "HEAD").split())
        out |= set(git("ls-files", "--others", "--exclude-standard").split())
        return out

    def test_paths(self):
        outside = sorted(p for p in self.changed()
                         if p not in RUNTIME and p not in ACCEPTED_TESTS
                         and not p.startswith("tests/movement/"))
        self.assertEqual(outside, [])
        self.assertEqual(git("merge-base", "--is-ancestor", BASE, "HEAD"), "")

    def test_frozen_layers_untouched(self):
        for p in self.changed():
            self.assertFalse(p.startswith(("evidence/", "docs/research/")), p)
            if p.startswith("imperium/") and not p.startswith("imperium/battle/"):
                self.fail(p)
            if p.startswith("imperium/battle/") and not p.startswith(
                    ("imperium/battle/engine/", "imperium/battle/audit/")):
                self.fail(p)

    def test_audit_exports_unchanged(self):
        self.assertEqual(git("diff", BASE, "--", "imperium/battle/audit/__init__.py"), "")


if __name__ == "__main__":
    unittest.main()
