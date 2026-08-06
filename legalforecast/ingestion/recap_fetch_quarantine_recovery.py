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
import re
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    UNKNOWN_PUBLIC_MATERIAL_RECOVERY_SCHEMA_VERSION,
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    PurchaseMaterialState,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    COURTLISTENER_RECAP_FETCH_PROVIDER,
    CourtListenerRecapFetchConfig,
    CourtListenerRecapFetchError,
    RecapFetchTransport,
    verified_public_recap_download_url,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentSource,
)
from legalforecast.ingestion.recap_fetch_broker import (
    BrokerOutcomeUnknown,
    validate_broker_receipt,
)
from legalforecast.path_safety import safe_path_component

SCHEMA_VERSION = "legalforecast.recap_fetch_quarantine_recovery.v1"
RESTRICTION_SCHEMA_VERSION = "legalforecast.post_recovery_restriction_evidence.v1"
REVIEW_REQUEST_SCHEMA_VERSION = "legalforecast.disclosure_review_request.v1"
TERMINAL_UNAVAILABLE_SCHEMA_VERSION = (
    "legalforecast.recap_fetch_terminal_unavailable.v1"
)
UNKNOWN_RECOVERY_ORIGIN = "unknown_status_attempt"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CANONICAL_USD = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}")
_CANONICAL_QUEUE_ID = re.compile(r"[1-9][0-9]*")
_RETRYABLE = frozenset({429, 500, 502, 503, 504})
_TERMINAL_QUEUE_STATUSES = frozenset({3, 6, 7})
_FRESH_PUBLIC_EVIDENCE = (
    "courtlistener_recap_fetch_fresh_detail_exact_match",
    "courtlistener_recap_fetch_is_available_true",
    "courtlistener_recap_fetch_is_sealed_false",
    "courtlistener_recap_fetch_no_positive_private_marker",
)
_FRESH_PUBLIC_UNKNOWN_SEAL_EVIDENCE = (
    "courtlistener_recap_fetch_fresh_detail_exact_match",
    "courtlistener_recap_fetch_is_available_true",
    "courtlistener_recap_fetch_is_sealed_unknown",
    "courtlistener_recap_fetch_no_positive_private_marker",
    "courtlistener_recap_fetch_public_download_url_allowlisted",
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
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
]:
    """Partition every authorized operation and quarantine available documents.

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
    terminal_unavailable: list[Mapping[str, Any]] = []
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
        selection_document_sha256 = _selection_document_sha256(
            authority, document_id=document_id
        )
        _validate_operation_authority(
            operation,
            candidate_id=candidate_id,
            document_id=document_id,
            attempt_policy_sha256=attempt_policy_sha256,
            selection_document_sha256=selection_document_sha256,
        )
        if operation.get("status") == "failed":
            terminal_unavailable.append(
                _terminal_unavailable_record(
                    operation,
                    candidate_id=candidate_id,
                    document_id=document_id,
                    attempt_policy_sha256=attempt_policy_sha256,
                    selection_document_sha256=selection_document_sha256,
                    expected_reservation=(
                        f"{journal.policy.per_document_reservation_usd:.2f}"
                    ),
                    expected_cycle_id=journal.policy.cycle_id,
                    expected_purchase_policy_sha256=journal.policy.policy_sha256,
                )
            )
            continue
        _validate_recoverable_operation(
            operation,
            candidate_id=candidate_id,
            document_id=document_id,
            attempt_policy_sha256=attempt_policy_sha256,
            selection_document_sha256=selection_document_sha256,
        )
        destination = _destination(output_root, candidate_id, document_id)
        detail = _fresh_detail(
            document_id,
            config=config,
            transport=transport,
            before_request=before_request,
        )
        detail_digest = _sha256_json(detail)
        _require_fresh_public_detail(detail, document_id)
        download_url = _verified_download_url(detail, document_id)
        url_digest = hashlib.sha256(download_url.encode("utf-8")).hexdigest()
        if operation["material_state"] is PurchaseMaterialState.NOT_RECOVERED:
            journal.mark_unknown_public_material_available(
                document_id,
                candidate_id=candidate_id,
                operation_key=str(operation["operation_key"]),
                attempt_policy_sha256=attempt_policy_sha256,
                attempt_document_sha256=_selection_document_sha256(
                    authority, document_id=document_id
                ),
                provider_detail_sha256=detail_digest,
                download_url_sha256=url_digest,
            )
            refreshed = journal.operation_evidence(document_id)
            if refreshed is None:
                raise CaseDevPurchaseLedgerError(
                    "purchase operation disappeared during public recovery"
                )
            operation = refreshed
        evidence = _mapping(operation.get("material_evidence"), "material evidence")
        if detail_digest != evidence.get(
            "provider_detail_sha256"
        ) or url_digest != evidence.get("download_url_sha256"):
            raise RecapFetchQuarantineRecoveryError(
                "fresh CourtListener material conflicts with delivery commitment: "
                f"{document_id}"
            )
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
    return tuple(records), tuple(restrictions), tuple(terminal_unavailable)


def write_recap_fetch_quarantine_manifest(
    path: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    label: str = "quarantine manifest",
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
                f"existing {label} conflicts with recovered lineage"
            )
        return
    _atomic_link_new(path, payload)


def write_recap_fetch_restriction_evidence(
    path: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    """Publish immutable URL-free fresh-detail public restriction evidence."""

    write_recap_fetch_quarantine_manifest(path, records)


def validate_terminal_unavailable_records(
    records: Sequence[Mapping[str, Any]], *, attempt_policy_sha256: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Validate the closed URL-free terminal partition emitted by recovery."""

    if _SHA256.fullmatch(attempt_policy_sha256) is None:
        raise RecapFetchQuarantineRecoveryError(
            "terminal unavailable partition lacks its attempt policy"
        )
    expected_keys = {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "source_provider",
        "attempt_policy_sha256",
        "attempt_document_sha256",
        "purchase_operation_key",
        "ledger_status",
        "material_state",
        "terminal_reason",
        "queue_status",
        "reservation_usd",
        "cap_counted",
        "recovery_provider_request_executed",
        "paid_redispatch_executed",
        "ledger_operation_sha256",
    }
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    operation_keys: set[str] = set()
    operation_hashes: set[str] = set()
    for record in records:
        candidate_id = record.get("candidate_id")
        document_id = record.get("source_document_id")
        operation_key = record.get("purchase_operation_key")
        queue_status = record.get("queue_status")
        try:
            parsed_operation_key = (
                uuid.UUID(operation_key) if isinstance(operation_key, str) else None
            )
        except ValueError:
            parsed_operation_key = None
        if (
            set(record) != expected_keys
            or record.get("schema_version") != TERMINAL_UNAVAILABLE_SCHEMA_VERSION
            or not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(document_id, str)
            or not document_id
            or record.get("source_provider") != COURTLISTENER_RECAP_FETCH_PROVIDER
            or record.get("attempt_policy_sha256") != attempt_policy_sha256
            or not isinstance(record.get("attempt_document_sha256"), str)
            or _SHA256.fullmatch(cast(str, record.get("attempt_document_sha256")))
            is None
            or parsed_operation_key is None
            or str(parsed_operation_key) != operation_key
            or record.get("ledger_status") != "failed"
            or record.get("material_state") != PurchaseMaterialState.NOT_RECOVERED.value
            or type(queue_status) is not int
            or queue_status not in _TERMINAL_QUEUE_STATUSES
            or record.get("terminal_reason") != f"recap_fetch_status_{queue_status}"
            or not isinstance(record.get("reservation_usd"), str)
            or _CANONICAL_USD.fullmatch(cast(str, record.get("reservation_usd")))
            is None
            or record.get("cap_counted") is not True
            or record.get("recovery_provider_request_executed") is not False
            or record.get("paid_redispatch_executed") is not False
            or not isinstance(record.get("ledger_operation_sha256"), str)
            or not cast(str, record.get("ledger_operation_sha256")).startswith(
                "sha256:"
            )
            or _SHA256.fullmatch(cast(str, record.get("ledger_operation_sha256"))[7:])
            is None
        ):
            raise RecapFetchQuarantineRecoveryError(
                "terminal unavailable operation is malformed or ambiguous"
            )
        key = (candidate_id, document_id)
        if key in indexed:
            raise RecapFetchQuarantineRecoveryError(
                f"terminal unavailable partition repeats a document: {document_id}"
            )
        operation_key = cast(str, operation_key)
        operation_hash = cast(str, record["ledger_operation_sha256"])
        if operation_key in operation_keys or operation_hash in operation_hashes:
            raise RecapFetchQuarantineRecoveryError(
                "terminal unavailable partition repeats operation evidence"
            )
        operation_keys.add(operation_key)
        operation_hashes.add(operation_hash)
        indexed[key] = record
    return indexed


