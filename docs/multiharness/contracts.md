# Multi-Harness Contracts

This page summarizes the current public contracts shared by community harnesses. The typed implementations and executable fixtures are authoritative; this page describes the boundary a contributor needs to preserve.

## Sealed deliverables

`legalforecast.multiharness.deliverable_manifest.v1` is the boundary between a solver run and later evaluation. Each harness declares the output files it permits, mapping source paths to canonical paths, artifact IDs, media types, and byte limits.

Sealing accepts exactly the declared regular files and required parent directories. It rejects missing or extra entries, symlinks, hard links, unsafe paths, case-folding collisions, invalid media types, and file, byte, or count limits. It copies validated bytes into a fresh read-only tree and records each file's hash and size together with the complete tree commitment and manifest commitment.

Validation rechecks the exact schema and manifest hash, safe tree structure, limits, complete tree hash, and every file's hash and size. It treats contributor files as opaque bytes and never imports, renders, or executes them. The source, destination, sealed tree, and evaluator-mount boundary require exclusive coordination; read-only modes do not isolate same-UID processes.

## Evaluation and receipts

`EvaluationSpec` binds the sealed deliverable, task, run, configuration, evaluator source and image, private material, rubric and aggregation, judge settings, and runtime policies. Content uses lowercase `sha256:` commitments; evaluator source uses full Git commit and tree IDs; evaluator images use immutable digests.

An `EvaluationReceipt` records one invocation and repeats its spec bindings, resolved judge identity, unique measurement and attempt IDs, nonce and repeat slot, raw-result hash, size and media type, status, usage, cost, timing, issuer policy, and issuer key. Raw evaluator output, prompts, private paths, rubric text, reasoning, transcripts, and credentials remain private.

Usage dimensions are provider-native and may be unknown with an explicit reason. Cost uses integer micro-USD and an explicit basis; subscription usage is not represented as zero per call. Timing keeps wall and monotonic intervals, with queue and judge-call time separate. A retry receives a new receipt and repeat identity.

Receipt signatures authenticate the receipt bytes but do not select an issuer. Acceptance also requires the caller's externally pinned issuer policy, key, expected hashes, nonce state, and occupied repeat slots. Verification is offline and never invokes a judge; callers consume replay state atomically after acceptance.

## Scoring

Version 1 scoring is the pinned Harvey LAB specialization. Its `MetricDefinition` fixes the metric identity, 23 binary criteria, bounds, direction, missingness behavior, aggregation, normalizer, and rubric, criteria, aggregation, and judge-schema commitments.

The authorized derivative is one canonical UTF-8 JSON spelling with 23 contiguous ordinal verdicts. Unknown, missing, extra, inconsistent, reordered, or differently encoded values fail. All criteria are unweighted and the task score is `1` only when all 23 pass; `n_passed` and `n_criteria` are diagnostics, never partial credit.

The public `ScoreArtifact` contains only the authorized receipt, spec, raw-result, and metric-definition commitments plus the aggregate binary score and diagnostic counts. It never publishes criterion IDs, rubric text, evaluator output, reasoning, cost, tokens, timing, attempts, or uncertainty.

## Identity and compatibility

Community submissions and official runs share `TaskIdentity`, `SolverIdentity`, `RunIdentity`, `MatchedHarnessIdentity`, and `SystemBundleLabel` keys. Each is a prefixed digest of canonical JSON that includes its schema version. An unresolved served model is JSON `null` on `SolverIdentity`; it cannot produce a matched-harness key.

Resume requires the same task identity, solver identity, configuration commitment, and runtime-policy commitment. Slot fields such as order and repeat index may change. Execution receipts either carry all three task, solver, and run keys with their reconstructing slot fields or carry none of them.

Versioned readers accept only their declared schema versions. The compatibility fixture at `tests/fixtures/multiharness-artifact-characterization/manifest.json` covers canonical tasks, run summaries, submission shards and packages, and legacy submission and aggregate envelopes. Readers rewrite accepted fixtures exactly and reject unknown versions; generated publication formats are write-only.

## Harvey LAB source pin

The current LAB projection is tested against the upstream [`harveyai/harvey-labs`](https://github.com/harveyai/harvey-labs) commit `73feb91d63d53b1a44151d99329779c4defcdb72`, tree `944913ee8cdeaef4930a106e5e16d74aa93a29d7`. The upstream checkout's `LICENSE` is MIT, SHA-256 `f92627d2ebe80fc0add3b171b2d7eee5e28a98dd0d0a4a5ee5829314243bb3b9`; redistributed upstream material must retain that notice and attribution.

The machine-readable observation is `tests/fixtures/harvey_lab/pinned-evaluator-seam-73feb91.json`. The fixture and `tests/test_harvey_lab_pinned_evaluator_seam.py` preserve the source, license, task, evaluator, judge, and scoring boundary without vendoring task documents. Any future upstream change requires a new reviewed pin and fixture.
