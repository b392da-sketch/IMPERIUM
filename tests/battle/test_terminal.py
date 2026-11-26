"""14.8 terminal records (AT-T01–T15) and restored H rows."""

import copy

import imperium.battle as B
from tests.battle.common import (
    BattleCase, a1, at_exit, f, fround, on_cell, place, plot, set_asset_place, set_lots, terminal,
    unheld, ORDER,
)
from tests.battle.scenarios import (
    S0_CELLS, S1_CELLS, capitulation, collapse, count_of, deadline_objective_victory,
)
from tests.support.battle_builder import as_adversarial, opening_document

CONTESTING = ("CONTESTING", "CONTESTING")


def record(d):
    return d["phase"]["record"]


def deplete(d, side_cells, side, keep=None):
    for fid, cell in side_cells.items():
        if fid == keep:
            continue
        f(d, fid)["disposition"] = "DEPLETED"
        set_lots(d, fid, [plot(f"{fid}:D1", fid, count_of(fid), "DEAD", on_cell(*cell), None,
                               origin="EV-1")])
        set_asset_place(d, fid, "UNASSIGNED_RECORDED", on_cell(*cell), side, "OWN", "UNRESOLVED")
    return d


def withdraw_all(d, side_cells, side, depleted=()):
    """Every listed formation WITHDRAWN on the exit row, or DEPLETED in place."""
    row = 0 if side == "S1" else 8
    for i, (fid, cell) in enumerate(sorted(side_cells.items())):
        if fid in depleted:
            deplete(d, {fid: cell}, side)
            continue
        place(d, fid, (i + 1, row), disposition="WITHDRAWN")
        set_lots(d, fid, [plot(f"{fid}:P0", fid, count_of(fid), "AVAILABLE", at_exit(side), side)])
        set_asset_place(d, fid, "ASSIGNED", at_exit(side), side, "OWN", "NOT_APPLICABLE")
    return d


def deadline(label, reason, result, winner, defeat, postures, objective=None):
    d = as_adversarial(opening_document(), label)
    d["clock"] = {"completed_rounds": 12, "event_cursor": 40}
    for i, p in enumerate(postures):
        d["sides"][i]["posture"] = p
    d["phase"] = terminal(reason, result, winner, defeat, "ROUND_END", 12, objective or unheld(),
                          postures, (8, 8), (1640, 1640), (0, 0))
    return d


def mutual_loss(label="T02", point="ROUND_END", completed=5, charged=5):
    d = collapse(label, point, completed, charged)
    f(d, "S0.H1")["disposition"] = "ROUTING"
    deplete(d, S0_CELLS, "S0", keep="S0.H1")
    d["phase"] = terminal("ZERO_VIABILITY_MUTUAL_LOSS", "DRAW", None, ("COLLAPSE", "COLLAPSE"),
                          point, charged, unheld(), CONTESTING, (0, 0), (240, 240), (0, 0))
    return d


def abandonment(label="T03"):
    d = collapse(label)
    d["sides"][0]["posture"] = "WITHDRAWING"
    d["phase"] = terminal("ZERO_VIABILITY_MUTUAL_ABANDONMENT", "DRAW", None, (None, "COLLAPSE"),
                          "ROUND_END", 5, unheld(), ("WITHDRAWING", "CONTESTING"), (8, 0),
                          (1640, 240), (0, 0))
    return d


def departure(label, depleted=()):
    d = as_adversarial(opening_document(), label)
    d["clock"] = {"completed_rounds": 5, "event_cursor": 20}
    withdraw_all(d, S1_CELLS, "S1", depleted)
    exit_ = sum(count_of(x) for x in S1_CELLS if x not in depleted)
    defeat = "DEPLETION_MIXED" if depleted else "DEPARTURE"
    d["phase"] = terminal("ZERO_VIABILITY_UNILATERAL", "VICTORY", "S0", (None, defeat),
                          "ROUND_END", 5, unheld(), CONTESTING, (8, 0), (1640, 0), (0, exit_))
    return d


