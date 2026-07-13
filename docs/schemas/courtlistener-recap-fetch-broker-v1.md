# CourtListener RECAP Fetch purchase broker v1

LegalForecastBench must not receive or store raw PACER credentials. PACER does not provide a hard account-wide spend cap, so an agent-readable username and password would let a compromised development host bypass the repository's SQLite journal and frozen budget policy.

The `acquisition purchase-missing-recap-fetch` adapter therefore supports offline fixtures but deliberately fails closed for production purchases until a separate budget-enforcing credential broker implements this contract. Direct CourtListener document verification and queue polling use `COURTLISTENER_API_TOKEN`; the charge-bearing POST crosses the broker boundary.

## Submission request

The client submits one authenticated request to the broker with exactly these string fields:

- `request_type`: always `2`, CourtListener's individual-document RECAP Fetch request type.
- `recap_document`: the noncharging-verified CourtListener RECAP document ID.
- `cycle_id`: the immutable purchase-policy cycle ID.
- `purchase_policy_sha256`: the immutable policy digest.
- `operation_key`: the journal-generated unique key durably committed before submission.
- `reservation_usd`: the verified worst-case per-document reservation.

The request never contains a PACER username, PACER password, PACER client code, or CourtListener token.

The broker must not trust caller-supplied caps. Before enabling a cycle, an out-of-band reviewed deployment must register the immutable policy digest, cycle cap, per-case cap, document reservation, and opening committed spend. The broker must atomically reserve against that server-side policy before any provider POST.

## Broker requirements

- Authenticate a narrowly scoped, short-lived machine identity that can invoke only this purchase operation and read its receipts.
- Make `operation_key` idempotent. Replays return the original receipt and never issue a second provider POST.
- Persist `submitted` before the provider call, then `queued`, `confirmed`, `failed`, or `unknown` with timestamps and response hashes.
- Issue exactly one CourtListener `POST /api/rest/v4/recap-fetch/` with form-encoded `request_type=2`, `recap_document`, and broker-custodied PACER credentials. The paid POST has zero automatic retries.
- Disable redirects on the credential-bearing provider request and never include credentials in logs, errors, traces, or receipts.
- Retain the full reservation for submitted, queued, unknown, and delivered-but-unreconciled operations. Release or replace it only from authoritative provider billing evidence.
- Reject any document or policy identity not present in the reviewed allowlist and any request that would exceed the server-side cycle or per-case cap.

## Submission receipt

A successful submission returns:

- `reservation_id`: the broker's durable reservation identifier.
- `id`: the CourtListener RECAP Fetch queue ID.

An ambiguous broker response is an unknown paid outcome. The local journal will not resubmit it; an operator must reconcile it using the broker receipt API.

The receipt API must expose the operation key, reservation ID, queue ID if known, state, authoritative fee when known, provider-response hash, and nonsecret evidence reference. It must never expose PACER credentials. Once authoritative fees are available, their evidence can drive the existing purchase-journal reconciliation path.

## Local command behavior

Offline execution requires both `--courtlistener-fixture` and `--purchase-broker-fixture`. `--live-purchase` currently fails before any journal submission or provider request. Enabling it requires a separately reviewed broker implementation and deployment; adding raw PACER environment variables is not an acceptable substitute.
