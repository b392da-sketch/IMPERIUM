"""TA-C01–C12: Hold, Pass, Declare withdrawal, alternation and the final slot (P2-C)."""

import imperium.battle as B
from imperium.battle import engine as E
from tests.battle.common import fr, individual, leg, move, place, response
from tests.engine.helpers import (
    CLOSE_CONTINUE, ROOT_TRACE, S0, S1, EngineCase, awaiting, build, fid, hold, hold_use,
    make_router, opened,
)

UNCHANGED = ("scenario", "formations", "authority", "personnel", "mounts", "ammunition", "contacts")
S0_TOKENS = ("S0.C1", "S0.H1", "S0.H2", "S0.H3", "S0.H4", "S0.H5", "S0.H6", "S0.L1")


def play(test, state, commands):
    for c in commands:
        state = test.accepted(state, c)
    return state


def round_of(state, token):
    for r in state.ledger.formations:
        if r.formation.token == token:
            return r
    raise KeyError(token)


class Hold(EngineCase):

    def test_c01_hold(self):
        a = opened()
        b = self.accepted(a, hold(S0, "S0.H1"), ROOT_TRACE)
        h1 = fid("S0.H1")
        self.assertEqual(B.usable_opportunities(b, S0), 3)
        self.assertIs(B.activation(b, h1), B.Activation.SPENT)
        self.assertEqual((B.effort_charged(b, h1), B.effort_remaining(b, h1)), (0, 3))
        self.assertEqual(b.phase, B.AwaitingPrincipal(S1))
        self.assertEqual(b.ledger.formations, a.ledger.formations)
        self.assertFalse(round_of(b, "S0.H1").exerted)
        self.assertEqual(b.ledger.uses, (B.OpportunityUse(S0, B.UseKind.INDIVIDUAL, None, (h1,), (B.Hold(),)),))
        for name in UNCHANGED + ("sides",):
            self.assertEqual(getattr(b, name), getattr(a, name), name)

    def test_c02_wrong_side(self):
        a = opened()
        self.rejected(a, hold(S1, "S1.H1"), E.RejectCode.WRONG_SIDE, "/side",
                      "side does not have the current opportunity")
        self.rejected(a, E.PassOrder(S1), E.RejectCode.WRONG_SIDE)
        self.rejected(a, E.DeclareWithdrawal(S1), E.RejectCode.WRONG_SIDE)
        self.rejected(a, E.Capitulate(S1), E.RejectCode.WRONG_SIDE)

    def test_c03_formation_ids(self):
        a = opened()
        self.rejected(a, hold(S0, "S9.X1"), E.RejectCode.UNKNOWN_FORMATION, "/formation",
                      "formation is not in the roster")
        self.rejected(a, hold(S0, "S1.H1"), E.RejectCode.NOT_OWN_FORMATION, "/formation",
                      "formation does not belong to the command side")

    def test_c04_spent_and_ineligible(self):
        a = play(self, opened(), [hold(S0, "S0.H1"), hold(S1, "S1.H1")])
        self.rejected(a, hold(S0, "S0.H1"), E.RejectCode.NOT_READY, "/formation", "SPENT")
        d = awaiting(label="C04i")
        make_router(d, "S0.H5")
        self.rejected(build(d), hold(S0, "S0.H5"), E.RejectCode.NOT_READY, "/formation", "INELIGIBLE")

    def test_c04_a10_forfeited(self):
        d = awaiting(label="C04f")
        fr(d, "S0.H1")["displacement_attempted"] = True
        s = build(d)
        self.assertEqual(B.usable_opportunities(s, S0), 4)
        self.rejected(s, hold(S0, "S0.H1"), E.RejectCode.NOT_READY, "/formation", "FORFEITED")

    def test_c04_ready_after_response(self):
        d = awaiting(label="C04r", uses=[
            hold_use("S0", "S0.H3"),
            individual("S1", "S1.L1", move([(3, 6)], [leg((3, 7), (3, 6), 4)])),
        ], side="S0")
        place(d, "S0.H2", (5, 7))
        place(d, "S0.H5", (6, 7))
        place(d, "S1.L1", (3, 6), 4)
        place(d, "S0.H1", (2, 6), 5)
        r = fr(d, "S0.H1")
        r["response"] = response("DEFENSIVE_PIVOT", "S1.L1")
        r["exerted"] = True
        fr(d, "S1.L1")["exerted"] = True
        for token in ("S0.H1", "S0.H2", "S0.H3", "S0.H4", "S0.H5", "S0.H6", "S0.L1", "S0.C1",
                      "S1.L1"):
            fr(d, token)["safe_latch"] = False
        s = build(d)
        h1 = fid("S0.H1")
        self.assertIs(B.activation(s, h1), B.Activation.READY)
        self.assertEqual(B.effort_charged(s, h1), 1)
        t = self.accepted(s, hold(S0, "S0.H1"), ROOT_TRACE)
        self.assertIs(B.activation(t, h1), B.Activation.SPENT)
        self.assertEqual((B.effort_charged(t, h1), B.effort_remaining(t, h1)), (1, 2))
        self.assertEqual(round_of(t, "S0.H1"), round_of(s, "S0.H1"))
        self.assertTrue(round_of(t, "S0.H1").exerted)
        self.assertEqual(t.ledger.formations, s.ledger.formations)


