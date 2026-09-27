# Evaluator receipt authority

The frozen evaluation receipt schema already carries the issuer policy hash, issuer key ID, and Ed25519 signature. `legalforecast.multiharness.receipt_authority` supplies the external authority that selects those values and verifies them without changing the authenticated receipt bytes.

The committed public configuration is [examples/adapters/harvey-lab/evaluator-issuer-authority.json](../../examples/adapters/harvey-lab/evaluator-issuer-authority.json). Its `public_key_base64` is deliberately `null` until the designated human provisions and reviews the production key. Loading this configuration therefore fails closed; no local or test key is treated as production authority. The supported `tier0 run` command now invokes `load_approved_issuer_authority` with `infisical_evaluator_issuer_secret_loader`. That callback is not executed while the public key remains `pending_human_provisioning`.

Tier-0 spend approval follows the ordinary recorded-owner-approval rule. The existing `--approval` input accepts a private JSON object with `spec_sha256`, `owner_approval` (the owner's actual words, with no required sentence), and `max_cost_usd`. The runner compares that ceiling with the spend policy and retains the record in its private archive. This path does not load or provision a human signing key. Historical signed approval records are still verified with their separate public-only authority; they do not change evaluator receipt authority.

## Native-thin cap evidence and remaining execution limits

The native-thin manifest can carry `provider_cap` instead of `budget_argument`. Its fields are `provider`, `auth_profile` (`published-api-key`), `credential_env_var`, `credential_sha256` (lowercase SHA-256 of the exact key), `hard_limit_usd`, timezone-bearing `observed_at` and `enforced_until`, `enforcement` (`hard_stop_no_auto_recharge`), and a private `evidence_reference`. The whole non-renewing provider limit must fit the solver ceiling; a delayed remaining-balance observation is insufficient. Deterministic minting checks provider/profile/ceiling compatibility without consulting the clock, so the same historical inputs reproduce the same artifact bytes and hashes. At live admission, evidence must be no more than 15 minutes old and remain valid beyond the solver timeout; stale evidence is refused before credentials are fetched. The reusable credential binding also rejects rotated or extra keys. These fields bind an observation; a locally written declaration does not verify provider enforcement. Keep the evidence reference and credential fingerprint private with the spend policy.

Paid native-thin execution therefore still refuses before the first solver, including when its manifest declares a budget flag. Three prerequisites remain: genuine provider-side hard-cap verification, native usage accounting, and wiring to the supported containment bridge. The stock upstream turn limit is not a monetary ceiling. Missing usage remains unknown in the existing spend journal; it is never converted to zero, and an overrun terminalizes the run. Minting an evidence-bound policy or passing synthetic tests does not complete issue #196 or authorize a real run.

The mint now deliberately pins Claude Code `2.1.283 (Claude Code)` and its observed executable digest rather than retaining the unavailable `2.1.233` identity. Exact-byte and version preflight remains mandatory; the runtime does not accept a moving launcher symlink as the pinned executable. This reconciliation is not a provider/authentication or baseline measurement.

Install the evaluator entrypoint with `legalforecast multiharness tier0 install-evaluator-wrapper --bin-dir BIN --scratch-root SCRATCH --output RECEIPT`, then include that directory on PATH and pin the reported digest when minting. Installation probes the committed wrapper without credentials. Run preflight checks the installed bytes and capabilities before solver launch; installation does not provision the evaluator signing authority described below.

## Provisioning handoff

The designated credential operator provisions the secret; agents never write or read it. The wrapper has no `secrets set` command, so provisioning is a human Infisical write into the exact coordinates below. After the public key is independently reviewed, commit it as `public_key_base64` and set `status` to `configured` in `examples/adapters/harvey-lab/evaluator-issuer-authority.json`. Verification stays fail-closed until that public key is present.

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

The supported command installs the reviewed production evaluator factory automatically. It returns a non-fixture `HarveyLabEvaluatorProvenance` record and a `ProductionHarveyLabEvaluatorRunner` whose provider adapter performs one real request per criterion, converts provider usage into an auditable observation, settles each reservation immediately, and retains every attempt and transcript in the private archive. The aggregate LAB CLI cannot substitute for this seam because it does not prove per-criterion spend. Live evaluation still requires genuine configured evaluator authority; a local test signer is not a substitute.

## Run-start metadata

`build_private_run_metadata` emits a private sidecar before execution. It records exact observed executable digests and versions, the boundary identity, and canonical hashes for all run configuration records. Its `config_sha256` is supplied to the existing `RunIdentity`, and therefore to `ExecutionReceipt.config_sha256`; `bind_execution_receipt` additionally emits a sidecar binding that checks the receipt public digest, metadata digest, spec digest, boundary digest, and binary-identity digest.

The executable probe invokes only `--version` and `--help` in an isolated credential-free environment. It reports mismatches against the declared pin and never asserts a pinned version when the installed bytes disagree. A corrected capability record updates only the observed executable version/digest; capability claims remain unchanged until supported help evidence is reviewed.

## Credential-free probe procedure

Run the executable probe with `--version` and `--help` only, in an isolated
provider/auth environment. Persist exact observed versions and byte digests in
the generated private run metadata; do not commit lane-host observations to
this reusable public document. Probe results do not authorize a paid solver or
evaluator run and do not replace the historical characterization fixtures.

The native adapter preflight is repeatable from a source checkout:

```sh
uv run python -m legalforecast.multiharness.native_cli_preflight --cli claude
uv run python -m legalforecast.multiharness.native_cli_preflight --cli codex
```

These commands check the example manifest pins. For an upgraded run, supply both `--version 'EXACT_VENDOR_VERSION'` and `--sha256 EXPECTED_EXECUTABLE_SHA256` from its intended pin; add `--paid` to require Claude's budget option. Preflight runs only `--version` and `--help` (Codex uses `exec --help`) in an empty credential-free home and scratch working directory. It rejects byte/version drift and missing options from the adapter's actual invocation template. The Tier-0 runner uses the same check for native arms whose frozen version command is `--version`; custom JSON identity probes retain their separate strict contract. An advertised option is parser compatibility evidence, not proof of containment, provider enforcement, authentication support, or permission to spend. Paid Codex remains unsupported.
