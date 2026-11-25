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

## Final source-case verification

The [coverage register](RG03_COVERAGE.md) identifies all 119 acceptance
cases, 25 amendments and eight hard invariants individually. For mixed
cases it identifies which standalone assertion passed and which external
clause is outside scope. Hidden blockers and campaign admission remain
outside the open-information standalone fixture. The resolver supports
explicit group authority availability at fixture setup, without a
standalone leader-loss generator.

The adversarial fixture test
`tests.test_f01_source_cases.SourceCases.test_hm01_hm02_reject_invalid_fixture_inventory_and_lots`
failed at checkpoint `8433ca40992b8c05ff6255df0ee2e543343c2cfa` on
boolean stock, negative casualty counts, duplicate stage lots, and
wrong formation lineage. HM01/HM02 and D3.1 require whole nonnegative
stocks and unique attributed allocations. `F01.check_invariants` now
validates each lot and inventory before accepting an audited state,
including typed cells and unique holding membership. The four fault
fixtures now reject. The guarded path does not change legal action effects.

All 135 tests passed. The full 96-execution matrix was regenerated
against the checkpoint and replayed. Its execution journal, summary
report and all 96 individual canonical traces are byte-for-byte equal
to the checkpoint, so the existing evidence files remain the published
archive. RG02 and RG03 checksums verified. All planned attempts completed.
BM07, O0 and D4-RP-0.1 remain as reported above. No holdout or RG04 work
was started. The draft is ready for independent technical review within
the recorded standalone scope. Independent acceptance remains pending.

### Additional review commands

```sh
python3 -m unittest -v tests.test_f01_source_cases
cmp "$archive/development.execution.jsonl" "$fresh/development.execution.jsonl"
for file in "$archive"/*-[01].jsonl; do
  cmp "$file" "$fresh/$(basename "$file")" || exit 1
done
```
