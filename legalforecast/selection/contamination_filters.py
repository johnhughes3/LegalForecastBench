"""Outcome-leakage filters for candidate selection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class LeakageSourceKind(StrEnum):
    """Kinds of pre-run material inspected for target-outcome leakage."""

    DOCKET_ENTRY = "docket_entry"
    DOCUMENT_TEXT = "document_text"
    ORAL_RULING_TRANSCRIPT = "oral_ruling_transcript"
    REPORT_AND_RECOMMENDATION = "report_and_recommendation"
    TENTATIVE_RULING = "tentative_ruling"
    WRITTEN_QUESTION = "written_question"
    RELATED_CASE_ORDER = "related_case_order"
    PUBLIC_REPORTING = "public_reporting"


class OutcomeLeakageType(StrEnum):
    """Hard-exclusion leakage categories from the benchmark protocol."""

    MINUTE_ORDER = "minute_order_resolving_target"
    ORAL_RULING_TRANSCRIPT = "oral_ruling_transcript_resolving_target"
    REPORT_AND_RECOMMENDATION = "rr_already_resolving_target"
    TENTATIVE_RULING = "tentative_ruling_revealing_target"
    WRITTEN_QUESTION = "written_question_revealing_disposition"
    RELATED_CASE_ORDER = "related_case_order_resolving_identical_units"
    PUBLIC_REPORTING = "public_reporting_revealing_target"


@dataclass(frozen=True, slots=True)
class LeakageSource:
    """One source available before model evaluation."""

    source_id: str
    source_kind: LeakageSourceKind
    text: str
    observed_at: datetime
    related_family_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.text, "text")
        _require_aware(self.observed_at, "observed_at")
        if self.related_family_id is not None:
            _require_non_empty(self.related_family_id, "related_family_id")


@dataclass(frozen=True, slots=True)
class OutcomeLeakageFinding:
    """A single hard-exclusion leakage finding."""

    source_id: str
    leakage_type: OutcomeLeakageType
    reason: str
    excerpt: str
    observed_at: datetime
    related_family_id: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "leakage_type": self.leakage_type.value,
            "reason": self.reason,
            "excerpt": self.excerpt,
            "observed_at": _iso_datetime(self.observed_at),
            "related_family_id": self.related_family_id,
        }


@dataclass(frozen=True, slots=True)
class OutcomeLeakageFilterResult:
    """Aggregate leakage decision for one candidate."""

    findings: tuple[OutcomeLeakageFinding, ...]

    @property
    def outcome_leakage_detected(self) -> bool:
        return bool(self.findings)

    @property
    def exclusion_reason(self) -> str | None:
        if not self.findings:
            return None
        return "outcome_leakage"

    def to_manifest_fields(self) -> dict[str, Any]:
        return {
            "outcome_leakage_detected": self.outcome_leakage_detected,
            "outcome_leakage_exclusion_reason": self.exclusion_reason,
            "outcome_leakage_types": [
                finding.leakage_type.value for finding in self.findings
            ],
            "outcome_leakage_source_ids": [
                finding.source_id for finding in self.findings
            ],
            "outcome_leakage_findings": [
                finding.to_record() for finding in self.findings
            ],
        }


@dataclass(frozen=True, slots=True)
class _LeakagePattern:
    leakage_type: OutcomeLeakageType
    pattern: re.Pattern[str]
    reason: str
    allowed_source_kinds: frozenset[LeakageSourceKind] | None = None

    def matches(self, source: LeakageSource) -> re.Match[str] | None:
        if (
            self.allowed_source_kinds is not None
            and source.source_kind not in self.allowed_source_kinds
        ):
            return None
        return self.pattern.search(_normalize_text(source.text))


def detect_outcome_leakage(
    sources: tuple[LeakageSource, ...],
    *,
    evaluation_timestamp: datetime,
) -> OutcomeLeakageFilterResult:
    """Detect target-outcome leakage in sources available before evaluation."""

    _require_aware(evaluation_timestamp, "evaluation_timestamp")
    findings: list[OutcomeLeakageFinding] = []
    for source in sources:
        if source.observed_at > evaluation_timestamp:
            continue
        for leakage_pattern in _LEAKAGE_PATTERNS:
            match = leakage_pattern.matches(source)
            if match is None:
                continue
            findings.append(
                OutcomeLeakageFinding(
                    source_id=source.source_id,
                    leakage_type=leakage_pattern.leakage_type,
                    reason=leakage_pattern.reason,
                    excerpt=_excerpt(_normalize_text(source.text), match),
                    observed_at=source.observed_at,
                    related_family_id=source.related_family_id,
                )
            )
            break
    return OutcomeLeakageFilterResult(findings=tuple(findings))


_RESULT_VERB = (
    r"(grant(?:s|ed|ing)?|den(?:y|ies|ied|ying)|dismiss(?:es|ed|ing)?|"
    r"surviv(?:e|es|ed|ing)|recommend(?:s|ed|ing)?)"
)
_TARGET_MOTION = (
    r"(motion(?:s)? to dismiss|mtd|rule 12|12\(b\)(?:\(6\))?|"
    r"judgment on the pleadings)"
)
_TARGET_MOTION_OR_CONTEXT = rf"(?:{_TARGET_MOTION}|the motion)"
_IDENTICAL_UNIT = (
    r"(identical|same|materially identical|substantially identical|related-case)"
)

_LEAKAGE_PATTERNS = (
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.MINUTE_ORDER,
        pattern=re.compile(
            rf"\bminute (?:order|entry)\b.*(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION})|"
            rf"(?:{_TARGET_MOTION}).*\b(?:{_RESULT_VERB})\b.*"
            rf"\bminute (?:order|entry)\b",
            re.IGNORECASE,
        ),
        reason="minute order already grants or denies the target motion",
    ),
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.ORAL_RULING_TRANSCRIPT,
        pattern=re.compile(
            rf"\b(?:oral ruling|hearing transcript|transcript)\b.*"
            rf"(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION})",
            re.IGNORECASE,
        ),
        reason="oral ruling transcript announces the target disposition",
        allowed_source_kinds=frozenset(
            {
                LeakageSourceKind.ORAL_RULING_TRANSCRIPT,
                LeakageSourceKind.DOCKET_ENTRY,
                LeakageSourceKind.DOCUMENT_TEXT,
            }
        ),
    ),
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.REPORT_AND_RECOMMENDATION,
        pattern=re.compile(
            rf"\b(?:report and recommendation|r&r|findings and recommendation)\b.*"
            rf"(?:(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION})|"
            rf"(?:{_TARGET_MOTION}).*(?:{_RESULT_VERB}))",
            re.IGNORECASE,
        ),
        reason="R&R already resolves the target motion before adoption",
        allowed_source_kinds=frozenset(
            {
                LeakageSourceKind.REPORT_AND_RECOMMENDATION,
                LeakageSourceKind.DOCKET_ENTRY,
                LeakageSourceKind.DOCUMENT_TEXT,
            }
        ),
    ),
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.TENTATIVE_RULING,
        pattern=re.compile(
            rf"\b(?:tentative ruling|tentative decision)\b.*"
            rf"(?:(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION})|"
            rf"(?:{_TARGET_MOTION}).*(?:{_RESULT_VERB}))",
            re.IGNORECASE,
        ),
        reason="tentative ruling reveals the likely target disposition",
    ),
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.WRITTEN_QUESTION,
        pattern=re.compile(
            rf"\b(?:written question|questions? for oral argument)\b.*"
            rf"(?:"
            rf"\b(?:intend(?:s)? to|inclined to)\b.*"
            rf"(?:(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION_OR_CONTEXT})|"
            rf"(?:{_TARGET_MOTION_OR_CONTEXT}).*(?:{_RESULT_VERB}))|"
            rf"\bwhy\b.*(?:{_TARGET_MOTION_OR_CONTEXT}).*"
            rf"\bshould not\b.*(?:{_RESULT_VERB})"
            rf")",
            re.IGNORECASE,
        ),
        reason="written court question reveals the anticipated target disposition",
    ),
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.RELATED_CASE_ORDER,
        pattern=re.compile(
            rf"(?:{_IDENTICAL_UNIT}).*(?:claim|unit|motion).*"
            rf"(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION})|"
            rf"(?:{_RESULT_VERB}).*(?:{_TARGET_MOTION}).*(?:{_IDENTICAL_UNIT})",
            re.IGNORECASE,
        ),
        reason="related-case order resolves materially identical units",
        allowed_source_kinds=frozenset(
            {
                LeakageSourceKind.RELATED_CASE_ORDER,
                LeakageSourceKind.DOCKET_ENTRY,
                LeakageSourceKind.DOCUMENT_TEXT,
            }
        ),
    ),
    _LeakagePattern(
        leakage_type=OutcomeLeakageType.PUBLIC_REPORTING,
        pattern=re.compile(
            rf"\b(?:reported|article|press report|news story)\b.*"
            rf"(?:{_TARGET_MOTION}).*(?:{_RESULT_VERB})|"
            rf"(?:{_TARGET_MOTION}).*(?:{_RESULT_VERB}).*"
            rf"\b(?:reported|article|press report|news story)\b",
            re.IGNORECASE,
        ),
        reason="public reporting reveals the target result before evaluation",
        allowed_source_kinds=frozenset(
            {
                LeakageSourceKind.PUBLIC_REPORTING,
                LeakageSourceKind.DOCUMENT_TEXT,
                LeakageSourceKind.DOCKET_ENTRY,
            }
        ),
    ),
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _excerpt(text: str, match: re.Match[str], *, window: int = 80) -> str:
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return text[start:end].strip()


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _iso_datetime(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
