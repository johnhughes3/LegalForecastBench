# CourtListener RECAP Fetch purchase broker v1

LegalForecastBench must not receive or store raw PACER credentials. PACER does not provide a hard account-wide spend cap, so an agent-readable username and password would let a compromised development host bypass the repository's SQLite journal and frozen budget policy.

The `acquisition purchase-missing-recap-fetch` adapter therefore supports offline fixtures but deliberately fails closed for production purchases until the dedicated `secure-gate-recap-fetch-broker` Worker implements and deploys this contract. Direct CourtListener document verification and local queue polling use `COURTLISTENER_API_TOKEN`; the charge-bearing POST and all PACER credentials remain inside the broker boundary.

## Service boundary

The production broker is a dedicated Worker on `https://secure-gate-recap-fetch.johnjhughes.com` with its own D1 database. It must not share a runtime with secure-gate Broker/Admin and must not receive GitHub App, deployment-approval, sudo, workflow, browser-session, or general secure-gate machine-grant authority.

The LegalForecastBench client receives a dedicated, expiring P-256 machine identity that is recognized only by this Worker. Requests use the `SECURE-GATE-MACHINE-V1` signed-request format, a single-use nonce, and the approved Tailscale App Connector source path. Ordinary secure-gate machine grants and keys are not valid broker identities.

The purchase identity may invoke only the submission and receipt routes below. Policy activation and billing reconciliation use a separate protected control-plane identity and are never authorized by the purchase identity.

Every authenticated request carries `x-secure-gate-machine-id`, `x-secure-gate-machine-timestamp`, `x-secure-gate-machine-nonce`, and `x-secure-gate-machine-signature`. The timestamp is 13-digit Unix epoch milliseconds, may be at most 60 seconds in the future, and expires five minutes after issuance. The nonce is 22 to 128 unpadded base64url characters and is consumed atomically. The P-256/SHA-256 signature covers `SECURE-GATE-MACHINE-V1`, uppercase method, path and query, lowercase SHA-256 of the exact body bytes, timestamp, nonce, and machine ID, joined in that order by newline characters.

A purchase identity expires no later than 24 hours after activation. Renewal or revocation is a protected control-plane operation; there is no purchase-identity self-enrollment or renewal route.

## Submission API

The submission endpoint is `POST /v1/recap-fetch` with `Content-Type: application/json` and `x-secure-gate-action: recap-fetch-submit`.

The body is a JSON object containing exactly these six string fields and no others:

- `request_type`: exactly `2`, CourtListener's individual-document RECAP Fetch request type.
- `recap_document`: the base-10 positive-integer CourtListener RECAP document ID with no sign, whitespace, or leading zeroes.
- `cycle_id`: the immutable purchase-policy cycle ID registered in the active broker policy.
- `purchase_policy_sha256`: exactly 64 lowercase hexadecimal characters and equal to the active policy digest.
- `operation_key`: a canonical lowercase UUIDv4 generated and durably committed by the local journal before submission.
- `reservation_usd`: canonical USD with exactly two fractional digits, matching `^(0|[1-9][0-9]*)\.[0-9]{2}$`, and exactly equal to the active policy's per-document reservation.

The request never contains a PACER username, PACER password, PACER client code, CourtListener token, case ID, candidate ID, cap, or opening-spend value. Authentication fields are request headers, not JSON fields.

The broker parses every USD value to a nonnegative integer number of cents before comparison or storage. It must never use binary floating-point or a database `REAL` value for caps, reservations, holds, or fees.

## Reviewed policy activation and document allowlist

Before a cycle can accept submissions, an out-of-band reviewed deployment must import and activate one immutable broker policy artifact with this logical schema:

```json
{
  "version": "courtlistener-recap-fetch-policy-v1",
  "cycle_id": "cycle-1",
  "purchase_policy_sha256": "<64 lowercase hex characters>",
  "cycle_cap_usd": "100.00",
  "per_case_cap_usd": "10.00",
  "reservation_usd": "3.05",
  "opening_committed_spend_usd": "0.00",
  "opening_case_committed_spend_usd": {},
  "allowed_documents": [
    { "recap_document": "123", "case_id": "candidate-123" }
  ]
}
```

All USD fields use the canonical two-decimal representation defined above. `opening_case_committed_spend_usd` maps case IDs to canonical amounts already committed before activation; its sum must not exceed `opening_committed_spend_usd`. Any unattributed remainder counts against the cycle cap but cannot be used to reduce a case's committed amount.

