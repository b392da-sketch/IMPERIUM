"""TA-P4-J01 to J08 and the window first-fault rows 32-35: options, the
defensive pivot, missile deferral, decision admission and the genuine-root
guard."""

import dataclasses
import json
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.engine import window as W
from tests.battle.common import individual
from tests.engine.helpers import hold_use, make_reformer, pass_use
from tests.movement.support import (
    S0, S1, MovementCase, carriers, cjson, complete, cond, doc, f, fid, fr, gm, hx, mv, place,
    rejection_oracles, run_carrier, state_of, window_hash,
)

R = E.RejectCode
DETAIL = rejection_oracles()


def detail(code):
    return DETAIL[code.name]["detail"]


def decode(tree):
    return E.decode_command(cjson(tree))


def g6():
    """S1 to decide on S0.L1 entering (5,4): missile-only window (G6)."""
    s = run_carrier("G6", upto=3)
    row = carriers()["G6"]["roots"][3]
    return s, decode(row["command"]), decode(row["decision"])


def g7():
    s = run_carrier("G7", upto=6)
    row = carriers()["G7"]["roots"][6]
    return s, decode(row["command"]), decode(row["decision"])


def options(root):
    return [(o.formation.token, o.kind.name, o.target.token) for o in root.window.options]


class J01OneWindow(MovementCase):

    def test_first_eligible_step_only(self):
        st = state_of(doc())
        root = self.suspended(st, mv("S0.H4", (5, 5), (5, 4)))
        self.assertEqual(root.window.after.rsplit(":", 1)[1], "STEP1")
        res = E.resolve(root, E.DeclineResponse(S1, root.window.window_id))
        self.assertEqual(sum(s is E.Stage.WINDOW for s in res.accepted.stages), 1)
        self.assertIn(E.Stage.STEP2, res.accepted.stages)
        window = [json.loads(e.data) for e in res.record.events if e.stage is E.Stage.WINDOW][0]
        self.assertEqual(window["decision"]["kind"], "DeclineResponse")
        self.assertEqual(window["after"], root.window.after)

    def test_no_window_without_options(self):
        res = complete(state_of(doc()), mv("S0.H1", (2, 5)))
        self.assertNotIn(E.Stage.WINDOW, res.accepted.stages)


class J02Pivot(unittest.TestCase):

    def defender(self, facing):
        st = state_of(doc())
        g = B.formation(st, fid("S1.H4"))
        return dataclasses.replace(g, cell=hx(5, 4), facing=facing)

    def test_turn_by_direction(self):
        from imperium.battle.values import DIRECTIONS
        d = self.defender(4)
        want = {0: 1, 3: -1, 4: None, 5: None, 1: None, 2: None}
        for direction, turn in want.items():
            dq, dr = DIRECTIONS[direction]
            self.assertEqual(W.pivot_turn(d, hx(5 + dq, 4 + dr)), turn, direction)

    def test_eligibility_controls(self):
        """Each negative keeps a window open through an independent missile
        option, so the excluded pivot's absence is asserted, not assumed."""
        pivot = ("S1.H4", "DEFENSIVE_PIVOT", "S0.L1")
        missile = ("S1.L1", "DEFENSIVE_MISSILE", "S0.L1")
        base = doc()
        place(base, "S1.H4", (3, 4), facing=4)          # S0.L1 entering (4,4) is at d0
        place(base, "S1.L1", (6, 3), facing=2)          # keeps a missile on (4,4)
        self.assertEqual(options(self.assert_window(state_of(base))), [pivot, missile])

        def no_effort(d):
            d["ledger"]["uses"] = [hold_use("S0", "S0.H1"), individual(
                "S1", "S1.H4", {"kind": "Pivot", "facing_before": 1, "turn": 1, "steps": 3})]
            cond(d, "S1.H4", e=3)
            fr(d, "S1.H4")["exerted"] = True

        for label, edit in (("C2", lambda d: cond(d, "S1.H4", c=2)),
                            ("reforming", lambda d: make_reformer(d, "S1.H4")),
                            ("used response", lambda d: _responded(d, "S1.H4")),
                            ("no effort", no_effort)):
            with self.subTest(control=label):
                d = json.loads(json.dumps(base))
                edit(d)
                self.assertEqual(options(self.assert_window(state_of(d))), [missile])
        d = json.loads(json.dumps(base))                         # SPENT stays eligible
        d["ledger"]["uses"] = [hold_use("S0", "S0.H1"), hold_use("S1", "S1.H4")]
        self.assertEqual(options(self.assert_window(state_of(d))), [pivot, missile])

    def test_only_hostile_adjacent_is_the_mover(self):
        d = doc()
        place(d, "S1.H4", (3, 4), facing=4)
        place(d, "S0.H4", (2, 4), facing=4)                     # already adjacent to S1.H4
        place(d, "S1.L1", (6, 3), facing=2)
        self.assertEqual(options(self.assert_window(state_of(d))),
                         [("S1.L1", "DEFENSIVE_MISSILE", "S0.L1")])

    def assert_window(self, st):
        r = E.step(st, mv("S0.L1", (4, 4)))
        self.assertIs(type(r), E.Suspended, msg=repr(r)[:300])
        return r.root


