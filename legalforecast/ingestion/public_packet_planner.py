"""Plan free public document downloads for candidate MTD packets."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_mix_optimizer import (
    CaseMixCandidate,
    CaseMixSelectionResult,
    select_exact_case_mix,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
    is_substantive_mtd_opposition_entry,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadRequest,
)
from legalforecast.ingestion.missing_core_budget import DEFAULT_PURCHASE_COST_USD
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    select_operative_complaint_document,
    select_operative_complaint_entry,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.restricted_material import restricted_material_markers

_OPTIONAL_BRIEF_ROLES = frozenset({CourtListenerEntryRole.REPLY})
_CASE_MIX_DIMENSIONS = (
    "court",
    "nos_macro_category",
    "related_family_id",
    "mdl_family_id",
)


@dataclass(frozen=True, slots=True)
class PublicPacketDocumentPlan:
    candidate_id: str
    source_document_id: str
    docket_entry_number: int | None
    document_role: DocumentRole
    source_url: str
    description: str
    model_visible: bool
    contains_target_outcome: bool

    def to_download_request(self) -> FreeDocumentDownloadRequest:
        return FreeDocumentDownloadRequest(
            candidate_id=self.candidate_id,
            source_provider="courtlistener",
            source_document_id=self.source_document_id,
            docket_entry_number=self.docket_entry_number,
            document_role=self.document_role,
            source_url=self.source_url,
            file_extension="pdf",
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "source_url": self.source_url,
            "description": self.description,
            "model_visible": self.model_visible,
            "contains_target_outcome": self.contains_target_outcome,
        }


@dataclass(frozen=True, slots=True)
class PublicPacketCandidatePlan:
    candidate_id: str
    case_id: str
    case_name: str | None
    court: str | None
    docket_number: str | None
    decision_date: str | None
    nature_of_suit: str | None
    nos_macro_category: str | None
    related_family_id: str | None
    mdl_family_id: str | None
    source_url: str | None
    selected: bool
    exclusion_reasons: tuple[str, ...]
    paid_recovery_required: bool
    paid_gap_reasons: tuple[str, ...]
    target_motion_entry_numbers: tuple[int, ...]
    decision_entry_numbers: tuple[int, ...]
    documents: tuple[PublicPacketDocumentPlan, ...]
    required_document_count: int = 0
    free_required_document_count: int = 0
    missing_required_document_count: int = 0
    projected_paid_cost_usd: str = "0.00"
    cost_rank: int | None = None
    case_type_stratum: str = "district_civil"

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "court": self.court,
            "docket_number": self.docket_number,
            "decision_date": self.decision_date,
            "nature_of_suit": self.nature_of_suit,
            "nos_macro_category": self.nos_macro_category,
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
            "source_url": self.source_url,
            "selected": self.selected,
            "exclusion_reasons": list(self.exclusion_reasons),
            "paid_recovery_required": self.paid_recovery_required,
            "paid_gap_reasons": list(self.paid_gap_reasons),
            "planning_status": self.planning_status,
            "target_motion_entry_numbers": list(self.target_motion_entry_numbers),
            "decision_entry_numbers": list(self.decision_entry_numbers),
            "documents": [document.to_record() for document in self.documents],
            "required_document_count": self.required_document_count,
            "free_required_document_count": self.free_required_document_count,
            "missing_required_document_count": self.missing_required_document_count,
            "projected_paid_cost_usd": self.projected_paid_cost_usd,
            "cost_rank": self.cost_rank,
            "case_type_stratum": self.case_type_stratum,
        }

    @property
    def planning_status(self) -> str:
        if self.selected:
            return "selected_free"
        if self.paid_recovery_required:
            return "paid_recovery_required"
        return "excluded"

    @property
    def final_excluded(self) -> bool:
        return not self.selected and not self.paid_recovery_required


@dataclass(frozen=True, slots=True)
class PublicPacketDownloadPlan:
    target_clean_cases: int
    allow_inferred_target_mtd: bool
    screened_case_count: int
    selected_case_count: int
    download_request_count: int
    candidate_plans: tuple[PublicPacketCandidatePlan, ...]
    max_case_mix_share: Decimal | None = None
    case_mix_max_per_bucket: int | None = None
    selection_optimizer: CaseMixSelectionResult | None = None

    @property
    def selected_cases(self) -> tuple[PublicPacketCandidatePlan, ...]:
        return tuple(plan for plan in self.candidate_plans if plan.selected)

    @property
    def paid_gap_cases(self) -> tuple[PublicPacketCandidatePlan, ...]:
        return tuple(
            plan for plan in self.candidate_plans if plan.paid_recovery_required
        )

    @property
    def final_exclusions(self) -> tuple[PublicPacketCandidatePlan, ...]:
        return tuple(plan for plan in self.candidate_plans if plan.final_excluded)

    @property
    def planned_cases(self) -> tuple[PublicPacketCandidatePlan, ...]:
        return tuple(
            plan
            for plan in self.candidate_plans
            if plan.selected or plan.paid_recovery_required
        )

    @property
    def download_requests(self) -> tuple[FreeDocumentDownloadRequest, ...]:
        return tuple(
            document.to_download_request()
            for plan in self.planned_cases
            for document in plan.documents
        )

    def summary_record(self) -> dict[str, Any]:
        planned_cases = self.planned_cases
        return {
            "target_clean_cases": self.target_clean_cases,
            "allow_inferred_target_mtd": self.allow_inferred_target_mtd,
            "screened_case_count": self.screened_case_count,
            "selected_case_count": self.selected_case_count,
            "paid_gap_case_count": len(self.paid_gap_cases),
            "planned_case_count": len(self.planned_cases),
            "final_exclusion_count": len(self.final_exclusions),
            "download_request_count": self.download_request_count,
            "selection_protocol": "exact_case_mix_cp_sat_v1",
            "optimizer_status": (
                None
                if self.selection_optimizer is None
                else self.selection_optimizer.audit.phases[-1].status
            ),
            "max_case_mix_share": (
                None
                if self.max_case_mix_share is None
                else str(self.max_case_mix_share)
            ),
            "case_mix_max_per_bucket": self.case_mix_max_per_bucket,
            "selection_optimizer": (
                None
                if self.selection_optimizer is None
                else _optimizer_summary_record(self.selection_optimizer)
            ),
            "required_document_count": sum(
                plan.required_document_count for plan in planned_cases
            ),
            "free_required_document_count": sum(
                plan.free_required_document_count for plan in planned_cases
            ),
            "missing_required_document_count": sum(
                plan.missing_required_document_count for plan in planned_cases
            ),
            "projected_paid_cost_usd": _money(
                sum(
                    (Decimal(plan.projected_paid_cost_usd) for plan in planned_cases),
                    start=Decimal("0"),
                )
            ),
            "shortfall": max(0, self.target_clean_cases - self.selected_case_count),
            "acquisition_candidate_shortfall": max(
                0, self.target_clean_cases - len(self.planned_cases)
            ),
        }


def plan_public_packet_downloads(
    screened_case_records: Iterable[Mapping[str, Any]],
    *,
    raw_html_dir: str | Path | None = None,
    raw_html_paths_by_candidate: Mapping[str, str | Path] | None = None,
    target_clean_cases: int = 25,
    allow_inferred_target_mtd: bool = False,
    use_embedded_entries: bool = False,
    cost_per_missing_document_usd: Decimal | str = DEFAULT_PURCHASE_COST_USD,
    max_case_mix_share: Decimal | str | float | None = None,
) -> PublicPacketDownloadPlan:
    """Select public/free packet candidates and emit document download requests."""

    if target_clean_cases <= 0:
        raise ValueError("target_clean_cases must be positive")
    if raw_html_dir is not None and raw_html_paths_by_candidate is not None:
        raise ValueError(
            "raw_html_dir and raw_html_paths_by_candidate are mutually exclusive"
        )
    if (
        raw_html_dir is None
        and raw_html_paths_by_candidate is None
        and not use_embedded_entries
    ):
        raise ValueError(
            "raw_html_dir or raw_html_paths_by_candidate is required unless "
            "use_embedded_entries=True"
        )
    unit_cost = _money_decimal(
        cost_per_missing_document_usd,
        "cost_per_missing_document_usd",
    )
    normalized_case_mix_share = _case_mix_share(max_case_mix_share)
    max_per_bucket = _case_mix_bucket_cap(
        target_clean_cases=target_clean_cases,
        max_case_mix_share=normalized_case_mix_share,
    )
    html_root = Path(raw_html_dir) if raw_html_dir is not None else None
    html_paths = (
        None
        if raw_html_paths_by_candidate is None
        else {
            candidate_id: Path(path)
            for candidate_id, path in raw_html_paths_by_candidate.items()
        }
    )
    evaluated_plans: list[PublicPacketCandidatePlan] = []
    for record in screened_case_records:
        plan = _candidate_plan(
            record,
            raw_html_dir=html_root,
            raw_html_paths_by_candidate=html_paths,
            allow_inferred_target_mtd=allow_inferred_target_mtd,
            use_embedded_entries=use_embedded_entries,
            cost_per_missing_document=unit_cost,
        )
        evaluated_plans.append(plan)
    candidate_plans, selection_optimizer = _select_lowest_cost_candidates(
        evaluated_plans,
        target_clean_cases=target_clean_cases,
        max_per_bucket=max_per_bucket,
    )
    selected_cases = tuple(plan for plan in candidate_plans if plan.selected)
    request_count = sum(
        len(plan.documents)
        for plan in candidate_plans
        if plan.selected or plan.paid_recovery_required
    )
    return PublicPacketDownloadPlan(
        target_clean_cases=target_clean_cases,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
        screened_case_count=len(candidate_plans),
        selected_case_count=len(selected_cases),
        download_request_count=request_count,
        candidate_plans=tuple(candidate_plans),
        max_case_mix_share=normalized_case_mix_share,
        case_mix_max_per_bucket=max_per_bucket,
        selection_optimizer=selection_optimizer,
    )


def _candidate_plan(
    record: Mapping[str, Any],
    *,
    raw_html_dir: Path | None,
    raw_html_paths_by_candidate: Mapping[str, Path] | None,
    allow_inferred_target_mtd: bool,
    use_embedded_entries: bool,
    cost_per_missing_document: Decimal,
) -> PublicPacketCandidatePlan:
    candidate = _mapping(record, "candidate")
    metadata = _mapping(candidate, "metadata")
    candidate_id = _required_str(candidate, "docket_id", "candidate_key")
    html_path = (
        raw_html_dir / f"{candidate_id}.html"
        if raw_html_dir is not None
        else (
            raw_html_paths_by_candidate.get(candidate_id)
            if raw_html_paths_by_candidate is not None
            else None
        )
    )
    target_entries = _entry_number_tuple(
        _mapping(record, "ai").get("target_motion_entry_numbers")
    )
    decision_entries = _entry_number_tuple(
        _mapping(record, "ai").get("decision_entry_numbers")
    )
    source_url = _optional_str(candidate, "url")
    case_mix_metadata = _case_mix_metadata(record, candidate, metadata)
    if len(target_entries) != 1:
        return _excluded_plan(
            candidate_id,
            metadata,
            decision_date=None,
            case_mix_metadata=case_mix_metadata,
            source_url=source_url,
            target_entries=target_entries,
            decision_entries=decision_entries,
            reason="selected_target_motion_count_not_one",
        )
    decision_date, decision_date_reason = _first_written_disposition_date(
        record,
        metadata=metadata,
    )
    if decision_date_reason is not None:
        return _excluded_plan(
            candidate_id,
            metadata,
            decision_date=decision_date,
            case_mix_metadata=case_mix_metadata,
            source_url=source_url,
            target_entries=target_entries,
            decision_entries=decision_entries,
            reason=decision_date_reason,
        )
    candidate_restrictions = restricted_material_markers(
        records=(record, candidate, metadata)
    )
    if candidate_restrictions:
        return _excluded_plan(
            candidate_id,
            metadata,
            decision_date=decision_date,
            case_mix_metadata=case_mix_metadata,
            source_url=source_url,
            target_entries=target_entries,
            decision_entries=decision_entries,
            reason=_restricted_material_reason("candidate", candidate_restrictions),
        )
    page: CourtListenerWebDocketPage | None = None
    if html_path is not None and html_path.exists():
        page = parse_courtlistener_docket_html(
            html_path.read_text(encoding="utf-8"),
            source_url=source_url,
            docket_id=candidate_id,
        )
    elif use_embedded_entries:
        page = _page_from_embedded_selected_entries(
            record,
            candidate_id=candidate_id,
            source_url=source_url,
        )
    if page is None:
        reason = (
            "embedded_entries_missing" if use_embedded_entries else "raw_html_missing"
        )
        return _excluded_plan(
            candidate_id,
            metadata,
            decision_date=decision_date,
            case_mix_metadata=case_mix_metadata,
            source_url=source_url,
            target_entries=target_entries,
            decision_entries=decision_entries,
            reason=reason,
        )
    core_restrictions = _core_packet_restriction_reasons(
        page,
        target_entries=target_entries,
        decision_entries=decision_entries,
    )
    if core_restrictions:
        return _excluded_plan(
            candidate_id,
            metadata,
            decision_date=decision_date,
            case_mix_metadata=case_mix_metadata,
            source_url=source_url,
            target_entries=target_entries,
            decision_entries=decision_entries,
            reason=";".join(core_restrictions),
        )
    documents, reasons, required_count, free_required_count = _documents_for_candidate(
        candidate_id,
        page=page,
        target_entries=target_entries,
        decision_entries=decision_entries,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
    )
    missing_required_count = required_count - free_required_count
    return PublicPacketCandidatePlan(
        candidate_id=candidate_id,
        case_id=_optional_str(metadata, "case_id") or candidate_id,
        case_name=_optional_str(metadata, "case_name"),
        court=_optional_str(metadata, "court"),
        docket_number=_optional_str(metadata, "docket_number"),
        decision_date=decision_date,
        nature_of_suit=case_mix_metadata["nature_of_suit"],
        nos_macro_category=case_mix_metadata["nos_macro_category"],
        related_family_id=case_mix_metadata["related_family_id"],
        mdl_family_id=case_mix_metadata["mdl_family_id"],
        case_type_stratum=case_mix_metadata["case_type_stratum"] or "district_civil",
        source_url=source_url,
        selected=not reasons,
        exclusion_reasons=(),
        paid_recovery_required=bool(reasons),
        paid_gap_reasons=reasons,
        target_motion_entry_numbers=target_entries,
        decision_entry_numbers=decision_entries,
        documents=documents,
        required_document_count=required_count,
        free_required_document_count=free_required_count,
        missing_required_document_count=missing_required_count,
        projected_paid_cost_usd=_money(
            cost_per_missing_document * missing_required_count
        ),
    )


def _documents_for_candidate(
    candidate_id: str,
    *,
    page: CourtListenerWebDocketPage,
    target_entries: tuple[int, ...],
    decision_entries: tuple[int, ...],
    allow_inferred_target_mtd: bool,
) -> tuple[tuple[PublicPacketDocumentPlan, ...], tuple[str, ...], int, int]:
    decision_floor = min(decision_entries) if decision_entries else _max_entry(page)
    complaint_floor = min(target_entries) if target_entries else decision_floor
    complaint = _operative_complaint_entry(page, before_entry=complaint_floor)
    target_mtd_entries = _target_mtd_entries(
        page,
        target_entries=target_entries,
        decision_floor=decision_floor,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
    )
    decision_entry_plans = _decision_entries(page, decision_entries=decision_entries)
    opposition_entries = _required_opposition_entries(
        page,
        target_entries=target_entries,
        before_entry=decision_floor,
    )
    reasons: list[str] = []
    complaint_plan = (
        None
        if complaint is None
        else _optional_document_plan(
            candidate_id,
            complaint,
            roles=(DocumentRole.AMENDED_COMPLAINT, DocumentRole.COMPLAINT),
            model_visible=True,
            contains_target_outcome=False,
        )
    )
    if complaint_plan is None:
        reasons.append("no_free_operative_complaint")
    free_target_numbers = _free_target_mtd_entry_numbers(
        page,
        target_entries=target_entries,
        decision_floor=decision_floor,
        allow_inferred_target_mtd=allow_inferred_target_mtd,
    )
    target_required_count = max(1, len(target_entries))
    for entry_number in target_entries:
        if entry_number not in free_target_numbers:
            reasons.append(
                _numbered_missing_reason(
                    "no_free_target_mtd_document",
                    entry_number,
                    total=target_required_count,
                )
            )
    if not target_entries and not target_mtd_entries:
        reasons.append("no_free_target_mtd_document")
    has_free_mtd_memorandum = any(
        _best_free_document(entry, DocumentRole.MTD_MEMORANDUM) is not None
        for entry in target_mtd_entries
    )
    if not has_free_mtd_memorandum:
        reasons.append("no_free_mtd_memorandum")
    decision_required_count = max(1, len(decision_entries))
    free_decision_numbers = {_entry_number(entry) for entry in decision_entry_plans}
    for entry_number in decision_entries:
        if entry_number not in free_decision_numbers:
            reasons.append(
                _numbered_missing_reason(
                    "no_free_decision_document",
                    entry_number,
                    total=decision_required_count,
                )
            )
    if not decision_entries and not decision_entry_plans:
        reasons.append("no_free_decision_document")
    free_opposition_entries = tuple(
        entry
        for entry in opposition_entries
        if _best_free_document(entry, DocumentRole.OPPOSITION) is not None
    )
    for entry in opposition_entries:
        if _best_free_document(entry, DocumentRole.OPPOSITION) is None:
            entry_number = _entry_number(entry)
            reasons.append(
                _numbered_missing_reason(
                    "no_free_opposition",
                    entry_number,
                    total=len(opposition_entries),
                )
                if entry_number is not None
                else "no_free_opposition:unknown_entry"
            )
    documents: list[PublicPacketDocumentPlan] = []
    if complaint_plan is not None:
        documents.append(complaint_plan)
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=_mtd_role(entry),
            model_visible=True,
            contains_target_outcome=False,
        )
        for entry in target_mtd_entries
    )
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=DocumentRole.OPPOSITION,
            model_visible=True,
            contains_target_outcome=False,
        )
        for entry in free_opposition_entries
    )
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=DocumentRole.REPLY,
            model_visible=True,
            contains_target_outcome=False,
        )
        for entry in _optional_brief_entries(
            page,
            before_entry=decision_floor,
            target_entries=target_entries,
        )
    )
    documents.extend(
        _document_plan(
            candidate_id,
            entry,
            role=DocumentRole.DECISION,
            model_visible=False,
            contains_target_outcome=True,
        )
        for entry in decision_entry_plans
    )
    required_count = (
        1 + target_required_count + len(opposition_entries) + decision_required_count
    )
    free_required_count = (
        int(complaint_plan is not None)
        + min(int(has_free_mtd_memorandum), target_required_count)
        + len(free_opposition_entries)
        + min(len(free_decision_numbers), decision_required_count)
    )
    return (
        tuple(_dedupe_documents(documents)),
        tuple(reasons),
        required_count,
        free_required_count,
    )


def _select_lowest_cost_candidates(
    plans: Sequence[PublicPacketCandidatePlan],
    *,
    target_clean_cases: int,
    max_per_bucket: int | None,
) -> tuple[list[PublicPacketCandidatePlan], CaseMixSelectionResult]:
    """Apply exact lexicographic cost selection to the complete viable pool."""

    viable = [plan for plan in plans if plan.selected or plan.paid_recovery_required]
    ranked = [
        replace(plan, cost_rank=rank)
        for rank, plan in enumerate(
            sorted(
                viable,
                key=lambda plan: (
                    Decimal(plan.projected_paid_cost_usd),
                    plan.missing_required_document_count,
                    plan.candidate_id.casefold(),
                    plan.candidate_id,
                ),
            ),
            start=1,
        )
    ]
    optimizer_result = select_exact_case_mix(
        tuple(
            CaseMixCandidate(
                candidate_id=plan.candidate_id,
                cost_cents=_money_cents(plan.projected_paid_cost_usd),
                missing_document_count=plan.missing_required_document_count,
                court=plan.court,
                nos_macro_category=plan.nos_macro_category,
                related_family_id=plan.related_family_id,
                mdl_family_id=plan.mdl_family_id,
            )
            for plan in ranked
        ),
        target_count=target_clean_cases,
        max_per_bucket=max_per_bucket,
    )
    selected_ids = set(optimizer_result.selected_candidate_ids)
    selected = [plan for plan in ranked if plan.candidate_id in selected_ids]
    counts = _selected_case_mix_counts(selected)
    reserves: list[PublicPacketCandidatePlan] = []
    for plan in ranked:
        if plan.candidate_id in selected_ids:
            continue
        blocked_bucket = _first_binding_bucket(
            plan,
            counts=counts,
            max_per_bucket=max_per_bucket,
        )
        if blocked_bucket is not None:
            dimension, bucket = blocked_bucket
            reserves.append(
                _sampling_reserve(plan, f"case_mix_cap_reached:{dimension}:{bucket}")
            )
        else:
            reserves.append(
                _sampling_reserve(plan, "higher_projected_acquisition_cost")
            )
    intrinsic_exclusions = sorted(
        (
            plan
            for plan in plans
            if not plan.selected and not plan.paid_recovery_required
        ),
        key=_canonical_candidate_plan_key,
    )
    return [*selected, *reserves, *intrinsic_exclusions], optimizer_result


def _sampling_reserve(
    plan: PublicPacketCandidatePlan,
    reason: str,
) -> PublicPacketCandidatePlan:
    return replace(
        plan,
        selected=False,
        paid_recovery_required=False,
        exclusion_reasons=(reason,),
    )


def _canonical_candidate_plan_key(
    plan: PublicPacketCandidatePlan,
) -> tuple[str, str, str]:
    return (
        plan.candidate_id.casefold(),
        plan.candidate_id,
        json.dumps(
            plan.to_record(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    )


def _case_mix_share(value: Decimal | str | float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        share = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("max_case_mix_share must be a finite decimal") from exc
    if not share.is_finite() or not Decimal("0") < share <= Decimal("1"):
        raise ValueError("max_case_mix_share must be greater than 0 and at most 1")
    return share


def _case_mix_bucket_cap(
    *,
    target_clean_cases: int,
    max_case_mix_share: Decimal | None,
) -> int | None:
    if max_case_mix_share is None:
        return None
    numerator, denominator = max_case_mix_share.as_integer_ratio()
    cap = (target_clean_cases * numerator) // denominator
    if cap < 1:
        raise ValueError(
            "max_case_mix_share must be at least 1 / target_clean_cases; the "
            "exact per-bucket cap would otherwise be zero"
        )
    return cap


def _money_cents(value: str) -> int:
    amount = _money_decimal(value, "projected_paid_cost_usd")
    cents = amount * 100
    integral = cents.to_integral_value()
    if cents != integral:
        raise ValueError("projected_paid_cost_usd must use whole cents")
    return int(integral)


def _optimizer_summary_record(
    result: CaseMixSelectionResult,
) -> dict[str, Any]:
    record = result.to_record()
    audit = cast(dict[str, Any], record.pop("audit"))
    return {**record, **audit}


def _selected_case_mix_counts(
    selected: Sequence[PublicPacketCandidatePlan],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for plan in selected:
        for dimension in _CASE_MIX_DIMENSIONS:
            bucket = cast(str | None, getattr(plan, dimension))
            if bucket is not None:
                key = (dimension, bucket)
                counts[key] = counts.get(key, 0) + 1
    return counts


def _first_binding_bucket(
    plan: PublicPacketCandidatePlan,
    *,
    counts: Mapping[tuple[str, str], int],
    max_per_bucket: int | None,
) -> tuple[str, str] | None:
    if max_per_bucket is None:
        return None
    for dimension in _CASE_MIX_DIMENSIONS:
        bucket = cast(str | None, getattr(plan, dimension))
        if bucket is not None and counts.get((dimension, bucket), 0) >= max_per_bucket:
            return dimension, bucket
    return None


def _free_target_mtd_entry_numbers(
    page: CourtListenerWebDocketPage,
    *,
    target_entries: tuple[int, ...],
    decision_floor: int | None,
    allow_inferred_target_mtd: bool,
) -> set[int]:
    free: set[int] = set()
    for target_entry in target_entries:
        exact = next(
            (
                entry
                for entry in page.entries
                if _entry_number(entry) == target_entry
                and _is_exact_target_mtd_entry(entry)
            ),
            None,
        )
        if exact is not None:
            free.add(target_entry)
            continue
        if any(
            _entry_is_before(entry, decision_floor)
            and _is_mtd_entry(entry)
            and _references_target_motion(entry, (target_entry,))
            for entry in page.entries
        ):
            free.add(target_entry)
    return free


def _numbered_missing_reason(base: str, entry_number: int, *, total: int) -> str:
    return base if total == 1 else f"{base}:{entry_number}"


def _money_decimal(value: Decimal | str, field_name: str) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal amount") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field_name} must be a finite non-negative amount")
    return amount.quantize(Decimal("0.01"))


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _page_from_embedded_selected_entries(
    record: Mapping[str, Any],
    *,
    candidate_id: str,
    source_url: str | None,
) -> CourtListenerWebDocketPage | None:
    entries_value = record.get("selected_entries")
    if not isinstance(entries_value, Sequence) or isinstance(entries_value, str):
        return None
    entry_records = (
        cast(Mapping[str, Any], entry_record)
        for entry_record in cast(Sequence[object], entries_value)
        if isinstance(entry_record, Mapping)
    )
    entries = tuple(
        _entry_from_embedded_record(entry_record) for entry_record in entry_records
    )
    if not entries:
        return None
    return CourtListenerWebDocketPage(
        docket_id=candidate_id,
        source_url=source_url,
        title=None,
        entries=_dedupe_entries(entries),
        has_next_page=False,
    )


def _entry_from_embedded_record(
    record: Mapping[str, Any],
) -> CourtListenerWebDocketEntry:
    documents_value = record.get("documents")
    documents: tuple[CourtListenerWebDocument, ...] = ()
    if isinstance(documents_value, Sequence) and not isinstance(documents_value, str):
        document_records = (
            cast(Mapping[str, Any], document_record)
            for document_record in cast(Sequence[object], documents_value)
            if isinstance(document_record, Mapping)
        )
        documents = tuple(
            _document_from_embedded_record(document_record)
            for document_record in document_records
        )
    return CourtListenerWebDocketEntry(
        row_id=_optional_str(record, "row_id") or "",
        entry_number=_optional_str(record, "entry_number"),
        filed_at=_optional_str(record, "filed_at"),
        text=_optional_str(record, "text") or "",
        documents=documents,
        restriction_markers=_merged_restriction_markers(
            record,
            restricted_material_markers(
                records=(record,),
                text_fields=(_optional_str(record, "text") or "",),
            ),
        ),
    )


def _document_from_embedded_record(
    record: Mapping[str, Any],
) -> CourtListenerWebDocument:
    return CourtListenerWebDocument(
        kind=_optional_str(record, "kind") or "",
        description=_optional_str(record, "description") or "",
        href=_optional_str(record, "href"),
        action_label=_optional_str(record, "action_label"),
        pacer_only=bool(record.get("pacer_only", False)),
        restriction_markers=_merged_restriction_markers(
            record,
            restricted_material_markers(
                records=(record,),
                text_fields=(
                    _optional_str(record, "kind") or "",
                    _optional_str(record, "description") or "",
                ),
                access_label_fields=(_optional_str(record, "action_label") or "",),
            ),
        ),
    )


def _merged_restriction_markers(
    record: Mapping[str, Any], detected: tuple[str, ...]
) -> tuple[str, ...]:
    explicit = record.get("restriction_markers")
    if explicit is None:
        return detected
    if not isinstance(explicit, list):
        raise ValueError("embedded restriction_markers must be a list")
    markers: list[str] = []
    for marker in cast(list[object], explicit):
        if not isinstance(marker, str) or not marker.strip():
            raise ValueError(
                "embedded restriction_markers must contain non-empty strings"
            )
        markers.append(marker.strip())
    return tuple(sorted(set((*detected, *markers))))


def _dedupe_entries(
    entries: Iterable[CourtListenerWebDocketEntry],
) -> tuple[CourtListenerWebDocketEntry, ...]:
    seen: set[tuple[str, str | None, str]] = set()
    deduped: list[CourtListenerWebDocketEntry] = []
    for entry in entries:
        key = (entry.row_id, entry.entry_number, entry.text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return tuple(deduped)


def _core_packet_restriction_reasons(
    page: CourtListenerWebDocketPage,
    *,
    target_entries: tuple[int, ...],
    decision_entries: tuple[int, ...],
) -> tuple[str, ...]:
    """Ledger restrictions attached to required packet entries, fail closed."""

    decision_floor = min(decision_entries) if decision_entries else _max_entry(page)
    complaint_floor = min(target_entries) if target_entries else decision_floor
    target_numbers = set(target_entries)
    decision_numbers = set(decision_entries)
    reasons: list[str] = []
    for entry in page.entries:
        if not entry.restricted:
            continue
        entry_number = _entry_number(entry)
        required_role: str | None = None
        if entry_number in target_numbers:
            required_role = "target_mtd"
        elif entry_number in decision_numbers:
            required_role = "decision"
        elif _entry_is_before(
            entry, complaint_floor
        ) and _restricted_entry_looks_like_complaint(entry):
            required_role = "operative_complaint"
        elif (
            _entry_is_before(entry, decision_floor)
            and entry.role is CourtListenerEntryRole.OPPOSITION
            and is_substantive_mtd_opposition_entry(entry)
            and _brief_targets_motion(entry, target_entries)
        ):
            required_role = "opposition"
        if required_role is None:
            continue
        location = f"entry_{entry_number}" if entry_number is not None else entry.row_id
        reasons.append(
            _restricted_material_reason(
                f"{required_role}_{location or 'unknown'}",
                _entry_restriction_markers(entry),
            )
        )
    return tuple(dict.fromkeys(reasons))


def _restricted_entry_looks_like_complaint(
    entry: CourtListenerWebDocketEntry,
) -> bool:
    text = " ".join(
        (
            entry.text,
            *(document.description for document in entry.documents),
        )
    ).casefold()
    if "complaint" not in text:
        return False
    return not bool(
        re.search(
            r"\b(?:answer|order|motion|memorandum|opposition|reply|notice)\b"
            r"[^.]{0,80}\bcomplaint\b",
            text,
        )
    )


def _entry_restriction_markers(
    entry: CourtListenerWebDocketEntry,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *entry.restriction_markers,
                *(
                    marker
                    for document in entry.documents
                    for marker in document.restriction_markers
                ),
            }
        )
    )


def _restricted_material_reason(
    location: str,
    markers: Sequence[str],
) -> str:
    evidence = ",".join(markers) if markers else "unspecified"
    return f"sealed_or_restricted_material:{location}:{evidence}"


def _operative_complaint_entry(
    page: CourtListenerWebDocketPage,
    *,
    before_entry: int | None,
) -> CourtListenerWebDocketEntry | None:
    if before_entry is None:
        return None
    selection = select_operative_complaint_entry(
        page.entries,
        before_entry=before_entry,
    )
    return None if selection is None else selection.entry


def _target_mtd_entries(
    page: CourtListenerWebDocketPage,
    *,
    target_entries: tuple[int, ...],
    decision_floor: int | None,
    allow_inferred_target_mtd: bool,
) -> tuple[CourtListenerWebDocketEntry, ...]:
    target_entry_set = set(target_entries)
    exact = tuple(
        entry
        for entry in page.entries
        if _entry_number(entry) in target_entry_set
        and _is_exact_target_mtd_entry(entry)
    )
    target_support = tuple(
        entry
        for entry in page.entries
        if _entry_is_before(entry, decision_floor)
        and _is_mtd_entry(entry)
        and _references_target_motion(entry, target_entries)
    )
    if exact or target_support:
        return _dedupe_entries((*exact, *target_support))
    if not allow_inferred_target_mtd:
        return ()
    if target_entries:
        return ()
    return tuple(
        entry
        for entry in page.entries
        if _entry_is_before(entry, decision_floor) and _is_mtd_entry(entry)
    )


def _optional_brief_entries(
    page: CourtListenerWebDocketPage,
    *,
    before_entry: int | None,
    target_entries: tuple[int, ...],
) -> tuple[CourtListenerWebDocketEntry, ...]:
    return tuple(
        entry
        for entry in page.entries
        if _entry_is_before(entry, before_entry)
        and _is_optional_brief_entry(entry)
        and _brief_targets_motion(entry, target_entries)
    )


def _required_opposition_entries(
    page: CourtListenerWebDocketPage,
    *,
    target_entries: tuple[int, ...],
    before_entry: int | None,
) -> tuple[CourtListenerWebDocketEntry, ...]:
    """Return filed target oppositions; every returned entry is a required slot."""

    return tuple(
        entry
        for entry in page.entries
        if _entry_is_before(entry, before_entry)
        and entry.role is CourtListenerEntryRole.OPPOSITION
        and is_substantive_mtd_opposition_entry(entry)
        and _brief_targets_motion(entry, target_entries)
    )


def _brief_targets_motion(
    entry: CourtListenerWebDocketEntry,
    target_entries: tuple[int, ...],
) -> bool:
    explicit_references = _explicit_motion_reference_numbers(entry)
    if explicit_references:
        return bool(explicit_references.intersection(target_entries))
    return len(target_entries) <= 1


def _explicit_motion_reference_numbers(
    entry: CourtListenerWebDocketEntry,
) -> set[int]:
    text = " ".join(entry.text.lower().split())
    return {
        int(match.group(1))
        for match in re.finditer(
            r"\b(?:re|regarding|opposition\s+to|motion|dkt\.?|ecf\s+no\.?)"
            r"\s*(?:#|no\.?)?\s*(\d+)\b",
            text,
        )
    }


def _decision_entries(
    page: CourtListenerWebDocketPage,
    *,
    decision_entries: tuple[int, ...],
) -> tuple[CourtListenerWebDocketEntry, ...]:
    exact = tuple(
        entry
        for entry in page.entries
        if _entry_number(entry) in set(decision_entries)
        and _best_free_document(entry, DocumentRole.DECISION) is not None
    )
    if decision_entries:
        return exact
    return tuple(
        entry
        for entry in page.entries
        if _is_decision_entry(entry)
        and _best_free_document(entry, DocumentRole.DECISION) is not None
    )


def _document_plan(
    candidate_id: str,
    entry: CourtListenerWebDocketEntry,
    *,
    role: DocumentRole,
    model_visible: bool,
    contains_target_outcome: bool,
) -> PublicPacketDocumentPlan:
    document = _best_free_document(entry, role)
    if document is None:
        raise ValueError(f"entry has no free document for role: {role.value}")
    entry_number = _entry_number(entry)
    source_document_id = (
        f"{candidate_id}-entry-{entry.entry_number or 'unknown'}-{role.value}".replace(
            "_", "-"
        )
    )
    return PublicPacketDocumentPlan(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        docket_entry_number=entry_number,
        document_role=role,
        source_url=document.href or "",
        description=document.description,
        model_visible=model_visible,
        contains_target_outcome=contains_target_outcome,
    )


def _optional_document_plan(
    candidate_id: str,
    entry: CourtListenerWebDocketEntry,
    *,
    roles: tuple[DocumentRole, ...],
    model_visible: bool,
    contains_target_outcome: bool,
) -> PublicPacketDocumentPlan | None:
    for role in roles:
        if _best_free_document(entry, role) is not None:
            return _document_plan(
                candidate_id,
                entry,
                role=role,
                model_visible=model_visible,
                contains_target_outcome=contains_target_outcome,
            )
    return None


def _dedupe_documents(
    documents: Iterable[PublicPacketDocumentPlan],
) -> tuple[PublicPacketDocumentPlan, ...]:
    seen: set[str] = set()
    deduped: list[PublicPacketDocumentPlan] = []
    for document in documents:
        key = document.source_url
        if key in seen:
            continue
        seen.add(key)
        deduped.append(document)
    return tuple(deduped)


def _excluded_plan(
    candidate_id: str,
    metadata: Mapping[str, Any],
    *,
    decision_date: str | None,
    case_mix_metadata: Mapping[str, str | None],
    source_url: str | None,
    target_entries: tuple[int, ...],
    decision_entries: tuple[int, ...],
    reason: str,
) -> PublicPacketCandidatePlan:
    return PublicPacketCandidatePlan(
        candidate_id=candidate_id,
        case_id=_optional_str(metadata, "case_id") or candidate_id,
        case_name=_optional_str(metadata, "case_name"),
        court=_optional_str(metadata, "court"),
        docket_number=_optional_str(metadata, "docket_number"),
        decision_date=decision_date,
        nature_of_suit=case_mix_metadata["nature_of_suit"],
        nos_macro_category=case_mix_metadata["nos_macro_category"],
        related_family_id=case_mix_metadata["related_family_id"],
        mdl_family_id=case_mix_metadata["mdl_family_id"],
        case_type_stratum=case_mix_metadata["case_type_stratum"] or "district_civil",
        source_url=source_url,
        selected=False,
        exclusion_reasons=(reason,),
        paid_recovery_required=False,
        paid_gap_reasons=(),
        target_motion_entry_numbers=target_entries,
        decision_entry_numbers=decision_entries,
        documents=(),
    )


def _case_mix_metadata(
    record: Mapping[str, Any],
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, str | None]:
    aliases = {
        "nature_of_suit": ("nature_of_suit", "natureOfSuit"),
        "nos_macro_category": ("nos_macro_category", "nosMacroCategory"),
        "related_family_id": (
            "related_family_id",
            "relatedFamilyId",
            "related_case_family_id",
            "relatedCaseFamilyId",
        ),
        "mdl_family_id": ("mdl_family_id", "mdlFamilyId", "mdl_id", "mdlId"),
        "case_type_stratum": ("case_type_stratum", "caseTypeStratum"),
    }
    return {
        output_key: _first_optional_string(
            (record, metadata, candidate),
            source_keys,
        )
        for output_key, source_keys in aliases.items()
    }


def _first_optional_string(
    records: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
) -> str | None:
    for record in records:
        for key in keys:
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, int) and not isinstance(value, bool):
                return str(value)
    return None


def _first_written_disposition_date(
    record: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    value = (
        _optional_str(record, "first_written_mtd_disposition_date")
        or _optional_str(record, "decision_date")
        or _optional_str(record, "decision_entered_date")
        or _optional_str(metadata, "decision_date")
        or _optional_str(metadata, "decision_entered_date")
    )
    if value is None:
        return None, "first_written_mtd_disposition_date_missing"
    try:
        date.fromisoformat(value)
    except ValueError:
        return value, "first_written_mtd_disposition_date_invalid"
    return value, None


def _mtd_role(entry: CourtListenerWebDocketEntry) -> DocumentRole:
    return (
        DocumentRole.MTD_MEMORANDUM
        if _best_free_document(entry, DocumentRole.MTD_MEMORANDUM) is not None
        else DocumentRole.MTD_NOTICE
    )


def _brief_role(entry: CourtListenerWebDocketEntry) -> DocumentRole:
    if entry.role is CourtListenerEntryRole.REPLY:
        return DocumentRole.REPLY
    return DocumentRole.OPPOSITION


def _is_mtd_entry(entry: CourtListenerWebDocketEntry) -> bool:
    if entry.role not in {
        CourtListenerEntryRole.MTD_NOTICE,
        CourtListenerEntryRole.MTD_MEMORANDUM,
    }:
        return False
    return (
        _best_free_document(entry, DocumentRole.MTD_NOTICE) is not None
        or _best_free_document(entry, DocumentRole.MTD_MEMORANDUM) is not None
    )


def _is_exact_target_mtd_entry(entry: CourtListenerWebDocketEntry) -> bool:
    """Accept MTD-role documents only at an already frozen exact target entry."""

    return (
        _best_free_document(entry, DocumentRole.MTD_NOTICE) is not None
        or _best_free_document(entry, DocumentRole.MTD_MEMORANDUM) is not None
    )


def _references_target_motion(
    entry: CourtListenerWebDocketEntry,
    target_entries: tuple[int, ...],
) -> bool:
    if not target_entries:
        return False
    text = " ".join(entry.text.lower().split())
    for target_entry in target_entries:
        escaped = re.escape(str(target_entry))
        if re.search(
            rf"\b(?:re|regarding|support(?:\s+of)?|opposition\s+to)\s+"
            rf"{escaped}\b",
            text,
        ):
            return True
        if re.search(rf"\b{escaped}\s+motions?\s+to\s+dismiss\b", text):
            return True
    return False


def _is_optional_brief_entry(entry: CourtListenerWebDocketEntry) -> bool:
    if entry.role not in _OPTIONAL_BRIEF_ROLES:
        return False
    role = _brief_role(entry)
    if _best_free_document(entry, role) is None:
        return False
    descriptions = _document_descriptions(entry)
    text = entry.text.lower()
    if re.search(r"\b(?:scheduling|extension|notice|order)\b", descriptions):
        return False
    opposition_pattern = (
        r"\b(?:opposition|response in opposition|brief in opposition)\b"
    )
    return bool(
        re.search(opposition_pattern, descriptions)
        or re.search(r"\breply(?: memorandum| brief)?\b", descriptions)
        or re.search(opposition_pattern, text)
        or re.search(r"\breply(?: memorandum| brief)?\b", text)
    )


def _is_decision_entry(entry: CourtListenerWebDocketEntry) -> bool:
    descriptions = _document_descriptions(entry)
    text = entry.text.lower()
    return bool(
        entry.role is CourtListenerEntryRole.DECISION
        or "order on motion to dismiss" in descriptions
        or "order on motion to dismiss" in text
    )


def _document_descriptions(entry: CourtListenerWebDocketEntry) -> str:
    return " ".join(document.description for document in entry.documents).lower()


def _best_free_document(
    entry: CourtListenerWebDocketEntry,
    role: DocumentRole,
):
    if role in {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}:
        number = _entry_number(entry)
        selection = (
            None
            if number is None
            else select_operative_complaint_entry((entry,), before_entry=number + 1)
        )
        expected_kind = (
            OperativeComplaintKind.AMENDED_COMPLAINT
            if role is DocumentRole.AMENDED_COMPLAINT
            else OperativeComplaintKind.COMPLAINT
        )
        if selection is not None and selection.kind is expected_kind:
            return select_operative_complaint_document(entry, require_free=True)
    matching_documents = tuple(
        document
        for document in entry.documents
        if document.freely_available
        and document.href
        and _document_matches_role(document.description, role)
    )
    if matching_documents:
        return matching_documents[0]
    if role is DocumentRole.MTD_MEMORANDUM and entry.role is (
        CourtListenerEntryRole.MTD_MEMORANDUM
    ):
        main_documents = tuple(
            document
            for document in entry.documents
            if document.freely_available
            and document.href
            and "main" in document.kind.lower()
        )
        if len(main_documents) == 1:
            return main_documents[0]
    if role is DocumentRole.MTD_MEMORANDUM and _is_explicit_combined_mtd(entry):
        main_documents = tuple(
            document
            for document in entry.documents
            if document.freely_available
            and document.href
            and "main" in document.kind.lower()
        )
        if len(main_documents) == 1:
            return main_documents[0]
    if role is DocumentRole.DECISION:
        return next(
            (
                document
                for document in entry.documents
                if document.freely_available and document.href
            ),
            None,
        )
    return None


def _is_explicit_combined_mtd(entry: CourtListenerWebDocketEntry) -> bool:
    text = " ".join(entry.text.lower().split())
    return bool(
        re.search(
            r"\bmotion\s+to\s+dismiss\b.{0,200}\b(?:and|with)\b.{0,100}"
            r"\b(?:memorandum|brief)\b.{0,100}\b(?:in\s+)?support\b",
            text,
        )
    )


def _document_matches_role(description: str, role: DocumentRole) -> bool:
    text = " ".join(description.lower().split())
    if not text and role is DocumentRole.MTD_NOTICE:
        return False
    if role is DocumentRole.COMPLAINT:
        return _looks_like_complaint_document_description(text, amended=False)
    if role is DocumentRole.AMENDED_COMPLAINT:
        return _looks_like_complaint_document_description(text, amended=True)
    if role is DocumentRole.MTD_NOTICE:
        return bool(
            (
                re.search(r"\b(?:motion\s+to\s+)?dismiss(?:al)?\b", text)
                or re.search(r"\bjudgment\s+on\s+the\s+pleadings\b", text)
            )
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.MTD_MEMORANDUM:
        return bool(
            re.search(r"\b(?:memorandum|brief)\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.OPPOSITION:
        return bool(
            re.search(r"\b(?:opposition|response\s+in\s+opposition)\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.REPLY:
        return bool(
            re.search(r"\breply\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    if role is DocumentRole.DECISION:
        return bool(
            re.search(r"\b(?:order|opinion|decision|judgment)\b", text)
            and not _contains_non_merits_motion_marker(text)
        )
    return False


def _looks_like_complaint_document_description(text: str, *, amended: bool) -> bool:
    if not text:
        return False
    if _contains_procedural_complaint_reference(text):
        return False
    if amended:
        if "alleged in" in text or "timeline" in text:
            return False
        return bool(
            re.fullmatch(
                r"(?:exhibit\s+)?(?:exh\s+[a-z0-9]+\s+)?"
                r"(?:(?:first|second|third)\s+)?amended complaint",
                text,
            )
        )
    return text in {
        "civil case - complaint",
        "complaint",
        "notice of removal",
        "notice of removal (attorney civil case opening)",
    }


def _contains_procedural_complaint_reference(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:answer|extension|initial order|standing order|order|stipulation|"
            r"proposed|summons|service|notice of appearance|cover sheet|certificate|"
            r"motion|deadline|responsive pleading)\b",
            text,
        )
    )


def _contains_non_merits_motion_marker(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:extension|adjourn|appear pro hac|appearance|withdraw|serve|"
            r"subpoena|discovery|scheduling|proposed order|stipulation|notice)\b",
            text,
        )
    )


def _entry_number(entry: CourtListenerWebDocketEntry) -> int | None:
    if entry.entry_number is None:
        return None
    match = re.match(r"\d+", entry.entry_number)
    return int(match.group(0)) if match is not None else None


def _entry_is_before(
    entry: CourtListenerWebDocketEntry,
    before_entry: int | None,
) -> bool:
    entry_number = _entry_number(entry)
    return entry_number is not None and (
        before_entry is None or entry_number < before_entry
    )


def _max_entry(page: CourtListenerWebDocketPage) -> int | None:
    numbers = [_entry_number(entry) for entry in page.entries]
    present = [number for number in numbers if number is not None]
    return max(present) if present else None


def _entry_number_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    numbers: list[int] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, int):
            if item not in numbers:
                numbers.append(item)
            continue
        if isinstance(item, str) and item.strip().isdigit():
            number = int(item.strip())
            if number not in numbers:
                numbers.append(number)
    return tuple(numbers)


def _mapping(record: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = record.get(key)
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _required_str(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    joined = ", ".join(keys)
    raise ValueError(f"record missing required string field: {joined}")


def _optional_str(record: Mapping[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value.strip() else None
