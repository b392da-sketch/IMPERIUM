"""TA-A01–A06: the command boundary, records, encoding and cursor bound."""

import dataclasses
import hashlib
import json
import pathlib

import imperium.battle as B
from imperium.battle import engine as E
from tests.engine.helpers import (
    DEFENSIVE, MAX, PHASE_DETAIL, S0, S1, EngineCase, awaiting, build, fid, hold, make_router,
    opened, pass_use,
)

# Independent command vectors (Codex, review-rev0.1/proposed-command-vectors.json).
VECTORS = {
    "OpenBattle": ('{"kind":"OpenBattle","schema":"imperium.battle-command/1"}',
                   "aecf280c32c3cc154e1699e3274260179f64bff8bc60f641f58fc587834415e4"),
    "HoldOrder": ('{"formation":"S0.H1","kind":"HoldOrder","schema":"imperium.battle-command/1","side":"S0"}',
                  "778e99ec9130365fc0942132dd923346ffd8370e9196eb73497b2cac7d96ff74"),
    "PassOrder": ('{"kind":"PassOrder","schema":"imperium.battle-command/1","side":"S1"}',
                  "fbd5f87aa74cee76283d10f098c4463d81f852e272f38743b17e22ca0beec450"),
    "DeclareWithdrawal": ('{"kind":"DeclareWithdrawal","schema":"imperium.battle-command/1","side":"S0"}',
                          "f4e21123f14945702cf827d9c0043dc61478571e077e1f4022a0182165aa69e6"),
    "Capitulate": ('{"kind":"Capitulate","schema":"imperium.battle-command/1","side":"S1"}',
                   "0d3a0f09585968ca6ddee26fc0c8f6a726af7161774720db3403e30bc162025d"),
}
SAMPLES = {
    "OpenBattle": E.OpenBattle(),
    "HoldOrder": E.HoldOrder(S0, B.FormationId("S0.H1")),
    "PassOrder": E.PassOrder(S1),
    "DeclareWithdrawal": E.DeclareWithdrawal(S0),
    "Capitulate": E.Capitulate(S1),
}


def all_commands(side=S0):
    return [E.OpenBattle(), hold(side, f"{side.name}.H1"), E.PassOrder(side),
            E.DeclareWithdrawal(side), E.Capitulate(side)]


class BoundaryTypes(EngineCase):
    """TA-A01."""

    def test_argument_types(self):
        s = opened()
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(object(), E.PassOrder(S0))
        self.assertEqual((cm.exception.clause, cm.exception.path), ("V00", "state"))
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(s, "PASS")
        self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))

    def test_dual_invalid_state_first(self):
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(object(), "PASS")
        self.assertEqual(cm.exception.clause, "V00")

    def test_subclass_negatives(self):
        s = opened()

        class Sub(E.PassOrder):
            pass

        class SubState(B.BattleState):
            pass

        with self.assertRaises(B.InvalidValue) as cm:
            E.step(s, Sub(S0))
        self.assertEqual(cm.exception.clause, "T15")
        sub = object.__new__(SubState)
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(sub, E.PassOrder(S0))
        self.assertEqual(cm.exception.clause, "V00")
        with self.assertRaises(B.InvalidValue) as cm:
            E.Accepted(sub, (E.Stage.ROOT,))
        self.assertEqual(cm.exception.clause, "V00")

    def test_field_types(self):
        for bad, clause in (("S0.H1", "T07"), (B.GroupId("S0.G1"), "T07")):
            with self.assertRaises(B.InvalidValue) as cm:
                E.HoldOrder(S0, bad)
            self.assertEqual(cm.exception.clause, clause)
        with self.assertRaises(B.InvalidValue) as cm:
            E.PassOrder("S0")
        self.assertEqual(cm.exception.clause, "T03")
        with self.assertRaises(TypeError):
            E.HoldOrder(side=S0, formation=fid("S0.H1"), charge=0)
        with self.assertRaises(TypeError):
            E.PassOrder()
        with self.assertRaises(TypeError):
            E.OpenBattle(S0)

    def test_result_records(self):
        s = opened()
        with self.assertRaises(B.InvalidValue):
            E.Accepted(s, ())
        with self.assertRaises(B.InvalidValue):
            E.Accepted(s, ("ROOT",))
        with self.assertRaises(B.InvalidValue):
            E.Rejected(s, "PHASE", "", "x")
        with self.assertRaises(B.InvalidValue):
            E.Deferred(s, "PASS", E.Stage.RECOVERY, ("DO-P2-02",))
        with self.assertRaises(B.InvalidValue):
            E.JournalEntry(-1, "0" * 64, "0" * 64, "0" * 64)
        with self.assertRaises(B.InvalidValue):
            E.JournalEntry(1, "A" * 64, "0" * 64, "0" * 64)


class ForeignCommand(EngineCase):
    """PR5-01: an unrelated class whose metaclass claims equality is never admitted."""

    def test_foreign_metaclass(self):
        calls = []

        class Liar(type):
            def __eq__(cls, other):
                calls.append(getattr(other, "__name__", other))
                return True

            def __hash__(cls):
                return hash(E.DeclareWithdrawal)

        class Foreign(metaclass=Liar):
            side = S0

        foreign = Foreign()
        withdrawing = build(awaiting(label="PR5-01"))
        withdrawing = self.accepted(withdrawing, E.DeclareWithdrawal(S0))
        for state in (B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD), opened(), withdrawing):
            with self.assertRaises(B.InvalidValue) as cm:
                E.step(state, foreign)
            self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))
        for fn in (E.encode_command, E.command_digest):
            with self.assertRaises(B.InvalidValue) as cm:
                fn(foreign)
            self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))
        with self.assertRaises(B.InvalidValue):
            E.Deferred(opened(), foreign, E.Stage.RECOVERY, ("DO-P2-02",))
        s = E.BattleSession.open(B.FixtureId("F01-v1-open-standard"))
        with self.assertRaises(B.InvalidValue):
            s.submit(foreign)
        self.assertEqual(s.journal, ())
        self.assertEqual(calls, [])


