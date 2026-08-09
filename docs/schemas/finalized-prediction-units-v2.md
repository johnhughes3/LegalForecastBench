# Finalized Prediction Units v2

`legalforecast.finalized_prediction_units.v2` is the Cycle 1 successor envelope for finalized Stage A prediction units. It preserves every v1 field and adds required `dropped_units` provenance so a blinded lawyer may remove a spurious nonunit without excluding an otherwise usable candidate.

Each `dropped_units` row contains the original `unit_id`, its canonical `source_unit_sha256`, the consuming `adjudication_id` and `adjudication_sha256`, and `disposition: DROP`. The referenced adjudication must name exactly that one distinct `source_unit_id`, include a nonempty `drop_reason`, and may consume multiple review IDs only when they all concern that same source unit. A dropped unit cannot also appear in `prediction_units`, duplicate drop rows are invalid, and a retained candidate must contain at least one finalized unit.

The v1 schema remains supported for immutable artifacts that predate `DROP`, but it cannot contain `dropped_units` or a `DROP` adjudication. New `apply-unitization-review` outputs use v2. Downstream readers accept both versions explicitly and continue to authenticate the raw-unit, review-queue, source-unit, and adjudication commitments.
