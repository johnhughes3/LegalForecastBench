"""Bridge public CourtListener candidates to authoritative case.dev document IDs.

CourtListener establishes the public docket chronology and which documents are
free or PACER-only.  It does not establish the identifier accepted by the
case.dev purchase endpoint.  This module therefore resolves each candidate by
exact court and docket number, corroborates the caption, and emits acquisition
records only from document IDs returned by the matched case.dev docket.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevDocketHit,
    CaseDevRateLimitError,
    CaseDevServerError,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerDocketEntry,
    CourtListenerRateLimitError,
    CourtListenerRecapDocument,
    CourtListenerServerError,
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
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    select_operative_complaint_document,
    select_operative_complaint_entry,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.recap_api_discovery import public_recap_download_url
from legalforecast.ingestion.recap_fetch_broker_policy import (
    COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE,
)
from legalforecast.ingestion.restricted_material import restricted_material_markers

_CASE_DEV_SEARCH_LIMIT = 20
_CASE_DEV_DOCKET_PAGE_SIZE = 100
_RECOVERABLE_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.REPLY,
        DocumentRole.DECISION,
    }
)
_MODEL_VISIBLE_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.REPLY,
    }
)
_COURTLISTENER_REST_FREE_RESTRICTION_EVIDENCE = (
    "courtlistener_rest_docket_exact_match",
    "courtlistener_rest_docket_entry_exact_match",
    "courtlistener_rest_recap_document_exact_match",
    "courtlistener_rest_recap_document_is_available_true",
    "courtlistener_rest_recap_document_is_sealed_false",
    "courtlistener_rest_public_download_url_allowlisted",
)
_CASE_DEV_FREE_RESTRICTION_EVIDENCE = (
    "courtlistener_docket_entry_checked",
    "case_dev_entry_and_document_checked",
)
_RESTRICTED_STATUS_VALUES = frozenset({"private", "restricted", "sealed", "under_seal"})
_PAID_GAP_ROLES = {
    "no_free_operative_complaint": frozenset(
        {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}
    ),
    "no_free_target_mtd_document": frozenset(
        {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}
    ),
    "no_free_opposition": frozenset({DocumentRole.OPPOSITION}),
    "no_free_mtd_memorandum": frozenset({DocumentRole.MTD_MEMORANDUM}),
    "no_free_decision_document": frozenset({DocumentRole.DECISION}),
}


class CourtListenerCaseDevBridgeError(ValueError):
    """Raised when a candidate cannot be bridged without guessing identity."""


@dataclass(frozen=True, slots=True)
class _BridgeDocument:
    candidate_id: str
    source_document_id: str
    case_dev_entry_id: str
    docket_entry_number: int
    document_role: DocumentRole
    source_url_or_reference: str
    description: str
    free: bool
    restriction_evidence: tuple[str, ...]

    @property
    def restriction_status(self) -> str:
        # A free CourtListener document has affirmative public-download
        # evidence. PACER-only documents remain unknown until post-recovery
        # docket-derived clearance; absence of a marker is never public proof.
        return "public" if self.free and self.restriction_evidence else "unknown"

    @property
    def contains_target_outcome(self) -> bool:
        return self.document_role is DocumentRole.DECISION

    @property
    def model_visible(self) -> bool:
        return self.document_role in _MODEL_VISIBLE_ROLES

    @property
    def setup_runner_label(self) -> str:
        if self.model_visible:
            return "core_mtd"
        return "other_substantive"

    def selection_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_provider": ("courtlistener" if self.free else "case.dev+pacer"),
            "source_document_id": self.source_document_id,
            "case_dev_docket_entry_id": self.case_dev_entry_id,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "source_url": self.source_url_or_reference,
            "source_url_or_reference": self.source_url_or_reference,
            "description": self.description,
            "model_visible": self.model_visible,
            "is_predecision_material": not self.contains_target_outcome,
            "contains_target_outcome": self.contains_target_outcome,
            "availability_status": "available" if self.free else "unavailable",
            "requires_paid_recovery": not self.free,
            "redaction_or_seal_status": self.restriction_status,
            "restriction_evidence": list(self.restriction_evidence),
            "is_private": None,
            "is_sealed": None,
            "file_extension": "pdf",
            "resolved_from_paid_gap": True,
        }

    def case_relevance_record(self) -> dict[str, Any]:
        record = self.selection_record()
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "setup_runner_label": self.setup_runner_label,
            "document_role": self.document_role.value,
            "docket_entry_id": self.case_dev_entry_id,
            "docket_entry_number": self.docket_entry_number,
            "docket_entry_text": self.description,
            "source_url_or_reference": self.source_url_or_reference,
            "availability_status": record["availability_status"],
            "requires_paid_recovery": record["requires_paid_recovery"],
            "redaction_or_seal_status": self.restriction_status,
            "restriction_evidence": list(self.restriction_evidence),
            "is_private": None,
            "is_sealed": None,
            "contains_target_outcome": self.contains_target_outcome,
            "model_visible": self.model_visible,
            "resolved_from_paid_gap": True,
        }

    def free_download_request(self) -> FreeDocumentDownloadRequest | None:
        if not self.free:
            return None
        return FreeDocumentDownloadRequest(
            candidate_id=self.candidate_id,
            source_provider="courtlistener",
            source_document_id=self.source_document_id,
            docket_entry_number=self.docket_entry_number,
            document_role=self.document_role,
            source_url=self.source_url_or_reference,
            file_extension="pdf",
        )


@dataclass(frozen=True, slots=True)
class _CourtListenerRestGapDocument:
    candidate_id: str
    source_document_id: str
    docket_entry_id: str
    docket_entry_number: int
    document_role: DocumentRole
    source_url_or_reference: str
    description: str
    free: bool = False

    @property
    def contains_target_outcome(self) -> bool:
        return self.document_role is DocumentRole.DECISION

    @property
    def model_visible(self) -> bool:
        return self.document_role in _MODEL_VISIBLE_ROLES

    def selection_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_provider": (
                "courtlistener" if self.free else "courtlistener+recap-fetch"
            ),
            "source_document_id": self.source_document_id,
            "courtlistener_docket_entry_id": self.docket_entry_id,
            "docket_entry_number": self.docket_entry_number,
            "document_role": self.document_role.value,
            "source_url": self.source_url_or_reference,
            "source_url_or_reference": self.source_url_or_reference,
            "description": self.description,
            "model_visible": self.model_visible,
            "is_predecision_material": not self.contains_target_outcome,
            "contains_target_outcome": self.contains_target_outcome,
            "availability_status": "available" if self.free else "unavailable",
            "requires_paid_recovery": not self.free,
            "redaction_or_seal_status": "public",
            "restriction_evidence": list(
                _COURTLISTENER_REST_FREE_RESTRICTION_EVIDENCE
                if self.free
                else COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE
            ),
            "is_private": None,
            "is_sealed": False,
            "file_extension": "pdf",
            "resolved_from_paid_gap": True,
        }

    def case_relevance_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "setup_runner_label": (
                "core_mtd" if self.model_visible else "other_substantive"
            ),
            "document_role": self.document_role.value,
            "docket_entry_id": self.docket_entry_id,
            "docket_entry_number": self.docket_entry_number,
            "docket_entry_text": self.description,
            "source_url_or_reference": self.source_url_or_reference,
            "availability_status": "available" if self.free else "unavailable",
            "requires_paid_recovery": not self.free,
            "redaction_or_seal_status": "public",
            "restriction_evidence": list(
                _COURTLISTENER_REST_FREE_RESTRICTION_EVIDENCE
                if self.free
                else COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE
            ),
            "is_private": None,
            "is_sealed": False,
            "contains_target_outcome": self.contains_target_outcome,
            "model_visible": self.model_visible,
            "resolved_from_paid_gap": True,
        }

    def free_download_request(self) -> FreeDocumentDownloadRequest | None:
        if not self.free:
            return None
        return FreeDocumentDownloadRequest(
            candidate_id=self.candidate_id,
            source_provider="courtlistener",
            source_document_id=self.source_document_id,
            docket_entry_number=self.docket_entry_number,
            document_role=self.document_role,
            source_url=self.source_url_or_reference,
            file_extension="pdf",
        )


@dataclass(frozen=True, slots=True)
class CourtListenerCaseDevBridgeResult:
    """Deterministic artifacts joining public availability to purchase IDs."""

    selection_records: tuple[Mapping[str, Any], ...]
    case_relevance_records: tuple[Mapping[str, Any], ...]
    free_download_requests: tuple[FreeDocumentDownloadRequest, ...]
    exclusions: tuple[Mapping[str, Any], ...]
    screened_case_count: int
    public_first_reconciled: bool = False
    bridge_provider: str = "case.dev"

    @property
    def selected_case_count(self) -> int:
        return len(self.selection_records)

    @property
    def paid_document_count(self) -> int:
        """Legacy count of documents whose bytes still require paid recovery."""

        return sum(
            document.get("requires_paid_recovery") is True
            for record in self.case_relevance_records
            for document in _mapping_sequence(record.get("documents"), "documents")
        )

    @property
    def paid_recovery_required_case_count(self) -> int:
        return sum(
            any(
                document.get("requires_paid_recovery") is True
                for document in _mapping_sequence(record.get("documents"), "documents")
            )
            for record in self.case_relevance_records
        )

    @property
    def identity_resolved_paid_gap_case_count(self) -> int:
        return sum(
            record.get("identity_resolution_status") == "resolved"
            and record.get("document_recovery_status") == "paid_recovery_required"
            for record in self.selection_records
        )

    @property
    def document_bytes_ready_case_count(self) -> int:
        # The legacy bridge runs before download-free and only proves that a
        # public URL exists. The public-first route validates its completed
        # free-download manifest before constructing this result. Documents
        # that become public during the bridge are new download requests and
        # therefore are not byte-ready until a later download-free replay.
        if not self.public_first_reconciled:
            return 0

        pending_free_candidates = {
            request.candidate_id for request in self.free_download_requests
        }

        def bytes_ready(record: Mapping[str, Any]) -> bool:
            if _required_str(record, "candidate_id") in pending_free_candidates:
                return False
            documents = _mapping_sequence(record.get("documents"), "documents")
            return bool(documents) and all(
                document.get("availability_status") == "available"
                and document.get("requires_paid_recovery") is not True
                for document in documents
            )

        return sum(bytes_ready(record) for record in self.case_relevance_records)

    def summary_record(self) -> dict[str, Any]:
        return {
            "schema_version": "legalforecast.courtlistener_case_dev_bridge.v2",
            "screened_case_count": self.screened_case_count,
            "selected_case_count": self.selected_case_count,
            "excluded_case_count": len(self.exclusions),
            "free_download_request_count": len(self.free_download_requests),
            "paid_document_count": self.paid_document_count,
            "paid_recovery_required_document_count": self.paid_document_count,
            "paid_recovery_required_case_count": (
                self.paid_recovery_required_case_count
            ),
            "identity_resolved_paid_gap_case_count": (
                self.identity_resolved_paid_gap_case_count
            ),
            "document_bytes_ready_case_count": self.document_bytes_ready_case_count,
            "identity_policy": self._identity_policy(),
            "free_first_required": True,
            "public_first_reconciled": self.public_first_reconciled,
        }

    def _identity_policy(self) -> str:
        if self.bridge_provider == "courtlistener_rest":
            return (
                "fully-free CourtListener IDs retained; paid-gap numeric RECAP "
                "IDs require exact REST docket/court/caption/entry corroboration "
                "and affirmative nonsealed/nonprivate metadata"
            )
        if self.public_first_reconciled:
            return (
                "fully-free CourtListener IDs retained; paid-gap case.dev IDs use "
                "exact court+docket match with caption corroboration"
            )
        return (
            "exact court+docket match with caption corroboration; "
            "case.dev document IDs only"
        )


def bridge_courtlistener_case_dev_documents(
    screened_case_records: Iterable[Mapping[str, Any]],
    *,
    client: CaseDevClient,
    raw_html_dir: str | Path | None = None,
    use_embedded_entries: bool = False,
    target_clean_cases: int = 150,
) -> CourtListenerCaseDevBridgeResult:
    """Resolve screened CourtListener cases to authoritative case.dev IDs.

    The function performs only free case.dev docket search/lookup requests.  It
    never invokes the PACER purchase endpoint and never downloads documents.
    """

    if target_clean_cases <= 0:
        raise ValueError("target_clean_cases must be positive")
    if raw_html_dir is None and not use_embedded_entries:
        raise ValueError("raw_html_dir is required unless use_embedded_entries=True")
    records = tuple(screened_case_records)
    html_root = None if raw_html_dir is None else Path(raw_html_dir)
    selections: list[Mapping[str, Any]] = []
    relevance: list[Mapping[str, Any]] = []
    free_requests: list[FreeDocumentDownloadRequest] = []
    exclusions: list[Mapping[str, Any]] = []

    for record in records:
        if len(selections) >= target_clean_cases:
            exclusions.append(_exclusion(record, "target_clean_case_limit_reached"))
            continue
        try:
            candidate, case_relevance, requests = _bridge_candidate(
                record,
                client=client,
                raw_html_dir=html_root,
                use_embedded_entries=use_embedded_entries,
            )
        except CourtListenerCaseDevBridgeError as exc:
            reason, _, detail = str(exc).partition(":")
            exclusions.append(_exclusion(record, reason, detail=detail.strip() or None))
            continue
        except (CaseDevRateLimitError, CaseDevServerError) as exc:
            reason = (
                "case_dev_rate_limit_retries_exhausted"
                if isinstance(exc, CaseDevRateLimitError)
                else "case_dev_server_error_retries_exhausted"
            )
            exclusions.append(
                _exclusion(
                    record,
                    reason,
                    detail=str(exc),
                )
            )
            continue
        selections.append(candidate)
        relevance.append(case_relevance)
        free_requests.extend(requests)

    return CourtListenerCaseDevBridgeResult(
        selection_records=tuple(selections),
        case_relevance_records=tuple(relevance),
        free_download_requests=tuple(free_requests),
        exclusions=tuple(exclusions),
        screened_case_count=len(records),
    )


def bridge_public_plan_paid_gaps(
    screened_case_records: Iterable[Mapping[str, Any]],
    *,
    public_selection_records: Iterable[Mapping[str, Any]],
    paid_gap_records: Iterable[Mapping[str, Any]],
    free_download_records: Iterable[Mapping[str, Any]],
    client: CaseDevClient,
    raw_html_dir: str | Path | None = None,
    use_embedded_entries: bool = False,
    validate_free_downloads: bool = True,
) -> CourtListenerCaseDevBridgeResult:
    """Recover only public-planner paid gaps after free downloads complete.

    Fully-free cases bypass case.dev. Mixed cases retain the CourtListener IDs
    already downloaded for their free documents and add only authoritative
    case.dev IDs for roles the public planner explicitly found unavailable.
    """

    screened = _unique_records_by_candidate(
        screened_case_records,
        source="screened_cases",
        nested_candidate=True,
    )
    public_selections = tuple(public_selection_records)
    paid_gaps = tuple(paid_gap_records)
    _validate_public_plan_routes(public_selections, paid_gaps)
    if validate_free_downloads:
        _validate_free_download_completion(
            (*public_selections, *paid_gaps),
            tuple(free_download_records),
        )
    html_root = None if raw_html_dir is None else Path(raw_html_dir)
    selections: list[Mapping[str, Any]] = list(public_selections)
    relevance: list[Mapping[str, Any]] = [
        _public_case_relevance(record) for record in public_selections
    ]
    free_requests: list[FreeDocumentDownloadRequest] = []
    exclusions: list[Mapping[str, Any]] = []
    for gap in paid_gaps:
        candidate_id = _required_str(gap, "candidate_id")
        record = screened.get(candidate_id)
        if record is None:
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_screened_candidate_missing: {candidate_id}"
            )
        try:
            selection, case_relevance = bridge_public_plan_paid_gap_candidate(
                record,
                paid_gap_record=gap,
                free_download_records=(),
                client=client,
                raw_html_dir=html_root,
                use_embedded_entries=use_embedded_entries,
                validate_free_downloads=False,
            )
        except CourtListenerCaseDevBridgeError as exc:
            reason, _, detail = str(exc).partition(":")
            exclusions.append(_exclusion(record, reason, detail=detail.strip() or None))
            continue
        except (CaseDevRateLimitError, CaseDevServerError) as exc:
            reason = (
                "case_dev_rate_limit_retries_exhausted"
                if isinstance(exc, CaseDevRateLimitError)
                else "case_dev_server_error_retries_exhausted"
            )
            exclusions.append(
                _exclusion(
                    record,
                    reason,
                    detail=str(exc),
                )
            )
            continue
        selections.append(selection)
        relevance.append(case_relevance)
        free_requests.extend(bridge_free_download_requests_from_selection(selection))
    selected_ids = {_required_str(record, "candidate_id") for record in selections}
    excluded_ids = {_required_str(record, "candidate_id") for record in exclusions}
    overlap = selected_ids & excluded_ids
    if overlap:
        raise CourtListenerCaseDevBridgeError(
            "selection_exclusion_overlap: " + ", ".join(sorted(overlap))
        )
    return CourtListenerCaseDevBridgeResult(
        selection_records=tuple(selections),
        case_relevance_records=tuple(relevance),
        free_download_requests=tuple(free_requests),
        exclusions=tuple(exclusions),
        screened_case_count=len(public_selections) + len(paid_gaps),
        public_first_reconciled=True,
    )


def bridge_public_plan_paid_gaps_via_courtlistener(
    screened_case_records: Iterable[Mapping[str, Any]],
    *,
    public_selection_records: Iterable[Mapping[str, Any]],
    paid_gap_records: Iterable[Mapping[str, Any]],
    free_download_records: Iterable[Mapping[str, Any]],
    client: CourtListenerClient,
    raw_html_dir: str | Path | None = None,
    use_embedded_entries: bool = False,
) -> CourtListenerCaseDevBridgeResult:
    """Reconcile public paid gaps using only noncharging CourtListener GETs."""

    screened = _unique_records_by_candidate(
        screened_case_records,
        source="screened_cases",
        nested_candidate=True,
    )
    public_selections = tuple(public_selection_records)
    paid_gaps = tuple(paid_gap_records)
    free_downloads = tuple(free_download_records)
    validate_public_plan_bridge_inputs(
        public_selection_records=public_selections,
        paid_gap_records=paid_gaps,
        free_download_records=free_downloads,
    )
    selections: list[Mapping[str, Any]] = list(public_selections)
    relevance: list[Mapping[str, Any]] = [
        _public_case_relevance(record) for record in public_selections
    ]
    free_requests: list[FreeDocumentDownloadRequest] = []
    exclusions: list[Mapping[str, Any]] = []
    for gap in paid_gaps:
        candidate_id = _required_str(gap, "candidate_id")
        record = screened.get(candidate_id)
        if record is None:
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_screened_candidate_missing: {candidate_id}"
            )
        try:
            selection, candidate_relevance = (
                bridge_public_plan_paid_gap_candidate_via_courtlistener(
                    record,
                    paid_gap_record=gap,
                    free_download_records=free_downloads,
                    client=client,
                    raw_html_dir=raw_html_dir,
                    use_embedded_entries=use_embedded_entries,
                    validate_free_downloads=False,
                )
            )
        except CourtListenerCaseDevBridgeError as exc:
            reason, _, detail = str(exc).partition(":")
            exclusions.append(
                _exclusion(record, reason, detail=detail.strip() or str(exc))
            )
            continue
        except (CourtListenerRateLimitError, CourtListenerServerError) as exc:
            reason = (
                "courtlistener_rest_rate_limit_retries_exhausted"
                if isinstance(exc, CourtListenerRateLimitError)
                else "courtlistener_rest_server_error_retries_exhausted"
            )
            exclusions.append(_exclusion(record, reason, detail=str(exc)))
            continue
        selections.append(selection)
        relevance.append(candidate_relevance)
        free_requests.extend(bridge_free_download_requests_from_selection(selection))
    selected_ids = {_required_str(record, "candidate_id") for record in selections}
    excluded_ids = {_required_str(record, "candidate_id") for record in exclusions}
    overlap = selected_ids & excluded_ids
    if overlap:
        raise CourtListenerCaseDevBridgeError(
            "selection_exclusion_overlap: " + ", ".join(sorted(overlap))
        )
    return CourtListenerCaseDevBridgeResult(
        selection_records=tuple(selections),
        case_relevance_records=tuple(relevance),
        free_download_requests=tuple(free_requests),
        exclusions=tuple(exclusions),
        screened_case_count=len(public_selections) + len(paid_gaps),
        public_first_reconciled=True,
        bridge_provider="courtlistener_rest",
    )


def bridge_public_plan_paid_gap_candidate(
    screened_case_record: Mapping[str, Any],
    *,
    paid_gap_record: Mapping[str, Any],
    free_download_records: Iterable[Mapping[str, Any]],
    client: CaseDevClient,
    raw_html_dir: str | Path | None = None,
    use_embedded_entries: bool = False,
    validate_free_downloads: bool = True,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Bridge exactly one public-plan paid gap without swallowing transients.

    The CLI uses this candidate-granular operation so an exhausted 429/5xx can
    be checkpointed and resumed without repeating other candidates. It remains
    free lookup only and never invokes a purchase endpoint.
    """

    _validate_public_plan_routes((), (paid_gap_record,))
    if validate_free_downloads:
        _validate_free_download_completion(
            (paid_gap_record,),
            tuple(free_download_records),
        )
    candidate_id = _required_str(paid_gap_record, "candidate_id")
    nested_candidate = screened_case_record.get("candidate")
    if (
        not isinstance(nested_candidate, Mapping)
        or _required_str_any(
            cast(Mapping[str, Any], nested_candidate),
            "docket_id",
            "candidate_key",
        )
        != candidate_id
    ):
        raise CourtListenerCaseDevBridgeError(
            f"paid_gap_screened_candidate_mismatch: {candidate_id}"
        )
    bridged_selection, bridged_relevance, _ = _bridge_candidate(
        screened_case_record,
        client=client,
        raw_html_dir=None if raw_html_dir is None else Path(raw_html_dir),
        use_embedded_entries=use_embedded_entries,
        paid_gap_reasons=_string_sequence(paid_gap_record.get("paid_gap_reasons")),
    )
    return _reconcile_paid_gap(
        paid_gap_record,
        bridged_selection=bridged_selection,
        bridged_relevance=bridged_relevance,
    )


