"""Signed client for the isolated, budget-enforcing RECAP Fetch broker."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from http.client import HTTPMessage
from typing import IO, Any, Protocol, cast
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

_ORIGIN = "https://secure-gate-recap-fetch.johnjhughes.com"
_DOMAIN = "SECURE-GATE-RECAP-FETCH-V1"
_HEX = re.compile(r"^[0-9a-f]{64}$")
_POSITIVE_DECIMAL = re.compile(r"^[1-9][0-9]*$")
_MONEY = re.compile(r"^(0|[1-9][0-9]*)\.[0-9]{2}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{22,128}$")
_MAX_BODY = 1_048_576
_RECEIPT_FIELDS = frozenset(
    {
        "version",
        "operation_key",
        "reservation_id",
        "cycle_id",
        "purchase_policy_sha256",
        "recap_document",
        "case_id",
        "client_code",
        "id",
        "state",
        "reservation_usd",
        "held_usd",
        "authoritative_fee_usd",
        "provider_response_body_sha256",
        "provider_response_sha256",
        "submitted_at",
        "updated_at",
        "delivered_at",
        "reconciled_at",
        "billing_evidence",
    }
)
_ERRORS: dict[tuple[int, str], bool] = {
    (400, "invalid_request"): True,
    (401, "machine_auth_required"): True,
    (403, "source_not_allowed"): True,
    (403, "document_not_allowed"): True,
    (409, "policy_not_active"): True,
    (409, "reservation_mismatch"): True,
    (409, "cycle_cap_exceeded"): True,
    (409, "case_cap_exceeded"): True,
    (409, "operation_key_conflict"): True,
    (409, "operation_outcome_pending"): False,
    (404, "receipt_not_found"): False,
    (409, "operation_failed"): True,
    (500, "client_code_collision"): True,
    (502, "provider_outcome_unknown"): False,
    (504, "provider_outcome_unknown"): False,
    (503, "broker_unavailable"): True,
}


class RecapFetchBrokerError(RuntimeError):
    """Base class for sanitized broker-client failures."""


class BrokerDefiniteRejection(RecapFetchBrokerError):
    """The broker contract proves no ambiguous paid-provider outcome."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BrokerOutcomeUnknown(RecapFetchBrokerError):
    """Submission may have crossed the charge-bearing dispatch boundary."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RecapFetchBrokerConfig:
    """Stage-scoped client identity and fixed broker endpoint."""

    broker_url: str
    machine_id: str
    private_key_jwk: str = field(repr=False)
    identity_policy_json: str = field(repr=False)
    identity_policy_sha256: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.broker_url)
        if (
            self.broker_url != _ORIGIN
            or parsed.scheme != "https"
            or parsed.hostname != "secure-gate-recap-fetch.johnjhughes.com"
            or parsed.port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "RECAP_FETCH_BROKER_URL must be the reviewed broker origin"
            )
        if not self.machine_id or "\n" in self.machine_id:
            raise ValueError("invalid broker machine ID")
        if not _HEX.fullmatch(self.identity_policy_sha256):
            raise ValueError("invalid broker identity-policy digest")
        if self.timeout_seconds <= 0:
            raise ValueError("broker timeout must be positive")

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> RecapFetchBrokerConfig:
        """Load only the four stage-scoped identity values from the environment."""

        values = os.environ if environ is None else environ
        names = (
            "RECAP_FETCH_BROKER_URL",
            "RECAP_FETCH_BROKER_MACHINE_ID",
            "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
            "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
            "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
        )
        missing = [name for name in names if not values.get(name, "").strip()]
        if missing:
            raise ValueError(
                "missing required broker configuration: " + ", ".join(missing)
            )
        return cls(
            broker_url=values[names[0]].strip(),
            machine_id=values[names[1]].strip(),
            private_key_jwk=values[names[2]].strip(),
            identity_policy_json=values[names[3]].strip(),
            identity_policy_sha256=values[names[4]].strip(),
            timeout_seconds=float(
                values.get("RECAP_FETCH_BROKER_TIMEOUT_SECONDS", "30")
            ),
        )


@dataclass(frozen=True, slots=True)
class BrokerRawResponse:
    """Bounded raw HTTP response used by the strict parser."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


