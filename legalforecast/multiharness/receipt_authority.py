"""External authority for evaluator receipt signing and verification.

The canonical :mod:`legalforecast.multiharness.evaluation` module intentionally
does not select an issuer or hold key material.  This module is the small
operator-facing seam that supplies that missing authority without changing the
frozen evaluation-spec or evaluation-receipt schemas:

* the public configuration is committed and contains no private key;
* signing is delegated to a caller-provided loader for the sanctioned
  Infisical ``dev`` namespace; and
* verification selects a public key by an exact issuer/key-id match, then
  delegates the byte and binding checks to the canonical evaluator contract.

The loader is deliberately a callback.  This module never invokes Infisical,
reads a credential, or falls back to an environment variable.  Tests can use
an explicitly synthetic fixture loader while production supplies the reviewed
Infisical wrapper integration at the process boundary.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self, cast

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from legalforecast.multiharness.evaluation import (
    CostMeasurement,
    EvaluationBindingError,
    EvaluationReceipt,
    EvaluationSpec,
    EvaluationTokenUsage,
    MonotonicTiming,
    build_evaluation_receipt,
    verify_evaluation_result,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_str,
    validate_sha256,
)

RECEIPT_AUTHORITY_SCHEMA_VERSION = "legalforecast.multiharness.receipt_authority.v1"
ED25519_RAW_PRIVATE_KEY_BYTES = 32
ED25519_RAW_PUBLIC_KEY_BYTES = 32

# This is the only proposed production custody location.  The value is a
# namespace/path, not a credential and must never be replaced with a secret.
EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT = "dev"
EVALUATOR_ISSUER_INFISICAL_PATH = (
    "/agents/sandbox/legalforecastbench/harness-runtime/evaluator-issuer"
)
EVALUATOR_ISSUER_PRIVATE_KEY_NAME = "HARVEY_LAB_EVALUATOR_ED25519_PRIVATE_KEY"
EVALUATOR_ISSUER_PRIVATE_KEY_ENCODING = "base64-raw-32-byte-ed25519"

_AUTHORITY_FIELDS = frozenset(
    {
        "schema_version",
        "issuer_id",
        "key_id",
        "algorithm",
        "issuer_policy_sha256",
        "public_key_base64",
        "private_key_source",
        "status",
    }
)
_PRIVATE_SOURCE_FIELDS = frozenset(
    {"backend", "environment", "path", "name", "encoding"}
)
_SAFE_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/@+-"
)


class ReceiptAuthorityError(ValueError):
    """A receipt could not be signed or authenticated by the configured issuer."""


@dataclass(frozen=True, slots=True)
class EvaluatorIssuerAuthority:
    """Public issuer authority plus a deferred, external signer loader.

    ``signing_secret_loader`` must return the configured secret as a base64
    string (or ASCII-encoded base64 bytes) only when signing is explicitly
    requested.  It is never called by construction or verification.  The loader
    receives the exact environment, path, and name from
    :class:`EvaluatorIssuerAuthority`;
    a production caller should reject any mismatch before fetching.
    """

    issuer_id: str
    key_id: str
    algorithm: str
    issuer_policy_sha256: str
    public_key_base64: str | None
    private_key_environment: str = EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT
    private_key_path: str = EVALUATOR_ISSUER_INFISICAL_PATH
    private_key_name: str = EVALUATOR_ISSUER_PRIVATE_KEY_NAME
    private_key_encoding: str = EVALUATOR_ISSUER_PRIVATE_KEY_ENCODING
    status: str = "configured"
    signing_secret_loader: Callable[[str, str, str], str | bytes] | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.issuer_id, "issuer_id")
        _require_identifier(self.key_id, "key_id")
        if self.algorithm != "Ed25519":
            raise ReceiptAuthorityError("issuer algorithm must be Ed25519")
        try:
            validate_sha256(self.issuer_policy_sha256, "issuer_policy_sha256")
        except MultiHarnessValidationError as exc:
            raise ReceiptAuthorityError(str(exc)) from exc
        if self.private_key_environment != EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT:
            raise ReceiptAuthorityError(
                "evaluator issuer private key must use Infisical dev"
            )
        if self.private_key_path != EVALUATOR_ISSUER_INFISICAL_PATH:
            raise ReceiptAuthorityError(
                "evaluator issuer private key path is outside the sanctioned namespace"
            )
        if self.private_key_name != EVALUATOR_ISSUER_PRIVATE_KEY_NAME:
            raise ReceiptAuthorityError(
                "evaluator issuer private key name is not approved"
            )
        if self.private_key_encoding != EVALUATOR_ISSUER_PRIVATE_KEY_ENCODING:
            raise ReceiptAuthorityError(
                "unsupported evaluator issuer private-key format"
            )
        if self.status not in {"configured", "pending_human_provisioning"}:
            raise ReceiptAuthorityError("issuer authority status is not recognized")
        if self.public_key_base64 is not None:
            _decode_public_key(self.public_key_base64)
        if self.status == "configured" and self.public_key_base64 is None:
            raise ReceiptAuthorityError(
                "configured issuer authority must contain a public verification key"
            )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        """Parse a public authority record with exact-field checking."""

        try:
            require_known_fields(
                record,
                required=_AUTHORITY_FIELDS,
                field_name="evaluator issuer authority",
            )
            if (
                require_str(record, "schema_version")
                != RECEIPT_AUTHORITY_SCHEMA_VERSION
            ):
                raise ReceiptAuthorityError(
                    "unsupported evaluator issuer authority schema"
                )
            raw_source = record.get("private_key_source")
            if not isinstance(raw_source, Mapping):
                raise ReceiptAuthorityError("private_key_source must be an object")
            source = cast(Mapping[str, Any], raw_source)
            require_known_fields(
                source,
                required=_PRIVATE_SOURCE_FIELDS,
                field_name="private_key_source",
            )
            if require_str(source, "backend") != "infisical-agent-sandbox":
                raise ReceiptAuthorityError(
                    "evaluator issuer private key must use the Infisical wrapper"
                )
            return cls(
                issuer_id=require_str(record, "issuer_id"),
                key_id=require_str(record, "key_id"),
                algorithm=require_str(record, "algorithm"),
                issuer_policy_sha256=require_str(record, "issuer_policy_sha256"),
                public_key_base64=_optional_string(record, "public_key_base64"),
                private_key_environment=require_str(source, "environment"),
                private_key_path=require_str(source, "path"),
                private_key_name=require_str(source, "name"),
                private_key_encoding=require_str(source, "encoding"),
                status=require_str(record, "status"),
            )
        except (MultiHarnessValidationError, TypeError) as exc:
            raise ReceiptAuthorityError(str(exc)) from exc

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        """Load a public authority config; never read a private key file."""

        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReceiptAuthorityError(
                "issuer authority config is unreadable"
            ) from exc
        if not isinstance(decoded, Mapping):
            raise ReceiptAuthorityError("issuer authority config must be an object")
        return cls.from_record(cast(Mapping[str, Any], decoded))

    def to_record(self) -> dict[str, object]:
        """Return the public config and custody metadata, never key material."""

        return {
            "schema_version": RECEIPT_AUTHORITY_SCHEMA_VERSION,
            "issuer_id": self.issuer_id,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "issuer_policy_sha256": self.issuer_policy_sha256,
            "public_key_base64": self.public_key_base64,
            "private_key_source": {
                "backend": "infisical-agent-sandbox",
                "environment": self.private_key_environment,
                "path": self.private_key_path,
                "name": self.private_key_name,
                "encoding": self.private_key_encoding,
            },
            "status": self.status,
        }

    @property
    def public_key(self) -> Ed25519PublicKey:
        """Return the configured public key or refuse a pending authority."""

        if self.public_key_base64 is None:
            raise ReceiptAuthorityError(
                "evaluator issuer public key is pending human provisioning"
            )
        return Ed25519PublicKey.from_public_bytes(
            _decode_public_key(self.public_key_base64)
        )

    def with_signing_secret_loader(
        self,
        loader: Callable[[str, str, str], str | bytes],
    ) -> Self:
        """Attach a deferred external loader without reading its secret."""

        if self.status != "configured":
            raise ReceiptAuthorityError("cannot sign with a pending issuer authority")
        return type(self)(
            issuer_id=self.issuer_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
            issuer_policy_sha256=self.issuer_policy_sha256,
            public_key_base64=self.public_key_base64,
            private_key_environment=self.private_key_environment,
            private_key_path=self.private_key_path,
            private_key_name=self.private_key_name,
            private_key_encoding=self.private_key_encoding,
            status=self.status,
            signing_secret_loader=loader,
        )

    def signer(self) -> Callable[[bytes], bytes]:
        """Return a signer that fetches only from the configured authority seam."""

        loader = self.signing_secret_loader
        if loader is None:
            raise ReceiptAuthorityError(
                "evaluator issuer signer is unavailable; use the Infisical loader seam"
            )
        # Fail before fetching if the public authority is unresolved.  This
        # check is intentionally separate from the loader call so a missing
        # public key cannot cause a secret fetch.
        public = self.public_key

        def sign(payload: bytes) -> bytes:
            raw = loader(
                self.private_key_environment,
                self.private_key_path,
                self.private_key_name,
            )
            private_bytes = _decode_private_key(raw)
            private = Ed25519PrivateKey.from_private_bytes(private_bytes)
            candidate = private.public_key().public_bytes_raw()
            if candidate != public.public_bytes_raw():
                raise ReceiptAuthorityError(
                    "evaluator issuer private key does not match committed public key"
                )
            return private.sign(payload)

        return sign

    def sign(self, payload: bytes) -> bytes:
        """Sign one payload through the configured external authority."""

        return self.signer()(payload)

    def build_receipt(
        self,
        *,
        spec: EvaluationSpec,
        measurement_id: str,
        evaluation_attempt_id: str,
        attempt_nonce: str,
        repeat_index: int,
        judge_resolved_identity: str,
        raw_result_sha256: str,
        raw_result_size_bytes: int,
        raw_result_media_type: str,
        status: str,
        token_usage: EvaluationTokenUsage,
        cost: CostMeasurement,
        timing: MonotonicTiming,
    ) -> EvaluationReceipt:
        """Build a receipt carrying exactly this authority's policy and key id."""

        try:
            return build_evaluation_receipt(
                spec=spec,
                signer=self.signer(),
                measurement_id=measurement_id,
                evaluation_attempt_id=evaluation_attempt_id,
                attempt_nonce=attempt_nonce,
                repeat_index=repeat_index,
                judge_resolved_identity=judge_resolved_identity,
                raw_result_sha256=raw_result_sha256,
                raw_result_size_bytes=raw_result_size_bytes,
                raw_result_media_type=raw_result_media_type,
                status=status,
                token_usage=token_usage,
                cost=cost,
                timing=timing,
                issuer_policy_sha256=self.issuer_policy_sha256,
                issuer_key_id=self.key_id,
            )
        except ReceiptAuthorityError:
            raise
        except (TypeError, ValueError) as exc:
            raise ReceiptAuthorityError(str(exc)) from exc

    def verify_receipt(
        self,
        receipt: EvaluationReceipt,
        raw_result: bytes,
        *,
        spec: EvaluationSpec,
        expected_measurement_id: str,
        expected_evaluation_attempt_id: str,
        expected_attempt_nonce: str,
        expected_repeat_index: int,
        expected_deliverable_manifest_sha256: str | None = None,
        expected_runtime_policy_sha256: str | None = None,
        seen_measurement_ids: set[str] | None = None,
        seen_attempt_nonces: set[str] | None = None,
        occupied_repeat_slots: set[tuple[str, int]] | None = None,
    ) -> EvaluationReceipt:
        """Verify an exact receipt/result pair against this trusted authority."""

        if not receipt.signature:
            raise ReceiptAuthorityError("unsigned evaluator receipt is refused")
        if receipt.issuer_key_id != self.key_id:
            raise ReceiptAuthorityError("unknown evaluator receipt issuer")
        if receipt.issuer_policy_sha256 != self.issuer_policy_sha256:
            raise ReceiptAuthorityError("evaluator receipt issuer policy is unknown")
        try:
            return verify_evaluation_result(
                receipt,
                raw_result,
                expected_media_type=receipt.raw_result_media_type,
                spec=spec,
                expected_spec_sha256=spec.spec_sha256,
                expected_deliverable_manifest_sha256=(
                    expected_deliverable_manifest_sha256
                    or spec.deliverable_manifest_sha256
                ),
                expected_runtime_policy_sha256=(
                    expected_runtime_policy_sha256 or spec.runtime_policy_sha256
                ),
                expected_issuer_policy_sha256=self.issuer_policy_sha256,
                expected_issuer_key_id=self.key_id,
                issuer_public_key=self.public_key,
                expected_measurement_id=expected_measurement_id,
                expected_evaluation_attempt_id=expected_evaluation_attempt_id,
                expected_attempt_nonce=expected_attempt_nonce,
                expected_repeat_index=expected_repeat_index,
                seen_measurement_ids=seen_measurement_ids,
                seen_attempt_nonces=seen_attempt_nonces,
                occupied_repeat_slots=occupied_repeat_slots,
            )
        except EvaluationBindingError as exc:
            raise ReceiptAuthorityError(str(exc)) from exc


