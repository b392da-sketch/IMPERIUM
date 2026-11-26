"""14.2 personnel and asset custody; restored F, L and A rows (14.11)."""

import copy

import imperium.battle as B
from tests.battle.common import (
    BattleCase, a1, account, at_exit, f, fi, in_formation, mount_lots, on_cell, place, plot,
    set_asset_place, set_lots,
)
from tests.battle.scenarios import capitulation, collapse
from tests.support.battle_builder import as_adversarial, edit, opening_document

H1 = B.FormationId("S0.H1")


def adv(label="L"):
    return as_adversarial(opening_document(), label)


def h1_split(d):
    return set_lots(d, "S0.H1", [
        plot("S0.H1:D1", "S0.H1", 10, "DEAD", on_cell(2, 6), None, origin="EV-1"),
        plot("S0.H1:P0", "S0.H1", 200, "AVAILABLE", in_formation("S0.H1"), "S0"),
        plot("S0.H1:W1", "S0.H1", 30, "WOUNDED", on_cell(2, 6), "S0", origin="EV-1"),
    ])


def lot(d, lot_id):
    for l in d["personnel"]:
        if l["lot"] == lot_id:
            return l
    raise KeyError(lot_id)


class PersonnelTests(BattleCase):
    def test_at_l01_l02a(self):
        for count in (239, 241, 5000):
            d = adv()
            lot(d, "S0.H1:P0")["count"] = count
            self.reject(d, "L02")

    def test_at_l02(self):
        s = self.accept(h1_split(adv()))
        self.assertEqual(B.available(s, H1), 200)
        self.assertEqual((B.wounded(s, H1), B.dead(s, H1), B.captured(s, H1)), (30, 10, 0))

    def test_l02d_extra_wounded(self):
        d = h1_split(adv())
        d["personnel"].append(plot("S0.H1:W2", "S0.H1", 77, "WOUNDED", on_cell(2, 6), "S0", origin="EV-2"))
        d["personnel"].sort(key=lambda l: l["lot"])
        self.reject(d, "L02")

    def test_at_l03_wounded_in_formation(self):
        d = h1_split(adv())
        lot(d, "S0.H1:W1")["place"] = in_formation("S0.H1")
        self.reject(d, "L04")

    def test_l04a_l05a(self):
        d = h1_split(adv())
        lot(d, "S0.H1:W1")["place"] = at_exit("S0")
        self.reject(d, "L04")
        d = h1_split(adv())
        lot(d, "S0.H1:W1")["custodian"] = "S1"
        self.reject(d, "L04")
        d = h1_split(adv())
        lot(d, "S0.H1:D1")["place"] = in_formation("S0.H1")
        self.reject(d, "L05")
        d = h1_split(adv())
        lot(d, "S0.H1:D1")["place"] = at_exit("S0")
        self.reject(d, "L05")

    def test_l03a(self):
        for key, value in [("place", in_formation("S0.H2")), ("place", on_cell(2, 6)),
                           ("custodian", "S1"), ("origin", "EV-9")]:
            with self.subTest(key=key, value=value):
                d = adv()
                lot(d, "S0.H1:P0")[key] = value
                self.reject(d, "L03")

    def test_at_l04_unknown_lineage(self):
        d = adv()
        lot(d, "S0.H1:P0")["lineage"] = "S9.X1"
        self.reject(d, "L01")

    def test_at_l05_fit_capture_elsewhere(self):
        d = capitulation()
        lot(d, "S1.H3:P0")["place"] = on_cell(6, 0)
        self.reject(d, "L07")

    def test_at_l06_captured_wounded_at_earlier_cell(self):
        self.accept(capitulation())

    def test_at_l07_l06a_captured_in_a(self):
        d = a1()
        set_lots(d, "S1.H1", [
            plot("S1.H1:C1", "S1.H1", 10, "CAPTURED", on_cell(8, 2), "S0", captured="WOUNDED"),
            plot("S1.H1:P0", "S1.H1", 230, "AVAILABLE", in_formation("S1.H1"), "S1"),
        ])
        self.reject(d, "L06")
        cap = capitulation()
        lot(cap, "S1.H1:W1")["custodian"] = "S1"
        self.reject(cap, "L06")

    def test_l06a_winner_lot_captured(self):
        d = capitulation()
        set_lots(d, "S0.H1", [
            plot("S0.H1:C1", "S0.H1", 10, "CAPTURED", on_cell(2, 6), "S1", captured="WOUNDED",
                 origin="EV-3"),
            plot("S0.H1:P0", "S0.H1", 230, "AVAILABLE", in_formation("S0.H1"), "S0"),
        ])
        self.reject(d, "L06")

    def test_at_l16_withdrawn_lineage(self):
        self.accept(capitulation())  # S1.H1 is WITHDRAWN with captured wounded
        d = capitulation()
        d["personnel"].append(plot("S1.H1:F1", "S1.H1", 0 + 10, "CAPTURED", on_cell(8, 0), "S0",
                                   captured="FIT"))
        lot(d, "S1.H1:P0")["count"] = 200
        d["personnel"].sort(key=lambda l: l["lot"])
        self.reject(d, "L07")

    def _l16b(self, cell):
        d = capitulation("L16B")
        set_lots(d, "S1.H2", [
            plot("S1.H2:D1", "S1.H2", 200, "DEAD", on_cell(7, 2), None, origin="EV-2"),
            plot("S1.H2:W1", "S1.H2", 40, "CAPTURED", on_cell(*cell), "S0", captured="WOUNDED",
                 origin="EV-4"),
        ])
        return d

    def test_at_l16b(self):
        self.accept(self._l16b((8, 1)))
        self.accept(self._l16b((7, 1)))
        d = self._l16b((8, 1))
        lot(d, "S1.H2:W1")["custodian"] = "S1"
        self.reject(d, "L06")
        d = self._l16b((8, 1))
        lot(d, "S1.H2:W1")["place"] = at_exit("S1")
        self.reject(d, "L06")

    def test_at_l17_l08b(self):
        self.accept(capitulation())
        d = capitulation()
        lot(d, "S1.H1:P0").update(status="CAPTURED", captured="FIT", place=on_cell(8, 0), custodian="S0")
        self.reject(d, "L07")

    def test_l08a_untransferred_wounded(self):
        d = capitulation()
        lot(d, "S1.H1:W1").update(status="WOUNDED", captured=None, custodian="S1")
        self.reject(d, "L08")

    def test_at_l15_l09(self):
        d = adv()
        set_lots(d, "S0.H1", [
            plot("S0.H1:P0", "S0.H1", 230, "AVAILABLE", in_formation("S0.H1"), "S0"),
            plot("S0.H1:W1", "S0.H1", 5, "WOUNDED", on_cell(2, 6), "S0", origin="EV-1"),
            plot("S0.H1:W2", "S0.H1", 5, "WOUNDED", on_cell(2, 6), "S0", origin="EV-2"),
        ])
        self.accept(d)
        lot(d, "S0.H1:W2")["origin"] = "EV-1"
        self.reject(d, "L09")

    def test_at_l14_dispersed_token(self):
        d = adv()
        lot(d, "S0.H1:P0")["status"] = "DISPERSED"
        self.decode_code(d, "TOKEN", f"/personnel/{d['personnel'].index(lot(d, 'S0.H1:P0'))}/status")

    def test_x_l01_duplicate_lot_and_types(self):
        d = adv()
        dup = copy.deepcopy(lot(d, "S0.H1:P0"))
        i = d["personnel"].index(lot(d, "S0.H1:P0"))
        d["personnel"].insert(i, dup)
        self.decode_code(d, "NONCANONICAL", "/personnel")
        d = adv()
        lot(d, "S0.H1:P0")["count"] = True
        self.decode_code(d, "JSON_TYPE")
        d = adv()
        lot(d, "S0.H1:P0")["count"] = -1
        self.decode_code(d, "CLAUSE")


