import math
import unittest

from imperium.displacement import arbitrate
from imperium.experiments import CONFIRMATION, MIRROR, POLICY, SCREENING, Run
from imperium.fixture import initial_encounter
from imperium.geometry import HEIGHT, OBJECTIVE, WIDTH, distance, front, in_bounds, mirror, step
from imperium.participation import allocate
from imperium.physical import beta_binomial, binomial, casualties
from imperium.pressure import directed_packet
from imperium.profiles import PROFILES
from imperium.randomness import DrawKey, inverse_cdf, melee_stage


def unexpected_draw(*args):
    raise AssertionError(f"unexpected random draw {args}")


class GeometryTests(unittest.TestCase):
    def test_fixture_and_mirror(self):
        original = initial_encounter(PROFILES["R0"])
        rotated = initial_encounter(PROFILES["R0"], mirrored=True)
        positions = {formation.position for formation in original.formations}
        self.assertEqual(len(positions), 12)
        self.assertTrue(all(map(in_bounds, positions)))
        self.assertEqual(sum(f.available_personnel for f in original.formations), 2880)
        self.assertEqual(mirror(OBJECTIVE), OBJECTIVE)
        for a, b in zip(original.formations, rotated.formations, strict=True):
            self.assertEqual(a.identity, b.identity)
            self.assertNotEqual(a.physical_side, b.physical_side)
            self.assertEqual(a.fatigue, 1)
            self.assertEqual(mirror(a.position), b.position)
            self.assertEqual(tuple((d + 3) % 6 for d in front(a.facing)), front(b.facing))

    def test_axial_steps_and_rotation(self):
        for q in range(WIDTH):
            for r in range(HEIGHT):
                for direction in range(6):
                    cell = (q, r)
                    neighbor = step(cell, direction)
                    self.assertEqual(distance(cell, neighbor), 1)
                    self.assertEqual(mirror(neighbor), step(mirror(cell), direction + 3))


class ParticipationTests(unittest.TestCase):
    def test_reference_allocations(self):
        self.assertEqual(allocate(240, 1, "B"), (24,))
        self.assertEqual(allocate(240, 2, "B"), (20, 20))
        self.assertEqual(allocate(240, 3, "C"), (20, 10, 10))
        self.assertEqual(allocate(1, 6, "C"), (1, 0, 0, 0, 0, 0))
        self.assertEqual(allocate(240, 2, "C", routing=True), (0, 0))

    def test_exhaustive_capacity_bounds(self):
        for model in ("B", "C"):
            for available in range(241):
                for count in range(7):
                    values = allocate(available, count, model)
                    self.assertEqual(len(values), count)
                    self.assertTrue(all(0 <= value <= 24 for value in values))
                    self.assertLessEqual(sum(values), min(available, 40))


class RandomnessTests(unittest.TestCase):
    def test_golden_vectors(self):
        for source, channel, numerator in (
            (0, "injury", 3009345297762912),
            (6, "injury", 2811142551922415),
            (0, "cohesion", 5676462493038990),
        ):
            with self.subTest(source=source, channel=channel):
                key = DrawKey(20000, "EF09-RH1", 20000, melee_stage(1, 0, 1, 0, 6, source), channel)
                self.assertEqual(key.integer(), numerator)
        self.assertEqual(DrawKey(256, "D43-dev-micro", 256, "A-to-B", "injury").integer(),
                         4417050748692798)

    def test_strict_inverse_and_endpoints(self):
        self.assertEqual(inverse_cdf((0.25, 0.75), lambda: 0.25), 1)
        self.assertEqual(inverse_cdf((0.25, 0.75), lambda: math.nextafter(0.25, 0)), 0)
        self.assertEqual(inverse_cdf((0, 0, 1), unexpected_draw), 2)
        self.assertEqual(inverse_cdf((1, 0, 0), unexpected_draw), 0)

    def test_distribution_moments(self):
        for n in (1, 5, 24):
            for p in (0.001, 0.1, 0.5, 0.99):
                for rho in (0, 0.05):
                    with self.subTest(n=n, p=p, rho=rho):
                        masses = beta_binomial(n, p, rho)
                        mean = math.fsum(k * mass for k, mass in enumerate(masses))
                        variance = math.fsum((k - mean)**2 * mass for k, mass in enumerate(masses))
                        self.assertAlmostEqual(math.fsum(masses), 1)
                        self.assertAlmostEqual(mean, n * p)
                        self.assertAlmostEqual(variance, n * p * (1 - p) * (1 + (n - 1) * rho))
        self.assertEqual(beta_binomial(24, 1, 0.05), binomial(24, 1))
        self.assertEqual(beta_binomial(24, 0, 0.05), binomial(24, 0))
        self.assertEqual(beta_binomial(0, 0.25, 0.05), (1.0,))


