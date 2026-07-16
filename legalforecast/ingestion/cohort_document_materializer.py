"""Immutable materialization of cleared free and purchased cohort documents."""

from __future__ import annotations

import hashlib
import os
import stat
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from legalforecast.ingestion.disclosure_clearance import (
    DisclosureClearanceError,
    require_cleared_documents,
)

MATERIALIZATION_SCHEMA = "legalforecast.cohort_document_materialization.v1"
_CHUNK_SIZE = 1024 * 1024


class CohortDocumentMaterializationError(ValueError):
    """Raised when immutable source documents cannot be safely materialized."""


@dataclass(frozen=True, slots=True)
class DocumentSource:
    """One authenticated source manifest, root, and matching clearance artifact."""

    phase: str
    document_root: Path
    manifest: Sequence[Mapping[str, Any]]
    clearance: Sequence[Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class PreparedCohortDocument:
    """One verified source file and its content-addressed destination."""

    source: Path
    destination: Path
    source_device: int
    source_inode: int
    manifest_record: Mapping[str, Any]
    clearance_record: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CohortDocumentMaterialization:
    """Deterministic parse-root artifacts prepared from authenticated sources."""

    manifest: tuple[Mapping[str, Any], ...]
    clearance: tuple[Mapping[str, Any], ...]
    documents: tuple[PreparedCohortDocument, ...]
    summary: Mapping[str, Any]


def prepare_cohort_document_materialization(
    sources: Sequence[DocumentSource],
    *,
    selected_document_keys: set[tuple[str, str]],
    output_root: Path,
    resolved_post_recovery_records: Sequence[Mapping[str, Any]] = (),
) -> CohortDocumentMaterialization:
    """Validate two immutable lineages and prepare a single parse-ready root."""

    if tuple(source.phase for source in sources) != ("free", "purchased"):
        raise CohortDocumentMaterializationError(
            "document sources must be ordered exactly as free, purchased"
        )
    output = output_root.absolute()
    document_output_root = output / "documents"
    _reject_overlapping_roots(
        output,
        tuple(source.document_root for source in sources),
    )
    prepared: list[PreparedCohortDocument] = []
    resolved_by_key = _resolved_record_index(resolved_post_recovery_records)
    required_resolved_keys: set[tuple[str, str]] = set()
    seen_keys: set[tuple[str, str]] = set()
    selected_owners: dict[str, set[str]] = {}
    for candidate_id, document_id in selected_document_keys:
        selected_owners.setdefault(document_id, set()).add(candidate_id)
    phase_counts: dict[str, int] = {}
    for source in sources:
        root = source.document_root.absolute()
        try:
            require_cleared_documents(
                source.manifest,
                document_root=root,
                clearance_records=source.clearance,
            )
        except DisclosureClearanceError as exc:
            raise CohortDocumentMaterializationError(str(exc)) from exc
        clearance_by_key = _unique_clearance_index(source.clearance)
        phase_counts[source.phase] = len(source.manifest)
        for record in source.manifest:
            key = _document_key(record)
            if key in seen_keys:
                raise CohortDocumentMaterializationError(
                    f"duplicate document identity across sources: {key[0]}/{key[1]}"
                )
            seen_keys.add(key)
            owners = selected_owners.get(key[1], set())
            if key not in selected_document_keys and not owners:
                raise CohortDocumentMaterializationError(
                    "document is absent from the authenticated target selection: "
                    f"{key[0]}/{key[1]}"
                )
            if key not in selected_document_keys:
                raise CohortDocumentMaterializationError(
                    "cross-candidate document substitution: "
                    f"{key[1]} belongs to {sorted(owners)}, not {key[0]}"
                )
            actual_phase = _required_string(record, "free_or_purchased")
            if actual_phase != source.phase:
                raise CohortDocumentMaterializationError(
                    f"{key[0]}/{key[1]} is {actual_phase}, expected {source.phase}"
                )
            if record.get("recovery_origin") == "unknown_status_attempt":
                required_resolved_keys.add(key)
            relative = _safe_relative_path(_required_string(record, "local_path"))
            source_path = root.joinpath(*relative.parts)
            expected_hash = _required_sha256(record, "sha256")
            expected_bytes = _required_nonnegative_int(record, "byte_count")
            device, inode, actual_hash, actual_bytes = _inspect_source_file(
                source_path,
                root=root,
            )
            if actual_hash != expected_hash:
                raise CohortDocumentMaterializationError(
                    f"source hash drift for {key[0]}/{key[1]}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            if actual_bytes != expected_bytes:
                raise CohortDocumentMaterializationError(
                    f"source byte-count drift for {key[0]}/{key[1]}: "
                    f"expected {expected_bytes}, got {actual_bytes}"
                )
            suffix = source_path.suffix.lower()
            if suffix != ".pdf":
                raise CohortDocumentMaterializationError(
                    f"source document must be a PDF: {key[0]}/{key[1]}"
                )
            destination_relative = PurePosixPath(
                "sha256", expected_hash[:2], f"{expected_hash}{suffix}"
            )
            destination = document_output_root.joinpath(*destination_relative.parts)
            _validate_destination(
                destination,
                root=document_output_root,
                expected_hash=expected_hash,
                expected_bytes=expected_bytes,
            )
            rebased_manifest = dict(record)
            rebased_manifest["local_path"] = destination_relative.as_posix()
            rebased_manifest["sha256"] = expected_hash
            rebased_manifest["byte_count"] = expected_bytes
            rebased_manifest["materialization_schema_version"] = MATERIALIZATION_SCHEMA
            resolved = resolved_by_key.get(key)
            if resolved is not None:
                if source.phase != "purchased":
                    raise CohortDocumentMaterializationError(
                        "resolved post-recovery proof cannot bind a free document: "
                        f"{key[0]}/{key[1]}"
                    )
                rebased_manifest["recovery_origin"] = "unknown_status_attempt"
                rebased_manifest["resolved_post_recovery_sha256"] = _required_sha256(
                    resolved, "record_sha256"
                )
            rebased_clearance = dict(clearance_by_key[key])
            rebased_clearance["local_path"] = destination_relative.as_posix()
            rebased_clearance["sha256"] = expected_hash
            rebased_clearance["byte_count"] = expected_bytes
            rebased_clearance["materialization_schema_version"] = MATERIALIZATION_SCHEMA
            if resolved is not None:
                rebased_clearance["recovery_origin"] = "unknown_status_attempt"
                rebased_clearance["resolved_post_recovery_sha256"] = _required_sha256(
                    resolved, "record_sha256"
                )
            prepared.append(
                PreparedCohortDocument(
                    source=source_path,
                    destination=destination,
                    source_device=device,
                    source_inode=inode,
                    manifest_record=rebased_manifest,
                    clearance_record=rebased_clearance,
                )
            )
    if seen_keys != selected_document_keys:
        missing = sorted(selected_document_keys - seen_keys)
        extra = sorted(seen_keys - selected_document_keys)
        raise CohortDocumentMaterializationError(
            "materialized document identities do not exactly cover the authenticated "
            f"target selection; missing={missing}, extra={extra}"
        )
    if set(resolved_by_key) != required_resolved_keys:
        raise CohortDocumentMaterializationError(
            "resolved post-recovery proof coverage differs; "
            f"missing={sorted(required_resolved_keys - set(resolved_by_key))}; "
            f"extra={sorted(set(resolved_by_key) - required_resolved_keys)}"
        )
    prepared.sort(key=lambda item: _document_key(item.manifest_record))
    manifest = tuple(item.manifest_record for item in prepared)
    clearance = tuple(item.clearance_record for item in prepared)
    return CohortDocumentMaterialization(
        manifest=manifest,
        clearance=clearance,
        documents=tuple(prepared),
        summary={
            "schema_version": MATERIALIZATION_SCHEMA,
            "document_count": len(prepared),
            "free_document_count": phase_counts.get("free", 0),
            "purchased_document_count": phase_counts.get("purchased", 0),
            "document_root": str(document_output_root.resolve(strict=False)),
            "content_addressed": True,
            "source_roots_mutated": False,
        },
    )


def _resolved_record_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = _document_key(record)
        if key in index:
            raise CohortDocumentMaterializationError(
                f"duplicate resolved post-recovery identity: {key[0]}/{key[1]}"
            )
        if record.get("recovery_origin") != "unknown_status_attempt":
            raise CohortDocumentMaterializationError(
                f"invalid resolved post-recovery origin: {key[0]}/{key[1]}"
            )
        _required_sha256(record, "record_sha256")
        index[key] = record
    return index


def publish_cohort_documents(
    documents: Sequence[PreparedCohortDocument],
) -> None:
    """Publish verified bytes with exclusive temporary and final paths."""

    for document in documents:
        expected_hash = _required_sha256(document.manifest_record, "sha256")
        expected_bytes = _required_nonnegative_int(
            document.manifest_record, "byte_count"
        )
        try:
            destination_exists = bool(document.destination.lstat())
        except FileNotFoundError:
            destination_exists = False
        if destination_exists:
            _recover_linked_temporary(
                document.destination,
                expected_hash=expected_hash,
                expected_bytes=expected_bytes,
            )
            _validate_destination(
                document.destination,
                root=document.destination.parents[2],
                expected_hash=expected_hash,
                expected_bytes=expected_bytes,
            )
            continue
        prepare_non_symlink_directory(document.destination.parent)
        temporary = document.destination.with_name(
            f".{document.destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        source_fd = _open_verified_source(document)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            target_fd = os.open(temporary, flags, 0o600)
        except OSError as exc:
            os.close(source_fd)
            raise CohortDocumentMaterializationError(
                f"cannot create exclusive temporary file: {temporary}"
            ) from exc
        try:
            digest = hashlib.sha256()
            byte_count = 0
            try:
                while chunk := os.read(source_fd, _CHUNK_SIZE):
                    digest.update(chunk)
                    byte_count += len(chunk)
                    _write_all(target_fd, chunk)
                os.fsync(target_fd)
            finally:
                os.close(source_fd)
                os.close(target_fd)
            if digest.hexdigest() != expected_hash or byte_count != expected_bytes:
                raise CohortDocumentMaterializationError(
                    f"source changed during copy: {document.source}"
                )
            linked = False
            try:
                os.link(
                    temporary,
                    document.destination,
                    follow_symlinks=False,
                )
                linked = True
            except FileExistsError:
                _validate_destination(
                    document.destination,
                    root=document.destination.parents[2],
                    expected_hash=expected_hash,
                    expected_bytes=expected_bytes,
                )
            if linked:
                _fsync_directory(document.destination.parent)
        finally:
            if temporary.exists():
                temporary.unlink()
                _fsync_directory(document.destination.parent)


def cleanup_orphaned_cohort_document_temporaries(
    documents: Sequence[PreparedCohortDocument],
) -> None:
    """Remove only publisher-owned crash residue before strict output scanning."""

    for document in documents:
        parent = document.destination.parent
        _reject_unsafe_directory_components(parent)
        if not parent.exists():
            continue
        expected_hash = _required_sha256(document.manifest_record, "sha256")
        expected_bytes = _required_nonnegative_int(
            document.manifest_record, "byte_count"
        )
        if document.destination.exists():
            _recover_linked_temporary(
                document.destination,
                expected_hash=expected_hash,
                expected_bytes=expected_bytes,
            )
        prefix = f".{document.destination.name}."
        for sibling in parent.iterdir():
            if not sibling.name.startswith(prefix) or not sibling.name.endswith(".tmp"):
                continue
            metadata = sibling.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise CohortDocumentMaterializationError(
                    f"unsafe materializer temporary file: {sibling}"
                )
            sibling.unlink()
            _fsync_directory(parent)


def _recover_linked_temporary(
    destination: Path,
    *,
    expected_hash: str,
    expected_bytes: int,
) -> None:
    """Remove only the exact linked temp left by a crash after final publication."""

    metadata = destination.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink == 1:
        return
    if metadata.st_nlink != 2:
        raise CohortDocumentMaterializationError(
            f"destination is not a singly linked regular file: {destination}"
        )
    candidates: list[Path] = []
    prefix = f".{destination.name}."
    for sibling in destination.parent.iterdir():
        if not sibling.name.startswith(prefix) or not sibling.name.endswith(".tmp"):
            continue
        sibling_metadata = sibling.lstat()
        if (
            stat.S_ISREG(sibling_metadata.st_mode)
            and sibling_metadata.st_dev == metadata.st_dev
            and sibling_metadata.st_ino == metadata.st_ino
        ):
            candidates.append(sibling)
    if len(candidates) != 1:
        raise CohortDocumentMaterializationError(
            f"destination is not a singly linked regular file: {destination}"
        )
    if _sha256_and_size(destination) != (expected_hash, expected_bytes):
        raise CohortDocumentMaterializationError(
            f"destination content differs from manifest: {destination}"
        )
    candidates[0].unlink()
    _fsync_directory(destination.parent)


def _sha256_and_size(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        digest = hashlib.sha256()
        byte_count = 0
        while chunk := os.read(fd, _CHUNK_SIZE):
            digest.update(chunk)
            byte_count += len(chunk)
        return digest.hexdigest(), byte_count
    finally:
        os.close(fd)


def _open_verified_source(document: PreparedCohortDocument) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(document.source, flags)
    except OSError as exc:
        raise CohortDocumentMaterializationError(
            f"cannot reopen immutable source: {document.source}"
        ) from exc
    metadata = os.fstat(fd)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_dev != document.source_device
        or metadata.st_ino != document.source_inode
    ):
        os.close(fd)
        raise CohortDocumentMaterializationError(
            f"source identity changed before copy: {document.source}"
        )
    return fd


def _inspect_source_file(path: Path, *, root: Path) -> tuple[int, int, str, int]:
    _reject_symlink_components(root)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise CohortDocumentMaterializationError(
            f"source path escapes document root: {path}"
        ) from exc
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise CohortDocumentMaterializationError(
                f"symlink in source path: {cursor}"
            )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise CohortDocumentMaterializationError(
            f"manifest document is unavailable: {path}"
        ) from exc
    try:
        opened = os.fstat(fd)
        current = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise CohortDocumentMaterializationError(
                f"source must be a singly linked regular file: {path}"
            )
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
        if resolved_root not in resolved_path.parents:
            raise CohortDocumentMaterializationError(
                f"source path escapes document root: {path}"
            )
        digest = hashlib.sha256()
        byte_count = 0
        while chunk := os.read(fd, _CHUNK_SIZE):
            digest.update(chunk)
            byte_count += len(chunk)
        return opened.st_dev, opened.st_ino, digest.hexdigest(), byte_count
    finally:
        os.close(fd)


def _validate_destination(
    path: Path,
    *,
    root: Path,
    expected_hash: str,
    expected_bytes: int,
) -> None:
    absolute_root = root.absolute()
    absolute_path = path.absolute()
    _reject_unsafe_directory_components(absolute_root)
    if absolute_root not in absolute_path.parents:
        raise CohortDocumentMaterializationError(
            f"destination escapes output document root: {path}"
        )
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
        _recover_linked_temporary(
            path,
            expected_hash=expected_hash,
            expected_bytes=expected_bytes,
        )
        metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise CohortDocumentMaterializationError(
            f"content-addressed destination is not a singly linked regular file: {path}"
        )
    device, inode, digest, byte_count = _inspect_source_file(path, root=root)
    del device, inode
    if digest != expected_hash or byte_count != expected_bytes:
        raise CohortDocumentMaterializationError(
            f"content-addressed destination collision: {path}"
        )


def _reject_overlapping_roots(output: Path, sources: Sequence[Path]) -> None:
    output_resolved = output.resolve(strict=False)
    source_resolved = tuple(path.resolve(strict=False) for path in sources)
    if len(set(source_resolved)) != len(source_resolved):
        raise CohortDocumentMaterializationError("duplicate source document roots")
    for source in source_resolved:
        if (
            output_resolved == source
            or output_resolved.is_relative_to(source)
            or source.is_relative_to(output_resolved)
        ):
            raise CohortDocumentMaterializationError(
                "output root overlaps an immutable source document root"
            )


def _unique_clearance_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = _document_key(record)
        if key in indexed:
            raise CohortDocumentMaterializationError(
                f"duplicate clearance identity: {key[0]}/{key[1]}"
            )
        indexed[key] = record
    return indexed


def _document_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (
        _required_string(record, "candidate_id"),
        _required_string(record, "source_document_id"),
    )


def _safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CohortDocumentMaterializationError(
            f"unsafe document local_path: {value!r}"
        )
    return path


def _required_string(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CohortDocumentMaterializationError(
            f"document record requires nonempty {field}"
        )
    return value.strip()


def _required_sha256(record: Mapping[str, Any], field: str) -> str:
    value = _required_string(record, field).lower()
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise CohortDocumentMaterializationError(f"document record has invalid {field}")
    return value


def _required_nonnegative_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CohortDocumentMaterializationError(f"document record has invalid {field}")
    return value


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise CohortDocumentMaterializationError(
                f"symlink in trusted root path: {current}"
            )


def _reject_unsafe_directory_components(path: Path) -> None:
    """Reject existing destination-root components that are not real directories."""

    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(metadata.st_mode):
            raise CohortDocumentMaterializationError(
                f"symlink in destination root path: {current}"
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise CohortDocumentMaterializationError(
                f"destination root component is not a directory: {current}"
            )


def prepare_non_symlink_directory(path: Path) -> Path:
    """Create a directory tree one component at a time without following links."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                metadata = current.lstat()
            else:
                metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise CohortDocumentMaterializationError(
                f"symlink in destination path: {current}"
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise CohortDocumentMaterializationError(
                f"destination parent is not a directory: {current}"
            )
    return absolute


def require_non_symlink_components(path: Path) -> None:
    """Reject an existing file path that traverses any symbolic link."""

    _reject_symlink_components(path.absolute())


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:  # pragma: no cover - defensive OS invariant
            raise CohortDocumentMaterializationError("short write to temporary file")
        view = view[written:]


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
