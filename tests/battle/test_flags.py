"""14.5 round flags, rest, rally and refuge; R-D and restored R rows."""

import dataclasses

import imperium.battle as B
from tests.battle.common import BattleCase, a1, cond, f, fr, individual, pivot, place, response, simple
from tests.battle.test_work import one, routing, uses, w06
from tests.support.battle_builder import as_adversarial, opening_document

F = B.FormationId


class FlagTests(BattleCase):
    def test_at_f01(self):
        d = a1("OPEN", "F01")
        d["ledger"]["uses"] = [individual("S0", "S0.H1", pivot(4, 1, 1))]
        d["phase"]["side"] = "S1"
        f(d, "S0.H1")["facing"] = 5
        self.reject(d, "R18")

    def test_at_f02(self):
        d = one(a1("OPEN", "F02"), "S0.H3", pivot(4, 1, 1))
        f(d, "S0.H3")["facing"] = 5
        fr(d, "S0.H3")["safe_latch"] = True
        s = self.accept(d)
        self.assertFalse(B.rest_order_exists(s, F("S0.H3")))
        self.assertFalse(B.full_safe_interval(s, F("S0.H3")))

    def test_at_f03(self):
        d = a1("OPEN", "F03")
        fr(d, "S0.H1").update(safe_latch=True, incoming=True, incoming_since_rally=True)
        s = self.accept(d)
        self.assertTrue(B.recovery_safe_now(s, F("S0.H1")))
        self.assertFalse(B.full_safe_interval(s, F("S0.H1")))

    def test_at_f04_r17b(self):
        d = a1("OPEN", "F04")
        place(d, "S1.H1", (2, 5), 1)
        fr(d, "S0.H1")["safe_latch"] = True
        self.reject(d, "R17")
        s = self.accept(a1("OPEN", "R17B"))
        self.assertTrue(B.recovery_safe_now(s, F("S0.H1")))
        self.assertFalse(s.ledger.formations[0].safe_latch)

    def test_at_f05(self):
        d = as_adversarial(opening_document(), "F05")
        d["scenario"]["profile"]["exertion_cleared_by"] = "RALLY"
        self.reject(d, "P01")
        profile = B.f01_scenario(B.Variant.OPEN, B.Orientation.STANDARD).profile
        with self.assertRaises(B.InvalidValue) as cm:
            dataclasses.replace(profile, exertion_cleared_by=B.Posture.CONTESTING)
        self.assertEqual(cm.exception.clause, "T16")

    def test_at_f06_f07(self):
        d = routing(a1("OPEN", "F06"), "S0.H5")
        fr(d, "S0.H5").update(opened_eligible=False, displacement_attempted=False,
                              response=response("DEFENSIVE_PIVOT", "S1.H1"), exerted=True)
        self.reject(d, "R12")
        d = routing(a1("OPEN", "F07"), "S0.H5")
        fr(d, "S0.H5").update(opened_eligible=False, displacement_attempted=False)
        s = self.accept(d)
        H5 = F("S0.H5")
        self.assertIs(B.activation(s, H5), B.Activation.INELIGIBLE)
        self.assertEqual(B.projected_opening_effort(s, H5), 0)
        self.assertFalse(B.response_allowance_unused(s, H5))

    def test_at_f08_r13b(self):
        d = routing(a1("OPEN", "F08"), "S0.H5")
        fr(d, "S0.H5")["displacement_attempted"] = False
        self.reject(d, "R13")
        s = self.accept(routing(a1("OPEN", "R13B"), "S0.H5"))
        self.assertIs(B.activation(s, F("S0.H5")), B.Activation.FORFEITED)

    def test_at_f09_f10_f11(self):
        d = a1("OPEN", "F09")
        fr(d, "S0.H1").update(displaced=True, exerted=True)
        self.reject(d, "R20")
        d = a1("OPEN", "F10")
        fr(d, "S0.H1").update(incoming=False, incoming_since_rally=True)
        self.reject(d, "R19")
        d = a1("OPEN", "F10B")
        fr(d, "S0.H1").update(incoming=True, incoming_since_rally=False)
        self.reject(d, "R19")
        d = one(a1("OPEN", "F10C"), "S0.H1", simple("Rally"))
        fr(d, "S0.H1").update(incoming=True, incoming_since_rally=False)
        self.accept(d)
        self.reject(one(a1("OPEN", "F11"), "S0.H1", simple("Rest")), "R16")

    def test_at_f12(self):
        d = a1("OPEN", "F12")
        fr(d, "S0.H1")["opened_eligible"] = False
        self.reject(d, "R22")
        d = routing(a1("OPEN", "F12B"), "S0.H5")
        fr(d, "S0.H5").update(opened_eligible=False, displacement_attempted=False)
        self.accept(d)


class RepresentativeLedgerTests(BattleCase):
    """R-D: hand-computed 9.2 values on representative ledgers."""

    def test_group_ledger(self):
        s = self.accept(w06("RD1"))
        expected = {"S0.H1": (B.Activation.SPENT, 1), "S0.H2": (B.Activation.SPENT, 2),
                    "S0.H3": (B.Activation.READY, 3), "S1.H1": (B.Activation.READY, 3)}
        for fid, (act, remaining) in expected.items():
            self.assertIs(B.activation(s, F(fid)), act)
            self.assertEqual(B.effort_remaining(s, F(fid)), remaining)
        self.assertEqual(B.usable_opportunities(s, B.Side.S0), 3)
        self.assertEqual(B.usable_opportunities(s, B.Side.S1), 4)
        self.assertFalse(B.side_finished(s, B.Side.S0))
        self.assertFalse(B.rest_benefit_pending(s, F("S0.H1")))

    def test_rest_benefit_pending(self):
        d = cond(a1("OPEN", "RD2"), "S0.H4", fat=1)
        fr(d, "S0.H4")["safe_latch"] = True
        s = self.accept(one(d, "S0.H4", simple("Rest")))
        H4 = F("S0.H4")
        self.assertTrue(B.full_safe_interval(s, H4))
        self.assertTrue(B.rest_benefit_pending(s, H4))
        self.assertEqual(B.effort_remaining(s, H4), 1)
        self.assertIs(B.activation(s, H4), B.Activation.SPENT)

    def test_pass_and_finish(self):
        d = uses(a1("OPEN", "RD3"), [individual("S0", "S0.H1", {"kind": "Hold"}),
                                     {"side": "S1", "kind": "PASS", "group": None, "members": [],
                                      "work": []}], "S0")
        s = self.accept(d)
        self.assertTrue(B.side_finished(s, B.Side.S1))
        self.assertEqual(B.usable_opportunities(s, B.Side.S1), 0)
        self.assertEqual(B.usable_opportunities(s, B.Side.S0), 3)
        self.assertIs(B.activation(s, F("S1.H2")), B.Activation.FORFEITED)
        self.assertIs(B.next_side(s), B.Side.S0)
