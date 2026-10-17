# Audit: lrb-vicar-trial-jury-instructions-assignment-2

> AI-generated audit judgments; no human verification or benchmark score correction is established. Authority verification labels are the auditors' assertions; citation-check results are separate.

[Source inputs](input.json) · [Instructions and prior prompts](instruction.md) · [Native upstream instructions](upstream-instruction.md)

Agreement buckets use the two saved blind reports only. Reconciliation is counted separately and never replaces a blind report. Each criterion takes the strongest status among that report's findings. A criterion can occur in multiple categories; category counts deduplicate within task and category. Missing reports are unavailable, never zero findings. Counts describe AI reviewer judgments, not human-verified errors or corrected benchmark scores.

| Report | Available / expected | Criteria with report | Findings | Flagged criteria | Problematic | Arguable |
|---|---|---|---|---|---|---|
| GPT-6 Sol (blind) | 1 / 1 | 10 | 2 | 7 / 10 (70.0%) | 7 / 10 (70.0%) | 0 / 10 (0.0%) |
| Claude Opus 5.5 (blind) | 1 / 1 | 10 | 3 | 6 / 10 (60.0%) | 1 / 10 (10.0%) | 5 / 10 (50.0%) |
| Final reconciliation | 0 / 1 | 0 | unavailable | unavailable | unavailable | unavailable |

Category totals count distinct task-criterion pairs within each category. They may sum above the overall flagged-criterion count.

| Category | Sol blind flagged criteria | Opus blind flagged criteria | Final flagged criteria |
|---|---|---|---|
| legal_error | 0 / 10 (0.0%) | 0 / 10 (0.0%) | unavailable |
| unsupported_fact | 0 / 10 (0.0%) | 1 / 10 (10.0%) | unavailable |
| source_conflict | 1 / 10 (10.0%) | 1 / 10 (10.0%) | unavailable |
| internal_inconsistency | 0 / 10 (0.0%) | 0 / 10 (0.0%) | unavailable |
| ambiguous_or_unjudgeable | 0 / 10 (0.0%) | 4 / 10 (40.0%) | unavailable |
| unrequested_requirement | 6 / 10 (60.0%) | 0 / 10 (0.0%) | unavailable |
| document_defect | 0 / 10 (0.0%) | 0 / 10 (0.0%) | unavailable |

Reports:

- [GPT-6 Sol (blind)](gpt-6-sol-audit.md)
- [Claude Opus 5.5 (blind)](claude-opus-5-5-audit.md)
- [Final reconciliation](reconciliation.md)

## Per-criterion comparison

| Task / criterion | GPT-6 Sol blind | Opus blind | Blind bucket | Final reconciliation |
|---|---|---|---|---|
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
