# pyright: reportPrivateUsage=false
"""Versioned predecessor coverage that omits authenticated paid-recovery gaps.

``legalforecast.exact100_successor_predecessor_coverage.v1`` (the frozen v1
successor-replacement validator) requires every selected document on the
download manifest, disclosure clearance, and restriction evidence. This v2
contract keeps those identities on selection and case relevance, but treats
documents marked ``requires_paid_recovery is True`` and
``availability_status == "unavailable"`` as pre-recovery gaps absent from
those three surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from legalforecast.ingestion.exact100_successor_replacement import (
    Exact100SuccessorReplacementError,
    _candidate_id,
    _candidate_rows,
    _document_ids_from_selection,
    _has_exact_document_coverage,
    _require_exact_candidate_coverage,
    _required_text,
)


def require_predecessor_artifact_coverage_v2(
    selection: Sequence[Mapping[str, Any]],
    *,
    case_relevance: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    disclosure_clearance: Sequence[Mapping[str, Any]],
    restriction_evidence: Sequence[Mapping[str, Any]],
    core_filter_results: Sequence[Mapping[str, Any]],
) -> None:
    """Require v2 coverage: acquired documents only on pre-recovery surfaces."""

    selected_by_candidate = {_candidate_id(row): row for row in selection}
    selected_ids = set(selected_by_candidate)
    if len(selected_by_candidate) != len(selection):
        raise Exact100SuccessorReplacementError(
            "predecessor selection is not exactly unique candidates"
        )
    _require_exact_candidate_coverage(
        case_relevance, selected_ids, label="case relevance"
    )
    _require_exact_candidate_coverage(
        core_filter_results, selected_ids, label="core filter results"
    )
    for label, records in (
        ("download manifest", download_manifest),
        ("disclosure clearance", disclosure_clearance),
        ("restriction evidence", restriction_evidence),
    ):
        if not {_candidate_id(row) for row in records} <= selected_ids:
            raise Exact100SuccessorReplacementError(
                f"predecessor {label} includes an unselected candidate"
            )
    for candidate_id, selection_row in selected_by_candidate.items():
        document_ids = _document_ids_from_selection(selection_row, "selection")
        acquired_ids = document_ids - _paid_recovery_gap_ids(selection_row, "selection")
        relevance_rows = _candidate_rows(case_relevance, candidate_id)
        if (
            _document_ids_from_selection(relevance_rows[0], "case relevance")
            != document_ids
        ):
            raise Exact100SuccessorReplacementError(
                "predecessor case relevance document coverage is incomplete"
            )
        for label, records in (
            ("download manifest", download_manifest),
            ("disclosure clearance", disclosure_clearance),
            ("restriction evidence", restriction_evidence),
        ):
            if not _has_exact_document_coverage(
                _candidate_rows(records, candidate_id), acquired_ids
            ):
                raise Exact100SuccessorReplacementError(
                    f"predecessor {label} document coverage is incomplete"
                )


def _paid_recovery_gap_ids(record: Mapping[str, Any], label: str) -> set[str]:
    """Return selected document ids that are authenticated unpaid recovery gaps."""

    documents = record.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise Exact100SuccessorReplacementError(
            f"predecessor {label} documents are invalid"
        )
    gaps: set[str] = set()
    for document in cast(Sequence[object], documents):
        if not isinstance(document, Mapping):
            raise Exact100SuccessorReplacementError(
                f"predecessor {label} documents are invalid"
            )
        typed = cast(Mapping[str, object], document)
        requires_paid = typed.get("requires_paid_recovery")
        availability = typed.get("availability_status")
        is_gap = requires_paid is True and availability == "unavailable"
        if (requires_paid is True or availability == "unavailable") is not is_gap:
            raise Exact100SuccessorReplacementError(
                "predecessor selection has inconsistent paid-recovery gap markers"
            )
        if is_gap:
            gaps.add(_required_text(typed, "source_document_id"))
    return gaps
