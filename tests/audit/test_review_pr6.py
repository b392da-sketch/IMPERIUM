"""Regression oracles for the PR #6 independent implementation review
(P3-IMP-01 to P3-IMP-04 and P3-IMP-06).

Each witness is a canonical, rechained journal built from real P3 output,
so it reaches the fault under test with valid hashes.
"""

import copy
import importlib
import json
import random
import unittest

import imperium.battle as B
from imperium.battle import audit
from imperium.battle import engine as E
from imperium.battle.audit import AuditError, verify
from tests.audit.support import RUN0, S0, S1, STANDARD, chained, cjson, journals, sha, trees

INT_MIN = -(2 ** 63 - 1)


def journal(commands):
    s = E.BattleSession.open(STANDARD, RUN0)
    for c in commands:
        assert type(s.submit(c)) is E.Accepted
    return s, trees(s.export_audit(seal=False))


def add_effect(event, effect):
    event["effects"].append(effect)
    event["effects"].sort(key=lambda f: f["path"])


def set_new(event, path, value):
    (f,) = [f for f in event["effects"] if f["path"] == path]
    f["new"] = value


HOLD = [E.OpenBattle(), E.HoldOrder(S0, B.FormationId("S0.H1"))]


class Review(unittest.TestCase):

    def fault(self, ts, code, line, path=None, endswith=None):
        with self.assertRaises(AuditError) as cm:
            verify(chained(ts), require_sealed=False)
        e = cm.exception
        self.assertEqual((e.code, e.line), (code, line), str(e))
        if path is not None:
            self.assertEqual(e.path, path, str(e))
        if endswith is not None:
            self.assertTrue(e.path.endswith(endswith), str(e))
        return e

    # ------------------------------------------------------------ IMP-01

    def test_imp01_hold_cannot_change_fatigue(self):
        s, ts = journal(HOLD)
        alt = B.encode_state(s.state)
        self.assertEqual(alt["formations"][0]["condition"]["fatigue"], 0)
        alt["formations"][0]["condition"]["fatigue"] = 1
        add_effect(ts[2]["events"][0], {"path": "/formations/0/condition/fatigue", "old": 0,
                                        "new": 1})
        ts[2]["current"] = B.digest(B.decode_state(alt))  # P1 accepts the altered state
        e = self.fault(ts, "AU07", 3)
        effects = ts[2]["events"][0]["effects"]
        j = [f["path"] for f in effects].index("/formations/0/condition/fatigue")
        self.assertEqual(e.path, f"/events/0/effects/{j}/path")
        with self.assertRaises(AuditError):
            E.replay(chained(ts), require_sealed=False)

    def test_imp01_command_scoped_root_paths(self):
        cases = [
            # Hold/Pass may not touch the round's formation ledger.
            (HOLD, "/ledger/formations/0/exerted", False, True),
            (HOLD, "/sides/0/posture", "CONTESTING", "WITHDRAWING"),
            ([E.OpenBattle(), E.PassOrder(S0)], "/personnel/0/status", "AVAILABLE", "CAPTURED"),
            # Withdrawal: only the acting side's posture.
            ([E.OpenBattle(), E.DeclareWithdrawal(S0)], "/sides/1/posture", "CONTESTING",
             "WITHDRAWING"),
        ]
        for commands, path, old, new in cases:
            with self.subTest(path=path, command=type(commands[-1]).__name__):
                _, ts = journal(commands)
                if path.startswith("/ledger/formations"):
                    (row,) = [f for f in ts[1]["events"][1]["effects"][0]["new"]["formations"]][:1]
                    old, new = row["exerted"], not row["exerted"]
                add_effect(ts[2]["events"][0], {"path": path, "old": old, "new": new})
                self.fault(ts, "AU07", 3, endswith="/path")
        # Capitulate may change custody fields but not the ledger or postures.
        for path, old, new in (("/ledger/uses", [], [1]), ("/sides/0/posture", "CONTESTING",
                                                           "WITHDRAWING")):
            with self.subTest(capitulate=path):
                _, ts = journal([E.OpenBattle(), E.Capitulate(S0)])
                add_effect(ts[2]["events"][0], {"path": path, "old": old, "new": new})
                self.fault(ts, "AU07", 3, endswith="/path")

    def test_imp01_h02_open_round_latch_still_structural(self):
        """The permitted OPEN_ROUND latch change still verifies structurally (TA-H02)."""
        from tests.audit.test_replay import Replay
        Replay("test_h02_safe_latch_witness").test_h02_safe_latch_witness()

    # ------------------------------------------------------------ IMP-02

    def test_imp02_wrong_containers(self):
        _, ts = journal([E.OpenBattle()])
        set_new(ts[1]["events"][1], "/phase", None)
        self.fault(ts, "AU10", 2, "/events/1/effects")
        _, ts = journal(HOLD)
        set_new(ts[2]["events"][0], "/ledger/uses", None)
        self.fault(ts, "AU10", 3, "/events/0/effects")
        _, ts = journal(HOLD)
        opening = trees(journals("G1")[0])[1]["events"][1]["effects"][0]["new"]
        ts[2]["events"][0]["effects"] = [f for f in ts[2]["events"][0]["effects"]
                                         if f["path"] != "/ledger/uses"]
        add_effect(ts[2]["events"][0], {"path": "/ledger", "old": opening, "new": None})
        self.fault(ts, "AU07", 3, endswith="/path")
        _, ts = journal([E.OpenBattle(), E.DeclareWithdrawal(S0)])
        set_new(ts[2]["events"][0], "/sides/0/posture", None)
        self.fault(ts, "AU10", 3, "/events/0/effects")
        _, ts = journal([E.OpenBattle(), E.Capitulate(S0)])
        ev = ts[2]["events"][2]
        set_new(ev, "/phase", 7)
        self.fault(ts, "AU10", 3, "/events/2/effects")

    def test_imp02_array_index_syntax(self):
        for seg in ("²", "٠", "9" * 4301, "9" * 20, "01", "-1", "+1", " 1", "1 "):
            with self.subTest(seg=seg[:8]):
                _, ts = journal(HOLD)
                add_effect(ts[2]["events"][0], {"path": f"/formations/{seg}/condition/fatigue",
                                                "old": 0, "new": 1})
                self.fault(ts, "AU07", 3, endswith="/path")

    def test_imp02_direct_records(self):
        cases = [("/ledger/uses/²", "T16", "path"), ("/formations/" + "9" * 4301, "T16", "path"),
                 ("/formations/" + "9" * 20, "T16", "path"), ("/café", "T16", "path")]
        for path, code, where in cases:
            with self.subTest(path=path[:20]):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.Effect(path, b"0", b"1")
                self.assertEqual((cm.exception.clause, cm.exception.path), (code, where))
        ok = E.Effect("/formations/" + "9" * 19, b"0", b"1")
        E.StageEvent(E.Stage.ROOT, "r1:S0.o1:ROOT", b"{}", (E.Effect("/a/2", b"0", b"1"),
                                                             E.Effect("/a/10", b"0", b"1"), ok), ())

    def test_imp02_fuzz_effect_values(self):
        """No malformed effect value escapes the diagnostic boundary."""
        junk = (None, 0, -1, True, "x", [], {}, [None], {"kind": None})
        rng = random.Random(6)
        for name in ("G1", "G2", "G3"):
            base = trees(journals(name)[1])
            spots = [(r, i, j) for r in range(1, len(base)) for i, ev in
                     enumerate(base[r]["events"]) for j in range(len(ev["effects"]))]
            for r, i, j in rng.sample(spots, min(len(spots), 40)):
                for value in junk:
                    ts = copy.deepcopy(base)
                    ts[r]["events"][i]["effects"][j]["new"] = value
                    try:
                        verify(chained(ts), require_sealed=False)
                    except AuditError:
                        pass
                    ts = copy.deepcopy(base)
                    ts[r]["events"][i]["data"] = {"junk": value}
                    with self.assertRaises(AuditError):
                        verify(chained(ts), require_sealed=False)

    # ------------------------------------------------------------ IMP-03

    def test_imp03_signed_domain(self):
        _, ts = journal(HOLD)
        line = cjson({**ts[0], "run": {"seed": -(2 ** 63), "replicate": 0}})
        with self.assertRaises(AuditError) as cm:
            verify(line + b"\n", require_sealed=False)
        self.assertEqual((cm.exception.code, cm.exception.line), ("AU01", 1))
        for value, code in ((INT_MIN, "AU02"), (-1, "AU02"), (2 ** 63, "AU01"),
                            (-(2 ** 63), "AU01")):
            with self.subTest(value=value):
                bad = copy.deepcopy(ts)
                bad[0]["run"]["seed"] = value
                with self.assertRaises(AuditError) as cm:
                    verify(chained(bad), require_sealed=False)
                self.assertEqual((cm.exception.code, cm.exception.line), (code, 1))
        top = copy.deepcopy(ts)
        top[0]["run"]["seed"] = 2 ** 63 - 1  # the exact upper edge is a valid run
        self.assertEqual(verify(chained(top), require_sealed=False).run, (2 ** 63 - 1, 0))
        _, ts = journal([E.OpenBattle()])
        set_new(ts[1]["events"][1], "/phase", -(2 ** 63))
        with self.assertRaises(AuditError) as cm:
            verify(chained(ts), require_sealed=False)
        self.assertEqual((cm.exception.code, cm.exception.line), ("AU01", 2))

    def test_imp03_direct_records(self):
        for raw in (b"-9223372036854775808", b"9223372036854775808", b'"\\ud800"',
                    b'{"\\udfff":1}', b'["\\ud800\\udc00x\\ud800"]'):
            with self.subTest(raw=raw):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.Effect("/phase", raw, b"null")
                self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "old"))
        for raw in (b"-9223372036854775807", b"9223372036854775807", b'"\\ud83d\\ude00"'):
            E.Effect("/phase", raw, b"null")
        for raw in (b'"\\ud800"', b'{"\\ud800":1}'):
            with self.assertRaises(AuditError) as cm:
                verify(b'{"a":' + raw + b"}\n")
            self.assertEqual(cm.exception.code, "AU01")

    # ------------------------------------------------------------ IMP-04

    def test_imp04_typed_old_before_noop(self):
        _, ts = journal(HOLD)
        (f,) = [f for f in ts[2]["events"][0]["effects"] if f["path"] == "/clock/event_cursor"]
        self.assertEqual(f["old"], 1)
        f["old"] = f["new"] = True
        self.fault(ts, "AU08", 3, "/events/0/effects/0/old")
        # An accurate old with a true no-op is still AU07 at its ``new``.
        _, ts = journal([E.OpenBattle(), E.Capitulate(S0)])
        add_effect(ts[2]["events"][0], {"path": "/formations/0/condition/fatigue", "old": 0,
                                        "new": 0})
        j = [x["path"] for x in ts[2]["events"][0]["effects"]].index(
            "/formations/0/condition/fatigue")
        self.fault(ts, "AU07", 3, f"/events/0/effects/{j}/new")

    # ------------------------------------------------------------ IMP-06

    def test_imp06_public_surface(self):
        self.assertEqual(sorted(audit.__all__), sorted(
            ["verify", "AuditReport", "AuditError", "check_draw_records", "DrawRecordError"]))
        self.assertEqual(sorted(n for n in dir(E.BattleSession) if not n.startswith("_")),
                         ["export_audit", "journal", "open", "pending", "state", "submit"])


if __name__ == "__main__":
    unittest.main()
