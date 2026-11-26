"""Layer E5a: replay of a verified audit journal (P3 contract rev 0.3
section 9, DO-10).

Replay first verifies with the same options, then reopens the registered
fixture with the verified run, resubmits each decoded command and requires
the re-exported journal to equal the input byte for byte.
"""

import json

from imperium.battle import FixtureId
from imperium.battle.canon import canonical_bytes_of
from imperium.battle.audit import verify
from imperium.battle.audit.refold import preflight

from .commands import Accepted, decode_command
from .draws import RunKey
from .session import BattleSession


class ReplayError(Exception):
    """A replay mismatch after successful verification (RP01)."""

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
        command = decode_command(canonical_bytes_of(json.loads(raw)["command"]))
        if type(session.submit(command)) is not Accepted:
            raise ReplayError("RP01", number, "the engine does not accept this root's command")
    again = session.export_audit(seal=report.sealed)
    if again != data:
        mine, theirs = again.split(b"\n"), data.split(b"\n")
        for number, (a, b) in enumerate(zip(mine, theirs), start=1):
            if a != b:
                raise ReplayError("RP01", number, "re-exported line differs")
        raise ReplayError("RP01", min(len(mine), len(theirs)), "re-exported length differs")
    return report
