"""TA-I01 and TA-I04, guard G-P3-2, and the poisoned-engine half of TA-D02
(contract rev 0.3 sections 1, 3, 13 and 14 I).

TA-I02 (367 P1+P2 tests, full random mode) and TA-I03 (RG02 35/35, legacy
golden and review tests) are suite runs recorded in the implementation-gate
evidence, not assertions inside this module.
"""

import ast
import fnmatch
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tests.audit.support import CARRIERS, HOLDOUT, WALK_SEEDS, allowed_seed, journals
from tests.audit.test_invariance import ORDER_SCRIPT, POISON, clean_env

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME_BASE = "5dcfd5dd186c7a2f3ee5a422992c302e2a521389"
DOC_BASE = "44a990ab94973a6db9707505f6bf63e6f774752c"
ALLOWED = (
    "imperium/battle/engine/draws.py", "imperium/battle/engine/events.py",
    "imperium/battle/engine/replay.py", "imperium/battle/audit/*", "tests/audit/*",
    "imperium/battle/engine/commands.py", "imperium/battle/engine/step.py",
    "imperium/battle/engine/session.py", "imperium/battle/engine/__init__.py",
    "tests/engine/test_architecture.py", "tests/engine/test_session.py",
)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


class Preservation(unittest.TestCase):

    def setUp(self):
        try:
            git("cat-file", "-e", RUNTIME_BASE + "^{commit}")
            git("cat-file", "-e", DOC_BASE + "^{commit}")
        except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
            self.skipTest(f"git history unavailable: {exc}")

    def test_i01_bases(self):
        self.assertEqual(git("diff", "--name-only", RUNTIME_BASE, DOC_BASE).split(), ["README.md"])
        self.assertEqual(git("merge-base", "--is-ancestor", DOC_BASE, "HEAD"), "")
        self.assertEqual(git("rev-parse", DOC_BASE + "^"), RUNTIME_BASE + "\n")

    def test_i01_changed_paths(self):
        changed = set(git("diff", "--name-only", DOC_BASE).split())
        changed |= set(git("ls-files", "--others", "--exclude-standard").split())
        changed |= set(git("diff", "--name-only", DOC_BASE, "HEAD").split())
        outside = sorted(p for p in changed if not any(fnmatch.fnmatch(p, g) for g in ALLOWED))
        self.assertEqual(outside, [])
        self.assertNotIn("README.md", changed)

    def test_i01_session_seam_only(self):
        diff = git("diff", "-U0", DOC_BASE, "--", "tests/engine/test_session.py")
        minus = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
        plus = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
        self.assertEqual(len(minus), 2)
        self.assertEqual([l[1:].replace('"step"', '"resolve"') for l in minus],
                         [l[1:] for l in plus])

    def test_i04_seed_allowlist(self):
        for seed in WALK_SEEDS:
            allowed_seed(seed)
        for bad in (-1, 1000, 10000, 14095, 30000, 31023, True, 1.0):
            with self.assertRaises(AssertionError):
                allowed_seed(bad)
        for path in sorted((ROOT / "tests" / "audit").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    v = node.value
                    if type(v) is int and path.name not in ("support.py", "test_preservation.py"):
                        self.assertFalse(any(v in r for r in HOLDOUT), (path.name, v))
                    if type(v) is str:
                        self.assertNotIn("HF" + "02", v, path.name)
        oracle = json.loads((ROOT / "tests" / "audit" / "reference_oracles.json").read_text())
        for row in oracle["bk1_vectors"]:
            allowed_seed(row[0])


class RuntimeGuards(unittest.TestCase):

    def test_g_p3_2_runtime_imports(self):
        """No runtime module imports ``tests`` or calls the isolated draw-record validator."""
        for path in sorted((ROOT / "imperium").rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module or ""]
                for m in mods:
                    self.assertFalse(m == "tests" or m.startswith("tests."), (rel, m))
                if not rel.startswith("imperium/battle/audit/"):
                    names = set()
                    if isinstance(node, ast.Name):
                        names.add(node.id)
                    elif isinstance(node, ast.Attribute):
                        names.add(node.attr)
                    elif isinstance(node, ast.ImportFrom):
                        names |= {a.name for a in node.names}
                    self.assertFalse(names & {"check_draw_records", "drawcheck"}, rel)

    def test_d02_poisoned_engine_subprocess(self):
        payload = {"journals": [journals(n)[0].hex() for n in sorted(CARRIERS)]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "journals.json")
            with open(path, "w") as fh:
                json.dump(payload, fh)
            out = subprocess.run([sys.executable, "-s", "-c", ORDER_SCRIPT, "audit-first", path],
                                 cwd=ROOT, env=clean_env(), capture_output=True, text=True,
                                 check=True).stdout
        result = json.loads(out)
        self.assertEqual(len(result["reports"]), len(CARRIERS))
        self.assertEqual([m for m in result["loaded"] if "engine" in m], [])
        self.assertNotIn("imperium.randomness", result["loaded"])
        self.assertNotIn("imperium.legacy", result["loaded"])
        probe = subprocess.run([sys.executable, "-s", "-c", POISON + "\nimport imperium.battle.engine\n"],
                               cwd=ROOT, env=clean_env(), capture_output=True, text=True)
        self.assertNotEqual(probe.returncode, 0)
        self.assertIn("engine loading is poisoned", probe.stderr)


if __name__ == "__main__":
    unittest.main()
