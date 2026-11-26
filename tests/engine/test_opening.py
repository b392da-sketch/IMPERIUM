"""TA-B01–B05: the initial assessment and round opening (P2-B)."""

import imperium.battle as B
from imperium.battle import engine as E
from tests.battle.common import at_exit, cond, f, on_cell, place, plot, set_asset_place, set_lots
from tests.battle.scenarios import S0_CELLS, S1_CELLS, count_of
from tests.engine.helpers import (
    OPEN_CONTINUE, OPEN_TERMINAL, OPENINGS, S0, S1, EngineCase, as_adversarial, build, hold,
    opening_document, opened,
)

ALL = sorted(list(S0_CELLS) + list(S1_CELLS))


def deplete(d, cells):
    for fid, cell in cells.items():
        f(d, fid)["disposition"] = "DEPLETED"
        set_lots(d, fid, [plot(f"{fid}:D1", fid, count_of(fid), "DEAD", on_cell(*cell), None,
                               origin="EV-1")])
        side = fid[:2]
        set_asset_place(d, fid, "UNASSIGNED_RECORDED", on_cell(*cell), side, "OWN", "UNRESOLVED")
    return d


def withdraw_s1(d):
    for i, fid in enumerate(sorted(S1_CELLS)):
        place(d, fid, (1 + i, 0), disposition="WITHDRAWN")
        set_lots(d, fid, [plot(f"{fid}:P0", fid, count_of(fid), "AVAILABLE", at_exit("S1"), "S1")])
        set_asset_place(d, fid, "ASSIGNED", at_exit("S1"), "S1", "OWN", "NOT_APPLICABLE")
    return d


