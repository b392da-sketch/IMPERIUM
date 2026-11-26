"""14.4 legs, work, charges and activation; restored R rows (14.11)."""

import imperium.battle as B
from tests.battle.common import (
    BattleCase, a1, account, assault, at_exit, cond, f, fr, group_pivot, group_step, individual,
    leg, missile, move, pivot, place, plot, response, set_asset_place, set_lots,
    simple, use, withdraw,
)
from tests.battle.test_mounts import a1a, split_mounts, xw03_positive, xw03_stopped

NON_EXERTING = ("Hold", "Rally", "Rest")
F = B.FormationId


def uses(d, records, side):
    """Write literal uses and the next side; mark exerting members."""
    d["ledger"]["uses"] = records
    d["phase"]["side"] = side
    for u in records:
        for m, w in zip(u["members"], u["work"]):
            if w["kind"] not in NON_EXERTING:
                fr(d, m)["exerted"] = True
    return d


def one(d, member, work, side_next="S1"):
    side = member[:2]
    return uses(d, [individual(side, member, work)], side_next)


def hold(side, member):
    return individual(side, member, {"kind": "Hold"})


def passed(side):
    return use(side, "PASS", [], [])


def posture(side):
    return use(side, "POSTURE_WITHDRAWAL", [], [])


def expend(d, fid, n=1):
    a = account(d, fid)
    a["carried"] -= n
    a["expended"] += n
    return d


def work_of(s, ui=0, k=0):
    return s.ledger.uses[ui].work[k]


def routing(d, fid):
    f(d, fid)["disposition"] = "ROUTING"
    cond(d, fid, 2, 2)
    fr(d, fid)["displacement_attempted"] = True
    return d


