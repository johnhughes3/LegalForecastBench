"""Verification for canonical complete screening-snapshot reconciliation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    SnapshotVerificationError,
    verify_snapshot,
)

_SNAPSHOT_SCHEMA = "legalforecast-cycle-acquisition-v1"
_SUMMARY_FIELDS = {
    "accepted_count",
    "batch_id",
    "excluded_count",
    "processed_count",
    "reconciliation_complete",
}
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class SnapshotReconciliationError(ValueError):
    """Raised when snapshot discovery evidence is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class SnapshotReconciliation:
    """Counts and immutable identity verified from one saturated snapshot."""

    accepted_count: int
    excluded_count: int
    processed_count: int
    cycle_hash: str
    batch_id: str
    batch_digest: str
    snapshot_id: str
    manifest_sha256: str
    cycle_store_path: str

    def to_record(self) -> dict[str, object]:
        """Return the immutable snapshot identity recorded by final readiness."""

        return {
            "accepted_count": self.accepted_count,
            "excluded_count": self.excluded_count,
            "processed_count": self.processed_count,
            "cycle_hash": self.cycle_hash,
            "batch_id": self.batch_id,
            "batch_digest": self.batch_digest,
            "snapshot_id": self.snapshot_id,
            "manifest_sha256": self.manifest_sha256,
            "cycle_store_path": self.cycle_store_path,
        }


def verify_saturated_snapshot_reconciliation(
    *,
    manifest_path: Path,
    summary_path: Path,
    screened_cases_path: Path,
    exclusions_path: Path,
    cycle_store_path: Path,
    expected_snapshot_path: Path,
    expected_manifest_sha256: str,
    expected_cycle_hash: str,
    expected_batch_digest: str,
) -> SnapshotReconciliation:
    """Verify exact snapshot members and return their normalized reconciliation."""

    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise SnapshotReconciliationError(
            "screening snapshot manifest is not a regular file"
        )
    snapshot_root = manifest_path.parent
    if _absolute_path(snapshot_root) != _absolute_path(expected_snapshot_path):
        raise SnapshotReconciliationError(
            "screening snapshot path differs from the authenticated target cohort"
        )
    expected_paths = {
        "manifest.json": manifest_path,
        "summary.json": summary_path,
        "screened-cases.jsonl": screened_cases_path,
        "exclusions.jsonl": exclusions_path,
    }
    for member_name, supplied_path in expected_paths.items():
        canonical_path = snapshot_root / member_name
        if _absolute_path(supplied_path) != _absolute_path(canonical_path):
            raise SnapshotReconciliationError(
                f"{member_name} must be supplied from the manifest's canonical "
                "snapshot directory"
            )
    try:
        canonical_manifest = verify_snapshot(
            snapshot_root,
            require_complete=True,
            require_saturated=True,
        )
    except SnapshotVerificationError as exc:
        raise SnapshotReconciliationError(
            f"canonical screening snapshot verification failed: {exc}"
        ) from exc

    manifest = canonical_manifest
    if manifest.get("schema_version") != _SNAPSHOT_SCHEMA:
        raise SnapshotReconciliationError(
            "screening snapshot manifest schema_version is unsupported"
        )
    if manifest.get("complete") is not True:
        raise SnapshotReconciliationError("screening snapshot is not complete")
    if manifest.get("saturated") is not True:
        raise SnapshotReconciliationError("screening snapshot is not saturated")

    cycle_hash = _required_sha256(manifest, "cycle_hash")
    batch_digest = _required_sha256(manifest, "batch_digest")
    batch_id = _required_text(manifest, "batch_id")
    snapshot_id = _required_text(manifest, "snapshot_id")
    manifest_sha256 = _sha256_file(manifest_path)
    if manifest_sha256 != _normalize_sha256(
        expected_manifest_sha256,
        "expected_manifest_sha256",
    ):
        raise SnapshotReconciliationError(
            "screening snapshot manifest differs from the authenticated target cohort"
        )
    if cycle_hash != _normalize_sha256(expected_cycle_hash, "expected_cycle_hash"):
        raise SnapshotReconciliationError(
            "screening snapshot cycle hash differs from the authenticated target cohort"
        )
    if batch_digest != _normalize_sha256(
        expected_batch_digest,
        "expected_batch_digest",
    ):
        raise SnapshotReconciliationError(
            "screening snapshot batch digest differs from the authenticated "
            "target cohort"
        )
    files = _required_mapping(manifest, "files")
    _verify_member(
        files,
        member_name="screened-cases.jsonl",
        path=screened_cases_path,
        jsonl=True,
    )
    _verify_member(
        files,
        member_name="exclusions.jsonl",
        path=exclusions_path,
        jsonl=True,
    )
    _verify_member(
        files,
        member_name="summary.json",
        path=summary_path,
        jsonl=False,
    )

    summary = _read_object(summary_path, label="screening snapshot summary")
    if set(summary) != _SUMMARY_FIELDS:
        raise SnapshotReconciliationError(
            "screening snapshot summary does not use the canonical "
            "saturated-snapshot shape"
        )
    accepted_count = _required_nonnegative_int(summary, "accepted_count")
    excluded_count = _required_nonnegative_int(summary, "excluded_count")
    processed_count = _required_nonnegative_int(summary, "processed_count")
    if summary.get("reconciliation_complete") is not True:
        raise SnapshotReconciliationError(
            "screening snapshot reconciliation is incomplete"
        )
    if _required_text(summary, "batch_id") != batch_id:
        raise SnapshotReconciliationError(
            "screening snapshot summary batch_id does not match manifest"
        )
    if processed_count != accepted_count + excluded_count:
        raise SnapshotReconciliationError(
            "screening snapshot processed_count must equal accepted plus excluded"
        )
    _require_manifest_row_count(
        files,
        member_name="screened-cases.jsonl",
        expected=accepted_count,
    )
    _require_manifest_row_count(
        files,
        member_name="exclusions.jsonl",
        expected=excluded_count,
    )
    _require_manifest_row_count(files, member_name="summary.json", expected=1)
    _verify_store_registration(
        cycle_store_path=cycle_store_path,
        snapshot_root=snapshot_root,
        snapshot_id=snapshot_id,
        batch_id=batch_id,
    )
    return SnapshotReconciliation(
        accepted_count=accepted_count,
        excluded_count=excluded_count,
        processed_count=processed_count,
        cycle_hash=cycle_hash,
        batch_id=batch_id,
        batch_digest=batch_digest,
        snapshot_id=snapshot_id,
        manifest_sha256=manifest_sha256,
        cycle_store_path=str(_absolute_path(cycle_store_path)),
    )