class AssetTests(BattleCase):
    def test_at_l08_l09_depleted_account(self):
        d = collapse()
        account(d, "S1.H2").update(assignment="ASSIGNED", place=in_formation("S1.H2"),
                                   recovery="NOT_APPLICABLE")
        self.reject(d, "A03")
        d = collapse()
        account(d, "S1.H2")["custodian"] = "S0"
        self.reject(d, "A03")
        d = collapse()
        account(d, "S1.H2").update(custodian="S0", custody="SURRENDERED_INVENTORY")
        self.reject(d, "A03")

    def test_at_l10_surrendered_account_still_own(self):
        d = capitulation()
        account(d, "S1.H3").update(assignment="ASSIGNED", place=in_formation("S1.H3"),
                                   custodian="S1", custody="OWN")
        self.reject(d, "A03")

    def test_at_l11_depleted_transferred_at_capitulation(self):
        d = capitulation()
        account(d, "S1.H2").update(custodian="S0", custody="SURRENDERED_INVENTORY",
                                   recovery="NOT_APPLICABLE")
        self.reject(d, "A03")

    def test_at_l11b_depleted_stays_own(self):
        s = self.accept(capitulation())
        a = B.account_of(s, B.FormationId("S1.H2"))
        self.assertEqual((a.custody, a.recovery, a.custodian), (B.Custody.OWN, B.Recovery.UNRESOLVED, B.Side.S1))
        self.assertEqual(a.place, B.OnCell(B.Hex(7, 2)))

    def test_at_l12_totals_by_lineage(self):
        s = self.accept(capitulation())
        s0 = B.side_totals(s, B.Side.S0)
        s1 = B.side_totals(s, B.Side.S1)
        self.assertEqual((s0.available, s0.mounts, s0.ammunition_carried), (1640, 80, 16))
        self.assertEqual((s1.available, s1.wounded, s1.dead, s1.captured, s1.mounts,
                          s1.ammunition_carried), (210, 0, 240, 1190, 80, 16))
        self.assertEqual(B.onmap_available(s, B.Side.S0), 1640)
        self.assertEqual(B.exit_available(s, B.Side.S1), 210)
        self.assertEqual(B.captured(s, B.FormationId("S1.H3")), 240)

    def test_at_l13_a02a(self):
        for fid, carried, expended in (("S0.L1", 5, 0), ("S0.H1", 2, 1)):
            d = adv()
            account(d, fid).update(carried=carried, expended=expended)
            self.reject(d, "A02")
        d = adv()
        account(d, "S0.H1").update(carried=0, expended=2)
        self.accept(d)
        d = adv()
        c1 = copy.deepcopy(account(d, "S0.H1"))
        c1["formation"] = "S0.C1"
        d["ammunition"].append(c1)
        d["ammunition"].sort(key=lambda a: a["formation"])
        self.reject(d, "A02")

    def test_a03b_each_row_of_table_8_5(self):
        self.accept(adv())  # ORGANIZED
        d = a1()
        f(d, "S0.H1")["disposition"] = "REFORMING"
        self.accept(d)  # REFORMING
        self.accept(collapse())  # ROUTING and DEPLETED
        self.accept(capitulation())  # WITHDRAWN, DEPLETED, SURRENDERED

    def test_x_l04_withdrawn_assets_in_formation(self):
        d = capitulation()
        account(d, "S1.H1")["place"] = in_formation("S1.H1")
        self.reject(d, "A03")

    def test_a01a_mount_lot_on_heavy(self):
        d = adv()
        m = copy.deepcopy(mount_lots(d, "S0.C1")[0])
        m.update(lot="S0.H1:M0", formation="S0.H1", place=in_formation("S0.H1"))
        d["mounts"].append(m)
        d["mounts"].sort(key=lambda x: x["lot"])
        self.reject(d, "A01")


