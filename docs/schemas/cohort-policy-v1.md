# Cohort policy and observation manifest schemas

`legalforecast.cohort_policy.v1` is the Cycle 1 acquisition precommitment schema. The generator accepts a decisions object only after John has supplied every policy value, validates it strictly, canonicalizes it, and stores its SHA-256 as `policy_sha256`. Regenerating the same decisions produces byte-identical output. An existing policy file may be verified or regenerated identically but may not be overwritten with changed content.

The top-level artifact contains exactly `schema_version`, `policy`, and `policy_sha256`. The `policy` object contains exactly:

- `cycle_id`, `cycle_acquisition_hash`, and `eligibility_anchor`.
- `stop_rule`: `mode` (`deadline_only` or `target_or_deadline`), `target_clean_cases`, `search_window_end`, and mandatory frontier-exhaustion and budget-headroom stop flags.
- `window_policy`: `overlap_days`, `backfill_late_indexed`, and `refresh_before_purchase`.
- `refresh_policy`: immutable, refreshable, accepted, newly-free, and transient reason-code lists derived from and required to equal the cycle store's complete transition taxonomy; the exact ordered evidence classes `transient`, `excluded_refreshable`, `accepted`, `newly_free`, and `excluded_immutable`; and explicit transition semantics requiring immutable exclusions never be reconsidered, transient failures never supersede evidenced state, higher-ranked evidence supersede lower-ranked evidence, and latest observations win only among equal ranks.
- `packet_completeness`: required motion-or-combined memorandum, conditionally required docketed opposition, and non-required reply definitions.
- `target_motion`: the deterministic earliest-eligible-MTD/lowest-entry-number selector and exactly-one-motion invariant.
- `purchase_policy`: `buy_cheapest_complete`, decimal-string cycle and per-case caps, and reservation-headroom enforcement.
- `disclosure_clearance`: clearance for every document, quarantine of unknown or unscannable documents, and next-cheapest eligible replacement under the same cap.
- `reduced_n`: the target clean count; an ascending list of inclusive `claim_tiers` that is contiguous, non-overlapping, and terminates exactly at the target; and an explicit `below_minimum_action` (`pilot_only_no_official_cycle` or `abort_cycle`). Each tier binds its minimum and maximum clean-case counts, claim class, optional minimum prediction-unit threshold, and a mandatory lower claim class or terminal action when that threshold is not met. The first tier's minimum implicitly defines the below-minimum range. For example, the proposed Cycle 1 values can represent 40-99 as provisional feasibility, 100-149 as official descriptive subject to a unit threshold, and 150 as the target class, while counts below 40 remain pilot-only rather than silently becoming an official cycle.

Unknown fields fail validation. In particular, `cycle_series` and per-batch snapshot hashes are prohibited: `cycle_series` belongs only in the later evaluation execution policy, while observed snapshot hashes belong only in the append-only manifest.

`legalforecast.cohort_observation_manifest.v1` is canonical JSONL. Record zero is a `header`; later records are `snapshot` observations exported from complete, saturated snapshots recorded in the cycle acquisition store. Every record contains a contiguous `sequence`, the cycle and policy commitments, `previous_record_sha256`, and `record_sha256`. Snapshot records additionally contain `snapshot_id`, `batch_id`, `batch_digest`, `snapshot_manifest_sha256`, and `snapshot_created_at`.

Export is append-only: the existing records must verify and must be an exact prefix of complete snapshots in the cycle store. The exporter appends only new snapshots using `O_APPEND` under an exclusive lock and never rewrites old rows. Snapshot bytes and store commitments are reverified before append. The final record hash is the observation-manifest state commitment consumed later by evaluation-policy integration; this acquisition-side implementation does not invoke or modify freeze, evaluation, or dispatch.
