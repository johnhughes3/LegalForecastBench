from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from legalforecast.ingestion.recap_fetch_broker import (
    BrokerDefiniteRejection,
    BrokerOutcomeUnknown,
    BrokerRawResponse,
    RecapFetchBrokerConfig,
    SignedRecapFetchPurchaseBroker,
    broker_reconciliation_record,
    canonical_provider_response_commitment_bytes,
    canonical_signature_payload_bytes,
    canonical_submission_bytes,
    parse_canonical_submission_bytes,
    validate_broker_receipt,
)


class _Transport:
    def __init__(self, *responses: BrokerRawResponse) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, bytes, dict[str, str]]] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> BrokerRawResponse:
        del timeout_seconds
        self.requests.append((method, url, body, dict(headers)))
        return self.responses.pop(0)


def test_signs_exact_canonical_six_field_submission_and_nine_field_domain() -> None:
    transport = _Transport(
        BrokerRawResponse(
            201,
            b'{"reservation_id":"reservation-1","id":"77"}',
            {"content-type": "application/json; charset=utf-8"},
        )
    )
    key, jwk = _key()
    broker = SignedRecapFetchPurchaseBroker(
        _config(jwk),
        transport=transport,
        clock_ms=lambda: 1_721_073_600_123,
        nonce=lambda: "abcdefghijklmnopqrstuv",
    )
    request = _request(cycle_id="cycle-é")

    assert broker.submit(request) == {"reservation_id": "reservation-1", "id": "77"}
    method, url, body, headers = transport.requests[0]
    assert method == "POST"
    assert url == "https://secure-gate-recap-fetch.johnjhughes.com/v1/recap-fetch"
    assert body == (
        b'{"request_type":"2","recap_document":"123","cycle_id":"cycle-'
        + "é".encode()
        + b'","purchase_policy_sha256":"'
        + b"a" * 64
        + b'","operation_key":"00000000-0000-4000-8000-000000000000",'
        b'"reservation_usd":"3.05"}'
    )
    assert headers["x-secure-gate-action"] == "recap-fetch-submit"
    assert (
        headers["x-secure-gate-identity-policy-sha256"]
        == broker.config.identity_policy_sha256
    )
    expected_payload = "\n".join(
        (
            "SECURE-GATE-RECAP-FETCH-V1",
            "POST",
            "/v1/recap-fetch",
            hashlib.sha256(body).hexdigest(),
            "1721073600123",
            "abcdefghijklmnopqrstuv",
            "machine-1",
            "recap-fetch-submit",
            broker.config.identity_policy_sha256,
        )
    ).encode()
    signature = _decode(headers["x-secure-gate-machine-signature"])
    assert len(signature) == 64
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    key.public_key().verify(
        encode_dss_signature(r, s), expected_payload, ec.ECDSA(hashes.SHA256())
    )


def test_local_signing_validation_does_not_count_or_dispatch_paid_request() -> None:
    transport = _Transport()
    _, jwk = _key()
    broker = SignedRecapFetchPurchaseBroker(
        _config(jwk),
        transport=transport,
        nonce=lambda: "invalid nonce",
    )

    with pytest.raises(ValueError, match="timestamp or nonce"):
        broker.submit(_request())

    assert broker.paid_dispatch_count == 0
    assert transport.requests == []


def test_receipt_signs_empty_body_and_validates_exact_schema() -> None:
    receipt = _receipt()
    transport = _Transport(
        BrokerRawResponse(
            200,
            json.dumps(receipt, separators=(",", ":")).encode(),
            {"content-type": "application/json"},
        )
    )
    _, jwk = _key()
    broker = SignedRecapFetchPurchaseBroker(
        _config(jwk),
        transport=transport,
        clock_ms=lambda: 1_721_073_600_123,
        nonce=lambda: "abcdefghijklmnopqrstuv",
    )
    assert broker.receipt(receipt["operation_key"]) == receipt
    _, url, body, headers = transport.requests[0]
    assert url.endswith("/v1/receipts/00000000-0000-4000-8000-000000000000")
    assert body == b""
    assert headers["x-secure-gate-action"] == "recap-fetch-receipt"


