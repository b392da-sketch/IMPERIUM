"""14.3 mounts and movement mode (A1, R24)."""

import copy

import imperium.battle as B
from tests.battle.common import (
    BattleCase, a1, account, at_exit, f, fr, in_formation, individual, leg, move, mount_lots,
    on_cell, place, plot, response, set_asset_place, set_lots, simple, withdraw,
)
from tests.battle.scenarios import capitulation
from tests.support.battle_builder import as_adversarial, opening_document

C1 = B.FormationId("S0.C1")


def split_mounts(d, fid="S0.C1", serviceable=70):
    side = fid[:2]
    others = [m for m in d["mounts"] if m["formation"] != fid]
    base = {"formation": fid, "assignment": "ASSIGNED", "place": in_formation(fid),
            "custodian": side, "custody": "OWN", "recovery": "NOT_APPLICABLE"}
    lots = [dict(base, lot=f"{fid}:M0", count=serviceable, serviceability="SERVICEABLE"),
            dict(base, lot=f"{fid}:M1", count=80 - serviceable, serviceability="UNSERVICEABLE")]
    d["mounts"] = sorted(others + lots, key=lambda m: m["lot"])
    return d


def riders(d, available, wounded_cells=((1, 6),)):
    lots = [plot("S0.C1:P0", "S0.C1", available, "AVAILABLE", in_formation("S0.C1"), "S0")]
    wounded = 80 - available
    if wounded:
        lots.append(plot("S0.C1:W1", "S0.C1", wounded, "WOUNDED", on_cell(*wounded_cells[0]), "S0",
                         origin="EV-1"))
    return set_lots(d, "S0.C1", lots)


def c1_use(d, work, side_next="S1"):
    d["ledger"]["uses"] = [individual("S0", "S0.C1", work)]
    d["phase"]["side"] = side_next
    fr(d, "S0.C1")["exerted"] = True
    return d


def withdrawn_c1(d, cell=(1, 8)):
    place(d, "S0.C1", cell, disposition="WITHDRAWN")
    set_lots(d, "S0.C1", [plot("S0.C1:P0", "S0.C1", 80, "AVAILABLE", at_exit("S0"), "S0")])
    set_asset_place(d, "S0.C1", "ASSIGNED", at_exit("S0"), "S0", "OWN", "NOT_APPLICABLE")
    return d


def a1a(variant="OPEN"):
    """AT-M16: a depleted C1 after a completed mounted step (A1a)."""
    d = a1(variant, "A1A")
    place(d, "S0.H1", (1, 7))
    place(d, "S1.L1", (2, 6), 4)
    place(d, "S0.C1", (2, 4), 0, disposition="DEPLETED")
    set_lots(d, "S0.C1", [
        plot("S0.C1:D1", "S0.C1", 1, "DEAD", on_cell(2, 4), None, origin="EV-2"),
        plot("S0.C1:W1", "S0.C1", 79, "WOUNDED", on_cell(2, 3), "S0", origin="EV-1"),
    ])
    set_asset_place(d, "S0.C1", "UNASSIGNED_RECORDED", on_cell(2, 4), "S0", "OWN", "UNRESOLVED")
    account(d, "S1.L1").update(carried=3, expended=1)
    c1_use(d, move([(2, 4)], [leg((2, 3), (2, 4), 0, "MOUNTED")]))
    fr(d, "S0.C1").update(incoming=True, incoming_since_rally=True)
    fr(d, "S1.L1").update(response=response("DEFENSIVE_MISSILE", "S0.C1"), exerted=True)
    return d


def a1b():
    """AT-M17: a mounted move, a defensive missile, then a compulsory exit (A1b)."""
    d = a1("OPEN", "A1B")
    place(d, "S1.L1", (4, 8), 2)
    withdrawn_c1(d, (2, 8))
    f(d, "S0.C1")["facing"] = 0
    f(d, "S0.C1")["condition"].update(cohesion=2, morale=2)
    account(d, "S1.L1").update(carried=3, expended=1)
    c1_use(d, move([(2, 8)], [leg((2, 7), (2, 8), 0, "MOUNTED")]))
    fr(d, "S0.C1").update(incoming=True, incoming_since_rally=True, displacement_attempted=True,
                          displaced=True)
    fr(d, "S1.L1").update(response=response("DEFENSIVE_MISSILE", "S0.C1"), exerted=True)
    return d


