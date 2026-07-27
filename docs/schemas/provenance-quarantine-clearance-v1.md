# Provider-free provenance quarantine clearance v1

`finalize-provenance-quarantine` is the provider-free terminal alternative to exception review for a v3 provenance routing plan.
It recomputes the exact routing plan and exception worksheet from immutable source artifacts and document bytes, clears only `auto_clear` rows, and quarantines every `exception_review` row.
It accepts no reviewer, model, provider, decision, or private-store input and never contacts a provider.

The command emits ordinary `legalforecast.disclosure_clearance.v1` rows.
Automatic rows retain `clearance_basis: "affirmative_public_provenance"`.
Exception rows have `status: "quarantined"`, `clearance_basis: "provider_free_exception_quarantine"`, and null `reviewer_id`, `reviewed_at`, and `controlled_store_provenance`.
The quarantine-only basis can never authorize a cleared downstream document.

The deterministic run card schema is `legalforecast.provenance_quarantine_clearance_run_card.v1`.
Its top-level fields are exactly:

- `schema_version`
- `stage`
- `status`
- `dry_run`
- `execute`
- `provider_activity_requested`
- `provider_activity_executed`
- `human_review_requested`
- `human_review_executed`
- `paid_activity_requested`
- `paid_activity_executed`
- `record_count`
- `auto_clear_count`
- `exception_quarantine_count`
- `input_paths`
- `source_commitments`
- `output_paths`
- `output_commitments`
- `disposition_policy`

The schema has no timestamp, reviewer identity, provider receipt, or clearance authority.
For an executed card, all activity booleans are false, `stage` is `finalize-provenance-quarantine`, and the exact source and output commitments are complete.
The run card must use the repository's canonical JSON encoding, and all three counts are non-negative JSON integers (booleans are invalid).
The closed `disposition_policy` requires `kind: "v3_auto_clear_else_quarantine"` and identifies the v3 routing and worksheet schemas, the v1 clearance schema, exact routing-plan, worksheet, and cohort-policy hashes, both disposition counts, and `human_or_model_override_permitted: false`.
Projection additionally requires the exact committed `case_relevance` path and digest, so clearance cannot be reused with a different eligibility, visibility, or document-role projection.
Without `--execute`, the command validates and replays all inputs but publishes no immutable artifacts, so the same output root remains available for a later executed run.

```bash
uv run legalforecast acquisition finalize-provenance-quarantine \
  --output-root <fresh-provider-free-clearance-root> \
  --review-requests <disclosure-review-requests.jsonl> \
  --download-manifest <document-downloads-merged.jsonl> \
  --case-relevance <case-relevance.jsonl> \
  --document-root <immutable-document-root> \
  --restriction-evidence <restriction-evidence.jsonl> \
  --routing-plan <v3-disclosure-provenance-plan.json> \
  --exception-worksheet <v3-disclosure-exception-worksheet.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --execute --no-resume
```

`project-target-cohort` independently replays the full run card and removes every candidate with a quarantined document before applying the unchanged rank and budget policy.
The run card is terminal exclusion evidence, not human or model clearance evidence.
