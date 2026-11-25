import unittest
from unittest.mock import patch

from imperium.f01.fixture import initial_formations
from imperium.f01.resolver import F01, Order, Reaction
from imperium.physical import Casualties
from imperium.pressure import Packet


def fixture(*placements):
    roster = initial_formations()
    selected = []
    for i, cell, facing in placements:
        unit = roster[i]
        unit.position, unit.facing = cell, facing
        selected.append(unit)
    return selected


class ResolverTests(unittest.TestCase):
    def test_last_opportunity_group_commits_selected_following(self):
        battle = F01(22000)
        battle.resolve(Order("hold", (2,)))
        battle.resolve(Order("pass"))
        battle.resolve(Order("hold", (3,)))
        battle.resolve(Order("hold", (5,)))
        battle.resolve(Order("group-move", (0, 1, 4), turn=4))
        self.assertEqual(battle.units[4].position, (3, 6))
        self.assertEqual(battle.round, 2)
        self.assertEqual(battle.elapsed, 10)

    def test_group_pivot_commits_one_stage(self):
        battle = F01(22000)
        battle.resolve(Order("group-pivot", (0, 1, 4), turn=1))
        self.assertEqual([battle.units[i].facing for i in (0, 1, 4)], [5, 5, 5])
        self.assertEqual(battle.used, [1, 0])
        self.assertEqual(battle.events[-1]["stages"][0]["kind"], "group-pivot")

    def test_exact_paid_assault_and_defensive_pivot(self):
        battle = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 5)))
        battle.effort[0] = 2
        battle.resolve(Order("assault", (0,), target=8),
                       lambda view, choices: Reaction("pivot", 8, 0, 1))
        self.assertEqual(battle.effort[0], 0)
        self.assertEqual(battle.effort[8], 2)
        self.assertEqual(battle.units[8].facing, 0)
        self.assertTrue(any(stage["kind"] == "packets" for stage in battle.events[-1]["stages"]))

    def test_reaction_after_pass_routs_and_interrupts_path(self):
        units = fixture((0, (4, 6), 4), (1, (0, 6), 4), (14, (4, 3), 1))
        units[0].cohesion = units[0].morale = 1
        battle = F01(22000, formations=units)
        battle.resolve(Order("hold", (1,)))
        battle.resolve(Order("pass"))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0), 1, 1)):
            battle.resolve(Order("move", (0,), path=((4, 5), (4, 4))),
                           lambda view, choices: Reaction("missile", 14, 0))
        self.assertEqual(battle.units[0].disposition, "routing")
        self.assertEqual(battle.units[14].ammunition, 3)
        self.assertEqual(battle.metrics["steps"], 1)
        self.assertTrue(any(stage["kind"] == "movement-interrupted"
                            for stage in battle.events[-1]["stages"]))

    def test_defensive_missile_aborts_paid_assault(self):
        units = fixture((0, (4, 6), 4), (1, (0, 6), 4), (8, (4, 5), 1))
        units[0].cohesion = units[0].morale = 1
        battle = F01(22000, formations=units)
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0), 1, 1)):
            battle.resolve(Order("assault", (0,), target=8),
                           lambda view, choices: Reaction("missile", 8, 0))
        self.assertEqual(battle.effort[0], 1)
        self.assertEqual(battle.metrics["assault_interruptions"], 1)
        self.assertFalse(battle.contacts)

    def test_missile_ammunition_spent_once(self):
        battle = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 1)))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0))):
            battle.resolve(Order("missile", (0,), target=8))
            battle.resolve(Order("pass"))
            battle.resolve(Order("pass"))
            battle.resolve(Order("pass"))
            battle.resolve(Order("missile", (0,), target=8))
        self.assertEqual(battle.units[0].ammunition, 0)
        self.assertEqual(battle.spent_ammunition, 2)
        self.assertFalse(battle.missile_legal(0, 8))

    def test_shared_contact_allocation_persists_across_rounds(self):
        battle = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 1),
                                               (9, (5, 5), 1)))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0))):
            battle.resolve(Order("assault", (0,), target=8))
            battle.resolve(Order("pass"))
            battle.resolve(Order("pass"))
            battle.resolve(Order("pass"))
            battle.resolve(Order("assault", (0,), target=9))
            allocation = next(s for s in battle.events[-1]["stages"] if s["kind"] == "packets")
        self.assertEqual(battle.contacts, {(0, 8), (0, 9)})
        self.assertEqual(allocation["allocations"], [(0, 9, 20), (9, 0, 24)])

    def test_reciprocal_rout_and_local_shock(self):
        units = fixture((0, (4, 6), 4), (1, (3, 6), 4), (8, (4, 5), 1))
        for unit in units[:1] + units[2:]:
            unit.cohesion = unit.morale = 1
        battle = F01(22000, formations=units)
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0), 1, 1)):
            battle.resolve(Order("assault", (0,), target=8))
        self.assertEqual(battle.units[1].morale, 1)
        self.assertEqual(battle.units[0].disposition, "routing")
        self.assertEqual(battle.units[8].disposition, "routing")
        self.assertEqual(battle.terminal["winner"], 0)

    def test_frozen_batch_does_not_follow_evacuating_primary(self):
        units = fixture((0, (4, 8), 4), (1, (4, 7), 4), (2, (3, 8), 4), (8, (9, 1), 1))
        units[0].disposition = units[1].disposition = "routing"
        battle = F01(22000, formations=units)
        battle.displace((0, 1))
        self.assertEqual(battle.exits[0].cell, (4, 8))
        self.assertEqual(battle.units[1].position, (4, 7))
        battle.check_invariants()

    def test_evacuation_captures_no_offboard_assets(self):
        battle = F01(22000, formations=fixture((0, (2, 6), 4), (7, (1, 8), 4),
                                               (8, (8, 2), 1)))
        battle.resolve(Order("evacuate", (7,)))
        battle.resolve(Order("pass"))
        battle.resolve(Order("capitulate"))
        self.assertEqual(battle.exits[7].mounts, 80)
        self.assertEqual(battle.custody[0].available, 240)
        self.assertNotIn(7, battle.custody)
        self.assertEqual(battle.elapsed, 10)
        self.assertEqual(battle.terminal["reason"], "capitulation")
        battle.check_invariants()

    def test_round_zero_terminal_and_observation_isolation(self):
        units = fixture((0, (2, 6), 4), (8, (8, 2), 1))
        units[1].disposition = "routing"
        battle = F01(22000, formations=units)
        self.assertEqual((battle.round, battle.elapsed), (0, 0))
        self.assertEqual(battle.terminal["defeat"], {1: "collapse"})
        before = battle.digest()
        with self.assertRaisesRegex(ValueError, "no principal opportunity"):
            battle.resolve(Order("pass"))
        self.assertEqual(battle.digest(), before)
        view = battle.observe(0)
        self.assertFalse(hasattr(view, "seed"))
        self.assertFalse(hasattr(view.formations[1], "losses"))
        self.assertEqual(tuple(i for i, _ in view.own_effort), (0,))

    def test_response_after_spent_principal_and_condition_cap(self):
        units = fixture((0, (4, 6), 4), (1, (0, 6), 4), (14, (4, 3), 1))
        units[0].cohesion = 1
        battle = F01(22000, formations=units)
        battle.resolve(Order("hold", (1,)))
        battle.resolve(Order("hold", (14,)))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0), 1, 0)):
            battle.resolve(Order("move", (0,), path=((4, 5), (4, 4))),
                           lambda view, choices: Reaction("missile", 14, 0))
        self.assertEqual(battle.units[0].position, (4, 5))
        self.assertEqual(battle.units[0].cohesion, 2)
        self.assertEqual(battle.effort[0], 2)
        self.assertIn(14, battle.responded)

    def test_shock_is_deduplicated_across_rout_waves(self):
        units = fixture((0, (4, 6), 4), (1, (3, 6), 4), (2, (3, 7), 4), (8, (4, 5), 1))
        units[0].cohesion = units[0].morale = 1
        units[1].cohesion, units[1].morale = 2, 1
        battle = F01(22000, formations=units)
        with patch("imperium.f01.resolver.packet", side_effect=(
            Packet(Casualties(0, 0)), Packet(Casualties(0, 0), 1, 1)
        )):
            battle.resolve(Order("assault", (0,), target=8))
        self.assertEqual(battle.units[1].disposition, "routing")
        self.assertEqual(battle.units[2].morale, 1)
        waves = [s["recipients"] for s in battle.events[-1]["stages"] if s["kind"] == "shock"]
        self.assertEqual(waves, [[1, 2]])

    def test_zero_allocation_and_controlled_disengagement(self):
        units = fixture((0, (4, 6), 4), (8, (4, 5), 3), (9, (5, 5), 1))
        units[0].record_losses("fixture", Casualties(239, 0))
        battle = F01(22000, formations=units)
        battle.contacts.add((0, 8))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0))):
            battle.resolve(Order("assault", (0,), target=9))
        packets = next(s for s in battle.events[-1]["stages"] if s["kind"] == "packets")
        self.assertEqual(packets["allocations"][0], (0, 9, 0))
        battle.resolve(Order("pass"))
        battle.resolve(Order("pass"))
        battle.resolve(Order("pass"))
        battle.resolve(Order("withdraw", (0,), path=((4, 7),)))
        self.assertFalse(battle.contacts)
        self.assertEqual(battle.units[0].available, 1)

    def test_captured_wounds_preserve_field_location_and_lineage(self):
        units = fixture((0, (1, 8), 4), (7, (2, 7), 4), (8, (9, 1), 1))
        units[0].record_losses("fixture", Casualties(5, 7))
        battle = F01(22000, formations=units)
        battle.resolve(Order("evacuate", (0,)))
        battle.resolve(Order("pass"))
        battle.resolve(Order("capitulate"))
        self.assertEqual(battle.exits[0].available, 228)
        self.assertEqual(battle.units[0].losses[0].casualties.wounded, 7)
        self.assertEqual(battle.wound_custody[0], 1)
        self.assertEqual(battle.custody[7].mounts, 80)
        battle.check_invariants()

    def test_invalid_precision_type_and_packets_fail_closed(self):
        battle = F01(22000, formations=fixture((0, (4, 6), 4), (8, (4, 5), 1)))
        before = battle.digest()
        with self.assertRaisesRegex(ValueError, "field type"):
            battle.resolve(Order("hold", (False,)))
        self.assertEqual(battle.digest(), before)
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(25, 0))):
            with self.assertRaisesRegex(AssertionError, "directed packet"):
                battle.resolve(Order("assault", (0,), target=8))
        with self.assertRaisesRegex(ValueError, "faulted"):
            battle.resolve(Order("pass"))

    def test_disabled_group_authority_preserves_local_control(self):
        battle = F01(22000, inactive_groups=((0, "G1"),))
        with self.assertRaisesRegex(ValueError, "authority"):
            battle.resolve(Order("group-move", (0, 1, 4), turn=4))
        battle.resolve(Order("move", (0,), path=((2, 5),)))
        self.assertEqual(battle.units[0].position, (2, 5))

    def test_interrupt_rest_with_safe_range_two_fire(self):
        units = fixture((0, (4, 6), 4), (14, (4, 4), 1))
        units[0].fatigue = 2
        battle = F01(22000, formations=units)
        battle.resolve(Order("rest", (0,)))
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(0, 0))):
            battle.resolve(Order("missile", (14,), target=0))
        battle.resolve(Order("pass"))
        battle.resolve(Order("pass"))
        self.assertEqual(battle.units[0].fatigue, 2)
        self.assertEqual(battle.metrics["rest_interrupted"], 1)

    def test_reciprocal_depletion_preserves_assets(self):
        units = fixture((7, (4, 6), 4), (15, (4, 5), 1))
        for unit in units:
            unit.record_losses("fixture", Casualties(79, 0))
        battle = F01(22000, formations=units)
        with patch("imperium.f01.resolver.packet", return_value=Packet(Casualties(1, 0))):
            battle.resolve(Order("assault", (7,), target=15))
        self.assertEqual(battle.terminal["reason"], "mutual")
        self.assertEqual(battle.elapsed, 10)
        self.assertEqual(sum(stock.mounts for stock in battle.removed_assets.values()), 160)
        battle.check_invariants()

    def test_orderly_departure_and_mutual_abandonment(self):
        for mutual in (False, True):
            with self.subTest(mutual=mutual):
                units = fixture((0, (2, 8), 4), (8, (8, 1), 1))
                battle = F01(22000, formations=units)
                battle.resolve(Order("hold", (0,)))
                battle.resolve(Order("declare-withdrawal") if mutual else Order("pass"))
                battle.resolve(Order("pass"))
                if mutual:
                    battle.resolve(Order("pass"))
                if battle.side == 1:
                    battle.resolve(Order("pass"))
                battle.resolve(Order("evacuate", (0,)))
                self.assertEqual(battle.terminal["reason"], "mutual_abandonment" if mutual else "military")
                self.assertEqual(battle.terminal["defeat"][0], "orderly_departure")
                self.assertEqual(battle.elapsed, 20)
                battle.check_invariants()

    def test_safe_refuge_reformer_gates_and_later_rally(self):
        units = fixture((0, (2, 6), 4), (1, (3, 6), 4), (8, (8, 2), 1))
        units[0].disposition = "routing"
        units[0].cohesion = units[0].morale = 2
        battle = F01(22000, formations=units)
        battle.resolve(Order("pass"))
        battle.resolve(Order("pass"))
        self.assertEqual(battle.units[0].disposition, "reforming")
        battle.resolve(Order("pass"))
        legal = {order.kind for order in battle.legal_orders() if order.members == (0,)}
        self.assertEqual(legal, {"rally", "hold"})
        battle.resolve(Order("rally", (0,)))
        battle.resolve(Order("pass"))
        self.assertEqual(battle.units[0].disposition, "organized")
        self.assertEqual((battle.units[0].cohesion, battle.units[0].morale), (1, 1))

    def test_withdrawal_posture_costs_opportunity_and_precedes_o0(self):
        units = fixture((0, (5, 4), 4), (8, (9, 1), 1))
        battle = F01(22000, formations=units)
        battle.resolve(Order("declare-withdrawal"))
        self.assertEqual(battle.used, [1, 0])
        self.assertEqual(battle.units[0].position, (5, 4))
        battle.resolve(Order("pass"))
        self.assertFalse(any(order.kind in ("assault", "missile") for order in battle.legal_orders()))
        with self.assertRaisesRegex(ValueError, "progress"):
            battle.resolve(Order("move", (0,), path=((5, 3),)))
        while not battle.terminal:
            battle.resolve(Order("pass"))
        self.assertEqual(battle.objective()["secure"], 0)
        self.assertEqual(battle.terminal["winner"], 1)
        self.assertEqual(battle.terminal["reason"], "abandonment")
        self.assertEqual(battle.elapsed, 120)

    def test_voluntary_exit_requires_designated_edge_and_safety(self):
        cases = (
            ((3, 7), (9, 1)),
            ((3, 8), (4, 7)),
        )
        for friendly, enemy in cases:
            with self.subTest(friendly=friendly, enemy=enemy):
                battle = F01(22000, formations=fixture((0, friendly, 4), (8, enemy, 1)))
                before = battle.digest()
                with self.assertRaisesRegex(ValueError, "illegal principal"):
                    battle.resolve(Order("evacuate", (0,)))
                self.assertEqual(battle.digest(), before)
