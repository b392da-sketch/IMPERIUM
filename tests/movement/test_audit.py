"""TA-P4-K03 to K05, E03 and E04: v2 verification, exact first faults,
version selection, the stage-id grammars, replay RP01 and RP02.

Adversarial journals are made by editing a genuine export's line trees
and rechaining them test-side (tests.audit.support.rechain).
"""

import json
import sys
import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import AuditError, verify
from imperium.battle.engine import draws as D
from tests.audit.support import cjson, rechain, trees
from tests.movement.support import P2_STAGE_NAMES, P4_STAGE_NAMES, STANDARD, run_carrier

replay_module = sys.modules["imperium.battle.engine.replay"]
RUN0 = E.RunKey(0, 0)
V1 = ("imperium.battle-audit/1", "imperium.battle-event/1")
V2 = ("imperium.battle-audit/2", "imperium.battle-event/2")


def export(name, seal=True):
    return run_carrier(name).export_audit(seal=seal)


def old_history(seal=True):
    s = E.BattleSession.open(STANDARD)
    s.submit(E.OpenBattle())
    s.submit(E.HoldOrder(B.Side.S0, B.FormationId("S0.H1")))
    return s.export_audit(seal=seal)


def event(ts, line, stage):
    return [e for e in ts[line - 1]["events"] if e["stage"] == stage][0]


def key(path):
    return [int(p) if p.isdigit() else p for p in path[1:].split("/")]


class Base(unittest.TestCase):

    def fault(self, data, code, line, path=None, **kw):
        with self.assertRaises(AuditError) as cm:
            verify(data, **kw)
        e = cm.exception
        self.assertEqual((e.code, e.line), (code, line), str(e))
        if path is not None:
            self.assertEqual(e.path, path, str(e))
        return e


class K03Verify(Base):

    def test_sealed_and_prefix_carriers(self):
        for name in ("G5", "G6", "G7", "G8", "G9", "GT15"):
            for seal in (True, False):
                data = export(name, seal)
                report = verify(data, require_sealed=seal)
                self.assertEqual(report.sealed, seal)
                self.assertEqual(dict(report.stages).keys() if type(report.stages) is dict else
                                 {k for k, _ in report.stages},
                                 set(P2_STAGE_NAMES) | set(P4_STAGE_NAMES))
                E.replay(data, require_sealed=seal)

    def test_trailer_has_twenty_keys(self):
        t = trees(export("G7"))[-1]
        self.assertEqual(sorted(t["stages"]), sorted(P2_STAGE_NAMES + P4_STAGE_NAMES))
        self.assertEqual(t["stages"]["WINDOW"], 1)
        self.assertEqual(t["stages"]["STEP2"], 0)