class FormationTests(BattleCase):
    def test_f01a(self):
        d = adv()
        d["formations"] = d["formations"][:-1]
        self.reject(d, "F01")
        d = adv()
        d["formations"][2] = copy.deepcopy(d["formations"][1])
        self.reject(d, "F01")

    def test_f02a_f02b_at_k07(self):
        d = adv()
        place(d, "S0.H2", (2, 6))
        self.reject(d, "F02")
        d = adv()
        place(d, "S0.H1", (5, 5), disposition="DEPLETED")
        set_lots(d, "S0.H1", [plot("S0.H1:D1", "S0.H1", 240, "DEAD", on_cell(5, 5), None, origin="EV-1")])
        set_asset_place(d, "S0.H1", "UNASSIGNED_RECORDED", on_cell(5, 5), "S0", "OWN", "UNRESOLVED")
        place(d, "S0.H2", (5, 5))
        self.accept(d)

    def test_f03a(self):
        d = adv()
        for e in (6, 7):
            f(d, "S0.H1")["condition"]["exertion"] = e
            self.decode_code(d, "CLAUSE")
            self.assertEqual(self.violations(d)[0].clause, "T09")
        f(d, "S0.H1")["condition"].update(exertion=5, fatigue=2)
        self.accept(d)

    def test_f04a_f04b(self):
        d = adv()
        f(d, "S0.H1")["condition"].update(cohesion=2, morale=2)
        self.reject(d, "F04")
        for disposition, c, m, fat in (("ORGANIZED", 2, 1, 0), ("ORGANIZED", 1, 2, 2)):
            d = adv()
            f(d, "S0.H1")["condition"].update(cohesion=c, morale=m, fatigue=fat)
            self.accept(d)
        d = a1()
        f(d, "S0.H1")["disposition"] = "REFORMING"
        f(d, "S0.H1")["condition"].update(cohesion=2, morale=2)
        self.accept(d)

    def test_f05a_f05b(self):
        d = adv()
        f(d, "S0.H1")["disposition"] = "WITHDRAWN"
        set_lots(d, "S0.H1", [plot("S0.H1:P0", "S0.H1", 240, "AVAILABLE", at_exit("S0"), "S0")])
        set_asset_place(d, "S0.H1", "ASSIGNED", at_exit("S0"), "S0", "OWN", "NOT_APPLICABLE")
        self.reject(d, "F05")
        place(d, "S0.H1", (2, 8))
        self.accept(d)
        m = as_adversarial(opening_document("OPEN", "MIRRORED"), "F05")
        f(m, "S0.H1")["disposition"] = "WITHDRAWN"
        place(m, "S0.H1", (8, 0))
        set_lots(m, "S0.H1", [plot("S0.H1:P0", "S0.H1", 240, "AVAILABLE", at_exit("S0"), "S0")])
        set_asset_place(m, "S0.H1", "ASSIGNED", at_exit("S0"), "S0", "OWN", "NOT_APPLICABLE")
        self.accept(m)

    def test_f06a(self):
        d = adv()
        set_lots(d, "S0.H1", [plot("S0.H1:D1", "S0.H1", 240, "DEAD", on_cell(2, 6), None)])
        self.reject(d, "F06")
        d = collapse()
        set_lots(d, "S1.H2", [
            plot("S1.H2:D1", "S1.H2", 230, "DEAD", on_cell(7, 2), None, origin="EV-1"),
            plot("S1.H2:P0", "S1.H2", 10, "AVAILABLE", in_formation("S1.H2"), "S1"),
        ])
        self.reject(d, "F06")

    def test_f07a(self):
        d = a1()
        f(d, "S1.H3")["disposition"] = "SURRENDERED"
        self.reject(d, "F07")
        self.reject(as_adversarial(edit(opening_document(), f"/formations/{fi('S1.H3')}/disposition",
                                        "SURRENDERED"), "F07"), "F07")

    def test_f08a(self):
        d = capitulation()
        f(d, "S1.H3")["disposition"] = "ORGANIZED"
        self.reject(d, "F08")
