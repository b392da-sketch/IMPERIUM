"""Layer 11: state-aware public wrappers (contract 4.1, 12.2–12.4).

Each wrapper checks an exact ``BattleState`` first (V00 at ``state``), then
its other arguments in signature order (12.2), then projects the state's
typed fields and calls the layer-7 field query. No derived value is
computed here.
"""

from . import queries
from .board import Board
from .board import entry_cost as _entry_cost
from .board import terrain_cost as _terrain_cost
from .canon import normalized_digest as _normalized_digest
from .descriptors import DESCRIPTORS, find_descriptor
from .errors import InvalidValue, UnknownId
from .ids import FixtureId, FormationId
from .profile import mode_compatible
from .profile import movement_cost_kind as _movement_cost_kind
from .records import WORK_CLASSES, Assault, GroupStep, Missile, Move, Response, Withdraw
from .scenario import Scenario
from .scenario import end_of as _end_of
from .state import V00, BattleState, state_values
from .values import (
    EnumK, FixtureClass, Hex, IdK, MovementMode, Opt, RecK, Side, TemplateKind,
)
from .values import direction_of as _direction_of

_FID = IdK(FormationId)
_SIDE = EnumK(Side)
_HEX = RecK((Hex,))
_WORK_OR_RESPONSE = RecK(WORK_CLASSES + (Response,))


def _check(kind, value, name):
    failure = kind.check(value, name)
    if failure is not None:
        raise InvalidValue(*failure)


def _fields(s):
    if type(s) is not BattleState:
        raise InvalidValue(V00[0].clause, "state", V00[0].detail)
    return queries.Fields(*state_values(s))


def _fid(fields, fid):
    _check(_FID, fid, "fid")
    if fid not in fields.roster:
        raise UnknownId(fid)
    return fid


def _side(side):
    _check(_SIDE, side, "side")
    return side


# --------------------------------------------------------------------------
# Formation reads


def formation(s, fid):
    f = _fields(s)
    return f.fmap[_fid(f, fid)]


def personnel_of(s, fid):
    f = _fields(s)
    return queries.lots_of(f, _fid(f, fid))


def mounts_of(s, fid):
    f = _fields(s)
    return queries.mounts_of(f, _fid(f, fid))


def account_of(s, fid):
    f = _fields(s)
    return queries.account_of(f, _fid(f, fid))


def contacts_of(s, fid):
    f = _fields(s)
    return queries.contacts_of(f, _fid(f, fid))


def available(s, fid):
    f = _fields(s)
    return queries.available(f, _fid(f, fid))


def wounded(s, fid):
    f = _fields(s)
    return queries.wounded(f, _fid(f, fid))


def dead(s, fid):
    f = _fields(s)
    return queries.dead(f, _fid(f, fid))


def captured(s, fid):
    f = _fields(s)
    return queries.captured(f, _fid(f, fid))


def serviceable_assigned_mounts(s, fid):
    f = _fields(s)
    return queries.serviceable_assigned_mounts(f, _fid(f, fid))


def side_totals(s, side):
    f = _fields(s)
    return queries.side_totals(f, _side(side))


def movement_mode(s, fid):
    f = _fields(s)
    return queries.movement_mode(f, _fid(f, fid))


# --------------------------------------------------------------------------
# Primitive functions (no state argument)


def movement_cost_kind(mode, template):
    _check(EnumK(MovementMode), mode, "mode")
    _check(EnumK(TemplateKind), template, "template")
    return _movement_cost_kind(mode, template)


def direction_of(origin, destination):
    _check(_HEX, origin, "origin")
    _check(_HEX, destination, "destination")
    return _direction_of(origin, destination)


def terrain_cost(board, cell, kind):
    _check(RecK((Board,)), board, "board")
    _check(_HEX, cell, "cell")
    _check(EnumK(TemplateKind), kind, "kind")
    return _terrain_cost(board, cell, kind)


def entry_cost(board, origin, destination, kind):
    _check(RecK((Board,)), board, "board")
    _check(_HEX, origin, "origin")
    _check(_HEX, destination, "destination")
    _check(EnumK(TemplateKind), kind, "kind")
    return _entry_cost(board, origin, destination, kind)


def end_of(scenario, side):
    _check(RecK((Scenario,)), scenario, "scenario")
    return _end_of(scenario, _side(side))


# --------------------------------------------------------------------------
# Charges (7.2, 12.4, E06, Q-G)


def _modes(work):
    t = type(work)
    if t is Move:
        return [leg.mode for leg in work.legs]
    if t is Withdraw or t is GroupStep:
        return [work.leg.mode]
    if t is Assault:
        return [work.mode]
    return []


