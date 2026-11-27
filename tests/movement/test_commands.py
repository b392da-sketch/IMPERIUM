"""TA-P4-A01 to A03: exact-type constructors, canonical bodies and BAD_VALUE."""

import unittest

import imperium.battle as B
from imperium.battle import engine as E
from tests.movement.support import (
    S0, S1, MovementCase, cjson, doc, fid, gid, hx, mv, rejection_oracles, state_of,
)

TOKEN = "a" * 64


class MyInt(int):
    pass


class MyStr(str):
    pass


class A01Types(unittest.TestCase):

    def t15(self, path, fn):
        with self.assertRaises(B.InvalidValue) as cm:
            fn()
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", path))

    def test_principal_field_types(self):
        F, H = fid("S0.H1"), hx(2, 5)
        self.t15("side", lambda: E.MoveOrder("S0", F, (H,)))
        self.t15("formation", lambda: E.MoveOrder(S0, "S0.H1", (H,)))
        self.t15("formation", lambda: E.MoveOrder(S0, gid("S0.H1"), (H,)))
        self.t15("path", lambda: E.MoveOrder(S0, F, [H]))
        self.t15("path/1", lambda: E.MoveOrder(S0, F, (H, (2, 4))))
        self.t15("turn", lambda: E.PivotOrder(S0, F, True, 1))
        self.t15("turn", lambda: E.PivotOrder(S0, F, MyInt(1), 1))
        self.t15("steps", lambda: E.PivotOrder(S0, F, 1, 1.0))
        self.t15("destination", lambda: E.WithdrawOrder(S0, F, (2, 7)))
        self.t15("formation", lambda: E.EvacuateOrder(S0, None))
        self.t15("group", lambda: E.GroupMoveOrder(S0, F, (F,), 4))
        self.t15("members", lambda: E.GroupMoveOrder(S0, gid("S0.G1"), [F], 4))
        self.t15("members/1", lambda: E.GroupMoveOrder(S0, gid("S0.G1"), (F, "S0.H2"), 4))
        self.t15("direction", lambda: E.GroupMoveOrder(S0, gid("S0.G1"), (F,), False))
        self.t15("turn", lambda: E.GroupPivotOrder(S0, gid("S0.G1"), (F,), MyInt(-1)))

    def test_decision_field_types(self):
        F = fid("S1.H4")
        self.t15("window_id", lambda: E.DeclineResponse(S1, TOKEN.encode()))
        self.t15("window_id", lambda: E.DeclineResponse(S1, MyStr(TOKEN)))
        self.t15("side", lambda: E.RespondPivot(1, TOKEN, F, F))
        self.t15("target", lambda: E.RespondMissile(S1, TOKEN, F, "S0.L1"))
        # A malformed but exact str is constructible; admission gives BAD_VALUE.
        self.assertEqual(E.DeclineResponse(S1, "x").window_id, "x")

    def test_old_v00_precedence(self):
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(object(), object())
        self.assertEqual((cm.exception.clause, cm.exception.path), ("V00", "state"))
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(state_of(doc()), object())
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))


BODIES = (
    (E.MoveOrder(S0, fid("S0.L1"), (hx(4, 4), hx(4, 3))),
     {"schema": "imperium.battle-command/1", "kind": "MoveOrder", "side": "S0",
      "formation": "S0.L1", "path": [[4, 4], [4, 3]]}),
    (E.PivotOrder(S1, fid("S1.H4"), -1, 1),
     {"schema": "imperium.battle-command/1", "kind": "PivotOrder", "side": "S1",
      "formation": "S1.H4", "turn": -1, "steps": 1}),
    (E.WithdrawOrder(S0, fid("S0.H1"), hx(2, 7)),
     {"schema": "imperium.battle-command/1", "kind": "WithdrawOrder", "side": "S0",
      "formation": "S0.H1", "destination": [2, 7]}),
    (E.EvacuateOrder(S0, fid("S0.H5")),
     {"schema": "imperium.battle-command/1", "kind": "EvacuateOrder", "side": "S0",
      "formation": "S0.H5"}),
    (E.GroupMoveOrder(S0, gid("S0.G1"), (fid("S0.H1"), fid("S0.H2"), fid("S0.H5")), 4),
     {"schema": "imperium.battle-command/1", "kind": "GroupMoveOrder", "side": "S0",
      "group": "S0.G1", "members": ["S0.H1", "S0.H2", "S0.H5"], "direction": 4}),
    (E.GroupPivotOrder(S1, gid("S1.G2"), (fid("S1.H3"), fid("S1.H4"), fid("S1.H6")), 1),
     {"schema": "imperium.battle-command/1", "kind": "GroupPivotOrder", "side": "S1",
      "group": "S1.G2", "members": ["S1.H3", "S1.H4", "S1.H6"], "turn": 1}),
    (E.RespondPivot(S1, TOKEN, fid("S1.H4"), fid("S0.L1")),
     {"schema": "imperium.battle-command/1", "kind": "RespondPivot", "side": "S1",
      "window_id": TOKEN, "formation": "S1.H4", "target": "S0.L1"}),
    (E.RespondMissile(S1, TOKEN, fid("S1.L1"), fid("S0.L1")),
     {"schema": "imperium.battle-command/1", "kind": "RespondMissile", "side": "S1",
      "window_id": TOKEN, "formation": "S1.L1", "target": "S0.L1"}),
    (E.DeclineResponse(S1, TOKEN),
     {"schema": "imperium.battle-command/1", "kind": "DeclineResponse", "side": "S1",
      "window_id": TOKEN}),
)