class ChargeTests(BattleCase):
    def test_at_w01(self):
        s = self.accept(a1())
        H1, L1, C1 = F("S0.H1"), F("S0.L1"), F("S0.C1")
        H, Hx = B.Hex, B.Hex
        L = B.Leg
        cases = [
            (H1, B.Hold(), 0),
            (H1, B.Move((H(2, 5),), (L(H(2, 6), H(2, 5), 4, B.MovementMode.FOOT),), B.MoveEnd.COMPLETED), 1),
            (H1, B.Move((H(2, 5), H(2, 4)), (L(H(2, 6), H(2, 5), 4, B.MovementMode.FOOT),
                                           L(H(2, 5), H(2, 4), 4, B.MovementMode.FOOT)),
                        B.MoveEnd.COMPLETED), 2),
            (H1, B.Pivot(4, 1, 1), 1), (H1, B.Pivot(4, -1, 3), 3),
            (H1, B.Assault(F("S1.H1"), H(2, 6), H(2, 5), 4, B.MovementMode.FOOT,
                           B.AssaultOutcome.ABORTED), 2),
            (L1, B.Missile(F("S1.L1"), H(4, 5), Hx(4, 3), 4), 1),
            (H1, B.Rally(), 2), (H1, B.Rest(), 2), (H1, B.Evacuate(H(2, 8)), 2),
            (H1, B.Withdraw(L(H(2, 6), H(2, 7), 4, B.MovementMode.FOOT)), 2),
            (H1, B.GroupStep(L(H(2, 6), H(2, 5), 4, B.MovementMode.FOOT)), 1),
            (H1, B.GroupPivot(4, 1), 1),
            (L1, B.Response(B.ResponseKind.DEFENSIVE_MISSILE, F("S1.H1")), 1),
            (H1, B.Response(B.ResponseKind.DEFENSIVE_PIVOT, F("S1.H1")), 1),
            (C1, B.Move((H(1, 5),), (L(H(1, 6), H(1, 5), 4, B.MovementMode.MOUNTED),),
                        B.MoveEnd.COMPLETED), 1),
        ]
        for fid, work, expected in cases:
            with self.subTest(work=work):
                self.assertEqual(B.charge(s, fid, work), expected)
        rough = self.accept(a1("ROUGH"))
        step = B.GroupStep(L(H(2, 5), H(2, 4), 4, B.MovementMode.FOOT))
        self.assertEqual(B.charge(rough, H1, step), 2)
        self.assertEqual(B.charge(rough, H1, B.Withdraw(L(H(2, 3), H(2, 4), 4, B.MovementMode.FOOT))), 3)
        with self.assertRaises(B.InvalidValue) as cm:
            B.charge(s, H1, B.Move((H(2, 5),), (L(H(2, 6), H(2, 5), 4, B.MovementMode.MOUNTED),),
                                   B.MoveEnd.COMPLETED))
        self.assertEqual(cm.exception.clause, "R24")

    def w02(self, cell=None):
        d = one(a1("ROUGH", "W02"), "S0.H1",
                move([(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4), leg((2, 5), (2, 4), 4)]))
        place(d, "S0.H1", cell or (2, 4))
        return d

    def test_at_w02_w31(self):
        for cell in ((2, 4), (0, 4)):
            s = self.accept(self.w02(cell))
            self.assertEqual(B.charge(s, F("S0.H1"), work_of(s)), 3)
            self.assertEqual(B.effort_remaining(s, F("S0.H1")), 0)

    def test_at_w03(self):
        d = one(a1("ROUGH", "W03"), "S0.H1",
                move([(2, 4), (8, 4)], [leg((2, 5), (2, 4), 4), leg((2, 4), (8, 4), 4)]))
        violations = self.reject(d, "R21")
        self.assertNotIn("R07", [v.clause for v in violations])

    def test_at_w03b(self):
        d = one(a1("ROUGH", "W03B"), "S0.H1", withdraw((2, 3), (2, 4), 4))
        place(d, "S0.H1", (2, 4))
        fr(d, "S0.H1")["response"] = response("DEFENSIVE_PIVOT", "S1.H1")
        self.reject(d, "R07")

    def test_at_w04_w05(self):
        for work in (move([], [leg((2, 6), (2, 5), 4)]), move([(2, 5)], [])):
            self.reject(one(a1(), "S0.H1", work), "T15")
        for steps in (0, 4):
            self.reject(one(a1(), "S0.H1", pivot(4, 1, steps)), "T08")
        for turn in (0, 2):
            self.reject(one(a1(), "S0.H1", pivot(4, turn, 1)), "T08")
        for kwargs in ({"turn": 0, "steps": 1}, {"turn": 1, "steps": 4}):
            with self.assertRaises(B.InvalidValue):
                B.Pivot(facing_before=4, **kwargs)


def w06(label="W06"):
    d = a1("ROUGH", label)
    for fid, cell in (("S0.H1", (2, 4)), ("S0.H2", (3, 4)), ("S0.H5", (3, 3))):
        place(d, fid, cell, 1)
    work = [group_step((2, 3), (2, 4), 1), group_step((3, 3), (3, 4), 1),
            group_step((3, 2), (3, 3), 0)]
    return uses(d, [use("S0", "GROUP", ["S0.H1", "S0.H2", "S0.H5"], work, "S0.G1")], "S1")


