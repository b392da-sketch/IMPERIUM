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
python3 -m imperium run F6 20000 AGG RES --mirror --output /tmp/ef09-mirror
cmp /tmp/ef09/events.jsonl /tmp/ef09-mirror/events.jsonl
python3 -m imperium matrix screening /tmp/screening.jsonl
python3 -m imperium matrix confirmation /tmp/confirmation.jsonl
python3 -m imperium matrix policy /tmp/policy.jsonl
python3 -m imperium matrix mirror /tmp/mirror.jsonl
python3 -m imperium matrix confirmation /tmp/legacy-confirmation.jsonl --legacy
python3 -m imperium report /tmp/confirmation.jsonl
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

The event format is `EF09-RH1-events-v1`. Each JSONL record carries version
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

Per-seed rows and reports are under `evidence/rg02/`. Each matrix row has
a digest for its complete normalized event journal. To retrieve a journal
beyond the committed sample, rerun its exact row with the single-run
command and compare the SHA-256 of `events.jsonl` with `trace_sha256`.
The full matrix journals are reproducible on demand from the committed
inputs. They are not bundled with the results. Independent review remains
pending. Preferred choices per decision are not a full BM11 workload
measure.
