# Comparison with the Harvey LAB audit

> AI-generated audit judgments; no human verification or benchmark score correction is established. Authority verification labels are the auditors' assertions; citation-check results are separate.

LegalReasonBench agreement uses two blind reports. Harvey agreement uses Sol's original report and Opus's final reconciled report, which saw Sol. These agreement counts are not directly comparable. Category comparisons below use Harvey's final Opus findings versus LegalReasonBench's separate final reconciliation. Neither is human verification; the corpora and denominators also differ. Harvey Sol reports lack the common category taxonomy and are not assigned invented categories.

| Audit | Criteria | Flagged criteria in agreement comparison |
|---|---|---|
| LegalReasonBench (paired blind reports) | 179 | 63 / 179 (35.2%) |
| Harvey (original Sol / reconciled Opus) | 2858 | 835 / 2858 (29.2%) |

| Category | Harvey final Opus flagged criteria | LegalReasonBench final flagged criteria |
|---|---|---|
| legal_error | 159 / 2858 (5.6%) | unavailable |
| unsupported_fact | 34 / 2858 (1.2%) | unavailable |
| source_conflict | 72 / 2858 (2.5%) | unavailable |
| internal_inconsistency | 38 / 2858 (1.3%) | unavailable |
| ambiguous_or_unjudgeable | 92 / 2858 (3.2%) | unavailable |
| unrequested_requirement | 106 / 2858 (3.7%) | unavailable |
| document_defect | 78 / 2858 (2.7%) | unavailable |

Category denominators are criteria covered by each final report; categories overlap and do not sum to an error rate.

| Agreement bucket | LegalReasonBench blind | Harvey original / reconciled |
|---|---|---|
| Both models: problematic | 9 / 179 (5.0%) | 83 / 2858 (2.9%) |
| Both models: arguable | 6 / 179 (3.4%) | 135 / 2858 (4.7%) |
| Both flagged, different strength (one problematic, one arguable) | 16 / 179 (8.9%) | 127 / 2858 (4.4%) |
| Flagged by GPT-6 Sol only | 20 / 179 (11.2%) | 271 / 2858 (9.5%) |
| Flagged by Claude Opus 5.5 only | 12 / 179 (6.7%) | 219 / 2858 (7.7%) |

| Citation check | Problem citations / checked real citations |
|---|---|
| Harvey | 467 / 3618 (12.9%) |
| LegalReasonBench | unavailable; coverage or checks pending |

Harvey counts citation occurrences in task environments, including repeated documents across tasks; LegalReasonBench counts citations in unique matter documents and avoids repeated assignment copies. These citation denominators are different counting units. Fictional authorities are excluded; unable-to-verify results remain disclosed in each citation summary, not treated as verified successes.

The LegalReasonBench public sample has 221 criteria, with 179 in litigation scope, clustered in a few sequential matters. This small sample does not support full-benchmark extrapolation or a causal comparison. Neither audit supplies a verified error rate or benchmark score corrections.