class A02Bodies(unittest.TestCase):

    def test_nine_bodies_round_trip(self):
        for command, body in BODIES:
            with self.subTest(kind=body["kind"]):
                self.assertEqual(E.encode_command(command), body)
                data = cjson(body)
                self.assertEqual(E.command_bytes(command), data)
                self.assertEqual(E.decode_command(data), command)

    def bad(self, data):
        with self.assertRaises(B.InvalidValue) as cm:
            E.decode_command(data)
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))

    def test_decoder_rejections(self):
        move = dict(BODIES[0][1])
        self.bad(cjson(dict(move, extra=1)))
        self.bad(cjson(dict(move, path={"q": 4, "r": 4})))
        self.bad(cjson(dict(move, path=[[4, 4, 0]])))
        self.bad(cjson(dict(move, path=[[True, 4]])))
        self.bad(cjson(dict(move, formation="!bad")))
        self.bad(cjson(dict(move, formation=7)))
        self.bad(cjson(dict(move, schema="imperium.battle-command/2")))
        self.bad(cjson(dict(BODIES[6][1], window_id="A" * 64)))
        self.bad(cjson(dict(BODIES[6][1], window_id="abc")))
        self.bad(cjson(dict(BODIES[1][1], turn=True)))
        self.bad(cjson(move).replace(b"[4,4]", b"[4.0,4]"))
        self.bad(cjson(move).replace(b",", b", ", 1))
        self.bad(cjson(dict(move, path=[[0, 0]] * 200)))
        long = cjson(dict(move, path=[[0, 0]] * 50))
        self.assertGreater(len(long), 0)
        padded = cjson(dict(BODIES[3][1], formation="S" + "0" * 63))
        self.assertLessEqual(len(padded), 1024)
        filler = b" " * (1025 - len(cjson(BODIES[3][1])))
        self.bad(cjson(BODIES[3][1]) + filler)

    def test_old_bodies_unchanged(self):
        for command, body in (
            (E.OpenBattle(), {"schema": "imperium.battle-command/1", "kind": "OpenBattle"}),
            (E.HoldOrder(S0, fid("S0.H1")), {"schema": "imperium.battle-command/1",
                                             "kind": "HoldOrder", "side": "S0",
                                             "formation": "S0.H1"}),
            (E.PassOrder(S1), {"schema": "imperium.battle-command/1", "kind": "PassOrder",
                               "side": "S1"}),
        ):
            self.assertEqual(E.command_bytes(command), cjson(body))

    def test_rule_invalid_bodies_decode(self):
        group = dict(BODIES[4][1], members=["S0.H5", "S0.H1"])
        command = E.decode_command(cjson(group))
        self.assertEqual(command.members, (fid("S0.H5"), fid("S0.H1")))
        for path in ([], [[2, 5]] * 4):
            self.assertEqual(len(E.decode_command(cjson(dict(BODIES[0][1], path=path))).path),
                             len(path))
        self.assertEqual(E.decode_command(cjson(dict(BODIES[1][1], turn=0))).turn, 0)


class A03BadValue(MovementCase):

    def setUp(self):
        self.state = state_of(doc())
        self.detail = rejection_oracles()["BAD_VALUE"]["detail"]
        self.assertEqual(self.detail, "invalid command value")

    def bad(self, command, path):
        self.rejected(self.state, command, E.RejectCode.BAD_VALUE, path, self.detail)

    def test_ranges(self):
        F = fid("S0.H4")
        self.bad(E.PivotOrder(S0, F, 0, 0), "/turn")
        self.bad(E.PivotOrder(S0, F, 1, 0), "/steps")
        self.bad(E.PivotOrder(S0, F, -1, 4), "/steps")
        g = gid("S0.G1")
        h1, h2, h5 = fid("S0.H1"), fid("S0.H2"), fid("S0.H5")
        self.bad(E.GroupMoveOrder(S0, g, (h5, h1), 6), "/direction")
        self.bad(E.GroupMoveOrder(S0, g, (h5, h1), 4), "/members")
        self.bad(E.GroupMoveOrder(S0, g, (h1, h1), 4), "/members")
        self.bad(E.GroupMoveOrder(S0, g, (h1,), 4), "/members")
        self.bad(E.GroupMoveOrder(S0, g, (h1, h2, h5, fid("S0.H3")), 4), "/members")
        self.bad(E.GroupPivotOrder(S0, g, (h5, h1), 2), "/turn")
        self.bad(E.GroupPivotOrder(S0, g, (h2, h1), 1), "/members")
        self.bad(mv("S0.H4"), "/path")
        self.bad(mv("S0.H4", (5, 5), (5, 4), (5, 3), (5, 2)), "/path")

    def test_window_token_shape(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        s.submit(E.OpenBattle())
        r = s.submit(E.DeclineResponse(S0, "x"))
        self.assertIs(type(r), E.Rejected)
        self.assertEqual((r.code, r.path), (E.RejectCode.PHASE, ""))


if __name__ == "__main__":
    unittest.main()