@pytest.mark.parametrize("bad_id", ["0", "01", "-1", 77, True, "1.0"])
def test_submission_rejects_noncanonical_queue_ids(bad_id: object) -> None:
    transport = _Transport(
        BrokerRawResponse(
            201,
            json.dumps({"reservation_id": "r", "id": bad_id}).encode(),
            {"content-type": "application/json"},
        )
    )
    _, jwk = _key()
    with pytest.raises(BrokerOutcomeUnknown):
        SignedRecapFetchPurchaseBroker(_config(jwk), transport=transport).submit(
            _request()
        )


@pytest.mark.parametrize(
    ("status", "code", "definite"),
    [
        (409, "case_cap_exceeded", True),
        (503, "broker_unavailable", True),
        (409, "operation_outcome_pending", False),
        (504, "provider_outcome_unknown", False),
    ],
)
def test_error_mapping_distinguishes_definite_from_ambiguous(
    status: int, code: str, definite: bool
) -> None:
    transport = _Transport(
        BrokerRawResponse(
            status,
            json.dumps({"error": {"code": code, "message": "safe"}}).encode(),
            {"content-type": "application/json"},
        )
    )
    _, jwk = _key()
    expected = BrokerDefiniteRejection if definite else BrokerOutcomeUnknown
    with pytest.raises(expected):
        SignedRecapFetchPurchaseBroker(_config(jwk), transport=transport).submit(
            _request()
        )


def test_reconciliation_uses_exact_existing_six_field_schema() -> None:
    receipt = _receipt(
        state="confirmed",
        held_usd="1.20",
        authoritative_fee_usd="1.20",
        delivered_at="2026-07-13T20:01:00.000Z",
        reconciled_at="2026-07-13T20:02:00.000Z",
        billing_evidence={
            "kind": "pacer_detailed_transactions",
            "statement_period": "2026-07",
            "evidence_sha256": "c" * 64,
            "evidence_ref": "statement-1",
            "imported_at": "2026-07-13T20:02:00.000Z",
        },
    )
    assert broker_reconciliation_record(
        receipt, download_url="https://storage.courtlistener.com/123.pdf"
    ) == {
        "source_document_id": "123",
        "disposition": "confirmed",
        "source_type": "statement_export",
        "source_reference": "recap-fetch-broker:00000000-0000-4000-8000-000000000000:"
        + "c" * 64,
        "pacer_fees": {"pacerFee": "1.20", "serviceFee": "0.00", "total": "1.20"},
        "download_url": "https://storage.courtlistener.com/123.pdf",
    }


def test_confirmed_receipt_requires_authoritative_fee_to_remain_held() -> None:
    receipt = _receipt(
        state="confirmed",
        held_usd="1.20",
        authoritative_fee_usd="1.20",
        delivered_at="2026-07-13T20:01:00.000Z",
        reconciled_at="2026-07-13T20:02:00.000Z",
        billing_evidence={
            "kind": "pacer_detailed_transactions",
            "statement_period": "2026-07",
            "evidence_sha256": "c" * 64,
            "evidence_ref": "statement-1",
            "imported_at": "2026-07-13T20:02:00.000Z",
        },
    )
    assert broker_reconciliation_record(
        receipt, download_url="https://storage.courtlistener.com/123.pdf"
    )["pacer_fees"] == {
        "pacerFee": "1.20",
        "serviceFee": "0.00",
        "total": "1.20",
    }
    with pytest.raises(BrokerOutcomeUnknown, match="confirmed broker receipt"):
        broker_reconciliation_record(
            {**receipt, "held_usd": "0.00"},
            download_url="https://storage.courtlistener.com/123.pdf",
        )


