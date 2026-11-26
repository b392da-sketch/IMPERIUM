"""14.10 construction utilities and the restored I and V rows (14.11)."""

import copy
import dataclasses
from fractions import Fraction

import imperium.battle as B
from tests.battle.common import BattleCase, a1
from tests.battle.scenarios import capitulation, collapse
from tests.support.battle_builder import as_adversarial, build, opening_document

R = dataclasses.replace
F = B.FormationId
OPEN = opening_document()
STATE = build(OPEN)
FORMATION = STATE.formations[0]
LOT = STATE.personnel[0]
ROSTER0 = STATE.scenario.roster[0]
DEFENSIVE = B.FixtureId("F01-v1-defensive-mutual-capitulation")


def walk(value, seen):
    """Every record and container reachable from a state value."""
    yield value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            yield from walk(getattr(value, field.name), seen)
    elif type(value) is tuple:
        for item in value:
            yield from walk(item, seen)


class ConstructionTests(BattleCase):
    def clause(self, call, clause):
        with self.assertRaises(B.InvalidValue) as cm:
            call()
        self.assertEqual(cm.exception.clause, clause, msg=str(cm.exception))
        return cm.exception

    def test_i01_i02_i10(self):
        states = [STATE, build(a1()), build(collapse()), build(capitulation()), B.f01_supplied(DEFENSIVE)]
        for s in states:
            for node in walk(s, set()):
                self.assertNotIn(type(node), (list, dict, set, bytearray))
                if dataclasses.is_dataclass(node):
                    self.assertTrue(type(node).__dataclass_params__.frozen, type(node))
        for s in states:
            for target, name in ((s, "formations"), (s.formations[0], "facing"),
                                 (s.clock, "completed_rounds")):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(target, name, 1)
        defensive = states[-1]
        for node in walk(defensive, set()):
            if dataclasses.is_dataclass(node):
                for field in dataclasses.fields(node):
                    with self.assertRaises(dataclasses.FrozenInstanceError):
                        setattr(node, field.name, None)
        self.assertEqual(B.validate_state(defensive), ())

    def test_i03(self):
        use = B.OpportunityUse(B.Side.S0, B.UseKind.INDIVIDUAL, None, (F("S0.H1"),), (B.Hold(),))
        e = self.clause(lambda: R(use, members=("S0.H1",)), "T07")
        self.assertIn("members", e.path)
        self.clause(lambda: R(use, members=[F("S0.H1")]), "T04")
        ledger = build(a1()).ledger
        self.clause(lambda: R(ledger, uses=[]), "T04")
        group = STATE.scenario.groups[0]
        self.clause(lambda: R(group, members=list(group.members)), "T04")
        board = STATE.scenario.board
        self.clause(lambda: R(board, edges={}), "T04")

    def test_i05_i06_i07(self):
        d = copy.deepcopy(OPEN)
        s = build(d)
        d["formations"][0]["facing"] = 1
        self.assertEqual(B.encode_state(s), OPEN)
        self.assertEqual(copy.copy(s), s)
        self.assertEqual(copy.deepcopy(s), s)
        same = s.evolve(clock=s.clock)
        self.assertEqual(same, s)
        self.assertEqual(hash(same), hash(s))
        with self.assertRaises(B.InvalidState) as cm:
            s.evolve(clock=B.Clock(5, 0))
        self.assertIn("H01", [v.clause for v in cm.exception.violations])
        if hasattr(copy, "replace"):
            self.assertEqual(copy.replace(s), s)
        other = B.f01_opening(B.Variant.ROUGH, B.Orientation.STANDARD)
        for a, b in ((s, s), (s, other), (s, build(copy.deepcopy(OPEN)))):
            self.assertEqual(a == b, B.canonical_bytes(a) == B.canonical_bytes(b))
            if a == b:
                self.assertEqual(hash(a), hash(b))

    def test_at_r02_i08(self):
        s = build(as_adversarial(OPEN, "R02"))
        before = B.canonical_bytes(s)
        swapped = (s.formations[1], s.formations[0]) + s.formations[2:]
        with self.assertRaises(B.InvalidState) as cm:
            s.evolve(formations=swapped)
        self.assertIn("F01", [v.clause for v in cm.exception.violations])
        self.assertEqual(B.canonical_bytes(s), before)

    def test_i09(self):
        s = build(OPEN)
        object.__setattr__(s.formations[0], "facing", 9)
        self.assertIn("T08", [v.clause for v in B.validate_state(s)])

    def test_v01_v03(self):
        self.clause(lambda: R(ROSTER0, side=5), "T03")
        for value, code in ((5, "JSON_TYPE"), ("S5", "TOKEN")):
            d = copy.deepcopy(OPEN)
            d["scenario"]["roster"][0]["side"] = value
            self.decode_code(d, code)
        self.clause(lambda: R(FORMATION, disposition="banana"), "T03")
        d = copy.deepcopy(OPEN)
        d["formations"][0]["disposition"] = "banana"
        self.decode_code(d, "TOKEN", "/formations/0/disposition")
        self.clause(lambda: R(FORMATION, disposition="ORGANIZED"), "T03")
        self.clause(lambda: R(FORMATION, disposition=B.Posture.CONTESTING), "T03")

    def test_v04_v07(self):
        for facing in (9, -1, 6):
            self.clause(lambda: R(FORMATION, facing=facing), "T08")
            d = copy.deepcopy(OPEN)
            d["formations"][0]["facing"] = facing
            e = self.decode_code(d, "CLAUSE", "/formations/0/facing")
            self.assertEqual(e.violations[0].clause, "T08")
        for facing in (0, 5):
            R(FORMATION, facing=facing)
        self.clause(lambda: R(FORMATION, facing=True), "T01")
        self.clause(lambda: R(FORMATION, facing=4.0), "T01")
        d = copy.deepcopy(OPEN)
        d["formations"][0]["facing"] = True
        self.decode_code(d, "JSON_TYPE", "/formations/0/facing")
        c = FORMATION.condition
        self.clause(lambda: R(c, cohesion=True), "T01")
        self.clause(lambda: R(c, morale=False), "T01")
        self.clause(lambda: R(c, fatigue=1.0), "T01")
        self.clause(lambda: R(c, exertion=Fraction(1)), "T01")

        class Sub(int):
            pass

        self.clause(lambda: R(LOT, count="240"), "T01")
        self.clause(lambda: R(LOT, count=Sub(240)), "T01")
        self.clause(lambda: R(LOT, count=F("S0.H1")), "T01")

    def test_v08_v09(self):
        c = FORMATION.condition
        for name in ("cohesion", "morale", "fatigue"):
            for bad in (3, -1):
                self.clause(lambda: R(c, **{name: bad}), "T09")
            for ok in (0, 2):
                R(c, **{name: ok})
        for bad in (0, -1):
            self.clause(lambda: R(LOT, count=bad), "T10")
        R(LOT, count=1)

    def test_v10(self):
        for token in ("", "é", "a" * 65, 3):
            self.clause(lambda: F(token), "T07")
        F("a" * 64)
        self.clause(lambda: R(FORMATION, formation=B.GroupId("S0.G1")), "T07")

    def test_v12(self):
        s = build(OPEN)
        lots = s.personnel
        self.clause(lambda: s.evolve(personnel=(lots[1], lots[0]) + lots[2:]), "T05")
        self.clause(lambda: s.evolve(personnel=(lots[0],) + lots), "T05")
        d = copy.deepcopy(OPEN)
        d["personnel"].insert(0, copy.deepcopy(d["personnel"][0]))
        self.decode_code(d, "NONCANONICAL", "/personnel")

    def test_v13(self):
        packet = STATE.scenario.profile.packet
        self.clause(lambda: R(packet, melee_p0=0.1), "T06")
        d = copy.deepcopy(OPEN)
        d["scenario"]["profile"]["packet"]["melee_p0"] = 0.1
        self.decode_code(d, "NOT_INTEGER", "/scenario/profile/packet/melee_p0")

    def test_v14_v15(self):
        G = B.UseKind.GROUP
        steps = (B.GroupPivot(4, 1),)
        h = (F("S0.H1"), F("S0.H2"), F("S0.H3"), F("S0.H5"))
        for n, ok in ((1, False), (2, True), (3, True), (4, False)):
            call = (lambda n=n: B.OpportunityUse(B.Side.S0, G, B.GroupId("S0.G1"), h[:n], steps * n))
            call() if ok else self.clause(call, "T12")
        self.clause(lambda: B.OpportunityUse(B.Side.S0, B.UseKind.PASS, None, h[:1], (B.Hold(),)), "T12")
        self.clause(lambda: B.OpportunityUse(B.Side.S0, B.UseKind.INDIVIDUAL, None, h[:2],
                                             (B.Hold(), B.Hold())), "T12")
        self.clause(lambda: B.OpportunityUse(B.Side.S0, B.UseKind.INDIVIDUAL, None, h[:1], ()), "T12")

    def test_v16_v17(self):
        S = B.PersonnelStatus
        self.clause(lambda: R(LOT, status=S.CAPTURED, captured=None), "T13")
        self.clause(lambda: R(LOT, captured=B.CapturedCondition.FIT), "T13")
        self.clause(lambda: R(LOT, status=S.DEAD, place=B.OnCell(B.Hex(1, 6)),
                              origin=B.EventRef("EV-1")), "T13")
        record = build(collapse()).phase.record
        self.clause(lambda: R(record, result=B.ResultKind.DRAW, winner=B.Side.S0), "T14")

    def test_v18_domain_errors_only(self):
        bad_values = (None, [], {}, object(), [[1]], 2 ** 80, "x", 1.5, True, B.Hex(0, 0))
        records = [FORMATION, LOT, ROSTER0, STATE.clock, STATE.formations[0].condition,
                   STATE.mounts[0], STATE.ammunition[0], STATE.scenario.board, STATE.scenario.profile]
        for rec in records:
            for field in dataclasses.fields(rec):
                for value in bad_values:
                    if getattr(rec, field.name) == value:
                        continue
                    try:
                        R(rec, **{field.name: value})
                    except B.DomainError:
                        pass
        fid = F("S0.H1")
        for value in bad_values:
            for fn in (B.available, B.activation, B.movement_mode, B.charge):
                args = (STATE, value) if fn is not B.charge else (STATE, fid, value)
                with self.assertRaises(B.DomainError):
                    fn(*args)
            for args in ((value,), ([value],), ({"schema": B.SCHEMA, "x": value},)):
                try:
                    B.decode_state(*args)
                except B.DomainError:
                    pass
        with self.assertRaises(TypeError):
            B.available(STATE)
        with self.assertRaises(TypeError):
            B.available(STATE, fid, bogus=1)

    def test_at_r01(self):
        d = as_adversarial(OPEN, "R01")
        d["formations"][1]["condition"]["fatigue"] = 2
        self.accept(d)
        d = copy.deepcopy(OPEN)
        d["formations"][1]["condition"]["fatigue"] = 2
        self.reject(d, "P10")
