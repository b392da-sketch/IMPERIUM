"""TA-P4-K02, L01, E01 (use lifetime), F01, F04, F06, G01 (G8), H02-H03
(G9) and J03/J04 carrier observations.

Every root's cursor and full state digest, every window's trigger, option
and token, and the selected final fields come from Codex's pinned
CARRIER_ORACLES.json. The GT15 arithmetic is written out from the design's
independent table.
"""

import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.audit import verify
from tests.engine.helpers import hold_use
from tests.movement.support import (
    S0, S1, STANDARD, MovementCase, carriers, cjson, doc, fid, gm, run_carrier, state_of,
    window_hash,
)


def decode(tree):
    return E.decode_command(cjson(tree))


def subset(document, keys):
    return {k: document[k] for k in keys}


class K02Carriers(unittest.TestCase):

    def test_every_root_digest_and_window(self):
        for name, case in carriers().items():
            with self.subTest(carrier=name):
                s = E.BattleSession.open(STANDARD)
                for row in case["roots"]:
                    base = s.state
                    command = decode(row["command"])
                    r = s.submit(command)
                    if "decision" in row:
                        self.assertIs(type(r), E.Suspended)
                        w = r.root.window
                        self.assertEqual(w.after, row["window_after"])
                        self.assertEqual([E.encode_command(decode(row["decision"]))["window_id"]],
                                         [w.window_id])
                        self.assertEqual(w.window_id,
                                         window_hash(B.digest(base), command, w.after))
                        option = row["window_option"]
                        self.assertIn((option["formation"], option["kind"], option["target"]),
                                      [(o.formation.token, o.kind.name, o.target.token)
                                       for o in w.options])
                        self.assertIs(s.pending, r.root)
                        r = s.submit(decode(row["decision"]))
                    else:
                        self.assertNotIn("window_after", row)
                    self.assertIs(type(r), E.Accepted, msg=repr(r)[:300])
                    self.assertIsNone(s.pending)
                    self.assertEqual(s.state.clock.event_cursor, row["cursor"])
                    self.assertEqual(B.digest(s.state), row["full_state_digest"])
                final = B.encode_state(s.state)
                self.assertEqual(subset(final, case["final"]), case["final"])

    def test_carriers_verify_and_replay(self):
        for name in carriers():
            with self.subTest(carrier=name):
                s = run_carrier(name)
                for seal in (True, False):
                    data = s.export_audit(seal=seal)
                    report = verify(data, require_sealed=seal)
                    self.assertEqual(report.roots, len(carriers()[name]["roots"]))
                    self.assertEqual(E.replay(data, require_sealed=seal).final,
                                     B.digest(s.state))
                header = s.export_audit().split(b"\n")[0]
                self.assertIn(b'"schema":"imperium.battle-audit/2"', header)
                self.assertIn(b'"command_schema":"imperium.battle-command/1"', header)


