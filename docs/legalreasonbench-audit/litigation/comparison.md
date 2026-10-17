# LegalReasonBench blind audit comparison

> AI-generated audit judgments; no human verification or benchmark score correction is established. Authority verification labels are the auditors' assertions; citation-check results are separate.

Agreement buckets use the two saved blind reports only. Reconciliation is counted separately and never replaces a blind report. Each criterion takes the strongest status among that report's findings. A criterion can occur in multiple categories; category counts deduplicate within task and category. Missing reports are unavailable, never zero findings. Counts describe AI reviewer judgments, not human-verified errors or corrected benchmark scores.

Scope: 11 assignments, 179 criteria including penalties.

| Report | Available / expected | Criteria with report | Findings | Flagged criteria | Problematic | Arguable |
|---|---|---|---|---|---|---|
| GPT-6 Sol (blind) | 11 / 11 | 179 | 31 | 51 / 179 (28.5%) | 35 / 179 (19.6%) | 16 / 179 (8.9%) |
| Claude Opus 5.5 (blind) | 11 / 11 | 179 | 33 | 43 / 179 (24.0%) | 12 / 179 (6.7%) | 31 / 179 (17.3%) |
| Final reconciliation | 0 / 11 | 0 | unavailable | unavailable | unavailable | unavailable |

Category totals count distinct task-criterion pairs within each category. They may sum above the overall flagged-criterion count.

| Category | Sol blind flagged criteria | Opus blind flagged criteria | Final flagged criteria |
|---|---|---|---|
| legal_error | 8 / 179 (4.5%) | 10 / 179 (5.6%) | unavailable |
| unsupported_fact | 6 / 179 (3.4%) | 8 / 179 (4.5%) | unavailable |
| source_conflict | 4 / 179 (2.2%) | 5 / 179 (2.8%) | unavailable |
| internal_inconsistency | 5 / 179 (2.8%) | 6 / 179 (3.4%) | unavailable |
| ambiguous_or_unjudgeable | 4 / 179 (2.2%) | 11 / 179 (6.1%) | unavailable |
| unrequested_requirement | 13 / 179 (7.3%) | 3 / 179 (1.7%) | unavailable |
| document_defect | 11 / 179 (6.1%) | 0 / 179 (0.0%) | unavailable |

## Blind agreement

Paired reports cover 11 assignments and 179 criteria.

| Bucket | Criteria |
|---|---|
| Both models: problematic | 9 |
| Both models: arguable | 6 |
| Both flagged, different strength (one problematic, one arguable) | 16 |
| Flagged by GPT-6 Sol only | 20 |
| Flagged by Claude Opus 5.5 only | 12 |
| Unflagged by both blind reports | 116 |

## Per-criterion comparison

| Task / criterion | GPT-6 Sol blind | Opus blind | Blind bucket | Final reconciliation |
|---|---|---|---|---|
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_order_granting_petition | problematic | unflagged | sol_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_circuit_court_found_that | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_circuit_court_found_th_2 | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_circuit_court_found_th_3 | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_circuit_court_found_th_4 | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / mentions_in_the_first_assignment_that_the_county_s_prior_rezonin | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_under_lee_county_fla_admin_c | problematic | problematic | both_problematic | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_dci2018_10023_remained_activ | problematic | problematic | both_problematic | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / mentions_in_the_first_assignment_that_the_subject_property_was_p | unflagged | arguable | opus_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_effect_of_the_order_gran | problematic | arguable | split | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_must_stop_constru | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_exclusive_method_of_revi | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_exclusive_method_of_chal | problematic | arguable | split | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_under_fla_stat_163_3167_10_2 | problematic | problematic | both_problematic | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_petitioners_may_file_a_s | arguable | arguable | both_arguable | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_appeal_the | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_remand_the | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_file_a_new | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_voluntarily | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_take_the_po | unflagged | arguable | opus_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_negotiate_f | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_could_negotiate_2 | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_should_file_a_tim | arguable | unflagged | sol_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_should_remand_the | arguable | unflagged | sol_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-1 / states_in_the_first_assignment_that_the_county_should_cease_cons | problematic | arguable | split | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / identifies_in_the_second_assignment_that_the_appropriate_mechani | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_by | arguable | unflagged | sol_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_staff_report_recommendi | arguable | unflagged | sol_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_expert_testimony_on_the_rec | arguable | unflagged | sol_only | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_hearing_examiner_s_reco | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_2 | arguable | problematic | split | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_in | problematic | arguable | split | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_3 | arguable | problematic | split | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_4 | problematic | problematic | both_problematic | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_i_2 | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_5 | unflagged | unflagged | — | unavailable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_s_erred_b | problematic | problematic | both_problematic | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_2 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_4 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_5 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_6 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_7 | arguable | arguable | both_arguable | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_8 | problematic | problematic | both_problematic | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-1 / criterion_9 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_2 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_4 | arguable | arguable | both_arguable | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_5 | unflagged | arguable | opus_only | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_6 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_7 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_8 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_9 | arguable | problematic | split | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_10 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_11 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-2 / criterion_12 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_2 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_4 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_5 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_6 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_7 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_8 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_9 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_10 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_11 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_12 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_13 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_14 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_15 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-3 / criterion_16 | arguable | unflagged | sol_only | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_2 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_4 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_5 | unflagged | arguable | opus_only | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_6 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_7 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_8 | arguable | arguable | both_arguable | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-4 / criterion_9 | unflagged | arguable | opus_only | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_1 | problematic | arguable | split | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_2 | arguable | arguable | both_arguable | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_4 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_5 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_6 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_7 | unflagged | unflagged | — | unavailable |
| lrb-dcca-challenge-police-discipline-assignment-5 / criterion_8 | arguable | arguable | both_arguable | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_2 | unflagged | arguable | opus_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_5 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_7 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_8 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_9 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_10 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_11 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_12 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_13 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_14 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_16 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_15 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_17 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_18 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_28 | unflagged | arguable | opus_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_29 | unflagged | arguable | opus_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_19 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_20 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_21 | problematic | arguable | split | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_23 | problematic | unflagged | sol_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_25 | unflagged | arguable | opus_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_27 | unflagged | arguable | opus_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-1 / criterion_26 | unflagged | arguable | opus_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_2 | unflagged | unflagged | — | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_3 | problematic | arguable | split | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_4 | problematic | problematic | both_problematic | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_5 | problematic | arguable | split | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_6 | problematic | arguable | split | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_7 | problematic | arguable | split | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_8 | problematic | arguable | split | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_9 | problematic | unflagged | sol_only | unavailable |
| lrb-vicar-trial-jury-instructions-assignment-2 / criterion_10 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_1 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_2 | arguable | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_3 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_4 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_30 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_5 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_6 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_7 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_8 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_9 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_10 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_11 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_12 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_13 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_15 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_16 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_17 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_18 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_19 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_20 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_21 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_22 | unflagged | arguable | opus_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_23 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_24 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_25 | problematic | problematic | both_problematic | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_26 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_27 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_28 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-1 / criterion_29 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_1 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_2 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_3 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_4 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_5 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_6 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_7 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_8 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_9 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_10 | problematic | unflagged | sol_only | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_11 | problematic | arguable | split | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_12 | problematic | arguable | split | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_13 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_14 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_15 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_16 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_17 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_18 | problematic | problematic | both_problematic | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_19 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_20 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_21 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_22 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_23 | unflagged | unflagged | — | unavailable |
| lrb-forum-non-conveniens-response-assignment-2 / criterion_24 | unflagged | unflagged | — | unavailable |
