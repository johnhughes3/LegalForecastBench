"""Execute the single authenticated public support-memorandum recovery.

This is deliberately not a general CourtListener downloader.  It may obtain
only the ECF 14 PDF which the authenticated raw-docket bridge identifies for
candidate 73327542.  The resulting source-augmentation package leaves the
target-cohort selection untouched: it commits the original selected-document
keys plus one exact additional key, so a later materialization can consume a
second free ``DocumentSource`` without silently changing the cohort.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.disclosure_clearance import (
    ClearanceRecord,
    DisclosurePdfScan,
    scan_disclosure_document,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentDownloadRecord,
    FreeDocumentDownloadRequest,
    FreeDocumentSource,
    download_free_docket_documents,
)
from legalforecast.ingestion.free_support_memorandum_recovery import (
    FreeSupportMemorandumRecoveryError,
    FreeSupportMemorandumRecoveryPlan,
    verify_free_support_memorandum_recovery_plan,
)
from legalforecast.ingestion.provenance import DocumentRole

JsonRecord = dict[str, Any]

SOURCE_AUGMENTATION_SCHEMA = (
    "legalforecast.free_support_memorandum_source_augmentation.v1"
)
_CANDIDATE_ID = "73327542"
_SOURCE_DOCUMENT_ID = "73327542-entry-14-motion-to-dismiss-memorandum"
_TARGET_ENTRY_NUMBER = 13
_SUPPORT_ENTRY_NUMBER = 14
_PUBLIC_EVIDENCE = "courtlistener_public_download_record_checked"


class FreeSupportMemorandumExecutorError(ValueError):
    """Raised when the single-document augmentation cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class FreeSupportMemorandumSourceAugmentation:
    """Verified execution result suitable for a second free source partition."""

    plan: FreeSupportMemorandumRecoveryPlan
    request: FreeDocumentDownloadRequest
    download: FreeDocumentDownloadRecord
    clearance: ClearanceRecord
    projection: JsonRecord

    @property
    def request_bytes(self) -> bytes:
        return _canonical_bytes(self.request.to_record())

    @property
    def download_bytes(self) -> bytes:
        return _canonical_bytes(self.download.to_record())

    @property
    def clearance_bytes(self) -> bytes:
        return _canonical_bytes(self.clearance.to_record())

    @property
    def projection_bytes(self) -> bytes:
        return _canonical_bytes(self.projection)


def execute_free_support_memorandum_source_augmentation(
    *,
    persisted_plan_bytes: bytes,
    bridge_descriptor_path: Path,
    corrected_selection_bytes: bytes,
    output_root: Path,
    source: FreeDocumentSource,
) -> FreeSupportMemorandumSourceAugmentation:
    """Download and clear the sole plan-derived public PDF.

    ``source`` is dependency injection for tests; the production CLI supplies
    the standard HTTPS source with a final-URL equality check.  Neither a URL,
    candidate, document identifier nor any paid/provider authority is accepted
    from the caller.
    """

    plan = _verified_plan(
        persisted_plan_bytes=persisted_plan_bytes,
        bridge_descriptor_path=bridge_descriptor_path,
    )
    base_keys, candidate_row_sha256 = _corrected_selection_state(
        corrected_selection_bytes
    )
    addition = (_CANDIDATE_ID, _SOURCE_DOCUMENT_ID)
    if addition in base_keys:
        raise FreeSupportMemorandumExecutorError(
            "corrected selection already includes the support memorandum"
        )
    request = _request_from_plan(plan)
    try:
        downloaded = download_free_docket_documents(
            (request,),
            output_root=output_root / "documents",
            source=source,
            allow_existing=False,
        )
    except (FreeDocumentDownloadError, OSError, ValueError) as exc:
        raise FreeSupportMemorandumExecutorError(
            "support memorandum public download did not complete safely"
        ) from exc
    if len(downloaded) != 1:
        raise FreeSupportMemorandumExecutorError(
            "support memorandum download did not emit exactly one document"
        )
    download = downloaded[0]
    if (
        download.candidate_id,
        download.source_document_id,
        download.source_url,
        download.docket_entry_number,
        download.document_role,
        download.free_or_purchased,
    ) != (
        _CANDIDATE_ID,
        _SOURCE_DOCUMENT_ID,
        request.source_url,
        _SUPPORT_ENTRY_NUMBER,
        DocumentRole.MTD_MEMORANDUM,
        "free",
    ):
        raise FreeSupportMemorandumExecutorError(
            "support memorandum download identity differs from the plan"
        )
    document_path = output_root / "documents" / download.local_path
    try:
        document_bytes = document_path.read_bytes()
    except OSError as exc:
        raise FreeSupportMemorandumExecutorError(
            "support memorandum download output is unavailable"
        ) from exc
    if (
        len(document_bytes) != download.byte_count
        or hashlib.sha256(document_bytes).hexdigest() != download.sha256
    ):
        raise FreeSupportMemorandumExecutorError(
            "support memorandum downloaded bytes do not match its record"
        )
    scan = scan_disclosure_document(document_bytes)
    if scan.automated_markers or scan.coverage_status != "complete":
        raise FreeSupportMemorandumExecutorError(
            "support memorandum requires normal disclosure review"
        )
    clearance = _clearance_record(
        plan=plan,
        corrected_selection_bytes=corrected_selection_bytes,
        request=request,
        download=download,
        scan=scan,
    )
    projection = _projection(
        plan=plan,
        corrected_selection_bytes=corrected_selection_bytes,
        base_keys=base_keys,
        candidate_row_sha256=candidate_row_sha256,
        download=download,
        clearance=clearance,
    )
    return FreeSupportMemorandumSourceAugmentation(
        plan=plan,
        request=request,
        download=download,
        clearance=clearance,
        projection=projection,
    )


