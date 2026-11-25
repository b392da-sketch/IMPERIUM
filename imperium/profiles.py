"""Immutable D4.7 profile definitions for the corrected research stream."""

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal

PROFILE_VERSION = "D47-RH1-v1"


@dataclass(frozen=True)
class Profile:
    name: str
    threshold: int = 6
    carry_exertion: bool = True
    initial_fatigue: int = 0
    allocation: Literal["B", "C"] = "B"
    exposure: Literal["E1", "C1"] = "E1"
    injury_model: Literal["B1", "O1"] = "B1"
    pressure_model: Literal["I1", "J1"] = "I1"
    pressure_factor: float = 1.0
    opportunities: int = 4
    formation_effort: int = 3
    exposure_cap: int = 24
    physical_anchor: float = 0.10
    killed_fraction: float = 0.25
    cohesion_anchor: float = 0.20
    morale_anchor: float = 0.15
    rho: float = 0.05
    kappa: float = 0.50


F6 = Profile("F6")
PROFILES = MappingProxyType({
    "R0": replace(F6, name="R0", threshold=3, carry_exertion=False, initial_fatigue=1),
    "F6": F6,
    "C": replace(F6, name="C", allocation="C"),
    "J": replace(F6, name="J", pressure_model="J1"),
    "O": replace(F6, name="O", injury_model="O1"),
    "N": replace(F6, name="N", exposure="C1"),
    "CJON": replace(F6, name="CJON", allocation="C", exposure="C1",
                    injury_model="O1", pressure_model="J1"),
    "LOW": replace(F6, name="LOW", allocation="C", exposure="C1", pressure_factor=0.5),
})
