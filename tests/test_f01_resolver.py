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
