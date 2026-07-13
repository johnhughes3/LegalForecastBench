from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
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
        held_usd="0.00",
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
