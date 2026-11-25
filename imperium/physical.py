"""Finite physical outcome distributions and casualty partitions."""

from dataclasses import dataclass
from math import comb, expm1, fsum, log1p
from typing import Callable

from .profiles import Profile
from .randomness import inverse_cdf

Draw = Callable[[str], float]


def binomial(n: int, p: float) -> tuple[float, ...]:
    return tuple(comb(n, k) * p**k * (1 - p)**(n - k) for k in range(n + 1))


def beta_binomial(n: int, p: float, rho: float) -> tuple[float, ...]:
    if n == 0 or p in (0, 1) or rho == 0:
        return binomial(n, p)

    concentration = 1 / rho - 1
    alpha, beta = p * concentration, (1 - p) * concentration
    weights = [1.0]
    for k in range(n):
        ratio = (n - k) * (alpha + k) / ((k + 1) * (beta + n - k - 1))
        weights.append(weights[-1] * ratio)
    total = fsum(weights)
    return tuple(weight / total for weight in weights)


@dataclass(frozen=True)
class Casualties:
    killed: int
    wounded: int


def casualties(contribution: int, available: int, profile: Profile, draw: Draw) -> Casualties:
    exposure = min(available, profile.exposure_cap)
    if contribution == 0 or exposure == 0:
        return Casualties(0, 0)

    divisor = exposure if profile.exposure == "E1" else profile.exposure_cap
    p = -expm1(log1p(-profile.physical_anchor) * contribution / divisor)
    masses = (beta_binomial(exposure, p, profile.rho)
              if profile.injury_model == "O1" else binomial(exposure, p))
    injuries = inverse_cdf(masses, lambda: draw("injury"))
    killed = inverse_cdf(binomial(injuries, profile.killed_fraction), lambda: draw("fatal"))
    return Casualties(killed, injuries - killed)
