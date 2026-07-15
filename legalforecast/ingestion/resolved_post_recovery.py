"""Immutable lineage for public documents recovered from unknown-status origins."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.disclosure_clearance import (
    SCHEMA_VERSION,
    DisclosureClearanceError,
    ReviewAuthority,
    validate_review_receipt,
)
from legalforecast.ingestion.recap_fetch_attempt_policy import (
    BOUNDED_FETCH_ATTEMPT_AUTHORITY,
    RECAP_FETCH_ATTEMPT_POLICY_VERSION,
)
from legalforecast.ingestion.recap_fetch_broker import (
    BrokerOutcomeUnknown,
    validate_broker_receipt,
)

RESOLVED_POST_RECOVERY_SCHEMA_VERSION = (
    "legalforecast.resolved_post_recovery_public_document.v1"
)
UNKNOWN_RECOVERY_ORIGIN = "unknown_status_attempt"
FRESH_PUBLIC_RESTRICTION_SCHEMA_VERSION = (
    "legalforecast.post_recovery_restriction_evidence.v1"
)
FRESH_PUBLIC_RESTRICTION_EVIDENCE = (
    "courtlistener_recap_fetch_fresh_detail_exact_match",
    "courtlistener_recap_fetch_is_available_true",
    "courtlistener_recap_fetch_is_sealed_false",
    "courtlistener_recap_fetch_no_positive_private_marker",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)


class ResolvedPostRecoveryError(ValueError):
    """Raised when unknown-origin bytes lack exact public-clearance lineage."""


@dataclass(frozen=True, slots=True)
class AuthenticatedClearanceLineage:
    """Exact controlled-review commitments from a completed clearance run."""

    clearance_run_card_sha256: str
    clearance_artifact_sha256: str
    reviews_artifact_sha256: str
    review_receipt_sha256: str
    restriction_evidence_artifact_sha256: str
    review_authority_sha256: str
    authority: ReviewAuthority


def validate_authenticated_clearance_lineage(
    *,
    clearance_records: Sequence[Mapping[str, Any]],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
) -> AuthenticatedClearanceLineage:
    """Verify the exact executed clearance inputs, authority, and output bytes."""

    if _json_object_from_bytes(
        clearance_run_card_bytes, "clear-disclosures run card"
    ) != dict(clearance_run_card):
        raise ResolvedPostRecoveryError(
            "clear-disclosures run-card bytes do not match the parsed artifact"
        )
    if _jsonl_records_from_bytes(clearance_artifact_bytes, "disclosure clearance") != [
        dict(record) for record in clearance_records
    ]:
        raise ResolvedPostRecoveryError(
            "disclosure-clearance bytes do not match the parsed records"
        )
    if _json_object_from_bytes(review_receipt_bytes, "review receipt") != dict(
        review_receipt_artifact
    ):
        raise ResolvedPostRecoveryError(
            "review-receipt bytes do not match the parsed artifact"
        )
    if _jsonl_records_from_bytes(
        restriction_artifact_bytes, "restriction evidence"
    ) != [dict(record) for record in restriction_records]:
        raise ResolvedPostRecoveryError(
            "restriction-evidence bytes do not match the parsed records"
        )
    if (
        clearance_run_card.get("schema_version")
        != "legalforecast.acquisition_run_card.v1"
        or clearance_run_card.get("stage") != "clear-disclosures"
        or clearance_run_card.get("status") != "completed"
        or clearance_run_card.get("dry_run") is not False
        or clearance_run_card.get("execute") is not True
        or clearance_run_card.get("paid_activity_requested") is not False
        or clearance_run_card.get("paid_activity_executed") is not False
    ):
        raise ResolvedPostRecoveryError(
            "resolved lineage requires an executed nonpaid clear-disclosures run card"
        )
    source = _mapping(
        clearance_run_card.get("source_commitments"), "clearance source commitments"
    )
    output = _mapping(
        clearance_run_card.get("output_commitments"), "clearance output commitments"
    )
    expected_sources = {
        "reviews": _bytes_sha256(reviews_artifact_bytes),
        "review_receipt": _bytes_sha256(review_receipt_bytes),
        "restriction_evidence": _bytes_sha256(restriction_artifact_bytes),
    }
    for name, expected in expected_sources.items():
        commitment = _mapping(source.get(name), f"{name} commitment")
        if _commitment_sha256(commitment.get("sha256"), name) != expected:
            raise ResolvedPostRecoveryError(
                f"clear-disclosures {name} commitment mismatch"
            )
    clearance_sha256 = _bytes_sha256(clearance_artifact_bytes)
    clearance_commitment = _mapping(
        output.get("disclosure_clearance"), "disclosure clearance commitment"
    )
    if (
        _commitment_sha256(clearance_commitment.get("sha256"), "disclosure clearance")
        != clearance_sha256
    ):
        raise ResolvedPostRecoveryError("clear-disclosures output commitment mismatch")
    try:
        authority = validate_review_receipt(
            reviews_artifact_bytes, review_receipt_artifact
        )
    except DisclosureClearanceError as exc:
        raise ResolvedPostRecoveryError(str(exc)) from exc
    expected_authority: dict[str, object] = {
        "reviewer_id": authority.reviewer_id,
        "controlled_store_uri": authority.controlled_store_uri,
        "authentication_method": authority.authentication_method,
        "authenticated_at": authority.authenticated_at,
        "review_artifact_sha256": "sha256:" + authority.review_artifact_sha256,
    }
    if clearance_run_card.get("review_authority") != expected_authority:
        raise ResolvedPostRecoveryError(
            "clear-disclosures review authority does not match its receipt"
        )

    clearance_index = _index(clearance_records, "clearance")
    restrictions = _group_index(restriction_records, "restriction evidence")
    if set(clearance_index) != set(restrictions):
        raise ResolvedPostRecoveryError(
            "restriction evidence does not exactly cover disclosure clearance"
        )
    for key, clearance in clearance_index.items():
        if (
            clearance.get("schema_version") != SCHEMA_VERSION
            or clearance.get("reviewer_id") != authority.reviewer_id
            or clearance.get("controlled_store_provenance")
            != authority.controlled_store_uri
            or not clearance.get("reviewed_at")
        ):
            raise ResolvedPostRecoveryError(
                f"clearance row does not bind authenticated review authority: {key}"
            )

    return AuthenticatedClearanceLineage(
        clearance_run_card_sha256=_bytes_sha256(clearance_run_card_bytes),
        clearance_artifact_sha256=clearance_sha256,
        reviews_artifact_sha256=expected_sources["reviews"],
        review_receipt_sha256=expected_sources["review_receipt"],
        restriction_evidence_artifact_sha256=expected_sources["restriction_evidence"],
        review_authority_sha256=_sha256(expected_authority),
        authority=authority,
    )


def build_resolved_post_recovery_documents(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    purchase_operation_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    attempt_policy_artifact: Mapping[str, object],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
) -> tuple[dict[str, object], ...]:
    """Build exact resolved records for every unknown-origin selected document."""

    clearance_lineage = validate_authenticated_clearance_lineage(
        clearance_records=clearance_records,
        clearance_artifact_bytes=clearance_artifact_bytes,
        clearance_run_card=clearance_run_card,
        clearance_run_card_bytes=clearance_run_card_bytes,
        reviews_artifact_bytes=reviews_artifact_bytes,
        review_receipt_artifact=review_receipt_artifact,
        review_receipt_bytes=review_receipt_bytes,
        restriction_records=restriction_records,
        restriction_artifact_bytes=restriction_artifact_bytes,
    )
    policy_sha256, attempt_documents = _attempt_documents(attempt_policy_artifact)
    unknown_selection = _unknown_selection(selection_records)
    if set(attempt_documents) != set(unknown_selection):
        raise ResolvedPostRecoveryError(
            "attempt policy does not exactly cover unknown selected documents"
        )
    operations = _index(purchase_operation_records, "purchase operation")
    downloads = _index(download_records, "download")
    clearances = _index(clearance_records, "clearance")
    restrictions = _group_index(restriction_records, "restriction evidence")
    required = set(unknown_selection)
    for label, index in (
        ("purchase operation", operations),
        ("download", downloads),
        ("clearance", clearances),
    ):
        missing = required - set(index)
        if missing:
            raise ResolvedPostRecoveryError(
                f"{label} lacks unknown-origin coverage: {sorted(missing)}"
            )

    output: list[dict[str, object]] = []
    for key in sorted(required):
        candidate_id, document_id = key
        selection_document = unknown_selection[key]
        attempt = attempt_documents[key]
        operation = operations[key]
        download = downloads[key]
        clearance = clearances[key]
        restriction_rows = restrictions[key]
        selection_sha256 = _sha256(selection_document)
        if attempt["selection_document_sha256"] != selection_sha256:
            raise ResolvedPostRecoveryError(
                f"attempt policy selection commitment changed: {key}"
            )
        _validate_operation(
            operation,
            key=key,
            attempt_policy_sha256=policy_sha256,
            selection_document_sha256=selection_sha256,
        )
        _validate_download(
            download,
            key=key,
            operation=operation,
            attempt_policy_sha256=policy_sha256,
        )
        _validate_clearance(clearance, key=key, download=download)
        fresh_public = _fresh_public_restriction_record(
            restriction_rows,
            key=key,
            operation=operation,
        )
        receipt = _terminal_delivery_receipt(operation, key=key)
        material = _mapping(operation.get("material_evidence"), "material evidence")
        record: dict[str, object] = {
            "schema_version": RESOLVED_POST_RECOVERY_SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "recovery_origin": UNKNOWN_RECOVERY_ORIGIN,
            "purchase_policy_sha256": _required_sha(
                receipt.get("purchase_policy_sha256"), "purchase policy"
            ),
            "attempt_policy_sha256": policy_sha256,
            "selection_document_sha256": selection_sha256,
            "purchase_operation_sha256": _sha256(operation),
            "operation_key": _uuid4(operation.get("operation_key")),
            "broker_receipt_sha256": _sha256(receipt),
            "broker_receipt_state": _required_text(receipt.get("state"), "state"),
            "queue_response_sha256": _required_sha(
                material.get("queue_response_sha256"), "queue response"
            ),
            "fresh_recap_detail_sha256": _required_sha(
                material.get("provider_detail_sha256"), "fresh RECAP detail"
            ),
            "download_url_sha256": _required_sha(
                material.get("download_url_sha256"), "download URL"
            ),
            "download_record_sha256": _sha256(download),
            "content_sha256": _required_sha(download.get("sha256"), "content"),
            "byte_count": _positive_int(download.get("byte_count"), "byte_count"),
            "clearance_record_sha256": _sha256(clearance),
            "clearance_run_card_sha256": (clearance_lineage.clearance_run_card_sha256),
            "clearance_artifact_sha256": (clearance_lineage.clearance_artifact_sha256),
            "reviews_artifact_sha256": clearance_lineage.reviews_artifact_sha256,
            "review_receipt_sha256": clearance_lineage.review_receipt_sha256,
            "review_authority_sha256": clearance_lineage.review_authority_sha256,
            "restriction_evidence_artifact_sha256": (
                clearance_lineage.restriction_evidence_artifact_sha256
            ),
            "restriction_evidence_rows_sha256": _sha256(restriction_rows),
            "fresh_detail_public_evidence_sha256": _sha256(fresh_public),
            "restriction_status": "public",
            "parser_eligible": True,
            "packet_eligible": True,
        }
        record["record_sha256"] = _sha256(record)
        output.append(record)
    return tuple(output)


def require_resolved_post_recovery_documents(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
    clearance_artifact_bytes: bytes,
    clearance_run_card: Mapping[str, Any],
    clearance_run_card_bytes: bytes,
    reviews_artifact_bytes: bytes,
    review_receipt_artifact: Mapping[str, object],
    review_receipt_bytes: bytes,
    restriction_records: Sequence[Mapping[str, Any]],
    restriction_artifact_bytes: bytes,
) -> None:
    """Require exact resolved coverage whenever selection originated unknown."""

    lineage = validate_authenticated_clearance_lineage(
        clearance_records=clearance_records,
        clearance_artifact_bytes=clearance_artifact_bytes,
        clearance_run_card=clearance_run_card,
        clearance_run_card_bytes=clearance_run_card_bytes,
        reviews_artifact_bytes=reviews_artifact_bytes,
        review_receipt_artifact=review_receipt_artifact,
        review_receipt_bytes=review_receipt_bytes,
        restriction_records=restriction_records,
        restriction_artifact_bytes=restriction_artifact_bytes,
    )
    required = set(_unknown_selection(selection_records))
    download_unknown = {
        key
        for key, record in _index(download_records, "download").items()
        if record.get("recovery_origin") == UNKNOWN_RECOVERY_ORIGIN
    }
    required |= download_unknown
    resolved = _index(resolved_records, "resolved post-recovery document")
    if set(resolved) != required:
        raise ResolvedPostRecoveryError(
            "resolved post-recovery coverage mismatch; "
            f"missing={sorted(required - set(resolved))}; "
            f"extra={sorted(set(resolved) - required)}"
        )
    downloads = _index(download_records, "download")
    clearances = _index(clearance_records, "clearance")
    restrictions = _group_index(restriction_records, "restriction evidence")
    for key, record in resolved.items():
        _validate_resolved_record(record, key=key)
        download = downloads.get(key)
        clearance = clearances.get(key)
        if download is None or clearance is None:
            raise ResolvedPostRecoveryError(
                f"resolved document lacks download or clearance: {key}"
            )
        if (
            record.get("download_record_sha256") != _sha256(download)
            or record.get("clearance_record_sha256") != _sha256(clearance)
            or record.get("content_sha256") != download.get("sha256")
            or record.get("byte_count") != download.get("byte_count")
        ):
            raise ResolvedPostRecoveryError(f"resolved document lineage changed: {key}")
        _validate_clearance(clearance, key=key, download=download)
        restriction_rows = restrictions.get(key)
        if restriction_rows is None:
            raise ResolvedPostRecoveryError(
                f"resolved document lacks restriction evidence: {key}"
            )
        expected_external = {
            "clearance_run_card_sha256": lineage.clearance_run_card_sha256,
            "clearance_artifact_sha256": lineage.clearance_artifact_sha256,
            "reviews_artifact_sha256": lineage.reviews_artifact_sha256,
            "review_receipt_sha256": lineage.review_receipt_sha256,
            "review_authority_sha256": lineage.review_authority_sha256,
            "restriction_evidence_artifact_sha256": (
                lineage.restriction_evidence_artifact_sha256
            ),
            "restriction_evidence_rows_sha256": _sha256(restriction_rows),
        }
        if any(record.get(name) != value for name, value in expected_external.items()):
            raise ResolvedPostRecoveryError(
                f"resolved document external lineage changed: {key}"
            )
        fresh_public = _fresh_public_restriction_record_from_resolved(
            restriction_rows,
            key=key,
            resolved_record=record,
        )
        if record.get("fresh_detail_public_evidence_sha256") != _sha256(fresh_public):
            raise ResolvedPostRecoveryError(
                f"resolved fresh-detail public proof changed: {key}"
            )


def require_resolved_post_recovery_parse_requests(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    request_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
) -> None:
    """Bind parser requests to exact resolved records for unknown origins."""

    requests = _index(request_records, "parse request")
    required = set(_unknown_selection(selection_records))
    required.update(
        key
        for key, request in requests.items()
        if request.get("recovery_origin") == UNKNOWN_RECOVERY_ORIGIN
    )
    resolved = _index(resolved_records, "resolved post-recovery document")
    if set(resolved) != required:
        raise ResolvedPostRecoveryError(
            "resolved post-recovery parse coverage mismatch"
        )
    for key in required:
        record = resolved[key]
        request = requests.get(key)
        if request is None:
            raise ResolvedPostRecoveryError(
                f"resolved unknown document lacks parse request: {key}"
            )
        _validate_resolved_record(record, key=key)
        if (
            request.get("expected_sha256") != record.get("content_sha256")
            or request.get("expected_byte_count") != record.get("byte_count")
            or request.get("resolved_post_recovery_sha256")
            != record.get("record_sha256")
        ):
            raise ResolvedPostRecoveryError(
                f"parse request does not bind resolved unknown material: {key}"
            )


def require_resolved_post_recovery_operation_bindings(
    *,
    purchase_operation_records: Sequence[Mapping[str, Any]],
    resolved_records: Sequence[Mapping[str, Any]],
) -> None:
    """Verify pre-clear, post-clear, and partially-cleared crash replays exactly."""

    operations = _index(purchase_operation_records, "purchase operation")
    resolved = _index(resolved_records, "resolved post-recovery document")
    if set(resolved) - set(operations):
        raise ResolvedPostRecoveryError(
            "canonical purchase journal lacks resolved operation coverage"
        )
    for key, record in resolved.items():
        operation = operations[key]
        _validate_resolved_record(record, key=key)
        state = operation.get("material_state")
        if state not in {"recovered_pending_clearance", "cleared_public"}:
            raise ResolvedPostRecoveryError(
                f"canonical purchase material state is not resolvable: {key}"
            )
        terminal_receipt = _terminal_delivery_receipt(operation, key=key)
        if _sha256(terminal_receipt) != record.get("broker_receipt_sha256"):
            raise ResolvedPostRecoveryError(
                f"resolved broker receipt is not the current terminal receipt: {key}"
            )
        material = _mapping(operation.get("material_evidence"), "material evidence")
        expected = {
            "candidate_id": operation.get("candidate_id"),
            "source_document_id": operation.get("source_document_id"),
            "operation_key": operation.get("operation_key"),
            "attempt_policy_sha256": operation.get("attempt_policy_sha256"),
            "selection_document_sha256": operation.get("attempt_document_sha256"),
            "queue_response_sha256": material.get("queue_response_sha256"),
            "fresh_recap_detail_sha256": material.get("provider_detail_sha256"),
            "download_url_sha256": material.get("download_url_sha256"),
            "content_sha256": material.get("content_sha256"),
            "byte_count": material.get("byte_count"),
        }
        if any(record.get(name) != value for name, value in expected.items()):
            raise ResolvedPostRecoveryError(
                f"resolved record differs from canonical purchase journal: {key}"
            )
        preclear = dict(operation)
        preclear["material_state"] = "recovered_pending_clearance"
        preclear_material = dict(material)
        preclear_material.pop("clearance_record_sha256", None)
        preclear["material_evidence"] = preclear_material
        preclear["resolved_document_sha256"] = None
        if record.get("purchase_operation_sha256") != _sha256(preclear):
            raise ResolvedPostRecoveryError(
                f"resolved purchase operation commitment changed: {key}"
            )
        if state == "cleared_public" and (
            operation.get("resolved_document_sha256") != record.get("record_sha256")
            or material.get("clearance_record_sha256")
            != record.get("clearance_record_sha256")
        ):
            raise ResolvedPostRecoveryError(
                f"canonical purchase journal clearance binding changed: {key}"
            )


def write_resolved_post_recovery_documents(
    path: str | Path, records: Sequence[Mapping[str, object]]
) -> Path:
    """Atomically publish canonical JSONL and refuse changed replays."""

    for record in records:
        _validate_resolved_record(record, key=_key(record))
    payload = b"".join(
        (json.dumps(dict(record), sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for record in records
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ResolvedPostRecoveryError("resolved output is a symlink")
    if target.exists():
        metadata = target.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ResolvedPostRecoveryError(
                "resolved output must be a singly linked regular file"
            )
        if target.read_bytes() != payload:
            raise ResolvedPostRecoveryError(
                "refusing to overwrite different resolved post-recovery bytes"
            )
        return target
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise ResolvedPostRecoveryError(
                "resolved output was concurrently created with different bytes"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _unknown_selection(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    output: dict[tuple[str, str], Mapping[str, Any]] = {}
    for selection in records:
        candidate_id = _required_text(selection.get("candidate_id"), "candidate_id")
        documents = selection.get("documents")
        if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
            raise ResolvedPostRecoveryError("selection documents must be a list")
        for item in cast(Sequence[object], documents):
            if not isinstance(item, Mapping):
                raise ResolvedPostRecoveryError("selected document must be an object")
            document = cast(Mapping[str, Any], item)
            key = (
                candidate_id,
                _required_text(
                    document.get("source_document_id"), "source_document_id"
                ),
            )
            paid_recovery = document.get("requires_paid_recovery") is True
            unknown = paid_recovery and (
                document.get("redaction_or_seal_status") != "public"
                or document.get("is_sealed") is not False
                or document.get("is_private") is not False
            )
            if unknown:
                if key in output:
                    raise ResolvedPostRecoveryError(
                        f"duplicate unknown selected document: {key}"
                    )
                output[key] = document
    return output


def _attempt_documents(
    artifact: Mapping[str, object],
) -> tuple[str, dict[tuple[str, str], Mapping[str, str]]]:
    if artifact.get("schema_version") != RECAP_FETCH_ATTEMPT_POLICY_VERSION:
        raise ResolvedPostRecoveryError("attempt policy schema is invalid")
    policy = _mapping(artifact.get("policy"), "attempt policy")
    policy_sha256 = _required_sha(artifact.get("policy_sha256"), "attempt policy")
    if _sha256(policy) != policy_sha256:
        raise ResolvedPostRecoveryError("attempt policy hash is invalid")
    if policy.get("authority") != BOUNDED_FETCH_ATTEMPT_AUTHORITY:
        raise ResolvedPostRecoveryError("attempt policy authority is invalid")
    raw_documents = policy.get("allowed_documents")
    if not isinstance(raw_documents, list):
        raise ResolvedPostRecoveryError("attempt policy documents must be a list")
    output: dict[tuple[str, str], Mapping[str, str]] = {}
    for item in cast(list[object], raw_documents):
        if not isinstance(item, Mapping):
            raise ResolvedPostRecoveryError("attempt document must be an object")
        row = cast(Mapping[str, Any], item)
        if (
            set(row)
            != {
                "case_id",
                "recap_document",
                "evidence_class",
                "selection_document_sha256",
            }
            or row.get("evidence_class") != "unknown_status_quarantine"
        ):
            raise ResolvedPostRecoveryError("attempt document fields are invalid")
        key = (
            _required_text(row.get("case_id"), "case_id"),
            _required_text(row.get("recap_document"), "recap_document"),
        )
        if key in output:
            raise ResolvedPostRecoveryError(f"duplicate attempt document: {key}")
        output[key] = {
            "selection_document_sha256": _required_sha(
                row.get("selection_document_sha256"), "selection document"
            )
        }
    return policy_sha256, output


def _validate_operation(
    operation: Mapping[str, Any],
    *,
    key: tuple[str, str],
    attempt_policy_sha256: str,
    selection_document_sha256: str,
) -> None:
    if (
        operation.get("material_authority") != UNKNOWN_RECOVERY_ORIGIN
        or operation.get("attempt_policy_sha256") != attempt_policy_sha256
        or operation.get("attempt_document_sha256") != selection_document_sha256
        or operation.get("material_state") != "recovered_pending_clearance"
        or operation.get("candidate_id") != key[0]
        or operation.get("source_document_id") != key[1]
    ):
        raise ResolvedPostRecoveryError(
            f"purchase operation lacks recovered quarantine lineage: {key}"
        )
    _uuid4(operation.get("operation_key"))
    material = _mapping(operation.get("material_evidence"), "material evidence")
    for field in (
        "provider_detail_sha256",
        "queue_response_sha256",
        "download_url_sha256",
        "content_sha256",
    ):
        _required_sha(material.get(field), field)
    _positive_int(material.get("byte_count"), "byte_count")


def _terminal_delivery_receipt(
    operation: Mapping[str, Any], *, key: tuple[str, str]
) -> Mapping[str, Any]:
    response = _mapping(operation.get("response"), "purchase response")
    history = response.get("broker_receipts")
    if not isinstance(history, list):
        raise ResolvedPostRecoveryError(f"purchase lacks broker receipt: {key}")
    receipts: list[Mapping[str, Any]] = []
    immutable_identity: tuple[object, ...] | None = None
    prior_updated_at: str | None = None
    for item_raw in cast(list[object], history):
        if not isinstance(item_raw, Mapping):
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt history is invalid: {key}"
            )
        item = cast(Mapping[str, Any], item_raw)
        if set(item) != {"sha256", "receipt"}:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt history is invalid: {key}"
            )
        raw_receipt: object = item.get("receipt")
        if not isinstance(raw_receipt, Mapping) or item.get("sha256") != _sha256(
            cast(Mapping[str, object], raw_receipt)
        ):
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt hash is invalid: {key}"
            )
        try:
            receipt = validate_broker_receipt(cast(Mapping[str, Any], raw_receipt))
        except BrokerOutcomeUnknown as exc:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt is invalid: {key}"
            ) from exc
        updated_at = _required_text(receipt.get("updated_at"), "receipt updated_at")
        if prior_updated_at is not None and updated_at < prior_updated_at:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt history is not chronological: {key}"
            )
        prior_updated_at = updated_at
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
        elif identity != immutable_identity:
            raise ResolvedPostRecoveryError(
                f"purchase broker receipt identity changed: {key}"
            )
        receipts.append(receipt)
    if not receipts:
        raise ResolvedPostRecoveryError(
            f"purchase lacks matching delivery receipt: {key}"
        )
    terminal = receipts[-1]
    if not (
        terminal.get("state") in {"delivered_but_unreconciled", "confirmed"}
        and terminal.get("operation_key") == operation.get("operation_key")
        and terminal.get("case_id") == key[0]
        and terminal.get("recap_document") == key[1]
    ):
        raise ResolvedPostRecoveryError(
            f"purchase broker receipt terminal state is not delivery: {key}"
        )
    return terminal


def _validate_download(
    download: Mapping[str, Any],
    *,
    key: tuple[str, str],
    operation: Mapping[str, Any],
    attempt_policy_sha256: str,
) -> None:
    material = _mapping(operation.get("material_evidence"), "material evidence")
    if (
        download.get("recovery_origin") != UNKNOWN_RECOVERY_ORIGIN
        or download.get("attempt_policy_sha256") != attempt_policy_sha256
        or download.get("purchase_operation_key") != operation.get("operation_key")
        or download.get("sha256") != material.get("content_sha256")
        or download.get("byte_count") != material.get("byte_count")
    ):
        raise ResolvedPostRecoveryError(
            f"download does not bind quarantined purchase material: {key}"
        )


def _validate_clearance(
    clearance: Mapping[str, Any],
    *,
    key: tuple[str, str],
    download: Mapping[str, Any],
) -> None:
    if (
        clearance.get("schema_version") != SCHEMA_VERSION
        or clearance.get("status") != "cleared"
        or clearance.get("restriction_status") != "public"
        or clearance.get("sha256") != download.get("sha256")
        or clearance.get("byte_count") != download.get("byte_count")
        or not clearance.get("reviewer_id")
        or not clearance.get("controlled_store_provenance")
        or not clearance.get("reviewed_at")
    ):
        raise ResolvedPostRecoveryError(
            f"download lacks authenticated public disclosure clearance: {key}"
        )


def _fresh_public_restriction_record(
    records: Sequence[Mapping[str, Any]],
    *,
    key: tuple[str, str],
    operation: Mapping[str, Any],
) -> Mapping[str, Any]:
    material = _mapping(operation.get("material_evidence"), "material evidence")
    matches = [
        record
        for record in records
        if record.get("schema_version") == FRESH_PUBLIC_RESTRICTION_SCHEMA_VERSION
        and record.get("candidate_id") == key[0]
        and record.get("source_document_id") == key[1]
        and record.get("source_provider") == "courtlistener_recap_fetch_fresh_detail"
        and record.get("fresh_recap_detail_sha256")
        == material.get("provider_detail_sha256")
        and record.get("is_available") is True
        and record.get("is_sealed") is False
        and record.get("is_private") in {False, None}
        and record.get("redaction_or_seal_status") == "public"
        and record.get("restriction_status") == "public"
        and record.get("restriction_evidence")
        == list(FRESH_PUBLIC_RESTRICTION_EVIDENCE)
    ]
    if len(matches) != 1:
        raise ResolvedPostRecoveryError(
            f"unknown-origin document lacks exact fresh-detail public proof: {key}"
        )
    return matches[0]


def _fresh_public_restriction_record_from_resolved(
    records: Sequence[Mapping[str, Any]],
    *,
    key: tuple[str, str],
    resolved_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    matches = [
        record
        for record in records
        if record.get("schema_version") == FRESH_PUBLIC_RESTRICTION_SCHEMA_VERSION
        and record.get("candidate_id") == key[0]
        and record.get("source_document_id") == key[1]
        and record.get("source_provider") == "courtlistener_recap_fetch_fresh_detail"
        and record.get("fresh_recap_detail_sha256")
        == resolved_record.get("fresh_recap_detail_sha256")
        and record.get("is_available") is True
        and record.get("is_sealed") is False
        and record.get("is_private") in {False, None}
        and record.get("redaction_or_seal_status") == "public"
        and record.get("restriction_status") == "public"
        and record.get("restriction_evidence")
        == list(FRESH_PUBLIC_RESTRICTION_EVIDENCE)
    ]
    if len(matches) != 1:
        raise ResolvedPostRecoveryError(
            f"resolved document lacks exact fresh-detail public proof: {key}"
        )
    return matches[0]


def _validate_resolved_record(
    record: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    if (
        record.get("schema_version") != RESOLVED_POST_RECOVERY_SCHEMA_VERSION
        or record.get("candidate_id") != key[0]
        or record.get("source_document_id") != key[1]
        or record.get("recovery_origin") != UNKNOWN_RECOVERY_ORIGIN
        or record.get("restriction_status") != "public"
        or record.get("parser_eligible") is not True
        or record.get("packet_eligible") is not True
    ):
        raise ResolvedPostRecoveryError(f"resolved document is invalid: {key}")
    for field in (
        "purchase_policy_sha256",
        "attempt_policy_sha256",
        "selection_document_sha256",
        "purchase_operation_sha256",
        "broker_receipt_sha256",
        "queue_response_sha256",
        "fresh_recap_detail_sha256",
        "download_url_sha256",
        "download_record_sha256",
        "content_sha256",
        "clearance_record_sha256",
        "clearance_run_card_sha256",
        "clearance_artifact_sha256",
        "reviews_artifact_sha256",
        "review_receipt_sha256",
        "review_authority_sha256",
        "restriction_evidence_artifact_sha256",
        "restriction_evidence_rows_sha256",
        "fresh_detail_public_evidence_sha256",
    ):
        _required_sha(record.get(field), field)
    _uuid4(record.get("operation_key"))
    _positive_int(record.get("byte_count"), "byte_count")
    committed = _required_sha(record.get("record_sha256"), "record")
    unhashed = {
        name: value for name, value in record.items() if name != "record_sha256"
    }
    if _sha256(unhashed) != committed:
        raise ResolvedPostRecoveryError(f"resolved document hash changed: {key}")


def _index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    output: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = _key(record)
        if key in output:
            raise ResolvedPostRecoveryError(f"duplicate {label}: {key}")
        output[key] = record
    return output


def _group_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], tuple[Mapping[str, Any], ...]]:
    output: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        output.setdefault(_key(record), []).append(record)
    if not output and records:
        raise ResolvedPostRecoveryError(f"{label} is invalid")
    return {key: tuple(sorted(rows, key=_sha256)) for key, rows in output.items()}


def _key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _required_text(record.get("candidate_id"), "candidate_id"),
        _required_text(record.get("source_document_id"), "source_document_id"),
    )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResolvedPostRecoveryError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ResolvedPostRecoveryError(f"{label} must be a canonical string")
    return value


def _required_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ResolvedPostRecoveryError(f"{label} must be lowercase SHA-256")
    return value


def _commitment_sha256(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ResolvedPostRecoveryError(f"{label} commitment must be SHA-256")
    return _required_sha(value.removeprefix("sha256:"), f"{label} commitment")


def _uuid4(value: object) -> str:
    if not isinstance(value, str) or _UUID4.fullmatch(value) is None:
        raise ResolvedPostRecoveryError("operation key must be canonical UUIDv4")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResolvedPostRecoveryError(f"{label} must be a positive integer")
    return value


def _sha256(value: object) -> str:
    normalized: object = value
    if isinstance(value, Mapping):
        normalized = dict(cast(Mapping[str, object], value))
    elif isinstance(value, tuple):
        normalized = list(cast(tuple[object, ...], value))
    return hashlib.sha256(
        json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_object_from_bytes(value: bytes, label: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResolvedPostRecoveryError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ResolvedPostRecoveryError(f"{label} must be a JSON object")
    return cast(dict[str, object], parsed)


def _jsonl_records_from_bytes(value: bytes, label: str) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    try:
        text = value.decode("utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            parsed: object = json.loads(line)
            if not isinstance(parsed, dict):
                raise ResolvedPostRecoveryError(f"{label} rows must be JSON objects")
            output.append(cast(dict[str, object], parsed))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResolvedPostRecoveryError(f"{label} is not valid JSONL") from exc
    return output
