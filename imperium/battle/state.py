"""Layer 9: ``BattleState`` and ``validate_state`` (contract 4.1 E05, 4.2,
10.2, 12.3).

``BattleState`` has one constructor, which validates. There is no
unchecked path, skip flag, placeholder or registration step.
"""

import dataclasses
from dataclasses import dataclass

from . import invariants
from .errors import InvalidState, InvalidValue, Violation
from .records import STATE_FIELDS, RoundLedger
from .scenario import Scenario

V00 = (Violation("V00", "", "not a BattleState"),)


@dataclass(frozen=True, slots=True)
class BattleState:
    scenario: Scenario
    phase: object
    clock: object
    sides: tuple
    formations: tuple
    authority: tuple
    personnel: tuple
    mounts: tuple
    ammunition: tuple
    contacts: tuple
    ledger: RoundLedger | None

    def __post_init__(self):
        values = _values(self)
        for (name, kind), value in zip(invariants.ROOT_SPEC, values):
            failure = kind.check(value, name)
            if failure is not None:
                raise InvalidValue(*failure)
        violations = invariants.validate_fields(*values)
        if violations:
            raise InvalidState(violations)

    def evolve(self, **changes):
        """``dataclasses.replace`` through the same validating constructor."""
        return dataclasses.replace(self, **changes)


def _values(state):
    return tuple(object.__getattribute__(state, name) for name in STATE_FIELDS)


def state_values(state):
    """The eleven field values of an exact ``BattleState``, in 6.2 order."""
    return _values(state)


def validate_state(obj):
    """``()`` iff valid; the V00 tuple for anything not exactly a state."""
    if type(obj) is not BattleState:
        return V00
    return invariants.validate_fields(*_values(obj))
