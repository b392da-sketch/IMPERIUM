"""14.6 phase queries and derived values (AT-Q01–Q07, D01–D06, X-OBJ)."""

import imperium.battle as B
from tests.battle.common import BattleCase, a1, cond, place
from tests.battle.scenarios import deadline_objective_victory, secure_o0
from tests.support.battle_builder import as_adversarial, opening_document

F = B.FormationId
ROSTER = [F(f"{s}.{p}") for s in ("S0", "S1") for p in ("C1", "H1", "H2", "H3", "H4", "H5", "H6", "L1")]
OPENINGS = [(v, o) for v in B.Variant for o in B.Orientation]

FID_QUERIES = (
    "formation", "personnel_of", "mounts_of", "account_of", "contacts_of", "available", "wounded",
    "dead", "captured", "serviceable_assigned_mounts", "movement_mode", "effort_charged",
    "effort_remaining", "projected_opening_effort", "effort_usable", "activation",
    "response_allowance_unused", "response_possible", "rest_benefit_pending",
    "recovery_safe_now", "rest_order_exists", "full_safe_interval",
)
SIDE_QUERIES = (
    "side_totals", "capacity_remaining", "projected_capacity", "usable_opportunities",
    "side_finished", "viable_count", "onmap_available", "exit_available",
)
STATE_QUERIES = (
    "next_side", "objective_status", "elapsed_minutes", "current_round", "normalized_digest",
    "encode_state", "canonical_bytes", "digest",
)


class ClosedPhaseTests(BattleCase):
    def assert_closed(self, s, elapsed):
        """The complete Terminal column of the 9.1 table."""
        for side in B.Side:
            self.assertEqual(B.usable_opportunities(s, side), 0)
            self.assertTrue(B.side_finished(s, side))
            self.assertIsNone(B.capacity_remaining(s, side))
            self.assertIsNone(B.projected_capacity(s, side))
        self.assertIsNone(B.next_side(s))
        self.assertIsNone(B.current_round(s))
        for fid in ROSTER:
            self.assertIs(B.activation(s, fid), B.Activation.CLOSED)
            self.assertFalse(B.response_allowance_unused(s, fid))
            self.assertFalse(B.response_possible(s, fid))
            self.assertFalse(B.rest_benefit_pending(s, fid))
            self.assertEqual(B.effort_usable(s, fid), 0)
            self.assertIsNone(B.effort_charged(s, fid))
            self.assertIsNone(B.effort_remaining(s, fid))
            self.assertIsNone(B.projected_opening_effort(s, fid))
            self.assertIsNone(B.rest_order_exists(s, fid))
            self.assertIsNone(B.full_safe_interval(s, fid))
        self.assertEqual(B.elapsed_minutes(s), elapsed)

    def test_at_q01(self):
        for v, o in OPENINGS:
            s = B.f01_opening(v, o)
            for side in B.Side:
                self.assertEqual(B.usable_opportunities(s, side), 0)
                self.assertFalse(B.side_finished(s, side))
                self.assertEqual(B.projected_capacity(s, side), 4)
                self.assertIsNone(B.capacity_remaining(s, side))
            self.assertIsNone(B.next_side(s))
            self.assertIsNone(B.current_round(s))
            self.assertEqual(B.elapsed_minutes(s), 0)
            for fid in ROSTER:
                self.assertEqual(B.effort_usable(s, fid), 0)
                self.assertFalse(B.response_allowance_unused(s, fid))
                self.assertFalse(B.response_possible(s, fid))
                self.assertIsNone(B.rest_order_exists(s, fid))
                self.assertIsNone(B.full_safe_interval(s, fid))
                self.assertFalse(B.rest_benefit_pending(s, fid))
                self.assertIs(B.activation(s, fid), B.Activation.CLOSED)
                self.assertIsNone(B.effort_charged(s, fid))
                self.assertIsNone(B.effort_remaining(s, fid))
                self.assertEqual(B.projected_opening_effort(s, fid), 3)

    def test_at_q02_q03(self):
        self.assert_closed(self.accept(deadline_objective_victory()), 120)
        defensive = B.FixtureId("F01-v1-defensive-mutual-capitulation")
        self.assert_closed(B.f01_supplied(defensive), 0)

    def test_at_q04(self):
        s = self.accept(a1())
        for side in B.Side:
            self.assertEqual(B.usable_opportunities(s, side), 4)
        for fid in ROSTER:
            self.assertIs(B.activation(s, fid), B.Activation.READY)
            self.assertEqual(B.effort_usable(s, fid), 3)
            self.assertEqual(B.projected_opening_effort(s, fid), 3)


