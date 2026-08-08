"""Bounded Firecrawl recovery of raw docket HTML missing from an exact target.

This is deliberately narrower than the public-document gap bridge: it never
plans a document download or a purchase.  It creates a fresh, same-cycle
Firecrawl batch whose only output is screening-compatible, pagination-proven
raw docket HTML for selected target cases absent from a pinned source manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from legalforecast.contracts import (
    TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
)
from legalforecast.ingestion.budgeted_docket_acquisition import (
    BudgetedDocketAcquisitionError,
    acquire_ranked_dockets,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import BudgetedFirecrawlScheduler
from legalforecast.ingestion.cycle_acquisition_store import (
    SnapshotVerificationError,
    verify_snapshot,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    snapshot_firecrawl_screening_source_count,
)

TARGET_RAW_DOCKET_RECOVERY_PLAN_SCHEMA = str(TARGET_RAW_DOCKET_RECOVERY_PLAN_V1)
TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA = str(TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1)
TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA = str(TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1)
TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA = str(
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DOCKET_ID = re.compile(r"[1-9][0-9]*\Z")
_CANDIDATE_PREFIX = "courtlistener-docket-"


class TargetRawDocketRecoveryError(ValueError):
    """Raised when exact-target raw recovery cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class TargetRawDocketRecoveryPlan:
    selection_path: str
    selection_sha256: str
    source_snapshot_path: str
    source_snapshot_manifest_sha256: str
    source_snapshot_screened_cases_sha256: str
    cycle_hash: str
    source_batch_id: str
    source_batch_digest: str
    source_snapshot_run_card_path: str
    source_snapshot_run_card_sha256: str
    source_raw_manifest_path: str
    source_raw_manifest_sha256: str
    cycle_store_path: str
    batch_id: str
    run_id: str
    credit_cap: int
    workers: int
    max_pages_per_docket: int
    max_attempts_per_page: int
    provider_breaker_threshold: int
    proxy: str
    force_browser: bool
    targets: tuple[Mapping[str, object], ...]

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": TARGET_RAW_DOCKET_RECOVERY_PLAN_SCHEMA,
            **asdict(self),
            "target_count": len(self.targets),
        }


def _read_jsonl_bytes(
    payload: bytes, label: str, *, allow_empty: bool = False
) -> list[Mapping[str, Any]]:
    try:
        lines = payload.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(f"{label} is not JSONL") from exc
    if (not rows and not allow_empty) or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise TargetRawDocketRecoveryError(f"{label} is empty or malformed")
    return cast(list[Mapping[str, Any]], rows)


