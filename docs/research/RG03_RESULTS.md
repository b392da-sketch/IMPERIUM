# RG03 integrated F01 research checkpoint

The standalone resolver runs the three predeclared terrain fixtures,
with 16 matched development seeds per variant and a separate physical
mirror for each. All 96 attempts completed. No technical stop occurred
in the manifest. The 48 mirrored pairs matched normalized journal and
terminal-state digests. All 96 archived executions reproduced through
type-sensitive deterministic replay.

| Terrain | Unresolved / 16 | 95% Wilson interval | Mean killed + wounded |
| --- | ---: | ---: | ---: |
| Open | 16 | 80.6%–100% | 121.81 |
| Rough | 14 | 64.0%–96.5% | 124.25 |
| Barrier | 16 | 80.6%–100% | 120.75 |

BM07 triggers in every variant. Both rough-fixture wins used the existing
deadline objective. The sample is small and terrain variants share
seeds. The result does not establish a preferred terrain, policy, or
numerical profile. Legal choices are distinct from the research policy's
top-ranked subset. Mean legal choices per decision were 60.73 open,
59.80 rough, and 60.38 barrier. Mean preferred choices were 1.77, 1.70,
and 1.85 respectively. These are decision counts under a single policy,
not human workload measurements.

The policy prioritizes legal assault and missile actions, then positive
centre progress, rally, rest, access-improving pivot and controlled
withdrawal. It uses stable enumeration order for equal ranks and
prefers an eligible missile at a reaction window. There is no automatic
counter-reaction. Scripted controllers can decline or choose another legal
response. The published run report includes per-variant opportunity and
outcome totals, objective classification and overlapping reason flags,
early exhaustion, secure closures, casualty distributions and matched
casualty differences against the open fixture.

Compared with RG01–RG02, F01 now includes the light and mounted roles,
command manoeuvres, missiles and reactions, terrain, and formal terminal
asset movement. Those differences and the new policies make direct
numerical comparison to EF09-RH1 descriptive only. Its accepted evidence
and execution schemas are preserved. The F01 execution journal uses the
shared durable per-attempt accounting under a separate plan and schema.

## Independent reproduction

From the repository root:

```sh
python3 -m unittest discover -v
python3 -m unittest -v tests.test_f01 tests.test_f01_resolver tests.test_f01_research
(cd evidence/rg02 && sha256sum -c SHA256SUMS)
(cd evidence/rg03 && sha256sum -c SHA256SUMS)
archive=$(mktemp -d)
cp evidence/rg03/development.execution.jsonl evidence/rg03/report.json "$archive/"
tar -xzf evidence/rg03/traces.tar.gz -C "$archive"
python3 -m imperium.f01.research verify "$archive"
python3 -m imperium.f01.research replay "$archive"
fresh=$(mktemp -d)
python3 -m imperium.f01.research matrix "$fresh"
cmp "$archive/report.json" "$fresh/report.json"
```

The artifact archive contains the complete canonical trace for every
execution. The journal stores the declared plan, per-attempt records,
and exact per-run summaries. Verification reconciles the manifest,
checks each trace digest, and verifies physical pairs. Replay validates
orders, effective responses, stages, terminal events and summaries.
A scripted controller can replay a separate accepted journal via
`replay_orders` using the same initial fixture.

## Review limits

The [source and case register](RG03_COVERAGE.md) identifies partial
acceptance-case coverage. Hidden blockers and campaign admission remain
outside the open-information standalone fixture. The resolver supports
explicit group authority availability at fixture setup, without a
standalone leader-loss generator. No holdout or RG04 work was started.
Independent acceptance remains pending, including review of the partial
source cases.
