"""Guard: every imported module is standard library or repository (16.5, AT-R07)."""

import importlib
import os
import pathlib
import sys
import sysconfig
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEST_MODULES = sorted(
    "tests.battle." + p.stem for p in (ROOT / "tests" / "battle").glob("*.py") if p.stem != "__init__")


def allowed(module):
    if module.__name__ in sys.builtin_module_names:
        return True
    spec = getattr(module, "__spec__", None)
    if spec is not None and spec.origin in ("built-in", "frozen"):
        return True
    path = getattr(module, "__file__", None)
    if path is None:
        return spec is None or spec.origin is None
    path = os.path.realpath(path)
    roots = {os.path.realpath(sysconfig.get_paths()[k]) for k in ("stdlib", "platstdlib")}
    roots.add(os.path.realpath(ROOT))
    return any(path.startswith(r + os.sep) for r in roots)


class StdlibOnlyTests(unittest.TestCase):
    def test_imports_are_stdlib_or_repository(self):
        importlib.import_module("imperium.battle")
        for name in sorted(p.stem for p in (ROOT / "imperium" / "battle").glob("*.py")):
            if name != "__init__":
                importlib.import_module("imperium.battle." + name)
        importlib.import_module("tests.support.battle_builder")
        for name in TEST_MODULES:
            importlib.import_module(name)
        bad = sorted(n for n, m in list(sys.modules.items()) if m is not None and not allowed(m))
        self.assertEqual(bad, [])

    def test_runtime_imports_no_third_party(self):
        import ast
        stdlib = sys.stdlib_module_names
        for path in (ROOT / "imperium" / "battle").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        self.assertIn(a.name.split(".")[0], stdlib, path)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split(".")[0], stdlib, path)
