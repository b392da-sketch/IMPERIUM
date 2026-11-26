"""IMPERIUM battle engine P2: the authoritative command boundary and
transition foundation (P2 contract revision 0.2, section 3).

``step`` is the single transition; ``BattleSession`` owns one current
state and its full-digest commitment journal.
"""

from .commands import (
    Accepted, Capitulate, Command, DeclareWithdrawal, Deferred, HoldOrder, JournalEntry,
    OpenBattle, PassOrder, RejectCode, Rejected, Result, Stage, command_digest, encode_command,
)
from .session import BattleSession
from .step import step

__all__ = [
    "OpenBattle", "HoldOrder", "PassOrder", "DeclareWithdrawal", "Capitulate", "Command",
    "Accepted", "Rejected", "Deferred", "Result", "Stage", "RejectCode",
    "step", "BattleSession", "JournalEntry", "encode_command", "command_digest",
]
