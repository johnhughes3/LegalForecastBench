"""Optimized public-record screening for MTD decision acquisition.

The first live acquisition pass showed that broad "motion to dismiss" search
terms are useful for recall but too noisy for quickly reaching 150 usable
decisions. This module captures the decision-oriented query plan and the
metadata/docket-row filters used to estimate whether a CourtListener docket is
worth packet reconstruction.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import cast

from legalforecast.ingestion.courtlistener_dates import parse_courtlistener_filed_date
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerBriefingCompleteness,
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    estimate_briefing_completeness,
)

OPTIMIZED_MTD_DECISION_SEARCH_TERMS: tuple[str, ...] = ("order on motion to dismiss",)

SECONDARY_MTD_DECISION_SEARCH_TERMS: tuple[str, ...] = (
    "order granting motion to dismiss",
    "order denying motion to dismiss",
    "order granting in part and denying in part motion to dismiss",
    "opinion and order motion to dismiss",
    "memorandum opinion and order motion to dismiss",
    "decision and order motion to dismiss",
    "order on motion for judgment on the pleadings",
    "order granting motion for judgment on the pleadings",
    "order denying motion for judgment on the pleadings",
)

LOW_YIELD_MTD_DISCOVERY_TERMS: tuple[str, ...] = (
    "motion to dismiss",
    "motions to dismiss",
    "MTD",
    "Rule 12",
)

# CourtListener's federal-bankruptcy court identifiers.  Keep this explicit:
# the former ``[a-z]{2,4}b`` heuristic also matched ordinary docket text such
# as "Feb", judge initials ("JLB"), and party abbreviations ("CAB").
_BANKRUPTCY_COURT_IDS = frozenset(
    {
        "akb",
        "almb",
        "alnb",
        "alsb",
        "areb",
        "arwb",
        "azb",
        "cacb",
        "caeb",
        "canb",
        "casb",
        "cob",
        "ctb",
        "dcb",
        "deb",
        "flmb",
        "flnb",
        "flsb",
        "gamb",
        "ganb",
        "gasb",
        "gub",
        "hib",
        "ianb",
        "iasb",
        "idb",
        "ilcb",
        "ilnb",
        "ilsb",
        "innb",
        "insb",
        "ksb",
        "kyeb",
        "kywb",
        "laeb",
        "lamb",
        "lawb",
        "mab",
        "mdb",
        "meb",
        "mieb",
        "miwb",
        "mnb",
        "moeb",
        "mowb",
        "mpb",
        "msnb",
        "mssb",
        "mtb",
        "nceb",
        "ncmb",
        "ncwb",
        "ndb",
        "neb",
        "nhb",
        "njb",
        "nmb",
        "nvb",
        "nyeb",
        "nynb",
        "nysb",
        "nywb",
        "ohnb",
        "ohsb",
        "okeb",
        "oknb",
        "okwb",
        "orb",
        "paeb",
        "pamb",
        "pawb",
        "prb",
        "rib",
        "scb",
        "sdb",
        "tneb",
        "tnmb",
        "tnwb",
        "txeb",
        "txnb",
        "txsb",
        "txwb",
        "utb",
        "vaeb",
        "vawb",
        "vib",
        "vtb",
        "waeb",
        "wawb",
        "wieb",
        "wiwb",
        "wvnb",
        "wvsb",
        "wyb",
    }
)


class MtdDocketScreenStatus(StrEnum):
    """Case-level acquisition screen outcome."""

    ACCEPTED_STRICT_CIVIL_MTD_DECISION = "accepted_strict_civil_mtd_decision"
    ACTUAL_MTD_DECISION_REVIEW_OR_EXCLUDED = "actual_mtd_decision_review_or_excluded"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class CaseDevDocketMetadata:
    """Case.dev docket-search metadata used before scraping CourtListener."""

    case_id: str
    query: str | None
    court_id: str | None
    court: str | None
    docket_number: str | None
    case_name: str | None
    nature_of_suit: str | None
    cause: str | None

    @property
    def case_type_stratum(self) -> str:
        """Return the acquisition stratum proved by source metadata."""

        if _looks_like_bankruptcy_adversary_metadata(self):
            return "bankruptcy_adversary"
        return "district_civil"

    @classmethod
    def from_mapping(
        cls,
        record: Mapping[str, object],
        *,
        query: str | None = None,
    ) -> CaseDevDocketMetadata:
        """Normalize common case.dev docket-search result shapes."""

        source = _nested_mapping(record, "legal_docket") or record
        case_id = (
            _optional_text(source, "id", "docketId", "case_id", "caseId")
            or _optional_text(record, "case_id", "caseId", "docket_id", "docketId")
            or "unknown"
        )
        return cls(
            case_id=case_id,
            query=query or _optional_text(record, "query", "search_query"),
            court_id=_optional_text(source, "courtId", "court_id"),
            court=_optional_text(source, "court", "courtName"),
            docket_number=_optional_text(
                source,
                "docketNumber",
                "docket_number",
                "case_number",
            ),
            case_name=_optional_text(
                source,
                "caseName",
                "case_name",
                "caption",
                "name",
            ),
            nature_of_suit=_optional_text(source, "natureOfSuit", "nature_of_suit"),
            cause=_optional_text(source, "cause"),
        )

    @property
    def searchable_text(self) -> str:
        return _normalized_text(
            " ".join(
                item
                for item in (
                    self.case_id,
                    self.query,
                    self.court_id,
                    self.court,
                    self.docket_number,
                    self.case_name,
                    self.nature_of_suit,
                    self.cause,
                )
                if item is not None
            )
        )

    def to_record(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "query": self.query,
            "court_id": self.court_id,
            "court": self.court,
            "docket_number": self.docket_number,
            "case_name": self.case_name,
            "nature_of_suit": self.nature_of_suit,
            "cause": self.cause,
            "case_type_stratum": self.case_type_stratum,
        }


@dataclass(frozen=True, slots=True)
class CaseDevMetadataScreen:
    """Pre-scrape screen result for one Case.dev docket-search hit."""

    metadata: CaseDevDocketMetadata
    exclusion_reasons: tuple[str, ...]

    @property
    def accepted_for_scrape(self) -> bool:
        return not self.exclusion_reasons

    def to_record(self) -> dict[str, object]:
        return {
            "metadata": self.metadata.to_record(),
            "accepted_for_scrape": self.accepted_for_scrape,
            "exclusion_reasons": list(self.exclusion_reasons),
        }


@dataclass(frozen=True, slots=True)
class MtdDecisionEntryScreen:
    """Decision-level screen for a CourtListener docket entry."""

    row_id: str
    entry_number: str | None
    filed_at: str | None
    actual_mtd_decision: bool
    exclusion_reasons: tuple[str, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "entry_number": self.entry_number,
            "filed_at": self.filed_at,
            "actual_mtd_decision": self.actual_mtd_decision,
            "exclusion_reasons": list(self.exclusion_reasons),
        }


@dataclass(frozen=True, slots=True)
class MtdDocketDecisionScreen:
    """Case-level screen result after parsing a CourtListener docket page."""

    docket_id: str | None
    source_url: str | None
    title: str | None
    status: MtdDocketScreenStatus
    exclusion_reasons: tuple[str, ...]
    decision_entries: tuple[MtdDecisionEntryScreen, ...]
    completeness: CourtListenerBriefingCompleteness
    case_type_stratum: str = "district_civil"

    @property
    def has_actual_mtd_decision(self) -> bool:
        return bool(self.decision_entries)

    @property
    def strict_clean(self) -> bool:
        return self.status is MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION

    def to_record(self) -> dict[str, object]:
        return {
            "docket_id": self.docket_id,
            "source_url": self.source_url,
            "title": self.title,
            "status": self.status.value,
            "exclusion_reasons": list(self.exclusion_reasons),
            "actual_mtd_decision_entry_count": len(self.decision_entries),
            "decision_entries": [entry.to_record() for entry in self.decision_entries],
            "completeness": self.completeness.to_record(),
            "case_type_stratum": self.case_type_stratum,
        }


@dataclass(frozen=True, slots=True)
class TargetYieldEstimate:
    """Observed yield and extrapolated screening depth for an acquisition target."""

    screened_count: int
    actual_decision_count: int
    strict_clean_count: int
    target_count: int = 150

    @property
    def actual_decision_yield(self) -> float:
        return _safe_rate(self.actual_decision_count, self.screened_count)

    @property
    def strict_clean_yield(self) -> float:
        return _safe_rate(self.strict_clean_count, self.screened_count)

    @property
    def estimated_screened_for_actual_target(self) -> int | None:
        return _estimated_screened_count(
            retained_count=self.actual_decision_count,
            screened_count=self.screened_count,
            target_count=self.target_count,
        )

    @property
    def estimated_screened_for_strict_target(self) -> int | None:
        return _estimated_screened_count(
            retained_count=self.strict_clean_count,
            screened_count=self.screened_count,
            target_count=self.target_count,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "screened_count": self.screened_count,
            "actual_decision_count": self.actual_decision_count,
            "strict_clean_count": self.strict_clean_count,
            "target_count": self.target_count,
            "actual_decision_yield": self.actual_decision_yield,
            "strict_clean_yield": self.strict_clean_yield,
            "estimated_screened_for_actual_target": (
                self.estimated_screened_for_actual_target
            ),
            "estimated_screened_for_strict_target": (
                self.estimated_screened_for_strict_target
            ),
        }


def screen_case_dev_docket_metadata(
    record: Mapping[str, object],
    *,
    query: str | None = None,
) -> CaseDevMetadataScreen:
    """Return metadata exclusions before spending a CourtListener scrape."""

    metadata = CaseDevDocketMetadata.from_mapping(record, query=query)
    return CaseDevMetadataScreen(
        metadata=metadata,
        exclusion_reasons=_case_dev_metadata_exclusion_reasons(metadata),
    )


def courtlistener_public_docket_url_from_case_dev(
    record: Mapping[str, object],
) -> str | None:
    """Build the public CourtListener docket URL from case.dev search metadata.

    case.dev docket search returns CourtListener API-style URLs such as
    ``/api/rest/v4/dockets/<id>/``. For public HTML scraping, use the stable
    ``/docket/<id>/<case-name-slug>/`` page instead of CourtListener search API
    resolution, which is rate limited for unauthenticated callers.
    """

    metadata = CaseDevDocketMetadata.from_mapping(record)
    docket_id = _courtlistener_docket_id(record) or metadata.case_id
    if not docket_id or docket_id == "unknown":
        return None
    if metadata.case_name is None:
        return f"https://www.courtlistener.com/docket/{docket_id}/"
    slug = courtlistener_case_name_slug(metadata.case_name)
    return f"https://www.courtlistener.com/docket/{docket_id}/{slug}/"


def courtlistener_case_name_slug(case_name: str) -> str:
    """Return a CourtListener-compatible case-name slug."""

    without_possessives = re.sub(r"['\u2019]", "", case_name.replace("&", " and "))
    slug = re.sub(r"[^A-Za-z0-9]+", "-", without_possessives).strip("-").lower()
    return re.sub(r"-+", "-", slug) or "case"


def screen_courtlistener_entry_for_mtd_decision(
    entry: CourtListenerWebDocketEntry,
) -> MtdDecisionEntryScreen:
    """Classify whether a docket row is an actual MTD disposition signal."""

    text = _entry_search_text(entry)
    exclusion_reasons: list[str] = []
    if not _references_mtd_or_pleadings_motion(text):
        exclusion_reasons.append("no_mtd_or_rule_12_reference")
    if _looks_like_service_or_mailing_entry(entry):
        exclusion_reasons.append("procedural_or_standing_order")
    if _looks_like_notice_of_removal_or_state_record(text):
        exclusion_reasons.append("notice_of_removal_or_state_record")
    if _looks_like_proposed_order_attachment(text):
        exclusion_reasons.append("proposed_order_not_decision")
    if _looks_like_procedural_or_standing_order(text):
        exclusion_reasons.append("procedural_or_standing_order")
    if _looks_like_self_or_voluntary_dismissal(text):
        exclusion_reasons.append("self_or_voluntary_dismissal")
    if _looks_like_transfer_only(text):
        exclusion_reasons.append("transfer_only")

    if exclusion_reasons:
        return MtdDecisionEntryScreen(
            row_id=entry.row_id,
            entry_number=entry.entry_number,
            filed_at=entry.filed_at,
            actual_mtd_decision=False,
            exclusion_reasons=tuple(exclusion_reasons),
        )

    actual = _looks_like_actual_mtd_decision(text)
    if actual:
        decision_reasons: tuple[str, ...] = ()
    elif _has_decision_form(text):
        decision_reasons = ("mtd_disposition_unproven",)
    else:
        decision_reasons = ("motion_filing_only",)
    return MtdDecisionEntryScreen(
        row_id=entry.row_id,
        entry_number=entry.entry_number,
        filed_at=entry.filed_at,
        actual_mtd_decision=actual,
        exclusion_reasons=decision_reasons,
    )


def _looks_like_service_or_mailing_entry(
    entry: CourtListenerWebDocketEntry,
) -> bool:
    """Reject service artifacts that merely quote a linked court order."""

    narrative = _entry_narrative_before_documents(entry)
    certificate = re.search(
        r"\b(?:bnc\s+)?certificate\s+of\s+(?:mailing|service)\b",
        narrative,
        re.IGNORECASE,
    )
    if certificate is None:
        return False
    court_output = re.search(
        r"\b(?:order|opinion|decision|report\s+and\s+recommendation|judgment)\b",
        narrative,
        re.IGNORECASE,
    )
    return court_output is None or certificate.start() < court_output.start()


def is_rule_7012_claim_merits_motion(text: str) -> bool:
    """Return whether one row proves an adversary Rule 12 claim challenge."""

    return _looks_like_rule_7012_claim_merits_motion(_normalized_text(text).lower())


def screen_courtlistener_docket_for_mtd_decision(
    page: CourtListenerWebDocketPage,
    *,
    candidate_text: str | None = None,
    decision_filed_on_or_after: date | None = None,
    decision_filed_on_or_before: date | None = None,
) -> MtdDocketDecisionScreen:
    """Screen a parsed CourtListener docket for actual and strict-clean MTDs."""

    completeness = estimate_briefing_completeness(page)
    if page.has_next_page:
        return MtdDocketDecisionScreen(
            docket_id=page.docket_id,
            source_url=page.source_url,
            title=page.title,
            status=MtdDocketScreenStatus.EXCLUDED,
            exclusion_reasons=("courtlistener_docket_more_than_one_page",),
            decision_entries=(),
            completeness=completeness,
        )

    entry_screens = tuple(
        screen_courtlistener_entry_for_mtd_decision(entry) for entry in page.entries
    )
    actual_decision_entries = tuple(
        entry_screen
        for entry_screen in entry_screens
        if entry_screen.actual_mtd_decision
    )
    decision_entries = tuple(
        entry_screen
        for entry_screen in actual_decision_entries
        if _decision_date_in_window(
            entry_screen.filed_at,
            decision_filed_on_or_after=decision_filed_on_or_after,
            decision_filed_on_or_before=decision_filed_on_or_before,
        )
    )
    combined_text = " ".join(
        item
        for item in (
            page.title,
            candidate_text,
            " ".join(entry.text for entry in page.entries),
        )
        if item is not None
    )
    if not decision_entries:
        decision_exclusion_reasons = (
            ("mtd_decision_outside_date_window",)
            if actual_decision_entries
            else _dominant_exclusion_reasons(entry_screens)
        )
        social_security_exclusions = (
            ("social_security_merits_review_posture",)
            if _looks_like_commissioner_social_security_context(combined_text)
            and re.search(
                r"\b(?:partial\s+)?judgment\s+on\s+(?:the\s+)?pleadings\b",
                combined_text,
                re.I,
            )
            else ()
        )
        return MtdDocketDecisionScreen(
            docket_id=page.docket_id,
            source_url=page.source_url,
            title=page.title,
            status=MtdDocketScreenStatus.EXCLUDED,
            exclusion_reasons=tuple(
                dict.fromkeys(
                    (*decision_exclusion_reasons, *social_security_exclusions)
                )
            ),
            decision_entries=(),
            completeness=completeness,
        )

    bankruptcy_context = _looks_like_bankruptcy_context(combined_text)
    decision_row_ids = {entry.row_id for entry in decision_entries}
    social_security_exclusions = (
        ("social_security_merits_review_posture",)
        if any(
            _looks_like_social_security_merits_jop(
                context_text=combined_text,
                decision_text=_entry_search_text(entry),
            )
            for entry in page.entries
            if entry.row_id in decision_row_ids
        )
        else ()
    )
    adversary_exclusions = (
        _bankruptcy_adversary_exclusion_reasons(
            page,
            combined_text=combined_text,
            candidate_text=candidate_text,
        )
        if bankruptcy_context
        else ()
    )
    strict_exclusions = tuple(
        dict.fromkeys(
            (
                *adversary_exclusions,
                *social_security_exclusions,
                *_strict_posture_exclusion_reasons(
                    combined_text,
                    allow_bankruptcy_adversary=(
                        bankruptcy_context and not adversary_exclusions
                    ),
                ),
            )
        )
    )
    return MtdDocketDecisionScreen(
        docket_id=page.docket_id,
        source_url=page.source_url,
        title=page.title,
        status=(
            MtdDocketScreenStatus.ACTUAL_MTD_DECISION_REVIEW_OR_EXCLUDED
            if strict_exclusions
            else MtdDocketScreenStatus.ACCEPTED_STRICT_CIVIL_MTD_DECISION
        ),
        exclusion_reasons=strict_exclusions,
        decision_entries=decision_entries,
        completeness=completeness,
        case_type_stratum=(
            "bankruptcy_adversary" if bankruptcy_context else "district_civil"
        ),
    )


def build_target_yield_estimate(
    screens: Sequence[MtdDocketDecisionScreen],
    *,
    target_count: int = 150,
) -> TargetYieldEstimate:
    """Summarize observed yield and target-depth extrapolations."""

    return TargetYieldEstimate(
        screened_count=len(screens),
        actual_decision_count=sum(
            1 for screen in screens if screen.has_actual_mtd_decision
        ),
        strict_clean_count=sum(1 for screen in screens if screen.strict_clean),
        target_count=target_count,
    )


def _case_dev_metadata_exclusion_reasons(
    metadata: CaseDevDocketMetadata,
) -> tuple[str, ...]:
    reasons: list[str] = []
    court_text = _normalized_text(f"{metadata.court_id or ''} {metadata.court or ''}")
    docket_number = metadata.docket_number or ""
    searchable_text = metadata.searchable_text

    bankruptcy_court = _looks_like_bankruptcy_court(metadata)
    bankruptcy_adversary = _looks_like_bankruptcy_adversary_metadata(metadata)
    if bankruptcy_court:
        if not bankruptcy_adversary:
            reasons.append("bankruptcy_court")
    elif not _looks_like_federal_district_court(court_text):
        reasons.append("not_federal_district_court")

    if not docket_number.strip():
        reasons.append("missing_docket_number")
    elif _looks_like_placeholder_or_sealed_docket(docket_number):
        reasons.append("placeholder_or_sealed_docket_number")
    elif (
        _looks_like_non_civil_docket_number(docket_number) and not bankruptcy_adversary
    ):
        reasons.append("not_civil_cv_docket")
    elif (
        not _looks_like_civil_cv_docket_number(docket_number)
        and not bankruptcy_adversary
    ):
        reasons.append("not_civil_cv_docket")

    if _looks_like_criminal_caption(metadata.case_name or ""):
        reasons.append("criminal_style_caption")
    reasons.extend(
        _strict_posture_exclusion_reasons(
            searchable_text,
            allow_bankruptcy_adversary=bankruptcy_adversary,
        )
    )
    return tuple(dict.fromkeys(reasons))


def _looks_like_bankruptcy_court(metadata: CaseDevDocketMetadata) -> bool:
    court_text = f"{metadata.court_id or ''} {metadata.court or ''}".lower()
    return "bankruptcy" in court_text or (metadata.court_id or "").lower().endswith("b")


def _looks_like_bankruptcy_adversary_metadata(
    metadata: CaseDevDocketMetadata,
) -> bool:
    if not _looks_like_bankruptcy_court(metadata):
        return False
    docket_number = metadata.docket_number or ""
    if re.search(r"(?:^|[-:])bk(?:[-:]|\b)", docket_number, re.I):
        return False
    explicit_adversary_number = bool(
        re.search(r"(?:^|[-:])(?:ap|adv)(?:[-:]|\b)", docket_number, re.I)
    )
    explicit_adversary_designation = _looks_like_adversary_designation(
        metadata.case_name or ""
    )
    # Some bankruptcy courts expose adversary proceedings through Case.dev with
    # a court-local number such as ``26-01028`` rather than an ``ap``/``adv``
    # marker.  A party-versus-party caption is still explicit adversary metadata
    # and is safe to retain for the later fail-closed Rule 7012 docket screen.
    explicit_adversary_caption = _looks_like_adversarial_caption(
        metadata.case_name or ""
    )
    return (
        explicit_adversary_number
        or explicit_adversary_designation
        or explicit_adversary_caption
    )


def _looks_like_adversarial_caption(text: str) -> bool:
    """Return whether text contains an explicit party-versus-party caption."""

    stripped = text.strip()
    if re.match(
        r"^(?:in\s+re|in\s+the\s+matter\s+of|matter\s+of|estate\s+of)\b",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Case.dev and CourtListener render the legal separator as lowercase ``v``.
    # Keeping this case-sensitive avoids treating a party's ``V.`` middle initial
    # as a versus delimiter.
    return bool(re.search(r"\S\s+v\.?\s+\S", stripped))


def _looks_like_adversary_designation(text: str) -> bool:
    """Return whether text explicitly designates an adversary docket."""

    return bool(re.search(r"\badversary\s+(?:proceeding|case)\b", text, re.I))


def _looks_like_federal_district_court(court_text: str) -> bool:
    lowered = court_text.lower()
    if "district court" in lowered and "bankruptcy" not in lowered:
        return True
    court_id = lowered.split(" ", maxsplit=1)[0]
    return bool(re.fullmatch(r"[a-z]{2,4}d?", court_id)) and not court_id.endswith("b")


def _looks_like_placeholder_or_sealed_docket(docket_number: str) -> bool:
    lowered = docket_number.lower()
    return "99999" in lowered or "sealed" in lowered or "placeholder" in lowered


def _looks_like_civil_cv_docket_number(docket_number: str) -> bool:
    return bool(
        re.search(r"(?:^|\b)\d{1,2}:\d{2,4}[-:]cv[-:]\d+", docket_number, re.I)
        or re.search(r"(?:^|\b)\d{2,4}[-:]cv[-:]\d+", docket_number, re.I)
        or re.search(r"(?:^|\b)cv[-:]\d+", docket_number, re.I)
    )


def _looks_like_non_civil_docket_number(docket_number: str) -> bool:
    return bool(
        re.search(
            r"(?:^|[-:])(?:cr|mj|mc|bk|ap|po|md|misc)(?:[-:]|\b)",
            docket_number,
            re.I,
        )
    )


def _looks_like_criminal_caption(case_name: str) -> bool:
    return bool(re.search(r"\b(?:united\s+states|u\.s\.|usa)\s+v[. ]", case_name, re.I))


def _entry_search_text(entry: CourtListenerWebDocketEntry) -> str:
    return _normalized_text(
        " ".join(
            (
                entry.text,
                " ".join(document.kind for document in entry.documents),
                " ".join(document.description for document in entry.documents),
                " ".join(document.action_label or "" for document in entry.documents),
            )
        )
    ).lower()


def _references_mtd_or_pleadings_motion(text: str) -> bool:
    return bool(
        re.search(r"\bmotions?\s+to\s+dismiss\b", text, re.I)
        or re.search(
            r"\bmotions?\s+by\b[^\n]{0,240}?\bto\s+dismiss\b",
            text,
            re.I,
        )
        or re.search(r"\bmtd\b", text, re.I)
        or re.search(r"\brule\s+12\b", text, re.I)
        or re.search(r"\b12\s*\(\s*b\s*\)\s*\(\s*[126]\s*\)", text, re.I)
        or re.search(r"\b12\s*\(\s*c\s*\)", text, re.I)
        or re.search(
            r"\b(?:partial\s+)?judgment\s+on\s+(?:the\s+)?pleadings\b",
            text,
            re.I,
        )
    )


def _looks_like_actual_mtd_decision(text: str) -> bool:
    return _has_decision_form(text) and _has_direct_mtd_disposition(text)


def _entry_narrative_before_documents(entry: CourtListenerWebDocketEntry) -> str:
    """Return row narrative without appended RECAP-document labels."""

    text = _normalized_text(entry.text)
    folded = text.casefold()
    offsets = [
        offset
        for document in entry.documents
        for field in (document.kind, document.description)
        if field
        if (offset := folded.find(_normalized_text(field).casefold())) >= 0
    ]
    return text[: min(offsets)] if offsets else text


def _has_direct_mtd_disposition(text: str) -> bool:
    """Return whether a disposition verb acts on the MTD or challenged pleading.

    Docket rows frequently combine a procedural ruling with a reference to a
    still-pending MTD.  Keep the verb and its target in the same clause so an
    order granting a stay or extension cannot borrow ``Motion to Dismiss`` from
    a later sentence. Generic event labels such as ``Order on Motion to
    Dismiss`` deliberately fail closed because they do not reveal what relief
    the court granted or denied.
    """

    text = re.sub(
        r"\b(?:ECF|Docket)\s+No\.",
        lambda match: match.group(0).removesuffix("."),
        text,
        flags=re.IGNORECASE,
    )
    action = (
        r"(?:grant(?:ed|ing|s)?|den(?:y|ied|ying|ies)|"
        r"terminat(?:ed|ing|es?)|dismiss(?:ed|es|ing)|"
        r"adopt(?:ed|ing|s)?)"
    )
    rule_12_motion = (
        r"(?:rule\s+12\s+motions?|"
        r"(?:rule\s+)?12\s*\(\s*[bc]\s*\)"
        r"(?:\s*\(\s*[126]\s*\))?\s+"
        r"(?:motions?|judgments?\s+on\s+the\s+pleadings)|"
        r"motions?\s+(?:under|pursuant\s+to)\s+(?:rule\s+)?12"
        r"(?:\s*\(\s*[bc]\s*\)(?:\s*\(\s*[126]\s*\))?)?)"
    )
    before_target_procedural_word = (
        r"(?:motion|extension|extend|respond|responses?|reply|oppos\w*|"
        r"stipulat\w*|stay|page|briefing|expedit\w*|"
        r"leave|file|filing|late|deadline|due)"
    )
    by_party_to_dismiss = (
        rf"motions?\s+by\b(?:(?!\b{before_target_procedural_word}\b)[^.;])"
        r"{0,100}?\bto\s+dismiss"
    )
    direct_object_target_motion = (
        r"(?:motions?\s+to\s+dismiss|"
        r"mtd|"
        rf"{rule_12_motion}|"
        r"motions?\s+for\s+(?:partial\s+)?judgment\s+on\s+"
        r"(?:the\s+)?pleadings)"
    )
    target_motion = (
        rf"(?:{direct_object_target_motion}|"
        rf"{by_party_to_dismiss})"
    )
    after_target_procedural_word = (
        r"(?:extension|extend|respond|responses?|reply|oppos\w*|stipulat\w*|"
        r"stay|page|briefing|expedit\w*|"
        r"leave|file|filing|late|deadline|due)"
    )
    before_target = rf"(?:(?!\b{before_target_procedural_word}\b)[^.;]){{0,120}}"
    after_target = rf"(?:(?!\b{after_target_procedural_word}\b)[^.;]){{0,240}}"
    clean_clause_prefix = (
        rf"(?:^|[.;])(?:(?!\b{before_target_procedural_word}\b)[^.;]){{0,240}}?"
    )
    disposition_qualifier = (
        r"(?:(?:in\s+part(?:\s+and\s+"
        r"(?:grant(?:ed|ing)?|den(?:ied|ying)?)\s+in\s+part)?|as\s+moot|"
        r"with(?:out)?\s+prejudice)\s+)?"
    )
    party_role = (
        r"(?:plaintiffs?|defendants?|petitioners?|respondents?|movants?|"
        r"parties?|appellants?|appellees?)"
    )
    possessive = r"(?:['\u2019]s|s['\u2019])"
    owner_word = r"[A-Za-z][\w.-]*,?"
    entity_suffix = (
        r"(?:llc|inc|corp|corporation|ltd|lp|llp|pllc|government|county|city|"
        r"state|department|agency)"
    )
    possessive_party = (
        rf"(?:{party_role}\s+(?:{owner_word}\s+){{0,4}}"
        rf"{owner_word}{possessive}\s+|"
        rf"(?:{owner_word}\s+){{1,6}}{entity_suffix}{possessive}\s+|"
        rf"{owner_word}\s+{owner_word}{possessive}\s+|"
        rf"{owner_word}{possessive}\s+)"
    )
    numbered_or_owned_target = (
        rf"(?:(?:\d+\s+)(?:{possessive_party})?|"
        rf"{possessive_party}(?:\d+\s+)?)?"
    )
    related_document_lead = r"(?:\(\s*related\s+documents?(?:\s*\(\s*s\s*\))?\s*:\s*)?"
    direct_target_lead = (
        rf"{disposition_qualifier}(?:the\s+)?{related_document_lead}"
        rf"{numbered_or_owned_target}"
    )
    if re.search(
        rf"\b{action}\b\s+{direct_target_lead}\b{direct_object_target_motion}\b",
        text,
        re.I,
    ):
        return True
    if re.search(
        rf"\b{action}\b[^.;]{{0,80}}\bmotions?\s+to\s+"
        rf"(?:stay|extend|expedite)\b[^.;]{{0,80}}\band\s+"
        rf"(?:the\s+)?{direct_object_target_motion}\b",
        text,
        re.I,
    ):
        return True
    if re.search(
        rf"{clean_clause_prefix}\b{target_motion}\b{after_target}"
        rf"\b(?:is|are|was|were|be|been|should\s+be)\s+"
        rf"(?:hereby\s+)?{action}\b",
        text,
        re.I,
    ):
        return True
    if re.search(
        rf"{clean_clause_prefix}\b{target_motion}\b"
        rf"(?:\s*(?:\[[^\]]+\]|\([^)]{{0,80}}\)|,|:))*\s+{action}\b",
        text,
        re.I,
    ):
        return True
    if re.search(
        rf"{clean_clause_prefix}\b{target_motion}\b{after_target}"
        r"\b(?:is|are|was|were|be|been|deemed|found)\s+moot\b",
        text,
        re.I,
    ):
        return True
    if re.search(
        rf"\b(?:find(?:s|ing)?|found)\b{before_target}\b{target_motion}\b"
        rf"{after_target}\bmoot\b",
        text,
        re.I,
    ):
        return True

    # A report may identify the target in one sentence and state its
    # recommendation in the next.  The report form plus this conventional
    # formulation proves the grammatical target without relying on proximity.
    if (
        re.search(r"\breport\s+and\s+recommendation\b", text, re.I)
        or _has_magistrate_recommendation_form(text)
    ) and (
        (
            re.search(
                rf"\brecommends?\s+(?:that\s+)?the\s+motion\s+"
                rf"(?:should\s+)?(?:be\s+)?{action}\b",
                text,
                re.I,
            )
            or re.search(
                rf"\brecommends?\s+{action}\b{before_target}\bthe\s+motion\b",
                text,
                re.I,
            )
        )
        and re.search(
            r"\bmotions?\s+(?:to\s+dismiss|by\b[^.;]{0,100}?\bto\s+dismiss)\b",
            text,
            re.I,
        )
    ):
        return True

    # Some merits orders state the result as dismissal of the challenged
    # pleading rather than disposition of the motion itself.
    same_clause = r"[^.;]{0,120}"
    challenged_pleading = r"(?:complaint|amended\s+complaint|claims?|counts?|action)"
    if re.search(
        rf"\b(?<!to\s)(?:dismiss(?:ed|es|ing)|terminat(?:ed|ing|es?))\b"
        rf"{same_clause}\b{challenged_pleading}\b",
        text,
        re.I,
    ):
        return True
    return bool(
        re.search(
            rf"\b{challenged_pleading}\b{same_clause}"
            rf"\b(?:is|are|be|been)\s+(?:dismissed|terminated)\b",
            text,
            re.I,
        )
        or re.search(
            r"\bdismissal\s+(?:is|was|be)\s+(?:hereby\s+)?granted\b",
            text,
            re.I,
        )
    )


def _has_decision_form(text: str) -> bool:
    return bool(
        re.search(r"\border\b", text, re.I)
        or re.search(r"\bopinion\b", text, re.I)
        or re.search(r"\bdecision\b", text, re.I)
        or re.search(r"\bruling\b", text, re.I)
        or re.search(r"\bjudgment\b", text, re.I)
        or re.search(r"\bmemorandum\s+(?:and\s+)?opinion\b", text, re.I)
        or re.search(r"\breport\s+and\s+recommendation\b", text, re.I)
        or _has_magistrate_recommendation_form(text)
        or re.search(
            r"\bminute(?:\s+\([^)]{0,80}\))?\b[^\n]{0,240}?"
            r"\bthe\s+court\s+(?:hereby\s+)?"
            r"(?:grant(?:s|ed)?|den(?:y|ies|ied)|dismiss(?:es|ed)?)\b",
            text,
            re.I,
        )
    )


def _has_magistrate_recommendation_form(text: str) -> bool:
    return bool(
        re.search(
            r"\brecommendation\s+(?:of|by)\s+(?:the\s+)?"
            r"(?:united\s+states\s+)?magistrate\s+judge\b",
            text,
            re.I,
        )
    )


def _has_substantive_mtd_recommendation(text: str) -> bool:
    recommendation_form = bool(
        re.search(r"\breport\s+and\s+recommendation\b", text, re.I)
        or _has_magistrate_recommendation_form(text)
    )
    recommends_disposition = bool(
        re.search(
            r"\brecommend(?:s|ed|ing|ation)?\b[^\n]{0,240}?"
            r"\b(?:grant(?:ed|ing)?|den(?:y|ied|ying)|dismiss(?:ed|ing)?)\b",
            text,
            re.I,
        )
    )
    return (
        recommendation_form
        and recommends_disposition
        and _references_mtd_or_pleadings_motion(text)
    )


def _has_disposition_terms(text: str) -> bool:
    return bool(
        re.search(r"\bgrant(?:ed|ing|s)?\b", text, re.I)
        or re.search(r"\bden(?:y|ied|ying|ies)\b", text, re.I)
        or re.search(r"\bdismiss(?:ed|es|ing|al)\b", text, re.I)
        or re.search(r"\bterminat(?:ed|ing|es?)\b", text, re.I)
        or re.search(r"\bmoot\b", text, re.I)
        or re.search(r"\badopt(?:ed|ing|s)?\b", text, re.I)
    )


def _looks_like_notice_of_removal_or_state_record(text: str) -> bool:
    return bool(
        re.search(r"\bnotice\s+of\s+removal\b", text, re.I)
        or re.search(
            r"\bstate\s+court\s+(?:complaint|record|docket|order)\b",
            text,
            re.I,
        )
        or re.search(r"\bno\s+answer\s*/\s*motion\s+to\s+dismiss\s+filed\b", text, re.I)
    )


def _looks_like_proposed_order_attachment(text: str) -> bool:
    if not re.search(r"\bproposed\s+order\b", text, re.I):
        return False
    return not _has_disposition_terms(_text_before_first_attachment(text))


def _looks_like_procedural_or_standing_order(text: str) -> bool:
    standing_order = bool(re.search(r"\bstanding\s+order\b", text, re.I))
    future_show_cause_on_mtd = bool(
        re.search(
            r"\b(?:order(?:ed|ing)?|direct(?:ed|ing|s)?)\b[^\n]{0,160}"
            r"\bto\s+show\s+cause\b[^\n]{0,320}\bwhy\b[^\n]{0,240}"
            r"\bmotion\s+to\s+dismiss\b[^\n]{0,120}"
            r"\bshould\s+not\s+be\s+granted\b",
            text,
            re.IGNORECASE,
        )
    )
    if future_show_cause_on_mtd:
        return True
    conditional_amendment_order = bool(
        re.search(r"\bshall\s+file\b[^.;]{0,120}\bamended\s+complaint\b", text, re.I)
        and re.search(r"\bif\b[^.;]{0,120}\bamend(?:ed|ment|s)?\b", text, re.I)
        and re.search(
            r"\b(?:opposition|response|reply|briefing|new\s+motion\s+to\s+dismiss)\b",
            text,
            re.I,
        )
    )
    clauses = re.split(r"(?<=[.;])\s+", text)
    conditional_disposition = any(
        _has_prospective_condition(clause)
        and _references_mtd_or_pleadings_motion(clause)
        and (
            _has_direct_mtd_disposition(clause)
            or re.search(
                r"\b(?:shall|will|would|may)\b[^.;]{0,80}"
                r"\b(?:grant(?:ed)?|den(?:y|ied)|dismiss(?:ed)?)\b",
                clause,
                re.IGNORECASE,
            )
        )
        for clause in clauses
    )
    unconditional_text = " ".join(
        clause for clause in clauses if not _has_prospective_condition(clause)
    )
    if (conditional_amendment_order or conditional_disposition) and not (
        _has_direct_mtd_disposition(unconditional_text)
        or _has_explicit_mtd_merits_disposition(unconditional_text)
    ):
        return True
    if _has_direct_mtd_disposition(text) or _has_explicit_mtd_merits_disposition(text):
        return False
    procedural_patterns = (
        r"\border\s+governing\b.*\bmotions?\s+to\s+dismiss\b",
        r"\bpre[- ]?motion\s+conference\b",
        r"\bconference\s+before\s+fil(?:ing|e)\b.*\bmotion\s+to\s+dismiss\b",
        r"\bbriefing\s+schedule\b",
        r"\bschedule\s+for\s+briefing\b",
        r"\bset(?:s|ting)?\s+briefing\b",
        r"\bextension\s+of\s+time\b.*\bmotion\s+to\s+dismiss\b",
        r"\btime\s+to\s+(?:respond|reply|file|oppose)\b.*\bmotion\s+to\s+dismiss\b",
        r"\bmotion\s+to\s+file\b.*\breply\b.*\bmotion\s+to\s+dismiss\b",
        r"\bleave\s+to\s+file\b.*\breply\b",
        r"\bdeadline\s+to\s+(?:respond|reply|file|oppose)\b.*\bmotion\s+to\s+dismiss\b",
        r"\bmotion\s+(?:for|to)\s+(?:stay|extend|extension|expedite)\b.*\bmotion\s+to\s+dismiss\b",
        r"\bstay(?:ed|ing|s)?\b.*\bpending\b.*\bmotion\s+to\s+dismiss\b",
        r"\bpending\s+(?:resolution|adjudication)\b.*\bmotion\s+to\s+dismiss\b",
        r"\b(?:exceed|enlarge|extend)\b.*\bpage\s+limit\b.*\bmotion\s+to\s+dismiss\b",
        r"\bexpedit(?:e|ed|ing)\b.*\b(?:briefing|hearing|schedule)\b.*\bmotion\s+to\s+dismiss\b",
        r"\border\s+to\s+show\s+cause\b",
        r"\bfailure\s+to\s+prosecute\b",
        r"\badministrative(?:ly)?\s+clos(?:e|ed|ing)\b",
    )
    if any(re.search(pattern, text, re.I) for pattern in procedural_patterns):
        return True
    return standing_order and not _has_substantive_mtd_recommendation(text)


def _has_prospective_condition(clause: str) -> bool:
    if_or_unless = bool(re.search(r"\b(?:if|unless)\b", clause, re.IGNORECASE))
    prospective_event = bool(
        re.search(
            r"\b(?:amend(?:ed|ing|ment|s)?|file[ds]?|filing|serve[ds]?|"
            r"service|submit(?:ted|s)?|submission|respond(?:ed|ing|s)?|"
            r"oppos(?:e|ed|es|ing|ition)|repl(?:y|ied|ies)|brief(?:ed|ing|s)?)\b",
            clause,
            re.IGNORECASE,
        )
    )
    future_disposition = bool(
        re.search(
            # ``entry.text`` begins with its filed date.  Do not mistake the
            # month in ``May 9, 2026 ORDER granting ...`` for a future modal.
            r"\b(?:shall|will|would|may(?!\s+\d))\b[^.;]{0,80}"
            r"\b(?:grant(?:ed)?|den(?:y|ied)|dismiss(?:ed)?|moot|decide[ds]?)\b",
            clause,
            re.IGNORECASE,
        )
    )
    prospective_upon = bool(
        re.search(
            r"\bupon\b[^.;]{0,60}\b(?:filing|submission|service)\b"
            r"[^.;]{0,60}\bamended\s+complaint\b",
            clause,
            re.IGNORECASE,
        )
    )
    return (
        if_or_unless and (prospective_event or future_disposition)
    ) or prospective_upon


def _looks_like_self_or_voluntary_dismissal(text: str) -> bool:
    return bool(
        re.search(r"\bvoluntary\s+dismissal\b", text, re.I)
        or re.search(r"\bstipulation\s+of\s+dismissal\b", text, re.I)
        or re.search(
            r"\b(?:plaintiff|petitioner|claimant|movant)'?s?\s+"
            r"(?:unopposed\s+)?motion\s+to\s+dismiss\b",
            text,
            re.I,
        )
        or re.search(r"\bmotion\s+to\s+dismiss\s+(?:current\s+)?petition\b", text, re.I)
    )


def _looks_like_transfer_only(text: str) -> bool:
    if not re.search(r"\btransfer(?:red|ring)?\b", text, re.I):
        return False
    references_alternative_transfer = bool(
        re.search(r"\bmotion\s+to\s+dismiss\s+or\s+transfer\b", text, re.I)
        or re.search(
            r"\bmotion\s+to\s+dismiss\s+or\s*,?\s*"
            r"(?:in\s+the\s+alternative\s*,?\s*)?transfer\b",
            text,
            re.I,
        )
        or re.search(r"\balternative\s+motion\s+to\s+transfer\b", text, re.I)
    )
    no_claim_dismissal = not re.search(
        r"\bdismiss(?:ed|ing|al)\s+(?:the\s+)?(?:complaint|claim|count|case)\b",
        text,
        re.I,
    )
    return (
        references_alternative_transfer
        and no_claim_dismissal
        and not _has_explicit_mtd_merits_disposition(text)
    )


def _has_explicit_mtd_merits_disposition(text: str) -> bool:
    motion = (
        r"(?:\d+\s+)?motions?\s+(?:to\s+dismiss|"
        r"for\s+judgment\s+on\s+the\s+pleadings)"
    )
    disposition = r"(?:grant(?:ed|ing|s)?|den(?:y|ied|ying|ies))"
    return bool(
        re.search(
            rf"\b{motion}\s+(?:is|are|was|were|be)\s+"
            rf"(?:hereby\s+)?{disposition}\b",
            text,
            re.I,
        )
        or re.search(
            rf"\b{disposition}\s+(?:in\s+part\s+)?(?:the\s+)?"
            rf"(?:[A-Za-z][\w'.\-]*\s+)?{motion}\b",
            text,
            re.I,
        )
        or re.search(
            r"\b(?:complaint|claim|count|case|action)\s+"
            r"(?:is|are|was|were|be)\s+(?:hereby\s+)?dismissed\b",
            text,
            re.I,
        )
        or re.search(
            r"\bdismissal\s+(?:is|was|be)\s+(?:hereby\s+)?granted\b",
            text,
            re.I,
        )
    )


def _text_before_first_attachment(text: str) -> str:
    return re.split(r"\battachments?:\b|\batt\s+\d+\b", text, maxsplit=1, flags=re.I)[0]


def _strict_posture_exclusion_reasons(
    text: str,
    *,
    allow_bankruptcy_adversary: bool = False,
) -> tuple[str, ...]:
    lowered = text.lower()
    reasons: list[str] = []
    if re.search(
        r"\b(?:habeas|2254|2241|warden|prisoner|detention\s+center|"
        r"correctional\s+(?:institution|facility)|ice|removal\s+center|"
        r"field\s+office\s+director|bondi|immigration\s+detention|"
        r"petition\s+for\s+writ)\b|(?:^|\W)hc(?:\W|$)",
        lowered,
        re.I,
    ):
        reasons.append("habeas_or_immigration_detention_posture")
    if (
        "bankruptcy" in lowered or "adversary proceeding" in lowered
    ) and not allow_bankruptcy_adversary:
        reasons.append("bankruptcy_posture")
    if re.search(r"\bcriminal\b|\b(?:united states|u\.s\.|usa)\s+v[. ]", lowered):
        reasons.append("criminal_posture")
    return tuple(dict.fromkeys(reasons))


def _looks_like_social_security_merits_jop(
    *, context_text: str, decision_text: str
) -> bool:
    """Reject administrative merits review mislabeled as a Rule 12(c) case."""

    commissioner_social_security_review = (
        _looks_like_commissioner_social_security_context(context_text)
    )
    named_social_security_agency = bool(
        commissioner_social_security_review
        or re.search(
            r"\bsocial\s+security\s+administration\b",
            context_text,
            re.I,
        )
    )
    alj_reference = bool(
        re.search(r"\badministrative\s+law\s+judge\b", decision_text, re.I)
        or re.search(r"\balj\b", decision_text, re.I)
    )
    commissioner_final_decision = bool(
        re.search(
            r"\b(?:commissioner|agency|ssa)(?:['\u2019]s)?\s+"
            r"(?:final\s+)?(?:decision|determination)\b",
            decision_text,
            re.I,
        )
    )
    administrative_remand = bool(
        re.search(
            r"\bremand\w*\b[^.;]{0,120}\b(?:further\s+)?"
            r"administrative\s+proceedings\b",
            decision_text,
            re.I,
        )
    )
    administrative_disposition = bool(
        re.search(
            r"\b(?:affirm(?:ed|ing|s)?|revers(?:e|ed|es|ing)|"
            r"uphold(?:s|ing)?|vacat(?:e|ed|es|ing)|remand(?:ed|ing|s)?)\b",
            decision_text,
            re.I,
        )
    )
    # CourtListener captions often use only the incumbent Commissioner's
    # surname.  The decision row itself can nevertheless prove administrative
    # merits review when it couples the ALJ/Commissioner's final decision with
    # an affirmance, reversal, vacatur, or administrative remand.
    strong_administrative_review = (alj_reference or commissioner_final_decision) and (
        administrative_disposition or administrative_remand
    )
    social_security_review = (
        named_social_security_agency or strong_administrative_review
    )
    administrative_merits = bool(
        # An explicit Commissioner-of-Social-Security caption identifies the
        # statutory merits-review posture even when the terse docket row says
        # only that a cross-motion for judgment on the pleadings was resolved.
        commissioner_social_security_review
        or alj_reference
        or re.search(
            r"\bdecision\s+of\s+the\s+(?:commissioner|agency)\b",
            decision_text,
            re.I,
        )
        or commissioner_final_decision
        or re.search(
            r"\bremand(?:ed|ing)?\s+to\s+(?:the\s+)?agency\b",
            decision_text,
            re.I,
        )
        or administrative_remand
    )
    judgment_on_pleadings = bool(
        re.search(
            r"\b(?:partial\s+)?judgment\s+on\s+(?:the\s+)?pleadings\b",
            decision_text,
            re.I,
        )
    )
    independent_rule_12_basis = _has_disposition_linked_rule_12_basis(decision_text)
    return (
        social_security_review
        and administrative_merits
        and judgment_on_pleadings
        and not independent_rule_12_basis
    )


def _looks_like_commissioner_social_security_context(text: str) -> bool:
    """Return whether a caption names the disability-review Commissioner."""

    return bool(
        re.search(
            r"\b(?:acting\s+)?commissioner(?:\s+of)?\s*,?\s*(?:the\s+)?"
            r"(?:social\s+security(?:\s+administration)?|ssa)\b",
            text,
            re.I,
        )
    )


def _has_disposition_linked_rule_12_basis(decision_text: str) -> bool:
    """Require Rule 12 evidence to modify the disposition being screened."""

    for clause in re.split(r"(?<=[.;])\s+", decision_text):
        judgment_on_pleadings = re.search(
            r"\b(?:partial\s+)?judgment\s+on\s+(?:the\s+)?pleadings\b",
            clause,
            re.I,
        )
        explicit_jop_rule = bool(
            judgment_on_pleadings
            and (
                re.search(r"\b(?:rule\s+)?12\s*\(\s*c\s*\)", clause, re.I)
                or _references_rule_7012(clause)
            )
        )
        direct_mtd_disposition = bool(
            re.search(
                r"\bmotion\s+to\s+dismiss\b|\bmtd\b|"
                r"\b(?:rule\s+)?12\s*\(\s*b\s*\)",
                clause,
                re.I,
            )
            and _has_direct_mtd_disposition(clause)
        )
        if explicit_jop_rule or direct_mtd_disposition:
            return True
    return False


def _looks_like_bankruptcy_context(text: str) -> bool:
    lowered = text.lower()
    court_ids = set(re.findall(r"\b[a-z]{2,5}b\b", lowered))
    return bool(
        "bankruptcy" in lowered
        or "adversary complaint" in lowered
        or _looks_like_adversary_designation(text)
        or court_ids.intersection(_BANKRUPTCY_COURT_IDS)
        or re.search(r"(?:^|[-:])(?:ap|adv)(?:[-:]|\b)", lowered)
        or _references_rule_7012(lowered)
    )


def _references_rule_7012(text: str) -> bool:
    """Return whether text explicitly cites Bankruptcy Rule 7012."""

    return bool(
        re.search(r"\brule\s+7012\b", text, re.I)
        or re.search(
            r"\b(?:fed(?:eral)?\.?\s+r\.?\s+)?bankr\.?\s+p\.?\s+7012\b",
            text,
            re.I,
        )
        or re.search(r"\bfrbp\s*7012\b", text, re.I)
    )


def _bankruptcy_adversary_exclusion_reasons(
    page: CourtListenerWebDocketPage,
    *,
    combined_text: str,
    candidate_text: str | None,
) -> tuple[str, ...]:
    """Fail closed unless docket rows prove the ordinary Rule 12 task."""

    reasons: list[str] = []
    if re.search(r"(?:^|[-:])bk(?:[-:]|\b)", combined_text, re.I):
        return ("bankruptcy_posture",)
    adversary_identity = bool(
        re.search(r"(?:^|[-:])(?:ap|adv)(?:[-:]|\b)", combined_text, re.I)
        or _looks_like_adversary_designation(page.title or "")
        or _looks_like_adversary_designation(candidate_text or "")
        or _looks_like_adversarial_caption(page.title or "")
        or _looks_like_adversarial_caption(candidate_text or "")
    )
    if not adversary_identity:
        return ("bankruptcy_posture",)

    entry_texts = tuple(_entry_search_text(entry) for entry in page.entries)
    if not any(_looks_like_adversary_initiating_pleading(text) for text in entry_texts):
        reasons.append("bankruptcy_adversary_initiating_pleading_unproven")
    if not any(_looks_like_rule_7012_claim_merits_motion(text) for text in entry_texts):
        reasons.append("bankruptcy_adversary_rule_basis_unproven")
    return tuple(reasons)


def _looks_like_adversary_initiating_pleading(text: str) -> bool:
    if re.search(r"\b(?:certificate|notice|response|opposition)\b", text, re.I):
        return False
    return bool(
        re.search(r"\b(?:adversary\s+)?complaint\b|\bcounterclaim\b", text, re.I)
    )


def _looks_like_rule_7012_claim_merits_motion(text: str) -> bool:
    motion = bool(
        re.search(r"\bmotion\b", text, re.I)
        and re.search(r"\bdismiss\b|\bjudgment\s+on\s+the\s+pleadings\b", text, re.I)
    )
    rule_basis = bool(
        _references_rule_7012(text)
        or re.search(r"\b12\s*\(\s*b\s*\)\s*\(\s*[1-7]\s*\)", text, re.I)
        or re.search(r"\b12\s*\(\s*c\s*\)", text, re.I)
        or re.search(r"\bjudgment\s+on\s+the\s+pleadings\b", text, re.I)
        or re.search(
            r"\brule\s+12\s*\(\s*b\s*\)\s*[-\u2013]\s*\(\s*i\s*\)",
            text,
            re.I,
        )
    )
    pleading_scope = bool(
        re.search(
            r"\b(?:complaint|counterclaim|count|claim|cause\s+of\s+action)s?\b",
            text,
            re.I,
        )
        or re.search(r"\bjudgment\s+on\s+the\s+pleadings\b", text, re.I)
    )
    # Bankruptcy docket event codes often say only ``Motion, Dismiss Adversary
    # Proceeding``.  That directly identifies the Rule-12-equivalent target even
    # when the clerk omits a Rule 7012 citation; generic case dismissals do not.
    explicit_adversary_pleading_target = bool(
        re.search(
            r"\bdismiss\b[^.;]{0,100}\b(?:adversary\s+(?:proceeding|case|complaint)|"
            r"complaint|counterclaim|count|claim|cause\s+of\s+action)s?\b",
            text,
            re.I,
        )
    )
    nonmerits_dismissal = bool(
        re.search(r"\b(?:administrative|voluntary|stipulated)\b", text, re.I)
        or _looks_like_self_or_voluntary_dismissal(text)
    )
    return (
        motion
        and not nonmerits_dismissal
        and ((rule_basis and pleading_scope) or explicit_adversary_pleading_target)
    )


def _dominant_exclusion_reasons(
    entry_screens: Sequence[MtdDecisionEntryScreen],
) -> tuple[str, ...]:
    counter: Counter[str] = Counter()
    for screen in entry_screens:
        counter.update(screen.exclusion_reasons)
    if not counter:
        return ("no_docket_entries",)
    if counter.get("no_mtd_or_rule_12_reference") == sum(counter.values()):
        return ("no_actual_mtd_decision",)
    # Unrelated docket rows can numerically swamp the one MTD-referencing row
    # that proves the discovery hit was only a procedural order.  Preserve that
    # decisive reason ahead of generic per-row noise so the candidate-level
    # exclusion remains specific and auditable.
    if counter.get("procedural_or_standing_order"):
        remaining = (
            reason
            for reason, _count in counter.most_common()
            if reason != "procedural_or_standing_order"
        )
        return ("procedural_or_standing_order", *tuple(remaining)[:2])
    return tuple(reason for reason, _count in counter.most_common(3))


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _estimated_screened_count(
    *,
    retained_count: int,
    screened_count: int,
    target_count: int,
) -> int | None:
    if retained_count <= 0 or screened_count <= 0:
        return None
    return math.ceil(target_count * screened_count / retained_count)


def _courtlistener_docket_id(record: Mapping[str, object]) -> str | None:
    for field_name in ("url", "source_url", "sourceUrl"):
        value = record.get(field_name)
        if not isinstance(value, str):
            continue
        match = re.search(r"/(?:api/rest/v\d+/)?dockets?/(\d+)/", value)
        if match is not None:
            return match.group(1)
    return _optional_text(record, "id", "docketId", "docket_id", "case_id", "caseId")


def _decision_date_in_window(
    filed_at: str | None,
    *,
    decision_filed_on_or_after: date | None,
    decision_filed_on_or_before: date | None,
) -> bool:
    if decision_filed_on_or_after is None and decision_filed_on_or_before is None:
        return True
    filed_date = parse_courtlistener_filed_date(filed_at)
    if filed_date is None:
        return False
    if (
        decision_filed_on_or_after is not None
        and filed_date < decision_filed_on_or_after
    ):
        return False
    if (
        decision_filed_on_or_before is not None
        and filed_date > decision_filed_on_or_before
    ):
        return False
    return True


def _nested_mapping(
    record: Mapping[str, object],
    field_name: str,
) -> Mapping[str, object] | None:
    value = record.get(field_name)
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None


def _optional_text(record: Mapping[str, object], *field_names: str) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
