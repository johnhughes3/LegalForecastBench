# Evaluator receipt authority

The frozen evaluation receipt schema already carries the issuer policy hash, issuer key ID, and Ed25519 signature. `legalforecast.multiharness.receipt_authority` supplies the external authority that selects those values and verifies them without changing the authenticated receipt bytes.

The committed public configuration is [examples/adapters/harvey-lab/evaluator-issuer-authority.json](../examples/adapters/harvey-lab/evaluator-issuer-authority.json). Its `public_key_base64` is deliberately `null` until the designated human provisions and reviews the production key. Loading this configuration therefore fails closed; no local or test key is treated as production authority.

## Provisioning handoff

John should provision one secret only after approving the exact issuer policy and public-key bytes:

| Field | Proposed value |
| --- | --- |
| Infisical environment | `dev` |
| Infisical path | `/agents/sandbox/legalforecastbench/harness-runtime/evaluator-issuer` |
| Secret name | `HARVEY_LAB_EVALUATOR_ED25519_PRIVATE_KEY` |
| Value format | Base64 of exactly 32 raw Ed25519 private-key bytes (RFC 8032 seed form) |
| Public counterpart | Base64 of exactly 32 raw Ed25519 public-key bytes, committed in `public_key_base64` after independent review |
| Issuer key ID | `harvey-lab-evaluator-v1` |

This lane did not read Infisical, resolve credentials, generate a production key, or provision the secret. The runtime must obtain the private value through the reviewed Infisical wrapper seam and must compare its derived public key to the committed public key before signing. Host environment fallback, a local private-key file, and an ad hoc in-process key are refused.

## Run-start metadata

`build_private_run_metadata` emits a private sidecar before execution. It records exact observed executable digests and versions, the boundary identity, and canonical hashes for all run configuration records. Its `config_sha256` is supplied to the existing `RunIdentity`, and therefore to `ExecutionReceipt.config_sha256`; `bind_execution_receipt` additionally emits a sidecar binding that checks the receipt public digest, metadata digest, spec digest, boundary digest, and binary-identity digest.

The executable probe invokes only `--version` and `--help` in an isolated credential-free environment. It reports mismatches against the declared pin and never asserts a pinned version when the installed bytes disagree. A corrected capability record updates only the observed executable version/digest; capability claims remain unchanged until supported help evidence is reviewed.

## Current no-spend probe evidence

The installed executable observations on the lane host were:

| Executable | Version output | Resolved bytes SHA-256 | Pin comparison |
| --- | --- | --- | --- |
| `claude` | `2.1.233 (Claude Code)` | `55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9` | drifted from the 2.1.231 pin |
| `codex` | `codex-cli 0.147.0` | `cb0a15567e9a60a5820d54b0f6ae86d504dc3805c1eab21a47f70e3eb7b73a40` | matches the supported 0.147.0 line; differs from the historical 0.146.0 characterization |

The probes were `--version` and `--help` only, with an empty provider/auth environment. These observations do not authorize a paid solver or evaluator run and do not replace the historical characterization fixtures.