def _responded(d, token):
    fr(d, token)["response"] = {"kind": "DEFENSIVE_PIVOT", "target": "S0.H1"}
    fr(d, token)["exerted"] = True
    return d


class J03G7(MovementCase):

    def test_pivot_response(self):
        s, command, decision = g7()
        before = s.state
        root = self.suspended(before, command)
        self.assertEqual(root.window.after, "r2:S0.o1:STEP1")
        self.assertIn(("S1.H4", "DEFENSIVE_PIVOT", "S0.L1"), options(root))
        res = E.resolve(root, decision)
        after = res.accepted.state
        h4 = B.formation(after, fid("S1.H4"))
        self.assertEqual((h4.cell, h4.facing), (hx(5, 2), 1))
        self.assertEqual(h4.condition.exertion,
                         B.formation(before, fid("S1.H4")).condition.exertion + 1)
        record = [r for r in after.ledger.formations if r.formation == fid("S1.H4")][0]
        self.assertEqual((record.response.kind.name, record.response.target), ("DEFENSIVE_PIVOT",
                                                                               fid("S0.L1")))
        data = [json.loads(e.data) for e in res.record.events if e.stage is E.Stage.RESPONSE][0]
        self.assertEqual(data, {"formation": "S1.H4", "kind": "DEFENSIVE_PIVOT",
                                "target": "S0.L1", "from": 0, "to": 1})
        self.assertEqual(sum(u.side is S1 for u in after.ledger.uses),
                         sum(u.side is S1 for u in before.ledger.uses))
        self.assertEqual(after.ammunition, before.ammunition)
        self.assertEqual(B.formation(after, fid("S0.L1")).cell, hx(4, 3))


