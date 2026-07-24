"""Main-pinned authority for hardware-authenticated disclosure review.

The public loader deliberately has no path, registry, or expected-hash argument.
Production trust is selected only from the immutable registry in this module.
The underscored loader exists solely so tests can exercise provisioned resources
without committing a fake official hardware identity.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    verify_cohort_policy,
)

AUTHORITY_SCHEMA_VERSION = "legalforecast.disclosure_review_authority.v1"
REVIEWER_POLICY_SCHEMA_VERSION = "legalforecast.disclosure_reviewer_policy.v1"
SIGNATURE_NAMESPACE = "legalforecast-disclosure-review-v1"
HARDWARE_SIGNER_BEAD = "LegalForecastBench-5qd6.39.7.1"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_PRINCIPAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@+-]{0,127}")
_HARDWARE_KEY_TYPES = frozenset(
    {
        "sk-ssh-ed25519@openssh.com",
        "sk-ecdsa-sha2-nistp256@openssh.com",
    }
)
_ARTIFACT_FIELDS = frozenset({"schema_version", "authority", "authority_sha256"})
_AUTHORITY_FIELDS = frozenset(
    {
        "cycle_id",
        "cohort_policy_sha256",
        "eligibility_anchor",
        "reviewer_id",
        "identity_kind",
        "ssh_key_type",
        "ssh_public_key",
        "ssh_public_key_fingerprint",
        "reviewer_policy_sha256",
        "signature_namespace",
        "controlled_store_uri_prefix",
    }
)
_REVIEWER_POLICY_FIELDS = frozenset(
    {
        "schema_version",
        "reviewer_id",
        "ssh_principal",
        "ssh_public_key",
        "identity_kind",
        "controlled_store_uri_prefix",
        "signature_namespace",
    }
)
_AUTHORITY_RESOURCE_ROOT = Path(__file__).with_name("disclosure_review_authorities")


class DisclosureReviewAuthorityError(ValueError):
    """Raised when disclosure-review authority is absent or has drifted."""


@dataclass(frozen=True, slots=True)
class DisclosureReviewAuthorityIdentity:
    """Stable registry key derived from verified frozen-cohort semantics."""

    cycle_id: str
    cohort_policy_sha256: str
    eligibility_anchor: date

    def __post_init__(self) -> None:
        if not self.cycle_id or self.cycle_id != self.cycle_id.strip():
            raise DisclosureReviewAuthorityError("cycle_id must be a non-empty string")
        if _SHA256.fullmatch(self.cohort_policy_sha256) is None:
            raise DisclosureReviewAuthorityError(
                "cohort policy hash must be a lowercase SHA-256 digest"
            )


@dataclass(frozen=True, slots=True)
class DisclosureReviewAuthority:
    """Verified authority selected by the main-pinned registry."""

    identity: DisclosureReviewAuthorityIdentity
    reviewer_id: str
    identity_kind: Literal["human_hardware"]
    ssh_key_type: str
    ssh_public_key: str
    ssh_public_key_fingerprint: str
    reviewer_policy_sha256: str
    signature_namespace: str
    controlled_store_uri_prefix: str
    authority_sha256: str


@dataclass(frozen=True, slots=True)
class DisclosureReviewAuthorityRegistryEntry:
    """Immutable registry metadata; provisioned entries pin complete file bytes."""

    status: Literal["provisioned", "unprovisioned"]
    blocker_bead: str | None
    resource_name: str | None = None
    resource_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.status == "unprovisioned":
            if not self.blocker_bead:
                raise DisclosureReviewAuthorityError(
                    "unprovisioned authority requires a blocker bead"
                )
            if self.resource_name is not None or self.resource_sha256 is not None:
                raise DisclosureReviewAuthorityError(
                    "unprovisioned authority cannot name a resource"
                )
            return
        if self.status != "provisioned":
            raise DisclosureReviewAuthorityError("unsupported authority status")
        if self.blocker_bead is not None:
            raise DisclosureReviewAuthorityError(
                "provisioned authority cannot retain a blocker bead"
            )
        _safe_resource_name(self.resource_name)
        _digest(self.resource_sha256, "authority resource hash")


CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY = DisclosureReviewAuthorityIdentity(
    cycle_id="cycle-1-superseding-target-100-2026-07-14",
    cohort_policy_sha256=(
        "d27bf66cd895ec42b912aafc535bf53cf9e9d38182bff9e32ff5ac72c0bc0128"
    ),
    eligibility_anchor=date(2026, 6, 30),
)

# This is intentionally unprovisioned until the independently controlled hardware
# signer in HARDWARE_SIGNER_BEAD is available. Never place a test key here.
MAIN_DISCLOSURE_REVIEW_AUTHORITY_REGISTRY: Mapping[
    DisclosureReviewAuthorityIdentity, DisclosureReviewAuthorityRegistryEntry
] = MappingProxyType(
    {
        CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY: DisclosureReviewAuthorityRegistryEntry(
            status="unprovisioned",
            blocker_bead=HARDWARE_SIGNER_BEAD,
        )
    }
)


def authority_artifact_bytes(artifact: Mapping[str, object]) -> bytes:
    """Serialize an authority artifact in its single canonical representation."""

    return _canonical_bytes(artifact)


def write_disclosure_review_authority(
    path: str | Path,
    artifact: Mapping[str, object],
    *,
    expected_identity: DisclosureReviewAuthorityIdentity,
    reviewer_policy_bytes: bytes,
) -> None:
    """Verify and atomically publish one immutable authority artifact."""

    payload = authority_artifact_bytes(artifact)
    verify_disclosure_review_authority(
        payload,
        expected_identity=expected_identity,
        reviewer_policy_bytes=reviewer_policy_bytes,
    )

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(f"{target}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if target.exists():
            if target.read_bytes() != payload:
                raise DisclosureReviewAuthorityError(
                    "disclosure review authority already exists with different "
                    "immutable content"
                )
            return
        _atomic_write(target, payload)
    finally:
        os.close(lock_fd)


def disclosure_authority_identity_from_cohort_policy(
    cohort_policy_artifact: Mapping[str, Any],
) -> DisclosureReviewAuthorityIdentity:
    """Derive the registry identity from verified frozen-policy semantics."""

    try:
        policy_sha256 = verify_cohort_policy(cohort_policy_artifact)
    except (CohortPolicyError, TypeError, ValueError) as exc:
        raise DisclosureReviewAuthorityError("frozen cohort policy is invalid") from exc
    policy_value = cohort_policy_artifact.get("policy")
    if not isinstance(policy_value, Mapping):
        raise DisclosureReviewAuthorityError(
            "frozen cohort policy has no policy object"
        )
    policy = cast(Mapping[str, object], policy_value)
    cycle_id = _text(policy.get("cycle_id"), "cycle_id")
    anchor_text = _text(policy.get("eligibility_anchor"), "eligibility anchor")
    try:
        anchor = date.fromisoformat(anchor_text)
    except ValueError as exc:
        raise DisclosureReviewAuthorityError(
            "frozen cohort policy has malformed eligibility anchor"
        ) from exc
    if anchor != CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY.eligibility_anchor:
        raise DisclosureReviewAuthorityError(
            "frozen cohort policy eligibility anchor is not 2026-06-30"
        )
    return DisclosureReviewAuthorityIdentity(cycle_id, policy_sha256, anchor)


def generate_disclosure_review_authority(
    identity: DisclosureReviewAuthorityIdentity,
    reviewer_policy_bytes: bytes,
) -> dict[str, object]:
    """Generate a complete authority artifact from exact reviewer-policy bytes."""

    policy = _parse_reviewer_policy(reviewer_policy_bytes)
    authority: dict[str, object] = {
        "cycle_id": identity.cycle_id,
        "cohort_policy_sha256": identity.cohort_policy_sha256,
        "eligibility_anchor": identity.eligibility_anchor.isoformat(),
        "reviewer_id": policy.reviewer_id,
        "identity_kind": "human_hardware",
        "ssh_key_type": policy.ssh_key_type,
        "ssh_public_key": policy.ssh_public_key,
        "ssh_public_key_fingerprint": policy.ssh_public_key_fingerprint,
        "reviewer_policy_sha256": policy.sha256,
        "signature_namespace": policy.signature_namespace,
        "controlled_store_uri_prefix": policy.controlled_store_uri_prefix,
    }
    return {
        "schema_version": AUTHORITY_SCHEMA_VERSION,
        "authority": authority,
        "authority_sha256": hashlib.sha256(_canonical_bytes(authority)).hexdigest(),
    }


def verify_disclosure_review_authority(
    authority_bytes: bytes,
    *,
    expected_identity: DisclosureReviewAuthorityIdentity,
    reviewer_policy_bytes: bytes,
) -> DisclosureReviewAuthority:
    """Verify strict schema and every authority binding against exact inputs."""

    artifact = _parse_canonical_object(authority_bytes, "authority artifact")
    _exact_fields(artifact, _ARTIFACT_FIELDS, "authority artifact")
    if artifact.get("schema_version") != AUTHORITY_SCHEMA_VERSION:
        raise DisclosureReviewAuthorityError("unsupported authority schema version")
    authority_value = artifact.get("authority")
    if not isinstance(authority_value, Mapping):
        raise DisclosureReviewAuthorityError("authority must be an object")
    authority = cast(Mapping[str, object], authority_value)
    _exact_fields(authority, _AUTHORITY_FIELDS, "authority")
    committed = _digest(artifact.get("authority_sha256"), "authority hash")
    if hashlib.sha256(_canonical_bytes(authority)).hexdigest() != committed:
        raise DisclosureReviewAuthorityError("authority hash does not match content")

    policy = _parse_reviewer_policy(reviewer_policy_bytes)
    if authority.get("cycle_id") != expected_identity.cycle_id:
        raise DisclosureReviewAuthorityError("authority cycle_id mismatch")
    if authority.get("cohort_policy_sha256") != expected_identity.cohort_policy_sha256:
        raise DisclosureReviewAuthorityError("authority cohort policy hash mismatch")
    if (
        authority.get("eligibility_anchor")
        != expected_identity.eligibility_anchor.isoformat()
    ):
        raise DisclosureReviewAuthorityError("authority eligibility anchor mismatch")
    if authority.get("reviewer_id") != policy.reviewer_id:
        raise DisclosureReviewAuthorityError("authority reviewer substitution")
    if authority.get("identity_kind") != "human_hardware":
        raise DisclosureReviewAuthorityError("authority must bind human_hardware")
    if authority.get("ssh_key_type") != policy.ssh_key_type:
        raise DisclosureReviewAuthorityError("authority SSH key type mismatch")
    if authority.get("ssh_public_key") != policy.ssh_public_key:
        raise DisclosureReviewAuthorityError("authority SSH public key mismatch")
    if authority.get("ssh_public_key_fingerprint") != policy.ssh_public_key_fingerprint:
        raise DisclosureReviewAuthorityError("authority SSH key fingerprint mismatch")
    if authority.get("reviewer_policy_sha256") != policy.sha256:
        raise DisclosureReviewAuthorityError("authority reviewer policy hash mismatch")
    if authority.get("signature_namespace") != policy.signature_namespace:
        raise DisclosureReviewAuthorityError("authority signature namespace mismatch")
    if (
        authority.get("controlled_store_uri_prefix")
        != policy.controlled_store_uri_prefix
    ):
        raise DisclosureReviewAuthorityError(
            "authority controlled store prefix mismatch"
        )
    return DisclosureReviewAuthority(
        identity=expected_identity,
        reviewer_id=policy.reviewer_id,
        identity_kind="human_hardware",
        ssh_key_type=policy.ssh_key_type,
        ssh_public_key=policy.ssh_public_key,
        ssh_public_key_fingerprint=policy.ssh_public_key_fingerprint,
        reviewer_policy_sha256=policy.sha256,
        signature_namespace=policy.signature_namespace,
        controlled_store_uri_prefix=policy.controlled_store_uri_prefix,
        authority_sha256=committed,
    )


def load_main_disclosure_review_authority(
    cohort_policy_artifact: Mapping[str, Any],
    *,
    reviewer_policy_bytes: bytes,
) -> DisclosureReviewAuthority:
    """Load authority selected exclusively by the main-pinned registry."""

    identity = disclosure_authority_identity_from_cohort_policy(cohort_policy_artifact)
    return _load_registered_disclosure_review_authority(
        identity,
        reviewer_policy_bytes=reviewer_policy_bytes,
        registry=MAIN_DISCLOSURE_REVIEW_AUTHORITY_REGISTRY,
        resource_root=_AUTHORITY_RESOURCE_ROOT,
    )


def _load_registered_disclosure_review_authority(
    identity: DisclosureReviewAuthorityIdentity,
    *,
    reviewer_policy_bytes: bytes,
    registry: Mapping[
        DisclosureReviewAuthorityIdentity, DisclosureReviewAuthorityRegistryEntry
    ],
    resource_root: Path,
) -> DisclosureReviewAuthority:
    """Load from an injected registry for tests, never as a production trust root."""

    entry = registry.get(identity)
    if entry is None:
        raise DisclosureReviewAuthorityError(
            "disclosure review authority is not registered for the frozen cohort"
        )
    if entry.status == "unprovisioned":
        raise DisclosureReviewAuthorityError(
            "disclosure review authority is explicitly unprovisioned; "
            f"complete {entry.blocker_bead}"
        )
    name = _safe_resource_name(entry.resource_name)
    expected_resource_sha256 = _digest(entry.resource_sha256, "authority resource hash")
    payload = _read_immutable_resource(resource_root, name)
    if hashlib.sha256(payload).hexdigest() != expected_resource_sha256:
        raise DisclosureReviewAuthorityError(
            "disclosure review authority resource hash drift"
        )
    return verify_disclosure_review_authority(
        payload,
        expected_identity=identity,
        reviewer_policy_bytes=reviewer_policy_bytes,
    )


@dataclass(frozen=True, slots=True)
class _ReviewerPolicy:
    reviewer_id: str
    ssh_key_type: str
    ssh_public_key: str
    ssh_public_key_fingerprint: str
    controlled_store_uri_prefix: str
    signature_namespace: str
    sha256: str


def _parse_reviewer_policy(policy_bytes: bytes) -> _ReviewerPolicy:
    policy = _parse_canonical_object(policy_bytes, "reviewer policy")
    _exact_fields(policy, _REVIEWER_POLICY_FIELDS, "reviewer policy")
    if policy.get("schema_version") != REVIEWER_POLICY_SCHEMA_VERSION:
        raise DisclosureReviewAuthorityError("unsupported reviewer policy schema")
    if policy.get("identity_kind") != "human_hardware":
        raise DisclosureReviewAuthorityError(
            "disclosure authority requires identity_kind human_hardware"
        )
    reviewer_id = _text(policy.get("reviewer_id"), "reviewer_id")
    principal = _text(policy.get("ssh_principal"), "ssh_principal")
    if _PRINCIPAL.fullmatch(principal) is None:
        raise DisclosureReviewAuthorityError("reviewer policy has invalid principal")
    public_key = _text(policy.get("ssh_public_key"), "ssh_public_key")
    parts = public_key.split(" ")
    if len(parts) != 2 or not all(parts):
        raise DisclosureReviewAuthorityError(
            "reviewer policy SSH public key must be exact type and base64 data"
        )
    key_type, encoded = parts
    if key_type not in _HARDWARE_KEY_TYPES:
        raise DisclosureReviewAuthorityError(
            "reviewer policy requires an allowlisted hardware-backed sk-* SSH key"
        )
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise DisclosureReviewAuthorityError(
            "reviewer policy has malformed SSH public key"
        ) from exc
    if base64.b64encode(blob).decode("ascii") != encoded:
        raise DisclosureReviewAuthorityError("SSH public key base64 is not canonical")
    _validate_security_key_blob(key_type, blob)
    namespace = _text(policy.get("signature_namespace"), "signature_namespace")
    if namespace != SIGNATURE_NAMESPACE:
        raise DisclosureReviewAuthorityError(
            "reviewer policy has unsupported signature namespace"
        )
    store_prefix = _text(
        policy.get("controlled_store_uri_prefix"), "controlled_store_uri_prefix"
    )
    _require_private_store_uri(store_prefix)
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode(
        "ascii"
    ).rstrip("=")
    return _ReviewerPolicy(
        reviewer_id=reviewer_id,
        ssh_key_type=key_type,
        ssh_public_key=public_key,
        ssh_public_key_fingerprint=fingerprint,
        controlled_store_uri_prefix=store_prefix,
        signature_namespace=namespace,
        sha256=hashlib.sha256(policy_bytes).hexdigest(),
    )


def _validate_security_key_blob(key_type: str, blob: bytes) -> None:
    algorithm, offset = _read_ssh_string(blob, 0)
    if algorithm.decode("ascii", errors="strict") != key_type:
        raise DisclosureReviewAuthorityError(
            "SSH public key embedded algorithm does not match key type"
        )
    if key_type == "sk-ssh-ed25519@openssh.com":
        public_key, offset = _read_ssh_string(blob, offset)
        application, offset = _read_ssh_string(blob, offset)
        if len(public_key) != 32 or not application:
            raise DisclosureReviewAuthorityError("malformed sk-ed25519 public key")
    else:
        curve, offset = _read_ssh_string(blob, offset)
        public_key, offset = _read_ssh_string(blob, offset)
        application, offset = _read_ssh_string(blob, offset)
        if (
            curve != b"nistp256"
            or len(public_key) != 65
            or public_key[:1] != b"\x04"
            or not application
        ):
            raise DisclosureReviewAuthorityError("malformed sk-ecdsa public key")
    if offset != len(blob):
        raise DisclosureReviewAuthorityError("SSH public key has trailing data")


def _read_ssh_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(blob):
        raise DisclosureReviewAuthorityError("malformed SSH public key structure")
    size = int.from_bytes(blob[offset : offset + 4], "big")
    start = offset + 4
    end = start + size
    if end > len(blob):
        raise DisclosureReviewAuthorityError("malformed SSH public key structure")
    return blob[start:end], end


def _read_immutable_resource(root: Path, name: str) -> bytes:
    root_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        root_fd = os.open(root, root_flags)
    except OSError as exc:
        raise DisclosureReviewAuthorityError(
            "authority resource root is missing, inaccessible, or a symlink"
        ) from exc
    try:
        try:
            file_fd = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=root_fd,
            )
        except OSError as exc:
            raise DisclosureReviewAuthorityError(
                "authority resource is missing, inaccessible, or a symlink"
            ) from exc
        try:
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode):
                raise DisclosureReviewAuthorityError(
                    "authority resource is not a regular file"
                )
            if before.st_nlink != 1:
                raise DisclosureReviewAuthorityError(
                    "authority resource hardlink count must be exactly one"
                )
            chunks: list[bytes] = []
            while chunk := os.read(file_fd, 65_536):
                chunks.append(chunk)
            after = os.fstat(file_fd)
            stable_fields = (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
            if any(
                getattr(before, field) != getattr(after, field)
                for field in stable_fields
            ):
                raise DisclosureReviewAuthorityError(
                    "authority resource changed while being read"
                )
            return b"".join(chunks)
        finally:
            os.close(file_fd)
    finally:
        os.close(root_fd)


def _safe_resource_name(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.endswith(".json")
        or value in {".json", "..json"}
        or Path(value).name != value
        or "/" in value
        or "\\" in value
    ):
        raise DisclosureReviewAuthorityError("unsafe authority resource name")
    return value


def _parse_canonical_object(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DisclosureReviewAuthorityError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise DisclosureReviewAuthorityError(f"{label} must be a JSON object")
    parsed = cast(dict[str, object], value)
    if payload != _canonical_bytes(parsed):
        raise DisclosureReviewAuthorityError(f"{label} is not canonical JSON")
    return parsed


def _canonical_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise DisclosureReviewAuthorityError(
            "authority artifact is not JSON-serializable"
        ) from exc
    return f"{text}\n".encode()


def _atomic_write(path: Path, payload: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _exact_fields(
    value: Mapping[str, object], expected: frozenset[str], label: str
) -> None:
    if frozenset(value) != expected:
        raise DisclosureReviewAuthorityError(f"{label} does not have exact fields")


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DisclosureReviewAuthorityError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DisclosureReviewAuthorityError(f"{label} must be a non-empty string")
    return value


def _require_private_store_uri(value: str) -> None:
    parsed = urlsplit(value)
    segments = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []
    if (
        parsed.scheme != "private-store"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or "//" in parsed.path
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise DisclosureReviewAuthorityError(
            "reviewer policy requires a controlled private-store URI prefix"
        )


__all__ = [
    "AUTHORITY_SCHEMA_VERSION",
    "CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY",
    "HARDWARE_SIGNER_BEAD",
    "MAIN_DISCLOSURE_REVIEW_AUTHORITY_REGISTRY",
    "DisclosureReviewAuthority",
    "DisclosureReviewAuthorityError",
    "DisclosureReviewAuthorityIdentity",
    "DisclosureReviewAuthorityRegistryEntry",
    "authority_artifact_bytes",
    "disclosure_authority_identity_from_cohort_policy",
    "generate_disclosure_review_authority",
    "load_main_disclosure_review_authority",
    "verify_disclosure_review_authority",
    "write_disclosure_review_authority",
]