def charge(s, fid, work):
    """Effort charge of ``work`` for ``fid``, in any phase (12.4)."""
    f = _fields(s)
    _check(_FID, fid, "fid")
    _check(_WORK_OR_RESPONSE, work, "work")
    entry = f.roster.get(fid)
    if entry is None:
        raise UnknownId(fid)
    t = type(work)
    if t is Assault or t is Missile or t is Response:
        if work.target not in f.roster:
            raise UnknownId(work.target)
    if not all(mode_compatible(m, entry.template) for m in _modes(work)):
        raise InvalidValue("R24", "work", "mode incompatible with the template")
    if t is Response:
        if not queries.response_ok(f.scenario, f.roster, fid, work):
            raise InvalidValue("R20", "work", "response target or kind is invalid")
    elif t is Assault:
        if not queries.assault_ok(f.scenario, f.roster, fid, work):
            raise InvalidValue("R21", "work", "assault geometry or target is invalid")
    elif t is Missile:
        if not queries.missile_ok(f.scenario, f.roster, fid, work):
            raise InvalidValue("R21", "work", "missile geometry or target is invalid")
    result = queries.work_charge(f.scenario, entry, work)
    if result is None:
        raise InvalidValue("R21", "work", "an initiated leg has no entry cost")
    return result


# --------------------------------------------------------------------------
# Round and phase queries (9.1, 9.2)


def effort_charged(s, fid):
    f = _fields(s)
    return queries.effort_charged(f, _fid(f, fid))


def effort_remaining(s, fid):
    f = _fields(s)
    return queries.effort_remaining(f, _fid(f, fid))


def projected_opening_effort(s, fid):
    f = _fields(s)
    return queries.projected_opening_effort(f, _fid(f, fid))


def effort_usable(s, fid):
    f = _fields(s)
    return queries.effort_usable(f, _fid(f, fid))


def activation(s, fid):
    f = _fields(s)
    return queries.activation(f, _fid(f, fid))


def capacity_remaining(s, side):
    f = _fields(s)
    return queries.capacity_remaining(f, _side(side))


def projected_capacity(s, side):
    f = _fields(s)
    return queries.projected_capacity(f, _side(side))


def usable_opportunities(s, side):
    f = _fields(s)
    return queries.usable_opportunities(f, _side(side))


def side_finished(s, side):
    f = _fields(s)
    return queries.side_finished(f, _side(side))


def next_side(s):
    return queries.next_side(_fields(s))


def response_allowance_unused(s, fid):
    f = _fields(s)
    return queries.response_allowance_unused(f, _fid(f, fid))


def response_possible(s, fid):
    f = _fields(s)
    return queries.response_possible(f, _fid(f, fid))


def rest_benefit_pending(s, fid):
    f = _fields(s)
    return queries.rest_benefit_pending(f, _fid(f, fid))


def recovery_safe_now(s, fid):
    f = _fields(s)
    return queries.recovery_safe_now(f, _fid(f, fid))


def rest_order_exists(s, fid):
    f = _fields(s)
    return queries.rest_order_exists(f, _fid(f, fid))


def full_safe_interval(s, fid):
    f = _fields(s)
    return queries.full_safe_interval(f, _fid(f, fid))


def threat_sources(s, cell, side=None):
    f = _fields(s)
    _check(_HEX, cell, "cell")
    _check(Opt(_SIDE), side, "side")
    return queries.threat_sources(f, cell, side)


def objective_status(s):
    return queries.objective_status(_fields(s))


def viable_count(s, side):
    f = _fields(s)
    return queries.viable_count(f, _side(side))


def onmap_available(s, side):
    f = _fields(s)
    return queries.onmap_available(f, _side(side))


def exit_available(s, side):
    f = _fields(s)
    return queries.exit_available(f, _side(side))


def elapsed_minutes(s):
    return queries.elapsed_minutes(_fields(s))


def current_round(s):
    return queries.current_round(_fields(s))


def normalized_digest(s):
    if type(s) is not BattleState:
        raise InvalidValue(V00[0].clause, "state", V00[0].detail)
    return _normalized_digest(state_values(s))


# --------------------------------------------------------------------------
# Descriptors (12.3)


def descriptor(fixture_id):
    _check(IdK(FixtureId), fixture_id, "fixture_id")
    d = find_descriptor(fixture_id)
    if d is None:
        raise UnknownId(fixture_id)
    return d


def canonical_ids():
    return tuple(d.fixture_id for d in DESCRIPTORS if d.fixture_class is FixtureClass.CANONICAL_OPENING)


def supplied_ids():
    return tuple(d.fixture_id for d in DESCRIPTORS if d.fixture_class is FixtureClass.SUPPLIED_VALIDATION)