class ObjectiveTests(BattleCase):
    def status(self, d):
        o = B.objective_status(self.accept(d))
        return o.kind, o.side

    def test_at_q05_x_obj(self):
        K = B.ObjectiveKind
        self.assertEqual(self.status(as_adversarial(opening_document(), "Q5A")), (K.UNHELD, None))
        d = cond(secure_o0("Q5B"), "S0.H1", fat=2)
        self.assertEqual(self.status(d), (K.SECURE, B.Side.S0))
        d = place(secure_o0("Q5C"), "S1.L1", (6, 3), 1)
        self.assertEqual(self.status(d), (K.CONTESTED, B.Side.S0))
        d = cond(place(secure_o0("Q5D"), "S1.L1", (6, 3), 1), "S0.H1", c=2)
        self.assertEqual(self.status(d), (K.CONTESTED, B.Side.S0))
        d = cond(secure_o0("Q5E"), "S0.H1", c=2)
        self.assertEqual(self.status(d), (K.INSECURE, B.Side.S0))
        d = place(secure_o0("Q5F"), "S1.H4", (5, 3), 4)
        d["contacts"] = [{"low": "S0.H1", "high": "S1.H4", "edge": [[5, 4], [5, 3]]}]
        self.assertEqual(self.status(d), (K.CONTESTED, B.Side.S0))

    def test_at_t14(self):
        s = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        self.assertEqual(B.threat_sources(s, B.Hex(5, 4)), (F("S0.L1"), F("S1.L1")))


