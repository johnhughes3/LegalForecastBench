# CourtListener RECAP Fetch purchase broker v1

LegalForecastBench must not receive or store raw PACER credentials. PACER does not provide a hard account-wide spend cap, so an agent-readable username and password would let a compromised development host bypass the repository's SQLite journal and frozen budget policy.

The `acquisition purchase-missing-recap-fetch` adapter therefore supports offline fixtures but deliberately fails closed for production purchases until the dedicated `secure-gate-recap-fetch-broker` Worker implements and deploys this contract. Direct CourtListener document verification and local queue polling use `COURTLISTENER_API_TOKEN`; the charge-bearing POST and all PACER credentials remain inside the broker boundary.

## Service boundary

The production broker is a dedicated Worker on `https://secure-gate-recap-fetch.johnjhughes.com` with its own D1 database. It must not share a runtime with secure-gate Broker/Admin and must not receive GitHub App, deployment-approval, sudo, workflow, browser-session, or general secure-gate machine-grant authority.

The LegalForecastBench client receives a dedicated, expiring P-256 machine identity that is recognized only by this Worker. Requests use the dedicated signature domain defined below, a single-use nonce, and the approved Tailscale App Connector source path. Ordinary secure-gate machine grants and keys are not valid broker identities.

The purchase identity may invoke only the submission and receipt routes below. Policy activation and billing reconciliation use a separate protected control-plane identity and are never authorized by the purchase identity.

Every authenticated request carries `x-secure-gate-machine-id`, `x-secure-gate-machine-timestamp`, `x-secure-gate-machine-nonce`, `x-secure-gate-machine-signature`, `x-secure-gate-action`, and `x-secure-gate-identity-policy-sha256`. The timestamp is 13-digit Unix epoch milliseconds, may be at most 60 seconds in the future, and expires five minutes after issuance. The nonce is 22 to 128 unpadded base64url characters and is consumed atomically. The identity-policy digest is exactly 64 lowercase hexadecimal characters.

This dedicated broker does not reuse the general secure-gate signature domain. Its P-256/SHA-256 signature input is exactly these nine UTF-8 fields joined in order by one newline character, with no trailing newline:

1. `SECURE-GATE-RECAP-FETCH-V1`;
2. the uppercase HTTP method;
3. the exact path and query string sent on the wire;
4. the lowercase SHA-256 of the exact request body bytes;
5. the 13-digit timestamp;
6. the nonce;
7. the machine ID;
8. the exact `x-secure-gate-action` value; and
9. the `x-secure-gate-identity-policy-sha256` value.

The broker identity row stores the same identity-policy digest together with the identity's exact `tailscale_node_id` and `allowed_source_ips_json`. Authentication requires the request digest and source to match that identity-specific policy; no global or cross-identity source allowlist may authorize the request. The broker consumes the nonce only after the signature, action, identity-policy digest, and source binding validate.

The signing key is an EC private JWK containing exactly `kty`, `crv`, `x`, `y`, and `d`, with `kty: "EC"` and `crv: "P-256"`. Each coordinate and the private scalar is an unpadded base64url encoding of exactly 32 bytes; the client rejects extra JWK fields and rejects a public point that does not correspond to `d`. `x-secure-gate-machine-signature` is the unpadded base64url encoding of the 64-byte IEEE P1363 form `r || s`, where each P-256 ECDSA integer is unsigned big-endian and left-padded to exactly 32 bytes. DER-encoded ECDSA signatures are not accepted on the wire.

The client also receives the full reviewed identity-policy JSON and recomputes its digest before signing. Its canonical UTF-8 bytes have this exact field order, compact JSON encoding, and no trailing newline:

```json
{"version":"recap-fetch-identity-policy-v1","machine_id":"machine-1","public_key_sha256":"<64 lowercase hex>","tailscale_node_id":"node-id","allowed_source_ips":["192.0.2.1"],"activated_at":"2026-07-13T20:00:00.000Z","expires_at":"2026-07-14T20:00:00.000Z"}
```

`public_key_sha256` is SHA-256 of the UTF-8 bytes of the private JWK's public portion serialized exactly as `{"crv":"P-256","kty":"EC","x":"<unpadded 32-byte base64url>","y":"<unpadded 32-byte base64url>"}`. The policy has exactly the seven fields shown. `machine_id` equals the configured signing identity. `tailscale_node_id` is nonempty. `allowed_source_ips` contains nonempty reviewed exact `cf-connecting-ip` strings with no leading or trailing whitespace or control characters, no duplicates, and Unicode-code-point sort order; neither client nor broker performs DNS or CIDR expansion. Both timestamps are semantically valid UTC RFC 3339 with exactly milliseconds, expiry is later than activation, and lifetime is at most 24 hours. The client requires the recomputed public-key digest to equal `public_key_sha256` and the recomputed policy digest to equal both the configured digest and the signed header. The broker independently recomputes the same digest and requires computed, stored, and signed values to agree.

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