class E03FirstFault(Base):

    def setUp(self):
        self.g7 = export("G7")       # line 8 is the windowed root

    def test_forbidden_path_with_wrong_old_is_au07(self):
        def mutate(ts):
            e = event(ts, 8, "STEP1")
            e["effects"].insert(0, {"path": "/clock/completed_rounds", "old": 9, "new": 2})
        self.fault(rechain(self.g7, mutate), "AU07", 8, "/events/1/effects/0/path")

    def test_typed_old_on_allowed_path_is_au08(self):
        def mutate(ts):
            e = event(ts, 8, "STEP1")
            e["effects"][1]["old"] = True
        self.fault(rechain(self.g7, mutate), "AU08", 8, "/events/1/effects/1/old")

    def test_latch_false_to_true_is_au07(self):
        def mutate(ts):
            e = event(ts, 8, "RESPONSE")
            e["effects"].append({"path": "/ledger/formations/7/safe_latch", "old": False,
                                 "new": True})
            e["effects"].sort(key=lambda x: key(x["path"]))
        e = self.fault(rechain(self.g7, mutate), "AU07", 8)
        self.assertTrue(e.path.startswith("/events/3/effects/"), e.path)

    def test_duplicate_window_id_is_au05(self):
        def mutate(ts):
            event(ts, 8, "RESPONSE")["id"] = "r2:S0.o1:WINDOW"
        self.fault(rechain(self.g7, mutate), "AU05", 8, "/events/3/id")

    def test_window_in_pivot_trace_is_au09(self):
        ts = trees(self.g7)
        line = [i + 1 for i, t in enumerate(ts)
                if t.get("kind") == "root" and t["command"]["kind"] == "PivotOrder"][0]
        root_id = ts[line - 1]["events"][0]["id"].rsplit(":", 1)[0]

        def mutate(ts):
            window = json.loads(cjson(event(ts, 8, "WINDOW")))
            window["id"] = root_id + ":WINDOW"
            ts[line - 1]["events"].insert(2, window)
        self.fault(rechain(self.g7, mutate), "AU09", line, "/events")

    def test_wrong_window_id_is_au10(self):
        def mutate(ts):
            data = event(ts, 8, "WINDOW")["data"]
            data["window_id"] = "0" * 64
            data["decision"]["window_id"] = "0" * 64
        self.fault(rechain(self.g7, mutate), "AU10", 8, "/events/2/data")

    def test_unoffered_decision_is_au10(self):
        def mutate(ts):
            event(ts, 8, "WINDOW")["data"]["decision"]["formation"] = "S1.H3"
        self.fault(rechain(self.g7, mutate), "AU10", 8, "/events/2/data")

    def test_respond_missile_is_au10(self):
        g6 = export("G6")

        def mutate(ts):
            data = event(ts, 5, "WINDOW")["data"]
            data["decision"] = {"formation": "S1.L1", "kind": "RespondMissile",
                                "schema": "imperium.battle-command/1", "side": "S1",
                                "target": "S0.L1", "window_id": data["window_id"]}
        self.fault(rechain(g6, mutate), "AU10", 5, "/events/2/data")


class E04Versions(Base):

    def test_v1_root_with_p4_command_is_au04(self):
        def mutate(ts):
            ts[0]["schema"], ts[0]["event_schema"] = V1
        self.fault(rechain(export("G8"), mutate), "AU04", 3, "/command/kind")

    def test_v1_root_with_p4_stage_is_au05(self):
        def mutate(ts):
            ts[2]["events"][0]["stage"] = "STEP1"
        self.fault(rechain(old_history(), mutate), "AU05", 3, "/events/0/stage")

    def test_mismatched_schema_pair_is_au02(self):
        def mutate(ts):
            ts[0]["event_schema"] = V1[1]
        self.fault(rechain(export("G8"), mutate), "AU02", 1, "/event_schema")

    def test_v2_without_p4_root_is_au16(self):
        for seal in (True, False):
            data = old_history(seal)

            def mutate(ts):
                ts[0]["schema"], ts[0]["event_schema"] = V2
                if seal:
                    for name in P4_STAGE_NAMES:
                        ts[-1]["stages"][name] = 0
            bad = rechain(data, mutate)
            self.fault(bad, "AU16", len(trees(bad)) + 1, "", require_sealed=seal)

    def test_v2_prefix_cut_before_first_p4_root(self):
        data = export("G5", seal=False)
        ts = trees(data)
        self.assertEqual(ts[2]["command"]["kind"], "GroupMoveOrder")
        cut = rechain(data, lambda ts: ts.__delitem__(slice(2, None)))
        self.assertEqual(len(trees(cut)), 2)
        self.fault(cut, "AU16", 3, "", require_sealed=False)

    def test_g5_upgrade(self):
        s = E.BattleSession.open(STANDARD)
        s.submit(E.OpenBattle())
        v1 = s.export_audit(seal=False)
        self.assertEqual(tuple(trees(v1)[0][k] for k in ("schema", "event_schema")), V1)
        g5 = run_carrier("G5")
        v2 = g5.export_audit(seal=False)
        self.assertEqual(tuple(trees(v2)[0][k] for k in ("schema", "event_schema")), V2)
        old_root, new_root = trees(v1)[1], trees(v2)[1]
        for k in ("command", "command_digest", "previous", "current", "cursor"):
            self.assertEqual(old_root[k], new_root[k])
        self.assertNotEqual(old_root["chain"], new_root["chain"])
        verify(v1, require_sealed=False)
        verify(v2, require_sealed=False)


