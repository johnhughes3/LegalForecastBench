# Provenance clearance v3

Version 3 is additive to the byte-exact version 1 and version 2 human-review contracts.
Existing `legalforecast.disclosure_provenance_routing_plan.v2`, `legalforecast.disclosure_exception_worksheet.v2`, interactive John decisions, and their validators are unchanged.

The v3 routing-plan schema is `legalforecast.disclosure_provenance_routing_plan.v3`.
It replaces the reviewer-specific `john_exception_review`, `john_review_count`, and `human_clearance_permitted` vocabulary with `exception_review`, `exception_review_count`, and `exception_clearance_permitted`.
All source, page-coverage, marker, public-provenance, restriction, visibility, ordering, and hash commitments are otherwise identical to v2.
The closed worksheet schema is `legalforecast.disclosure_exception_worksheet.v3`.
Both artifacts have closed top-level fields and canonical JSON bytes.
The plan’s four `source_sha256` commitments are closed and must each be a lowercase SHA-256 digest.
The worksheet validator rejects noncanonical encoding, duplicate keys at any depth, substituted bytes, and any projection other than the exact exception rows of the supplied plan.

Model review is permitted only when `automated_marker_present` is the sole route reason, page-text coverage is complete, CourtListener provenance is affirmative, the visibility contract is valid, and there is no positive sealed, private, restricted, or under-seal evidence.
Every other exception remains quarantined or requires separately authenticated human review.

Model-produced mappings never carry clearance authority.
This core schema deliberately exports no model-clearance constructor, authority type, run-card builder, or receipt parser.
Those remain blocked until an integration can authenticate the independently frozen cycle configuration, read back the exact local provider-journal row and raw payload, authenticate the matching remote logical call, and issue an opaque capability from verifier-owned evidence.
A caller-supplied registry, expected digest, provider receipt mapping, or per-document cost is not authority.

The v2 John-only constructor rejects v3 plans.
Model output can therefore never mint either a v2 John clearance row or a v3 model clearance row through this core.