class Records(EngineCase):
    """TA-A02 and the command document (3.1)."""

    def test_frozen_and_equality(self):
        for c in SAMPLES.values():
            with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
                c.side = S1
        self.assertEqual(E.HoldOrder(S0, fid("S0.H1")), SAMPLES["HoldOrder"])
        self.assertNotEqual(E.PassOrder(S0), E.PassOrder(S1))
        self.assertNotEqual(E.PassOrder(S0), E.DeclareWithdrawal(S0))
        for a in SAMPLES.values():
            for b in SAMPLES.values():
                self.assertEqual(a == b, E.encode_command(a) == E.encode_command(b))

    def test_vectors(self):
        for kind, (text, sha) in VECTORS.items():
            c = SAMPLES[kind]
            doc = E.encode_command(c)
            self.assertEqual(json.dumps(doc, ensure_ascii=True, sort_keys=True,
                                        separators=(",", ":")), text)
            self.assertEqual(hashlib.sha256(text.encode("ascii")).hexdigest(), sha)
            self.assertEqual(E.command_digest(c), sha)

    def test_fresh_primitive_tree(self):
        c = SAMPLES["HoldOrder"]
        a, b = E.encode_command(c), E.encode_command(c)
        self.assertIsNot(a, b)
        a["side"] = "S1"
        self.assertEqual(E.encode_command(c)["side"], "S0")
        self.assertTrue(all(type(v) is str for v in b.values()))

    def test_encode_wrong_type(self):
        for bad in ("PASS", None, B.Side.S0, object()):
            with self.assertRaises(B.InvalidValue) as cm:
                E.encode_command(bad)
            self.assertEqual((cm.exception.clause, cm.exception.path), ("T15", "command"))

    def test_hash_seed_stability(self):
        # The digests are pinned literals above; the determinism row reruns them
        # under both hash seeds in a subprocess.
        self.assertEqual(E.command_digest(E.OpenBattle()), VECTORS["OpenBattle"][1])


class PhaseAdmissibility(EngineCase):
    """TA-A03."""

    def test_principal_in_opening(self):
        s = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        for c in all_commands()[1:]:
            self.rejected(s, c, E.RejectCode.PHASE, "", PHASE_DETAIL)

    def test_open_battle_in_awaiting(self):
        self.rejected(opened(), E.OpenBattle(), E.RejectCode.PHASE, "", PHASE_DETAIL)

    def test_phase_before_side(self):
        s = B.f01_opening(B.Variant.OPEN, B.Orientation.STANDARD)
        self.rejected(s, E.PassOrder(S1), E.RejectCode.PHASE)

    def test_terminal_states(self):
        defensive = B.f01_supplied(DEFENSIVE)
        s = opened()
        t = self.accepted(s, E.Capitulate(S0))
        for state in (defensive, t):
            for side in (S0, S1):
                for c in all_commands(side):
                    self.rejected(state, c, E.RejectCode.PHASE, "", PHASE_DETAIL)


class CursorBound(EngineCase):
    """TA-A06 (P2-01)."""

    def test_last_increment(self):
        s = build(awaiting(cursor=MAX - 1, label="A06a"))
        t = self.accepted(s, hold(S0, "S0.H1"))
        self.assertEqual(t.clock.event_cursor, MAX)

    def test_overflow_is_technical(self):
        s = build(awaiting(cursor=MAX, label="A06b"))
        before, dig = B.canonical_bytes(s), B.digest(s)
        with self.assertRaises(B.InvalidValue) as cm:
            E.step(s, hold(S0, "S0.H1"))
        e = cm.exception
        self.assertEqual((e.clause, e.path, e.detail),
                         ("T10", "state.clock.event_cursor",
                          "successor cursor exceeds the P1 integer domain"))
        self.assertEqual((B.canonical_bytes(s), B.digest(s)), (before, dig))
        self.rejected(s, E.PassOrder(S1), E.RejectCode.WRONG_SIDE)
        self.assertEqual((B.canonical_bytes(s), B.digest(s)), (before, dig))

    def test_deferral_precedes_bound(self):
        d = awaiting(side="S1", cursor=MAX, uses=[pass_use("S0")], label="A06c")
        make_router(d, "S1.H3")
        s = build(d)
        self.deferred(s, E.PassOrder(S1), E.Stage.CLOSURE_DISPLACEMENT, ("DO-P2-01", "DO-P2-02"))

    def test_defensive_terminal_phase_first(self):
        self.rejected(B.f01_supplied(DEFENSIVE), hold(S0, "S0.H1"), E.RejectCode.PHASE)


class Atomicity(EngineCase):
    """TA-A05: covered by every ``rejected``/``deferred`` helper call; one explicit control."""

    def test_identity(self):
        s = opened()
        r = E.step(s, E.PassOrder(S1))
        self.assertIs(r.state, s)
