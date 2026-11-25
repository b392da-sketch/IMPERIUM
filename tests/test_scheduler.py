import unittest

from imperium.__main__ import mirror_task, simulate
from imperium.events import jsonl
from imperium.experiments import MIRROR
from imperium.fixture import Encounter, Formation, Identity
from imperium.geometry import mirror
from imperium.profiles import PROFILES
from imperium.scheduler import Action, Battle


def setup(*rows, mirrored=False):
    formations = []
    for identifier, position, disposition, *facing in rows:
        logical, role = divmod(identifier, 6)
        direction = facing[0] if facing else (4 if logical == 0 else 1)
        formations.append(Formation(Identity(logical, role), logical ^ int(mirrored),
                                    mirror(position) if mirrored else position,
                                    (direction + 3 * mirrored) % 6, disposition=disposition))
    return Battle(PROFILES["F6"], 20000, mirrored, encounter=Encounter(tuple(formations)))


class IntegratedDisplacementTests(unittest.TestCase):
    def test_exiting_primary_stays_occupied_for_batch(self):
        battle = setup((0, (4, 8), "routing"), (1, (4, 7), "routing"), (2, (3, 8), "organized"))
        battle.displace((1, 0))
        self.assertEqual(battle.units[0].disposition, "withdrawn")
        self.assertEqual(battle.units[1].position, (4, 7))
        self.assertTrue(battle.units[1].forced_stop)
        self.assertTrue(all(battle.units[i].mandatory_displacement_attempted for i in (0, 1)))

    def test_contested_destination(self):
        battle = setup((0, (4, 7), "routing"), (1, (5, 7), "routing"),
                       (2, (3, 8), "organized"), (3, (5, 8), "organized"))
        self.assertEqual(battle.displace((0, 1)).assignments, ())
        self.assertEqual(battle.metrics["blocked"], 2)

    def test_contested_fallback_and_mirror(self):
        rows = ((0, (4, 3), "routing"), (6, (4, 5), "routing"))
        for order in ((0, 6), (6, 0)):
            for reflected in (False, True):
                with self.subTest(order=order, reflected=reflected):
                    battle = setup(*rows, mirrored=reflected)
                    expected = ((0, (3, 4)), (6, (5, 4)))
                    if reflected:
                        expected = tuple((i, mirror(cell)) for i, cell in expected)
                    self.assertEqual(battle.displace(order).assignments, expected)

    def test_blocked_repulse_then_rout(self):
        battle = setup((0, (4, 6), "organized"), (1, (4, 7), "organized"), (2, (3, 7), "organized"))
        unit = battle.units[0]
        unit.cohesion = unit.morale = 1
        battle.pressure_stage({0: (1, 0)}, melee=True)
        battle.units[1].position = (5, 8)
        battle.pressure_stage({0: (0, 1)}, melee=True)
        self.assertEqual((unit.position, unit.disposition), ((4, 6), "routing"))
        self.assertTrue(unit.forced_stop)
        self.assertFalse(unit.principal_eligibility)
        self.assertEqual(unit.activity_marks, 0)

    def test_reaching_exit_consumes_attempt(self):
        battle = setup((0, (4, 7), "routing"), (1, (3, 8), "organized"))
        battle.displace((0,))
        battle.displace((0,))
        self.assertEqual(battle.units[0].position, (4, 8))
        self.assertEqual(battle.units[0].activity_marks, 1)

    def test_frozen_threat(self):
        battle = setup((0, (4, 3), "routing"), (6, (4, 5), "organized", 4))
        before = battle.units[6].position
        battle.displace((6, 0))
        self.assertNotEqual(battle.units[6].position, before)
        self.assertEqual(battle.units[0].position, (3, 4))

    def test_stationary_primary(self):
        battle = setup((0, (4, 7), "routing"), (1, (4, 8), "organized"))
        battle.displace((0,))
        self.assertEqual(battle.units[0].position, (3, 8))


class SchedulerTests(unittest.TestCase):
    def test_rejected_action_preserves_state(self):
        battle = setup((0, (4, 6), "organized"), (6, (4, 4), "organized"))
        before = battle.digest()
        with self.assertRaises(ValueError):
            battle.resolve(Action("move", 0, ((4, 5), (4, 4))))
        self.assertEqual(battle.digest(), before)
        self.assertEqual(battle.events, [])

    def test_last_opportunity_with_exact_effort(self):
        battle = setup((0, (4, 6), "organized"), (6, (4, 5), "organized"))
        battle.used[0] = 3
        battle.effort[0] = 2
        battle.resolve(Action("assault", 0, target=6))
        self.assertEqual(battle.effort[0], 0)
        self.assertEqual(battle.units[0].activity_marks, 2)
        self.assertEqual(battle.units[6].activity_marks, 1)

    def test_replay_and_event_mirror(self):
        config = MIRROR[0][0]
        battle, _ = simulate(config)
        replay, _ = simulate(config, scripted=battle.actions)
        self.assertEqual(jsonl(replay.events), jsonl(battle.events))
        self.assertEqual(mirror_task(MIRROR[0])["roots"], len(battle.events))

    def test_morale_shock_uses_pre_move_witnesses_and_deduplicates_waves(self):
        from unittest.mock import patch

        from imperium.physical import Casualties
        from imperium.pressure import Packet

        battle = setup((0, (4, 5), "organized"), (1, (3, 5), "organized"),
                       (2, (3, 6), "organized"), (6, (4, 4), "organized"))
        battle.units[0].cohesion = battle.units[0].morale = 1
        battle.units[1].cohesion, battle.units[1].morale = 2, 1
        with patch("imperium.scheduler.directed_packet",
                   side_effect=(Packet(Casualties(0, 0)), Packet(Casualties(0, 0), 1, 1))):
            battle.resolve(Action("assault", 0, target=6))
        self.assertEqual(battle.units[0].disposition, "routing")
        self.assertEqual(battle.units[1].disposition, "routing")
        self.assertEqual(battle.units[2].morale, 1)
        self.assertTrue(battle.units[2].incoming_effect_flag)
        self.assertEqual(sum(f.available_personnel for f in battle.ordered()), 960)

    def test_recovery_requires_full_interval_and_refuge_precedes_reform(self):
        battle = setup((0, (1, 2), "organized"), (1, (2, 2), "routing"),
                       (2, (2, 6), "organized"), (6, (9, 7), "organized"))
        unit = battle.units[0]
        unit.fatigue, unit.exertion_remainder = 1, 4
        battle.resolve(Action("rest", 0))
        battle.incoming(0)
        battle.resolve(Action("pass"))
        battle.resolve(Action("pass"))
        self.assertEqual((unit.fatigue, unit.exertion_remainder), (1, 4))
        self.assertEqual(battle.metrics["rest_interrupted"], 1)
        self.assertEqual(battle.units[1].disposition, "reforming")
        battle.resolve(Action("pass"))
        battle.resolve(Action("rest", 0))
        battle.resolve(Action("pass"))
        self.assertEqual((unit.fatigue, unit.exertion_remainder), (0, 0))
        self.assertEqual(battle.units[1].disposition, "organized")
