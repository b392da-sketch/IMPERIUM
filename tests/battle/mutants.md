# Targeted mutant inventory (contract 16.3)

Each mutant is applied to a disposable copy of `imperium/battle/` outside the
working tree, and the mandatory suite is run against it. Status records the
result on the acceptance commit.

**Status in this submission: inventory recorded, mutants not yet executed.**
The runs are pending and will be added here with each kill, equivalence or
redundancy note before acceptance is claimed.

| # | Mutant | Killing oracle | Status |
| --- | --- | --- | --- |
| 1 | `type(x) is int` replaced by `isinstance(x, int)` | V05, V06, AT-C02 | not run |
| 2 | Nested record checking bypassed | AT-C07, V18 | not run |
| 3 | An unsorted keyed tuple normalized instead of rejected | V12, AT-C05 | not run |
| 4 | The duplicate-key hook dropped | AT-C03 | not run |
| 5 | Genesis pinning skipped for the Terminal fixture | AT-O09(b), AT-T05 | not run |
| 6 | Normalized digest used for the event link | AT-O16 | not run |
| 7 | Work mode inferred from the final state | AT-M10, AT-M16, AT-M17, AT-W29 | not run |
| 8 | The leg's source edge omitted from entry cost | AT-W26 | not run |
| 9 | Terminal previewing fresh capacity | AT-Q02 | not run |
| 10 | A response charged twice | AT-W03b, AT-W14 | not run |
| 11 | Usable and raw capacity conflated | AT-W14, AT-Q01 | not run |
| 12 | Current facing required for a persistent contact | AT-K03 | not run |
| 13 | Totals summed by custody instead of lineage | AT-L12 | not run |
| 14 | An arbitrary `ValueError` converted into a `DecodeError` | AT-C08 | not run |
| 15 | `≤` changed to `<` in the movement-mode rule | AT-M08 | not run |
| 16 | The `ADV-` prefix check dropped | AT-O08 | not run |
| 17 | Objective step 3 and step 4 swapped | AT-Q05 | not run |
| 18 | DEPARTURE allowed with a DEPLETED formation | AT-T15 | not run |
| 19 | R24 requires present MOUNTED mode or battlefield presence | AT-M16, AT-M17, AT-W35d | not run |
| 20 | Parse hooks raise immediately instead of deferring to the stage 3 priority | AT-C03b | not run |
| 21 | R23 rejects a nonmember later found on a recorded destination | AT-W36 | not run |

## Sweep workload (16.1)

Measured on CPython 3.12.13, this container:

- Per-push run (every 17th node, all edit kinds): 2,943 single edits plus 1,000 seeded multi-edits, about 20 s.
- Full run (`IMPERIUM_FULL_SWEEP=1`): 49,868 single edits, 3 min 47 s, all passing.
