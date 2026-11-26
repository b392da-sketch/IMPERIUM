"""Layer 5: dynamic records, legs and work records, the round ledger, the
terminal record and the phases (contract 5.6, 6.2–6.4)."""

from dataclasses import dataclass

from .ids import EventRef, FormationId, GroupId, LotId
from .values import (
    AssaultOutcome, Assignment, Bool, CapturedCondition, Condition, Custody, DefeatClass,
    Disposition, EnumK, Fixed, Hex, IdK, Int, MoveEnd, MovementMode, ObjectiveKind, Opt,
    PersonnelStatus, Posture, RecK, Recovery, ResponseKind, ResultKind, Serviceability, Side,
    TerminalReason, TerminationPoint, UseKind, Var, register, validate_record,
)

_HEX = RecK((Hex,))
_FACING = Int("T08", 0, 5)
_FID = IdK(FormationId)


# --------------------------------------------------------------------------
# Places (union)


@dataclass(frozen=True, slots=True)
class InFormation:
    formation: FormationId

    def __post_init__(self):
        validate_record(self)


@dataclass(frozen=True, slots=True)
class OnCell:
    cell: Hex

    def __post_init__(self):
        validate_record(self)


@dataclass(frozen=True, slots=True)
class AtExit:
    side: Side

    def __post_init__(self):
        validate_record(self)


register(InFormation, (("formation", _FID),))
register(OnCell, (("cell", RecK((Hex,), "T11")),))
register(AtExit, (("side", EnumK(Side)),))

PLACE_CLASSES = (InFormation, OnCell, AtExit)
_PLACE = RecK(PLACE_CLASSES, "T11")


# --------------------------------------------------------------------------
# Dynamic state records (6.2)


@dataclass(frozen=True, slots=True)
class Clock:
    completed_rounds: int
    event_cursor: int

    def __post_init__(self):
        validate_record(self)


register(Clock, (
    ("completed_rounds", Int("T10", 0)),
    ("event_cursor", Int("T10", 0)),
))


@dataclass(frozen=True, slots=True)
class SideState:
    side: Side
    posture: Posture

    def __post_init__(self):
        validate_record(self)


register(SideState, (("side", EnumK(Side)), ("posture", EnumK(Posture))))


@dataclass(frozen=True, slots=True)
class Formation:
    formation: FormationId
    disposition: Disposition
    cell: Hex
    facing: int
    condition: Condition

    def __post_init__(self):
        validate_record(self)


register(Formation, (
    ("formation", _FID),
    ("disposition", EnumK(Disposition)),
    ("cell", _HEX),
    ("facing", _FACING),
    ("condition", RecK((Condition,))),
))


def _lot_extra(lot, lineage, count, status, captured, place, custodian, origin):
    if (status is PersonnelStatus.CAPTURED) != (captured is not None):
        return ("T13", "captured", "captured condition iff CAPTURED")
    if (status is PersonnelStatus.DEAD) != (custodian is None):
        return ("T13", "custodian", "custodian None iff DEAD")
    return None


@dataclass(frozen=True, slots=True)
class PersonnelLot:
    lot: LotId
    lineage: FormationId
    count: int
    status: PersonnelStatus
    captured: CapturedCondition | None
    place: object
    custodian: Side | None
    origin: EventRef | None

    def __post_init__(self):
        validate_record(self)


register(PersonnelLot, (
    ("lot", IdK(LotId)),
    ("lineage", _FID),
    ("count", Int("T10", 1)),
    ("status", EnumK(PersonnelStatus)),
    ("captured", Opt(EnumK(CapturedCondition))),
    ("place", _PLACE),
    ("custodian", Opt(EnumK(Side))),
    ("origin", Opt(IdK(EventRef))),
), _lot_extra)


@dataclass(frozen=True, slots=True)
class MountLot:
    lot: LotId
    formation: FormationId
    count: int
    serviceability: Serviceability
    assignment: Assignment
    place: object
    custodian: Side
    custody: Custody
    recovery: Recovery

    def __post_init__(self):
        validate_record(self)


register(MountLot, (
    ("lot", IdK(LotId)),
    ("formation", _FID),
    ("count", Int("T10", 1)),
    ("serviceability", EnumK(Serviceability)),
    ("assignment", EnumK(Assignment)),
    ("place", _PLACE),
    ("custodian", EnumK(Side)),
    ("custody", EnumK(Custody)),
    ("recovery", EnumK(Recovery)),
))


@dataclass(frozen=True, slots=True)
class AmmunitionAccount:
    formation: FormationId
    carried: int
    expended: int
    assignment: Assignment
    place: object
    custodian: Side
    custody: Custody
    recovery: Recovery

    def __post_init__(self):
        validate_record(self)


register(AmmunitionAccount, (
    ("formation", _FID),
    ("carried", Int("T10", 0)),
    ("expended", Int("T10", 0)),
    ("assignment", EnumK(Assignment)),
    ("place", _PLACE),
    ("custodian", EnumK(Side)),
    ("custody", EnumK(Custody)),
    ("recovery", EnumK(Recovery)),
))