def test_confirmed_receipt_may_precede_queue_and_delivery_recovery() -> None:
    receipt = _receipt(
        id=None,
        state="confirmed",
        held_usd="1.20",
        authoritative_fee_usd="1.20",
        delivered_at=None,
        reconciled_at="2026-07-13T20:02:00.000Z",
        provider_response_body_sha256=None,
        provider_response_sha256=None,
        billing_evidence={
            "kind": "pacer_detailed_transactions",
            "statement_period": "2026-07",
            "evidence_sha256": "c" * 64,
            "evidence_ref": "statement-1",
            "imported_at": "2026-07-13T20:02:00.000Z",
        },
    )

    assert validate_broker_receipt(receipt) == receipt
    with pytest.raises(BrokerOutcomeUnknown, match="queue ID"):
        broker_reconciliation_record(
            receipt, download_url="https://storage.courtlistener.com/123.pdf"
        )


@pytest.mark.parametrize(
    ("body_hash", "redacted_hash"),
    [("e" * 64, None), (None, "f" * 64)],
)
def test_provider_response_commitments_are_present_as_a_pair(
    body_hash: str | None, redacted_hash: str | None
) -> None:
    with pytest.raises(BrokerOutcomeUnknown, match="response commitment"):
        validate_broker_receipt(
            _receipt(
                provider_response_body_sha256=body_hash,
                provider_response_sha256=redacted_hash,
            )
        )


def test_provider_response_commitment_uses_exact_versioned_canonical_schema() -> None:
    body_sha256 = "d" * 64
    assert canonical_provider_response_commitment_bytes(
        outcome="accepted",
        http_status=201,
        queue_id="77",
        body_sha256=body_sha256,
    ) == (
        b'{"version":"courtlistener-recap-fetch-provider-response-v1",'
        b'"outcome":"accepted","http_status":201,"queue_id":"77",'
        b'"body_sha256":"' + b"d" * 64 + b'"}'
    )
    assert canonical_provider_response_commitment_bytes(
        outcome="unknown",
        http_status=502,
        queue_id=None,
        body_sha256=body_sha256,
    ) == (
        b'{"version":"courtlistener-recap-fetch-provider-response-v1",'
        b'"outcome":"unknown","http_status":502,"queue_id":null,'
        b'"body_sha256":"' + b"d" * 64 + b'"}'
    )


@pytest.mark.parametrize(
    ("outcome", "status", "queue_id"),
    [
        ("accepted", 201, None),
        ("unknown", 502, "77"),
        ("other", 201, "77"),
        ("accepted", True, "77"),
        ("accepted", 99, "77"),
        ("accepted", 404, "77"),
    ],
)
def test_provider_response_commitment_rejects_noncanonical_states(
    outcome: str, status: object, queue_id: str | None
) -> None:
    with pytest.raises(ValueError, match="provider response commitment"):
        canonical_provider_response_commitment_bytes(
            outcome=outcome,
            http_status=status,
            queue_id=queue_id,
            body_sha256="d" * 64,
        )


def test_frozen_contract_names_the_versioned_provider_commitment() -> None:
    contract = Path("docs/schemas/courtlistener-recap-fetch-broker-v1.md").read_text(
        encoding="utf-8"
    )
    assert (
        "exact field order `version`, `outcome`, `http_status`, `queue_id`, "
        "`body_sha256`" in contract
    )
    assert "exact field order `status`, `id`" not in contract


