"""TA-P4-K01 and E02: pending custody, publication, rollback and exports."""

import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.engine import session as session_module
from tests.movement.support import S0, S1, carriers, cjson, fid, run_carrier, window_hash


def decode(tree):
    return E.decode_command(cjson(tree))


def g7():
    s = run_carrier("G7", upto=6)
    row = carriers()["G7"]["roots"][6]
    return s, decode(row["command"]), decode(row["decision"])


class K01Pending(unittest.TestCase):

    def test_identity_while_pending(self):
        s, command, decision = g7()
        state, journal = s.state, s.journal
        sealed, prefix = s.export_audit(), s.export_audit(seal=False)
        r = s.submit(command)
        self.assertIs(type(r), E.Suspended)
        root = s.pending
        self.assertIs(root, r.root)
        for attempt in (E.HoldOrder(S1, fid("S1.H1")), E.DeclineResponse(S0, root.window.window_id),
                        E.DeclineResponse(S1, "0" * 64),
                        E.RespondPivot(S1, root.window.window_id, fid("S1.H3"), fid("S0.L1"))):
            out = s.submit(attempt)
            self.assertIs(type(out), E.WindowRejected)
            self.assertIs(s.pending, root)
            self.assertIs(s.state, state)
            self.assertIs(s.journal, journal)
            self.assertEqual(s.export_audit(), sealed)
            self.assertEqual(s.export_audit(seal=False), prefix)
        self.assertIn(b'"schema":"imperium.battle-audit/2"', sealed.split(b"\n")[0])
        out = s.submit(decision)
        self.assertIs(type(out), E.Accepted)
        self.assertIsNone(s.pending)
        self.assertEqual(len(s.journal), len(journal) + 1)
        self.assertEqual(s.journal[:-1], journal)
        self.assertEqual(s.journal[-1].previous, B.digest(state))
        self.assertEqual(s.journal[-1].current, B.digest(s.state))
        self.assertEqual(s.state.clock.event_cursor, state.clock.event_cursor + 1)
        # Pure resolution of the immutable root is reproducible.
        self.assertEqual(B.digest(E.step(root, decision).state), B.digest(s.state))

    def test_v1_while_only_old_roots_completed(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        s.submit(E.OpenBattle())
        before = s.export_audit()
        self.assertIn(b'"schema":"imperium.battle-audit/1"', before.split(b"\n")[0])
        r = s.submit(decode(carriers()["G6"]["roots"][1]["command"]))
        self.assertIs(type(r), E.Accepted)
        upgraded = s.export_audit()
        self.assertIn(b'"schema":"imperium.battle-audit/2"', upgraded.split(b"\n")[0])

    def test_pending_v1_export_unchanged(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        s.submit(E.OpenBattle())
        v1 = s.export_audit()
        r = s.submit(E.MoveOrder(S0, fid("S0.L1"), (B.Hex(5, 4),)))
        self.assertIs(type(r), E.Suspended)
        self.assertEqual(s.export_audit(), v1)
        out = s.submit(E.RespondMissile(S1, r.root.window.window_id, fid("S1.L1"), fid("S0.L1")))
        self.assertIs(type(out), E.WindowDeferred)
        self.assertEqual(s.export_audit(), v1)

    def test_rollback_before_install(self):
        s, command, decision = g7()
        state, journal = s.state, s.journal
        s.submit(command)
        root = s.pending
        with mock.patch.object(session_module, "JournalEntry", side_effect=RuntimeError("seam")):
            with self.assertRaises(RuntimeError):
                s.submit(decision)
        self.assertIs(s.state, state)
        self.assertIs(s.journal, journal)
        self.assertIs(s.pending, root)
        self.assertIs(type(s.submit(decision)), E.Accepted)

    def test_stale_after_consumption_new_window(self):
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        s.submit(E.OpenBattle())
        r = s.submit(E.MoveOrder(S0, fid("S0.L1"), (B.Hex(5, 4),)))
        old = r.root.window.window_id
        s.submit(E.DeclineResponse(S1, old))
        out = s.submit(E.DeclineResponse(S1, old))
        self.assertIs(type(out), E.Rejected)
        self.assertEqual((out.code, out.path), (E.RejectCode.PHASE, ""))
        s.submit(E.HoldOrder(S1, fid("S1.H1")))
        r2 = s.submit(E.MoveOrder(S0, fid("S0.H4"), (B.Hex(6, 5),)))
        self.assertIs(type(r2), E.Suspended)
        out = s.submit(E.DeclineResponse(S1, old))
        self.assertIs(type(out), E.WindowRejected)
        self.assertEqual((out.code, out.path), (E.RejectCode.STALE_WINDOW, "/window_id"))
        self.assertNotEqual(r2.root.window.window_id, old)
        self.assertEqual(r2.root.window.window_id,
                         window_hash(B.digest(s.state), r2.root.command, r2.root.window.after))

    def test_single_dispatch(self):
        s, command, decision = g7()
        calls = []
        real = session_module.resolve

        def counting(*args):
            calls.append(args)
            return real(*args)

        with mock.patch.object(session_module, "resolve", counting):
            s.submit(command)
            s.submit(decision)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