class GroupTests(BattleCase):
    def test_at_w06(self):
        s = self.accept(w06())
        for fid, charged, remaining in (("S0.H1", 2, 1), ("S0.H2", 1, 2), ("S0.H5", 1, 2)):
            self.assertEqual(B.effort_charged(s, F(fid)), charged)
            self.assertEqual(B.effort_remaining(s, F(fid)), remaining)
        self.assertEqual(B.usable_opportunities(s, B.Side.S0), 3)
        self.assertIs(B.next_side(s), B.Side.S1)

    def test_at_w07(self):
        d = w06("W07")
        d["ledger"]["uses"][0]["work"][2] = group_pivot(0, 1)
        self.reject(d, "R06")
        d = w06("W07B")
        d["ledger"]["uses"][0]["work"][1] = group_step((3, 3), (4, 3), 1)
        place(d, "S0.H2", (4, 3))
        self.reject(d, "R23")

    def test_at_w32(self):
        d = w06("W32")
        d["ledger"]["uses"][0]["work"][1] = group_step((2, 3), (2, 4), 1)
        self.reject(d, "R23")
        d = w06("W32B")
        d["ledger"]["uses"][0]["work"][2] = group_step((6, 5), (6, 6), 1)
        place(d, "S0.H5", (6, 6))
        self.reject(d, "R23")

    def test_at_w12b(self):
        d = a1("OPEN", "W12B")
        for fid, cell in (("S0.H3", (5, 5)), ("S0.H4", (6, 5)), ("S0.H6", (5, 6))):
            place(d, fid, cell)
        group = use("S0", "GROUP", ["S0.H3", "S0.H4", "S0.H6"],
                    [group_step((4, 6), (5, 5), 4), group_step((5, 6), (6, 5), 4),
                     group_step((4, 7), (5, 6), 4)], "S0.G2")
        uses(d, [hold("S0", "S0.H1"), hold("S1", "S1.H1"), hold("S0", "S0.H2"),
                 hold("S1", "S1.H2"), hold("S0", "S0.H5"), hold("S1", "S1.H3"), group], "S1")
        s = self.accept(d)
        self.assertTrue(B.side_finished(s, B.Side.S0))
        self.assertIs(B.next_side(s), B.Side.S1)
        self.assertIs(B.activation(s, F("S0.C1")), B.Activation.FORFEITED)
        for fid in ("S0.H3", "S0.H4", "S0.H6"):
            self.assertIs(B.activation(s, F(fid)), B.Activation.SPENT)
            self.assertEqual(B.effort_charged(s, F(fid)), 1)

    def test_at_w36_a2(self):
        d = w06("A2")
        place(d, "S0.H2", (3, 5), 1)
        fr(d, "S0.H2").update(displacement_attempted=True, displaced=True)
        place(d, "S0.H3", (3, 4), 3)
        d["ledger"]["uses"] += [hold("S1", "S1.H1"),
                                individual("S0", "S0.H3", move([(3, 4)], [leg((4, 4), (3, 4), 3)]))]
        uses(d, d["ledger"]["uses"], "S1")
        self.accept(d)


def w14(label="W14"):
    d = a1("OPEN", label)
    return uses(d, [hold("S0", "S0.H1"), hold("S1", "S1.H1"), hold("S0", "S0.H2"),
                    hold("S1", "S1.H2"), passed("S0")], "S1")


