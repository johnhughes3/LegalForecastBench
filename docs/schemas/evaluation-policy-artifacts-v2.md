# Execution policy v2

`legalforecast.execution_policy.v2` is an additive execution-policy schema for Cycle 1 manifest-mode issuance. It does not change `legalforecast.execution_policy.v1`; existing v1 producers, verifiers, freeze bundles, receipts, and runtime consumers retain their four-field lifecycle contract.

Like v1, the artifact is canonical JSON with exactly `schema_version`, `policy`, and `policy_sha256`. The digest is SHA-256 over the canonical `policy` object. The v2 `policy` object retains the v1 policy fields and their validation rules, but its `lifecycle` contains exactly:

- `labeling_policy_published_at`: the timezone-aware `published_at` value authenticated from the frozen labeling-policy artifact.
- `production_labeling_started_at`: the timezone-aware earliest durable `reserved_at` value in the authenticated canonical paid-labeling provider journal.

The labeling-policy publication must not be later than the first durable provider reservation. V2 intentionally omits `cohort_policy_published_at` and `batch_002_started_at`: those v1 chronology fields do not truthfully describe the successor manifest execution path, and v2 neither fabricates them nor represents them as null.

The v2 issuer derives every policy value from authenticated inputs. It does not accept lifecycle timestamps or policy JSON from the operator. Generic `verify_execution_policy()` and `execution_policy_content()` remain v1-only and reject v2; only labels-deferred code uses the explicit `verify_execution_policy_v2()` and `execution_policy_v2_content()` APIs.

The provider-free issuer writes `execution-decisions-v2.json`, `execution-policy-v2.json`, `beads-observation-v2.json`, and `run-cards/issue-manifest-execution-decisions-v2.json` as one create-only tree. The decisions bind the owner manifest, provider-free forecast, four-model successor registry, evaluation and labeling provider-cap artifacts, canonical paid-labeling journal identity and durable bytes, labeling and cohort policies, current cohort observation bytes, fresh Beads evidence, and the fully replayed generic-freeze inputs.

`legalforecast.manifest_execution_decisions.v2` contains `schema_version`, the exact policy-source fields consumed by the v2 generator, and `authenticated_inputs`. The latter records the raw hashes and replay identities for every source, including the journal schema/cycle/caps/canonical-path identity, committed database and WAL bytes, attempt count, and deterministic earliest reservation. The paired `legalforecast.manifest_execution_decisions_run_card.v2` records the completed provider-free stage, exact input paths and commitments, and commitments to the decisions and generated policy; `provider_calls_made` is zero and `paid_activity_executed` is false.

`legalforecast.execution_decisions_beads_observation.v2` contains exactly `schema_version`, `issue_id`, `model_registry_path`, `model_registry_sha256`, `raw_observation_sha256`, `raw_observation_base64`, and `evidence`. The critical decisions issuer captures `bd comments legalforecastbench-3ak.38 --json` directly, authenticates it, and publishes the wrapper as `beads-observation-v2.json`; verification consumes that published wrapper and replays its raw Base64 comments without querying live Beads. Replay accepts only exact owner-authored manifest approval, contamination replacement, and successor-registry spend-approval records; it does not parse a lifecycle comment. Neither caller-supplied raw comment JSON nor a caller-authored wrapper is a critical-issuance input.

This artifact is issuance groundwork only. Producing or verifying it makes no provider call, performs no AWS action, dispatches no shard, attaches no label, scores no forecast, and publishes no result.
