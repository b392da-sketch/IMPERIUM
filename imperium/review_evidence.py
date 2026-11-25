"""Compare regenerated RG02 evidence with the exact reviewed v1 corpus."""

import argparse
import json
from collections import Counter
from pathlib import Path

from .events import canonical_json
from .experiments import CONFIRMATION, MIRROR, POLICY, SCREENING
from .provenance import EARLY_EXIT, EP08, FROZEN, H32, observation

ADDED_FIELDS = {
    "defeat_subreasons", "fixture_version", "initial_fixture", "initial_state_sha256",
    "profile_version", "resolver_variant", "terminal_state_sha256", "trace_sha256",
}


def rows(directory, name):
    return list(map(json.loads, (directory / name).read_text().splitlines()))


def compare_run(old, new, config, stream, variant):
    actual, (_, _, actual_stream, actual_variant, _) = observation(new)
    expected = (config, stream, variant)
    if (actual, actual_stream, actual_variant) != expected or new["initial_fixture"] != "default":
        raise ValueError(f"invalid matrix identity: {expected}")
    old_fields = {key: value for key, value in new.items() if key not in ADDED_FIELDS}
    if canonical_json(old_fields) != canonical_json(
        {key: value for key, value in old.items() if key != "trace_sha256"}
    ):
        raise ValueError(f"run differs from reviewed mechanical evidence: {expected}")
    return new["trace_sha256"] != old["trace_sha256"]


def compare(baseline, current):
    counts = {}
    changed = Counter()
    for name, configs in (("screening", SCREENING), ("confirmation", CONFIRMATION), ("policy", POLICY)):
        for prefix, stream in (("", EP08), ("legacy-", H32)):
            label = prefix + name
            filename = label + ".jsonl"
            for old, new, config in zip(rows(baseline, filename), rows(current, filename),
                                        configs, strict=True):
                changed[label] += compare_run(old, new, config, stream, FROZEN)
            counts[label] = len(configs)

    filename = "legacy-displacement.jsonl"
    configs = [c for c in SCREENING if c.profile == "F6"]
    for old, new, config in zip(rows(baseline, filename), rows(current, filename),
                                configs, strict=True):
        if old["seed"] != config.seed or new["seed"] != config.seed:
            raise ValueError("legacy displacement pair identity mismatch")
        for name, variant in (("frozen", FROZEN), ("early_exit", EARLY_EXIT)):
            changed["legacy_displacement_executions"] += compare_run(
                old[name], new[name], config, H32, variant)
        frozen, early = new["frozen"], new["early_exit"]
        if frozen["terminal_state_sha256"] != early["terminal_state_sha256"] or any(
            frozen[key] != early[key] for key in frozen
            if key not in ("resolver_variant", "trace_sha256")
        ):
            raise ValueError(f"legacy displacement result divergence at seed {config.seed}")
    counts["legacy_displacement_executions"] = 2 * len(configs)

    policy = {r["run"]["seed"]: r for r in rows(current, "policy.jsonl")
              if r["run"]["policies"] == ["AGG", "RES"]}
    for old, new, (original, _) in zip(rows(baseline, "mirror.jsonl"), rows(current, "mirror.jsonl"),
                                       MIRROR, strict=True):
        if ((old["seed"], old["roots"]) != (new["seed"], new["roots"])
                or new["seed"] != original.seed
                or new["trace_sha256"] != policy[original.seed]["trace_sha256"]):
            raise ValueError("mirror evidence mismatch")
        changed["mirror_pairs"] += old["trace_sha256"] != new["trace_sha256"]
    counts["mirror_pairs"] = len(MIRROR)

    [replayed] = rows(current, "replay-sample/summary.json")
    [compared] = rows(current, "comparator-sample/summary.json")
    if replayed != policy[20000] or compared != rows(current, filename)[0]["early_exit"]:
        raise ValueError("committed replay artifacts do not match their matrix rows")

    military = [r for r in rows(current, "confirmation.jsonl") if r["reason"] == "military"]
    collapses = [r for r in military if r["defeat_subreasons"] == {str(1 - r["winner"]): "collapse"}]
    if len(military) != 8 or len(collapses) != len(military):
        raise ValueError("confirmation military classification mismatch")

    sample = "replay-sample/events.jsonl"
    roots = 0
    for old, new in zip(rows(baseline, sample), rows(current, sample), strict=True):
        projected = {k: v for k, v in new.items() if k not in ("resolver_variant", "stream")}
        projected["schema_version"] = old["schema_version"]
        projected["data"] = {k: v for k, v in projected["data"].items() if k != "defeat_subreasons"}
        if canonical_json(projected) != canonical_json(old):
            raise ValueError("mechanical event changed in reviewed replay sample")
        roots += 1
    aggregate_groups = 0
    for name in ("screening", "confirmation", "policy", "legacy-screening", "legacy-confirmation", "legacy-policy"):
        filename = name + "-report.json"
        old = json.loads((baseline / filename).read_text())
        new = json.loads((current / filename).read_text())
        if old.keys() != new.keys():
            raise ValueError(f"aggregate group identity changed for {name}")
        for group in old:
            if any(new[group][key] != value for key, value in old[group].items()):
                raise ValueError(f"existing aggregate changed for {name}, {group}")
            aggregate_groups += 1

    def paired(directory):
        return json.loads((directory / "confirmation-paired.json").read_text())

    old_paired, new_paired = paired(baseline), paired(current)
    for profile, old in old_paired["profiles"].items():
        new = new_paired["profiles"][profile]
        if old["matched_runs"] != new["matched_runs"] or any(
            old[key]["mean_difference"] != new[key]["mean_difference"]
            for key in ("unresolved", "casualties")
        ):
            raise ValueError(f"matched estimates changed for {profile}")

    return {"observations_compared": counts, "changed_trace_digests": dict(changed),
            "mechanical_summary_differences": 0, "projected_sample_roots_equal": roots,
            "aggregate_groups_verified": aggregate_groups,
            "confirmation_military_collapses": len(collapses)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    args = parser.parse_args()
    print(canonical_json(compare(args.baseline, args.current)))


if __name__ == "__main__":
    main()