class K05StageIds(unittest.TestCase):

    def test_ids_and_grammars(self):
        seen = {}
        for name in ("G5", "G6", "G7", "G8", "G9", "GT15"):
            for t in trees(export(name))[1:-1]:
                for e in t["events"]:
                    seen.setdefault(e["stage"], e["id"])
        for stage in ("STEP1", "WITHDRAW", "GROUP_STEP", "PIVOT", "GROUP_PIVOT", "EVACUATE",
                      "WINDOW", "RESPONSE"):
            self.assertRegex(seen[stage], r"^r[0-9]+:S[01]\.o[1-4]:" + stage + "$")
        self.assertEqual(seen["WINDOW"].split(":")[0], "r1")
        with mock.patch.object(D.hashlib, "sha256", side_effect=AssertionError("hashed")):
            for name in P4_STAGE_NAMES:
                stage_id = "r1:S0.o1:" + name
                with self.assertRaises(B.InvalidValue) as cm:
                    E.draw_numerator(RUN0, "F01-v1-open", stage_id, E.Channel.injury, 0)
                self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "stage_id"))
                with self.assertRaises(B.InvalidValue) as cm:
                    E.parse_stage_id(stage_id)
                self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "stage_id"))
        state = run_carrier("G8").state
        from imperium.battle.records import STATE_FIELDS
        from imperium.battle.state import state_values
        values = tuple(state_values(state))
        self.assertEqual(len(values), len(STATE_FIELDS))
        for name in P4_STAGE_NAMES:
            snap = E.StageSnapshot(E.Stage[name], "r1:S0.o1:" + name, values)
            self.assertEqual(snap.stage_id, "r1:S0.o1:" + name)


class K04Replay(Base):

    def test_forged_options_pass_refold_fail_replay(self):
        g6 = export("G6")

        def mutate(ts):
            options = event(ts, 5, "WINDOW")["data"]["options"]
            options.insert(0, {"formation": "S1.H4", "kind": "DEFENSIVE_PIVOT",
                               "target": "S0.L1"})
        forged = rechain(g6, mutate)
        verify(forged)
        with self.assertRaises(E.ReplayError) as cm:
            E.replay(forged)
        self.assertEqual((cm.exception.code, cm.exception.line), ("RP01", 5))

    def test_rp02_missing_decision(self):
        data = export("G7")
        with mock.patch.object(replay_module, "recorded_decision", return_value=None):
            with self.assertRaises(E.ReplayError) as cm:
                E.replay(data)
        self.assertEqual((cm.exception.code, cm.exception.line), ("RP02", 8))

    def test_rp02_unusable_and_rejected_decision(self):
        data = export("G7")
        for doc in ({"kind": "Nope"},
                    {"kind": "HoldOrder", "schema": "imperium.battle-command/1", "side": "S1",
                     "formation": "S1.H1"},
                    {"kind": "DeclineResponse", "schema": "imperium.battle-command/1",
                     "side": "S1", "window_id": "0" * 64}):
            with mock.patch.object(replay_module, "recorded_decision", return_value=doc):
                with self.assertRaises(E.ReplayError) as cm:
                    E.replay(data)
            self.assertEqual((cm.exception.code, cm.exception.line), ("RP02", 8), doc)

    def test_au_errors_propagate_first(self):
        def mutate(ts):
            event(ts, 8, "WINDOW")["data"]["decision"]["formation"] = "S1.H3"
        with self.assertRaises(AuditError) as cm:
            E.replay(rechain(export("G7"), mutate))
        self.assertEqual(cm.exception.code, "AU10")


if __name__ == "__main__":
    unittest.main()
