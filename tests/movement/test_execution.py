"""TA-P4-D01 to D05, E02, H02 and H03: physical stages, exertion, safety
latch, the shortfall fixture, pivot traces and evacuation terminals."""

import json
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.queries import Fields, recovery_safe_now
from imperium.battle.records import STATE_FIELDS
from tests.engine.helpers import hold_use, pass_use
from tests.movement.support import (
    S0, S1, MovementCase, carriers, cjson, complete, cond, doc, ev, f, fid, fr, hx, mv, place,
    pv, run_carrier, state_of,
)

P4_PHYSICAL = {E.Stage.STEP1, E.Stage.STEP2, E.Stage.STEP3, E.Stage.WITHDRAW,
               E.Stage.GROUP_STEP, E.Stage.PIVOT, E.Stage.GROUP_PIVOT, E.Stage.EVACUATE,
               E.Stage.RESPONSE}


def fields_of(values):
    return Fields(**dict(zip(STATE_FIELDS, values)))


def data_of(res, stage):
    return [json.loads(e.data) for e in res.record.events if e.stage is stage]


class D01Steps(MovementCase):

    def test_two_step_completed(self):
        st = state_of(doc())
        res = complete(st, mv("S0.H4", (5, 5), (5, 4)))
        after = res.accepted.state
        self.assertEqual(after.clock.event_cursor, st.clock.event_cursor + 1)
        self.assertEqual(after.clock.completed_rounds, st.clock.completed_rounds)
        work = after.ledger.uses[-1].work
        self.assertEqual(len(work), 1)
        move = work[0]
        self.assertEqual(move.declared, (hx(5, 5), hx(5, 4)))
        self.assertEqual(move.end.name, "COMPLETED")
        self.assertEqual([(l.origin, l.destination, l.facing, l.mode.name) for l in move.legs],
                         [(hx(5, 6), hx(5, 5), 4, "FOOT"), (hx(5, 5), hx(5, 4), 4, "FOOT")])
        steps = data_of(res, E.Stage.STEP1) + data_of(res, E.Stage.STEP2)
        self.assertEqual([s["cost"] for s in steps], [1, 1])
        self.assertEqual([s["to"] for s in steps], [[5, 5], [5, 4]])
        self.assertNotIn(E.Stage.STEP3, res.accepted.stages)

    def test_completed_even_if_last_cell_threatened(self):
        d = doc()
        place(d, "S1.H4", (5, 3), facing=1)            # threatens (5,4)
        res = complete(state_of(d), mv("S0.H4", (5, 5), (5, 4)))
        self.assertEqual(res.accepted.state.ledger.uses[-1].work[0].end.name, "COMPLETED")
        self.assertTrue(data_of(res, E.Stage.STEP2)[0]["threatened"])

    def test_stopped_suffix_unentered(self):
        row = carriers()["G7"]["roots"][6]
        s = run_carrier("G7", upto=6)
        r = s.submit(E.decode_command(cjson(row["command"])))
        res = E.resolve(r.root, E.decode_command(cjson(row["decision"])))
        move = res.accepted.state.ledger.uses[-1].work[0]
        before = B.formation(s.state, fid("S0.L1")).condition.exertion
        self.assertEqual(move.declared, (hx(4, 3), hx(4, 2)))
        self.assertEqual([l.destination for l in move.legs], [hx(4, 3)])
        self.assertEqual(move.end.name, "STOPPED")
        self.assertNotIn(E.Stage.STEP2, res.accepted.stages)
        self.assertEqual(B.formation(res.accepted.state, fid("S0.L1")).condition.exertion,
                         before + 1)


class D02Threat(MovementCase):

    def test_into_threat_no_contact(self):
        d = doc()
        place(d, "S1.H4", (5, 3), facing=1)            # threatens (5,4) and (4,4)
        res = complete(state_of(d), mv("S0.L1", (4, 4)))
        step = data_of(res, E.Stage.STEP1)[0]
        self.assertTrue(step["threatened"])
        self.assertEqual(res.accepted.state.contacts, ())


class D02EntryStopSeam(MovementCase):

    def test_latched_entry_stops_with_clear_current_threat(self):
        """Labelled planner seam (D02): only the stored entry stop is injected;
        the board and the live threat query match the positive control."""
        import sys
        from unittest import mock
        step_module = sys.modules["imperium.battle.engine.step"]
        st = state_of(doc())
        order = mv("S0.H1", (2, 5), (2, 4))
        real = step_module.move_step

        def latched(values, command, k):
            stage, after, data, threatened = real(values, command, k)
            self.assertEqual((k, threatened), (1, False))
            return stage, after, dict(data, threatened=True), True

        control = complete(st, order)
        self.assertIn(E.Stage.STEP2, control.accepted.stages)
        with mock.patch.object(step_module, "move_step", latched):
            stopped = complete(st, order)
        self.assertNotIn(E.Stage.STEP2, stopped.accepted.stages)
        work = stopped.accepted.state.ledger.uses[-1].work[0]
        self.assertEqual((work.end.name, len(work.legs)), ("STOPPED", 1))
        self.assertEqual(B.formation(stopped.accepted.state, fid("S0.H1")).condition.exertion, 1)


