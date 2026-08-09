# Finalized Prediction Units v2

`legalforecast.finalized_prediction_units.v2` is the explicit Cycle 1 correctness-emergency migration for finalized Stage A prediction units. It preserves every v1 field and adds required `dropped_units` provenance so a blinded lawyer may remove a spurious nonunit without excluding an otherwise usable candidate.

Each `dropped_units` row contains the original `unit_id`, its canonical `source_unit_sha256`, the consuming `adjudication_id` and `adjudication_sha256`, and `disposition: DROP`. The referenced adjudication must name exactly that one distinct `source_unit_id`, include a nonempty `drop_reason`, and may consume multiple review IDs only when they all concern that same source unit. A dropped unit cannot also appear in `prediction_units`, duplicate drop rows are invalid, and a retained candidate must contain at least one finalized unit.

## Migration boundary

The affected artifacts are Cycle 1 finalized Stage A outputs whose blinded adjudications use `DROP`, plus the downstream readers that authenticate those outputs. Existing v1 artifacts remain immutable. An application run with no `DROP` continues to emit byte-compatible v1 records; the migration activates for the entire new output only when at least one adjudication uses `DROP`, preventing a mixed-schema artifact.

The migration validates the complete current Stage A chain before publication: the authenticated raw-unit candidate set, every review-queue row, every adjudication, every source-unit hash, the full queue drain, and every retained, replaced, excluded, or dropped unit. `apply-unitization-review` then re-verifies the produced envelope against those complete inputs before writing its authenticated run card. This batches the known correctness defects addressed by the migration: spurious nonunits that require deletion and multiple review objections attached to one source unit. It does not mutate, promote, or patch any earlier artifact.

The v1 schema remains supported for immutable artifacts that predate `DROP`, but it cannot contain `dropped_units` or a `DROP` adjudication. Downstream readers accept both versions explicitly and continue to authenticate the raw-unit, review-queue, source-unit, and adjudication commitments.