The exact request bytes are canonical UTF-8 JSON with the fields in the order listed above, no insignificant whitespace, no escaping of `/`, and no trailing newline. JSON escapes only quotation mark, reverse solidus, and required control characters; all other Unicode characters are emitted directly as UTF-8 rather than `\u` escapes. For example:

```json
{"request_type":"2","recap_document":"123","cycle_id":"cycle-1","purchase_policy_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","operation_key":"00000000-0000-4000-8000-000000000000","reservation_usd":"3.05"}
```

The body SHA-256 in the signature and the stored request digest are computed over those exact bytes. A semantically equivalent JSON object with different field order or whitespace is not canonical and returns `400 invalid_request`.

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

All USD fields use the canonical two-decimal representation defined above. `opening_case_committed_spend_usd` maps nonempty case IDs to canonical amounts already committed before activation. Every key must occur as a `case_id` in `allowed_documents`, every value must be less than or equal to `per_case_cap_usd`, and the sum must equal `opening_committed_spend_usd`. An allowlisted case omitted from the map has zero opening case commitment. Unattributed opening spend is forbidden because it could evade the per-case cap. LegalForecastBench freezes the same mapping inside the purchase-policy artifact whose digest is `purchase_policy_sha256`; activation rejects any mapping that does not exactly equal that commitment.

The activation process must validate that document IDs are unique, every document maps to exactly one nonempty case ID, all amounts are nonnegative, the reservation and per-case cap are positive, the per-case cap does not exceed the cycle cap, opening committed spend does not exceed the cycle cap, and the opening per-case mapping satisfies the equality, membership, per-case, and sum constraints above. The broker stores the reviewed artifact's SHA-256 digest and activation evidence reference in addition to the LegalForecastBench `purchase_policy_sha256`.

Activation is append-only. A cycle ID or purchase-policy digest may not be overwritten, and at most one policy may accept new submissions for a cycle. Changes require a new reviewed artifact and policy identity; disabling a policy prevents new reservations but does not release existing holds.

The broker derives `case_id` exclusively from the reviewed `recap_document` allowlist. This server-side mapping, not caller input, is the authority for the per-case cap.

## Atomic reservation and idempotency

Before any provider request, one D1 transaction must either insert the operation in `submitted` with its full hold or make no change. The transaction validates the identity, active cycle, exact policy digest, exact reservation, document allowlist, cycle cap, and server-derived per-case cap.

For cap calculations, committed spend is the policy's opening committed spend plus every operation's current hold or reconciled authoritative fee. The new reservation is permitted only when both of these are true:

- cycle committed cents plus reservation cents is less than or equal to the cycle cap cents;
- the server-derived case's committed cents plus reservation cents is less than or equal to the per-case cap cents.

`operation_key` is the idempotency key and primary operation identity. The broker stores the originating authenticated `machine_id` and a SHA-256 digest of the canonical six-field request. A replay from a different machine identity, or a replay from the owning identity with a different request digest, returns `409 operation_key_conflict` and never calls CourtListener. A byte-equivalent replay from the owning identity never calls CourtListener and behaves as follows:

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
- `Authorization: Token <broker-custodied COURTLISTENER_API_TOKEN>`;
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

A syntactically valid provider success contains an `id` that canonicalizes to a positive base-10 decimal string matching `^[1-9][0-9]*$`. A JSON string must already be canonical. A JSON number is accepted only when it is a safe positive integer and is then canonicalized to its decimal string; zero, negative, fractional, exponent-ambiguous, boolean, or unsafe numeric values are invalid.

Whenever the provider fetch returns an HTTP response, the broker commits the exact raw response-body bytes before parsing them, regardless of status or validity. `provider_response_body_sha256` is SHA-256 of those exact bytes for success, non-success, and malformed bodies alike, including the hash of empty bytes for an empty body. It is null only when no HTTP response bytes were received. For every HTTP response, `provider_response_sha256` commits to compact canonical UTF-8 JSON in the exact field order `status`, `id`: `{"status":<integer>,"id":"<canonical positive decimal>"}` for a valid queue ID and `{"status":<integer>,"id":null}` otherwise. Thus raw-byte and redacted commitments are present together for every HTTP outcome, while a timeout or transport failure before any response leaves both null. No response commitment contains headers, credentials, request form fields, or raw response bytes.

