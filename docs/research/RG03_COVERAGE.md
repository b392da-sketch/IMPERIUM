# RG03 source and coverage register

The private Charter, D3, and D4 exports match the SHA-256 values in the
[source manifest](SOURCE_MANIFEST.md). The starting point is merged main
`eb93451e84d4ffb0c73fe6016ec204a18bbbbc7c`. Charter and hard invariants
govern first, then D3.9 amendments, base D3, explicit D4-RP-0.1 overrides,
and fixture definitions. The EF09-RH1 evidence remains a separate baseline.

| Source and scope | Code and planned test evidence | Status at foundation |
| --- | --- | --- |
| D3.1 R3.1-01–06 and F01, HC01–04/07; D4 MP01/02/09–13 | F01 roster, identity, assets, mirror and template checks | Fixture and opening ledger implemented |
| D3.1 R3.1-07–12, D3.2 R3.2-01–16, A01–03, HM02/HM04 | Principal and response ledgers, committed action stages, last-slot and exact-cost regressions | Individual and group move prevalidation implemented. Full F01 resolver pending |
| D3.3 R3.3-01–06/09–14, A04/05, GT11/14, HM03 | Axial projection, exact LOS, independent passability and opacity, terrain and mount movement tests | Geometry and ground-cost primitives implemented. Resolver integration pending |
| D3.3 R3.3-07/08/15–18, A01/05/06 | Group dependencies and actual reaction windows, no recursive effects | Pending |
| D3.4 R3.4-01–18, A06–09, D4.8 N05, HM08 | Full target exposure, bounded directed packets, shared allocation, reciprocal and missile integration | Packet kernels implemented. Stage integration pending |
| D3.5 R3.5-01–22, A09–11, D4.8 N01/N02 | Actual exertion, conditions, displacement, waves and recovery tests | Numerical profile and existing reduced kernels available. Full F01 integration pending |
| D3.6 R3.6-01–19, A12–14/A23, HM05 | Initial terminal, evacuation, custody, departure, deadline and exactly-once clock scenarios | Pending for F01 |
| D3.8 observation contracts, A21, HM07 | Separate filtered view, shared action/reaction enumerator, denied information tests | Open-information F01 pending. Fog, campaign views and hidden admission excluded |
| D4 EP08, D4.8 N06, HM06 | F01 root, action/stage and logical-role keys; independent vectors and event replay | Key format and kernel tests defined. Resolver replay and event mirror pending |
| RG02 deferred verification issue | Type-sensitive execution and baseline evidence comparisons | Implemented in opening maintenance |
| D3.7–8 campaign, A14–20, A22 campaign portion, A24–25 | No standalone campaign mutation | Excluded. Tactical timing and observation portions remain applicable |

The rough coordinates come from D3.1. The barrier test is an original
development fixture, separate from HF02 and its reserved barrier placement.
D4.8 defines exposure by the target template rather than by its allocated
resistance. Mounted shortfall changes movement rate and prevents a mounted
charge under D3.3; it does not select a replacement D4 frontage or grant
legionary equipment.

No full-F01 experiment results have been inspected. Predeclared development
set for resolver validation: 16 open F01, 16 rough F01, and 16 barrier F01
runs using matched seeds 22000–22015. Run paired physical mirrors separately.
Exercise authored command, reaction, contact, and terminal adversarial cases
before the matrix. Stop and retain records on a hard invariant failure.
Use O0 and D4-RP-0.1 throughout. This is a small integration comparison,
with no intended winner and no holdout evaluation.


## Foundation verification

Run from the checkout root with CPython 3.12.14:

```sh
python3 -m unittest discover -v
python3 -m unittest -v tests.test_f01 tests.test_execution
(cd evidence/rg02 && sha256sum -c SHA256SUMS)
```

The foundation tests cover the exact roster and physical mirror, mounted
shortfall, independent edge traversal and opacity, shared-edge LOS and
vertex-only intersections, known fatigue stops, group membership and
selected-vacating path validation, bounded packet support, immutable
casualty-lot lineage and location, and two independently serialized EP08
reference vectors. Each vector uses index zero and excludes the numerical
profile from the semantic key.

The full-F01 accepted-root ledger must still supply monotonically ordered
actual stage leg numbers. Group movement commits at one leg with its
logical member IDs recorded in the event. Missile responses and principal
or reciprocal packets are separate directed stages. Fixture pair names
must remain identical across orientation mirrors and must distinguish
the open, rough, and barrier variants.

Group order commitment, pivots, elective response decisions, terminal
asset transfers, filtered observations, replay and execution accounting
are pending for F01. The reduced harness remains runnable as the accepted
baseline. No F01 battle has run, so the preliminary manifest is unexecuted
and there is no F01 statistical or review-readiness claim.