def verify_terminal_unavailable_ledger_bindings(
    records: Sequence[Mapping[str, Any]],
    *,
    purchase_operations: Sequence[Mapping[str, Any]],
    attempt_policy_sha256: str,
    expected_cycle_id: str,
    expected_purchase_policy_sha256: str,
) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Replay every terminal row from the authenticated purchase snapshot."""

    indexed = validate_terminal_unavailable_records(
        records, attempt_policy_sha256=attempt_policy_sha256
    )
    operations: dict[tuple[str, str], Mapping[str, Any]] = {}
    for operation in purchase_operations:
        candidate_id = operation.get("candidate_id")
        document_id = operation.get("source_document_id")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(document_id, str)
            or not document_id
        ):
            raise RecapFetchQuarantineRecoveryError(
                "authenticated purchase snapshot contains an invalid operation"
            )
        key = (candidate_id, document_id)
        if key in operations:
            raise RecapFetchQuarantineRecoveryError(
                "authenticated purchase snapshot repeats an operation"
            )
        operations[key] = operation
    for key, record in indexed.items():
        operation = operations.get(key)
        if operation is None:
            raise RecapFetchQuarantineRecoveryError(
                "terminal unavailable operation is absent from purchase state"
            )
        evidence = dict(operation)
        evidence.pop("source_document_id", None)
        selection_document_sha256 = operation.get("attempt_document_sha256")
        if not isinstance(selection_document_sha256, str):
            raise RecapFetchQuarantineRecoveryError(
                "terminal purchase operation lacks attempt document authority"
            )
        expected_reservation = evidence.get("reservation_usd")
        if not isinstance(expected_reservation, str):
            raise RecapFetchQuarantineRecoveryError(
                "terminal purchase operation lacks canonical reservation"
            )
        try:
            _validate_operation_authority(
                evidence,
                candidate_id=key[0],
                document_id=key[1],
                attempt_policy_sha256=attempt_policy_sha256,
                selection_document_sha256=selection_document_sha256,
            )
            expected = _terminal_unavailable_record(
                evidence,
                candidate_id=key[0],
                document_id=key[1],
                attempt_policy_sha256=attempt_policy_sha256,
                selection_document_sha256=selection_document_sha256,
                expected_reservation=expected_reservation,
                expected_cycle_id=expected_cycle_id,
                expected_purchase_policy_sha256=(expected_purchase_policy_sha256),
            )
        except RecapFetchQuarantineRecoveryError as exc:
            raise RecapFetchQuarantineRecoveryError(
                "terminal unavailable operation conflicts with purchase state"
            ) from exc
        if dict(record) != dict(expected):
            raise RecapFetchQuarantineRecoveryError(
                "terminal unavailable operation conflicts with purchase state"
            )
    return indexed


def project_purchased_case_relevance(
    case_relevance: Sequence[Mapping[str, Any]],
    recovered_manifest: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, object], ...]:
    """Filter authenticated target relevance to exactly recovered purchased keys."""

    recovered_keys = {_purchased_relevance_key(record) for record in recovered_manifest}
    if len(recovered_keys) != len(recovered_manifest):
        raise RecapFetchQuarantineRecoveryError(
            "recovered quarantine manifest repeats a document"
        )
    if any(
        record.get("free_or_purchased") != "purchased" for record in recovered_manifest
    ):
        raise RecapFetchQuarantineRecoveryError(
            "recovered quarantine manifest includes a non-purchased row"
        )
    seen_candidates: set[str] = set()
    seen_documents: set[tuple[str, str]] = set()
    projected: list[dict[str, object]] = []
    for raw_case in case_relevance:
        candidate_id = _required_projection_text(raw_case, "candidate_id")
        if candidate_id in seen_candidates:
            raise RecapFetchQuarantineRecoveryError(
                "target case relevance repeats a candidate"
            )
        seen_candidates.add(candidate_id)
        raw_documents = raw_case.get("documents")
        if not isinstance(raw_documents, list):
            raise RecapFetchQuarantineRecoveryError(
                "target case relevance lacks documents"
            )
        selected_documents: list[dict[str, object]] = []
        for raw_document in cast(list[object], raw_documents):
            if not isinstance(raw_document, Mapping):
                raise RecapFetchQuarantineRecoveryError(
                    "target case relevance has invalid document row"
                )
            document = dict(cast(Mapping[str, object], raw_document))
            key = (
                candidate_id,
                _required_projection_text(document, "source_document_id"),
            )
            if key in seen_documents:
                raise RecapFetchQuarantineRecoveryError(
                    "target case relevance repeats a document"
                )
            seen_documents.add(key)
            if key in recovered_keys:
                selected_documents.append(document)
        if selected_documents:
            projected_case = dict(raw_case)
            projected_case["documents"] = selected_documents
            projected.append(projected_case)
    missing = recovered_keys - seen_documents
    if missing:
        raise RecapFetchQuarantineRecoveryError(
            "recovered quarantine document lacks target case relevance: "
            f"{sorted(missing)}"
        )
    projected_keys = {
        (str(case["candidate_id"]), str(document["source_document_id"]))
        for case in projected
        for document in cast(list[dict[str, object]], case["documents"])
    }
    if projected_keys != recovered_keys:
        raise RecapFetchQuarantineRecoveryError(
            "purchased case-relevance projection coverage mismatch"
        )
    return tuple(projected)


def _purchased_relevance_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (
        _required_projection_text(record, "candidate_id"),
        _required_projection_text(record, "source_document_id"),
    )


def _required_projection_text(record: Mapping[str, Any], field_name: str) -> str:
    if field_name not in record:
        raise RecapFetchQuarantineRecoveryError(f"{field_name} is required")
    value = record[field_name]
    if not isinstance(value, str) or not value.strip():
        raise RecapFetchQuarantineRecoveryError(
            f"{field_name} must be a non-empty string"
        )
    return value


def build_recap_fetch_disclosure_review_requests(
    manifest_records: Sequence[Mapping[str, Any]],
    restriction_records: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Derive the exact human-review queue from immutable recovery outputs."""

    manifests = _index_by_document_key(manifest_records, label="quarantine manifest")
    restrictions = _index_by_document_key(
        restriction_records, label="post-recovery restriction evidence"
    )
    if set(manifests) != set(restrictions):
        raise RecapFetchQuarantineRecoveryError(
            "review-request coverage differs from quarantine recovery outputs"
        )
    requests: list[Mapping[str, Any]] = []
    for key in sorted(manifests):
        manifest = manifests[key]
        restriction = restrictions[key]
        sha256 = manifest.get("sha256")
        byte_count = manifest.get("byte_count")
        if (
            manifest.get("schema_version") != SCHEMA_VERSION
            or manifest.get("free_or_purchased") != "purchased"
            or manifest.get("recovery_origin") != UNKNOWN_RECOVERY_ORIGIN
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
            or type(byte_count) is not int
            or byte_count < 1
        ):
            raise RecapFetchQuarantineRecoveryError(
                f"invalid quarantine manifest record: {key[0]}/{key[1]}"
            )
        evidence = restriction.get("restriction_evidence")
        if (
            restriction.get("schema_version") != RESTRICTION_SCHEMA_VERSION
            or restriction.get("restriction_status") != "public"
            or restriction.get("redaction_or_seal_status") != "public"
            or not _is_false_or_none(restriction.get("is_sealed"))
            or not _is_false_or_none(restriction.get("is_private"))
            or not isinstance(evidence, Sequence)
            or isinstance(evidence, (str, bytes))
            or not evidence
            or not all(
                isinstance(item, str) and item
                for item in cast(Sequence[object], evidence)
            )
            or tuple(cast(Sequence[str], evidence))
            != (
                _FRESH_PUBLIC_EVIDENCE
                if restriction.get("is_sealed") is False
                else _FRESH_PUBLIC_UNKNOWN_SEAL_EVIDENCE
            )
        ):
            raise RecapFetchQuarantineRecoveryError(
                f"invalid post-recovery restriction evidence: {key[0]}/{key[1]}"
            )
        requests.append(
            {
                "schema_version": REVIEW_REQUEST_SCHEMA_VERSION,
                "candidate_id": key[0],
                "source_document_id": key[1],
                "sha256": sha256,
                "byte_count": byte_count,
                "free_or_purchased": "purchased",
                "restriction_status": "public",
                "restriction_evidence": list(cast(Sequence[str], evidence)),
                "required_human_decision": "cleared_or_quarantined",
            }
        )
    return tuple(requests)


