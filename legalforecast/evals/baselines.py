"""Required empirical and run-label baselines for LegalForecast-MTD."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

JUDGE_HISTORY_MIN_DECISIONS = 30


class BaselineId(StrEnum):
    GLOBAL_BASE_RATE = "global_base_rate"
    COURT_NOS_MOTION_BASE_RATE = "court_nos_motion_base_rate"
    METADATA_ONLY = "metadata_only"
    JUDGE_HISTORY = "judge_history"
    NO_BRIEF_LLM = "no_brief_llm"
    FULL_PACKET_LLM = "full_packet_llm"


@dataclass(frozen=True, slots=True)
class BaselineUnitFeatures:
    """Metadata available to statistical baselines for one prediction unit."""

    unit_id: str
    case_id: str
    court: str
    district: str
    circuit: str
    nos_macro_category: str
    motion_type: str
    judge_id: str | None = None
    represented_party_status: str | None = None
    government_party_status: str | None = None
    claim_count: int | None = None
    defendant_count: int | None = None
    motion_length_tokens: int | None = None
    complaint_length_tokens: int | None = None
    case_age_days: int | None = None
    docket_entry_count: int | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("unit_id", self.unit_id),
            ("case_id", self.case_id),
            ("court", self.court),
            ("district", self.district),
            ("circuit", self.circuit),
            ("nos_macro_category", self.nos_macro_category),
            ("motion_type", self.motion_type),
        ):
            _require_non_empty(value, field_name)
        _optional_non_empty(self.judge_id, "judge_id")
        _optional_non_empty(self.represented_party_status, "represented_party_status")
        _optional_non_empty(self.government_party_status, "government_party_status")
        for field_name, value in (
            ("claim_count", self.claim_count),
            ("defendant_count", self.defendant_count),
            ("motion_length_tokens", self.motion_length_tokens),
            ("complaint_length_tokens", self.complaint_length_tokens),
            ("case_age_days", self.case_age_days),
            ("docket_entry_count", self.docket_entry_count),
        ):
            _optional_positive_int(value, field_name)

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "case_id": self.case_id,
            "court": self.court,
            "district": self.district,
            "circuit": self.circuit,
            "nos_macro_category": self.nos_macro_category,
            "motion_type": self.motion_type,
            "judge_id": self.judge_id,
            "represented_party_status": self.represented_party_status,
            "government_party_status": self.government_party_status,
            "claim_count": self.claim_count,
            "defendant_count": self.defendant_count,
            "motion_length_tokens": self.motion_length_tokens,
            "complaint_length_tokens": self.complaint_length_tokens,
            "case_age_days": self.case_age_days,
            "docket_entry_count": self.docket_entry_count,
        }


@dataclass(frozen=True, slots=True)
class BaselineTrainingExample:
    """Historical labeled unit used to fit empirical baselines."""

    features: BaselineUnitFeatures
    fully_dismissed: bool
    decision_date: date

    def to_record(self) -> dict[str, Any]:
        return {
            "features": self.features.to_record(),
            "fully_dismissed": self.fully_dismissed,
            "decision_date": self.decision_date.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BaselineCalibrationArtifact:
    """Training-period provenance for an empirical baseline prediction."""

    baseline_id: BaselineId
    bucket_key: tuple[str, ...]
    training_period_start: date
    training_period_end: date
    training_unit_count: int
    positive_unit_count: int
    empirical_rate: float
    probability_fully_dismissed: float

    def __post_init__(self) -> None:
        if self.training_period_end < self.training_period_start:
            raise ValueError("training_period_end must be on or after start")
        if self.training_unit_count <= 0:
            raise ValueError("training_unit_count must be positive")
        if self.positive_unit_count < 0:
            raise ValueError("positive_unit_count must be non-negative")
        if self.positive_unit_count > self.training_unit_count:
            raise ValueError("positive_unit_count cannot exceed training count")
        _require_probability(self.empirical_rate, "empirical_rate")
        _require_probability(
            self.probability_fully_dismissed,
            "probability_fully_dismissed",
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id.value,
            "bucket_key": list(self.bucket_key),
            "training_period_start": self.training_period_start.isoformat(),
            "training_period_end": self.training_period_end.isoformat(),
            "training_unit_count": self.training_unit_count,
            "positive_unit_count": self.positive_unit_count,
            "empirical_rate": self.empirical_rate,
            "probability_fully_dismissed": self.probability_fully_dismissed,
        }


@dataclass(frozen=True, slots=True)
class BaselinePrediction:
    """One baseline probability for a benchmark unit."""

    unit_id: str
    baseline_id: BaselineId
    probability_fully_dismissed: float
    fallback_level: str
    calibration: BaselineCalibrationArtifact
    feature_keys: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.unit_id, "unit_id")
        _require_probability(
            self.probability_fully_dismissed,
            "probability_fully_dismissed",
        )
        _require_non_empty(self.fallback_level, "fallback_level")

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "baseline_id": self.baseline_id.value,
            "probability_fully_dismissed": self.probability_fully_dismissed,
            "fallback_level": self.fallback_level,
            "feature_keys": [
                {"feature": feature, "bucket": bucket}
                for feature, bucket in self.feature_keys
            ],
            "calibration": self.calibration.to_record(),
        }


@dataclass(frozen=True, slots=True)
class BaselinePredictionSet:
    """All required statistical baseline predictions for one unit."""

    unit_id: str
    predictions: tuple[BaselinePrediction, ...]

    def prediction_for(self, baseline_id: BaselineId) -> BaselinePrediction:
        for prediction in self.predictions:
            if prediction.baseline_id is baseline_id:
                return prediction
        raise KeyError(baseline_id.value)

    def to_records(self) -> list[dict[str, Any]]:
        return [prediction.to_record() for prediction in self.predictions]


@dataclass(frozen=True, slots=True)
class JudgeHistoryUsageSummary:
    """Share of benchmark units using judge prior vs fallback priors."""

    unit_count: int
    judge_prior_units: int
    court_or_district_fallback_units: int
    global_fallback_units: int

    def __post_init__(self) -> None:
        if self.unit_count < 0:
            raise ValueError("unit_count must be non-negative")
        total = (
            self.judge_prior_units
            + self.court_or_district_fallback_units
            + self.global_fallback_units
        )
        if total != self.unit_count:
            raise ValueError("judge-history usage counts must sum to unit_count")

    @property
    def judge_prior_share(self) -> float:
        return _share(self.judge_prior_units, self.unit_count)

    @property
    def court_or_district_fallback_share(self) -> float:
        return _share(self.court_or_district_fallback_units, self.unit_count)

    @property
    def global_fallback_share(self) -> float:
        return _share(self.global_fallback_units, self.unit_count)

    def to_record(self) -> dict[str, Any]:
        return {
            "unit_count": self.unit_count,
            "judge_prior_units": self.judge_prior_units,
            "court_or_district_fallback_units": (self.court_or_district_fallback_units),
            "global_fallback_units": self.global_fallback_units,
            "judge_prior_share": self.judge_prior_share,
            "court_or_district_fallback_share": (self.court_or_district_fallback_share),
            "global_fallback_share": self.global_fallback_share,
        }


@dataclass(frozen=True, slots=True)
class BaselineSuite:
    """Fitted empirical baseline suite with deterministic predictions."""

    training_period_start: date
    training_period_end: date
    examples: tuple[BaselineTrainingExample, ...]
    judge_min_decisions: int = JUDGE_HISTORY_MIN_DECISIONS

    def __post_init__(self) -> None:
        if self.training_period_end < self.training_period_start:
            raise ValueError("training_period_end must be on or after start")
        if not self.examples:
            raise ValueError("baseline training examples must not be empty")
        if self.judge_min_decisions <= 0:
            raise ValueError("judge_min_decisions must be positive")
        for example in self.examples:
            if (
                not self.training_period_start
                <= example.decision_date
                <= (self.training_period_end)
            ):
                raise ValueError("training example outside declared training period")

    def predict(self, features: BaselineUnitFeatures) -> BaselinePredictionSet:
        return BaselinePredictionSet(
            unit_id=features.unit_id,
            predictions=(
                self.global_base_rate_prediction(features),
                self.court_nos_motion_prediction(features),
                self.metadata_only_prediction(features),
                self.judge_history_prediction(features),
            ),
        )

    def global_base_rate_prediction(
        self,
        features: BaselineUnitFeatures,
    ) -> BaselinePrediction:
        counts = self._global_counts()
        probability = counts.rate
        return BaselinePrediction(
            unit_id=features.unit_id,
            baseline_id=BaselineId.GLOBAL_BASE_RATE,
            probability_fully_dismissed=probability,
            fallback_level="global",
            calibration=self._calibration(
                BaselineId.GLOBAL_BASE_RATE,
                ("global",),
                counts,
                probability,
            ),
        )

    def court_nos_motion_prediction(
        self,
        features: BaselineUnitFeatures,
    ) -> BaselinePrediction:
        lookup = self._court_nos_motion_lookup(features)
        return BaselinePrediction(
            unit_id=features.unit_id,
            baseline_id=BaselineId.COURT_NOS_MOTION_BASE_RATE,
            probability_fully_dismissed=lookup.probability,
            fallback_level=lookup.fallback_level,
            calibration=self._calibration(
                BaselineId.COURT_NOS_MOTION_BASE_RATE,
                lookup.bucket_key,
                lookup.counts,
                lookup.probability,
            ),
        )

    def metadata_only_prediction(
        self,
        features: BaselineUnitFeatures,
    ) -> BaselinePrediction:
        components = self._metadata_components(features)
        total_weight = sum(component.weight for component in components)
        probability = (
            sum(component.counts.rate * component.weight for component in components)
            / total_weight
        )
        global_counts = self._global_counts()
        return BaselinePrediction(
            unit_id=features.unit_id,
            baseline_id=BaselineId.METADATA_ONLY,
            probability_fully_dismissed=probability,
            fallback_level="metadata_weighted",
            calibration=self._calibration(
                BaselineId.METADATA_ONLY,
                ("metadata_only",),
                global_counts,
                probability,
            ),
            feature_keys=tuple(component.feature_key for component in components),
        )

    def judge_history_prediction(
        self,
        features: BaselineUnitFeatures,
    ) -> BaselinePrediction:
        judge_counts = self._judge_counts()
        if features.judge_id is not None and features.judge_id in judge_counts:
            counts = judge_counts[features.judge_id]
            if counts.unit_count >= self.judge_min_decisions:
                probability = counts.rate
                return BaselinePrediction(
                    unit_id=features.unit_id,
                    baseline_id=BaselineId.JUDGE_HISTORY,
                    probability_fully_dismissed=probability,
                    fallback_level="judge_history",
                    calibration=self._calibration(
                        BaselineId.JUDGE_HISTORY,
                        ("judge_id", features.judge_id),
                        counts,
                        probability,
                    ),
                )

        lookup = self._court_nos_motion_lookup(features)
        return BaselinePrediction(
            unit_id=features.unit_id,
            baseline_id=BaselineId.JUDGE_HISTORY,
            probability_fully_dismissed=lookup.probability,
            fallback_level=lookup.fallback_level,
            calibration=self._calibration(
                BaselineId.JUDGE_HISTORY,
                lookup.bucket_key,
                lookup.counts,
                lookup.probability,
            ),
        )

    def judge_history_usage_summary(
        self,
        features: tuple[BaselineUnitFeatures, ...],
    ) -> JudgeHistoryUsageSummary:
        judge_prior_units = 0
        court_or_district_fallback_units = 0
        global_fallback_units = 0
        for feature_record in features:
            prediction = self.judge_history_prediction(feature_record)
            if prediction.fallback_level == "judge_history":
                judge_prior_units += 1
            elif prediction.fallback_level == "global":
                global_fallback_units += 1
            else:
                court_or_district_fallback_units += 1
        return JudgeHistoryUsageSummary(
            unit_count=len(features),
            judge_prior_units=judge_prior_units,
            court_or_district_fallback_units=court_or_district_fallback_units,
            global_fallback_units=global_fallback_units,
        )

    def training_period_record(self) -> dict[str, str]:
        return {
            "training_period_start": self.training_period_start.isoformat(),
            "training_period_end": self.training_period_end.isoformat(),
        }

    def _calibration(
        self,
        baseline_id: BaselineId,
        bucket_key: tuple[str, ...],
        counts: _BucketCounts,
        probability: float,
    ) -> BaselineCalibrationArtifact:
        return BaselineCalibrationArtifact(
            baseline_id=baseline_id,
            bucket_key=bucket_key,
            training_period_start=self.training_period_start,
            training_period_end=self.training_period_end,
            training_unit_count=counts.unit_count,
            positive_unit_count=counts.positive_count,
            empirical_rate=counts.rate,
            probability_fully_dismissed=probability,
        )

    def _court_nos_motion_lookup(
        self,
        features: BaselineUnitFeatures,
    ) -> _RateLookup:
        exact_key = (
            features.court,
            features.nos_macro_category,
            features.motion_type,
        )
        exact_counts = self._court_nos_motion_counts().get(exact_key)
        if exact_counts is not None:
            return _RateLookup(
                probability=exact_counts.rate,
                fallback_level="court_nos_motion",
                bucket_key=("court_nos_motion", *exact_key),
                counts=exact_counts,
            )

        district_key = (
            features.district,
            features.nos_macro_category,
            features.motion_type,
        )
        district_counts = self._district_nos_motion_counts().get(district_key)
        if district_counts is not None:
            return _RateLookup(
                probability=district_counts.rate,
                fallback_level="district_nos_motion",
                bucket_key=("district_nos_motion", *district_key),
                counts=district_counts,
            )

        nos_motion_key = (features.nos_macro_category, features.motion_type)
        nos_motion_counts = self._nos_motion_counts().get(nos_motion_key)
        if nos_motion_counts is not None:
            return _RateLookup(
                probability=nos_motion_counts.rate,
                fallback_level="nos_motion",
                bucket_key=("nos_motion", *nos_motion_key),
                counts=nos_motion_counts,
            )

        global_counts = self._global_counts()
        return _RateLookup(
            probability=global_counts.rate,
            fallback_level="global",
            bucket_key=("global",),
            counts=global_counts,
        )

    def _metadata_components(
        self,
        features: BaselineUnitFeatures,
    ) -> tuple[_MetadataComponent, ...]:
        components = [
            _MetadataComponent(
                feature_key=("global", "global"),
                counts=self._global_counts(),
                weight=1.0,
            )
        ]
        feature_counts = self._metadata_feature_counts()
        for feature_key in _metadata_feature_keys(features):
            counts = feature_counts.get(feature_key)
            if counts is None:
                continue
            if feature_key[0] == "judge_id" and counts.unit_count < (
                self.judge_min_decisions
            ):
                continue
            components.append(
                _MetadataComponent(
                    feature_key=feature_key,
                    counts=counts,
                    weight=min(counts.unit_count / self.judge_min_decisions, 1.0),
                )
            )
        return tuple(components)

    def _global_counts(self) -> _BucketCounts:
        counts = _BucketCounts()
        for example in self.examples:
            counts.add(example.fully_dismissed)
        return counts

    def _court_nos_motion_counts(self) -> dict[tuple[str, ...], _BucketCounts]:
        return self._counts_by(
            lambda example: (
                example.features.court,
                example.features.nos_macro_category,
                example.features.motion_type,
            )
        )

    def _district_nos_motion_counts(self) -> dict[tuple[str, ...], _BucketCounts]:
        return self._counts_by(
            lambda example: (
                example.features.district,
                example.features.nos_macro_category,
                example.features.motion_type,
            )
        )

    def _nos_motion_counts(self) -> dict[tuple[str, ...], _BucketCounts]:
        return self._counts_by(
            lambda example: (
                example.features.nos_macro_category,
                example.features.motion_type,
            )
        )

    def _judge_counts(self) -> dict[str, _BucketCounts]:
        counts: dict[str, _BucketCounts] = {}
        for example in self.examples:
            judge_id = example.features.judge_id
            if judge_id is None:
                continue
            bucket = counts.setdefault(judge_id, _BucketCounts())
            bucket.add(example.fully_dismissed)
        return counts

    def _metadata_feature_counts(self) -> dict[tuple[str, str], _BucketCounts]:
        counts: dict[tuple[str, str], _BucketCounts] = {}
        for example in self.examples:
            for feature_key in _metadata_feature_keys(example.features):
                bucket = counts.setdefault(feature_key, _BucketCounts())
                bucket.add(example.fully_dismissed)
        return counts

    def _counts_by(
        self,
        key_fn: _ExampleKeyFn,
    ) -> dict[tuple[str, ...], _BucketCounts]:
        counts: dict[tuple[str, ...], _BucketCounts] = {}
        for example in self.examples:
            bucket = counts.setdefault(key_fn(example), _BucketCounts())
            bucket.add(example.fully_dismissed)
        return counts


def fit_baseline_suite(
    examples: tuple[BaselineTrainingExample, ...],
    *,
    training_period_start: date,
    training_period_end: date,
    judge_min_decisions: int = JUDGE_HISTORY_MIN_DECISIONS,
) -> BaselineSuite:
    return BaselineSuite(
        training_period_start=training_period_start,
        training_period_end=training_period_end,
        examples=examples,
        judge_min_decisions=judge_min_decisions,
    )


def required_llm_run_labels() -> tuple[BaselineId, BaselineId]:
    return (BaselineId.NO_BRIEF_LLM, BaselineId.FULL_PACKET_LLM)


@dataclass(slots=True)
class _BucketCounts:
    unit_count: int = 0
    positive_count: int = 0

    def add(self, fully_dismissed: bool) -> None:
        self.unit_count += 1
        if fully_dismissed:
            self.positive_count += 1

    @property
    def rate(self) -> float:
        if self.unit_count == 0:
            raise ValueError("cannot compute rate for empty bucket")
        return self.positive_count / self.unit_count


@dataclass(frozen=True, slots=True)
class _RateLookup:
    probability: float
    fallback_level: str
    bucket_key: tuple[str, ...]
    counts: _BucketCounts


@dataclass(frozen=True, slots=True)
class _MetadataComponent:
    feature_key: tuple[str, str]
    counts: _BucketCounts
    weight: float


type _ExampleKeyFn = Callable[[BaselineTrainingExample], tuple[str, ...]]


def _metadata_feature_keys(
    features: BaselineUnitFeatures,
) -> tuple[tuple[str, str], ...]:
    keys: list[tuple[str, str]] = [
        ("court", features.court),
        ("district", features.district),
        ("circuit", features.circuit),
        ("nos_macro_category", features.nos_macro_category),
        ("motion_type", features.motion_type),
    ]
    if features.judge_id is not None:
        keys.append(("judge_id", features.judge_id))
    if features.represented_party_status is not None:
        keys.append(("represented_party_status", features.represented_party_status))
    if features.government_party_status is not None:
        keys.append(("government_party_status", features.government_party_status))
    if features.claim_count is not None:
        keys.append(("claim_count_bin", _small_medium_large(features.claim_count)))
    if features.defendant_count is not None:
        keys.append(
            ("defendant_count_bin", _small_medium_large(features.defendant_count))
        )
    if features.motion_length_tokens is not None:
        keys.append(
            ("motion_length_bin", _length_bucket(features.motion_length_tokens))
        )
    if features.complaint_length_tokens is not None:
        keys.append(
            (
                "complaint_length_bin",
                _length_bucket(features.complaint_length_tokens),
            )
        )
    if features.case_age_days is not None:
        keys.append(("case_age_bin", _age_bucket(features.case_age_days)))
    if features.docket_entry_count is not None:
        keys.append(("docket_length_bin", _docket_bucket(features.docket_entry_count)))
    return tuple(keys)


def _small_medium_large(value: int) -> str:
    if value <= 2:
        return "1_2"
    if value <= 5:
        return "3_5"
    return "6_plus"


def _length_bucket(value: int) -> str:
    if value <= 5_000:
        return "short"
    if value <= 20_000:
        return "medium"
    return "long"


def _age_bucket(value: int) -> str:
    if value <= 180:
        return "0_180"
    if value <= 730:
        return "181_730"
    return "731_plus"


def _docket_bucket(value: int) -> str:
    if value <= 25:
        return "0_25"
    if value <= 100:
        return "26_100"
    return "101_plus"


def _share(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _optional_non_empty(value: str | None, field_name: str) -> None:
    if value is not None:
        _require_non_empty(value, field_name)


def _optional_positive_int(value: int | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_probability(value: float, field_name: str) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be between 0 and 1")