class OpportunityTests(BattleCase):
    def test_at_w12_w13(self):
        seq = []
        for i, p in enumerate(("H1", "H2", "H3", "H4")):
            seq += [hold("S0", f"S0.{p}"), hold("S1", f"S1.{p}")]
        seq.append(hold("S0", "S0.H5"))
        self.reject(uses(a1("OPEN", "W12"), seq, "S1"), "R09")
        d = uses(a1("OPEN", "W13"), [passed("S0"), hold("S1", "S1.H1"), hold("S0", "S0.H1")], "S1")
        self.reject(d, "R08")

    def test_at_w14(self):
        s = self.accept(w14())
        H3 = F("S0.H3")
        self.assertEqual(B.capacity_remaining(s, B.Side.S0), 2)
        self.assertEqual(B.usable_opportunities(s, B.Side.S0), 0)
        self.assertTrue(B.side_finished(s, B.Side.S0))
        self.assertTrue(B.response_allowance_unused(s, H3))
        # AT-W14b
        self.assertIs(B.activation(s, H3), B.Activation.FORFEITED)
        self.assertTrue(B.response_possible(s, H3))
        self.assertEqual(B.effort_usable(s, H3), 3)

    def test_at_w14c(self):
        d = w14("W14C")
        fr(d, "S0.H3").update(response=response("DEFENSIVE_PIVOT", "S1.H1"), exerted=True)
        s = self.accept(d)
        self.assertFalse(B.response_allowance_unused(s, F("S0.H3")))
        self.assertEqual(B.effort_remaining(s, F("S0.H3")), 2)

    def test_at_w14d(self):
        d = cond(w14("W14D"), "S0.H3", 2, 0)
        s = self.accept(d)
        self.assertTrue(B.response_allowance_unused(s, F("S0.H3")))
        self.assertFalse(B.response_possible(s, F("S0.H3")))
        d = w14("W14E")
        place(d, "S1.H4", (5, 5), 1)
        place(d, "S0.H4", (6, 6))
        d["contacts"] = [{"low": "S0.H3", "high": "S1.H4", "edge": [[4, 6], [5, 5]]}]
        s = self.accept(d)
        self.assertTrue(B.response_allowance_unused(s, F("S0.H3")))
        self.assertFalse(B.response_possible(s, F("S0.H3")))

    def test_at_w15(self):
        A = B.Activation
        d = a1("OPEN", "W15")
        routing(d, "S0.H6")
        fr(d, "S0.H6").update(opened_eligible=False, displacement_attempted=False)
        routing(d, "S0.H5")
        fr(d, "S0.H4")["displacement_attempted"] = True
        one(d, "S0.H1", {"kind": "Hold"})
        s = self.accept(d)
        expected = {"S0.H6": A.INELIGIBLE, "S0.H1": A.SPENT, "S0.H4": A.FORFEITED,
                    "S0.H5": A.FORFEITED, "S0.H2": A.READY}
        for fid, act in expected.items():
            self.assertIs(B.activation(s, F(fid)), act, fid)
        self.assertIs(B.activation(self.accept(w14("W15B")), F("S0.H3")), A.FORFEITED)

    def test_at_w16(self):
        d = routing(a1("OPEN", "W16"), "S0.H5")
        fr(d, "S0.H5").update(response=response("DEFENSIVE_PIVOT", "S1.H1"), exerted=True)
        s = self.accept(d)
        self.assertFalse(B.response_possible(s, F("S0.H5")))

    def test_at_w17(self):
        d = a1("OPEN", "W17")
        f(d, "S0.H5")["disposition"] = "REFORMING"
        fr(d, "S0.H5").update(response=response("DEFENSIVE_PIVOT", "S1.H1"), exerted=True)
        self.reject(d, "R14")
        d = a1("OPEN", "W17B")
        f(d, "S0.H1")["disposition"] = "REFORMING"
        place(d, "S0.H1", (2, 5))
        self.reject(one(d, "S0.H1", move([(2, 5)], [leg((2, 6), (2, 5), 4)])), "R14")

    def test_r14b(self):
        d = a1("OPEN", "R14B")
        f(d, "S0.H1")["disposition"] = "REFORMING"
        self.accept(one(d, "S0.H1", simple("Rally")))
        d = a1("OPEN", "R14C")
        f(d, "S0.H1")["disposition"] = "REFORMING"
        s = self.accept(d)
        self.assertIs(B.activation(s, F("S0.H1")), B.Activation.READY)

    def test_at_w18_w19(self):
        d = routing(a1("OPEN", "W18"), "S0.H5")
        fr(d, "S0.H5").update(opened_eligible=False, displacement_attempted=False)
        self.reject(one(d, "S0.H5", {"kind": "Hold"}), "R05")
        d = uses(a1("OPEN", "W19"), [hold("S0", "S0.H1"), hold("S1", "S1.H1"), hold("S0", "S0.H1")],
                 "S1")
        self.reject(d, "R04")

    def test_r03(self):
        d = a1("OPEN", "R03A")
        uses(d, [use("S0", "INDIVIDUAL", ["S1.H1"], [{"kind": "Hold"}])], "S1")
        self.reject(d, "R03")
        d = a1("OPEN", "R03B")
        uses(d, [use("S0", "GROUP", ["S0.H1", "S0.H3"], [{"kind": "GroupPivot", "facing_before": 4,
                                                          "turn": 1}] * 2, "S0.G1")], "S1")
        f(d, "S0.H1")["facing"] = 5
        f(d, "S0.H3")["facing"] = 5
        self.reject(d, "R03")

    def test_r10a(self):
        self.reject(uses(a1("OPEN", "R10A"), [posture("S0")], "S1"), "R10")
        d = a1("OPEN", "R10B")
        d["sides"][0]["posture"] = "WITHDRAWING"
        self.reject(uses(d, [posture("S0"), hold("S1", "S1.H1"), posture("S0")], "S1"), "R10")

    def test_r11b_r11d(self):
        seq = [hold("S0", "S0.H1"), hold("S1", "S1.H1"), hold("S0", "S0.H2"), passed("S1"),
               hold("S0", "S0.H3")]
        self.accept(uses(a1("OPEN", "R11B"), seq, "S0"))
        self.reject(uses(a1("OPEN", "R11X"), [hold("S1", "S1.H1")], "S0"), "R11")
        self.reject(uses(a1("OPEN", "R11D"), [passed("S0"), passed("S1")], "S0"), "R11")


