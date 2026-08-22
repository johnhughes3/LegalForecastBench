# Labels-deferred manifest forecast bundle v2

`legalforecast.manifest_forecast_bundle.v2` is a canonical, provider-free commitment to the authenticated Cycle 1 manifest forecast inputs. It is not a provider receipt, scoring input, or publication artifact.

The top-level object has exactly these fields:

- `schema_version`, `cycle_id`, `generated_at`, and `bundle_sha256`.
- `labels_state`, fixed to `deferred`, and `labels_sha256`, fixed to null.
- `scoreable` and `publishable`, both fixed to false.
- `provider_calls_made`, fixed to zero.
- `owner_manifest`, `forecast_inputs`, `generic_freeze_inputs`, `model_registry`, `provider_cycle_caps`, and `execution_policy`, which bind exact paths and bytes.
- `execution_constraints`, fixed to no docket tool, no search, no tools, and no visible outcome labels.
- `repeat_policy`, `shard_schedule`, and `provider_attempt_policy`, derived from the verified execution policy rather than supplied independently.
- `prediction_unit_identities`, derived from the signed manifest's authenticated finalized-unit source.

`generated_at` is copied from the authenticated manifest forecast run record and must equal the run-input timestamp. It is not an issuance-time clock value and cannot be supplied by the operator.

The bundle requires execution policy v2 and exact four-model successor-registry safety settings. It authenticates exact provider-cap coverage, the complete 100-case by two-ablation provider-free packet matrix, every packet and prompt commitment, the owner approval line, and the six-output generic-freeze replay. The generic-freeze run card must point to the same owner manifest, registry, and forecast directory, and its prompt replay must match the same manifest, registry, run-record, run-input, packet-count, candidate-count, and prompt-commitment values.

The issuer rejects packet objects containing outcome-label fields or a true `contains_target_outcome` marker at any nesting depth. Publication uses create-only, no-replace tree installation, and verification replays every bound input from single-link regular files.

The paired `legalforecast.manifest_forecast_bundle_run_card.v2` contains exactly `schema_version`, `stage`, `status`, `cycle_id`, `provider_calls_made`, `paid_activity_executed`, `bundle_sha256`, and `input_commitments`. Its provider count is zero and paid activity is false.

No v2 API finalizes a deferred provider receipt or attaches Stage B labels. Those transitions remain unsupported until their production producers and authentic verifiers ship together.
