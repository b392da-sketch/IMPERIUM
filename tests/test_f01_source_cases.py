"""Directed open-information acceptance cases for the F01 source register."""

import unittest
from itertools import combinations, product
from unittest.mock import patch

from imperium.f01.combat import contribution, packet
from imperium.f01.fixture import initial_groups
from imperium.f01.resolver import F01, Order, Reaction
from imperium.geometry import step
from imperium.physical import Casualties
from imperium.pressure import Packet

from .test_f01_resolver import fixture

ZERO = Packet(Casualties(0, 0))


class SourceCases(unittest.TestCase):
    def test_ct01_ct10_ct11_opportunities_forfeiture_and_closure(self):
        b = F01(22000)
        for i in range(4):
            before = b.elapsed
            b.resolve(Order("hold", (i,)))
            self.assertEqual(b.effort[i], 3)
            self.assertEqual(b.used[0], i + 1)
            self.assertNotIn(i, b.ready)
            self.assertEqual(b.elapsed, before)
            if i == 3:
                self.assertFalse(set(range(8)) & b.ready)
            b.resolve(Order("hold", (8 + i,)))
        self.assertEqual((b.root, b.round, b.side, b.elapsed), (8, 2, 1, 10))
        self.assertEqual(sum(e["kind"] == "root" for e in b.events), 8)

    def test_ct02_ct03_ct05_group_coverage_and_atomic_rejection(self):
        b = F01(22000)
        sequence = (
            Order("group-pivot", (0, 1, 4), turn=1),
            Order("group-pivot", (2, 3, 5), turn=1),
            Order("hold", (6,)),
            Order("hold", (7,)),
        )
        for index, order in enumerate(sequence):
            b.resolve(order)
            if index == 0:
                self.assertEqual([b.effort[i] for i in order.members], [2, 2, 2])
                b.resolve(Order("pass"))
                before = b.digest()
                for bad in (Order("group-pivot", (0, 1), turn=1),
                            Order("group-move", (2, 3, 5), turn=4),
                            Order("group-move", (2, 2, 3), turn=4)):
                    with self.assertRaises(ValueError):
                        b.resolve(bad)
                    self.assertEqual(b.digest(), before)
                self.assertEqual(b.used, [1, 0])
        self.assertEqual((b.round, b.elapsed), (2, 10))

    def test_ct06_rt05_paid_assault_then_response_then_free_resistance(self):
        b = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 1), (9, (3, 5), 0), (10, (5, 5), 1)))
        with patch("imperium.f01.resolver.packet", side_effect=(Packet(Casualties(0, 0), 2, 0), ZERO)):
            b.resolve(Order("assault", (0,), target=8))
        self.assertFalse(b.contacts)
        self.assertEqual(b.effort[0], 1)
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("move", (9,), path=((4, 5),)), lambda view, choices: Reaction("missile", 0, 9))
            self.assertEqual(b.effort[0], 0)
            self.assertEqual(b.units[0].ammunition, 1)
            b.resolve(Order("pass"))
            b.resolve(Order("assault", (10,), target=0))
        combat = next(s for s in b.events[-1]["stages"] if s["kind"] == "packets")
        self.assertEqual(combat["allocations"], [(10, 0, 24), (0, 10, 24)])
        self.assertEqual(b.units[0].exertion, 4)
        self.assertEqual(b.metrics["responses"], 1)

    def test_ct07_bt15_reaction_before_principal_and_round_shared_flag(self):
        b = F01(22000, formations=fixture((0, (4, 6), 4), (1, (5, 6), 4), (8, (4, 4), 1)))
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("move", (0,), path=((4, 5),)), lambda view, choices: Reaction("missile", 8, 0))
            self.assertIn(8, b.ready)
            self.assertEqual(b.effort[8], 2)
            self.assertEqual(b.reaction_options((0,), {0: (4, 6)}), ())
            b.resolve(Order("assault", (8,), target=0))
        self.assertEqual(b.effort[8], 0)
        self.assertIn((0, 8), b.contacts)
        self.assertEqual(b.units[8].exertion, 3)

    def test_ct08_gt09_declining_two_options_closes_root_window(self):
        b = F01(22000, formations=fixture((0, (4, 6), 4), (9, (5, 4), 3), (14, (4, 3), 1)))
        offers = []

        def decline(view, choices):
            offers.append(choices)
            return None

        b.resolve(Order("move", (0,), path=((4, 5), (4, 4))), decline)
        self.assertEqual(offers, [(Reaction("pivot", 9, 0, -1), Reaction("missile", 14, 0))])
        self.assertEqual([s["kind"] for s in b.events[-1]["stages"]],
                         ["translation", "reaction", "translation"])
        self.assertIsNone(b.events[-1]["stages"][1]["decision"])
        self.assertEqual(b.effort[14], 3)
        self.assertFalse(b.responded)
        self.assertEqual(b.units[0].position, (4, 4))

    def test_gt04_pivot_angle_and_threat_sources(self):
        for enemies, allowed in (
            (((8, (8, 3), 1),), {-3, -2, -1, 1, 2, 3}),
            (((8, (4, 5), 1),), {-1, 1}),
            (((8, (4, 5), 1), (9, (5, 5), 1)), set()),
        ):
            with self.subTest(enemies=enemies):
                b = F01(22000, formations=fixture((0, (4, 6), 4), *enemies))
                self.assertEqual({o.turn for o in b.legal_orders() if o.kind == "pivot"}, allowed)
                if 3 in allowed:
                    b.resolve(Order("pivot", (0,), turn=3))
                    self.assertEqual((b.effort[0], b.units[0].facing, b.units[0].exertion), (0, 1, 3))
        b = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 4)))
        b.contacts.add((0, 8))
        self.assertFalse(any(o.kind == "pivot" for o in b.legal_orders()))

    def test_gt08_overlay_and_nontraversable_threat(self):
        b = F01(22000, "barrier", formations=fixture((0, (3, 4), 0), (8, (4, 4), 3)))
        self.assertNotIn((4, 4), b.projected(0))
        self.assertIn(Order("missile", (0,), target=8), b.legal_orders())
        self.assertNotIn(Order("assault", (0,), target=8), b.legal_orders())
        b = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 4), 1), (9, (5, 4), 2)))
        self.assertIn((4, 5), b.projected(8) & b.projected(9))
        b.resolve(Order("move", (0,), path=((4, 5),)))
        self.assertEqual(b.units[0].position, (4, 5))
        self.assertFalse(b.contacts)

    def test_gt10_pivot_only_on_new_adjacent_and_no_other_enemy(self):
        b = F01(22000, formations=fixture((0, (4, 5), 4), (9, (5, 4), 3)))
        reaction = Reaction("pivot", 9, 0, -1)
        self.assertEqual(b.reaction_options((0,), {0: (4, 6)}), (reaction,))
        self.assertEqual(b.reaction_options((0,), {0: (5, 5)}), ())
        b.contacts.add((0, 9))
        self.assertEqual(b.reaction_options((0,), {0: (4, 6)}), ())
        b.contacts.clear()
        b.units[9].disposition = "routing"
        self.assertEqual(b.reaction_options((0,), {0: (4, 6)}), ())
        b = F01(22000, formations=fixture((0, (4, 5), 4), (1, (5, 5), 4), (9, (5, 4), 3)))
        self.assertEqual(b.reaction_options((0,), {0: (4, 6)}), ())

    def test_bt01_bt02_missile_negative_and_stationary_debits(self):
        for identifier, cell, facing, stock, contact in (
            (0, (4, 4), 4, 2, None),          # Range
            (0, (4, 5), 1, 2, None),          # Rear / sector
            (0, (4, 5), 4, 0, None),          # Empty stock
            (7, (4, 5), 4, 1, None),          # Mounted with no weapon
            (0, (4, 5), 4, 2, (0, 8)),        # Engaged shooter
            (0, (4, 5), 4, 2, (1, 8)),        # Engaged target
        ):
            with self.subTest(identifier=identifier, cell=cell, facing=facing, contact=contact):
                units = fixture((identifier, (4, 6), facing), (1, (3, 5), 4), (8, cell, 1))
                units[0].ammunition = stock
                b = F01(22000, formations=units)
                if contact:
                    b.contacts.add(contact)
                before = b.digest()
                with self.assertRaisesRegex(ValueError, "illegal attack"):
                    b.resolve(Order("missile", (identifier,), target=8))
                self.assertEqual(b.digest(), before)
        b = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 1)))
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("missile", (0,), target=8),
                      lambda *_: self.fail("stationary fire opened a reaction window"))
        self.assertEqual([s["kind"] for s in b.events[-1]["stages"]], ["packets"])
        self.assertEqual(b.events[-1]["stages"][0]["allocations"], [(0, 8, 40)])
        self.assertEqual((b.effort[0], b.units[0].ammunition, b.units[0].exertion), (2, 1, 1))
        self.assertEqual((b.effort[8], b.units[8].ammunition), (3, 2))

    def test_bt07_bt08_bt10_packet_support_by_template(self):
        units = fixture((0, (4, 6), 4), (6, (4, 5), 4), (7, (3, 6), 4))
        self.assertEqual([contribution(units[0], "melee", n) for n in (1, 2, 3)], [24, 20, 13])
        units[0].available = 360
        self.assertEqual(contribution(units[0], "melee", 3), 13)
        for source, target, stage, available, percentile in product(
            units, units, ("missile", "melee"), (0, 1, 5, 120), (0, .3, .8, .999999)
        ):
            target.available = available
            slots = contribution(source, stage, int(stage == "melee"))
            result = packet(slots, target, stage, lambda channel: percentile)
            template = target.identity.template
            cap = template.slots if stage == "missile" else template.edge_capacity
            killed, wounded = result.casualties.killed, result.casualties.wounded
            self.assertTrue(0 <= killed + wounded <= min(cap, available))
            self.assertTrue(0 <= result.cohesion <= 2 and 0 <= result.morale <= 2)

    def test_rt08_rt19_blocked_repulse_then_rout_shares_allowance(self):
        units = fixture((0, (4, 5), 4), (1, (4, 6), 4), (2, (3, 6), 4), (8, (4, 4), 1))
        units[0].cohesion = units[0].morale = 1
        b = F01(22000, formations=units)
        b.contacts.add((0, 8))
        b.pressure({0: (1, 0)}, melee=True)
        self.assertEqual(b.units[0].position, (4, 5))
        self.assertIn((0, 8), b.contacts)
        self.assertNotIn(0, b.ready)
        b.units[1].position = (5, 6)
        b.pressure({0: (0, 1)}, melee=False)
        self.assertEqual((b.units[0].position, b.units[0].disposition), ((4, 5), "routing"))
        self.assertEqual(b.displaced, {0})
        self.assertEqual(b.metrics["blocked_displacements"], 1)
        self.assertFalse(b.contacts)
        b.resolve(Order("pass"))
        b.resolve(Order("pass"))
        self.assertNotIn(0, b.displaced)

    def test_rt11_rt21_contested_displacement_fallback_order_independent(self):
        units = fixture((0, (4, 3), 4), (1, (1, 7), 4), (8, (4, 5), 1), (9, (8, 1), 1))
        units[0].disposition = units[2].disposition = "routing"
        for triggers in ((0, 8), (8, 0)):
            b = F01(22000, formations=units)
            b.displace(triggers)
            self.assertEqual((b.units[0].position, b.units[8].position), ((3, 4), (5, 4)))
            self.assertEqual((b.units[0].exertion, b.units[8].exertion), (1, 1))
            b.check_invariants()

    def test_rt09_rt12_frozen_threat_even_when_source_displaced(self):
        units = fixture((0, (4, 5), 4), (1, (1, 7), 4), (8, (5, 6), 3), (9, (8, 1), 1))
        units[0].disposition = "routing"
        b = F01(22000, formations=units)
        self.assertIn((4, 6), b.projected(8))
        b.displace((8, 0))
        self.assertEqual(b.units[0].position, (3, 6))
        self.assertNotEqual(b.units[8].position, (5, 6))

    def test_et01_et03_et04_objective_timing_and_exclusions(self):
        for state, label, winner in (
            ("secure", "secure", 0), ("empty", "empty", None), ("adverse", "condition", None),
            ("threatened", "threat", None), ("engaged", "contact", None),
        ):
            with self.subTest(state=state):
                centre = (5, 4) if state != "empty" else (5, 5)
                enemy = (5, 3) if state in ("threatened", "engaged") else (9, 1)
                units = fixture((0, centre, 4), (8, enemy, 1 if state == "threatened" else 4))
                if state == "adverse":
                    units[0].morale = 2
                b = F01(22000, formations=units)
                if state == "engaged":
                    b.contacts.add((0, 8))
                while b.round < 6:
                    b.resolve(Order("pass"))
                self.assertIsNone(b.terminal)
                self.assertEqual(b.objective()["classification"], label)
                while not b.terminal:
                    b.resolve(Order("pass"))
                self.assertEqual(b.terminal["winner"], winner)
                self.assertEqual(b.elapsed, 120)

    def test_et14_et15_edge_arrival_and_exit_are_distinct_attempts(self):
        units = fixture((0, (4, 7), 4), (1, (1, 6), 4), (8, (8, 1), 1))
        units[0].disposition = "routing"
        b = F01(22000, formations=units)
        b.displace((0,))
        self.assertEqual(b.units[0].position, (4, 8))
        b.resolve(Order("pass"))
        b.resolve(Order("pass"))
        self.assertNotIn(0, b.exits)
        b.resolve(Order("pass"))
        b.resolve(Order("pass"))
        self.assertEqual(b.exits[0].available, 240)
        self.assertEqual(b.exits[0].ammunition, 2)
        self.assertEqual(b.units[0].disposition, "withdrawn")
        self.assertEqual(b.elapsed, 20)

    def test_exhaustive_principal_enumeration_matches_validator(self):
        b = F01(22000)
        candidates = {Order(k) for k in ("pass", "declare-withdrawal", "capitulate")}
        for i, unit in b.units.items():
            if unit.identity.logical_side:
                continue
            members = (i,)
            candidates.update(Order(k, members) for k in ("hold", "rally", "rest", "evacuate"))
            candidates.update(Order("pivot", members, turn=d) for d in range(-3, 4))
            for j in b.units:
                candidates.update(Order(k, members, target=j) for k in ("missile", "assault"))
            for count in range(1, 4):
                for directions in product(range(6), repeat=count):
                    path = [unit.position]
                    for d in directions:
                        path.append(step(path[-1], d))
                    candidates.add(Order("move", members, path=tuple(path[1:])))
                    if count == 1:
                        candidates.add(Order("withdraw", members, path=tuple(path[1:])))
        for group in initial_groups():
            for size in (2, 3):
                for members in combinations(sorted(group.members), size):
                    candidates.update(Order("group-move", members, turn=d) for d in range(6))
                    candidates.update(Order("group-pivot", members, turn=d) for d in (-1, 1))
        accepted = set()
        for order in candidates:
            try:
                b.validate(order)
            except ValueError:
                continue
            accepted.add(order)
        self.assertEqual(set(b.legal_orders()), accepted)
        self.assertEqual(len(b.legal_orders()), len(accepted))

    def test_gt15_bt18_full_command_round_and_light_follow_on(self):
        b = F01(22000)
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("group-move", (0, 1, 4), turn=4))
            b.resolve(Order("group-move", (8, 9, 12), turn=1))
            b.resolve(Order("move", (6,), path=((5, 4),)),
                      lambda view, choices: Reaction("missile", 14, 6))
            self.assertEqual(b.units[14].ammunition, 3)
            self.assertIn(14, b.ready)
            b.resolve(Order("group-pivot", (10, 11, 13), turn=1))
            b.resolve(Order("group-pivot", (2, 3, 5), turn=1))
            b.resolve(Order("hold", (15,)))
            b.resolve(Order("move", (7,), path=((1, 5),)))
            self.assertEqual((b.elapsed, b.used), (0, [4, 3]))
            b.resolve(Order("pass"))
            self.assertEqual((b.round, b.side, b.elapsed), (2, 1, 10))
            assault = Order("assault", (14,), target=6)
            self.assertIn(assault, b.legal_orders())
            b.resolve(assault, lambda view, choices: Reaction("missile", 6, 14))
        kinds = [stage["kind"] for stage in b.events[-1]["stages"]]
        self.assertEqual(kinds, ["reaction", "packets", "packets"])
        self.assertEqual([s["weapon"] for s in b.events[-1]["stages"][1:]], ["missile", "melee"])
        self.assertIn((6, 14), b.contacts)

    def test_rt04_three_actual_marks_carry_to_six_and_no_pass_recovery(self):
        units = fixture((0, (4, 7), 4), (8, (3, 4), 0))
        units[0].exertion = 3
        b = F01(22000, formations=units)
        b.resolve(Order("move", (0,), path=((4, 6), (4, 5))))
        self.assertEqual((b.units[0].fatigue, b.units[0].exertion, b.effort[0]), (0, 5, 1))
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("move", (8,), path=((4, 4),)),
                      lambda view, choices: Reaction("missile", 0, 8))
        self.assertEqual((b.units[0].fatigue, b.units[0].exertion, b.effort[0]), (1, 0, 0))
        b.resolve(Order("pass"))
        b.resolve(Order("pass"))
        self.assertEqual((b.units[0].available, b.units[0].ammunition, b.units[0].fatigue),
                         (240, 1, 1))

    def test_rt01_rt06_exhaustion_is_not_loss_of_threat(self):
        units = fixture((0, (4, 6), 4), (8, (4, 5), 4))
        units[0].fatigue = 2
        b = F01(22000, formations=units)
        self.assertIn((4, 5), b.projected(0))
        self.assertNotIn(Order("assault", (0,), target=8), b.legal_orders())
        self.assertEqual(b.units[0].movement_cap, 1)
        b.units[0].fatigue = 0
        b.units[0].cohesion = 2
        self.assertEqual(b.projected(0), frozenset())
        self.assertEqual(b.units[0].available, 240)
        self.assertEqual(b.units[0].disposition, "organized")
        b.units[0].cohesion, b.units[0].morale = 0, 2
        self.assertNotIn(Order("assault", (0,), target=8), b.legal_orders())
        self.assertIn(Order("missile", (0,), target=8), b.legal_orders())

    def test_et07_et17_blocked_mutual_collapse_has_no_extra_casualties(self):
        units = fixture((0, (4, 6), 4), (8, (4, 5), 1))
        for u in units:
            u.cohesion = u.morale = 1
        b = F01(22000, formations=units)
        from imperium.f01.terrain import Terrain
        b.terrain = Terrain(impassable=frozenset({(4, 7), (3, 7), (4, 4), (5, 4)}))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0), 1, 1)):
            b.resolve(Order("assault", (0,), target=8))
        self.assertEqual(b.terminal["reason"], "mutual")
        self.assertEqual(b.terminal["defeat"], {0: "collapse", 1: "collapse"})
        self.assertEqual([u.position for u in b.units.values()], [(4, 6), (4, 5)])
        self.assertEqual([u.available for u in b.units.values()], [240, 240])
        self.assertEqual(b.metrics["blocked_displacements"], 2)
        self.assertFalse(b.custody or b.exits)

    def test_et18_closure_terminal_order_defensive_state(self):
        # Boundary-only fixture: inject the final loss of viability after the
        # principal checkpoint to exercise the closure's independent guard.
        units = fixture((0, (2, 6), 4), (8, (8, 0), 1))
        units[0].fatigue = 2
        b = F01(22000, formations=units)
        b.resolve(Order("rest", (0,)))
        b.units[8].disposition = "routing"
        b.ready.discard(8)
        b.close_round()
        self.assertEqual(b.exits[8].available, 240)
        self.assertEqual(b.terminal["defeat"], {1: "orderly_departure"})
        self.assertEqual(b.units[0].fatigue, 2)
        self.assertEqual(b.elapsed, 10)
        b.check_invariants()

    def test_et11_both_withdraw_then_one_exits_and_capitulation_precedence(self):
        for finish in ("evacuate", "capitulate"):
            with self.subTest(finish=finish):
                b = F01(22000, formations=fixture((0, (2, 8), 4), (8, (8, 0), 1)))
                b.resolve(Order("declare-withdrawal"))
                b.resolve(Order("declare-withdrawal"))
                b.resolve(Order(finish, (0,) if finish == "evacuate" else ()))
                self.assertEqual(b.terminal["reason"], "mutual_abandonment" if finish == "evacuate" else "capitulation")
                self.assertEqual(b.terminal["winner"], None if finish == "evacuate" else 1)
                self.assertEqual(b.elapsed, 10)

    def test_hm01_hm02_reject_invalid_fixture_inventory_and_lots(self):
        from imperium.f01.fixture import LossLot

        for mutation in ("stock", "negative", "duplicate", "lineage"):
            with self.subTest(mutation=mutation):
                units = fixture((0, (4, 6), 4), (8, (4, 5), 1))
                unit = units[0]
                if mutation == "stock":
                    unit.ammunition = True
                else:
                    lot = LossLot(units[1].identity if mutation == "lineage" else unit.identity,
                                  "fixture", unit.position,
                                  Casualties(-1, 2) if mutation == "negative" else Casualties(1, 0))
                    unit.losses = (lot, lot) if mutation == "duplicate" else (lot,)
                with self.assertRaises(AssertionError):
                    F01(22000, formations=units)

    def test_bt09_neutral_coefficients_and_backward_inherent_resistance(self):
        units = fixture((0, (4, 6), 4), (8, (4, 5), 4))
        b = F01(22000, formations=units)
        self.assertNotIn((4, 6), b.projected(8))
        b.effort[8] = 0
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("assault", (0,), target=8))
        self.assertEqual(b.events[-1]["stages"][0]["allocations"], [(0, 8, 24), (8, 0, 24)])
        self.assertEqual(b.units[8].exertion, 1)
        target = b.units[8]
        rear = packet(24, target, "melee", lambda _: .75)
        target.facing = 1
        self.assertEqual(packet(24, target, "melee", lambda _: .75), rear)

    def test_et03_refuge_at_o0_is_still_insecure_until_organized(self):
        for disposition in ("routing", "reforming"):
            with self.subTest(disposition=disposition):
                units = fixture((0, (5, 4), 4), (1, (1, 6), 4), (8, (9, 1), 1))
                units[0].disposition = disposition
                units[0].cohesion = units[0].morale = 2
                b = F01(22000, formations=units)
                while not b.terminal:
                    b.resolve(Order("pass"))
                self.assertEqual(b.units[0].position, (5, 4))
                self.assertEqual(b.units[0].disposition, "reforming")
                self.assertEqual(b.objective()["classification"], "condition")
                self.assertEqual(b.terminal["reason"], "unresolved")

    def test_et13_safe_own_edge_still_requires_two_effort(self):
        b = F01(22000, formations=fixture((0, (5, 8), 4), (8, (9, 1), 1)))
        b.effort[0] = 1
        before = b.digest()
        with self.assertRaisesRegex(ValueError, "insufficient effort"):
            b.resolve(Order("evacuate", (0,)))
        self.assertEqual(b.digest(), before)

    def test_gt12_withdrawal_cost_and_blocking(self):
        units = fixture((0, (2, 3), 4), (8, (9, 1), 1))
        b = F01(22000, "rough", formations=units)
        b.resolve(Order("withdraw", (0,), path=((2, 4),)))
        self.assertEqual(b.units[0].position, (2, 4))
        self.assertEqual((b.effort[0], b.units[0].exertion, b.units[0].facing), (0, 2, 4))
        for variant, start, facing, end, opponents in (
            ("barrier", (4, 4), 0, (3, 4), ((8, (9, 1), 1),)),
            ("open", (2, 8), 4, (2, 9), ((8, (9, 1), 1),)),
            ("open", (4, 5), 4, (4, 6), ((8, (4, 6), 1),)),
            ("open", (4, 5), 4, (4, 6), ((8, (5, 6), 3),)),
        ):
            with self.subTest(variant=variant, start=start, end=end):
                b = F01(22000, variant, formations=fixture((0, start, facing), *opponents))
                before = b.digest()
                with self.assertRaisesRegex(ValueError, "blocked rear"):
                    b.resolve(Order("withdraw", (0,), path=(end,)))
                self.assertEqual(b.digest(), before)

    def test_ct09_pass_forfeits_two_slots_and_preserves_other_side_budget(self):
        b = F01(22000)
        for i in (0, 1):
            b.resolve(Order("hold", (i,)))
            b.resolve(Order("hold", (8 + i,)))
        b.resolve(Order("pass"))
        self.assertEqual(b.used, [2, 2])
        self.assertFalse(set(range(8)) & b.ready)
        b.resolve(Order("hold", (10,)))
        self.assertEqual((b.side, b.elapsed), (1, 0))
        b.resolve(Order("hold", (11,)))
        self.assertEqual((b.round, b.side, b.elapsed), (2, 1, 10))

    def test_gt02_gt03_role_mobility_and_actual_rough_debit(self):
        for i, cap in ((0, 2), (6, 2), (7, 3)):
            with self.subTest(i=i):
                b = F01(22000, formations=fixture((i, (4, 7), 4), (8, (9, 1), 1)))
                moves = [order for order in b.legal_orders() if order.kind == "move"]
                self.assertEqual(max(len(order.path) for order in moves), cap)
                for path in (((4, 8),), ((3, 7),), ((4, 6), (4, 7))):
                    with self.assertRaises(ValueError):
                        b.validate(Order("move", (i,), path=path))
        b = F01(22000, "rough", formations=fixture((0, (2, 6), 4), (8, (9, 1), 1)))
        b.resolve(Order("move", (0,), path=((2, 5), (2, 4))))
        self.assertEqual(b.effort[0], 0)
        self.assertEqual(b.units[0].facing, 4)
        self.assertEqual([s["moves"][0][2] for s in b.events[-1]["stages"]], [1, 2])
        mounted = F01(22000, "rough", formations=fixture((7, (2, 5), 4), (8, (9, 1), 1)))
        with self.assertRaisesRegex(ValueError, "insufficient effort"):
            mounted.validate(Order("move", (7,), path=((2, 4), (2, 3))))

    def test_bt01_bt04_occluded_fire_and_existing_contact_has_no_window(self):
        b = F01(22000, formations=fixture((6, (4, 6), 4), (0, (4, 5), 4), (8, (4, 4), 1)))
        with self.assertRaisesRegex(ValueError, "illegal attack"):
            b.validate(Order("missile", (6,), target=8))
        b = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 1)))
        b.contacts.add((0, 8))
        with patch("imperium.f01.resolver.packet", return_value=ZERO):
            b.resolve(Order("assault", (0,), target=8), lambda *_: self.fail("engaged response"))
        self.assertEqual(b.contacts, {(0, 8)})
        self.assertEqual([stage["kind"] for stage in b.events[-1]["stages"]], ["packets"])

    def test_et19_standalone_terminal_round_five_freezes_clock(self):
        b = F01(22000, formations=fixture((0, (2, 6), 4), (8, (9, 1), 1)))
        while b.round < 5:
            b.resolve(Order("pass"))
        self.assertEqual(b.elapsed, 40)
        b.resolve(Order("capitulate"))
        self.assertEqual((b.round, b.elapsed), (5, 50))
        self.assertEqual(b.terminal["reason"], "capitulation")
        before = b.digest()
        with self.assertRaisesRegex(ValueError, "no principal opportunity"):
            b.resolve(Order("pass"))
        self.assertEqual(b.digest(), before)

    def test_reaction_candidates_are_authoritative_for_both_choices_and_decline(self):
        units = fixture((0, (4, 6), 4), (9, (5, 4), 3), (14, (4, 3), 1))
        order = Order("move", (0,), path=((4, 5), (4, 4)))
        legal = (Reaction("pivot", 9, 0, -1), Reaction("missile", 14, 0))
        for chosen in (*legal, None, Reaction("pivot", 9, False, -1)):
            with self.subTest(chosen=chosen):
                b = F01(22000, formations=units)

                def choose(_, offered):
                    self.assertEqual(offered, legal)
                    return chosen

                if chosen is not None and type(chosen.target) is bool:
                    with self.assertRaisesRegex(ValueError, "invalid elective response"):
                        b.resolve(order, choose)
                    self.assertFalse(b.responded)
                    with self.assertRaisesRegex(ValueError, "faulted"):
                        b.resolve(Order("pass"))
                    continue
                with patch("imperium.f01.resolver.packet", return_value=ZERO):
                    b.resolve(order, choose)
                self.assertEqual(b.responded, {chosen.source} if chosen else set())
                self.assertEqual(sum(s["kind"] == "reaction" for s in b.events[-1]["stages"]), 1)
                if chosen and chosen.kind == "pivot":
                    self.assertEqual(b.units[0].position, (4, 5))
                    self.assertEqual(b.effort[0], 2)
                    self.assertEqual(b.events[-1]["stages"][-1]["kind"], "movement-interrupted")
                else:
                    self.assertEqual(b.units[0].position, (4, 4))
