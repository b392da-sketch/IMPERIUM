"""Canonical EF09-RH1 state and event serialization."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .fixture import FIXTURE_VERSION, Encounter
from .profiles import PROFILE_VERSION
from .geometry import mirror
from .provenance import EP08, FROZEN

SCHEMA_VERSION = "EF09-RH1-events-v2"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=True)


def state_digest(encounter: Encounter, *, round_state: dict[str, Any], mirrored: bool = False) -> str:
    """Hash canonical state, including caller-supplied scheduler bookkeeping."""
    formations = []
    for formation in sorted(encounter.formations, key=lambda item: item.identity.formation_id):
        record = vars(formation).copy()
        record["identity"] = vars(formation.identity)
        if mirrored:
            record["physical_side"] ^= 1
            record["facing"] = (record["facing"] + 3) % 6
            if record["position"] is not None:
                record["position"] = mirror(record["position"])
        formations.append(record)
    state = {
        "formations": formations,
        "contacts": sorted(encounter.contacts),
        "round_state": round_state,
    }
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Event:
    profile_id: str
    root_seed: int
    round: int
    root_action_id: int
    stage_id: int
    event_kind: str
    state_before_digest: str
    state_after_digest: str
    source_id: int | None = None
    target_id: int | None = None
    semantic_random_key: tuple[str | int, ...] | None = None
    data: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    fixture_version: str = FIXTURE_VERSION
    profile_version: str = PROFILE_VERSION
    stream: str = EP08
    resolver_variant: str = FROZEN


def jsonl(events: Iterable[Event]) -> str:
    """Encode in resolver order; object keys are independently canonical."""
    return "".join(canonical_json(asdict(event)) + "\n" for event in events)
