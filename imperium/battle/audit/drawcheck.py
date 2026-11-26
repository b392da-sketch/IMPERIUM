"""The isolated draw-record validator (P3 contract rev 0.3 section 10, ER03).

Pure, with no production caller and no dependency on engine types. It is
never applied to audit-wire events: audit v1 journals are draw-free.
"""

from . import rules
from .errors import DrawRecordError

CHANNELS = ("cohesion", "couple", "fatal", "injury", "latent", "morale", "policy")
INDEX_MAX = 63
NUMERATOR_LIMIT = 2 ** 53
RUN_MAX = 2 ** 63 - 1


def check_draw_records(run, pair, stage_id, records):
    """Raise ``DrawRecordError`` at the first fault (ER03 order); else None."""
    if type(records) is not tuple or not records:
        raise DrawRecordError("DR07", "/records", "expected a nonempty tuple")
    for i, r in enumerate(records):
        if type(r) is not tuple or len(r) != 3:
            raise DrawRecordError("DR07", f"/records/{i}", "expected a three-element tuple")
    if (type(run) is not tuple or len(run) != 2
            or any(type(v) is not int or not 0 <= v <= RUN_MAX for v in run)):
        raise DrawRecordError("DR03", "/run", "null or malformed run")
    if type(pair) is not str or pair not in rules.PAIRS:
        raise DrawRecordError("DR01", "/pair", "wrong type or unregistered pair")
    if rules.packet_id(stage_id) is None:
        raise DrawRecordError("DR02", "/stage_id", "not a BK-1 packet stage id")
    for i, (channel, index, _) in enumerate(records):
        if type(channel) is not str or channel not in CHANNELS:
            raise DrawRecordError("DR01", f"/records/{i}/0", "unregistered channel")
        if type(index) is not int or not 0 <= index <= INDEX_MAX:
            raise DrawRecordError("DR01", f"/records/{i}/1", "index outside 0..63")
    for i in range(1, len(records)):
        if not records[i - 1][:2] < records[i][:2]:
            raise DrawRecordError("DR04", f"/records/{i}", "records not strictly increasing")
    for i, (_, _, numerator) in enumerate(records):
        if type(numerator) is not int or not 0 <= numerator < NUMERATOR_LIMIT:
            raise DrawRecordError("DR05", f"/records/{i}/2", "numerator outside 0..2**53-1")
    seed, replicate = run
    for i, (channel, index, numerator) in enumerate(records):
        if rules.ep08(seed, pair, replicate, stage_id, channel, index) != numerator:
            raise DrawRecordError("DR06", f"/records/{i}/2", "numerator disagrees")
