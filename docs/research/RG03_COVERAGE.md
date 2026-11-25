# RG03 source and coverage register

The private Charter, D3, and D4 exports match the SHA-256 values in the
[source manifest](SOURCE_MANIFEST.md). The branch starts at merged main
`eb93451e84d4ffb0c73fe6016ec204a18bbbbc7c`. Charter and hard invariants
govern first, followed by D3.9 amendments, base D3, explicit D4-RP-0.1
overrides, and fixture definitions. The EF09-RH1 evidence remains separate.

| Source | Resolver and evidence | Applicability |
| --- | --- | --- |
| D3.1 R3.1-01–06, HC01–04/07, D4 MP01/02/09–13 | `fixture`, exact roster, starting placements, casualty-lot lineage and per-root inventory checks | Standalone F01 |
| D3.1 R3.1-07–12, D3.2 R3.2-01–16, A01–03, HM02/HM04 | `resolver.F01.validate`, `resolve` and `advance_side`; group following, final principal slot, exact-cost assault, reaction after pass or spent activation | F01 principal and response ledger. Group leader availability is an explicit fixture flag for CT04. The sources do not assign leader loss to a named formation or define a standalone random leader-loss event |
| D3.3 R3.3-01–18, A04–06, GT11/14, HM03 | `terrain`, `movement`, `translate`, `offer_response`; exact rational LOS, independent edge opacity, actual steps and fatigue/condition stops | Open information. Unknown blocking, fog previews and dependency pruning for an unseen obstruction remain outside the executed fixture surface |
| D3.4 R3.4-01–18, A06–09, D4.8 N05, HM08 | `combat`, `discharge`, `assault` and `packets`; source-specific contribution, target-specific exposure, ammo debit, pre-contact response and reciprocal snapshots | Tactical packet effects. No equipment or mount injury model |
| D3.5 R3.5-01–22, A09–11, D4.8 N01/N02 | Reuses `condition.assess/exert` and `displacement.arbitrate`; F01 terrain-aware frozen threats, root shock-deduplication, rally, refuge and rest | Tactical only. Actual paths preserve the paid and completed stages before interruption |
| D3.6 R3.6-01–19, A12–14/A23, HM01/HM05 | `leave`, `surrender`, `adjudicate`, `finish` and `close_round`; round zero, orderly departure, mutual abandonment, capitulation with wounded, deadline O0 | Standalone holding and custody ledgers. No strategic admission, transport, healing or campaign commit |
| D3.8 observation contracts, A21, HM07 | Filtered immutable `Observation`, eligible reaction choices and `legal_orders` shared with the principal validator | Exact enemy wound/death ledger, seed and future draws stay internal. Fog and strategic disclosure excluded |
| D4 EP08, D4.8 N06, HM06 | `combat.effect_key`, two independent golden vectors, policy and scripted replay, and 48 paired physical mirrors | Deterministic F01 keys, distinct from EF09-RH1 |
| D4 EP11, EP16 | Shared durable journal parser and writer, unique exact manifest, 96 run traces and separate aggregate report | No failed or partial executions in the committed corpus. Review failures stop publication and retain attempted identities |
| D3.7–8, A14–20 and A22 campaign portion | No campaign entry point | Excluded. Applicable standalone clock and observation rules remain in force |

## Acceptance evidence

**Directed** means a named F01 regression exercises the interaction.
**Partial** means the production path or development corpus covers part of
the rule without an exact isolated reproduction of every source case.

| Cases | Status | Evidence |
| --- | --- | --- |
| CT02–05, CT06/09–10, CT12; AT01–03 | Directed / partial | Group last-slot test, selected-vacating test, authority-disabled fixture, exact-cost assault and pass/reaction tests. Exact CT conflict variants remain partial |
| CT01/07/08/11; GT04/08/10/15 | Partial | Matrix journals and directed response tests verify the principal/response boundary. Every source variant has separate expected-stage details still to be asserted |
| GT01–03, GT05/07/09/11–12/14; AT05–06 | Directed / partial | Fixture geometry, individual path, group eligibility and following, actual missile response, shared edge/corner LOS, controlled disengagement, mounted shortfall. AT05 hidden stationary dependency pruning excluded |
| GT06/13 | Excluded | Hidden obstruction and hidden contact require fog outside the open-information manifest |
| BT01–08/10–15/17–18; AT04 | Directed / partial | Ammo use, paid assault and interruption, reciprocal depletion, zero allocation, multi-link reserve, persistent contacts, live withdrawal, replay. Exact loss bounds by every template/weapon combination and all eligibility variants remain partial |
| BT09/16 | Partial | Front/rear geometry and neutral reference coefficients, directed stage records, no automatic flank bonus |
| RT01–19/21–22; AT07 | Directed / partial | Rest completion/interruption, forced stops and frozen evacuation cells, reciprocal rout, bounded local shock, mirror corpus, closure precedence. A directed fixture covers safe refuge, reformer gates and later rally. Some isolated displacement tie fixtures remain partial for F01. Accepted reduced displacement tests still pass |
| RT20; ET16/23; AT08/15/20 | Directed / partial | Reciprocal mounted depletion, surrender with escaped formation and wounded, conserved custody, offboard inventory, and mirror corpus. Campaign destination portions excluded |
| ET02/05–08/11–12/16/20–22 | Directed / partial | Exhausted holder O0, reciprocal rout/depletion, orderly exit, abandonment, zero intervals at initial terminal, passes to deadline, post-terminal rejection and replay |
| ET09/10/13 | Directed | Withdrawal consumes an opportunity and takes precedence over O0. Exit rejected off the designated edge and when unsafe |
| ET01/03–04/14–15/17–18 | Partial | Stable viability checkpoints, objective condition/contact/threat classification and frozen mandatory exit. Individual source variants remain to be isolated |
| ET19/24; AT09–14/16/21–22 | Excluded / partial | Campaign admission, supply, custody handoff and strategic effects excluded. Standalone terminal before recovery is directed. F01 barriers exercise actual local obstruction only |
| AT17–19 | Directed / partial | Injected invalid packet faults and rejects further orders, private fields excluded from controller observations, canonical replay and boolean type regression. Save transaction and restoration of external campaign state excluded |

## Manifest and stage keys

The predeclared set is 16 open F01, 16 rough F01, and 16 barrier F01 runs
at seeds 22000–22015, with a separate physical mirror of each. O0 and
D4-RP-0.1 are fixed. The symmetric rough coordinates come from D3.1.
The barrier fixture uses original development edges away from the
reserved HF02 barrier placement. No holdout fixture or seed was run.
An invariant or mirror failure stops the execution and retains the
journal and available trace, with no successful matrix report.

F01 uses EP08 `F01-stage-v1`. Fixture pair is `F01-v1-<variant>`, replicated
by the root seed. Logical formation ID is side × 8 plus index in
H1–H6, L1, C1. Each accepted action has a root ordinal. A simultaneous
group move is one numbered leg with all member IDs and costs.
The actual stage leg distinguishes movement and reaction windows.
Directed packet keys include source/target IDs, melee or missile,
principal or response, channel and index zero. The profile name is
excluded from draw keys. Mirrors preserve the keys. The full journal
records the effective keyed draws.

See [RG03 results and review instructions](RG03_RESULTS.md).