class FinalWorkTests(BattleCase):
    def test_at_w08(self):
        d = a1("OPEN", "W08")
        place(d, "S0.L1", (4, 4))
        s = self.accept(one(d, "S0.H3", assault("S1.H1", (4, 6), (4, 5), 4, outcome="ABORTED")))
        self.assertEqual(B.charge(s, F("S0.H3"), work_of(s)), 2)
        self.assertEqual(B.effort_remaining(s, F("S0.H3")), 1)
        self.assertEqual(s.contacts, ())

    def test_at_w08b(self):
        d = a1("OPEN", "W08B")
        place(d, "S0.L1", (4, 4))
        one(d, "S0.H3", assault("S1.H1", (4, 6), (4, 5), 4, outcome="ABORTED"))
        d["ledger"]["uses"][0]["work"][0]["charge"] = 0
        self.decode_code(d, "KEYS", "/ledger/uses/0/work/0")
        with self.assertRaises(TypeError):
            B.Assault(F("S1.H1"), B.Hex(4, 6), B.Hex(4, 5), 4, B.MovementMode.FOOT,
                      B.AssaultOutcome.ABORTED, charge=0)

    def test_at_w09_w10(self):
        for target in ((4, 4), (4, 7)):
            self.reject(one(a1(), "S0.H3", assault("S1.H1", (4, 6), target, 4)), "R21")
        d = a1("BARRIER")
        place(d, "S0.H3", (3, 4), 0)
        self.reject(one(d, "S0.H3", assault("S1.H1", (3, 4), (4, 4), 0)), "R21")
        self.accept(one(a1(), "S0.L1", assault("S1.H1", (4, 5), (4, 4), 4, outcome="ABORTED")))

    def test_at_w11_w34(self):
        self.reject(one(a1(), "S0.L1", missile("S1.H1", (4, 5), (4, 3), 4)), "A05")
        d = one(a1(), "S0.L1", missile("S1.H1", (4, 5), (4, 3), 4))
        self.accept(expend(d, "S0.L1"))
        fr(d, "S0.L1")["response"] = response("DEFENSIVE_MISSILE", "S1.H2")
        self.reject(d, "A05")

    def test_at_w20_x_l04(self):
        d = a1("OPEN", "W20")
        place(d, "S0.H6", (4, 8), disposition="WITHDRAWN")
        cond(d, "S0.H6", 2, 2)
        set_lots(d, "S0.H6", [plot("S0.H6:P0", "S0.H6", 240, "AVAILABLE", at_exit("S0"), "S0")])
        set_asset_place(d, "S0.H6", "ASSIGNED", at_exit("S0"), "S0", "OWN", "NOT_APPLICABLE")
        fr(d, "S0.H6")["displacement_attempted"] = True
        self.accept(one(d, "S0.H6", withdraw((4, 7), (4, 8), 4)))

    def test_at_w21_w38(self):
        self.reject(one(a1(), "S0.H1", simple("Evacuate", cell=[2, 6])), "R15")
        for cell, ok in (((2, 8), True), ((3, 8), False)):
            d = a1("OPEN", "W38")
            place(d, "S0.H1", (2, 8), disposition="WITHDRAWN")
            set_lots(d, "S0.H1", [plot("S0.H1:P0", "S0.H1", 240, "AVAILABLE", at_exit("S0"), "S0")])
            set_asset_place(d, "S0.H1", "ASSIGNED", at_exit("S0"), "S0", "OWN", "NOT_APPLICABLE")
            one(d, "S0.H1", simple("Evacuate", cell=list(cell)))
            self.accept(d) if ok else self.reject(d, "R15")
        d = a1("OPEN", "W38C")
        place(d, "S0.H1", (2, 8))
        self.accept(one(d, "S0.H1", withdraw((2, 7), (2, 8), 4)))

    def test_at_w22(self):
        d = a1("OPEN", "W22")
        cond(d, "S0.H4", fat=1)
        place(d, "S1.L1", (5, 4), 1)
        expend(d, "S1.L1")
        fr(d, "S0.H4").update(safe_latch=True, incoming=True, incoming_since_rally=True)
        s = self.accept(one(d, "S0.H4", simple("Rest")))
        H4 = F("S0.H4")
        self.assertTrue(B.rest_order_exists(s, H4))
        self.assertFalse(B.rest_benefit_pending(s, H4))
        self.assertTrue(B.recovery_safe_now(s, H4))


