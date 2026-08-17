# Evaluator receipt authority

The frozen evaluation receipt schema already carries the issuer policy hash, issuer key ID, and Ed25519 signature. `legalforecast.multiharness.receipt_authority` supplies the external authority that selects those values and verifies them without changing the authenticated receipt bytes.

The committed public configuration is [examples/adapters/harvey-lab/evaluator-issuer-authority.json](../examples/adapters/harvey-lab/evaluator-issuer-authority.json). Its `public_key_base64` is deliberately `null` until the designated human provisions and reviews the production key. Loading this configuration therefore fails closed; no local or test key is treated as production authority.

Tier-0 detached spend approvals use a separate public-only authority. The committed handoff is [examples/adapters/harvey-lab/tier0-approval-authority.json](../examples/adapters/harvey-lab/tier0-approval-authority.json), with schema `legalforecast.multiharness.tier0_approval_authority.v1`, issuer ID `legalforecast.tier0-spend-approval-issuer.v1`, key ID `tier0-spend-approver-v1`, and policy digest `sha256:29c9fa3cd4f1788f6089d74d02676dc68187d513c709be2f3c27ddfdd92c7fe4`. Its `public_key_base64` must remain `null` until designated human review and provisioning complete; the committed status is `pending_human_provisioning`. This file contains no private key and no Infisical path. The approval authority is human-only and distinct from the evaluator receipt signer, which is the only authority allowed to sign evaluator receipts.

## Provisioning handoff

The designated operator should provision one secret only after approving the exact issuer policy and public-key bytes:

| Field | Proposed value |
| --- | --- |
| Infisical environment | `dev` |
| Infisical path | `/agents/sandbox/legalforecastbench/harness-runtime/evaluator-issuer` |
| Secret name | `HARVEY_LAB_EVALUATOR_ED25519_PRIVATE_KEY` |
| Value format | Base64 of exactly 32 raw Ed25519 private-key bytes (RFC 8032 seed form) |
| Public counterpart | Base64 of exactly 32 raw Ed25519 public-key bytes, committed in `public_key_base64` after independent review |
| Issuer key ID | `harvey-lab-evaluator-v1` |

This lane did not read Infisical, resolve credentials, generate a production key, or provision the secret. The runtime must obtain the private value through the reviewed Infisical wrapper seam and must compare its derived public key to the committed public key before signing. Host environment fallback, a local private-key file, and an ad hoc in-process key are refused.

Paid Tier-0 execution also requires the embedding runtime to install a reviewed `install_tier0_production_evaluator_factory(...)` factory. It must return a non-fixture `HarveyLabEvaluatorProvenance` record and a `ProductionHarveyLabEvaluatorRunner` (or equivalent reviewed runner) whose provider adapter performs one real request per criterion, converts provider usage into an auditable observation, settles each reservation immediately, and retains every attempt and transcript in the private archive. The aggregate LAB CLI cannot substitute for this seam because it does not prove per-criterion spend. Until the authority public key and reviewed provider adapter are provisioned, only the provider-free fixture path is executable.

## Run-start metadata

`build_private_run_metadata` emits a private sidecar before execution. It records exact observed executable digests and versions, the boundary identity, and canonical hashes for all run configuration records. Its `config_sha256` is supplied to the existing `RunIdentity`, and therefore to `ExecutionReceipt.config_sha256`; `bind_execution_receipt` additionally emits a sidecar binding that checks the receipt public digest, metadata digest, spec digest, boundary digest, and binary-identity digest.

The executable probe invokes only `--version` and `--help` in an isolated credential-free environment. It reports mismatches against the declared pin and never asserts a pinned version when the installed bytes disagree. A corrected capability record updates only the observed executable version/digest; capability claims remain unchanged until supported help evidence is reviewed.

## Credential-free probe procedure

Run the executable probe with `--version` and `--help` only, in an isolated
provider/auth environment. Persist exact observed versions and byte digests in
the generated private run metadata; do not commit lane-host observations to
this reusable public document. Probe results do not authorize a paid solver or
evaluator run and do not replace the historical characterization fixtures.