class L01GT15(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.case = carriers()["GT15"]
        cls.pre = run_carrier("GT15", upto=8)
        cls.done = run_carrier("GT15")

    def test_pre_last_hold_full_document(self):
        self.assertEqual(B.encode_state(self.pre.state), self.case["pre_last_hold"])

    def test_independent_arithmetic(self):
        st = self.pre.state
        want = {
            "S0.H1": ((2, 5), 4), "S0.H2": ((3, 5), 4), "S0.H5": ((3, 6), 4),
            "S0.L1": ((5, 4), 4), "S0.C1": ((1, 5), 4), "S0.H3": ((4, 6), 5),
            "S0.H4": ((5, 6), 5), "S0.H6": ((4, 7), 5),
            "S1.H1": ((8, 3), 1), "S1.H2": ((7, 3), 1), "S1.H5": ((7, 2), 1),
            "S1.L1": ((6, 3), 1), "S1.C1": ((9, 2), 1), "S1.H3": ((6, 2), 2),
            "S1.H4": ((5, 2), 2), "S1.H6": ((6, 1), 2),
        }
        cells = set()
        for token, (cell, facing) in want.items():
            g = B.formation(st, fid(token))
            self.assertEqual((g.cell, g.facing), (B.Hex(*cell), facing), token)
            self.assertEqual(g.condition.fatigue, 0)
            marked = token.startswith("S0") or token not in ("S1.L1", "S1.C1")
            self.assertEqual(g.condition.exertion, 1 if marked else 0, token)
            cells.add(g.cell)
        self.assertEqual(len(cells), 16)
        uses = st.ledger.uses
        self.assertEqual(sum(u.side is S0 for u in uses), 4)
        self.assertEqual(sum(u.side is S1 for u in uses), 3)
        for side in ("S0", "S1"):
            carried = sum(a.carried for a in st.ammunition if a.custodian.name == side)
            self.assertEqual(carried, 16, side)
        l1 = [a for a in st.ammunition if a.formation == fid("S0.L1")]
        self.assertEqual(sum(a.carried for a in l1), 4)
        latches = {r.formation.token: r.safe_latch for r in st.ledger.formations}
        self.assertFalse(latches["S0.L1"])
        self.assertFalse(latches["S1.L1"])
        self.assertEqual(st.contacts, ())

    def test_round_closes_once(self):
        st = self.done.state
        self.assertEqual(st.clock.completed_rounds, 1)
        self.assertEqual(st.clock.event_cursor, 9)
        self.assertIs(type(st.phase), B.AwaitingPrincipal)
        self.assertIs(st.phase.side, S1)
        self.assertEqual(st.ledger.uses, ())                 # E01: fresh round, no uses
        self.assertFalse(any(r.exerted for r in st.ledger.formations))
        for token in ("S0.H1", "S1.H1"):
            self.assertEqual(B.formation(st, fid(token)).condition.exertion, 1)
        last = E.resolve(self.pre.state, decode(self.case["roots"][-1]["command"]))
        pre_open = [s for s in last.snapshots if s.stage is not E.Stage.OPEN_ROUND][-1]
        ledger = pre_open.document()["ledger"]
        self.assertEqual(len(ledger["uses"]), 8)               # E01: the full round 1 ledger

    def test_decline_costs_nothing(self):
        s = run_carrier("GT15", upto=4)
        rows = self.case["roots"]
        index = [i for i, row in enumerate(rows) if "decision" in row][0]
        s = run_carrier("GT15", upto=index)
        before = B.encode_state(s.state)
        r = s.submit(decode(rows[index]["command"]))
        self.assertIs(type(r), E.Suspended)
        r = s.submit(decode(rows[index]["decision"]))
        after = B.encode_state(s.state)
        for key in ("ammunition", "mounts", "personnel"):
            self.assertEqual(after[key], before[key])
        l1 = [g for g in after["formations"] if g["formation"] == "S1.L1"][0]
        self.assertEqual(l1["condition"]["exertion"], 0)
        record = [r for r in after["ledger"]["formations"] if r["formation"] == "S1.L1"][0]
        self.assertIsNone(record["response"])


class E01UseLifetime(MovementCase):

    def test_one_append_at_first_physical_stage(self):
        s = run_carrier("G7", upto=6)
        row = carriers()["G7"]["roots"][6]
        r = s.submit(decode(row["command"]))
        res = E.resolve(r.root, decode(row["decision"]))
        counts = [len(snap.document()["ledger"]["uses"]) for snap in res.snapshots]
        start = len(s.state.ledger.uses)
        stages = [snap.stage for snap in res.snapshots]
        self.assertEqual(stages[:4], [E.Stage.ROOT, E.Stage.STEP1, E.Stage.WINDOW,
                                      E.Stage.RESPONSE])
        self.assertEqual(counts[0], start)
        self.assertTrue(all(c == start + 1 for c in counts[1:]))
        work = res.accepted.state.ledger.uses[-1].work[0]
        self.assertEqual(work.end.name, "STOPPED")
        self.assertEqual(len(work.legs), 1)

    def test_g9_terminal(self):
        s = run_carrier("G9", upto=34)
        row = carriers()["G9"]["roots"][34]
        res = E.resolve(s.state, decode(row["command"]))
        evacuate = [snap for snap in res.snapshots if snap.stage is E.Stage.EVACUATE][0]
        uses = evacuate.document()["ledger"]["uses"]
        self.assertEqual(sum(u["side"] == "S0" and u["members"] == ["S0.L1"] for u in uses), 1)
        self.assertIsNone(res.accepted.state.ledger)
        self.assertIs(type(res.accepted.state.phase), B.Terminal)


class F01G5(unittest.TestCase):

    def test_following_group_step(self):
        st = run_carrier("G5").state
        for token, cell in (("S0.H1", (2, 5)), ("S0.H2", (3, 5)), ("S0.H5", (3, 6)),
                            ("S1.H1", (8, 3)), ("S1.H2", (7, 3)), ("S1.H5", (7, 2))):
            g = B.formation(st, fid(token))
            self.assertEqual(g.cell, B.Hex(*cell))
            self.assertEqual(g.condition.exertion, 1)
        cells = [g.cell for g in st.formations]
        self.assertEqual(len(set(cells)), len(cells))
        self.assertEqual([u.side for u in st.ledger.uses], [S0, S1])
        self.assertEqual([len(u.work) for u in st.ledger.uses], [3, 3])


class F04LastSlot(MovementCase):

    def test_adversary_unfinished(self):
        d = doc()
        d["ledger"]["uses"] = [hold_use("S0", "S0.H3"), hold_use("S1", "S1.H1"),
                               hold_use("S0", "S0.H4"), hold_use("S1", "S1.H2"),
                               hold_use("S0", "S0.H6"), hold_use("S1", "S1.H3")]
        after = self.accepted(state_of(d), gm("S0.G1", ("S0.H1", "S0.H2"), 4))
        fields = _fields(after)
        from imperium.battle.queries import activation
        for token, want in (("S0.H1", "SPENT"), ("S0.H2", "SPENT"), ("S0.H3", "SPENT"),
                            ("S0.H5", "FORFEITED"), ("S0.L1", "FORFEITED"),
                            ("S0.C1", "FORFEITED")):
            self.assertEqual(activation(fields, fid(token)).name, want, token)

    def test_both_finish_inspect_last_pre_open_round(self):
        d = doc()
        d["ledger"]["uses"] = [hold_use("S0", "S0.H3"), hold_use("S1", "S1.H1"),
                               hold_use("S0", "S0.H4"), hold_use("S1", "S1.H2"),
                               hold_use("S0", "S0.H6"), hold_use("S1", "S1.H3")]
        after = self.accepted(state_of(d), gm("S0.G1", ("S0.H1", "S0.H2"), 4))
        res = E.resolve(after, E.HoldOrder(S1, fid("S1.H4")))
        self.assertIn(E.Stage.OPEN_ROUND, res.accepted.stages)
        snaps = [s for s in res.snapshots if s.stage is not E.Stage.OPEN_ROUND]
        fields = _fields_of_values(snaps[-1].values)
        from imperium.battle.queries import activation
        for token, want in (("S0.H1", "SPENT"), ("S0.H2", "SPENT"), ("S0.H3", "SPENT"),
                            ("S0.H5", "FORFEITED")):
            self.assertEqual(activation(fields, fid(token)).name, want, token)


def _fields(state):
    from imperium.battle.queries import Fields
    from imperium.battle.records import STATE_FIELDS
    from imperium.battle.state import state_values
    return Fields(**dict(zip(STATE_FIELDS, state_values(state))))


def _fields_of_values(values):
    from imperium.battle.queries import Fields
    from imperium.battle.records import STATE_FIELDS
    return Fields(**dict(zip(STATE_FIELDS, values)))


class F06GroupPivot(unittest.TestCase):

    def test_gt15_group_pivots(self):
        rows = carriers()["GT15"]["roots"]
        pivots = [i for i, row in enumerate(rows) if row["command"]["kind"] == "GroupPivotOrder"]
        self.assertEqual(len(pivots), 2)
        for i in pivots:
            s = run_carrier("GT15", upto=i)
            command = decode(rows[i]["command"])
            self.assertEqual(command.turn, 1)
            before = {m: B.formation(s.state, m) for m in command.members}
            res = E.resolve(s.state, command)
            self.assertIs(type(res), E.Resolved)
            self.assertNotIn(E.Stage.WINDOW, res.accepted.stages)
            self.assertEqual(res.accepted.stages[:3], (E.Stage.ROOT, E.Stage.GROUP_PIVOT,
                                                       E.Stage.IMMEDIATE_CHECK))
            for m, g in before.items():
                h = B.formation(res.accepted.state, m)
                self.assertEqual(h.cell, g.cell)
                self.assertEqual(h.facing, (g.facing + 1) % 6)
                self.assertEqual(h.condition.exertion, g.condition.exertion + 1)


class G08Withdraw(unittest.TestCase):

    def test_g8(self):
        st = run_carrier("G8").state
        g = B.formation(st, fid("S0.H1"))
        self.assertEqual((g.cell, g.facing, g.condition.exertion), (B.Hex(2, 7), 4, 2))
        work = st.ledger.uses[-1].work
        self.assertEqual([w.__class__.__name__ for w in work], ["Withdraw"])


class H02G9(unittest.TestCase):

    def test_g9_terminal_record(self):
        final = carriers()["G9"]["final"]
        st = run_carrier("G9").state
        record = B.encode_state(st)["phase"]["record"]
        self.assertEqual(record, final["phase"]["record"])
        self.assertEqual((record["reason"], record["result"], record["winner"]),
                         ("ZERO_VIABILITY_UNILATERAL", "VICTORY", "S1"))
        self.assertEqual(record["charged_rounds"], 8)
        self.assertEqual(st.clock.completed_rounds, 7)
        for g in st.formations:
            if g.formation.token.startswith("S0"):
                self.assertIs(g.disposition, B.Disposition.WITHDRAWN)


if __name__ == "__main__":
    unittest.main()
