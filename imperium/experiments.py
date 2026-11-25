"""Frozen development matrix declarations. Importing this module runs no battles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Run:
    profile: str
    seed: int
    policies: tuple[str, str]
    mirrored: bool = False

    def __post_init__(self) -> None:
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if 10000 <= self.seed <= 14095 or 30000 <= self.seed <= 31023:
            raise ValueError("reserved holdout seed")


SCREENING = tuple(
    Run(profile, seed, ("AGG", "AGG"))
    for profile in ("R0", "F6", "C", "J", "O", "N", "CJON", "LOW")
    for seed in range(20000, 20128)
)
CONFIRMATION = tuple(
    Run(profile, seed, ("AGG", "AGG"))
    for profile in ("R0", "F6", "CJON", "LOW")
    for seed in range(21000, 21512)
)
POLICY = tuple(
    Run("F6", seed, matchup)
    for matchup in (("ADV", "PASS"), ("AGG", "RES"), ("ADV", "RES"), ("AGG", "ADV"))
    for seed in range(20000, 20128)
)
MIRROR = tuple(
    (Run("F6", seed, ("AGG", "RES")), Run("F6", seed, ("AGG", "RES"), mirrored=True))
    for seed in range(20000, 20128)
)
