"""TA-P4-C01 to C06, E01, F02, F03, F05, G01, G02 and H01: admission, plus
the 35 bound first-fault conflict rows (E06), each at its exact code, path
and detail with the input unchanged.

Rows that need a priced edge use the declared geometry-only seam: the
pure admission function on a field bundle whose board carries a surcharge
(F05). No production fixture or P1 state is added.
"""

import dataclasses
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.board import EdgeRule
from imperium.battle.engine import movement
from imperium.battle.queries import Fields, activation, effort_remaining
from imperium.battle.records import STATE_FIELDS
from imperium.battle.state import state_values
from tests.battle.common import fround, response
from tests.engine.helpers import hold_use, make_reformer, pass_use
from tests.movement.support import (
    S0, S1, MovementCase, cond, doc, ev, f, fid, fr, gid, gm, gp, hx, mv, opened, place, pv,
    rejection_oracles, state_of, wd,
)

R = E.RejectCode
NOT_READY = R.NOT_READY


def contact(d, low, high):
    d["contacts"].append({"low": low, "high": high,
                          "edge": [list(f(d, low)["cell"]), list(f(d, high)["cell"])]})
    return d


def responded(d, token, target):
    fr(d, token)["response"] = response("DEFENSIVE_PIVOT", target)
    fr(d, token)["exerted"] = True
    return d


def seam(state, edges):
    """Field values with the board's edge rules replaced (pure seam)."""
    values = dict(zip(STATE_FIELDS, state_values(state)))
    scenario = values["scenario"]
    values["scenario"] = dataclasses.replace(
        scenario, board=dataclasses.replace(scenario.board, edges=tuple(edges)))
    return Fields(**values)


class Case(MovementCase):

    def accepted(self, state, command, stages=None):
        """Accepted, declining any window the order opens (admission only)."""
        r = E.step(state, command)
        if type(r) is E.Suspended:
            w = r.root.window
            r = E.step(r.root, E.DeclineResponse(w.side, w.window_id))
            self.assertIs(type(r), E.Accepted, msg=repr(r)[:300])
            return r.state
        return super().accepted(state, command, stages)

    def no(self, state, command, code, path, detail=None):
        if detail is None:
            detail = rejection_oracles()[code.name]["detail"]
        return self.rejected(state, command, code, path, detail)


# --------------------------------------------------------------------------
# C: move admission


class C01Positives(Case):

    def test_heavy_mounted_light(self):
        st = state_of(doc())
        after = self.accepted(st, mv("S0.H4", (5, 5), (5, 4)))
        self.assertEqual(effort_remaining(_fields(after), fid("S0.H4")), 1)
        after = self.accepted(st, mv("S0.C1", (1, 5), (1, 4), (1, 3)))
        self.assertEqual(effort_remaining(_fields(after), fid("S0.C1")), 0)
        after = self.accepted(st, mv("S0.L1", (4, 4), (4, 3)))
        self.assertEqual(B.formation(after, fid("S0.L1")).cell, hx(4, 3))

    def test_exact_remaining_after_response_on_last_slot(self):
        d = doc()
        d["ledger"]["uses"] = [hold_use("S0", "S0.H1"), hold_use("S1", "S1.H1"),
                               hold_use("S0", "S0.H2"), hold_use("S1", "S1.H2"),
                               hold_use("S0", "S0.H3"), hold_use("S1", "S1.H3")]
        responded(d, "S0.H4", "S1.H4")
        st = state_of(d)
        self.assertEqual(effort_remaining(_fields(st), fid("S0.H4")), 2)
        after = self.accepted(st, mv("S0.H4", (5, 5), (5, 4)))
        fields = _fields(after)
        self.assertEqual(effort_remaining(fields, fid("S0.H4")), 0)
        self.assertIs(activation(fields, fid("S0.H4")), B.Activation.SPENT)
        self.assertIs(activation(fields, fid("S0.H5")), B.Activation.FORFEITED)
        self.assertIs(activation(fields, fid("S0.H1")), B.Activation.SPENT)


