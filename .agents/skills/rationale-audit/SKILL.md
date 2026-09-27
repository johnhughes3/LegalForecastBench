---
name: rationale-audit
description: Prepare private model-blinded rationale review rows from saved forecast responses.
---

# Rationale review export

Run `uv run python -m legalforecast.evals.rationale_audit --runs private-runs.jsonl --output-dir private-rationale-review`. Inspect `--help` and [the input and review guide](../../../docs/rationale-audit.md) before use.

Use existing case-run JSONL identities plus saved `raw_output`, or substitute `--ledger run-ledger.sqlite3` for read-only export of completed native runner cells. Public `parser_output` receipts and provider payloads without normalized `raw_output` contain no usable prose and produce explicitly missing rationales. Ledger mode covers completed cells, not the planned run census. The exporter does not fetch protected artifacts. Do not infer or regenerate missing explanations.

Give reviewers only `review.jsonl` and the appropriate pre-decision packet. Keep `private-key.jsonl` with the coordinator. Structured model identity is removed, but original prose can still self-identify or contain leakage and needs inspection. All outputs stay private. Preserve the random review IDs when collecting ratings; existing output directories are refused. Coverage includes missing rationales and defaulted predictions.

This command prepares qualitative review inputs. It does not establish independent lawyer review, per-ground scoring, cutoff-safe external retrieval, or a reasoning-validity conclusion; it never changes benchmark scores.
