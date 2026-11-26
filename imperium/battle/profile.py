"""Layer 3: templates, packet parameters, the profile record and the frozen
registered profile D4-RP-0.1 (contract 5.5, 7.3)."""

from dataclasses import dataclass
from fractions import Fraction

from .errors import InvalidValue
from .values import (
    Bool, EnumK, Fixed, Frac, Int, MovementMode, Opt, RecK, Str, TemplateKind,
    register, validate_record,
)


@dataclass(frozen=True, slots=True)
class Template:
    kind: TemplateKind
    personnel: int
    mounts: int
    ammunition: int
    frontage_dm: int
    pitch_dm: int
    edge_capacity: int
    missile_range: int | None
    max_steps: int
    open_cost: int
    rough_cost: int
    melee_capable: bool
    foot_fallback: TemplateKind | None

    def __post_init__(self):
        validate_record(self)


register(Template, (
    ("kind", EnumK(TemplateKind)),
    ("personnel", Int()),
    ("mounts", Int()),
    ("ammunition", Int()),
    ("frontage_dm", Int()),
    ("pitch_dm", Int()),
    ("edge_capacity", Int()),
    ("missile_range", Opt(Int())),
    ("max_steps", Int()),
    ("open_cost", Int()),
    ("rough_cost", Int()),
    ("melee_capable", Bool()),
    ("foot_fallback", Opt(EnumK(TemplateKind))),
))


@dataclass(frozen=True, slots=True)
class PacketParameters:
    melee_p0: Fraction
    missile_p0: Fraction
    fatal_share: Fraction
    melee_pressure: tuple
    missile_pressure: tuple
    melee_a_ref: int
    missile_a_ref: int
    allocation: str
    injury: str
    exposure: str
    pressure: str

    def __post_init__(self):
        validate_record(self)


register(PacketParameters, (
    ("melee_p0", Frac()),
    ("missile_p0", Frac()),
    ("fatal_share", Frac()),
    ("melee_pressure", Fixed((Frac(), Frac()))),
    ("missile_pressure", Fixed((Frac(), Frac()))),
    ("melee_a_ref", Int()),
    ("missile_a_ref", Int()),
    ("allocation", Str()),
    ("injury", Str()),
    ("exposure", Str()),
    ("pressure", Str()),
))


@dataclass(frozen=True, slots=True)
class Profile:
    profile_id: str
    templates: tuple
    opportunities: int
    effort: int
    principal_per_round: int
    responses_per_round: int
    responses_per_root: int
    exertion_threshold: int
    exertion_carry: bool
    exertion_cleared_by: str
    displacement_attempts: int
    rounds: int
    round_minutes: int
    hex_pitch_m: int
    packet: PacketParameters

    def __post_init__(self):
        validate_record(self)


_TEMPLATE = RecK((Template,))

register(Profile, (
    ("profile_id", Str()),
    ("templates", Fixed((_TEMPLATE, _TEMPLATE, _TEMPLATE))),
    ("opportunities", Int()),
    ("effort", Int()),
    ("principal_per_round", Int()),
    ("responses_per_round", Int()),
    ("responses_per_root", Int()),
    ("exertion_threshold", Int()),
    ("exertion_carry", Bool()),
    ("exertion_cleared_by", Str()),
    ("displacement_attempts", Int()),
    ("rounds", Int()),
    ("round_minutes", Int()),
    ("hex_pitch_m", Int()),
    ("packet", RecK((PacketParameters,))),
))


# --------------------------------------------------------------------------
# The registered profile D4-RP-0.1 (5.5), as literal data

HEAVY_TEMPLATE = Template(TemplateKind.HEAVY, 240, 0, 2, 600, 15, 24, 1, 2, 1, 2, True, None)
LIGHT_TEMPLATE = Template(TemplateKind.LIGHT, 120, 0, 4, 450, 20, 18, 2, 2, 1, 1, True, None)
MOUNTED_TEMPLATE = Template(
    TemplateKind.MOUNTED, 80, 80, 0, 600, 30, 12, None, 3, 1, 3, True, TemplateKind.HEAVY
)

D4_RP_0_1 = Profile(
    profile_id="D4-RP-0.1",
    templates=(HEAVY_TEMPLATE, LIGHT_TEMPLATE, MOUNTED_TEMPLATE),
    opportunities=4,
    effort=3,
    principal_per_round=1,
    responses_per_round=1,
    responses_per_root=1,
    exertion_threshold=6,
    exertion_carry=True,
    exertion_cleared_by="COMPLETED_REST",
    displacement_attempts=1,
    rounds=12,
    round_minutes=10,
    hex_pitch_m=65,
    packet=PacketParameters(
        melee_p0=Fraction(1, 10),
        missile_p0=Fraction(1, 20),
        fatal_share=Fraction(1, 4),
        melee_pressure=(Fraction(1, 5), Fraction(3, 20)),
        missile_pressure=(Fraction(3, 25), Fraction(1, 10)),
        melee_a_ref=24,
        missile_a_ref=40,
        allocation="B",
        injury="B1",
        exposure="E1",
        pressure="I1",
    ),
)

PROFILES = {"D4-RP-0.1": D4_RP_0_1}

TEMPLATES = {t.kind: t for t in D4_RP_0_1.templates}

# Nominal step caps per movement mode (7.4 item 11): heavy 2, light 2,
# mounted 3, mixed foot 2 (the heavy cap, R3.3-04).


def movement_cost_kind(mode, template):
    """Cost kind of a template moving in ``mode`` (7.3); raises R24."""
    if mode is MovementMode.FOOT and (template is TemplateKind.HEAVY or template is TemplateKind.LIGHT):
        return template
    if template is TemplateKind.MOUNTED:
        if mode is MovementMode.MOUNTED:
            return TemplateKind.MOUNTED
        if mode is MovementMode.MIXED_FOOT:
            return TemplateKind.HEAVY
    raise InvalidValue("R24", "mode", "mode incompatible with template")


def mode_compatible(mode, template):
    if template is TemplateKind.MOUNTED:
        return mode is MovementMode.MOUNTED or mode is MovementMode.MIXED_FOOT
    return mode is MovementMode.FOOT


def step_cap(mode, template):
    """Nominal step cap of ``mode`` for ``template`` (compatible pair)."""
    return TEMPLATES[movement_cost_kind(mode, template)].max_steps
