# Provider-free recovered-public marker clearance v1

`finalize-provenance-quarantine` accepts `--public-marker-clearance-policy` only together with the completed v3 `--plan-run-card`.
This explicit provider-free mode clears an `exception_review` row only when its sole route reason is `automated_marker_present` and the unchanged v3 plan carries verifier-issued recovered-public CourtListener lineage, valid visibility, complete scan coverage, zero unscanned pages, and no positive sealed, private, or restricted evidence.
The structural markers remain in each clearance row as diagnostics.
Every other exception remains quarantined.

The immutable owner policy uses `legalforecast.disclosure_public_marker_policy.v1`.
It is canonical JSON with a self-hash and exact cycle/cohort-policy binding.
Its closed semantics require CourtListener recovered-public provenance, complete scan coverage, valid visibility, diagnostic-only markers, no model review, and quarantine for positive restriction, unproven public status, incomplete scanning, or visibility contradiction.

The finalizer emits `legalforecast.provenance_public_marker_clearance_run_card.v1` and records the exact boolean `resume` invocation state so the cycle orchestrator can authenticate resumable stage completion.
It has the common provider-free fields documented in [provenance-quarantine-clearance-v1.md](provenance-quarantine-clearance-v1.md), plus exact `plan_run_card` and `public_marker_clearance_policy` source commitments.
Its disposition kind is `v3_authenticated_recovered_public_markers_clear_else_quarantine` and additionally commits the policy schema and SHA-256 plus `markers_are_diagnostic_only: true` and the exact `public_marker_clear_count`.
All provider, human-review, paid-activity, and override fields remain false.

The existing v3 routing plan, worksheet, and clearance-row schemas are unchanged.
Eligible marker rows reuse `clearance_basis: "provider_free_recovered_public"`, null reviewer metadata, the exact recovered-public lineage, and `courtlistener-rest://recap-documents/<document-id>` provenance.
This preserves downstream resolver, materializer, and packet semantics while the distinct run-card schema prevents an old quarantine-only card from being reinterpreted.

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
  --public-marker-clearance-policy <owner-policy.json> \
  --cohort-policy <frozen-cohort-policy.json> \
  --execute --no-resume
```

Replay re-reads every committed source, reconstructs the recovered-public authority, regenerates the unchanged v3 plan and worksheet, verifies the canonical owner policy and its cohort binding, and byte-compares both clearance outputs.
Policy-byte, path, hash, cycle, cohort, recovery-lineage, document, or disposition drift fails closed.