def _fields(state):
    return Fields(**dict(zip(STATE_FIELDS, state_values(state))))


class C02Negatives(Case):

    def test_cap_effort_repeat_front(self):
        st = state_of(doc())
        self.no(st, mv("S0.H4", (5, 5), (5, 4), (5, 3)), R.OVER_CAP, "/path")
        self.no(st, mv("S0.L1", (4, 4), (4, 3), (4, 2)), R.OVER_CAP, "/path")
        self.no(st, mv("S0.H4", (5, 5), (5, 6)), R.REPEATED_CELL, "/path/1")
        self.no(st, mv("S0.H4", (6, 6)), R.NOT_FRONT, "/path/0")
        rough = state_of(doc_variant("ROUGH"))
        self.no(rough, mv("S0.C1", (2, 5), (2, 4)), R.OVER_EFFORT, "/path")
        self.accepted(rough, mv("S0.H1", (2, 5), (2, 4)))      # heavy open+rough = 3


def doc_variant(variant, orientation="STANDARD"):
    from tests.battle.common import a1
    return a1(variant=variant, label="P4-" + variant, orientation=orientation)


class C04PredictedStops(Case):

    def test_threatened_nonfinal_cell(self):
        d = doc()
        place(d, "S1.H4", (5, 3), facing=1)          # threatens (5,4) and (4,4)
        st = state_of(d)
        self.no(st, mv("S0.L1", (4, 4), (4, 3)), R.PAST_STOP, "/path/1")
        self.accepted(st, mv("S0.L1", (4, 4)))

    def test_own_exertion(self):
        st = state_of(cond(doc(), "S0.H4", fat=1, e=5))
        self.no(st, mv("S0.H4", (5, 5), (5, 4)), R.PAST_STOP, "/path/1")
        after = self.accepted(st, mv("S0.H4", (5, 5)))
        c = B.formation(after, fid("S0.H4")).condition
        self.assertEqual((c.fatigue, c.exertion), (2, 0))
        st = state_of(cond(doc(), "S0.H4", fat=1, e=4))
        after = self.accepted(st, mv("S0.H4", (5, 5), (5, 4)))
        c = B.formation(after, fid("S0.H4")).condition
        self.assertEqual((c.fatigue, c.exertion), (2, 0))
        legs = after.ledger.uses[-1].work[0].legs
        self.assertEqual(len(legs), 2)


class C05Origins(Case):

    def test_engaged_beats_threatened(self):
        d = doc()
        place(d, "S0.H4", (5, 4), facing=4)
        place(d, "S1.H4", (5, 3), facing=1)
        contact(d, "S0.H4", "S1.H4")
        self.no(state_of(d), mv("S0.H4", (6, 3)), R.ENGAGED, "/formation")

    def test_threatened_origin(self):
        d = doc()
        place(d, "S0.H4", (5, 4), facing=4)
        place(d, "S1.H4", (5, 3), facing=1)
        self.no(state_of(d), mv("S0.H4", (6, 3)), R.THREATENED_ORIGIN, "/formation")


class C06Withdrawing(Case):

    def test_progress(self):
        d = doc()
        d["sides"][0]["posture"] = "WITHDRAWING"
        place(d, "S0.H4", (5, 6), facing=0)
        st = state_of(d)
        self.no(st, mv("S0.H4", (6, 6)), R.NO_EXIT_PROGRESS, "/path/0")
        self.no(st, mv("S0.H4", (5, 7), (6, 7)), R.NO_EXIT_PROGRESS, "/path/1")
        self.accepted(st, mv("S0.H4", (5, 7)))

    def test_logical_exit_row_under_mirror(self):
        d = doc_variant("OPEN", "MIRRORED")
        d["sides"][0]["posture"] = "WITHDRAWING"
        place(d, "S0.H4", (5, 2), facing=3)          # S0's exit row is 0 when mirrored
        st = state_of(d)
        self.no(st, mv("S0.H4", (4, 2)), R.NO_EXIT_PROGRESS, "/path/0")
        self.accepted(st, mv("S0.H4", (5, 1)))


