# RECAP Fetch confirmation provenance

**Status:** adopted 2026-08-17 · non-authoritative · applies to the Cycle 1 purchase journal.

A queued RECAP Fetch purchase is normally confirmed from the queue receipt (`status=2`). When CourtListener's queue detail lags behind the paid dispatch — a `404` or `5xx` on `/recap-fetch/{id}/` while the PDF is already published — the client confirms from the public document instead, after verifying document identity and an allowlisted download URL. That path exists so a later retry cannot issue a second paid POST.

Both confirmations bind billing identically. They do not rest on the same evidence, and only the first carries a queue receipt.

## Why the marker is not on the purchase row

`response_json` is embedded in `_purchase_operation_record`, so it is covered by `canonical_purchase_operation_sha256` and `canonical_purchase_state_sha256`. [Cycle 1 change control](cycle-1-change-control.md) freezes those bytes and routes new observational metadata into non-authoritative sidecars. Adding a `confirmation_evidence` field to the confirmed response would move both digests without the versioned emergency migration that a frozen-contract change requires.

Before this sidecar existed the weaker evidence could only be inferred from an absent `queue_response` key — true, but unstated, and indistinguishable from a field that was simply never written.

## The sidecar

`legalforecast/ingestion/recap_fetch_confirmation_provenance.py` writes one JSON document beside the canonical ledger, at `<ledger>.confirmation-provenance.json`. That name is deliberately outside `_purchase_ledger_reserved_paths`, so the sidecar enters neither the ledger's authenticated filesystem identity nor the byte closure returned by `read_case_dev_purchase_authority_audit`. Nothing on the authoritative purchase path reads it, and no failure in it can change a billing state.

Following the same convention as the [contamination tier sidecar](contamination-tier-reporting.md), the document declares `kind` equal to `recap_fetch_confirmation_provenance_sidecar` and `authoritative` equal to `false`, and deliberately does not declare a `legalforecast.*.vN` `schema_version`.

```json
{
  "kind": "recap_fetch_confirmation_provenance_sidecar",
  "authoritative": false,
  "cycle_id": "cycle-1",
  "purchase_policy_sha256": "…",
  "confirmations": {
    "123": {
      "queue_id": "77",
      "confirmation_evidence": "public_document_during_queue_lag",
      "confirmed_response_sha256": "…",
      "queue_receipt_attached_after_confirmation": false
    }
  }
}
```

`confirmation_evidence` is one of `recap_fetch_queue_status_2` or `public_document_during_queue_lag`. When a queue receipt is present the entry also carries `queue_response` and `queue_response_sha256`.

## Reading it honestly

Two bindings keep an entry from being read as evidence about something it does not describe:

- **Row binding.** `confirmed_response_sha256` commits the exact confirmed response the entry annotates. An entry whose digest no longer matches the row in front of the reader is refused rather than reconciled.
- **Generation binding.** `cycle_id` and `purchase_policy_sha256` bind the whole document to one ledger generation. A document from another generation reads as no observation and is replaced on the next write, so a stale file can never block acquisition.

A present but malformed document — bad JSON, a foreign `kind`, or an entry missing a required field — fails closed when read as evidence, because reporting loss as an empty set would present it as a fact.

Writers cannot fail closed on the same input, and should not: an unreadable observational file is not preservable, and refusing to write would strand acquisition behind a file no purchase depends on. The write path replaces the rubble and lets the backfill refill it from the journal.

A sidecar that cannot be persisted at all — a full disk, a directory that lost write permission, a path replaced by a symlink — is absorbed by the client for the same reason, one step further out. Every write runs after `confirm_reserved` has already committed the charge, so raising would lose the caller's purchase result for a durable, already-paid row and would fail identically on every retry over it. The module still raises; only `courtlistener_recap_fetch.py` absorbs it, and only for `OSError` and `RecapFetchConfirmationProvenanceError`, so a genuine defect in the sidecar still surfaces.

## Late queue-receipt attachment

When a purchase was confirmed during queue lag and CourtListener later publishes the queue detail, the next run over that document attaches the stronger receipt to the sidecar entry and sets `queue_receipt_attached_after_confirmation`. This costs one free `GET /recap-fetch/{id}/`, happens only for entries that lack a receipt, and touches no billing state: `confirm_reserved` already ran, the confirmed response bytes stay exactly as the confirmation wrote them, and the purchase state digest does not move.

A confirmed row with no sidecar entry is backfilled from its confirmed response on the next run, since which branch confirmed it is recoverable from bytes already held. Backfill asks CourtListener nothing.

## What it deliberately does not record

An absent `queue_response` names the weaker evidence only for a response the direct queued-confirmation path wrote, because that path writes the receipt whenever it has one. A purchase confirmed by reconciling an authoritative broker receipt carries no queue payload either, even though the broker verified a readable `status=2` queue detail before reconciling. Reading absence alone would label that row as queue-lagged and then spend a free queue read chasing a receipt its confirmation already had, so the sidecar stays silent about it: a row with no `post_delivery_restrictions` in its confirmed response gets no entry. Recording broker-confirmed evidence is a separate observation, not this one told wrong.

## Operator notes

- The sidecar is private (`0600`) and replaced atomically. It is not an input to any gate, validator, or published artifact.
- Deleting or corrupting it loses only the late-attached receipts; the evidence kind is reconstructed on the next run, and no run stops because of it.
- It belongs to exactly one ledger generation. Re-initializing a ledger at the same path leaves the old sidecar in place until the next confirmation rewrites it.
