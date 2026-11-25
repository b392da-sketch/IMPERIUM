# EF09-RH1 source-conformance matrix

The [source manifest](SOURCE_MANIFEST.md) identifies the verified private
exports. This is the implementation audit for independent re-review.
Hard constraints and D3.9 control the applicable D3 rules. D4 overrides
apply only to named profiles or reduced experiments. A supported row
addresses the EF09-RH1 portion. A partial row identifies a remaining
evidence or representation gap.

Evidence references use test classes in `tests/`. Matrix, replay, and
mirror evidence is in `evidence/rg02/`. The early-exit resolver is a
quarantined fault comparator. Its expected A10 violation is never a
conformance result for the default resolver.

## D4.1 hard invariants

| ID | Implementation | Verification | Status and scope |
| --- | --- | --- | --- |
| HM01 | `scheduler.Battle.assert_invariants`, `exchange`, `fixture` | Every matrix root and closure. Packet and injected-state tests | Supported for aggregate killed, wounded and available partitions. Individual lots, stock and custody excluded |
| HM02 | `cost`, `resolve`, round opening and stable effort/activation ledger | Exact-effort last-slot, invalid-effort and phantom-opportunity tests | Supported for principal slots and effort. Supply, ammunition and reservations across reactions excluded |
| HM03 | `geometry`, `participation`, `FrozenField`, `arbitrate`, contact invariants | Geometry and capacity sweeps, DX01–DX06, integrated displacement and contact tests | Supported in open land. No LOS, groups or barriers |
| HM04 | `resolve`, `pressure_stage`, `displace`, stable ledgers | Invalid activation and side bounds. Rejection and morale deduplication. Displacement regressions | Supported for reduced principals and mandatory effects |
| HM05 | `check_terminal`, `close_round`, `summarize` | Initial no-action terminal tests, mutual rout, deadline exhaustion, no postterminal mutation, matrix charged rounds | Supported for standalone tactical intervals. No external admissions |
| HM06 | `exchange`, `events`, `replay_run`, `mirror_task` | Regular and comparator replay, full normalized 128-pair comparison, reversed displacement ordering | Supported for the tested scope; H32 diagnostic does not validate the stream for general use |
| HM07 | `policies.choose`, `cost`, `randomness` | Deterministic replay, mirrored decisions, rejection trace | Partial. Open information and no hidden assets in this fixture. No filtered controller-view architecture or fog permissions test |
| HM08 | `physical`, `pressure`, packet validation in `exchange` | Packet endpoint tests, distribution moments, four EP08 vectors, all stochastic matrices | Supported for modeled packet channels. Asset and mount effects excluded |

## D3.9 reconciliation amendments