class TerminalReasonTests(BattleCase):
    def reject_any(self, doc, clauses):
        violations = self.violations(doc)
        found = {v.clause for v in violations}
        self.assertTrue(found & set(clauses), msg=f"{clauses} not in {violations}")
        return violations

    def test_at_t01(self):
        self.accept(collapse())
        d = collapse()
        record(d)["defeat"] = [None, "DEPARTURE"]
        self.reject(d, "X03")

    def test_at_t02(self):
        self.accept(mutual_loss())
        d = mutual_loss()
        record(d)["winner"] = "S0"
        self.reject(d, "T14")

    def test_at_t03(self):
        self.accept(abandonment())
        d = abandonment()
        record(d).update(result="VICTORY", winner="S0")
        self.reject(d, "X03")

    def test_at_t04(self):
        self.accept(capitulation())
        d = capitulation()
        d["clock"]["completed_rounds"] = 0
        record(d).update(point="INITIAL_CHECK", charged_rounds=0)
        self.reject_any(d, ("X02", "X06"))
        d = capitulation()
        f(d, "S1.H3")["disposition"] = "ORGANIZED"
        self.reject_any(d, ("F07", "F08", "L08", "X02"))

    def test_at_t05(self):
        fid = B.FixtureId("F01-v1-defensive-mutual-capitulation")
        doc = B.encode_state(B.f01_supplied(fid))
        self.accept(doc)
        for cls in ("CANONICAL_OPENING", "ADVERSARIAL_TEST"):
            d = copy.deepcopy(doc)
            d["scenario"]["provenance"]["fixture_class"] = cls
            self.reject_any(d, ("X05", "P10", "P07", "P08", "P09"))
        d = copy.deepcopy(doc)
        lots = [p for p in d["personnel"] if p["lineage"] == "S1.H3"]
        set_lots(d, "S1.H3", [plot("S1.H3:P0", "S1.H3", 240, "CAPTURED", on_cell(6, 2), "S0",
                                   captured="FIT")])
        self.reject_any(d, ("X05", "P10"))
        self.assertTrue(lots)
        d = copy.deepcopy(doc)
        d["formations"][0]["facing"] = 5
        self.reject(d, "P10")

    def test_at_t06(self):
        self.accept(deadline("T06", "DEADLINE_ABANDONMENT", "VICTORY", "S0", (None, "ABANDONMENT"),
                             ("CONTESTING", "WITHDRAWING")))
        d = deadline("T06B", "DEADLINE_ABANDONMENT", "VICTORY", "S0", (None, "ABANDONMENT"),
                     ("CONTESTING", "WITHDRAWING"))
        d["clock"]["completed_rounds"] = 11
        record(d)["charged_rounds"] = 11
        self.reject_any(d, ("X04", "X06"))

    def test_at_t07(self):
        self.accept(deadline("T07", "DEADLINE_MUTUAL_WITHDRAWAL", "DRAW", None, (None, None),
                             ("WITHDRAWING", "WITHDRAWING")))
        self.reject(deadline("T07B", "DEADLINE_MUTUAL_WITHDRAWAL", "DRAW", None, (None, "ABANDONMENT"),
                             ("WITHDRAWING", "WITHDRAWING")), "X04")

    def test_at_t08(self):
        self.accept(deadline_objective_victory())
        d = deadline_objective_victory("T08B")
        d["sides"][1]["posture"] = "WITHDRAWING"
        record(d)["postures"] = ["CONTESTING", "WITHDRAWING"]
        self.reject(d, "X04")
        d = deadline_objective_victory("T08C")
        record(d)["defeat"] = [None, "ABANDONMENT"]
        self.reject(d, "X04")

    def test_at_t09(self):
        self.accept(deadline("T09", "DEADLINE_OBJECTIVE_UNRESOLVED", "DRAW", None, (None, None),
                             CONTESTING))
        for winner in ("S0", "S1"):
            self.reject(deadline("T09B", "DEADLINE_OBJECTIVE_UNRESOLVED", "VICTORY", winner,
                                 (None, None), CONTESTING), "X04")

    def test_at_t15(self):
        self.accept(departure("T15"))
        self.accept(departure("T15B", depleted=("S1.H1",)))
        d = departure("T15C", depleted=("S1.H1",))
        record(d)["defeat"] = [None, "DEPARTURE"]
        self.reject(d, "X03")


