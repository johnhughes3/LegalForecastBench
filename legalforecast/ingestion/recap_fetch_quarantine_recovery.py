"""Recover unknown-status RECAP Fetch material into a controlled quarantine.

The paid executor deliberately persists only a hash of CourtListener's download
locator.  This module is the separate, non-charging recovery boundary: it
revalidates the exact public RECAP document, downloads the bytes into an
immutable local quarantine, and advances only the material state.  It never
makes the document parser-eligible and never persists the provider URL.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    PurchaseMaterialState,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    COURTLISTENER_RECAP_FETCH_PROVIDER,
    CourtListenerRecapFetchConfig,
    CourtListenerRecapFetchError,
    RecapFetchTransport,
    verified_recap_download_url,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentSource,
)
from legalforecast.path_safety import safe_path_component

SCHEMA_VERSION = "legalforecast.recap_fetch_quarantine_recovery.v1"
RESTRICTION_SCHEMA_VERSION = "legalforecast.post_recovery_restriction_evidence.v1"
UNKNOWN_RECOVERY_ORIGIN = "unknown_status_attempt"
_RETRYABLE = frozenset({429, 500, 502, 503, 504})
_FRESH_PUBLIC_EVIDENCE = (
    "courtlistener_recap_fetch_fresh_detail_exact_match",
    "courtlistener_recap_fetch_is_available_true",
    "courtlistener_recap_fetch_is_sealed_false",
    "courtlistener_recap_fetch_no_positive_private_marker",
)


class RecapFetchQuarantineRecoveryError(RuntimeError):
    """Raised when unknown-origin material cannot safely enter quarantine."""


def recover_recap_fetch_quarantine_documents(
    *,
    journal: CaseDevPurchaseJournal,
    allowed_documents: Mapping[str, Mapping[str, str]],
    attempt_policy_sha256: str,
    output_root: Path,
    source: FreeDocumentSource,
    config: CourtListenerRecapFetchConfig,
    transport: RecapFetchTransport,
    before_request: Callable[[str, str], None] | None = None,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    """Recover every authorized available document without clearing it.

    Existing canonical bytes are replayed only when their hash and size match
    the journal.  A first recovery always obtains fresh CourtListener detail and
    requires it to match the delivery-time detail and locator commitments.
    """

    if output_root.is_symlink():
        raise RecapFetchQuarantineRecoveryError(
            "quarantine output root must not be a symbolic link"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    output_root = output_root.resolve()
    records: list[Mapping[str, Any]] = []
    restrictions: list[Mapping[str, Any]] = []
    for document_id, authority in sorted(allowed_documents.items()):
        candidate_id = authority.get("case_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise RecapFetchQuarantineRecoveryError(
                f"attempt authority lacks candidate identity: {document_id}"
            )
        operation = journal.operation_evidence(document_id)
        if operation is None:
            raise RecapFetchQuarantineRecoveryError(
                f"purchase operation is missing: {document_id}"
            )
        _validate_operation(
            operation,
            candidate_id=candidate_id,
            document_id=document_id,
            attempt_policy_sha256=attempt_policy_sha256,
        )
        destination = _destination(output_root, candidate_id, document_id)
        detail = _fresh_detail(
            document_id,
            config=config,
            transport=transport,
            before_request=before_request,
        )
        detail_digest = _sha256_json(detail)
        download_url = _verified_download_url(detail, document_id)
        url_digest = hashlib.sha256(download_url.encode("utf-8")).hexdigest()
        evidence = _mapping(operation.get("material_evidence"), "material evidence")
        if detail_digest != evidence.get(
            "provider_detail_sha256"
        ) or url_digest != evidence.get("download_url_sha256"):
            raise RecapFetchQuarantineRecoveryError(
                "fresh CourtListener material conflicts with delivery commitment: "
                f"{document_id}"
            )
        _require_fresh_public_detail(detail, document_id)
        restrictions.append(
            _restriction_record(
                candidate_id=candidate_id,
                document_id=document_id,
                detail=detail,
                detail_sha256=detail_digest,
            )
        )
        state = operation["material_state"]
        if state in {
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE,
            PurchaseMaterialState.CLEARED_PUBLIC,
        }:
            digest, byte_count = _validate_existing(destination)
            evidence = _mapping(operation.get("material_evidence"), "material evidence")
            if digest != evidence.get("content_sha256") or byte_count != evidence.get(
                "byte_count"
            ):
                raise RecapFetchQuarantineRecoveryError(
                    f"canonical quarantined bytes conflict with journal: {document_id}"
                )
            records.append(
                _record(
                    candidate_id=candidate_id,
                    document_id=document_id,
                    operation=operation,
                    attempt_policy_sha256=attempt_policy_sha256,
                    output_root=output_root,
                    destination=destination,
                    digest=digest,
                    byte_count=byte_count,
                )
            )
            continue
        try:
            fetch = source.fetch(download_url)
        except (FreeDocumentDownloadError, RuntimeError) as exc:
            raise RecapFetchQuarantineRecoveryError(
                f"quarantine download failed for {document_id}"
            ) from exc
        _validate_pdf(fetch.content, document_id)
        digest, byte_count, _ = _publish_immutable(destination, fetch.content)
        journal.record_quarantined_material_bytes(
            document_id, content_sha256=digest, byte_count=byte_count
        )
        operation = journal.operation_evidence(document_id)
        if operation is None:
            raise CaseDevPurchaseLedgerError("purchase operation disappeared")
        records.append(
            _record(
                candidate_id=candidate_id,
                document_id=document_id,
                operation=operation,
                attempt_policy_sha256=attempt_policy_sha256,
                output_root=output_root,
                destination=destination,
                digest=digest,
                byte_count=byte_count,
            )
        )
    return tuple(records), tuple(restrictions)


def write_recap_fetch_quarantine_manifest(
    path: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    """Atomically publish an immutable canonical JSONL manifest."""

    payload = b"".join(
        (json.dumps(dict(record), sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for record in records
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RecapFetchQuarantineRecoveryError(
                "existing quarantine manifest conflicts with recovered lineage"
            )
        return
    _atomic_link_new(path, payload)


def write_recap_fetch_restriction_evidence(
    path: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    """Publish immutable URL-free fresh-detail public restriction evidence."""

    write_recap_fetch_quarantine_manifest(path, records)


def _validate_operation(
    operation: Mapping[str, Any],
    *,
    candidate_id: str,
    document_id: str,
    attempt_policy_sha256: str,
) -> None:
    state = operation.get("material_state")
    if (
        operation.get("candidate_id") != candidate_id
        or operation.get("material_authority") != UNKNOWN_RECOVERY_ORIGIN
        or operation.get("attempt_policy_sha256") != attempt_policy_sha256
        or not isinstance(operation.get("operation_key"), str)
        or state
        not in {
            PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE,
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE,
            PurchaseMaterialState.CLEARED_PUBLIC,
        }
    ):
        raise RecapFetchQuarantineRecoveryError(
            f"purchase lacks recoverable unknown-origin material: {document_id}"
        )
    evidence = _mapping(operation.get("material_evidence"), "material evidence")
    for field in (
        "provider_detail_sha256",
        "queue_response_sha256",
        "download_url_sha256",
    ):
        value = evidence.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise RecapFetchQuarantineRecoveryError(
                f"purchase material lacks {field}: {document_id}"
            )


def _fresh_detail(
    document_id: str,
    *,
    config: CourtListenerRecapFetchConfig,
    transport: RecapFetchTransport,
    before_request: Callable[[str, str], None] | None,
) -> Mapping[str, Any]:
    path = f"/recap-documents/{_identifier(document_id)}/"
    for attempt in range(3):
        if before_request is not None:
            before_request("GET", path)
        response = transport.request(
            method="GET",
            path=path,
            form={},
            headers={
                "Authorization": f"Token {config.api_token}",
                "Accept": "application/json",
            },
            timeout_seconds=config.timeout_seconds,
        )
        if 200 <= response.status_code < 300:
            return response.payload
        if response.status_code not in _RETRYABLE or attempt == 2:
            raise RecapFetchQuarantineRecoveryError(
                f"CourtListener detail returned HTTP {response.status_code}: "
                f"{document_id}"
            )
    raise AssertionError("unreachable")


def _verified_download_url(payload: Mapping[str, Any], document_id: str) -> str:
    # Keep this validation local so the controlled recovery boundary does not
    # expose or return a raw URL to any manifest-producing caller.
    try:
        return verified_recap_download_url(payload, document_id)
    except CourtListenerRecapFetchError as exc:
        raise RecapFetchQuarantineRecoveryError(str(exc)) from exc


def _require_fresh_public_detail(detail: Mapping[str, Any], document_id: str) -> None:
    if (
        detail.get("is_available") is not True
        or detail.get("is_sealed") is not False
        or detail.get("is_private") not in {False, None}
    ):
        raise RecapFetchQuarantineRecoveryError(
            f"fresh CourtListener detail is not explicitly public: {document_id}"
        )


def _destination(output_root: Path, candidate_id: str, document_id: str) -> Path:
    candidate = safe_path_component(candidate_id, field_name="candidate_id")
    document = safe_path_component(document_id, field_name="source_document_id")
    parent = output_root / candidate
    if parent.exists() and parent.is_symlink():
        raise RecapFetchQuarantineRecoveryError(
            f"quarantine candidate directory is a symbolic link: {candidate_id}"
        )
    parent.mkdir(parents=True, exist_ok=True)
    return parent / f"{document}.pdf"


def _validate_pdf(content: bytes, document_id: str) -> None:
    if not content or not content.lstrip().startswith(b"%PDF"):
        raise RecapFetchQuarantineRecoveryError(
            f"quarantine document is not a PDF: {document_id}"
        )


def _publish_immutable(path: Path, content: bytes) -> tuple[str, int, bool]:
    digest = hashlib.sha256(content).hexdigest()
    if path.exists():
        existing_digest, existing_size = _validate_existing(path)
        if existing_digest != digest or existing_size != len(content):
            raise RecapFetchQuarantineRecoveryError(
                f"existing quarantine document conflicts: {path.name}"
            )
        return digest, len(content), True
    _atomic_link_new(path, content)
    return digest, len(content), False


def _atomic_link_new(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".partial"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            if path.read_bytes() != content:
                raise RecapFetchQuarantineRecoveryError(
                    f"concurrent quarantine publication conflicts: {path.name}"
                ) from exc
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_existing(path: Path) -> tuple[str, int]:
    stat = path.lstat()
    if not path.is_file() or path.is_symlink() or stat.st_nlink != 1:
        raise RecapFetchQuarantineRecoveryError(
            f"canonical quarantine path is not a private regular file: {path.name}"
        )
    content = path.read_bytes()
    _validate_pdf(content, path.stem)
    return hashlib.sha256(content).hexdigest(), len(content)


def _record(
    *,
    candidate_id: str,
    document_id: str,
    operation: Mapping[str, Any],
    attempt_policy_sha256: str,
    output_root: Path,
    destination: Path,
    digest: str,
    byte_count: int,
) -> Mapping[str, Any]:
    evidence = _mapping(operation.get("material_evidence"), "material evidence")
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
        "recovery_origin": UNKNOWN_RECOVERY_ORIGIN,
        "attempt_policy_sha256": attempt_policy_sha256,
        "purchase_operation_key": operation["operation_key"],
        "fresh_recap_detail_sha256": evidence["provider_detail_sha256"],
        "local_path": destination.relative_to(output_root).as_posix(),
        "sha256": digest,
        "byte_count": byte_count,
        "free_or_purchased": "purchased",
        "parser_eligible": False,
        "packet_eligible": False,
    }


def _restriction_record(
    *,
    candidate_id: str,
    document_id: str,
    detail: Mapping[str, Any],
    detail_sha256: str,
) -> Mapping[str, Any]:
    return {
        "schema_version": RESTRICTION_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "source_provider": "courtlistener_recap_fetch_fresh_detail",
        "fresh_recap_detail_sha256": detail_sha256,
        "is_available": True,
        "is_sealed": False,
        "is_private": detail.get("is_private"),
        "redaction_or_seal_status": "public",
        "restriction_status": "public",
        "restriction_evidence": list(_FRESH_PUBLIC_EVIDENCE),
    }


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecapFetchQuarantineRecoveryError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _sha256_json(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _identifier(value: str) -> str:
    if not value.isdigit() or not value:
        raise RecapFetchQuarantineRecoveryError(
            "RECAP document identity must contain only decimal digits"
        )
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