class LegTests(BattleCase):
    def h1(self, work, variant="OPEN"):
        return one(a1(variant), "S0.H1", work)

    def test_at_w23_w30(self):
        self.reject(self.h1(move([(2, 6)], [leg((0, 0), (2, 6), 4)])), "R21")
        self.reject(self.h1(move([(2, 5), (2, 6)], [leg((2, 6), (2, 5), 4)], "STOPPED")), "R21")
        self.reject(self.h1(move([(2, 7)], [leg((2, 6), (2, 7), 4)])), "R21")
        self.reject(self.h1(withdraw((2, 6), (2, 5), 4)), "R21")
        self.reject(self.h1(move([(2, 5)], [leg((2, 6), (3, 5), 4)])), "R21")

    def test_at_w26(self):
        self.reject(self.h1(move([(4, 4)], [leg((3, 4), (4, 4), 0)]), "BARRIER"), "R21")
        d = self.h1(move([(5, 4)], [leg((4, 4), (5, 4), 0)]), "BARRIER")
        place(d, "S0.H1", (5, 4), 0)
        s = self.accept(d)
        self.assertEqual(B.charge(s, F("S0.H1"), work_of(s)), 1)

    def test_at_w27(self):
        self.reject(self.h1(move([(2, 5), (3, 4)], [leg((2, 6), (2, 5), 4), leg((3, 5), (3, 4), 4)])),
                    "R21")
        self.reject(self.h1(move([(2, 5), (3, 4)], [leg((2, 6), (2, 5), 4), leg((2, 5), (3, 4), 5)])),
                    "R21")

    def test_at_w28(self):
        d = self.h1(move([(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4)], "STOPPED"))
        place(d, "S0.H1", (2, 5))
        s = self.accept(d)
        self.assertEqual(B.effort_charged(s, F("S0.H1")), 1)
        self.reject(self.h1(move([(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4)])), "R21")
        self.reject(self.h1(move([(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4), leg((2, 5), (2, 4), 4)],
                                 "STOPPED")), "R21")

    def test_at_w28b(self):
        self.reject(self.h1(move([(2, 5), (2, 3)], [leg((2, 6), (2, 5), 4)], "STOPPED")), "R21")
        self.reject(self.h1(move([(2, 5), (1, 6)], [leg((2, 6), (2, 5), 4)], "STOPPED")), "R21")
        self.reject(self.h1(move([(3, 4), (4, 4)], [leg((2, 5), (3, 4), 5)], "STOPPED"), "BARRIER"),
                    "R21")

    def test_at_w28c(self):
        d = one(a1("ROUGH"), "S0.C1",
                move([(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4, "MOUNTED")], "STOPPED"))
        self.reject(d, "R21")

    def test_at_w28d_w29(self):
        s = self.accept(xw03_stopped())
        self.assertEqual(B.charge(s, F("S0.C1"), work_of(s)), 1)
        self.assertEqual(len(work_of(s).declared), 2)
        occupied = xw03_stopped()
        place(occupied, "S0.H1", (2, 4))
        self.accept(occupied)
        s = self.accept(xw03_positive())
        self.assertEqual(B.charge(s, F("S0.C1"), work_of(s)), 3)
        self.assertEqual(B.effort_remaining(s, F("S0.C1")), 0)
        self.assertEqual(B.available(s, F("S0.C1")), 70)
        self.assertEqual(B.wounded(s, F("S0.C1")), 10)

    def test_at_w29c_w29d(self):
        d = xw03_stopped()
        d["ledger"]["uses"][0]["work"][0] = move(
            [(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4, "MIXED_FOOT"), leg((2, 5), (2, 4), 4, "MOUNTED")])
        self.reject(d, "R07")
        d = xw03_positive()
        legs = d["ledger"]["uses"][0]["work"][0]["legs"]
        legs[0]["mode"], legs[1]["mode"] = "MOUNTED", "MIXED_FOOT"
        self.reject(d, "R24")


