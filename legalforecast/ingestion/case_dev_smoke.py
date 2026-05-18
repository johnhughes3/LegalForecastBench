"""Phase 0 case.dev smoke-runner and markdown report helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevClientError,
    CaseDevDocketHit,
    CaseDevFeatureUnavailableError,
)
from legalforecast.ingestion.case_dev_config import CaseDevUsageEstimate
from legalforecast.ingestion.docket_sync import (
    DocketRetrievalPipeline,
    DocketRetrievalResult,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    OPTIMIZED_MTD_DECISION_SEARCH_TERMS,
    SECONDARY_MTD_DECISION_SEARCH_TERMS,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.selection.candidate_discovery import (
    DocketEntryRecord,
    MtdDiscoveryCandidate,
    discover_mtd_candidates,
)


def case_dev_smoke_query_terms() -> tuple[str, ...]:
    """Return the optimized decision-oriented case.dev smoke query terms."""

    return OPTIMIZED_MTD_DECISION_SEARCH_TERMS + SECONDARY_MTD_DECISION_SEARCH_TERMS


@dataclass(frozen=True, slots=True)
class CaseDevSmokeConfig:
    """Runtime knobs for a bounded Phase 0 case.dev smoke pass."""

    query_terms: tuple[str, ...] = field(default_factory=case_dev_smoke_query_terms)
    date_window_start: str | None = None
    date_window_end: str | None = None
    per_query_limit: int = 10
    candidate_retrieval_limit: int = 10
    retrieved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.query_terms:
            raise ValueError("at least one query term is required")
        if self.per_query_limit <= 0:
            raise ValueError("per_query_limit must be positive")
        if self.candidate_retrieval_limit < 0:
            raise ValueError("candidate_retrieval_limit must be nonnegative")
        start = _optional_date(self.date_window_start, "date_window_start")
        end = _optional_date(self.date_window_end, "date_window_end")
        if start is not None and end is not None and start > end:
            raise ValueError("date_window_start must be on or before date_window_end")


@dataclass(frozen=True, slots=True)
class CaseDevSmokeQuerySummary:
    query: str
    hit_count: int
    candidate_case_count: int

    def to_record(self) -> dict[str, object]:
        return {
            "query": self.query,
            "hit_count": self.hit_count,
            "candidate_case_count": self.candidate_case_count,
        }


@dataclass(frozen=True, slots=True)
class CaseDevSmokeCandidateSummary:
    candidate_id: str
    case_id: str
    trigger_terms: tuple[str, ...]
    retrieved: bool
    clean_packet_proxy: bool
    missing_document_reasons: tuple[str, ...]
    retrieval_error: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "trigger_terms": list(self.trigger_terms),
            "retrieved": self.retrieved,
            "clean_packet_proxy": self.clean_packet_proxy,
            "missing_document_reasons": list(self.missing_document_reasons),
            "retrieval_error": self.retrieval_error,
        }


@dataclass(frozen=True, slots=True)
class CaseDevSmokeResult:
    config: CaseDevSmokeConfig
    query_summaries: tuple[CaseDevSmokeQuerySummary, ...]
    candidates: tuple[CaseDevSmokeCandidateSummary, ...]
    usage: CaseDevUsageEstimate
    generated_at: datetime
    discovered_candidate_count: int
    dry_run: bool = False

    @property
    def total_hit_count(self) -> int:
        return sum(summary.hit_count for summary in self.query_summaries)

    @property
    def unique_candidate_count(self) -> int:
        return self.discovered_candidate_count

    @property
    def retrieved_candidate_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.retrieved)

    @property
    def clean_mtd_candidate_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.clean_packet_proxy)

    @property
    def missing_document_reasons(self) -> Mapping[str, int]:
        counter: Counter[str] = Counter()
        for candidate in self.candidates:
            counter.update(candidate.missing_document_reasons)
        return dict(sorted(counter.items()))

    @property
    def fallback_recommendation(self) -> str:
        if self.dry_run:
            return (
                "No live or fixture requests were executed; run with a fixture or "
                "CASE_DEV_API_KEY before making a fallback decision."
            )
        if self.clean_mtd_candidate_count == 0:
            return (
                "No clean MTD candidate survived the smoke sample; targeted fallback "
                "or query redesign appears necessary before Phase 0 reporting."
            )
        if self.missing_document_reasons:
            return (
                "case.dev produced at least one clean candidate, but missing "
                "documents indicate targeted fallback should be evaluated."
            )
        return (
            "case.dev produced clean candidates without missing-document reasons "
            "in this smoke sample; continue the Phase 0 pilot before broad claims."
        )

    def to_record(self) -> dict[str, object]:
        return {
            "date_window": _date_window_label(self.config),
            "dry_run": self.dry_run,
            "query_summaries": [
                summary.to_record() for summary in self.query_summaries
            ],
            "candidates": [candidate.to_record() for candidate in self.candidates],
            "total_hit_count": self.total_hit_count,
            "unique_candidate_count": self.unique_candidate_count,
            "retrieved_candidate_count": self.retrieved_candidate_count,
            "clean_mtd_candidate_count": self.clean_mtd_candidate_count,
            "missing_document_reasons": dict(self.missing_document_reasons),
            "request_count": self.usage.request_count,
            "estimated_cost_usd": self.usage.estimated_cost_usd,
            "fallback_recommendation": self.fallback_recommendation,
            "generated_at": _iso_datetime(self.generated_at),
        }


def plan_case_dev_smoke(config: CaseDevSmokeConfig) -> CaseDevSmokeResult:
    """Return a deterministic no-network smoke report skeleton."""

    generated_at = config.retrieved_at or datetime.now(UTC)
    return CaseDevSmokeResult(
        config=config,
        query_summaries=tuple(
            CaseDevSmokeQuerySummary(
                query=query,
                hit_count=0,
                candidate_case_count=0,
            )
            for query in config.query_terms
        ),
        candidates=(),
        usage=CaseDevUsageEstimate(request_count=0, estimated_cost_usd=None),
        generated_at=generated_at,
        discovered_candidate_count=0,
        dry_run=True,
    )


def run_case_dev_smoke(
    client: CaseDevClient,
    *,
    config: CaseDevSmokeConfig | None = None,
) -> CaseDevSmokeResult:
    """Run bounded case.dev searches and retrieve candidate dockets."""

    smoke_config = CaseDevSmokeConfig() if config is None else config
    generated_at = smoke_config.retrieved_at or datetime.now(UTC)
    hits_by_query: dict[str, tuple[CaseDevDocketHit, ...]] = {}
    all_hits: list[CaseDevDocketHit] = []
    for query in smoke_config.query_terms:
        raw_hits = tuple(
            client.iter_docket_entry_search(
                query,
                page_size=smoke_config.per_query_limit,
                max_results=smoke_config.per_query_limit,
            )
        )
        hits = _filter_search_hits_by_date_window(raw_hits, smoke_config)
        hits_by_query[query] = hits
        all_hits.extend(hits)

    unique_records = _unique_docket_records(all_hits)
    all_candidates = discover_mtd_candidates(unique_records)
    candidates_by_case_id = {
        candidate.case_id: candidate for candidate in all_candidates
    }

    query_summaries = tuple(
        CaseDevSmokeQuerySummary(
            query=query,
            hit_count=len(hits),
            candidate_case_count=len(
                {hit.case_id for hit in hits if hit.case_id in candidates_by_case_id}
            ),
        )
        for query, hits in hits_by_query.items()
    )

    pipeline = DocketRetrievalPipeline(client)
    candidate_summaries = tuple(
        _summarize_candidate(
            candidate,
            pipeline=pipeline,
            config=smoke_config,
            retrieved_at=generated_at,
        )
        for candidate in all_candidates[: smoke_config.candidate_retrieval_limit]
    )

    return CaseDevSmokeResult(
        config=smoke_config,
        query_summaries=query_summaries,
        candidates=candidate_summaries,
        usage=client.usage_estimate(),
        generated_at=generated_at,
        discovered_candidate_count=len(all_candidates),
    )


def render_case_dev_smoke_markdown(result: CaseDevSmokeResult) -> str:
    """Render the smoke result as the required Phase 0 markdown report."""

    estimated_cost = (
        "not configured"
        if result.usage.estimated_cost_usd is None
        else f"${result.usage.estimated_cost_usd:.2f}"
    )
    lines = [
        "# Phase 0 case.dev Smoke Report",
        "",
        "## Run Configuration",
        "",
        f"- Generated at: {_iso_datetime(result.generated_at)}",
        f"- Date window: {_date_window_label(result.config)}",
        f"- Query limit per term: {result.config.per_query_limit}",
        f"- Candidate retrieval limit: {result.config.candidate_retrieval_limit}",
        f"- Dry run: {_yes_no(result.dry_run)}",
        "",
        "## Search Queries",
        "",
        "| Query string | Hit count | Candidate cases |",
        "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {summary.query} | {summary.hit_count} | {summary.candidate_case_count} |"
        for summary in result.query_summaries
    )
    lines.extend(
        [
            "",
            "## Candidate Yield",
            "",
            f"- Total hit count: {result.total_hit_count}",
            f"- Unique candidate cases: {result.unique_candidate_count}",
            f"- Retrieved candidate cases: {result.retrieved_candidate_count}",
            f"- Clean MTD candidates: {result.clean_mtd_candidate_count}",
            "",
            "## Missing Document Reasons",
            "",
        ]
    )
    if result.missing_document_reasons:
        lines.extend(
            f"- {reason}: {count}"
            for reason, count in result.missing_document_reasons.items()
        )
    else:
        lines.append("- None recorded")
    lines.extend(
        [
            "",
            "## Request And Cost Counts",
            "",
            f"- case.dev request count: {result.usage.request_count}",
            f"- Estimated case.dev cost: {estimated_cost}",
            "",
            "## Candidate Ledger",
            "",
            "| Candidate ID | Case ID | Clean proxy | Missing reasons | "
            "Retrieval error |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if result.candidates:
        lines.extend(
            "| {candidate_id} | {case_id} | {clean} | {missing} | {error} |".format(
                candidate_id=candidate.candidate_id,
                case_id=candidate.case_id,
                clean=_yes_no(candidate.clean_packet_proxy),
                missing=", ".join(candidate.missing_document_reasons) or "none",
                error=candidate.retrieval_error or "none",
            )
            for candidate in result.candidates
        )
    else:
        lines.append("| none | none | no | none | none |")
    lines.extend(
        [
            "",
            "## Fallback Recommendation",
            "",
            result.fallback_recommendation,
            "",
        ]
    )
    return "\n".join(lines)


def _unique_docket_records(
    hits: Sequence[CaseDevDocketHit],
) -> tuple[DocketEntryRecord, ...]:
    records: list[DocketEntryRecord] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        key = (hit.case_id, hit.docket_entry_id)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            DocketEntryRecord(
                case_id=hit.case_id,
                docket_entry_id=hit.docket_entry_id,
                entry_text=hit.entry_text,
                entry_number=hit.entry_number,
                filed_at=hit.filed_at,
            )
        )
    return tuple(records)


def _filter_search_hits_by_date_window(
    hits: Sequence[CaseDevDocketHit],
    config: CaseDevSmokeConfig,
) -> tuple[CaseDevDocketHit, ...]:
    start = _optional_date(config.date_window_start, "date_window_start")
    end = _optional_date(config.date_window_end, "date_window_end")
    if start is None and end is None:
        return tuple(hits)
    return tuple(
        hit
        for hit in hits
        if _is_docket_level_search_hit(hit) or _hit_is_in_date_window(hit, start, end)
    )


def _is_docket_level_search_hit(hit: CaseDevDocketHit) -> bool:
    return hit.entry_number is None and "legal_docket" in hit.raw


def _hit_is_in_date_window(
    hit: CaseDevDocketHit,
    start: date | None,
    end: date | None,
) -> bool:
    if hit.filed_at is None:
        return False
    try:
        filed_at = date.fromisoformat(hit.filed_at[:10])
    except ValueError:
        return False
    if start is not None and filed_at < start:
        return False
    if end is not None and filed_at > end:
        return False
    return True


def _summarize_candidate(
    candidate: MtdDiscoveryCandidate,
    *,
    pipeline: DocketRetrievalPipeline,
    config: CaseDevSmokeConfig,
    retrieved_at: datetime,
) -> CaseDevSmokeCandidateSummary:
    candidate_id = f"case-dev-smoke-{candidate.case_id}"
    try:
        retrieval = pipeline.retrieve_candidate(
            candidate_id=candidate_id,
            case_id=candidate.case_id,
            retrieved_at=retrieved_at,
        )
    except CaseDevFeatureUnavailableError as exc:
        return CaseDevSmokeCandidateSummary(
            candidate_id=candidate_id,
            case_id=candidate.case_id,
            trigger_terms=candidate.trigger_terms,
            retrieved=False,
            clean_packet_proxy=False,
            missing_document_reasons=("docket_entry_listing_unavailable",),
            retrieval_error=str(exc) or type(exc).__name__,
        )
    except CaseDevClientError as exc:
        return CaseDevSmokeCandidateSummary(
            candidate_id=candidate_id,
            case_id=candidate.case_id,
            trigger_terms=candidate.trigger_terms,
            retrieved=False,
            clean_packet_proxy=False,
            missing_document_reasons=(f"retrieval_failed:{type(exc).__name__}",),
            retrieval_error=type(exc).__name__,
        )

    missing_reasons = {missing.reason for missing in retrieval.missing_filings}
    if (
        _date_window_is_configured(config)
        and _has_any_decision_signal(retrieval)
        and not _has_decision_filing_in_date_window(retrieval, config)
    ):
        missing_reasons.add("mtd_decision_outside_date_window")
    return CaseDevSmokeCandidateSummary(
        candidate_id=candidate_id,
        case_id=candidate.case_id,
        trigger_terms=candidate.trigger_terms,
        retrieved=True,
        clean_packet_proxy=_has_clean_packet_proxy(retrieval, config),
        missing_document_reasons=tuple(sorted(missing_reasons)),
    )


def _has_clean_packet_proxy(
    retrieval: DocketRetrievalResult,
    config: CaseDevSmokeConfig,
) -> bool:
    roles = {filing.document_role for filing in retrieval.filings}
    has_motion = bool(roles & {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM})
    return (
        DocumentRole.COMPLAINT in roles
        and has_motion
        and _has_decision_filing_in_date_window(retrieval, config)
    )


def _has_decision_filing_in_date_window(
    retrieval: DocketRetrievalResult,
    config: CaseDevSmokeConfig,
) -> bool:
    start = _optional_date(config.date_window_start, "date_window_start")
    end = _optional_date(config.date_window_end, "date_window_end")
    entry_dates = {
        entry.docket_entry_id: entry.filed_at for entry in retrieval.docket_entries
    }
    for filing in retrieval.filings:
        if filing.document_role is not DocumentRole.DECISION:
            continue
        if _date_text_is_in_window(entry_dates.get(filing.docket_entry_id), start, end):
            return True
    return False


def _date_window_is_configured(config: CaseDevSmokeConfig) -> bool:
    return config.date_window_start is not None or config.date_window_end is not None


def _has_any_decision_signal(retrieval: DocketRetrievalResult) -> bool:
    has_decision_entry = any(
        entry.document_role is DocumentRole.DECISION
        for entry in retrieval.docket_entries
    )
    has_decision_filing = any(
        filing.document_role is DocumentRole.DECISION for filing in retrieval.filings
    )
    return has_decision_entry or has_decision_filing


def _date_text_is_in_window(
    value: str | None,
    start: date | None,
    end: date | None,
) -> bool:
    if start is None and end is None:
        return True
    if value is None:
        return False
    try:
        filed_at = date.fromisoformat(value[:10])
    except ValueError:
        return False
    if start is not None and filed_at < start:
        return False
    if end is not None and filed_at > end:
        return False
    return True


def _date_window_label(config: CaseDevSmokeConfig) -> str:
    if config.date_window_start is None and config.date_window_end is None:
        return "not specified"
    start = config.date_window_start or "unspecified"
    end = config.date_window_end or "unspecified"
    return f"{start} to {end}"


def _optional_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD") from exc


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
