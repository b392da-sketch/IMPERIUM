"""AT-R03 static guards and the builder guards G-BLD-1 to G-BLD-3 (11.7)."""

import ast
import dataclasses
import pathlib
import sys
import unittest

import imperium.battle as B

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "imperium" / "battle"
BUILDER = ROOT / "tests" / "support" / "battle_builder.py"
LAYERS = {
    "errors": 0, "ids": 1, "values": 2, "board": 3, "profile": 3, "scenario": 4,
    "descriptors": 4, "records": 5, "canon": 6, "queries": 7, "invariants": 8, "state": 9,
    "codec": 10, "fixtures": 10, "api": 11, "__init__": 12,
}
FORBIDDEN_NAMES = ("_unchecked", "from_trusted", "skip_validation", "no_validate", "unchecked",
                   "trusted", "placeholder", "disable", "_skip", "bypass")


def modules():
    for path in sorted(PACKAGE.glob("*.py")):
        yield path.stem, ast.parse(path.read_text(encoding="utf-8"), str(path))


def imported(tree):
    """``(level, module, names)`` for every import statement."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.level, node.module or "", [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield 0, a.name, []


class ArchitectureTests(unittest.TestCase):
    def test_every_module_has_a_layer(self):
        self.assertEqual({name for name, _ in modules()}, set(LAYERS))

    def test_layer_order(self):
        for name, tree in modules():
            for level, module, names in imported(tree):
                if level == 0:
                    self.assertFalse(module.startswith("imperium"), (name, module))
                    continue
                targets = [module] if module else names
                for target in targets:
                    with self.subTest(module=name, target=target):
                        self.assertLess(LAYERS[target], LAYERS[name])

    def test_no_bypass_or_registration_at_runtime(self):
        for name, tree in modules():
            for node in ast.walk(tree):
                ident = None
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    ident = node.name
                elif isinstance(node, ast.Name):
                    ident = node.id
                elif isinstance(node, ast.Attribute):
                    ident = node.attr
                elif isinstance(node, ast.arg):
                    ident = node.arg
                elif isinstance(node, ast.keyword):
                    ident = node.arg
                if ident:
                    lowered = ident.lower()
                    for bad in FORBIDDEN_NAMES:
                        self.assertNotIn(bad, lowered, (name, ident))
            for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.Lambda))]:
                for node in ast.walk(func):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertNotEqual(node.func.id, "register", (name, "runtime registration"))
                    if isinstance(node, ast.Global):
                        self.fail(f"{name}: global statement")

    def test_queries_and_invariants_never_see_state(self):
        for name in ("queries", "invariants"):
            tree = ast.parse((PACKAGE / f"{name}.py").read_text(encoding="utf-8"))
            for level, module, names in imported(tree):
                self.assertNotIn("state", [module] + names, name)
                self.assertNotIn("BattleState", names, name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "BattleState", name)
                if isinstance(node, ast.Attribute):
                    self.assertNotEqual(node.attr, "BattleState", name)

    def test_g_bld_2_no_tests_import(self):
        for path in (ROOT / "imperium").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for level, module, names in imported(tree):
                self.assertFalse(level == 0 and (module == "tests" or module.startswith("tests.")),
                                 path)

    def test_g_bld_1_builder_imports(self):
        tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
        stdlib = sys.stdlib_module_names
        for level, module, names in imported(tree):
            self.assertEqual(level, 0)
            if module == "imperium.battle":
                for n in names:
                    self.assertIn(n, B.__all__)
            else:
                self.assertIn(module.split(".")[0], stdlib, module)

    def test_g_bld_3_public_surface_validates(self):
        tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
        exported = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and node.targets[0].id == "__all__":
                exported = [e.value for e in node.value.elts]
        self.assertEqual(sorted(exported), sorted(B.__all__))
        self.assertEqual(len(exported), len(set(exported)))
        for name in B.__all__:
            for bad in FORBIDDEN_NAMES:
                self.assertNotIn(bad, name.lower())
        self.assertFalse(hasattr(B.BattleState, "unchecked"))
        fields = {f.name for f in dataclasses.fields(B.BattleState)}
        extra = {n for n in vars(B.BattleState) if not n.startswith("_")} - fields
        self.assertEqual(extra, {"evolve"})