class MissileAssaultTests(BattleCase):
    def fired(self, fid, work, label="M"):
        d = one(a1("OPEN", label), fid, work)
        return expend(d, fid) if fid != "S0.C1" else d

    def test_at_w33(self):
        self.reject(self.fired("S0.L1", missile("S1.H1", (4, 5), (4, 2), 4)), "R21")
        self.reject(self.fired("S0.H1", missile("S1.H1", (2, 6), (2, 4), 4)), "R21")
        d = a1()
        fr(d, "S0.C1").update(response=response("DEFENSIVE_MISSILE", "S1.H1"), exerted=True)
        self.reject(d, "R20")

    def test_at_w33b(self):
        s = self.accept(a1())
        for kind in ("DEFENSIVE_MISSILE", "DEFENSIVE_PIVOT"):
            for target in ("S9.X1", "S0.L1", "S0.H1"):
                d = a1()
                fr(d, "S0.L1").update(response=response(kind, target), exerted=True)
                expend(d, "S0.L1")
                self.reject(d, "R20")
                work = B.Response(B.ResponseKind[kind], F(target))
                if target == "S9.X1":
                    with self.assertRaises(B.UnknownId):
                        B.charge(s, F("S0.L1"), work)
                else:
                    with self.assertRaises(B.InvalidValue) as cm:
                        B.charge(s, F("S0.L1"), work)
                    self.assertEqual(cm.exception.clause, "R20")

    def test_at_w33c_d(self):
        self.reject(one(a1(), "S0.H1", assault("S0.H2", (2, 6), (2, 5), 4)), "R21")
        self.reject(self.fired("S0.L1", missile("S0.H1", (4, 5), (4, 4), 4)), "R21")
        self.reject(self.fired("S0.C1", missile("S1.H1", (1, 6), (1, 5), 4)), "R21")
        d = split_mounts(self.fired("S0.C1", missile("S1.H1", (1, 6), (1, 5), 4)))
        self.reject(d, "R21")

    def test_at_w33e_h(self):
        self.reject(self.fired("S0.H3", missile("S1.H1", (4, 6), (4, 7), 4)), "R21")
        self.reject(self.fired("S0.L1", missile("S1.H1", (4, 5), (6, 5), 4)), "R21")
        for cell in ((4, 3), (5, 3)):
            self.accept(self.fired("S0.L1", missile("S1.H1", (4, 5), cell, 4)))
        d = self.fired("S0.L1", missile("S1.L1", (4, 5), (4, 3), 4))
        place(d, "S1.L1", (6, 0), disposition="WITHDRAWN")
        set_lots(d, "S1.L1", [plot("S1.L1:P0", "S1.L1", 120, "AVAILABLE", at_exit("S1"), "S1")])
        set_asset_place(d, "S1.L1", "ASSIGNED", at_exit("S1"), "S1", "OWN", "NOT_APPLICABLE")
        self.accept(d)

    def test_at_w35(self):
        self.reject(one(a1(), "S0.C1", assault("S1.H1", (1, 6), (1, 5), 4, "FOOT")), "R24")
        self.reject(one(a1(), "S0.H1", assault("S1.H1", (2, 6), (2, 5), 4, "MOUNTED")), "R24")
        self.reject(one(a1(), "S0.L1", assault("S1.H1", (4, 5), (4, 4), 4, "MOUNTED")), "R24")
        d = split_mounts(one(a1(), "S0.C1", assault("S1.H1", (1, 6), (1, 5), 4, "MIXED_FOOT",
                                                    "ABORTED")))
        self.accept(d)
        d = a1a()
        d["ledger"]["uses"][0]["work"][0] = assault("S1.L1", (2, 4), (2, 5), 1, "MOUNTED", "ABORTED")
        self.accept(d)
        d = one(a1(), "S0.H1", assault("S1.H1", (2, 6), (2, 5), 4, "CONTESTING"))
        self.decode_code(d, "TOKEN", "/ledger/uses/0/work/0/mode")
        with self.assertRaises(B.InvalidValue) as cm:
            B.Assault(F("S1.H1"), B.Hex(2, 6), B.Hex(2, 5), 4, B.Posture.CONTESTING,
                      B.AssaultOutcome.ABORTED)
        self.assertEqual(cm.exception.clause, "T03")


