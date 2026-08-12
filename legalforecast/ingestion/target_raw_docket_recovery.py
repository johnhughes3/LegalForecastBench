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
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from legalforecast.contracts import (
    ACQUISITION_RUN_CARD_V1,
    FIRECRAWL_PROVIDER_CONTRACT_DEFECT_AUTHORIZATION_V1,
    FIRECRAWL_SCRAPE_REQUEST_CONTRACT_V1,
    SELECTED_ACQUISITION_SLICE_V1,
    TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
)
from legalforecast.ingestion.budgeted_docket_acquisition import (
    BudgetedDocketAcquisitionError,
    acquire_ranked_dockets,
    provisional_lineage_flags,
    ranked_docket_targets,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlScheduler,
    FirecrawlArtifactError,
    FirecrawlCircuitOpenError,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    SnapshotVerificationError,
    verify_snapshot,
)
from legalforecast.ingestion.firecrawl_docket_pagination import (
    canonical_courtlistener_docket_page_url,
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
TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_SCHEMA = str(
    TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_V1
)
TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_SCHEMA = str(
    TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_V1
)
_PROVIDER_CONTRACT_RETRY_REQUEST_CONTRACT: Mapping[str, object] = {
    "schema_version": str(FIRECRAWL_SCRAPE_REQUEST_CONTRACT_V1),
    "only_change_from_predecessor": "omit_optional_json_property",
    "omitted_property": "blockAds",
    "omitted_value": False,
}
_PROVIDER_CONTRACT_DEFECT_AUTHORIZATION: Mapping[str, object] = {
    "schema_version": str(FIRECRAWL_PROVIDER_CONTRACT_DEFECT_AUTHORIZATION_V1),
    "declared_provider_contract_defect": {
        "provider": "firecrawl",
        "endpoint": "v2/scrape",
        "request_property": "blockAds",
        "prior_json_value": False,
        "authorized_retry_change": "omit_optional_json_property",
    },
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DOCKET_ID = re.compile(r"[1-9][0-9]*\Z")
_CANDIDATE_PREFIX = "courtlistener-docket-"
_VERIFIED_RECOVERY_BYTE_COLLECTOR: ContextVar[dict[str, bytes] | None] = ContextVar(
    "verified_recovery_byte_collector", default=None
)
_VERIFIED_RECOVERY_ABSENCE_COLLECTOR: ContextVar[set[str] | None] = ContextVar(
    "verified_recovery_absence_collector", default=None
)


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


@dataclass(frozen=True, slots=True)
class TargetRawDocketRecoverySuccessorPlan:
    """One direct child of a zero-success circuit-open recovery run."""

    parent_plan_path: str
    parent_plan_sha256: str
    parent_failure_run_card_path: str
    parent_failure_run_card_sha256: str
    parent_raw_html_dir: str
    batch_id: str
    run_id: str

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_SCHEMA,
            **asdict(self),
        }


@dataclass(frozen=True, slots=True)
class TargetRawDocketRecoveryProviderContractRetryPlan:
    """One final retry after two verified zero-success provider circuits.

    This is intentionally not a general successor.  It exists only to bind the
    Firecrawl v2 correction that omits its broken optional ``blockAds: false``
    request property while preserving every target, scheduler, and cycle-budget
    commitment inherited through the already exhausted direct successor.
    """

    root_plan_path: str
    root_plan_sha256: str
    root_failure_run_card_path: str
    root_failure_run_card_sha256: str
    direct_successor_plan_path: str
    direct_successor_plan_sha256: str
    direct_successor_failure_run_card_path: str
    direct_successor_failure_run_card_sha256: str
    direct_successor_raw_html_dir: str
    provider_contract_defect_authorization_path: str
    provider_contract_defect_authorization_sha256: str
    batch_id: str
    run_id: str

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": (
                TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_SCHEMA
            ),
            **asdict(self),
            "provider_request_contract": dict(
                _PROVIDER_CONTRACT_RETRY_REQUEST_CONTRACT
            ),
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


def _load_provider_contract_defect_authorization(
    path: Path, expected_sha256: str
) -> None:
    """Require the separately pinned owner authorization for this exact defect."""

    payload = _pinned_bytes(
        path, expected_sha256, "provider-contract defect authorization"
    )
    try:
        record = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "provider-contract defect authorization is not JSON"
        ) from exc
    if record != dict(_PROVIDER_CONTRACT_DEFECT_AUTHORIZATION):
        raise TargetRawDocketRecoveryError(
            "provider-contract defect authorization does not bind the sole "
            "permitted Firecrawl defect"
        )


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
            except OSError:
                # Best-effort cleanup must not mask the original publish failure.
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


