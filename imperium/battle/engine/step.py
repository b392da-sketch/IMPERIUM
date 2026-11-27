"""Layer E4: ``resolve`` and ``step``, the single transition (P2 contract
5, 6, 8, 10; P3 contract rev 0.3 section 5; P4 contract rev 0.2 sections
4.3, 8 and 9).

``resolve`` returns the P2 result plus the root's events and stage
snapshots; ``step`` is its ``Accepted`` projection. Order: argument types, phase, side, command prerequisites, the pure
deferral decision, the cursor bound, then exactly one ``BattleState``
construction through P1's validating constructor. This is the only engine
module that constructs a state.

P4: a movement root may suspend at its single response window. A
``SuspendedRoot`` is resolved by replanning from its base and principal
command; the rebuilt window must equal the root's before any decision is
admitted (ER02).
"""

import dataclasses

from imperium.battle.queries import (
    Fields, activation, ledger_side_finished, onmap_available,
)
from imperium.battle.records import (
    STATE_FIELDS, AwaitingPrincipal, Clock, Hold, Opening, OpportunityUse, Terminal,
)
from imperium.battle.state import BattleState, state_values
from imperium.battle.values import (
    INT_DOMAIN, Activation, Posture, TerminationPoint, UseKind,
)
from imperium.battle.codec import digest
from imperium.battle.errors import InvalidValue

from .commands import (
    NOT_READY_PATH, REJECT_TEXT, Accepted, Capitulate, DeclareWithdrawal, Deferred, EvacuateOrder,
    GroupMoveOrder, GroupPivotOrder, HoldOrder, MoveOrder, OpenBattle, PassOrder, PivotOrder,
    RejectCode, Rejected, RespondPivot, Stage, WithdrawOrder, check_command, check_state,
    command_digest, encode_command, is_decision, is_p4_principal,
)
from .custody import capitulate
from .events import Resolved, StageSnapshot, build_root, stage_ids
from .movement import (
    admit, evacuate_stage, group_pivot_stage, group_step_stage, move_continues, move_step,
    movers_of, pivot_stage, withdraw_stage,
)
from .rounds import both_finished, closure_deferral, next_to_move, open_round
from .terminal import immediate_outcome, round_end_outcome
from .window import (
    Suspended, SuspendedRoot, WindowDeferred, WindowRejected, ResponseWindow, admit_decision,
    option_tree, rejection_detail, response_stage, window_options, window_token,
)

Result = Accepted | Rejected | Deferred | Suspended | WindowRejected | WindowDeferred



def _reject(state, code, detail=None):
    if code is RejectCode.NOT_READY:
        return Rejected(state, code, NOT_READY_PATH, detail)
    path, text = REJECT_TEXT[code]
    return Rejected(state, code, path, text)


def _terminal(values, record):
    out = dict(values)
    out["phase"] = Terminal(record)
    out["ledger"] = None
    return out


def _admissible(state, fields, command):
    """The first rule failure as a ``Rejected``, or None (6, steps 2–4)."""
    phase = type(fields.phase)
    if type(command) is OpenBattle:
        return None if phase is Opening else _reject(state, RejectCode.PHASE)
    if phase is not AwaitingPrincipal or is_decision(command):
        return _reject(state, RejectCode.PHASE)
    side = command.side
    if side is not fields.phase.side:
        return _reject(state, RejectCode.WRONG_SIDE)
    t = type(command)
    if is_p4_principal(command):
        outcome = admit(fields, command)
        if outcome is None:
            return None
        if outcome[0] == "defer":
            return Deferred(state, command, Stage.ROOT, outcome[1])
        _, code, path, detail = outcome
        return Rejected(state, code, path, detail)
    if t is HoldOrder:
        entry = fields.roster.get(command.formation)
        if entry is None:
            return _reject(state, RejectCode.UNKNOWN_FORMATION)
        if entry.side is not side:
            return _reject(state, RejectCode.NOT_OWN_FORMATION)
        act = activation(fields, command.formation)
        if act is not Activation.READY:
            return _reject(state, RejectCode.NOT_READY, act.name)
    elif t is DeclareWithdrawal:
        if _posture(fields, side) is not Posture.CONTESTING:
            return _reject(state, RejectCode.ALREADY_WITHDRAWING)
    elif t is Capitulate:
        if onmap_available(fields, side) <= 0:
            return _reject(state, RejectCode.NO_ONMAP_AVAILABLE)
    return None