# --------------------------------------------------------------------------
# E: pivot


class E01Pivot(Case):

    def test_half_turn_both_ways(self):
        st = state_of(doc())
        for turn in (1, -1):
            after = self.accepted(st, pv("S0.H4", turn, 3),
                                  (E.Stage.ROOT, E.Stage.PIVOT, E.Stage.IMMEDIATE_CHECK))
            g = B.formation(after, fid("S0.H4"))
            self.assertEqual((g.facing, g.cell, g.condition.exertion), (1, hx(5, 6), 3))
            self.assertEqual(effort_remaining(_fields(after), fid("S0.H4")), 0)

    def test_threat_restrictions(self):
        d = doc()
        place(d, "S0.H4", (5, 4), facing=4)
        place(d, "S1.L1", (9, 3))
        place(d, "S1.H4", (5, 3), facing=1)
        st = state_of(d)
        self.no(st, pv("S0.H4", 1, 2), R.PIVOT_RESTRICTED, "/steps")
        self.accepted(st, pv("S0.H4", 1, 1))
        place(d, "S1.L1", (9, 3))
        place(d, "S1.H3", (6, 3), facing=2)          # second source on (5,4)
        self.no(state_of(d), pv("S0.H4", 1, 1), R.PIVOT_RESTRICTED, "/formation")
        contact(d, "S0.H4", "S1.H4")
        self.no(state_of(d), pv("S0.H4", 1, 1), R.ENGAGED, "/formation")

    def test_no_cap_at_f2_or_c2(self):
        st = state_of(cond(doc(), "S0.H4", c=2, fat=2))
        after = self.accepted(st, pv("S0.H4", -1, 3))
        self.assertEqual(B.formation(after, fid("S0.H4")).facing, 1)


# --------------------------------------------------------------------------
# F: group orders


class F02Group(Case):

    def test_whole_order_rejections(self):
        st = state_of(doc())
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H2"), 6), R.BAD_VALUE, "/direction")
        self.no(st, gm("S0.G1", ("S0.H2", "S0.H1"), 4), R.BAD_VALUE, "/members")
        self.no(st, gm("S0.G9", ("S0.H1", "S0.H2"), 4), R.UNKNOWN_GROUP, "/group")
        self.no(st, E.GroupMoveOrder(S0, gid("S1.G1"), (fid("S1.H1"), fid("S1.H2")), 4),
                R.NOT_OWN_GROUP, "/group")
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H3"), 4), R.NOT_IN_GROUP, "/members/1")
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H2"), 0), R.NOT_FRONT, "/members/0")
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H5"), 4), R.NOT_CONNECTED, "/members")
        d = doc()
        place(d, "S0.L1", (2, 5))                     # stationary blocker
        self.no(state_of(d), gm("S0.G1", ("S0.H1", "S0.H2"), 4), R.OCCUPIED, "/members/0")
        d = doc()
        d["authority"][0][1] = "INACTIVE"
        self.no(state_of(d), gm("S0.G1", ("S0.H1", "S0.H2"), 4), R.NO_AUTHORITY, "/group")

    def test_e06_withdrawing_group_progress(self):
        command = gm("S0.G1", ("S0.H1", "S0.H2", "S0.H5"), 4)
        self.accepted(state_of(doc()), command)                    # G5's contesting move
        d = doc()
        d["sides"][0]["posture"] = "WITHDRAWING"
        self.no(state_of(d), command, R.NO_EXIT_PROGRESS, "/members/0")

    def test_selected_vacating_only(self):
        after = self.accepted(state_of(doc()), gm("S0.G1", ("S0.H1", "S0.H2", "S0.H5"), 4))
        self.assertEqual(B.formation(after, fid("S0.H5")).cell, hx(3, 6))


