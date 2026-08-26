# Execution policy v4

`legalforecast.execution_policy.v4` is the provider-free, non-authorizing
successor used to break the final-freeze circular dependency in the official
model-scoped path.

The v4 policy preserves the v3 plan shape and all execution safeguards. Its
`common_frozen_inputs` may omit only `freeze_bundle_sha256` while the plan is
issued before the final freeze. The final freeze contains this plan; the
authenticated cost receipt and exact-model execution scope subsequently bind
the final freeze hash and derive provider authority from the frozen
provider-cycle-caps bytes.

The v3 issuer and verifier remain strict and continue to require
`freeze_bundle_sha256`. Existing v1, v2, and v3 artifacts are not reinterpreted
as v4, and a v4 plan never authorizes provider execution on its own. Use
`issue-manifest-execution-policy-v4` for the pre-freeze producer and issue a
model scope only after the final freeze and cost receipt exist.
