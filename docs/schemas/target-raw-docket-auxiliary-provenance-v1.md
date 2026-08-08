# Target raw-docket auxiliary provenance bridge v1

`legalforecast.target_raw_docket_auxiliary_provenance_bridge.v1` is a provider-free provenance descriptor for a completed target cohort.

It does not create a new screening snapshot or alter eligibility, ranking, selection, or model-visible materials.

The descriptor authenticates all of the following before publishing its immutable output manifest:

- the frozen screening snapshot, union run card, cycle store, and canonical raw-artifact manifest;
- the exact target selection;
- the completed raw-docket recovery plan, receipt, successes, exclusions, summary, and recovered raw HTML bytes; and
- the combined raw-artifact projection.

The projection retains every canonical raw-artifact record byte-for-byte and adds only the selected candidate identities absent from the canonical manifest.

The bridge records that it requested and executed neither provider activity nor paid activity.

`legalforecast.target_raw_docket_auxiliary_provenance_bridge_run_card.v1` is the corresponding completion record.

`acquisition plan-packet-inputs --raw-provenance-bridge` loads and reauthenticates this descriptor before accepting the auxiliary raw HTML paths; packet-planner replay reauthenticates the same committed descriptor.
