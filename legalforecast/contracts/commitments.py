"""Named canonical JSON and digest profiles for new commitment-bearing code."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes,
    canonical_json_value_bytes,
)
from legalforecast.protocol.manifest import canonical_json as manifest_canonical_json

from .schemas import SchemaIdentifier


class CommitmentEncodingError(ValueError):
    """Raised when a value cannot enter a named commitment profile."""


class CommitmentMismatchError(ValueError):
    """Raised when committed bytes, profile, or schema domain do not match."""


Encoder = Callable[[object], bytes]


@dataclass(frozen=True, slots=True)
class CanonicalJsonCodec:
    """One explicitly named canonical JSON byte profile."""

    name: str
    _encoder: Encoder = field(repr=False, compare=False)

    def encode(self, value: object) -> bytes:
        """Encode *value* after rejecting non-finite numeric tokens."""

        _reject_non_finite(value)
        return self._encoder(value)


def _artifact_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=CommitmentEncodingError,
        error_message="value is invalid for artifact canonical JSON v1",
    )


def _artifact_value_bytes(value: object) -> bytes:
    return canonical_json_value_bytes(
        value,
        error_type=CommitmentEncodingError,
        error_message="value is invalid for artifact JSON value v1",
    )


def _manifest_bytes(value: object) -> bytes:
    try:
        return manifest_canonical_json(value).encode("utf-8")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise CommitmentEncodingError(
            "value is invalid for manifest canonical JSON v1"
        ) from exc


def _run_card_bytes(value: object) -> bytes:
    try:
        return (
            f"{json.dumps(value, indent=2, sort_keys=True, allow_nan=False)}\n".encode()
        )
    except (TypeError, UnicodeError, ValueError) as exc:
        raise CommitmentEncodingError(
            "value is invalid for indented run-card JSON v1"
        ) from exc


def _reject_non_finite(value: object, *, _seen: set[int] | None = None) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise CommitmentEncodingError(
            "non-finite numbers are invalid in commitment payloads"
        )
    if isinstance(value, (str, bytes, bytearray)):
        return
    if _seen is None:
        _seen = set()
    identity = id(value)
    if identity in _seen:
        return
    if isinstance(value, Mapping):
        _seen.add(identity)
        for key, item in cast(Mapping[object, object], value).items():
            _reject_non_finite(key, _seen=_seen)
            _reject_non_finite(item, _seen=_seen)
    elif isinstance(value, Sequence):
        _seen.add(identity)
        for item in cast(Sequence[object], value):
            _reject_non_finite(item, _seen=_seen)


ARTIFACT_CANONICAL_JSON_V1 = CanonicalJsonCodec(
    "legalforecast.codec.artifact-canonical-json.v1",
    _artifact_bytes,
)
ARTIFACT_JSON_VALUE_V1 = CanonicalJsonCodec(
    "legalforecast.codec.artifact-json-value.v1",
    _artifact_value_bytes,
)
MANIFEST_CANONICAL_JSON_V1 = CanonicalJsonCodec(
    "legalforecast.codec.manifest-canonical-json.v1",
    _manifest_bytes,
)
RUN_CARD_INDENTED_JSON_V1 = CanonicalJsonCodec(
    "legalforecast.codec.run-card-indented-json.v1",
    _run_card_bytes,
)


@dataclass(frozen=True, slots=True)
class RawSha256:
    """A lowercase SHA-256 hex digest without a prefix."""

    value: str

    def __post_init__(self) -> None:
        if not is_lowercase_sha256(self.value):
            raise ValueError("raw SHA-256 must be 64 lowercase hexadecimal characters")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PrefixedSha256:
    """A lowercase SHA-256 hex digest with the persisted ``sha256:`` prefix."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith("sha256:") or not is_lowercase_sha256(
            self.value.removeprefix("sha256:")
        ):
            raise ValueError(
                "prefixed SHA-256 must be sha256: plus 64 lowercase "
                "hexadecimal characters"
            )

    def __str__(self) -> str:
        return self.value


Digest = RawSha256 | PrefixedSha256


class DigestRepresentation(StrEnum):
    """Persisted SHA-256 representations that must never be implicit."""

    RAW_HEX = "raw-hex"
    SHA256_PREFIXED = "sha256-prefixed"


@dataclass(frozen=True, slots=True)
class Commitment:
    """A digest bound to its named byte profile and schema domain."""

    profile: str
    domain: SchemaIdentifier
    digest: Digest


@dataclass(frozen=True, slots=True)
class CommitmentProfile:
    """A named codec plus its persisted digest representation."""

    name: str
    codec: CanonicalJsonCodec
    representation: DigestRepresentation

    def commit(self, value: object, *, domain: SchemaIdentifier) -> Commitment:
        """Commit *value* under this exact byte and representation profile."""

        raw = hashlib.sha256(self.codec.encode(value)).hexdigest()
        digest: Digest
        if self.representation is DigestRepresentation.RAW_HEX:
            digest = RawSha256(raw)
        else:
            digest = PrefixedSha256(f"sha256:{raw}")
        return Commitment(profile=self.name, domain=domain, digest=digest)

    def verify(
        self,
        value: object,
        commitment: Commitment,
        *,
        domain: SchemaIdentifier,
    ) -> None:
        """Fail closed on profile, domain, representation, or byte mismatch."""

        if commitment.profile != self.name:
            raise CommitmentMismatchError("commitment profile does not match")
        if commitment.domain != domain:
            raise CommitmentMismatchError("commitment domain does not match")
        wrong_representation = (
            self.representation is DigestRepresentation.RAW_HEX
            and not isinstance(commitment.digest, RawSha256)
        ) or (
            self.representation is DigestRepresentation.SHA256_PREFIXED
            and not isinstance(commitment.digest, PrefixedSha256)
        )
        if wrong_representation:
            raise CommitmentMismatchError("digest representation does not match")
        actual = self.commit(value, domain=domain)
        if not hmac.compare_digest(str(actual.digest), str(commitment.digest)):
            raise CommitmentMismatchError("commitment digest does not match")


ARTIFACT_RAW_SHA256_V1 = CommitmentProfile(
    "legalforecast.commitment.artifact-canonical-json.raw-sha256.v1",
    ARTIFACT_CANONICAL_JSON_V1,
    DigestRepresentation.RAW_HEX,
)
ARTIFACT_PREFIXED_SHA256_V1 = CommitmentProfile(
    "legalforecast.commitment.artifact-canonical-json.sha256-prefixed.v1",
    ARTIFACT_CANONICAL_JSON_V1,
    DigestRepresentation.SHA256_PREFIXED,
)
MANIFEST_RAW_SHA256_V1 = CommitmentProfile(
    "legalforecast.commitment.manifest-canonical-json.raw-sha256.v1",
    MANIFEST_CANONICAL_JSON_V1,
    DigestRepresentation.RAW_HEX,
)
RUN_CARD_RAW_SHA256_V1 = CommitmentProfile(
    "legalforecast.commitment.run-card-indented-json.raw-sha256.v1",
    RUN_CARD_INDENTED_JSON_V1,
    DigestRepresentation.RAW_HEX,
)
