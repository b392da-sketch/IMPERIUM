"""TA-P4-B01 to B04: directions, threat, exact line of sight, cost and cap.

B03 compares the engine's exact LOS with Codex's independent oracle
(``los_oracle.py``, pinned by digest) over all 9,801 ordered F01 pairs.
"""

import dataclasses
import importlib.util
import itertools
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.board import EdgeRule, entry_cost
from imperium.battle.engine import exertion, geometry
from imperium.battle.queries import Fields, recovery_safe_now, threat_sources
from imperium.battle.records import STATE_FIELDS
from imperium.battle.state import state_values
from imperium.battle.values import (
    DIRECTIONS, MovementMode, TemplateKind, front_directions, mirror_facing, mirror_hex,
    rear_directions,
)
from tests.movement.support import HERE, S1, cond, doc, f, fid, oracle_bytes, place, state_of

BOARD = frozenset(itertools.product(range(11), range(9)))


def load_oracle():
    oracle_bytes("los_oracle.py")
    spec = importlib.util.spec_from_file_location("p4_los_oracle", HERE / "los_oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fields_of(state):
    return Fields(**dict(zip(STATE_FIELDS, state_values(state))))


class B01Directions(unittest.TestCase):

    def test_pairs(self):
        self.assertEqual(DIRECTIONS, ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)))
        for facing in range(6):
            front = front_directions(facing)
            rear = rear_directions(facing)
            self.assertEqual(front, (facing, (facing + 1) % 6))
            self.assertEqual(rear, ((facing + 3) % 6, (facing + 4) % 6))
            side = set(range(6)) - set(front) - set(rear)
            self.assertEqual(side, {(facing + 2) % 6, (facing + 5) % 6})

    def test_half_turn(self):
        for q, r in BOARD:
            self.assertEqual(mirror_hex(B.Hex(q, r)), B.Hex(10 - q, 8 - r))
        for facing in range(6):
            self.assertEqual(mirror_facing(facing), (facing + 3) % 6)
            for d in range(6):
                # A direction rotates with the board; a signed turn is unchanged.
                vq, vr = DIRECTIONS[d]
                self.assertEqual(DIRECTIONS[(d + 3) % 6], (-vq, -vr))


class B02Threat(unittest.TestCase):

    def setUp(self):
        d = doc()
        place(d, "S1.L1", (9, 3))
        place(d, "S1.H4", (5, 3), facing=1)    # (5,4) at d1
        place(d, "S1.H3", (6, 3), facing=2)    # (5,4) at d2
        self.d = d

    def sources(self, d):
        return threat_sources(fields_of(state_of(d)), B.Hex(5, 4), S1)

    def test_two_sources_sorted(self):
        self.assertEqual(self.sources(self.d), (fid("S1.H3"), fid("S1.H4")))

    def test_toggles(self):
        for c, m, fat, kept in ((2, 0, 0, False), (0, 2, 0, False), (0, 0, 2, True),
                                (1, 1, 1, True)):
            d = cond(doc(), "S1.H4", c=c, m=m, fat=fat)
            for name, cell, facing in (("S1.L1", (9, 3), None), ("S1.H4", (5, 3), 1),
                                       ("S1.H3", (6, 3), 2)):
                place(d, name, cell, facing)
            got = self.sources(d)
            self.assertEqual(fid("S1.H4") in got, kept, (c, m, fat))
        d = dict(self.d)
        f(d, "S1.H4")["disposition"] = "REFORMING"
        self.assertEqual(self.sources(d), (fid("S1.H3"),))

    def test_directed_edge_seam(self):
        """A one-way closed edge removes the source in that direction only."""
        state = state_of(self.d)
        values = dict(zip(STATE_FIELDS, state_values(state)))
        board = values["scenario"].board
        closed = EdgeRule(B.Hex(5, 3), B.Hex(5, 4), False, False, 0)
        seam = dataclasses.replace(values["scenario"], board=dataclasses.replace(
            board, edges=(closed,)))
        values["scenario"] = seam
        fields = Fields(**values)
        self.assertEqual(threat_sources(fields, B.Hex(5, 4), S1), (fid("S1.H3"),))
        self.assertEqual(entry_cost(seam.board, B.Hex(5, 4), B.Hex(5, 3), TemplateKind.HEAVY), 1)

    def test_adjacent_but_not_threatening_is_unsafe(self):
        d = doc()
        place(d, "S0.H4", (5, 4), facing=4)
        place(d, "S1.L1", (9, 3))
        place(d, "S1.H4", (5, 3), facing=4)    # adjacent, facing away from S0.H4
        fields = fields_of(state_of(d))
        self.assertEqual(threat_sources(fields, B.Hex(5, 4), S1), ())
        self.assertFalse(recovery_safe_now(fields, fid("S0.H4")))


