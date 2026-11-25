"""Run, replay and aggregate the EF09-RH1 development comparisons."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median, stdev

from .events import canonical_json, jsonl
from .experiments import CONFIRMATION, MIRROR, POLICY, SCREENING, Run
from .policies import choose
from .fixture import FIXTURE_VERSION, INTERVAL_MINUTES, Encounter, Formation, Identity
from .profiles import PROFILE_VERSION, PROFILES
from .provenance import EARLY_EXIT, EP08, FROZEN, H32, compatible_rows, observation
from .reporting import describe, paired_continuous
from .scheduler import Action, Battle


def simulate(config, *, legacy=False, scripted=None, variant=FROZEN, encounter=None):
    profile = PROFILES[config.profile]
    initial = deepcopy(encounter)
    if variant == EARLY_EXIT and legacy:
        from .legacy_displacement import EarlyExitBattle
        battle = EarlyExitBattle(profile, config.seed, config.mirrored, encounter=initial)
    elif variant == FROZEN:
        battle = Battle(profile, config.seed, config.mirrored, legacy=legacy, encounter=initial)
    else:
        raise ValueError("unsupported stream and resolver combination")
    release = [False, False]
    counts = []
    if scripted is not None:
        for action in scripted:
            battle.resolve(action)
        if battle.terminal is None:
            raise ValueError("incomplete replay")
    else:
        while not battle.terminal:
            side = battle.side
            action, count, release[side] = choose(battle, config.policies[side], release[side])
            counts.append(count)
            battle.resolve(action)

    return battle, counts


def summarize(config, battle, counts, trace):
    totals = Counter()
    for f in battle.ordered():
        totals["available"] += f.available_personnel
        totals["killed"] += f.killed_personnel
        totals["wounded"] += f.wounded_unavailable_personnel
    secured = [0, 0]
    streak = [0, 0]
    longest = [0, 0]
    for checkpoint in (p for p in battle.objectives if p["stage"] == "closure"):
        for side in (0, 1):
            streak[side] = streak[side] + 1 if checkpoint["secure"] == side else 0
            secured[side] += int(checkpoint["secure"] == side)
            longest[side] = max(longest[side], streak[side])

    secure_events = [p for p in battle.objectives if p["secure"] is not None]
    return {
        "run": asdict(config), "stream": H32 if battle.legacy else EP08,
        "resolver_variant": battle.resolver_variant, "fixture_version": FIXTURE_VERSION,
        "profile_version": PROFILE_VERSION,
        "trace_sha256": hashlib.sha256(trace.encode()).hexdigest(), "charged_rounds": battle.round,
        "initial_fixture": "explicit" if battle.explicit_fixture else "default",
        "initial_state_sha256": battle.initial_state_digest, "terminal_state_sha256": battle.digest(),
        "defeat_subreasons": battle.defeat_subreasons,
        "elapsed_minutes": battle.round * INTERVAL_MINUTES, "winner": battle.terminal[0], "reason": battle.terminal[1],
        "personnel": dict(totals), "round_three_exhaustion": battle.exhaustion,
        "objective": battle.objective(), "secure_closures": secured, "longest_secure_streak": longest,
        "first_secure": secure_events[0] if secure_events else None,
        "last_secure": secure_events[-1] if secure_events else None,
        "metrics": dict(battle.metrics), "preferred_choices": counts,
    }


def run_task(task):
    config, legacy = task
    try:
        battle, counts = simulate(config, legacy=legacy)
        trace = jsonl(battle.events)
        return summarize(config, battle, counts, trace)
    except Exception as exc:
        raise RuntimeError(f"failed run {config!r}, legacy={legacy}") from exc


def legacy_displacement_task(config):
    results = []
    for variant in (FROZEN, EARLY_EXIT):
        battle, counts = simulate(config, legacy=True, variant=variant)
        trace = jsonl(battle.events)
        results.append(summarize(config, battle, counts, trace))
    return {"seed": config.seed, "frozen": results[0], "early_exit": results[1]}


def mirror_task(pair):
    original, transformed = pair
    left, _ = simulate(original)
    right, _ = simulate(transformed)
    for a, b in zip(left.events, right.events):
        if a != b:
            raise ValueError(f"mirror divergence at seed {original.seed}, root {a.root_action_id}")
    if len(left.events) != len(right.events) or left.digest() != right.digest():
        raise ValueError(f"mirror final divergence at seed {original.seed}")
    trace = jsonl(left.events)
    return {"seed": original.seed, "roots": len(left.events),
            "trace_sha256": hashlib.sha256(trace.encode()).hexdigest()}


def dump_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(canonical_json(row) + "\n")
    temporary.replace(path)


def report(rows):
    groups = {}
    for row, run in compatible_rows(rows):
        groups.setdefault((run.profile, "/".join(run.policies)), []).append(row)
    result = {}
    for (profile, matchup), group in groups.items():
        n = len(group)
        unresolved = sum(row["reason"] == "unresolved" for row in group)
        p = unresolved / n
        z = 1.959963984540054
        center = (p + z*z/(2*n)) / (1 + z*z/n)
        margin = z * (p*(1-p)/n + z*z/(4*n*n))**0.5 / (1 + z*z/n)
        metrics = sorted(set().union(*(row["metrics"].keys() for row in group)) - {"first_rout"})
        fatigue = [[row["round_three_exhaustion"][s]
                    for row in group if row["round_three_exhaustion"] is not None] for s in (0, 1)]
        fatigue_fractions = [[num / den for num, den in side if den] for side in fatigue]
        casualty_counts = [row["personnel"]["killed"] + row["personnel"]["wounded"] for row in group]
        rout_rounds = [row["metrics"]["first_rout"] for row in group if "first_rout" in row["metrics"]]
        choice_counts = [value for row in group for value in row["preferred_choices"]]
        subreasons = Counter(reason for row in group for reason in row["defeat_subreasons"].values())
        result[f"{profile} {matchup}"] = {
            "runs": n, "attempted_runs": n, "completed_runs": n,
            "technical_stops": 0, "unresolved_denominator": n, "wins_draws": dict(Counter(str(row["winner"]) for row in group)),
            "terminal_reasons": dict(Counter(row["reason"] for row in group)),
            "defeat_subreasons_by_side_ending": dict(subreasons),
            "objective": dict(Counter(row["objective"]["classification"] for row in group)),
            "objective_flags": {key: sum(row["objective"].get(key, False) for row in group)
                                for key in ("condition", "contact", "threat")},
            "unresolved_wilson95": [max(0., center-margin), min(1., center+margin)],
            "bm07_warning": p > .75 if "PASS" not in matchup else None,
            "mean_rounds": mean(row["charged_rounds"] for row in group),
            "median_rounds": median(row["charged_rounds"] for row in group),
            "mean_losses": mean(casualty_counts), "median_losses": median(casualty_counts),
            "losses_descriptive": describe(casualty_counts),
            "preferred_choices_descriptive": describe(choice_counts),
            "losses_min_max": [min(casualty_counts), max(casualty_counts)],
            "median_first_rout_round": median(rout_rounds) if rout_rounds else None,
            "mean_preferred_choices": mean(choice_counts) if choice_counts else None,
            "mean_metrics": {key: mean(row["metrics"].get(key, 0) for row in group) for key in metrics},
            "mean_round_three_exhaustion": [mean(side) if side else None for side in fatigue_fractions],
            "median_round_three_exhaustion": [median(side) if side else None for side in fatigue_fractions],
            "round_three_exhaustion_gt_half": [sum(value > .5 for value in side)
                                               for side in fatigue_fractions],
            "round_three_defined_runs": [sum(den > 0 for _, den in side) for side in fatigue],
        }
    return result


def paired_report(rows, baseline):
    profiles = {}
    matchup = None
    for row, run in compatible_rows(rows):
        if matchup is not None and matchup != run.policies:
            raise ValueError("paired comparison requires one policy matchup")
        matchup = run.policies
        profiles.setdefault(run.profile, {})[run.seed] = row
    if baseline not in profiles or len(profiles) < 2 or len(profiles[baseline]) < 2:
        raise ValueError("paired comparison requires a baseline and comparator with at least two seeds")
    reference = profiles[baseline]
    result = {}
    for profile, sample in profiles.items():
        if profile == baseline:
            continue
        if sample.keys() != reference.keys():
            raise ValueError(f"unmatched seeds for {profile} against {baseline}")
        keys = sorted(reference)
        changes = {
            "unresolved": [int(sample[k]["reason"] == "unresolved")
                           - int(reference[k]["reason"] == "unresolved") for k in keys],
            "casualties": [sum(sample[k]["personnel"][kind] - reference[k]["personnel"][kind]
                               for kind in ("killed", "wounded")) for k in keys],
        }
        result[profile] = {"matched_runs": len(keys)}
        for metric, differences in changes.items():
            average = mean(differences)
            if metric == "casualties":
                result[profile][metric] = {"mean_difference": average,
                                          **paired_continuous(differences)}
            else:
                margin = 1.959963984540054 * stdev(differences) / len(keys)**0.5
                result[profile][metric] = {"mean_difference": average, **describe(differences),
                                          "normal_approximation_95": [average-margin, average+margin]}
    return {"baseline": baseline, "profiles": result}


def write_run(directory, config, battle, counts, *, initial=None):
    trace = jsonl(battle.events)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "events.jsonl").write_text(trace, encoding="utf-8")
    dump_rows(directory / "summary.json", [summarize(config, battle, counts, trace)])
    dump_rows(directory / "actions.jsonl", map(asdict, battle.actions))
    initial_path = directory / "initial-state.json"
    if initial is not None:
        dump_rows(initial_path, [{
            "formations": [asdict(formation) for formation in initial.formations],
            "contacts": sorted(initial.contacts),
        }])
    else:
        initial_path.unlink(missing_ok=True)


def read_initial_fixture(path):
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    formations = []
    for row in data["formations"]:
        fields = dict(row)
        fields["identity"] = Identity(**fields["identity"])
        if fields["position"] is not None:
            fields["position"] = tuple(fields["position"])
        formations.append(Formation(**fields))
    return Encounter(tuple(formations), set(map(tuple, data["contacts"])))


def replay_run(directory, expected_variant=None):
    summary = json.loads((directory / "summary.json").read_text())
    config, (_, _, stream, variant, _) = observation(summary)
    if expected_variant is not None and variant != expected_variant:
        raise ValueError("replay resolver variant mismatch")
    rows = (directory / "actions.jsonl").read_text().splitlines()
    actions = [Action(**{**row, "path": tuple(map(tuple, row["path"]))})
               for row in map(json.loads, rows)]
    legacy = stream == H32
    initial = read_initial_fixture(directory / "initial-state.json")
    battle, _ = simulate(config, legacy=legacy, variant=variant, scripted=actions, encounter=initial)
    trace = jsonl(battle.events)
    if trace != (directory / "events.jsonl").read_text():
        raise ValueError("replay trace mismatch")

    # Independently re-evaluate the deterministic policy to verify its identity
    # and candidate counts rather than trusting values in the recorded summary.
    policy_battle, counts = simulate(config, legacy=legacy, variant=variant, encounter=initial)
    if policy_battle.actions != actions:
        raise ValueError("replay policy action mismatch")
    actual = summarize(config, battle, counts, trace)
    if canonical_json(actual) != canonical_json(summary):
        fields = sorted(key for key in actual.keys() | summary.keys()
                        if key not in actual or key not in summary
                        or canonical_json(actual[key]) != canonical_json(summary[key]))
        raise ValueError("replay summary mismatch: " + ", ".join(fields))
    return len(battle.actions), variant


def validated_matrix_rows(rows, expected, legacy):
    for row, config in zip(rows, expected, strict=True):
        run, (_, _, stream, variant, _) = observation(row)
        if (run != config or stream != (H32 if legacy else EP08) or variant != FROZEN
                or row.get("initial_fixture") != "default"):
            raise ValueError(f"matrix observation mismatch for {config}")
        yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    single = commands.add_parser("run")
    single.add_argument("profile", choices=PROFILES)
    single.add_argument("seed", type=int)
    single.add_argument("policies", nargs=2, choices=("AGG", "ADV", "RES", "PASS"))
    single.add_argument("--legacy", action="store_true")
    single.add_argument("--resolver", choices=(FROZEN, EARLY_EXIT), default=FROZEN)
    single.add_argument("--mirror", action="store_true")
    single.add_argument("--output", required=True, type=Path)
    replay = commands.add_parser("replay")
    replay.add_argument("directory", type=Path)
    replay.add_argument("--resolver", choices=(FROZEN, EARLY_EXIT))
    matrix = commands.add_parser("matrix")
    matrix.add_argument("name", choices=("screening", "confirmation", "policy", "mirror", "legacy-displacement"))
    matrix.add_argument("output", type=Path)
    matrix.add_argument("--legacy", action="store_true")
    matrix.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    aggregate = commands.add_parser("report")
    aggregate.add_argument("input", type=Path)
    aggregate.add_argument("--paired-baseline", choices=PROFILES)
    args = parser.parse_args()

    if args.command == "run":
        config = Run(args.profile, args.seed, tuple(args.policies), args.mirror)
        if args.resolver == EARLY_EXIT and not args.legacy:
            parser.error("--resolver early-exit-v1 requires --legacy")
        battle, counts = simulate(config, legacy=args.legacy, variant=args.resolver)
        write_run(args.output, config, battle, counts)
    elif args.command == "replay":
        roots, variant = replay_run(args.directory, args.resolver)
        print(f"verified {roots} roots and summary ({variant})")
    elif args.command == "matrix":
        matrices = {"screening": SCREENING, "confirmation": CONFIRMATION, "policy": POLICY}
        if args.name == "mirror" and args.legacy:
            parser.error("the mirror matrix uses EP08")
        with concurrent.futures.ProcessPoolExecutor(args.jobs) as pool:
            if args.name == "mirror":
                rows = pool.map(mirror_task, MIRROR, chunksize=4)
            elif args.name == "legacy-displacement":
                rows = pool.map(legacy_displacement_task,
                                [c for c in SCREENING if c.profile == "F6"], chunksize=4)
            else:
                configs = matrices[args.name]
                rows = validated_matrix_rows(
                    pool.map(run_task, [(c, args.legacy) for c in configs], chunksize=4),
                    configs, args.legacy,
                )
            dump_rows(args.output, rows)
    else:
        rows = map(json.loads, args.input.read_text().splitlines())
        result = paired_report(rows, args.paired_baseline) if args.paired_baseline else report(rows)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
