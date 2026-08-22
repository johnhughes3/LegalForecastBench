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

`stipulated_ineligible` is available only through a completed `audit-stage-a-target-eligibility` root. The successor replay treats the root as a locator for the persisted audit and completed audit card, then replays the exact original materialization, selection-card, parse-plan, parser-run, parser-manifest, document tree, and Markdown tree. The replayed selection bytes must equal the authenticated exact-100 predecessor selection, the ineligible document's parser source SHA-256 and byte count must equal the unique predecessor download-manifest row, the audit must reproduce byte-for-byte, and it must contain exactly one ineligible target document. The in-process verifier alone mints the terminal evidence; a caller-owned PDF, parser directory, audit JSONL, or self-consistent run card cannot mint authority.

The successor replays the stipulated root both before and after projection, together with the predecessor. It rejects changes to either persisted audit artifact, any drift in the reconstructed terminal records, or a changed sealed successor result. The audit card records the two materialization replay paths (`controlled_private_root` and `purchase_ledger_initialization_receipt`) as a closed mapping so the replay cannot substitute a different authority context.

## Noncharging recovery request, receipt, and run card

The `terminal_missing_core_document` route structurally validates only the following closed persisted artifacts:

- `legalforecast.exact100_zero_cost_recovery_request.v2`
- `legalforecast.exact100_zero_cost_recovery_receipt.v2`
- `legalforecast.exact100_zero_cost_recovery_run.v2`
- `legalforecast.exact100_zero_cost_recovery_rest_observation.v1`
- `legalforecast.exact100_zero_cost_recovery_rest_observation_transcript.v1`
- the exact `rest-observation-response.bin` bytes

The request identifies one selected candidate and target-motion document, its CourtListener docket and docket-entry identifiers, and fixes `recovery_mode` to `courtlistener_rest_noncharging_only`. It requires `paid_permitted`, `pacer_permitted`, and `recap_fetch_permitted` all to be false.

The receipt must bind the request, REST observation, and exact one-row transcript digests and prove one completed, nonretryable, unrecovered `unavailable` result. The sole transcript row must identify the exact direct `GET` and status 404; its response digest must be recomputed from the raw response sidecar. The receipt must record false paid, PACER, RECAP Fetch, and fee-acknowledgement activity.

The completed run card binds exactly the request and selection input commitments and the receipt, observation, transcript, and raw-response output commitments. Its provider-activity fields describe execution of the bounded CourtListener REST request; they are not authority for any model provider, paid source, PACER, or RECAP Fetch route.

Those persisted artifacts are caller-owned after serialization and therefore establish only canonical-byte integrity and internal consistency. They cannot mint terminal-exclusion authority. The public successor command and every later materializer or purchase-approval replay must make a fresh request through the canonical bounded CourtListener producer, receive an opaque verifier-owned in-process capability for the same terminal 404, and require the capability's complete evidence-commitment map to equal the persisted bundle. A saved 404 cannot override a fresh public-document or other nonterminal result, and a recovery-command resume never recreates the capability.

## Verification boundary

The structural verifier rejects syntactically valid but unbound digests, candidate IDs outside the exact selection, wrong document roles, duplicate terminal candidates, incomplete receipts, altered canonical bytes, and any request or run card that expands the permitted route. Structural verification alone grants no authority. Only a fresh canonical producer capability exactly matching the persisted commitments can produce the verified terminal record used by a successor projection, and that record is not a substitute for the projection's full predecessor replay and promotion checks.