class D03Exertion(MovementCase):

    def condition_after(self, d, command):
        g = B.formation(complete(state_of(d), command).accepted.state, command.formation)
        return (g.condition.fatigue, g.condition.exertion)

    def test_mp21(self):
        self.assertEqual(self.condition_after(cond(doc(), "S0.H4", fat=0, e=5),
                                              mv("S0.H4", (5, 5))), (1, 0))
        self.assertEqual(self.condition_after(cond(doc(), "S0.H4", fat=1, e=5),
                                              pv("S0.H4", 1, 2)), (2, 1))
        self.assertEqual(self.condition_after(cond(doc(), "S0.H4", fat=2, e=5),
                                              pv("S0.H4", 1, 3)), (2, 2))

    def test_hold_and_pass_preserve(self):
        d = cond(doc(), "S0.H4", fat=1, e=3)
        st = state_of(d)
        after = self.accepted(st, E.HoldOrder(S0, fid("S0.H4")))
        c = B.formation(after, fid("S0.H4")).condition
        self.assertEqual((c.fatigue, c.exertion), (1, 3))
        after = self.accepted(st, E.PassOrder(S0))
        c = B.formation(after, fid("S0.H4")).condition
        self.assertEqual((c.fatigue, c.exertion), (1, 3))

    def test_exerted_flag(self):
        st = state_of(doc())
        after = complete(st, pv("S0.H4", 1, 1)).accepted.state
        flags = {r.formation.token: r.exerted for r in after.ledger.formations}
        self.assertTrue(flags["S0.H4"])
        self.assertFalse(flags["S0.H3"])
        after = self.accepted(after, E.HoldOrder(S1, fid("S1.H1")))
        self.assertTrue({r.formation.token: r.exerted
                         for r in after.ledger.formations}["S0.H4"])


class D04Latch(MovementCase):

    def check_root(self, before_values, res):
        prev = {r.formation: r.safe_latch for r in fields_of(before_values).ledger.formations}
        for snap in res.snapshots:
            fields = fields_of(snap.values)
            if fields.ledger is None:
                continue
            now = {r.formation: r.safe_latch for r in fields.ledger.formations}
            if snap.stage in P4_PHYSICAL:
                for g in fields.formations:
                    if g.disposition is B.Disposition.WITHDRAWN:
                        continue
                    want = prev[g.formation] and recovery_safe_now(fields, g.formation)
                    self.assertEqual(now[g.formation], want, (snap.stage_id, g.formation))
            if snap.stage is not E.Stage.OPEN_ROUND:
                for k, v in now.items():
                    self.assertFalse(v and not prev[k], (snap.stage_id, k))
            prev = now

    def test_every_carrier_stage(self):
        from imperium.battle.state import state_values
        for name, case in carriers().items():
            s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
            for row in case["roots"]:
                base = s.state
                command = E.decode_command(cjson(row["command"]))
                r = E.resolve(base, command)
                if type(r) is E.Suspended:
                    r = E.resolve(r.root, E.decode_command(cjson(row["decision"])))
                if base.ledger is not None:
                    self.check_root(state_values(base), r)
                s.submit(command)
                if s.pending is not None:
                    s.submit(E.decode_command(cjson(row["decision"])))

    def test_adjacency_breaks_both_sides_and_stays_false(self):
        d = doc()
        for r in d["ledger"]["formations"]:
            r["safe_latch"] = True
        res = complete(state_of(d), mv("S0.L1", (5, 4)))
        after = res.accepted.state
        latch = {r.formation.token: r.safe_latch for r in after.ledger.formations}
        self.assertFalse(latch["S0.L1"])
        self.assertFalse(latch["S1.L1"])
        # Back away in a later root: the vanished adjacency never restores it.
        after = self.accepted(after, E.HoldOrder(S1, fid("S1.H1")))
        after = complete(after, mv("S0.H4", (5, 5))).accepted.state
        after = self.accepted(after, E.HoldOrder(S1, fid("S1.H2")))
        moved = B.encode_state(after)
        self.assertFalse({r.formation.token: r.safe_latch
                          for r in after.ledger.formations}["S0.L1"])
        self.assertTrue(moved)

    def test_real_adjacency_loss_keeps_both_latches_false(self):
        from tests.movement.support import wd
        d = doc()
        place(d, "S1.H3", (8, 1))                         # frees S1.L1's rear cell (6,2)
        for r in d["ledger"]["formations"]:
            r["safe_latch"] = True
        adjacent = complete(state_of(d), mv("S0.L1", (5, 4))).accepted.state
        apart = complete(adjacent, wd("S1.L1", (6, 2))).accepted.state
        for st, safe in ((adjacent, False), (apart, True)):
            fields = fields_of(_values(st))
            for token in ("S0.L1", "S1.L1"):
                self.assertEqual(recovery_safe_now(fields, fid(token)), safe, token)
        latch = {r.formation.token: r.safe_latch for r in apart.ledger.formations}
        self.assertEqual((latch["S0.L1"], latch["S1.L1"]), (False, False))

    def test_latch_true_survives_safe_move(self):
        d = doc()
        for r in d["ledger"]["formations"]:
            r["safe_latch"] = True
        after = complete(state_of(d), mv("S0.H1", (2, 5))).accepted.state
        latch = {r.formation.token: r.safe_latch for r in after.ledger.formations}
        self.assertTrue(latch["S0.H1"])
        self.assertTrue(latch["S1.H1"])
        after = complete(state_of(d), mv("S0.L1", (5, 4))).accepted.state
        latch = {r.formation.token: r.safe_latch for r in after.ledger.formations}
        self.assertFalse(latch["S0.L1"])
        self.assertFalse(latch["S1.L1"])                  # both sides lose it
        self.assertTrue(latch["S0.H1"])
        self.assertTrue(latch["S1.H4"])


