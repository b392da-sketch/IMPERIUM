"""TA-D01–D04 and TA-E01–E11: independent structural verification and
corruption codes (contract rev 0.3 section 8, ER01, ER06).

Every mutation is rechained with the test-side chain unless the case tests
the chain itself. Each case asserts the exact code, 1-based line and path.
"""

import ast
import importlib
import json
import pathlib
import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import AuditError, AuditReport, verify
from tests.audit.support import (
    CARRIERS, DEFENSIVE, RUN0, S0, S1, STANDARD, WALK_SEEDS, chained, cjson, final_chain,
    journals, oracles, rechain, session, sha, trees, walk,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT = ROOT / "imperium" / "battle" / "audit"
STAGE_ORDER = ("ADVANCE", "CLOSURE_CHECK", "CLOSURE_DISPLACEMENT", "END_CHECK", "IMMEDIATE_CHECK",
               "INITIAL_CHECK", "OPEN_ROUND", "RECOVERY", "ROOT", "TERMINAL")
EXPECTED = {  # roots, cursor, terminal, stage counts (test-side, section 11)
    "G0": (0, 0, True, {}),
    "G1": (4, 4, False, {"INITIAL_CHECK": 1, "OPEN_ROUND": 2, "ROOT": 3, "IMMEDIATE_CHECK": 3,
                         "CLOSURE_DISPLACEMENT": 1, "CLOSURE_CHECK": 1, "RECOVERY": 1,
                         "ADVANCE": 1, "END_CHECK": 1}),
    "G2": (2, 2, False, {"INITIAL_CHECK": 1, "OPEN_ROUND": 1, "ROOT": 1, "IMMEDIATE_CHECK": 1}),
    "G3": (2, 2, True, {"INITIAL_CHECK": 1, "OPEN_ROUND": 1, "ROOT": 1, "IMMEDIATE_CHECK": 1,
                        "TERMINAL": 1}),
    "G4": (25, 25, True, {"INITIAL_CHECK": 1, "OPEN_ROUND": 12, "ROOT": 24, "IMMEDIATE_CHECK": 24,
                          "CLOSURE_DISPLACEMENT": 12, "CLOSURE_CHECK": 12, "RECOVERY": 12,
                          "ADVANCE": 12, "END_CHECK": 12, "TERMINAL": 1}),
}


def stages_of(counts):
    return tuple((n, counts.get(n, 0)) for n in STAGE_ORDER)


def capitulate_s1():
    """OpenBattle, Pass(S0), Capitulate(S1): custody effects at list indices 8..15."""
    s = E.BattleSession.open(STANDARD, RUN0)
    for c in (E.OpenBattle(), E.PassOrder(S0), E.Capitulate(S1)):
        assert type(s.submit(c)) is E.Accepted
    return s.export_audit()


class Base(unittest.TestCase):

    def fault(self, data, code, line, path=None, **kw):
        with self.assertRaises(AuditError) as cm:
            verify(data, **kw)
        e = cm.exception
        self.assertEqual((e.code, e.line), (code, line), str(e))
        if path is not None:
            self.assertEqual(e.path, path, str(e))
        return e


class Verification(Base):

    def report_for(self, name, data, sealed):
        roots, cursor, terminal, counts = EXPECTED[name]
        fixture = CARRIERS[name][0]
        return AuditReport(fixture.token, "F01-v1-defensive-mutual-capitulation" if name == "G0"
                           else "F01-v1-open", (0, 0), sealed, roots, cursor,
                           oracles()["g0_wire_model"]["full_state_digest"] if name == "G0"
                           else oracles()["p2_carriers"][name]["full_state_digest"],
                           terminal, stages_of(counts), 0, final_chain(data))

    def test_d01_goldens_both_modes(self):
        for name in CARRIERS:
            sealed, prefix = journals(name)
            with self.subTest(carrier=name):
                self.assertEqual(verify(sealed), self.report_for(name, sealed, True))
                self.assertEqual(verify(sealed, require_sealed=False),
                                 self.report_for(name, sealed, True))
                self.assertEqual(verify(prefix, require_sealed=False),
                                 self.report_for(name, prefix, False))
                # L3 on the sealed artifact; ER06 anchored unsealed positive.
                self.assertEqual(verify(sealed, expected_chain=final_chain(sealed)).sealed, True)
                anchored = verify(prefix, require_sealed=False, expected_chain=final_chain(prefix))
                self.assertEqual((anchored.sealed, anchored.final_chain),
                                 (False, final_chain(prefix)))
                self.fault(prefix, "AU16", len(trees(prefix)) + 1, "")
                if name != "G0":
                    p2 = oracles()["p2_carriers"][name]
                    self.assertEqual((verify(sealed).roots, sum(dict(verify(sealed).stages).values())),
                                     (p2["roots"], p2["stages"]))

    def test_d01_null_run(self):
        s = session("G1", None)
        r = verify(s.export_audit())
        self.assertIsNone(r.run)
        self.assertIsNone(trees(s.export_audit())[0]["run"])

    def test_d01_d03_walks(self):
        for seed in WALK_SEEDS:
            s, commands, _ = walk(seed)
            for seal in (True, False):
                data = s.export_audit(seal=seal)
                r = verify(data, require_sealed=seal)
                self.assertEqual((r.roots, r.cursor, r.final, r.terminal, r.sealed, r.draws),
                                 (len(commands), s.state.clock.event_cursor, B.digest(s.state),
                                  type(s.state.phase) is B.Terminal, seal, 0), seed)
                counts = {}
                for rec in s.records:
                    for e in rec.events:
                        counts[e.stage.name] = counts.get(e.stage.name, 0) + 1
                self.assertEqual(r.stages, stages_of(counts), seed)
            # D03: the final document decodes through P1 and matches the last current
            # (verify itself decodes every root, AU15, and compares every current, AU14).
            state = B.decode_bytes(B.canonical_bytes(s.state))
            self.assertEqual(B.digest(state), s.records[-1].current, seed)

    def test_d03_each_root_decodes(self):
        for name in ("G1", "G2", "G3", "G4"):
            fixture, commands = CARRIERS[name]
            s = E.BattleSession.open(fixture, RUN0)
            for c, t in zip(commands(), trees(journals(name)[0])[1:]):
                s.submit(c)
                body = B.canonical_bytes(s.state)
                self.assertEqual(B.decode_bytes(body), s.state)
                self.assertEqual(sha(body), t["current"])

    def test_d04_pinned_faults(self):
        sealed = journals("G1")[0]

        def drop_cursor(ts):
            ts[2]["events"][0]["effects"] = [f for f in ts[2]["events"][0]["effects"]
                                             if f["path"] != "/clock/event_cursor"]
        self.fault(rechain(sealed, drop_cursor), "AU10", 3, "/events/0/effects")

        def scenario(ts):
            evs = ts[2]["events"]
            evs[0]["effects"].append({"path": "/scenario/first_side", "old": "x", "new": "y"})
        e = self.fault(rechain(sealed, scenario), "AU07", 3)
        self.assertTrue(e.path.startswith("/events/0/effects/"), e.path)

        def scenario_pair(ts):
            doc = json.loads(B.canonical_bytes(B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)))
            old = doc["scenario"]["first_side"]
            ts[2]["events"][0]["effects"].append({"path": "/scenario/first_side", "old": old,
                                                  "new": "S1"})
            ts[2]["events"][1]["effects"].insert(0, {"path": "/scenario/first_side", "old": "S1",
                                                     "new": old})
        self.fault(rechain(sealed, scenario_pair), "AU07", 3, "/events/0/effects/2/path")

        def bool_old(ts):
            ts[2]["events"][0]["effects"][0]["old"] = True
        self.assertEqual(trees(sealed)[2]["events"][0]["effects"][0],
                         {"path": "/clock/event_cursor", "old": 1, "new": 2})
        self.fault(rechain(sealed, bool_old), "AU08", 3, "/events/0/effects/0/old")

        def advance_data(ts):
            ev = ts[4]["events"][5]
            self.assertEqual(ev["stage"], "ADVANCE")
            ev["data"] = {"completed": 2}
        self.fault(rechain(sealed, advance_data), "AU10", 5, "/events/5/data")

        def dup_id(ts):
            ts[4]["events"][3]["id"] = ts[4]["events"][2]["id"]
        self.fault(rechain(sealed, dup_id), "AU05", 5, "/events/3/id")


