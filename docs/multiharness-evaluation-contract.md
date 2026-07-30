# Canonical evaluation contract

Status: contract foundation for `LegalForecastBench-dm0g.4.1.8`.

`EvaluationSpec` precommits the exact sealed deliverable manifest, tree, task, run, and configuration hashes; evaluator repository commit, tree, file manifest, image digest, and trusted wrapper; private-material, rubric, ordered-criteria, and aggregation commitments; requested judge identity, settings, prompt, and output schema; and runtime, egress, and resource policies.

All content commitments use canonical prefixed lowercase `sha256:` digests. Evaluator Git commits and trees use full lowercase 40-character object IDs. The image field is a content digest, never a mutable tag. Criterion commitments are ordered by criterion ID before hashing and reveal only criterion IDs and per-criterion hashes.

`EvaluationReceipt` records one stochastic measurement. It binds the spec hash and repeats its exact deliverable/task/run/config, judge, and policy bindings; identifies a unique measurement, evaluator attempt, nonce, repeat slot, attempt number, and retry count; records the resolved judge identity; commits to the raw result's bytes, size, and media type; and records status, token usage, cost, timing, issuer policy, and issuer key ID.

The raw result commitment does not publish raw private evaluator output. Receipts must not contain rubric text, private paths, criterion reasoning, prompts, transcripts, or credentials.

## Accounting semantics

Every token dimension is either a non-negative integer or `null` with a non-empty reason. A known zero is distinct from an unknown value. Input, output, cached-input, reasoning, and authoritative total evaluation tokens remain separate so later efficiency analysis does not infer or double-count provider-specific dimensions.

Cost uses integer micro-USD and an explicit basis. Metered, provider-reported, and pricing-snapshot estimates may record an authenticated zero. `unknown` and `subscription_unallocable` require a null amount, null currency, and a non-empty reason; a flat subscription is never represented as zero per call.

Timing binds canonical UTC start/end chronology and monotonic start/end nanoseconds. Wall elapsed time must equal the monotonic endpoint difference. Queue time and summed judge-call time are separate; summed call time may exceed wall time when calls run in parallel.

## Authorization and replay

A receipt self-hash detects accidental mutation but does not authorize an issuer. Receipt builders sign domain-separated canonical bytes through a caller-provided signer. Offline verification requires an externally pinned issuer policy hash, key ID, and Ed25519 public key; embedded issuer identifiers are never trusted as key material.

Verification is offline and never invokes a judge. The caller pins the expected spec hash in addition to the exact deliverable, runtime policy, issuer policy, key ID, measurement, attempt, and repeat bindings. A separate opaque-byte verifier checks the raw result's exact hash, size, and media type without parsing it. A fresh judge invocation must use a new measurement ID, attempt ID, nonce, and repeat index, producing a new receipt even when its verdict happens to match an earlier call.

Cryptographic validity alone does not prevent replay. Callers accepting a new result supply their authoritative consumed-measurement and occupied-repeat-slot sets to the verifier. The verifier rejects collisions without mutating those sets. Callers performing archival verification may omit replay state, so a historically valid receipt does not expire merely because it was already accepted.

This module defines records, hashing, signatures, and verification only. It does not select issuer policy, hold signing keys, invoke evaluator code, authorize deployment, or publish scores.
