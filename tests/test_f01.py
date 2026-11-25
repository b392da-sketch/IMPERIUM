import unittest

from imperium.f01.combat import contribution, effect_key, packet
from imperium.f01.fixture import initial_formations, initial_groups
from imperium.f01.movement import group_translation, path_cost
from imperium.f01.terrain import BARRIER, OPEN, ROUGH, Edge, Terrain, in_front_sector
from imperium.geometry import mirror


class F01FoundationTests(unittest.TestCase):
    def test_exact_roster_and_mirror(self):
        units, reflected = initial_formations(), initial_formations(True)
        red_positions = ((2, 6), (3, 6), (4, 6), (5, 6), (3, 7), (4, 7), (4, 5), (1, 6))
        self.assertEqual(tuple(unit.position for unit in units[:8]), red_positions)
        self.assertEqual(tuple(unit.position for unit in units[8:]), tuple(map(mirror, red_positions)))
        self.assertEqual(len({unit.position for unit in units}), 16)
        self.assertEqual(tuple(unit.facing for unit in units), (4,) * 8 + (1,) * 8)
        self.assertEqual(sum(unit.available for unit in units), 3280)
        self.assertEqual(sum(unit.mounts for unit in units), 160)
        self.assertEqual(sum(unit.ammunition for unit in units), 32)
        self.assertEqual([group.members for group in initial_groups()],
                         [(0, 1, 4), (2, 3, 5), (8, 9, 12), (10, 11, 13)])
        for original, transformed in zip(units, reflected, strict=True):
            self.assertEqual(original.identity, transformed.identity)
            self.assertEqual(mirror(original.position), transformed.position)
            self.assertEqual((original.facing + 3) % 6, transformed.facing)

    def test_terrain_and_mount_shortfall(self):
        heavy, light, mounted = (initial_formations()[i] for i in (0, 6, 7))
        self.assertEqual([ROUGH.entry_cost(u, (2, 5), (2, 4)) for u in (heavy, light, mounted)],
                         [2, 1, 3])
        mounted.mounts -= 1
        self.assertEqual(mounted.movement_cap, 2)
        self.assertEqual(ROUGH.entry_cost(mounted, (2, 5), (2, 4)), 2)
        self.assertEqual(mounted.identity.template.slots, 20)

    def test_los_shared_edge_and_vertex(self):
        source, target = (3, 3), (4, 4)
        self.assertTrue(OPEN.line_of_sight(source, target, frozenset({source, target})))
        for cell in ((3, 4), (4, 3)):
            self.assertFalse(OPEN.line_of_sight(source, target, frozenset({cell})))
        shared = Terrain(edges=(Edge((3, 4), (4, 3), opaque=True),))
        self.assertFalse(shared.line_of_sight(source, target, frozenset()))
        self.assertTrue(OPEN.line_of_sight(source, (4, 7), frozenset({(4, 4), (3, 6)})))
        touch = Terrain(edges=(Edge((4, 4), (3, 5), opaque=True),))
        self.assertTrue(touch.line_of_sight(source, (4, 7), frozenset()))

    def test_los_and_edge_passability_independent(self):
        source, target = (3, 4), (4, 4)
        self.assertIsNone(BARRIER.entry_cost(initial_formations()[0], source, target))
        self.assertTrue(BARRIER.line_of_sight(source, target, frozenset()))
        opaque = Terrain(edges=(Edge(source, target, opaque=True),))
        self.assertEqual(opaque.entry_cost(initial_formations()[0], source, target), 1)
        self.assertFalse(opaque.line_of_sight(source, target, frozenset()))
        self.assertTrue(opaque.line_of_sight(target, source, frozenset()))
        self.assertTrue(in_front_sector((3, 3), (4, 4), 0))
        self.assertFalse(in_front_sector((3, 3), (2, 5), 0))

    def test_exertion_predicts_mounted_path_stop(self):
        mounted = initial_formations()[7]
        path = ((1, 5), (1, 4), (1, 3))
        self.assertEqual(path_cost(mounted, path, OPEN, frozenset(), frozenset(), False, 3), 3)
        mounted.fatigue, mounted.exertion = 1, 5
        with self.assertRaisesRegex(ValueError, "known stop"):
            path_cost(mounted, path, OPEN, frozenset(), frozenset(), False, 3)

    def test_group_follows_only_selected_vacating_members(self):
        units = {unit.identity.id: unit for unit in initial_formations()}
        ready = frozenset(range(8))
        effort = dict.fromkeys(ready, 3)
        result = group_translation(0, (0, 1, 4), 4, units, OPEN, ready,
                                   effort, frozenset(), frozenset())
        self.assertEqual(result, {0: ((2, 5), 1), 1: ((3, 5), 1), 4: ((3, 6), 1)})
        units[0].position = (2, 7)
        with self.assertRaisesRegex(ValueError, "blocked"):
            group_translation(0, (0, 4), 4, units, OPEN, ready, effort, frozenset(), frozenset())
        with self.assertRaisesRegex(ValueError, "membership"):
            group_translation(0, (0, 2), 4, units, OPEN, ready, effort, frozenset(), frozenset())

    def test_directed_packet_and_template_participation(self):
        units = initial_formations()
        self.assertEqual([contribution(units[i], "melee", 1) for i in (0, 6, 7)], [24, 18, 12])
        self.assertEqual([contribution(units[i], "missile") for i in (0, 6, 7)], [40, 22, 0])
        self.assertEqual(contribution(units[6], "melee", 4), 5)
        target = units[7]
        target.available, target.disposition = 1, "routing"
        channels = []

        def draw(channel):
            channels.append(channel)
            return .99

        self.assertEqual(packet(0, target, "missile", draw).casualties.wounded, 0)
        self.assertEqual(channels, [])
        result = packet(40, target, "missile", draw)
        self.assertEqual(result.casualties.killed + result.casualties.wounded, 1)
        self.assertEqual(channels, ["injury", "fatal"])
        self.assertEqual((result.cohesion, result.morale), (0, 0))

    def test_full_fixture_golden_keys(self):
        key = effect_key(22000, "F01-v1", 1, 3, 2, "missile", True, 14, 1, "injury")
        self.assertEqual(key.integer(), 4916743851368613)
        key = effect_key(22000, "F01-v1", 1, 4, 0, "melee", False, 0, 8, "morale")
        self.assertEqual(key.integer(), 6962112971620345)

    def test_loss_transfers_preserve_location_and_lineage(self):
        from imperium.physical import Casualties

        unit = initial_formations()[7]
        unit.record_losses("root4/leg0", Casualties(3, 5))
        unit.position = (1, 5)
        self.assertEqual((unit.available, unit.mounts, unit.ammunition), (72, 80, 0))
        self.assertEqual(len(unit.losses), 1)
        lot = unit.losses[0]
        self.assertEqual((lot.cell, lot.formation), ((1, 6), unit.identity))
        self.assertEqual(unit.available + lot.casualties.killed + lot.casualties.wounded, 80)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            unit.record_losses("root4/leg0", Casualties(1, 0))
        with self.assertRaisesRegex(ValueError, "invalid"):
            unit.record_losses("root5/leg0", Casualties(1, 72))
        self.assertEqual(unit.available, 72)