class F03Gates(Case):

    def test_condition_gate(self):
        for c, m, fat in ((2, 0, 0), (0, 2, 0), (0, 0, 2)):
            st = state_of(cond(doc(), "S0.H2", c=c, m=m, fat=fat))
            self.no(st, gm("S0.G1", ("S0.H1", "S0.H2"), 4), R.CONDITION, "/members/1")

    def test_threat_move_versus_pivot(self):
        d = doc()
        place(d, "S1.H4", (3, 5), facing=0)          # threatens (3,6) = S0.H2 only
        st = state_of(d)
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H2"), 4), R.THREATENED_ORIGIN, "/members/1")
        self.accepted(st, gp("S0.G1", ("S0.H1", "S0.H2"), 1))
        place(d, "S1.H3", (4, 5), facing=2)          # second source on (3,6)
        place(d, "S0.L1", (6, 5))
        self.no(state_of(d), gp("S0.G1", ("S0.H1", "S0.H2"), 1), R.PIVOT_RESTRICTED,
                "/members/1")


class F05PerMemberPricing(Case):

    def test_rough_and_open_members(self):
        d = doc_variant("ROUGH")
        place(d, "S0.H1", (2, 5))
        place(d, "S0.H2", (3, 5))
        st = state_of(d)
        r = E.resolve(st, gm("S0.G1", ("S0.H1", "S0.H2"), 4))
        data = [e for e in r.record.events if e.stage is E.Stage.GROUP_STEP][0].data
        self.assertIn(b'"cost":2', data)
        self.assertIn(b'"cost":1', data)
        fields = _fields(r.accepted.state)
        self.assertEqual(effort_remaining(fields, fid("S0.H1")), 1)
        self.assertEqual(effort_remaining(fields, fid("S0.H2")), 2)

    def test_surcharge_seam_over_effort(self):
        d = responded(doc(), "S0.H1", "S1.H1")
        st = state_of(d)
        surcharge = EdgeRule(hx(2, 6), hx(2, 5), True, False, 2)
        out = movement.admit(seam(st, (surcharge,)), gm("S0.G1", ("S0.H1", "S0.H2"), 4))
        self.assertEqual(out, ("reject", R.OVER_EFFORT, "/members/0",
                               rejection_oracles()["OVER_EFFORT"]["detail"]))
        self.assertIsNone(movement.admit(seam(st, ()), gm("S0.G1", ("S0.H1", "S0.H2"), 4)))


# --------------------------------------------------------------------------
# G: withdrawal; H: evacuation


class G01Withdraw(Case):

    def test_costs(self):
        st = state_of(doc())
        after = self.accepted(st, wd("S0.H1", (2, 7)))
        self.assertEqual(effort_remaining(_fields(after), fid("S0.H1")), 1)
        self.assertEqual(B.formation(after, fid("S0.H1")).condition.exertion, 2)
        rough = doc_variant("ROUGH")
        place(rough, "S0.H1", (2, 3))
        place(rough, "S0.L1", (3, 3))
        place(rough, "S0.C1", (1, 3))
        st = state_of(rough)
        after = self.accepted(st, wd("S0.H1", (2, 4)))
        self.assertEqual(effort_remaining(_fields(after), fid("S0.H1")), 0)
        after = self.accepted(st, wd("S0.L1", (2, 4)))
        self.assertEqual(effort_remaining(_fields(after), fid("S0.L1")), 1)
        place(rough, "S0.C1", (2, 3))
        place(rough, "S0.H1", (5, 3))
        self.no(state_of(rough), wd("S0.C1", (2, 4)), R.OVER_EFFORT, "/destination")

    def test_destination_faults(self):
        d = doc()
        place(d, "S0.H1", (2, 8))
        st = state_of(d)
        self.no(st, wd("S0.H1", (2, 9)), R.OFF_BOARD, "/destination")
        self.no(st, wd("S0.H1", (2, 6)), R.NOT_ADJACENT, "/destination")
        self.no(st, wd("S0.H1", (2, 7)), R.NOT_REAR, "/destination")
        self.no(state_of(doc()), wd("S0.H2", (3, 7)), R.OCCUPIED, "/destination")
        barrier = doc_variant("BARRIER")
        place(barrier, "S0.H4", (4, 4), facing=0)
        self.no(state_of(barrier), wd("S0.H4", (3, 4)), R.IMPASSABLE, "/destination")
        d = doc()
        place(d, "S1.H4", (6, 6), facing=2)          # threatens (5,7)
        self.no(state_of(d), wd("S0.H4", (5, 7)), R.THREATENED_DESTINATION, "/destination")

    def test_threatened_origin_allowed(self):
        d = doc()
        place(d, "S1.H4", (5, 5), facing=1)          # threatens (5,6) = S0.H4
        self.accepted(state_of(d), wd("S0.H4", (5, 7)))