def write_recap_fetch_disclosure_review_requests(
    path: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    """Publish the immutable, exact-coverage human-review request artifact."""

    write_recap_fetch_quarantine_manifest(path, records)


def _index_by_document_key(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        document_id = record.get("source_document_id")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(document_id, str)
            or not document_id
        ):
            raise RecapFetchQuarantineRecoveryError(f"{label} has an invalid key")
        key = (candidate_id, document_id)
        if key in indexed:
            raise RecapFetchQuarantineRecoveryError(
                f"duplicate {label} identity: {candidate_id}/{document_id}"
            )
        indexed[key] = record
    return indexed


def _validate_operation_authority(
    operation: Mapping[str, Any],
    *,
    candidate_id: str,
    document_id: str,
    attempt_policy_sha256: str,
    selection_document_sha256: str,
) -> None:
    state = operation.get("material_state")
    if (
        operation.get("candidate_id") != candidate_id
        or operation.get("material_authority") != UNKNOWN_RECOVERY_ORIGIN
        or operation.get("attempt_policy_sha256") != attempt_policy_sha256
        or operation.get("attempt_document_sha256") != selection_document_sha256
        or not isinstance(operation.get("operation_key"), str)
        or state
        not in {
            PurchaseMaterialState.NOT_RECOVERED,
            PurchaseMaterialState.AVAILABLE_PENDING_QUARANTINE,
            PurchaseMaterialState.RECOVERED_PENDING_CLEARANCE,
            PurchaseMaterialState.CLEARED_PUBLIC,
        }
    ):
        raise RecapFetchQuarantineRecoveryError(
            f"purchase lacks recoverable unknown-origin material: {document_id}"
        )


def _validate_recoverable_operation(
    operation: Mapping[str, Any],
    *,
    candidate_id: str,
    document_id: str,
    attempt_policy_sha256: str,
    selection_document_sha256: str,
) -> None:
    state = operation.get("material_state")
    if state is PurchaseMaterialState.NOT_RECOVERED:
        if (
            operation.get("status") != "unknown"
            or operation.get("reconciliation") is not None
            or operation.get("material_evidence")
        ):
            raise RecapFetchQuarantineRecoveryError(
                f"purchase lacks recoverable unknown-origin material: {document_id}"
            )
        return
    evidence = _mapping(operation.get("material_evidence"), "material evidence")
    for field in ("provider_detail_sha256", "download_url_sha256"):
        value = evidence.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise RecapFetchQuarantineRecoveryError(
                f"purchase material lacks {field}: {document_id}"
            )
    queue_sha256 = evidence.get("queue_response_sha256")
    recovery = operation.get("public_material_recovery")
    has_queue = isinstance(queue_sha256, str) and len(queue_sha256) == 64
    has_public_recovery = _is_bound_public_recovery(
        recovery,
        operation=operation,
        candidate_id=candidate_id,
        document_id=document_id,
        attempt_policy_sha256=attempt_policy_sha256,
        selection_document_sha256=selection_document_sha256,
    )
    if has_queue == has_public_recovery:
        raise RecapFetchQuarantineRecoveryError(
            f"purchase material lacks one exact delivery authority: {document_id}"
        )


def _terminal_unavailable_record(
    operation: Mapping[str, Any],
    *,
    candidate_id: str,
    document_id: str,
    attempt_policy_sha256: str,
    selection_document_sha256: str,
    expected_reservation: str,
    expected_cycle_id: str,
    expected_purchase_policy_sha256: str,
) -> Mapping[str, Any]:
    """Authenticate one cap-counted terminal queue failure without I/O."""

    operation_key = operation.get("operation_key")
    response_value = operation.get("response")
    error = operation.get("error")
    if isinstance(operation_key, str):
        try:
            parsed_operation_key = uuid.UUID(operation_key)
        except ValueError:
            parsed_operation_key = None
    else:
        parsed_operation_key = None
    queue_status = next(
        (
            status
            for status in _TERMINAL_QUEUE_STATUSES
            if error
            == (
                "CourtListenerRecapFetchError: RECAP Fetch terminal queue status "
                f"{status}"
            )
        ),
        None,
    )
    response = (
        cast(Mapping[str, Any], response_value)
        if isinstance(response_value, Mapping)
        else None
    )
    queue_id = None if response is None else response.get("queue_id")
    reservation_id = None if response is None else response.get("reservation_id")
    response_keys: frozenset[str] = (
        frozenset() if response is None else frozenset(response)
    )
    if (
        operation.get("status") != "failed"
        or operation.get("material_state")
        not in {
            PurchaseMaterialState.NOT_RECOVERED,
            PurchaseMaterialState.NOT_RECOVERED.value,
        }
        or operation.get("actual_usd") is not None
        or operation.get("reconciliation") is not None
        or operation.get("material_evidence") != {}
        or operation.get("public_material_recovery") is not None
        or operation.get("resolved_document_sha256") is not None
        or parsed_operation_key is None
        or str(parsed_operation_key) != operation_key
        or operation.get("reservation_usd") != expected_reservation
        or response is None
        or response_keys
        not in {
            frozenset(
                {
                    "source_provider",
                    "reservation_usd",
                    "queue_id",
                    "reservation_id",
                }
            ),
            frozenset(
                {
                    "source_provider",
                    "reservation_usd",
                    "queue_id",
                    "reservation_id",
                    "broker_receipts",
                }
            ),
        }
        or response.get("source_provider") != COURTLISTENER_RECAP_FETCH_PROVIDER
        or response.get("reservation_usd") != expected_reservation
        or not isinstance(queue_id, str)
        or _CANONICAL_QUEUE_ID.fullmatch(queue_id) is None
        or not isinstance(reservation_id, str)
        or not reservation_id
        or reservation_id.strip() != reservation_id
        or queue_status is None
    ):
        raise RecapFetchQuarantineRecoveryError(
            "failed operation is not a canonical terminal-unavailable purchase: "
            f"{document_id}"
        )
    broker_receipts = response.get("broker_receipts")
    if "broker_receipts" in response and broker_receipts is None:
        raise RecapFetchQuarantineRecoveryError(
            "terminal broker receipt history is malformed or ambiguous"
        )
    _validate_terminal_broker_receipts(
        broker_receipts,
        operation_key=cast(str, operation_key),
        candidate_id=candidate_id,
        document_id=document_id,
        reservation_id=reservation_id,
        queue_id=queue_id,
        reservation_usd=expected_reservation,
        expected_cycle_id=expected_cycle_id,
        expected_purchase_policy_sha256=expected_purchase_policy_sha256,
    )
    return {
        "schema_version": TERMINAL_UNAVAILABLE_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
        "attempt_policy_sha256": attempt_policy_sha256,
        "attempt_document_sha256": selection_document_sha256,
        "purchase_operation_key": operation_key,
        "ledger_status": "failed",
        "material_state": PurchaseMaterialState.NOT_RECOVERED.value,
        "terminal_reason": f"recap_fetch_status_{queue_status}",
        "queue_status": queue_status,
        "reservation_usd": expected_reservation,
        "cap_counted": True,
        "recovery_provider_request_executed": False,
        "paid_redispatch_executed": False,
        "ledger_operation_sha256": _canonical_operation_sha256(operation),
    }


def _validate_terminal_broker_receipts(
    value: object,
    *,
    operation_key: str,
    candidate_id: str,
    document_id: str,
    reservation_id: str,
    queue_id: str,
    reservation_usd: str,
    expected_cycle_id: str,
    expected_purchase_policy_sha256: str,
) -> None:
    """Validate optional immutable broker history retained by a failed row."""

    if value is None:
        return
    if not isinstance(value, list) or not value:
        raise RecapFetchQuarantineRecoveryError(
            "terminal broker receipt history is malformed or ambiguous"
        )
    immutable_identity: tuple[object, ...] | None = None
    previous_updated_at: str | None = None
    receipt_hashes: set[str] = set()
    for raw_item in cast(list[object], value):
        if not isinstance(raw_item, Mapping):
            raise RecapFetchQuarantineRecoveryError(
                "terminal broker receipt history is malformed or ambiguous"
            )
        item = cast(Mapping[str, Any], raw_item)
        raw_receipt = item.get("receipt")
        receipt_hash = item.get("sha256")
        if (
            set(item) != {"sha256", "receipt"}
            or not isinstance(receipt_hash, str)
            or not isinstance(raw_receipt, Mapping)
            or receipt_hash
            != _canonical_mapping_sha256(cast(Mapping[str, Any], raw_receipt))
            or receipt_hash in receipt_hashes
        ):
            raise RecapFetchQuarantineRecoveryError(
                "terminal broker receipt history is malformed or ambiguous"
            )
        receipt_hashes.add(receipt_hash)
        try:
            receipt = validate_broker_receipt(cast(Mapping[str, Any], raw_receipt))
        except BrokerOutcomeUnknown as exc:
            raise RecapFetchQuarantineRecoveryError(
                "terminal broker receipt history is malformed or ambiguous"
            ) from exc
        updated_at = receipt.get("updated_at")
        receipt_queue_id = receipt.get("id")
        if (
            not isinstance(updated_at, str)
            or not updated_at
            or (previous_updated_at is not None and updated_at < previous_updated_at)
            or receipt.get("operation_key") != operation_key
            or receipt.get("case_id") != candidate_id
            or receipt.get("recap_document") != document_id
            or receipt.get("reservation_id") != reservation_id
            or receipt.get("reservation_usd") != reservation_usd
            or receipt.get("cycle_id") != expected_cycle_id
            or receipt.get("purchase_policy_sha256") != expected_purchase_policy_sha256
            or receipt_queue_id not in {None, queue_id}
            or receipt.get("billing_evidence") is not None
            or receipt.get("authoritative_fee_usd") not in {None, "0.00"}
        ):
            raise RecapFetchQuarantineRecoveryError(
                "terminal broker receipt history conflicts with purchase identity"
            )
        previous_updated_at = updated_at
        identity = tuple(
            receipt.get(field)
            for field in (
                "operation_key",
                "reservation_id",
                "cycle_id",
                "purchase_policy_sha256",
                "recap_document",
                "case_id",
                "client_code",
                "reservation_usd",
            )
        )
        if immutable_identity is None:
            immutable_identity = identity
        elif immutable_identity != identity:
            raise RecapFetchQuarantineRecoveryError(
                "terminal broker receipt identity changed"
            )


def _canonical_mapping_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _selection_document_sha256(
    authority: Mapping[str, str], *, document_id: str
) -> str:
    digest = authority.get("selection_document_sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise RecapFetchQuarantineRecoveryError(
            f"attempt authority lacks selection document identity: {document_id}"
        )
    return digest


def _is_bound_public_recovery(
    value: object,
    *,
    operation: Mapping[str, Any],
    candidate_id: str,
    document_id: str,
    attempt_policy_sha256: str,
    selection_document_sha256: str,
) -> bool:
    if not isinstance(value, Mapping):
        return False
    recovery = cast(Mapping[str, object], value)
    evidence = _mapping(operation.get("material_evidence"), "material evidence")
    return (
        recovery
        == {
            "schema_version": UNKNOWN_PUBLIC_MATERIAL_RECOVERY_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "operation_key": operation.get("operation_key"),
            "purchase_policy_sha256": recovery.get("purchase_policy_sha256"),
            "attempt_policy_sha256": attempt_policy_sha256,
            "attempt_document_sha256": selection_document_sha256,
            "provider_detail_sha256": evidence.get("provider_detail_sha256"),
            "download_url_sha256": evidence.get("download_url_sha256"),
            "billing_status": "unknown",
            "reservation_retained": True,
            "no_paid_redispatch": True,
        }
        and isinstance(recovery.get("purchase_policy_sha256"), str)
        and (
            _SHA256.fullmatch(cast(str, recovery.get("purchase_policy_sha256")))
            is not None
        )
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
        return verified_public_recap_download_url(payload, document_id)
    except CourtListenerRecapFetchError as exc:
        raise RecapFetchQuarantineRecoveryError(str(exc)) from exc


def _require_fresh_public_detail(detail: Mapping[str, Any], document_id: str) -> None:
    if (
        "is_sealed" not in detail
        or detail.get("is_available") is not True
        or not _is_false_or_none(detail.get("is_sealed"))
        or not _is_false_or_none(detail.get("is_private"))
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
    is_sealed = detail.get("is_sealed")
    evidence = (
        _FRESH_PUBLIC_EVIDENCE
        if is_sealed is False
        else _FRESH_PUBLIC_UNKNOWN_SEAL_EVIDENCE
    )
    return {
        "schema_version": RESTRICTION_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "source_provider": "courtlistener_recap_fetch_fresh_detail",
        "fresh_recap_detail_sha256": detail_sha256,
        "is_available": True,
        "is_sealed": is_sealed,
        "is_private": detail.get("is_private"),
        "redaction_or_seal_status": "public",
        "restriction_status": "public",
        "restriction_evidence": list(evidence),
    }


def _is_false_or_none(value: object) -> bool:
    return value is False or value is None


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecapFetchQuarantineRecoveryError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _sha256_json(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _canonical_operation_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


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
