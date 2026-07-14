"""Pure recovery projection for durably acquired RECAP search pages.

This module deliberately makes no provider-exhaustion or saturation claim.  It
verifies the scheduler records supplied by its caller, parses each raw artifact,
and projects the recoverable entry and docket identities into deterministic,
explicitly partial checkpoints.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from legalforecast.ingestion.budgeted_firecrawl import FirecrawlPageRecord
from legalforecast.ingestion.firecrawl_recap_discovery import (
    RecapSearchError,
    RecapSearchHit,
    RecapSearchPage,
    RecapSearchProvenance,
    parse_recap_search_html,
)


class RecapPartialProjectionError(RuntimeError):
    """Raised when durable page evidence cannot be reconciled safely."""


@dataclass(frozen=True, slots=True)
class RecapPartialPageCheckpoint:
    """One verified durable search artifact included in the checkpoint."""

    target_id: str
    term: str
    entry_date_filed_after: str
    entry_date_filed_before: str
    page_number: int
    ordinal: int
    attempt_id: int
    attempt_number: int
    artifact_path: str
    artifact_sha256: str
    artifact_byte_count: int
    reported_credits: int
    raw_hit_count: int
    declared_total_results: int
    declared_total_pages: int
    checkpoint_only: bool = True
    complete: bool = False
    saturated: bool = False


@dataclass(frozen=True, slots=True)
class RecapPartialEntryCheckpoint:
    """One deduplicated RECAP entry with its durable source evidence."""

    entry_key: str
    source_entry_key: str
    docket_id: str
    docket_entry_id: str | None
    document_number: str | None
    attachment_number: int | None
    docket_url: str
    document_url: str
    entry_date_filed: str
    case_name: str
    description: str
    is_available: bool
    matched_terms: tuple[str, ...]
    provenances: tuple[RecapSearchProvenance, ...]
    source_target_ids: tuple[str, ...]
    source_attempt_ids: tuple[int, ...]
    source_artifact_sha256s: tuple[str, ...]
    checkpoint_only: bool = True
    complete: bool = False
    saturated: bool = False


@dataclass(frozen=True, slots=True)
class RecapPartialCandidateCheckpoint:
    """One docket-level potential candidate recovered from partial discovery."""

    candidate_id: str
    case_id: str
    docket_id: str
    docket_url: str
    entry_keys: tuple[str, ...]
    matched_terms: tuple[str, ...]
    source_target_ids: tuple[str, ...]
    source_attempt_ids: tuple[int, ...]
    source_artifact_sha256s: tuple[str, ...]
    candidate_count_semantics: str = (
        "potential docket from a partial RECAP search checkpoint; eligibility, "
        "document completeness, leakage, and labeling remain unverified"
    )
    checkpoint_only: bool = True
    complete: bool = False
    saturated: bool = False


@dataclass(frozen=True, slots=True)
class RecapPartialReconciliationSummary:
    """Counts reconciling durable inputs to the partial projection."""

    acquired_page_count: int
    raw_hit_count: int
    unique_entry_count: int
    duplicate_entry_count: int
    unique_docket_count: int
    reported_credits_total: int
    artifact_byte_count_total: int
    terms: tuple[str, ...]
    attempt_ids: tuple[int, ...]
    artifact_sha256s: tuple[str, ...]
    provider_completeness_status: str = "unproven"
    provider_saturation_status: str = "unproven"
    checkpoint_only: bool = True
    complete: bool = False
    saturated: bool = False


@dataclass(frozen=True, slots=True)
class RecapPartialCheckpointProjection:
    """Deterministic partial recovery result."""

    pages: tuple[RecapPartialPageCheckpoint, ...]
    entries: tuple[RecapPartialEntryCheckpoint, ...]
    candidates: tuple[RecapPartialCandidateCheckpoint, ...]
    summary: RecapPartialReconciliationSummary


@dataclass(frozen=True, slots=True)
class _VerifiedPage:
    record: FirecrawlPageRecord
    hits: tuple[RecapSearchHit, ...]
    term: str
    entry_date_filed_after: str
    entry_date_filed_before: str
    declared_total_results: int
    declared_total_pages: int


def project_partial_recap_checkpoint(
    records: Sequence[FirecrawlPageRecord],
    *,
    parse_search_html: Callable[..., RecapSearchPage] = parse_recap_search_html,
) -> RecapPartialCheckpointProjection:
    """Project verified scheduler pages without claiming a complete search."""

    verified = tuple(
        _verify_page_record(record, parse_search_html=parse_search_html)
        for record in records
    )
    ordered_pages = tuple(sorted(verified, key=lambda item: item.record.ordinal))
    _validate_unique_page_provenance(ordered_pages)

    term_first_ordinal: dict[str, int] = {}
    evidence_by_provenance: dict[tuple[str, int, str], FirecrawlPageRecord] = {}
    for page in ordered_pages:
        term_first_ordinal.setdefault(page.term, page.record.ordinal)
        key = (
            page.record.source_url,
            page.record.page_number,
            page.record.artifact_sha256,
        )
        if key in evidence_by_provenance:
            raise RecapPartialProjectionError(
                "duplicate search page artifact provenance"
            )
        evidence_by_provenance[key] = page.record

    def term_sort_key(term: str) -> tuple[int, str]:
        return (term_first_ordinal[term], term)

    raw_hits = tuple(hit for page in ordered_pages for hit in page.hits)
    entries = _dedupe_entries(
        raw_hits,
        evidence_by_provenance=evidence_by_provenance,
        term_sort_key=term_sort_key,
    )
    candidates = _dedupe_dockets(entries, term_sort_key=term_sort_key)
    page_checkpoints = tuple(_page_checkpoint(page) for page in ordered_pages)
    artifact_hashes = tuple(
        dict.fromkeys(page.record.artifact_sha256 for page in ordered_pages)
    )
    summary = RecapPartialReconciliationSummary(
        acquired_page_count=len(ordered_pages),
        raw_hit_count=len(raw_hits),
        unique_entry_count=len(entries),
        duplicate_entry_count=len(raw_hits) - len(entries),
        unique_docket_count=len(candidates),
        reported_credits_total=sum(
            page.record.reported_credits for page in ordered_pages
        ),
        artifact_byte_count_total=sum(
            page.record.artifact_byte_count for page in ordered_pages
        ),
        terms=tuple(sorted(term_first_ordinal, key=term_sort_key)),
        attempt_ids=tuple(page.record.attempt_id for page in ordered_pages),
        artifact_sha256s=artifact_hashes,
    )
    return RecapPartialCheckpointProjection(
        pages=page_checkpoints,
        entries=entries,
        candidates=candidates,
        summary=summary,
    )


def _verify_page_record(
    record: FirecrawlPageRecord,
    *,
    parse_search_html: Callable[..., RecapSearchPage],
) -> _VerifiedPage:
    if record.target_kind != "search":
        raise RecapPartialProjectionError(
            "partial RECAP projection requires search pages"
        )
    raw = record.raw_html.encode("utf-8")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != record.artifact_sha256:
        raise RecapPartialProjectionError(
            "raw page hash disagrees with durable artifact"
        )
    if len(raw) != record.artifact_byte_count:
        raise RecapPartialProjectionError(
            "raw page size disagrees with durable artifact"
        )
    if record.target_http_status is not None and not (
        200 <= record.target_http_status < 300
    ):
        raise RecapPartialProjectionError(
            "successful page has a non-success target status"
        )
    if record.attempt_id <= 0 or record.attempt_number <= 0:
        raise RecapPartialProjectionError("page attempt provenance is invalid")
    if record.reported_credits < 0:
        raise RecapPartialProjectionError("reported credits cannot be negative")
    try:
        parsed = parse_search_html(record.raw_html, source_url=record.source_url)
    except (RecapSearchError, ValueError) as exc:
        raise RecapPartialProjectionError(
            "durable artifact is not a valid RECAP search page"
        ) from exc
    if parsed.target.page != record.page_number:
        raise RecapPartialProjectionError(
            "record page number disagrees with parsed search page"
        )
    for hit in parsed.hits:
        provenance = hit.provenance
        if (
            provenance.search_url != record.source_url
            or provenance.page != record.page_number
            or provenance.raw_html_sha256 != record.artifact_sha256
        ):
            raise RecapPartialProjectionError(
                "parsed hit provenance disagrees with durable artifact"
            )
    return _VerifiedPage(
        record=record,
        hits=parsed.hits,
        term=parsed.target.term,
        entry_date_filed_after=parsed.target.entry_date_filed_after.isoformat(),
        entry_date_filed_before=parsed.target.entry_date_filed_before.isoformat(),
        declared_total_results=parsed.total_results,
        declared_total_pages=parsed.total_pages,
    )


def _validate_unique_page_provenance(pages: Sequence[_VerifiedPage]) -> None:
    page_identities: set[tuple[str, str, str, int]] = set()
    target_ids: set[str] = set()
    attempt_ids: set[int] = set()
    ordinals: set[int] = set()
    artifact_paths: set[str] = set()
    for page in pages:
        record = page.record
        page_identity = (
            page.term,
            page.entry_date_filed_after,
            page.entry_date_filed_before,
            record.page_number,
        )
        if page_identity in page_identities:
            raise RecapPartialProjectionError(
                "duplicate search page in partial projection"
            )
        page_identities.add(page_identity)
        artifact_path = str(record.artifact_path)
        if (
            record.target_id in target_ids
            or record.attempt_id in attempt_ids
            or record.ordinal in ordinals
            or artifact_path in artifact_paths
        ):
            raise RecapPartialProjectionError("conflicting page provenance")
        target_ids.add(record.target_id)
        attempt_ids.add(record.attempt_id)
        ordinals.add(record.ordinal)
        artifact_paths.add(artifact_path)


def _dedupe_entries(
    hits: Sequence[RecapSearchHit],
    *,
    evidence_by_provenance: dict[tuple[str, int, str], FirecrawlPageRecord],
    term_sort_key: Callable[[str], tuple[int, str]],
) -> tuple[RecapPartialEntryCheckpoint, ...]:
    by_entry: dict[str, list[RecapSearchHit]] = {}
    for hit in hits:
        by_entry.setdefault(_checkpoint_entry_key(hit), []).append(hit)
    entries: list[RecapPartialEntryCheckpoint] = []
    for entry_key in sorted(by_entry, key=_entry_sort_key):
        grouped = by_entry[entry_key]
        canonical = grouped[0]
        canonical_identity = _entry_identity(canonical)
        if any(_entry_identity(hit) != canonical_identity for hit in grouped[1:]):
            raise RecapPartialProjectionError(
                f"conflicting duplicate entry identity: {entry_key}"
            )
        source_records: list[FirecrawlPageRecord] = []
        for hit in grouped:
            provenance = hit.provenance
            evidence_key = (
                provenance.search_url,
                provenance.page,
                provenance.raw_html_sha256,
            )
            record = evidence_by_provenance.get(evidence_key)
            if record is None:
                raise RecapPartialProjectionError(
                    f"missing artifact provenance for entry: {entry_key}"
                )
            source_records.append(record)
        ordered_sources = tuple(
            sorted(
                {record.attempt_id: record for record in source_records}.values(),
                key=lambda record: record.ordinal,
            )
        )
        provenances = tuple(
            sorted(
                set(hit.provenance for hit in grouped),
                key=lambda item: (
                    term_sort_key(item.query_term),
                    item.page,
                    item.result_ordinal,
                    item.entry_ordinal,
                    item.raw_html_sha256,
                ),
            )
        )
        entries.append(
            RecapPartialEntryCheckpoint(
                entry_key=entry_key,
                source_entry_key=canonical.entry_key,
                docket_id=canonical.docket_id,
                docket_entry_id=canonical.docket_entry_id,
                document_number=canonical.document_number,
                attachment_number=canonical.attachment_number,
                docket_url=canonical.docket_url,
                document_url=canonical.document_url,
                entry_date_filed=canonical.entry_date_filed.isoformat(),
                case_name=canonical.case_name,
                description=canonical.description,
                is_available=any(hit.is_available for hit in grouped),
                matched_terms=tuple(
                    sorted(
                        {hit.provenance.query_term for hit in grouped},
                        key=term_sort_key,
                    )
                ),
                provenances=provenances,
                source_target_ids=tuple(record.target_id for record in ordered_sources),
                source_attempt_ids=tuple(
                    record.attempt_id for record in ordered_sources
                ),
                source_artifact_sha256s=tuple(
                    dict.fromkeys(record.artifact_sha256 for record in ordered_sources)
                ),
            )
        )
    return tuple(entries)


def _dedupe_dockets(
    entries: Sequence[RecapPartialEntryCheckpoint],
    *,
    term_sort_key: Callable[[str], tuple[int, str]],
) -> tuple[RecapPartialCandidateCheckpoint, ...]:
    by_docket: dict[str, list[RecapPartialEntryCheckpoint]] = {}
    for entry in entries:
        by_docket.setdefault(entry.docket_id, []).append(entry)
    candidates: list[RecapPartialCandidateCheckpoint] = []
    for docket_id in sorted(by_docket, key=_numeric_sort_key):
        docket_entries = by_docket[docket_id]
        docket_urls = {entry.docket_url for entry in docket_entries}
        if len(docket_urls) != 1:
            raise RecapPartialProjectionError(
                f"conflicting duplicate docket identity: {docket_id}"
            )
        candidates.append(
            RecapPartialCandidateCheckpoint(
                candidate_id=f"courtlistener-docket-{docket_id}",
                case_id=f"courtlistener-docket-{docket_id}",
                docket_id=docket_id,
                docket_url=next(iter(docket_urls)),
                entry_keys=tuple(entry.entry_key for entry in docket_entries),
                matched_terms=tuple(
                    sorted(
                        {
                            term
                            for entry in docket_entries
                            for term in entry.matched_terms
                        },
                        key=term_sort_key,
                    )
                ),
                source_target_ids=_ordered_unique(
                    value
                    for entry in docket_entries
                    for value in entry.source_target_ids
                ),
                source_attempt_ids=_ordered_unique_int(
                    value
                    for entry in docket_entries
                    for value in entry.source_attempt_ids
                ),
                source_artifact_sha256s=_ordered_unique(
                    value
                    for entry in docket_entries
                    for value in entry.source_artifact_sha256s
                ),
            )
        )
    return tuple(candidates)


def _page_checkpoint(page: _VerifiedPage) -> RecapPartialPageCheckpoint:
    record = page.record
    return RecapPartialPageCheckpoint(
        target_id=record.target_id,
        term=page.term,
        entry_date_filed_after=page.entry_date_filed_after,
        entry_date_filed_before=page.entry_date_filed_before,
        page_number=record.page_number,
        ordinal=record.ordinal,
        attempt_id=record.attempt_id,
        attempt_number=record.attempt_number,
        artifact_path=str(record.artifact_path),
        artifact_sha256=record.artifact_sha256,
        artifact_byte_count=record.artifact_byte_count,
        reported_credits=record.reported_credits,
        raw_hit_count=len(page.hits),
        declared_total_results=page.declared_total_results,
        declared_total_pages=page.declared_total_pages,
    )


def _entry_identity(hit: RecapSearchHit) -> tuple[object, ...]:
    return (
        hit.docket_id,
        hit.docket_entry_id,
        hit.document_number,
        hit.attachment_number,
        hit.docket_url,
        hit.document_url,
        hit.entry_date_filed,
        hit.case_name,
        hit.description,
    )


def _checkpoint_entry_key(hit: RecapSearchHit) -> str:
    if hit.attachment_number is None:
        return hit.entry_key
    return f"{hit.entry_key}:attachment:{hit.attachment_number}"


def _entry_sort_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(_numeric_sort_key(part) for part in value.split(":"))


def _numeric_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _ordered_unique_int(values: Iterable[int]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(values))
