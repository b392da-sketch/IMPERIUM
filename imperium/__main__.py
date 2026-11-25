"""Run, replay and aggregate the EF09-RH1 development comparisons."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import tempfile
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median, stdev

from .events import canonical_json, jsonl
from .execution import Journal, identity, load_execution, validate_terminal
from .experiments import Run
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


def dump_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(canonical_json(row) + "\n")
    temporary.replace(path)


def report(rows, execution=None):
    rows = list(rows)
    accounting = execution.groups(rows) if execution is not None else {}
    groups = {}
    for row, run in compatible_rows(rows):
        groups.setdefault((run.profile, "/".join(run.policies)), []).append(row)
    result = {}
    status = execution.status if execution is not None else "unverified"
    for profile, matchup in sorted(groups.keys() | accounting.keys()):
        group = groups.get((profile, matchup), [])
        n = len(group)
        counts = accounting.get((profile, matchup), {
            "planned_runs": None, "attempted_runs": None, "completed_runs": n,
            "technical_stops": None, "unfinished_attempts": None, "not_attempted_runs": None,
        })
        counts = {**counts, "execution_status": status}
        if not group:
            result[f"{profile} {matchup}"] = {
                "runs": 0, **counts, "unresolved_denominator": 0, "wins_draws": {},
                "terminal_reasons": {}, "bm07_warning": None,
            }
            continue
        for row in group:
            validate_terminal(row)
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
            "runs": n, **counts, "unresolved_denominator": n, "wins_draws": dict(Counter(str(row["winner"]) for row in group)),
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
        for key in keys:
            validate_terminal(reference[key])
            validate_terminal(sample[key])
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


def matrix_worker(entry):
    config, (_, _, stream, variant, _) = identity(entry)
    battle, counts = simulate(config, legacy=stream == H32, variant=variant)
    trace = jsonl(battle.events)
    return summarize(config, battle, counts, trace), len(battle.events)


def run_matrix(matrix, legacy, output, execution_path, jobs, worker=matrix_worker):
    if output.resolve() == execution_path.resolve():
        raise ValueError("matrix output and execution journal must differ")
    if output.exists():
        raise FileExistsError(f"matrix output already exists: {output}")
    if jobs < 1:
        raise ValueError("jobs must be positive")
    journal, plan = Journal.create(execution_path, matrix, legacy)
    if jobs == 1:
        for index, entry in enumerate(plan):
            journal.execute(index, entry, worker)
    else:
        with concurrent.futures.ProcessPoolExecutor(jobs) as pool:
            pending = {pool.submit(journal.execute, index, plan[index], worker)
                       for index in range(min(jobs, len(plan)))}
            indices = iter(range(len(pending), len(plan)))
            try:
                while pending:
                    done, pending = concurrent.futures.wait(
                        pending, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for future in done:
                        future.result()
                    for index in [next(indices, None) for _ in done]:
                        if index is not None:
                            pending.add(pool.submit(journal.execute, index, plan[index], worker))
            except BaseException:
                for future in pending:
                    future.cancel()
                raise
    rows = load_execution(execution_path).materialize()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only after verification and never overwrite a previous run.
    with tempfile.NamedTemporaryFile(dir=output.parent, mode="w", encoding="utf-8") as staged:
        staged.writelines(canonical_json(row) + "\n" for row in rows)
        staged.flush()
        os.fsync(staged.fileno())
        os.link(staged.name, output)


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
    matrix.add_argument("--execution", type=Path)
    matrix.add_argument("--legacy", action="store_true")
    matrix.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    aggregate = commands.add_parser("report")
    aggregate.add_argument("input", type=Path)
    aggregate.add_argument("--paired-baseline", choices=PROFILES)
    source = aggregate.add_mutually_exclusive_group()
    source.add_argument("--execution", type=Path, help="verify observations against this journal")
    source.add_argument("--from-execution", action="store_true", help="read completed rows from input journal")
    verify = commands.add_parser("verify-execution")
    verify.add_argument("journal", type=Path)
    verify.add_argument("--observations", type=Path)
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
        path = args.execution or args.output.with_suffix(".execution.jsonl")
        run_matrix(args.name, args.legacy, args.output, path, args.jobs)
    elif args.command == "verify-execution":
        execution = load_execution(args.journal)
        published = execution.materialize() if execution.complete or args.observations is not None else None
        if args.observations is not None:
            rows = list(map(json.loads, args.observations.read_text().splitlines()))
            if rows != published:
                raise ValueError("published matrix differs from execution completions")
        print(json.dumps({"matrix": execution.matrix, "status": execution.status,
                          "complete": execution.complete, "torn_tail": execution.torn_tail,
                          "technical_stop_reasons": execution.stops,
                          **execution.counts(range(len(execution.plan)))}, indent=2))
    else:
        journal = args.input if args.from_execution else args.execution
        execution = load_execution(journal) if journal is not None else None
        rows = (execution.observations() if args.from_execution else
                list(map(json.loads, args.input.read_text().splitlines())))
        if args.paired_baseline:
            if execution is not None:
                execution.groups(rows)
            result = paired_report(rows, args.paired_baseline)
        else:
            result = report(rows, execution)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