class ClockPointTests(BattleCase):
    def test_at_t10(self):
        self.accept(collapse("T10A", "INITIAL_CHECK", 0, 0))
        self.accept(collapse("T10B", "AFTER_ROOT", 0, 1))
        self.accept(collapse("T10C", "ROUND_END", 1, 1))
        self.accept(collapse("T10D", "AFTER_CLOSURE_DISPLACEMENT", 0, 1))
        for point, completed, charged in (("ROUND_END", 0, 0), ("AFTER_ROOT", 0, 0),
                                          ("AFTER_CLOSURE_DISPLACEMENT", 0, 0),
                                          ("ROUND_END", 12, 13)):
            with self.subTest(point=point, charged=charged):
                self.reject(collapse("T10X", point, completed, charged), "H03")

    def test_h03a_elapsed(self):
        s = self.accept(collapse("T10E", "AFTER_ROOT", 3, 4))
        self.assertEqual(B.elapsed_minutes(s), 40)

    def test_at_t11(self):
        for key, value in (("viable", [8, 1]), ("onmap_available", [1640, 239]),
                           ("exit_available", [0, 1]), ("postures", ["CONTESTING", "WITHDRAWING"]),
                           ("objective", {"kind": "SECURE", "side": "S0"})):
            d = collapse("T11")
            record(d)[key] = value
            with self.subTest(key=key):
                self.reject(d, "X01")

    def test_at_t12(self):
        d = collapse("T12")
        d["ledger"] = {"uses": [], "formations": [fround(x) for x in ORDER]}
        self.reject(d, "R01")

    def test_at_t13(self):
        self.accept(collapse("T13A", "ROUND_END", 5, 5))
        d = deadline("T13B", "DEADLINE_OBJECTIVE_UNRESOLVED", "DRAW", None, (None, None), CONTESTING)
        d["clock"]["completed_rounds"] = 5
        record(d)["charged_rounds"] = 5
        self.reject(d, "X06")
        d = deadline("T13C", "DEADLINE_OBJECTIVE_UNRESOLVED", "DRAW", None, (None, None), CONTESTING)
        d["clock"]["completed_rounds"] = 0
        record(d).update(point="INITIAL_CHECK", charged_rounds=0)
        self.reject(d, "X06")
        d = capitulation("T13D")
        record(d)["point"] = "ROUND_END"
        record(d)["charged_rounds"] = 3
        self.reject(d, "X06")

    def test_at_t13b(self):
        d = collapse("T13E", "INITIAL_CHECK", 0, 0)
        d["sides"][0]["posture"] = "WITHDRAWING"
        record(d)["postures"] = ["WITHDRAWING", "CONTESTING"]
        self.reject(d, "X06")
        d = abandonment("T13F")
        d["clock"]["completed_rounds"] = 0
        record(d).update(point="INITIAL_CHECK", charged_rounds=0)
        self.reject(d, "X06")

    def test_at_t13c(self):
        self.accept(collapse("T13G", "INITIAL_CHECK", 0, 0))
        self.accept(mutual_loss("T13H", "INITIAL_CHECK", 0, 0))


class PhaseClockTests(BattleCase):
    def test_h01a(self):
        for edit in (lambda d: d["clock"].update(completed_rounds=1),
                     lambda d: d["clock"].update(event_cursor=1),
                     lambda d: d["sides"][1].update(posture="WITHDRAWING")):
            d = as_adversarial(opening_document(), "H01")
            edit(d)
            self.reject(d, "H01")

    def test_h02a_h02b(self):
        d = a1("OPEN", "H02")
        d["clock"]["completed_rounds"] = 12
        self.reject(d, "H02")
        d = a1("OPEN", "H02B")
        d["clock"]["completed_rounds"] = 11
        d["phase"]["side"] = "S1"
        self.accept(d)
        d = a1("OPEN", "H02C")
        for fid in S1_CELLS:
            f(d, fid)["disposition"] = "ROUTING"
            f(d, fid)["condition"].update(cohesion=2, morale=2)
            d["ledger"]["formations"][ORDER.index(fid)]["displacement_attempted"] = True
        self.reject(d, "H02")
