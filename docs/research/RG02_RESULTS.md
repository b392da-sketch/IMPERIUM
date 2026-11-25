# EF09-RH1 development results

Corrected EP08 executions comprise 1,024 screening, 2,048 confirmation and
512 commander runs, with 256 additional executions for 128 physical mirror
pairs. All 128 pairs had identical normalized event journals and final
digests. The committed F6 seed 20000 AGG/RES sample replayed 92 complete
roots through the resolver and matched both the original event file and
its digest. No technical failures occurred in the completed comparisons.
No holdout seed or fixture was used. CI and independent review remain open.

## Confirmation

Each row represents 512 AGG/AGG runs at seeds 21000–21511. Wins are
logical sides 0 and 1. Intervals are Wilson 95% for unresolved draws.

| Profile | Wins 0/1 | O0 unresolved | Wilson 95% | Archived draws | Mean killed + wounded |
| --- | --- | --- | --- | --- | --- |
| R0 | 51/59 | 402 (78.52%) | 74.75–81.85% | 418 | 119.36 |
| F6 | 57/52 | 403 (78.71%) | 74.96–82.04% | 400 | 136.04 |
| CJON | 68/49 | 395 (77.15%) | 73.32–80.58% | 389 | 137.42 |
| LOW | 35/40 | 437 (85.35%) | 82.03–88.15% | 430 | 186.20 |

**BM07 remains triggered in each confirmation profile.** There were two
military ends in F6 and six in CJON. All other runs reached the objective
decision at the deadline. For matched seeds LOW increased unresolved
draws by 6.64 percentage points against F6 (paired normal approximation
95% interval 1.89–11.39 points) and mean loss by 50.15 (47.79–52.51).
LOW combines allocation, exposure and pressure changes. Screening N and
F6 matched in their screening summaries, which offers limited evidence
about exposure when most targets start with full ranks.

| Profile | Centre classification at terminal, exclusive | Condition/contact/threat flags, overlapping |
| --- | --- | --- |
| R0 | 140 empty, 171 condition, 38 contact, 53 threat, 110 secure | 171/68/172 |
| F6 | 143 empty, 197 condition, 35 contact, 30 threat, 107 secure | 197/58/131 |
| CJON | 171 empty, 160 condition, 32 contact, 36 threat, 113 secure | 160/50/125 |
| LOW | 122 empty, 170 condition, 84 contact, 61 threat, 75 secure | 170/140/242 |

The terminal classification includes the last objective observation of
military ends. It can record secure occupation independently of the
winning predicate. When several reasons apply, the exclusive class uses
condition, then contact, then threat. Raw records preserve the overlapping
flags. First and last secure checkpoints and longest/total secure closure
counts are recorded per run. Closure streaks are sampled observations.

Round-three mean exhaustion among organized on-map formations was
48.30%/47.88% for R0 and 0%/0% for F6, CJON and LOW. There were 512
defined runs per side in each profile. R0 had median 50% on each side,
with 94 and 98 runs above 50% respectively. The carry profiles still
showed exhaustion-only denial later in the battle. The counted denials
are geometrically available front targets at each decision checkpoint.
A repeated observation can count the same target again.

## Screening and commander comparisons

Screening seeds 20000–20127 yielded R0 104, F6 99, C 100, J 97, O 98,
N 99, CJON 105 and LOW 108 unresolved runs out of 128 each. Screening
and confirmation use different seed sets.

The same screening seeds under F6 yielded 128 objective wins for
ADV/PASS with zero casualties. AGG/RES had 93 unresolved outcomes,
ADV/RES 120, and AGG/ADV 116. These are reduced deterministic commander
comparisons with shared seeds and preferred-candidate workload.

## Legacy H32 diagnostics

The H32 stream on the corrected resolver produced the following
confirmation results for the same named seed set. H32 is isolated from
the corrected experiment's EP08 default.

| Profile | H32 wins 0/1 | H32 unresolved | Archived unresolved | H32 minus archive |
| --- | --- | --- | --- | --- |
| R0 | 46/46 | 420 | 418 | +2 |
| F6 | 60/53 | 399 | 400 | -1 |
| CJON | 76/53 | 383 | 389 | -6 |
| LOW | 44/42 | 426 | 430 | -4 |

The archived runner's temporary code and raw logs are unavailable.
The H32 diagnostic uses current D3-conforming legality, the documented
tie decisions, and current quantile arithmetic. These affect exact
reproduction alongside the displacement correction.

A separate 128-pair F6 AGG/AGG diagnostic at 20000–20127 changed only
whether eligible exit cells stay occupied through arbitration. The
comparison preserves frozen threat and releases all eligible exit cells
together in the diagnostic branch to isolate the occupancy effect. The
synthetic edge regression exhibits the forbidden follow when the defect
is enabled. No mechanical terminal divergence was observed among these 128 matched
development pairs. This checks the selected seeds and
isolated variation. The original procedure could also depend on its
iteration order, which the comparator does not recreate.

The archived pooled F3 tendency persists, and the unresolved-draw warning
persists in the corrected confirmation. The H32 and EP08 run outputs
remain separately labelled. They provide no basis for RG03, full D4
validation or D5 readiness.

## Independent-review rerun

The reviewed baseline is `cda92e4b6ee9138fb421a2951777dbf88c7dcc64`.
The [baseline comparison](../../evidence/rg02/review-comparison.json)
validates each regenerated observation against its reviewed mechanical
fields. Existing outcomes, charged intervals, losses, objectives,
and recorded metrics and policy counts are unchanged.

The eight EP08 confirmation military wins, two F6 and six CJON, all
classify the losing side as collapse. This classification comes from
actual routing survivors. It leaves the broad military category, winner
and O0 result unchanged. The initial adjudication fix is exercised
separately by zero-action fixtures because the standard starting
formations on both sides are viable.

Trace digests changed in v2 because event records carry stream, resolver
variant and defeat classifications. Raw H32 comparator digests therefore
differ by variant even when the mechanics agree. The isolated occupancy
pairs still agree on terminal-state digests and existing mechanical
summary fields. Projecting the committed EP08 replay sample back to v1
reproduces all 92 reviewed event records.

The aggregate reports preserve the earlier point estimates. They add
sample counts and denominators, sample standard deviation, and type-7
P10/P90 (linear interpolation at zero-based index (n−1)p). Preferred-choice
counts are descriptive per decision. Multiple decisions can come from
one run, and this measure does not establish complete legal-action
workload or human usability. Paired casualty intervals now use one
difference per matched seed and a two-sided 95% Student t interval with
n−1 degrees of freedom. Insufficient paired samples yield no interval
in the numerical helper, and zero variance yields a point interval.
Report-level pairing requires at least two matched seeds.

## EP11 accounting rerun

Against the reviewed commit `7082b4aa156d612b231e393fc479725eb41157a3`,
all eight regenerated observation files are byte-identical. Existing
statistics and BM07 warnings match. The eight separate journals verify
3,584 corrected principal runs, 3,584 H32 principal runs, 256 mirror
executions and 256 isolated displacement executions. Each planned
identity has exactly one completed attempt. There are zero technical
stops, unfinished attempts or unattempted runs in these archived
executions. The [evidence manifest](../../evidence/rg02/manifest.json)
links each journal to its observation file and counts.
