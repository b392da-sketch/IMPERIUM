"""TA-F01–F04: BattleSession, the read-only state and the full-digest journal (P2-F)."""

import unittest
from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
from imperium.battle.engine import session as session_module
from tests.engine.helpers import REGISTERED, S0, S1, STANDARD, EngineCase, hold

HOLD_DIGEST = "778e99ec9130365fc0942132dd923346ffd8370e9196eb73497b2cac7d96ff74"
OPEN_DIGEST = "aecf280c32c3cc154e1699e3274260179f64bff8bc60f641f58fc587834415e4"
CAP_S1_DIGEST = "0d3a0f09585968ca6ddee26fc0c8f6a726af7161774720db3403e30bc162025d"


def check_journal(journal, genesis_full, final_state):
    """The F03 oracle: cursors, chain from F, and current equal to the final digest."""
    previous = genesis_full
    for entry in journal:
        if entry.previous != previous:
            return False
        previous = entry.current
    return previous == B.digest(final_state)


class Session(EngineCase):

    def test_f01_open(self):
        for fixture_id in REGISTERED:
            with self.subTest(fixture=fixture_id.token):
                s = E.BattleSession.open(fixture_id)
                self.assertEqual(B.digest(s.state), B.descriptor(fixture_id).full_genesis_digest)
                self.assertEqual(s.journal, ())
        for bad in (B.FixtureId("ADV-A1"), B.FixtureId("F01-v9-unknown")):
            with self.assertRaises(B.UnknownId):
                E.BattleSession.open(bad)
        with self.assertRaises(B.InvalidValue) as cm:
            E.BattleSession.open("F01-v1-open-standard")
        self.assertEqual(cm.exception.clause, "T07")

    def test_f02_read_only(self):
        s = E.BattleSession.open(STANDARD)
        with self.assertRaises(AttributeError):
            s.state = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        with self.assertRaises(AttributeError):
            del s.state
        with self.assertRaises(AttributeError):
            s.extra = 1
        with self.assertRaises(AttributeError):
            s._state = None
        with self.assertRaises(AttributeError):
            s.journal = ()
        with self.assertRaises(TypeError):
            E.BattleSession()
        with self.assertRaises(TypeError):
            E.BattleSession(B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD))

    def test_f03_chain(self):
        s = E.BattleSession.open(STANDARD)
        F = B.descriptor(STANDARD).full_genesis_digest
        self.assertIs(type(s.submit(E.OpenBattle())), E.Accepted)
        self.assertIs(type(s.submit(E.PassOrder(S1))), E.Rejected)
        self.assertEqual(len(s.journal), 1)
        self.assertIs(type(s.submit(hold(S0, "S0.H1"))), E.Accepted)
        self.assertIs(type(s.submit(E.Capitulate(S1))), E.Accepted)
        j = s.journal
        self.assertEqual([e.cursor for e in j], [1, 2, 3])
        self.assertEqual([e.command_digest for e in j], [OPEN_DIGEST, HOLD_DIGEST, CAP_S1_DIGEST])
        self.assertEqual(j[0].previous, F)
        self.assertEqual(j[1].previous, j[0].current)
        self.assertEqual(j[2].previous, j[1].current)
        self.assertEqual(j[2].current, B.digest(s.state))
        self.assertTrue(check_journal(j, F, s.state))
        with self.assertRaises(B.InvalidValue):
            s.submit("PASS")
        self.assertEqual(s.journal, j)

    def test_f03_technical_error_atomic(self):
        s = E.BattleSession.open(STANDARD)
        s.submit(E.OpenBattle())
        state, journal = s.state, s.journal
        with mock.patch.object(session_module, "resolve", side_effect=B.InvalidValue("T10", "x", "y")):
            with self.assertRaises(B.InvalidValue):
                s.submit(hold(S0, "S0.H1"))
        self.assertIs(s.state, state)
        self.assertEqual(s.journal, journal)

    def test_f03_deferred_dispatch_stub(self):
        """Dispatch test only: a test-local transition stub returning Deferred."""
        s = E.BattleSession.open(STANDARD)
        s.submit(E.OpenBattle())
        state, journal = s.state, s.journal
        c = E.PassOrder(S0)
        stub = lambda st, cmd: E.Deferred(st, cmd, E.Stage.RECOVERY, ("DO-P2-02",))
        with mock.patch.object(session_module, "resolve", side_effect=stub):
            r = s.submit(c)
        self.assertIs(type(r), E.Deferred)
        self.assertIs(s.state, state)
        self.assertEqual(s.journal, journal)

    def test_f04_normalized_predecessor_mutant(self):
        s = E.BattleSession.open(STANDARD)
        s.submit(E.OpenBattle())
        d = B.descriptor(STANDARD)
        j = s.journal
        self.assertTrue(check_journal(j, d.full_genesis_digest, s.state))
        mutated = (E.JournalEntry(j[0].cursor, j[0].command_digest, d.normalized_genesis_digest,
                                  j[0].current),)
        self.assertNotEqual(d.normalized_genesis_digest, d.full_genesis_digest)
        self.assertFalse(check_journal(mutated, d.full_genesis_digest, s.state))
        self.assertEqual(j[0].previous, d.full_genesis_digest)
