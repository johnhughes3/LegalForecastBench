# Evaluation policy artifact schemas

Cycle 1 separates decisions made before labeling or acquisition from facts observed later. All three policy files use canonical JSON, reject unknown fields, and contain exactly `schema_version`, `policy`, and `policy_sha256`. `policy_sha256` is SHA-256 over the canonical `policy` object. The immutable writers allow an identical retry but reject changed bytes at an existing path.

## `legalforecast.labeling_policy.v1`

The labeling policy must be generated and hash-published before production labeling. Its `policy` object contains exactly:

- `cycle_id`: the non-empty cycle identifier.
- `published_at`: the timezone-aware publication timestamp.
- `judge_registry_sha256`: SHA-256 over the exact dedicated judge-registry file. Generation parses and validates that registry before hashing it; verification with `--judge-registry` rehashes the supplied bytes and fails on drift.
- `label_audit`: the precommitted cycle-level audit policy described below.

`label_audit` contains exactly:

- `population`: fixed to `auto_labeled_units`.
- `sample_fraction`: fixed to `0.05`. The sampler's population rule is `min(N_auto, max(minimum_sample_size, ceil(sample_fraction * N_auto)))`.
- `minimum_sample_size`: fixed to `20`.
- `strata`: fixed, mutually exclusive ordered values `unanimous_grant`, `unanimous_deny`, and `partial`, derived from retained raw resolutions.
- `minimum_per_stratum`: fixed to `5`; a smaller observed stratum is audited exhaustively.
- `allocation`: fixed to `largest_remainder_with_minimums_exhaustive_below_minimum`.
- `seed_components`: fixed, in order, to `cycle_id`, `pre_adjudication_ensemble_corpus_sha256`, and `labeling_policy_sha256`. `labels_sha256` is forbidden because adjudication can rewrite labels after sampling.
- `max_llm_error_rate`: fixed to `0.05` per sampled stratum.
- `max_human_disagreement_rate`: fixed to `0.05` per sampled stratum.
- `threshold_operator`: fixed to `greater_than`, so a rate above 5% blocks release pending adjudication.
- `threshold_source`: a required non-empty citation or decision record fixed before labeling.

Generate and verify it with:

```text
legalforecast acquisition generate-labeling-policy CYCLE_ID --judge-registry PATH --published-at TIMESTAMP --threshold-source SOURCE --output PATH
legalforecast acquisition verify-labeling-policy --artifact PATH --judge-registry PATH --cycle-id CYCLE_ID
legalforecast freeze verify-labeling-policy --artifact PATH --judge-registry PATH --cycle-id CYCLE_ID
```

## `legalforecast.cohort_policy.v1`

The cohort precommitment is owned by the acquisition pipeline and documented field-by-field in [cohort-policy-v1.md](cohort-policy-v1.md). The freeze consumes the already-published file and binds its raw-file SHA-256. It does not regenerate or amend it. `cycle_series` is forbidden from that schema.

## `legalforecast.execution_policy.v1`

The execution policy is generated at freeze. Its `policy` object contains exactly:

- `cycle_id`: the cycle identifier, which must match the freeze bundle.
- `cycle_series`: the sole authoritative `rapid` or `official` choice. A conflicting restatement in another JSON/JSONL frozen artifact is rejected.
- `allow_no_baselines`: the frozen Boolean. Mutable dispatch input must match through `require_dispatch_policy_match()`.
- `labeling_policy_sha256`: SHA-256 over the exact `labeling-policy.json` file bytes.
- `cohort_policy_sha256`: SHA-256 over the exact `cohort-policy.json` file bytes.
- `cohort_observation_manifest_sha256`: SHA-256 over the final append-only observation-manifest state.
- `lifecycle`: precommitment and constrained-activity timestamps.
- `shard_schedule`: the fixed shard layout.
- `concurrency_policy`: the chosen shard-concurrency strategy.
- `receipt_policy`: immutable receipt rules.
- `attempt_policy`: the reservation-ledger commitment and billable-attempt limit.
- `repeat_policy`: the preselected repeat cases.
- `cadence_counts`: the authoritative derived-count rules.

`lifecycle` contains exactly `labeling_policy_published_at`, `production_labeling_started_at`, `cohort_policy_published_at`, and `batch_002_started_at`, all timezone-aware ISO-8601 timestamps. Each policy timestamp must be no later than the activity it constrains. `labeling_policy_published_at` must equal the timestamp inside the frozen labeling policy.

`shard_schedule` contains exactly positive `shard_count`; `dispatch_unit`, fixed to `model_key_ablation`; and `shards`, the exact unique `{model_key, ablation}` pairs. Every model must declare both `full_packet` and `metadata_only`. The policy writer sorts the pairs canonically, rejects duplicates or undeclared ablations, and requires `shard_count` to equal the declared-pair count. Cycle 1's four-model schedule therefore contains eight shards; smaller synthetic registries use proportionately smaller complete schedules.

`concurrency_policy` contains exactly `mode` and `identity_fields`. The retained Cycle 1 choice is `shard_identity`, with identity fields `cycle_id`, `model_key`, and `ablation`; the policy generator rejects the unimplemented `queue_max` and `orchestrator` alternatives so a valid freeze cannot silently select behavior the official workflow does not enforce. Because GitHub concurrency groups are case-insensitive, the frozen shard schedule also rejects identity pairs that collide after Unicode case folding. Dispatch provenance reconstructs the actual GitHub concurrency group from this frozen choice and rejects a mismatch before provider work.

`receipt_policy` contains exactly `write_once_per_attempt` (required `true`), `identity_fields` (the non-empty receipt identity field list), and `result_commitment_required` (required `true`).

`attempt_policy` contains exactly `reservation_ledger_sha256` (the lowercase SHA-256 commitment) and `max_billable_attempts` (a positive integer).

`repeat_policy` contains exactly `case_ids` (unique non-empty identifiers) and `count`, which must equal the list length.

`cadence_counts` contains exactly `clean_motion_count_source` (fixed to `frozen_manifest`), `prediction_unit_count_source` (fixed to `frozen_units`), and `reject_operator_mismatch` (required `true`).

Generate and verify it with:

```text
legalforecast freeze generate-execution-policy --decisions PATH --output PATH
legalforecast freeze verify-execution-policy --artifact PATH --cycle-id CYCLE_ID
```

The final freeze requires `--execution-policy`, `--labeling-policy`, and `--cohort-policy` in addition to the pre-existing artifacts. It verifies each internal commitment, checks raw-file hash links from execution policy to both precommitments, checks lifecycle ordering, and includes all three raw-file hashes in the bundle. It never creates or modifies an official artifact implicitly.