def _successor_plan_bytes(plan: TargetRawDocketRecoverySuccessorPlan) -> bytes:
    return (
        json.dumps(
            plan.as_record(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def write_target_raw_docket_recovery_successor_plan(
    path: Path, plan: TargetRawDocketRecoverySuccessorPlan
) -> str:
    """Publish one immutable direct-successor authorization."""

    payload = _successor_plan_bytes(plan)
    if path.exists():
        if _read_unique_regular_file(path, "successor plan output") != payload:
            raise TargetRawDocketRecoveryError(
                "successor plan output already exists with different bytes"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_target_raw_docket_recovery_successor_plan(
    path: Path, expected_sha256: str
) -> TargetRawDocketRecoverySuccessorPlan:
    """Load one externally pinned successor authorization."""

    payload = _pinned_bytes(path, expected_sha256, "successor plan")
    try:
        record = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError("successor plan is not JSON") from exc
    fields = {
        field for field in TargetRawDocketRecoverySuccessorPlan.__dataclass_fields__
    }
    if not isinstance(record, dict):
        raise TargetRawDocketRecoveryError("successor plan schema is invalid")
    typed_record = cast(dict[str, object], record)
    if typed_record.get(
        "schema_version"
    ) != TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_SCHEMA or set(typed_record) != {
        "schema_version",
        *fields,
    }:
        raise TargetRawDocketRecoveryError("successor plan schema is invalid")
    try:
        plan = TargetRawDocketRecoverySuccessorPlan(
            **{field: cast(Any, typed_record[field]) for field in fields}
        )
    except TypeError as exc:
        raise TargetRawDocketRecoveryError(
            "successor plan fields are malformed"
        ) from exc
    for field in fields:
        if not isinstance(getattr(plan, field), str) or not getattr(plan, field):
            raise TargetRawDocketRecoveryError(
                "successor plan fields must be nonempty strings"
            )
    return plan


def _provider_contract_retry_plan_bytes(
    plan: TargetRawDocketRecoveryProviderContractRetryPlan,
) -> bytes:
    return (
        json.dumps(
            plan.as_record(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def write_target_raw_docket_recovery_provider_contract_retry_plan(
    path: Path, plan: TargetRawDocketRecoveryProviderContractRetryPlan
) -> str:
    """Publish the one immutable provider-contract retry authorization."""

    payload = _provider_contract_retry_plan_bytes(plan)
    if path.exists():
        if (
            _read_unique_regular_file(path, "provider-contract retry plan output")
            != payload
        ):
            raise TargetRawDocketRecoveryError(
                "provider-contract retry plan output already exists with "
                "different bytes"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_target_raw_docket_recovery_provider_contract_retry_plan(
    path: Path, expected_sha256: str
) -> TargetRawDocketRecoveryProviderContractRetryPlan:
    """Load the externally pinned final provider-contract retry authority."""

    payload = _pinned_bytes(path, expected_sha256, "provider-contract retry plan")
    try:
        record = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "provider-contract retry plan is not JSON"
        ) from exc
    fields = {
        field
        for field in (
            TargetRawDocketRecoveryProviderContractRetryPlan.__dataclass_fields__
        )
    }
    if not isinstance(record, dict):
        raise TargetRawDocketRecoveryError(
            "provider-contract retry plan schema is invalid"
        )
    typed_record = cast(dict[str, object], record)
    if (
        typed_record.get("schema_version")
        != TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_SCHEMA
        or set(typed_record) != {"schema_version", *fields, "provider_request_contract"}
        or typed_record.get("provider_request_contract")
        != dict(_PROVIDER_CONTRACT_RETRY_REQUEST_CONTRACT)
    ):
        raise TargetRawDocketRecoveryError(
            "provider-contract retry plan schema is invalid"
        )
    try:
        plan = TargetRawDocketRecoveryProviderContractRetryPlan(
            **{field: cast(Any, typed_record[field]) for field in fields}
        )
    except TypeError as exc:
        raise TargetRawDocketRecoveryError(
            "provider-contract retry plan fields are malformed"
        ) from exc
    for field in fields:
        if not isinstance(getattr(plan, field), str) or not getattr(plan, field):
            raise TargetRawDocketRecoveryError(
                "provider-contract retry plan fields must be nonempty strings"
            )
    return plan


def _rebuild_target_raw_docket_recovery_plan(
    plan: TargetRawDocketRecoveryPlan,
) -> TargetRawDocketRecoveryPlan:
    return build_target_raw_docket_recovery_plan(
        selection_path=Path(plan.selection_path),
        expected_selection_sha256=plan.selection_sha256,
        source_snapshot_path=Path(plan.source_snapshot_path),
        expected_source_snapshot_manifest_sha256=(plan.source_snapshot_manifest_sha256),
        expected_cycle_hash=plan.cycle_hash,
        source_snapshot_run_card_path=Path(plan.source_snapshot_run_card_path),
        expected_source_snapshot_run_card_sha256=(plan.source_snapshot_run_card_sha256),
        source_raw_manifest_path=Path(plan.source_raw_manifest_path),
        expected_source_raw_manifest_sha256=plan.source_raw_manifest_sha256,
        cycle_store_path=Path(plan.cycle_store_path),
        batch_id=plan.batch_id,
        run_id=plan.run_id,
        credit_cap=plan.credit_cap,
        workers=plan.workers,
        max_pages_per_docket=plan.max_pages_per_docket,
        max_attempts_per_page=plan.max_attempts_per_page,
        provider_breaker_threshold=plan.provider_breaker_threshold,
        proxy=plan.proxy,
        force_browser=plan.force_browser,
    )


def _expected_selected_slice_config(
    plan: TargetRawDocketRecoveryPlan,
    *,
    source_batch_config: Mapping[str, object],
) -> Mapping[str, object]:
    targets = ranked_docket_targets(plan.targets, limit=len(plan.targets))
    selection_payload = [
        {
            "candidate_id": target.candidate_id,
            "courtlistener_url": target.docket_url,
            "cost_rank": target.rank,
        }
        for target in targets
    ]
    selection_hash = hashlib.sha256(
        json.dumps(selection_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": str(SELECTED_ACQUISITION_SLICE_V1),
        "parent_batch_id": plan.source_batch_id,
        "parent_batch_digest": plan.source_batch_digest,
        "selection_hash": selection_hash,
        "selection_count": len(targets),
        "parent_discovery_saturation_claimed": False,
        "purpose": "target-raw-docket-recovery",
        **provisional_lineage_flags(source_batch_config),
    }


def _expected_root_run_config(
    plan: TargetRawDocketRecoveryPlan, parent_raw_html_dir: Path
) -> Mapping[str, object]:
    return {
        "purpose": "target-raw-docket-recovery",
        "recovery_of_run_id": plan.source_snapshot_manifest_sha256,
        "max_pages_per_docket": plan.max_pages_per_docket,
        "raw_artifact_root": str((parent_raw_html_dir / "pages").resolve()),
        "firecrawl_proxy": plan.proxy,
        "firecrawl_force_browser": plan.force_browser,
        "workers": plan.workers,
        "max_attempts_per_page": plan.max_attempts_per_page,
        "provider_breaker_threshold": plan.provider_breaker_threshold,
    }


def _verify_zero_success_parent(
    *,
    parent: TargetRawDocketRecoveryPlan,
    failure_card: Mapping[str, Any],
    parent_raw_html_dir: Path,
    expected_plan_input: Path,
    expected_card_inputs: tuple[Path, ...] | None = None,
    expected_run_config: Mapping[str, object] | None = None,
    first_input_error: str | None = None,
) -> None:
    expected_inputs = expected_card_inputs or (
        Path(parent.selection_path).resolve(),
        (Path(parent.source_snapshot_path) / "manifest.json").resolve(),
        Path(parent.source_snapshot_run_card_path).resolve(),
        Path(parent.source_raw_manifest_path).resolve(),
    )
    raw_inputs = failure_card.get("input_paths")
    raw_outputs = failure_card.get("output_paths")
    if not isinstance(raw_inputs, list) or not isinstance(raw_outputs, list):
        raise TargetRawDocketRecoveryError(
            "parent failure run card is not an authenticated circuit failure"
        )
    typed_inputs = cast(list[object], raw_inputs)
    typed_outputs = cast(list[object], raw_outputs)
    if (
        failure_card.get("schema_version") != str(ACQUISITION_RUN_CARD_V1)
        or failure_card.get("stage") != "execute-target-raw-docket-recovery"
        or failure_card.get("status") != "failed"
        or failure_card.get("dry_run") is not False
        or failure_card.get("execute") is not True
        or failure_card.get("record_count") != 0
        or failure_card.get("paid_activity_requested") is not True
        or failure_card.get("paid_activity_executed") is not True
        or failure_card.get("firecrawl_metered_activity_requested") is not True
        or failure_card.get("firecrawl_metered_activity_executed") is not True
        or failure_card.get("firecrawl_run_status") != "circuit_open"
        or not isinstance(failure_card.get("failure_reason"), str)
        or "circuit" not in cast(str, failure_card["failure_reason"]).lower()
        or len(typed_inputs) != len(expected_inputs) + 1
        or len(typed_outputs) != 4
        or any(not isinstance(item, str) for item in (*typed_inputs, *typed_outputs))
    ):
        raise TargetRawDocketRecoveryError(
            "parent failure run card is not an authenticated circuit failure"
        )
    input_anchor = _recorded_path_anchor(
        cast(str, typed_inputs[0]), expected_plan_input
    )
    resolved_inputs = tuple(
        _resolve_recorded_path(
            cast(str, item), anchor=input_anchor, label="parent failure run card input"
        )
        for item in typed_inputs
    )
    if resolved_inputs[0] != expected_plan_input.resolve() or resolved_inputs[1:] != (
        expected_inputs
    ):
        if (
            first_input_error is not None
            and resolved_inputs[0] != expected_plan_input.resolve()
        ):
            raise TargetRawDocketRecoveryError(first_input_error)
        raise TargetRawDocketRecoveryError(
            "parent failure run card input lineage differs from parent plan"
        )
    output_paths = tuple(
        _resolve_recorded_path(
            cast(str, output),
            anchor=input_anchor,
            label="parent failure run card output",
        )
        for output in typed_outputs
    )
    resolved_outputs = output_paths
    if len(set(resolved_outputs)) != 4:
        raise TargetRawDocketRecoveryError(
            "parent failure run card repeats a terminal output"
        )
    for path in output_paths:
        if path.exists() or path.is_symlink():
            raise TargetRawDocketRecoveryError(
                "parent failure run unexpectedly has terminal output residue"
            )
    root = parent_raw_html_dir.resolve()
    if parent_raw_html_dir.is_symlink() or not parent_raw_html_dir.is_dir():
        raise TargetRawDocketRecoveryError("parent raw HTML directory is invalid")
    for child in parent_raw_html_dir.rglob("*"):
        if (
            child.resolve() == (root / "pages")
            and child.is_dir()
            and not child.is_symlink()
        ):
            continue
        raise TargetRawDocketRecoveryError(
            "parent circuit failure contains raw artifact residue"
        )
    with CycleAcquisitionStore(Path(parent.cycle_store_path)) as store:
        if (
            store.cycle_hash != parent.cycle_hash
            or store.batch_digest(parent.source_batch_id) != parent.source_batch_digest
            or store.batch_config(parent.batch_id)
            != _expected_selected_slice_config(
                parent,
                source_batch_config=store.batch_config(parent.source_batch_id),
            )
            or store.firecrawl_run_status(parent.run_id) != "circuit_open"
            or store.firecrawl_run_config(parent.run_id)
            != (
                expected_run_config
                if expected_run_config is not None
                else _expected_root_run_config(parent, parent_raw_html_dir)
            )
        ):
            raise TargetRawDocketRecoveryError(
                "parent failure differs from durable cycle-store authority"
            )
        summary = store.firecrawl_run_summary(parent.run_id)
        for key in (
            "run_id",
            "batch_id",
            "config_digest",
            "credit_cap",
            "reserved_credits_per_attempt",
            "run_reserved_credits",
            "run_reported_credits",
            "attempt_status_counts",
            "failure_code_counts",
        ):
            if failure_card.get(key) != summary.get(key):
                raise TargetRawDocketRecoveryError(
                    f"parent failure run card differs from durable {key}"
                )
        if failure_card.get("firecrawl_run_status") != summary.get("status"):
            raise TargetRawDocketRecoveryError(
                "parent failure run card differs from durable run status"
            )
        attempts = store.firecrawl_attempts(parent.run_id)
        if not attempts:
            raise TargetRawDocketRecoveryError(
                "parent circuit failure has no provider attempts"
            )
        if any(
            attempt.status != "provider_error"
            or attempt.provider_http_status is None
            or attempt.provider_http_status < 500
            or attempt.page_number != 1
            or attempt.artifact_path is not None
            or attempt.artifact_sha256 is not None
            or attempt.artifact_byte_count is not None
            for attempt in attempts
        ):
            raise TargetRawDocketRecoveryError(
                "parent run is not a zero-success all-provider-error circuit"
            )
        expected_urls = {
            canonical_courtlistener_docket_page_url(
                cast(
                    str,
                    cast(Mapping[str, object], target["identity"])["courtlistener_url"],
                ),
                page_number=1,
            )
            for target in parent.targets
        }
        attempted_urls = {attempt.request_url for attempt in attempts}
        registered_targets = store.firecrawl_targets(parent.run_id)
        if (
            not attempted_urls.issubset(expected_urls)
            or not {target.source_url for target in registered_targets}.issubset(
                expected_urls
            )
            or not {attempt.target_id for attempt in attempts}.issubset(
                {target.target_id for target in registered_targets}
            )
        ):
            raise TargetRawDocketRecoveryError(
                "parent provider attempts differ from the exact target set"
            )
        byte_collector = _VERIFIED_RECOVERY_BYTE_COLLECTOR.get()
        absence_collector = _VERIFIED_RECOVERY_ABSENCE_COLLECTOR.get()
        if (byte_collector is None) != (absence_collector is None):
            raise TargetRawDocketRecoveryError(
                "recovery authority collectors must be installed together"
            )
        if byte_collector is not None and absence_collector is not None:
            store.close_database_for_locked_snapshot()
            _merge_recovery_cycle_store_evidence(
                Path(parent.cycle_store_path), byte_collector, absence_collector
            )


def _merge_recovery_cycle_store_evidence(
    cycle_store_path: Path,
    byte_collector: dict[str, bytes],
    absence_collector: set[str],
) -> None:
    """Merge one locked, post-close SQLite namespace without contradictions."""

    for path in (
        cycle_store_path,
        Path(f"{cycle_store_path}-wal"),
        Path(f"{cycle_store_path}-journal"),
    ):
        key = os.path.abspath(path)
        if os.path.lexists(path):
            payload = _read_unique_regular_file(path, "recovery cycle store")
            if key in absence_collector:
                raise TargetRawDocketRecoveryError(
                    "recovery cycle-store presence closure conflicts"
                )
            existing = byte_collector.get(key)
            if existing is not None and existing != payload:
                raise TargetRawDocketRecoveryError(
                    "recovery cycle-store byte closure conflicts"
                )
            byte_collector[key] = payload
        else:
            if key in byte_collector:
                raise TargetRawDocketRecoveryError(
                    "recovery cycle-store absence closure conflicts"
                )
            absence_collector.add(key)


def _recorded_path_anchor(recorded: str, expected: Path) -> Path | None:
    """Anchor historical relative card paths to their authenticated input.

    Run cards from the original recovery stored paths relative to the repository
    root.  Resolving those strings against a later process cwd changes their
    meaning.  Instead, require the recorded first input to be an exact suffix
    of the known, hash-pinned plan path and recover the one permissible anchor.
    """

    path = Path(recorded)
    if path.is_absolute():
        return None
    if not path.parts or any(part in {".", ".."} for part in path.parts):
        raise TargetRawDocketRecoveryError(
            "parent failure run card has unsafe relative input path"
        )
    expected_path = expected.resolve()
    if (
        len(path.parts) > len(expected_path.parts)
        or tuple(expected_path.parts[-len(path.parts) :]) != path.parts
    ):
        raise TargetRawDocketRecoveryError(
            "parent failure run card relative input is not the pinned plan path"
        )
    anchor = Path(*expected_path.parts[: -len(path.parts)])
    if not anchor.is_absolute():
        raise TargetRawDocketRecoveryError(
            "parent failure run card relative input has no absolute anchor"
        )
    return anchor


def _resolve_recorded_path(recorded: str, *, anchor: Path | None, label: str) -> Path:
    """Resolve a card path without consulting the process cwd."""

    path = Path(recorded)
    if path.is_absolute():
        return path.resolve()
    if (
        anchor is None
        or not path.parts
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise TargetRawDocketRecoveryError(f"{label} is unsafe or unanchored")
    resolved_anchor = anchor.resolve()
    resolved = (resolved_anchor / path).resolve()
    try:
        resolved.relative_to(resolved_anchor)
    except ValueError as exc:
        raise TargetRawDocketRecoveryError(
            f"{label} escapes its authenticated anchor"
        ) from exc
    return resolved


def build_target_raw_docket_recovery_successor_plan(
    *,
    parent_plan_path: Path,
    expected_parent_plan_sha256: str,
    parent_failure_run_card_path: Path,
    expected_parent_failure_run_card_sha256: str,
    parent_raw_html_dir: Path,
    batch_id: str,
    run_id: str,
) -> TargetRawDocketRecoverySuccessorPlan:
    """Authorize one new direct child after a zero-success provider circuit."""

    parent = load_target_raw_docket_recovery_plan(
        parent_plan_path, expected_parent_plan_sha256
    )
    if _rebuild_target_raw_docket_recovery_plan(parent) != parent:
        raise TargetRawDocketRecoveryError("parent plan no longer reconstructs")
    card_payload = _pinned_bytes(
        parent_failure_run_card_path,
        expected_parent_failure_run_card_sha256,
        "parent failure run card",
    )
    try:
        card = json.loads(card_payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "parent failure run card is not JSON"
        ) from exc
    if not isinstance(card, Mapping):
        raise TargetRawDocketRecoveryError("parent failure run card is malformed")
    batch_id = batch_id.strip()
    run_id = run_id.strip()
    if not batch_id or not run_id or batch_id == run_id:
        raise TargetRawDocketRecoveryError(
            "successor batch and run identities must be nonempty and distinct"
        )
    if batch_id in {parent.batch_id, parent.run_id} or run_id in {
        parent.batch_id,
        parent.run_id,
    }:
        raise TargetRawDocketRecoveryError(
            "successor identities must differ from parent identities"
        )
    _verify_zero_success_parent(
        parent=parent,
        failure_card=cast(Mapping[str, Any], card),
        parent_raw_html_dir=parent_raw_html_dir,
        expected_plan_input=parent_plan_path,
    )
    # Bind the card's first input separately so relative paths resolve exactly once.
    raw_inputs = cast(list[str], card["input_paths"])
    input_anchor = _recorded_path_anchor(raw_inputs[0], parent_plan_path)
    if (
        _resolve_recorded_path(
            raw_inputs[0], anchor=input_anchor, label="parent failure run card input"
        )
        != parent_plan_path.resolve()
    ):
        raise TargetRawDocketRecoveryError(
            "parent failure run card does not bind the pinned parent plan"
        )
    return TargetRawDocketRecoverySuccessorPlan(
        parent_plan_path=str(parent_plan_path.resolve()),
        parent_plan_sha256=expected_parent_plan_sha256,
        parent_failure_run_card_path=str(parent_failure_run_card_path.resolve()),
        parent_failure_run_card_sha256=expected_parent_failure_run_card_sha256,
        parent_raw_html_dir=str(parent_raw_html_dir.resolve()),
        batch_id=batch_id,
        run_id=run_id,
    )


def resolve_target_raw_docket_recovery_successor(
    plan: TargetRawDocketRecoverySuccessorPlan,
) -> tuple[TargetRawDocketRecoveryPlan, TargetRawDocketRecoveryPlan]:
    """Reauthenticate the parent and derive the exact child execution plan."""

    rebuilt = build_target_raw_docket_recovery_successor_plan(
        parent_plan_path=Path(plan.parent_plan_path),
        expected_parent_plan_sha256=plan.parent_plan_sha256,
        parent_failure_run_card_path=Path(plan.parent_failure_run_card_path),
        expected_parent_failure_run_card_sha256=(plan.parent_failure_run_card_sha256),
        parent_raw_html_dir=Path(plan.parent_raw_html_dir),
        batch_id=plan.batch_id,
        run_id=plan.run_id,
    )
    if rebuilt != plan:
        raise TargetRawDocketRecoveryError("successor plan no longer reconstructs")
    parent = load_target_raw_docket_recovery_plan(
        Path(plan.parent_plan_path), plan.parent_plan_sha256
    )
    child_values = asdict(parent)
    child_values["batch_id"] = plan.batch_id
    child_values["run_id"] = plan.run_id
    return parent, TargetRawDocketRecoveryPlan(**child_values)


def _expected_successor_run_config(
    *,
    parent: TargetRawDocketRecoveryPlan,
    successor: TargetRawDocketRecoverySuccessorPlan,
    child_raw_html_dir: Path,
) -> Mapping[str, object]:
    return {
        "purpose": "target-raw-docket-recovery",
        "recovery_of_run_id": parent.run_id,
        "parent_plan_sha256": successor.parent_plan_sha256,
        "parent_failure_run_card_sha256": successor.parent_failure_run_card_sha256,
        "max_pages_per_docket": parent.max_pages_per_docket,
        "raw_artifact_root": str((child_raw_html_dir / "pages").resolve()),
        "firecrawl_proxy": parent.proxy,
        "firecrawl_force_browser": parent.force_browser,
        "workers": parent.workers,
        "max_attempts_per_page": parent.max_attempts_per_page,
        "provider_breaker_threshold": parent.provider_breaker_threshold,
    }


def build_target_raw_docket_recovery_provider_contract_retry_plan(
    *,
    root_plan_path: Path,
    expected_root_plan_sha256: str,
    root_failure_run_card_path: Path,
    expected_root_failure_run_card_sha256: str,
    direct_successor_plan_path: Path,
    expected_direct_successor_plan_sha256: str,
    direct_successor_failure_run_card_path: Path,
    expected_direct_successor_failure_run_card_sha256: str,
    direct_successor_raw_html_dir: Path,
    provider_contract_defect_authorization_path: Path,
    expected_provider_contract_defect_authorization_sha256: str,
    batch_id: str,
    run_id: str,
) -> TargetRawDocketRecoveryProviderContractRetryPlan:
    """Authorize the sole Firecrawl request-contract retry after two circuits."""

    _load_provider_contract_defect_authorization(
        provider_contract_defect_authorization_path,
        expected_provider_contract_defect_authorization_sha256,
    )
    root = load_target_raw_docket_recovery_plan(
        root_plan_path, expected_root_plan_sha256
    )
    successor = load_target_raw_docket_recovery_successor_plan(
        direct_successor_plan_path, expected_direct_successor_plan_sha256
    )
    if (
        Path(successor.parent_plan_path).resolve() != root_plan_path.resolve()
        or successor.parent_plan_sha256 != expected_root_plan_sha256
        or Path(successor.parent_failure_run_card_path).resolve()
        != root_failure_run_card_path.resolve()
        or successor.parent_failure_run_card_sha256
        != expected_root_failure_run_card_sha256
    ):
        raise TargetRawDocketRecoveryError(
            "direct successor does not bind the exact root circuit failure"
        )
    rebuilt_successor = build_target_raw_docket_recovery_successor_plan(
        parent_plan_path=root_plan_path,
        expected_parent_plan_sha256=expected_root_plan_sha256,
        parent_failure_run_card_path=root_failure_run_card_path,
        expected_parent_failure_run_card_sha256=expected_root_failure_run_card_sha256,
        parent_raw_html_dir=Path(successor.parent_raw_html_dir),
        batch_id=successor.batch_id,
        run_id=successor.run_id,
    )
    if rebuilt_successor != successor:
        raise TargetRawDocketRecoveryError("direct successor no longer reconstructs")
    root_card_payload = _pinned_bytes(
        root_failure_run_card_path,
        expected_root_failure_run_card_sha256,
        "root failure run card",
    )
    child_card_payload = _pinned_bytes(
        direct_successor_failure_run_card_path,
        expected_direct_successor_failure_run_card_sha256,
        "direct successor failure run card",
    )
    try:
        root_card = json.loads(root_card_payload)
        child_card = json.loads(child_card_payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "provider-contract retry circuit card is not JSON"
        ) from exc
    if not isinstance(root_card, Mapping) or not isinstance(child_card, Mapping):
        raise TargetRawDocketRecoveryError(
            "provider-contract retry circuit card is malformed"
        )
    _verify_zero_success_parent(
        parent=root,
        failure_card=cast(Mapping[str, Any], root_card),
        parent_raw_html_dir=Path(successor.parent_raw_html_dir),
        expected_plan_input=root_plan_path,
    )
    _, child = resolve_target_raw_docket_recovery_successor(successor)
    child_inputs = (
        root_plan_path.resolve(),
        root_failure_run_card_path.resolve(),
        Path(successor.parent_raw_html_dir).resolve(),
        Path(child.selection_path).resolve(),
        (Path(child.source_snapshot_path) / "manifest.json").resolve(),
        Path(child.source_snapshot_run_card_path).resolve(),
        Path(child.source_raw_manifest_path).resolve(),
    )
    _verify_zero_success_parent(
        parent=child,
        failure_card=cast(Mapping[str, Any], child_card),
        parent_raw_html_dir=direct_successor_raw_html_dir,
        expected_plan_input=direct_successor_plan_path,
        expected_card_inputs=child_inputs,
        expected_run_config=_expected_successor_run_config(
            parent=root,
            successor=successor,
            child_raw_html_dir=direct_successor_raw_html_dir,
        ),
        first_input_error=(
            "direct successor failure run card does not bind the pinned direct "
            "successor plan"
        ),
    )
    child_inputs_from_card = cast(list[str], child_card["input_paths"])
    child_input_anchor = _recorded_path_anchor(
        child_inputs_from_card[0], direct_successor_plan_path
    )
    if (
        _resolve_recorded_path(
            child_inputs_from_card[0],
            anchor=child_input_anchor,
            label="direct successor failure run card input",
        )
        != direct_successor_plan_path.resolve()
    ):
        raise TargetRawDocketRecoveryError(
            "direct successor failure run card does not bind the pinned direct "
            "successor plan"
        )
    batch_id = batch_id.strip()
    run_id = run_id.strip()
    if not batch_id or not run_id or batch_id == run_id:
        raise TargetRawDocketRecoveryError(
            "provider-contract retry batch and run identities must be nonempty "
            "and distinct"
        )
    if batch_id in {
        root.batch_id,
        root.run_id,
        child.batch_id,
        child.run_id,
    } or run_id in {
        root.batch_id,
        root.run_id,
        child.batch_id,
        child.run_id,
    }:
        raise TargetRawDocketRecoveryError(
            "provider-contract retry identities must differ from both circuit runs"
        )
    return TargetRawDocketRecoveryProviderContractRetryPlan(
        root_plan_path=str(root_plan_path.resolve()),
        root_plan_sha256=expected_root_plan_sha256,
        root_failure_run_card_path=str(root_failure_run_card_path.resolve()),
        root_failure_run_card_sha256=expected_root_failure_run_card_sha256,
        direct_successor_plan_path=str(direct_successor_plan_path.resolve()),
        direct_successor_plan_sha256=expected_direct_successor_plan_sha256,
        direct_successor_failure_run_card_path=str(
            direct_successor_failure_run_card_path.resolve()
        ),
        direct_successor_failure_run_card_sha256=(
            expected_direct_successor_failure_run_card_sha256
        ),
        direct_successor_raw_html_dir=str(direct_successor_raw_html_dir.resolve()),
        provider_contract_defect_authorization_path=str(
            provider_contract_defect_authorization_path.resolve()
        ),
        provider_contract_defect_authorization_sha256=(
            expected_provider_contract_defect_authorization_sha256
        ),
        batch_id=batch_id,
        run_id=run_id,
    )


def resolve_target_raw_docket_recovery_provider_contract_retry(
    plan: TargetRawDocketRecoveryProviderContractRetryPlan,
    *,
    _verified_byte_closure: dict[str, bytes] | None = None,
    _verified_absence_closure: set[str] | None = None,
) -> tuple[
    TargetRawDocketRecoveryPlan,
    TargetRawDocketRecoveryPlan,
    TargetRawDocketRecoverySuccessorPlan,
]:
    """Reauthenticate both exhausted circuits and derive the one retry plan."""

    if (_verified_byte_closure is None) != (_verified_absence_closure is None):
        raise TargetRawDocketRecoveryError(
            "recovery authority collectors must be installed together"
        )

    byte_token = _VERIFIED_RECOVERY_BYTE_COLLECTOR.set(_verified_byte_closure)
    absence_token = _VERIFIED_RECOVERY_ABSENCE_COLLECTOR.set(_verified_absence_closure)
    try:
        return _resolve_target_raw_docket_recovery_provider_contract_retry(plan)
    finally:
        _VERIFIED_RECOVERY_ABSENCE_COLLECTOR.reset(absence_token)
        _VERIFIED_RECOVERY_BYTE_COLLECTOR.reset(byte_token)


def _resolve_target_raw_docket_recovery_provider_contract_retry(
    plan: TargetRawDocketRecoveryProviderContractRetryPlan,
) -> tuple[
    TargetRawDocketRecoveryPlan,
    TargetRawDocketRecoveryPlan,
    TargetRawDocketRecoverySuccessorPlan,
]:
    rebuilt = build_target_raw_docket_recovery_provider_contract_retry_plan(
        root_plan_path=Path(plan.root_plan_path),
        expected_root_plan_sha256=plan.root_plan_sha256,
        root_failure_run_card_path=Path(plan.root_failure_run_card_path),
        expected_root_failure_run_card_sha256=plan.root_failure_run_card_sha256,
        direct_successor_plan_path=Path(plan.direct_successor_plan_path),
        expected_direct_successor_plan_sha256=plan.direct_successor_plan_sha256,
        direct_successor_failure_run_card_path=Path(
            plan.direct_successor_failure_run_card_path
        ),
        expected_direct_successor_failure_run_card_sha256=(
            plan.direct_successor_failure_run_card_sha256
        ),
        direct_successor_raw_html_dir=Path(plan.direct_successor_raw_html_dir),
        provider_contract_defect_authorization_path=Path(
            plan.provider_contract_defect_authorization_path
        ),
        expected_provider_contract_defect_authorization_sha256=(
            plan.provider_contract_defect_authorization_sha256
        ),
        batch_id=plan.batch_id,
        run_id=plan.run_id,
    )
    if rebuilt != plan:
        raise TargetRawDocketRecoveryError(
            "provider-contract retry plan no longer reconstructs"
        )
    successor = load_target_raw_docket_recovery_successor_plan(
        Path(plan.direct_successor_plan_path), plan.direct_successor_plan_sha256
    )
    root, child = resolve_target_raw_docket_recovery_successor(successor)
    retry_values = asdict(child)
    retry_values["batch_id"] = plan.batch_id
    retry_values["run_id"] = plan.run_id
    return root, TargetRawDocketRecoveryPlan(**retry_values), successor


def provider_contract_retry_run_config(
    *,
    retry_plan: TargetRawDocketRecoveryProviderContractRetryPlan,
    direct_successor_run_id: str,
    recovered_plan: TargetRawDocketRecoveryPlan,
    raw_html_dir: Path,
) -> Mapping[str, object]:
    """Return the sole durable scheduler configuration for the final retry."""

    return {
        "purpose": "target-raw-docket-recovery-provider-contract-retry",
        "recovery_of_run_id": direct_successor_run_id,
        "root_plan_sha256": retry_plan.root_plan_sha256,
        "root_failure_run_card_sha256": retry_plan.root_failure_run_card_sha256,
        "direct_successor_plan_sha256": retry_plan.direct_successor_plan_sha256,
        "direct_successor_failure_run_card_sha256": (
            retry_plan.direct_successor_failure_run_card_sha256
        ),
        "provider_request_contract": dict(_PROVIDER_CONTRACT_RETRY_REQUEST_CONTRACT),
        "max_pages_per_docket": recovered_plan.max_pages_per_docket,
        "raw_artifact_root": str((raw_html_dir / "pages").resolve()),
        "firecrawl_proxy": recovered_plan.proxy,
        "firecrawl_force_browser": recovered_plan.force_browser,
        "workers": recovered_plan.workers,
        "max_attempts_per_page": recovered_plan.max_attempts_per_page,
        "provider_breaker_threshold": recovered_plan.provider_breaker_threshold,
    }


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
        except (FirecrawlArtifactError, FirecrawlCircuitOpenError) as exc:
            raise TargetRawDocketRecoveryError(
                f"target raw docket acquisition provider failure: {exc}"
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
