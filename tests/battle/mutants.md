# Targeted mutant inventory (contract 16.3)

Each mutant is applied to a disposable copy of `imperium/battle/` outside the
working tree, and the mandatory suite is run against it. Status records the
result on the acceptance commit.

**Status:** run externally by the Codex review of PR #4 at `5aa08ea` (isolated
copies, named oracles plus the mandatory suite in fail-fast mode). Results
below are that review's; rows 8 and 9 were re-checked locally after the
review fixes.

| # | Mutant | Killing oracle | Status |
| --- | --- | --- | --- |
| 1 | `type(x) is int` replaced by `isinstance(x, int)` | V05, V06, AT-C02 | killed by its named oracle and by the mandatory suite |
| 2 | Nested record checking bypassed | AT-C07, V18 | killed by its named oracle and by the mandatory suite |
| 3 | An unsorted keyed tuple normalized instead of rejected | V12, AT-C05 | killed by its named oracle and by the mandatory suite |
| 4 | The duplicate-key hook dropped | AT-C03 | killed by its named oracle and by the mandatory suite |
| 5 | Genesis pinning skipped for the Terminal fixture | AT-O09(b), AT-T05 | killed by its named oracle and by the mandatory suite |
| 6 | Normalized digest used for the event link | AT-O16 | deferred to DO-09/DO-10: P1 has no event-chain writer; no kill claimed |
| 7 | Work mode inferred from the final state | AT-M10, AT-M16, AT-M17, AT-W29 | killed by its named oracle and by the mandatory suite |
| 8 | The leg's source edge omitted from entry cost | AT-W26 | killed at 5aa08ea only via AT-W03 (different oracle); AT-W26 now calls `charge` on the closed barrier edge and kills it directly |
| 9 | Terminal previewing fresh capacity | AT-Q02 | survived at 5aa08ea; AT-Q02/Q03 now assert the full Terminal column (`projected_capacity`, `capacity_remaining` None) and kill it |
| 10 | A response charged twice | AT-W03b, AT-W14 | killed by its named oracle and by the mandatory suite |
| 11 | Usable and raw capacity conflated | AT-W14, AT-Q01 | killed by its named oracle and by the mandatory suite |
| 12 | Current facing required for a persistent contact | AT-K03 | killed by its named oracle and by the mandatory suite |
| 13 | Totals summed by custody instead of lineage | AT-L12 | killed by its named oracle and by the mandatory suite |
| 14 | An arbitrary `ValueError` converted into a `DecodeError` | AT-C08 | killed by its named oracle and by the mandatory suite |
| 15 | `≤` changed to `<` in the movement-mode rule | AT-M08 | killed by its named oracle and by the mandatory suite |
| 16 | The `ADV-` prefix check dropped | AT-O08 | killed by its named oracle and by the mandatory suite |
| 17 | Objective step 3 and step 4 swapped | AT-Q05 | killed by its named oracle and by the mandatory suite |
| 18 | DEPARTURE allowed with a DEPLETED formation | AT-T15 | killed by its named oracle and by the mandatory suite |
| 19 | R24 requires present MOUNTED mode or battlefield presence | AT-M16, AT-M17, AT-W35d | killed by its named oracle and by the mandatory suite |
| 20 | Parse hooks raise immediately instead of deferring to the stage 3 priority | AT-C03b | killed by its named oracle and by the mandatory suite |
| 21 | R23 rejects a nonmember later found on a recorded destination | AT-W36 | killed by its named oracle and by the mandatory suite |

## Sweep workload (16.1)

Measured on CPython 3.12.13, this container:

- Per-push run (every 17th node, all edit kinds): 2,943 single edits plus 1,000 seeded multi-edits, about 20 s.
- Full run (`IMPERIUM_FULL_SWEEP=1`): 49,868 single edits, 3 min 47 s, all passing.