A definite exception before the provider fetch function is invoked transitions the operation to `failed` and releases the hold. Once fetch invocation begins, every timeout, transport error, redirect, malformed success body, invalid or missing queue ID, non-success CourtListener response, persistence error, or Worker exception is conservatively stored as `unknown` and retains the full hold. `failed` must not be inferred from a provider HTTP status. The broker durably records a provider-attempt marker before dispatch and, after a syntactically valid response, a separately durable queue-receipt commitment before attempting the normal operation-row transition. This lets receipt recovery repair a failed D1 transition without repeating the paid POST.

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
| `503` | `broker_unavailable` | A definite broker failure occurred before provider fetch invocation; any inserted operation is `failed` and its hold is released. |

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
  "provider_response_body_sha256": "<64 lowercase hex characters or null>",
  "provider_response_sha256": "<64 lowercase hex characters or null>",
  "submitted_at": "2026-07-13T20:00:00.000Z",
  "updated_at": "2026-07-13T20:01:00.000Z",
  "delivered_at": "2026-07-13T20:01:00.000Z",
  "reconciled_at": null,
  "billing_evidence": null
}
```

`id` is the canonical positive-decimal CourtListener queue ID and is null until known, including when billing evidence arrives before queue recovery. `held_usd` is the amount currently counted against the caps. `authoritative_fee_usd` is null until protected billing reconciliation, a positive canonical amount for a reconciled charge, and exactly `0.00` for a reconciled no-charge failure. A charged `confirmed` receipt has `held_usd` exactly equal to `authoritative_fee_usd`; zero hold is valid only for an authoritative no-charge `failed` receipt. `delivered_at` and `reconciled_at` are independently nullable, and `confirmed` does not imply that the queue ID or delivery timestamp is already known.

The receipt also contains nullable `provider_response_body_sha256` immediately before `provider_response_sha256`. The raw-body and redacted commitments follow the all-outcomes rules above. Both fields are exactly 64 lowercase hexadecimal characters when present, and either both are present for an HTTP response or both are null when no HTTP response was received.

The receipt operation is machine-owned. A different authenticated machine receives `404 receipt_not_found`, even when the operation key exists, to prevent cross-identity enumeration. When the owning identity requests a receipt for `submitted`, `unknown`, or `failed` with no queue ID, the broker may perform at most one recovery traversal beginning at the fixed noncharging URL `https://www.courtlistener.com/api/rest/v4/recap-fetch/?client_code=<percent-encoded persisted client code>`. Each page must be a JSON object with a `results` array and an explicit DRF `next` field. Recovery follows at most 100 pages, permits continuation URLs only on the same HTTPS origin and exact `/api/rest/v4/recap-fetch/` path, rejects a repeated continuation URL, and treats only `next: null` as proven exhaustion. Exactly one result across the exhausted result set must have the exact persisted client code; zero or multiple matches leave the operation unchanged. A unique match with a valid queue ID may durably repair the queue ID and receipt commitments. A missing or malformed `next`, a nonnull `next` on page 100, an off-origin or wrong-path continuation, absence, ambiguity, or any lookup failure leaves the full hold and current state unchanged. This recovery path never repeats the paid POST.

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

The receipt intentionally contains neither a download URL nor fee components. `authoritative_fee_usd` is the total PACER fee established by the protected billing source. LegalForecastBench obtains the delivered file URL only through its existing noncharging queue and document lookups, validates that URL against the CourtListener/storage allowlist, and converts the authoritative total to the local journal's componentized fee object as PACER fee equal to the authoritative total, service fee `0.00`, and total equal to the authoritative total.

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

`statement_period` syntax depends on `kind`: Detailed Transactions requires an actual calendar month in exact `YYYY-MM` form; a quarterly invoice requires exact `YYYY-Q[1-4]`. The quarterly period covers its three corresponding calendar months.

A successful import returns HTTP `200` and exactly `{ "import_id": "<durable import ID>", "applied": <integer>, "unchanged": <integer> }`. An exact manifest replay with the same canonical manifest digest, evidence SHA-256, evidence reference, and canonical content returns the original response with HTTP `200`. Reuse of an evidence digest or evidence reference with different canonical content returns `409 reconciliation_conflict` and changes nothing. Invalid or unmatched entries make the entire import fail atomically with `400 invalid_reconciliation`; partial application is forbidden.

The protected importer correlates each charge to the persisted `client_code`, validates the operation and statement period, and records an append-only reconciliation event. A Detailed Transactions match may replace the full hold with the authoritative fee and set `confirmed`. A documented no-charge result may release the hold and set `failed`. An unmatched, ambiguous, incomplete, or conflicting record leaves the full hold and current state unchanged.

Precedence is deterministic per operation and covered period, independent of cross-kind arrival order:

