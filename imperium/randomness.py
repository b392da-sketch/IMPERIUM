"""EP08 deterministic, stateless SHA-256 draws."""

import hashlib
import json
from dataclasses import dataclass
from typing import Callable

RANDOM_VERSION = "D4-SHA256-v1"


@dataclass(frozen=True)
class DrawKey:
    seed: int
    fixture_pair: str
    replicate: int
    stage: str
    channel: str
    index: int = 0

    def integer(self) -> int:
        if any(type(value) is not int or value < 0
               for value in (self.seed, self.replicate, self.index)):
            raise ValueError("draw numeric fields must be nonnegative integers")
        if not all(value.isascii() for value in (self.fixture_pair, self.stage, self.channel)):
            raise ValueError("draw identifiers must be ASCII")
        data = [RANDOM_VERSION, self.seed, self.fixture_pair, self.replicate,
                self.stage, self.channel, self.index]
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return int.from_bytes(hashlib.sha256(payload).digest()[:7], "big") >> 3

    def uniform(self) -> float:
        return self.integer() / 2**53


def melee_stage(round_number: int, side: int, opportunity: int,
                attacker: int, target: int, source: int) -> str:
    return f"r{round_number}/s{side}/o{opportunity}/a{attacker}/t{target}/src{source}"


def inverse_cdf(masses: tuple[float, ...], draw: Callable[[], float]) -> int:
    support = [outcome for outcome, mass in enumerate(masses) if mass > 0]
    if len(support) == 1:
        return support[0]
    percentile = draw()
    cumulative = 0.0
    for outcome in support:
        cumulative += masses[outcome]
        if cumulative > percentile:
            return outcome
    # Rounding can put the computed final cumulative slightly below one.
    return support[-1]
