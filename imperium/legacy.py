"""D47-H32-v1 compatibility stream, used only by explicit legacy diagnostics."""

CHANNELS = {"injury": "x", "fatal": "k", "cohesion": "c", "morale": "m", "couple": "j"}
MASK = 2**32 - 1


def legacy_draw(seed: int, stage: str, channel: str) -> int:
    value = (2166136261 ^ seed) & MASK
    for char in f"{stage}|{CHANNELS[channel]}":
        value = ((value ^ ord(char)) * 16777619) & MASK
    value = ((value ^ (value >> 16)) * 0x85EBCA6B) & MASK
    value = ((value ^ (value >> 13)) * 0xC2B2AE35) & MASK
    return value ^ (value >> 16)
