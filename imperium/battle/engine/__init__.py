"""IMPERIUM battle engine: the authoritative command boundary and
transition foundation (P2 contract revision 0.2, section 3), with P3
semantic events, the BK-1 draw-key registry and replay (P3 contract
revision 0.3, ER04 export inventory), and P4 movement, group orders,
evacuation and the single response window (P4 contract revision 0.2, E05).

``resolve`` is the single transition and ``step`` its ``Accepted``
projection; ``BattleSession`` owns one current state, its full-digest
commitment journal and its audit records.
"""

from .commands import (
    Accepted, Capitulate, Command, DeclareWithdrawal, DeclineResponse, Deferred, EvacuateOrder,
    GroupMoveOrder, GroupPivotOrder, HoldOrder, JournalEntry, MoveOrder, OpenBattle, PassOrder,
    PivotOrder, RejectCode, Rejected, RespondMissile, RespondPivot, Stage, WithdrawOrder,
    command_bytes, command_digest, decode_command, encode_command,
)
from .draws import (
    Channel, RunKey, StageKey, draw_numerator, fixture_pair, format_stage_id, parse_stage_id,
)
from .events import DrawRecord, Effect, Resolved, RootRecord, StageEvent, StageSnapshot
from .session import BattleSession
from .step import Result, resolve, step
from .window import (
    ResponseOption, ResponseWindow, Suspended, SuspendedRoot, WindowDeferred, WindowRejected,
)
from .replay import ReplayError, replay

__all__ = [
    "OpenBattle", "HoldOrder", "PassOrder", "DeclareWithdrawal", "Capitulate", "Command",
    "Accepted", "Rejected", "Deferred", "Result", "Stage", "RejectCode",
    "step", "BattleSession", "JournalEntry", "encode_command", "command_digest",
    "RunKey", "Channel", "StageKey", "format_stage_id", "parse_stage_id", "fixture_pair",
    "draw_numerator", "Effect", "DrawRecord", "StageEvent", "StageSnapshot", "RootRecord",
    "Resolved", "resolve", "command_bytes", "decode_command", "replay", "ReplayError",
    # P4 (contract rev 0.2 section 4, E05)
    "MoveOrder", "PivotOrder", "WithdrawOrder", "EvacuateOrder", "GroupMoveOrder",
    "GroupPivotOrder", "RespondPivot", "RespondMissile", "DeclineResponse", "ResponseOption",
    "ResponseWindow", "SuspendedRoot", "Suspended", "WindowRejected", "WindowDeferred",
]