- Before any covering quarterly invoice, the latest successfully imported Detailed Transactions entry for the same operation and month controls. A later Detailed Transactions entry is an append-only correction; if its outcome or fee differs, it updates the authoritative result, and if it is identical it is retained but counted as unchanged.
- A quarterly invoice entry dominates every Detailed Transactions entry for its operation and any month covered by that quarter, even when the invoice was imported first and even when outcome and fee are identical. The first successfully imported covering invoice is applied because it changes the controlling evidence source. Detailed Transactions evidence imported after a covering invoice is retained as an append-only event but cannot change the authoritative fee, hold, or state and is counted as unchanged.
- A later successfully imported quarterly invoice entry for the same operation and quarter is an append-only correction to the earlier invoice. The latest invoice controls; an identical later entry is retained but counted as unchanged.

No evidence or event is deleted or rewritten. Imports and corrections use a single deterministic database ordering assigned by the successful atomic import, never an untrusted timestamp from the manifest.

For `submitted`, `queued`, `unknown`, and `delivered_but_unreconciled`, `held_usd` remains the full reservation. For a charged `confirmed` operation, `held_usd` equals the authoritative fee and continues to count against both caps. Only an authoritative no-charge result sets `held_usd` to zero and state to `failed`. The broker may release a hold or replace it with an authoritative fee only through the protected reconciliation path. Disabling a policy, receiving a local download, observing CourtListener delivery, aging an operation, or receiving an operator assertion without protected source evidence cannot release it.

There is no public HTTP policy-activation endpoint in v1. Policy and document-to-case activation occurs only through the reviewed deployment/migration path described above, before the purchase route is enabled.

## Audit and retention

Every accepted request, idempotent replay, rejection, provider transition, receipt refresh, policy activation, and reconciliation import produces a structured, nonsecret audit event. Provider response hashes are computed from a canonical redacted representation that excludes headers, credentials, form fields, and raw response bodies.

Operation rows, client-code mappings, policy artifacts, nonce/replay evidence, state transitions, and reconciliation events are retained for the benchmark cycle's audit lifetime. No artifact destined for LegalForecastBench packets may contain PACER account information, credentials, raw billing records, or sealed/private material.

## Local command behavior

Offline execution requires both `--courtlistener-fixture` and `--purchase-broker-fixture`. `--live-purchase` continues to fail before any journal submission or provider request until the dedicated Worker is deployed, the reviewed policy and document-to-case allowlist are active, the production signed HTTP adapter is configured, and the nonpurchase end-to-end gates pass. Adding raw PACER environment variables to LegalForecastBench is not an acceptable substitute.

The production adapter accepts only the stage-scoped broker URL, machine ID, P-256 private signing JWK, full canonical identity-policy JSON, and identity-policy SHA-256, plus the existing CourtListener token used for noncharging lookups. It has no PACER credential fields or environment variables. Merely configuring those values does not enable `--live-purchase`; deployment activation and a nonpurchase end-to-end proof remain separate fail-closed gates.

The adapter validates the exact receipt schema and binds `operation_key`, `cycle_id`, `purchase_policy_sha256`, `recap_document`, `reservation_usd`, and any queue ID to the local journal before using it. It durably stores every valid machine-owned receipt, including a broker-originated local `failed` row and a `confirmed` receipt whose queue ID or delivery timestamp is still null. A billing receipt alone never proves delivery. For a `confirmed` charged receipt, LegalForecastBench must also obtain a nonnull queue ID, queue status `2`, and an available matching document through noncharging CourtListener lookups, then validate the download URL. Only then does it construct this exact six-field journal reconciliation record:

```json
{
  "source_document_id": "123",
  "disposition": "confirmed",
  "source_type": "statement_export",
  "source_reference": "recap-fetch-broker:00000000-0000-4000-8000-000000000000:<billing-evidence-sha256>",
  "pacer_fees": {
    "pacerFee": "0.10",
    "serviceFee": "0.00",
    "total": "0.10"
  },
  "download_url": "https://storage.courtlistener.com/123.pdf"
}
```

The source reference uses the literal prefix `recap-fetch-broker:`, the canonical operation key, one colon, and the billing evidence SHA-256. Before applying the six-field record, LegalForecastBench durably stores the entire validated nonsecret broker receipt in the operation's local provider evidence. For a protected `no_charge` receipt in state `failed`, the same transformation uses `disposition: "failed"`, the same source type/reference construction, and JSON null for both `pacer_fees` and `download_url`; the stored broker receipt preserves its reservation and held-spend audit facts. Any other state, missing billing evidence, missing authoritative fee, mismatched identity, non-success queue status, unavailable document, or invalid URL produces no reconciliation record and leaves the local full reservation in place.
