"""IMPERIUM battle package P1: the validated, immutable representation of
the standalone F01 battlefield and its authoritative stable states.

``__all__`` is exactly the public surface of contract section 12.
"""

from .api import (
    account_of, activation, available, canonical_ids, capacity_remaining, captured, charge,
    contacts_of, current_round, dead, descriptor, direction_of, effort_charged,
    effort_remaining, effort_usable, elapsed_minutes, end_of, entry_cost, exit_available,
    formation, full_safe_interval, mounts_of, movement_cost_kind, movement_mode, next_side,
    normalized_digest, objective_status, onmap_available, personnel_of, projected_capacity,
    projected_opening_effort, recovery_safe_now, response_allowance_unused,
    response_possible, rest_benefit_pending, rest_order_exists, serviceable_assigned_mounts,
    side_finished, side_totals, supplied_ids, terrain_cost, threat_sources,
    usable_opportunities, viable_count, wounded,
)
from .board import Board, EdgeRule
from .canon import SCHEMA
from .codec import canonical_bytes, decode_bytes, decode_state, digest, encode_state
from .descriptors import DESCRIPTORS, FixtureDescriptor
from .errors import DecodeError, DomainError, InvalidState, InvalidValue, UnknownId, Violation
from .fixtures import f01_board, f01_opening, f01_scenario, f01_supplied, mirror_state
from .ids import EventRef, FixtureId, FormationId, GroupId, LotId
from .profile import PacketParameters, Profile, Template
from .records import (
    AmmunitionAccount, Assault, AtExit, AwaitingPrincipal, Clock, Contact, Evacuate, Formation,
    FormationRound, GroupPivot, GroupStep, Hold, InFormation, Leg, Missile, MountLot, Move,
    ObjectiveStatus, OnCell, Opening, OpportunityUse, PersonnelLot, Phase, Pivot, Rally,
    Response, Rest, RoundLedger, SideState, SideTotals, Terminal, TerminalRecord, Withdraw,
    Work,
)
from .scenario import GroupSpec, Provenance, RosterEntry, Scenario
from .state import BattleState, validate_state
from .values import (
    Activation, AssaultOutcome, Assignment, Authority, CapturedCondition, Condition, Custody,
    DefeatClass, Disposition, End, FixtureClass, Hex, MoveEnd, MovementMode, ObjectiveKind,
    Orientation, PersonnelStatus, Posture, Recovery, ResponseKind, ResultKind, Serviceability,
    Side, TemplateKind, TerminalReason, TerminationPoint, Terrain, UseKind, Variant,
)

__all__ = [
    # identifiers (5.2)
    "FormationId", "GroupId", "LotId", "EventRef", "FixtureId",
    # enumerations (5.3-5.7)
    "Side", "End", "Orientation", "Variant", "Terrain", "TemplateKind", "Disposition",
    "PersonnelStatus", "CapturedCondition", "Serviceability", "Assignment", "Custody",
    "Recovery", "MovementMode", "Posture", "Authority", "Activation", "UseKind", "MoveEnd",
    "AssaultOutcome", "ResponseKind", "FixtureClass", "TerminalReason", "ResultKind",
    "DefeatClass", "TerminationPoint", "ObjectiveKind",
    # values and static records (5.4, 5.5, 6.1)
    "Hex", "EdgeRule", "Board", "Template", "PacketParameters", "Profile", "Provenance",
    "Scenario", "RosterEntry", "GroupSpec",
    # places (5.6)
    "InFormation", "OnCell", "AtExit",
    # dynamic records (6.2)
    "Clock", "SideState", "Condition", "Formation", "PersonnelLot", "MountLot",
    "AmmunitionAccount", "Contact",
    # legs and work records (6.4)
    "Leg", "Hold", "Move", "Pivot", "Assault", "Missile", "Withdraw", "Rally", "Rest",
    "Evacuate", "GroupStep", "GroupPivot", "Work",
    # ledger, response, terminal, phases (6.3)
    "OpportunityUse", "FormationRound", "Response", "RoundLedger", "ObjectiveStatus",
    "TerminalRecord", "SideTotals", "Opening", "AwaitingPrincipal", "Terminal", "Phase",
    # state and descriptors
    "BattleState", "FixtureDescriptor",
    # errors
    "DomainError", "InvalidValue", "InvalidState", "UnknownId", "DecodeError", "Violation",
    # construction, openings and descriptors (12.3)
    "f01_board", "f01_scenario", "f01_opening", "f01_supplied", "validate_state",
    "mirror_state", "DESCRIPTORS", "descriptor", "canonical_ids", "supplied_ids",
    # queries (12.4)
    "formation", "personnel_of", "mounts_of", "account_of", "contacts_of", "available",
    "wounded", "dead", "captured", "serviceable_assigned_mounts", "side_totals",
    "movement_mode", "movement_cost_kind", "direction_of", "terrain_cost", "entry_cost",
    "charge", "effort_charged", "effort_remaining", "projected_opening_effort",
    "effort_usable", "activation", "capacity_remaining", "projected_capacity",
    "usable_opportunities", "side_finished", "next_side", "response_allowance_unused",
    "response_possible", "rest_benefit_pending", "recovery_safe_now", "rest_order_exists",
    "full_safe_interval", "threat_sources", "objective_status", "viable_count",
    "onmap_available", "exit_available", "elapsed_minutes", "current_round", "end_of",
    "normalized_digest",
    # codec (12.5)
    "SCHEMA", "encode_state", "canonical_bytes", "digest", "decode_state", "decode_bytes",
]
