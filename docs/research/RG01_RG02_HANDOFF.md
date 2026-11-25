# EF09-RH1 research foundation

This branch implements the parts of RG01/RG02 that can be derived directly
from the supplied handoff. EF09-RH1 is an abstract open-land Roman tabletop
fixture. Scope covers the starting formations, geometry, eight immutable
profiles, allocation, directed effects, semantic draws, development matrix
declarations, and frozen-occupancy destination arbitration.

## Sources and discrepancy register

The supplied RG01/RG02 brief was inspected. Its source precedence is hard
invariants, D3.9 A01–A25, D3 v0.2, explicit D4-RP-0.1 overrides, reduced-fixture
restrictions, then earlier examples. The following pages could not be read.

| Source | Access result | Dependency |
| --- | --- | --- |
| [Project charter](https://app.notion.com/p/423d0e0c758e81b3b254cd9e39dafa26) | HTTP 200 with only a generic Notion shell | Project and experimental scope verification |
| [D3 Candidate rules synthesis](https://app.notion.com/p/423d0e0c758e81d2bafbcb918b9a4771) | HTTP 200 with only a generic Notion shell | Sections D3.1–D3.6 and D3.9, including A01–A25 |
| [D4 Mathematical modelling and experimental validation](https://app.notion.com/p/423d0e0c758e81df9a9b-c0ecc014f480) | HTTP 404 with only a generic Notion shell | Sections D4.1–D4.5, D4.7–D4.8, and RG01–02 reference |

Open source questions include the controlling contact creation and retention
rules, pivot and controlled-withdrawal conditions, retreat-edge designation and
edge evacuation eligibility, shock witness eligibility, reforming closure
requirements, and the precise D4.7 policy comparators and reserve-release
proximity. Each can change results for fixed seeds. No source conflict could
be resolved against uninspected D3 or D4 text. The temporary D4.7 executable
and raw logs are unavailable per the supplied brief. The H32 key contract
and detailed legacy comparator are also unverified.

## Run the implemented tests

Use CPython 3.12.14 as recorded in `.python-version`. There are no third-party
dependencies and no installation command. From the repository root run

```sh
python3 -m unittest discover -v
```

To reproduce a destination-arbitration failure, run

```sh
python3 -m unittest -v tests.test_foundation.DisplacementTests
```

## Random key registry

`imperium.randomness.DrawKey` hashes a compact JSON array with SHA-256. Its
first 53 digest bits produce an integer percentile numerator over 2**53.
For EF09-RH1 use the root seed as both seed and replicate. The directed melee
stage is `r{round}/s{logical_side}/o{opportunity}/a{attacker}/t{target}/src{source}`.
Use logical IDs across orientations and omit the profile. The channel
registry is injury, fatal, cohesion, morale, couple, and reserved latent.
Draw index is zero for each current distribution. Finite inverse CDFs select
the first strictly greater cumulative mass. Deterministic outcomes bypass
the draw. Four independent reference vectors from the brief are tested.

## Arbitration regression inputs

A=(0,0), B=(1,0), C=(2,0), x=(1,1), y=(2,1), z=(3,1).
These coordinates label abstract proposals. They carry no claims about
adjacency or threat legality. Every initial primary remains in the
occupancy snapshot, including any exiting formation.

| Case | Occupied | Exit | Ranked proposals | Assignments |
| --- | --- | --- | --- | --- |
| DX01 | A B | A | B A | none |
| DX02 | A B | A | B A x | B to x |
| DX03 | A B C | A | B x y, C x z | B to y, C to z |
| DX04 | A B C | A | B A x, C x | none |
| DX05 | A B C | A | B C x, C y | B to x, C to y |
| DX06 | A B | none | A x, B x | none |

All cases are specified for both forward and reverse input order. The
arbitrator returns canonical proposals and conflicts. The scheduler must
supply separately decided exits and threat-filtered ranked lists and commit
the batch after arbitration. No integrated scheduler or actual hex-based
scheduler regression is present.

## Experiment freeze and scope

`imperium.experiments` records 1,024 screening, 2,048 confirmation, and
512 policy specifications plus 128 orientation pairs. It rejects the two
reserved seed ranges. Zero battle runs were executed and no holdout
fixtures were used. The orientation tests cover fixture geometry.
The canonical full mirror comparison, resolver replay, event-log schema,
per-seed traces, aggregate reports, and durable run artifacts remain pending.

The planned reduced experiment omits missiles, ammunition, mounted assets,
light infantry, cavalry, group orders, elective reactions, barriers,
rough terrain, capitulation, reinforcements, strategic mechanics, and
historical scenarios. The current foundation also lacks round scheduling,
recovery, morale propagation, displacement commitment, reduced policies,
termination, and battle instrumentation. A read-only export of the cited
source sections, or explicit governing rules for the open questions, is
required before resolving the source-dependent mechanics and running the
matrix. Independent review has not taken place.

## Additional pure checks

The frozen-field case uses an exhausted organized hostile at (3,3) facing
d0. It projects threat onto (4,3) and (3,4). A router occupies (4,4) and
is removed after capture. Original occupancy still excludes (4,4), and
original threat still excludes (4,3) and (3,4) if the hostile subsequently
moves. The adjacent but unthreatened (2,4) remains available. This is a
snapshot-filter unit test. Actual placement, exits, scheduling and shared
attempt flags are pending.

The condition module covers depletion precedence, strict severe-condition
crossings, rout precedence, and threshold/remainder arithmetic. This
does not establish the ordering of those effects within an accepted root.

## Continuation source access and event format

The continuation brief was inspected. Three attempts to retrieve the private
Markdown exports (IMPERIUM-Charter.md, IMPERIUM-D3.md and IMPERIUM-D4.md)
returned an attachment authorization or resolution error. The workspace
contained the two briefs. The exports were unavailable to inspect or hash,
and the open source questions above remain open.

`imperium.events` now defines `EF09-RH1-events-v1`. Each JSONL record carries
the fixture, profile and schema versions, profile ID, seed, round, root
action, stage, kind, optional endpoints and semantic key, before/after
digests, and event-specific data. Records are written in resolver order.
Object keys are sorted recursively, and non-finite numbers are rejected.
The SHA-256 state digest includes complete formation records, sorted contacts
and caller-supplied round bookkeeping. Runtime metadata stays outside its
input. The serializer is tested in isolation. Resolver event emission, replay,
mirror normalization and durable trace artifacts still require integration.