def verify_free_support_memorandum_source_augmentation(
    *,
    persisted_plan_bytes: bytes,
    bridge_descriptor_path: Path,
    corrected_selection_bytes: bytes,
    output_root: Path,
) -> FreeSupportMemorandumSourceAugmentation:
    """Reauthenticate an immutable completed source-augmentation package."""

    plan = _verified_plan(
        persisted_plan_bytes=persisted_plan_bytes,
        bridge_descriptor_path=bridge_descriptor_path,
    )
    expected_request = _request_from_plan(plan)
    request = _read_object(output_root / "free-document-request.json")
    download = _read_object(output_root / "free-document-download.json")
    clearance = _read_object(output_root / "disclosure-clearance.json")
    projection = _read_object(output_root / "source-augmentation.json")
    if _canonical_bytes(request) != _canonical_bytes(expected_request.to_record()):
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum request differs from the plan"
        )
    download_record = _download_record(download)
    document_path = output_root / "documents" / download_record.local_path
    try:
        payload = document_path.read_bytes()
    except OSError as exc:
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum document is unavailable"
        ) from exc
    if (
        len(payload) != download_record.byte_count
        or hashlib.sha256(payload).hexdigest() != download_record.sha256
    ):
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum bytes differ from its record"
        )
    base_keys, candidate_row_sha256 = _corrected_selection_state(
        corrected_selection_bytes
    )
    expected_clearance = _clearance_from_saved_document(
        plan=plan,
        corrected_selection_bytes=corrected_selection_bytes,
        request=expected_request,
        download=download_record,
        payload=payload,
    )
    if _canonical_bytes(clearance) != _canonical_bytes(expected_clearance.to_record()):
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum clearance does not replay"
        )
    expected_projection = _projection(
        plan=plan,
        corrected_selection_bytes=corrected_selection_bytes,
        base_keys=base_keys,
        candidate_row_sha256=candidate_row_sha256,
        download=download_record,
        clearance=expected_clearance,
    )
    if _canonical_bytes(projection) != _canonical_bytes(expected_projection):
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum augmentation does not replay"
        )
    return FreeSupportMemorandumSourceAugmentation(
        plan=plan,
        request=expected_request,
        download=download_record,
        clearance=expected_clearance,
        projection=expected_projection,
    )