class J04Missile(MovementCase):

    def test_missile_only_window_and_deferral(self):
        s, command, decision = g6()
        r = s.submit(command)
        root = r.root
        self.assertEqual(options(root), [("S1.L1", "DEFENSIVE_MISSILE", "S0.L1")])
        state, journal = s.state, s.journal
        audit = s.export_audit()
        shot = E.RespondMissile(S1, root.window.window_id, fid("S1.L1"), fid("S0.L1"))
        for _ in range(2):
            out = s.submit(shot)
            self.assertIs(type(out), E.WindowDeferred)
            self.assertIs(out.root, root)
            self.assertEqual(out.obligations, ("DO-P4-02",))
            self.assertIs(s.pending, root)
            self.assertIs(s.state, state)
            self.assertIs(s.journal, journal)
            self.assertEqual(s.export_audit(), audit)
        self.assertIs(type(s.submit(decision)), E.Accepted)
        self.assertIsNone(s.pending)
        self.assertEqual(s.state.ammunition, state.ammunition)

    def missile_options(self, d, path=((5, 4),), token="S0.L1"):
        r = E.step(state_of(d), mv(token, *path))
        if type(r) is not E.Suspended:
            return []
        return [o for o in options(r.root) if o[1] == "DEFENSIVE_MISSILE"]

    def test_controls(self):
        self.assertEqual(self.missile_options(doc()), [("S1.L1", "DEFENSIVE_MISSILE", "S0.L1")])
        d = doc()
        for lot in d["ammunition"]:
            if lot["formation"] == "S1.L1":
                lot["carried"], lot["expended"] = 0, lot["carried"] + lot["expended"]
        if _valid(d):
            self.assertEqual(self.missile_options(d), [])
        d = doc()
        place(d, "S1.L1", (6, 3), facing=4)                 # mover outside the front sector
        self.assertEqual(self.missile_options(d), [])
        d = doc()
        place(d, "S1.L1", (9, 5), facing=2)                 # out of range
        self.assertEqual(self.missile_options(d), [])

    def test_c1_has_no_missile(self):
        d = doc()
        place(d, "S1.L1", (9, 5))
        place(d, "S1.C1", (6, 3), facing=1)
        self.assertEqual(self.missile_options(d), [])


def _valid(d):
    try:
        state_of(d)
        return True
    except Exception:
        return False


class J05J08Admission(MovementCase):

    def setUp(self):
        self.s, self.command, self.decision = g7()
        self.root = self.suspended(self.s.state, self.command)
        self.token = self.root.window.window_id

    def test_pending_window_and_phase(self):
        r = self.window_rejected(self.root, E.HoldOrder(S1, fid("S1.H1")), R.PENDING_WINDOW, "",
                                 detail(R.PENDING_WINDOW))
        self.assertIs(r.root, self.root)
        self.rejected(self.s.state, E.DeclineResponse(S1, self.token), R.PHASE, "",
                      "command is not admissible in this phase")

    def test_side_token_option(self):
        self.window_rejected(self.root, E.DeclineResponse(S0, self.token), R.WRONG_SIDE, "/side",
                             "side does not have the current opportunity")
        self.window_rejected(self.root, E.DeclineResponse(S1, "x"), R.BAD_VALUE, "/window_id",
                             "invalid command value")
        self.window_rejected(self.root, E.DeclineResponse(S1, "0" * 64), R.STALE_WINDOW,
                             "/window_id", detail(R.STALE_WINDOW))
        self.window_rejected(self.root, E.RespondPivot(S1, self.token, fid("S1.H3"),
                                                       fid("S0.L1")),
                             R.NOT_OFFERED, "/formation", detail(R.NOT_OFFERED))

    def test_row32_wrong_side_old_token(self):
        _, _, old = g6()
        self.window_rejected(self.root, E.DeclineResponse(S0, old.window_id), R.WRONG_SIDE,
                             "/side", "side does not have the current opportunity")

    def test_row33_old_token_and_invalid_option(self):
        _, _, old = g6()
        self.window_rejected(self.root, E.RespondPivot(S1, old.window_id, fid("S1.H3"),
                                                       fid("S0.H1")),
                             R.STALE_WINDOW, "/window_id", detail(R.STALE_WINDOW))

    def test_row34_forged_root_before_admission(self):
        forged_window = dataclasses.replace(self.root.window, options=(
            W.ResponseOption(fid("S1.H3"), B.ResponseKind.DEFENSIVE_PIVOT, fid("S0.L1")),))
        for forged in (dataclasses.replace(self.root, window=forged_window),
                       dataclasses.replace(self.root, window=dataclasses.replace(
                           self.root.window, movers=(fid("S0.H1"),)))):
            for decision in (E.DeclineResponse(S0, self.token), self.decision):
                with self.assertRaises(B.InvalidValue) as cm:
                    E.step(forged, decision)
                self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", "root"))

    def test_stale_after_consumption(self):
        s = self.s
        s.submit(self.command)
        s.submit(self.decision)
        r = s.submit(E.DeclineResponse(S1, self.token))
        self.assertIs(type(r), E.Rejected)
        self.assertEqual((r.code, r.path), (R.PHASE, ""))
        again = E.step(self.root, self.decision)
        self.assertIs(type(again), E.Accepted)
        self.assertEqual(B.digest(again.state), B.digest(s.state))

    def test_record_shapes(self):
        w = self.root.window
        for field, value in (("window_id", "A" * 64), ("after", "r2:S0.o1:PIVOT"),
                             ("movers", ()), ("options", ())):
            with self.assertRaises(B.InvalidValue) as cm:
                dataclasses.replace(w, **{field: value})
            self.assertEqual((cm.exception.clause, cm.exception.path), ("T16", field))
        with self.assertRaises(B.InvalidValue) as cm:
            dataclasses.replace(w, movers=[fid("S0.L1")])
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "movers"))
        with self.assertRaises(B.InvalidValue) as cm:
            W.ResponseOption(fid("S1.H4"), "DEFENSIVE_PIVOT", fid("S0.L1"))
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "kind"))
        for cls in (W.ResponseOption, W.ResponseWindow, W.SuspendedRoot, W.Suspended,
                    W.WindowRejected, W.WindowDeferred):
            self.assertTrue(cls.__dataclass_params__.frozen)
            self.assertTrue(hasattr(cls, "__slots__"))

    def test_token_formula(self):
        self.assertEqual(self.token, window_hash(B.digest(self.s.state), self.command,
                                                 self.root.window.after))