class DerivedValueTests(BattleCase):
    def test_at_q06_d01_d06(self):
        s = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        obj = B.Hex(5, 4)
        self.assertEqual(B.threat_sources(s, obj), (F("S0.L1"), F("S1.L1")))
        self.assertEqual(B.threat_sources(s, obj, B.Side.S0), (F("S0.L1"),))
        self.assertEqual(B.threat_sources(s, obj, B.Side.S1), (F("S1.L1"),))
        self.assertEqual(B.threat_sources(s, B.Hex(4, 4)), (F("S0.L1"),))
        self.assertEqual(B.threat_sources(s, B.Hex(20, 20)), ())
        for fid in ROSTER:
            self.assertTrue(B.recovery_safe_now(s, fid))
        for side in B.Side:
            self.assertEqual(B.viable_count(s, side), 8)
        self.assertIs(B.objective_status(s).kind, B.ObjectiveKind.UNHELD)
        self.assertIs(B.end_of(s.scenario, B.Side.S0), B.End.RED)
        mirrored = B.f01_opening(B.Variant.OPEN, B.Orientation.MIRRORED)
        self.assertIs(B.end_of(mirrored.scenario, B.Side.S0), B.End.BLUE)
        with self.assertRaises(B.UnknownId):
            B.available(s, F("S9.X1"))
        for bad in ("S0.H1", B.GroupId("S0.G1")):
            with self.assertRaises(B.InvalidValue) as cm:
                B.available(s, bad)
            self.assertEqual((cm.exception.clause, cm.exception.path), ("T07", "fid"))

    def test_at_q07_public_routes(self):
        s = self.accept(a1())
        fid = F("S0.H1")
        calls = [(n, (fid,), "fid", "T07") for n in FID_QUERIES]
        calls += [(n, (B.Side.S0,), "side", "T03") for n in SIDE_QUERIES]
        calls += [(n, (), None, None) for n in STATE_QUERIES]
        calls += [("threat_sources", (B.Hex(5, 4),), "cell", "T15"),
                  ("charge", (fid, B.Hold()), "fid", "T07")]
        for name, args, argname, clause in calls:
            fn = getattr(B, name)
            with self.subTest(name=name):
                with self.assertRaises(B.InvalidValue) as cm:
                    fn(object(), *args)
                self.assertEqual((cm.exception.clause, cm.exception.path), ("V00", "state"))
                fn(s, *args)
                if argname is not None:
                    with self.assertRaises(B.InvalidValue) as cm:
                        fn(s, "S0.H1" if argname != "cell" else (5, 4), *args[1:])
                    self.assertEqual((cm.exception.clause, cm.exception.path), (clause, argname))
        with self.assertRaises(B.InvalidValue) as cm:
            B.charge(s, fid, "Hold")
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "work"))
        with self.assertRaises(B.InvalidValue) as cm:
            B.threat_sources(s, B.Hex(5, 4), "S0")
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T03", "side"))
        with self.assertRaises(B.InvalidValue) as cm:
            B.mirror_state(object())
        self.assertEqual(cm.exception.clause, "V00")
        with self.assertRaises(B.InvalidValue) as cm:
            B.mirror_state(s)
        self.assertEqual(cm.exception.clause, "P10")
        self.assertEqual(B.validate_state(object()), (B.Violation("V00", "", "not a BattleState"),))

    def test_at_q07_primitives(self):
        board = B.f01_board(B.Variant.ROUGH)
        scenario = B.f01_scenario(B.Variant.OPEN, B.Orientation.STANDARD)
        H, K, M = B.Hex, B.TemplateKind, B.MovementMode
        self.assertIs(B.movement_cost_kind(M.FOOT, K.HEAVY), K.HEAVY)
        self.assertEqual(B.direction_of(H(2, 6), H(2, 5)), 4)
        self.assertIsNone(B.direction_of(H(2, 6), H(2, 4)))
        self.assertEqual(B.terrain_cost(board, H(2, 4), K.HEAVY), 2)
        self.assertIsNone(B.terrain_cost(board, H(20, 4), K.HEAVY))
        self.assertIsNone(B.entry_cost(B.f01_board(B.Variant.BARRIER), H(3, 4), H(4, 4), K.HEAVY))
        self.assertIs(B.end_of(scenario, B.Side.S1), B.End.BLUE)
        for fn, args, path, clause in (
                (B.movement_cost_kind, ("FOOT", K.HEAVY), "mode", "T03"),
                (B.movement_cost_kind, (M.FOOT, "HEAVY"), "template", "T03"),
                (B.direction_of, ((2, 6), H(2, 5)), "origin", "T15"),
                (B.direction_of, (H(2, 6), [2, 5]), "destination", "T15"),
                (B.terrain_cost, (None, H(2, 4), K.HEAVY), "board", "T15"),
                (B.terrain_cost, (board, (2, 4), K.HEAVY), "cell", "T15"),
                (B.terrain_cost, (board, H(2, 4), "HEAVY"), "kind", "T03"),
                (B.entry_cost, (board, H(2, 5), (2, 4), K.HEAVY), "destination", "T15"),
                (B.end_of, ("scenario", B.Side.S0), "scenario", "T15"),
                (B.end_of, (scenario, "S0"), "side", "T03"),
                (B.f01_board, ("OPEN",), "variant", "T03"),
                (B.f01_opening, (B.Variant.OPEN, "STANDARD"), "orientation", "T03"),
                (B.f01_supplied, ("F01-shortfall",), "fixture_id", "T07"),
                (B.descriptor, (object(),), "fixture_id", "T07")):
            with self.subTest(fn=fn.__name__, path=path):
                with self.assertRaises(B.InvalidValue) as cm:
                    fn(*args)
                self.assertEqual((cm.exception.clause, cm.exception.path), (clause, path))
        with self.assertRaises(B.InvalidValue) as cm:
            B.movement_cost_kind(M.MOUNTED, K.HEAVY)
        self.assertEqual(cm.exception.clause, "R24")
        with self.assertRaises(B.UnknownId):
            B.f01_supplied(B.FixtureId("F01-nothing"))
        self.assertEqual(len(B.canonical_ids()), 6)
        self.assertEqual(len(B.supplied_ids()), 2)