class G02EngagedWithdraw(Case):

    def test_contact_defers_after_admission(self):
        d = doc()
        place(d, "S1.H4", (5, 5), facing=1)
        contact(d, "S0.H4", "S1.H4")
        st = state_of(d)
        self.deferred(st, wd("S0.H4", (5, 7)), E.Stage.ROOT, ("DO-P4-01",))
        self.no(st, wd("S0.H4", (5, 8)), R.NOT_ADJACENT, "/destination")


class H01Evacuate(Case):

    def test_order_and_safety(self):
        d = doc()
        place(d, "S0.H5", (3, 8))
        st = state_of(d)
        self.no(st, ev("S0.H4"), R.NOT_ON_EXIT, "/formation")
        after = self.accepted(st, ev("S0.H5"))
        self.assertIs(B.formation(after, fid("S0.H5")).disposition, B.Disposition.WITHDRAWN)
        place(d, "S1.H4", (4, 8), facing=0)          # adjacent, facing away
        self.no(state_of(d), ev("S0.H5"), R.EXIT_UNSAFE, "/formation")

    def test_effort(self):
        d = responded(doc(), "S0.H5", "S1.H1")
        place(d, "S0.H5", (3, 8))
        st = state_of(d)
        after = self.accepted(st, ev("S0.H5"))
        self.assertEqual(effort_remaining(_fields(after), fid("S0.H5")), 0)
        d2 = cond(doc(), "S0.H5", fat=1, e=5)
        place(d2, "S0.H5", (3, 8))
        after = self.accepted(state_of(d2), ev("S0.H5"))
        c = B.formation(after, fid("S0.H5")).condition
        self.assertEqual((c.fatigue, c.exertion), (2, 1))


# --------------------------------------------------------------------------
# The 35 first-fault conflict rows (E06)