def _verify_member(
    files: Mapping[str, Any],
    *,
    member_name: str,
    path: Path,
    jsonl: bool,
) -> None:
    descriptor = _required_mapping(files, member_name)
    expected_sha256 = _required_sha256(descriptor, "sha256")
    expected_bytes = _required_nonnegative_int(descriptor, "byte_count")
    expected_rows = _required_nonnegative_int(descriptor, "row_count")
    if not path.is_file() or path.is_symlink():
        raise SnapshotReconciliationError(
            f"snapshot member is not a regular file: {member_name}"
        )
    if _sha256_file(path) != expected_sha256:
        raise SnapshotReconciliationError(
            f"snapshot member hash mismatch: {member_name}"
        )
    if path.stat().st_size != expected_bytes:
        raise SnapshotReconciliationError(
            f"snapshot member byte count mismatch: {member_name}"
        )
    actual_rows = (
        sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)
        if jsonl
        else 1
    )
    if actual_rows != expected_rows:
        raise SnapshotReconciliationError(
            f"snapshot member row count mismatch: {member_name}"
        )


def _require_manifest_row_count(
    files: Mapping[str, Any],
    *,
    member_name: str,
    expected: int,
) -> None:
    descriptor = _required_mapping(files, member_name)
    if _required_nonnegative_int(descriptor, "row_count") != expected:
        raise SnapshotReconciliationError(
            f"snapshot member row count does not reconcile: {member_name}"
        )


def _read_object(path: Path, *, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotReconciliationError(f"{label} is unreadable or invalid") from exc
    if not isinstance(value, dict):
        raise SnapshotReconciliationError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _required_mapping(record: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise SnapshotReconciliationError(f"{key} must be a JSON object")
    return cast(dict[str, Any], value)


def _required_text(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SnapshotReconciliationError(f"{key} must be a non-empty string")
    return value.strip()


def _required_sha256(record: Mapping[str, Any], key: str) -> str:
    value = _required_text(record, key)
    if _SHA256_RE.fullmatch(value) is None:
        raise SnapshotReconciliationError(f"{key} must be a lowercase SHA-256 digest")
    return value


def _required_nonnegative_int(record: Mapping[str, Any], key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SnapshotReconciliationError(f"{key} must be a nonnegative integer")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_sha256(value: str, label: str) -> str:
    normalized = value.removeprefix("sha256:")
    if _SHA256_RE.fullmatch(normalized) is None:
        raise SnapshotReconciliationError(f"{label} must be a lowercase SHA-256 digest")
    return normalized


def _verify_store_registration(
    *,
    cycle_store_path: Path,
    snapshot_root: Path,
    snapshot_id: str,
    batch_id: str,
) -> None:
    if not cycle_store_path.is_file() or cycle_store_path.is_symlink():
        raise SnapshotReconciliationError("screening cycle store is not a regular file")
    try:
        with CycleAcquisitionStore(cycle_store_path) as store:
            registered = store.existing_complete_snapshot(
                snapshot_root.parent,
                snapshot_id=snapshot_id,
                batch_id=batch_id,
            )
    except (CycleAcquisitionStoreError, OSError, ValueError) as exc:
        raise SnapshotReconciliationError(
            f"screening snapshot store registration verification failed: {exc}"
        ) from exc
    if registered is None:
        raise SnapshotReconciliationError(
            "screening snapshot is not registered in the cycle store"
        )


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))
