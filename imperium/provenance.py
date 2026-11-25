"""Observation identity for the versioned research evidence."""

from .experiments import Run
from .fixture import FIXTURE_VERSION
from .profiles import PROFILE_VERSION, PROFILES

FROZEN = "frozen-v1"
EARLY_EXIT = "early-exit-v1"
EP08 = "D4-SHA256-v1"
H32 = "D47-H32-v1"


def observation(row):
    """Return the typed run configuration and its comparison context."""
    try:
        config = dict(row["run"])
        if config.keys() != {"profile", "seed", "policies", "mirrored"}:
            raise ValueError("run identity requires profile, seed, policies and orientation")
        config["policies"] = tuple(config["policies"])
        run = Run(**config)
        context = (row["fixture_version"], row["profile_version"],
                   row["stream"], row["resolver_variant"], run.mirrored)
    except (KeyError, TypeError) as error:
        raise ValueError("missing or invalid versioned observation identity (v2 evidence required)") from error
    if (run.profile not in PROFILES or len(run.policies) != 2
            or any(policy not in ("AGG", "ADV", "RES", "PASS") for policy in run.policies)
            or type(run.mirrored) is not bool):
        raise ValueError("invalid run configuration")
    if context[:2] != (FIXTURE_VERSION, PROFILE_VERSION):
        raise ValueError("unsupported fixture or profile version")
    if context[2:4] not in ((EP08, FROZEN), (H32, FROZEN), (H32, EARLY_EXIT)):
        raise ValueError("unsupported stream and resolver combination")
    return run, context


def compatible_rows(rows):
    """Report files must describe one provenance and orientation stratum."""
    seen = set()
    expected = None
    for row in rows:
        run, context = observation(row)
        if row.get("initial_fixture") != "default":
            raise ValueError("reports require the default experiment fixture")
        if expected is not None and context != expected:
            raise ValueError("incompatible observation provenance or orientation")
        expected = context
        if run in seen:
            raise ValueError(f"duplicate observation: {run}")
        seen.add(run)
        yield row, run
