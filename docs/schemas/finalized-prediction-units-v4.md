# Finalized Prediction Units v4

`legalforecast.finalized_prediction_units.v4` is the finalized terminal-unitizer candidate envelope produced from an authenticated terminal receipt, its candidate-level review row, and an `ADD` [`legalforecast.unitization_adjudication.v3`](unitization-adjudication-v3.md) decision.

Every closed envelope contains `schema_version`, `status`, `candidate_id`, `case_id`, `unitizer_terminal_escalation_sha256`, the canonical digest of the complete terminal review queue, `prediction_units`, `exclusion`, and `added_units`. In the Cycle 1 exact-100 path its status is `finalized` and `exclusion` is null.

For `status: finalized`, `exclusion` is null and the envelope contains one or more attorney-reconstructed prediction units. Each unit has:

- empty `source_unit_sha256s`, because the unitizer emitted no source unit;
- the locally derived adjudication ID and digest;
- `disposition: ADD` and the single `added_from_review_ids` value;
- the terminal receipt digest; and
- the receipt's ordered `predecision_source_document_ids`.

The `added_units` ledger has exactly one row for each prediction unit and repeats only its unit ID, review ID, receipt digest, adjudication ID and digest, and `ADD` disposition. Unit and ledger IDs must match exactly, and each canonical unit body must equal the attorney's v3 output.

Adjudication v3 can represent `CANDIDATE-EXCLUSION`, but the Cycle 1 exact-100 successor apply does not emit a `candidate_excluded` v4 envelope or accept a shrunken downstream cohort. It fails closed without publishing the finalized artifact until an authenticated replacement candidate has traversed the upstream lineage.

Verification requires exact candidate coverage across receipts, terminal queues, adjudications, and v4 envelopes; reproduces the queue, receipt, and adjudication hashes; and rejects substituted unit content, duplicate IDs, orphaned ledgers, invented provenance, or mixed ADD/exclusion output. It reconstructs every complete citation against authenticated parser and Markdown lineage and verifies exact source text, document role, line span, excerpt, page marker, and docket evidence rather than trusting document-ID membership alone.

This v4 schema is not a successor for every ordinary finalized-unit artifact. Existing finalized v1/v2/v3 envelopes retain their meanings and remain supported. V4 is valid only for terminal-unitizer candidates and cannot be used to bypass the ordinary source-unit and structural-flag chains.