class WithdrawingTests(BattleCase):
    def withdrawing(self, label, records, side="S1", declared=True):
        d = a1("OPEN", label)
        d["sides"][0]["posture"] = "WITHDRAWING"
        return uses(d, records, side)

    def test_at_w37a_b(self):
        attack = individual("S0", "S0.H3", assault("S1.H1", (4, 6), (4, 5), 4, outcome="ABORTED"))
        self.accept(self.withdrawing("W37A", [attack, hold("S1", "S1.H1"), posture("S0")]))
        late = individual("S0", "S0.H3", assault("S1.H1", (4, 6), (4, 5), 4, outcome="ABORTED"))
        self.reject(self.withdrawing("W37B", [posture("S0"), hold("S1", "S1.H1"), late]), "R10")

    def test_at_w37c(self):
        d = self.withdrawing("W37C", [individual("S0", "S0.L1", missile("S1.H1", (4, 5), (4, 3), 4))])
        expend(d, "S0.L1")
        self.reject(d, "R10")

    def test_at_w37d_f(self):
        d = self.withdrawing("W37D", [individual("S0", "S0.H1", move([(2, 7)], [leg((2, 6), (2, 7), 1)]))])
        place(d, "S0.H1", (2, 7), 1)
        self.accept(d)
        d = self.withdrawing("W37E", [individual("S0", "S0.H1", move([(2, 5)], [leg((2, 6), (2, 5), 4)]))])
        place(d, "S0.H1", (2, 5))
        self.reject(d, "R10")
        d = self.withdrawing("W37F", [individual("S0", "S0.H1", pivot(4, 1, 1))])
        f(d, "S0.H1")["facing"] = 5
        self.accept(d)
        d = self.withdrawing("W37G", [individual("S0", "S0.H1", withdraw((2, 6), (3, 6), 2))])
        place(d, "S0.H2", (3, 5))
        place(d, "S0.H1", (3, 6), 2)
        self.accept(d)

    def test_at_w37g(self):
        def group(label, h5_leg):
            work = [group_step((2, 6), (2, 7), 1), group_step((3, 6), (3, 7), 1), h5_leg]
            d = self.withdrawing(label, [use("S0", "GROUP", ["S0.H1", "S0.H2", "S0.H5"], work,
                                             "S0.G1")])
            for fid, cell in (("S0.H1", (2, 7)), ("S0.H2", (3, 7)), ("S0.H5", (3, 8))):
                place(d, fid, cell, 1)
            return d
        self.accept(group("W37G1", group_step((3, 7), (3, 8), 1)))
        d = group("W37G2", group_step((3, 7), (3, 8), 1))
        d["ledger"]["uses"][0]["work"][2] = group_step((3, 7), (4, 7), 0)
        place(d, "S0.H5", (4, 7), 0)
        place(d, "S0.H6", (5, 7))
        self.reject(d, "R10")

