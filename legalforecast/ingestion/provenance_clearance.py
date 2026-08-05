"""Provenance-first disclosure routing with hash-bound human exceptions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import cast

from legalforecast.ingestion.canonical_json import (
    canonical_json_bytes as _canonical_json_bytes,
)
from legalforecast.ingestion.disclosure_clearance import (
    PDF_SCAN_SCHEMA_VERSION,
    PDF_SCAN_SCHEMA_VERSION_V1,
    ClearanceRecord,
    DisclosureClearanceError,
    DisclosurePdfScan,
    normalize_restriction_token,
    safe_disclosure_document_path,
    scan_disclosure_document,
    scan_disclosure_document_v1,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.disclosure_uri import is_allowlisted_public_recap_uri

PLAN_SCHEMA_VERSION = "legalforecast.disclosure_provenance_routing_plan.v2"
WORKSHEET_SCHEMA_VERSION = "legalforecast.disclosure_exception_worksheet.v2"
PLAN_SCHEMA_VERSION_V3 = "legalforecast.disclosure_provenance_routing_plan.v3"
WORKSHEET_SCHEMA_VERSION_V3 = "legalforecast.disclosure_exception_worksheet.v3"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_RESTRICTED_STATUSES = frozenset({"private", "restricted", "sealed", "under_seal"})
_PUBLIC_EVIDENCE = frozenset({"courtlistener_public_download_record_checked"})
_REST_PUBLIC_EVIDENCE = frozenset(
    {
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "courtlistener_rest_public_download_url_allowlisted",
    }
)
_POSITIVE_RESTRICTION_EVIDENCE = re.compile(
    r"(?:^|_)(?:sealed|private|restricted|under_seal)(?:_true|$)"
)
_RECOVERED_PUBLIC_EVIDENCE = frozenset(
    {
        "courtlistener_recap_fetch_fresh_detail_exact_match",
        "courtlistener_recap_fetch_is_available_true",
        "courtlistener_recap_fetch_is_sealed_false",
        "courtlistener_recap_fetch_no_positive_private_marker",
    }
)
_UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)


class ProvenanceClearanceError(ValueError):
    """Raised when provenance routing is incomplete, contradictory, or changed."""


def _recovered_public_capability_boundary() -> tuple[
    Callable[[Sequence[Mapping[str, object]]], object],
    Callable[[object | None], Mapping[tuple[str, str], Mapping[str, object]]],
]:
    """Keep verifier-issued recovered-public authority opaque to callers."""

    capabilities: dict[object, dict[tuple[str, str], Mapping[str, object]]] = {}

    def issue(rows: Sequence[Mapping[str, object]]) -> object:
        indexed: dict[tuple[str, str], Mapping[str, object]] = {}
        expected = {
            "candidate_id",
            "source_document_id",
            "recovery_run_card_sha256",
            "recovery_manifest_sha256",
            "recovery_restriction_evidence_sha256",
            "purchase_state_sha256",
            "purchase_operation_sha256",
            "purchase_operation_key",
            "fresh_recap_detail_sha256",
        }
        for raw in rows:
            row = dict(raw)
            key = _key(row)
            if key in indexed or set(row) != expected:
                raise ProvenanceClearanceError(
                    "invalid recovered-public verifier evidence"
                )
            for field in (
                "recovery_run_card_sha256",
                "recovery_manifest_sha256",
                "recovery_restriction_evidence_sha256",
                "purchase_state_sha256",
                "purchase_operation_sha256",
                "fresh_recap_detail_sha256",
            ):
                _digest(row, field)
            operation_key = row.get("purchase_operation_key")
            if (
                not isinstance(operation_key, str)
                or _UUID4.fullmatch(operation_key) is None
            ):
                raise ProvenanceClearanceError(
                    "invalid recovered-public purchase operation key"
                )
            indexed[key] = row
        capability = object()
        capabilities[capability] = indexed
        return capability

    def consume(
        capability: object | None,
    ) -> Mapping[tuple[str, str], Mapping[str, object]]:
        try:
            return capabilities[capability]
        except (KeyError, TypeError):
            raise ProvenanceClearanceError(
                "recovered-public clearance requires a verifier-issued capability"
            ) from None

    return issue, consume


(
    _issue_recovered_public_clearance_capability,
    _consume_recovered_public_clearance_capability,
) = _recovered_public_capability_boundary()
del _recovered_public_capability_boundary


def canonical_json_bytes(value: object) -> bytes:
    """Serialize one artifact value in its canonical representation."""

    return _canonical_json_bytes(
        value,
        error_type=ProvenanceClearanceError,
        error_message="provenance artifact is not canonical JSON",
    )


def build_provenance_clearance_plan(
    review_requests: Sequence[Mapping[str, object]],
    download_manifest: Sequence[Mapping[str, object]],
    restriction_evidence: Sequence[Mapping[str, object]],
    case_relevance: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
    case_relevance_bytes: bytes,
    document_bytes_by_relative_path: Mapping[str, bytes] | None = None,
    document_scanner: Callable[[bytes], DisclosurePdfScan] = scan_disclosure_document,
) -> dict[str, object]:
    """Derive complete auto-clear versus John-review routing from exact inputs."""

    _require_records_match(review_requests, review_requests_bytes, "review requests")
    _require_records_match(download_manifest, download_manifest_bytes, "manifest")
    _require_records_match(
        restriction_evidence, restriction_evidence_bytes, "restriction evidence"
    )
    _require_records_match(case_relevance, case_relevance_bytes, "case relevance")
    requests = _index(review_requests, "review request")
    manifest = _index(download_manifest, "manifest")
    restrictions = _index(restriction_evidence, "restriction evidence")
    relevance = _relevance_index(case_relevance)
    exact_keysets = {frozenset(index) for index in (requests, manifest, restrictions)}
    if len(exact_keysets) != 1 or not set(manifest).issubset(relevance):
        raise ProvenanceClearanceError(
            "provenance routing input coverage mismatch across exact source artifacts"
        )
    expected_relative_paths = {
        _required_text(source, "local_path") for source in manifest.values()
    }
    if (
        document_bytes_by_relative_path is not None
        and set(document_bytes_by_relative_path) != expected_relative_paths
    ):
        raise ProvenanceClearanceError(
            "authenticated document snapshot coverage differs from manifest"
        )
    for key in sorted(set(relevance) - set(manifest)):
        extra = relevance[key]
        if (
            extra.get("availability_status") != "unavailable"
            or extra.get("requires_paid_recovery") is not True
            or extra.get("is_available") is not False
        ):
            raise ProvenanceClearanceError(
                f"extra case relevance document is not a missing paid gap: {key}"
            )

    documents: list[dict[str, object]] = []
    for key in sorted(manifest):
        request = requests[key]
        source = manifest[key]
        restriction = restrictions[key]
        visibility = relevance[key]
        _validate_request(request, source=source, restriction=restriction, key=key)
        _validate_restriction_flags(restriction, key=key)
        _validate_visibility_flags(visibility, key=key)
        relative_path = _required_text(source, "local_path")
        data = _read_document(
            document_root,
            relative_path,
            key=key,
            document_bytes_by_relative_path=document_bytes_by_relative_path,
        )
        digest = hashlib.sha256(data).hexdigest()
        byte_count = len(data)
        if digest != _digest(source, "sha256") or byte_count != _nonnegative_int(
            source, "byte_count"
        ):
            raise ProvenanceClearanceError(
                f"document manifest commitment mismatch: {key}"
            )
        scan = document_scanner(data)
        scan_record = scan.to_record()
        _validate_scan_record(scan_record, key=key)
        markers = scan.automated_markers
        route_reasons: list[str] = []
        positive_restriction = _positive_restriction(restriction)
        visibility_valid = _visibility_contract_valid(visibility)
        affirmative_public = _affirmative_public_provenance(
            source, restriction=restriction, visibility=visibility
        )
        if positive_restriction:
            route_reasons.append("positive_restriction_evidence")
        if not visibility_valid:
            route_reasons.append("visibility_contract_contradiction")
        if not affirmative_public:
            route_reasons.append("affirmative_public_provenance_unproven")
        if scan.coverage_status != "complete":
            route_reasons.append("page_scan_coverage_incomplete")
        if markers:
            route_reasons.append("automated_marker_present")
        auto_clear = not route_reasons
        documents.append(
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "local_path": relative_path,
                "sha256": digest,
                "byte_count": byte_count,
                "free_or_purchased": _required_text(source, "free_or_purchased"),
                "source_provider": source.get("source_provider"),
                "source_url": source.get("source_url"),
                "source_url_or_reference": visibility.get("source_url_or_reference"),
                "restriction_status": _required_text(restriction, "restriction_status"),
                "restriction_evidence": list(
                    _text_set(restriction, "restriction_evidence")
                ),
                "is_sealed": restriction.get("is_sealed"),
                "is_private": restriction.get("is_private"),
                "model_visible": visibility.get("model_visible"),
                "contains_target_outcome": visibility.get("contains_target_outcome"),
                "disclosure_pdf_scan": scan_record,
                "automated_markers": list(markers),
                "route": "auto_clear" if auto_clear else "john_exception_review",
                "route_reasons": route_reasons,
                "human_clearance_permitted": not (
                    positive_restriction or not visibility_valid
                ),
            }
        )
    auto_count = sum(row["route"] == "auto_clear" for row in documents)
    plan: dict[str, object] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "source_sha256": {
            "review_requests": hashlib.sha256(review_requests_bytes).hexdigest(),
            "download_manifest": hashlib.sha256(download_manifest_bytes).hexdigest(),
            "restriction_evidence": hashlib.sha256(
                restriction_evidence_bytes
            ).hexdigest(),
            "case_relevance": hashlib.sha256(case_relevance_bytes).hexdigest(),
        },
        "document_set_sha256": hashlib.sha256(
            canonical_json_bytes(documents)
        ).hexdigest(),
        "document_count": len(documents),
        "auto_clear_count": auto_count,
        "john_review_count": len(documents) - auto_count,
        "documents": documents,
    }
    document_scanner_for_plan(plan)
    return plan


def document_scanner_for_plan(
    plan: Mapping[str, object],
) -> Callable[[bytes], DisclosurePdfScan]:
    """Select the exact scanner needed to replay one immutable routing plan."""

    raw_documents = plan.get("documents")
    if not isinstance(raw_documents, list):
        raise ProvenanceClearanceError(
            "routing plan requires documents for scanner selection"
        )
    if not raw_documents:
        return scan_disclosure_document
    versions: set[tuple[object, object]] = set()
    for raw_document in cast(list[object], raw_documents):
        if not isinstance(raw_document, Mapping):
            raise ProvenanceClearanceError(
                "routing plan document is invalid for scanner selection"
            )
        document = cast(Mapping[str, object], raw_document)
        scan = document.get("disclosure_pdf_scan")
        if not isinstance(scan, Mapping):
            raise ProvenanceClearanceError(
                "routing plan lacks PDF scan for scanner selection"
            )
        typed_scan = cast(Mapping[str, object], scan)
        versions.add((typed_scan.get("schema_version"), typed_scan.get("method")))
    if versions == {(PDF_SCAN_SCHEMA_VERSION_V1, "pypdf_page_text_v1")}:
        return scan_disclosure_document_v1
    if versions == {(PDF_SCAN_SCHEMA_VERSION, "pypdf_page_text_v2")}:
        return scan_disclosure_document
    raise ProvenanceClearanceError(
        "routing plan has unsupported or mixed PDF scanner versions"
    )


def exception_review_worksheet(plan: Mapping[str, object]) -> dict[str, object]:
    """Project only exception-routed rows into the existing interactive recorder."""

    documents = _plan_documents(plan)
    exceptions = [
        row for row in documents if row.get("route") == "john_exception_review"
    ]
    routing_plan_sha256 = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()
    return {
        "schema_version": WORKSHEET_SCHEMA_VERSION,
        "routing_plan_sha256": routing_plan_sha256,
        "document_set_sha256": hashlib.sha256(
            canonical_json_bytes(exceptions)
        ).hexdigest(),
        "document_count": len(exceptions),
        "documents": exceptions,
    }


def build_provenance_clearance_plan_v3(
    review_requests: Sequence[Mapping[str, object]],
    download_manifest: Sequence[Mapping[str, object]],
    restriction_evidence: Sequence[Mapping[str, object]],
    case_relevance: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
    case_relevance_bytes: bytes,
    document_bytes_by_relative_path: Mapping[str, bytes] | None = None,
    document_scanner: Callable[[bytes], DisclosurePdfScan] = scan_disclosure_document,
    verified_recovery_capability: object | None = None,
) -> dict[str, object]:
    """Build additive v3 routing with reviewer-neutral exception vocabulary."""

    legacy = build_provenance_clearance_plan(
        review_requests,
        download_manifest,
        restriction_evidence,
        case_relevance,
        document_root=document_root,
        review_requests_bytes=review_requests_bytes,
        download_manifest_bytes=download_manifest_bytes,
        restriction_evidence_bytes=restriction_evidence_bytes,
        case_relevance_bytes=case_relevance_bytes,
        document_bytes_by_relative_path=document_bytes_by_relative_path,
        document_scanner=document_scanner,
    )
    recovered: Mapping[tuple[str, str], Mapping[str, object]] = (
        {}
        if verified_recovery_capability is None
        else _consume_recovered_public_clearance_capability(
            verified_recovery_capability
        )
    )
    manifest_index = _index(download_manifest, "manifest")
    restriction_index = _index(restriction_evidence, "restriction evidence")
    relevance_index = _relevance_index(case_relevance)
    legacy_documents = cast(list[dict[str, object]], legacy["documents"])
    documents: list[dict[str, object]] = []
    for legacy_document in legacy_documents:
        document = dict(legacy_document)
        key = _key(document)
        recovery_lineage = recovered.get(key)
        if recovery_lineage is not None and _verified_recovered_public_document(
            manifest_index[key],
            restriction=restriction_index[key],
            visibility=relevance_index[key],
            lineage=recovery_lineage,
        ):
            scan = cast(Mapping[str, object], document["disclosure_pdf_scan"])
            if scan.get("coverage_status") == "complete" and not document.get(
                "automated_markers"
            ):
                document["route"] = "auto_clear"
                document["route_reasons"] = []
                document["recovered_public_lineage"] = dict(recovery_lineage)
        if document["route"] == "john_exception_review":
            document["route"] = "exception_review"
        document["exception_clearance_permitted"] = document.pop(
            "human_clearance_permitted"
        )
        documents.append(document)
    auto_count = sum(row["route"] == "auto_clear" for row in documents)
    plan: dict[str, object] = {
        "schema_version": PLAN_SCHEMA_VERSION_V3,
        "source_sha256": legacy["source_sha256"],
        "document_set_sha256": hashlib.sha256(
            canonical_json_bytes(documents)
        ).hexdigest(),
        "document_count": legacy["document_count"],
        "auto_clear_count": auto_count,
        "exception_review_count": len(documents) - auto_count,
        "documents": documents,
    }
    document_scanner_for_plan(plan)
    return plan


def exception_review_worksheet_v3(
    plan: Mapping[str, object],
) -> dict[str, object]:
    """Project reviewer-neutral v3 exception rows."""

    documents = _plan_documents_v3(plan)
    exceptions = [
        deepcopy(row) for row in documents if row.get("route") == "exception_review"
    ]
    return {
        "schema_version": WORKSHEET_SCHEMA_VERSION_V3,
        "routing_plan_sha256": hashlib.sha256(canonical_json_bytes(plan)).hexdigest(),
        "document_set_sha256": hashlib.sha256(
            canonical_json_bytes(exceptions)
        ).hexdigest(),
        "document_count": len(exceptions),
        "documents": exceptions,
    }


def validate_exception_review_worksheet_v3(
    worksheet: Mapping[str, object],
    *,
    routing_plan: Mapping[str, object],
    routing_plan_bytes: bytes,
    worksheet_bytes: bytes,
) -> list[Mapping[str, object]]:
    """Validate exact bytes and the exact v3 routing-plan exception projection."""

    if _load_exact_json_object(routing_plan_bytes, "routing plan") != dict(
        routing_plan
    ) or routing_plan_bytes != canonical_json_bytes(routing_plan):
        raise ProvenanceClearanceError("routing plan differs from exact bytes")
    if _load_exact_json_object(worksheet_bytes, "worksheet") != dict(
        worksheet
    ) or worksheet_bytes != canonical_json_bytes(worksheet):
        raise ProvenanceClearanceError("worksheet differs from exact bytes")
    plan_documents = _plan_documents_v3(routing_plan)
    expected_documents = [
        row for row in plan_documents if row.get("route") == "exception_review"
    ]
    expected_plan_sha256 = hashlib.sha256(
        canonical_json_bytes(routing_plan)
    ).hexdigest()

    expected_fields = {
        "schema_version",
        "routing_plan_sha256",
        "document_set_sha256",
        "document_count",
        "documents",
    }
    if (
        set(worksheet) != expected_fields
        or worksheet.get("schema_version") != WORKSHEET_SCHEMA_VERSION_V3
    ):
        raise ProvenanceClearanceError("invalid provenance exception worksheet shape")
    if worksheet.get("routing_plan_sha256") != expected_plan_sha256:
        raise ProvenanceClearanceError("worksheet routing plan hash mismatch")
    raw = worksheet.get("documents")
    if not isinstance(raw, list):
        raise ProvenanceClearanceError("provenance exception worksheet lacks documents")
    documents: list[Mapping[str, object]] = []
    keys: list[tuple[str, str]] = []
    for value in cast(list[object], raw):
        if not isinstance(value, Mapping):
            raise ProvenanceClearanceError(
                "provenance exception worksheet document is not an object"
            )
        row = cast(Mapping[str, object], value)
        key = _key(row)
        _validate_plan_document_v3(row, key=key)
        if row.get("route") != "exception_review":
            raise ProvenanceClearanceError(
                f"provenance exception worksheet contains auto-clear row: {key}"
            )
        documents.append(row)
        keys.append(key)
    if keys != sorted(set(keys)):
        raise ProvenanceClearanceError(
            "provenance exception worksheet documents are not unique and ordered"
        )
    document_count = _nonnegative_int(worksheet, "document_count")
    if (
        documents != expected_documents
        or document_count != len(documents)
        or worksheet.get("document_set_sha256")
        != hashlib.sha256(canonical_json_bytes(documents)).hexdigest()
    ):
        raise ProvenanceClearanceError(
            "provenance exception worksheet summary mismatch"
        )
    return documents


def _load_exact_json_object(data: bytes, label: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ProvenanceClearanceError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceClearanceError(f"{label} bytes are malformed") from exc
    if not isinstance(value, dict):
        raise ProvenanceClearanceError(f"{label} must be an object")
    return cast(dict[str, object], value)


def validate_exception_review_worksheet(
    worksheet: Mapping[str, object],
) -> list[Mapping[str, object]]:
    """Validate and return the canonically ordered closed v2 exception rows."""

    expected_fields = {
        "schema_version",
        "routing_plan_sha256",
        "document_set_sha256",
        "document_count",
        "documents",
    }
    if (
        set(worksheet) != expected_fields
        or worksheet.get("schema_version") != WORKSHEET_SCHEMA_VERSION
    ):
        raise ProvenanceClearanceError("invalid provenance exception worksheet shape")
    _digest(worksheet, "routing_plan_sha256")
    raw = worksheet.get("documents")
    if not isinstance(raw, list):
        raise ProvenanceClearanceError("provenance exception worksheet lacks documents")
    documents: list[Mapping[str, object]] = []
    keys: list[tuple[str, str]] = []
    for value in cast(list[object], raw):
        if not isinstance(value, Mapping):
            raise ProvenanceClearanceError(
                "provenance exception worksheet document is not an object"
            )
        row = cast(Mapping[str, object], value)
        key = _key(row)
        _validate_plan_document(row, key=key)
        if row.get("route") != "john_exception_review":
            raise ProvenanceClearanceError(
                f"provenance exception worksheet contains auto-clear row: {key}"
            )
        documents.append(row)
        keys.append(key)
    if keys != sorted(set(keys)):
        raise ProvenanceClearanceError(
            "provenance exception worksheet documents are not unique and ordered"
        )
    if (
        worksheet.get("document_count") != len(documents)
        or worksheet.get("document_set_sha256")
        != hashlib.sha256(canonical_json_bytes(documents)).hexdigest()
    ):
        raise ProvenanceClearanceError(
            "provenance exception worksheet summary mismatch"
        )
    return documents


def build_exception_inspection_map(
    plan: Mapping[str, object],
    *,
    document_root: Path,
    document_bytes_by_relative_path: Mapping[str, bytes] | None = None,
) -> bytes:
    """Map only exception-routed commitments to contained local inspection bytes."""

    schema_version = plan.get("schema_version")
    if schema_version == PLAN_SCHEMA_VERSION:
        documents = _plan_documents(plan)
        exception_route = "john_exception_review"
    elif schema_version == PLAN_SCHEMA_VERSION_V3:
        documents = _plan_documents_v3(plan)
        exception_route = "exception_review"
    else:
        raise ProvenanceClearanceError("unsupported provenance routing plan")
    rows: list[dict[str, object]] = []
    for document in documents:
        if document.get("route") != exception_route:
            continue
        key = _key(document)
        relative = _required_text(document, "local_path")
        data = _read_document(
            document_root,
            relative,
            key=key,
            document_bytes_by_relative_path=document_bytes_by_relative_path,
        )
        digest = hashlib.sha256(data).hexdigest()
        if digest != _digest(document, "sha256") or len(data) != _nonnegative_int(
            document, "byte_count"
        ):
            raise ProvenanceClearanceError(
                f"exception inspection commitment mismatch: {key}"
            )
        inspection_path = safe_disclosure_document_path(document_root, relative)
        rows.append(
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "inspection_path": str(inspection_path),
                "sha256": digest,
                "byte_count": len(data),
            }
        )
    return b"".join(canonical_json_bytes(row) for row in rows)


def build_provenance_clearance_records(
    plan: Mapping[str, object],
    exception_decisions: Sequence[Mapping[str, object]],
    *,
    routing_plan_sha256: str,
) -> tuple[ClearanceRecord, ...]:
    """Apply a complete interactive exception artifact to one immutable plan."""

    if hashlib.sha256(canonical_json_bytes(plan)).hexdigest() != _strict_digest(
        routing_plan_sha256, "routing plan hash"
    ):
        raise ProvenanceClearanceError("routing plan hash mismatch")
    documents = _plan_documents(plan)
    exceptions = {
        _key(row): row
        for row in documents
        if row.get("route") == "john_exception_review"
    }
    decisions = _validated_decisions(exception_decisions, exceptions=exceptions)
    records: list[ClearanceRecord] = []
    for document in documents:
        key = _key(document)
        markers = tuple(_text_list(document, "automated_markers"))
        evidence = tuple(_text_list(document, "restriction_evidence"))
        if document.get("route") == "auto_clear":
            status = "cleared"
            reviewer_id = None
            reviewed_at = None
            provenance = _required_text(document, "source_url")
            basis = "affirmative_public_provenance"
        else:
            decision = decisions[key]
            status = _required_text(decision, "status")
            if (
                status == "cleared"
                and document.get("human_clearance_permitted") is not True
            ):
                raise ProvenanceClearanceError(
                    "positive restriction or visibility contradiction cannot be "
                    f"cleared: {key}"
                )
            reviewer_id = _required_text(decision, "intended_reviewer_id")
            reviewed_at = _required_text(decision, "reviewed_at")
            provenance = "private-store://john/disclosure-exception-review"
            basis = "john_exception_review"
        records.append(
            ClearanceRecord(
                candidate_id=key[0],
                source_document_id=key[1],
                local_path=_required_text(document, "local_path"),
                sha256=_digest(document, "sha256"),
                byte_count=_nonnegative_int(document, "byte_count"),
                status=status,
                automated_markers=markers,
                restriction_status=_required_text(document, "restriction_status"),
                restriction_evidence=evidence,
                reviewer_id=reviewer_id,
                controlled_store_provenance=provenance,
                reviewed_at=reviewed_at,
                free_or_purchased=_required_text(document, "free_or_purchased"),
                clearance_basis=basis,
                routing_plan_sha256=routing_plan_sha256,
            )
        )
    return tuple(records)


def build_provider_free_quarantine_records_v3(
    plan: Mapping[str, object],
    *,
    routing_plan_sha256: str,
) -> tuple[ClearanceRecord, ...]:
    """Clear automatic v3 rows and quarantine every exception without review."""

    if hashlib.sha256(canonical_json_bytes(plan)).hexdigest() != _strict_digest(
        routing_plan_sha256, "routing plan hash"
    ):
        raise ProvenanceClearanceError("routing plan hash mismatch")
    documents = _plan_documents_v3(plan)
    records: list[ClearanceRecord] = []
    for document in documents:
        key = _key(document)
        automatic = document.get("route") == "auto_clear"
        recovered_lineage = document.get("recovered_public_lineage")
        recovered_public = automatic and isinstance(recovered_lineage, Mapping)
        records.append(
            ClearanceRecord(
                candidate_id=key[0],
                source_document_id=key[1],
                local_path=_required_text(document, "local_path"),
                sha256=_digest(document, "sha256"),
                byte_count=_nonnegative_int(document, "byte_count"),
                status="cleared" if automatic else "quarantined",
                automated_markers=tuple(_text_list(document, "automated_markers")),
                restriction_status=_required_text(document, "restriction_status"),
                restriction_evidence=tuple(
                    _text_list(document, "restriction_evidence")
                ),
                reviewer_id=None,
                controlled_store_provenance=(
                    (
                        f"courtlistener-rest://recap-documents/{key[1]}"
                        if recovered_public
                        else _required_text(document, "source_url")
                    )
                    if automatic
                    else None
                ),
                reviewed_at=None,
                free_or_purchased=_required_text(document, "free_or_purchased"),
                clearance_basis=(
                    "provider_free_recovered_public"
                    if recovered_public
                    else "affirmative_public_provenance"
                    if automatic
                    else "provider_free_exception_quarantine"
                ),
                routing_plan_sha256=routing_plan_sha256,
                recovered_public_lineage=(
                    dict(cast(Mapping[str, object], recovered_lineage))
                    if recovered_public
                    else None
                ),
            )
        )
    return tuple(records)


def build_authenticated_model_provenance_clearance_records_v3(
    plan: Mapping[str, object],
    *,
    model_review_capability: object,
    routing_plan_sha256: str,
) -> tuple[ClearanceRecord, ...]:
    """Apply only decisions carried by verifier-issued model authority."""

    from legalforecast.ingestion.disclosure_model_review import (
        DECISION_SCHEMA_VERSION,
        model_review_eligible_documents,
    )
    from legalforecast.ingestion.disclosure_model_review_authority import (
        public_disclosure_model_review_record,
    )

    if hashlib.sha256(canonical_json_bytes(plan)).hexdigest() != _strict_digest(
        routing_plan_sha256, "routing plan hash"
    ):
        raise ProvenanceClearanceError("routing plan hash mismatch")
    documents = _plan_documents_v3(plan)
    eligible = model_review_eligible_documents(
        tuple(row for row in documents if row.get("route") == "exception_review")
    )
    eligible_index = {_key(row): row for row in eligible}
    try:
        authority = public_disclosure_model_review_record(model_review_capability)
    except ValueError as exc:
        raise ProvenanceClearanceError(str(exc)) from exc
    if authority.get("routing_plan_sha256") != routing_plan_sha256:
        raise ProvenanceClearanceError("model authority routing plan hash mismatch")
    raw_decisions = authority.get("decisions")
    if not isinstance(raw_decisions, list):
        raise ProvenanceClearanceError("model authority lacks decisions")
    decisions: dict[tuple[str, str], Mapping[str, object]] = {}
    expected_fields = {
        "schema_version",
        "candidate_id",
        "source_document_id",
        "document_sha256",
        "prompt_sha256",
        "batch_prompt_sha256",
        "response_sha256",
        "batch_response_sha256",
        "reviewer_registry_entry_sha256",
        "status",
    }
    for value in cast(list[object], raw_decisions):
        if not isinstance(value, Mapping):
            raise ProvenanceClearanceError("model authority decision is invalid")
        decision = cast(Mapping[str, object], value)
        key = _key(decision)
        if (
            set(decision) != expected_fields
            or decision.get("schema_version") != DECISION_SCHEMA_VERSION
            or decision.get("status") not in ("cleared", "quarantined")
            or key in decisions
        ):
            raise ProvenanceClearanceError("model authority decision is invalid")
        decisions[key] = decision
    if list(decisions) != sorted(decisions) or set(decisions) != set(eligible_index):
        raise ProvenanceClearanceError("model authority decision coverage mismatch")
    for key, decision in decisions.items():
        if decision.get("document_sha256") != eligible_index[key].get("sha256"):
            raise ProvenanceClearanceError(
                f"model authority reviewed wrong document bytes: {key}"
            )

    records: list[ClearanceRecord] = []
    reviewer_id = authority.get("reviewer_registry_key")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        raise ProvenanceClearanceError("model authority reviewer identity is invalid")
    for document in documents:
        key = _key(document)
        automatic = document.get("route") == "auto_clear"
        recovered_lineage = document.get("recovered_public_lineage")
        recovered_public = automatic and isinstance(recovered_lineage, Mapping)
        decision = decisions.get(key)
        status = (
            "cleared"
            if automatic
            else cast(str, decision["status"])
            if decision is not None
            else "quarantined"
        )
        records.append(
            ClearanceRecord(
                candidate_id=key[0],
                source_document_id=key[1],
                local_path=_required_text(document, "local_path"),
                sha256=_digest(document, "sha256"),
                byte_count=_nonnegative_int(document, "byte_count"),
                status=status,
                automated_markers=tuple(_text_list(document, "automated_markers")),
                restriction_status=_required_text(document, "restriction_status"),
                restriction_evidence=tuple(
                    _text_list(document, "restriction_evidence")
                ),
                reviewer_id=reviewer_id if decision is not None else None,
                controlled_store_provenance=(
                    f"courtlistener-rest://recap-documents/{key[1]}"
                    if recovered_public
                    else _required_text(document, "source_url")
                    if automatic
                    else "private-store://disclosure/model-review"
                    if decision is not None
                    else None
                ),
                reviewed_at=None,
                free_or_purchased=_required_text(document, "free_or_purchased"),
                clearance_basis=(
                    "provider_free_recovered_public"
                    if recovered_public
                    else "affirmative_public_provenance"
                    if automatic
                    else "authenticated_model_exception_review"
                    if decision is not None
                    else "model_ineligible_exception_quarantine"
                ),
                routing_plan_sha256=routing_plan_sha256,
                recovered_public_lineage=(
                    dict(cast(Mapping[str, object], recovered_lineage))
                    if recovered_public
                    else None
                ),
            )
        )
    return tuple(records)


def _validated_decisions(
    rows: Sequence[Mapping[str, object]],
    *,
    exceptions: Mapping[tuple[str, str], Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    if not exceptions and not rows:
        return {}
    index = _index(rows, "exception decision")
    if set(index) != set(exceptions):
        raise ProvenanceClearanceError("exception decision coverage mismatch")
    if list(index) != sorted(index):
        raise ProvenanceClearanceError(
            "exception decisions are not canonically ordered"
        )
    pins: set[str] = set()
    bases: list[dict[str, object]] = []
    for key, row in index.items():
        expected_fields = {
            "candidate_id",
            "source_document_id",
            "status",
            "reviewed_at",
            "inspected_at",
            "inspected_sha256",
            "recording_method",
            "intended_reviewer_id",
            "batch_confirmation_sha256",
        }
        if (
            set(row) != expected_fields
            or row.get("recording_method") != "interactive_review_cli"
        ):
            raise ProvenanceClearanceError("invalid interactive exception decision")
        if row.get("status") not in ("cleared", "quarantined"):
            raise ProvenanceClearanceError(f"invalid exception decision status: {key}")
        if row.get("intended_reviewer_id") != "John Hughes":
            raise ProvenanceClearanceError(
                f"exception decision reviewer must be John Hughes: {key}"
            )
        for field in ("reviewed_at", "inspected_at"):
            timestamp = _required_text(row, field)
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ProvenanceClearanceError(
                    f"invalid exception decision timestamp: {key}"
                ) from exc
            if parsed.tzinfo is None:
                raise ProvenanceClearanceError(
                    f"invalid exception decision timestamp: {key}"
                )
        if _digest(row, "inspected_sha256") != _digest(exceptions[key], "sha256"):
            raise ProvenanceClearanceError(
                f"exception decision inspected wrong bytes: {key}"
            )
        pins.add(_digest(row, "batch_confirmation_sha256"))
        bases.append(
            {
                name: value
                for name, value in row.items()
                if name != "batch_confirmation_sha256"
            }
        )
    expected = hashlib.sha256(
        b"".join(canonical_json_bytes(row) for row in bases)
    ).hexdigest()
    if pins != {expected}:
        raise ProvenanceClearanceError("exception decision batch confirmation mismatch")
    return index


def _plan_documents(plan: Mapping[str, object]) -> list[Mapping[str, object]]:
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ProvenanceClearanceError("unsupported provenance routing plan")
    raw = plan.get("documents")
    if not isinstance(raw, list):
        raise ProvenanceClearanceError("provenance routing plan lacks documents")
    documents: list[Mapping[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for value in cast(list[object], raw):
        if not isinstance(value, Mapping):
            raise ProvenanceClearanceError("routing plan document is not an object")
        row = cast(Mapping[str, object], value)
        key = _key(row)
        if key in seen:
            raise ProvenanceClearanceError(f"duplicate routing plan document: {key}")
        seen.add(key)
        if row.get("route") not in {"auto_clear", "john_exception_review"}:
            raise ProvenanceClearanceError(f"invalid routing action: {key}")
        _validate_plan_document(row, key=key)
        documents.append(row)
    if [_key(row) for row in documents] != sorted(seen):
        raise ProvenanceClearanceError(
            "routing plan documents are not canonically ordered"
        )
    document_scanner_for_plan(plan)
    auto_count = sum(row.get("route") == "auto_clear" for row in documents)
    if (
        plan.get("document_count") != len(documents)
        or plan.get("auto_clear_count") != auto_count
        or plan.get("john_review_count") != len(documents) - auto_count
        or plan.get("document_set_sha256")
        != hashlib.sha256(canonical_json_bytes(documents)).hexdigest()
    ):
        raise ProvenanceClearanceError("provenance routing plan summary mismatch")
    return documents


def _plan_documents_v3(plan: Mapping[str, object]) -> list[Mapping[str, object]]:
    expected_fields = {
        "schema_version",
        "source_sha256",
        "document_set_sha256",
        "document_count",
        "auto_clear_count",
        "exception_review_count",
        "documents",
    }
    if (
        set(plan) != expected_fields
        or plan.get("schema_version") != PLAN_SCHEMA_VERSION_V3
    ):
        raise ProvenanceClearanceError("unsupported provenance routing plan")
    source_sha256 = plan.get("source_sha256")
    source_fields = {
        "review_requests",
        "download_manifest",
        "restriction_evidence",
        "case_relevance",
    }
    if not isinstance(source_sha256, Mapping):
        raise ProvenanceClearanceError("invalid provenance routing source commitments")
    source_commitments = cast(Mapping[str, object], source_sha256)
    if set(source_commitments) != source_fields:
        raise ProvenanceClearanceError("invalid provenance routing source commitments")
    for field in sorted(source_fields):
        value = source_commitments.get(field)
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise ProvenanceClearanceError(
                f"invalid provenance routing source digest: {field}"
            )
    raw = plan.get("documents")
    if not isinstance(raw, list):
        raise ProvenanceClearanceError("provenance routing plan lacks documents")
    documents: list[Mapping[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for value in cast(list[object], raw):
        if not isinstance(value, Mapping):
            raise ProvenanceClearanceError("routing plan document is not an object")
        row = cast(Mapping[str, object], value)
        key = _key(row)
        if key in seen:
            raise ProvenanceClearanceError(f"duplicate routing plan document: {key}")
        seen.add(key)
        _validate_plan_document_v3(row, key=key)
        documents.append(row)
    if [_key(row) for row in documents] != sorted(seen):
        raise ProvenanceClearanceError(
            "routing plan documents are not canonically ordered"
        )
    document_scanner_for_plan(plan)
    auto_count = sum(row.get("route") == "auto_clear" for row in documents)
    document_count = _nonnegative_int(plan, "document_count")
    declared_auto_count = _nonnegative_int(plan, "auto_clear_count")
    exception_review_count = _nonnegative_int(plan, "exception_review_count")
    if (
        document_count != len(documents)
        or declared_auto_count != auto_count
        or exception_review_count != len(documents) - auto_count
        or plan.get("document_set_sha256")
        != hashlib.sha256(canonical_json_bytes(documents)).hexdigest()
    ):
        raise ProvenanceClearanceError("provenance routing plan summary mismatch")
    return documents


def _validate_plan_document_v3(
    row: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    expected_fields = {
        "candidate_id",
        "source_document_id",
        "local_path",
        "sha256",
        "byte_count",
        "free_or_purchased",
        "source_provider",
        "source_url",
        "source_url_or_reference",
        "restriction_status",
        "restriction_evidence",
        "is_sealed",
        "is_private",
        "model_visible",
        "contains_target_outcome",
        "disclosure_pdf_scan",
        "automated_markers",
        "route",
        "route_reasons",
        "exception_clearance_permitted",
    }
    actual_fields = set(row)
    recovered_lineage = row.get("recovered_public_lineage")
    if actual_fields == expected_fields | {"recovered_public_lineage"}:
        if (
            not isinstance(recovered_lineage, Mapping)
            or row.get("route") != "auto_clear"
        ):
            raise ProvenanceClearanceError(
                f"invalid recovered-public routing lineage: {key}"
            )
        expected_fields = actual_fields
    if set(row) != expected_fields or row.get("route") not in {
        "auto_clear",
        "exception_review",
    }:
        raise ProvenanceClearanceError(f"invalid routing plan document shape: {key}")
    legacy = dict(row)
    legacy.pop("recovered_public_lineage", None)
    legacy["human_clearance_permitted"] = legacy.pop("exception_clearance_permitted")
    if legacy["route"] == "exception_review":
        legacy["route"] = "john_exception_review"
    if recovered_lineage is None:
        _validate_plan_document(legacy, key=key)
        return
    if legacy.get("source_url") is None:
        legacy["source_url"] = f"courtlistener-rest://recap-documents/{key[1]}"
    legacy["route"] = "john_exception_review"
    legacy["route_reasons"] = ["affirmative_public_provenance_unproven"]
    _validate_plan_document(legacy, key=key)
    if row.get("route_reasons") != []:
        raise ProvenanceClearanceError(
            f"invalid recovered-public routing decision: {key}"
        )


def _verified_recovered_public_document(
    source: Mapping[str, object],
    *,
    restriction: Mapping[str, object],
    visibility: Mapping[str, object],
    lineage: Mapping[str, object],
) -> bool:
    """Accept only the exact closed post-purchase CourtListener proof."""

    if (
        source.get("source_provider") != "courtlistener_recap_fetch"
        or source.get("free_or_purchased") != "purchased"
        or source.get("source_url") is not None
        or restriction.get("source_provider")
        != "courtlistener_recap_fetch_fresh_detail"
        or restriction.get("is_available") is not True
        or restriction.get("is_sealed") is not False
        or restriction.get("is_private") not in {False, None}
        or restriction.get("redaction_or_seal_status") != "public"
        or restriction.get("restriction_status") != "public"
        or tuple(_text_list(restriction, "restriction_evidence"))
        != tuple(sorted(_RECOVERED_PUBLIC_EVIDENCE))
        or not _visibility_contract_valid(visibility)
        or _positive_restriction(restriction)
    ):
        return False
    fresh_sha = restriction.get("fresh_recap_detail_sha256")
    return (
        isinstance(fresh_sha, str)
        and source.get("fresh_recap_detail_sha256") == fresh_sha
        and lineage.get("fresh_recap_detail_sha256") == fresh_sha
        and source.get("purchase_operation_key")
        == lineage.get("purchase_operation_key")
    )


def _validate_plan_document(row: Mapping[str, object], *, key: tuple[str, str]) -> None:
    expected_fields = {
        "candidate_id",
        "source_document_id",
        "local_path",
        "sha256",
        "byte_count",
        "free_or_purchased",
        "source_provider",
        "source_url",
        "source_url_or_reference",
        "restriction_status",
        "restriction_evidence",
        "is_sealed",
        "is_private",
        "model_visible",
        "contains_target_outcome",
        "disclosure_pdf_scan",
        "automated_markers",
        "route",
        "route_reasons",
        "human_clearance_permitted",
    }
    if set(row) != expected_fields:
        raise ProvenanceClearanceError(f"invalid routing plan document shape: {key}")
    _digest(row, "sha256")
    _nonnegative_int(row, "byte_count")
    _validate_relative_local_path(_required_text(row, "local_path"), key=key)
    if _required_text(row, "free_or_purchased") not in {"free", "purchased"}:
        raise ProvenanceClearanceError(
            f"free_or_purchased must be free or purchased: {key}"
        )
    for field in (
        "source_provider",
        "source_url",
        "source_url_or_reference",
        "restriction_status",
    ):
        _required_text(row, field)
    _validate_restriction_flags(row, key=key)
    _validate_visibility_flags(row, key=key)
    raw_scan = row.get("disclosure_pdf_scan")
    if not isinstance(raw_scan, Mapping):
        raise ProvenanceClearanceError(f"routing plan document lacks PDF scan: {key}")
    scan = cast(Mapping[str, object], raw_scan)
    _validate_scan_record(scan, key=key)
    markers = _text_list(row, "automated_markers")
    if markers != scan.get("automated_markers"):
        raise ProvenanceClearanceError(
            f"routing plan markers differ from PDF scan: {key}"
        )
    positive_restriction = _positive_restriction(row)
    visibility_valid = _visibility_contract_valid(row)
    affirmative_public = _affirmative_public_provenance(
        row, restriction=row, visibility=row
    )
    expected_reasons: list[str] = []
    if positive_restriction:
        expected_reasons.append("positive_restriction_evidence")
    if not visibility_valid:
        expected_reasons.append("visibility_contract_contradiction")
    if not affirmative_public:
        expected_reasons.append("affirmative_public_provenance_unproven")
    if scan.get("coverage_status") != "complete":
        expected_reasons.append("page_scan_coverage_incomplete")
    if markers:
        expected_reasons.append("automated_marker_present")
    expected_route = "auto_clear" if not expected_reasons else "john_exception_review"
    if (
        row.get("route_reasons") != expected_reasons
        or row.get("route") != expected_route
        or row.get("human_clearance_permitted")
        is not (not positive_restriction and visibility_valid)
    ):
        raise ProvenanceClearanceError(f"invalid routing plan decision: {key}")


def _validate_scan_record(scan: Mapping[str, object], *, key: tuple[str, str]) -> None:
    expected_fields = {
        "schema_version",
        "method",
        "parsed_page_count",
        "text_scanned_page_numbers",
        "text_scanned_page_count",
        "ocr_scanned_page_numbers",
        "ocr_scanned_page_count",
        "unscanned_page_numbers",
        "coverage_status",
        "diagnostics",
        "automated_markers",
    }
    scanner_identity = (scan.get("schema_version"), scan.get("method"))
    supported_scanners = {
        (PDF_SCAN_SCHEMA_VERSION_V1, "pypdf_page_text_v1"),
        (PDF_SCAN_SCHEMA_VERSION, "pypdf_page_text_v2"),
    }
    if set(scan) != expected_fields or scanner_identity not in supported_scanners:
        raise ProvenanceClearanceError(f"invalid PDF scan shape: {key}")
    parsed_page_count = _nonnegative_int(scan, "parsed_page_count")
    text_pages = _page_numbers(scan, "text_scanned_page_numbers", key=key)
    ocr_pages = _page_numbers(scan, "ocr_scanned_page_numbers", key=key)
    unscanned_pages = _page_numbers(scan, "unscanned_page_numbers", key=key)
    text_page_count = _nonnegative_int(scan, "text_scanned_page_count")
    ocr_page_count = _nonnegative_int(scan, "ocr_scanned_page_count")
    if text_page_count != len(text_pages) or ocr_page_count != len(ocr_pages):
        raise ProvenanceClearanceError(f"invalid PDF scan page count: {key}")
    partitions = (set(text_pages), set(ocr_pages), set(unscanned_pages))
    if any(
        left & right
        for index, left in enumerate(partitions)
        for right in partitions[index + 1 :]
    ) or set().union(*partitions) != set(range(1, parsed_page_count + 1)):
        raise ProvenanceClearanceError(f"invalid PDF scan page partition: {key}")
    if ocr_pages:
        raise ProvenanceClearanceError(
            f"PDF scan pypdf page-text method cannot claim OCR coverage: {key}"
        )
    complete = parsed_page_count > 0 and not unscanned_pages
    if scan.get("coverage_status") != ("complete" if complete else "incomplete"):
        raise ProvenanceClearanceError(f"invalid PDF scan coverage status: {key}")
    for field in ("diagnostics", "automated_markers"):
        values = _text_list(scan, field)
        if values != sorted(set(values)):
            raise ProvenanceClearanceError(
                f"PDF scan {field} must be sorted and unique: {key}"
            )


def _page_numbers(
    record: Mapping[str, object], field: str, *, key: tuple[str, str]
) -> list[int]:
    value = record.get(field)
    if not isinstance(value, list):
        raise ProvenanceClearanceError(f"{field} must be a list: {key}")
    result: list[int] = []
    for item in cast(list[object], value):
        if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
            raise ProvenanceClearanceError(
                f"{field} must contain positive integers: {key}"
            )
        result.append(item)
    if result != sorted(set(result)):
        raise ProvenanceClearanceError(f"{field} must be sorted and unique: {key}")
    return result


def _affirmative_public_provenance(
    source: Mapping[str, object],
    *,
    restriction: Mapping[str, object],
    visibility: Mapping[str, object],
) -> bool:
    if (
        source.get("source_provider") != "courtlistener"
        or source.get("free_or_purchased") != "free"
        or visibility.get("source_url_or_reference") != source.get("source_url")
    ):
        return False
    if not is_allowlisted_public_recap_uri(_required_text(source, "source_url")):
        return False
    evidence = frozenset(_text_set(restriction, "restriction_evidence"))
    status = restriction.get("restriction_status")
    if status == "public":
        return evidence == _PUBLIC_EVIDENCE
    return (
        status == "unknown"
        and evidence == _REST_PUBLIC_EVIDENCE
        and restriction.get("is_sealed") is None
        and restriction.get("is_private") is None
    )


def _positive_restriction(record: Mapping[str, object]) -> bool:
    status = record.get("restriction_status")
    return (
        (
            isinstance(status, str)
            and normalize_restriction_token(status) in _RESTRICTED_STATUSES
        )
        or record.get("is_sealed") is True
        or record.get("is_private") is True
        or any(
            _POSITIVE_RESTRICTION_EVIDENCE.search(normalize_restriction_token(item))
            for item in _text_list(record, "restriction_evidence")
        )
    )


def _visibility_contract_valid(record: Mapping[str, object]) -> bool:
    model_visible = record.get("model_visible")
    contains_target_outcome = record.get("contains_target_outcome")
    if not isinstance(model_visible, bool) or not isinstance(
        contains_target_outcome, bool
    ):
        return False
    pair = (model_visible, contains_target_outcome)
    return pair in {(True, False), (False, True)}


def _validate_restriction_flags(
    record: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    for field in ("is_sealed", "is_private"):
        value = record.get(field)
        if value is not None and not isinstance(value, bool):
            raise ProvenanceClearanceError(
                f"restriction {field} must be bool or null: {key}"
            )


def _validate_visibility_flags(
    record: Mapping[str, object], *, key: tuple[str, str]
) -> None:
    for field in ("model_visible", "contains_target_outcome"):
        if not isinstance(record.get(field), bool):
            raise ProvenanceClearanceError(f"visibility {field} must be bool: {key}")


def _validate_request(
    request: Mapping[str, object],
    *,
    source: Mapping[str, object],
    restriction: Mapping[str, object],
    key: tuple[str, str],
) -> None:
    if (
        request.get("schema_version") != "legalforecast.disclosure_review_request.v1"
        or request.get("required_human_decision") != "cleared_or_quarantined"
    ):
        raise ProvenanceClearanceError(f"unsupported frozen review request: {key}")
    for field in ("sha256", "byte_count", "free_or_purchased"):
        if request.get(field) != source.get(field):
            raise ProvenanceClearanceError(f"review request {field} mismatch: {key}")
    for field in ("restriction_status", "restriction_evidence"):
        if request.get(field) != restriction.get(field):
            raise ProvenanceClearanceError(f"review request {field} mismatch: {key}")


def _relevance_index(
    records: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    output: dict[tuple[str, str], Mapping[str, object]] = {}
    for case in records:
        candidate_id = _required_text(case, "candidate_id")
        raw_documents = case.get("documents")
        if not isinstance(raw_documents, list):
            raise ProvenanceClearanceError("case relevance lacks documents")
        for value in cast(list[object], raw_documents):
            if not isinstance(value, Mapping):
                raise ProvenanceClearanceError(
                    "case relevance document is not an object"
                )
            row = cast(Mapping[str, object], value)
            key = (candidate_id, _required_text(row, "source_document_id"))
            if key in output:
                raise ProvenanceClearanceError(
                    f"duplicate case relevance document: {key}"
                )
            output[key] = row
    return output


def _index(
    records: Sequence[Mapping[str, object]], label: str
) -> dict[tuple[str, str], Mapping[str, object]]:
    output: dict[tuple[str, str], Mapping[str, object]] = {}
    for row in records:
        key = _key(row)
        if key in output:
            raise ProvenanceClearanceError(f"duplicate {label}: {key}")
        output[key] = row
    return output


def _key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _required_text(record, "candidate_id"),
        _required_text(record, "source_document_id"),
    )


def _read_document(
    root: Path,
    relative: str,
    *,
    key: tuple[str, str],
    document_bytes_by_relative_path: Mapping[str, bytes] | None = None,
) -> bytes:
    try:
        resolved = safe_disclosure_document_path(root, relative)
        if document_bytes_by_relative_path is not None:
            try:
                return document_bytes_by_relative_path[relative]
            except KeyError as exc:
                raise ProvenanceClearanceError(
                    f"authenticated document snapshot lacks: {key}"
                ) from exc
        return read_unique_regular_file(resolved)
    except (DisclosureClearanceError, ReviewBundleError) as exc:
        raise ProvenanceClearanceError(f"unsafe document path: {key}") from exc


def _require_records_match(
    records: Sequence[Mapping[str, object]], payload: bytes, label: str
) -> None:
    try:
        parsed = [
            json.loads(line)
            for line in payload.decode("utf-8").splitlines()
            if line.strip()
        ]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceClearanceError(f"{label} bytes are malformed") from exc
    if parsed != [dict(row) for row in records]:
        raise ProvenanceClearanceError(f"{label} records differ from exact bytes")


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ProvenanceClearanceError(f"{field} must be a non-empty string")
    return value


def _validate_relative_local_path(value: str, *, key: tuple[str, str]) -> None:
    raw_parts = value.split("/")
    if "\\" in value or any(part in {"", ".", ".."} for part in raw_parts):
        raise ProvenanceClearanceError(
            f"local_path must be a safe relative POSIX path: {key}"
        )


def _nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ProvenanceClearanceError(f"{label} must be a non-empty string")
    return value


def _digest(record: Mapping[str, object], field: str) -> str:
    return _strict_digest(_required_text(record, field), field)


def _strict_digest(value: str, label: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise ProvenanceClearanceError(f"{label} must be a lowercase SHA-256")
    return value


def _nonnegative_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProvenanceClearanceError(f"{field} must be a non-negative integer")
    return value


def _text_set(record: Mapping[str, object], field: str) -> tuple[str, ...]:
    return tuple(sorted(set(_text_list(record, field))))


def _text_list(record: Mapping[str, object], field: str) -> list[str]:
    value = record.get(field)
    if not isinstance(value, list):
        raise ProvenanceClearanceError(f"{field} must be a list")
    return [_nonempty(item, field) for item in cast(list[object], value)]


__all__ = [
    "PLAN_SCHEMA_VERSION",
    "PLAN_SCHEMA_VERSION_V3",
    "WORKSHEET_SCHEMA_VERSION",
    "WORKSHEET_SCHEMA_VERSION_V3",
    "ProvenanceClearanceError",
    "build_exception_inspection_map",
    "build_provenance_clearance_plan",
    "build_provenance_clearance_plan_v3",
    "build_provenance_clearance_records",
    "build_provider_free_quarantine_records_v3",
    "canonical_json_bytes",
    "exception_review_worksheet",
    "exception_review_worksheet_v3",
    "validate_exception_review_worksheet",
    "validate_exception_review_worksheet_v3",
]