class B03LineOfSight(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.oracle = load_oracle()

    def test_all_ordered_pairs_against_oracle(self):
        census = {}
        pairs = 0
        for a, b in itertools.product(sorted(BOARD), repeat=2):
            pairs += 1
            delta = (b[0] - a[0], b[1] - a[1])
            if delta not in census:
                census[delta] = (geometry.intermediate_cells((0, 0), delta),
                                 self.oracle.intermediate((0, 0), delta))
            mine, theirs = census[delta]
            self.assertEqual(mine, theirs, (a, b))
        self.assertEqual(pairs, 9801)
        for (q, r), (forward, _) in census.items():
            backward = census[(-q, -r)][0]
            self.assertEqual(forward, frozenset((x + q, y + r) for x, y in backward))

    def test_self_and_symmetry(self):
        self.assertEqual(geometry.intermediate_cells((3, 3), (3, 3)), frozenset())
        self.assertTrue(geometry.sight_clear((3, 3), (3, 3), BOARD))
        for a, b in (((0, 0), (1, 6)), ((0, 1), (2, 0)), ((2, 2), (7, 5))):
            self.assertEqual(geometry.sight_clear(a, b, BOARD, {(1, 2)}),
                             geometry.sight_clear(b, a, BOARD, {(1, 2)}))

    def test_codex_witnesses(self):
        clear = geometry.sight_clear
        self.assertTrue(clear((0, 0), (1, 6), BOARD))
        self.assertFalse(clear((0, 0), (1, 6), BOARD, occupied={(0, 4)}))
        self.assertFalse(clear((1, 6), (0, 0), BOARD, occupied={(0, 4)}))
        # (0,0)->(2,-1) translated by (0,1): both shared-edge cells are intermediate.
        a, b = (0, 1), (2, 0)
        self.assertEqual(geometry.intermediate_cells(a, b), {(1, 1), (1, 0)})
        self.assertFalse(clear(a, b, BOARD, occupied={(1, 1)}))
        self.assertFalse(clear(a, b, BOARD, occupied={(1, 0)}))
        self.assertFalse(clear(a, b, BOARD, opaque_cells={(1, 0)}))
        self.assertFalse(clear(a, b, BOARD, opaque_edges=(((1, 1), (1, 0)),)))
        self.assertTrue(clear(a, b, BOARD, opaque_edges=(((0, 1), (1, 1)),)))   # vertex only
        # A true mid-edge crossing, in either stored direction.
        a, b = (1, 1), (3, 1)
        self.assertTrue(geometry.edge_blocks(a, b, (1, 1), (2, 1)))
        self.assertFalse(clear(a, b, BOARD, opaque_edges=(((2, 1), (1, 1)),)))
        self.assertFalse(clear(a, b, BOARD - {(2, 1)}))                       # masked cell
        self.assertTrue(clear(a, b, BOARD, occupied={a, b}))                  # endpoints
        self.assertFalse(clear((0, 0), (11, 0), BOARD))                      # off-board end

    def test_production_barrier_is_transparent(self):
        state = E.BattleSession.open(B.FixtureId("F01-v1-barrier-standard")).state
        fields = fields_of(state)
        self.assertTrue(any(not e.opaque for e in fields.scenario.board.edges))
        self.assertTrue(geometry.los_clear(fields, B.Hex(2, 4), B.Hex(5, 4)))
        self.assertTrue(geometry.los_clear(fields, B.Hex(6, 4), B.Hex(8, 4)))
        self.assertFalse(geometry.los_clear(fields, B.Hex(2, 4), B.Hex(11, 4)))


class B04CostAndCap(unittest.TestCase):

    def test_costs(self):
        rough = E.BattleSession.open(B.FixtureId("F01-v1-rough-standard")).state.scenario.board
        o, r = B.Hex(2, 5), B.Hex(2, 4)
        for kind, open_cost, rough_cost in ((TemplateKind.HEAVY, 1, 2),
                                            (TemplateKind.LIGHT, 1, 1),
                                            (TemplateKind.MOUNTED, 1, 3)):
            self.assertEqual(entry_cost(rough, o, B.Hex(3, 4), kind), open_cost)
            self.assertEqual(entry_cost(rough, o, r, kind), rough_cost)
        from imperium.battle.profile import movement_cost_kind
        mixed = movement_cost_kind(MovementMode.MIXED_FOOT, TemplateKind.MOUNTED)
        self.assertEqual(entry_cost(rough, o, r, mixed), 2)

    def test_caps(self):
        from imperium.battle.profile import step_cap
        self.assertEqual([step_cap(MovementMode.FOOT, TemplateKind.HEAVY),
                          step_cap(MovementMode.FOOT, TemplateKind.LIGHT),
                          step_cap(MovementMode.MOUNTED, TemplateKind.MOUNTED),
                          step_cap(MovementMode.MIXED_FOOT, TemplateKind.MOUNTED)], [2, 2, 3, 2])
        c = B.Condition(0, 0, 0, 0)
        self.assertEqual(exertion.cap_for(c, 3), 3)
        self.assertEqual(exertion.cap_for(dataclasses.replace(c, cohesion=2), 3), 1)
        self.assertEqual(exertion.cap_for(dataclasses.replace(c, fatigue=2), 3), 1)
        self.assertEqual(exertion.cap_for(dataclasses.replace(c, morale=2), 3), 3)


if __name__ == "__main__":
    unittest.main()
