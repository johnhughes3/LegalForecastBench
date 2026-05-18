"""Targeted fallback rules for case.dev-first candidate ingestion."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.selection.case_mix_diagnostics import FallbackSource


class FallbackGap(StrEnum):
    DOCKET_ENTRY_LISTING_UNAVAILABLE = "docket_entry_listing_unavailable"
    CASE_METADATA_MISSING = "case_metadata_missing"
    DOCKET_HISTORY_MISSING = "docket_history_missing"
    MISSING_COMPLAINT_DOCUMENT = "missing_complaint_document"
    MISSING_MOTION_DOCUMENT = "missing_motion_document"
    MISSING_OPPOSITION_DOCUMENT = "missing_opposition_document"
    MISSING_REPLY_DOCUMENT = "missing_reply_document"
    MISSING_DISPOSITION_DOCUMENT = "missing_disposition_document"
    SOURCE_DOCUMENT_DOWNLOAD_UNAVAILABLE = "source_document_download_unavailable"
    UNCLEAN_LINKAGE_FROM_INCOMPLETE_DOCKET = "unclean_linkage_from_incomplete_docket"
    TEXT_EXTRACTION_FAILED = "text_extraction_failed"
    SEALED_OR_RESTRICTED_MATERIAL = "sealed_or_restricted_material"
    OUTCOME_LEAKAGE = "outcome_leakage"
    AMBIGUOUS_MOTION_ORDER_LINKAGE = "ambiguous_motion_order_linkage"


class FallbackDecisionStatus(StrEnum):
    CASE_DEV_ONLY = "case.dev-only"
    CASE_DEV_PLUS_FALLBACK = "case.dev-plus-fallback"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class TargetedFallbackRule:
    """One pre-specified fallback rule for a case.dev ingestion gap."""

    gap: FallbackGap
    preferred_sources: tuple[FallbackSource, ...]
    exclusion_reason: str
    note: str

    def __post_init__(self) -> None:
        if not self.exclusion_reason.strip():
            raise ValueError("exclusion_reason is required")
        if not self.note.strip():
            raise ValueError("note is required")
        for source in self.preferred_sources:
            if source is FallbackSource.CASE_DEV_ONLY:
                raise ValueError(
                    "fallback rules must not use case.dev-only as fallback"
                )

    @property
    def fallback_allowed(self) -> bool:
        return bool(self.preferred_sources)

    def to_record(self) -> dict[str, Any]:
        return {
            "gap": self.gap.value,
            "preferred_sources": [source.value for source in self.preferred_sources],
            "exclusion_reason": self.exclusion_reason,
            "fallback_allowed": self.fallback_allowed,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    """Auditable source decision for one candidate after case.dev retrieval."""

    status: FallbackDecisionStatus
    fallback_source: FallbackSource
    fallback_reason: str | None
    exclusion_reason: str | None
    rule: TargetedFallbackRule | None = None

    def __post_init__(self) -> None:
        if self.status is FallbackDecisionStatus.CASE_DEV_ONLY:
            if self.fallback_source is not FallbackSource.CASE_DEV_ONLY:
                raise ValueError("case.dev-only decisions cannot set fallback_source")
            if self.fallback_reason is not None or self.exclusion_reason is not None:
                raise ValueError(
                    "case.dev-only decisions cannot set fallback/exclusion"
                )
        elif self.status is FallbackDecisionStatus.CASE_DEV_PLUS_FALLBACK:
            if self.fallback_source is FallbackSource.CASE_DEV_ONLY:
                raise ValueError("fallback decisions require a supplemental source")
            _require_non_empty(self.fallback_reason or "", "fallback_reason")
            if self.exclusion_reason is not None:
                raise ValueError("included fallback decisions cannot set exclusion")
            if self.rule is None:
                raise ValueError("fallback decisions require a rule")
        elif self.status is FallbackDecisionStatus.EXCLUDED:
            if self.fallback_source is not FallbackSource.CASE_DEV_ONLY:
                raise ValueError("excluded fallback decisions should not set source")
            _require_non_empty(self.exclusion_reason or "", "exclusion_reason")

    @property
    def included_in_benchmark(self) -> bool:
        return self.status is not FallbackDecisionStatus.EXCLUDED

    @property
    def fallback_used(self) -> bool:
        return self.status is FallbackDecisionStatus.CASE_DEV_PLUS_FALLBACK

    def to_case_mix_fields(self) -> dict[str, Any]:
        return {
            "fallback_used": self.fallback_used,
            "fallback_source": self.fallback_source,
            "fallback_reason": self.fallback_reason,
            "included_in_benchmark": self.included_in_benchmark,
            "exclusion_reason": self.exclusion_reason,
        }

    def to_record(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "fallback_used": self.fallback_used,
            "fallback_source": self.fallback_source.value,
            "fallback_reason": self.fallback_reason,
            "included_in_benchmark": self.included_in_benchmark,
            "exclusion_reason": self.exclusion_reason,
            "rule": self.rule.to_record() if self.rule is not None else None,
        }


_DOCKET_FALLBACK_SOURCES = (
    FallbackSource.COURTLISTENER_RECAP,
    FallbackSource.COURTLISTENER,
    FallbackSource.RECAP,
    FallbackSource.PACER,
)
_DOCUMENT_FALLBACK_SOURCES = (
    FallbackSource.COURTLISTENER_RECAP,
    FallbackSource.RECAP,
    FallbackSource.PACER,
)

_FALLBACK_RULES = (
    TargetedFallbackRule(
        gap=FallbackGap.DOCKET_ENTRY_LISTING_UNAVAILABLE,
        preferred_sources=_DOCKET_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_docket_entry_listing",
        note=(
            "case.dev search may identify the candidate, but docket rows must be "
            "provided by case.dev or by an explicitly enabled fallback source."
        ),
    ),
    TargetedFallbackRule(
        gap=FallbackGap.CASE_METADATA_MISSING,
        preferred_sources=_DOCKET_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_case_metadata",
        note=(
            "Recover missing court, docket, judge, or NOS metadata from public dockets."
        ),
    ),
    TargetedFallbackRule(
        gap=FallbackGap.DOCKET_HISTORY_MISSING,
        preferred_sources=_DOCKET_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_docket_history",
        note="Recover the docket sheet before attempting motion/order linkage.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.MISSING_COMPLAINT_DOCUMENT,
        preferred_sources=_DOCUMENT_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_complaint",
        note="A complaint or operative amended complaint is required for units.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.MISSING_MOTION_DOCUMENT,
        preferred_sources=_DOCUMENT_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_motion",
        note="A target MTD notice or memorandum is required for clean packets.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.MISSING_OPPOSITION_DOCUMENT,
        preferred_sources=_DOCUMENT_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_opposition",
        note="If an opposition was filed, try public archives before excluding.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.MISSING_REPLY_DOCUMENT,
        preferred_sources=_DOCUMENT_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_reply",
        note=(
            "A filed reply should be recovered when available; missing replies "
            "remain reported."
        ),
    ),
    TargetedFallbackRule(
        gap=FallbackGap.MISSING_DISPOSITION_DOCUMENT,
        preferred_sources=_DOCUMENT_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_disposition",
        note="The first written disposition is required for labels and leakage checks.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.SOURCE_DOCUMENT_DOWNLOAD_UNAVAILABLE,
        preferred_sources=_DOCUMENT_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_source_document",
        note="A known public document handle may be rehydrated from RECAP or PACER.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.UNCLEAN_LINKAGE_FROM_INCOMPLETE_DOCKET,
        preferred_sources=_DOCKET_FALLBACK_SOURCES,
        exclusion_reason="fallback_unavailable_linkage_docket",
        note=(
            "Use fallback only when linkage is unclear because docket history "
            "is incomplete."
        ),
    ),
    TargetedFallbackRule(
        gap=FallbackGap.TEXT_EXTRACTION_FAILED,
        preferred_sources=(),
        exclusion_reason="insufficient_text_quality",
        note=(
            "Provider fallback is not a substitute for extraction/OCR quality control."
        ),
    ),
    TargetedFallbackRule(
        gap=FallbackGap.SEALED_OR_RESTRICTED_MATERIAL,
        preferred_sources=(),
        exclusion_reason="sealed_or_restricted_material",
        note=(
            "Do not use fallback to bypass sealed, restricted, or access-limited "
            "material."
        ),
    ),
    TargetedFallbackRule(
        gap=FallbackGap.OUTCOME_LEAKAGE,
        preferred_sources=(),
        exclusion_reason="outcome_leakage",
        note="Outcome leakage is a hard exclusion, not a retrieval gap.",
    ),
    TargetedFallbackRule(
        gap=FallbackGap.AMBIGUOUS_MOTION_ORDER_LINKAGE,
        preferred_sources=(),
        exclusion_reason="ambiguous_motion_order_linkage",
        note="True linkage ambiguity after complete docket review is excluded.",
    ),
)
FALLBACK_RULES_BY_GAP = {rule.gap: rule for rule in _FALLBACK_RULES}


def targeted_fallback_rules() -> tuple[TargetedFallbackRule, ...]:
    """Return the frozen targeted fallback rule table."""

    return _FALLBACK_RULES


def decide_targeted_fallback(
    gap: FallbackGap | str | None,
    *,
    available_sources: Iterable[FallbackSource | str] = (),
) -> FallbackDecision:
    """Choose case.dev-only, targeted fallback, or exclusion for one gap."""

    if gap is None:
        return FallbackDecision(
            status=FallbackDecisionStatus.CASE_DEV_ONLY,
            fallback_source=FallbackSource.CASE_DEV_ONLY,
            fallback_reason=None,
            exclusion_reason=None,
            rule=None,
        )

    parsed_gap = FallbackGap(gap)
    rule = FALLBACK_RULES_BY_GAP[parsed_gap]
    selected_source = _first_available(rule.preferred_sources, available_sources)
    if selected_source is not None:
        return FallbackDecision(
            status=FallbackDecisionStatus.CASE_DEV_PLUS_FALLBACK,
            fallback_source=selected_source,
            fallback_reason=parsed_gap.value,
            exclusion_reason=None,
            rule=rule,
        )

    return FallbackDecision(
        status=FallbackDecisionStatus.EXCLUDED,
        fallback_source=FallbackSource.CASE_DEV_ONLY,
        fallback_reason=None,
        exclusion_reason=rule.exclusion_reason,
        rule=rule,
    )


def _first_available(
    preferred_sources: tuple[FallbackSource, ...],
    available_sources: Iterable[FallbackSource | str],
) -> FallbackSource | None:
    available = {FallbackSource(source) for source in available_sources}
    for source in preferred_sources:
        if source in available:
            return source
    return None


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
