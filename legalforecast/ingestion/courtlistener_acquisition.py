"""Live CourtListener discovery and fail-closed MTD candidate screening."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Protocol

from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerDocket,
    CourtListenerUnavailableError,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.docket_sync import NormalizedDocketEntry
from legalforecast.ingestion.mtd_acquisition_screen import (
    OPTIMIZED_MTD_DECISION_SEARCH_TERMS,
    SECONDARY_MTD_DECISION_SEARCH_TERMS,
    CaseDevMetadataScreen,
    is_rule_7012_claim_merits_motion,
    screen_case_dev_docket_metadata,
    screen_courtlistener_docket_for_mtd_decision,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.selection.contamination_filters import (
    LeakageSource,
    LeakageSourceKind,
    detect_outcome_leakage,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)
from legalforecast.selection.motion_linkage import (
    link_mtd_dispositions,
    referenced_mtd_entry_numbers,
)

DEFAULT_COURTLISTENER_MTD_QUERY_TERMS = (
    *OPTIMIZED_MTD_DECISION_SEARCH_TERMS,
    *SECONDARY_MTD_DECISION_SEARCH_TERMS,
)


class CourtListenerDocketHTMLSource(Protocol):
    """Source of a public CourtListener docket page."""

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class FixtureCourtListenerDocketHTMLSource:
    """Read docket pages from ``<docket_id>.html`` fixture files."""

    root: Path

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        del source_url
        path = self.root / f"{docket_id}.html"
        if not path.is_file():
            raise CourtListenerUnavailableError(
                f"CourtListener docket HTML fixture is missing: {path}"
            )
        return path.read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class LiveCourtListenerDocketHTMLSource:
    """Fetch allowlisted public CourtListener docket HTML over HTTPS."""

    timeout_seconds: float = 30.0
    max_bytes: int = 10 * 1024 * 1024

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        url = _validated_public_docket_url(source_url, docket_id=docket_id)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "LegalForecastBench/1.0 public-record-acquisition",
            },
        )
        try:
            opener = urllib.request.build_opener(_CourtListenerRedirectHandler())
            with opener.open(request, timeout=self.timeout_seconds) as response:  # nosec B310
                final_url = response.geturl()
                _validate_courtlistener_transport_url(final_url)
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > self.max_bytes:
                    raise CourtListenerClientError(
                        "CourtListener docket HTML exceeds byte ceiling"
                    )
                content = response.read(self.max_bytes + 1)
                if len(content) > self.max_bytes:
                    raise CourtListenerClientError(
                        "CourtListener docket HTML exceeds byte ceiling"
                    )
                return content.decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise CourtListenerUnavailableError(
                    f"CourtListener docket {docket_id} is unavailable"
                ) from exc
            raise CourtListenerClientError(
                f"CourtListener docket HTML request failed with status {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise CourtListenerClientError(
                f"CourtListener docket HTML request failed: {exc.reason}"
            ) from exc


@dataclass(frozen=True, slots=True)
class CourtListenerDiscoveryResult:
    """Auditable outputs from one bounded discovery/screening run."""

    screened_cases: tuple[Mapping[str, Any], ...]
    exclusions: tuple[ExclusionLedgerEntry, ...]
    summary: Mapping[str, Any]


def discover_courtlistener_mtd_candidates(
    *,
    client: CourtListenerClient,
    html_source: CourtListenerDocketHTMLSource,
    raw_html_dir: Path,
    decision_filed_on_or_after: date,
    search_window_start: date,
    search_window_end: date,
    query_terms: Sequence[str] = DEFAULT_COURTLISTENER_MTD_QUERY_TERMS,
    target_clean_cases: int = 150,
    max_candidates: int = 3000,
    search_page_size: int = 50,
    resume: bool = True,
) -> CourtListenerDiscoveryResult:
    """Search a bounded rolling window and screen against an immutable anchor."""

    if search_window_end < search_window_start:
        raise ValueError("search_window_end cannot precede search_window_start")
    if search_window_end < decision_filed_on_or_after:
        raise ValueError("search_window_end cannot precede eligibility anchor")

    validate_courtlistener_discovery_limits(
        query_terms=query_terms,
        target_clean_cases=target_clean_cases,
        max_candidates=max_candidates,
        search_page_size=search_page_size,
    )
    raw_html_dir.mkdir(parents=True, exist_ok=True)
    screened_cases: list[Mapping[str, Any]] = []
    exclusions: list[ExclusionLedgerEntry] = []
    seen_docket_ids: set[str] = set()
    search_hit_count = 0
    duplicate_hit_count = 0
    processed_count = 0
    queries: list[str] = []
    per_term: dict[str, dict[str, Any]] = {}

    for term in query_terms:
        query = _windowed_query(term, search_window_start, search_window_end)
        queries.append(query)
        term_request_count = 0
        term_candidate_ids: set[str] = set()
        terminal_status = "exhausted"
        cursor: str | None = None
        while True:
            page = client.search_recap_documents(
                query,
                cursor=cursor,
                page_size=search_page_size,
            )
            term_request_count += 1
            search_hit_count += len(page.items)
            for hit in page.items:
                term_candidate_ids.add(hit.docket_id)
                if hit.docket_id in seen_docket_ids:
                    duplicate_hit_count += 1
                    continue
                seen_docket_ids.add(hit.docket_id)
                if processed_count >= max_candidates:
                    break
                processed_count += 1
                screened, exclusion = _screen_candidate(
                    client=client,
                    html_source=html_source,
                    raw_html_dir=raw_html_dir,
                    docket_id=hit.docket_id,
                    anchor=decision_filed_on_or_after,
                    query=query,
                    resume=resume,
                )
                if screened is not None:
                    screened_cases.append(screened)
                elif exclusion is not None:
                    exclusions.append(exclusion)
                if len(screened_cases) >= target_clean_cases:
                    terminal_status = "limit_bound:target_clean_cases"
                    break
            if processed_count >= max_candidates:
                terminal_status = "limit_bound:max_candidates"
            if (
                len(screened_cases) >= target_clean_cases
                or processed_count >= max_candidates
                or page.next_cursor is None
            ):
                break
            cursor = page.next_cursor
        per_term[term] = {
            "request_count": term_request_count,
            "candidate_count": len(term_candidate_ids),
            "terminal_status": terminal_status,
            "limit_bound": terminal_status.startswith("limit_bound"),
        }
        if (
            len(screened_cases) >= target_clean_cases
            or processed_count >= max_candidates
        ):
            break

    summary: dict[str, Any] = {
        "schema_version": "legalforecast.courtlistener_discovery_summary.v1",
        "anchor_date": decision_filed_on_or_after.isoformat(),
        "search_window_start": search_window_start.isoformat(),
        "search_window_end": search_window_end.isoformat(),
        "query_terms": list(query_terms),
        "queries": queries,
        "target_clean_cases": target_clean_cases,
        "max_candidates": max_candidates,
        "search_page_size": search_page_size,
        "search_hit_count": search_hit_count,
        "duplicate_search_hit_count": duplicate_hit_count,
        "unique_candidate_count": len(seen_docket_ids),
        "processed_candidate_count": processed_count,
        "accepted_case_count": len(screened_cases),
        "excluded_case_count": len(exclusions),
        "target_met": len(screened_cases) >= target_clean_cases,
        "candidate_limit_reached": processed_count >= max_candidates,
        "per_term": per_term,
    }
    return CourtListenerDiscoveryResult(
        screened_cases=tuple(screened_cases),
        exclusions=tuple(exclusions),
        summary=summary,
    )


def _screen_candidate(
    *,
    client: CourtListenerClient,
    html_source: CourtListenerDocketHTMLSource,
    raw_html_dir: Path,
    docket_id: str,
    anchor: date,
    query: str,
    resume: bool,
) -> tuple[Mapping[str, Any] | None, ExclusionLedgerEntry | None]:
    try:
        docket = client.get_docket(docket_id)
    except CourtListenerUnavailableError as exc:
        return None, _exclusion(
            docket_id=docket_id,
            stage=ExclusionStage.RETRIEVAL,
            reason="courtlistener_docket_unavailable",
            notes=str(exc),
        )

    metadata_screen = screen_case_dev_docket_metadata(
        {
            "id": docket.docket_id,
            "court_id": docket.court_id,
            "docket_number": docket.docket_number,
            "case_name": docket.case_name,
        },
        query=query,
    )
    if not metadata_screen.accepted_for_scrape:
        return None, _metadata_exclusion(
            docket=docket,
            metadata_screen=metadata_screen,
        )

    source_url = _public_docket_url(docket)
    raw_html_path = raw_html_dir / f"{docket_id}.html"
    try:
        if raw_html_path.exists():
            if not resume:
                raise CourtListenerClientError(
                    f"raw docket HTML already exists and --no-resume was requested: "
                    f"{raw_html_path}"
                )
            raw_html = raw_html_path.read_text(encoding="utf-8")
        else:
            raw_html = html_source.fetch(docket_id=docket_id, source_url=source_url)
            raw_html_path.write_text(raw_html, encoding="utf-8")
    except CourtListenerUnavailableError as exc:
        return None, _exclusion(
            docket_id=docket_id,
            docket=docket,
            stage=ExclusionStage.RETRIEVAL,
            reason="courtlistener_docket_html_unavailable",
            notes=str(exc),
        )

    return screen_courtlistener_docket_html(
        docket=docket,
        metadata_screen=metadata_screen,
        raw_html=raw_html,
        decision_filed_on_or_after=anchor,
    )


def screen_courtlistener_docket_html(
    *,
    docket: CourtListenerDocket,
    metadata_screen: CaseDevMetadataScreen,
    raw_html: str,
    decision_filed_on_or_after: date,
) -> tuple[Mapping[str, Any] | None, ExclusionLedgerEntry | None]:
    """Strictly screen one already-fetched public CourtListener docket page.

    Both the direct CourtListener route and the Case.dev-to-Firecrawl route use
    this provider-independent kernel.  The caller must supply the pre-fetch
    metadata screen so a downstream route cannot silently bypass that gate.
    """

    docket_id = docket.docket_id
    case_id = metadata_screen.metadata.case_id
    if not metadata_screen.accepted_for_scrape:
        return None, _metadata_exclusion(
            docket=docket,
            metadata_screen=metadata_screen,
        )
    source_url = _public_docket_url(docket)
    try:
        parsed = parse_courtlistener_docket_html(
            raw_html,
            source_url=source_url,
            docket_id=docket_id,
        )
    except CourtListenerWebParseError as exc:
        return None, _exclusion(
            docket_id=docket_id,
            case_id=case_id,
            docket=docket,
            stage=ExclusionStage.EXTRACTION,
            reason=ExclusionReason.PARSE_ERROR.value,
            notes=f"CourtListener docket HTML could not be parsed: {exc}",
        )

    unanchored = screen_courtlistener_docket_for_mtd_decision(
        parsed,
        candidate_text=_candidate_text(docket),
    )
    anchored = screen_courtlistener_docket_for_mtd_decision(
        parsed,
        candidate_text=_candidate_text(docket),
        decision_filed_on_or_after=decision_filed_on_or_after,
    )
    unparseable_decision_entries = tuple(
        entry
        for entry in unanchored.decision_entries
        if _parse_filed_date(entry.filed_at) is None
    )
    if unparseable_decision_entries:
        return None, _exclusion(
            docket_id=docket_id,
            case_id=case_id,
            docket=docket,
            stage=ExclusionStage.ELIGIBILITY,
            reason=ExclusionReason.PARSE_ERROR.value,
            source_entry_ids=tuple(
                entry.row_id for entry in unparseable_decision_entries
            ),
            notes=(
                "At least one written MTD disposition date could not be parsed, "
                "so the first disposition cannot be proven eligible."
            ),
        )
    first_decision_date = _first_decision_date(unanchored.decision_entries)
    if (
        first_decision_date is not None
        and first_decision_date < decision_filed_on_or_after
    ):
        return None, _exclusion(
            docket_id=docket_id,
            case_id=case_id,
            docket=docket,
            stage=ExclusionStage.ELIGIBILITY,
            reason=ExclusionReason.DECISION_BEFORE_RELEASE_ANCHOR.value,
            source_entry_ids=tuple(
                entry.row_id for entry in unanchored.decision_entries
            ),
            decision_date=first_decision_date,
            notes=(
                "The first written MTD disposition predates the eligibility anchor "
                f"{decision_filed_on_or_after.isoformat()}."
            ),
        )
    if not anchored.strict_clean:
        reasons = anchored.exclusion_reasons or ("no_actual_mtd_disposition",)
        return None, _exclusion(
            docket_id=docket_id,
            case_id=case_id,
            docket=docket,
            stage=ExclusionStage.DISCOVERY,
            reason=reasons[0],
            secondary_reasons=reasons[1:],
            source_entry_ids=tuple(entry.row_id for entry in anchored.decision_entries),
            decision_date=first_decision_date,
            notes="CourtListener docket failed the strict MTD acquisition screen.",
        )
    assert first_decision_date is not None

    normalized_entries = _linkage_entries(
        parsed.entries,
        actual_decision_row_ids={entry.row_id for entry in anchored.decision_entries},
        docket_id=docket_id,
        source_url=source_url,
        case_type_stratum=anchored.case_type_stratum,
    )
    linkage = link_mtd_dispositions(
        normalized_entries,
        candidate_id=docket_id,
        case_id=case_id,
    )
    if not linkage.is_clean:
        exclusion = linkage.exclusion_entries[0]
        return None, ExclusionLedgerEntry(
            candidate_id=exclusion.candidate_id,
            case_id=exclusion.case_id,
            court=docket.court_id,
            decision_date=first_decision_date,
            stage=exclusion.stage,
            reason=exclusion.reason,
            secondary_reasons=exclusion.secondary_reasons,
            source_entry_ids=exclusion.source_entry_ids,
            source_document_ids=exclusion.source_document_ids,
            related_family_id=exclusion.related_family_id,
            notes=exclusion.notes,
        )

    entry_number_by_id = {entry.row_id: entry.entry_number for entry in parsed.entries}
    motion_numbers = _linked_entry_numbers(
        tuple(entry_id for link in linkage.links for entry_id in link.motion_entry_ids),
        entry_number_by_id,
    )
    decision_numbers = _linked_entry_numbers(
        tuple(
            entry_id
            for link in linkage.links
            for entry_id in link.disposition_entry_ids
        ),
        entry_number_by_id,
    )
    if not motion_numbers or not decision_numbers:
        return None, _exclusion(
            docket_id=docket_id,
            case_id=case_id,
            docket=docket,
            stage=ExclusionStage.MOTION_LINKAGE,
            reason=ExclusionReason.UNCLEAN_LINKAGE.value,
            source_entry_ids=tuple(entry_number_by_id),
            decision_date=first_decision_date,
            notes="Linked MTD or disposition entries lack numeric docket numbers.",
        )

    leakage = detect_outcome_leakage(
        _predecision_docket_leakage_sources(
            parsed.entries,
            decision_entries=anchored.decision_entries,
            target_motion_numbers=motion_numbers,
            decision_date=first_decision_date,
            related_family_id=_docket_case_mix_metadata(docket).get(
                "related_family_id"
            ),
        ),
        evaluation_timestamp=datetime.combine(
            first_decision_date,
            time.max,
            tzinfo=UTC,
        ),
    )
    if leakage.outcome_leakage_detected:
        return None, ExclusionLedgerEntry.from_outcome_leakage(
            candidate_id=docket_id,
            case_id=case_id,
            leakage_result=leakage,
            court=docket.court_id,
            decision_date=first_decision_date,
        )

    return {
        "candidate": {
            "docket_id": docket_id,
            "candidate_key": docket_id,
            "metadata": {
                "case_id": case_id,
                "case_name": docket.case_name,
                "court": docket.court_id,
                "docket_number": docket.docket_number,
                "case_type_stratum": anchored.case_type_stratum,
                **_docket_case_mix_metadata(docket),
            },
            "url": source_url,
        },
        "ai": {
            "target_motion_entry_numbers": list(motion_numbers),
            "decision_entry_numbers": list(decision_numbers),
        },
        "selected_entries": [entry.to_record() for entry in parsed.entries],
        "first_written_mtd_disposition_date": first_decision_date.isoformat(),
        "eligibility_anchor_date": decision_filed_on_or_after.isoformat(),
        "mtd_decision_screen": anchored.to_record(),
        "motion_linkage": linkage.to_record(),
    }, None


def _metadata_exclusion(
    *,
    docket: CourtListenerDocket,
    metadata_screen: CaseDevMetadataScreen,
) -> ExclusionLedgerEntry:
    reasons = metadata_screen.exclusion_reasons or ("metadata_screen_not_accepted",)
    return _exclusion(
        docket_id=docket.docket_id,
        case_id=metadata_screen.metadata.case_id,
        docket=docket,
        stage=ExclusionStage.DISCOVERY,
        reason=reasons[0],
        secondary_reasons=reasons[1:],
        notes="CourtListener docket metadata failed the strict civil MTD screen.",
    )


def _predecision_docket_leakage_sources(
    entries: Sequence[CourtListenerWebDocketEntry],
    *,
    decision_entries: Sequence[Any],
    target_motion_numbers: Sequence[str],
    decision_date: date,
    related_family_id: str | None,
) -> tuple[LeakageSource, ...]:
    """Return docket rows that could have revealed the target before decision."""

    decision_row_ids = {entry.row_id for entry in decision_entries}
    decision_numbers = tuple(
        int(entry.entry_number)
        for entry in entries
        if entry.row_id in decision_row_ids
        and entry.entry_number is not None
        and entry.entry_number.isdigit()
    )
    first_decision_number = min(decision_numbers) if decision_numbers else None
    target_numbers = {int(number) for number in target_motion_numbers}
    docket_mtd_numbers = {
        int(entry.entry_number)
        for entry in entries
        if entry.entry_number is not None
        and entry.entry_number.isdigit()
        and entry.role
        in {CourtListenerEntryRole.MTD_NOTICE, CourtListenerEntryRole.MTD_MEMORANDUM}
        and _looks_like_target_mtd_filing(entry.text)
    }
    target_reference_required = bool(docket_mtd_numbers - target_numbers)
    sources: list[LeakageSource] = []
    for entry in entries:
        if entry.row_id in decision_row_ids or not entry.text.strip():
            continue
        filed_date = _parse_filed_date(entry.filed_at)
        entry_number = (
            int(entry.entry_number)
            if entry.entry_number is not None and entry.entry_number.isdigit()
            else None
        )
        is_predecision = (filed_date is not None and filed_date < decision_date) or (
            first_decision_number is not None
            and entry_number is not None
            and entry_number < first_decision_number
            and (filed_date is None or filed_date <= decision_date)
        )
        if not is_predecision:
            continue
        if target_reference_required and not _entry_references_target_motion(
            entry.text,
            target_numbers=target_numbers,
        ):
            continue
        observed_date = filed_date or decision_date
        sources.append(
            LeakageSource(
                source_id=entry.row_id,
                source_kind=LeakageSourceKind.DOCKET_ENTRY,
                text=entry.text,
                observed_at=datetime.combine(observed_date, time.min, tzinfo=UTC),
                related_family_id=related_family_id,
            )
        )
    return tuple(sources)


def _entry_references_target_motion(
    text: str,
    *,
    target_numbers: set[int],
) -> bool:
    referenced_numbers = {
        int(match.group("number"))
        for match in re.finditer(
            r"\b(?:ecf|dkt|docket|doc(?:ument)?)[ .#:-]*"
            r"(?:no[ .#:-]*)?(?P<number>\d+)\b",
            text,
            re.IGNORECASE,
        )
    }
    # Explicit references to other motions are safely out of target scope.
    # Unscoped outcome-bearing text is ambiguous and therefore fail-closed.
    return not referenced_numbers or bool(referenced_numbers & target_numbers)


def _docket_case_mix_metadata(docket: CourtListenerDocket) -> dict[str, str]:
    """Preserve source-provided strata without inferring unavailable values."""

    aliases = {
        "nature_of_suit": ("nature_of_suit", "natureOfSuit"),
        "nos_macro_category": ("nos_macro_category", "nosMacroCategory"),
        "related_family_id": (
            "related_family_id",
            "relatedFamilyId",
            "related_case_family_id",
            "relatedCaseFamilyId",
        ),
        "mdl_family_id": (
            "mdl_family_id",
            "mdlFamilyId",
            "mdl_id",
            "mdlId",
        ),
        "case_type_stratum": ("case_type_stratum", "caseTypeStratum"),
    }
    metadata: dict[str, str] = {}
    for output_key, source_keys in aliases.items():
        value = _first_source_string(docket.raw, source_keys)
        if value is not None:
            metadata[output_key] = value
    return metadata


def _first_source_string(
    record: Mapping[str, Any],
    keys: Sequence[str],
) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _linkage_entries(
    entries: Sequence[CourtListenerWebDocketEntry],
    *,
    actual_decision_row_ids: set[str],
    docket_id: str,
    source_url: str,
    case_type_stratum: str = "district_civil",
) -> tuple[NormalizedDocketEntry, ...]:
    entry_by_row_id = {entry.row_id: entry for entry in entries}
    explicitly_referenced_numbers: set[int] = set()
    for row_id in actual_decision_row_ids:
        disposition = entry_by_row_id.get(row_id)
        if disposition is not None:
            explicitly_referenced_numbers.update(
                referenced_mtd_entry_numbers(disposition.text)
            )

    normalized: list[NormalizedDocketEntry] = []
    for entry in entries:
        adversary_motion_qualifies = (
            case_type_stratum != "bankruptcy_adversary"
            or is_rule_7012_claim_merits_motion(entry.text)
        )
        if entry.row_id in actual_decision_row_ids:
            role = DocumentRole.DECISION
        elif (
            entry.role is CourtListenerEntryRole.MTD_NOTICE
            and _looks_like_target_mtd_filing(entry.text)
            and adversary_motion_qualifies
        ):
            role = DocumentRole.MTD_NOTICE
        elif (
            entry.role is CourtListenerEntryRole.MTD_MEMORANDUM
            and _looks_like_target_mtd_filing(entry.text)
            and adversary_motion_qualifies
        ):
            role = DocumentRole.MTD_MEMORANDUM
        elif (
            entry.entry_number is not None
            and entry.entry_number.isdigit()
            and int(entry.entry_number) in explicitly_referenced_numbers
            and (
                _looks_like_target_mtd_filing(entry.text)
                or _looks_like_generic_mtd_document(entry.text)
            )
            and adversary_motion_qualifies
        ):
            role = DocumentRole.MTD_NOTICE
        else:
            continue
        normalized.append(
            NormalizedDocketEntry(
                source_provider="courtlistener",
                source_case_id=docket_id,
                docket_entry_id=entry.row_id,
                entry_number=entry.entry_number,
                entry_text=entry.text,
                filed_at=entry.filed_at,
                document_role=role,
                source_document_ids=tuple(
                    document.href
                    for document in entry.documents
                    if document.href is not None
                ),
                source_url=source_url,
            )
        )
    return tuple(normalized)


def _looks_like_target_mtd_filing(text: str) -> bool:
    if re.search(
        r"\b(?:report and recommendation|r&r|tentative ruling|minute order|"
        r"oral ruling|hearing transcript|opinion|order)\b",
        text,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"\bnotice\s+of\s+compliance\b", text, re.IGNORECASE):
        return False
    return bool(
        re.search(r"\bmotions?\s+to\s+dismiss\b", text, re.IGNORECASE)
        or re.search(
            r"\bmotions?\s+by\b[^\n]{0,240}?\bto\s+dismiss\b",
            text,
            re.IGNORECASE,
        )
        or re.search(r"\bjudgment\s+on\s+the\s+pleadings\b", text, re.IGNORECASE)
        or re.search(r"\brule\s+12\b", text, re.IGNORECASE)
    )


def _looks_like_generic_mtd_document(text: str) -> bool:
    """Recognize PACER's terse MTD document label, never by itself.

    Callers must additionally prove that an actual disposition explicitly
    references this row number.  The negative terms keep voluntary and other
    non-merits dismissal filings outside the recovery path.
    """

    normalized = " ".join(text.replace("\xad", "").lower().split())
    labels = re.findall(
        r"(?=\bmain\s+doc\s*ument\s+(?P<label>.*?)\s+"
        r"(?:download\s+pdf|buy\s+on\s+pacer)\b)",
        normalized,
    )
    return any(_is_safe_generic_mtd_label(label) for label in labels)


def _is_safe_generic_mtd_label(label: str) -> bool:
    components = tuple(
        component.strip() for component in re.split(r"\s+and\s+", label.strip())
    )
    return bool(components) and all(
        component in _GENERIC_MTD_DOCUMENT_LABELS for component in components
    )


_GENERIC_MTD_DOCUMENT_LABELS = frozenset(
    {
        "dismiss",
        "dismiss for failure to state a claim",
        "dismiss/failure to state a claim",
        "dismiss / failure to state a claim",
        "dismiss/lack of jurisdiction",
        "dismiss / lack of jurisdiction",
    }
)


def _linked_entry_numbers(
    entry_ids: Sequence[str],
    entry_number_by_id: Mapping[str, str | None],
) -> tuple[str, ...]:
    numbers: list[str] = []
    for entry_id in entry_ids:
        number = entry_number_by_id.get(entry_id)
        if number is None or not number.isdigit():
            return ()
        if number not in numbers:
            numbers.append(number)
    return tuple(numbers)


def _first_decision_date(entries: Sequence[Any]) -> date | None:
    parsed_dates = tuple(
        parsed
        for entry in entries
        if (parsed := _parse_filed_date(entry.filed_at)) is not None
    )
    return min(parsed_dates) if parsed_dates else None


def _parse_filed_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    match = re.fullmatch(
        r"(?P<date>[A-Z][a-z]+\.? \d{1,2}, \d{4})"
        r"(?:, (?:noon|midnight|(?:1[0-2]|[1-9])(?::[0-5]\d)? [ap]\.m\.))?",
        value.strip(),
    )
    if match is None:
        return None
    date_text = match.group("date")
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%b. %d, %Y"):
        try:
            return datetime.strptime(date_text, pattern).date()
        except ValueError:
            continue
    return None


def _exclusion(
    *,
    docket_id: str,
    case_id: str | None = None,
    stage: ExclusionStage,
    reason: str,
    notes: str,
    docket: CourtListenerDocket | None = None,
    secondary_reasons: Sequence[str] = (),
    source_entry_ids: Sequence[str] = (),
    decision_date: date | None = None,
) -> ExclusionLedgerEntry:
    return ExclusionLedgerEntry(
        candidate_id=docket_id,
        case_id=case_id or docket_id,
        court=docket.court_id if docket is not None else None,
        decision_date=decision_date,
        stage=stage,
        reason=reason,
        secondary_reasons=tuple(reason for reason in secondary_reasons if reason),
        source_entry_ids=tuple(source_entry_ids),
        notes=notes,
    )


def _candidate_text(docket: CourtListenerDocket) -> str:
    return " ".join(
        value
        for value in (docket.court_id, docket.docket_number, docket.case_name)
        if value is not None
    )


def _windowed_query(term: str, start: date, end: date) -> str:
    escaped = term.strip().replace('"', r"\"")
    return (
        f'"{escaped}" AND entry_date_filed:[{start.isoformat()} TO {end.isoformat()}]'
    )


def _public_docket_url(docket: CourtListenerDocket) -> str:
    if docket.source_url:
        if docket.source_url.startswith("/"):
            return f"https://www.courtlistener.com{docket.source_url}"
        return docket.source_url
    return f"https://www.courtlistener.com/docket/{docket.docket_id}/"


def _validate_courtlistener_transport_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.courtlistener.com", "storage.courtlistener.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise CourtListenerClientError(
            "CourtListener redirect left the HTTPS CourtListener host allowlist"
        )


class _CourtListenerRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        _validate_courtlistener_transport_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


def _validated_public_docket_url(source_url: str, *, docket_id: str) -> str:
    parsed = urllib.parse.urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname != "www.courtlistener.com":
        raise CourtListenerClientError(
            "CourtListener docket HTML URL must use https://www.courtlistener.com"
        )
    if parsed.port not in (None, 443):
        raise CourtListenerClientError(
            "CourtListener docket HTML URL must use port 443"
        )
    if not re.match(rf"^/docket/{re.escape(docket_id)}(?:/|$)", parsed.path):
        raise CourtListenerClientError(
            "CourtListener docket HTML URL does not match the candidate docket ID"
        )
    return source_url


def validate_courtlistener_discovery_limits(
    *,
    query_terms: Sequence[str],
    target_clean_cases: int,
    max_candidates: int,
    search_page_size: int,
) -> None:
    if not query_terms or any(not term.strip() for term in query_terms):
        raise ValueError("at least one non-empty CourtListener query term is required")
    if target_clean_cases <= 0:
        raise ValueError("target_clean_cases must be positive")
    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    if search_page_size <= 0 or search_page_size > 100:
        raise ValueError("search_page_size must be between 1 and 100")
