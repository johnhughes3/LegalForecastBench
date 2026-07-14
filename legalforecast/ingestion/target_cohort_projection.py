"""Project a resolved acquisition pool into an exact post-clearance cohort."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.ingestion.core_document_filter import (
    CoreDocumentFilterResult,
    filter_core_documents,
)
from legalforecast.ingestion.missing_core_budget import (
    MissingCoreBudgetPlan,
    plan_missing_core_document_budget,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionStage,
)

JsonRecord = dict[str, Any]
_PUBLIC_RESTRICTION_STATUSES = frozenset({"public", "redacted"})
_RESTRICTED_STATUSES = frozenset({"private", "restricted", "sealed", "under_seal"})


class TargetCohortProjectionError(ValueError):
    """Raised when an exact cohort cannot be proven from frozen inputs."""


@dataclass(frozen=True, slots=True)
class TargetCohortProjection:
    """Exact downstream artifacts for one post-clearance frontier."""

    selected_candidate_ids: tuple[str, ...]
    selections: tuple[JsonRecord, ...]
    case_relevance: tuple[JsonRecord, ...]
    download_manifest: tuple[JsonRecord, ...]
    clearance_records: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    core_filter_results: tuple[CoreDocumentFilterResult, ...]
    budget_plan: MissingCoreBudgetPlan
    exclusions: tuple[JsonRecord, ...]
    summary: JsonRecord


def project_target_cohort(
    *,
    selections: Sequence[Mapping[str, Any]],
    case_relevance: Sequence[Mapping[str, Any]],
    download_manifest: Sequence[Mapping[str, Any]],
    clearance_records: Sequence[Mapping[str, Any]],
    target_case_count: int,
    cost_per_document_usd: str,
    max_projected_budget_usd: str,
    max_missing_core_documents_per_case: int,
) -> TargetCohortProjection:
    """Filter quarantined cases, rerank, and emit an exact cohort boundary."""

    if target_case_count < 1:
        raise TargetCohortProjectionError("target_case_count must be positive")

    selection_index = _unique_candidate_index(selections, label="selection")
    relevance_index = _unique_candidate_index(
        case_relevance,
        label="case relevance",
    )
    if set(relevance_index) != set(selection_index):
        raise TargetCohortProjectionError(
            "selection and case relevance candidate sets must match exactly"
        )
    for candidate_id, selection in selection_index.items():
        if selection.get("selected") is not True:
            raise TargetCohortProjectionError(
                f"resolved-pool selection is not selected: {candidate_id}"
            )

    manifest_index = _unique_document_index(download_manifest, label="manifest")
    clearance_index = _unique_document_index(
        clearance_records,
        label="clearance",
    )
    pool_ids = set(selection_index)
    for candidate_id, _ in (*manifest_index, *clearance_index):
        if candidate_id not in pool_ids:
            raise TargetCohortProjectionError(
                f"document record is outside resolved pool: {candidate_id}"
            )
    if set(manifest_index) != set(clearance_index):
        raise TargetCohortProjectionError(
            "manifest document lacks exactly one clearance row or clearance "
            "contains an unmanifested document"
        )

    manifest_by_candidate: dict[str, list[tuple[str, str]]] = {
        candidate_id: [] for candidate_id in selection_index
    }
    quarantined: dict[str, list[str]] = {}
    for key, manifest in manifest_index.items():
        candidate_id, source_document_id = key
        manifest_by_candidate[candidate_id].append(key)
        relevance_documents = _relevance_document_index(relevance_index[candidate_id])
        if source_document_id not in relevance_documents:
            raise TargetCohortProjectionError(
                "manifest document is absent from case relevance: "
                f"{candidate_id}/{source_document_id}"
            )
        clearance = clearance_index[key]
        _validate_clearance_binding(manifest, clearance, key=key)
        if clearance.get("status") != "cleared":
            quarantined.setdefault(candidate_id, []).append(source_document_id)

    empty_candidates = sorted(
        candidate_id for candidate_id, keys in manifest_by_candidate.items() if not keys
    )
    if empty_candidates:
        raise TargetCohortProjectionError(
            "resolved candidates lack acquired documents: "
            + ", ".join(empty_candidates)
        )

    eligible_relevance = tuple(
        relevance_index[candidate_id]
        for candidate_id in sorted(selection_index)
        if candidate_id not in quarantined
    )
    if len(eligible_relevance) < target_case_count:
        raise TargetCohortProjectionError(
            f"only {len(eligible_relevance)} post-clearance candidates remain; "
            f"{target_case_count} required"
        )

    filter_results = filter_core_documents(eligible_relevance)
    budget_plan = plan_missing_core_document_budget(
        filter_results,
        dry_run=False,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
        cost_per_document_usd=cost_per_document_usd,
        max_projected_budget_usd=max_projected_budget_usd,
        truncate_to_budget=True,
        target_case_count=target_case_count,
    )
    if not budget_plan.target_case_count_met or len(budget_plan.case_plans) != (
        target_case_count
    ):
        raise TargetCohortProjectionError(
            "post-clearance purchase frontier cannot meet the exact target under "
            "the configured cap"
        )

    selected_ids = tuple(plan.candidate_id for plan in budget_plan.case_plans)
    selected_set = set(selected_ids)
    exact_selections = tuple(
        selection_index[candidate_id] for candidate_id in selected_ids
    )
    exact_relevance = tuple(
        relevance_index[candidate_id] for candidate_id in selected_ids
    )
    exact_manifest = tuple(
        manifest_index[key]
        for candidate_id in selected_ids
        for key in sorted(manifest_by_candidate[candidate_id])
    )
    exact_clearance = tuple(
        clearance_index[_document_key(row)] for row in exact_manifest
    )
    filter_result_index = {result.candidate_id: result for result in filter_results}
    exact_filter_results = tuple(
        filter_result_index[candidate_id] for candidate_id in selected_ids
    )
    exact_restrictions = restriction_evidence_from_case_relevance(exact_relevance)

    exclusion_records = _projection_exclusions(
        selection_index=selection_index,
        quarantined=quarantined,
        budget_plan=budget_plan,
        selected_ids=selected_set,
    )
    expected_excluded = pool_ids - selected_set
    actual_excluded = {_required_str(row, "candidate_id") for row in exclusion_records}
    if actual_excluded != expected_excluded:
        raise TargetCohortProjectionError(
            "projection exclusions do not reconcile the resolved pool"
        )

    budget_record = budget_plan.to_record()
    summary: JsonRecord = {
        "schema_version": "legalforecast.target_cohort_projection.v1",
        "target_case_count": target_case_count,
        "resolved_pool_case_count": len(selection_index),
        "post_clearance_case_count": len(eligible_relevance),
        "quarantined_case_count": len(quarantined),
        "selected_case_count": len(selected_ids),
        "excluded_case_count": len(exclusion_records),
        "selected_candidate_ids_sha256": _canonical_sha256(list(selected_ids)),
        "budget_plan_sha256": _canonical_sha256(budget_record),
        "total_missing_core_documents": budget_plan.total_missing_core_documents,
        "total_estimated_cost_usd": budget_plan.total_estimated_cost_usd,
        "max_projected_budget_usd": budget_plan.max_projected_budget_usd,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    summary["projection_sha256"] = _canonical_sha256(
        {
            "summary": summary,
            "selections": exact_selections,
            "case_relevance": exact_relevance,
            "download_manifest": exact_manifest,
            "clearance_records": exact_clearance,
            "restriction_evidence": exact_restrictions,
            "core_filter_results": [row.to_record() for row in exact_filter_results],
            "budget_plan": budget_record,
            "exclusions": exclusion_records,
        }
    )
    return TargetCohortProjection(
        selected_candidate_ids=selected_ids,
        selections=exact_selections,
        case_relevance=exact_relevance,
        download_manifest=exact_manifest,
        clearance_records=exact_clearance,
        restriction_evidence=exact_restrictions,
        core_filter_results=exact_filter_results,
        budget_plan=budget_plan,
        exclusions=exclusion_records,
        summary=summary,
    )


def _unique_candidate_index(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[str, JsonRecord]:
    output: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in output:
            raise TargetCohortProjectionError(
                f"duplicate {label} candidate: {candidate_id}"
            )
        output[candidate_id] = dict(record)
    if not output:
        raise TargetCohortProjectionError(f"{label} input is empty")
    return output


def _unique_document_index(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[tuple[str, str], JsonRecord]:
    output: dict[tuple[str, str], JsonRecord] = {}
    for record in records:
        key = _document_key(record)
        if key in output:
            raise TargetCohortProjectionError(f"duplicate {label} document: {key}")
        output[key] = dict(record)
    return output


def _document_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (
        _required_str(record, "candidate_id"),
        _required_str(record, "source_document_id"),
    )


def _relevance_document_index(record: Mapping[str, Any]) -> dict[str, JsonRecord]:
    raw_documents = record.get("documents")
    if not isinstance(raw_documents, Sequence) or isinstance(
        raw_documents, (str, bytes)
    ):
        raise TargetCohortProjectionError("case relevance requires documents")
    output: dict[str, JsonRecord] = {}
    for raw in cast(Sequence[object], raw_documents):
        if not isinstance(raw, Mapping):
            raise TargetCohortProjectionError(
                "case relevance document must be an object"
            )
        document = cast(Mapping[str, Any], raw)
        document_id = _required_str(document, "source_document_id")
        if document_id in output:
            raise TargetCohortProjectionError(
                f"duplicate case relevance document: {document_id}"
            )
        output[document_id] = dict(document)
    return output


def _validate_clearance_binding(
    manifest: Mapping[str, Any],
    clearance: Mapping[str, Any],
    *,
    key: tuple[str, str],
) -> None:
    for field in ("sha256", "byte_count", "free_or_purchased"):
        if clearance.get(field) != manifest.get(field):
            raise TargetCohortProjectionError(
                f"clearance {field} does not match manifest: {key}"
            )
    status = clearance.get("status")
    if status not in {"cleared", "quarantined"}:
        raise TargetCohortProjectionError(f"invalid clearance status: {key}")
    if status != "cleared":
        return
    if clearance.get("restriction_status") not in _PUBLIC_RESTRICTION_STATUSES:
        raise TargetCohortProjectionError(
            f"cleared document lacks public restriction status: {key}"
        )
    for field in (
        "reviewer_id",
        "controlled_store_provenance",
        "reviewed_at",
    ):
        _required_str(clearance, field)
    evidence = clearance.get("restriction_evidence")
    if (
        not isinstance(evidence, Sequence)
        or isinstance(evidence, (str, bytes))
        or not evidence
    ):
        raise TargetCohortProjectionError(
            f"cleared document lacks restriction evidence: {key}"
        )


def restriction_evidence_from_case_relevance(
    case_relevance: Sequence[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Flatten docket-derived restriction evidence for clearance inputs."""

    output: list[JsonRecord] = []
    for case in case_relevance:
        candidate_id = _required_str(case, "candidate_id")
        for source_document_id, document in sorted(
            _relevance_document_index(case).items()
        ):
            status = document.get("redaction_or_seal_status")
            evidence = document.get("restriction_evidence")
            if not isinstance(status, str) or not status:
                raise TargetCohortProjectionError(
                    "case relevance document lacks restriction status: "
                    f"{candidate_id}/{source_document_id}"
                )
            if (
                status in _RESTRICTED_STATUSES
                or document.get("is_sealed") is True
                or document.get("is_private") is True
            ):
                raise TargetCohortProjectionError(
                    "case relevance document is sealed/private/restricted: "
                    f"{candidate_id}/{source_document_id}"
                )
            if (
                not isinstance(evidence, Sequence)
                or isinstance(evidence, (str, bytes))
                or not evidence
            ):
                raise TargetCohortProjectionError(
                    "case relevance document lacks restriction evidence: "
                    f"{candidate_id}/{source_document_id}"
                )
            evidence_items = tuple(cast(Sequence[object], evidence))
            if not all(isinstance(item, str) and item for item in evidence_items):
                raise TargetCohortProjectionError(
                    "case relevance document lacks restriction evidence: "
                    f"{candidate_id}/{source_document_id}"
                )
            output.append(
                {
                    "candidate_id": candidate_id,
                    "source_document_id": source_document_id,
                    "restriction_status": status,
                    "restriction_evidence": list(cast(tuple[str, ...], evidence_items)),
                    "is_sealed": document.get("is_sealed"),
                    "is_private": document.get("is_private"),
                }
            )
    return tuple(output)