def pending_evaluator_issuer_authority(
    *,
    issuer_id: str,
    key_id: str,
    issuer_policy_sha256: str,
) -> EvaluatorIssuerAuthority:
    """Create the fail-closed authority used before human key provisioning."""

    return EvaluatorIssuerAuthority(
        issuer_id=issuer_id,
        key_id=key_id,
        algorithm="Ed25519",
        issuer_policy_sha256=issuer_policy_sha256,
        public_key_base64=None,
        status="pending_human_provisioning",
    )


def authority_from_synthetic_fixture_key(
    *,
    issuer_id: str,
    key_id: str,
    issuer_policy_sha256: str,
    private_key_bytes: bytes,
) -> EvaluatorIssuerAuthority:
    """Build an explicitly synthetic authority for provider-free tests only."""

    if len(private_key_bytes) != ED25519_RAW_PRIVATE_KEY_BYTES:
        raise ReceiptAuthorityError("synthetic Ed25519 private key must be 32 bytes")
    private = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    encoded = base64.b64encode(private.public_key().public_bytes_raw()).decode("ascii")
    encoded_private = base64.b64encode(private_key_bytes)
    authority = EvaluatorIssuerAuthority(
        issuer_id=issuer_id,
        key_id=key_id,
        algorithm="Ed25519",
        issuer_policy_sha256=issuer_policy_sha256,
        public_key_base64=encoded,
    )
    return authority.with_signing_secret_loader(
        lambda _environment, _path, _name: encoded_private
    )


def _decode_public_key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ReceiptAuthorityError("issuer public key is not valid base64") from exc
    if len(decoded) != ED25519_RAW_PUBLIC_KEY_BYTES:
        raise ReceiptAuthorityError("issuer public key must contain exactly 32 bytes")
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ReceiptAuthorityError("issuer public key must use canonical base64")
    return decoded


def _decode_private_key(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        encoded = value
    else:
        encoded = value.encode("ascii", errors="strict")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise ReceiptAuthorityError("issuer private key is not valid base64") from exc
    if len(decoded) != ED25519_RAW_PRIVATE_KEY_BYTES:
        raise ReceiptAuthorityError("issuer private key must contain exactly 32 bytes")
    return decoded


def _optional_string(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if type(value) is not str:
        raise ReceiptAuthorityError(f"{field_name} must be a string or null")
    return value


def _require_identifier(value: str, field_name: str) -> None:
    if not value or any(char not in _SAFE_ID_CHARS for char in value):
        raise ReceiptAuthorityError(f"{field_name} is not a valid issuer identifier")
