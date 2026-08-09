# Exact-100 successor terminal exclusion v1

This contract family provides the evidence-only predecessor to exact-100 successor replacement. It does not itself alter a cohort, choose a replacement, retrieve a document, authorize PACER or RECAP Fetch, or authorize any model, evaluation, freeze, or dispatch activity.

## Terminal-exclusion record

`legalforecast.exact100_successor_terminal_exclusion.v1` is a canonical JSONL record emitted only after a reason-specific verifier has authenticated evidence against the byte-exact selected 100-case cohort. Its closed fields are:

- `schema_version`
- `candidate_id`
- `source_document_id`
- `reason`
- `evidence_kind`
- `evidence_commitments`

The closed reason vocabulary reserves `stipulated_ineligible` and `terminal_missing_core_document`. Records are unique by candidate and emitted in the predecessor selection order. The closed record-set commitment binds the complete canonical JSONL surface and the exact predecessor selection bytes.

`stipulated_ineligible` is unavailable through the v1 public successor command. A caller-owned parser root can make its PDF, request, manifest, run card, parser record, and Markdown internally consistent without proving that the asserted Markdown came from the authenticated predecessor's completed parser producer. The command therefore rejects every stipulated-evidence root before reading it. Enabling this reserved reason requires a later versioned bridge that replays the original materialization, parse-plan, parser-run, manifest, and Markdown lineage against the predecessor; matching only a source-document digest is insufficient.

## Noncharging recovery request, receipt, and run card

The `terminal_missing_core_document` route accepts only the following closed artifacts:

- `legalforecast.exact100_zero_cost_recovery_request.v2`
- `legalforecast.exact100_zero_cost_recovery_receipt.v2`
- `legalforecast.exact100_zero_cost_recovery_run.v2`
- `legalforecast.exact100_zero_cost_recovery_rest_observation.v1`
- `legalforecast.exact100_zero_cost_recovery_rest_observation_transcript.v1`
- the exact `rest-observation-response.bin` bytes

The request identifies one selected candidate and target-motion document, its CourtListener docket and docket-entry identifiers, and fixes `recovery_mode` to `courtlistener_rest_noncharging_only`. It requires `paid_permitted`, `pacer_permitted`, and `recap_fetch_permitted` all to be false.

The receipt must bind the request, REST observation, and exact one-row transcript digests and prove one completed, nonretryable, unrecovered `unavailable` result. The sole transcript row must identify the exact direct `GET` and status 404; its response digest must be recomputed from the raw response sidecar. The receipt must record false paid, PACER, RECAP Fetch, and fee-acknowledgement activity.

The completed run card binds exactly the request and selection input commitments and the receipt, observation, transcript, and raw-response output commitments. Its provider-activity fields describe execution of the bounded CourtListener REST request; they are not authority for any model provider, paid source, PACER, or RECAP Fetch route.

## Verification boundary

The verifier rejects syntactically valid but unbound digests, candidate IDs outside the exact selection, wrong document roles, duplicate terminal candidates, unavailable stipulated evidence, incomplete receipts, altered canonical bytes, and any request or run card that expands the permitted route. A verified terminal record is therefore evidence for a later successor projection, not a substitute for that projection's full predecessor replay and promotion checks.
