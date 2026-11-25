"""Pure condition arithmetic for the reduced model."""

from dataclasses import dataclass
from typing import Literal

from .fixture import Disposition
from .profiles import Profile

Transition = Literal["depleted", "rout", "repulse", "none"]


@dataclass(frozen=True)
class Assessment:
    cohesion: int
    morale: int
    transition: Transition


def assess(available: int, disposition: Disposition, cohesion: int, morale: int,
           delta_cohesion: int, delta_morale: int, *, melee: bool) -> Assessment:
    if available == 0:
        return Assessment(cohesion, morale, "depleted")

    new_cohesion = min(2, cohesion + delta_cohesion)
    new_morale = min(2, morale + delta_morale)
    positive_pressure = delta_cohesion > 0 or delta_morale > 0
    if (positive_pressure and disposition in ("organized", "reforming")
            and new_cohesion == new_morale == 2):
        return Assessment(new_cohesion, new_morale, "rout")
    if (melee and disposition == "organized"
            and (cohesion < new_cohesion == 2 or morale < new_morale == 2)):
        return Assessment(new_cohesion, new_morale, "repulse")
    return Assessment(new_cohesion, new_morale, "none")


def exert(fatigue: int, remainder: int, marks: int, profile: Profile) -> tuple[int, int]:
    increases, next_remainder = divmod(remainder + marks, profile.threshold)
    return min(2, fatigue + increases), next_remainder