class InitialAssessment(EngineCase):

    def test_b01_each_opening(self):
        for fixture_id in OPENINGS:
            d = B.descriptor(fixture_id)
            o = (B.f01_opening(d.variant, d.orientation)
                 if d.fixture_class is B.FixtureClass.CANONICAL_OPENING else B.f01_supplied(fixture_id))
            with self.subTest(fixture=fixture_id.token):
                a = self.accepted(o, E.OpenBattle(), OPEN_CONTINUE)
                self.assertEqual(a.phase, B.AwaitingPrincipal(S0))
                self.assertEqual(a.clock, B.Clock(0, 1))
                self.assertEqual(a.ledger.uses, ())
                self.assertEqual(len(a.ledger.formations), 16)
                for fr in a.ledger.formations:
                    self.assertEqual(
                        (fr.opened_eligible, fr.response, fr.displacement_attempted, fr.safe_latch,
                         fr.incoming, fr.incoming_since_rally, fr.exerted, fr.displaced),
                        (True, None, False, True, False, False, False, False))
                    self.assertIs(B.activation(a, fr.formation), B.Activation.READY)
                    self.assertEqual(B.effort_usable(a, fr.formation), 3)
                self.assertEqual((B.usable_opportunities(a, S0), B.usable_opportunities(a, S1)), (4, 4))
                for name in ("scenario", "sides", "formations", "authority", "personnel",
                             "mounts", "ammunition", "contacts"):
                    self.assertEqual(getattr(a, name), getattr(o, name), name)

    def test_b02_parity_both_orientations(self):
        for orientation in (B.Orientation.STANDARD, B.Orientation.MIRRORED):
            o = B.f01_opening(B.Variant.OPEN, orientation)
            a = self.accepted(o, E.OpenBattle())
            self.assertIs(a.phase.side, S0)
            a = self.accepted(a, E.PassOrder(S0))
            self.assertIs(a.phase.side, S1)
            a = self.accepted(a, E.PassOrder(S1))
            self.assertEqual(a.clock.completed_rounds, 1)
            self.assertIs(a.phase.side, S1)
            a = self.accepted(a, E.PassOrder(S1))
            self.assertIs(a.phase.side, S0)
        std = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        mir = B.f01_opening(B.Variant.OPEN, B.Orientation.MIRRORED)
        self.assertIs(B.end_of(std.scenario, S0), B.End.RED)
        self.assertIs(B.end_of(mir.scenario, S0), B.End.BLUE)

    def _initial_terminal(self, d, reason, result, winner, defeat, viable, onmap, exit_):
        o = build(d)
        t = self.accepted(o, E.OpenBattle(), OPEN_TERMINAL)
        rec = t.phase.record
        self.assertEqual(
            (rec.reason, rec.result, rec.winner, rec.defeat, rec.point, rec.charged_rounds,
             rec.viable, rec.onmap_available, rec.exit_available, rec.postures, rec.objective),
            (reason, result, winner, defeat, B.TerminationPoint.INITIAL_CHECK, 0, viable, onmap,
             exit_, (B.Posture.CONTESTING, B.Posture.CONTESTING),
             B.ObjectiveStatus(B.ObjectiveKind.UNHELD, None)))
        self.assertEqual(t.clock, B.Clock(0, 1))
        self.assertIsNone(t.ledger)
        self.assertEqual(B.elapsed_minutes(t), 0)
        for name in ("formations", "personnel", "mounts", "ammunition", "contacts", "sides"):
            self.assertEqual(getattr(t, name), getattr(o, name), name)
        return t

    def test_b03_all_depleted(self):
        d = deplete(as_adversarial(opening_document(), "B03a"), S1_CELLS)
        self._initial_terminal(d, B.TerminalReason.ZERO_VIABILITY_UNILATERAL, B.ResultKind.VICTORY, S0,
                               (None, B.DefeatClass.DEPLETION_MIXED), (8, 0), (1640, 0), (0, 0))

    def test_b03_all_withdrawn(self):
        d = withdraw_s1(as_adversarial(opening_document(), "B03b"))
        self._initial_terminal(d, B.TerminalReason.ZERO_VIABILITY_UNILATERAL, B.ResultKind.VICTORY, S0,
                               (None, B.DefeatClass.DEPARTURE), (8, 0), (1640, 0), (0, 1640))

    def test_b03_mutual_loss(self):
        d = deplete(deplete(as_adversarial(opening_document(), "B03c"), S1_CELLS), S0_CELLS)
        self._initial_terminal(d, B.TerminalReason.ZERO_VIABILITY_MUTUAL_LOSS, B.ResultKind.DRAW, None,
                               (B.DefeatClass.DEPLETION_MIXED, B.DefeatClass.DEPLETION_MIXED),
                               (0, 0), (0, 0), (0, 0))

    def test_b04_opening_once(self):
        a = opened()
        self.rejected(a, E.OpenBattle(), E.RejectCode.PHASE)
        s = E.BattleSession.open(B.FixtureId("F01-v1-rough-mirrored"))
        opens = list(s.submit(E.OpenBattle()).stages)
        while type(s.state.phase) is B.AwaitingPrincipal:
            opens += s.submit(E.PassOrder(s.state.phase.side)).stages
        self.assertEqual(opens.count(E.Stage.OPEN_ROUND), 12)

    def test_b05_flags(self):
        d = as_adversarial(opening_document(), "B05")
        place(d, "S0.C1", (0, 7))
        place(d, "S1.L1", (2, 5), 2)        # adjacent to S0.H1 at (2,6) only
        f(d, "S0.H6")["disposition"] = "REFORMING"
        f(d, "S0.H5")["disposition"] = "ROUTING"
        cond(d, "S0.H2", e=3)
        o = build(d)
        a = self.accepted(o, E.OpenBattle(), OPEN_CONTINUE)
        rounds = {fr.formation.token: fr for fr in a.ledger.formations}
        self.assertFalse(rounds["S0.H1"].safe_latch)
        self.assertFalse(rounds["S1.L1"].safe_latch)
        self.assertTrue(rounds["S0.H6"].opened_eligible)
        self.assertTrue(rounds["S0.H6"].safe_latch)
        self.assertFalse(rounds["S0.H5"].opened_eligible)
        self.assertTrue(rounds["S0.H5"].safe_latch)
        for token, fr in rounds.items():
            if token not in ("S0.H1", "S1.L1"):
                self.assertTrue(fr.safe_latch, token)
            if token != "S0.H5":
                self.assertTrue(fr.opened_eligible, token)
            self.assertEqual((fr.response, fr.displacement_attempted, fr.incoming,
                              fr.incoming_since_rally, fr.exerted, fr.displaced),
                             (None, False, False, False, False, False), token)
        self.assertEqual(B.formation(a, B.FormationId("S0.H2")).condition.exertion, 3)
        self.assertEqual(a.formations, o.formations)