@dataclass(frozen=True, slots=True)
class Contact:
    low: FormationId
    high: FormationId
    edge: tuple

    def __post_init__(self):
        validate_record(self)


register(Contact, (
    ("low", _FID),
    ("high", _FID),
    ("edge", Fixed((_HEX, _HEX))),
))


# --------------------------------------------------------------------------
# Legs and work records (6.4)


@dataclass(frozen=True, slots=True)
class Leg:
    origin: Hex
    destination: Hex
    facing: int
    mode: MovementMode

    def __post_init__(self):
        validate_record(self)


register(Leg, (
    ("origin", _HEX),
    ("destination", _HEX),
    ("facing", _FACING),
    ("mode", EnumK(MovementMode)),
))
_LEG = RecK((Leg,))


@dataclass(frozen=True, slots=True)
class Hold:
    def __post_init__(self):
        validate_record(self)


register(Hold, ())


def _move_extra(declared, legs, end):
    if not 1 <= len(declared) <= 3:
        return ("T15", "declared", "declared path must hold 1 to 3 cells")
    if not 1 <= len(legs) <= len(declared):
        return ("T15", "legs", "legs must number 1 to len(declared)")
    return None


@dataclass(frozen=True, slots=True)
class Move:
    declared: tuple
    legs: tuple
    end: MoveEnd

    def __post_init__(self):
        validate_record(self)


register(Move, (
    ("declared", Var(_HEX)),
    ("legs", Var(_LEG)),
    ("end", EnumK(MoveEnd)),
), _move_extra)


@dataclass(frozen=True, slots=True)
class Pivot:
    facing_before: int
    turn: int
    steps: int

    def __post_init__(self):
        validate_record(self)


register(Pivot, (
    ("facing_before", _FACING),
    ("turn", Int("T08", choices=(-1, 1))),
    ("steps", Int("T08", 1, 3)),
))


@dataclass(frozen=True, slots=True)
class Assault:
    target: FormationId
    origin: Hex
    target_cell: Hex
    facing: int
    mode: MovementMode
    outcome: AssaultOutcome

    def __post_init__(self):
        validate_record(self)


register(Assault, (
    ("target", _FID),
    ("origin", _HEX),
    ("target_cell", _HEX),
    ("facing", _FACING),
    ("mode", EnumK(MovementMode)),
    ("outcome", EnumK(AssaultOutcome)),
))


@dataclass(frozen=True, slots=True)
class Missile:
    target: FormationId
    origin: Hex
    target_cell: Hex
    facing: int

    def __post_init__(self):
        validate_record(self)


register(Missile, (
    ("target", _FID),
    ("origin", _HEX),
    ("target_cell", _HEX),
    ("facing", _FACING),
))


@dataclass(frozen=True, slots=True)
class Withdraw:
    leg: Leg

    def __post_init__(self):
        validate_record(self)


register(Withdraw, (("leg", _LEG),))


@dataclass(frozen=True, slots=True)
class Rally:
    def __post_init__(self):
        validate_record(self)


register(Rally, ())


@dataclass(frozen=True, slots=True)
class Rest:
    def __post_init__(self):
        validate_record(self)


register(Rest, ())


@dataclass(frozen=True, slots=True)
class Evacuate:
    cell: Hex

    def __post_init__(self):
        validate_record(self)


register(Evacuate, (("cell", _HEX),))


@dataclass(frozen=True, slots=True)
class GroupStep:
    leg: Leg

    def __post_init__(self):
        validate_record(self)


register(GroupStep, (("leg", _LEG),))


@dataclass(frozen=True, slots=True)
class GroupPivot:
    facing_before: int
    turn: int

    def __post_init__(self):
        validate_record(self)


register(GroupPivot, (
    ("facing_before", _FACING),
    ("turn", Int("T08", choices=(-1, 1))),
))

WORK_CLASSES = (Hold, Move, Pivot, Assault, Missile, Withdraw, Rally, Rest, Evacuate, GroupStep, GroupPivot)
Work = Hold | Move | Pivot | Assault | Missile | Withdraw | Rally | Rest | Evacuate | GroupStep | GroupPivot
_WORK = RecK(WORK_CLASSES)


# --------------------------------------------------------------------------
# Ledger, response, terminal record and phases (6.3)


@dataclass(frozen=True, slots=True)
class Response:
    kind: ResponseKind
    target: FormationId

    def __post_init__(self):
        validate_record(self)


register(Response, (("kind", EnumK(ResponseKind)), ("target", _FID)))


def _use_extra(side, kind, group, members, work):
    if kind is UseKind.INDIVIDUAL:
        if group is not None:
            return ("T12", "group", "an individual use names no group")
        if len(members) != 1:
            return ("T12", "members", "an individual use has one member")
    elif kind is UseKind.GROUP:
        if group is None:
            return ("T12", "group", "a group use names its group")
        if not 2 <= len(members) <= 3:
            return ("T12", "members", "a group use has 2 or 3 members")
    else:
        if group is not None:
            return ("T12", "group", "a pass or posture use names no group")
        if members:
            return ("T12", "members", "a pass or posture use has no members")
        if work:
            return ("T12", "work", "a pass or posture use has no work")
    if len(work) != len(members):
        return ("T12", "work", "one work record per member")
    return None