def _verified_plan(
    *, persisted_plan_bytes: bytes, bridge_descriptor_path: Path
) -> FreeSupportMemorandumRecoveryPlan:
    try:
        plan = verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=persisted_plan_bytes,
            bridge_descriptor_path=bridge_descriptor_path,
        )
    except (FreeSupportMemorandumRecoveryError, OSError, ValueError) as exc:
        raise FreeSupportMemorandumExecutorError(
            "support memorandum recovery plan is not authenticated"
        ) from exc
    record = plan.record
    required = {
        "schema_version",
        "candidate_id",
        "selection_sha256",
        "raw_docket_bridge_sha256",
        "raw_artifacts_manifest_sha256",
        "raw_docket_sha256",
        "raw_docket_byte_count",
        "target_motion_entry_number",
        "supporting_entry_number",
        "source_document_id",
        "document_role",
        "description",
        "source_url",
        "linkage_basis",
        "paid_permitted",
        "pacer_permitted",
        "recap_fetch_permitted",
        "provider_permitted",
        "retrieval_permitted",
        "parse_permitted",
        "materialization_permitted",
        "selection_mutation_permitted",
        "evaluation_permitted",
        "freeze_permitted",
        "dispatch_permitted",
    }
    if (
        set(record) != required
        or record.get("candidate_id") != _CANDIDATE_ID
        or record.get("source_document_id") != _SOURCE_DOCUMENT_ID
        or record.get("target_motion_entry_number") != _TARGET_ENTRY_NUMBER
        or record.get("supporting_entry_number") != _SUPPORT_ENTRY_NUMBER
        or record.get("document_role") != DocumentRole.MTD_MEMORANDUM.value
        or record.get("linkage_basis") != "explicit_in_support_re_target_motion"
        or any(
            record.get(name) is not False
            for name in (
                "paid_permitted",
                "pacer_permitted",
                "recap_fetch_permitted",
                "provider_permitted",
                "retrieval_permitted",
                "parse_permitted",
                "materialization_permitted",
                "selection_mutation_permitted",
                "evaluation_permitted",
                "freeze_permitted",
                "dispatch_permitted",
            )
        )
    ):
        raise FreeSupportMemorandumExecutorError(
            "support memorandum plan is outside the fixed executor authority"
        )
    return plan


def _request_from_plan(
    plan: FreeSupportMemorandumRecoveryPlan,
) -> FreeDocumentDownloadRequest:
    source_url = plan.record.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        raise FreeSupportMemorandumExecutorError("support memorandum URL is invalid")
    return FreeDocumentDownloadRequest(
        candidate_id=_CANDIDATE_ID,
        source_provider="courtlistener_recap_public",
        source_document_id=_SOURCE_DOCUMENT_ID,
        docket_entry_number=_SUPPORT_ENTRY_NUMBER,
        document_role=DocumentRole.MTD_MEMORANDUM,
        source_url=source_url,
    )


def _corrected_selection_state(
    selection_bytes: bytes,
) -> tuple[set[tuple[str, str]], str]:
    rows = _jsonl(selection_bytes, "corrected selection")
    selected = [row for row in rows if row.get("selected") is True]
    candidate_ids = [_text(row, "candidate_id") for row in selected]
    if len(selected) != 100 or len(set(candidate_ids)) != 100:
        raise FreeSupportMemorandumExecutorError(
            "corrected selection must retain exactly 100 distinct candidates"
        )
    try:
        row = next(row for row in selected if row["candidate_id"] == _CANDIDATE_ID)
    except StopIteration as exc:
        raise FreeSupportMemorandumExecutorError(
            "corrected selection omits the support-memorandum candidate"
        ) from exc
    if row.get("target_motion_entry_numbers") != [_TARGET_ENTRY_NUMBER]:
        raise FreeSupportMemorandumExecutorError(
            "corrected selection target motion differs from entry 13"
        )
    documents = row.get("documents")
    if not isinstance(documents, list) or not documents:
        raise FreeSupportMemorandumExecutorError(
            "corrected selection support candidate lacks documents"
        )
    keys: set[tuple[str, str]] = set()
    for selected_row in selected:
        documents = selected_row.get("documents")
        if not isinstance(documents, list) or not documents:
            raise FreeSupportMemorandumExecutorError(
                "corrected selection contains an invalid document list"
            )
        candidate_id = _text(selected_row, "candidate_id")
        for raw_document in cast(list[object], documents):
            if not isinstance(raw_document, Mapping):
                raise FreeSupportMemorandumExecutorError(
                    "corrected selection contains an invalid document"
                )
            typed_document = cast(Mapping[str, object], raw_document)
            document_id = typed_document.get("source_document_id")
            if not isinstance(document_id, str) or not document_id:
                raise FreeSupportMemorandumExecutorError(
                    "corrected selection document ID is invalid"
                )
            key = (candidate_id, document_id)
            if key in keys:
                raise FreeSupportMemorandumExecutorError(
                    "corrected selection repeats a document identity"
                )
            keys.add(key)
    return keys, hashlib.sha256(_canonical_bytes(row)).hexdigest()


