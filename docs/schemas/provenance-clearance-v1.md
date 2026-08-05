# Provenance clearance v1

**Superseded.** `plan-disclosure-provenance --schema-version` accepts only `v2` and `v3`, so this contract can no longer be emitted. It is retained because v1 artifacts from historical runs remain verifiable against it. For new work use [provenance clearance v2](provenance-clearance-v2.md) (the current default) or [provenance clearance v3](provenance-clearance-v3.md).

Cycle 1 uses provenance-first disclosure clearance instead of a signing-key ceremony.
The supported path is `plan-disclosure-provenance` -> `record-disclosure-review-decisions` for exceptions -> `clear-provenance-disclosures`.
Legacy signed-review artifacts remain verifiable for historical runs but are not a Cycle-1 readiness dependency.

## Routing plan

`plan-disclosure-provenance` consumes the exact frozen disclosure requests, complete download manifest, full case-relevance artifact, restriction evidence, and acquired document tree.
It rejects symlinks, hard links, special files, changed bytes, malformed or semantically mismatched source bytes, incomplete key coverage, and unexplained relevance-only rows.
Every relevance-only document must be an explicit unavailable paid-recovery gap.

The output schema is `legalforecast.disclosure_provenance_routing_plan.v1`.
A document is `auto_clear` only when all of the following are true:

- its current descriptor-stable bytes match the manifest SHA-256 and byte count;
- it is a free CourtListener document with an allowlisted public `storage.courtlistener.com/recap/` URL that matches case relevance;
- public provenance is affirmative, either from the checked public-download record or the exact CourtListener REST proof set;
- the visibility contract is exactly predecision/model-visible or decision/outcome-only;
- automated disclosure scanning returns no marker; and
- no status, boolean, or evidence token affirmatively indicates sealed, private, restricted, or under-seal material.

All other rows route to `john_exception_review`.
Marker-only or missing-provenance exceptions may be cleared after inspection.
A positive restriction or visibility contradiction sets `human_clearance_permitted: false` and can never be cleared.

The planner also emits `legalforecast.disclosure_exception_worksheet.v1` and an exception-only private inspection map.
The full immutable case-relevance artifact remains committed; the planner never filters or forks it upstream.

## Hash-bound John review

`record-disclosure-review-decisions` requires reviewer ID `John Hughes` for a provenance exception worksheet.
For every exception it displays the controlled inspection path and exact SHA-256, requires the full hash to be typed, records a cleared or quarantined decision, reopens the bytes, and checkpoints the result before continuing.
The terminal batch confirmation binds canonical decision bases and counts.

The recorder run card commits the worksheet and inspection-map hashes, checkpoint-config path and hash, checkpoint-directory path and tree hash, completed count, reviewer ID, timestamps, decisions hash, and batch confirmation.
The final decisions are reconstructed from the committed checkpoint bytes.
Hand-authored or rehashed decision/run-card pairs are not authority.
If there are no exceptions, the same command deterministically publishes an empty decision artifact and zero-count checkpoint/run-card commitments without prompting.

## Private-store trust boundary

Cycle 1 deliberately uses no FIDO key, hardware signature, or other cryptographic proof of human identity.
The controlled private store and the integrity of the host account that owns it are therefore trusted boundaries: a malicious writer running as that same UID could forge internally consistent checkpoints and hashes.
The reviewer ID and review/inspection timestamps are asserted audit metadata, not cryptographic identity or trusted-time evidence.
The hashes, descriptor-stable reads, replay checks, and typed batch confirmation detect drift and unsupported artifact construction only while that host/private-store boundary remains trustworthy.
If same-UID or private-store integrity is in doubt, invalidate the clearance and repeat review from the frozen public inputs on a trusted host; do not describe the existing artifacts as cryptographically authenticated.

## Final clearance and downstream replay

`clear-provenance-disclosures` reopens the exact current inputs and document bytes, regenerates the routing plan and exception worksheet byte for byte, verifies the frozen cohort policy, validates the private inspection map and checkpoint tree, reconstructs every decision, and writes canonical `legalforecast.disclosure_clearance.v1` rows.

Automatic rows have `clearance_basis: "affirmative_public_provenance"`, no reviewer or review timestamp, the public source URL as provenance, and the routing-plan hash.
Exception rows have `clearance_basis: "john_exception_review"`, reviewer `John Hughes`, a validated review timestamp, controlled private-store provenance, and the same routing-plan hash.
Legacy rows omit both new fields so their v1 bytes remain unchanged.

The completed run card uses `clearance_authority.kind: "provenance_first_with_john_exceptions"` and commits the exact cohort policy, plan, worksheet, decisions, recorder run card, document tree, output rows, exception batch, reviewer, and route counts.
Projection and materialization dispatch on this authority kind and independently replay all commitments.
Unknown authority kinds, missing inputs, altered checkpoints, changed PDFs, positive restrictions, visibility contradictions, or noncanonical clearance rows fail closed.

## Purchased and post-recovery documents

Purchased or unknown-origin bytes use the same planner, exception recorder, and finalizer after recovery has emitted the exact manifest, fresh restriction evidence, complete case-relevance rows, review requests, and committed document tree.
A successful purchase is not affirmative public provenance and therefore does not itself auto-clear a document.
The purchased clearance run card is replayed before post-recovery resolution and again before combined materialization.

`resolve-post-recovery-documents` accepts `--reviews` and `--review-receipt` only for a legacy signed-review run card.
For `provenance_first_with_john_exceptions`, it discovers the exception decisions, recorder run card, worksheet, plan, cohort policy, manifest, restrictions, and document tree from the clearance commitments and independently validates them.
The v1 resolved schema retains the field names `reviews_artifact_sha256` and `review_receipt_sha256` for byte compatibility; under the provenance authority kind those fields commit the exception-decisions artifact and exception-recorder run card respectively.
Downstream consumers must dispatch on the authority kind rather than infer semantics from those historical field names.

Retained-cohort extension follows the same rule.
Its frozen lineage field names retain the decisions and recorder hashes for schema continuity, while the clearance run card supplies the authoritative provenance semantics.

No step contacts a provider, acknowledges fees, purchases a document, invokes parsing or labeling, freezes the official cycle, evaluates models, or dispatches packets.
