# Finalized Prediction Units v3

`legalforecast.finalized_prediction_units.v3` is the explicit Cycle 1 correctness migration that lets a blinded adjudicator repair a structural omission. It preserves every v2 field, including required `dropped_units`, and adds both an explicit `added_units` envelope ledger and the provenance an `ADD` disposition needs so a unit the Stage A unitizer never emitted can enter the finalized artifact without forging a derivation from a raw unit that is not its source.

## Why ADD exists

The structural reviewer may only flag, and an `omitted` flag names the neighbouring unit it noticed the gap from — not the missing unit, which has no identifier. Every pre-`ADD` disposition resolves a review by consuming that named unit: `ACCEPT` discards the finding, `AMEND` and `SPLIT` emit the missing unit as though it were derived from the named unit's canonical hash, and `CANDIDATE-EXCLUSION` discards an otherwise usable candidate. The first three either lose the finding or write a false hash link into the chain; the fourth is the only honest option and costs a case. `ADD` is the narrow fourth path: it consumes the omitted review, adds one unit, and leaves every raw unit intact.

## Added-unit provenance

An added unit appears in `prediction_units` with `disposition: ADD`, an empty `source_unit_sha256s` (it derives from no raw unit), and five bindings:

- `adjudication_id` and `adjudication_sha256` — the consuming `ADD` adjudication, which must name this candidate and no `source_unit_ids`.
- `added_from_review_ids` — the exact review IDs the adjudication consumed, in adjudication order.
- `structural_flag_sha256` — the single authenticated structural flag those reviews carry. Reviews from two different flags may not be combined into one `ADD`.
- `raw_prediction_units_sha256` — the raw candidate envelope the flag was raised against, which must equal the finalized record's own raw-unit commitment.
- `predecision_source_document_ids` — the sorted union of the consumed reviews' cited predecision documents, which must equal the document IDs in the added unit's `source_citations` exactly. Citing a document the reviewer did not cite is unauthenticated evidence; omitting one is incomplete coverage.

Each consumed review must be a `structural_omitted` queue row for this candidate, carrying its flag hash, its raw-envelope commitment, and at least one cited predecision document. An added `unit_id` may not collide with a raw unit, a retained unit, or another added unit.

Every v3 envelope also contains an `added_units` array, including an empty array for a candidate with no local ADD in an otherwise v3 run. It contains exactly one row per added prediction unit: `unit_id`, ordered `review_ids`, `structural_flag_sha256`, `raw_prediction_units_sha256`, `adjudication_id`, `adjudication_sha256`, and `disposition: ADD`. The ledger row must match exactly one ADD prediction unit and one ADD adjudication. Missing, duplicate, mismatched, or orphaned ledger rows fail verification.

## Migration boundary

The affected artifacts are Cycle 1 finalized Stage A outputs whose blinded adjudications use `ADD`, plus the Stage A readers that authenticate those outputs. Existing v1 and v2 artifacts remain immutable. An application run with no `ADD` continues to emit byte-compatible v1 or v2 records; the migration activates for the entire new output only when at least one adjudication uses `ADD`, preventing a mixed-schema artifact. A v1 or v2 record containing an `ADD` unit is invalid, and so is a v3 added unit that declares any source-unit hash. `ADD` requires `legalforecast.unitization_adjudication.v2`; the v1 adjudication contract remains valid only for pre-ADD dispositions.

`apply-unitization-review` re-verifies the produced envelope against the complete inputs — raw candidate set, every review-queue row, every adjudication, every source-unit hash, the full queue drain — before writing its authenticated run card, so an added unit that cannot reproduce its evidence chain never reaches an artifact. The migration does not mutate, promote, or patch any earlier artifact.

Two downstream gates do not yet know `ADD`, and both fail closed rather than silently accepting it. `legalforecast.ingestion.decision_text_artifact` authenticates v1 and v2 only, so it rejects a v3 envelope as an unsupported schema before reaching its per-unit checks. After schema support is migrated, those checks must also allow the deliberately empty `source_unit_sha256s` required by an added unit; `legalforecast.ingestion.corpus_readiness` accepts only the pre-`ADD` disposition set, so a cycle whose adjudications use `ADD` reports `stage_a_review_adjudication_invalid` instead of reaching readiness.

This boundary is deliberate and is the accepted end state for the Stage A-only milestone, not an oversight: this change lands `ADD` for Stage A adjudication and stops there, so a v3 artifact cannot silently flow into Stage B labeling or corpus readiness on a chain that has not been re-authenticated for empty source hashes. Until that migration lands, a cycle that uses `ADD` is a Stage A artifact only. Adopting v3 in the Stage B decision-text chain and the readiness gate is a separate migration in its own integration lane, tracked as `legalforecastbench-ch6`.
