# RECAP Fetch confirmation provenance sidecar v1

`legalforecast.recap_fetch_confirmation_provenance.v1` is a non-authoritative observation emitted beside a purchase journal after a CourtListener RECAP Fetch operation reaches `confirmed` with its original queue-lag evidence intact. It records whether confirmation used the status-2 queue receipt or the already-public document during queue lag. A sparse submitted or queued row later confirmed only by billing reconciliation is ineligible because it lacks that original observation; reconciliation still succeeds without emitting a sidecar for that row.

The sidecar is not a purchase result, ledger row, billing receipt, clearance decision, or corpus-membership authority. It must never be merged into `response_json`, the canonical purchase-operation record, the canonical purchase-state record, or any other authenticated Cycle 1 bytes.

The exact closed field set is `canonical_purchase_operation_sha256`, `candidate_id`, `confirmation_evidence`, `cycle_id`, `non_authoritative`, `provider_detail_sha256`, `purchase_policy_sha256`, `queue_id`, `queue_response_sha256`, `schema_version`, and `source_document_id`.

`schema_version` is `legalforecast.recap_fetch_confirmation_provenance.v1`; `non_authoritative` is always `true`; `confirmation_evidence` is either `recap_fetch_queue_status_2` or `public_document_during_queue_lag`; and every non-null digest is lowercase SHA-256 without a prefix.

`provider_detail_sha256` is the SHA-256 of canonical compact JSON for the exact `post_delivery_restrictions` provider document retained in the confirmed response. `queue_response_sha256` is the same digest for the exact status-2 queue response, or JSON `null` when the queue detail was not visible and confirmation used the public document.

Each file is named `<canonical_purchase_operation_sha256>.json` under the private `purchases.sqlite3.confirmation-provenance/` directory (or an explicitly supplied output directory). Files are create-once and digest-keyed; if a later billing reconciliation changes the canonical operation digest, a new observation is emitted and the prior observation remains historical evidence.

The sidecar writer is read-only with respect to the purchase journal. It writes and fsyncs a no-follow, singly-linked temporary in the output directory, atomically installs the create-once final name only after those bytes are durable, fsyncs the directory, and uses canonical JSON bytes with a trailing newline. Replaying the writer must leave the journal's operation records and purchase-state digest byte-for-byte unchanged.
