"""Provenance-first disclosure routing with hash-bound human exceptions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from legalforecast.ingestion.disclosure_clearance import (
    ClearanceRecord,
    DisclosureClearanceError,
    safe_disclosure_document_path,
    scan_disclosure_markers,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)

PLAN_SCHEMA_VERSION = "legalforecast.disclosure_provenance_routing_plan.v1"
WORKSHEET_SCHEMA_VERSION = "legalforecast.disclosure_exception_worksheet.v1"

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


class ProvenanceClearanceError(ValueError):
    """Raised when provenance routing is incomplete, contradictory, or changed."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize one artifact value in its canonical representation."""

    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


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
    marker_scanner: Callable[[bytes], Sequence[str]] = scan_disclosure_markers,
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
        markers = tuple(
            sorted(
                {_nonempty(item, "automated marker") for item in marker_scanner(data)}
            )
        )
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
                "restriction_status": _required_text(restriction, "restriction_status"),
                "restriction_evidence": list(
                    _text_set(restriction, "restriction_evidence")
                ),
                "is_sealed": restriction.get("is_sealed"),
                "is_private": restriction.get("is_private"),
                "model_visible": visibility.get("model_visible"),
                "contains_target_outcome": visibility.get("contains_target_outcome"),
                "automated_markers": list(markers),
                "route": "auto_clear" if auto_clear else "john_exception_review",
                "route_reasons": route_reasons,
                "human_clearance_permitted": not (
                    positive_restriction or not visibility_valid
                ),
            }
        )
    auto_count = sum(row["route"] == "auto_clear" for row in documents)
    return {
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


def build_exception_inspection_map(
    plan: Mapping[str, object],
    *,
    document_root: Path,
    document_bytes_by_relative_path: Mapping[str, bytes] | None = None,
) -> bytes:
    """Map only exception-routed commitments to contained local inspection bytes."""

    rows: list[dict[str, object]] = []
    for document in _plan_documents(plan):
        if document.get("route") != "john_exception_review":
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
        if row.get("status") not in {"cleared", "quarantined"}:
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
        documents.append(row)
    if [_key(row) for row in documents] != sorted(seen):
        raise ProvenanceClearanceError(
            "routing plan documents are not canonically ordered"
        )
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
    parsed = urlsplit(_required_text(source, "source_url"))
    if (
        parsed.scheme != "https"
        or parsed.hostname != "storage.courtlistener.com"
        or not parsed.path.startswith("/recap/")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
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
            and status.casefold().replace("-", "_") in _RESTRICTED_STATUSES
        )
        or record.get("is_sealed") is True
        or record.get("is_private") is True
        or any(
            _POSITIVE_RESTRICTION_EVIDENCE.search(item.casefold().replace("-", "_"))
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
    "WORKSHEET_SCHEMA_VERSION",
    "ProvenanceClearanceError",
    "build_exception_inspection_map",
    "build_provenance_clearance_plan",
    "build_provenance_clearance_records",
    "canonical_json_bytes",
    "exception_review_worksheet",
]
