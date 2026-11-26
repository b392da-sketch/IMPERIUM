"""TA-E01–E05: the round-boundary sequence and the typed closure deferral (P2-E)."""

from unittest import mock

import imperium.battle as B
from imperium.battle import engine as E
import importlib

step_module = importlib.import_module("imperium.battle.engine.step")
from imperium.battle.engine import terminal as terminal_module
from tests.battle.common import cond, individual
from tests.engine.helpers import (
    CLOSE_CONTINUE, ROOT_TERMINAL, ROOT_TRACE, S0, S1, EngineCase, awaiting, build, hold,
    hold_use, make_reformer, make_router, opened, pass_use,
)

BOTH = ("DO-P2-01", "DO-P2-02")
RECOVERY = ("DO-P2-02",)


def rest_use(side, token):
    return individual(side, token, {"kind": "Rest"})


def closing(label, router=False, reformer=False, rest=False):
    """S0 already finished, S1 to move, both viable: S1's Pass closes the round."""
    if rest:
        uses = [rest_use("S0", "S0.H1"), hold_use("S1", "S1.H1"), pass_use("S0")]
    else:
        uses = [pass_use("S0")]
    d = awaiting(side="S1", uses=uses, label=label)
    if rest:
        cond(d, "S0.H1", fat=1)
    if router:
        make_router(d, "S1.H3")
    if reformer:
        make_reformer(d, "S0.H6")
    return d


def open_turn(label, router=False, reformer=False, rest=False):
    """The same boards one turn earlier: S0 to move and unfinished."""
    uses = [rest_use("S0", "S0.H1"), hold_use("S1", "S1.H1")] if rest else []
    d = awaiting(side="S0", uses=uses, label=label)
    if rest:
        cond(d, "S0.H1", fat=1)
    if router:
        make_router(d, "S1.H3")
    if reformer:
        make_reformer(d, "S0.H6")
    return d


VARIANTS = {
    "router": (dict(router=True), E.Stage.CLOSURE_DISPLACEMENT, BOTH),
    "mixed": (dict(router=True, reformer=True, rest=True), E.Stage.CLOSURE_DISPLACEMENT, BOTH),
    "router_rest": (dict(router=True, rest=True), E.Stage.CLOSURE_DISPLACEMENT, BOTH),
    "reformer": (dict(reformer=True), E.Stage.RECOVERY, RECOVERY),
    "rest": (dict(rest=True), E.Stage.RECOVERY, RECOVERY),
    "reformer_rest": (dict(reformer=True, rest=True), E.Stage.RECOVERY, RECOVERY),
}


class Boundary(EngineCase):

    def test_e01_both_pass(self):
        a = self.accepted(opened(), E.PassOrder(S0), ROOT_TRACE)
        b = self.accepted(a, E.PassOrder(S1), CLOSE_CONTINUE)
        self.assertEqual(b.clock, B.Clock(1, 3))
        self.assertEqual(b.phase, B.AwaitingPrincipal(S1))
        self.assertEqual(b.ledger.uses, ())
        self.assertEqual(b.ledger.formations, opened().ledger.formations)

    def test_e01_predicate_points(self):
        """PR5-02: the immediate predicate runs after the root, after the no-op closure
        displacement (pre-advance clock) and at round end, in that order."""
        a = self.accepted(opened(), E.PassOrder(S0))
        points = []
        original = terminal_module.immediate_outcome

        def audit(fields, point, charged, capitulator=None):
            points.append((point, charged, fields.clock.completed_rounds))
            return original(fields, point, charged, capitulator)

        with mock.patch.object(step_module, "immediate_outcome", side_effect=audit), \
                mock.patch.object(terminal_module, "immediate_outcome", side_effect=audit):
            b = E.step(a, E.PassOrder(S1))
        self.assertEqual(b.stages, CLOSE_CONTINUE)
        P = B.TerminationPoint
        self.assertEqual(points, [(P.AFTER_ROOT, 1, 0), (P.AFTER_CLOSURE_DISPLACEMENT, 1, 0),
                                  (P.ROUND_END, 1, 1)])

    def test_e02_e03_deferral(self):
        for name, (kw, stage, obligations) in VARIANTS.items():
            with self.subTest(variant=name):
                s = build(closing("E-" + name, **kw))
                self.assertFalse(B.side_finished(s, S1))
                self.assertGreaterEqual(B.viable_count(s, S0), 1)
                self.assertGreaterEqual(B.viable_count(s, S1), 1)
                self.deferred(s, E.PassOrder(S1), stage, obligations)
                self.deferred(s, E.PassOrder(S1), stage, obligations)
                t = self.accepted(s, E.Capitulate(S1), ROOT_TERMINAL)
                self.assertIs(t.phase.record.reason, B.TerminalReason.CAPITULATION)

    def test_e02_closing_hold_defers(self):
        d = awaiting(side="S1", uses=[pass_use("S0"), hold_use("S1", "S1.H1"),
                                      hold_use("S1", "S1.H2"), hold_use("S1", "S1.H4")],
                     label="E-hold")
        make_router(d, "S1.H3")
        s = build(d)
        self.deferred(s, hold(S1, "S1.H5"), E.Stage.CLOSURE_DISPLACEMENT, BOTH)

    def test_e04_non_closing(self):
        for name, (kw, _, _) in VARIANTS.items():
            with self.subTest(variant=name):
                s = build(open_turn("E4-" + name, **kw))
                token = "S0.H2"
                t = self.accepted(s, hold(S0, token), ROOT_TRACE)
                self.assertIs(t.phase.side, S1)

    def test_e05_never_both_finished(self):
        states = [opened()]
        for name, (kw, _, _) in VARIANTS.items():
            states.append(build(open_turn("E5-" + name, **kw)))
        for s in states:
            for c in (E.PassOrder(S0), hold(S0, "S0.H2"), E.DeclareWithdrawal(S0)):
                r = E.step(s, c)
                if type(r) is E.Accepted and type(r.state.phase) is B.AwaitingPrincipal:
                    self.assertFalse(B.side_finished(r.state, S0) and B.side_finished(r.state, S1))