def _read_unique_regular_file(path: Path, label: str) -> bytes:
    """Read one stable unique file without following any path component."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise TargetRawDocketRecoveryError(f"{label} requires no-follow support")
    absolute = Path(os.path.abspath(path))
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | nofollow
    file_flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | nofollow
    directory_fd: int | None = None
    descriptor: int | None = None
    try:
        directory_fd = os.open(absolute.anchor, directory_flags)
        for component in absolute.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        descriptor = os.open(absolute.name, file_flags, dir_fd=directory_fd)
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        if directory_fd is not None:
            os.close(directory_fd)
        raise TargetRawDocketRecoveryError(
            f"{label} is not a singly linked regular file"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise TargetRawDocketRecoveryError(
                f"{label} is not a singly linked regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_mode, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
        ) or after.st_nlink != 1:
            raise TargetRawDocketRecoveryError(f"{label} changed while reading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)
        os.close(directory_fd)


def _pinned_bytes(path: Path, expected: str, label: str) -> bytes:
    if _SHA256.fullmatch(expected) is None:
        raise TargetRawDocketRecoveryError(f"{label} SHA-256 is invalid")
    payload = _read_unique_regular_file(path, label)
    if hashlib.sha256(payload).hexdigest() != expected:
        raise TargetRawDocketRecoveryError(f"{label} SHA-256 mismatch")
    return payload


def _pinned_sha(path: Path, expected: str, label: str) -> str:
    _pinned_bytes(path, expected, label)
    return expected


def _require_snapshot_payload_commitment(
    manifest: Mapping[str, Any], filename: str, payload: bytes
) -> None:
    files_value = manifest.get("files")
    files = (
        cast(Mapping[str, object], files_value)
        if isinstance(files_value, Mapping)
        else None
    )
    commitment_value = files.get(filename) if files is not None else None
    commitment = (
        cast(Mapping[str, object], commitment_value)
        if isinstance(commitment_value, Mapping)
        else None
    )
    if not isinstance(commitment, Mapping) or (
        commitment.get("sha256") != hashlib.sha256(payload).hexdigest()
        or commitment.get("byte_count") != len(payload)
        or commitment.get("row_count") != payload.count(b"\n")
    ):
        raise TargetRawDocketRecoveryError(
            f"source snapshot commitment mismatch: {filename}"
        )


def _require_no_symlink_components(path: Path, label: str) -> None:
    normalized = Path(os.path.abspath(path))
    for candidate in (normalized, *normalized.parents):
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise TargetRawDocketRecoveryError(
                f"cannot inspect {label}: {candidate}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise TargetRawDocketRecoveryError(f"{label} contains a symlink")


def _validated_courtlistener_docket_url(*, docket_id: str, value: object) -> str:
    if not isinstance(value, str):
        raise TargetRawDocketRecoveryError(
            f"selected target has invalid CourtListener URL: {docket_id}"
        )
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise TargetRawDocketRecoveryError(
            f"selected target has invalid CourtListener URL: {docket_id}"
        ) from exc
    components = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.courtlistener.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or len(components) < 2
        or components[0] != "docket"
        or components[1] != docket_id
    ):
        raise TargetRawDocketRecoveryError(
            f"selected URL docket does not match candidate ID: {docket_id}"
        )
    return value


def _validated_target_map(
    targets: tuple[object, ...],
) -> dict[str, Mapping[str, object]]:
    """Return canonical planned targets before provider activity."""

    target_by_docket: dict[str, Mapping[str, object]] = {}
    for target in targets:
        if not isinstance(target, Mapping):
            raise TargetRawDocketRecoveryError("plan target is malformed")
        target_record = cast(Mapping[str, object], target)
        candidate_id = target_record.get("candidate_id")
        identity_value = target_record.get("identity")
        screening_metadata_value = target_record.get("screening_metadata")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(identity_value, Mapping)
            or not isinstance(screening_metadata_value, Mapping)
        ):
            raise TargetRawDocketRecoveryError("plan target is malformed")
        identity = cast(Mapping[str, object], identity_value)
        docket_id = identity.get("courtlistener_docket_id")
        if not isinstance(docket_id, str) or _DOCKET_ID.fullmatch(docket_id) is None:
            raise TargetRawDocketRecoveryError("plan target has invalid docket ID")
        if candidate_id != _CANDIDATE_PREFIX + docket_id:
            raise TargetRawDocketRecoveryError("plan target candidate ID mismatch")
        source_url = _validated_courtlistener_docket_url(
            docket_id=docket_id,
            value=identity.get("courtlistener_url"),
        )
        screening_metadata = cast(Mapping[str, object], screening_metadata_value)
        if (
            screening_metadata.get("candidate_id") != docket_id
            or screening_metadata.get("source_url") != source_url
            or docket_id in target_by_docket
        ):
            raise TargetRawDocketRecoveryError("plan target metadata is malformed")
        target_by_docket[docket_id] = target_record
    if not target_by_docket:
        raise TargetRawDocketRecoveryError("plan contains no targets")
    return target_by_docket


def _parse_completed_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed


def _open_raw_html_directory(raw_html_dir: Path) -> int:
    """Open one real raw-artifact directory without following its leaf link."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise TargetRawDocketRecoveryError(
            "recovery raw HTML directory requires no-follow support"
        )
    absolute = Path(os.path.abspath(raw_html_dir))
    flags = os.O_RDONLY | os.O_CLOEXEC | nofollow | directory
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            try:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise TargetRawDocketRecoveryError(
                "recovery raw HTML directory is not a real directory"
            )
    except (OSError, TargetRawDocketRecoveryError) as exc:
        if descriptor is not None:
            os.close(descriptor)
        if isinstance(exc, TargetRawDocketRecoveryError):
            raise
        raise TargetRawDocketRecoveryError(
            "recovery raw HTML directory is not a real directory"
        ) from exc
    return descriptor