class D05Shortfall(MovementCase):

    def test_mixed_foot(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard-mount-shortfall"))
        s.submit(E.OpenBattle())
        st = s.state
        self.reject_at(st, mv("S0.C1", (1, 5), (1, 4), (1, 3)), E.RejectCode.OVER_CAP, "/path")
        res = complete(st, mv("S0.C1", (1, 5), (1, 4)))
        legs = res.accepted.state.ledger.uses[-1].work[0].legs
        self.assertEqual([l.mode.name for l in legs], ["MIXED_FOOT", "MIXED_FOOT"])
        self.assertEqual(res.accepted.state.mounts, st.mounts)
        self.assertEqual(res.accepted.state.scenario, st.scenario)
        from imperium.battle.queries import template_for
        self.assertIsNone(template_for(fields_of(_values(st)), fid("S0.C1")).missile_range)


class E02PivotTrace(MovementCase):

    def test_no_window_cell_or_intermediate(self):
        res = complete(state_of(doc()), pv("S0.H4", -1, 3))
        self.assertEqual(res.accepted.stages, (E.Stage.ROOT, E.Stage.PIVOT,
                                               E.Stage.IMMEDIATE_CHECK))
        data = data_of(res, E.Stage.PIVOT)[0]
        self.assertEqual(data, {"formation": "S0.H4", "from": 4, "to": 1, "steps": 3})
        pivot = [e for e in res.record.events if e.stage is E.Stage.PIVOT][0]
        paths = [x.path for x in pivot.effects]
        self.assertFalse(any(p.endswith("/cell") for p in paths))
        facing = [x for x in pivot.effects if x.path.endswith("/facing")]
        self.assertEqual(len(facing), 1)


class H02Evacuation(MovementCase):

    def test_assets_preserved(self):
        d = doc()
        place(d, "S0.H5", (3, 8))
        st = state_of(d)
        after = complete(st, ev("S0.H5")).accepted.state
        before, now = B.encode_state(st), B.encode_state(after)
        for key in ("personnel", "mounts", "ammunition"):
            self.assertEqual(len(now[key]), len(before[key]))
            self.assertEqual(sorted(l["lot"] if "lot" in l else l["formation"] for l in now[key]),
                             sorted(l["lot"] if "lot" in l else l["formation"]
                                    for l in before[key]))
        old = {json.dumps(l, sort_keys=True) for l in before["personnel"]}
        changed = [l for l in now["personnel"] if json.dumps(l, sort_keys=True) not in old]
        self.assertTrue(changed)
        self.assertTrue(all(l["custodian"] == "S0" for l in changed))
        total = lambda doc_: sum(l["count"] for l in doc_["personnel"])
        self.assertEqual(total(now), total(before))

    def test_offboard_ready_ineligible(self):
        d = doc()
        place(d, "S0.H5", (3, 8))
        after = complete(state_of(d), ev("S0.H5")).accepted.state
        self.assertIs(B.formation(after, fid("S0.H5")).disposition, B.Disposition.WITHDRAWN)
        from imperium.battle.queries import activation
        self.assertNotEqual(activation(fields_of(_values(after)), fid("S0.H5")).name, "READY")


def _values(state):
    from imperium.battle.state import state_values
    return state_values(state)


class H03MutualAbandonment(MovementCase):

    def test_g9_final_root_with_opponent_withdrawing(self):
        from tests.support.battle_builder import as_adversarial
        d = as_adversarial(B.encode_state(run_carrier("G9", upto=34).state), "H03")
        d["sides"][1]["posture"] = "WITHDRAWING"
        res = complete(state_of(d), ev("S0.L1"))
        record = res.accepted.state.phase.record
        self.assertEqual((record.reason.name, record.result.name, record.winner),
                         ("ZERO_VIABILITY_MUTUAL_ABANDONMENT", "DRAW", None))
        self.assertNotIn(E.Stage.WINDOW, res.accepted.stages)
        self.assertIsNone(res.accepted.state.ledger)


if __name__ == "__main__":
    unittest.main()
