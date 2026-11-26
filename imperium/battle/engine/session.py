"""Layer E5: ``BattleSession``, the owned current state and its full-digest
commitment journal (P2 contract 3.2; P1 4.4, DO-09).

Only ``BattleSession.open`` constructs a session, from a registered
fixture. ``submit`` installs only an accepted successor, together with its
journal entry. The journal commits digests; replay also needs the ordered
original commands (DO-10, DO-P2-04).

P3 (contract rev 0.3 sections 6, 7): ``submit`` resolves once and installs
the successor, its journal entry and its ``RootRecord`` together;
``export_audit`` writes the canonical audit journal without changing the
session.
"""

from imperium.battle import (
    FixtureClass, InvalidValue, UnknownId, descriptor, digest, f01_opening, f01_supplied,
)

from imperium.battle.canon import canonical_bytes_of, sha256_hex
from imperium.battle.records import Terminal

from .commands import COMMAND_SCHEMA, JournalEntry, check_fixture_id, encode_command
from .draws import REGISTRY, RNG_VERSION, RunKey, fixture_pair
from .events import EVENT_SCHEMA, Resolved, canonical_tree
from .step import resolve

AUDIT_SCHEMA = "imperium.battle-audit/1"
STATE_SCHEMA = "imperium.battle-state/1"
STAGE_NAMES = (
    "ADVANCE", "CLOSURE_CHECK", "CLOSURE_DISPLACEMENT", "END_CHECK", "IMMEDIATE_CHECK",
    "INITIAL_CHECK", "OPEN_ROUND", "RECOVERY", "ROOT", "TERMINAL",
)


def _genesis(d):
    if d.fixture_class is FixtureClass.CANONICAL_OPENING:
        return f01_opening(d.variant, d.orientation)
    return f01_supplied(d.fixture_id)


class BattleSession:
    """One registered battle: a read-only current state and its journal."""

    __slots__ = ("_state", "_journal", "_digest", "_records", "_descriptor", "_run")

    def __init__(self, *args, **kwargs):
        raise TypeError("BattleSession is opened only through BattleSession.open")

    @classmethod
    def open(cls, fixture_id, run=None):
        check_fixture_id(fixture_id)
        d = descriptor(fixture_id)
        if d.fixture_class not in (FixtureClass.CANONICAL_OPENING, FixtureClass.SUPPLIED_VALIDATION):
            raise UnknownId(fixture_id)
        if run is not None and type(run) is not RunKey:
            raise InvalidValue("T15", "run", "expected None or a RunKey")
        state = _genesis(d)
        full = digest(state)
        if full != d.full_genesis_digest:
            raise InvalidValue("P10", "fixture_id", "genesis digest disagrees with its descriptor")
        session = object.__new__(cls)
        object.__setattr__(session, "_state", state)
        object.__setattr__(session, "_journal", ())
        object.__setattr__(session, "_digest", full)
        object.__setattr__(session, "_records", ())
        object.__setattr__(session, "_descriptor", d)
        object.__setattr__(session, "_run", run)
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

    @property
    def records(self):
        """The accepted ``RootRecord``s, in order (P3 6)."""
        return self._records

    @property
    def run(self):
        return self._run

    def submit(self, command):
        result = resolve(self._state, command)
        if type(result) is not Resolved:
            return result
        accepted, record = result.accepted, result.record
        new = accepted.state
        current = digest(new)
        if record.previous != self._digest or record.current != current:
            raise InvalidValue("T16", "record", "root record disagrees with the session")
        entry = JournalEntry(
            cursor=new.clock.event_cursor,
            command_digest=record.command_digest,
            previous=self._digest,
            current=current,
        )
        journal = self._journal + (entry,)
        records = self._records + (record,)
        object.__setattr__(self, "_state", new)
        object.__setattr__(self, "_journal", journal)
        object.__setattr__(self, "_records", records)
        object.__setattr__(self, "_digest", current)
        return accepted

    def export_audit(self, seal=True):
        """The canonical audit journal bytes (P3 7); the session is unchanged."""
        if type(seal) is not bool:
            raise TypeError("seal must be a bool")
        return audit_bytes(self._descriptor, self._run, self._records, self._state, seal)


def _line(tree, chain):
    body = canonical_bytes_of(tree)
    link = sha256_hex(body if chain is None else chain.encode("ascii") + body)
    out = dict(tree)
    out["chain"] = link
    return canonical_bytes_of(out) + b"\n", link


def _event_tree(event):
    return {
        "stage": event.stage.name,
        "id": event.stage_id,
        "data": canonical_tree(event.data, "data"),
        "effects": [{"path": e.path, "old": canonical_tree(e.old, "old"),
                     "new": canonical_tree(e.new, "new")} for e in event.effects],
        "draws": [],
    }


def audit_bytes(d, run, records, final_state, seal):
    """Serialize a header, the root lines and, if sealed, the trailer."""
    header = {
        "kind": "header", "schema": AUDIT_SCHEMA, "state_schema": STATE_SCHEMA,
        "command_schema": COMMAND_SCHEMA, "event_schema": EVENT_SCHEMA, "rng": RNG_VERSION,
        "registry": REGISTRY, "fixture": d.fixture_id.token, "pair": fixture_pair(d),
        "genesis": d.full_genesis_digest,
        "run": None if run is None else {"seed": run.seed, "replicate": run.replicate},
    }
    chunks = []
    data, chain = _line(header, None)
    chunks.append(data)
    counts = dict.fromkeys(STAGE_NAMES, 0)
    for r in records:
        tree = {
            "kind": "root", "cursor": r.cursor, "command": encode_command(r.command),
            "command_digest": r.command_digest, "previous": r.previous, "current": r.current,
            "events": [_event_tree(e) for e in r.events],
        }
        data, chain = _line(tree, chain)
        chunks.append(data)
        for e in r.events:
            counts[e.stage.name] += 1
    if seal:
        trailer = {
            "kind": "trailer", "roots": len(records), "cursor": final_state.clock.event_cursor,
            "final": digest(final_state), "terminal": type(final_state.phase) is Terminal,
            "stages": counts, "draws": 0,
        }
        data, chain = _line(trailer, chain)
        chunks.append(data)
    return b"".join(chunks)