def _projection(
    *,
    plan: FreeSupportMemorandumRecoveryPlan,
    corrected_selection_bytes: bytes,
    base_keys: set[tuple[str, str]],
    candidate_row_sha256: str,
    download: FreeDocumentDownloadRecord,
    clearance: ClearanceRecord,
) -> JsonRecord:
    ordered_base = [
        {"candidate_id": candidate_id, "source_document_id": source_document_id}
        for candidate_id, source_document_id in sorted(base_keys)
    ]
    added = {"candidate_id": _CANDIDATE_ID, "source_document_id": _SOURCE_DOCUMENT_ID}
    augmented = [*ordered_base, added]
    return {
        "schema_version": SOURCE_AUGMENTATION_SCHEMA,
        "base_selection_sha256": hashlib.sha256(corrected_selection_bytes).hexdigest(),
        "base_selected_candidate_count": 100,
        "base_selected_document_count": len(ordered_base),
        "support_candidate_row_sha256": candidate_row_sha256,
        "plan_sha256": hashlib.sha256(plan.record_bytes).hexdigest(),
        "raw_docket_bridge_sha256": plan.record["raw_docket_bridge_sha256"],
        "additive_document": added,
        "selected_document_keys": augmented,
        "augmented_selected_document_count": len(augmented),
        "free_document_download_sha256": hashlib.sha256(
            _canonical_bytes(download.to_record())
        ).hexdigest(),
        "disclosure_clearance_sha256": hashlib.sha256(
            _canonical_bytes(clearance.to_record())
        ).hexdigest(),
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "provider_activity_executed": False,
        "evaluation_permitted": False,
        "freeze_permitted": False,
        "dispatch_permitted": False,
    }


def _clearance_from_saved_document(
    *,
    plan: FreeSupportMemorandumRecoveryPlan,
    corrected_selection_bytes: bytes,
    request: FreeDocumentDownloadRequest,
    download: FreeDocumentDownloadRecord,
    payload: bytes,
) -> ClearanceRecord:
    scan = scan_disclosure_document(payload)
    if scan.automated_markers or scan.coverage_status != "complete":
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum requires normal disclosure review"
        )
    return _clearance_record(
        plan=plan,
        corrected_selection_bytes=corrected_selection_bytes,
        request=request,
        download=download,
        scan=scan,
    )


def _clearance_record(
    *,
    plan: FreeSupportMemorandumRecoveryPlan,
    corrected_selection_bytes: bytes,
    request: FreeDocumentDownloadRequest,
    download: FreeDocumentDownloadRecord,
    scan: DisclosurePdfScan,
) -> ClearanceRecord:
    markers = scan.automated_markers
    routing_plan_sha256 = _routing_plan_sha256(
        plan=plan,
        corrected_selection_bytes=corrected_selection_bytes,
        download=download,
    )
    return ClearanceRecord(
        candidate_id=_CANDIDATE_ID,
        source_document_id=_SOURCE_DOCUMENT_ID,
        local_path=download.local_path,
        sha256=download.sha256,
        byte_count=download.byte_count,
        status="cleared",
        automated_markers=markers,
        restriction_status="public",
        restriction_evidence=(_PUBLIC_EVIDENCE,),
        reviewer_id=None,
        controlled_store_provenance=request.source_url,
        reviewed_at=None,
        free_or_purchased="free",
        clearance_basis="affirmative_public_provenance",
        routing_plan_sha256=routing_plan_sha256,
    )


