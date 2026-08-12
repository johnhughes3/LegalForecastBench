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

The downstream Stage B gates now authenticate v3 as well. `legalforecast.ingestion.decision_text_artifact` accepts a v3 envelope only after the shared finalized-envelope verifier succeeds, and its per-unit check requires the deliberate empty `source_unit_sha256s` for `ADD` while preserving nonempty hash links for every other disposition. `legalforecast.ingestion.corpus_readiness` accepts `ADD` adjudications only when they omit `source_unit_ids`, retain the v3 hash binding to the adjudication, and pass the same finalized-unit envelope checks; malformed or mixed provenance continues to fail closed.

Existing v1 and v2 artifacts remain byte-compatible, and the Stage A-only fail-closed boundary described above was the deliberate accepted end state for the earlier milestone, not an oversight. This migration now completes the separate Stage B/readiness integration lane tracked as `legalforecastbench-ch6` without mutating or promoting any earlier artifact.
