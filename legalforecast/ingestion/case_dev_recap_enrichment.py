"""Free Case.dev enrichment and conservative cost ranking for RECAP dockets."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, cast
from urllib.parse import urlsplit

from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevDocketHit,
    CaseDevPage,
)
from legalforecast.ingestion.courtlistener_dates import parse_courtlistener_filed_date
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.docket_sync import classify_document_role
from legalforecast.ingestion.firecrawl_recap_discovery import RecapDiscoveredDocket
from legalforecast.ingestion.mtd_acquisition_screen import (
    MtdDocketDecisionScreen,
    screen_case_dev_docket_metadata,
    screen_courtlistener_docket_for_mtd_decision,
    screen_courtlistener_entry_for_mtd_decision,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.restricted_material import restricted_material_markers

_COURTLISTENER_HOST = "www.courtlistener.com"
_DOCKET_ID = re.compile(r"[1-9][0-9]*")
_PUBLIC_DOCKET_PATH = re.compile(
    r"^/docket/(?P<docket_id>[1-9][0-9]*)/(?P<slug>[^/]+)/$"
)
_API_DOCKET_PATH = re.compile(
    r"^/api/rest/v[1-9][0-9]*/dockets/(?P<docket_id>[1-9][0-9]*)/$"
)
_MANDATORY_REQUIREMENTS: tuple[tuple[str, frozenset[DocumentRole]], ...] = (
    (
        "operative_complaint",
        frozenset({DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}),
    ),
    (
        "motion_to_dismiss",
        frozenset({DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}),
    ),
    ("decision", frozenset({DocumentRole.DECISION})),
)
_REQUIRED_ENTRY_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.MTD_MEMORANDUM,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    }
)
CASE_DEV_RANKING_POLICY_VERSION = "eligibility-aware-v2"


class CaseDevRecapEnrichmentError(RuntimeError):
    """Raised when free Case.dev evidence cannot be verified completely."""


@dataclass(frozen=True, slots=True)
class CaseDevRecapLookupTarget:
    """Exact CourtListener docket identity for a free Case.dev lookup.

    ``docket_url`` is absent when the source provider supplied only the
    shared CourtListener docket primary key. In that mode Case.dev must return
    and prove the canonical URL before the enrichment can succeed.
    """

    docket_id: str
    docket_url: str | None
    entry_keys: tuple[str, ...]
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaseDevRecapNamespaceMapping:
    """Verified mapping between CourtListener and Case.dev docket identities."""

    courtlistener_docket_id: str
    courtlistener_url: str
    case_dev_id: str
    case_dev_url: str

    def to_record(self) -> dict[str, str]:
        return {
            "courtlistener_docket_id": self.courtlistener_docket_id,
            "courtlistener_url": self.courtlistener_url,
            "case_dev_id": self.case_dev_id,
            "case_dev_url": self.case_dev_url,
        }


@dataclass(frozen=True, slots=True)
class CaseDevRecapDocument:
    """One Case.dev document with availability evidence kept uncollapsed."""

    document_id: str
    docket_entry_id: str
    entry_number: str | None
    entry_text: str
    document_role: DocumentRole
    description: str
    kind: str | None
    pdf_url: str | None
    is_available: bool | None
    restriction_markers: tuple[str, ...]

    @property
    def pdf_url_present(self) -> bool:
        return self.pdf_url is not None

    @property
    def actually_free(self) -> bool:
        return (
            self.pdf_url is not None
            and self.is_available is True
            and not self.restriction_markers
        )

    @property
    def availability_reason(self) -> str:
        if self.restriction_markers:
            return "restricted"
        if self.pdf_url is not None and self.is_available is True:
            return "free_pdf"
        if self.pdf_url is not None and self.is_available is False:
            return "pdf_url_but_unavailable"
        if self.pdf_url is not None:
            return "availability_unknown"
        if self.is_available is True:
            return "available_without_pdf_url"
        if self.is_available is False:
            return "unavailable"
        return "availability_unknown"

    def to_record(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "docket_entry_id": self.docket_entry_id,
            "entry_number": self.entry_number,
            "entry_text": self.entry_text,
            "document_role": self.document_role.value,
            "description": self.description,
            "kind": self.kind,
            "pdf_url": self.pdf_url,
            "pdf_url_present": self.pdf_url_present,
            "is_available": self.is_available,
            "actually_free": self.actually_free,
            "availability_reason": self.availability_reason,
            "restriction_markers": list(self.restriction_markers),
        }


@dataclass(frozen=True, slots=True)
class CaseDevRecapEntry:
    """One normalized Case.dev docket entry retained for free eligibility ranking."""

    docket_entry_id: str
    entry_number: str | None
    filed_at: str | None
    entry_text: str
    documents: tuple[CaseDevRecapDocument, ...]

    def as_courtlistener_entry(self) -> CourtListenerWebDocketEntry:
        return CourtListenerWebDocketEntry(
            row_id=self.docket_entry_id,
            entry_number=self.entry_number,
            filed_at=self.filed_at,
            text=self.entry_text,
            documents=tuple(
                CourtListenerWebDocument(
                    kind=document.kind or "",
                    description=document.description,
                    href=document.pdf_url,
                    action_label=None,
                    pacer_only=not document.actually_free,
                    restriction_markers=document.restriction_markers,
                )
                for document in self.documents
            ),
            restriction_markers=tuple(
                dict.fromkeys(
                    marker
                    for document in self.documents
                    for marker in document.restriction_markers
                )
            ),
            narrative_text=self.entry_text,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "docket_entry_id": self.docket_entry_id,
            "entry_number": self.entry_number,
            "filed_at": self.filed_at,
            "entry_text": self.entry_text,
            "document_ids": [document.document_id for document in self.documents],
        }


@dataclass(frozen=True, slots=True)
class CaseDevRequiredDocumentSlot:
    """One required core-document slot and its conservative satisfaction proof."""

    requirement: str
    document_role: DocumentRole
    entry_id: str | None
    entry_number: str | None
    candidate_document_ids: tuple[str, ...]
    selected_document_id: str | None
    satisfied: bool
    missing_reason: str | None

    def to_record(self) -> dict[str, object]:
        return {
            "requirement": self.requirement,
            "document_role": self.document_role.value,
            "entry_id": self.entry_id,
            "entry_number": self.entry_number,
            "candidate_document_ids": list(self.candidate_document_ids),
            "selected_document_id": self.selected_document_id,
            "satisfied": self.satisfied,
            "missing_reason": self.missing_reason,
        }


@dataclass(frozen=True, slots=True)
class CaseDevRecapEnrichment:
    """Complete free Case.dev inventory used for pre-acquisition cost ranking."""

    identity: CaseDevRecapNamespaceMapping
    screening_metadata: Mapping[str, object]
    pages_fetched: int
    docket_entry_count: int
    entries: tuple[CaseDevRecapEntry, ...]
    documents: tuple[CaseDevRecapDocument, ...]
    required_documents: tuple[CaseDevRequiredDocumentSlot, ...]
    eligibility_anchor: date | None = None

    @property
    def courtlistener_docket_id(self) -> str:
        return self.identity.courtlistener_docket_id

    @property
    def case_dev_id(self) -> str:
        return self.identity.case_dev_id

    @property
    def case_dev_url(self) -> str:
        return self.identity.case_dev_url

    @property
    def required_document_count(self) -> int:
        return len(self.required_documents)

    @property
    def actual_free_required_document_count(self) -> int:
        return sum(slot.satisfied for slot in self.required_documents)

    @property
    def missing_required_document_count(self) -> int:
        return self.required_document_count - self.actual_free_required_document_count

    @property
    def eligibility_screen(self) -> MtdDocketDecisionScreen:
        """Replay the canonical MTD screen over the free Case.dev entry inventory."""

        return screen_courtlistener_docket_for_mtd_decision(
            CourtListenerWebDocketPage(
                docket_id=self.courtlistener_docket_id,
                source_url=self.identity.courtlistener_url,
                title=cast(str | None, self.screening_metadata.get("case_name")),
                entries=tuple(entry.as_courtlistener_entry() for entry in self.entries),
                has_next_page=False,
            ),
            decision_filed_on_or_after=self.eligibility_anchor,
        )

    @property
    def observed_target_motion(self) -> bool:
        """Return whether Case.dev exposes a motion filing distinct from its ruling."""

        for entry in self.entries:
            screen = screen_courtlistener_entry_for_mtd_decision(
                entry.as_courtlistener_entry()
            )
            if screen.actual_mtd_decision:
                continue
            if _core_document_role(entry.entry_text) in {
                DocumentRole.MTD_NOTICE,
                DocumentRole.MTD_MEMORANDUM,
            }:
                return True
            if "motion_filing_only" in screen.exclusion_reasons:
                return True
        return False

    @property
    def eligibility_priority(self) -> tuple[int, str]:
        """Return a recall-preserving eligibility scheduling tier.

        This is deliberately a ranking signal, not an exclusion. CourtListener
        remains authoritative, while complete Case.dev entry dates and text let
        us spend the constrained REST quota on the strongest candidates first.
        """

        if self.eligibility_anchor is None:
            return (2, "eligibility_anchor_unconfigured")
        screen = self.eligibility_screen
        anchor_dates = tuple(
            parse_courtlistener_filed_date(entry.filed_at)
            for entry in screen.anchor_disposition_entries
        )
        if any(
            filed_at is not None and filed_at < self.eligibility_anchor
            for filed_at in anchor_dates
        ):
            return (4, "first_written_mtd_disposition_before_anchor")
        if self._has_non_merits_or_moot_disposition:
            return (3, "post_anchor_non_merits_or_moot_disposition")
        if anchor_dates and any(filed_at is None for filed_at in anchor_dates):
            return (2, "first_written_mtd_disposition_date_unproven")
        if screen.strict_clean:
            if not anchor_dates:
                return (2, "first_written_mtd_disposition_date_unproven")
            if self.observed_target_motion:
                return (0, "strict_post_anchor_mtd_with_observed_target_motion")
            return (1, "strict_post_anchor_mtd_target_motion_unproven")
        if screen.has_actual_mtd_decision:
            return (3, "post_anchor_mtd_requires_posture_review")
        if "mtd_decision_outside_date_window" in screen.exclusion_reasons:
            return (4, "first_written_mtd_disposition_before_anchor")
        if "procedural_or_standing_order" in screen.exclusion_reasons:
            return (5, "procedural_or_standing_order")
        return (6, "eligible_mtd_disposition_unproven")

    @property
    def _has_non_merits_or_moot_disposition(self) -> bool:
        for entry in self.entries:
            text = _normalized(entry.entry_text)
            screen = screen_courtlistener_entry_for_mtd_decision(
                entry.as_courtlistener_entry()
            )
            if not screen.actual_mtd_decision:
                continue
            if re.search(r"\b(?:as\s+moot|mooting)\b", text, re.I):
                return True
            if re.search(
                r"\bterminate\w*\b[^.;]{0,160}\bmotion\w*\s+to\s+dismiss\b",
                text,
                re.I,
            ) and re.search(r"\bamended\s+complaint\b", text, re.I):
                return True
        return False

    @property
    def structural_priority(self) -> tuple[int, str]:
        """Return a recall-preserving structural scheduling tier and reason."""

        metadata = self.screening_metadata
        if not metadata.get("court_id") or not metadata.get("docket_number"):
            return (1, "metadata_incomplete_or_unknown")
        screen = screen_case_dev_docket_metadata(metadata)
        if screen.accepted_for_scrape:
            if screen.metadata.case_type_stratum == "bankruptcy_adversary":
                return (0, "bankruptcy_adversary_metadata")
            return (0, "federal_civil_district_metadata")
        return (2, "hard_structural_exclusion_metadata")

    @property
    def decision_signal_priority(self) -> tuple[int, str]:
        """Prioritize eligibility evidence without treating weak signals as drops."""

        if self.eligibility_anchor is not None:
            return self.eligibility_priority

        texts = tuple(
            f"{document.entry_text} {document.description}".lower()
            for document in self.documents
        )
        motion_reference = re.compile(
            r"motion(?:s)? to dismiss|rule\s+12\s*\(\s*c\s*\)|"
            r"judgment on the pleadings",
            re.I,
        )
        decision_form = re.compile(
            r"\b(?:order|opinion|memorandum|judgment|granted|denied|dismissed)\b",
            re.I,
        )
        if any(
            motion_reference.search(text) and decision_form.search(text)
            for text in texts
        ):
            return (0, "explicit_mtd_or_12c_disposition")
        if any(
            document.document_role is DocumentRole.DECISION
            for document in self.documents
        ):
            return (1, "classified_decision_document")
        if any(
            "report and recommendation" in text or "findings and recommendation" in text
            for text in texts
        ):
            return (2, "report_or_recommendation")
        return (3, "weak_or_generic_signal")

    @property
    def ranking_key(self) -> tuple[int, int, int, int, str]:
        structural_tier, _structural_reason = self.structural_priority
        decision_tier, _decision_reason = self.decision_signal_priority
        return (
            structural_tier,
            decision_tier,
            self.missing_required_document_count,
            self.required_document_count,
            self.courtlistener_docket_id,
        )

    def to_record(self) -> dict[str, object]:
        structural_tier, structural_reason = self.structural_priority
        eligibility_tier, eligibility_reason = self.eligibility_priority
        decision_tier, decision_reason = self.decision_signal_priority
        return {
            "ranking_policy_version": CASE_DEV_RANKING_POLICY_VERSION,
            "identity": self.identity.to_record(),
            "screening_metadata": dict(self.screening_metadata),
            "pages_fetched": self.pages_fetched,
            "docket_entry_count": self.docket_entry_count,
            "entries": [entry.to_record() for entry in self.entries],
            "documents": [document.to_record() for document in self.documents],
            "required_documents": [
                document.to_record() for document in self.required_documents
            ],
            "required_document_count": self.required_document_count,
            "actual_free_required_document_count": (
                self.actual_free_required_document_count
            ),
            "missing_required_document_count": self.missing_required_document_count,
            "structural_priority_tier": structural_tier,
            "structural_priority_reason": structural_reason,
            "eligibility_anchor": (
                None
                if self.eligibility_anchor is None
                else self.eligibility_anchor.isoformat()
            ),
            "eligibility_priority_tier": eligibility_tier,
            "eligibility_priority_reason": eligibility_reason,
            "eligibility_screen": self.eligibility_screen.to_record(),
            "observed_target_motion": self.observed_target_motion,
            "decision_signal_priority_tier": decision_tier,
            "decision_signal_priority_reason": decision_reason,
            "ranking_key": list(self.ranking_key),
        }


def enrich_recap_docket_with_case_dev(
    *,
    client: CaseDevClient,
    discovery: RecapDiscoveredDocket | CaseDevRecapLookupTarget,
    page_size: int = 100,
    max_pages: int = 100,
    eligibility_anchor: date | None = None,
) -> CaseDevRecapEnrichment:
    """Inventory one RECAP docket using free ``includeEntries`` lookups only."""

    if type(page_size) is not int or page_size <= 0:
        raise ValueError("page_size must be a positive integer")
    if type(max_pages) is not int or max_pages <= 0:
        raise ValueError("max_pages must be a positive integer")
    _validate_discovery_identity(discovery)

    cursor: str | None = None
    seen_continuations: set[str] = set()
    hits: list[CaseDevDocketHit] = []
    case_dev_id: str | None = None
    case_dev_url: str | None = None
    pages_fetched = 0
    screening_metadata: Mapping[str, object] | None = None

    while True:
        if pages_fetched >= max_pages:
            raise CaseDevRecapEnrichmentError(
                f"case_dev_page_limit_reached: max_pages={max_pages}"
            )
        page = client.get_case_docket_entries(
            discovery.docket_id,
            cursor=cursor,
            limit=page_size,
        )
        pages_fetched += 1
        page_case_dev_id, page_case_dev_url = _verified_page_identity(
            page,
            discovery=discovery,
        )
        page_docket = _mapping(page.raw.get("docket", page.raw), "case.dev docket")
        page_screening_metadata = _screening_metadata(page_docket, discovery=discovery)
        if screening_metadata is None:
            screening_metadata = page_screening_metadata
        elif screening_metadata != page_screening_metadata:
            raise CaseDevRecapEnrichmentError(
                "case_dev_screening_metadata_changed_during_pagination"
            )
        if case_dev_id is None:
            case_dev_id = page_case_dev_id
            case_dev_url = page_case_dev_url
        elif (case_dev_id, case_dev_url) != (page_case_dev_id, page_case_dev_url):
            raise CaseDevRecapEnrichmentError(
                "case_dev_identity_changed_during_pagination"
            )
        hits.extend(page.items)

        next_cursor = page.next_cursor
        if next_cursor is None:
            if len(page.items) >= page_size:
                raise CaseDevRecapEnrichmentError(
                    "case_dev_pagination_exhaustion_unproven"
                )
            break
        if next_cursor in seen_continuations:
            raise CaseDevRecapEnrichmentError("case_dev_continuation_cycle")
        seen_continuations.add(next_cursor)
        cursor = next_cursor

    if case_dev_url is None:
        raise CaseDevRecapEnrichmentError("case_dev_identity_missing")
    entries = _deduplicate_hits(hits)
    documents_by_entry, documents = _inventory_documents(entries)
    normalized_entries = tuple(
        CaseDevRecapEntry(
            docket_entry_id=entry.docket_entry_id,
            entry_number=entry.entry_number,
            filed_at=entry.filed_at,
            entry_text=entry.entry_text,
            documents=documents_by_entry[entry.docket_entry_id],
        )
        for entry in entries
    )
    required_documents = _required_document_slots(
        entries,
        documents_by_entry=documents_by_entry,
    )
    return CaseDevRecapEnrichment(
        identity=CaseDevRecapNamespaceMapping(
            courtlistener_docket_id=discovery.docket_id,
            courtlistener_url=discovery.docket_url or case_dev_url,
            case_dev_id=case_dev_id,
            case_dev_url=case_dev_url,
        ),
        screening_metadata=screening_metadata,
        pages_fetched=pages_fetched,
        docket_entry_count=len(entries),
        entries=normalized_entries,
        documents=documents,
        required_documents=required_documents,
        eligibility_anchor=eligibility_anchor,
    )


def _screening_metadata(
    docket: Mapping[str, Any],
    *,
    discovery: RecapDiscoveredDocket | CaseDevRecapLookupTarget,
) -> Mapping[str, object]:
    result: dict[str, object] = {
        "case_id": discovery.docket_id,
        "case_name": _optional_string(docket, "caseName", "case_name", "caption")
        or "unknown",
        "court_id": _optional_string(docket, "courtId", "court_id", "court"),
        "docket_number": _optional_string(docket, "docketNumber", "docket_number"),
        "date_filed": _optional_string(docket, "dateFiled", "date_filed"),
        "source_url": discovery.docket_url
        or _required_string(docket, "url", "sourceUrl", "source_url"),
    }
    return result


def rank_case_dev_recap_enrichments(
    enrichments: Iterable[CaseDevRecapEnrichment],
) -> tuple[CaseDevRecapEnrichment, ...]:
    """Rank verified dockets by missing required documents, deterministically."""

    by_docket: dict[str, CaseDevRecapEnrichment] = {}
    for enrichment in enrichments:
        docket_id = enrichment.courtlistener_docket_id
        existing = by_docket.get(docket_id)
        if existing is not None and existing != enrichment:
            raise CaseDevRecapEnrichmentError(
                f"conflicting_case_dev_enrichment: docket_id={docket_id}"
            )
        by_docket[docket_id] = enrichment
    return tuple(sorted(by_docket.values(), key=lambda item: item.ranking_key))


def _validate_discovery_identity(
    discovery: RecapDiscoveredDocket | CaseDevRecapLookupTarget,
) -> None:
    if discovery.docket_url is None:
        if _DOCKET_ID.fullmatch(discovery.docket_id) is None:
            raise CaseDevRecapEnrichmentError("courtlistener_docket_id_invalid")
        return
    split = urlsplit(discovery.docket_url)
    if (
        split.scheme != "https"
        or split.netloc != _COURTLISTENER_HOST
        or split.query
        or split.fragment
    ):
        raise CaseDevRecapEnrichmentError("courtlistener_discovery_url_invalid")
    match = _PUBLIC_DOCKET_PATH.fullmatch(split.path)
    if match is None or match.group("docket_id") != discovery.docket_id:
        raise CaseDevRecapEnrichmentError("courtlistener_discovery_identity_mismatch")


def _verified_page_identity(
    page: CaseDevPage[CaseDevDocketHit],
    *,
    discovery: RecapDiscoveredDocket | CaseDevRecapLookupTarget,
) -> tuple[str, str]:
    docket = _mapping(page.raw.get("docket", page.raw), "case.dev docket")
    case_dev_id = _required_string(docket, "id", "docketId", "docket_id")
    if case_dev_id != discovery.docket_id:
        raise CaseDevRecapEnrichmentError(
            f"case_dev_id_mismatch: expected={discovery.docket_id} actual={case_dev_id}"
        )
    case_dev_url = _required_string(docket, "url", "sourceUrl", "source_url")
    if _courtlistener_id_from_returned_url(case_dev_url) != discovery.docket_id:
        raise CaseDevRecapEnrichmentError(
            "case_dev_url_mismatch: "
            f"expected_docket={discovery.docket_id} url={case_dev_url}"
        )
    return case_dev_id, case_dev_url


def _courtlistener_id_from_returned_url(source_url: str) -> str | None:
    split = urlsplit(source_url)
    if (
        split.scheme != "https"
        or split.netloc != _COURTLISTENER_HOST
        or split.query
        or split.fragment
    ):
        return None
    for pattern in (_PUBLIC_DOCKET_PATH, _API_DOCKET_PATH):
        if (match := pattern.fullmatch(split.path)) is not None:
            return match.group("docket_id")
    return None


def _deduplicate_hits(
    hits: Iterable[CaseDevDocketHit],
) -> tuple[CaseDevDocketHit, ...]:
    ordered: list[CaseDevDocketHit] = []
    by_id: dict[str, CaseDevDocketHit] = {}
    index_by_id: dict[str, int] = {}
    for hit in hits:
        existing = by_id.get(hit.docket_entry_id)
        if existing is None:
            by_id[hit.docket_entry_id] = hit
            index_by_id[hit.docket_entry_id] = len(ordered)
            ordered.append(hit)
            continue
        if existing != hit:
            merged = _merge_duplicate_hit(existing, hit)
            by_id[hit.docket_entry_id] = merged
            ordered[index_by_id[hit.docket_entry_id]] = merged
    return tuple(ordered)


def _merge_duplicate_hit(
    left: CaseDevDocketHit, right: CaseDevDocketHit
) -> CaseDevDocketHit:
    semantic_fields = (
        "case_id",
        "docket_id",
        "docket_entry_id",
        "entry_number",
        "filed_at",
        "source_url",
    )
    if any(getattr(left, field) != getattr(right, field) for field in semantic_fields):
        raise CaseDevRecapEnrichmentError(
            f"case_dev_duplicate_entry_irreconcilable: entry_id={right.docket_entry_id}"
        )

    merged_raw = dict(left.raw)
    for key, value in right.raw.items():
        if key == "documents":
            continue
        if key in merged_raw and merged_raw[key] != value:
            raise CaseDevRecapEnrichmentError(
                "case_dev_duplicate_entry_irreconcilable: "
                f"entry_id={right.docket_entry_id}"
            )
        merged_raw[key] = value

    documents: list[object] = []
    by_id: dict[str, Mapping[str, Any]] = {}
    raw_document_groups = (
        left.raw.get("documents", []),
        right.raw.get("documents", []),
    )
    for raw_documents in raw_document_groups:
        if not isinstance(raw_documents, list):
            raise CaseDevRecapEnrichmentError(
                f"case_dev_documents_invalid: entry_id={right.docket_entry_id}"
            )
        for raw_document in cast(list[object], raw_documents):
            document = _mapping(raw_document, "case.dev document")
            document_id = _required_string(document, "id", "documentId", "document_id")
            existing = by_id.get(document_id)
            if existing is not None and existing != document:
                raise CaseDevRecapEnrichmentError(
                    f"case_dev_duplicate_document_conflict: document_id={document_id}"
                )
            if existing is None:
                by_id[document_id] = document
                documents.append(raw_document)
    merged_raw["documents"] = documents
    return replace(
        left,
        entry_text="; ".join(dict.fromkeys((left.entry_text, right.entry_text))),
        source_document_ids=tuple(
            dict.fromkeys((*left.source_document_ids, *right.source_document_ids))
        ),
        raw=merged_raw,
    )


def _inventory_documents(
    entries: Iterable[CaseDevDocketHit],
) -> tuple[
    Mapping[str, tuple[CaseDevRecapDocument, ...]],
    tuple[CaseDevRecapDocument, ...],
]:
    by_entry: dict[str, tuple[CaseDevRecapDocument, ...]] = {}
    ordered: list[CaseDevRecapDocument] = []
    by_document_id: dict[str, CaseDevRecapDocument] = {}
    for entry in entries:
        role = _core_document_role(entry.entry_text)
        raw_documents = entry.raw.get("documents", [])
        if not isinstance(raw_documents, list):
            raise CaseDevRecapEnrichmentError(
                f"case_dev_documents_invalid: entry_id={entry.docket_entry_id}"
            )
        entry_documents: list[CaseDevRecapDocument] = []
        for raw_document in cast(list[object], raw_documents):
            raw = _mapping(raw_document, "case.dev document")
            document = _document_from_record(entry, role=role, raw=raw)
            existing = by_document_id.get(document.document_id)
            if existing is not None and existing != document:
                raise CaseDevRecapEnrichmentError(
                    "case_dev_duplicate_document_conflict: "
                    f"document_id={document.document_id}"
                )
            if existing is None:
                by_document_id[document.document_id] = document
                ordered.append(document)
            entry_documents.append(document)
        by_entry[entry.docket_entry_id] = tuple(entry_documents)
    return by_entry, tuple(ordered)


def _document_from_record(
    entry: CaseDevDocketHit,
    *,
    role: DocumentRole,
    raw: Mapping[str, Any],
) -> CaseDevRecapDocument:
    document_id = _required_string(raw, "id", "documentId", "document_id")
    description = _optional_string(raw, "description", "name") or entry.entry_text
    kind = _optional_string(raw, "type", "kind")
    pdf_url = _optional_pdf_url(raw)
    is_available = _optional_bool(raw, "isAvailable", "is_available")
    markers = restricted_material_markers(
        records=(
            cast(Mapping[str, object], entry.raw),
            cast(Mapping[str, object], raw),
        ),
        text_fields=(entry.entry_text, description),
    )
    return CaseDevRecapDocument(
        document_id=document_id,
        docket_entry_id=entry.docket_entry_id,
        entry_number=entry.entry_number,
        entry_text=entry.entry_text,
        document_role=role,
        description=description,
        kind=kind,
        pdf_url=pdf_url,
        is_available=is_available,
        restriction_markers=markers,
    )


def _required_document_slots(
    entries: Iterable[CaseDevDocketHit],
    *,
    documents_by_entry: Mapping[str, tuple[CaseDevRecapDocument, ...]],
) -> tuple[CaseDevRequiredDocumentSlot, ...]:
    slots: list[CaseDevRequiredDocumentSlot] = []
    observed_roles: set[DocumentRole] = set()
    for entry in entries:
        role = _core_document_role(entry.entry_text)
        if role not in _REQUIRED_ENTRY_ROLES:
            continue
        observed_roles.add(role)
        requirement = _requirement_for_role(role)
        slots.append(
            _entry_required_slot(
                entry,
                role=role,
                requirement=requirement,
                documents=documents_by_entry[entry.docket_entry_id],
            )
        )
    for requirement, roles in _MANDATORY_REQUIREMENTS:
        if observed_roles.isdisjoint(roles):
            slots.append(
                CaseDevRequiredDocumentSlot(
                    requirement=requirement,
                    document_role=_representative_role(roles),
                    entry_id=None,
                    entry_number=None,
                    candidate_document_ids=(),
                    selected_document_id=None,
                    satisfied=False,
                    missing_reason="required_role_absent",
                )
            )
    return tuple(slots)


def _entry_required_slot(
    entry: CaseDevDocketHit,
    *,
    role: DocumentRole,
    requirement: str,
    documents: tuple[CaseDevRecapDocument, ...],
) -> CaseDevRequiredDocumentSlot:
    selected, missing_reason = _select_main_document(documents)
    satisfied = selected is not None and selected.actually_free
    if selected is not None and not satisfied:
        missing_reason = f"required_document_{selected.availability_reason}"
    return CaseDevRequiredDocumentSlot(
        requirement=requirement,
        document_role=role,
        entry_id=entry.docket_entry_id,
        entry_number=entry.entry_number,
        candidate_document_ids=tuple(document.document_id for document in documents),
        selected_document_id=None if selected is None else selected.document_id,
        satisfied=satisfied,
        missing_reason=None if satisfied else missing_reason,
    )


def _select_main_document(
    documents: tuple[CaseDevRecapDocument, ...],
) -> tuple[CaseDevRecapDocument | None, str]:
    if not documents:
        return None, "document_not_listed"
    explicit_main = tuple(
        document
        for document in documents
        if document.kind is not None and "main" in _normalized(document.kind)
    )
    if len(explicit_main) == 1:
        return explicit_main[0], ""
    if len(documents) == 1:
        return documents[0], ""
    return None, "main_document_ambiguous"


def _core_document_role(entry_text: str) -> DocumentRole:
    role = classify_document_role(entry_text)
    if role is DocumentRole.DECISION and not _references_mtd(entry_text):
        return DocumentRole.OTHER
    return role


def _references_mtd(value: str) -> bool:
    normalized = _normalized(value)
    return any(
        marker in normalized
        for marker in ("motion to dismiss", "motions to dismiss", "rule 12", "mtd")
    )


def _requirement_for_role(role: DocumentRole) -> str:
    if role in {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}:
        return "operative_complaint"
    if role in {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}:
        return "motion_to_dismiss"
    if role is DocumentRole.OPPOSITION:
        return "opposition"
    if role is DocumentRole.DECISION:
        return "decision"
    raise CaseDevRecapEnrichmentError(f"unsupported required role: {role.value}")


def _representative_role(roles: frozenset[DocumentRole]) -> DocumentRole:
    for role in (
        DocumentRole.COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.DECISION,
    ):
        if role in roles:
            return role
    raise CaseDevRecapEnrichmentError("mandatory requirement has no role")


def _optional_pdf_url(record: Mapping[str, Any]) -> str | None:
    for field_name in ("pdfUrl", "pdf_url"):
        if field_name not in record or record[field_name] is None:
            continue
        value = record[field_name]
        if not isinstance(value, str):
            raise CaseDevRecapEnrichmentError(f"{field_name} must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        split = urlsplit(stripped)
        if (
            split.scheme != "https"
            or not split.netloc
            or split.username is not None
            or split.password is not None
            or split.fragment
        ):
            raise CaseDevRecapEnrichmentError(
                f"{field_name} must be a canonical HTTPS URL"
            )
        return stripped
    return None


def _optional_bool(record: Mapping[str, Any], *field_names: str) -> bool | None:
    for field_name in field_names:
        if field_name not in record or record[field_name] is None:
            continue
        value = record[field_name]
        if not isinstance(value, bool):
            raise CaseDevRecapEnrichmentError(f"{field_name} must be a boolean")
        return value
    return None


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaseDevRecapEnrichmentError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _required_string(record: Mapping[str, Any], *field_names: str) -> str:
    value = _optional_string(record, *field_names)
    if value is None:
        raise CaseDevRecapEnrichmentError(
            f"missing required Case.dev field: {' or '.join(field_names)}"
        )
    return value


def _optional_string(record: Mapping[str, Any], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalized(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())
