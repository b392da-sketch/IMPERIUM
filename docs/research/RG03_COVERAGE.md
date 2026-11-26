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

## Individual acceptance evidence

**Isolated** means a named regression passed the applicable standalone
assertions. Mixed cases identify the campaign or fog clause kept outside
scope. **Integrated trace** names a verified member of the committed
evidence archive. The source identifiers refer to D3.1 T01–T06, the
D3.2–D3.6 CT/GT/BT/RT/ET tables, and the D3.9 AT table.

| Case | Disposition | Test and boundary |
| --- | --- | --- |
| T01 | Isolated | `tests.test_f01_source_cases.SourceCases.test_hm01_hm02_reject_invalid_fixture_inventory_and_lots`. Unique typed lots, lineage and conservation. Campaign splitting/merging excluded. |
| T02 | Isolated | `tests.test_f01.F01FoundationTests.test_exact_roster_and_mirror`. Exact starting roster, mounts, placements and stock. |
| T03 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt04_pivot_angle_and_threat_sources`. Six-direction and mirror geometry also checked by test_exact_roster_and_mirror and tests.test_foundation. |
| T04 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct01_ct10_ct11_opportunities_forfeiture_and_closure`. One interval and alternating starter. Tactical terminal ordering at ET18/ET19. |
| T05 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt01_bt02_missile_negative_and_stationary_debits`. Rejected orders preserve authoritative digest. Fog disclosure excluded. |
| T06 | Isolated | `tests.test_f01_research.ResearchTests.test_exact_development_manifest`. Separate versioned fixture and bounded standalone execution plan. No campaign API. |
| CT01 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct01_ct10_ct11_opportunities_forfeiture_and_closure`. Eight roots; unused ready actors forfeit; time advances once. |
| CT02 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct02_ct03_ct05_group_coverage_and_atomic_rejection`. Six group members plus two individuals in four slots. |
| CT03 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct02_ct03_ct05_group_coverage_and_atomic_rejection`. Overlapping spent members rejected without cost. |
| CT04 | Isolated | `tests.test_f01_resolver.ResolverTests.test_disabled_group_authority_preserves_local_control`. Local action remains legal after fixture authority flag is disabled. |
| CT05 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct02_ct03_ct05_group_coverage_and_atomic_rejection`. Stationary blocker and repeated member reject entire order. |
| CT06 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct06_rt05_paid_assault_then_response_then_free_resistance`. Effort 3 to 1 to 0; reciprocal resistance still contributes. |
| CT07 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct07_bt15_reaction_before_principal_and_round_shared_flag`. Response leaves ready flag intact and permits exact-cost subsequent assault. |
| CT08 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct08_gt09_declining_two_options_closes_root_window`. Two candidates, one decision across actual stages. Round flag checked by CT07. |
| CT09 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct09_pass_forfeits_two_slots_and_preserves_other_side_budget`. Two slots forfeited while opponent spends remaining slots; AT03 covers reactions. |
| CT10 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct01_ct10_ct11_opportunities_forfeiture_and_closure`. Hold consumes slot and readiness without effort debit; CT05 exercises invalid roots. |
| CT11 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct01_ct10_ct11_opportunities_forfeiture_and_closure`. Round closure, single clock debit and alternating starter; ET18 covers terminal before refresh. |
| CT12 | Isolated | `tests.test_f01_research.ResearchTests.test_scripted_replay_reexecutes_normalized_group_and_passes`. Exact actions and canonical mirrored replay; rejected order isolation at BT01. |
| GT01 | Isolated | `tests.test_f01.F01FoundationTests.test_exact_roster_and_mirror`. Opposite formation facing and mirrored coordinates; axial symmetry additionally covered by tests.test_foundation. |
| GT02 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt02_gt03_role_mobility_and_actual_rough_debit`. All three caps and occupied, nonfrontal and repeated path gates. |
| GT03 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt02_gt03_role_mobility_and_actual_rough_debit`. Heavy open plus rough actual debit and mounted cap-by-budget; GT08 covers barrier. |
| GT04 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt04_pivot_angle_and_threat_sources`. Zero, one and two threats; engaged pivot rejected; 180° costs three. |
| GT05 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt15_bt18_full_command_round_and_light_follow_on`. Both mirrored G1 translations in one live round. |
| GT06 | Inapplicable | Hidden obstructions are excluded by the open-information F01 fixture. Known dependency rejection remains tested at GT07. |
| GT07 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct02_ct03_ct05_group_coverage_and_atomic_rejection`. Stationary occupant rejects whole root; no individual displacement. |
| GT08 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt08_overlay_and_nontraversable_threat`. Overlapping projections, blocked melee edge and no automatic contact on entry. |
| GT09 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct08_gt09_declining_two_options_closes_root_window`. First eligible stage only and decline consumes window; RT03 covers revalidation. |
| GT10 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt10_pivot_only_on_new_adjacent_and_no_other_enemy`. Prior adjacency, multiple neighbors, engagement and routing forbid pivot. CT07 and AT03 cover remaining response budgets. |
| GT11 | Isolated | `tests.test_f01.F01FoundationTests.test_los_shared_edge_and_vertex`. Shared-edge overlap and vertex touch. test_los_and_edge_passability_independent covers directional edge opacity. |
| GT12 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt12_withdrawal_cost_and_blocking`. Rough rear cost and closed, threatened, occupied and off-map rejection. BT13 tests contact cleanup. |
| GT13 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt01_bt02_missile_negative_and_stationary_debits`. Known invalid action isolation. Hidden obstacle and disclosure clauses are out of F01 scope. |
| GT14 | Isolated | `tests.test_f01.F01FoundationTests.test_terrain_and_mount_shortfall`. Mounted shortfall changes rate without adding equipment. |
| GT15 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt15_bt18_full_command_round_and_light_follow_on`. Authored opening and subsequent round under a stipulated zero-effect packet. |
| BT01 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt01_bt02_missile_negative_and_stationary_debits`. Range, sector, stock, template and engagement. Separate occlusion test and GT08 barrier allowance. |
| BT02 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt01_bt02_missile_negative_and_stationary_debits`. Stationary discharge pays exactly once and opens no response. |
| BT03 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt03_assault_requires_actual_forward_adjacency`. Frontality, range, origin threat and no translation. GT08 covers blocked edges. |
| BT04 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt01_bt04_occluded_fire_and_existing_contact_has_no_window`. Persistent contact has no reaction. GT15 and the exact-cost pivot regression exercise live reaction choices. |
| BT05 | Isolated | `tests.test_f01_resolver.ResolverTests.test_defensive_missile_aborts_paid_assault`. Attack paid before disruption, no contact or refund. |
| BT06 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt09_neutral_coefficients_and_backward_inherent_resistance`. Zero-effort defender retains contribution and a single resistance mark. BT11 verifies simultaneous last losses. |
| BT07 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt07_bt08_bt10_packet_support_by_template`. Heavy 24/20/13 per link. BT04 verifies reselecting contact does not duplicate it. |
| BT08 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt07_bt08_bt10_packet_support_by_template`. Increasing depth leaves frontage contribution capped. |
| BT09 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt09_neutral_coefficients_and_backward_inherent_resistance`. Rear-facing defender retains resistance. D4-RP-0.1 uses neutral physical coefficients. |
| BT10 | Isolated | `tests.test_f01_source_cases.SourceCases.test_bt07_bt08_bt10_packet_support_by_template`. Weapon/template/low-strength cross-product. Injected invalid packet fails closed in test_invalid_precision_type_and_packets_fail_closed. |
| BT11 | Isolated | `tests.test_f01_resolver.ResolverTests.test_reciprocal_depletion_preserves_assets`. Both last casualties applied before mutual result; assets retained. |
| BT12 | Isolated | `tests.test_f01_resolver.ResolverTests.test_shared_contact_allocation_persists_across_rounds`. Contact survives closure without passive attack. |
| BT13 | Isolated | `tests.test_f01_resolver.ResolverTests.test_zero_allocation_and_controlled_disengagement`. Legal rear step breaks persistent contacts without a free strike. Hidden failure excluded. |
| BT14 | Isolated | `tests.test_f01_resolver.ResolverTests.test_shared_contact_allocation_persists_across_rounds`. Only selected pair contributes while other links reserve frontage. |
| BT15 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct07_bt15_reaction_before_principal_and_round_shared_flag`. Round response flag and shared effort; decline stage CT08. |
| BT16 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt04_three_actual_marks_carry_to_six_and_no_pass_recovery`. No second debit for expenditure. BT11 and AT04 exercise validated casualty/pressure handoff. |
| BT17 | Isolated | `tests.test_f01_research.ResearchTests.test_policy_replay_mirror_and_strict_type`. Canonical replay validates events and types. ET22 blocks later action. |
| BT18 | Isolated | `tests.test_f01_source_cases.SourceCases.test_gt15_bt18_full_command_round_and_light_follow_on`. Light assault and response in round two, with stage order and exact contact. |
| RT01 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt01_rt06_exhaustion_is_not_loss_of_threat`. Severe cohesion alone keeps living organized formation. |
| RT02 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et07_et17_blocked_mutual_collapse_has_no_extra_casualties`. Both rupture before terminal adjudication. |
| RT03 | Isolated | `tests.test_f01_resolver.ResolverTests.test_defensive_missile_aborts_paid_assault`. Precontact missile causes abort and retains paid effort. |
| RT04 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt04_three_actual_marks_carry_to_six_and_no_pass_recovery`. Two steps and a shot add three actual marks. D4-RP-0.1 raises fatigue at six. |
| RT05 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct06_rt05_paid_assault_then_response_then_free_resistance`. Zero effort inherent resistance still contributes, no new attack or ammo cost. |
| RT06 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt01_rt06_exhaustion_is_not_loss_of_threat`. Distinct exhaustion, wavering and severe gates. |
| RT07 | Isolated | `tests.test_f01_source_cases.SourceCases.test_ct06_rt05_paid_assault_then_response_then_free_resistance`. Melee threshold crossing moves defender to rear and unlinks. RT08 checks blocked alternative. |
| RT08 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt08_rt19_blocked_repulse_then_rout_shares_allowance`. Blocked repulse marks attempt and keeps valid contact. |
| RT09 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt09_rt12_frozen_threat_even_when_source_displaced`. Rout moves closer while respecting the original projections. |
| RT10 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et07_et17_blocked_mutual_collapse_has_no_extra_casualties`. Blocked routers keep surviving personnel, with no imposed capture. |
| RT11 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt11_rt21_contested_displacement_fallback_order_independent`. Contested first pick denied to both with distinct alternatives. |
| RT12 | Isolated | `tests.test_f01_resolver.ResolverTests.test_frozen_batch_does_not_follow_evacuating_primary`. Exit cell remains unavailable during simultaneous reservation. |
| RT13 | Isolated | `tests.test_f01_resolver.ResolverTests.test_shock_is_deduplicated_across_rout_waves`. Actual two-stage cascade affects adjacent observed allies only. |
| RT14 | Isolated | `tests.test_f01_resolver.ResolverTests.test_shock_is_deduplicated_across_rout_waves`. Recipient witnessing two allied breaks in the same root gets one increment. In standalone reciprocal combat the two direct targets are opponents. |
| RT15 | Isolated | `tests.test_f01_resolver.ResolverTests.test_safe_refuge_reformer_gates_and_later_rally`. Safe stationary closure creates reformer before a later paid rally. |
| RT16 | Isolated | `tests.test_f01_resolver.ResolverTests.test_safe_refuge_reformer_gates_and_later_rally`. Safe reformer rallies to 1/1 and organizes only at eligible closure. |
| RT17 | Isolated | `tests.test_f01_resolver.ResolverTests.test_interrupt_rest_with_safe_range_two_fire`. Zero-casualty interruption suppresses recovery. |
| RT18 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt04_three_actual_marks_carry_to_six_and_no_pass_recovery`. Pass/refresh preserves fatigue, roster and spent ammo. |
| RT19 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt08_rt19_blocked_repulse_then_rout_shares_allowance`. Second trigger changes disposition without new attempt; next opening resets flag. |
| RT20 | Isolated | `tests.test_f01_resolver.ResolverTests.test_reciprocal_depletion_preserves_assets`. Depleted primary removed and mounts conserved. Captured wound locations checked by ET16. |
| RT21 | Isolated | `tests.test_f01_source_cases.SourceCases.test_rt11_rt21_contested_displacement_fallback_order_independent`. Reversed input order produces same positions; all 48 transformed corpus pairs additionally match. |
| RT22 | Isolated | `tests.test_f01_research.ResearchTests.test_terminal_root_skips_pending_recovery`. Mandatory action resolves before terminal and pending recovery is cancelled. |
| ET01 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et01_et03_et04_objective_timing_and_exclusions`. Secure centre at round six does not end battle. |
| ET02 | Isolated | `tests.test_f01_research.ResearchTests.test_deadline_o0_and_completed_rest`. Secure organized centre wins only at deadline. |
| ET03 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et03_refuge_at_o0_is_still_insecure_until_organized`. Router/reformer remains insecure at deadline; empty case in ET01. |
| ET04 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et01_et03_et04_objective_timing_and_exclusions`. Threat and engagement separately prevent O0. |
| ET05 | Isolated | `tests.test_f01_research.ResearchTests.test_deadline_o0_and_completed_rest`. Exhausted organized centre is secure. |
| ET06 | Isolated | `tests.test_f01_resolver.ResolverTests.test_reciprocal_rout_and_local_shock`. Blue last viable routs, Red ally survives and wins. |
| ET07 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et07_et17_blocked_mutual_collapse_has_no_extra_casualties`. Reciprocal mutual break before choosing result. |
| ET08 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et08_only_reformer_preserves_viability`. The sole Blue survivor is viable and can hold while ordinary movement remains unavailable. |
| ET09 | Isolated | `tests.test_f01_resolver.ResolverTests.test_withdrawal_posture_costs_opportunity_and_precedes_o0`. Declaration costs side slot, leaves position and disables offensive orders. |
| ET10 | Isolated | `tests.test_f01_resolver.ResolverTests.test_withdrawal_posture_costs_opportunity_and_precedes_o0`. Withdrawing secure occupier loses by abandonment at deadline. |
| ET11 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et11_both_withdraw_then_one_exits_and_capitulation_precedence`. Mutual abandonment versus surrender precedence. |
| ET12 | Isolated | `tests.test_f01_resolver.ResolverTests.test_orderly_departure_and_mutual_abandonment`. Last viable side evacuated intact, opposite contesting side wins. |
| ET13 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et13_safe_own_edge_still_requires_two_effort`. Insufficient effort with no mutation. Wrong boundary and hostile safety in test_voluntary_exit_requires_designated_edge_and_safety. Hidden interruption excluded. |
| ET14 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et14_et15_edge_arrival_and_exit_are_distinct_attempts`. Same-round arrival cannot exit on the consumed attempt. |
| ET15 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et14_et15_edge_arrival_and_exit_are_distinct_attempts`. Next eligible closure exits rather than reforming. |
| ET16 | Isolated | `tests.test_f01_resolver.ResolverTests.test_captured_wounds_preserve_field_location_and_lineage`. Evacuated formation survives in holding; on-map and field wound custody preserve lineage. |
| ET17 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et07_et17_blocked_mutual_collapse_has_no_extra_casualties`. Blocked collapse invents neither capture nor movement. |
| ET18 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et18_closure_terminal_order_defensive_state`. Boundary-only fixture isolates the defensive terminal guard before recovery. Ordinary F01 root adjudication already stops zero viability before closure. |
| ET19 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et19_standalone_terminal_round_five_freezes_clock`. Standalone portion ends at minute 50 and freezes. External timed arrivals excluded. |
| ET20 | Isolated | `tests.test_f01_research.ResearchTests.test_replay_initial_terminal_without_an_action_root`. Zero elapsed before a root and deterministic result on replay. |
| ET21 | Isolated | `tests.test_f01_research.ResearchTests.test_deadline_o0_and_completed_rest`. Passes still charge rounds through the deadline and never create an earlier draw. |
| ET22 | Isolated | `tests.test_f01_research.ResearchTests.test_replay_initial_terminal_without_an_action_root`. Postterminal rejection and digest covered in test_round_zero_terminal_and_observation_isolation. Replay is type-sensitive. |
| ET23 | Integrated trace | open-22000-0.jsonl ↔ open-22000-1.jsonl Matching canonical root sequence and digests. All 48 pairs checked; asset transfer cases ET16 and BT11. |
| ET24 | Isolated | `tests.test_f01_resolver.ResolverTests.test_round_zero_terminal_and_observation_isolation`. Standalone owner/controller visibility. Hidden fog and campaign handoff excluded. |
| AT01 | Isolated | `tests.test_f01_resolver.ResolverTests.test_last_opportunity_group_commits_selected_following`. Last opportunity commits group before forfeiture, actual moves complete once. |
| AT02 | Isolated | `tests.test_f01_resolver.ResolverTests.test_exact_paid_assault_and_defensive_pivot`. Accepted two effort continues after paying it. |
| AT03 | Isolated | `tests.test_f01_resolver.ResolverTests.test_reaction_after_pass_routs_and_interrupts_path`. Passage after pass still permits a valid reaction; one window and one debit. |
| AT04 | Isolated | `tests.test_f01_resolver.ResolverTests.test_zero_allocation_and_controlled_disengagement`. Single personnel spread over two links yields zero contribution, principal still paid. |
| AT05 | Isolated | `tests.test_f01.F01FoundationTests.test_group_follows_only_selected_vacating_members`. Known selected-vacating dependency passes. Hidden dependency pruning excluded by open-information boundary. |
| AT06 | Isolated | `tests.test_f01_resolver.ResolverTests.test_response_after_spent_principal_and_condition_cap`. Actual response cuts legal cap and unused second step stays unpaid. Known exhaustion path rejected separately. |
| AT07 | Isolated | `tests.test_f01_resolver.ResolverTests.test_safe_refuge_reformer_gates_and_later_rally`. Reformer viable with limited safe choices, and organized after later recovery. |
| AT08 | Isolated | `tests.test_f01_resolver.ResolverTests.test_captured_wounds_preserve_field_location_and_lineage`. Standalone exit/custody separation. Campaign provision charging excluded. |
| AT09 | Isolated | `tests.test_f01_source_cases.SourceCases.test_et19_standalone_terminal_round_five_freezes_clock`. Standalone timing only. Arrival admission and cross-mode tick tests excluded. |
| AT10 | Inapplicable | Campaign access-cell admission and external reserve placement are outside standalone F01. |
| AT11 | Inapplicable | Campaign supply splitting, reserves and shortage are outside standalone F01. |
| AT12 | Inapplicable | Campaign shortage and readiness application are outside standalone F01. Tactical terminal is independently covered by RT22 and ET19. |
| AT13 | Inapplicable | Compulsory post-battle campaign settlement is outside standalone F01. |
| AT14 | Inapplicable | Inbound campaign route reservation excluded. Local rear-edge obstruction separately checked at GT12. |
| AT15 | Isolated | `tests.test_f01_resolver.ResolverTests.test_evacuation_captures_no_offboard_assets`. Tactical offboard holding conserved through terminal. Assembly is a later campaign action. |
| AT16 | Inapplicable | Campaign control-order timing outside standalone F01. |
| AT17 | Isolated | `tests.test_f01_resolver.ResolverTests.test_invalid_precision_type_and_packets_fail_closed`. Invalid stage faults resolver. Legitimate blocked retreat remains military outcome at ET17. |
| AT18 | Isolated | `tests.test_f01_resolver.ResolverTests.test_round_zero_terminal_and_observation_isolation`. Own resource ledger without enemy casualty detail or seed. Controller parity/replay at CT12. |
| AT19 | Isolated | `tests.test_f01_research.ResearchTests.test_scripted_replay_reexecutes_normalized_group_and_passes`. Standalone replay parity. Campaign commit, external arrival overwrite and transaction recovery excluded. |
| AT20 | Integrated trace | open-22000-0.jsonl ↔ open-22000-1.jsonl F01 mirror, per-root personnel/mount/ammo invariants and exact roster. Campaign provision figure excluded. |
| AT21 | Inapplicable | Depot access and convoy loading are campaign operations. |
| AT22 | Inapplicable | Strategic deadline and external admission are outside standalone F01. Tactical deadline/terminal freeze at ET13/ET19/ET21. |

## Individual amendment dispositions

The case IDs below point to exact test and artifact references in the
individual register. An applicable standalone clause remains tested when
the same amendment also governs an excluded campaign operation.

| Amendment | Disposition | Governing boundary and implementation |
| --- | --- | --- |
| A01 | Isolated | CT05, GT05, GT07 and RT12. `movement.group_translation` allows selected vacating cells only in group translation. `F01.displace` uses frozen occupancy. |
| A02 | Isolated | CT01, CT09, AT01 and ET09. `F01.resolve_accepted` commits once, and `advance_side` forfeits remaining readiness after the current order. |
| A03 | Isolated | AT02, BT05 and RT03. `F01.validate` checks the initial effort. `assault` revalidates the actual geometry after the response without charging effort twice. |
| A04 | Isolated | GT01 and GT11. `geometry.distance` and `Terrain.line_of_sight` enforce axial distance and exact positive-length intersections. |
| A05 | Isolated | GT02, GT09 and AT06. `movement.path_cost` rejects a known excess path. `resolve_accepted` checks actual stops after each response leg. Unseen obstacles are outside F01. |
| A06 | Isolated | GT10, BT01 and BT04. `missile_legal` blocks both engaged endpoints. `reaction_options` applies the assault-specific pivot exception and one root window. |
| A07 | Isolated | BT07, BT08, BT14 and AT04. `combat.contribution` caps shared frontage; `assault` includes temporary contact with a router. |
| A08 | Isolated | BT10, BT11 and BT16. `packets` validates packet support and calculates both directions before applying losses. `mark` accounts for actual exertion separately. |
| A09 | Isolated | RT06 and AT07. `projected`, `validate` and the reaction gates distinguish condition, fatigue, disposition and movement limits. |
| A10 | Isolated | RT08, RT11, RT12 and RT19. `displace` freezes occupancy and threat before reservation, with one shared attempt per formation. |
| A11 | Isolated | RT13–RT17. `pressure` captures local witnesses and `packets` deduplicates recipients per root. The safe-interval ledger uses actual exposure and effects. |
| A12 | Isolated | ET12–ET16 and AT08. `leave` and `surrender` reconcile standalone escape, custody, ammo and mounts. Campaign pooled provision is excluded. |
| A13 | Isolated | CT11, RT22 and ET18–ET20. Tactical compulsory movement and terminal checkpoints precede refresh and recovery. Campaign timing remains outside scope. |
| A14 | Inapplicable | Campaign arrival and reinforcement admission are excluded. T02 checks the fixed initial standalone roster. |
| A15 | Isolated | ET22 and AT19 for a canonical standalone state and replay. Campaign lease and posting transactions are excluded. |
| A16 | Inapplicable | Settlement, reserves and beneficiary portions apply to campaign accounting. Standalone casualty and inventory partitions are checked separately as HM01/HM02. |
| A17 | Inapplicable | Detachment, convoy and depot operations are outside standalone F01. |
| A18 | Inapplicable | F02 protected withdrawal and compulsory settlement are outside standalone F01. |
| A19 | Isolated | ET16 and AT15 verify actual standalone holding/custody and no tactical reentry. Offboard campaign assembly and aftermath processing are excluded. |
| A20 | Inapplicable | Strategic control and campaign task timing are outside standalone F01. |
| A21 | Isolated | T05, ET24 and AT18. `F01.observe` supplies the permitted open tactical view and withholds authoritative enemy losses and future RNG. Fog and campaign disclosure are excluded. |
| A22 | Isolated | RT04 and RT18 for the tactical ledger under D4-RP-0.1 six-mark carry. Campaign marching and assembly accumulators are outside this milestone. |
| A23 | Isolated | ET01–ET10 and ET20. `adjudicate`, `objective` and `close_round` retain existing viability and O0, including reformer viability and exhausted-holder security. |
| A24 | Isolated | AT17 checks a standalone invalid effect fails closed. Unsupported strategic encounter cases are outside standalone F01. |
| A25 | Isolated | GT01 tests the corrected axial distance semantics and BT11 checks typed packet application. Editorial fixes to campaign examples need no F01 execution. |

## Hard-invariant register

| ID | Disposition | Enforcement and regression evidence |
| --- | --- | --- |
| HM01 | Isolated | `F01.check_invariants` enforces population and inventory conservation, unique typed casualty lots and their lineage. T01, RT20 and ET16. |
| HM02 | Isolated | Spending happens at the actual stage and captured inventory stays distinct. CT06/07, BT02, RT19 and ET16. Invalid fixture stock types fail through T01. |
| HM03 | Isolated | `check_invariants`, `Terrain`, `group_translation` and `combat.contribution` enforce occupancy, edge/LOS and participation. GT05/08/11, BT07/10 and AT04. |
| HM04 | Isolated | CT01/08/09, RT14/19 and the independent principal candidate comparison in `tests.test_f01_source_cases.SourceCases.test_exhaustive_principal_enumeration_matches_validator`. Response candidates, both selections, decline and malformed reaction identity also verified in `tests.test_f01_source_cases.SourceCases.test_reaction_candidates_are_authoritative_for_both_choices_and_decline`. |
| HM05 | Isolated | CT11, RT22, ET18–ET22. Tactical time only and no terminal mutation. External admission excluded. |
| HM06 | Integrated trace | ET23 names one pair. All 48 transformed pairs and 96 type-sensitive canonical replays were checked. BT11 and RT21 direct reciprocal and permutation tests. |
| HM07 | Isolated | AT18 tests observation isolation, CT12 parity and ET22 no continued mutation. Campaign isolation and secrecy tests beyond the public tactical fixture are outside scope. |
| HM08 | Isolated | BT10 exercises bounded numeric support across eligible templates/stages and test injection of invalid packets. The binomial trial count is capped by exposure, fatality trials are bounded by losses, and pressure uses two trials. All invariant checks also run during the matrix. |

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
