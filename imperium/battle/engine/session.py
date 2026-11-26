"""Layer E5: ``BattleSession``, the owned current state and its full-digest
commitment journal (P2 contract 3.2; P1 4.4, DO-09).

Only ``BattleSession.open`` constructs a session, from a registered
fixture. ``submit`` installs only an accepted successor, together with its
journal entry. The journal commits digests; replay also needs the ordered
original commands (DO-10, DO-P2-04).
"""

from imperium.battle import (
    FixtureClass, InvalidValue, UnknownId, descriptor, digest, f01_opening, f01_supplied,
)

from .commands import Accepted, JournalEntry, check_fixture_id, command_digest
from .step import step


def _genesis(d):
    if d.fixture_class is FixtureClass.CANONICAL_OPENING:
        return f01_opening(d.variant, d.orientation)
    return f01_supplied(d.fixture_id)


class BattleSession:
    """One registered battle: a read-only current state and its journal."""

    __slots__ = ("_state", "_journal", "_digest")

    def __init__(self, *args, **kwargs):
        raise TypeError("BattleSession is opened only through BattleSession.open")

    @classmethod
    def open(cls, fixture_id):
        check_fixture_id(fixture_id)
        d = descriptor(fixture_id)
        if d.fixture_class not in (FixtureClass.CANONICAL_OPENING, FixtureClass.SUPPLIED_VALIDATION):
            raise UnknownId(fixture_id)
        state = _genesis(d)
        full = digest(state)
        if full != d.full_genesis_digest:
            raise InvalidValue("P10", "fixture_id", "genesis digest disagrees with its descriptor")
        session = object.__new__(cls)
        object.__setattr__(session, "_state", state)
        object.__setattr__(session, "_journal", ())
        object.__setattr__(session, "_digest", full)
        return session

    def __setattr__(self, name, value):
        raise AttributeError("BattleSession is read-only")

    def __delattr__(self, name):
        raise AttributeError("BattleSession is read-only")

    @property
    def state(self):
        return self._state

    @property
    def journal(self):
        return self._journal

    def submit(self, command):
        result = step(self._state, command)
        if type(result) is Accepted:
            new = result.state
            current = digest(new)
            entry = JournalEntry(
                cursor=new.clock.event_cursor,
                command_digest=command_digest(command),
                previous=self._digest,
                current=current,
            )
            journal = self._journal + (entry,)
            object.__setattr__(self, "_state", new)
            object.__setattr__(self, "_journal", journal)
            object.__setattr__(self, "_digest", current)
        return result