class Alternation(EngineCase):

    def test_c05_pass_first(self):
        a = self.accepted(opened(), E.PassOrder(S0), ROOT_TRACE)
        self.assertTrue(B.side_finished(a, S0))
        for token in S0_TOKENS:
            self.assertIs(B.activation(a, fid(token)), B.Activation.FORFEITED)
            self.assertTrue(B.response_allowance_unused(a, fid(token)))
        for i, token in enumerate(("S1.H1", "S1.H2", "S1.H3")):
            a = self.accepted(a, hold(S1, token), ROOT_TRACE)
            self.assertIs(a.phase.side, S1)
        b = self.accepted(a, hold(S1, "S1.H4"), CLOSE_CONTINUE)
        self.assertEqual(b.clock.completed_rounds, 1)

    def test_c05_pass_after_two_holds(self):
        a = play(self, opened(), [hold(S0, "S0.H1"), hold(S1, "S1.H1"), hold(S0, "S0.H2"),
                                  hold(S1, "S1.H2")])
        a = self.accepted(a, E.PassOrder(S0))
        self.assertIs(a.phase.side, S1)
        self.assertIs(B.activation(a, fid("S0.H1")), B.Activation.SPENT)
        self.assertIs(B.activation(a, fid("S0.H3")), B.Activation.FORFEITED)
        a = self.accepted(a, hold(S1, "S1.H3"), ROOT_TRACE)
        self.assertIs(a.phase.side, S1)
        self.accepted(a, hold(S1, "S1.H4"), CLOSE_CONTINUE)

    def test_c06_consecutive_after_opponent_pass(self):
        a = self.accepted(opened(), hold(S0, "S0.H1"))
        self.assertIs(a.phase.side, S1)
        a = self.accepted(a, E.PassOrder(S1))
        self.assertIs(a.phase.side, S0)
        a = self.accepted(a, hold(S0, "S0.H2"), ROOT_TRACE)
        self.assertIs(a.phase.side, S0)
        a = self.accepted(a, hold(S0, "S0.H3"), ROOT_TRACE)
        self.assertIs(a.phase.side, S0)
        b = self.accepted(a, hold(S0, "S0.H4"), CLOSE_CONTINUE)
        self.assertEqual((b.clock.completed_rounds, b.phase.side, b.ledger.uses), (1, S1, ()))

    def test_c07_final_slot(self):
        seq = []
        for k in (1, 2, 3):
            seq += [hold(S0, f"S0.H{k}"), hold(S1, f"S1.H{k}")]
        a = play(self, opened(), seq)
        b = self.accepted(a, hold(S0, "S0.H4"), ROOT_TRACE)
        self.assertTrue(B.side_finished(b, S0))
        self.assertFalse(B.side_finished(b, S1))
        self.assertIs(b.phase.side, S1)
        self.assertIs(B.activation(b, fid("S0.H4")), B.Activation.SPENT)
        for token in ("S0.H5", "S0.H6", "S0.L1", "S0.C1"):
            self.assertIs(B.activation(b, fid(token)), B.Activation.FORFEITED)
            self.assertTrue(B.response_allowance_unused(b, fid(token)))
        self.assertEqual(b.ledger.formations, a.ledger.formations)


class Withdrawal(EngineCase):

    def test_c08_declare(self):
        a = opened()
        b = self.accepted(a, E.DeclareWithdrawal(S0), ROOT_TRACE)
        self.assertEqual(b.sides, (B.SideState(S0, B.Posture.WITHDRAWING), B.SideState(S1, B.Posture.CONTESTING)))
        self.assertEqual(B.usable_opportunities(b, S0), 3)
        for token in S0_TOKENS:
            self.assertIs(B.activation(b, fid(token)), B.Activation.READY)
            self.assertEqual(B.effort_charged(b, fid(token)), 0)
        for name in UNCHANGED:
            self.assertEqual(getattr(b, name), getattr(a, name), name)
        self.assertEqual(b.ledger.formations, a.ledger.formations)
        self.assertEqual(b.ledger.uses, (B.OpportunityUse(S0, B.UseKind.POSTURE_WITHDRAWAL, None, (), ()),))

    def test_c09_irreversible(self):
        a = play(self, opened(), [E.DeclareWithdrawal(S0), E.PassOrder(S1)])
        self.rejected(a, E.DeclareWithdrawal(S0), E.RejectCode.ALREADY_WITHDRAWING, "/side",
                      "side is already withdrawing")
        b = self.accepted(a, E.PassOrder(S0))
        self.assertEqual(b.clock.completed_rounds, 1)
        b = self.accepted(b, E.PassOrder(S1))
        self.rejected(b, E.DeclareWithdrawal(S0), E.RejectCode.ALREADY_WITHDRAWING)
        self.assertIs(b.sides[0].posture, B.Posture.WITHDRAWING)

    def test_c10_hold_while_withdrawing(self):
        a = self.accepted(opened(), E.DeclareWithdrawal(S0))
        a = self.accepted(a, E.PassOrder(S1))
        self.accepted(a, hold(S0, "S0.H1"), ROOT_TRACE)

    def test_c11_declare_as_last_slot(self):
        seq = []
        for k in (1, 2, 3):
            seq += [hold(S0, f"S0.H{k}"), hold(S1, f"S1.H{k}")]
        a = play(self, opened(), seq)
        b = self.accepted(a, E.DeclareWithdrawal(S0), ROOT_TRACE)
        self.assertTrue(B.side_finished(b, S0))
        self.assertIs(b.phase.side, S1)
        self.assertIs(B.activation(b, fid("S0.H4")), B.Activation.FORFEITED)
