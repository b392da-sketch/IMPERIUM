"""TA-A04: engine guards G-P2-1 to G-P2-5 (AST scans) and the public surface."""

import ast
import pathlib
import subprocess
import sys
import unittest

import imperium.battle as B
from imperium.battle import engine as E

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "imperium" / "battle" / "engine"
LAYERS = {"commands": 0, "terminal": 1, "custody": 2, "rounds": 3, "step": 4, "session": 5,
          "__init__": 6}
BANNED = ("unchecked", "trusted", "force", "skip", "bypass", "raw_install", "rawinstall",
          "setter")
P1_BASELINE = "d93d69195ddb04786f481638d850351ab4934b2e"


def modules():
    for path in sorted(ENGINE.glob("*.py")):
        yield path.stem, ast.parse(path.read_text(encoding="utf-8"))


class EngineGuards(unittest.TestCase):

    def test_inventory(self):
        self.assertEqual({name for name, _ in modules()}, set(LAYERS))

    def test_g_p2_1_single_constructor(self):
        """Only step.py constructs a state; nothing calls ``evolve``."""
        for name, tree in modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    called = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                    if called == "BattleState":
                        self.assertEqual(name, "step", f"{name} constructs a state")
                    self.assertNotEqual(called, "evolve", name)
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            if name not in ("step", "commands"):
                self.assertNotIn("BattleState", names, name)

    def test_g_p2_2_layer_order(self):
        for name, tree in modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 1:
                    target = node.module
                    self.assertLess(LAYERS[target], LAYERS[name], f"{name} imports {target}")
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                    self.assertFalse((mod or "").startswith("tests"), name)

    def test_g_p2_3_no_bypass_names(self):
        for name, tree in modules():
            for node in ast.walk(tree):
                ident = None
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    ident = node.name
                elif isinstance(node, ast.arg):
                    ident = node.arg
                elif isinstance(node, ast.Attribute):
                    ident = node.attr
                if ident:
                    low = ident.lower()
                    for b in BANNED:
                        self.assertNotIn(b, low, f"{name}: {ident}")
        self.assertEqual(sorted(n for n in dir(E.BattleSession) if not n.startswith("_")),
                         ["journal", "open", "state", "submit"])
        self.assertEqual(set(E.__all__), {
            "OpenBattle", "HoldOrder", "PassOrder", "DeclareWithdrawal", "Capitulate", "Command",
            "Accepted", "Rejected", "Deferred", "Result", "Stage", "RejectCode", "step",
            "BattleSession", "JournalEntry", "encode_command", "command_digest"})

    def test_g_p2_4_stdlib_only(self):
        stdlib = set(sys.stdlib_module_names)
        for name, tree in modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        self.assertIn(a.name.split(".")[0], stdlib | {"imperium"}, name)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split(".")[0], stdlib | {"imperium"}, name)

    def test_g_p2_5_p1_unchanged(self):
        try:
            out = subprocess.run(
                ["git", "diff", "--name-only", P1_BASELINE, "--", "imperium/battle/*.py",
                 "tests/battle", "tests/support", "evidence"],
                cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
            self.skipTest(f"git unavailable: {exc}")
        changed = [p for p in out.splitlines() if "/engine/" not in p]
        self.assertEqual(changed, [])

    def test_no_group_commands(self):
        """TA-C12: group orders are outside the P2 command union (DO-P2-03)."""
        kinds = {n for n in E.__all__ if n.endswith("Order") or n in ("OpenBattle", "Capitulate",
                                                                          "DeclareWithdrawal")}
        self.assertEqual(kinds, {"OpenBattle", "HoldOrder", "PassOrder", "DeclareWithdrawal",
                                 "Capitulate"})