def _posture(fields, side):
    for s in fields.sides:
        if s.side is side:
            return s.posture
    raise LookupError(side)


def _use_of(command):
    t = type(command)
    if t is HoldOrder:
        return OpportunityUse(command.side, UseKind.INDIVIDUAL, None, (command.formation,), (Hold(),))
    if t is PassOrder:
        return OpportunityUse(command.side, UseKind.PASS, None, (), ())
    return OpportunityUse(command.side, UseKind.POSTURE_WITHDRAWAL, None, (), ())


def _plan(values, command):
    """``("deferred", stage, obligations)`` or ``("accepted", trace)``.

    ``trace`` is a tuple of ``(stage, values)`` pairs: the field values
    after each stage of the root (P3 5.3). Pure: works on field values
    only. Every entry still holds the input cursor; the caller advances it.
    """
    fields = Fields(**values)
    clock = fields.clock
    t = type(command)
    if t is OpenBattle:
        record = immediate_outcome(fields, TerminationPoint.INITIAL_CHECK, 0)
        if record is not None:
            return "accepted", ((Stage.INITIAL_CHECK, values),
                                (Stage.TERMINAL, _terminal(values, record)))
        return "accepted", ((Stage.INITIAL_CHECK, values), (Stage.OPEN_ROUND, open_round(values)))
    charged = clock.completed_rounds + 1
    if t is Capitulate:
        after = capitulate(values, command.side)
        record = immediate_outcome(Fields(**after), TerminationPoint.AFTER_ROOT, charged,
                                   capitulator=command.side)
        return "accepted", ((Stage.ROOT, after), (Stage.IMMEDIATE_CHECK, after),
                            (Stage.TERMINAL, _terminal(after, record)))
    # ROOT: append the ledger-bearing use; the phase is unchanged here.
    after = dict(values)
    if t is DeclareWithdrawal:
        after["sides"] = tuple(
            dataclasses.replace(s, posture=Posture.WITHDRAWING) if s.side is command.side else s
            for s in fields.sides)
    ledger = fields.ledger
    ledger = dataclasses.replace(ledger, uses=ledger.uses + (_use_of(command),))
    after["ledger"] = ledger
    return _tail(values, ((Stage.ROOT, after),), after)


def _tail(values, trace, after):
    """IMMEDIATE_CHECK, continuation or closure after the root's last
    physical stage (P2 8, 10), on the post-root field values ``after``."""
    fields = Fields(**values)
    clock = fields.clock
    charged = clock.completed_rounds + 1
    ledger = after["ledger"]
    # IMMEDIATE_CHECK
    record = immediate_outcome(Fields(**after), TerminationPoint.AFTER_ROOT, charged)
    if record is not None:
        return "accepted", trace + ((Stage.IMMEDIATE_CHECK, after),
                                    (Stage.TERMINAL, _terminal(after, record)))
    scenario = fields.scenario
    if not both_finished(scenario, ledger):
        cont = dict(after)
        cont["phase"] = AwaitingPrincipal(next_to_move(scenario, clock, ledger))
        return "accepted", trace + ((Stage.IMMEDIATE_CHECK, cont),)
    deferral = closure_deferral(after)
    if deferral is not None:
        return ("deferred",) + deferral
    trace += ((Stage.IMMEDIATE_CHECK, after), (Stage.CLOSURE_DISPLACEMENT, after))
    # CLOSURE_DISPLACEMENT is a verified no-op in the supported subset (10.1).
    # CLOSURE_CHECK: the immediate predicate on the post-displacement fields,
    # with the pre-advance clock; no positive is reachable in P2.
    record = immediate_outcome(Fields(**after), TerminationPoint.AFTER_CLOSURE_DISPLACEMENT, charged)
    trace += ((Stage.CLOSURE_CHECK, after),)
    if record is not None:
        return "accepted", trace + ((Stage.TERMINAL, _terminal(after, record)),)
    # RECOVERY is a verified no-op; ADVANCE; END_CHECK.
    trace += ((Stage.RECOVERY, after),)
    completed = clock.completed_rounds + 1
    advanced = dict(after)
    advanced["clock"] = Clock(completed_rounds=completed, event_cursor=clock.event_cursor)
    trace += ((Stage.ADVANCE, advanced), (Stage.END_CHECK, advanced))
    record = round_end_outcome(Fields(**advanced), completed, scenario.profile.rounds)
    if record is not None:
        return "accepted", trace + ((Stage.TERMINAL, _terminal(advanced, record)),)
    return "accepted", trace + ((Stage.OPEN_ROUND, open_round(advanced)),)