The activation process must validate that document IDs are unique, every document maps to exactly one nonempty case ID, all amounts are nonnegative, the reservation and per-case cap are positive, the per-case cap does not exceed the cycle cap, and opening committed spend does not exceed the cycle cap. The broker stores the reviewed artifact's SHA-256 digest and activation evidence reference in addition to the LegalForecastBench `purchase_policy_sha256`.

Activation is append-only. A cycle ID or purchase-policy digest may not be overwritten, and at most one policy may accept new submissions for a cycle. Changes require a new reviewed artifact and policy identity; disabling a policy prevents new reservations but does not release existing holds.

The broker derives `case_id` exclusively from the reviewed `recap_document` allowlist. This server-side mapping, not caller input, is the authority for the per-case cap.

## Atomic reservation and idempotency

Before any provider request, one D1 transaction must either insert the operation in `submitted` with its full hold or make no change. The transaction validates the identity, active cycle, exact policy digest, exact reservation, document allowlist, cycle cap, and server-derived per-case cap.

For cap calculations, committed spend is the policy's opening committed spend plus every operation's current hold or reconciled authoritative fee. The new reservation is permitted only when both of these are true:

- cycle committed cents plus reservation cents is less than or equal to the cycle cap cents;
- the server-derived case's committed cents plus reservation cents is less than or equal to the per-case cap cents.

`operation_key` is the idempotency key and primary operation identity. The broker stores a SHA-256 digest of the canonical six-field request. A replay with the same operation key and a different request digest returns `409 operation_key_conflict` and never calls CourtListener. A byte-equivalent replay never calls CourtListener and behaves as follows:

- If a queue ID is known, return the original exact two-field success receipt with HTTP `200`.
- If the operation is still `submitted` or `unknown` and no queue ID is known, return `409 operation_outcome_pending` and direct the caller to the receipt endpoint.
- If protected reconciliation established a definite pre-queue failure with no charge and no queue ID, return `409 operation_failed`.

The local journal must never automatically resubmit an operation after an ambiguous response, regardless of the HTTP status it observed.

## PACER client code

For every newly inserted operation, the broker derives and persists a PACER client code as `lfb-` followed by the first 26 characters of the unpadded lowercase RFC 4648 base32 encoding of `SHA-256(UTF-8(operation_key))`. The result is 30 characters, within PACER's 32-character limit, and the database enforces uniqueness.

Although CourtListener treats `client_code` as optional, this broker always supplies the derived value. A client-code collision fails closed before the provider request with `500 client_code_collision`; the broker must not choose an unreviewed alternate mapping or omit the code.

The persisted client-code mapping is the primary correlation key for PACER Detailed Transactions and invoice reconciliation. The submission response does not expose it, but the authenticated receipt API does.

## Exact CourtListener request

After `submitted` is durably committed, the broker issues exactly one request to `https://www.courtlistener.com/api/rest/v4/recap-fetch/`:

- method: `POST`;
- redirect mode: disabled/manual, with every redirect treated as an unknown paid outcome;
- `Authorization: Bearer <broker-custodied COURTLISTENER_API_TOKEN>`;
- `Content-Type: application/x-www-form-urlencoded`;
- form fields: `request_type=2`, `pacer_username`, `pacer_password`, `recap_document`, and the derived `client_code`;
- automatic retries: zero for every timeout, transport error, redirect, HTTP response, parse error, or Worker exception.

The form contains no other field unless a later reviewed contract version explicitly adds it. The broker verifies the fixed HTTPS scheme, host, port, and path in code rather than accepting a caller-supplied provider URL.

The CourtListener token, PACER username, and PACER password are dedicated Worker secrets provisioned through the protected deployment path. They must never appear in Terraform state, repository files, client environments, D1, logs, errors, traces, Sentry events, response hashes, receipts, or evidence references.

## Provider outcome and state ownership

The broker owns its operation state. LegalForecastBench may continue noncharging CourtListener queue polling to acquire the delivered document, but local polling cannot confirm a charge, release a broker hold, or mutate broker state.

The state machine is:

- `submitted`: the reservation and operation are durable and the paid provider request has not produced a valid queue receipt.
- `queued`: CourtListener returned a syntactically valid queue ID.
- `delivered_but_unreconciled`: a noncharging CourtListener queue/document check established delivery, but authoritative PACER billing evidence has not been imported.
- `confirmed`: protected PACER billing evidence established the authoritative fee and the hold was replaced by that fee.
- `failed`: protected evidence established a definite failure or no-charge outcome and the hold was released, or the operation failed before any provider request.
- `unknown`: the paid request may have reached CourtListener but no valid queue ID or authoritative no-charge evidence is available.

