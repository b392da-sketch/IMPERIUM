# EF09-RH1 research handoff

The research harness models the twelve heavy infantry formations on the
open 99-cell EF09-RH1 board. The resolver accepts individual moves, one-step
pivots, controlled withdrawals, assaults, hold, rally, rest and pass.
Routing evacuation is compulsory. The experiment excludes voluntary
off-board evacuation, missiles, light infantry, cavalry, grouped orders,
elective reactions, external arrivals, rough terrain, barriers, campaign
and historical scenarios. The charter keeps the production and D5 gates open.

## Sources and precedence

See the [source manifest](SOURCE_MANIFEST.md) for the three offline exports,
their digests and the governing rules. The original and continuation
briefs were also consulted. The source exports remain private.
The [source-conformance matrix](SOURCE_CONFORMANCE.md) traces the applicable
hard invariants and D3/D4 rules to tests and remaining scope limits.

Hard invariants govern first, followed by D3.9 A01–A25, D3 v0.2, explicit
experimental profile overrides, reduced-fixture restrictions and earlier
examples. D4-RP-0.1 provides provisional research values. It does not
supersede D3 semantics.

## Reviewer commands

Run from the repository root using CPython 3.12.14. The harness uses the
standard library.

```sh
python3 -m unittest discover -v
python3 -m unittest -v tests.test_scheduler.IntegratedDisplacementTests
python3 -m imperium run F6 20000 AGG RES --output /tmp/ef09
python3 -m imperium replay /tmp/ef09
python3 -m imperium run F6 20000 AGG AGG --legacy --resolver early-exit-v1 --output /tmp/ef09-early-exit
python3 -m imperium replay /tmp/ef09-early-exit --resolver early-exit-v1
python3 -m imperium replay evidence/rg02/initial-terminal-sample --resolver frozen-v1
python3 -m imperium run F6 20000 AGG RES --mirror --output /tmp/ef09-mirror
cmp /tmp/ef09/events.jsonl /tmp/ef09-mirror/events.jsonl
matrix_dir=$(mktemp -d)
for matrix in screening confirmation policy mirror legacy-displacement; do
  python3 -m imperium matrix "$matrix" "$matrix_dir/$matrix.jsonl"
done
for matrix in screening confirmation policy; do
  python3 -m imperium matrix "$matrix" "$matrix_dir/legacy-$matrix.jsonl" --legacy
done
python3 -m imperium verify-execution "$matrix_dir/confirmation.execution.jsonl" \
  --observations "$matrix_dir/confirmation.jsonl"
python3 -m imperium report "$matrix_dir/confirmation.jsonl" \
  --execution "$matrix_dir/confirmation.execution.jsonl"
python3 -m imperium report "$matrix_dir/confirmation.jsonl" \
  --execution "$matrix_dir/confirmation.execution.jsonl" --paired-baseline F6
(cd evidence/rg02 && sha256sum -c SHA256SUMS)
```

For a failed run use its profile, seed and two policies in the single-run
command, with the recorded orientation and stream flags. Failure messages
include the run configuration. Replay forwards the accepted actions to the
same resolver, including explicit passes, then compares the whole trace
and SHA-256 digest.

## Architecture and evidence

The scheduler uses the existing fixture, geometry, allocations, directed
packet and condition kernels. Its displacement phase freezes occupancy
and threat, ranks candidates, arbitrates conflict waves, then commits exits
and on-map steps. The deterministic policies rank a preferred subset of
orders and use the same declaration validation as scripted play. See
[regression inputs and expected outcomes](RG02_REGRESSIONS.md).

The corrected manifest is defined in `imperium/experiments.py`. Screening
has 1,024 runs, confirmation 2,048, policy 512 and mirror 128 orientation
pairs. This freezes the declared comparisons. Shared seeds are matched
observations. The development run configuration rejects both holdout
ranges. HF01–HF06 are outside the harness.

The event format is `EF09-RH1-events-v2`. Each JSONL record carries version
and run identifiers, round, root ordinal, stage ordinal, event kind,
endpoints, and SHA-256 before/after digests. A principal event contains
the accepted action, effective draw keys and numerators, packets,
displacement proposals and reservations, shock witnesses, objective
state and condition snapshots. For roots closing a round, the journal
also contains the closure checkpoint and the after digest includes any
next-round opening. The observation tuple is logical ID, disposition,
available personnel, cohesion, morale, fatigue. Runtime metadata stays
outside the deterministic digests.

In the default stream, a directed effect key is
`r{round}/s{logical_side}/o{opportunity}/a{attacker}/t{target}/src{source}`.
Run seed and replicate are identical and fixture pair is EF09-RH1.
Channels are injury, fatal, cohesion, morale, couple and reserved latent.
The SHA-256 first 53 bits represent the numerator over 2**53.
Single quantiles use draw index zero. Finite inverse CDF sampling
selects the first strictly greater cumulative mass. Four independent
source vectors exercise the hash contract. Legacy uses its own tag and a
32-bit numerator. Mirroring rotates cells and facings and swaps physical
side while keeping logical identities, action order, and semantic keys.

