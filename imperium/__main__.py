"""Run, replay and aggregate the EF09-RH1 development comparisons."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median, stdev

from .events import canonical_json, jsonl
from .experiments import CONFIRMATION, MIRROR, POLICY, SCREENING, Run
from .policies import choose
from .profiles import PROFILES
from .scheduler import Action, Battle


def simulate(config, *, legacy=False, scripted=None, early_exit=False):
    profile = PROFILES[config.profile]
    if early_exit:
        from .legacy_displacement import EarlyExitBattle
        battle = EarlyExitBattle(profile, config.seed, config.mirrored)
    else:
        battle = Battle(profile, config.seed, config.mirrored, legacy=legacy)
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
        "run": asdict(config), "stream": "D47-H32-v1" if battle.legacy else "D4-SHA256-v1",
        "trace_sha256": hashlib.sha256(trace.encode()).hexdigest(), "charged_rounds": battle.round,
        "elapsed_minutes": battle.round * 10, "winner": battle.terminal[0], "reason": battle.terminal[1],
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
    for early_exit in (False, True):
        battle, counts = simulate(config, legacy=True, early_exit=early_exit)
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
    for row in rows:
        run = row["run"]
        groups.setdefault((run["profile"], "/".join(run["policies"])), []).append(row)
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
        result[f"{profile} {matchup}"] = {
            "runs": n, "wins_draws": dict(Counter(str(row["winner"]) for row in group)),
            "terminal_reasons": dict(Counter(row["reason"] for row in group)),
            "objective": dict(Counter(row["objective"]["classification"] for row in group)),
            "objective_flags": {key: sum(row["objective"].get(key, False) for row in group)
                                for key in ("condition", "contact", "threat")},
            "unresolved_wilson95": [max(0., center-margin), min(1., center+margin)],
            "bm07_warning": p > .75 if "PASS" not in matchup else None,
            "mean_rounds": mean(row["charged_rounds"] for row in group),
            "median_rounds": median(row["charged_rounds"] for row in group),
            "mean_losses": mean(casualty_counts), "median_losses": median(casualty_counts),
            "losses_min_max": [min(casualty_counts), max(casualty_counts)],
            "median_first_rout_round": median(rout_rounds) if rout_rounds else None,
            "mean_preferred_choices": mean(choice_counts),
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
    for row in rows:
        config = row["run"]
        profiles.setdefault(config["profile"], {})[(config["seed"], tuple(config["policies"]))] = row
    reference = profiles[baseline]
    result = {}
    for profile, sample in profiles.items():
        if profile == baseline:
            continue
        keys = sorted(sample.keys() & reference.keys())
        if len(keys) < 2:
            continue
        changes = {
            "unresolved": [int(sample[k]["reason"] == "unresolved")
                           - int(reference[k]["reason"] == "unresolved") for k in keys],
            "casualties": [sum(sample[k]["personnel"][kind] - reference[k]["personnel"][kind]
                               for kind in ("killed", "wounded")) for k in keys],
        }
        result[profile] = {"matched_runs": len(keys)}
        for metric, differences in changes.items():
            average = mean(differences)
            margin = 1.959963984540054 * stdev(differences) / len(keys)**0.5
            result[profile][metric] = {"mean_difference": average,
                                      "normal_approximation_95": [average-margin, average+margin]}
    return {"baseline": baseline, "profiles": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    single = commands.add_parser("run")
    single.add_argument("profile", choices=PROFILES)
    single.add_argument("seed", type=int)
    single.add_argument("policies", nargs=2, choices=("AGG", "ADV", "RES", "PASS"))
    single.add_argument("--legacy", action="store_true")
    single.add_argument("--mirror", action="store_true")
    single.add_argument("--output", required=True, type=Path)
    replay = commands.add_parser("replay")
    replay.add_argument("directory", type=Path)
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
        battle, counts = simulate(config, legacy=args.legacy)
        trace = jsonl(battle.events)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "events.jsonl").write_text(trace, encoding="utf-8")
        dump_rows(args.output / "summary.json", [summarize(config, battle, counts, trace)])
        dump_rows(args.output / "actions.jsonl", map(asdict, battle.actions))
    elif args.command == "replay":
        summary = json.loads((args.directory / "summary.json").read_text())
        config = Run(**summary["run"])
        rows = (args.directory / "actions.jsonl").read_text().splitlines()
        actions = [Action(**{**row, "path": tuple(map(tuple, row["path"]))})
                   for row in map(json.loads, rows)]
        battle, _ = simulate(config, legacy=summary["stream"] == "D47-H32-v1", scripted=actions)
        trace = jsonl(battle.events)
        if (trace != (args.directory / "events.jsonl").read_text()
                or hashlib.sha256(trace.encode()).hexdigest() != summary["trace_sha256"]):
            raise ValueError("replay trace mismatch")
        print(f"verified {len(battle.events)} roots")
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
                rows = pool.map(run_task, [(c, args.legacy) for c in matrices[args.name]], chunksize=4)
            dump_rows(args.output, rows)
    else:
        rows = map(json.loads, args.input.read_text().splitlines())
        result = paired_report(rows, args.paired_baseline) if args.paired_baseline else report(rows)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