def _advance_cursor(values):
    clock = values["clock"]
    out = dict(values)
    out["clock"] = Clock(completed_rounds=clock.completed_rounds,
                         event_cursor=clock.event_cursor + 1)
    return out


class _Suspend(Exception):
    """Internal signal: the plan reached a window with no decision."""

    def __init__(self, stage, values, window):
        super().__init__(stage.name)
        self.stage = stage
        self.values = values
        self.window = window


_FIRST_STAGE = {
    WithdrawOrder: withdraw_stage, GroupMoveOrder: group_step_stage, PivotOrder: pivot_stage,
    GroupPivotOrder: group_pivot_stage, EvacuateOrder: evacuate_stage,
}
_TRIGGERS = (Stage.STEP1, Stage.STEP2, Stage.STEP3, Stage.WITHDRAW, Stage.GROUP_STEP)


class _P4Plan:
    """The physical stages of one P4 root, its optional window and decision."""

    def __init__(self, values, command, decision, base_digest):
        self.base = values
        self.command = command
        self.decision = decision
        self.base_digest = base_digest
        self.trace = [(Stage.ROOT, values)]
        self.data = [None]
        self.opened = False

    def push(self, stage, values, data):
        self.trace.append((stage, values))
        self.data.append(data)

    def after_physical(self, pre, post):
        """The window test after a trigger stage; returns the current values."""
        stage = self.trace[-1][0]
        if self.opened or stage not in _TRIGGERS:
            return post
        side = self.command.side
        movers = tuple(sorted(movers_of(self.command), key=lambda f: f.token))
        options = window_options(Fields(**pre), Fields(**post), side, movers)
        if not options:
            return post
        self.opened = True
        after = stage_ids(self.base, self.command, tuple(s for s, _ in self.trace))[-1]
        token = window_token(self.base_digest, command_digest(self.command), after)
        defender = Fields(**post).roster[options[0].formation].side
        window = ResponseWindow(defender, token, after, movers, options)
        if self.decision is None:
            if self._closure_deferral(post) is not None:
                raise _Deferral(self._closure_deferral(post))
            raise _Suspend(stage, post, window)
        self.push(Stage.WINDOW, post, {
            "after": after, "window_id": token, "options": [option_tree(o) for o in options],
            "decision": encode_command(self.decision)})
        if type(self.decision) is RespondPivot:
            post, data = response_stage(post, Fields(**post), self.decision)
            self.push(Stage.RESPONSE, post, data)
        return post

    def _closure_deferral(self, post):
        """ER03: the P2 closure deferral this root would reach, or None."""
        fields = Fields(**self.base)
        charged = fields.clock.completed_rounds + 1
        if immediate_outcome(Fields(**post), TerminationPoint.AFTER_ROOT, charged) is not None:
            return None
        if not both_finished(fields.scenario, post["ledger"]):
            return None
        return closure_deferral(post)

    def run(self):
        command = self.command
        cur = self.base
        if type(command) is MoveOrder:
            latched = False
            for k in range(1, len(command.path) + 1):
                if k > 1 and not move_continues(cur, command, k, latched):
                    break
                stage, post, data, latched = move_step(cur, command, k)
                self.push(stage, post, data)
                cur = self.after_physical(cur, post)
        else:
            stage, post, data = _FIRST_STAGE[type(command)](cur, command)
            self.push(stage, post, data)
            cur = self.after_physical(cur, post)
        outcome = _tail(self.base, tuple(self.trace), cur)
        if outcome[0] == "deferred":
            return outcome
        trace = outcome[1]
        return ("accepted", trace, tuple(self.data) + (None,) * (len(trace) - len(self.data)))