| ID | Implementation | Test or evidence | Status and scope |
| --- | --- | --- | --- |
| A01 | `cost`, frozen field, `arbitrate` | Known illegal move. Edge/stationary-primary regressions | Supported for individuals and mandatory movement. Group following excluded |
| A02 | `resolve`, opening and activation ledger | Last-slot, rejected order and injected-opportunity tests | Supported for principal actions/pass. Optional responses excluded |
| A03 | `cost` then committed `resolve` | Last-slot assault with exactly two effort | Supported. Post-response revalidation unexercised because responses are excluded |
| A04 | `geometry.distance/front/rear` | Geometry sweep and mirror tests | Supported for axial geometry; LOS and group pivot excluded |
| A05 | Movement prevalidation in `cost`, step checkpoints in `resolve` | Rejected illegal path. Mirror and matrix events | Supported for known geometry and exertion. No hidden interruption or reaction stage |
| A06 | `exchange`, persistent contact lifecycle | Contact persists through closure and ends on controlled withdrawal | Supported for no passive melee and selected pair only. Missile and elective pivot exclusions |
| A07 | `allocate`, `exchange` | Participation sweep, zero allocation, reciprocal rout | Supported with explicit weighted-profile override. Routers have temporary edge |
| A08 | `exchange`, `pressure`, `condition` | Bounded packets and exact attack/defence marks | Supported for personnel and C/M. No equipment or animals |
| A09 | `cost`, `FrozenField.capture` | Exhausted threat fixture, secure exhausted occupant, matrix | Supported for reduced actions. Group/missile gates excluded |
| A10 | `displace`, `arbitrate`, `close_round` | DX01–DX06, shared attempt, stationary blocks, fallbacks, frozen threat and mirror | Supported by frozen resolver. Intentional fault in isolated comparator |
| A11 | `pressure_stage`, `incoming`, `checkpoint`, recovery closure | Shock witness/deduplication and interrupted rest/refuge tests | Supported for open adjacent observation |
| A12 | `displace`, withdrawn disposition | Routing exit and shared allowance regressions | Supported for compulsory exit plus one mark. Elective exit, assets and supply excluded |
| A13 | `resolve`, `check_terminal`, `close_round` | Initial viability before allowances, mutual rout, O0 deadline, replayed interval count | Supported for standalone tactical boundary. Campaign tick and arrivals excluded |
| A14 | `fixture.initial_encounter` | Twelve-formation fixture test | External admission excluded. Only fixed initial roster |
| A15 | `events`, replay summary | Replay and checksums | Encounter leasing, campaign commit and crash journal excluded |
| A16 | Aggregate personnel partitions | Personnel conservation only | Campaign beneficiary/stock/custody accounting excluded |
| A17 | None | No campaign entry point | Campaign detachment and logistics excluded |
| A18 | None | No campaign entry point | Protected F02 withdrawal excluded |
| A19 | None | No campaign entry point | Aftermath occupancy and consolidation excluded |
| A20 | None | No campaign entry point | Strategic control and concession excluded |
| A21 | Open-information `policies.choose` | Policy matrices and mirrors | Partial, only open tactical observation. Full fog view, stock permissions and campaign observation excluded |
| A22 | `open_round`, `condition.exert`, `profiles` | Arithmetic tests and R0/F6 data | Supported for tactic-only reset or explicit D4 carry. No strategic march accumulator |
| A23 | `objective`, `check_terminal`, `close_round` | Mutual-rout and exhausted-occupant tests, confirmation | Supported. O0 only. No alternative adjudication |
| A24 | `cost`, provenance/runner validation | Rejected action and invalid scenario metadata tests | Unsupported reduced actions fail as invalid, not a military result. Campaign encounter scope excluded |
| A25 | `geometry.distance` | Axial distance sweep | Supported distance correction. Campaign formatting and stipulated stock examples excluded |

## D3 base rules

Ranges below are inclusive and use the prefix in the first column.
These rows distinguish reduced checks from full F01/F02 representation.

| Base ID | Implementation | Test or evidence | Status and scope |
| --- | --- | --- | --- |
| R3.1-01–03 | `Identity`, fixtures, evidence provenance, personnel partitions | Fixture mirror and tampered-provenance tests, roster checks | Supported for aggregate immutable lineage. No named individual lots, missing or captive states |
| R3.1-04–08 | Geometry, fixture scale, stable invariants, effort and terminal interval | Fixture/geometry, activation and deadline tests | Supported for open-land individual play and tactical ledger |
| R3.1-09–12 | Policy/cost isolation, journal, terminal check, reduced runner | Golden vectors, pass control, replay and rejection tests | Supported determinism and standalone freeze. Partial observation/terminal record as under HM07 and R3.6-15–18 |
| R3.2-01–04, 08–10, 12–13, 15–16 | `open_round`, `cost`, `resolve`, `exchange`, `close_round` | Last-slot, mutual-rout, pass/closure and ledger tests. Replay | Supported for alternating individual roots and automatic effects. No reservations across external stages |
| R3.2-05–07, 11, 14 | Unsupported order rejection | Scope inspection | Groups, leadership interruption and optional reaction effort excluded |
| R3.3-01–06, 09–12, 17–18 | Geometry, `FrozenField`, path/turn/withdrawal validation and `unlink` | Geometry/occupancy, contact withdrawal, frozen-threat tests. Matrix mirrors | Supported for open 60° pivot subset and public prevalidation. No terrain, LOS or hidden events |
| R3.3-07–08, 13–16 | Unsupported order rejection | Scope inspection | Group movement, LOS, missiles and reaction windows excluded |
| R3.4-01, 05–06, 08–11, 13–18 | `cost`, `exchange`, allocations, simultaneous transfer, stage effects and `unlink` | Packet bounds, mutual rout, exact effort, contact and replay tests | Supported for reciprocal melee in an uninterrupted accepted root. Explicit neutral aspect/equipment factors |
| R3.4-02–04, 07, 12 | Reduced profile constants and unsupported order rejection | Profile and packet tests | Missile, optional response and differentiated aspect/equipment omitted |
| R3.5-01–19, 21 | `condition`, `pressure_stage`, `displace`, safety latch, recovery, withdrawal and closure | Integrated displacement, casualty/condition, shock and recovery tests. Matrix assertions | Supported for applicable conditions and reduced allocation. Explicit D4 fatigue overrides |
| R3.5-20 | No surrender/custody route | Scope inspection | Excluded |
| R3.5-22 | Root journal, packet keys and nested ordered stage details | Exact replay and mirror corpus | Partial detail. Nested consequences have stable ordered context but lack separate cause-ID records for every recovery/transfer |
| R3.6-01–03, 07, 11–14, 19 | `fixture`, `objective`, `displace`, terminal and closure logic | Initial pre-round viability, disposition classification, O0, evacuation, mutual rout and complete matrices | Supported for initial/ongoing viability and O0, with collapse/departure/depletion-or-mixed subreason. Side-withdrawal/capitulation branches excluded |
| R3.6-04–06, 09–10 | Unsupported action rejection | Scope inspection | Postures, surrender custody and voluntary evacuation excluded in EF09-RH1 |
| R3.6-08, 15–18 | Survivor partitions, resolver terminal state, event log and summary | Conservation, no postterminal mutation, terminal summary replay | Partial representation. Exit actor and root recorded, with cell recoverable from replay rather than separate exit-pool manifest. No individual custody/asset deltas or separate player-view result |
| R3.7 and R3.8 | No campaign subsystem | Standalone harness entry point | Excluded for every base rule in these chapters |

