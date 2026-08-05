# Provenance clearance v2

This is the contract `plan-disclosure-provenance` emits by default. [Provenance clearance v3](provenance-clearance-v3.md) is additive and is selected explicitly with `--schema-version v3`; it supersedes the v2 review vocabulary with a reviewer-neutral exception-review contract. [Provenance clearance v1](provenance-clearance-v1.md) can no longer be emitted.

Cycle 1 uses provenance-first disclosure clearance instead of a signing-key ceremony.
The supported path is `plan-disclosure-provenance` -> `record-disclosure-review-decisions` for exceptions -> `clear-provenance-disclosures`.
Legacy signed-review and v1 routing artifacts remain verifiable for historical runs but are not a Cycle-1 readiness dependency.

## Routing plan

`plan-disclosure-provenance` consumes the exact frozen disclosure requests, complete download manifest, full case-relevance artifact, restriction evidence, and acquired document tree.
It rejects symlinks, hard links, special files, changed bytes, malformed or semantically mismatched source bytes, incomplete key coverage, and unexplained relevance-only rows.

The output schema is `legalforecast.disclosure_provenance_routing_plan.v2`.
Each document embeds one closed `legalforecast.disclosure_pdf_scan.v1` record containing the parser method, parsed page count, disjoint text-scanned, reserved OCR-scanned, and unscanned page-number sets, coverage status, diagnostics, and substantive markers.
The three page sets must be sorted, unique, pairwise disjoint, and exactly partition `1..parsed_page_count`.
The current `legalforecast.disclosure_pdf_scan.v2` / `pypdf_page_text_v2` scanner does not perform OCR, requires the OCR-scanned set and count to be empty, and treats every page without nonempty extracted text as unscanned.
Coverage is complete only when at least one page was parsed and the unscanned set is empty.
The redundant legacy extractor is retired for new v2 scans; immutable v1 scans replay through `pypdf_page_text_v1`, whose historical content-stream/page-count mismatch remains diagnostic-only.
That diagnostic never proves coverage or suppresses medical, SSN, mixed, or any other substantive or unknown marker.

A document is `auto_clear` only when all of the following are true:

- its current descriptor-stable bytes match the manifest SHA-256 and byte count;
- it is a free CourtListener document with an allowlisted public `storage.courtlistener.com/recap/` URL that matches case relevance;
- public provenance is affirmative, either from the checked public-download record or the exact CourtListener REST proof set;
- the visibility contract is exactly predecision/model-visible or decision/outcome-only;
- page-text coverage is complete and the scan returns no substantive marker; and
- no status, boolean, or evidence token affirmatively indicates sealed, private, restricted, or under-seal material.

All other rows route to `john_exception_review`.
Incomplete extraction and marker-only or missing-provenance exceptions may be cleared after inspection.
A positive restriction or visibility contradiction sets `human_clearance_permitted: false` and can never be cleared.

The planner emits `legalforecast.disclosure_exception_worksheet.v2`, which projects the same closed document rows for exceptions, and an exception-only private inspection map.
The review and final-clearance integrity properties otherwise remain those documented for v1.