class PacketTests(unittest.TestCase):
    def test_casualty_partitions_and_zero_draws(self):
        for profile in PROFILES.values():
            for contribution in (0, 1, 24):
                for available in (0, 1, 23, 240):
                    percentile = lambda channel: math.nextafter(1.0, 0.0)
                    draw = percentile if contribution and available else unexpected_draw
                    result = casualties(contribution, available, profile, draw)
                    self.assertGreaterEqual(min(result.killed, result.wounded), 0)
                    self.assertLessEqual(result.killed + result.wounded, min(available, 24))

    def test_joint_percentile_is_shared(self):
        drawn = []

        def draw(channel):
            drawn.append(channel)
            return {"injury": 0.9, "fatal": 0.5, "couple": 0.0}[channel]

        packet = directed_packet(24, 240, False, PROFILES["J"], draw)
        self.assertEqual(drawn, ["injury", "fatal", "couple"])
        self.assertEqual((packet.cohesion, packet.morale), (1, 1))

    def test_routing_recipient_only_receives_physical_effects(self):
        def draw(channel):
            self.assertIn(channel, ("injury", "fatal"))
            return 0.9

        result = directed_packet(24, 240, True, PROFILES["J"], draw)
        self.assertGreater(result.casualties.killed + result.casualties.wounded, 0)
        self.assertEqual((result.cohesion, result.morale), (0, 0))


A, B, C = (0, 0), (1, 0), (2, 0)
X, Y, Z = (1, 1), (2, 1), (3, 1)


class DisplacementTests(unittest.TestCase):
    def check_case(self, occupancy, candidates, expected):
        frozen = frozenset(occupancy)
        result = arbitrate(frozen, dict(candidates))
        reversed_result = arbitrate(frozen, dict(reversed(candidates)))
        self.assertEqual(result, reversed_result)
        self.assertEqual(dict(result.assignments), expected)
        destinations = {cell for _, cell in result.assignments}
        self.assertEqual(len(destinations), len(result.assignments))
        self.assertTrue(destinations.isdisjoint(frozen))

    def test_dx01(self):
        self.check_case((A, B), [(1, (A,))], {})

    def test_dx02(self):
        self.check_case((A, B), [(1, (A, X))], {1: X})

    def test_dx03(self):
        self.check_case((A, B, C), [(1, (X, Y)), (2, (X, Z))], {1: Y, 2: Z})

    def test_dx04(self):
        self.check_case((A, B, C), [(1, (A, X)), (2, (X,))], {})

    def test_dx05(self):
        self.check_case((A, B, C), [(1, (C, X)), (2, (Y,))], {1: X, 2: Y})

    def test_dx06(self):
        self.check_case((A, B), [(0, (X,)), (1, (X,))], {})


class ManifestTests(unittest.TestCase):
    def test_counts_and_mirror_pairing(self):
        self.assertEqual((len(SCREENING), len(CONFIRMATION), len(POLICY), len(MIRROR)),
                         (1024, 2048, 512, 128))
        for a, b in MIRROR:
            self.assertFalse(a.mirrored)
            self.assertTrue(b.mirrored)
            self.assertEqual((a.profile, a.seed, a.policies), (b.profile, b.seed, b.policies))

    def test_holdout_boundaries(self):
        for seed in (10000, 14095, 30000, 31023):
            with self.subTest(seed=seed), self.assertRaisesRegex(ValueError, "reserved holdout"):
                Run("F6", seed, ("AGG", "AGG"))


class FrozenFieldTests(unittest.TestCase):
    def test_occupancy_and_threat_survive_live_changes(self):
        from imperium.displacement import FrozenField

        encounter = initial_encounter(PROFILES["F6"])
        router, hostile = encounter.formations[0], encounter.formations[6]
        router.position = (4, 4)
        router.disposition = "routing"
        hostile.position, hostile.facing, hostile.fatigue = (3, 3), 0, 2
        snapshot = FrozenField.capture(encounter)
        router.position = None
        hostile.position = (0, 0)
        ranked = ((4, 4), (4, 3), (3, 4), (2, 4), (11, 5))
        self.assertEqual(snapshot.destinations(0, ranked), ((2, 4),))


class ConditionTests(unittest.TestCase):
    def test_depletion_rout_and_repulse_precedence(self):
        from imperium.condition import assess

        self.assertEqual(assess(0, "organized", 1, 1, 1, 1, melee=True).transition, "depleted")
        self.assertEqual(assess(1, "organized", 1, 1, 1, 1, melee=True).transition, "rout")
        self.assertEqual(assess(1, "organized", 1, 0, 1, 0, melee=True).transition, "repulse")
        self.assertEqual(assess(1, "organized", 2, 0, 1, 0, melee=True).transition, "none")
        self.assertEqual(assess(1, "reforming", 2, 1, 0, 1, melee=False).transition, "rout")

    def test_actual_marks_and_remainder(self):
        from imperium.condition import exert

        self.assertEqual(exert(0, 5, 2, PROFILES["F6"]), (1, 1))
        self.assertEqual(exert(2, 5, 2, PROFILES["F6"]), (2, 1))
        self.assertEqual(exert(1, 1, 2, PROFILES["R0"]), (2, 0))
