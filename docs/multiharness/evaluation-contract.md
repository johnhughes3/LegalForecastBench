# Canonical evaluation contract

Status: contract foundation for `LegalForecastBench-dm0g.4.1.8`.

`EvaluationSpec` precommits the exact sealed deliverable manifest, tree, task, run, and configuration hashes; evaluator repository commit, tree, file manifest, image digest, and trusted wrapper; private-material, rubric, ordered-criteria, and aggregation commitments; requested judge identity, settings, prompt, and output schema; and runtime, egress, resource, and token-accounting policies.

The settings commitment describes the effective provider request, not a custom sampling override inherited from a registry. The Tier-0 Anthropic Messages path omits `temperature` and `top_p`, records `provider_sampling_policy=provider_default` in its settings and per-attempt sidecars, and leaves any legacy registry values as observational compatibility metadata. Existing Cycle 1 registry bytes and historical artifact hashes remain unchanged.

All content commitments use canonical prefixed lowercase `sha256:` digests. Evaluator Git commits and trees use full lowercase 40-character object IDs. The image field is a content digest, never a mutable tag. Criterion commitments expose only contiguous one-based ordinals and hashes; private criterion IDs are never recorded.

`EvaluationReceipt` records exactly one stochastic invocation. It binds the spec hash and repeats its exact deliverable/task/run/config, judge, and policy bindings; identifies a unique measurement, evaluator attempt, externally expected nonce, and repeat slot; records the resolved judge identity; commits to the raw result's bytes, size, and media type; and records status, token usage, cost, timing, issuer policy, and issuer key ID. A retry is another receipt and repeat with its own complete usage and cost.

The raw result commitment does not publish raw private evaluator output. Receipts must not contain rubric text, private paths, criterion reasoning, prompts, transcripts, or credentials.

Opaque measurement, attempt, nonce, key, and clock identifiers use bounded path-free syntax. Judge identities use a constrained `provider/model` form with an optional immutable suffix. Evaluator repositories are canonical HTTPS URLs without user information, ports, queries, fragments, or traversal. Serialized specs and receipts also pass the shared public-record validator.

## Accounting semantics

Every token dimension is either a non-negative integer or `null` with an allowlisted public-safe reason code. A known zero is distinct from an unknown value. Input, output, cache-read, cache-write, reasoning, and authoritative total evaluation tokens remain separate. Counters are provider-native; the bound token-accounting policy defines inclusion relationships, so this layer performs no arithmetic inference or double counting.

Cost uses integer micro-USD and an explicit basis. Metered, provider-reported, and pricing-snapshot estimates may record an authenticated zero. `unknown` and `subscription_unallocable` require a null amount, null currency, and a non-empty reason; a flat subscription is never represented as zero per call.

Timing binds canonical UTC start/end chronology and monotonic start/end nanoseconds. Wall elapsed time must equal the monotonic endpoint difference. Queue time and summed judge-call time are separate; summed call time may exceed wall time when calls run in parallel.

## Authorization and replay

A receipt self-hash detects accidental mutation but does not authorize an issuer. Receipt builders sign domain-separated canonical bytes through a caller-provided signer. Offline verification requires an externally pinned issuer policy hash, key ID, and Ed25519 public key; those inputs must be co-validated by the caller because this verifier does not prove that a policy authorizes a key. Embedded issuer identifiers are never trusted as key material.

Verification is offline and never invokes a judge. The caller pins the expected spec hash in addition to the exact deliverable, runtime policy, issuer policy, key ID, measurement, attempt, and repeat bindings. A separate opaque-byte verifier checks the raw result's exact hash, size, and media type without parsing it. A fresh judge invocation must use a new measurement ID, attempt ID, nonce, and repeat index, producing a new receipt even when its verdict happens to match an earlier call.

Cryptographic validity alone does not prevent replay. Callers accepting a new result supply their authoritative consumed-measurement, nonce, and occupied-repeat-slot sets to the verifier. These are check-only inputs; the caller must atomically consume them after acceptance. Callers performing archival verification may omit replay state, so a historically valid receipt does not expire merely because it was already accepted.

`verify_evaluation_result` is the acceptance API: it verifies trust and bindings, then exact raw bytes. Lower-level receipt-only and raw-byte helpers are available for staged archival workflows. Canonical bytes use this Python implementation's sorted-key, compact UTF-8 JSON encoding; cross-language canonical JSON compatibility is not claimed.

This module defines records, hashing, signatures, and verification only. It does not select issuer policy, hold signing keys, invoke evaluator code, authorize deployment, or publish scores.