class BrokerTransport(Protocol):
    """Single-attempt HTTP transport boundary."""

    def request(
        self,
        *,
        method: str,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> BrokerRawResponse: ...


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, fp, code, msg, headers, newurl
        return None


class UrlLibBrokerTransport:
    """One-attempt HTTPS transport with redirects disabled."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_RejectRedirects())

    def request(
        self,
        *,
        method: str,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> BrokerRawResponse:
        request = urllib.request.Request(
            url, data=body, method=method, headers=dict(headers)
        )
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                return BrokerRawResponse(
                    response.status,
                    response.read(_MAX_BODY + 1),
                    dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            return BrokerRawResponse(
                exc.code,
                exc.read(_MAX_BODY + 1),
                dict(exc.headers.items()) if exc.headers else {},
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BrokerOutcomeUnknown("broker transport outcome is unknown") from exc


class SignedRecapFetchPurchaseBroker:
    """Strict P-256 signed adapter for submission and receipt recovery."""

    def __init__(
        self,
        config: RecapFetchBrokerConfig,
        *,
        transport: BrokerTransport | None = None,
        clock_ms: Callable[[], int] | None = None,
        nonce: Callable[[], str] | None = None,
    ) -> None:
        self.config = config
        self._key = _private_key(config.private_key_jwk)
        _validate_identity_policy(config, self._key)
        self._transport = transport or UrlLibBrokerTransport()
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._nonce = nonce or (lambda: _b64(secrets.token_bytes(18)))

    def submit(self, request: Mapping[str, str]) -> Mapping[str, Any]:
        """Submit canonical purchase bytes exactly once."""

        response = self._request(
            path="/v1/recap-fetch",
            action="recap-fetch-submit",
            body=canonical_submission_bytes(request),
        )
        if response.status_code not in {200, 201}:
            _raise_broker_error(response)
        payload = _json(response)
        if set(payload) != {"reservation_id", "id"}:
            raise BrokerOutcomeUnknown("broker success receipt has unexpected fields")
        reservation_id = payload.get("reservation_id")
        queue_id = payload.get("id")
        if not isinstance(reservation_id, str) or not reservation_id:
            raise BrokerOutcomeUnknown("broker success receipt is invalid")
        if not isinstance(queue_id, str) or not _POSITIVE_DECIMAL.fullmatch(queue_id):
            raise BrokerOutcomeUnknown("broker queue ID is not canonical")
        return {"reservation_id": reservation_id, "id": queue_id}

    def receipt(self, operation_key: str) -> Mapping[str, Any]:
        """Retrieve a machine-owned durable receipt without replaying submission."""

        operation_key = _uuid4(operation_key)
        response = self._request(
            path=f"/v1/receipts/{operation_key}",
            action="recap-fetch-receipt",
            body=b"",
        )
        if response.status_code != 200:
            _raise_broker_error(response)
        return validate_broker_receipt(_json(response))

    def _request(self, *, path: str, action: str, body: bytes) -> BrokerRawResponse:
        timestamp = str(self._clock_ms())
        nonce = self._nonce()
        if not re.fullmatch(r"[0-9]{13}", timestamp) or not _NONCE.fullmatch(nonce):
            raise ValueError("invalid broker timestamp or nonce")
        payload = canonical_signature_payload_bytes(
            method="POST",
            path=path,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
            machine_id=self.config.machine_id,
            action=action,
            identity_policy_sha256=self.config.identity_policy_sha256,
        )
        der = self._key.sign(payload, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        signature = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-secure-gate-machine-id": self.config.machine_id,
            "x-secure-gate-machine-timestamp": timestamp,
            "x-secure-gate-machine-nonce": nonce,
            "x-secure-gate-machine-signature": signature,
            "x-secure-gate-action": action,
            "x-secure-gate-identity-policy-sha256": self.config.identity_policy_sha256,
        }
        response = self._transport.request(
            method="POST",
            url=f"{self.config.broker_url}{path}",
            body=body,
            headers=headers,
            timeout_seconds=self.config.timeout_seconds,
        )
        if len(response.body) > _MAX_BODY:
            raise BrokerOutcomeUnknown("broker response exceeds size limit")
        return response


def canonical_submission_bytes(request: Mapping[str, str]) -> bytes:
    """Return the exact six-field body committed by the broker contract."""

    fields = (
        "request_type",
        "recap_document",
        "cycle_id",
        "purchase_policy_sha256",
        "operation_key",
        "reservation_usd",
    )
    if set(request) != set(fields) or any(
        not isinstance(request.get(k), str) for k in fields
    ):
        raise ValueError("broker submission requires the exact six string fields")
    ordered = {field: request[field] for field in fields}
    if ordered["request_type"] != "2":
        raise ValueError("invalid RECAP Fetch request type")
    if not _POSITIVE_DECIMAL.fullmatch(ordered["recap_document"]):
        raise ValueError("invalid RECAP document ID")
    if not ordered["cycle_id"] or "\n" in ordered["cycle_id"]:
        raise ValueError("invalid cycle ID")
    if not _HEX.fullmatch(ordered["purchase_policy_sha256"]):
        raise ValueError("invalid purchase-policy digest")
    _uuid4(ordered["operation_key"])
    if not _MONEY.fullmatch(ordered["reservation_usd"]):
        raise ValueError("invalid canonical reservation")
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":")).encode()


def parse_canonical_submission_bytes(raw: bytes) -> dict[str, str]:
    """Parse only the byte-exact canonical request accepted by the broker."""

    try:
        decoded = raw.decode("utf-8")
        value: object = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        if not isinstance(value, dict):
            raise ValueError
        request = cast(dict[str, str], value)
        if canonical_submission_bytes(request) != raw:
            raise ValueError
        return request
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise ValueError("invalid canonical broker submission bytes") from None


def canonical_provider_response_commitment_bytes(
    *,
    outcome: str,
    http_status: object,
    queue_id: str | None,
    body_sha256: str,
) -> bytes:
    """Build the broker's exact versioned redacted provider commitment."""

    if (
        outcome not in {"accepted", "unknown"}
        or isinstance(http_status, bool)
        or not isinstance(http_status, int)
        or not 100 <= http_status <= 599
        or not _HEX.fullmatch(body_sha256)
        or (
            outcome == "accepted"
            and (
                not 200 <= http_status <= 299
                or not _POSITIVE_DECIMAL.fullmatch(queue_id or "")
            )
        )
        or (outcome == "unknown" and queue_id is not None)
    ):
        raise ValueError("invalid canonical provider response commitment")
    return json.dumps(
        {
            "version": "courtlistener-recap-fetch-provider-response-v1",
            "outcome": outcome,
            "http_status": http_status,
            "queue_id": queue_id,
            "body_sha256": body_sha256,
        },
        separators=(",", ":"),
    ).encode()


def canonical_signature_payload_bytes(
    *,
    method: str,
    path: str,
    body: bytes,
    timestamp: str,
    nonce: str,
    machine_id: str,
    action: str,
    identity_policy_sha256: str,
) -> bytes:
    """Build the exact cross-language nine-field signing-domain bytes."""

    fields = (
        _DOMAIN,
        method,
        path,
        hashlib.sha256(body).hexdigest(),
        timestamp,
        nonce,
        machine_id,
        action,
        identity_policy_sha256,
    )
    if any(not value or "\n" in value or "\r" in value for value in fields):
        raise ValueError("invalid broker signature field")
    if method != "POST" or not path.startswith("/") or "?" in path or "#" in path:
        raise ValueError("invalid broker signature method or path")
    if not re.fullmatch(r"[0-9]{13}", timestamp) or not _NONCE.fullmatch(nonce):
        raise ValueError("invalid broker timestamp or nonce")
    if not _HEX.fullmatch(identity_policy_sha256):
        raise ValueError("invalid broker identity-policy digest")
    return "\n".join(fields).encode()


def validate_broker_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy the broker's exact nonsecret receipt schema."""

    if frozenset(payload) != _RECEIPT_FIELDS:
        raise BrokerOutcomeUnknown("broker receipt has unexpected fields")
    receipt = dict(payload)
    if receipt["version"] != "courtlistener-recap-fetch-receipt-v1":
        raise BrokerOutcomeUnknown("broker receipt version is invalid")
    for field_name in ("reservation_id", "cycle_id", "case_id"):
        if not isinstance(receipt[field_name], str) or not receipt[field_name]:
            raise BrokerOutcomeUnknown("broker receipt identity is invalid")
    try:
        operation_key = _uuid4(_string(receipt["operation_key"]))
    except ValueError as exc:
        raise BrokerOutcomeUnknown("broker receipt operation key is invalid") from exc
    if receipt["client_code"] != _client_code(operation_key):
        raise BrokerOutcomeUnknown("broker receipt client code is invalid")
    if not _POSITIVE_DECIMAL.fullmatch(_string(receipt["recap_document"])):
        raise BrokerOutcomeUnknown("broker receipt document ID is invalid")
    if not _HEX.fullmatch(_string(receipt["purchase_policy_sha256"])):
        raise BrokerOutcomeUnknown("broker receipt policy digest is invalid")
    reservation = _money(_string(receipt["reservation_usd"]))
    held = _money(_string(receipt["held_usd"]))
    state = receipt["state"]
    if state not in {
        "submitted",
        "queued",
        "delivered_but_unreconciled",
        "confirmed",
        "failed",
        "unknown",
    }:
        raise BrokerOutcomeUnknown("broker receipt state is invalid")
    queue_id = receipt["id"]
    if queue_id is not None and (
        not isinstance(queue_id, str) or not _POSITIVE_DECIMAL.fullmatch(queue_id)
    ):
        raise BrokerOutcomeUnknown("broker receipt queue ID is invalid")
    if state in {"queued", "delivered_but_unreconciled"} and queue_id is None:
        raise BrokerOutcomeUnknown("broker receipt state requires a queue ID")
    for hash_field in ("provider_response_body_sha256", "provider_response_sha256"):
        value = receipt[hash_field]
        if value is not None and (
            not isinstance(value, str) or not _HEX.fullmatch(value)
        ):
            raise BrokerOutcomeUnknown("broker receipt response commitment is invalid")
    if (receipt["provider_response_body_sha256"] is None) != (
        receipt["provider_response_sha256"] is None
    ):
        raise BrokerOutcomeUnknown(
            "broker receipt response commitments must be present as a pair"
        )
    fee_value = receipt["authoritative_fee_usd"]
    evidence = receipt["billing_evidence"]
    if state == "confirmed":
        fee = _money(_string(fee_value))
        if (
            fee <= 0
            or held != fee
            or evidence is None
            or receipt["reconciled_at"] is None
        ):
            raise BrokerOutcomeUnknown("confirmed broker receipt is inconsistent")
    elif state == "failed":
        if evidence is not None:
            if (
                _money(_string(fee_value)) != 0
                or held != 0
                or receipt["reconciled_at"] is None
            ):
                raise BrokerOutcomeUnknown("failed broker receipt is inconsistent")
        elif fee_value is not None or held != 0 or receipt["reconciled_at"] is not None:
            raise BrokerOutcomeUnknown("failed broker receipt is inconsistent")
    elif fee_value is not None or evidence is not None or held != reservation:
        raise BrokerOutcomeUnknown("unreconciled broker receipt is inconsistent")
    if evidence is not None:
        _validate_billing_evidence(evidence)
    submitted = _receipt_timestamp(receipt["submitted_at"])
    updated = _receipt_timestamp(receipt["updated_at"])
    delivered = (
        None
        if receipt["delivered_at"] is None
        else _receipt_timestamp(receipt["delivered_at"])
    )
    reconciled = (
        None
        if receipt["reconciled_at"] is None
        else _receipt_timestamp(receipt["reconciled_at"])
    )
    if updated < submitted or any(
        value is not None and not (submitted <= value <= updated)
        for value in (delivered, reconciled)
    ):
        raise BrokerOutcomeUnknown("broker receipt timestamps are inconsistent")
    if state == "delivered_but_unreconciled" and delivered is None:
        raise BrokerOutcomeUnknown("broker receipt delivery timestamp is missing")
    return receipt


def broker_reconciliation_record(
    receipt: Mapping[str, Any], *, download_url: str | None
) -> dict[str, Any]:
    """Transform a validated terminal receipt to the exact six-field journal record."""

    validated = validate_broker_receipt(receipt)
    evidence = cast(Mapping[str, Any], validated["billing_evidence"])
    digest = _string(evidence["evidence_sha256"])
    reference = f"recap-fetch-broker:{validated['operation_key']}:{digest}"
    state = validated["state"]
    if state == "confirmed":
        if validated["id"] is None:
            raise BrokerOutcomeUnknown(
                "confirmed broker receipt lacks a verified queue ID"
            )
        if download_url is None:
            raise BrokerOutcomeUnknown(
                "confirmed broker receipt lacks verified download"
            )
        _validate_download_url(download_url)
        fee = _string(validated["authoritative_fee_usd"])
        fees: Mapping[str, str] | None = {
            "pacerFee": fee,
            "serviceFee": "0.00",
            "total": fee,
        }
        disposition = "confirmed"
    elif state == "failed":
        fees = None
        disposition = "failed"
        download_url = None
    else:
        raise BrokerOutcomeUnknown("broker receipt is not terminal")
    return {
        "source_document_id": validated["recap_document"],
        "disposition": disposition,
        "source_type": "statement_export",
        "source_reference": reference,
        "pacer_fees": fees,
        "download_url": download_url,
    }


def _raise_broker_error(response: BrokerRawResponse) -> None:
    try:
        payload = _json(response)
        if set(payload) != {"error"} or not isinstance(payload["error"], Mapping):
            raise ValueError
        error = cast(Mapping[str, Any], payload["error"])
        if set(error) != {"code", "message"}:
            raise ValueError
        code, message = error["code"], error["message"]
        if not isinstance(code, str) or not isinstance(message, str) or not message:
            raise ValueError
        definite = _ERRORS[(response.status_code, code)]
    except (ValueError, KeyError, TypeError):
        raise BrokerOutcomeUnknown("broker returned an undocumented error") from None
    if definite:
        raise BrokerDefiniteRejection(code, message)
    raise BrokerOutcomeUnknown("broker operation outcome remains unresolved", code=code)


def _json(response: BrokerRawResponse) -> dict[str, Any]:
    content_type = next(
        (v for k, v in response.headers.items() if k.lower() == "content-type"), ""
    )
    if content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise BrokerOutcomeUnknown("broker response is not JSON")
    try:
        value = json.loads(
            response.body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise BrokerOutcomeUnknown("broker returned malformed JSON") from None
    if not isinstance(value, dict):
        raise BrokerOutcomeUnknown("broker response must be an object")
    return cast(dict[str, Any], value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value {value}")


def _private_key(raw: str) -> ec.EllipticCurvePrivateKey:
    try:
        decoded: object = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(decoded, dict):
            raise ValueError
        value = cast(dict[str, object], decoded)
        if set(value) != {"kty", "crv", "x", "y", "d"}:
            raise ValueError
        if value["kty"] != "EC" or value["crv"] != "P-256":
            raise ValueError
        coordinates = tuple(value[name] for name in ("x", "y", "d"))
        if any(not isinstance(coordinate, str) for coordinate in coordinates):
            raise ValueError
        x, y, d = (_decode32(cast(str, coordinate)) for coordinate in coordinates)
        numbers = ec.EllipticCurvePrivateNumbers(
            int.from_bytes(d, "big"),
            ec.EllipticCurvePublicNumbers(
                int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
            ),
        )
        return numbers.private_key()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid P-256 private signing JWK") from exc


def _validate_identity_policy(
    config: RecapFetchBrokerConfig, key: ec.EllipticCurvePrivateKey
) -> None:
    try:
        decoded: object = json.loads(
            config.identity_policy_json, object_pairs_hook=_unique_object
        )
        if not isinstance(decoded, dict):
            raise ValueError
        policy = cast(dict[str, object], decoded)
        fields = (
            "version",
            "machine_id",
            "public_key_sha256",
            "tailscale_node_id",
            "allowed_source_ips",
            "activated_at",
            "expires_at",
        )
        if tuple(policy) != fields or set(policy) != set(fields):
            raise ValueError
        canonical = json.dumps(
            {field: policy[field] for field in fields},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if canonical != config.identity_policy_json:
            raise ValueError
        if (
            policy["version"] != "recap-fetch-identity-policy-v1"
            or policy["machine_id"] != config.machine_id
            or not isinstance(policy["tailscale_node_id"], str)
            or not policy["tailscale_node_id"]
        ):
            raise ValueError
        public = key.public_key().public_numbers()
        public_jwk = json.dumps(
            {
                "crv": "P-256",
                "kty": "EC",
                "x": _b64(public.x.to_bytes(32, "big")),
                "y": _b64(public.y.to_bytes(32, "big")),
            },
            separators=(",", ":"),
        )
        if (
            policy["public_key_sha256"]
            != hashlib.sha256(public_jwk.encode()).hexdigest()
        ):
            raise ValueError
        raw_ips = policy["allowed_source_ips"]
        if not isinstance(raw_ips, list):
            raise ValueError
        ips = cast(list[object], raw_ips)
        if not ips or any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            for value in ips
        ):
            raise ValueError
        typed_ips = cast(list[str], ips)
        if typed_ips != sorted(set(typed_ips)):
            raise ValueError
        activated = _policy_timestamp(policy["activated_at"])
        expires = _policy_timestamp(policy["expires_at"])
        lifetime = (expires - activated).total_seconds()
        if lifetime <= 0 or lifetime > 86_400:
            raise ValueError
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        if digest != config.identity_policy_sha256:
            raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid RECAP Fetch broker identity policy") from exc


def _policy_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z",
        value,
    ):
        raise ValueError("invalid policy timestamp")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return parsed


def _receipt_timestamp(value: object) -> datetime:
    try:
        return _policy_timestamp(value)
    except ValueError as exc:
        raise BrokerOutcomeUnknown("broker receipt timestamp is invalid") from exc


def _validate_billing_evidence(value: object) -> None:
    if not isinstance(value, Mapping):
        raise BrokerOutcomeUnknown("billing evidence is invalid")
    evidence = cast(Mapping[str, object], value)
    if set(evidence) != {
        "kind",
        "statement_period",
        "evidence_sha256",
        "evidence_ref",
        "imported_at",
    }:
        raise BrokerOutcomeUnknown("billing evidence is invalid")
    kind = evidence["kind"]
    period = evidence["statement_period"]
    valid_period = bool(
        kind == "pacer_detailed_transactions"
        and isinstance(period, str)
        and re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", period)
    ) or bool(
        kind == "pacer_quarterly_invoice"
        and isinstance(period, str)
        and re.fullmatch(r"[0-9]{4}-Q[1-4]", period)
    )
    if not valid_period or not _HEX.fullmatch(_string(evidence["evidence_sha256"])):
        raise BrokerOutcomeUnknown("billing evidence is invalid")
    if not isinstance(evidence["evidence_ref"], str) or not evidence["evidence_ref"]:
        raise BrokerOutcomeUnknown("billing evidence is invalid")
    _receipt_timestamp(evidence["imported_at"])


def _client_code(operation_key: str) -> str:
    digest = hashlib.sha256(operation_key.encode()).digest()
    return "lfb-" + base64.b32encode(digest).decode().lower().rstrip("=")[:26]


def _validate_download_url(value: str) -> None:
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise BrokerOutcomeUnknown("broker reconciliation URL is invalid") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.courtlistener.com", "storage.courtlistener.com"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise BrokerOutcomeUnknown("broker reconciliation URL is not allowlisted")


def _uuid4(value: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid operation key") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("invalid operation key")
    return value


def _money(value: str) -> Decimal:
    if not _MONEY.fullmatch(value):
        raise BrokerOutcomeUnknown("invalid canonical money")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise BrokerOutcomeUnknown("invalid canonical money") from exc


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise BrokerOutcomeUnknown("broker field must be a string")
    return value


def _decode32(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        raise ValueError("invalid JWK coordinate")
    decoded = base64.urlsafe_b64decode(value + "=")
    if len(decoded) != 32:
        raise ValueError("invalid JWK coordinate")
    return decoded


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