class Corruption(Base):

    def test_direct_call_diagnostics(self):
        data = journals("G1")[0]
        for bad in ("x", bytearray(data), memoryview(data), None):
            with self.assertRaises(TypeError):
                verify(bad)
            with self.assertRaises(TypeError):
                E.replay(bad)
        for flag in (1, None, "True"):
            with self.assertRaises(TypeError):
                verify(data, require_sealed=flag)
        for chain in ("A" * 64, "a" * 63, b"a" * 64, 0, "g" * 64):
            with self.assertRaises(ValueError):
                verify(data, expected_chain=chain)
        with self.assertRaises(TypeError):
            verify(data, require_sealed=1, expected_chain="bad")
        with self.assertRaises(TypeError):
            verify(data, True)

    def test_e01_framing_vs_stale_checksum(self):
        sealed = journals("G1")[0]
        lines = sealed.split(b"\n")
        for n in (1, 3, 6):
            spaced = lines[:]
            spaced[n - 1] = spaced[n - 1].replace(b":", b": ", 1)
            self.fault(b"\n".join(spaced), "AU01", n, "")
            stale = lines[:]
            t = json.loads(stale[n - 1])
            key = {1: "fixture", 3: "previous", 6: "final"}[n]
            t[key] = "F01-v1-rough-standard" if n == 1 else "0" * 64
            stale[n - 1] = cjson(t)
            self.fault(b"\n".join(stale), "AU03", n, "/chain")
        bad_chain = lines[:]
        bad_chain[2] = bad_chain[2].replace(b'"chain":"', b'"chain":"Z', 1)
        self.fault(b"\n".join(bad_chain), "AU01", 3, "/chain")

    def test_e02_header(self):
        sealed = journals("G1")[0]
        cases = [
            ("fixture", "F01-v1-nowhere", "/fixture"),
            ("fixture", "F01-v1-rough-standard", "/genesis"),
            ("pair", "F01-v1-rough", "/pair"),
            ("pair", "F01-v1-open-standard", "/pair"),
            ("genesis", "0" * 64, "/genesis"),
            ("schema", "imperium.battle-audit/2", "/schema"),
            ("state_schema", "imperium.battle-state/2", "/state_schema"),
            ("rng", "D4-SHA256-v2", "/rng"),
            ("registry", "IMPERIUM-BK-2", "/registry"),
            ("run", {"seed": True, "replicate": 0}, "/run"),
            ("run", {"seed": 0, "replicate": -1}, "/run"),
            ("run", {"seed": 0}, "/run"),
            ("run", [0, 0], "/run"),
        ]
        for key, value, path in cases:
            with self.subTest(key=key, value=value):
                self.fault(rechain(sealed, lambda ts: ts[0].__setitem__(key, value)), "AU02", 1,
                           path)
        self.fault(rechain(sealed, lambda ts: ts[0].pop("rng")), "AU02", 1, "")
        self.fault(rechain(sealed, lambda ts: ts.insert(0, ts.pop(1))), "AU02", 1)

    def test_e02_replacement_run(self):
        for name in ("G0", "G1", "G4"):
            sealed = journals(name)[0]
            other = rechain(sealed, lambda ts: ts[0].__setitem__("run", {"seed": 1, "replicate": 3}))
            r = verify(other)
            self.assertEqual(r.run, (1, 3))
            self.assertEqual(E.replay(other), r)
            self.fault(other, "AU17", len(trees(other)), "", expected_chain=final_chain(sealed))
            self.assertEqual(other, E.BattleSession.open(CARRIERS[name][0], E.RunKey(1, 3))
                             .export_audit() if name == "G0" else session(name, E.RunKey(1, 3))
                             .export_audit())

    def test_e03_e04_duplicates_and_sequence(self):
        sealed = journals("G1")[0]
        lines = sealed.split(b"\n")
        dup = b"\n".join(lines[:3] + lines[2:])
        self.fault(dup, "AU03", 4, "/chain")
        self.fault(rechain(sealed, lambda ts: ts.insert(2, json.loads(cjson(ts[2])))), "AU04", 4,
                   "/cursor")

        def swap(ts):
            ts[2]["events"].reverse()
        self.fault(rechain(sealed, swap), "AU09", 3, "/events")

        def swap_bad_ordinal(ts):
            ts[2]["events"].reverse()
            ts[2]["events"][0]["id"] = "r1:S0.o2:IMMEDIATE_CHECK"
        self.fault(rechain(sealed, swap_bad_ordinal), "AU05", 3, "/events/0/id")

        def packet(ts):
            ts[2]["events"][0]["id"] = "r1:S0.o1:MELEE:S0.H1:S1.H1:-"
        self.fault(rechain(sealed, packet), "AU05", 3, "/events/0/id")

        def unknown_stage(ts):
            ts[2]["events"][0]["stage"] = "MELEE"
        self.fault(rechain(sealed, unknown_stage), "AU05", 3, "/events/0/stage")

        def disagree(ts):
            ts[2]["events"][0]["stage"] = "IMMEDIATE_CHECK"
        self.fault(rechain(sealed, disagree), "AU05", 3, "/events/0/id")

        def drop_check(ts):
            del ts[2]["events"][1]
        self.fault(rechain(sealed, drop_check), "AU09", 3, "/events")

    def test_e03_root_end_phase_family(self):
        rules = importlib.import_module("imperium.battle.audit.rules")
        trace = ("ROOT", "IMMEDIATE_CHECK")
        family = rules.TRACES[trace]
        with mock.patch.dict(rules.TRACES, {trace: (family[0], "Terminal")}):
            self.fault(journals("G1")[0], "AU09", 3, "/events")

    def test_e05_splices(self):
        g1, g2, g4 = journals("G1")[0], journals("G2")[0], journals("G4")[0]

        def foreign(ts):
            ts[3] = trees(g4)[3]
        self.fault(rechain(g1, foreign), "AU06", 4, "/previous")
        branch = chained(trees(g1)[:2] + trees(g2)[2:3])
        self.assertEqual(branch, journals("G2")[1])
        g1_prefix = chained(trees(g1)[:3])
        r = verify(branch, require_sealed=False)
        self.assertEqual(r.roots, 2)
        self.assertEqual(E.replay(branch, require_sealed=False), r)
        self.fault(branch, "AU17", 3, "", require_sealed=False, expected_chain=final_chain(g1_prefix))

    def test_e06_order_and_truncation(self):
        sealed, prefix = journals("G1")
        self.fault(rechain(sealed, lambda ts: ts.insert(2, ts.pop(3))), "AU04", 3, "/cursor")
        no_trailer = b"".join(l + b"\n" for l in sealed.split(b"\n")[:-2])
        self.assertEqual(no_trailer, prefix)
        self.fault(no_trailer, "AU16", 6, "")
        self.assertEqual(verify(no_trailer, require_sealed=False).roots, 4)
        short = b"".join(l + b"\n" for l in sealed.split(b"\n")[:3])
        self.fault(short, "AU16", 4, "")
        self.assertEqual(verify(short, require_sealed=False).roots, 2)
        header_only = sealed.split(b"\n")[0] + b"\n"
        self.assertEqual(verify(header_only, require_sealed=False).roots, 0)
        for cut in (10, len(sealed) - 5, len(short) + 7):
            self.fault(sealed[:cut], "AU01", sealed[:cut].count(b"\n") + 1, "")
            self.fault(sealed[:cut], "AU01", sealed[:cut].count(b"\n") + 1, "",
                       require_sealed=False)
        lines = sealed.split(b"\n")
        after = sealed + lines[2] + b"\n"
        self.fault(after, "AU16", 7, "")
        self.fault(sealed + b'{"a": 1}\n', "AU01", 7, "")

    def test_e07_e08_effects(self):
        sealed = journals("G1")[0]

        def old_alone(ts):
            ts[2]["events"][0]["effects"][0]["old"] = 7
        self.fault(rechain(sealed, old_alone), "AU08", 3, "/events/0/effects/0/old")

        def zero_false(ts):
            ts[1]["events"][0]["effects"][0]["old"] = False
        self.fault(rechain(sealed, zero_false), "AU08", 2, "/events/0/effects/0/old")

        def bad_path_and_old(ts):
            f = ts[2]["events"][0]["effects"][0]
            f["path"], f["old"] = "/clock/missing", 99
        self.fault(rechain(sealed, bad_path_and_old), "AU07", 3, "/events/0/effects/0/path")

        def swap_order(ts):
            ts[4]["events"][7]["effects"].reverse()
        self.assertEqual(len(trees(sealed)[4]["events"][7]["effects"]), 2)
        self.fault(rechain(sealed, swap_order), "AU07", 5, "/events/7/effects/1/path")

        def overlap(ts):
            effs = ts[4]["events"][7]["effects"]
            effs.insert(0, {"path": "/ledger", "old": None, "new": None})
        e = self.fault(rechain(sealed, overlap), "AU07", 5)
        self.assertTrue(e.path.startswith("/events/7/effects/"), e.path)

        def schema_path(ts):
            ts[1]["events"][0]["effects"].append({"path": "/schema", "old": "imperium.battle-state/1",
                                                  "new": "x"})
        self.fault(rechain(sealed, schema_path), "AU07", 2, "/events/0/effects/1/path")

        def cursor_wrong_stage(ts):
            ts[2]["events"][1]["effects"].insert(0, {"path": "/clock/event_cursor", "old": 2,
                                                     "new": 3})
        self.fault(rechain(sealed, cursor_wrong_stage), "AU07", 3, "/events/1/effects/0/path")

        def whole_value(ts):
            ev = ts[4]["events"][7]
            self.assertEqual(ev["stage"], "OPEN_ROUND")
            self.assertEqual(ev["effects"][1]["path"], "/phase/side")
            ev["effects"][1] = {"path": "/phase", "old": {"kind": "AwaitingPrincipal", "side": "S0"},
                                "new": {"kind": "AwaitingPrincipal", "side": "S1"}}
        self.fault(rechain(sealed, whole_value), "AU07", 5, "/events/7/effects")

        def check_data(ts):
            ts[2]["events"][1]["data"]["result"] = "TERMINAL"
        self.fault(rechain(sealed, check_data), "AU10", 3, "/events/1/data")

        def omit_advance(ts):
            ts[4]["events"][5]["effects"] = []
        self.fault(rechain(sealed, omit_advance), "AU10", 5, "/events/5/effects")

        def wrong_cursor_delta(ts):
            ts[2]["events"][0]["effects"][0]["new"] = 3
        self.fault(rechain(sealed, wrong_cursor_delta), "AU10", 3, "/events/0/effects")

        g3 = journals("G3")[0]

        def terminal_data(ts):
            ts[2]["events"][2]["data"]["record"]["charged_rounds"] = 2
        self.fault(rechain(g3, terminal_data), "AU10", 3, "/events/2/data")

    def test_e08_numeric_segment_order(self):
        data = capitulate_s1()
        effects = trees(data)[3]["events"][0]["effects"]
        paths = [f["path"] for f in effects if f["path"].startswith("/formations/")]
        self.assertEqual(paths, [f"/formations/{i}/disposition" for i in range(8, 16)])
        self.assertEqual(verify(data).roots, 3)

        def string_sort(ts):
            ts[3]["events"][0]["effects"].sort(key=lambda f: f["path"])
        e = self.fault(rechain(data, string_sort), "AU07", 4)
        self.assertTrue(e.path.endswith("/path"), e.path)

    def test_e09_draws_and_packet(self):
        sealed = journals("G1")[0]

        def draws(ts):
            ts[2]["events"][1]["draws"] = [{"channel": "injury", "index": 0, "numerator": 1}]
        self.fault(rechain(sealed, draws), "AU13", 3, "/events/1/draws")

        def draws_bad_shape(ts):
            ts[2]["events"][1]["draws"] = [None]
        self.fault(rechain(sealed, draws_bad_shape), "AU13", 3, "/events/1/draws")

    def test_e10_after_terminal(self):
        g3 = journals("G3")[1]
        ts = trees(g3)
        root = json.loads(cjson(trees(journals("G1")[0])[3]))
        root.update(cursor=3, previous=ts[-1]["current"])
        self.fault(chained(ts + [root]), "AU11", 4, "", require_sealed=False)
        g4 = trees(journals("G4")[1])
        root.update(cursor=26, previous=g4[-1]["current"])
        self.fault(chained(g4 + [root]), "AU11", 27, "", require_sealed=False)

    def test_e10_command_binding(self):
        sealed = journals("G1")[0]

        def open_again(ts):
            ts[2]["command"] = {"kind": "OpenBattle", "schema": "imperium.battle-command/1"}
            ts[2]["command_digest"] = sha(cjson(ts[2]["command"]))
        self.fault(rechain(sealed, open_again), "AU04", 3, "/command/kind")

        def wrong_side(ts):
            ts[2]["command"]["side"] = "S1"
            ts[2]["command_digest"] = sha(cjson(ts[2]["command"]))
        self.fault(rechain(sealed, wrong_side), "AU04", 3, "/command/side")

        def stale_digest(ts):
            ts[2]["command_digest"] = "0" * 64
        self.fault(rechain(sealed, stale_digest), "AU04", 3, "/command_digest")

        def principal_at_opening(ts):
            ts[1]["command"] = {"kind": "PassOrder", "schema": "imperium.battle-command/1",
                                "side": "S0"}
            ts[1]["command_digest"] = sha(cjson(ts[1]["command"]))
        self.fault(rechain(sealed, principal_at_opening), "AU04", 2, "/command/kind")

        def current(ts):
            ts[2]["current"] = "1" * 64
        self.fault(rechain(sealed, current), "AU14", 3, "/current")

        def cursor_type(ts):
            ts[2]["cursor"] = "2"
        self.fault(rechain(sealed, cursor_type), "AU04", 3, "/cursor")

        def bool_cursor(ts):
            ts[1]["cursor"] = True
        self.fault(rechain(sealed, bool_cursor), "AU04", 2, "/cursor")

        def kind(ts):
            ts[2]["kind"] = "event"
        self.fault(rechain(sealed, kind), "AU04", 3, "/kind")

        def origins(ts):
            ts[2]["events"][0]["effects"].append(
                {"path": "/personnel/0/origin", "old": None, "new": "r1:S0.o1:ROOT"})
            ts[2]["current"] = "0" * 64
        self.fault(rechain(sealed, origins), "AU12", 3, "/events")

    def test_e11_trailer_fields(self):
        sealed = journals("G1")[0]
        n = len(trees(sealed))
        for key, value in (("roots", 5), ("cursor", 3), ("final", "0" * 64), ("terminal", True),
                           ("draws", 1), ("roots", True), ("terminal", 0)):
            with self.subTest(key=key, value=value):
                self.fault(rechain(sealed, lambda ts: ts[-1].__setitem__(key, value)), "AU16", n,
                           f"/{key}")
        self.fault(rechain(sealed, lambda ts: ts[-1]["stages"].__setitem__("ROOT", 4)), "AU16", n,
                   "/stages/ROOT")
        self.fault(rechain(sealed, lambda ts: ts[-1]["stages"].pop("ROOT")), "AU16", n, "/stages")
        self.fault(rechain(sealed, lambda ts: ts[-1].pop("draws")), "AU16", n, "")

    def test_e11_wire(self):
        sealed = journals("G1")[0]
        head = sealed.split(b"\n")[0]
        for data in (b"", b"\n", b"\r\n", head + b"\r\n", b"\xef\xbb\xbf" + sealed,
                     sealed.replace(b"\n", b"\n\n", 1), head, b" " + sealed):
            with self.subTest(data=data[:30]):
                self.fault(data, "AU01", 1 if not data.startswith(head + b"\n") else 2, "")
        t = json.loads(head)
        dupe = cjson(t)[:-1] + b',"kind":"header"}' + b"\n"
        self.fault(dupe, "AU01", 1, "")
        for token in (b"1.0", b"1e3", b"NaN", b"Infinity", b"-0", b"9223372036854775808",
                      b'"\\ud800"', b"01"):
            with self.subTest(token=token):
                line = cjson({**t, "run": None})[:-1] + b',"x":' + token + b"}\n"
                self.fault(line, "AU01", 1, "")
        self.fault(b'{"a":' * 33 + b"1" + b"}" * 33 + b"\n", "AU01", 1, "")
        # Depth 32 (the root counts as 1) passes the depth scan and fails only on the chain.
        self.fault(b'{"a":' * 32 + b"1" + b"}" * 32 + b"\n", "AU01", 1, "/chain")
        chain = b',"chain":"' + b"0" * 64 + b'"}'
        pad = 1024 * 1024 - len(b'{"a":""') - len(chain)
        exact = b'{"a":"' + b"x" * pad + b'"' + chain
        self.assertEqual(len(exact), 1024 * 1024)
        self.fault(exact + b"\n", "AU03", 1, "/chain")
        over = b'{"a":"' + b"x" * (pad + 1) + b'"' + chain
        self.fault(over + b"\n", "AU01", 1, "")


class Guard(unittest.TestCase):

    def test_d02_ast_guard(self):
        """G-P3-1: no engine, queries or legacy resolver/RNG import in the audit package."""
        for path in sorted(AUDIT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    if node.level:
                        base = "imperium.battle.audit." + base
                    names = [base] + [f"{base}.{a.name}" for a in node.names]
                elif isinstance(node, ast.Name) and node.id in ("importlib", "__import__"):
                    self.fail(f"{path.name}: dynamic import")
                elif isinstance(node, ast.Attribute) and node.attr == "import_module":
                    self.fail(f"{path.name}: dynamic import")
                for n in names:
                    self.assertFalse(n.startswith("imperium.battle.engine"), (path.name, n))
                    self.assertFalse(n.startswith("imperium.battle.queries"), (path.name, n))
                    self.assertNotIn(n.split(".")[0:2], (["imperium", "randomness"],
                                                         ["imperium", "legacy"]), (path.name, n))
                    if n.startswith("imperium.") and not n.startswith("imperium.battle"):
                        self.fail((path.name, n))
                    self.assertFalse(n.startswith("tests"), (path.name, n))


if __name__ == "__main__":
    unittest.main()