def xw03_positive():
    """AT-W29 (15.3.1): mixed foot rough entry, a reaction wound, then mounted."""
    d = a1("ROUGH", "XW03")
    split_mounts(d)
    place(d, "S0.H1", (1, 7))
    place(d, "S1.L1", (2, 6), 4)
    place(d, "S0.C1", (2, 5), 0)
    set_lots(d, "S0.C1", [
        plot("S0.C1:P0", "S0.C1", 70, "AVAILABLE", in_formation("S0.C1"), "S0"),
        plot("S0.C1:W1", "S0.C1", 9, "WOUNDED", on_cell(1, 6), "S0", origin="EV-1"),
        plot("S0.C1:W2", "S0.C1", 1, "WOUNDED", on_cell(2, 4), "S0", origin="EV-2"),
    ])
    account(d, "S1.L1").update(carried=3, expended=1)
    c1_use(d, move([(2, 4), (2, 5)], [leg((2, 3), (2, 4), 0, "MIXED_FOOT"),
                                      leg((2, 4), (2, 5), 0, "MOUNTED")]))
    fr(d, "S0.C1").update(incoming=True, incoming_since_rally=True)
    fr(d, "S1.L1").update(response=response("DEFENSIVE_MISSILE", "S0.C1"), exerted=True)
    return d


def xw03_stopped():
    """AT-W29b: the stopped control."""
    d = a1("ROUGH", "XW03B")
    split_mounts(d)
    place(d, "S0.H1", (1, 7))
    place(d, "S1.L1", (2, 3), 1)
    place(d, "S0.C1", (2, 5), 4)
    set_lots(d, "S0.C1", [
        plot("S0.C1:P0", "S0.C1", 70, "AVAILABLE", in_formation("S0.C1"), "S0"),
        plot("S0.C1:W1", "S0.C1", 9, "WOUNDED", on_cell(1, 6), "S0", origin="EV-1"),
        plot("S0.C1:W2", "S0.C1", 1, "WOUNDED", on_cell(2, 5), "S0", origin="EV-2"),
    ])
    account(d, "S1.L1").update(carried=3, expended=1)
    c1_use(d, move([(2, 5), (2, 4)], [leg((2, 6), (2, 5), 4, "MIXED_FOOT")], "STOPPED"))
    fr(d, "S0.C1").update(incoming=True, incoming_since_rally=True)
    fr(d, "S1.L1").update(response=response("DEFENSIVE_MISSILE", "S0.C1"), exerted=True)
    return d


