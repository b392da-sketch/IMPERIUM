# IMPERIUM

A research-led historical wargame exploring ancient military decision-making, beginning with the Roman Republic. IMPERIUM aims to combine historically grounded tactical and operational systems with the experience of commanding armies on a living 3D tabletop.

**Status:** research and rules-engine development. P1 and P2 are merged; P3 is the next planned engineering package. This repository is not yet a playable historical game or a historically validated simulation.

## Project direction

- Tactical battles with formations, terrain, command, morale, fatigue, reserves and combined arms.
- Operational and campaign systems connecting movement, logistics, settlements, recruitment and battle aftermath.
- Reproducible resolution, inspectable events and independent verification.
- Historical scenarios and counterfactual outcomes informed by ancient sources, scholarship and comparative wargame research, with uncertainty kept explicit.
- A planned Roman-inspired 3D war table, context-sensitive hex overlays, painted miniatures or carved pieces, historically informed artwork, music and sound.

These are design goals, not claims that the features are already implemented. Engine and presentation choices remain subject to validation.

## Engineering roadmap

| Package | Scope | Status |
| --- | --- | --- |
| P1 | Validated immutable battlefield state and canonical encoding | Merged |
| P2 | Authoritative commands and transition engine | [Merged — PR #5](https://github.com/b392da-sketch/IMPERIUM/pull/5) |
| P3 | Semantic events, independent refolding and deterministic randomness | Next — planned |
| P4 | Movement, group orders, evacuation and defensive windows | Planned |
| P5 | Missile and melee resolution | Planned |
| P6 | Morale and compulsory consequences | Planned |
| P7 | Round closure, recovery and result manifest | Planned |
| P8 | Controllers, observations and evidence verification | Planned |
| P9 | Standalone F01 development evidence | Planned |
| P10 | Integrated RG03 replacement acceptance | Planned |

P2 merge baseline: [`5dcfd5d`](https://github.com/b392da-sketch/IMPERIUM/commit/5dcfd5dd186c7a2f3ee5a422992c302e2a521389).

P2 establishes typed commands, session ownership, opening and round sequencing, opportunity accounting, withdrawal declaration, capitulation custody and terminal handling within its supported scope. Ordinary movement, combat, full mandatory consequences and complete closure remain later packages. P3 is not started or authorized by this README.

## Research and validation

RG01/RG02 development status and verification commands are recorded in
[the research handoff](docs/research/RG01_RG02_HANDOFF.md).

The engineering packages above rebuild the RG03 research engine. Subsequent gates cover behavioural diagnosis (RG04), reduced campaign integration (RG05), independent held-out validation (RG06), and readiness for playtesting (RG07). Human playtesting, architecture and presentation evaluation, and independent design approval remain later stages.

The first historical scenario candidate is Pharsalus (48 BCE). Preliminary historical research, personnel reconciliation, geography, formation feasibility and comparisons with published historical wargames are documented separately in the project's research workspace. The HS08-R5 independent historical close-out is currently tabled; no certified battlefield map, exact historical roster or implementation approval is implied.

## Development and verification

Implementation proceeds in bounded packages against explicit contracts, with independent acceptance tests and review before owner-approved merges. Preserve accepted fixtures and evidence, distinguish development cases from reserved validation, and keep experimental outcomes separate from claims of historical fidelity.

For the repository's research verification instructions, see the handoff linked above.
