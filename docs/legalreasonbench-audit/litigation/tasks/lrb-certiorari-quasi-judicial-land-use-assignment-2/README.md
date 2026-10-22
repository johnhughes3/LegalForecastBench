# Audit: lrb-certiorari-quasi-judicial-land-use-assignment-2

> AI-generated audit judgments; no human verification or benchmark score correction is established. Authority verification labels are the auditors' assertions; citation-check results are separate.

[Source inputs](input.json) · [Instructions and prior prompts](instruction.md) · [Native upstream instructions](upstream-instruction.md)

Agreement buckets use the two saved blind reports only. Reconciliation is counted separately and never replaces a blind report. Each criterion takes the strongest status among that report's findings. A criterion can occur in multiple categories; category counts deduplicate within task and category. Missing reports are unavailable, never zero findings. Counts describe AI reviewer judgments, not human-verified errors or corrected benchmark scores.

| Report | Available / expected | Criteria with report | Findings | Flagged criteria | Problematic | Arguable |
|---|---|---|---|---|---|---|
| GPT-6 Sol (blind) | 1 / 1 | 12 | 5 | 8 / 12 (66.7%) | 3 / 12 (25.0%) | 5 / 12 (41.7%) |
| Claude Opus 5.5 (blind) | 1 / 1 | 12 | 4 | 5 / 12 (41.7%) | 4 / 12 (33.3%) | 1 / 12 (8.3%) |
| Final reconciliation | 1 / 1 | 12 | 4 | 5 / 12 (41.7%) | 4 / 12 (33.3%) | 1 / 12 (8.3%) |

Category totals count distinct task-criterion pairs within each category. They may sum above the overall flagged-criterion count.

| Category | Sol blind flagged criteria | Opus blind flagged criteria | Final flagged criteria |
|---|---|---|---|
| legal_error | 2 / 12 (16.7%) | 3 / 12 (25.0%) | 3 / 12 (25.0%) |
| unsupported_fact | 4 / 12 (33.3%) | 2 / 12 (16.7%) | 2 / 12 (16.7%) |
| source_conflict | 2 / 12 (16.7%) | 0 / 12 (0.0%) | 0 / 12 (0.0%) |
| internal_inconsistency | 0 / 12 (0.0%) | 0 / 12 (0.0%) | 0 / 12 (0.0%) |
| ambiguous_or_unjudgeable | 0 / 12 (0.0%) | 0 / 12 (0.0%) | 0 / 12 (0.0%) |
| unrequested_requirement | 0 / 12 (0.0%) | 0 / 12 (0.0%) | 0 / 12 (0.0%) |
| document_defect | 0 / 12 (0.0%) | 0 / 12 (0.0%) | 0 / 12 (0.0%) |

Reports:

- [GPT-6 Sol (blind)](gpt-6-sol-audit.md)
- [Claude Opus 5.5 (blind)](claude-opus-5-5-audit.md)
- [Final reconciliation](reconciliation.md)

## Per-criterion comparison

| Task / criterion | GPT-6 Sol blind | Opus blind | Blind bucket | Final reconciliation |
|---|---|---|---|---|
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / identifies_in_the_second_assignment_that_the_appropriate_mechani | unflagged | unflagged | — | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_by | arguable | unflagged | sol_only | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_staff_report_recommendi | arguable | unflagged | sol_only | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_expert_testimony_on_the_rec | arguable | unflagged | sol_only | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_hearing_examiner_s_reco | unflagged | unflagged | — | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_2 | arguable | problematic | split | problematic |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_in | problematic | arguable | split | arguable |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_3 | arguable | problematic | split | problematic |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_4 | problematic | problematic | both_problematic | problematic |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_i_2 | unflagged | unflagged | — | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_erred_b_5 | unflagged | unflagged | — | unflagged |
| lrb-certiorari-quasi-judicial-land-use-assignment-2 / states_in_the_second_assignment_that_the_circuit_court_s_erred_b | problematic | problematic | both_problematic | problematic |
