# Unitization adjudication v3

`legalforecast.unitization_adjudication.v3` is the closed attorney decision for one candidate-level unitizer-terminal review. It exists because an exhausted unitizer produced no frozen source unit for the ordinary v1/v2 adjudication contracts to consume.

Every record contains exactly one terminal `review_id`, the matching candidate and case IDs, the canonical `terminal_escalation_sha256`, a unique `adjudication_id`, nonempty `adjudicator_id` and `adjudication_notes`, and one of two dispositions:

- `ADD` requires one or more complete `finalized_units`, omits `exclusion_reason`, and may reconstruct several independently disposable units from the authenticated predecision record in one candidate decision.
- `CANDIDATE-EXCLUSION` requires an empty `finalized_units` array and a nonempty `exclusion_reason`. It records the attorney's decision but is not authority to publish a 99-candidate artifact: exact-100 successor apply stops and requires an authenticated replacement candidate.

The record must omit `source_unit_ids`: no unit existed before attorney reconstruction. An added unit may not declare its own provenance fields, must have a unique unit ID, must carry nonempty source citations, and may cite only document IDs committed by the terminal receipt. At apply time, local code also reconstructs each complete citation against authenticated source text and verifies its document role, exact line span and excerpt, page marker, and docket evidence; an allowed document ID is necessary but not sufficient. Local code derives the receipt, review, and adjudication provenance that appears in finalized v4; the adjudicator may not author those links.

No other disposition is valid. In particular, `ACCEPT`, `AMEND`, `SPLIT`, `MERGE`, and `DROP` require an existing unit and remain on the ordinary adjudication path. Adjudication v3 does not broaden ordinary omission `ADD`, which remains a one-unit v2 operation bound to an authenticated structural-omission flag.