## D4 overrides and reduced brief

| Source and rule | Implementation | Test or evidence | Status and scope |
| --- | --- | --- | --- |
| D4.1 EP01–07, EP13–15; D4.7 §1. Brief §§23,30 | `experiments`, run guards and provenance | Exact membership. Forbidden-range tests. Evidence manifest | Supported for preregistered battle seeds and fixed scale. No tactical scale variation, packet holdouts or historical inference |
| D4.1 EP08–09. Brief §11 | `randomness`, `exchange`, `pressure` | Four EP08 vectors. Stochastic endpoints. No rejected-action draws | Supported. Omitted latent draw produces no effect |
| D4.1 EP10–12, 16–18. Brief §§26,29 | `provenance`, report/replay, result files and commands | Duplicate/mixed-input regressions, exact matching, replay and archived baseline comparison | Supported identity, exact pairing, Wilson and Student t intervals, sample SD, P10 and P90 for losses and preferred choices. Counts are descriptive; BM11 and independent acceptance remain open |
| D4.2 §5. Brief §8 | `participation` | Bounds sweep and source allocation examples | Supported B/C, capped by available personnel and edge/frontage limits |
| D4.3 §§1–2,7 and D4.7 §1. Brief §9 | `physical`, profile exposure and injury choices | Support and analytical moment tests | Supported B1/O1 and E1/C1. Neutral aspect |
| D4.4 §§1–2 and D4.7 §1. Brief §10 | `pressure`, profile scale and gate | Joint percentile and routing tests | Supported I1/J1, LOW factor, no duplicate casualty penalty |
| D4.5 §§1–2,6; D4.7 §1. Brief §§7,19 | `profiles`, round start, exertion and recovery | Remainder, interrupted rest and refuge tests. Eight matrix profiles | Supported T3/reset/F1 and T6/carry/F0/rest clear. No simulated march |
| D4.7 §2. Brief §21 | `policies.choose`, same resolved actions as scripts | Policy matrices, ADV/PASS negative control and mirrors | Supported declared comparator subset. Centre rally before centre rest, facing-order paths on ties and −60° before +60° on tied pivot scores are explicit implementation decisions where ordering is implicit |
| D4.7 §3. Brief §22 | `legacy`, isolated H32 and early-exit resolver | H32 vector. All legacy comparisons and exact comparator replay | Diagnostic only. Current D3 legality and quantile arithmetic remain in use. Original temporary executable and pair records unavailable |
| D4.8 §3. Brief §§16–17 | Corrected arbitration and forced-stop ledger | Abstract and integrated displacement regressions | Supported in default. Early-exit diagnostic intentionally exposes only the occupancy flaw |
| D4.8 objective discussion. Brief §20 | O0 objective and terminal procedure | Exact matrix comparison and unchanged O0 regression | Supported. BM07 stays open |
| Charter and brief §§3–5,27–28,30,35 | Standalone heavyweight-only scenario, public scope and hard checks | Fixture, unsupported-order rejection, matrix evidence | Supported reduced research scope. No RG03, full-F01 mechanics, production UI, linked campaign, balance tuning or holdout execution |