@dataclass(frozen=True, slots=True)
class OpportunityUse:
    side: Side
    kind: UseKind
    group: GroupId | None
    members: tuple
    work: tuple

    def __post_init__(self):
        validate_record(self)


register(OpportunityUse, (
    ("side", EnumK(Side)),
    ("kind", EnumK(UseKind)),
    ("group", Opt(IdK(GroupId))),
    ("members", Var(_FID, key=((),))),
    ("work", Var(_WORK)),
), _use_extra)


@dataclass(frozen=True, slots=True)
class FormationRound:
    formation: FormationId
    opened_eligible: bool
    response: Response | None
    displacement_attempted: bool
    safe_latch: bool
    incoming: bool
    incoming_since_rally: bool
    exerted: bool
    displaced: bool

    def __post_init__(self):
        validate_record(self)


register(FormationRound, (
    ("formation", _FID),
    ("opened_eligible", Bool()),
    ("response", Opt(RecK((Response,)))),
    ("displacement_attempted", Bool()),
    ("safe_latch", Bool()),
    ("incoming", Bool()),
    ("incoming_since_rally", Bool()),
    ("exerted", Bool()),
    ("displaced", Bool()),
))


@dataclass(frozen=True, slots=True)
class RoundLedger:
    uses: tuple
    formations: tuple

    def __post_init__(self):
        validate_record(self)


register(RoundLedger, (
    ("uses", Var(RecK((OpportunityUse,)))),
    ("formations", Var(RecK((FormationRound,)))),
))


@dataclass(frozen=True, slots=True)
class ObjectiveStatus:
    kind: ObjectiveKind
    side: Side | None

    def __post_init__(self):
        validate_record(self)


register(ObjectiveStatus, (("kind", EnumK(ObjectiveKind)), ("side", Opt(EnumK(Side)))))


def _terminal_extra(reason, result, winner, defeat, point, charged_rounds, objective,
                    postures, viable, onmap_available, exit_available):
    if (result is ResultKind.VICTORY) != (winner is not None):
        return ("T14", "winner", "winner set iff VICTORY")
    return None


_DEFEAT = Opt(EnumK(DefeatClass))
_COUNT = Int("T10", 0)
_POSTURE = EnumK(Posture)


@dataclass(frozen=True, slots=True)
class TerminalRecord:
    reason: TerminalReason
    result: ResultKind
    winner: Side | None
    defeat: tuple
    point: TerminationPoint
    charged_rounds: int
    objective: ObjectiveStatus
    postures: tuple
    viable: tuple
    onmap_available: tuple
    exit_available: tuple

    def __post_init__(self):
        validate_record(self)


register(TerminalRecord, (
    ("reason", EnumK(TerminalReason)),
    ("result", EnumK(ResultKind)),
    ("winner", Opt(EnumK(Side))),
    ("defeat", Fixed((_DEFEAT, _DEFEAT))),
    ("point", EnumK(TerminationPoint)),
    ("charged_rounds", _COUNT),
    ("objective", RecK((ObjectiveStatus,))),
    ("postures", Fixed((_POSTURE, _POSTURE))),
    ("viable", Fixed((_COUNT, _COUNT))),
    ("onmap_available", Fixed((_COUNT, _COUNT))),
    ("exit_available", Fixed((_COUNT, _COUNT))),
), _terminal_extra)


@dataclass(frozen=True, slots=True)
class Opening:
    def __post_init__(self):
        validate_record(self)


register(Opening, ())


@dataclass(frozen=True, slots=True)
class AwaitingPrincipal:
    side: Side

    def __post_init__(self):
        validate_record(self)


register(AwaitingPrincipal, (("side", EnumK(Side)),))


@dataclass(frozen=True, slots=True)
class Terminal:
    record: TerminalRecord

    def __post_init__(self):
        validate_record(self)


register(Terminal, (("record", RecK((TerminalRecord,))),))

PHASE_CLASSES = (Opening, AwaitingPrincipal, Terminal)
Phase = Opening | AwaitingPrincipal | Terminal

UNION_CLASSES = frozenset(PHASE_CLASSES + PLACE_CLASSES + WORK_CLASSES)


@dataclass(frozen=True, slots=True)
class SideTotals:
    """A derived, never-stored summary (12.1)."""

    available: int
    wounded: int
    dead: int
    captured: int
    mounts: int
    ammunition_carried: int

    def __post_init__(self):
        validate_record(self)


register(SideTotals, tuple((n, Int()) for n in (
    "available", "wounded", "dead", "captured", "mounts", "ammunition_carried")))


# --------------------------------------------------------------------------
# The state's own fields (6.2), used by the state module and the decoder

STATE_FIELDS = (
    "scenario", "phase", "clock", "sides", "formations", "authority",
    "personnel", "mounts", "ammunition", "contacts", "ledger",
)