def _routing_plan_sha256(
    *,
    plan: FreeSupportMemorandumRecoveryPlan,
    corrected_selection_bytes: bytes,
    download: FreeDocumentDownloadRecord,
) -> str:
    return hashlib.sha256(
        _canonical_bytes(
            {
                "kind": "free_support_memorandum_affirmative_public_provenance",
                "base_selection_sha256": hashlib.sha256(
                    corrected_selection_bytes
                ).hexdigest(),
                "plan_sha256": hashlib.sha256(plan.record_bytes).hexdigest(),
                "download": download.to_record(),
            }
        )
    ).hexdigest()


def _download_record(record: Mapping[str, object]) -> FreeDocumentDownloadRecord:
    expected = {
        "candidate_id",
        "source_provider",
        "source_document_id",
        "docket_entry_number",
        "document_role",
        "source_url",
        "local_path",
        "sha256",
        "byte_count",
        "free_or_purchased",
        "retry_count",
        "rate_limited",
        "reused_existing",
    }
    if set(record) != expected:
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum download has unexpected fields"
        )
    try:
        document_role = DocumentRole(_text(record, "document_role"))
    except ValueError as exc:
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum role is invalid"
        ) from exc
    candidate_id = _text(record, "candidate_id")
    source_provider = _text(record, "source_provider")
    source_document_id = _text(record, "source_document_id")
    docket_entry_number = record.get("docket_entry_number")
    source_url = _text(record, "source_url")
    local_path = _text(record, "local_path")
    sha256 = _text(record, "sha256")
    byte_count = record.get("byte_count")
    free_or_purchased = _text(record, "free_or_purchased")
    retry_count = record.get("retry_count")
    rate_limited = record.get("rate_limited")
    reused_existing = record.get("reused_existing")
    if (
        candidate_id != _CANDIDATE_ID
        or source_provider != "courtlistener_recap_public"
        or source_document_id != _SOURCE_DOCUMENT_ID
        or not isinstance(docket_entry_number, int)
        or isinstance(docket_entry_number, bool)
        or docket_entry_number != _SUPPORT_ENTRY_NUMBER
        or document_role is not DocumentRole.MTD_MEMORANDUM
        or free_or_purchased != "free"
        or not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or not isinstance(retry_count, int)
        or isinstance(retry_count, bool)
        or not isinstance(rate_limited, bool)
        or not isinstance(reused_existing, bool)
    ):
        raise FreeSupportMemorandumExecutorError(
            "saved support memorandum download identity is invalid"
        )
    return FreeDocumentDownloadRecord(
        candidate_id=candidate_id,
        source_provider=source_provider,
        source_document_id=source_document_id,
        docket_entry_number=docket_entry_number,
        document_role=document_role,
        source_url=source_url,
        local_path=local_path,
        sha256=sha256,
        byte_count=byte_count,
        free_or_purchased=free_or_purchased,
        retry_count=retry_count,
        rate_limited=rate_limited,
        reused_existing=reused_existing,
    )


def _read_object(path: Path) -> JsonRecord:
    try:
        payload = path.read_bytes()
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FreeSupportMemorandumExecutorError(
            f"missing or invalid support memorandum artifact: {path.name}"
        ) from exc
    if not isinstance(value, Mapping):
        raise FreeSupportMemorandumExecutorError(
            f"support memorandum artifact is not canonical: {path.name}"
        )
    record = dict(cast(Mapping[str, Any], value))
    if _canonical_bytes(record) != payload:
        raise FreeSupportMemorandumExecutorError(
            f"support memorandum artifact is not canonical: {path.name}"
        )
    return record


def _jsonl(payload: bytes, label: str) -> list[JsonRecord]:
    try:
        rows = [json.loads(line) for line in payload.decode("utf-8").splitlines()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FreeSupportMemorandumExecutorError(f"{label} is not JSONL") from exc
    if not rows or any(not isinstance(row, Mapping) for row in rows):
        raise FreeSupportMemorandumExecutorError(f"{label} is malformed")
    return [dict(cast(Mapping[str, Any], row)) for row in rows]


def _text(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise FreeSupportMemorandumExecutorError(
            f"support memorandum {key} must be a non-empty string"
        )
    return value


def _canonical_bytes(record: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(
        dict(record),
        error_type=FreeSupportMemorandumExecutorError,
        error_message="support memorandum artifact cannot be canonicalized",
    )