class J07Group(MovementCase):

    def test_group_offers_across_movers(self):
        d = doc()
        place(d, "S0.L1", (8, 6))
        place(d, "S1.H4", (2, 4), facing=5)                     # H1 arrives at d1 = f+2
        place(d, "S1.H3", (4, 4), facing=0)                     # H2 arrives at d2 = f+2
        r = E.step(state_of(d), gm("S0.G1", ("S0.H1", "S0.H2", "S0.H5"), 4))
        self.assertIs(type(r), E.Suspended, msg=repr(r)[:300])
        root = r.root
        self.assertEqual([m.token for m in root.window.movers], ["S0.H1", "S0.H2", "S0.H5"])
        pivots = [o for o in options(root) if o[1] == "DEFENSIVE_PIVOT"]
        self.assertEqual(pivots, [("S1.H3", "DEFENSIVE_PIVOT", "S0.H2"),
                                  ("S1.H4", "DEFENSIVE_PIVOT", "S0.H1")])
        res = E.resolve(root, E.RespondPivot(S1, root.window.window_id, fid("S1.H4"),
                                             fid("S0.H1")))
        self.assertEqual(sum(s is E.Stage.RESPONSE for s in res.accepted.stages), 1)
        after = res.accepted.state
        self.assertEqual(B.formation(after, fid("S1.H4")).facing, 0)
        self.assertEqual(B.formation(after, fid("S1.H3")).facing, 0)


class Row35ClosingRoot(MovementCase):

    def test_unsupported_closure_defers_before_window(self):
        d = doc()
        make_reformer(d, "S1.H6")
        d["ledger"]["uses"] = [hold_use("S0", "S0.H1"), hold_use("S1", "S1.H1"),
                               hold_use("S0", "S0.H2"), pass_use("S1"),
                               hold_use("S0", "S0.H3")]
        st = state_of(d)
        control = E.step(st, E.HoldOrder(S0, fid("S0.H4")))
        self.assertIs(type(control), E.Deferred)
        r = E.step(st, mv("S0.L1", (5, 4)))
        self.assertIs(type(r), E.Deferred, msg=repr(r)[:300])
        self.assertIs(r.state, st)
        self.assertEqual((r.stage, r.obligations), (control.stage, control.obligations))


if __name__ == "__main__":
    unittest.main()
