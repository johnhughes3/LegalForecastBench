# Canonical score contract

Status: contract foundation for `LegalForecastBench-dm0g.4.1.9`.

Version 1 is deliberately a strict pinned Harvey LAB specialization. It does not claim generic metric arithmetic, weighting, rounding, missing-value imputation, or compatibility with other evaluator semantics.

`MetricDefinition` is the complete deterministic scoring policy. The pinned Harvey LAB v1 definition binds exactly 23 binary criteria, raw bounds 0 and 1, higher-is-better direction, binary units, absent weights, reject-on-missingness, no rounding, all-pass aggregation, and exact rubric, ordered-criteria, aggregation, and judge-output-schema hashes.

The scoring entrypoint does not accept a merely well-formed receipt. It calls the evaluation contract's high-level verifier over the receipt, exact raw derivative bytes, specification, externally pinned issuer trust inputs, nonce/repeat state, and expected hashes. It additionally requires an externally pinned metric-definition hash, a succeeded receipt, and exact definition-to-spec rubric, criteria, aggregation, and output-schema bindings.

The authorized derivative is strict canonical JSON containing exactly 23 unique contiguous one-based ordinals and `pass` or `fail` verdicts. It may include only its fixed schema version, verdict vector, binary task score, passed count, and criterion count. Unknown, duplicate, missing, extra, or inconsistent values fail. Parsing is offline and never invokes an evaluator or judge.

The verdict vector is used only inside normalization. `ScoreArtifact` publishes and hashes only the authorized receipt, spec, raw-result, and metric-definition hashes plus the aggregate binary score and diagnostic passed/criterion counts. It never exposes private criterion IDs, ordinal verdicts, rubric text, reasoning, evaluator output, cost, tokens, timing, attempts, or uncertainty.

Pinned LAB semantics are exact: all 23 criteria are unweighted; no mean, partial credit, or rounding occurs; the task score is 1 only when all 23 pass and is otherwise 0. `n_passed` and `n_criteria` are diagnostics and never a partial score.

All arithmetic is bounded integer arithmetic. Records use strict exact-field schemas, prefixed lowercase SHA-256 commitments, deterministic sorted-key compact JSON hashing, and shared public-record validation. This foundation does not hold signing keys, invoke evaluation, publish results, or authorize deployment.
