"""Private run-start metadata bound to existing execution identities.

Cycle 1 freezes the authenticated receipt bytes, so exact executable,
boundary, and configuration observations live in a private sidecar.  The
sidecar's ``config_sha256`` is the value callers place in the existing
``RunIdentity`` and ``ExecutionReceipt`` fields.  This keeps one RunSpec,
ExecutionReceipt, and identity-key family while making the receipt unable to
silently cross a metadata/configuration boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self, cast

from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)
from legalforecast.multiharness.local_cli_identity import (
    ObservedExecutableIdentity,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_str,
    validate_sha256,
)

RUN_METADATA_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative private run metadata sidecar
    "legalforecast.multiharness.private_run_metadata.v1"
)
RECEIPT_METADATA_BINDING_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative receipt binding sidecar
    "legalforecast.multiharness.receipt_metadata_binding.v1"
)

_RUN_METADATA_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "started_at_utc",
        "run_spec_sha256",
        "config_hashes",
        "config_sha256",
        "binary_identities",
        "boundary_identity",
        "metadata_sha256",
    }
)
_BINARY_FIELDS = frozenset(
    {"executable_name", "executable_version", "executable_sha256", "capability_sha256"}
)
_BINDING_FIELDS = frozenset(
    {
        "schema_version",
        "receipt_id",
        "receipt_public_sha256",
        "run_metadata_sha256",
        "run_spec_sha256",
        "config_sha256",
        "boundary_identity_sha256",
        "binary_identity_sha256",
    }
)


class RunMetadataError(ValueError):
    """A private metadata sidecar or receipt binding is invalid."""


@dataclass(frozen=True, slots=True)
class BinaryRunIdentity:
    """Exact path-free executable identity observed at run start."""

    executable_name: str
    executable_version: str
    executable_sha256: str
    capability_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.executable_name, "executable_name")
        _require_non_empty(self.executable_version, "executable_version")
        _require_prefixed_digest(self.executable_sha256, "executable_sha256")
        if self.capability_sha256 is not None:
            _require_prefixed_digest(self.capability_sha256, "capability_sha256")

    @classmethod
    def from_observed(
        cls,
        observed: ObservedExecutableIdentity,
        *,
        capability_sha256: str | None = None,
    ) -> Self:
        """Convert a local identity probe result to private run metadata."""

        return cls(
            executable_name=observed.basename,
            executable_version=observed.version,
            executable_sha256=f"sha256:{observed.sha256}",
            capability_sha256=capability_sha256,
        )

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "executable_name": self.executable_name,
            "executable_version": self.executable_version,
            "executable_sha256": self.executable_sha256,
        }
        if self.capability_sha256 is not None:
            record["capability_sha256"] = self.capability_sha256
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        try:
            require_known_fields(
                record,
                required=_BINARY_FIELDS - {"capability_sha256"},
                optional=frozenset({"capability_sha256"}),
                field_name="binary identity",
            )
            return cls(
                executable_name=require_str(record, "executable_name"),
                executable_version=require_str(record, "executable_version"),
                executable_sha256=require_str(record, "executable_sha256"),
                capability_sha256=_optional_str(record, "capability_sha256"),
            )
        except (MultiHarnessValidationError, TypeError) as exc:
            raise RunMetadataError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class PrivateRunMetadata:
    """Immutable private metadata emitted at the beginning of one run."""

    run_id: str
    started_at_utc: str
    run_spec_sha256: str
    config_hashes: Mapping[str, str]
    config_sha256: str
    binary_identities: tuple[BinaryRunIdentity, ...]
    boundary_identity: Mapping[str, object]
    metadata_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, "run_id")
        _require_non_empty(self.started_at_utc, "started_at_utc")
        _require_prefixed_digest(self.run_spec_sha256, "run_spec_sha256")
        _validate_hash_map(self.config_hashes, "config_hashes")
        _require_prefixed_digest(self.config_sha256, "config_sha256")
        if not self.binary_identities:
            raise RunMetadataError("binary_identities must not be empty")
        if not self.boundary_identity:
            raise RunMetadataError("boundary_identity must not be empty")
        expected = _digest(self._content_record())
        _require_prefixed_digest(self.metadata_sha256, "metadata_sha256")
        if self.metadata_sha256 != expected:
            raise RunMetadataError("metadata_sha256 does not match metadata content")

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": RUN_METADATA_SCHEMA_VERSION,
            "run_id": self.run_id,
            "started_at_utc": self.started_at_utc,
            "run_spec_sha256": self.run_spec_sha256,
            "config_hashes": dict(sorted(self.config_hashes.items())),
            "config_sha256": self.config_sha256,
            "binary_identities": [item.to_record() for item in self.binary_identities],
            "boundary_identity": _canonical_value(self.boundary_identity),
        }

    def to_record(self) -> dict[str, object]:
        return {**self._content_record(), "metadata_sha256": self.metadata_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        try:
            require_known_fields(
                record,
                required=_RUN_METADATA_FIELDS,
                field_name="private run metadata",
            )
            raw_hashes = record.get("config_hashes")
            if not isinstance(raw_hashes, Mapping):
                raise RunMetadataError("config_hashes must be an object")
            typed_hashes = cast(Mapping[str, Any], raw_hashes)
            config_hashes = {key: value for key, value in typed_hashes.items()}
            raw_binaries = record.get("binary_identities")
            if not isinstance(raw_binaries, Sequence) or isinstance(
                raw_binaries, (str, bytes, bytearray)
            ):
                raise RunMetadataError("binary_identities must be an array")
            typed_binaries = cast(Sequence[Any], raw_binaries)
            binaries = tuple(
                BinaryRunIdentity.from_record(cast(Mapping[str, Any], item))
                for item in typed_binaries
                if isinstance(item, Mapping)
            )
            if len(binaries) != len(typed_binaries):
                raise RunMetadataError("binary identities must be objects")
            raw_boundary = record.get("boundary_identity")
            if not isinstance(raw_boundary, Mapping):
                raise RunMetadataError("boundary_identity must be an object")
            return cls(
                run_id=require_str(record, "run_id"),
                started_at_utc=require_str(record, "started_at_utc"),
                run_spec_sha256=require_str(record, "run_spec_sha256"),
                config_hashes=config_hashes,
                config_sha256=require_str(record, "config_sha256"),
                binary_identities=binaries,
                boundary_identity=cast(Mapping[str, object], raw_boundary),
                metadata_sha256=require_str(record, "metadata_sha256"),
            )
        except (MultiHarnessValidationError, TypeError, ValueError) as exc:
            raise RunMetadataError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ReceiptMetadataBinding:
    """Sidecar binding from an existing receipt to run-start metadata."""

    receipt_id: str
    receipt_public_sha256: str
    run_metadata_sha256: str
    run_spec_sha256: str
    config_sha256: str
    boundary_identity_sha256: str
    binary_identity_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.receipt_id, "receipt_id")
        for name in (
            "receipt_public_sha256",
            "run_metadata_sha256",
            "run_spec_sha256",
            "config_sha256",
            "boundary_identity_sha256",
            "binary_identity_sha256",
        ):
            _require_prefixed_digest(getattr(self, name), name)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": RECEIPT_METADATA_BINDING_SCHEMA_VERSION,
            "receipt_id": self.receipt_id,
            "receipt_public_sha256": self.receipt_public_sha256,
            "run_metadata_sha256": self.run_metadata_sha256,
            "run_spec_sha256": self.run_spec_sha256,
            "config_sha256": self.config_sha256,
            "boundary_identity_sha256": self.boundary_identity_sha256,
            "binary_identity_sha256": self.binary_identity_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        try:
            require_known_fields(
                record,
                required=_BINDING_FIELDS,
                field_name="receipt metadata binding",
            )
            if require_str(record, "schema_version") != (
                RECEIPT_METADATA_BINDING_SCHEMA_VERSION
            ):
                raise RunMetadataError("unsupported receipt metadata binding schema")
            return cls(
                receipt_id=require_str(record, "receipt_id"),
                receipt_public_sha256=require_str(record, "receipt_public_sha256"),
                run_metadata_sha256=require_str(record, "run_metadata_sha256"),
                run_spec_sha256=require_str(record, "run_spec_sha256"),
                config_sha256=require_str(record, "config_sha256"),
                boundary_identity_sha256=require_str(
                    record, "boundary_identity_sha256"
                ),
                binary_identity_sha256=require_str(record, "binary_identity_sha256"),
            )
        except (MultiHarnessValidationError, TypeError) as exc:
            raise RunMetadataError(str(exc)) from exc


def build_private_run_metadata(
    *,
    run_id: str,
    run_spec: RunSpec | str,
    executable_identities: Sequence[BinaryRunIdentity | ObservedExecutableIdentity],
    boundary_identity: Mapping[str, object],
    config_records: Mapping[str, object],
    started_at_utc: str | None = None,
) -> PrivateRunMetadata:
    """Create run-start metadata and derive its receipt-bound config hash."""

    spec_sha256 = run_spec.spec_sha256 if isinstance(run_spec, RunSpec) else run_spec
    _require_prefixed_digest(spec_sha256, "run_spec_sha256")
    binaries = tuple(
        identity
        if isinstance(identity, BinaryRunIdentity)
        else BinaryRunIdentity.from_observed(identity)
        for identity in executable_identities
    )
    if not binaries:
        raise RunMetadataError("executable_identities must not be empty")
    hashes = {
        name: _record_or_digest(record, f"config_records[{name}]")
        for name, record in config_records.items()
    }
    _validate_hash_map(hashes, "config_hashes")
    config_sha256 = _digest({"config_hashes": dict(sorted(hashes.items()))})
    timestamp = started_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    content = {
        "schema_version": RUN_METADATA_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at_utc": timestamp,
        "run_spec_sha256": spec_sha256,
        "config_hashes": dict(sorted(hashes.items())),
        "config_sha256": config_sha256,
        "binary_identities": [item.to_record() for item in binaries],
        "boundary_identity": _canonical_value(boundary_identity),
    }
    return PrivateRunMetadata(
        run_id=run_id,
        started_at_utc=timestamp,
        run_spec_sha256=spec_sha256,
        config_hashes=hashes,
        config_sha256=config_sha256,
        binary_identities=binaries,
        boundary_identity=dict(boundary_identity),
        metadata_sha256=_digest(content),
    )


def bind_execution_receipt(
    receipt: ExecutionReceipt,
    metadata: PrivateRunMetadata,
) -> ReceiptMetadataBinding:
    """Require existing receipt config/spec fields to carry metadata identity."""

    if receipt.spec_sha256 != metadata.run_spec_sha256:
        raise RunMetadataError("receipt spec_sha256 does not match run metadata")
    if receipt.config_sha256 != metadata.config_sha256:
        raise RunMetadataError("receipt config_sha256 does not match run metadata")
    return ReceiptMetadataBinding(
        receipt_id=receipt.receipt_id,
        receipt_public_sha256=receipt.public_sha256(),
        run_metadata_sha256=metadata.metadata_sha256,
        run_spec_sha256=metadata.run_spec_sha256,
        config_sha256=metadata.config_sha256,
        boundary_identity_sha256=_digest(metadata.boundary_identity),
        binary_identity_sha256=_digest(
            {
                "binary_identities": [
                    item.to_record() for item in metadata.binary_identities
                ]
            }
        ),
    )


def verify_receipt_metadata_binding(
    receipt: ExecutionReceipt,
    metadata: PrivateRunMetadata,
    binding: ReceiptMetadataBinding,
) -> None:
    """Verify a receipt and sidecar still point to the same private run."""

    expected = bind_execution_receipt(receipt, metadata)
    if binding != expected:
        raise RunMetadataError("receipt metadata binding does not match receipt")


def write_private_run_metadata(path: Path, metadata: PrivateRunMetadata) -> None:
    """Write a fresh metadata file with restrictive permissions and no overwrite."""

    if path.exists() or path.is_symlink():
        raise RunMetadataError("private run metadata path must be fresh")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(metadata.to_record()) + b"\n"
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as exc:
        raise RunMetadataError("could not create private run metadata") from exc
    try:
        os.write(descriptor, payload)
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def _record_or_digest(record: object, field_name: str) -> str:
    if isinstance(record, str):
        try:
            return validate_sha256(record, field_name)
        except MultiHarnessValidationError as exc:
            raise RunMetadataError(str(exc)) from exc
    if not isinstance(record, Mapping):
        raise RunMetadataError(f"{field_name} must be a JSON object or SHA-256 digest")
    return _digest(cast(Mapping[str, object], record))


def _validate_hash_map(values: Mapping[Any, Any], field_name: str) -> None:
    for name, value in values.items():
        if not isinstance(name, str) or not name.strip():
            raise RunMetadataError(f"{field_name} keys must be non-empty strings")
        _require_prefixed_digest(value, f"{field_name}[{name}]")


def _require_prefixed_digest(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise RunMetadataError(f"{field_name} must be a SHA-256 digest")
    try:
        validate_sha256(value, field_name, allow_prefix=True)
    except MultiHarnessValidationError as exc:
        raise RunMetadataError(str(exc)) from exc
    if not value.startswith("sha256:"):
        raise RunMetadataError(f"{field_name} must use the sha256: prefix")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise RunMetadataError(f"{field_name} must be non-empty")


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if type(value) is not str:
        raise RunMetadataError(f"{field_name} must be a string or null")
    return value


def _canonical_value(value: Mapping[str, object]) -> Mapping[str, object]:
    encoded = json.loads(_canonical_json(value).decode("utf-8"))
    if not isinstance(encoded, Mapping):
        raise RunMetadataError("canonical metadata value must be an object")
    return cast(Mapping[str, object], encoded)


def _canonical_json(value: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RunMetadataError("metadata must contain canonical JSON values") from exc


def _digest(value: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()
