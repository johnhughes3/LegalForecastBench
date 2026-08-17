"""Paid CourtListener RECAP Fetch construction and provenance sidecars.

The purchase journal's response JSON is authenticated by the Cycle 1
operation/state commitments.  Queue-lag provenance is therefore emitted next
to the journal, keyed by the exact operation digest, and never added to the
authoritative response.  The wrapper is deliberately installed only by the
paid-client factory so the restored ``courtlistener_recap_fetch`` byte path
stays unchanged for every existing caller.
"""

from __future__ import annotations

import hashlib
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
    root = (
        confirmation_provenance_root(journal.path)
        if output_root is None
        else Path(output_root)
    )
    _ensure_output_directory(root)
    paths: list[Path] = []
    directory_fd = _open_directory(root)
    try:
        for record in confirmed:
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
    source_document_id = _positive_decimal(operation.get("source_document_id"))
    candidate_id = _required_text(operation.get("candidate_id"), "candidate_id")
    queue_id = _positive_decimal(response.get("queue_id"))
    restrictions_value = response.get("post_delivery_restrictions")
    if not isinstance(restrictions_value, Mapping):
        raise ConfirmationProvenanceError(
            "confirmed CourtListener operation lacks document evidence"
        )
    restrictions = cast(Mapping[str, object], restrictions_value)
    provider_detail_sha256 = _sha256_json(restrictions)
    has_queue_response = "queue_response" in response
    queue_response_value = response.get("queue_response")
    if not has_queue_response:
        confirmation_evidence = _CONFIRMATION_EVIDENCE_PUBLIC
        queue_response_sha256 = None
    else:
        if not isinstance(queue_response_value, Mapping):
            raise ConfirmationProvenanceError(
                "queue confirmation evidence must carry status 2"
            )
        queue_response = cast(Mapping[str, object], queue_response_value)
        if queue_response.get("status") != 2:
            raise ConfirmationProvenanceError(
                "queue confirmation evidence must carry status 2"
            )
        confirmation_evidence = _CONFIRMATION_EVIDENCE_QUEUE
        queue_response_sha256 = _sha256_json(queue_response)
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
        "queue_id": queue_id,
        "queue_response_sha256": queue_response_sha256,
        "schema_version": CONFIRMATION_PROVENANCE_SCHEMA_VERSION,
        "source_document_id": source_document_id,
    }


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
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ConfirmationProvenanceError(
            "confirmation provenance writes require O_NOFOLLOW"
        )
    try:
        descriptor = os.open(
            name,
            flags | nofollow,
            0o600,
            dir_fd=directory_fd,
        )
    except FileExistsError:
        existing = _read_existing(directory_fd, name)
        if existing != payload:
            raise ConfirmationProvenanceError(
                f"confirmation provenance output conflicts: {name}"
            ) from None
        return
    except OSError as exc:
        raise ConfirmationProvenanceError(
            f"unable to create confirmation provenance output: {name}"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.unlink(name, dir_fd=directory_fd)
        except OSError:
            # Preserve the original write failure; cleanup is best effort.
            pass
        raise


def _read_existing(directory_fd: int, name: str) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ConfirmationProvenanceError(
            "confirmation provenance reads require O_NOFOLLOW"
        )
    descriptor: int | None = None
    try:
        descriptor = os.open(name, os.O_RDONLY | nofollow, dir_fd=directory_fd)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ConfirmationProvenanceError(
                "confirmation provenance output must be a singly linked file"
            )
        return os.read(descriptor, metadata.st_size)
    except ConfirmationProvenanceError:
        raise
    except OSError as exc:
        raise ConfirmationProvenanceError(
            "unable to read existing confirmation provenance output"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


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

    client.execute_purchase_plan = execute_purchase_plan
    client.execute_one_document = execute_one_document


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
) -> tuple[Path, ...]:
    """Reconcile one operation and emit its successor observation, if confirmed."""

    journal.reconcile(evidence)
    return write_confirmation_provenance_sidecars(journal)


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