See [the results](RG02_RESULTS.md) for comparisons and limitations.
Per-seed rows and reports are under `evidence/rg02/`. Each matrix row has
a digest for its complete normalized event journal. To retrieve a journal
beyond the committed sample, rerun its exact row with the single-run
command and compare the SHA-256 of `events.jsonl` with `trace_sha256`.
The full matrix journals are reproducible on demand from the committed
inputs. They are not bundled with the results. Independent review remains
pending. Preferred choices per decision are not a full BM11 workload
measure.

## Independent review remediation

Evidence v2 binds the random stream and resolver variant to each trace
record and records the fixture and profile versions in every run summary. Pre-remediation
evidence is rejected without these fields.
Replay checks the recorded action stream through the resolver and
independently enumerates the declared policy to recover its deterministic
candidate counts. It verifies all summary fields. Supplying
`replay --resolver` also asserts the expected variant. To regenerate
reviewed v1 runs in the current format, rerun the listed commands.
Reports require the explicit v2 run identity and reject mixed provenance
or orientations and duplicate observations. Paired reports require one
matchup, at least two matched seeds and identical seed sets across profiles.

The archived reviewer baseline is commit
`cda92e4b6ee9138fb421a2951777dbf88c7dcc64`. Compare regenerated results to
that Git tree using [the remediation comparison](../../evidence/rg02/review-comparison.json).
Source delivery is handled outside GitHub through the existing private
review channel. The private packet contains the original assignment brief,
the exact three exports and checksums. The public PR only links the
source manifest and conformance documentation.

An initial nonviable side is adjudicated at round zero. An initially
terminal artifact has a separate `initial_terminal` event and an empty
actions file. For explicit regression fixtures the artifact stores
`initial-state.json`; replay reconstructs it and verifies both the
initial and terminal digests. Reports accept only the default experiment
fixture.

Baseline comparison from the repository root:

```sh
baseline=$(mktemp -d)
git archive cda92e4b6ee9138fb421a2951777dbf88c7dcc64 evidence/rg02 | tar -x -C "$baseline"
python3 -m imperium.review_evidence "$baseline/evidence/rg02" evidence/rg02
python3 -m unittest -v tests.test_review tests.test_scheduler.IntegratedDisplacementTests
```

## EP11 execution accounting

Each matrix invocation has its own `EF09-RH1-execution-v1` JSONL journal.
The runner uses POSIX file locking and atomic publication on Linux.
The default path changes `.jsonl` on the matrix output to
`.execution.jsonl`. Use `matrix --execution PATH` to select a different
journal. The plan records the exact run identities, including stream,
resolver variant and physical orientation. Each attempt references its
plan index. The worker flushes and syncs that record before simulation.
A completion stores the observation and event count in the journal. A
caught simulation failure stores the technical-stop reason separately.
Mirror and displacement pairs each account for two simulations.

A started attempt without a durable outcome is unfinished. A journal
reader can recover the valid prefix if its final record is torn, and a
torn tail blocks publication. An identity with no attempt record remains
unattempted. The runner publishes the final matrix only after validating
all planned completions and pair checks. Both the journal and output
use fresh paths. To retry, start a new execution at a new journal path.
There is no in-place resume or pooling of retries. Prior attempts remain
auditable in their original journal.

For a failed or interrupted principal matrix, inspect the journal and
recover a report directly from its completed rows:

```sh
python3 -m imperium verify-execution "$matrix_dir/confirmation.execution.jsonl"
python3 -m imperium report "$matrix_dir/confirmation.execution.jsonl" --from-execution
python3 -m unittest -v tests.test_execution
```

With `report --execution`, the observation file must match every completed
row in that journal exactly. Without a journal, a report shows the number
of supplied completed observations and uses null for attempted runs,
technical stops and other execution-level counts. An unresolved draw
denominator counts only successful observations. Paired reports still
require exact matched sets. Journal append order reflects actual worker
execution, so parallel reruns can differ in record order while producing
the same plan, counts and published observations.

To check the accounting rerun against the previous reviewed observation
files and verify the committed journals:

```sh
for label in screening confirmation policy mirror legacy-screening legacy-confirmation legacy-policy legacy-displacement; do
  git show "7082b4aa156d612b231e393fc479725eb41157a3:evidence/rg02/$label.jsonl" | cmp - "$matrix_dir/$label.jsonl"
  python3 -m imperium verify-execution "evidence/rg02/$label.execution.jsonl" \
    --observations "evidence/rg02/$label.jsonl"
done
```
