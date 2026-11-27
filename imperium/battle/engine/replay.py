"""Layer E5a: replay of a verified audit journal (P3 contract rev 0.3
section 9, DO-10).

Replay first verifies with the same options, then reopens the registered
fixture with the verified run, resubmits each decoded command and requires
the re-exported journal to equal the input byte for byte.

P4 (contract rev 0.2 section 10.6): a root that suspends is completed by
submitting the decision recorded in its WINDOW event; a missing or unusable
decision, or one replay rejects or defers, is RP02.
"""

import json

from imperium.battle import FixtureId, InvalidValue
from imperium.battle.canon import canonical_bytes_of
from imperium.battle.audit import verify
from imperium.battle.audit.refold import preflight

from .commands import Accepted, decode_command, is_decision
from .draws import RunKey
from .session import BattleSession
from .window import Suspended


class ReplayError(Exception):
    """A replay mismatch after successful verification (RP01), or an
    unusable recorded window decision (RP02)."""

    def __init__(self, code, line, detail):
        super().__init__(f"{code} line {line}: {detail}")
        self.code = code
        self.line = line
        self.detail = detail


def replay(data, *, require_sealed=True, expected_chain=None):
    """Return the verified ``AuditReport`` iff the engine reproduces ``data``."""
    preflight(data, require_sealed, expected_chain)
    report = verify(data, require_sealed=require_sealed, expected_chain=expected_chain)
    run = None if report.run is None else RunKey(*report.run)
    session = BattleSession.open(FixtureId(report.fixture), run)
    for number, raw in enumerate(data.split(b"\n")[1:1 + report.roots], start=2):
        line = json.loads(raw)
        command = decode_command(canonical_bytes_of(line["command"]))
        result = session.submit(command)
        if type(result) is Suspended:
            result = _decide(session, line, number)
        if type(result) is not Accepted:
            raise ReplayError("RP01", number, "the engine does not accept this root's command")
    if session.pending is not None:  # pragma: no cover - _decide always resolves or raises
        raise ReplayError("RP02", 1 + report.roots, "a window is still pending")
    again = session.export_audit(seal=report.sealed)
    if again != data:
        mine, theirs = again.split(b"\n"), data.split(b"\n")
        for number, (a, b) in enumerate(zip(mine, theirs), start=1):
            if a != b:
                raise ReplayError("RP01", number, "re-exported line differs")
        raise ReplayError("RP01", min(len(mine), len(theirs)), "re-exported length differs")
    return report


def recorded_decision(line):
    """The decision document recorded in a root line's WINDOW event, or None."""
    for event in line["events"]:
        if event["stage"] == "WINDOW" and type(event["data"]) is dict:
            return event["data"].get("decision")
    return None


def _decide(session, line, number):
    doc = recorded_decision(line)
    if doc is None:
        raise ReplayError("RP02", number, "the suspended root has no recorded decision")
    try:
        decision = decode_command(canonical_bytes_of(doc))
    except (InvalidValue, TypeError, ValueError):
        raise ReplayError("RP02", number, "the recorded decision is unusable") from None
    if not is_decision(decision):
        raise ReplayError("RP02", number, "the recorded decision is unusable")
    result = session.submit(decision)
    if type(result) is not Accepted:
        raise ReplayError("RP02", number, "replay rejects or defers the recorded decision")
    return result
