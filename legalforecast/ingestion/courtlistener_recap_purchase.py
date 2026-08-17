"""Paid CourtListener RECAP Fetch construction and provenance sidecars.

The purchase journal's response JSON is authenticated by the Cycle 1
operation/state commitments.  Queue-lag provenance is therefore emitted next
to the journal, keyed by the exact operation digest, and never added to the
authoritative response.  The wrapper is deliberately installed only by the
paid-client factory so the restored ``courtlistener_recap_fetch`` byte path
stays unchanged for every existing caller.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast

from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes,
    canonical_json_value_bytes,
)
from legalforecast.ingestion.courtlistener_provider_identity import (
    COURTLISTENER_RECAP_FETCH_PROVIDER,
)

CONFIRMATION_PROVENANCE_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative sidecar; no canonical commitments
    "legalforecast.recap_fetch_confirmation_provenance.v1"
)
_CONFIRMATION_EVIDENCE_QUEUE = "recap_fetch_queue_status_2"
_CONFIRMATION_EVIDENCE_PUBLIC = "public_document_during_queue_lag"
_CONFIRMATION_EVIDENCE = frozenset(
    {_CONFIRMATION_EVIDENCE_QUEUE, _CONFIRMATION_EVIDENCE_PUBLIC}
)
_CONFIRMATION_RECORD_FIELDS = frozenset(
    {
        "canonical_purchase_operation_sha256",
        "candidate_id",
        "confirmation_evidence",
        "cycle_id",
        "non_authoritative",
        "provider_detail_sha256",
        "purchase_policy_sha256",
        "queue_id",
        "queue_response_sha256",
        "schema_version",
        "source_document_id",
    }
)


class _PurchasePolicy(Protocol):
    @property
    def cycle_id(self) -> str:
        raise NotImplementedError

    @property
    def policy_sha256(self) -> str:
        raise NotImplementedError


class _PurchaseJournal(Protocol):
    @property
    def path(self) -> Path:
        raise NotImplementedError

    @property
    def policy(self) -> _PurchasePolicy:
        raise NotImplementedError

    def operation_records(self) -> tuple[Mapping[str, object], ...]:
        raise NotImplementedError

    def reconcile(self, evidence: Mapping[str, object]) -> None:
        raise NotImplementedError


class _PaidRecapClient(Protocol):
    journal: _PurchaseJournal
    execute_purchase_plan: Callable[..., object]
    execute_one_document: Callable[[str, str], object]
    apply_broker_receipt: Callable[[str, Mapping[str, object]], None]


class ConfirmationProvenanceError(ValueError):
    """A non-authoritative confirmation sidecar could not be trusted."""


def confirmation_provenance_root(ledger_path: str | Path) -> Path:
    """Return the private sidecar directory beside one purchase ledger."""

    return Path(f"{Path(ledger_path).resolve()}.confirmation-provenance")


def write_confirmation_provenance_sidecars(
    journal: _PurchaseJournal,
    *,
    output_root: Path | None = None,
) -> tuple[Path, ...]:
    """Write immutable queue-lag observations without mutating *journal*.

    A file is keyed by ``canonical_purchase_operation_sha256``.  If later fee
    reconciliation changes that canonical operation, a new digest-keyed
    observation is written and the earlier observation remains an audit record.
    """

    records = tuple(
        _confirmation_record(journal, operation)
        for operation in journal.operation_records()
    )
    confirmed = tuple(record for record in records if record is not None)
    if not confirmed:
        return ()
    return _write_confirmation_records(
        journal,
        confirmed,
        output_root=output_root,
    )


def _write_confirmation_records(
    journal: _PurchaseJournal,
    records: tuple[Mapping[str, object], ...],
    *,
    output_root: Path | None,
) -> tuple[Path, ...]:
    root = (
        confirmation_provenance_root(journal.path)
        if output_root is None
        else Path(output_root)
    )
    _ensure_output_directory(root)
    paths: list[Path] = []
    directory_fd = _open_directory(root)
    try:
        for record in records:
            digest = str(record["canonical_purchase_operation_sha256"])
            payload = canonical_json_bytes(
                record,
                error_type=ConfirmationProvenanceError,
                error_message="confirmation provenance is not canonical JSON",
            )
            name = f"{digest}.json"
            _write_create_once(directory_fd, name, payload)
            paths.append(root / name)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return tuple(paths)


def _confirmation_record(
    journal: _PurchaseJournal,
    operation: Mapping[str, object],
) -> dict[str, object] | None:
    if operation.get("status") != "confirmed":
        return None
    response_value = operation.get("response")
    if not isinstance(response_value, Mapping):
        raise ConfirmationProvenanceError(
            "confirmed CourtListener operation lacks response evidence"
        )
    response = cast(Mapping[str, object], response_value)
    if response.get("source_provider") != COURTLISTENER_RECAP_FETCH_PROVIDER:
        return None
    if "confirmation_evidence" in response:
        raise ConfirmationProvenanceError(
            "confirmation provenance must remain outside response_json"
        )
    if "queue_id" not in response or "post_delivery_restrictions" not in response:
        # Billing reconciliation can confirm a submitted or queued row that never
        # carried queue-lag confirmation evidence: a submitted response has no
        # queue identity and a queued response has no provider document.  Such a
        # row is ineligible for a confirmation observation, not malformed, so the
        # supported reconciliation flow must not fail after it has already
        # committed.  Present-but-malformed evidence still fails closed below.
        return None
    restrictions_value = response.get("post_delivery_restrictions")
    if not isinstance(restrictions_value, Mapping):
        raise ConfirmationProvenanceError(
            "confirmed CourtListener operation lacks document evidence"
        )
    has_queue_response = "queue_response" in response
    queue_response_value = response.get("queue_response")
    if has_queue_response and not isinstance(queue_response_value, Mapping):
        raise ConfirmationProvenanceError(
            "queue confirmation evidence must carry status 2"
        )
    return _confirmation_record_from_evidence(
        journal,
        operation,
        queue_id=response.get("queue_id"),
        provider_detail=cast(Mapping[str, object], restrictions_value),
        queue_response=(
            cast(Mapping[str, object], queue_response_value)
            if has_queue_response
            else None
        ),
    )


def _confirmation_record_from_evidence(
    journal: _PurchaseJournal,
    operation: Mapping[str, object],
    *,
    queue_id: object,
    provider_detail: Mapping[str, object],
    queue_response: Mapping[str, object] | None,
) -> dict[str, object]:
    source_document_id = _positive_decimal(operation.get("source_document_id"))
    candidate_id = _required_text(operation.get("candidate_id"), "candidate_id")
    normalized_queue_id = _positive_decimal(queue_id)
    provider_detail_sha256 = _sha256_json(provider_detail)
    confirmation_evidence = (
        _CONFIRMATION_EVIDENCE_PUBLIC
        if queue_response is None
        else _CONFIRMATION_EVIDENCE_QUEUE
    )
    if queue_response is None:
        queue_response_sha256 = None
    else:
        if queue_response.get("status") != 2:
            raise ConfirmationProvenanceError(
                "queue confirmation evidence must carry status 2"
            )
        queue_response_sha256 = _sha256_json(queue_response)
    has_queue_response = queue_response is not None
    if has_queue_response != (queue_response_sha256 is not None):
        raise ConfirmationProvenanceError(
            "queue confirmation digest does not match response evidence"
        )
    if confirmation_evidence not in _CONFIRMATION_EVIDENCE:
        raise AssertionError("unreachable confirmation evidence")
    operation_digest = _canonical_operation_sha256(operation)
    return {
        "canonical_purchase_operation_sha256": operation_digest,
        "candidate_id": candidate_id,
        "confirmation_evidence": confirmation_evidence,
        "cycle_id": journal.policy.cycle_id,
        "non_authoritative": True,
        "provider_detail_sha256": provider_detail_sha256,
        "purchase_policy_sha256": journal.policy.policy_sha256,
        "queue_id": normalized_queue_id,
        "queue_response_sha256": queue_response_sha256,
        "schema_version": CONFIRMATION_PROVENANCE_SCHEMA_VERSION,
        "source_document_id": source_document_id,
    }


def _broker_confirmation_record(
    journal: _PurchaseJournal,
    operation: Mapping[str, object],
    *,
    queue_response: Mapping[str, object],
    provider_detail: Mapping[str, object],
) -> dict[str, object] | None:
    if operation.get("status") != "confirmed":
        return None
    response_value = operation.get("response")
    if not isinstance(response_value, Mapping):
        raise ConfirmationProvenanceError(
            "confirmed CourtListener operation lacks response evidence"
        )
    response = cast(Mapping[str, object], response_value)
    if response.get("source_provider") != COURTLISTENER_RECAP_FETCH_PROVIDER:
        return None
    if "confirmation_evidence" in response:
        raise ConfirmationProvenanceError(
            "confirmation provenance must remain outside response_json"
        )
    return _confirmation_record_from_evidence(
        journal,
        operation,
        queue_id=response.get("queue_id"),
        provider_detail=provider_detail,
        queue_response=queue_response,
    )


def _ensure_output_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.lstat()
    except OSError as exc:
        raise ConfirmationProvenanceError(
            "confirmation provenance output directory is unavailable"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ConfirmationProvenanceError(
            "confirmation provenance output must be a real directory"
        )


def _open_directory(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ConfirmationProvenanceError(
            "confirmation provenance writes require O_NOFOLLOW"
        )
    try:
        descriptor = os.open(path, flags | nofollow)
        metadata = os.fstat(descriptor)
    except OSError as exc:
        raise ConfirmationProvenanceError(
            "confirmation provenance output directory cannot be opened"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise ConfirmationProvenanceError(
            "confirmation provenance output is not a directory"
        )
    return descriptor


def _write_create_once(directory_fd: int, name: str, payload: bytes) -> None:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ConfirmationProvenanceError(
            "confirmation provenance writes require O_NOFOLLOW"
        )
    stage_name = f".{name}.{hashlib.sha256(payload).hexdigest()}.partial"
    descriptor = -1
    stage_metadata: os.stat_result | None = None
    try:
        try:
            descriptor = os.open(
                stage_name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | nofollow,
                0o600,
                dir_fd=directory_fd,
            )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            _write_all(descriptor, payload)
            os.fsync(descriptor)
        except FileExistsError:
            descriptor = os.open(
                stage_name,
                os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC | nofollow,
                dir_fd=directory_fd,
            )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            stage_metadata = _require_recoverable_stage(
                descriptor,
                stage_name,
                expected_size=len(payload),
                directory_fd=directory_fd,
                output_name=name,
                allow_incomplete_single_link=True,
            )
            if stage_metadata.st_size < len(payload):
                os.ftruncate(descriptor, 0)
                _write_all(descriptor, payload)
                os.fsync(descriptor)
                stage_metadata = _require_recoverable_stage(
                    descriptor,
                    stage_name,
                    expected_size=len(payload),
                    directory_fd=directory_fd,
                    output_name=name,
                )
            if _read_fd(descriptor, stage_name) != payload:
                raise ConfirmationProvenanceError(
                    "existing confirmation provenance staging file differs"
                ) from None
            os.fsync(descriptor)
        else:
            stage_metadata = _require_recoverable_stage(
                descriptor,
                stage_name,
                expected_size=len(payload),
                directory_fd=directory_fd,
                output_name=name,
            )
        assert stage_metadata is not None
        try:
            os.link(
                stage_name,
                name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except (FileExistsError, FileNotFoundError):
            if _read_at(directory_fd, name, linked_to=stage_metadata) != payload:
                raise ConfirmationProvenanceError(
                    f"confirmation provenance output conflicts: {name}"
                ) from None
        else:
            if _read_at(directory_fd, name, linked_to=stage_metadata) != payload:
                raise ConfirmationProvenanceError(
                    f"confirmation provenance output changed while publishing: {name}"
                )
        _unlink_if_same_inode(directory_fd, stage_name, stage_metadata)
        os.fsync(directory_fd)
        if _read_existing(directory_fd, name) != payload:
            raise ConfirmationProvenanceError(
                f"confirmation provenance output changed while publishing: {name}"
            )
    except ConfirmationProvenanceError:
        raise
    except OSError as exc:
        raise ConfirmationProvenanceError(
            f"unable to publish confirmation provenance output: {name}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if stage_metadata is not None:
            try:
                _unlink_if_same_inode(directory_fd, stage_name, stage_metadata)
                os.fsync(directory_fd)
            except OSError:
                # Preserve the original publish result; cleanup is best effort.
                pass


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("confirmation provenance write made no progress")
        view = view[written:]


def _read_at(
    directory_fd: int,
    name: str,
    *,
    linked_to: os.stat_result | None = None,
    required_nlink: int | None = None,
) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ConfirmationProvenanceError(
            "confirmation provenance reads require O_NOFOLLOW"
        )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | nofollow,
            dir_fd=directory_fd,
        )
        metadata = os.fstat(descriptor)
        recoverable_link = (
            linked_to is not None
            and metadata.st_nlink == 2
            and _same_inode(metadata, linked_to)
        )
        required_link = (
            required_nlink is not None
            and linked_to is not None
            and metadata.st_nlink == required_nlink
            and _same_inode(metadata, linked_to)
        )
        valid_links = (
            required_link
            if required_nlink is not None
            else metadata.st_nlink == 1 or recoverable_link
        )
        if not stat.S_ISREG(metadata.st_mode) or not valid_links:
            raise ConfirmationProvenanceError(
                "confirmation provenance output must be a singly linked file"
            )
        return _read_fd(descriptor, name)
    except ConfirmationProvenanceError:
        raise
    except OSError as exc:
        raise ConfirmationProvenanceError(
            "unable to read existing confirmation provenance output"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_existing(directory_fd: int, name: str) -> bytes:
    return _read_at(directory_fd, name)


def _read_existing_with_stage_recovery(
    directory_fd: int,
    name: str,
) -> tuple[bytes, tuple[str, os.stat_result] | None]:
    try:
        return _read_existing(directory_fd, name), None
    except ConfirmationProvenanceError as read_error:
        try:
            final_metadata = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except OSError:
            raise read_error from None
        if not stat.S_ISREG(final_metadata.st_mode) or final_metadata.st_nlink != 2:
            raise read_error

        stage_prefix = f".{name}."
        try:
            stage_names = tuple(
                entry
                for entry in os.listdir(directory_fd)
                if entry.startswith(stage_prefix) and entry.endswith(".partial")
            )
        except OSError as exc:
            raise ConfirmationProvenanceError(
                "unable to inspect confirmation provenance staging recovery"
            ) from exc
        if len(stage_names) != 1:
            raise ConfirmationProvenanceError(
                "confirmation provenance output has no unique recoverable staging alias"
            ) from read_error
        stage_name = stage_names[0]
        payload = _read_at(
            directory_fd,
            stage_name,
            linked_to=final_metadata,
            required_nlink=2,
        )
        expected_stage_name = f".{name}.{hashlib.sha256(payload).hexdigest()}.partial"
        if stage_name != expected_stage_name:
            raise ConfirmationProvenanceError(
                "confirmation provenance staging alias digest conflicts"
            ) from read_error
        if (
            _read_at(
                directory_fd,
                name,
                linked_to=final_metadata,
                required_nlink=2,
            )
            != payload
        ):
            raise ConfirmationProvenanceError(
                "confirmation provenance staging alias differs from output"
            ) from read_error
        return payload, (stage_name, final_metadata)


def _complete_existing_stage_recovery(
    directory_fd: int,
    name: str,
    payload: bytes,
    recovery: tuple[str, os.stat_result],
) -> None:
    stage_name, final_metadata = recovery
    try:
        _unlink_if_same_inode(directory_fd, stage_name, final_metadata)
        os.fsync(directory_fd)
    except OSError as exc:
        raise ConfirmationProvenanceError(
            "unable to complete confirmation provenance staging recovery"
        ) from exc
    recovered = _read_at(
        directory_fd,
        name,
        linked_to=final_metadata,
        required_nlink=1,
    )
    if recovered != payload:
        raise ConfirmationProvenanceError(
            "confirmation provenance output changed during staging recovery"
        )


def _existing_confirmation_record(
    journal: _PurchaseJournal,
    operation: Mapping[str, object],
    *,
    output_root: Path | None,
) -> Mapping[str, object] | None:
    root = (
        confirmation_provenance_root(journal.path)
        if output_root is None
        else Path(output_root)
    )
    try:
        root.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ConfirmationProvenanceError(
            "confirmation provenance output directory is unavailable"
        ) from exc
    operation_digest = _canonical_operation_sha256(operation)
    name = f"{operation_digest}.json"
    directory_fd = _open_directory(root)
    try:
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ConfirmationProvenanceError(
                "unable to inspect existing confirmation provenance output"
            ) from exc
        payload, recovery = _read_existing_with_stage_recovery(directory_fd, name)
        record = _decode_existing_confirmation_record(
            journal,
            operation,
            payload,
            operation_digest=operation_digest,
        )
        if recovery is not None:
            _complete_existing_stage_recovery(
                directory_fd,
                name,
                payload,
                recovery,
            )
        return record
    finally:
        os.close(directory_fd)


def _decode_existing_confirmation_record(
    journal: _PurchaseJournal,
    operation: Mapping[str, object],
    payload: bytes,
    *,
    operation_digest: str,
) -> Mapping[str, object]:
    try:
        decoded: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfirmationProvenanceError(
            "existing confirmation provenance is not canonical JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise ConfirmationProvenanceError(
            "existing confirmation provenance must be an object"
        )
    record = cast(dict[str, object], decoded)
    if (
        frozenset(record) != _CONFIRMATION_RECORD_FIELDS
        or canonical_json_bytes(
            record,
            error_type=ConfirmationProvenanceError,
            error_message="existing confirmation provenance is not canonical JSON",
        )
        != payload
    ):
        raise ConfirmationProvenanceError(
            "existing confirmation provenance is not canonical JSON"
        )
    _validate_existing_confirmation_record(
        journal,
        operation,
        record,
        operation_digest=operation_digest,
    )
    return record


def _validate_existing_confirmation_record(
    journal: _PurchaseJournal,
    operation: Mapping[str, object],
    record: Mapping[str, object],
    *,
    operation_digest: str,
) -> None:
    response = operation.get("response")
    if not isinstance(response, Mapping):
        raise ConfirmationProvenanceError(
            "confirmed CourtListener operation lacks response evidence"
        )
    normalized_response = cast(Mapping[str, object], response)
    expected_identity = {
        "canonical_purchase_operation_sha256": operation_digest,
        "candidate_id": _required_text(operation.get("candidate_id"), "candidate_id"),
        "cycle_id": journal.policy.cycle_id,
        "non_authoritative": True,
        "purchase_policy_sha256": journal.policy.policy_sha256,
        "queue_id": _positive_decimal(normalized_response.get("queue_id")),
        "schema_version": CONFIRMATION_PROVENANCE_SCHEMA_VERSION,
        "source_document_id": _positive_decimal(operation.get("source_document_id")),
    }
    if any(record.get(key) != value for key, value in expected_identity.items()):
        raise ConfirmationProvenanceError(
            "existing confirmation provenance identity conflicts"
        )
    evidence = record.get("confirmation_evidence")
    provider_digest = record.get("provider_detail_sha256")
    queue_digest = record.get("queue_response_sha256")
    if evidence not in _CONFIRMATION_EVIDENCE or not _is_sha256(provider_digest):
        raise ConfirmationProvenanceError(
            "existing confirmation provenance evidence is invalid"
        )
    if (evidence == _CONFIRMATION_EVIDENCE_PUBLIC and queue_digest is not None) or (
        evidence == _CONFIRMATION_EVIDENCE_QUEUE and not _is_sha256(queue_digest)
    ):
        raise ConfirmationProvenanceError(
            "existing confirmation provenance queue evidence is invalid"
        )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_fd(descriptor: int, label: str) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    before = os.fstat(descriptor)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 64 * 1024):
        chunks.append(chunk)
    after = os.fstat(descriptor)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    payload = b"".join(chunks)
    if before_identity != after_identity or len(payload) != after.st_size:
        raise ConfirmationProvenanceError(f"{label} changed while reading")
    return payload


def _require_recoverable_stage(
    descriptor: int,
    label: str,
    *,
    expected_size: int,
    directory_fd: int,
    output_name: str,
    allow_incomplete_single_link: bool = False,
) -> os.stat_result:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise ConfirmationProvenanceError(f"{label} must be a recoverable regular file")
    if metadata.st_nlink == 1:
        if metadata.st_size == expected_size or (
            allow_incomplete_single_link and metadata.st_size < expected_size
        ):
            return metadata
        raise ConfirmationProvenanceError(f"{label} must be a recoverable regular file")
    if metadata.st_nlink == 2 and metadata.st_size == expected_size:
        try:
            output_metadata = os.stat(
                output_name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            if _same_inode(metadata, output_metadata):
                return metadata
    raise ConfirmationProvenanceError(f"{label} must be a recoverable regular file")


def _unlink_if_same_inode(
    directory_fd: int,
    name: str,
    expected: os.stat_result,
) -> None:
    try:
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not _same_inode(current, expected):
        return
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        # A concurrent publisher may remove the same verified staging alias.
        pass


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ConfirmationProvenanceError(
            f"confirmation provenance {field_name} must be non-empty text"
        )
    return value


def _positive_decimal(value: object) -> str:
    if not isinstance(value, str) or not value.isdecimal() or value.startswith("0"):
        raise ConfirmationProvenanceError(
            "confirmation provenance identifiers must be positive decimals"
        )
    return value


# contract-ratchet: allow sidecar digest adapter reuses shared canonical JSON
def _sha256_json(value: Mapping[str, object]) -> str:
    payload = canonical_json_value_bytes(
        dict(value),
        error_type=ConfirmationProvenanceError,
        error_message="confirmation provenance evidence is not canonical JSON",
    )
    # contract-ratchet: allow observational digest excluded from commitments
    return hashlib.sha256(payload).hexdigest()


# contract-ratchet: allow sidecar digest-key adapter reuses shared canonical JSON
def _canonical_operation_sha256(operation: Mapping[str, object]) -> str:
    """Match the journal helper without creating an authenticated import cycle."""

    payload = canonical_json_value_bytes(
        dict(operation),
        error_type=ConfirmationProvenanceError,
        error_message="confirmation provenance operation is not canonical JSON",
    )
    # contract-ratchet: allow sidecar digest key is excluded from canonical commitments
    return hashlib.sha256(payload).hexdigest()


def _is_courtlistener_recap_fetch_client_type(client_type: object) -> bool:
    return (
        getattr(client_type, "__module__", None)
        == "legalforecast.ingestion.courtlistener_recap_fetch"
        and getattr(client_type, "__qualname__", None)
        == "CourtListenerRecapFetchClient"
    )


def _install_provenance_decorators(
    client: _PaidRecapClient,
    *,
    output_root: Path | None,
) -> None:
    journal = client.journal
    original_plan = client.execute_purchase_plan
    original_one = client.execute_one_document
    original_apply_broker_receipt = client.apply_broker_receipt
    # Observe the already-authorized GET results at the paid-client boundary;
    # the fetch implementation itself is a frozen byte contract for Cycle 1.
    original_request = cast(
        Callable[..., Mapping[str, object]],
        object.__getattribute__(client, "_request"),
    )
    had_instance_request = "_request" in vars(client)
    prior_instance_request = vars(client).get("_request")

    def execute_purchase_plan(*args: object, **kwargs: object) -> object:
        return _execute_with_provenance(
            journal,
            output_root,
            lambda: original_plan(*args, **kwargs),
        )

    def execute_one_document(candidate_id: str, document_id: str) -> object:
        return _execute_with_provenance(
            journal,
            output_root,
            lambda: original_one(candidate_id, document_id),
        )

    def apply_broker_receipt(
        document_id: str,
        receipt: Mapping[str, object],
    ) -> None:
        prior = _operation_for_document(journal, document_id)
        prior_confirmation = (
            None if prior is None else _confirmation_record(journal, prior)
        )
        prior_reconciliation = None if prior is None else prior.get("reconciliation")
        prior_existing_record = (
            _existing_confirmation_record(
                journal,
                prior,
                output_root=output_root,
            )
            if prior is not None and prior_reconciliation is not None
            else None
        )
        if prior_confirmation is not None and prior_reconciliation is None:
            _write_confirmation_records(
                journal,
                (prior_confirmation,),
                output_root=output_root,
            )
        queue_id = receipt.get("id")
        prior_response = None if prior is None else prior.get("response")
        if queue_id is None and isinstance(prior_response, Mapping):
            queue_id = cast(Mapping[str, object], prior_response).get("queue_id")
        queue_path = (
            f"/recap-fetch/{queue_id}/"
            if isinstance(queue_id, str) and queue_id.isdecimal()
            else None
        )
        document_path = f"/recap-documents/{document_id}/"
        queue_observation: Mapping[str, object] | None = None
        provider_observation: Mapping[str, object] | None = None

        def observe_request(
            method: str,
            path: str,
            form: Mapping[str, str],
            *,
            paid: bool,
            retry: bool = False,
            queue_detail: bool = False,
        ) -> Mapping[str, object]:
            nonlocal queue_observation, provider_observation
            result = original_request(
                method,
                path,
                form,
                paid=paid,
                retry=retry,
                queue_detail=queue_detail,
            )
            if method == "GET" and path == queue_path and queue_detail:
                queue_observation = dict(result)
            elif method == "GET" and path == document_path and not paid:
                provider_observation = dict(result)
            return result

        object.__setattr__(client, "_request", observe_request)
        try:
            original_apply_broker_receipt(document_id, receipt)
        finally:
            if had_instance_request:
                object.__setattr__(client, "_request", prior_instance_request)
            else:
                object.__delattr__(client, "_request")

        if (
            queue_observation is not None
            and provider_observation is not None
            and provider_observation.get("is_available") is True
        ):
            operation = _operation_for_document(journal, document_id)
            if operation is not None:
                record = _broker_confirmation_record(
                    journal,
                    operation,
                    queue_response=queue_observation,
                    provider_detail=provider_observation,
                )
                if record is not None:
                    if (
                        prior_existing_record is not None
                        and prior_existing_record["canonical_purchase_operation_sha256"]
                        == record["canonical_purchase_operation_sha256"]
                    ):
                        return
                    _write_confirmation_records(
                        journal,
                        (record,),
                        output_root=output_root,
                    )
                    return
        write_confirmation_provenance_sidecars(journal, output_root=output_root)

    client.execute_purchase_plan = execute_purchase_plan
    client.execute_one_document = execute_one_document
    client.apply_broker_receipt = apply_broker_receipt


def _operation_for_document(
    journal: _PurchaseJournal,
    document_id: str,
) -> Mapping[str, object] | None:
    matches = tuple(
        operation
        for operation in journal.operation_records()
        if operation.get("source_document_id") == document_id
    )
    if len(matches) > 1:
        raise ConfirmationProvenanceError(
            f"confirmation provenance operation is ambiguous: {document_id}"
        )
    return None if not matches else matches[0]


def _execute_with_provenance[ResultT](
    journal: _PurchaseJournal,
    output_root: Path | None,
    operation: Callable[[], ResultT],
) -> ResultT:
    try:
        result = operation()
    except BaseException as exc:
        try:
            write_confirmation_provenance_sidecars(journal, output_root=output_root)
        except BaseException as sidecar_error:
            exc.add_note(f"confirmation provenance sidecar failed: {sidecar_error}")
        raise
    write_confirmation_provenance_sidecars(journal, output_root=output_root)
    return result


def reconcile_purchase(
    journal: _PurchaseJournal,
    evidence: Mapping[str, object],
    *,
    confirmation_provenance_root: Path | None = None,
) -> tuple[Path, ...]:
    """Reconcile one operation and emit its successor observation, if confirmed."""

    journal.reconcile(evidence)
    return write_confirmation_provenance_sidecars(
        journal,
        output_root=confirmation_provenance_root,
    )


def build_paid_recap[ClientT](
    client_type: Callable[..., ClientT],
    config: object,
    *,
    confirmation_provenance_root: Path | None = None,
    **kwargs: object,
) -> ClientT:
    """Build every paid executor with a 16-minute queue-lag window."""

    client = client_type(
        config,
        **kwargs,
        poll_attempts=120,
        poll_backoff_seconds=8.0,
    )
    if _is_courtlistener_recap_fetch_client_type(client_type):
        _install_provenance_decorators(
            cast(_PaidRecapClient, client), output_root=confirmation_provenance_root
        )
    return client
