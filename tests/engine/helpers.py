"""Shared literal carriers and assertions for the P2 acceptance suite.

Carriers are literal P1 documents decoded through P1's decoder. Expected
values are written in the tests; nothing here derives a checked value
from engine code.
"""

import copy
import unittest

import imperium.battle as B
from imperium.battle import engine as E
from tests.battle.common import a1, f, fi, fr, fround, individual, place, plot, use
from tests.support.battle_builder import as_adversarial, build, opening_document

S0, S1 = B.Side.S0, B.Side.S1
MAX = 2 ** 63 - 1
REGISTERED = tuple(d.fixture_id for d in B.DESCRIPTORS)
OPENINGS = tuple(d.fixture_id for d in B.DESCRIPTORS
                 if d.fixture_class is B.FixtureClass.CANONICAL_OPENING) + (
    B.FixtureId("F01-v1-open-standard-mount-shortfall"),)
DEFENSIVE = B.FixtureId("F01-v1-defensive-mutual-capitulation")
STANDARD = B.FixtureId("F01-v1-open-standard")

ROOT_TRACE = (E.Stage.ROOT, E.Stage.IMMEDIATE_CHECK)
ROOT_TERMINAL = ROOT_TRACE + (E.Stage.TERMINAL,)
CLOSURE = (E.Stage.CLOSURE_DISPLACEMENT, E.Stage.CLOSURE_CHECK, E.Stage.RECOVERY,
           E.Stage.ADVANCE, E.Stage.END_CHECK)
CLOSE_CONTINUE = ROOT_TRACE + CLOSURE + (E.Stage.OPEN_ROUND,)
CLOSE_TERMINAL = ROOT_TRACE + CLOSURE + (E.Stage.TERMINAL,)
OPEN_CONTINUE = (E.Stage.INITIAL_CHECK, E.Stage.OPEN_ROUND)
OPEN_TERMINAL = (E.Stage.INITIAL_CHECK, E.Stage.TERMINAL)

PHASE_DETAIL = "command is not admissible in this phase"


def fid(token):
    return B.FormationId(token)


def hold(side, token):
    return E.HoldOrder(side, fid(token))


def opened(fixture_id=STANDARD):
    """The round-1 A state of a registered opening, via a real session."""
    s = E.BattleSession.open(fixture_id)
    s.submit(E.OpenBattle())
    return s.state


def doc_of(state):
    return B.encode_state(state)


def awaiting(side="S0", completed=0, cursor=1, uses=(), label="P2", rounds=None):
    """An adversarial A carrier on the open-standard board."""
    d = a1(label=label)
    d["clock"] = {"completed_rounds": completed, "event_cursor": cursor}
    d["phase"] = {"kind": "AwaitingPrincipal", "side": side}
    d["ledger"]["uses"] = [copy.deepcopy(u) for u in uses]
    if rounds is not None:
        d["ledger"]["formations"] = rounds
    return d


def pass_use(side):
    return use(side, "PASS", [], [])


def hold_use(side, token):
    return individual(side, token, {"kind": "Hold"})


def make_router(d, token):
    f(d, token)["disposition"] = "ROUTING"
    r = fr(d, token)
    r["opened_eligible"] = False
    return d


def make_reformer(d, token):
    f(d, token)["disposition"] = "REFORMING"
    return d


class EngineCase(unittest.TestCase):

    def assert_valid(self, state):
        self.assertIs(type(state), B.BattleState)
        self.assertEqual(B.validate_state(state), ())
        self.assertEqual(B.decode_state(B.encode_state(state)), state)
        self.assertEqual(B.decode_bytes(B.canonical_bytes(state)), state)

    def accepted(self, state, command, stages=None):
        before = B.canonical_bytes(state)
        r = E.step(state, command)
        self.assertIs(type(r), E.Accepted, msg=repr(r)[:300])
        self.assertEqual(B.canonical_bytes(state), before)
        self.assert_valid(r.state)
        self.assertEqual(r.state.clock.event_cursor, state.clock.event_cursor + 1)
        if stages is not None:
            self.assertEqual(r.stages, stages)
        return r.state

    def rejected(self, state, command, code, path=None, detail=None):
        before, dig = B.canonical_bytes(state), B.digest(state)
        r = E.step(state, command)
        self.assertIs(type(r), E.Rejected, msg=repr(r)[:300])
        self.assertIs(r.state, state)
        self.assertIs(r.code, code)
        if path is not None:
            self.assertEqual(r.path, path)
        if detail is not None:
            self.assertEqual(r.detail, detail)
        self.assertEqual(B.canonical_bytes(state), before)
        self.assertEqual(B.digest(state), dig)
        return r

    def deferred(self, state, command, stage, obligations):
        before, dig = B.canonical_bytes(state), B.digest(state)
        r = E.step(state, command)
        self.assertIs(type(r), E.Deferred, msg=repr(r)[:300])
        self.assertIs(r.state, state)
        self.assertIs(r.command, command)
        self.assertIs(r.stage, stage)
        self.assertEqual(r.obligations, obligations)
        self.assertEqual(B.canonical_bytes(state), before)
        self.assertEqual(B.digest(state), dig)
        again = E.step(state, command)
        self.assertEqual(again, r)
        return r


__all__ = [n for n in dir() if not n.startswith("__")]