Receipt lookup for `queued` operations performs at most one noncharging CourtListener status refresh in that HTTP request. A successful delivery result advances the operation to `delivered_but_unreconciled`. A transient status-refresh failure leaves the state unchanged. A scheduled broker poller may perform the same noncharging refresh with bounded retries, but neither path may repeat the paid POST.

Any timeout, transport error, redirect, malformed success body, missing queue ID, or non-success CourtListener response after the paid request begins is conservatively stored as `unknown`. It returns a sanitized broker error and retains the full hold. `failed` must not be inferred merely from a provider HTTP status unless a later reviewed contract version identifies that response as authoritative no-charge evidence.

## Submission response and errors

A newly queued operation returns HTTP `201` and exactly this JSON object with no additional fields:

```json
{ "reservation_id": "<durable broker reservation ID>", "id": "<CourtListener queue ID>" }
```

An idempotent replay with a known queue ID returns the same object with HTTP `200`. Both values are nonempty strings.

Every non-success response is `application/json` with exactly this shape:

```json
{ "error": { "code": "invalid_request", "message": "sanitized nonsecret description" } }
```

The broker uses these status and code mappings:

| HTTP | Code | Meaning |
| --- | --- | --- |
| `400` | `invalid_request` | JSON, field set, identifier, digest, UUID, or money syntax is invalid. |
| `401` | `machine_auth_required` | Signed machine authentication is missing, stale, replayed, expired, or invalid. |
| `403` | `source_not_allowed` | The signed identity arrived outside its approved source path. |
| `403` | `document_not_allowed` | The active reviewed allowlist does not contain the document. |
| `409` | `policy_not_active` | The cycle or policy digest is not the active reviewed policy. |
| `409` | `reservation_mismatch` | The canonical caller reservation differs from the reviewed policy reservation. |
| `409` | `cycle_cap_exceeded` | The atomic reservation would exceed the cycle cap. |
| `409` | `case_cap_exceeded` | The atomic reservation would exceed the server-derived case cap. |
| `409` | `operation_key_conflict` | The operation key already exists with a different request digest. |
| `409` | `operation_outcome_pending` | An identical replay has no known queue ID and must be inspected through receipts. |
| `404` | `receipt_not_found` | The authenticated receipt lookup does not identify an operation. |
| `409` | `operation_failed` | Protected reconciliation established a no-queue terminal failure. |
| `500` | `client_code_collision` | The deterministic client code conflicts with a different operation. |
| `502` | `provider_outcome_unknown` | The provider returned an unusable or non-success response after submission began. |
| `504` | `provider_outcome_unknown` | A provider timeout or transport failure left the paid outcome ambiguous. |
| `503` | `broker_unavailable` | The broker failed before any provider request and made no reservation or submission. |

Messages must not reproduce provider response bodies or secret-bearing exception text. An HTTP error from the broker after `submitted` is not proof that no provider charge occurred.

## Receipt API

The receipt endpoint is `POST /v1/receipts/{operation_key}` with an empty request body and `x-secure-gate-action: recap-fetch-receipt`. It uses the same dedicated purchase identity and source restrictions. The path operation key is a canonical lowercase UUIDv4.

An existing operation returns HTTP `200` with exactly these fields; nullable fields are present as JSON `null` rather than omitted:

```json
{
  "version": "courtlistener-recap-fetch-receipt-v1",
  "operation_key": "00000000-0000-4000-8000-000000000000",
  "reservation_id": "reservation-1",
  "cycle_id": "cycle-1",
  "purchase_policy_sha256": "<64 lowercase hex characters>",
  "recap_document": "123",
  "case_id": "candidate-123",
  "client_code": "lfb-abcdefghijklmnopqrstuvwxyz",
  "id": "77",
  "state": "delivered_but_unreconciled",
  "reservation_usd": "3.05",
  "held_usd": "3.05",
  "authoritative_fee_usd": null,
  "provider_response_sha256": "<64 lowercase hex characters or null>",
  "submitted_at": "2026-07-13T20:00:00.000Z",
  "updated_at": "2026-07-13T20:01:00.000Z",
  "delivered_at": "2026-07-13T20:01:00.000Z",
  "reconciled_at": null,
  "billing_evidence": null
}
```

`id` is the CourtListener queue ID and is null until known. `held_usd` is the amount currently counted against the caps. `authoritative_fee_usd` is null until protected billing reconciliation. `delivered_at` and `reconciled_at` are independently nullable.

After reconciliation, `billing_evidence` is exactly:

```json
{
  "kind": "pacer_detailed_transactions",
  "statement_period": "2026-07",
  "evidence_sha256": "<64 lowercase hex characters>",
  "evidence_ref": "<opaque nonsecret audit reference>",
  "imported_at": "2026-08-10T15:00:00.000Z"
}
```

