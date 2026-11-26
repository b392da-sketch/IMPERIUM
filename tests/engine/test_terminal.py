"""TA-D01–D11: terminal accounting, precedence and capitulation custody (P2-D)."""

import copy

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.engine import terminal as T
from imperium.battle.queries import Fields
from imperium.battle.state import state_values
from tests.battle.common import (
    at_exit, f, fr, fround, on_cell, place, plot, set_asset_place, set_lots,
)
from tests.battle.scenarios import S1_CELLS, capitulation, collapse, count_of
from tests.engine.helpers import (
    CLOSE_TERMINAL, DEFENSIVE, PHASE_DETAIL, ROOT_TERMINAL, S0, S1, EngineCase, awaiting, build,
    hold, hold_use, opened, make_router,
)

ROSTER = sorted(f"{s}.{p}" for s in ("S0", "S1") for p in ("H1", "H2", "H3", "H4", "H5", "H6", "L1", "C1"))


def lineage_totals(state):
    out = {}
    for l in state.personnel:
        out[l.lineage] = out.get(l.lineage, 0) + l.count
    mounts = {}
    for m in state.mounts:
        mounts[m.formation] = mounts.get(m.formation, 0) + m.count
    ammo = {a.formation: a.carried + a.expended for a in state.ammunition}
    return out, mounts, ammo


def capitulation_carrier():
    """Catalogue capitulation configuration, one root before S1 capitulates (round 4)."""
    d = awaiting(side="S1", completed=3, cursor=29, label="CAPITULATION")
    place(d, "S1.H1", (8, 0), disposition="WITHDRAWN")
    set_lots(d, "S1.H1", [
        plot("S1.H1:P0", "S1.H1", 210, "AVAILABLE", at_exit("S1"), "S1"),
        plot("S1.H1:W1", "S1.H1", 30, "WOUNDED", on_cell(8, 2), "S1", origin="EV-1"),
    ])
    set_asset_place(d, "S1.H1", "ASSIGNED", at_exit("S1"), "S1", "OWN", "NOT_APPLICABLE")
    fr(d, "S1.H1")["opened_eligible"] = False
    f(d, "S1.H2")["disposition"] = "DEPLETED"
    set_lots(d, "S1.H2", [plot("S1.H2:D1", "S1.H2", 240, "DEAD", on_cell(7, 2), None, origin="EV-2")])
    set_asset_place(d, "S1.H2", "UNASSIGNED_RECORDED", on_cell(7, 2), "S1", "OWN", "UNRESOLVED")
    fr(d, "S1.H2")["opened_eligible"] = False
    make_router(d, "S1.H3")
    f(d, "S1.H4")["disposition"] = "REFORMING"
    return d