def _read_unique_raw_html(
    directory_fd: int, filename: str, *, label: str
) -> bytes | None:
    """Read one stable, singly-linked regular child through a directory FD."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise TargetRawDocketRecoveryError(
            "recovery raw HTML requires no-follow support"
        )
    try:
        descriptor = os.open(
            filename,
            os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | nofollow,
            dir_fd=directory_fd,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise TargetRawDocketRecoveryError(
            f"{label} is not a singly linked regular file"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise TargetRawDocketRecoveryError(
                f"{label} is not a singly linked regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read()
        after = os.fstat(descriptor)
        lexical = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
        if (before.st_dev, before.st_ino, before.st_nlink) != (
            after.st_dev,
            after.st_ino,
            after.st_nlink,
        ) or (after.st_dev, after.st_ino, after.st_nlink) != (
            lexical.st_dev,
            lexical.st_ino,
            lexical.st_nlink,
        ):
            raise TargetRawDocketRecoveryError(f"{label} changed while reading")
        return payload
    finally:
        os.close(descriptor)


def _publish_unique_raw_html(
    directory_fd: int, filename: str, payload: bytes, *, label: str
) -> None:
    """Publish immutable raw HTML or prove the existing child has identical bytes."""

    existing = _read_unique_raw_html(directory_fd, filename, label=label)
    if existing is not None:
        if existing != payload:
            raise TargetRawDocketRecoveryError(
                "raw output already exists with different bytes: "
                f"{filename.removesuffix('.html')}"
            )
        return
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise TargetRawDocketRecoveryError(
            "recovery raw HTML requires no-follow support"
        )
    temporary_name = f".{filename}.{uuid.uuid4().hex}.tmp"
    descriptor: int | None = None
    temporary_created = False
    try:
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | nofollow,
            0o600,
            dir_fd=directory_fd,
        )
        temporary_created = True
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short raw HTML write")
            view = view[written:]
        os.fsync(descriptor)
        temporary_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(temporary_metadata.st_mode)
            or temporary_metadata.st_nlink != 1
        ):
            raise TargetRawDocketRecoveryError(
                f"{label} temporary output is not a singly linked regular file"
            )
        try:
            os.link(
                temporary_name,
                filename,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            existing = _read_unique_raw_html(directory_fd, filename, label=label)
            if existing != payload:
                raise TargetRawDocketRecoveryError(
                    "raw output already exists with different bytes: "
                    f"{filename.removesuffix('.html')}"
                ) from None
        else:
            os.unlink(temporary_name, dir_fd=directory_fd)
            temporary_created = False
            os.fsync(directory_fd)
        published = _read_unique_raw_html(directory_fd, filename, label=label)
        if published != payload:
            raise TargetRawDocketRecoveryError(f"{label} changed while publishing")
    except OSError as exc:
        raise TargetRawDocketRecoveryError(f"cannot publish {label}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass


def verify_target_raw_docket_recovery_receipt(
    *,
    receipt_path: Path,
    expected_receipt_sha256: str,
    expected_plan_sha256: str,
    successes_path: Path,
    exclusions_path: Path,
    summary_path: Path,
    raw_html_dir: Path,
) -> Mapping[str, Any]:
    """Authenticate the exact recovery-to-screen handoff."""

    receipt_payload = _pinned_bytes(
        receipt_path, expected_receipt_sha256, "recovery receipt"
    )
    successes_payload = _read_unique_regular_file(successes_path, "recovery successes")
    exclusions_payload = _read_unique_regular_file(
        exclusions_path, "recovery exclusions"
    )
    summary_payload = _read_unique_regular_file(summary_path, "recovery summary")
    _require_no_symlink_components(raw_html_dir, "recovery raw HTML directory")
    try:
        receipt_value = json.loads(
            receipt_payload,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
        summary_value = json.loads(
            summary_payload,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise TargetRawDocketRecoveryError(
            "recovery receipt or summary is not canonical JSON"
        ) from exc
    if not isinstance(receipt_value, Mapping) or not isinstance(summary_value, Mapping):
        raise TargetRawDocketRecoveryError("recovery receipt or summary is malformed")
    receipt = cast(Mapping[str, Any], receipt_value)
    summary = cast(Mapping[str, Any], summary_value)
    if (
        receipt.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA
        or receipt.get("dry_run") is not False
        or receipt.get("plan_sha256") != expected_plan_sha256
    ):
        raise TargetRawDocketRecoveryError(
            "recovery receipt does not bind the executed plan"
        )
    expected_paths = {
        "successes_path": successes_path,
        "exclusions_path": exclusions_path,
        "summary_path": summary_path,
        "raw_html_dir": raw_html_dir,
    }
    if any(
        receipt.get(field) != str(path.resolve())
        for field, path in expected_paths.items()
    ):
        raise TargetRawDocketRecoveryError("recovery receipt output path mismatch")
    for field, payload in (
        ("successes_sha256", successes_payload),
        ("exclusions_sha256", exclusions_payload),
        ("summary_sha256", summary_payload),
    ):
        if receipt.get(field) != hashlib.sha256(payload).hexdigest():
            raise TargetRawDocketRecoveryError(
                f"recovery receipt {field} commitment mismatch"
            )
    successes = _read_jsonl_bytes(
        successes_payload, "recovery successes", allow_empty=True
    )
    exclusions = _read_jsonl_bytes(
        exclusions_payload, "recovery exclusions", allow_empty=True
    )
    success_count = summary.get("success_count")
    exclusion_count = summary.get("exclusion_count")
    if (
        summary.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA
        or not isinstance(success_count, int)
        or isinstance(success_count, bool)
        or not isinstance(exclusion_count, int)
        or isinstance(exclusion_count, bool)
        or success_count != len(successes)
        or exclusion_count != len(exclusions)
    ):
        raise TargetRawDocketRecoveryError("recovery summary contract is invalid")
    expected_provenance = {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA,
        "plan_sha256": expected_plan_sha256,
        "batch_id": receipt.get("batch_id"),
        "run_id": receipt.get("run_id"),
    }
    if any(
        record.get("target_raw_docket_recovery") != expected_provenance
        for record in (*successes, *exclusions)
    ):
        raise TargetRawDocketRecoveryError(
            "recovery terminal record provenance mismatch"
        )
    receipt_artifacts = receipt.get("raw_artifacts")
    summary_artifacts = summary.get("raw_artifacts")
    if (
        not isinstance(receipt_artifacts, list)
        or receipt_artifacts != summary_artifacts
    ):
        raise TargetRawDocketRecoveryError(
            "recovery receipt raw-artifact commitment mismatch"
        )
    projected: list[Mapping[str, object]] = []
    seen_candidates: set[str] = set()
    for record in successes:
        candidate_id = record.get("candidate_id")
        docket_id = record.get("docket_id")
        sha256 = record.get("raw_html_sha256")
        byte_count = record.get("raw_html_bytes")
        retrieved_at = record.get("retrieved_at")
        raw_path_value = record.get("raw_html_path")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(docket_id, str)
            or _DOCKET_ID.fullmatch(docket_id) is None
            or candidate_id != _CANDIDATE_PREFIX + docket_id
            or candidate_id in seen_candidates
            or not isinstance(sha256, str)
            or _SHA256.fullmatch(sha256.removeprefix("sha256:")) is None
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or not isinstance(retrieved_at, str)
            or not retrieved_at
            or not isinstance(raw_path_value, str)
        ):
            raise TargetRawDocketRecoveryError(
                "recovery success has malformed raw-artifact commitment"
            )
        seen_candidates.add(candidate_id)
        raw_path = raw_html_dir / f"{docket_id}.html"
        if Path(raw_path_value).resolve() != raw_path.resolve():
            raise TargetRawDocketRecoveryError("recovery success raw path mismatch")
        raw = _read_unique_regular_file(raw_path, f"recovery raw HTML {candidate_id}")
        if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != (
            sha256.removeprefix("sha256:")
        ):
            raise TargetRawDocketRecoveryError(
                f"recovery raw HTML commitment mismatch: {candidate_id}"
            )
        projected.append(
            {
                "candidate_id": candidate_id,
                "sha256": sha256,
                "byte_count": byte_count,
                "retrieved_at": retrieved_at,
            }
        )
    if receipt_artifacts != projected:
        raise TargetRawDocketRecoveryError(
            "recovery receipt does not match success raw artifacts"
        )
    return receipt


def build_target_raw_docket_recovery_plan(
    *,
    selection_path: Path,
    expected_selection_sha256: str,
    source_snapshot_path: Path,
    expected_source_snapshot_manifest_sha256: str,
    expected_cycle_hash: str,
    source_snapshot_run_card_path: Path,
    expected_source_snapshot_run_card_sha256: str,
    source_raw_manifest_path: Path,
    expected_source_raw_manifest_sha256: str,
    cycle_store_path: Path,
    batch_id: str,
    run_id: str,
    credit_cap: int,
    workers: int,
    max_pages_per_docket: int,
    max_attempts_per_page: int,
    provider_breaker_threshold: int,
    proxy: str,
    force_browser: bool,
) -> TargetRawDocketRecoveryPlan:
    """Derive exactly selected-minus-raw targets from three pinned inputs."""

    selection_payload = _pinned_bytes(
        selection_path, expected_selection_sha256, "selection"
    )
    selection_sha = expected_selection_sha256
    card_payload = _pinned_bytes(
        source_snapshot_run_card_path,
        expected_source_snapshot_run_card_sha256,
        "source snapshot run card",
    )
    card_sha = expected_source_snapshot_run_card_sha256
    snapshot_manifest_path = source_snapshot_path / "manifest.json"
    snapshot_manifest_payload = _pinned_bytes(
        snapshot_manifest_path,
        expected_source_snapshot_manifest_sha256,
        "source snapshot manifest",
    )
    try:
        captured_manifest_value = json.loads(snapshot_manifest_payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "source snapshot manifest is not JSON"
        ) from exc
    if not isinstance(captured_manifest_value, Mapping):
        raise TargetRawDocketRecoveryError("source snapshot manifest is malformed")
    captured_manifest = cast(Mapping[str, Any], captured_manifest_value)
    try:
        manifest = verify_snapshot(
            source_snapshot_path,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
        snapshot_firecrawl_screening_source_count(manifest, require_current=True)
    except (SnapshotVerificationError, ValueError) as exc:
        raise TargetRawDocketRecoveryError(
            f"source snapshot is not current complete and saturated: {exc}"
        ) from exc
    if manifest != captured_manifest:
        raise TargetRawDocketRecoveryError(
            "source snapshot manifest changed during verification"
        )
    source_batch_id = captured_manifest.get("batch_id")
    source_batch_digest = captured_manifest.get("batch_digest")
    if (
        not isinstance(source_batch_id, str)
        or not source_batch_id
        or not isinstance(source_batch_digest, str)
        or _SHA256.fullmatch(source_batch_digest) is None
    ):
        raise TargetRawDocketRecoveryError(
            "source snapshot has invalid batch authority"
        )
    snapshot_manifest_sha = expected_source_snapshot_manifest_sha256
    screened_path = source_snapshot_path / "screened-cases.jsonl"
    screened_payload = _read_unique_regular_file(
        screened_path, "source snapshot screened-cases"
    )
    _require_snapshot_payload_commitment(
        captured_manifest, "screened-cases.jsonl", screened_payload
    )
    screened_sha = hashlib.sha256(screened_payload).hexdigest()
    screened_by_candidate: dict[str, Mapping[str, Any]] = {}
    for screened in _read_jsonl_bytes(
        screened_payload, "source snapshot screened-cases"
    ):
        candidate = screened.get("candidate_id")
        if isinstance(candidate, str):
            if candidate in screened_by_candidate:
                raise TargetRawDocketRecoveryError(
                    f"source snapshot repeats screened candidate: {candidate}"
                )
            screened_by_candidate[candidate] = screened
    canonical_raw_manifest = source_snapshot_path / "raw-artifacts.jsonl"
    if source_raw_manifest_path.resolve() != canonical_raw_manifest.resolve():
        raise TargetRawDocketRecoveryError(
            "source raw manifest is not the authenticated snapshot raw-artifacts.jsonl"
        )
    raw_payload = _pinned_bytes(
        canonical_raw_manifest,
        expected_source_raw_manifest_sha256,
        "source raw manifest",
    )
    _require_snapshot_payload_commitment(
        captured_manifest, "raw-artifacts.jsonl", raw_payload
    )
    raw_sha = expected_source_raw_manifest_sha256
    try:
        card = json.loads(card_payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "source snapshot run card is not JSON"
        ) from exc
    if not isinstance(card, dict):
        raise TargetRawDocketRecoveryError("source snapshot run card is not completed")
    typed_card = cast(dict[str, object], card)
    if typed_card.get("status") != "completed":
        raise TargetRawDocketRecoveryError("source snapshot run card is not completed")
    card_snapshot = typed_card.get("snapshot_path")
    if (
        not isinstance(card_snapshot, str)
        or Path(card_snapshot).resolve() != source_snapshot_path.resolve()
    ):
        raise TargetRawDocketRecoveryError(
            "source snapshot run card does not bind source snapshot"
        )
    if not batch_id.strip() or not run_id.strip() or batch_id == run_id:
        raise TargetRawDocketRecoveryError(
            "batch and run identities must be nonempty and distinct"
        )
    if (
        not 1 <= credit_cap <= 500
        or not 1 <= workers <= 10
        or not 1 <= max_pages_per_docket <= 100
    ):
        raise TargetRawDocketRecoveryError(
            "credit cap, workers, or page limit is out of bounds"
        )
    if (
        max_attempts_per_page <= 0
        or provider_breaker_threshold <= 0
        or proxy not in {"basic", "auto", "enhanced"}
    ):
        raise TargetRawDocketRecoveryError("scheduler configuration is invalid")

    selected: dict[str, Mapping[str, Any]] = {}
    for row in _read_jsonl_bytes(selection_payload, "selection"):
        if row.get("selected") is not True:
            continue
        docket_id = row.get("candidate_id")
        source_url = row.get("source_url")
        if not isinstance(docket_id, str) or _DOCKET_ID.fullmatch(docket_id) is None:
            raise TargetRawDocketRecoveryError(
                "selected target has invalid candidate ID"
            )
        candidate_id = _CANDIDATE_PREFIX + docket_id
        source_url = _validated_courtlistener_docket_url(
            docket_id=docket_id, value=source_url
        )
        snapshot_source = screened_by_candidate.get(candidate_id)
        snapshot_candidate_value = (
            snapshot_source.get("candidate")
            if isinstance(snapshot_source, Mapping)
            else None
        )
        snapshot_candidate = (
            cast(Mapping[str, Any], snapshot_candidate_value)
            if isinstance(snapshot_candidate_value, Mapping)
            else None
        )
        snapshot_url = (
            snapshot_candidate.get("url") if snapshot_candidate is not None else None
        )
        if snapshot_url != source_url:
            raise TargetRawDocketRecoveryError(
                f"selected URL is not authenticated by source snapshot: {docket_id}"
            )
        if candidate_id in selected:
            raise TargetRawDocketRecoveryError(
                f"selected target repeats: {candidate_id}"
            )
        selected[candidate_id] = row
    if not selected:
        raise TargetRawDocketRecoveryError("selection contains no selected targets")

    present: set[str] = set()
    for row in _read_jsonl_bytes(raw_payload, "source raw manifest"):
        candidate_id = row.get("candidate_id")
        sha = row.get("sha256")
        byte_count = row.get("byte_count")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(sha, str)
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise TargetRawDocketRecoveryError("source raw manifest has malformed row")
        if _SHA256.fullmatch(sha.removeprefix("sha256:")) is None:
            raise TargetRawDocketRecoveryError(
                "source raw manifest has invalid content digest"
            )
        # Saturated union snapshots intentionally retain multiple authenticated
        # observations of the same docket.  Presence is candidate-level here;
        # verify_snapshot owns the integrity and conflict checks for each row.
        present.add(candidate_id)

    targets: list[Mapping[str, object]] = []
    for rank, candidate_id in enumerate(sorted(set(selected) - present)):
        source = selected[candidate_id]
        docket_id = candidate_id.removeprefix(_CANDIDATE_PREFIX)
        targets.append(
            {
                "candidate_id": candidate_id,
                "identity": {
                    "courtlistener_docket_id": docket_id,
                    "courtlistener_url": source["source_url"],
                },
                "ranking_key": [rank, candidate_id],
                "screening_metadata": dict(source),
            }
        )
    if not targets:
        raise TargetRawDocketRecoveryError("no selected raw docket gaps remain")
    return TargetRawDocketRecoveryPlan(
        selection_path=str(selection_path.resolve()),
        selection_sha256=selection_sha,
        source_snapshot_path=str(source_snapshot_path.resolve()),
        source_snapshot_manifest_sha256=snapshot_manifest_sha,
        source_snapshot_screened_cases_sha256=screened_sha,
        cycle_hash=expected_cycle_hash,
        source_batch_id=source_batch_id,
        source_batch_digest=source_batch_digest,
        source_snapshot_run_card_path=str(source_snapshot_run_card_path.resolve()),
        source_snapshot_run_card_sha256=card_sha,
        source_raw_manifest_path=str(source_raw_manifest_path.resolve()),
        source_raw_manifest_sha256=raw_sha,
        cycle_store_path=str(cycle_store_path.resolve()),
        batch_id=batch_id,
        run_id=run_id,
        credit_cap=credit_cap,
        workers=workers,
        max_pages_per_docket=max_pages_per_docket,
        max_attempts_per_page=max_attempts_per_page,
        provider_breaker_threshold=provider_breaker_threshold,
        proxy=proxy,
        force_browser=force_browser,
        targets=tuple(targets),
    )


def write_target_raw_docket_recovery_plan(
    path: Path, plan: TargetRawDocketRecoveryPlan
) -> str:
    payload = (
        json.dumps(
            plan.as_record(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )
    if path.exists():
        if _read_unique_regular_file(path, "plan output") != payload:
            raise TargetRawDocketRecoveryError(
                "plan output already exists with different bytes"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def target_raw_docket_recovery_receipt_bytes(
    receipt: Mapping[str, object],
) -> bytes:
    """Serialize one deterministic terminal receipt."""
    if receipt.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA:
        raise TargetRawDocketRecoveryError("recovery receipt schema is invalid")
    return (
        json.dumps(
            dict(receipt),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def write_target_raw_docket_recovery_receipt(
    path: Path, receipt: Mapping[str, object]
) -> str:
    """Publish or exact-byte resume one deterministic terminal receipt."""

    payload = target_raw_docket_recovery_receipt_bytes(receipt)
    if path.exists():
        if _read_unique_regular_file(path, "recovery receipt output") != payload:
            raise TargetRawDocketRecoveryError(
                "recovery receipt already exists with different bytes"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_target_raw_docket_recovery_plan(
    path: Path, expected_sha256: str
) -> TargetRawDocketRecoveryPlan:
    payload = _pinned_bytes(path, expected_sha256, "plan")
    try:
        record = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError("plan is not JSON") from exc
    if not isinstance(record, dict):
        raise TargetRawDocketRecoveryError("plan schema is invalid")
    typed_record = cast(dict[str, object], record)
    if typed_record.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_PLAN_SCHEMA:
        raise TargetRawDocketRecoveryError("plan schema is invalid")
    fields = {field for field in TargetRawDocketRecoveryPlan.__dataclass_fields__}
    targets_value = typed_record.get("targets")
    targets = (
        cast(list[object], targets_value) if isinstance(targets_value, list) else None
    )
    if (
        set(typed_record) != {"schema_version", "target_count", *fields}
        or targets is None
        or typed_record.get("target_count") != len(targets)
        or any(not isinstance(item, Mapping) for item in targets)
    ):
        raise TargetRawDocketRecoveryError("plan fields are invalid")
    try:
        values = {field: cast(Any, typed_record[field]) for field in fields}
        values["targets"] = tuple(cast(Mapping[str, object], item) for item in targets)
        plan = TargetRawDocketRecoveryPlan(**values)
    except TypeError as exc:
        raise TargetRawDocketRecoveryError("plan fields are malformed") from exc
    _validated_target_map(plan.targets)
    return plan


def execute_target_raw_docket_recovery(
    *,
    plan: TargetRawDocketRecoveryPlan,
    scheduler: BudgetedFirecrawlScheduler,
    raw_html_dir: Path,
) -> tuple[
    list[Mapping[str, object]], list[Mapping[str, object]], Mapping[str, object]
]:
    """Run complete pagination and return screen-firecrawl-compatible records."""

    # Recheck every external pin immediately before provider activity.
    _pinned_sha(Path(plan.selection_path), plan.selection_sha256, "selection")
    try:
        snapshot_manifest = verify_snapshot(
            Path(plan.source_snapshot_path),
            expected_cycle_hash=plan.cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
        snapshot_firecrawl_screening_source_count(
            snapshot_manifest, require_current=True
        )
    except (SnapshotVerificationError, ValueError) as exc:
        raise TargetRawDocketRecoveryError(
            f"source snapshot is not current complete and saturated: {exc}"
        ) from exc
    snapshot_manifest_payload = _pinned_bytes(
        Path(plan.source_snapshot_path) / "manifest.json",
        plan.source_snapshot_manifest_sha256,
        "source snapshot manifest",
    )
    try:
        captured_manifest = json.loads(snapshot_manifest_payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "source snapshot manifest is not JSON"
        ) from exc
    if (
        not isinstance(captured_manifest, Mapping)
        or snapshot_manifest != captured_manifest
    ):
        raise TargetRawDocketRecoveryError(
            "source snapshot manifest changed during verification"
        )
    _pinned_sha(
        Path(plan.source_snapshot_path) / "screened-cases.jsonl",
        plan.source_snapshot_screened_cases_sha256,
        "source snapshot screened-cases",
    )
    _pinned_sha(
        Path(plan.source_snapshot_run_card_path),
        plan.source_snapshot_run_card_sha256,
        "source snapshot run card",
    )
    _pinned_sha(
        Path(plan.source_raw_manifest_path),
        plan.source_raw_manifest_sha256,
        "source raw manifest",
    )
    target_by_docket = _validated_target_map(plan.targets)
    raw_directory_fd = _open_raw_html_directory(raw_html_dir)
    try:
        try:
            result = acquire_ranked_dockets(
                records=plan.targets,
                scheduler=scheduler,
                limit=len(plan.targets),
                max_pages_per_docket=plan.max_pages_per_docket,
                decision_anchor=None,
            )
        except BudgetedDocketAcquisitionError as exc:
            raise TargetRawDocketRecoveryError(
                f"target raw docket acquisition is invalid: {exc}"
            ) from exc
        successes: list[Mapping[str, object]] = []
        completed_at_by_url = {
            attempt.request_url: attempt.completed_at
            for attempt in scheduler.store.firecrawl_attempts(scheduler.run_id)
            if attempt.status == "succeeded" and attempt.completed_at is not None
        }
        for bundle in result.bundles:
            target = target_by_docket.get(bundle.docket_id)
            if target is None:
                raise TargetRawDocketRecoveryError(
                    f"recovered docket is not a planned target: {bundle.docket_id}"
                )
            raw = render_complete_docket_html(bundle).encode()
            filename = f"{bundle.docket_id}.html"
            _publish_unique_raw_html(
                raw_directory_fd,
                filename,
                raw,
                label=f"recovery raw HTML {target['candidate_id']}",
            )
            retrieval_times = [
                completed_at_by_url.get(page.source_url) for page in bundle.pages
            ]
            if not retrieval_times or any(value is None for value in retrieval_times):
                raise TargetRawDocketRecoveryError(
                    f"durable retrieval time is missing: {bundle.docket_id}"
                )
            try:
                retrieved_at = max(
                    cast(list[str], retrieval_times),
                    key=_parse_completed_at,
                )
            except ValueError as exc:
                raise TargetRawDocketRecoveryError(
                    f"durable retrieval time is not ISO-8601: {bundle.docket_id}"
                ) from exc
            screening_metadata = dict(
                cast(Mapping[str, object], target["screening_metadata"])
            )
            screening_metadata["case_id"] = target["candidate_id"]
            successes.append(
                {
                    "case_id": target["candidate_id"],
                    "candidate_id": target["candidate_id"],
                    "source_url": bundle.base_url,
                    "docket_id": bundle.docket_id,
                    "raw_html_path": str((raw_html_dir / filename).resolve()),
                    "case_metadata": screening_metadata,
                    "raw_html_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "raw_html_bytes": len(raw),
                    "retrieved_at": retrieved_at,
                    "pagination_complete_for_anchor_window": True,
                    "page_count": len(bundle.pages),
                }
            )
    finally:
        os.close(raw_directory_fd)
    exclusions: list[Mapping[str, object]] = [
        dict(failure.as_record()) for failure in result.failures
    ]
    summary: Mapping[str, object] = {
        **dict(result.credit_summary),
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA,
        "target_count": len(plan.targets),
        "success_count": len(successes),
        "exclusion_count": len(exclusions),
        "pagination_complete_before_screening": True,
        "source_snapshot_manifest_sha256": plan.source_snapshot_manifest_sha256,
        "source_batch_id": plan.source_batch_id,
        "source_batch_digest": plan.source_batch_digest,
    }
    return successes, exclusions, summary
