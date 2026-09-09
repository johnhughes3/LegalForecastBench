# Training-cutoff reporting

The owner selected training-cutoff eligibility before the benchmark runs. This September 9, 2026 documentation alignment replaces deployment date as the eligibility criterion; it does not rewrite historical artifacts. See [methods](METHODS.md) and [publication governance](publication-governance.md).

## Rule and evidence

A documented training-data cutoff must strictly precede every scored decision. The existing `provider_training_cutoff` and `provider_training_cutoff_status` fields record cutoff evidence; `eligibility_anchor` records the cohort boundary. Preserve the source and date precision. Unknown, undisclosed, or overlapping cutoffs do not establish eligibility and must remain visibly qualified. A provider's knowledge cutoff is an imperfect proxy for training exposure; “contamination-resistant” is a conditional claim, not a guarantee.

Release date remains useful metadata and a criterion for future stricter post-release backtests, but does not itself exclude a model from the training-cutoff-eligible comparison. Historical `pre_anchor` / `post_anchor` fields and their renderer behavior remain in existing artifacts. Do not reinterpret them as training-cutoff classifications or silently rewrite frozen results. Publication code must be aligned before claiming the new policy is automatically enforced.

## Testing contamination over time

Fresh cohorts allow comparisons of a model's relative performance against the same reference models on old and post-release cases. Compare changes in within-cohort differences, with clustered uncertainty and attention to case composition; do not subtract raw scores across different case sets and call the result contamination. Fixed model versions and consistent harnesses help separate serving changes from cohort effects. A systematic relative change is a possible signal to investigate. Random-looking or nonsignificant differences do not prove absence of contamination, particularly with small samples.

## Existing reporting implementation

Cutoff annotations use `legalforecast.evals.model_registry` and `reported_model_label` / `PRELIMINARY_CAVEAT` in the reporting code. The `contamination_tier` sidecar is non-authoritative and does not replace the scored aggregate. Existing unknown/overlapping-cutoff markers stay visible. This documentation update changes no packet leakage filters, acquisition state, or saved prediction bytes.