def _projection_exclusions(
    *,
    selection_index: Mapping[str, Mapping[str, Any]],
    quarantined: Mapping[str, Sequence[str]],
    budget_plan: MissingCoreBudgetPlan,
    selected_ids: set[str],
) -> tuple[JsonRecord, ...]:
    budget_excluded = {
        plan.candidate_id: plan for plan in budget_plan.excluded_case_plans
    }
    omitted = set(budget_plan.omitted_candidate_ids)
    output: list[JsonRecord] = []
    for candidate_id in sorted(set(selection_index) - selected_ids):
        selection = selection_index[candidate_id]
        if candidate_id in quarantined:
            reason = "disclosure_clearance_quarantined"
            document_ids = tuple(sorted(quarantined[candidate_id]))
            notes = "One or more acquired documents failed disclosure clearance."
        elif candidate_id in budget_excluded:
            case_plan = budget_excluded[candidate_id]
            reason = case_plan.exclusion_reasons[0]
            document_ids = case_plan.purchase_document_ids
            notes = "Candidate failed the post-clearance core-document budget gate."
        elif candidate_id in omitted:
            reason = "target_cohort_frontier_omitted"
            document_ids = ()
            notes = (
                "Candidate was outside the deterministic cheapest exact-cohort prefix."
            )
        else:
            raise TargetCohortProjectionError(
                f"unclassified target-cohort exclusion: {candidate_id}"
            )
        output.append(
            ExclusionLedgerEntry(
                candidate_id=candidate_id,
                case_id=_optional_str(selection, "case_id") or candidate_id,
                court=_optional_str(selection, "court"),
                stage=ExclusionStage.EXTRACTION,
                reason=reason,
                source_entry_ids=(),
                source_document_ids=document_ids,
                notes=notes,
            ).to_record()
        )
    return tuple(output)


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise TargetCohortProjectionError(f"{field} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, Any], field: str) -> str | None:
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TargetCohortProjectionError(f"{field} must be null or non-empty")
    return value


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()