def test_cross_language_wire_vector_binds_raw_body_hash_and_signature_payload() -> None:
    request = _request(cycle_id="cycle-é")
    body = canonical_submission_bytes(request)
    payload = canonical_signature_payload_bytes(
        method="POST",
        path="/v1/recap-fetch",
        body=body,
        timestamp="1721073600123",
        nonce="abcdefghijklmnopqrstuv",
        machine_id="machine-1",
        action="recap-fetch-submit",
        identity_policy_sha256="b" * 64,
    )
    assert body.hex() == (
        "7b22726571756573745f74797065223a2232222c2272656361705f646f63756d656e"
        "74223a22313233222c226379636c655f6964223a226379636c652dc3a9222c227075"
        "7263686173655f706f6c6963795f736861323536223a22"
        + "61"
        * 64
        + "222c226f7065726174696f6e5f6b6579223a2230303030303030302d303030302d"
        "343030302d383030302d303030303030303030303030222c22726573657276617469"
        "6f6e5f757364223a22332e3035227d"
    )
    assert hashlib.sha256(body).hexdigest() == (
        "a7c600d7a0ac3601e3a0f8d4729d4666426adae5946e03b33906aae534161376"
    )
    assert (
        payload
        == (
            "SECURE-GATE-RECAP-FETCH-V1\nPOST\n/v1/recap-fetch\n"
            "a7c600d7a0ac3601e3a0f8d4729d4666426adae5946e03b33906aae534161376\n"
            "1721073600123\nabcdefghijklmnopqrstuv\nmachine-1\n"
            "recap-fetch-submit\n" + "b" * 64
        ).encode()
    )
    golden_signature = _decode(
        "tNAcSXKjJn84LneqPVBQs_AGgf_KMHApzMcKMa598hJ5AzF3j4fKGZGx_6NuDAOS"
        "FQl5vGkDzUBTQQB1ESBwOA"
    )
    assert len(golden_signature) == 64
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    public_key, _ = _key()
    public_key.public_key().verify(
        encode_dss_signature(
            int.from_bytes(golden_signature[:32], "big"),
            int.from_bytes(golden_signature[32:], "big"),
        ),
        payload,
        ec.ECDSA(hashes.SHA256()),
    )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"recap_document":"123","request_type":"2","cycle_id":"cycle-1",'
        + b'"purchase_policy_sha256":"'
        + b"a" * 64
        + b'","operation_key":"00000000-0000-4000-8000-000000000000",'
        + b'"reservation_usd":"3.05"}',
        b'{"request_type":"2","recap_document":"123","cycle_id":"cycle-1",'
        + b'"purchase_policy_sha256":"'
        + b"a" * 64
        + b'","operation_key":"00000000-0000-4000-8000-000000000000",'
        + b'"reservation_usd":"3.05"}\n',
        b'{"request_type":"2","request_type":"2","recap_document":"123",'
        + b'"cycle_id":"cycle-1","purchase_policy_sha256":"'
        + b"a" * 64
        + b'","operation_key":"00000000-0000-4000-8000-000000000000",'
        + b'"reservation_usd":"3.05"}',
        b'\xff{"request_type":"2"}',
    ],
    ids=("field-order", "trailing-newline", "duplicate-key", "invalid-utf8"),
)
def test_noncanonical_raw_submission_bytes_are_rejected(raw: bytes) -> None:
    with pytest.raises(ValueError, match="canonical broker submission"):
        parse_canonical_submission_bytes(raw)


def test_nocharge_failed_reconciliation_has_null_fees_and_url() -> None:
    receipt = _receipt(
        id=None,
        state="failed",
        held_usd="0.00",
        authoritative_fee_usd="0.00",
        reconciled_at="2026-07-13T20:02:00.000Z",
        billing_evidence={
            "kind": "pacer_quarterly_invoice",
            "statement_period": "2026-Q3",
            "evidence_sha256": "d" * 64,
            "evidence_ref": "invoice-1",
            "imported_at": "2026-07-13T20:02:00.000Z",
        },
    )
    record = broker_reconciliation_record(receipt, download_url=None)
    assert tuple(record) == (
        "source_document_id",
        "disposition",
        "source_type",
        "source_reference",
        "pacer_fees",
        "download_url",
    )
    assert record["disposition"] == "failed"
    assert record["pacer_fees"] is None
    assert record["download_url"] is None


