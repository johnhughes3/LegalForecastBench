# Publication Governance

This is the current public reporting contract for LegalForecastBench. It keeps official LegalForecast-MTD results separate from non-official community comparisons and defines the claims each result may make.

## Track separation

Official LegalForecast-MTD results and Community Harness Comparisons are different products with different score meanings and public identities. Do not rank a LegalForecast-MTD Brier score against a Harvey LAB rubric score or combine the tracks into an overall winner.

Community results are non-official observations of their declared tasks, adapters, models, and run conditions. They may report observed scores, coverage, efficiency, and failures. They must not claim official status, provider affiliation, harness causality, or general superiority beyond the declared run.

## Result arms

Every official result is assigned an arm from the model's first documented external deployment relative to the cycle's corpus anchor. A pre-anchor model was deployed on or before the anchor; a post-anchor model was deployed after it. Both arms are official and viable benchmark results.

The arm is a claim boundary. A pre-anchor result may claim contamination resistance on this corpus when its recorded training cutoff predates every scored decision. A post-anchor result may not make that claim. The two arms use the same pipeline and are aggregated and ranked separately; no post-anchor result enters the pre-anchor aggregate.

## Reporting

An official report identifies the frozen model and arm, score, uncertainty, coverage, accounting, baseline context, and limitations. It preserves the distinction between requested and served model identities and records the evidence needed to reproduce the published aggregate.

Published excerpts must be human-reviewed, attributed to this project, and identified as AI-generated where the provider requires it. Provider names identify the measured product surface and do not imply review, approval, sponsorship, partnership, or endorsement.

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.