def bridge_public_plan_paid_gap_candidate_via_courtlistener(
    screened_case_record: Mapping[str, Any],
    *,
    paid_gap_record: Mapping[str, Any],
    free_download_records: Iterable[Mapping[str, Any]],
    client: CourtListenerClient,
    raw_html_dir: str | Path | None = None,
    use_embedded_entries: bool = False,
    validate_free_downloads: bool = True,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Resolve one proven public paid gap through noncharging REST metadata.

    This route never invokes RECAP Fetch or PACER. It only turns an exact
    Firecrawl docket-row match into the real numeric RECAP document identifier
    needed by the separately budgeted purchase planner.
    """

    _validate_public_plan_routes((), (paid_gap_record,))
    if validate_free_downloads:
        _validate_free_download_completion(
            (paid_gap_record,),
            tuple(free_download_records),
        )
    candidate_id = _required_str(paid_gap_record, "candidate_id")
    candidate = _mapping(screened_case_record.get("candidate"), "candidate")
    if _required_str_any(candidate, "docket_id", "candidate_key") != candidate_id:
        raise CourtListenerCaseDevBridgeError(
            f"paid_gap_screened_candidate_mismatch: {candidate_id}"
        )
    if not candidate_id.isdecimal() or candidate_id.startswith("0"):
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_docket_id_invalid: {candidate_id}"
        )
    source_url = _optional_str(candidate, "url")
    source_docket_id = _courtlistener_docket_id_from_url(source_url)
    if source_docket_id is not None and source_docket_id != candidate_id:
        raise CourtListenerCaseDevBridgeError("courtlistener_source_id_conflict")
    metadata = _mapping(candidate.get("metadata"), "candidate.metadata")
    court = _required_str(metadata, "court")
    docket_number = _required_str(metadata, "docket_number")
    caption = _required_str(metadata, "case_name")
    page = _courtlistener_page(
        screened_case_record,
        candidate_id=candidate_id,
        source_url=source_url,
        raw_html_dir=None if raw_html_dir is None else Path(raw_html_dir),
        use_embedded_entries=use_embedded_entries,
    )
    if page.has_next_page:
        raise CourtListenerCaseDevBridgeError("courtlistener_docket_more_than_one_page")

    docket = client.get_docket(candidate_id)
    _corroborate_courtlistener_docket(
        docket_id=docket.docket_id,
        hit_court=docket.court_id,
        hit_docket=docket.docket_number,
        hit_caption=docket.case_name,
        expected_id=candidate_id,
        court=court,
        docket_number=docket_number,
        caption=caption,
    )
    rest_entries = tuple(client.iter_docket_entries(candidate_id, page_size=100))
    documents = _bridge_courtlistener_rest_gap_documents(
        screened_case_record,
        page=page,
        rest_entries=rest_entries,
        client=client,
        candidate_id=candidate_id,
        paid_gap_reasons=_string_sequence(paid_gap_record.get("paid_gap_reasons")),
    )
    case_mix = _case_mix_metadata(
        screened_case_record,
        candidate=candidate,
        metadata=metadata,
    )
    identity_resolution = {
        "courtlistener_candidate_id": candidate_id,
        "courtlistener_docket_id": docket.docket_id,
        "matched_by": "direct_rest_exact_docket_court_caption_entries",
    }
    selection = {
        "candidate_id": candidate_id,
        "case_id": docket.docket_id,
        "court": court,
        "docket_number": docket_number,
        "case_name": caption,
        "decision_date": _required_str(
            screened_case_record,
            "first_written_mtd_disposition_date",
        ),
        "eligibility_anchor_date": _required_str(
            screened_case_record,
            "eligibility_anchor_date",
        ),
        "source_url": source_url,
        **case_mix,
        "selected": True,
        "exclusion_reasons": [],
        "target_motion_entry_numbers": list(
            _entry_numbers(
                _mapping(screened_case_record.get("ai"), "ai").get(
                    "target_motion_entry_numbers"
                )
            )
        ),
        "decision_entry_numbers": list(
            _entry_numbers(
                _mapping(screened_case_record.get("ai"), "ai").get(
                    "decision_entry_numbers"
                )
            )
        ),
        "identity_resolution": identity_resolution,
        "documents": [document.selection_record() for document in documents],
    }
    relevance = {
        "candidate_id": candidate_id,
        "courtlistener_docket_id": docket.docket_id,
        "documents": [document.case_relevance_record() for document in documents],
    }
    return _reconcile_paid_gap(
        paid_gap_record,
        bridged_selection=selection,
        bridged_relevance=relevance,
    )


def bridge_free_download_requests_from_selection(
    selection_record: Mapping[str, Any],
) -> tuple[FreeDocumentDownloadRequest, ...]:
    """Return only authoritative documents newly recovered from a paid gap."""

    candidate_id = _required_str(selection_record, "candidate_id")
    requests: list[FreeDocumentDownloadRequest] = []
    seen_ids: set[str] = set()
    for document in _mapping_sequence(selection_record.get("documents"), "documents"):
        if document.get("resolved_from_paid_gap") is not True:
            continue
        if (
            document.get("availability_status") == "unavailable"
            and document.get("requires_paid_recovery") is True
        ):
            continue
        restriction_evidence = _string_sequence(document.get("restriction_evidence"))
        rest_evidence_valid = (
            restriction_evidence == _COURTLISTENER_REST_FREE_RESTRICTION_EVIDENCE
            and document.get("is_sealed") is False
        )
        case_dev_evidence_valid = (
            restriction_evidence == _CASE_DEV_FREE_RESTRICTION_EVIDENCE
            and document.get("is_sealed") is None
        )
        if (
            document.get("availability_status") != "available"
            or document.get("requires_paid_recovery") is not False
            or _required_str(document, "source_provider") != "courtlistener"
            or document.get("redaction_or_seal_status") != "public"
            or not (rest_evidence_valid or case_dev_evidence_valid)
        ):
            raise CourtListenerCaseDevBridgeError(
                f"bridge_free_document_evidence_invalid: {candidate_id}"
            )
        source_document_id = _required_str(document, "source_document_id")
        if source_document_id in seen_ids:
            raise CourtListenerCaseDevBridgeError(
                f"bridge_free_document_duplicate: {candidate_id}/{source_document_id}"
            )
        seen_ids.add(source_document_id)
        entry_number = document.get("docket_entry_number")
        if not isinstance(entry_number, int) or isinstance(entry_number, bool):
            raise CourtListenerCaseDevBridgeError(
                "bridge_free_document_entry_invalid: "
                f"{candidate_id}/{source_document_id}"
            )
        source_url = _required_str(document, "source_url")
        if (
            public_recap_download_url(source_url) != source_url
            or _required_str(document, "source_url_or_reference") != source_url
            or _required_str(document, "file_extension").lower() != "pdf"
        ):
            raise CourtListenerCaseDevBridgeError(
                f"bridge_free_document_url_invalid: {candidate_id}/{source_document_id}"
            )
        role_value = _required_str(document, "document_role")
        try:
            document_role = DocumentRole(role_value)
        except ValueError as exc:
            raise CourtListenerCaseDevBridgeError(
                "bridge_free_document_role_invalid: "
                f"{candidate_id}/{source_document_id}/{role_value}"
            ) from exc
        requests.append(
            FreeDocumentDownloadRequest(
                candidate_id=candidate_id,
                source_provider="courtlistener",
                source_document_id=source_document_id,
                docket_entry_number=entry_number,
                document_role=document_role,
                source_url=source_url,
                file_extension="pdf",
            )
        )
    return tuple(requests)


def case_dev_bridge_exclusion_record(
    screened_case_record: Mapping[str, Any],
    *,
    reason: str,
    detail: str,
) -> Mapping[str, Any]:
    """Build the canonical fail-closed bridge exclusion ledger record."""

    return _exclusion(screened_case_record, reason, detail=detail)


def validate_public_plan_bridge_inputs(
    *,
    public_selection_records: Iterable[Mapping[str, Any]],
    paid_gap_records: Iterable[Mapping[str, Any]],
    free_download_records: Iterable[Mapping[str, Any]],
) -> None:
    """Fail closed on corruption shared by all public-first bridge routes."""

    public_selections = tuple(public_selection_records)
    paid_gaps = tuple(paid_gap_records)
    _validate_public_plan_routes(public_selections, paid_gaps)
    _validate_free_download_completion(
        (*public_selections, *paid_gaps),
        tuple(free_download_records),
    )


def _validate_public_plan_routes(
    public_selections: tuple[Mapping[str, Any], ...],
    paid_gaps: tuple[Mapping[str, Any], ...],
) -> None:
    selected_ids: set[str] = set()
    for record in public_selections:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in selected_ids:
            raise CourtListenerCaseDevBridgeError(
                f"public_selection_duplicate: {candidate_id}"
            )
        selected_ids.add(candidate_id)
        if record.get("selected") is not True or record.get(
            "paid_recovery_required"
        ) not in (None, False):
            raise CourtListenerCaseDevBridgeError(
                f"public_selection_route_invalid: {candidate_id}"
            )
        if _string_sequence(record.get("exclusion_reasons")):
            raise CourtListenerCaseDevBridgeError(
                f"public_selection_has_exclusion: {candidate_id}"
            )
    gap_ids: set[str] = set()
    for record in paid_gaps:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in gap_ids:
            raise CourtListenerCaseDevBridgeError(f"paid_gap_duplicate: {candidate_id}")
        gap_ids.add(candidate_id)
        reasons = _string_sequence(record.get("paid_gap_reasons"))
        if (
            record.get("selected") is not False
            or record.get("paid_recovery_required") is not True
            or not reasons
            or _string_sequence(record.get("exclusion_reasons"))
        ):
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_route_invalid: {candidate_id}"
            )
        unsupported = {
            reason
            for reason in reasons
            if _paid_gap_reason_base_or_none(reason) is None
        }
        if unsupported:
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_reason_unsupported: {candidate_id}: "
                + ", ".join(sorted(unsupported))
            )
    overlap = selected_ids & gap_ids
    if overlap:
        raise CourtListenerCaseDevBridgeError(
            "public_route_overlap: " + ", ".join(sorted(overlap))
        )


def _validate_free_download_completion(
    plan_records: tuple[Mapping[str, Any], ...],
    download_records: tuple[Mapping[str, Any], ...],
) -> None:
    required = {
        (
            _required_str(plan, "candidate_id"),
            _required_str(document, "source_document_id"),
        )
        for plan in plan_records
        for document in _mapping_sequence(plan.get("documents"), "documents")
    }
    downloaded: set[tuple[str, str]] = set()
    for record in download_records:
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        )
        if key in downloaded:
            raise CourtListenerCaseDevBridgeError(
                f"free_download_duplicate: {key[0]}/{key[1]}"
            )
        _required_str(record, "local_path")
        sha256 = _required_str(record, "sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise CourtListenerCaseDevBridgeError(
                f"free_download_sha256_invalid: {key[0]}/{key[1]}"
            )
        if _required_str(record, "free_or_purchased") != "free":
            raise CourtListenerCaseDevBridgeError(
                f"free_download_provenance_invalid: {key[0]}/{key[1]}"
            )
        downloaded.add(key)
    missing = sorted(required - downloaded)
    if missing:
        sample = ", ".join(f"{candidate}/{document}" for candidate, document in missing)
        raise CourtListenerCaseDevBridgeError(
            f"free_download_manifest_incomplete: {sample}"
        )


def _reconcile_paid_gap(
    gap: Mapping[str, Any],
    *,
    bridged_selection: Mapping[str, Any],
    bridged_relevance: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    candidate_id = _required_str(gap, "candidate_id")
    reasons = _string_sequence(gap.get("paid_gap_reasons"))
    required_roles = {
        role
        for reason in reasons
        for role in _PAID_GAP_ROLES[_paid_gap_reason_base(reason)]
    }
    bridged_documents = _mapping_sequence(
        bridged_selection.get("documents"), "documents"
    )
    resolved_documents = tuple(
        document
        for document in bridged_documents
        if DocumentRole(_required_str(document, "document_role")) in required_roles
        and document.get("resolved_from_paid_gap") is True
    )
    for reason in reasons:
        required_entry_number = _paid_gap_reason_entry_number(reason)
        matching_resolved_document = any(
            DocumentRole(_required_str(document, "document_role"))
            in _PAID_GAP_ROLES[_paid_gap_reason_base(reason)]
            and (
                required_entry_number is None
                or document.get("docket_entry_number") == required_entry_number
            )
            for document in resolved_documents
        )
        if not matching_resolved_document:
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_document_not_found: {candidate_id}: {reason}"
            )
    public_documents = _mapping_sequence(gap.get("documents"), "documents")
    document_ids = {
        _required_str(document, "source_document_id") for document in public_documents
    }
    for document in resolved_documents:
        document_id = _required_str(document, "source_document_id")
        if document_id in document_ids:
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_document_id_conflict: {candidate_id}/{document_id}"
            )
        document_ids.add(document_id)
    relevance_by_id = {
        _required_str(document, "source_document_id"): document
        for document in _mapping_sequence(
            bridged_relevance.get("documents"), "documents"
        )
    }
    resolved_relevance = tuple(
        relevance_by_id[_required_str(document, "source_document_id")]
        for document in resolved_documents
    )
    paid_documents = tuple(
        document
        for document in resolved_documents
        if document.get("requires_paid_recovery") is True
    )
    paid_recovery_required = bool(paid_documents)
    selection = {
        **gap,
        "case_id": _required_str(bridged_selection, "case_id"),
        "selected": True,
        "exclusion_reasons": [],
        # Identity resolution makes the candidate purchasable; it does not
        # recover document bytes. Keep the legacy selected route for downstream
        # selection compatibility while stating recovery readiness explicitly.
        "paid_recovery_required": paid_recovery_required,
        "paid_gap_reasons": [],
        "resolved_paid_gap_reasons": list(reasons),
        "planning_status": (
            "identity_resolved_paid_recovery_required"
            if paid_recovery_required
            else "free_recovery_required"
        ),
        "identity_resolution_status": "resolved",
        "document_recovery_status": (
            "paid_recovery_required"
            if paid_recovery_required
            else "free_recovery_required"
        ),
        "identity_resolution": bridged_selection["identity_resolution"],
        "documents": [*public_documents, *resolved_documents],
    }
    identity_fields: dict[str, str] = {}
    for field_name in ("case_dev_case_id", "courtlistener_docket_id"):
        value = _optional_str(bridged_relevance, field_name)
        if value is not None:
            identity_fields[field_name] = value
    if not identity_fields:
        raise CourtListenerCaseDevBridgeError(
            f"paid_gap_identity_provenance_missing: {candidate_id}"
        )
    case_relevance = {
        "candidate_id": candidate_id,
        **identity_fields,
        "documents": [
            *(_public_relevance_document(document) for document in public_documents),
            *resolved_relevance,
        ],
    }
    return selection, case_relevance


def _paid_gap_reason_base_or_none(reason: str) -> str | None:
    base, separator, suffix = reason.partition(":")
    if base not in _PAID_GAP_ROLES:
        return None
    if separator and not (
        suffix == "unknown_entry" or (suffix.isdecimal() and int(suffix) > 0)
    ):
        return None
    return base


def _paid_gap_reason_base(reason: str) -> str:
    base = _paid_gap_reason_base_or_none(reason)
    if base is None:
        raise CourtListenerCaseDevBridgeError(f"paid_gap_reason_unsupported: {reason}")
    return base


def _paid_gap_reason_entry_number(reason: str) -> int | None:
    _, separator, suffix = reason.partition(":")
    if not separator or suffix == "unknown_entry":
        return None
    return int(suffix)


def _public_relevance_document(document: Mapping[str, Any]) -> Mapping[str, Any]:
    role = DocumentRole(_required_str(document, "document_role"))
    model_visible = document.get("model_visible") is True
    restriction_markers = restricted_material_markers(
        records=(document,),
        text_fields=(
            _optional_str(document, "description") or "",
            _optional_str(document, "docket_entry_text") or "",
        ),
    )
    status = "restricted" if restriction_markers else "public"
    evidence = (
        tuple(f"marker:{marker}" for marker in restriction_markers)
        if restriction_markers
        else ("courtlistener_public_download_record_checked",)
    )
    return {
        "source_document_id": _required_str(document, "source_document_id"),
        "setup_runner_label": "core_mtd" if model_visible else "other_substantive",
        "document_role": role.value,
        "docket_entry_number": document.get("docket_entry_number"),
        "docket_entry_text": _optional_str(document, "description"),
        "source_url_or_reference": _required_str(document, "source_url"),
        "availability_status": "available",
        "requires_paid_recovery": False,
        "redaction_or_seal_status": status,
        "restriction_evidence": list(evidence),
        "is_private": document.get("is_private") is True,
        "is_sealed": document.get("is_sealed") is True or bool(restriction_markers),
        "contains_target_outcome": document.get("contains_target_outcome") is True,
        "model_visible": model_visible,
    }


def _public_case_relevance(selection: Mapping[str, Any]) -> Mapping[str, Any]:
    """Project a fully-free public selection into the relevance schema."""

    return {
        "candidate_id": _required_str(selection, "candidate_id"),
        "documents": [
            _public_relevance_document(document)
            for document in _mapping_sequence(selection.get("documents"), "documents")
        ],
    }


def merge_download_manifest_records(
    manifest_groups: Iterable[Iterable[Mapping[str, Any]]],
) -> tuple[Mapping[str, Any], ...]:
    """Merge free and purchased downloads into one parser-consumable manifest."""

    merged: list[Mapping[str, Any]] = []
    seen: dict[tuple[str, str], Mapping[str, Any]] = {}
    for group in manifest_groups:
        for record in group:
            candidate_id = _required_str(record, "candidate_id")
            document_id = _required_str(record, "source_document_id")
            key = (candidate_id, document_id)
            existing = seen.get(key)
            if existing is not None:
                if dict(existing) == dict(record):
                    continue
                raise CourtListenerCaseDevBridgeError(
                    "download_manifest_conflict: conflicting records for "
                    f"{candidate_id}/{document_id}"
                )
            _required_str(record, "local_path")
            _required_str(record, "sha256")
            seen[key] = record
            merged.append(record)
    return tuple(merged)


def _bridge_candidate(
    record: Mapping[str, Any],
    *,
    client: CaseDevClient,
    raw_html_dir: Path | None,
    use_embedded_entries: bool,
    paid_gap_reasons: tuple[str, ...] = (),
) -> tuple[
    Mapping[str, Any], Mapping[str, Any], tuple[FreeDocumentDownloadRequest, ...]
]:
    candidate = _mapping(record.get("candidate"), "candidate")
    metadata = _mapping(candidate.get("metadata"), "candidate.metadata")
    candidate_id = _required_str_any(candidate, "docket_id", "candidate_key")
    court = _required_str(metadata, "court")
    docket_number = _required_str(metadata, "docket_number")
    caption = _required_str(metadata, "case_name")
    source_url = _optional_str(candidate, "url")
    source_docket_id = _courtlistener_docket_id_from_url(source_url)
    if (
        candidate_id.isdecimal()
        and source_docket_id is not None
        and source_docket_id != candidate_id
    ):
        raise CourtListenerCaseDevBridgeError("courtlistener_source_id_conflict")
    page = _courtlistener_page(
        record,
        candidate_id=candidate_id,
        source_url=source_url,
        raw_html_dir=raw_html_dir,
        use_embedded_entries=use_embedded_entries,
    )
    if page.has_next_page:
        raise CourtListenerCaseDevBridgeError("courtlistener_docket_more_than_one_page")

    matched_case_id, case_dev_entries, matched_by = _resolve_case_dev_docket(
        client,
        candidate_id=candidate_id,
        court=court,
        docket_number=docket_number,
        caption=caption,
    )
    documents = _bridge_documents(
        record,
        page=page,
        case_dev_entries=case_dev_entries,
        candidate_id=candidate_id,
        paid_gap_reasons=paid_gap_reasons,
    )
    case_mix = _case_mix_metadata(record, candidate=candidate, metadata=metadata)
    selection = {
        "candidate_id": candidate_id,
        "case_id": matched_case_id,
        "court": court,
        "docket_number": docket_number,
        "case_name": caption,
        "decision_date": _required_str(
            record,
            "first_written_mtd_disposition_date",
        ),
        "eligibility_anchor_date": _required_str(record, "eligibility_anchor_date"),
        "source_url": _optional_str(candidate, "url"),
        **case_mix,
        "selected": True,
        "exclusion_reasons": [],
        "target_motion_entry_numbers": list(
            _entry_numbers(
                _mapping(record.get("ai"), "ai").get("target_motion_entry_numbers")
            )
        ),
        "decision_entry_numbers": list(
            _entry_numbers(
                _mapping(record.get("ai"), "ai").get("decision_entry_numbers")
            )
        ),
        "identity_resolution": {
            "courtlistener_candidate_id": candidate_id,
            "case_dev_case_id": matched_case_id,
            "matched_by": matched_by,
        },
        "documents": [document.selection_record() for document in documents],
    }
    case_relevance = {
        "candidate_id": candidate_id,
        "case_dev_case_id": matched_case_id,
        "documents": [document.case_relevance_record() for document in documents],
    }
    requests = tuple(
        request
        for document in documents
        if (request := document.free_download_request()) is not None
    )
    return selection, case_relevance, requests


def _case_mix_metadata(
    record: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> Mapping[str, str | None]:
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


def _resolve_case_dev_case_id(
    client: CaseDevClient,
    *,
    court: str,
    docket_number: str,
    caption: str,
) -> str:
    page = client.search_docket_entries(docket_number, limit=_CASE_DEV_SEARCH_LIMIT)
    exact_court_docket: list[CaseDevDocketHit] = []
    corroborated: list[CaseDevDocketHit] = []
    for hit in page.items:
        docket = _mapping(hit.raw.get("legal_docket"), "legal_docket")
        hit_court = _optional_str_any(docket, "courtId", "court_id", "court")
        hit_docket = _optional_str_any(
            docket,
            "docketNumber",
            "docket_number",
            "case_number",
        )
        if (
            hit_court is None
            or hit_docket is None
            or _identifier(hit_court) != _identifier(court)
            or _docket_identifier(hit_docket) != _docket_identifier(docket_number)
        ):
            continue
        exact_court_docket.append(hit)
        hit_caption = _optional_str_any(docket, "caseName", "caption", "name")
        if hit_caption is not None and _caption(hit_caption) == _caption(caption):
            corroborated.append(hit)
    if not exact_court_docket:
        raise CourtListenerCaseDevBridgeError("case_dev_exact_match_not_found")
    if not corroborated:
        raise CourtListenerCaseDevBridgeError("case_dev_caption_conflict")
    unique_ids = {hit.case_id for hit in corroborated}
    if len(unique_ids) != 1:
        raise CourtListenerCaseDevBridgeError("case_dev_exact_match_ambiguous")
    return next(iter(unique_ids))


def _resolve_case_dev_docket(
    client: CaseDevClient,
    *,
    candidate_id: str,
    court: str,
    docket_number: str,
    caption: str,
) -> tuple[str, tuple[CaseDevDocketHit, ...], str]:
    if candidate_id.isdecimal():
        docket, entries = _lookup_case_dev_docket_entries(
            client,
            candidate_id,
        )
        _corroborate_case_dev_docket(
            docket,
            expected_case_id=candidate_id,
            court=court,
            docket_number=docket_number,
            caption=caption,
        )
        return (
            candidate_id,
            entries,
            "direct_numeric_id_exact_court_docket_caption",
        )

    case_id = _resolve_case_dev_case_id(
        client,
        court=court,
        docket_number=docket_number,
        caption=caption,
    )
    docket, entries = _lookup_case_dev_docket_entries(
        client,
        case_id,
    )
    _corroborate_case_dev_docket(
        docket,
        expected_case_id=case_id,
        court=court,
        docket_number=docket_number,
        caption=caption,
    )
    return case_id, entries, "exact_court_docket_caption"


def _lookup_case_dev_docket_entries(
    client: CaseDevClient,
    case_id: str,
) -> tuple[Mapping[str, Any], tuple[CaseDevDocketHit, ...]]:
    cursor: str | None = None
    seen_cursors: set[str] = set()
    docket_metadata: Mapping[str, Any] | None = None
    entries: list[CaseDevDocketHit] = []
    while True:
        page = client.get_case_docket_entries(
            case_id,
            cursor=cursor,
            limit=_CASE_DEV_DOCKET_PAGE_SIZE,
        )
        current_docket = _mapping(page.raw.get("docket", page.raw), "legal_docket")
        if docket_metadata is None:
            docket_metadata = current_docket
        elif dict(current_docket) != dict(docket_metadata):
            current_without_entries = {
                key: value for key, value in current_docket.items() if key != "entries"
            }
            original_without_entries = {
                key: value for key, value in docket_metadata.items() if key != "entries"
            }
            if current_without_entries != original_without_entries:
                raise CourtListenerCaseDevBridgeError(
                    "case_dev_pagination_metadata_conflict"
                )
        entries.extend(page.items)
        next_cursor = page.next_cursor
        if next_cursor is None:
            if len(page.items) >= _CASE_DEV_DOCKET_PAGE_SIZE:
                raise CourtListenerCaseDevBridgeError(
                    "case_dev_pagination_exhaustion_unproven"
                )
            return docket_metadata, tuple(entries)
        if next_cursor in seen_cursors:
            raise CourtListenerCaseDevBridgeError("case_dev_pagination_cursor_cycle")
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def _corroborate_case_dev_docket(
    docket: Mapping[str, Any],
    *,
    expected_case_id: str,
    court: str,
    docket_number: str,
    caption: str,
) -> None:
    hit_id = _optional_str_any(docket, "id", "docketId", "docket_id")
    hit_court = _optional_str_any(docket, "courtId", "court_id", "court")
    hit_docket = _optional_str_any(
        docket,
        "docketNumber",
        "docket_number",
        "case_number",
    )
    hit_caption = _optional_str_any(docket, "caseName", "caption", "name")
    if hit_id is None or hit_id != expected_case_id:
        raise CourtListenerCaseDevBridgeError("case_dev_direct_id_conflict")
    if (
        hit_court is None
        or hit_docket is None
        or _identifier(hit_court) != _identifier(court)
        or _docket_identifier(hit_docket) != _docket_identifier(docket_number)
    ):
        raise CourtListenerCaseDevBridgeError("case_dev_exact_match_not_found")
    if hit_caption is None or _caption(hit_caption) != _caption(caption):
        raise CourtListenerCaseDevBridgeError("case_dev_caption_conflict")


def _corroborate_courtlistener_docket(
    *,
    docket_id: str,
    hit_court: str | None,
    hit_docket: str | None,
    hit_caption: str,
    expected_id: str,
    court: str,
    docket_number: str,
    caption: str,
) -> None:
    if docket_id != expected_id:
        raise CourtListenerCaseDevBridgeError("courtlistener_direct_id_conflict")
    if (
        hit_court is None
        or hit_docket is None
        or _identifier(hit_court) != _identifier(court)
        or _docket_identifier(hit_docket) != _docket_identifier(docket_number)
    ):
        raise CourtListenerCaseDevBridgeError("courtlistener_exact_match_not_found")
    if _caption(hit_caption) != _caption(caption):
        raise CourtListenerCaseDevBridgeError("courtlistener_caption_conflict")


def _bridge_courtlistener_rest_gap_documents(
    record: Mapping[str, Any],
    *,
    page: CourtListenerWebDocketPage,
    rest_entries: tuple[CourtListenerDocketEntry, ...],
    client: CourtListenerClient,
    candidate_id: str,
    paid_gap_reasons: tuple[str, ...],
) -> tuple[_CourtListenerRestGapDocument, ...]:
    requested = _requested_paid_gap_entries(
        record,
        page=page,
        paid_gap_reasons=paid_gap_reasons,
    )
    by_number: dict[int, list[CourtListenerDocketEntry]] = {}
    for entry in rest_entries:
        number = _positive_entry_number(entry.entry_number)
        if number is not None:
            by_number.setdefault(number, []).append(entry)

    bridged: list[_CourtListenerRestGapDocument] = []
    seen_document_ids: set[str] = set()
    for web_entry, role in requested:
        number = cast(int, _positive_entry_number(web_entry.entry_number))
        hits = by_number.get(number, [])
        if not hits:
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_entry_not_found: {number}"
            )
        if any(hit.docket_id != candidate_id for hit in hits):
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_entry_docket_conflict: {number}"
            )
        if len(hits) != 1:
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_entry_ambiguous: {number}"
            )
        hit = hits[0]
        if hit.entry_text and _text_key(hit.entry_text) != _text_key(web_entry.text):
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_entry_text_conflict: {number}"
            )
        if (
            hit.filed_at is not None
            and web_entry.filed_at is not None
            and not _same_filed_date(hit.filed_at, web_entry.filed_at)
        ):
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_entry_date_conflict: {number}"
            )
        web_document = _select_courtlistener_document(web_entry, role)
        if web_document.freely_available:
            raise CourtListenerCaseDevBridgeError(
                f"paid_gap_public_document_conflict: {number}"
            )
        recap_document, public_download_url = _select_courtlistener_recap_document(
            client,
            hit=hit,
            entry_number=number,
            web_document=web_document,
        )
        if recap_document.document_id in seen_document_ids:
            continue
        seen_document_ids.add(recap_document.document_id)
        description = (
            web_document.description
            or recap_document.description
            or web_entry.text
            or hit.entry_text
        )
        bridged.append(
            _CourtListenerRestGapDocument(
                candidate_id=candidate_id,
                source_document_id=recap_document.document_id,
                docket_entry_id=hit.docket_entry_id,
                docket_entry_number=number,
                document_role=role,
                source_url_or_reference=public_download_url
                or (
                    "https://www.courtlistener.com/api/rest/v4/recap-documents/"
                    f"{recap_document.document_id}/"
                ),
                description=description,
                free=public_download_url is not None,
            )
        )
    return tuple(bridged)


def _same_filed_date(first: str, second: str) -> bool:
    """Compare REST ISO dates with either scraped or reconstructed web dates."""

    first_date = _normalized_filed_date(first)
    second_date = _normalized_filed_date(second)
    if first_date is None or second_date is None:
        return first.strip() == second.strip()
    return first_date == second_date


def _normalized_filed_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        pass
    for date_format in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    return None


def _select_courtlistener_recap_document(
    client: CourtListenerClient,
    *,
    hit: CourtListenerDocketEntry,
    entry_number: int,
    web_document: CourtListenerWebDocument,
) -> tuple[CourtListenerRecapDocument, str | None]:
    if not hit.recap_document_ids:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_recap_document_id_missing: {entry_number}"
        )
    matching_documents: list[CourtListenerRecapDocument] = []
    for expected_document_id in hit.recap_document_ids:
        document = client.get_recap_document(expected_document_id)
        if document.document_id != expected_document_id:
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_recap_document_id_conflict: {entry_number}"
            )
        if document.docket_entry_id != hit.docket_entry_id:
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_recap_entry_conflict: {entry_number}"
            )
        if (
            document.document_number is not None
            and _positive_entry_number(document.document_number) != entry_number
        ):
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_recap_document_number_conflict: {entry_number}"
            )
        if _recap_document_matches_web_document(web_document, document):
            matching_documents.append(document)
    if not matching_documents:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_recap_document_match_not_found: {entry_number}"
        )
    if len(matching_documents) != 1:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_recap_document_match_ambiguous: {entry_number}"
        )
    selected = matching_documents[0]
    if selected.is_sealed is True or _record_is_restricted(selected.raw):
        raise CourtListenerCaseDevBridgeError(
            f"restricted_core_document: {entry_number}"
        )
    if selected.is_sealed is not False:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_recap_privacy_unproven: {entry_number}"
        )
    if selected.is_available is True:
        raw_url = _optional_str_any(
            selected.raw,
            "filepath_local",
            "download_url",
        )
        public_url = None if raw_url is None else public_recap_download_url(raw_url)
        if public_url is None:
            raise CourtListenerCaseDevBridgeError(
                f"courtlistener_recap_public_url_unproven: {entry_number}"
            )
        return selected, public_url
    if selected.is_available is not False:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_recap_availability_unproven: {entry_number}"
        )
    return selected, None


def _recap_document_matches_web_document(
    web_document: CourtListenerWebDocument,
    recap_document: CourtListenerRecapDocument,
) -> bool:
    if _text_key(web_document.description) != _text_key(
        recap_document.description or ""
    ):
        return False
    kind = _text_key(web_document.kind)
    if "main" in kind:
        return recap_document.attachment_number is None
    if "attachment" not in kind:
        return True
    if recap_document.attachment_number is None:
        return False
    stated_numbers = tuple(re.findall(r"\d+", kind))
    return not stated_numbers or recap_document.attachment_number in stated_numbers


def _requested_paid_gap_entries(
    record: Mapping[str, Any],
    *,
    page: CourtListenerWebDocketPage,
    paid_gap_reasons: tuple[str, ...],
) -> tuple[tuple[CourtListenerWebDocketEntry, DocumentRole], ...]:
    ai = _mapping(record.get("ai"), "ai")
    target_numbers = _entry_numbers(ai.get("target_motion_entry_numbers"))
    decision_numbers = _entry_numbers(ai.get("decision_entry_numbers"))
    if not target_numbers:
        raise CourtListenerCaseDevBridgeError("target_motion_entry_numbers_missing")
    if not decision_numbers:
        raise CourtListenerCaseDevBridgeError("decision_entry_numbers_missing")
    decision_floor = min(decision_numbers)
    numbered_entries = {
        number: entry
        for entry in page.entries
        if (number := _positive_entry_number(entry.entry_number)) is not None
    }
    requested: dict[int, tuple[CourtListenerWebDocketEntry, DocumentRole]] = {}
    for reason in paid_gap_reasons:
        base = _paid_gap_reason_base(reason)
        explicit_number = _paid_gap_reason_entry_number(reason)
        if base == "no_free_operative_complaint":
            complaint = select_operative_complaint_entry(
                numbered_entries.values(),
                before_entry=min(target_numbers),
            )
            if complaint is None:
                raise CourtListenerCaseDevBridgeError("operative_complaint_not_found")
            number = cast(int, _positive_entry_number(complaint.entry.entry_number))
            role = (
                DocumentRole.AMENDED_COMPLAINT
                if complaint.kind is OperativeComplaintKind.AMENDED_COMPLAINT
                else DocumentRole.COMPLAINT
            )
            requested[number] = (complaint.entry, role)
            continue
        numbers = (
            (explicit_number,)
            if explicit_number is not None
            else (
                decision_numbers
                if base == "no_free_decision_document"
                else target_numbers
            )
        )
        if base == "no_free_opposition" and explicit_number is None:
            opposition = tuple(
                (number, entry)
                for number, entry in sorted(numbered_entries.items())
                if number < decision_floor
                and entry.role is CourtListenerEntryRole.OPPOSITION
                and is_substantive_mtd_opposition_entry(entry)
                and _brief_targets_motion(entry, target_numbers)
            )
            if len(opposition) != 1:
                raise CourtListenerCaseDevBridgeError(
                    "opposition_entry_not_found"
                    if not opposition
                    else "opposition_entry_ambiguous"
                )
            numbers = (opposition[0][0],)
        for number in numbers:
            entry = numbered_entries.get(number)
            if entry is None:
                raise CourtListenerCaseDevBridgeError(
                    f"courtlistener_gap_entry_not_found: {number}"
                )
            if base == "no_free_opposition":
                role = DocumentRole.OPPOSITION
            elif base == "no_free_decision_document":
                role = DocumentRole.DECISION
            elif base == "no_free_mtd_memorandum":
                role = DocumentRole.MTD_MEMORANDUM
            else:
                existing = requested.get(number)
                role = (
                    existing[1]
                    if existing is not None
                    and existing[1] is DocumentRole.MTD_MEMORANDUM
                    else _mtd_role(entry)
                )
            requested[number] = (entry, role)
    return tuple(requested[number] for number in sorted(requested))


def _bridge_documents(
    record: Mapping[str, Any],
    *,
    page: CourtListenerWebDocketPage,
    case_dev_entries: tuple[CaseDevDocketHit, ...],
    candidate_id: str,
    paid_gap_reasons: tuple[str, ...] = (),
) -> tuple[_BridgeDocument, ...]:
    ai = _mapping(record.get("ai"), "ai")
    target_numbers = _entry_numbers(ai.get("target_motion_entry_numbers"))
    decision_numbers = _entry_numbers(ai.get("decision_entry_numbers"))
    if not target_numbers:
        raise CourtListenerCaseDevBridgeError("target_motion_entry_numbers_missing")
    if not decision_numbers:
        raise CourtListenerCaseDevBridgeError("decision_entry_numbers_missing")
    decision_floor = min(decision_numbers)

    numbered_entries = {
        number: entry
        for entry in page.entries
        if (number := _positive_entry_number(entry.entry_number)) is not None
    }
    requested: list[tuple[CourtListenerWebDocketEntry, DocumentRole]] = []
    required_gap_roles = {
        role
        for reason in paid_gap_reasons
        for role in _PAID_GAP_ROLES[_paid_gap_reason_base(reason)]
    }
    needs_complaint = not paid_gap_reasons or bool(
        required_gap_roles & {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}
    )
    needs_target_mtd = not paid_gap_reasons or bool(
        required_gap_roles & {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}
    )
    needs_opposition = DocumentRole.OPPOSITION in required_gap_roles
    needs_decision = not paid_gap_reasons or DocumentRole.DECISION in required_gap_roles
    if needs_complaint:
        complaint_selection = select_operative_complaint_entry(
            numbered_entries.values(),
            before_entry=min(target_numbers),
        )
        if complaint_selection is None:
            raise CourtListenerCaseDevBridgeError("operative_complaint_not_found")
        requested.append(
            (
                complaint_selection.entry,
                DocumentRole.AMENDED_COMPLAINT
                if complaint_selection.kind is OperativeComplaintKind.AMENDED_COMPLAINT
                else DocumentRole.COMPLAINT,
            )
        )
    if needs_target_mtd:
        numbered_target_gaps = _numbered_gap_entries(
            paid_gap_reasons,
            "no_free_target_mtd_document",
        )
        required_target_numbers = numbered_target_gaps or target_numbers
        for number in required_target_numbers:
            entry = numbered_entries.get(number)
            if entry is None:
                raise CourtListenerCaseDevBridgeError(
                    f"target_motion_entry_not_found: {number}"
                )
            requested.append(
                (
                    entry,
                    DocumentRole.MTD_MEMORANDUM
                    if paid_gap_reasons
                    and DocumentRole.MTD_MEMORANDUM in required_gap_roles
                    else _mtd_role(entry),
                )
            )
    if needs_opposition:
        numbered_oppositions = tuple(
            sorted(
                number
                for reason in paid_gap_reasons
                if _paid_gap_reason_base(reason) == "no_free_opposition"
                if (number := _paid_gap_reason_entry_number(reason)) is not None
            )
        )
        if numbered_oppositions:
            for number in numbered_oppositions:
                entry = numbered_entries.get(number)
                if (
                    entry is None
                    or number >= decision_floor
                    or not is_substantive_mtd_opposition_entry(entry)
                    or not _brief_targets_motion(entry, target_numbers)
                ):
                    raise CourtListenerCaseDevBridgeError(
                        f"opposition_entry_not_found: {number}"
                    )
                requested.append((entry, DocumentRole.OPPOSITION))
        else:
            for target_number in sorted(target_numbers):
                upper_bound = min(
                    (
                        *(
                            number
                            for number in target_numbers
                            if number > target_number
                        ),
                        decision_floor,
                    )
                )
                linked = tuple(
                    entry
                    for number, entry in sorted(numbered_entries.items())
                    if target_number < number < upper_bound
                    and entry.role is CourtListenerEntryRole.OPPOSITION
                    and is_substantive_mtd_opposition_entry(entry)
                    and _brief_targets_motion(entry, target_numbers)
                )
                if not linked:
                    raise CourtListenerCaseDevBridgeError(
                        f"opposition_entry_not_found: {target_number}"
                    )
                # Without an entry-qualified gap, the first substantive linked
                # opposition in the target-motion interval is the only safe choice.
                requested.append((linked[0], DocumentRole.OPPOSITION))
    if not paid_gap_reasons:
        for number, entry in sorted(numbered_entries.items()):
            if number >= decision_floor:
                continue
            if entry.role is CourtListenerEntryRole.OPPOSITION:
                if is_substantive_mtd_opposition_entry(entry):
                    requested.append((entry, DocumentRole.OPPOSITION))
            elif entry.role is CourtListenerEntryRole.REPLY and any(
                document.freely_available for document in entry.documents
            ):
                requested.append((entry, DocumentRole.REPLY))
    if needs_decision:
        numbered_decision_gaps = _numbered_gap_entries(
            paid_gap_reasons,
            "no_free_decision_document",
        )
        required_decision_numbers = numbered_decision_gaps or decision_numbers
        for number in required_decision_numbers:
            entry = numbered_entries.get(number)
            if entry is None:
                raise CourtListenerCaseDevBridgeError(
                    f"decision_entry_not_found: {number}"
                )
            requested.append((entry, DocumentRole.DECISION))

    by_entry_number: dict[int, list[CaseDevDocketHit]] = {}
    for hit in case_dev_entries:
        number = _positive_entry_number(hit.entry_number)
        if number is not None:
            by_entry_number.setdefault(number, []).append(hit)

    documents: list[_BridgeDocument] = []
    seen: set[str] = set()
    for entry, role in requested:
        if role not in _RECOVERABLE_ROLES:
            continue
        number = cast(int, _positive_entry_number(entry.entry_number))
        hits = by_entry_number.get(number, [])
        if len(hits) != 1:
            reason = (
                "case_dev_entry_not_found" if not hits else "case_dev_entry_ambiguous"
            )
            raise CourtListenerCaseDevBridgeError(f"{reason}: {number}")
        courtlistener_document = _select_courtlistener_document(entry, role)
        case_dev_document = _select_case_dev_document(
            hits[0],
            courtlistener_document=courtlistener_document,
            role=role,
        )
        if _record_is_restricted(hits[0].raw) or _record_is_restricted(
            case_dev_document
        ):
            raise CourtListenerCaseDevBridgeError(f"restricted_core_document: {number}")
        document_id = _required_str(case_dev_document, "id")
        if document_id in seen:
            continue
        seen.add(document_id)
        source_reference = courtlistener_document.href
        if source_reference is None:
            source_reference = f"case.dev://document/{document_id}"
        documents.append(
            _BridgeDocument(
                candidate_id=candidate_id,
                source_document_id=document_id,
                case_dev_entry_id=hits[0].docket_entry_id,
                docket_entry_number=number,
                document_role=role,
                source_url_or_reference=source_reference,
                description=(
                    courtlistener_document.description
                    or _optional_str(case_dev_document, "description")
                    or entry.text
                ),
                free=courtlistener_document.freely_available,
                restriction_evidence=(
                    "courtlistener_docket_entry_checked",
                    "case_dev_entry_and_document_checked",
                ),
            )
        )
    return tuple(documents)


def _select_courtlistener_document(
    entry: CourtListenerWebDocketEntry,
    role: DocumentRole,
) -> CourtListenerWebDocument:
    if role in {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}:
        complaint = select_operative_complaint_document(entry, require_free=False)
        if complaint is None:
            raise CourtListenerCaseDevBridgeError(
                f"operative_complaint_document_not_found: "
                f"{entry.entry_number or 'unknown'}"
            )
        return complaint
    candidates = tuple(entry.documents)
    if not candidates:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_document_not_found: {entry.entry_number or 'unknown'}"
        )
    ranked = sorted(
        candidates,
        key=lambda document: (
            -_document_role_score(document.description, role),
            0 if document.freely_available else 1,
            _text_key(document.description),
            document.href or "",
        ),
    )
    best = ranked[0]
    if _document_role_score(best.description, role) <= 0 and len(candidates) > 1:
        raise CourtListenerCaseDevBridgeError(
            f"courtlistener_document_ambiguous: {entry.entry_number or 'unknown'}"
        )
    return best


def _select_case_dev_document(
    hit: CaseDevDocketHit,
    *,
    courtlistener_document: CourtListenerWebDocument,
    role: DocumentRole,
) -> Mapping[str, Any]:
    documents = _mapping_sequence(hit.raw.get("documents"), "documents")
    if not documents:
        raise CourtListenerCaseDevBridgeError(
            f"case_dev_document_id_missing: {hit.entry_number or 'unknown'}"
        )
    if len(documents) == 1:
        _required_str(documents[0], "id")
        return documents[0]
    cl_description = _text_key(courtlistener_document.description)

    def rank(document: Mapping[str, Any]) -> tuple[int, int, str]:
        description = _optional_str(document, "description") or ""
        exact = int(bool(cl_description) and _text_key(description) == cl_description)
        kind = _optional_str_any(document, "type", "kind") or ""
        main = int("main" in _text_key(kind))
        score = exact * 1000 + main * 100 + _document_role_score(description, role)
        return score, main, _required_str(document, "id")

    ranked = sorted(documents, key=rank, reverse=True)
    best_score = rank(ranked[0])[0]
    if best_score <= 0 or sum(rank(item)[0] == best_score for item in ranked) != 1:
        raise CourtListenerCaseDevBridgeError(
            f"case_dev_document_ambiguous: {hit.entry_number or 'unknown'}"
        )
    return ranked[0]


def _courtlistener_page(
    record: Mapping[str, Any],
    *,
    candidate_id: str,
    source_url: str | None,
    raw_html_dir: Path | None,
    use_embedded_entries: bool,
) -> CourtListenerWebDocketPage:
    html_path = None if raw_html_dir is None else raw_html_dir / f"{candidate_id}.html"
    if html_path is not None and html_path.is_file():
        return parse_courtlistener_docket_html(
            html_path.read_text(encoding="utf-8"),
            source_url=source_url,
            docket_id=candidate_id,
        )
    if not use_embedded_entries:
        raise CourtListenerCaseDevBridgeError("raw_courtlistener_html_missing")
    entries = tuple(
        _embedded_entry(item)
        for item in _mapping_sequence(
            record.get("selected_entries"), "selected_entries"
        )
    )
    if not entries:
        raise CourtListenerCaseDevBridgeError("embedded_entries_missing")
    return CourtListenerWebDocketPage(
        docket_id=candidate_id,
        source_url=source_url,
        title=None,
        entries=entries,
        has_next_page=False,
    )


def _embedded_entry(record: Mapping[str, Any]) -> CourtListenerWebDocketEntry:
    return CourtListenerWebDocketEntry(
        row_id=_required_str(record, "row_id"),
        entry_number=_optional_str(record, "entry_number"),
        filed_at=_optional_str(record, "filed_at"),
        text=_required_str(record, "text"),
        documents=tuple(
            CourtListenerWebDocument(
                kind=_optional_str(document, "kind") or "",
                description=_optional_str(document, "description") or "",
                href=_optional_str(document, "href"),
                action_label=_optional_str(document, "action_label"),
                pacer_only=_optional_bool(document, "pacer_only", default=False),
            )
            for document in _mapping_sequence(record.get("documents"), "documents")
        ),
    )


def _mtd_role(entry: CourtListenerWebDocketEntry) -> DocumentRole:
    text = _text_key(
        " ".join((entry.text, *(document.description for document in entry.documents)))
    )
    return (
        DocumentRole.MTD_MEMORANDUM
        if "memorandum" in text or "brief in support" in text
        else DocumentRole.MTD_NOTICE
    )


def _document_role_score(description: str, role: DocumentRole) -> int:
    text = _text_key(description)
    if role in {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}:
        return 30 if "complaint" in text else 0
    if role in {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}:
        if "proposed order" in text:
            return -100
        return (
            40
            if "memorandum" in text or "brief in support" in text
            else 30
            if "dismiss" in text or "pleadings" in text
            else 0
        )
    if role is DocumentRole.OPPOSITION:
        return 30 if "opposition" in text or "response" in text else 0
    if role is DocumentRole.REPLY:
        return 30 if "reply" in text else 0
    if role is DocumentRole.DECISION:
        return (
            30 if any(word in text for word in ("order", "opinion", "decision")) else 0
        )
    return 0


def _record_is_restricted(record: Mapping[str, Any]) -> bool:
    if restricted_material_markers(
        records=(record,),
        text_fields=(
            _optional_str(record, "description") or "",
            _optional_str(record, "docket_entry_text") or "",
            _optional_str(record, "text") or "",
        ),
    ):
        return True
    for key, value in record.items():
        normalized_key = _identifier(str(key))
        if normalized_key in {"issealed", "isprivate", "isrestricted"} and (
            value is True or (value is not None and not isinstance(value, bool))
        ):
            return True
        if normalized_key in {
            "availabilitystatus",
            "redactionorsealstatus",
            "sealstatus",
            "privacy",
            "visibility",
        }:
            normalized_value = _text_key(str(value)).replace(" ", "_")
            if normalized_value in _RESTRICTED_STATUS_VALUES:
                return True
    return False


def _exclusion(
    record: Mapping[str, Any],
    reason: str,
    *,
    detail: str | None = None,
) -> Mapping[str, Any]:
    candidate = _mapping(record.get("candidate"), "candidate")
    metadata = _mapping(candidate.get("metadata"), "candidate.metadata")
    candidate_id = _required_str_any(candidate, "docket_id", "candidate_key")
    return {
        "candidate_id": candidate_id,
        "case_id": _optional_str(metadata, "case_id") or candidate_id,
        "court": _optional_str(metadata, "court"),
        "docket_number": _optional_str(metadata, "docket_number"),
        "decision_date": _optional_str(record, "first_written_mtd_disposition_date"),
        "stage": "retrieval",
        "primary_exclusion_reason": reason,
        "exclusion_reasons": [reason],
        "notes": detail or "CourtListener/case.dev identity bridge failed closed.",
    }


def _entry_numbers(value: object) -> tuple[int, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return ()
    numbers: list[int] = []
    for item in cast(Sequence[object], value):
        number = _positive_entry_number(item)
        if number is None:
            raise CourtListenerCaseDevBridgeError("docket_entry_number_invalid")
        if number not in numbers:
            numbers.append(number)
    return tuple(numbers)


def _brief_targets_motion(
    entry: CourtListenerWebDocketEntry,
    target_entries: tuple[int, ...],
) -> bool:
    text = " ".join(entry.text.lower().split())
    explicit_references = {
        int(match.group(1))
        for match in re.finditer(
            r"\b(?:re|regarding|opposition\s+to|motion|dkt\.?|docket|ecf\s+no\.?)"
            r"\s*(?:#|no\.?)?\s*(\d+)\b",
            text,
        )
    }
    if explicit_references:
        return bool(explicit_references.intersection(target_entries))
    return len(target_entries) <= 1


def _numbered_gap_entries(
    reasons: tuple[str, ...],
    base: str,
) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                number
                for reason in reasons
                if _paid_gap_reason_base(reason) == base
                if (number := _paid_gap_reason_entry_number(reason)) is not None
            }
        )
    )


def _courtlistener_docket_id_from_url(record_url: str | None) -> str | None:
    if record_url is None:
        return None
    match = re.search(r"/docket/(\d+)(?:/|$)", record_url)
    return match.group(1) if match else None


def _positive_entry_number(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(str(value))
    except ValueError:
        return None
    return number if number > 0 else None


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CourtListenerCaseDevBridgeError(f"{field_name}_missing")
    return cast(Mapping[str, Any], value)


def _mapping_sequence(
    value: object,
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise CourtListenerCaseDevBridgeError(f"{field_name}_missing")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise CourtListenerCaseDevBridgeError(f"{field_name}_invalid")
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _unique_records_by_candidate(
    records: Iterable[Mapping[str, Any]],
    *,
    source: str,
    nested_candidate: bool,
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if nested_candidate:
            candidate = _mapping(record.get("candidate"), "candidate")
            candidate_id = _required_str_any(candidate, "docket_id", "candidate_key")
        else:
            candidate_id = _required_str(record, "candidate_id")
        if candidate_id in indexed:
            raise CourtListenerCaseDevBridgeError(
                f"{source}_candidate_duplicate: {candidate_id}"
            )
        indexed[candidate_id] = record
    return indexed


def _string_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return ()
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise CourtListenerCaseDevBridgeError("string_sequence_invalid")
        strings.append(item.strip())
    return tuple(strings)


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = _optional_str(record, field_name)
    if value is None:
        raise CourtListenerCaseDevBridgeError(f"{field_name}_missing")
    return value


def _required_str_any(record: Mapping[str, Any], *field_names: str) -> str:
    value = _optional_str_any(record, *field_names)
    if value is None:
        raise CourtListenerCaseDevBridgeError(f"{field_names[0]}_missing")
    return value


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CourtListenerCaseDevBridgeError(f"{field_name}_invalid")
    return value.strip() or None


def _optional_str_any(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = _optional_str(record, field_name)
        if value is not None:
            return value
    return None


def _optional_bool(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: bool,
) -> bool:
    value = record.get(field_name)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise CourtListenerCaseDevBridgeError(f"{field_name}_invalid")
    return value


def _identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _docket_identifier(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def _caption(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return " ".join("v" if word in {"vs", "versus"} else word for word in words)


def _text_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))
