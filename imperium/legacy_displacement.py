"""Quarantined H32 diagnostic that admits vacated exit cells into arbitration."""

from .scheduler import Battle


class EarlyExitBattle(Battle):
    """Isolate early release of exiting primaries, preserving frozen threat."""

    def __init__(self, profile, seed, mirrored=False, **kwargs):
        super().__init__(profile, seed, mirrored, legacy=True, **kwargs)

    def arbitration_occupancy(self, field, exits):
        return field.occupied.difference(self.units[i].position for i in exits)