`kind` is either `pacer_detailed_transactions` or `pacer_quarterly_invoice`. The receipt never contains the imported statement, PACER account data, credentials, or unrelated transactions. A missing operation returns `404 receipt_not_found` using the standard error shape.

## Authoritative billing reconciliation

CourtListener queue delivery is not authoritative billing evidence. The authoritative sources are PACER Manage My Account's Usage -> View Detailed Transactions export and the quarterly PACER invoice or statement. Prior-month detailed transactions may not be complete until after the tenth of the following month, and the quarterly invoice is the final billing record.

There is no automated PACER billing API in this contract. A human obtains the source record, stores it in protected custody, and initiates a reviewed control-plane import. The import supplies only a normalized reconciliation manifest plus the source file's SHA-256 digest and an opaque nonsecret evidence reference to the Worker. The raw source record and unrelated transactions are not exposed to the purchase identity or stored in receipts.

The protected import endpoint is `POST /v1/admin/reconciliations` with `Content-Type: application/json` and `x-secure-gate-action: recap-fetch-reconciliation-import`. It rejects the purchase identity even if that identity supplies an otherwise valid signature. Only the dedicated protected control-plane identity may call it.

The import body contains exactly this logical schema:

```json
{
  "version": "courtlistener-recap-fetch-reconciliation-v1",
  "kind": "pacer_detailed_transactions",
  "statement_period": "2026-07",
  "evidence_sha256": "<64 lowercase hex characters>",
  "evidence_ref": "<opaque nonsecret audit reference>",
  "entries": [
    {
      "client_code": "lfb-abcdefghijklmnopqrstuvwxyz",
      "outcome": "charged",
      "authoritative_fee_usd": "0.10"
    }
  ]
}
```

`kind` is `pacer_detailed_transactions` or `pacer_quarterly_invoice`; `outcome` is `charged` or `no_charge`. A `charged` entry requires a positive canonical fee. A `no_charge` entry requires `authoritative_fee_usd` to be `0.00`. Client codes must be unique within the manifest, every client code must resolve to one operation, and the evidence digest and reference must not have been imported with different contents.

A successful import returns HTTP `200` and exactly `{ "import_id": "<durable import ID>", "applied": <integer>, "unchanged": <integer> }`. A byte-equivalent replay returns the original response with HTTP `200`. Reuse of an evidence digest or evidence reference with different contents returns `409 reconciliation_conflict`. Invalid or unmatched entries make the entire import fail atomically with `400 invalid_reconciliation`; partial application is forbidden.

The protected importer correlates each charge to the persisted `client_code`, validates the operation and statement period, and records an append-only reconciliation event. A Detailed Transactions match may replace the full hold with the authoritative fee and set `confirmed`. A documented no-charge result may release the hold and set `failed`. An unmatched, ambiguous, incomplete, or conflicting record leaves the full hold and current state unchanged.

A later quarterly invoice controls over an earlier Detailed Transactions import if they conflict. Corrections are append-only: retain both evidence digests and events, update the authoritative fee and hold from the later final record, and never delete or rewrite the earlier evidence history.

For `submitted`, `queued`, `unknown`, and `delivered_but_unreconciled`, `held_usd` remains the full reservation. The broker may release a hold or replace it with an authoritative fee only through the protected reconciliation path. Disabling a policy, receiving a local download, observing CourtListener delivery, aging an operation, or receiving an operator assertion without protected source evidence cannot release it.

There is no public HTTP policy-activation endpoint in v1. Policy and document-to-case activation occurs only through the reviewed deployment/migration path described above, before the purchase route is enabled.

## Audit and retention

Every accepted request, idempotent replay, rejection, provider transition, receipt refresh, policy activation, and reconciliation import produces a structured, nonsecret audit event. Provider response hashes are computed from a canonical redacted representation that excludes headers, credentials, form fields, and raw response bodies.

Operation rows, client-code mappings, policy artifacts, nonce/replay evidence, state transitions, and reconciliation events are retained for the benchmark cycle's audit lifetime. No artifact destined for LegalForecastBench packets may contain PACER account information, credentials, raw billing records, or sealed/private material.

## Local command behavior

Offline execution requires both `--courtlistener-fixture` and `--purchase-broker-fixture`. `--live-purchase` continues to fail before any journal submission or provider request until the dedicated Worker is deployed, the reviewed policy and document-to-case allowlist are active, the production signed HTTP adapter is configured, and the nonpurchase end-to-end gates pass. Adding raw PACER environment variables to LegalForecastBench is not an acceptable substitute.