class MountLotTests(BattleCase):
    def adv(self):
        return as_adversarial(opening_document(), "M")

    def test_at_m01(self):
        for count in (79, 81):
            d = self.adv()
            mount_lots(d, "S0.C1")[0]["count"] = count
            self.reject(d, "A01")

    def test_at_m02(self):
        d = split_mounts(self.adv(), serviceable=40)
        mount_lots(d, "S0.C1")[1]["serviceability"] = "SERVICEABLE"
        self.reject(d, "A01")

    def test_at_m03(self):
        d = self.adv()
        m = copy.deepcopy(mount_lots(d, "S0.C1")[0])
        m.update(lot="S0.H1:M0", formation="S0.H1", place=in_formation("S0.H1"))
        d["mounts"] = sorted(d["mounts"] + [m], key=lambda x: x["lot"])
        self.reject(d, "A01")

    def test_at_m04_m05(self):
        canonical = split_mounts(opening_document())
        self.reject(canonical, "A04")
        self.accept(split_mounts(self.adv()))
        self.accept(B.encode_state(B.f01_supplied(B.supplied_ids()[0])))

    def test_at_m06(self):
        s = B.f01_opening(B.Variant.ROUGH, B.Orientation.STANDARD)
        board = s.scenario.board
        self.assertIs(B.movement_mode(s, C1), B.MovementMode.MOUNTED)
        self.assertEqual(B.terrain_cost(board, B.Hex(2, 4), B.TemplateKind.MOUNTED), 3)
        self.assertEqual(B.entry_cost(board, B.Hex(2, 5), B.Hex(2, 4), B.TemplateKind.MOUNTED), 3)

    def test_at_m07(self):
        s = B.f01_supplied(B.supplied_ids()[0])
        self.assertIs(B.movement_mode(s, C1), B.MovementMode.MIXED_FOOT)
        kind = B.movement_cost_kind(B.MovementMode.MIXED_FOOT, B.TemplateKind.MOUNTED)
        self.assertIs(kind, B.TemplateKind.HEAVY)
        rough = B.f01_board(B.Variant.ROUGH)
        self.assertEqual(B.terrain_cost(rough, B.Hex(0, 0), kind), 1)
        self.assertEqual(B.terrain_cost(rough, B.Hex(2, 4), kind), 2)
        heavy = [t for t in s.scenario.profile.templates if t.kind is kind][0]
        self.assertEqual(heavy.max_steps, 2)
        self.assertIs([e for e in s.scenario.roster if e.formation == C1][0].template,
                      B.TemplateKind.MOUNTED)

    def test_at_m08_m09(self):
        s = self.accept(riders(split_mounts(self.adv()), 70))
        self.assertIs(B.movement_mode(s, C1), B.MovementMode.MOUNTED)
        s = self.accept(riders(split_mounts(self.adv()), 71))
        self.assertIs(B.movement_mode(s, C1), B.MovementMode.MIXED_FOOT)

    def test_at_m14(self):
        s = self.accept(withdrawn_c1(self.adv()))
        self.assertIsNone(B.movement_mode(s, C1))
        self.assertEqual(B.mounts_of(s, B.FormationId("S0.H1")), ())
        self.assertIsNone(B.account_of(s, C1))
        with self.assertRaises(B.UnknownId):
            B.formation(s, B.FormationId("S9.X1"))