class _Deferral(Exception):
    def __init__(self, deferral):
        super().__init__(deferral[0].name)
        self.deferral = deferral


def _plan_p4(values, command, decision, base_digest):
    try:
        return _P4Plan(values, command, decision, base_digest).run()
    except _Suspend as s:
        return ("suspended", s.stage, s.values, s.window)
    except _Deferral as d:
        return ("deferred",) + d.deferral


def _check_cursor(state):
    if state.clock.event_cursor >= INT_DOMAIN:
        raise InvalidValue("T10", "state.clock.event_cursor",
                           "successor cursor exceeds the P1 integer domain")


def _publish(state, values, command, trace, data):
    _check_cursor(state)
    stages = tuple(stage for stage, _ in trace)
    stage_values = tuple(_advance_cursor(v) for _, v in trace)
    successor = BattleState(**stage_values[-1])
    accepted = Accepted(successor, stages)
    record, snapshots = build_root(values, command, stages, stage_values,
                                   digest(state), digest(successor), data)
    return Resolved(accepted, record, snapshots)


def _rederive(root):
    """The rebuilt first window of ``root``; T16 at ``root`` unless genuine."""
    base = root.base
    values = dict(zip(STATE_FIELDS, state_values(base)))
    fields = Fields(**values)
    command = root.command
    genuine = (type(fields.phase) is AwaitingPrincipal and command.side is fields.phase.side
               and admit(fields, command) is None)
    if genuine:
        outcome = _plan_p4(values, command, None, digest(base))
        genuine = outcome[0] == "suspended"
    if genuine:
        _, stage, post, window = outcome
        advanced = _advance_cursor(post)
        snapshot = StageSnapshot(stage, window.after, tuple(advanced[n] for n in STATE_FIELDS))
        genuine = snapshot == root.stage and window == root.window
    if not genuine:
        raise InvalidValue("T16", "root", "not a genuine suspended root")
    return values


def _resolve_root(root, command):
    check_command(command)
    values = _rederive(root)
    outcome = admit_decision(root, command)
    if outcome is not None:
        if outcome[0] == "defer":
            return WindowDeferred(root, command, outcome[1])
        _, code, path = outcome
        return WindowRejected(root, code, path, rejection_detail(code))
    base = root.base
    planned = _plan_p4(values, root.command, command, digest(base))
    if planned[0] != "accepted":  # pragma: no cover - excluded by the genuine-root check
        raise InvalidValue("T16", "root", "the decision does not complete the root")
    return _publish(base, values, root.command, planned[1], planned[2])


def resolve(state, command):
    """Apply one command to one stable state or one suspended root (P3 5.1,
    P4 4.3).

    Returns the P2 ``Rejected`` or ``Deferred`` unchanged, ``Resolved``
    carrying the P2 ``Accepted``, its ``RootRecord`` and one snapshot per
    event, or for P4 ``Suspended``, ``WindowRejected`` or ``WindowDeferred``.
    """
    if type(state) is SuspendedRoot:
        return _resolve_root(state, command)
    check_state(state)
    check_command(command)
    values = dict(zip(STATE_FIELDS, state_values(state)))
    rejected = _admissible(state, Fields(**values), command)
    if rejected is not None:
        return rejected
    if is_p4_principal(command):
        base_digest = digest(state)
        outcome = _plan_p4(values, command, None, base_digest)
        if outcome[0] == "deferred":
            return Deferred(state, command, outcome[1], outcome[2])
        if outcome[0] == "suspended":
            _, stage, post, window = outcome
            _check_cursor(state)
            advanced = _advance_cursor(post)
            snapshot = StageSnapshot(stage, window.after, tuple(advanced[n] for n in STATE_FIELDS))
            return Suspended(SuspendedRoot(state, command, snapshot, window))
        return _publish(state, values, command, outcome[1], outcome[2])
    outcome = _plan(values, command)
    if outcome[0] == "deferred":
        return Deferred(state, command, outcome[1], outcome[2])
    return _publish(state, values, command, outcome[1], None)


def step(state, command):
    """Apply one command to one stable state or suspended root; return
    Accepted, Rejected, Deferred, Suspended, WindowRejected or WindowDeferred."""
    result = resolve(state, command)
    if type(result) is Resolved:
        return result.accepted
    return result
