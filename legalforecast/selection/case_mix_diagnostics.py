"""Case-mix diagnostics and pre-specified dominance triggers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.selection.eligibility import PressPublicityTag


class DocumentCompleteness(StrEnum):
    COMPLETE = "complete"
    MISSING_REPLY = "missing_reply"
    MISSING_OPPOSITION = "missing_opposition"
    MISSING_MOTION = "missing_motion"
    MISSING_COMPLAINT = "missing_complaint"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


class FallbackSource(StrEnum):
    CASE_DEV_ONLY = "case.dev-only"
    COURTLISTENER = "courtlistener"
    RECAP = "recap"
    COURTLISTENER_RECAP = "courtlistener_recap"
    PACER = "pacer"
    OTHER = "other"


class CandidateSourceClass(StrEnum):
    CASE_DEV_ONLY = "case.dev-only"
    CASE_DEV_PLUS_FALLBACK = "case.dev-plus-fallback"
    EXCLUDED = "excluded"


class DominanceDimension(StrEnum):
    DISTRICT = "district"
    NOS_MACRO_CATEGORY = "nos_macro_category"
    RELATED_CASE_FAMILY = "related_case_family"
    MDL_FAMILY = "mdl_family"


@dataclass(frozen=True, slots=True)
class CaseMixCandidate:
    """Candidate-level fields required for cycle case-mix reporting."""

    candidate_id: str
    case_id: str
    district: str
    circuit: str
    nos_code: str
    nos_macro_category: str
    represented_party_status: str
    government_party_status: str
    mdl_flag: bool
    public_company_flag: bool
    claim_count: int
    defendant_count: int
    defendant_group_count: int
    prediction_unit_count: int
    document_completeness: DocumentCompleteness
    motion_available: bool
    opposition_available: bool
    reply_available: bool
    fallback_used: bool
    fallback_source: FallbackSource = FallbackSource.CASE_DEV_ONLY
    fallback_reason: str | None = None
    press_publicity_tags: tuple[PressPublicityTag, ...] = ()
    included_in_benchmark: bool = True
    related_family_id: str | None = None
    mdl_family_id: str | None = None
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("candidate_id", self.candidate_id),
            ("case_id", self.case_id),
            ("district", self.district),
            ("circuit", self.circuit),
            ("nos_code", self.nos_code),
            ("nos_macro_category", self.nos_macro_category),
            ("represented_party_status", self.represented_party_status),
            ("government_party_status", self.government_party_status),
        ):
            _require_non_empty(value, field_name)

        _require_positive(self.claim_count, "claim_count")
        _require_positive(self.defendant_count, "defendant_count")
        _require_positive(self.defendant_group_count, "defendant_group_count")
        if self.included_in_benchmark:
            _require_positive(self.prediction_unit_count, "prediction_unit_count")
            if self.exclusion_reason is not None:
                raise ValueError(
                    "included benchmark candidates must not have exclusion_reason"
                )
        elif self.prediction_unit_count < 0:
            raise ValueError("prediction_unit_count must be non-negative")
        elif self.exclusion_reason is None:
            raise ValueError("excluded candidates require exclusion_reason")

        if self.related_family_id is not None:
            _require_non_empty(self.related_family_id, "related_family_id")
        if self.mdl_family_id is not None:
            _require_non_empty(self.mdl_family_id, "mdl_family_id")
        if self.exclusion_reason is not None:
            _require_non_empty(self.exclusion_reason, "exclusion_reason")
        if self.fallback_used:
            if self.fallback_source is FallbackSource.CASE_DEV_ONLY:
                raise ValueError(
                    "fallback_source must identify the supplemental source "
                    "when fallback_used is true"
                )
            _require_non_empty(self.fallback_reason or "", "fallback_reason")
        else:
            if self.fallback_source is not FallbackSource.CASE_DEV_ONLY:
                raise ValueError(
                    "case.dev-only candidates must not set a fallback source"
                )
            if self.fallback_reason is not None:
                raise ValueError(
                    "case.dev-only candidates must not set fallback_reason"
                )
        _require_unique_press_publicity_tags(self.press_publicity_tags)

    @property
    def source_class(self) -> CandidateSourceClass:
        if not self.included_in_benchmark:
            return CandidateSourceClass.EXCLUDED
        if self.fallback_used:
            return CandidateSourceClass.CASE_DEV_PLUS_FALLBACK
        return CandidateSourceClass.CASE_DEV_ONLY

    @property
    def press_publicity_sensitivity_flag(self) -> bool:
        return bool(self.press_publicity_tags)

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "source_class": self.source_class.value,
            "district": self.district,
            "circuit": self.circuit,
            "nos_code": self.nos_code,
            "nos_macro_category": self.nos_macro_category,
            "represented_party_status": self.represented_party_status,
            "government_party_status": self.government_party_status,
            "mdl_flag": self.mdl_flag,
            "public_company_flag": self.public_company_flag,
            "claim_count": self.claim_count,
            "defendant_count": self.defendant_count,
            "defendant_group_count": self.defendant_group_count,
            "prediction_unit_count": self.prediction_unit_count,
            "document_completeness": self.document_completeness.value,
            "motion_available": self.motion_available,
            "opposition_available": self.opposition_available,
            "reply_available": self.reply_available,
            "fallback_used": self.fallback_used,
            "fallback_source": self.fallback_source.value,
            "fallback_reason": self.fallback_reason,
            "press_publicity_sensitivity_flag": (self.press_publicity_sensitivity_flag),
            "press_publicity_tags": [tag.value for tag in self.press_publicity_tags],
            "included_in_benchmark": self.included_in_benchmark,
            "related_family_id": self.related_family_id,
            "mdl_family_id": self.mdl_family_id,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True, slots=True)
class DistributionBucket:
    """One bucket in a candidate-count and benchmark-unit distribution table."""

    bucket: str
    candidate_count: int
    candidate_share: float
    unit_count: int
    unit_share: float

    def __post_init__(self) -> None:
        _require_non_empty(self.bucket, "bucket")
        if self.candidate_count < 0:
            raise ValueError("candidate_count must be non-negative")
        if self.unit_count < 0:
            raise ValueError("unit_count must be non-negative")
        _require_share(self.candidate_share, "candidate_share")
        _require_share(self.unit_share, "unit_share")

    def to_record(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "candidate_count": self.candidate_count,
            "candidate_share": self.candidate_share,
            "unit_count": self.unit_count,
            "unit_share": self.unit_share,
        }


@dataclass(frozen=True, slots=True)
class CaseMixTable:
    """Named distribution table for one diagnostic field."""

    name: str
    buckets: tuple[DistributionBucket, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")

    def to_records(self) -> list[dict[str, Any]]:
        return [bucket.to_record() for bucket in self.buckets]


@dataclass(frozen=True, slots=True)
class DominanceFinding:
    """Pre-specified sensitivity trigger for a dominant benchmark bucket."""

    dimension: DominanceDimension
    bucket: str
    unit_count: int
    unit_share: float
    candidate_count: int
    trigger_share: float
    recommended_sensitivity: str = "exclude_or_cap_bucket"

    def __post_init__(self) -> None:
        _require_non_empty(self.bucket, "bucket")
        _require_positive(self.unit_count, "unit_count")
        _require_positive(self.candidate_count, "candidate_count")
        _require_share(self.unit_share, "unit_share")
        _require_share(self.trigger_share, "trigger_share")

    def to_record(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "bucket": self.bucket,
            "unit_count": self.unit_count,
            "unit_share": self.unit_share,
            "candidate_count": self.candidate_count,
            "trigger_share": self.trigger_share,
            "recommended_sensitivity": self.recommended_sensitivity,
        }


@dataclass(frozen=True, slots=True)
class CaseMixDiagnostics:
    """Per-cycle diagnostic tables and dominance findings."""

    cycle_id: str | None
    dominance_threshold: float
    candidates: tuple[CaseMixCandidate, ...]
    tables: tuple[CaseMixTable, ...]
    source_class_distribution: tuple[DistributionBucket, ...]
    exclusion_reason_distribution: tuple[DistributionBucket, ...]
    dominance_findings: tuple[DominanceFinding, ...]

    def __post_init__(self) -> None:
        if self.cycle_id is not None:
            _require_non_empty(self.cycle_id, "cycle_id")
        _require_threshold(self.dominance_threshold)

    @property
    def total_candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def included_candidate_count(self) -> int:
        return sum(
            1 for candidate in self.candidates if candidate.included_in_benchmark
        )

    @property
    def excluded_candidate_count(self) -> int:
        return self.total_candidate_count - self.included_candidate_count

    @property
    def benchmark_unit_count(self) -> int:
        return sum(
            candidate.prediction_unit_count
            for candidate in self.candidates
            if candidate.included_in_benchmark
        )

    @property
    def dominance_triggered(self) -> bool:
        return bool(self.dominance_findings)

    def table_named(self, name: str) -> CaseMixTable:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)

    def to_record(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "scope_note": (
                "case_mix_diagnostics_describe_benchmark_scope_not_population_"
                "representativeness"
            ),
            "dominance_threshold": self.dominance_threshold,
            "candidate_count": self.total_candidate_count,
            "included_candidate_count": self.included_candidate_count,
            "excluded_candidate_count": self.excluded_candidate_count,
            "benchmark_unit_count": self.benchmark_unit_count,
            "dominance_triggered": self.dominance_triggered,
            "tables": {
                table.name: table.to_records()
                for table in sorted(self.tables, key=lambda item: item.name)
            },
            "source_class_distribution": [
                bucket.to_record() for bucket in self.source_class_distribution
            ],
            "exclusion_reason_distribution": [
                bucket.to_record() for bucket in self.exclusion_reason_distribution
            ],
            "dominance_findings": [
                finding.to_record() for finding in self.dominance_findings
            ],
            "candidates": [candidate.to_record() for candidate in self.candidates],
        }


def build_case_mix_diagnostics(
    candidates: Iterable[CaseMixCandidate],
    *,
    cycle_id: str | None = None,
    dominance_threshold: float = 0.40,
) -> CaseMixDiagnostics:
    """Build cycle diagnostics and dominance triggers from candidate records."""

    _require_threshold(dominance_threshold)
    candidate_tuple = tuple(candidates)
    included_candidates = tuple(
        candidate for candidate in candidate_tuple if candidate.included_in_benchmark
    )
    excluded_candidates = tuple(
        candidate
        for candidate in candidate_tuple
        if not candidate.included_in_benchmark
    )

    tables = (
        _table("district", included_candidates, lambda candidate: candidate.district),
        _table("circuit", included_candidates, lambda candidate: candidate.circuit),
        _table("nos_code", included_candidates, lambda candidate: candidate.nos_code),
        _table(
            "nos_macro_category",
            included_candidates,
            lambda candidate: candidate.nos_macro_category,
        ),
        _table(
            "represented_party_status",
            included_candidates,
            lambda candidate: candidate.represented_party_status,
        ),
        _table(
            "government_party_status",
            included_candidates,
            lambda candidate: candidate.government_party_status,
        ),
        _table("mdl_flag", included_candidates, lambda candidate: candidate.mdl_flag),
        _table(
            "public_company_flag",
            included_candidates,
            lambda candidate: candidate.public_company_flag,
        ),
        _table(
            "claim_count",
            included_candidates,
            lambda candidate: candidate.claim_count,
        ),
        _table(
            "defendant_count",
            included_candidates,
            lambda candidate: candidate.defendant_count,
        ),
        _table(
            "defendant_group_count",
            included_candidates,
            lambda candidate: candidate.defendant_group_count,
        ),
        _table(
            "prediction_unit_count",
            included_candidates,
            lambda candidate: candidate.prediction_unit_count,
        ),
        _table(
            "document_completeness",
            included_candidates,
            lambda candidate: candidate.document_completeness.value,
        ),
        _table(
            "motion_available",
            included_candidates,
            lambda candidate: candidate.motion_available,
        ),
        _table(
            "opposition_available",
            included_candidates,
            lambda candidate: candidate.opposition_available,
        ),
        _table(
            "reply_available",
            included_candidates,
            lambda candidate: candidate.reply_available,
        ),
        _table(
            "fallback_used",
            included_candidates,
            lambda candidate: candidate.fallback_used,
        ),
        _table(
            "fallback_source",
            included_candidates,
            lambda candidate: candidate.fallback_source.value,
        ),
        _table(
            "fallback_reason",
            included_candidates,
            lambda candidate: candidate.fallback_reason,
        ),
        _table(
            "press_publicity_sensitivity_flag",
            included_candidates,
            lambda candidate: candidate.press_publicity_sensitivity_flag,
        ),
        _multi_value_table(
            "press_publicity_tags",
            included_candidates,
            lambda candidate: candidate.press_publicity_tags,
        ),
        _table(
            "related_family_id",
            included_candidates,
            lambda candidate: candidate.related_family_id,
        ),
        _table(
            "mdl_family_id",
            included_candidates,
            lambda candidate: candidate.mdl_family_id,
        ),
    )
    exclusion_reason_distribution = _distribution(
        excluded_candidates,
        lambda candidate: candidate.exclusion_reason,
        none_bucket="none",
    )
    source_class_distribution = _distribution(
        candidate_tuple,
        lambda candidate: candidate.source_class.value,
        none_bucket="none",
    )
    dominance_findings = _dominance_findings(
        included_candidates,
        threshold=dominance_threshold,
    )
    return CaseMixDiagnostics(
        cycle_id=cycle_id,
        dominance_threshold=dominance_threshold,
        candidates=candidate_tuple,
        tables=tables,
        source_class_distribution=source_class_distribution,
        exclusion_reason_distribution=exclusion_reason_distribution,
        dominance_findings=dominance_findings,
    )


def _dominance_findings(
    candidates: tuple[CaseMixCandidate, ...],
    *,
    threshold: float,
) -> tuple[DominanceFinding, ...]:
    findings: list[DominanceFinding] = []
    for dimension, key_fn in (
        (DominanceDimension.DISTRICT, _district_key),
        (DominanceDimension.NOS_MACRO_CATEGORY, _nos_macro_category_key),
        (DominanceDimension.RELATED_CASE_FAMILY, _related_family_key),
        (DominanceDimension.MDL_FAMILY, _mdl_family_key),
    ):
        for bucket in _distribution(candidates, key_fn, none_bucket=None):
            if bucket.unit_share > threshold:
                findings.append(
                    DominanceFinding(
                        dimension=dimension,
                        bucket=bucket.bucket,
                        unit_count=bucket.unit_count,
                        unit_share=bucket.unit_share,
                        candidate_count=bucket.candidate_count,
                        trigger_share=threshold,
                    )
                )
    return tuple(findings)


def _table(
    name: str,
    candidates: tuple[CaseMixCandidate, ...],
    key_fn: Callable[[CaseMixCandidate], bool | int | str | None],
) -> CaseMixTable:
    return CaseMixTable(
        name=name,
        buckets=_distribution(candidates, key_fn, none_bucket="none"),
    )


def _multi_value_table(
    name: str,
    candidates: tuple[CaseMixCandidate, ...],
    key_fn: Callable[[CaseMixCandidate], tuple[PressPublicityTag, ...]],
) -> CaseMixTable:
    return CaseMixTable(
        name=name,
        buckets=_multi_value_distribution(candidates, key_fn, none_bucket="none"),
    )


def _distribution(
    candidates: tuple[CaseMixCandidate, ...],
    key_fn: Callable[[CaseMixCandidate], bool | int | str | None],
    *,
    none_bucket: str | None,
) -> tuple[DistributionBucket, ...]:
    candidate_counts: dict[str, int] = {}
    unit_counts: dict[str, int] = {}
    for candidate in candidates:
        raw_bucket = key_fn(candidate)
        if raw_bucket is None:
            if none_bucket is None:
                continue
            bucket = none_bucket
        else:
            bucket = _bucket_value(raw_bucket)
        candidate_counts[bucket] = candidate_counts.get(bucket, 0) + 1
        unit_counts[bucket] = (
            unit_counts.get(bucket, 0) + candidate.prediction_unit_count
        )

    if none_bucket is None:
        total_candidates = len(candidates)
        total_units = sum(candidate.prediction_unit_count for candidate in candidates)
    else:
        total_candidates = sum(candidate_counts.values())
        total_units = sum(unit_counts.values())
    return tuple(
        DistributionBucket(
            bucket=bucket,
            candidate_count=candidate_counts[bucket],
            candidate_share=_share(candidate_counts[bucket], total_candidates),
            unit_count=unit_counts[bucket],
            unit_share=_share(unit_counts[bucket], total_units),
        )
        for bucket in sorted(candidate_counts)
    )


def _multi_value_distribution(
    candidates: tuple[CaseMixCandidate, ...],
    key_fn: Callable[[CaseMixCandidate], tuple[PressPublicityTag, ...]],
    *,
    none_bucket: str,
) -> tuple[DistributionBucket, ...]:
    candidate_counts: dict[str, int] = {}
    unit_counts: dict[str, int] = {}
    for candidate in candidates:
        buckets = tuple(tag.value for tag in key_fn(candidate))
        if not buckets:
            buckets = (none_bucket,)
        for bucket in buckets:
            candidate_counts[bucket] = candidate_counts.get(bucket, 0) + 1
            unit_counts[bucket] = (
                unit_counts.get(bucket, 0) + candidate.prediction_unit_count
            )

    total_candidates = len(candidates)
    total_units = sum(candidate.prediction_unit_count for candidate in candidates)
    return tuple(
        DistributionBucket(
            bucket=bucket,
            candidate_count=candidate_counts[bucket],
            candidate_share=_share(candidate_counts[bucket], total_candidates),
            unit_count=unit_counts[bucket],
            unit_share=_share(unit_counts[bucket], total_units),
        )
        for bucket in sorted(candidate_counts)
    )


def _bucket_value(value: bool | int | str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _district_key(candidate: CaseMixCandidate) -> str:
    return candidate.district


def _nos_macro_category_key(candidate: CaseMixCandidate) -> str:
    return candidate.nos_macro_category


def _related_family_key(candidate: CaseMixCandidate) -> str | None:
    return candidate.related_family_id


def _mdl_family_key(candidate: CaseMixCandidate) -> str | None:
    return candidate.mdl_family_id


def _share(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_share(value: float, field_name: str) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be between 0 and 1")


def _require_threshold(value: float) -> None:
    if value <= 0 or value >= 1:
        raise ValueError("dominance_threshold must be greater than 0 and less than 1")


def _require_unique_press_publicity_tags(
    tags: tuple[PressPublicityTag, ...],
) -> None:
    tag_values = [tag.value for tag in tags]
    if len(set(tag_values)) != len(tag_values):
        raise ValueError("press_publicity_tags must be unique")
