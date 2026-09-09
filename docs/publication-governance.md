# Publication Governance

This is the current public reporting contract for LegalForecastBench. It keeps official LegalForecast-MTD results separate from non-official community comparisons and defines the claims each result may make.

## Track separation

Official LegalForecast-MTD results and Community Harness Comparisons are different products with different score meanings and public identities. Do not rank a LegalForecast-MTD Brier score against a Harvey LAB rubric score or combine the tracks into an overall winner.

Community results are non-official observations of their declared tasks, adapters, models, and run conditions. They may report observed scores, coverage, efficiency, and failures. They must not claim official status, provider affiliation, harness causality, or general superiority beyond the declared run.

## Eligibility and historical result arms

The owner selected training-cutoff eligibility before the benchmark runs; this September 9, 2026 documentation update aligns the public contract with that decision. A documented training-data cutoff must strictly precede every scored decision for the eligible official comparison. A provider-reported knowledge cutoff is evidence for that assessment, not independent proof of all training or post-training exposure. Unknown or overlapping cutoffs remain visibly qualified comparisons and must not be represented as satisfying this rule.

A model's public release date does not determine eligibility. Frequent releases make a new post-release cohort for every model impractical; low contamination is the working assumption to test, not an established result. Preserve release dates and historical pre-/post-anchor metadata for traceability. Existing release-arm renderers and frozen artifacts retain their historical classification until aligned; this documentation update does not relabel old artifacts or establish that automated publication already implements the revised policy.

## Reporting

An official report identifies the frozen model and cutoff evidence, score, uncertainty, coverage, accounting, baseline context, and limitations. It reports micro-Brier and equal-case Brier together, retaining micro-Brier as the methods' headline and equal-case weighting as a sensitivity analysis. Cost tables distinguish actual charges or reconstructed usage costs from standard-rate repricing, with discounts, cache treatment, missing usage, and failed-attempt coverage disclosed. It preserves the distinction between requested and served model identities and records the evidence needed to reproduce the published aggregate.

Published excerpts must be human-reviewed, attributed to this project, and identified as AI-generated where the provider requires it. Provider names identify the measured product surface and do not imply review, approval, sponsorship, partnership, or endorsement.

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.