class ModeHistoryTests(BattleCase):
    def shortfall_a(self, label):
        return split_mounts(a1("OPEN", label))

    def test_at_m10_mounted_leg_with_shortfall(self):
        d = c1_use(self.shortfall_a("M10"), move([(1, 5)], [leg((1, 6), (1, 5), 4, "MOUNTED")]))
        place(d, "S0.C1", (1, 5))
        self.reject(d, "R24")

    def test_at_m11_m12(self):
        d = c1_use(self.shortfall_a("M11"),
                   move([(1, 5), (1, 4)], [leg((1, 6), (1, 5), 4, "MIXED_FOOT"),
                                           leg((1, 5), (1, 4), 4, "MIXED_FOOT")]))
        place(d, "S0.C1", (1, 4))
        s = self.accept(d)
        self.assertEqual(B.effort_charged(s, C1), 2)
        self.assertEqual(B.charge(s, C1, s.ledger.uses[0].work[0]), 2)
        d = c1_use(self.shortfall_a("M12"),
                   move([(1, 5), (1, 4), (1, 3)], [leg((1, 6), (1, 5), 4, "MIXED_FOOT")], "STOPPED"))
        place(d, "S0.C1", (1, 5))
        self.reject(d, "R21")

    def test_at_m13_mounted_rough_withdrawal(self):
        d = a1("ROUGH", "M13")
        place(d, "S0.C1", (2, 4), 4)
        c1_use(d, withdraw((2, 3), (2, 4), 4, "MOUNTED"))
        self.reject(d, "R07")

    def test_at_m15(self):
        d = c1_use(a1("OPEN", "M15"), move([(1, 5)], [leg((1, 6), (1, 5), 4, "MIXED_FOOT")]))
        place(d, "S0.C1", (1, 5))
        self.reject(d, "R24")
        d = c1_use(withdrawn_c1(a1("OPEN", "M15B")), move([(1, 5)], [leg((1, 6), (1, 5), 4, "MIXED_FOOT")]))
        self.reject(d, "R24")

    def test_at_m16_a1a(self):
        s = self.accept(a1a())
        self.assertIsNone(B.movement_mode(s, C1))
        self.assertEqual(B.effort_charged(s, C1), 1)
        self.assertEqual(B.side_totals(s, B.Side.S0).available, 1640 - 80)
        self.assertEqual(sum(m.count for m in B.mounts_of(s, C1)), 80)
        rear = a1a()
        rear["ledger"]["uses"][0]["work"][0]["legs"][0]["facing"] = 3
        self.reject(rear, "R21")
        nonunit = a1a()
        nonunit["ledger"]["uses"][0]["work"][0]["legs"][0]["origin"] = [2, 2]
        self.reject(nonunit, "R21")
        blocked = a1a("BARRIER")
        place(blocked, "S0.C1", (4, 4))
        blocked["ledger"]["uses"][0]["work"][0] = move([(4, 4)], [leg((3, 4), (4, 4), 0, "MOUNTED")])
        set_asset_place(blocked, "S0.C1", "UNASSIGNED_RECORDED", on_cell(4, 4), "S0", "OWN", "UNRESOLVED")
        self.reject(blocked, "R21")

    def test_at_m17_a1b(self):
        s = self.accept(a1b())
        self.assertEqual(B.effort_charged(s, C1), 1)
        self.assertIsNone(B.movement_mode(s, C1))
        self.assertFalse(any(type(w) is B.Evacuate for u in s.ledger.uses for w in u.work))

    def test_at_m18a_b(self):
        s = self.accept(xw03_positive())
        self.assertIs(B.movement_mode(s, C1), B.MovementMode.MOUNTED)
        d = xw03_positive()
        set_lots(d, "S0.C1", [
            plot("S0.C1:P0", "S0.C1", 71, "AVAILABLE", in_formation("S0.C1"), "S0"),
            plot("S0.C1:W1", "S0.C1", 9, "WOUNDED", on_cell(1, 6), "S0", origin="EV-1"),
        ])
        self.reject(d, "R24")

    def test_at_m18c(self):
        d = a1b()
        lot = mount_lots(d, "S0.C1")[0]
        lot["serviceability"] = "UNSERVICEABLE"
        violations = self.reject(d, "R24")
        self.assertNotIn("A01", [v.clause for v in violations])
        self.assertNotIn("A03", [v.clause for v in violations])
        self.assertNotIn("A04", [v.clause for v in violations])
        self.accept(a1b())

    def test_at_m19a(self):
        d = capitulation("M19A")
        set_lots(d, "S1.C1", [
            plot("S1.C1:P0", "S1.C1", 70, "CAPTURED", on_cell(9, 2), "S0", captured="FIT"),
            plot("S1.C1:W1", "S1.C1", 10, "CAPTURED", on_cell(9, 3), "S0", captured="WOUNDED",
                 origin="EV-5"),
        ])
        d["phase"]["record"]["exit_available"] = [0, 210]
        self.accept(d)
        with_ledger = copy.deepcopy(d)
        with_ledger["ledger"] = {"uses": [], "formations": [fr(a1(), x) for x in
                                                           [g["formation"] for g in d["formations"]]]}
        self.reject(with_ledger, "R01")

    def test_at_m19b_m19c(self):
        d = withdrawn_c1(a1("OPEN", "M19B"))
        d["clock"]["completed_rounds"] = 2
        c1_use(d, simple("Evacuate", cell=[1, 8]))
        self.accept(d)
        d = withdrawn_c1(a1("OPEN", "M19C"))
        d["ledger"]["uses"] = [
            individual("S0", "S0.C1", move([(1, 7)], [leg((1, 6), (1, 7), 0, "MOUNTED")])),
            individual("S1", "S1.H1", {"kind": "Hold"}),
            individual("S0", "S0.C1", simple("Evacuate", cell=[1, 8])),
        ]
        fr(d, "S0.C1")["exerted"] = True
        self.reject(d, "R04")



