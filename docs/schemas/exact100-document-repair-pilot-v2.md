# Exact-100 document-repair pilot v2

`legalforecast.exact100_document_repair_pilot.v2` projects exactly five unique candidate IDs from one authenticated `legalforecast.exact100_missing_document_acquisition_plan.v2`. It retains the full plan and approved repair-manifest digests; it does not create or approve a replacement five-row manifest.

The `items` array contains only full-plan acquisition items for those of the five named candidates that have repair obligations. An approved keep row from the same sidecar (empty `missing_docs`) may appear in `candidate_ids` without contributing items; the executor still requires a docket snapshot for every named candidate. The hashed field set is unchanged: `items` remain the full-plan projection, and keep IDs are named only in `candidate_ids`.

The pilot preserves the full plan's free-first order and refuses projected paid cost above the explicit pilot sub-cap. Its activity flags are always false because projection performs no resolution, network request, provider call, fee acknowledgement, purchase, parsing, Stage A execution, freeze, dispatch, or publication.

A later executor must bind every resolved document identity and acquisition operation to both the pilot and full-plan digests. This artifact does not translate into an older purchase authority and cannot authorize a hand-built legacy selection or budget plan.