class FirstFault(Case):

    def test_01_phase_before_side(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        self.rejected(s.state, mv("S1.H4", (5, 3)), R.PHASE, "",
                      "command is not admissible in this phase")

    def test_02_side_before_formation(self):
        st = state_of(doc())
        self.rejected(st, E.MoveOrder(S1, fid("S1.X9"), (hx(5, 3),)), R.WRONG_SIDE, "/side",
                      "side does not have the current opportunity")

    def test_03_ownership_before_spent(self):
        d = doc()
        d["ledger"]["uses"] = [hold_use("S0", "S0.H1"), hold_use("S1", "S1.H1")]
        self.rejected(state_of(d), mv("S1.H1", (8, 3)).__class__(S0, fid("S1.H1"), (hx(8, 3),)),
                      R.NOT_OWN_FORMATION, "/formation",
                      "formation does not belong to the command side")

    def test_04_not_ready_before_disposition(self):
        d = make_reformer(doc(), "S0.H4")
        d["ledger"]["uses"] = [hold_use("S0", "S0.H4"), hold_use("S1", "S1.H1")]
        self.rejected(state_of(d), mv("S0.H4", (5, 5)), NOT_READY, "/formation", "SPENT")

    def test_05_not_organized_before_engaged(self):
        d = make_reformer(doc(), "S0.H4")
        place(d, "S1.H4", (5, 5), facing=1)
        contact(d, "S0.H4", "S1.H4")
        self.no(state_of(d), mv("S0.H4"), R.NOT_ORGANIZED, "/formation")

    def test_06_engaged_before_path_size(self):
        d = doc()
        place(d, "S1.H4", (5, 5), facing=1)
        contact(d, "S0.H4", "S1.H4")
        self.no(state_of(d), mv("S0.H4"), R.ENGAGED, "/formation")

    def test_07_path_size_before_threatened_origin(self):
        d = doc()
        place(d, "S1.H4", (5, 5), facing=1)
        self.no(state_of(d), mv("S0.H4"), R.BAD_VALUE, "/path")

    def test_08_threatened_origin_before_first_cell(self):
        d = doc()
        place(d, "S1.H4", (5, 5), facing=1)
        self.no(state_of(d), mv("S0.H4", (9, 9)), R.THREATENED_ORIGIN, "/formation")

    def test_09_off_board_before_adjacent(self):
        self.no(state_of(doc()), mv("S0.H1", (20, 20)), R.OFF_BOARD, "/path/0")

    def test_10_repeated_before_rear(self):
        self.no(state_of(doc()), mv("S0.H4", (5, 5), (5, 6)), R.REPEATED_CELL, "/path/1")

    def test_11_adjacent_before_sector(self):
        self.no(state_of(doc()), mv("S0.H4", (5, 5), (3, 5)), R.NOT_ADJACENT, "/path/1")

    def test_12_front_before_occupied(self):
        self.no(state_of(doc()), mv("S0.H4", (4, 6)), R.NOT_FRONT, "/path/0")

    def test_13_impassable_before_occupied(self):
        d = doc_variant("BARRIER")
        place(d, "S0.H4", (3, 4), facing=0)
        place(d, "S0.L1", (4, 4))
        self.no(state_of(d), mv("S0.H4", (4, 4)), R.IMPASSABLE, "/path/0")

    def test_14_occupied_before_later_off_board(self):
        d = doc()
        place(d, "S0.H4", (5, 1))
        place(d, "S0.L1", (5, 0))
        self.no(state_of(d), mv("S0.H4", (5, 0), (5, -1)), R.OCCUPIED, "/path/0")

    def test_15_cap_before_cost(self):
        self.no(state_of(doc_variant("ROUGH")), mv("S0.H1", (2, 5), (2, 4), (2, 3)),
                R.OVER_CAP, "/path")

    def test_16_effort_before_stop(self):
        d = doc_variant("ROUGH")
        place(d, "S1.H1", (3, 4), facing=2)          # threatens (2,5)
        self.no(state_of(d), mv("S0.C1", (2, 5), (2, 4)), R.OVER_EFFORT, "/path")

    def test_17_stop_before_progress(self):
        d = doc()
        d["sides"][0]["posture"] = "WITHDRAWING"
        place(d, "S0.H4", (5, 6), facing=0)
        place(d, "S1.H1", (6, 6), facing=1)          # threatens (5,7) and (6,7)
        self.no(state_of(d), mv("S0.H4", (5, 7), (6, 7)), R.PAST_STOP, "/path/1")

    def test_18_turn_before_steps(self):
        self.no(state_of(doc()), pv("S0.H4", 0, 9), R.BAD_VALUE, "/turn")

    def test_19_engaged_before_restriction(self):
        d = doc()
        place(d, "S0.H4", (5, 4), facing=4)
        place(d, "S1.L1", (9, 3))
        place(d, "S1.H4", (5, 3), facing=1)
        place(d, "S1.H3", (6, 3), facing=2)
        contact(d, "S0.H4", "S1.H4")
        self.no(state_of(d), pv("S0.H4", 1, 1), R.ENGAGED, "/formation")

    def test_20_restriction_before_effort(self):
        d = responded(doc(), "S0.H4", "S1.H1")
        place(d, "S0.H4", (5, 4), facing=4)
        place(d, "S1.L1", (9, 3))
        place(d, "S1.H4", (5, 3), facing=1)
        self.no(state_of(d), pv("S0.H4", 1, 3), R.PIVOT_RESTRICTED, "/steps")

    def test_21_occupied_before_threatened_destination(self):
        d = doc()
        place(d, "S1.H4", (2, 6), facing=1)           # threatens (3,7)
        place(d, "S0.H1", (1, 5))
        self.no(state_of(d), wd("S0.H2", (3, 7)), R.OCCUPIED, "/destination")

    def test_22_threatened_destination_before_effort(self):
        d = responded(doc(), "S0.C1", "S1.H1")
        d = doc_with_rough_threat(d)
        self.no(state_of(d), wd("S0.C1", (2, 4)), R.THREATENED_DESTINATION, "/destination")

    def test_23_contacted_effort_rejects_without_deferral(self):
        d = doc_variant("ROUGH")
        place(d, "S0.C1", (2, 3))
        place(d, "S0.H1", (5, 3))
        place(d, "S1.H4", (2, 2), facing=1)
        place(d, "S1.L1", (9, 3))
        contact(d, "S0.C1", "S1.H4")
        self.no(state_of(d), wd("S0.C1", (2, 4)), R.OVER_EFFORT, "/destination")

    def test_24_not_on_exit_first(self):
        d = responded(doc(), "S0.H4", "S1.H1")
        place(d, "S1.H4", (5, 5), facing=4)
        self.no(state_of(d), ev("S0.H4"), R.NOT_ON_EXIT, "/formation")

    def test_25_unsafe_before_effort(self):
        d = responded(doc(), "S0.H5", "S1.H1")
        fr(d, "S0.H5")["opened_eligible"] = True
        place(d, "S0.H5", (3, 8))
        place(d, "S1.H4", (4, 8), facing=0)
        d["ledger"]["uses"] = []
        d2 = cond(d, "S0.H5", e=0)
        self.no(state_of(d2), ev("S0.H5"), R.EXIT_UNSAFE, "/formation")

    def test_26_direction_before_group(self):
        self.no(state_of(doc()), gm("S0.G9", ("S0.H2", "S0.H1"), 7), R.BAD_VALUE, "/direction")

    def test_27_ownership_before_authority(self):
        d = doc()
        d["authority"][2][1] = "INACTIVE"            # S1.G1
        self.no(state_of(d), E.GroupMoveOrder(S0, gid("S1.G1"), (fid("S1.H1"), fid("S1.H2")),
                                              1), R.NOT_OWN_GROUP, "/group")

    def test_28_member_rows_in_order(self):
        d = doc()
        d["ledger"]["uses"] = [hold_use("S0", "S0.H1"), hold_use("S1", "S1.H1")]
        self.rejected(state_of(d), gm("S0.G1", ("S0.H1", "S0.H3"), 4), NOT_READY,
                      "/members/0", "SPENT")

    def test_29_member_gate_before_connected(self):
        st = state_of(make_reformer(doc(), "S0.H1"))
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H5"), 4), R.NOT_ORGANIZED, "/members/0")
        st = state_of(cond(doc(), "S0.H5", c=2))
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H5"), 4), R.CONDITION, "/members/1")

    def test_30_connected_before_destination(self):
        self.no(state_of(doc()), gm("S0.G1", ("S0.H1", "S0.H5"), 0), R.NOT_CONNECTED,
                "/members")

    def test_31_member0_effort_before_member1_front(self):
        d = responded(doc(), "S0.H1", "S1.H1")
        place(d, "S0.H2", (3, 6), facing=0)
        st = state_of(d)
        surcharge = EdgeRule(hx(2, 6), hx(2, 5), True, False, 2)
        out = movement.admit(seam(st, (surcharge,)), gm("S0.G1", ("S0.H1", "S0.H2"), 4))
        self.assertEqual(out[:3], ("reject", R.OVER_EFFORT, "/members/0"))
        self.no(st, gm("S0.G1", ("S0.H1", "S0.H2"), 4), R.NOT_FRONT, "/members/1")


def doc_with_rough_threat(d):
    from tests.battle.common import a1
    out = a1(variant="ROUGH", label="P4-ROUGH")
    out["ledger"] = d["ledger"]
    place(out, "S0.C1", (2, 3))
    place(out, "S0.H1", (5, 3))
    place(out, "S1.H4", (1, 4), facing=0)            # threatens (2,4)
    return out


if __name__ == "__main__":
    unittest.main()
