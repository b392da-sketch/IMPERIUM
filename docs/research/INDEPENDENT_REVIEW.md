# RG01–RG02 independent re-review

Reviewed baseline: `cda92e4b6ee9138fb421a2951777dbf88c7dcc64`.
The independent source audit closed the source-access finding. The exact
exports and original brief were recovered and checksum-verified. The
[conformance matrix](SOURCE_CONFORMANCE.md) records applicability,
evidence and remaining scope limits. Private materials stay outside Git.

| Finding | Governing rule | Remediation and evidence |
| --- | --- | --- |
| RM01 Initial terminal ordering | R3.6-11/14, A13/A14, HM05 | `Battle.__init__` adjudicates stable initialized viability before creating allowances. Initial terminal has zero actions, effort and charged intervals, and an explicit round-zero event. `InitialTerminalReviewTests` covers both viable, Red only, Blue only, neither, on-map routers, viable reformers and exact zero-action replay. |
| RM02 Defeat classification | R3.6-11/12, BM07 | `Battle.check_terminal` preserves broad outcome and records side-indexed subreasons. A router remaining on-map establishes collapse. Only withdrawn formations means orderly departure. A depleted or mixed roster with no router is recorded as depletion or mixed loss. The classification adds no casualty threshold and cannot change the winner. The exact confirmation check is in `imperium.review_evidence`. |
| RM03 Statistical reporting | EP11 | `reporting.describe` emits count, sample SD, median and type-7 P10/P90. `paired_continuous` uses a two-sided Student t critical value with one degree of freedom less than the number of matched seeds. `StatisticalReviewTests` exercises independent tabulated quantiles, an interval reference, insufficient input and zero variance. |
| RM04 Aggregation integrity | EP10 | `provenance.observation` and `compatible_rows` validate configuration, versions, stream, orientation and resolver; reject duplicate identities and mixed strata. `paired_report` requires the same matchup and exact seed sets. `AggregationReviewTests` exercises mixed EP08/H32, duplicate paired rows, unmatched seeds and incompatible provenance. |
| RM05 Replay and evidence retrieval | HM06, EP16 | `replay_run` re-executes logged actions and independently recovers policy counts. It verifies all deterministic summary fields, full event JSONL, state digests, stream and explicit variant. V2 evidence declares frozen and H32 early-exit provenance. Tampered summary, variant mismatch and positive comparator replay are tested. |
| RM06 Runtime invariants and regressions | HM03/HM04, R3.2-08/09, R3.4-09/16 | Stable checkpoints validate opportunity debits, opening and remaining effort, once-per-round activation, legal on/offboard dispositions, and unique primary/contact constraints. Adversarial tests include invalid side counts, effort, spent readiness and withdrawn/depleted on-board positions. Contact persistence and adjacent legal withdrawal are tested. Matrix combinations are checked exactly. |

The [handoff](RG01_RG02_HANDOFF.md) provides rerun commands. The
[results report](RG02_RESULTS.md) distinguishes mechanical outcomes from
schema, classification and statistical changes. The audit covers only the
reduced open-information fixture. The comparator deliberately restores the
occupancy flaw for the isolated H32 diagnostic. Full campaign/fog and
player-facing workload validation remain outside this scope. Independent
re-review is required for acceptance and BM07 remains open.
