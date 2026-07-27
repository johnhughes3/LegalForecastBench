# Provenance clearance v3

Version 3 is additive to the byte-exact version 1 and version 2 human-review contracts.
Existing `legalforecast.disclosure_provenance_routing_plan.v2`, `legalforecast.disclosure_exception_worksheet.v2`, and interactive John decisions keep their schemas and semantics.
Shared document validation now also enforces closed identity and safety domains, safe relative local paths, and exact scan-page counts on the v2 path.

Select this contract explicitly with `plan-disclosure-provenance --schema-version v3`.
Omitting `--schema-version` or passing `--schema-version v2` preserves the legacy v2 artifacts and run-card shape.
The selector is closed to `v2` and `v3`.
Never resume a v3 execution from a v2 output root, or a v2 execution from a v3 output root; use a fresh immutable output root and controlled private store for each selected contract.
Completed run cards for v3 bind both selected artifact schema versions and record `exception_review_count`, while v2 retains its byte-compatible `john_review_count` metadata.
The v3 terminal log binds those same schema versions so same-version repair remains possible if only the completed log survives.
The closed legacy terminal-log shape continues to prove v2 without changing its bytes.
An opposite-version card or log fails before any public artifact or private inspection map can be restored.
The v3 completed-log schema is `legalforecast.disclosure_provenance_stage_log.v1`.
Its fields are exactly `schema_version`, `event`, `stage`, `status`, `dry_run`, `run_card_path`, `record_count`, `paid_activity_requested`, `paid_activity_executed`, `routing_plan_schema_version`, and `exception_worksheet_schema_version`.
Failure-history rows retain `legalforecast.acquisition_stage_log.v1`; they carry no completion authority and remain retryable only under the existing closed failure contract.

```bash
uv run legalforecast acquisition plan-disclosure-provenance \
  --schema-version v3 \
  --output-root <fresh-v3-review-root> \
  --review-requests <disclosure-review-requests.jsonl> \
  --download-manifest <document-downloads-merged.jsonl> \
  --case-relevance <case-relevance.jsonl> \
  --document-root <immutable-document-root> \
  --restriction-evidence <restriction-evidence.jsonl> \
  --controlled-private-store-root <fresh-controlled-private-v3-root> \
  --execute --no-resume
```

The v3 routing-plan schema is `legalforecast.disclosure_provenance_routing_plan.v3`.
It replaces the reviewer-specific `john_exception_review`, `john_review_count`, and `human_clearance_permitted` vocabulary with `exception_review`, `exception_review_count`, and `exception_clearance_permitted`.
All source, page-coverage, marker, public-provenance, restriction, visibility, ordering, and hash commitments are otherwise identical to v2.
The closed worksheet schema is `legalforecast.disclosure_exception_worksheet.v3`.
Both artifacts have closed top-level fields and canonical JSON bytes.
The plan’s four `source_sha256` commitments are closed and must each be a lowercase SHA-256 digest.
The worksheet validator rejects noncanonical encoding, duplicate keys at any depth, substituted bytes, and any projection other than the exact exception rows of the supplied plan.

Model review is permitted only when `automated_marker_present` is the sole route reason, page-text coverage is complete, CourtListener provenance is affirmative, the visibility contract is valid, and there is no positive sealed, private, restricted, or under-seal evidence.
Every other exception remains quarantined or requires separately authenticated human review.

The provider-free alternative is documented in [Provider-free provenance quarantine clearance v1](provenance-quarantine-clearance-v1.md).
It clears only `auto_clear` rows and deterministically quarantines every exception row without claiming human or model authority.
Its output is suitable for fail-closed cohort replacement when enough candidates remain under the frozen budget.

Model-produced mappings never carry clearance authority.
This core schema deliberately exports no model-clearance constructor, authority type, run-card builder, or receipt parser.
Those remain blocked until an integration can authenticate the independently frozen cycle configuration, read back the exact local provider-journal row and raw payload, authenticate the matching remote logical call, and issue an opaque capability from verifier-owned evidence.
A caller-supplied registry, expected digest, provider receipt mapping, or per-document cost is not authority.

The v2 John-only constructor rejects v3 plans.
Model output can therefore never mint either a v2 John clearance row or a v3 model clearance row through this core.
