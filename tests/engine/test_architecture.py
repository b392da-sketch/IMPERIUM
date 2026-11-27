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
# P3 (contract rev 0.3 section 3) adds draws (E0a), events (E4a) and replay (E5a).
LAYERS = {"commands": 0, "draws": 0.5, "terminal": 1, "custody": 2, "rounds": 3, "events": 3.5,
          "step": 4, "session": 5, "replay": 5.5, "__init__": 6,
          # P4 (contract rev 0.2 section 3, ER09)
          "geometry": 0.6, "exertion": 0.7, "movement": 3.6, "window": 3.7}
P4_EDGES = {"geometry": set(), "exertion": set(),
            "movement": {"commands", "geometry", "exertion"},
            "window": {"commands", "events", "geometry", "exertion"}}
BANNED = ("unchecked", "trusted", "force", "skip", "bypass", "raw_install", "rawinstall",
          "setter")
P1_BASELINE = "d93d69195ddb04786f481638d850351ab4934b2e"


P4_EXPORTS = {
    "MoveOrder", "PivotOrder", "WithdrawOrder", "EvacuateOrder", "GroupMoveOrder",
    "GroupPivotOrder", "RespondPivot", "RespondMissile", "DeclineResponse", "ResponseOption",
    "ResponseWindow", "SuspendedRoot", "Suspended", "WindowRejected", "WindowDeferred"}


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
                         ["export_audit", "journal", "open", "pending", "state", "submit"])
        self.assertEqual(set(E.__all__) - P4_EXPORTS, {
            "OpenBattle", "HoldOrder", "PassOrder", "DeclareWithdrawal", "Capitulate", "Command",
            "Accepted", "Rejected", "Deferred", "Result", "Stage", "RejectCode", "step",
            "BattleSession", "JournalEntry", "encode_command", "command_digest",
            # P3 additions, exactly ER04's inventory
            "RunKey", "Channel", "StageKey", "format_stage_id", "parse_stage_id", "fixture_pair",
            "draw_numerator", "Effect", "DrawRecord", "StageEvent", "StageSnapshot", "RootRecord",
            "Resolved", "resolve", "command_bytes", "decode_command", "replay", "ReplayError"})
        self.assertLessEqual(P4_EXPORTS, set(E.__all__))

    def test_p4_edges_and_inventory(self):
        """ER09/E05: the four P4 modules' edges and the exact public classes."""
        for name, tree in modules():
            if name in P4_EDGES:
                got = {n.module for n in ast.walk(tree)
                       if isinstance(n, ast.ImportFrom) and n.level == 1}
                self.assertEqual(got, P4_EDGES[name], name)
        import inspect
        self.assertEqual(sorted(n for n in E.__all__ if inspect.isclass(getattr(E, n))), sorted([
            "Accepted", "BattleSession", "Capitulate", "Channel", "DeclareWithdrawal",
            "DeclineResponse", "Deferred", "DrawRecord", "Effect", "EvacuateOrder",
            "GroupMoveOrder", "GroupPivotOrder", "HoldOrder", "JournalEntry", "MoveOrder",
            "OpenBattle", "PassOrder", "PivotOrder", "RejectCode", "Rejected", "ReplayError",
            "Resolved", "RespondMissile", "RespondPivot", "ResponseOption", "ResponseWindow",
            "RootRecord", "RunKey", "Stage", "StageEvent", "StageKey", "StageSnapshot",
            "Suspended", "SuspendedRoot", "WindowDeferred", "WindowRejected", "WithdrawOrder"]))
        self.assertEqual([s.name for s in E.Stage][10:], [
            "STEP1", "STEP2", "STEP3", "WITHDRAW", "GROUP_STEP", "PIVOT", "GROUP_PIVOT",
            "EVACUATE", "WINDOW", "RESPONSE"])
        self.assertEqual(len(E.RejectCode), 35)

    def test_p4_no_stable_bypass(self):
        """Results and suspended roots are built only on the transition path."""
        built = {"Accepted", "Resolved", "Suspended", "SuspendedRoot", "WindowRejected",
                 "WindowDeferred"}
        for name, tree in modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    called = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                    if called in built:
                        self.assertEqual(name, "step", f"{name} builds {called}")

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
        changed = [p for p in out.splitlines() if "/engine/" not in p and "/audit/" not in p]
        self.assertEqual(changed, [])

    def test_no_group_commands(self):
        """TA-C12, as amended by P4 ER09: the exact supported command inventory.
        Assault, missile, rally and rest orders stay outside the union."""
        kinds = {n for n in E.__all__ if n.endswith("Order") or n in ("OpenBattle", "Capitulate",
                                                                          "DeclareWithdrawal")}
        self.assertEqual(kinds, {"OpenBattle", "HoldOrder", "PassOrder", "DeclareWithdrawal",
                                 "Capitulate", "MoveOrder", "PivotOrder", "WithdrawOrder",
                                 "EvacuateOrder", "GroupMoveOrder", "GroupPivotOrder"})
        for absent in ("AssaultOrder", "MissileOrder", "RallyOrder", "RestOrder"):
            self.assertNotIn(absent, E.__all__)
            self.assertFalse(hasattr(E, absent), absent)
