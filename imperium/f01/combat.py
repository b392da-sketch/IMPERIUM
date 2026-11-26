"""D4-RP-0.1 full-template exposure and directed combat packets."""

from math import expm1, log1p
from typing import Literal

from ..physical import Casualties, Draw, binomial
from ..pressure import Packet
from ..randomness import DrawKey, inverse_cdf
from .fixture import Formation

Stage = Literal["melee", "missile"]


def contribution(source: Formation, stage: Stage, contacts: int = 0) -> int:
    if source.disposition == "routing" or source.available == 0:
        return 0
    template = source.identity.template
    slots = min(source.available, template.slots)
    if stage == "missile":
        return slots if template.missile_range and not contacts else 0
    return min(template.edge_capacity, slots // contacts) if contacts else 0


def packet(allocated: int, target: Formation, stage: Stage, draw: Draw) -> Packet:
    template = target.identity.template
    nominal = template.slots if stage == "missile" else template.edge_capacity
    exposed = min(target.available, nominal)
    if not (allocated and exposed):
        return Packet(Casualties(0, 0))
    p0, c0, m0, divisor = (.05, .12, .10, 40) if stage == "missile" else (.10, .20, .15, 24)

    def sample(trials, anchor, intensity, channel):
        p = -expm1(log1p(-anchor) * intensity)
        return inverse_cdf(binomial(trials, p), lambda: draw(channel))

    injured = sample(exposed, p0, allocated / exposed, "injury")
    killed = inverse_cdf(binomial(injured, .25), lambda: draw("fatal"))
    casualties = Casualties(killed, injured - killed)
    if target.disposition == "routing":
        return Packet(casualties)
    volume = allocated / divisor
    return Packet(casualties, sample(2, c0, volume, "cohesion"),
                  sample(2, m0, volume, "morale"))


KEY_VERSION = "F01-stage-v1"


def effect_key(seed: int, fixture: str, round_number: int, root: int, leg: int,
               stage: Stage, response: bool, source: int, target: int, channel: str) -> DrawKey:
    """Use an accepted-root ordinal, actual leg, and directed logical identities."""
    key = (f"{KEY_VERSION}/r{round_number}/root{root}/leg{leg}/"
           f"{'response' if response else 'principal'}/{stage}/{source}>{target}")
    return DrawKey(seed, fixture, seed, key, channel)