class Capitulation(EngineCase):

    def test_d01_round_three(self):
        s = build(awaiting(side="S1", completed=2, cursor=7, uses=[hold_use("S0", "S0.H1")], label="D01"))
        t = self.accepted(s, E.Capitulate(S1), ROOT_TERMINAL)
        rec = t.phase.record
        self.assertEqual((rec.reason, rec.result, rec.winner, rec.defeat, rec.point, rec.charged_rounds),
                         (B.TerminalReason.CAPITULATION, B.ResultKind.VICTORY, S0,
                          (None, B.DefeatClass.CAPITULATED), B.TerminationPoint.AFTER_ROOT, 3))
        self.assertEqual(t.clock, B.Clock(2, 8))
        self.assertEqual(B.elapsed_minutes(t), 30)
        self.assertIsNone(t.ledger)

    def test_d02_overrides_withdrawal(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        for c in (E.OpenBattle(), E.DeclareWithdrawal(S0), hold(S1, "S1.H1")):
            self.assertIs(type(s.submit(c)), E.Accepted)
        r = s.submit(E.Capitulate(S0))
        self.assertEqual(r.stages, ROOT_TERMINAL)
        rec = s.state.phase.record
        self.assertEqual((rec.reason, rec.winner, rec.defeat, rec.postures),
                         (B.TerminalReason.CAPITULATION, S1, (B.DefeatClass.CAPITULATED, None),
                          (B.Posture.WITHDRAWING, B.Posture.CONTESTING)))

    def test_d03_catalogue_custody(self):
        pre = build(capitulation_carrier())
        t = self.accepted(pre, E.Capitulate(S1), ROOT_TERMINAL)
        expected = capitulation("CAPITULATION")
        expected["clock"] = {"completed_rounds": 3, "event_cursor": 30}
        self.assertEqual(B.canonical_bytes(t), B.canonical_bytes(build(expected)))
        # DO-02 witnesses: identity, lineage, count, cell and origin of the wounded lot.
        before = {l.lot.token: l for l in pre.personnel}
        after = {l.lot.token: l for l in t.personnel}
        self.assertEqual(set(before), set(after))
        w0, w1 = before["S1.H1:W1"], after["S1.H1:W1"]
        self.assertEqual((w1.lineage, w1.count, w1.place, w1.origin), (w0.lineage, w0.count, w0.place, w0.origin))
        self.assertEqual((w1.status, w1.captured, w1.custodian),
                         (B.PersonnelStatus.CAPTURED, B.CapturedCondition.WOUNDED, S0))
        for token in before:
            self.assertEqual((after[token].lineage, after[token].count, after[token].origin),
                             (before[token].lineage, before[token].count, before[token].origin))
        self.assertEqual(after["S1.H1:P0"], before["S1.H1:P0"])
        self.assertEqual(after["S1.H2:D1"], before["S1.H2:D1"])
        self.assertEqual(t.contacts, ())

    def test_d04_unreachable_no_onmap(self):
        """H02 makes NO_ONMAP_AVAILABLE unreachable on a validated A state: each side has a
        viable formation, which is on the battlefield with available > 0."""
        for side in (S0, S1):
            a = opened()
            self.assertGreaterEqual(B.viable_count(a, side), 1)
            self.assertGreater(B.onmap_available(a, side), 0)

    def test_d05_assets_and_totals(self):
        pre = build(capitulation_carrier())
        t = self.accepted(pre, E.Capitulate(S1), ROOT_TERMINAL)
        surrendered = {"S1.H3", "S1.H4", "S1.H5", "S1.H6", "S1.L1", "S1.C1"}
        for rec in t.mounts + t.ammunition:
            token = rec.formation.token
            if token in surrendered:
                self.assertEqual((rec.assignment, rec.custodian, rec.custody, rec.recovery, rec.place),
                                 (B.Assignment.UNASSIGNED_RECORDED, S0, B.Custody.SURRENDERED_INVENTORY,
                                  B.Recovery.NOT_APPLICABLE, B.OnCell(B.Hex(*S1_CELLS[token]))))
        by_formation = {r.formation.token: r for r in pre.mounts + pre.ammunition}
        for rec in t.mounts + t.ammunition:
            if rec.formation.token in ("S1.H1", "S1.H2") or rec.formation.token.startswith("S0"):
                self.assertIn(rec, pre.mounts + pre.ammunition)
        self.assertEqual(B.side_totals(t, S0), B.side_totals(pre, S0))
        self.assertEqual((B.onmap_available(t, S0), B.exit_available(t, S0)),
                         (B.onmap_available(pre, S0), B.exit_available(pre, S0)))
        st = B.side_totals(t, S1)
        self.assertEqual((st.available, st.wounded, st.captured), (210, 0, 240 * 4 + 120 + 80 + 30))

    def test_d06_conservation(self):
        pre = build(capitulation_carrier())
        t = self.accepted(pre, E.Capitulate(S1))
        self.assertEqual(lineage_totals(t), lineage_totals(pre))
        roster_side = {e.formation: e.side for e in pre.scenario.roster}
        self.assertEqual(roster_side, {e.formation: e.side for e in t.scenario.roster})


class Deadline(EngineCase):

    def test_d07_twelve_pass_rounds(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        s.submit(E.OpenBattle())
        s.submit(E.PassOrder(S0))
        r = s.submit(E.PassOrder(S1))
        self.assertEqual((s.state.clock.completed_rounds, s.state.phase), (1, B.AwaitingPrincipal(S1)))
        last = r
        while type(s.state.phase) is B.AwaitingPrincipal:
            last = s.submit(E.PassOrder(s.state.phase.side))
        self.assertEqual(len(s.journal), 25)
        self.assertEqual(last.stages, CLOSE_TERMINAL)
        rec = s.state.phase.record
        self.assertEqual((rec.reason, rec.result, rec.point, rec.charged_rounds),
                         (B.TerminalReason.DEADLINE_OBJECTIVE_UNRESOLVED, B.ResultKind.DRAW,
                          B.TerminationPoint.ROUND_END, 12))
        self.assertEqual((s.state.clock.completed_rounds, B.elapsed_minutes(s.state)), (12, 120))

    def _final_round(self, label, postures=("CONTESTING", "CONTESTING"), secure=False):
        d = awaiting(side="S1", completed=11, cursor=40, label=label)
        if secure:
            place(d, "S0.H1", (5, 4), 4)
            place(d, "S1.L1", (8, 3), 1)
        d["sides"] = [{"side": "S0", "posture": postures[0]}, {"side": "S1", "posture": postures[1]}]
        s = build(d)
        s = self.accepted(s, E.PassOrder(S1))
        return self.accepted(s, E.PassOrder(S0), CLOSE_TERMINAL).phase.record

    def test_d08_variants(self):
        rec = self._final_round("D08a", secure=True)
        self.assertEqual((rec.reason, rec.result, rec.winner, rec.defeat),
                         (B.TerminalReason.DEADLINE_OBJECTIVE_VICTORY, B.ResultKind.VICTORY, S0, (None, None)))
        rec = self._final_round("D08b", postures=("CONTESTING", "WITHDRAWING"), secure=True)
        self.assertEqual((rec.reason, rec.result, rec.winner, rec.defeat),
                         (B.TerminalReason.DEADLINE_ABANDONMENT, B.ResultKind.VICTORY, S0,
                          (None, B.DefeatClass.ABANDONMENT)))
        rec = self._final_round("D08c", postures=("WITHDRAWING", "WITHDRAWING"))
        self.assertEqual((rec.reason, rec.result, rec.winner, rec.defeat),
                         (B.TerminalReason.DEADLINE_MUTUAL_WITHDRAWAL, B.ResultKind.DRAW, None, (None, None)))

    def test_d08_immediate_beats_deadline(self):
        """Test-local predicate input: a zero-viability side at charged 12 is classified by
        the immediate rows, never the deadline (no claim the P2 path reaches it)."""
        t = build(collapse("D08d", completed=12, charged=12))
        fields = Fields(*state_values(t))
        rec = T.round_end_outcome(fields, 12, 12)
        self.assertEqual((rec.reason, rec.defeat), (B.TerminalReason.ZERO_VIABILITY_UNILATERAL,
                                                    (None, B.DefeatClass.COLLAPSE)))
        values = list(state_values(t))
        values[3] = (B.SideState(S0, B.Posture.WITHDRAWING), B.SideState(S1, B.Posture.CONTESTING))
        rec = T.round_end_outcome(Fields(*values), 12, 12)
        self.assertEqual((rec.reason, rec.result), (B.TerminalReason.ZERO_VIABILITY_MUTUAL_ABANDONMENT,
                                                    B.ResultKind.DRAW))


class Freeze(EngineCase):

    def test_d09_after_terminal(self):
        cases = []
        cases.append(self.accepted(opened(), E.Capitulate(S0)))
        cases.append(self.accepted(build(capitulation_carrier()), E.Capitulate(S1)))
        s = opened()
        while type(s.phase) is B.AwaitingPrincipal:
            s = self.accepted(s, E.PassOrder(s.phase.side))
        cases.append(s)
        for t in cases:
            for side in (S0, S1):
                for c in (E.OpenBattle(), hold(side, f"{side.name}.H1"), E.PassOrder(side),
                          E.DeclareWithdrawal(side), E.Capitulate(side)):
                    self.rejected(t, c, E.RejectCode.PHASE, "", PHASE_DETAIL)
                self.assertEqual(B.usable_opportunities(t, side), 0)
                self.assertIsNone(B.projected_capacity(t, side))
                self.assertIsNone(B.capacity_remaining(t, side))
            for e in t.scenario.roster:
                self.assertIs(B.activation(t, e.formation), B.Activation.CLOSED)
                self.assertFalse(B.response_allowance_unused(t, e.formation))
                self.assertIsNone(B.effort_charged(t, e.formation))
            self.assertIsNone(t.ledger)

    def test_d10_charged_once(self):
        t = self.accepted(build(awaiting(side="S0", completed=4, cursor=9, label="D10")), E.Capitulate(S0))
        self.assertEqual((t.clock.completed_rounds, t.phase.record.charged_rounds), (4, 5))

    def test_d11_defensive_fixture(self):
        s = E.BattleSession.open(DEFENSIVE)
        F = B.descriptor(DEFENSIVE).full_genesis_digest
        self.assertEqual(B.digest(s.state), F)
        for side in (S0, S1):
            for c in (E.OpenBattle(), hold(side, f"{side.name}.H1"), E.PassOrder(side),
                      E.DeclareWithdrawal(side), E.Capitulate(side)):
                r = s.submit(c)
                self.assertIs(r.code, E.RejectCode.PHASE)
        self.assertEqual(s.journal, ())
        self.assertEqual(B.digest(s.state), F)
        self.assertEqual(B.canonical_bytes(s.state), B.canonical_bytes(B.f01_supplied(DEFENSIVE)))

    def test_initial_collapse(self):
        d = collapse("D-IC")
        d["clock"] = {"completed_rounds": 0, "event_cursor": 0}
        d["phase"] = {"kind": "Opening"}
        o = build(d)
        t = self.accepted(o, E.OpenBattle())
        self.assertEqual(t.phase.record.defeat, (None, B.DefeatClass.COLLAPSE))