def test_env_lists_exact_missing_stage_scoped_credentials() -> None:
    with pytest.raises(
        ValueError,
        match=r"RECAP_FETCH_BROKER_URL.*RECAP_FETCH_BROKER_MACHINE_ID.*RECAP_FETCH_BROKER_PRIVATE_KEY_JWK.*RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON.*RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
    ):
        RecapFetchBrokerConfig.from_env({})


def test_identity_policy_digest_and_public_key_are_recomputed() -> None:
    _, jwk = _key()
    config = _config(jwk)
    policy = json.loads(config.identity_policy_json)
    policy["public_key_sha256"] = "0" * 64
    tampered = json.dumps(policy, separators=(",", ":"))
    with pytest.raises(ValueError, match="identity policy"):
        SignedRecapFetchPurchaseBroker(
            RecapFetchBrokerConfig(
                broker_url=config.broker_url,
                machine_id=config.machine_id,
                private_key_jwk=jwk,
                identity_policy_json=tampered,
                identity_policy_sha256=hashlib.sha256(tampered.encode()).hexdigest(),
            ),
            transport=_Transport(),
        )


def _request(**changes: str) -> dict[str, str]:
    value = {
        "request_type": "2",
        "recap_document": "123",
        "cycle_id": "cycle-1",
        "purchase_policy_sha256": "a" * 64,
        "operation_key": "00000000-0000-4000-8000-000000000000",
        "reservation_usd": "3.05",
    }
    value.update(changes)
    return value


def _receipt(**changes: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "version": "courtlistener-recap-fetch-receipt-v1",
        "operation_key": "00000000-0000-4000-8000-000000000000",
        "reservation_id": "reservation-1",
        "cycle_id": "cycle-1",
        "purchase_policy_sha256": "a" * 64,
        "recap_document": "123",
        "case_id": "candidate-123",
        "client_code": "lfb-3oaflyhagb6vuall5rg4gogwtb",
        "id": "77",
        "state": "queued",
        "reservation_usd": "3.05",
        "held_usd": "3.05",
        "authoritative_fee_usd": None,
        "provider_response_body_sha256": "e" * 64,
        "provider_response_sha256": "f" * 64,
        "submitted_at": "2026-07-13T20:00:00.000Z",
        "updated_at": "2026-07-13T20:02:00.000Z",
        "delivered_at": None,
        "reconciled_at": None,
        "billing_evidence": None,
    }
    value.update(changes)
    return value


def _config(jwk: str) -> RecapFetchBrokerConfig:
    private = json.loads(jwk)
    public_jwk = json.dumps(
        {
            "crv": "P-256",
            "kty": "EC",
            "x": private["x"],
            "y": private["y"],
        },
        separators=(",", ":"),
    )
    policy = json.dumps(
        {
            "version": "recap-fetch-identity-policy-v1",
            "machine_id": "machine-1",
            "public_key_sha256": hashlib.sha256(public_jwk.encode()).hexdigest(),
            "tailscale_node_id": "node-1",
            "allowed_source_ips": ["192.0.2.1"],
            "activated_at": "2026-07-13T20:00:00.000Z",
            "expires_at": "2026-07-14T20:00:00.000Z",
        },
        separators=(",", ":"),
    )
    return RecapFetchBrokerConfig(
        broker_url="https://secure-gate-recap-fetch.johnjhughes.com",
        machine_id="machine-1",
        private_key_jwk=jwk,
        identity_policy_json=policy,
        identity_policy_sha256=hashlib.sha256(policy.encode()).hexdigest(),
    )


def _key() -> tuple[ec.EllipticCurvePrivateKey, str]:
    key = ec.derive_private_key(7, ec.SECP256R1())
    numbers = key.private_numbers()
    public = numbers.public_numbers
    encoded = {
        "kty": "EC",
        "crv": "P-256",
        "x": _encode(public.x.to_bytes(32, "big")),
        "y": _encode(public.y.to_bytes(32, "big")),
        "d": _encode(numbers.private_value.to_bytes(32, "big")),
    }
    return key, json.dumps(encoded, separators=(",", ":"))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
