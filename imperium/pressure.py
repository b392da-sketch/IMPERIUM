"""Directed organizational pressure and joint percentile coupling."""

from dataclasses import dataclass
from functools import cache
from math import expm1, log1p

from .physical import Casualties, Draw, binomial, casualties
from .profiles import Profile
from .randomness import inverse_cdf


@dataclass(frozen=True)
class Packet:
    casualties: Casualties
    cohesion: int = 0
    morale: int = 0


def directed_packet(contribution: int, available: int, routing: bool,
                    profile: Profile, draw: Draw) -> Packet:
    # Share the injury percentile between the injury, cohesion and morale models
    # when the coupling gate selects it. Each channel is evaluated at most once.
    draws = cache(draw)
    physical = casualties(contribution, available, profile, draws)
    if not contribution or not available or routing:
        return Packet(physical)

    volume = contribution * profile.pressure_factor / profile.exposure_cap
    if volume == 0:
        return Packet(physical)
    cohesion_p = -expm1(log1p(-profile.cohesion_anchor) * volume)
    morale_p = -expm1(log1p(-profile.morale_anchor) * volume)
    coupled = profile.pressure_model == "J1" and (
        profile.kappa == 1 or (profile.kappa > 0 and draws("couple") < profile.kappa)
    )
    cohesion = inverse_cdf(binomial(2, cohesion_p),
                            lambda: draws("injury" if coupled else "cohesion"))
    morale = inverse_cdf(binomial(2, morale_p),
                          lambda: draws("injury" if coupled else "morale"))
    return Packet(physical, cohesion, morale)
