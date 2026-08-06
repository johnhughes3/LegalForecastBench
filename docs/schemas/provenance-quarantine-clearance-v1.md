# Provider-free provenance quarantine clearance v1

`finalize-provenance-quarantine` has two explicit provider-free terminal modes for a v3 provenance routing plan.
The plan-proven empty-set mode requires `--plan-run-card` together with `--require-no-model-review-eligible-exceptions`; it authenticates the completed planner record and rejects the run if any exact exception remains eligible for model review.
The compatibility mode requires `--quarantine-all-exceptions-without-review`; it preserves the older behavior of quarantining every exception, but it is not the supported target-100 recovery continuation.
Omitting model authority, both empty-set proof flags, and the explicit compatibility flag fails closed.

Both provider-free modes recompute the exact routing plan and exception worksheet from immutable source artifacts and document bytes, clear only `auto_clear` rows, and quarantine every `exception_review` row that they accept.
They accept no disclosure reviewer, model decision, provider response, or disclosure-review private-store input and never contact a provider.
For recovered public documents, they additionally replay the exact recovery and purchase authority, including the controlled purchase-ledger state, and add the exact `recovered_public_authority` field to the run card.

The command emits ordinary `legalforecast.disclosure_clearance.v1` rows.
Automatic rows retain `clearance_basis: "affirmative_public_provenance"`.
Exception rows have `status: "quarantined"`, `clearance_basis: "provider_free_exception_quarantine"`, and null `reviewer_id`, `reviewed_at`, and `controlled_store_provenance`.
The quarantine-only basis can never authorize a cleared downstream document.

The deterministic provider-free run card schema is `legalforecast.provenance_quarantine_clearance_run_card.v1`.
Its common top-level fields are exactly:

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

The explicit compatibility variant adds exactly `quarantine_all_exceptions_without_review`: `true` and uses disposition-policy kind `v3_auto_clear_else_quarantine`.

The plan-proven empty-set variant instead adds exactly `model_review_eligible_exception_count`: `0` and `no_model_review_eligible_exceptions_required`: `true`, adds the authenticated `plan_run_card` source commitment, and uses disposition-policy kind `v3_auto_clear_no_model_eligible_else_quarantine`.
The committed planner record must use the planner's canonical JSON encoding and must replay its exact input paths, output paths, source commitments, output commitments, timestamp, resume flag, counts, schema identities, document tree, and any recovered-public authority.

The provider-free schema has no finalizer timestamp, reviewer identity, provider receipt, or clearance authority.
For an executed card, all activity booleans are false, `stage` is `finalize-provenance-quarantine`, and the exact source and output commitments are complete.
The run card must use the repository's canonical JSON encoding; all common counts and the empty-set variant's eligibility count are non-negative JSON integers (booleans are invalid).
The closed `disposition_policy` identifies the selected variant kind, the v3 routing and worksheet schemas, the v1 clearance schema, exact routing-plan, worksheet, and cohort-policy hashes, both disposition counts, and `human_or_model_override_permitted: false`.
Projection additionally requires the exact committed `case_relevance` path and digest, so clearance cannot be reused with a different eligibility, visibility, or document-role projection.
Without `--execute`, the command validates and replays all inputs but publishes no immutable artifacts, so the same output root remains available for a later executed run.

The compatibility form is:

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
  --quarantine-all-exceptions-without-review \
  --execute --no-resume
```

The target-100 provider-free continuation replaces the compatibility flag with both proof arguments:

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
  --plan-run-card <completed-plan-disclosure-provenance-run-card.json> \
  --require-no-model-review-eligible-exceptions \
  --cohort-policy <frozen-cohort-policy.json> \
  --execute --no-resume
```

`project-target-cohort` independently replays the full run card and removes every candidate with a quarantined document before applying the unchanged rank and budget policy.
The run card is terminal exclusion evidence, not human or model clearance evidence.
