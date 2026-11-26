"""14.7 contacts and placement (AT-K01–K07, K02b/K04b/K05a)."""

import imperium.battle as B
from imperium.battle.board import statically_traversable
from tests.battle.common import BattleCase, a1, cond, f, individual, place
from tests.battle.test_work import routing, uses

F = B.FormationId


def k01(variant="OPEN", label="K"):
    d = a1(variant, label)
    place(d, "S0.H1", (3, 4), 4)
    place(d, "S1.H1", (4, 4), 0)
    f(d, "S1.H1")["disposition"] = "REFORMING"
    cond(d, "S0.H1", fat=2, e=5)
    d["contacts"] = [{"low": "S0.H1", "high": "S1.H1", "edge": [[3, 4], [4, 4]]}]
    return d


class ContactTests(BattleCase):
    def test_at_k01(self):
        d = k01()
        d["contacts"][0]["high"] = "S0.H2"
        self.reject(d, "K01")
        d = k01()
        d["contacts"][0].update(low="S1.H1", high="S0.H1", edge=[[4, 4], [3, 4]])
        self.reject(d, "K01")

    def test_at_k02(self):
        self.reject(routing(k01(), "S1.H1"), "K02")

    def test_at_k03_x_k01_k02b_k04b(self):
        s = self.accept(k01())
        self.assertEqual(len(B.contacts_of(s, F("S0.H1"))), 1)
        self.assertEqual(B.contacts_of(s, F("S0.H2")), ())

    def test_at_k04_k05(self):
        d = k01()
        place(d, "S1.H1", (5, 4))
        d["contacts"][0]["edge"] = [[3, 4], [5, 4]]
        self.reject(d, "K03")
        d = k01()
        d["contacts"][0]["edge"] = [[3, 4], [4, 3]]
        self.reject(d, "K03")
        self.reject(k01("BARRIER"), "K04")

    def test_k05a(self):
        d = k01("OPEN", "K05A")
        place(d, "S0.H1", (3, 4), 1)
        cond(d, "S0.H1", 2, 1, 2, 5)
        place(d, "S1.H2", (3, 3), 4)
        d["contacts"].append({"low": "S0.H1", "high": "S1.H2", "edge": [[3, 4], [3, 3]]})
        uses(d, [individual("S0", "S0.H1", {"kind": "Hold"})], "S1")
        s = self.accept(d)
        self.assertEqual(len(B.contacts_of(s, F("S0.H1"))), 2)
        self.assertIs(B.activation(s, F("S0.H1")), B.Activation.SPENT)

    def test_at_k06(self):
        d = k01()
        d["contacts"].append(dict(d["contacts"][0]))
        self.decode_code(d, "NONCANONICAL", "/contacts")
        s = self.accept(k01())
        with self.assertRaises(B.InvalidValue) as cm:
            s.evolve(contacts=s.contacts * 2)
        self.assertEqual(cm.exception.clause, "T05")

    def test_at_k07(self):
        self.reject(place(a1(), "S0.H2", (2, 6)), "F02")

    def test_one_way_edge_predicate(self):
        """K04's one-way case on a test-only board record (14.7 note)."""
        base = B.f01_board(B.Variant.OPEN)
        a, b = B.Hex(3, 4), B.Hex(4, 4)
        rule = B.EdgeRule(a, b, False, False, 0)
        board = B.Board(base.width, base.height, base.terrain, (rule,), base.objective)
        self.assertFalse(statically_traversable(board, a, b))
        self.assertTrue(statically_traversable(board, b, a))
        self.assertTrue(statically_traversable(board, a, b) or statically_traversable(board, b, a))
        self.assertIsNone(B.entry_cost(board, a, b, B.TemplateKind.HEAVY))
        self.assertEqual(B.entry_cost(board, b, a, B.TemplateKind.HEAVY), 1)
