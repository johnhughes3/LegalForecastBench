"""Public immutable contracts for multi-cohort evaluation studies.

These records describe a reproducible Bench computation.  They contain public
release and run identities, never corpus source bytes or label records.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from legalforecast._canonical import canonical_json
from legalforecast.contracts.schemas import (
    STUDY_REPORT_SCHEMA_VERSION,
    STUDY_SPEC_SCHEMA_VERSION,
    StudySchemaVersion,
)
from legalforecast.evals.model_registry import ModelRegistry
from legalforecast.release import BenchmarkRunManifest, ForecastRelease, LabelsRelease

NonEmptyString = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)
]
Sha256 = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$"),
]
StudyMode = Literal["clean", "exploratory"]
SuitabilityStatus = Literal["suitable_under_policy", "unsuitable", "unknown"]
ClusterUnit = Literal["case", "linked_matter"]
MultiplicityMethod = Literal["bonferroni", "none"]
ComparisonStatus = Literal[
    "complete",
    "exploratory",
    "missing_arm",
    "refused",
    "unsupported_dependence",
]
ArmStatus = Literal["complete", "missing", "invalid"]


class _FrozenModel(BaseModel):
    """Strict immutable public model with no Pydantic copy escape hatch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    def model_copy(
        self, *, update: Mapping[str, object] | None = None, deep: bool = False
    ):  # type: ignore[override]
        if update:
            raise ValueError("study records are immutable")
        return super().model_copy(update=update, deep=deep)


class SuitabilityBinding(_FrozenModel):
    """Exact public identity to which a suitability decision applies."""

    benchmark_family_id: NonEmptyString
    benchmark_version_id: NonEmptyString
    forecast_release_digest: Sha256
    manifest_sha256: Sha256
    model_key: NonEmptyString
    model_registry_sha256: Sha256
    model_registry_entry_sha256: Sha256
    served_model_version: NonEmptyString
    protocol_id: NonEmptyString
    protocol_settings_digest: Sha256
    scoring_policy_id: NonEmptyString


class Suitability(_FrozenModel):
    """Per-arm suitability snapshot imported from the public exposure contract."""

    status: SuitabilityStatus
    policy_id: NonEmptyString
    basis: NonEmptyString
    binding: SuitabilityBinding


class StudyProtocol(_FrozenModel):
    """Public protocol settings compared with the locked run receipt fields."""

    protocol_id: NonEmptyString
    scoring_policy_id: NonEmptyString
    harness: NonEmptyString = "native"
    ablation: NonEmptyString = "none"
    repeat_index: int = Field(default=1, gt=0)

    @field_validator("repeat_index")
    @classmethod
    def _repeat_is_int(cls, value: int) -> int:
        if type(value) is not int:
            raise ValueError("repeat_index must be an integer")
        return value

    @property
    def settings_digest(self) -> str:
        """Return the digest of the protocol settings that are actually frozen."""

        payload = canonical_json(
            {
                "ablation": self.ablation,
                "harness": self.harness,
                "repeat_index": self.repeat_index,
                "scoring_policy_id": self.scoring_policy_id,
            }
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class ClusterAssignment(_FrozenModel):
    """Public case-to-independence-cluster projection for one cohort."""

    case_id: NonEmptyString
    cluster_id: NonEmptyString


class StudyCohort(_FrozenModel):
    """Read-only census and cluster basis for one public benchmark version."""

    cohort_id: NonEmptyString
    benchmark_family_id: NonEmptyString
    benchmark_version_id: NonEmptyString
    forecast_release_id: NonEmptyString
    forecast_release_digest: Sha256
    labels_release_id: NonEmptyString
    labels_release_digest: Sha256
    manifest_sha256: Sha256
    case_ids: tuple[NonEmptyString, ...] = Field(min_length=1)
    expected_unit_count: int | None = Field(default=None, ge=0)
    cluster_unit: ClusterUnit = "case"
    cluster_basis: NonEmptyString
    cluster_assignments: tuple[ClusterAssignment, ...] = ()

    @field_validator("cluster_assignments", mode="before")
    @classmethod
    def _accept_json_array(cls, value: object) -> object:
        """Allow JSON arrays while retaining tuple storage after validation."""

        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _canonical_census(self) -> StudyCohort:
        if self.case_ids != tuple(sorted(set(self.case_ids))):
            raise ValueError("cohort case_ids must be sorted and unique")
        assignment_ids = tuple(item.case_id for item in self.cluster_assignments)
        if self.cluster_unit == "linked_matter":
            if assignment_ids != self.case_ids:
                raise ValueError(
                    "linked_matter cohorts require one cluster assignment per case"
                )
            if len(set(assignment_ids)) != len(assignment_ids):
                raise ValueError("cluster assignments must have unique case IDs")
        elif self.cluster_assignments:
            if assignment_ids != self.case_ids:
                raise ValueError(
                    "case cohorts may omit cluster assignments or provide the "
                    "full census"
                )
        return self

    @property
    def cluster_by_case(self) -> dict[str, str]:
        """Return the validated public cluster projection."""

        if self.cluster_unit == "case":
            return {case_id: case_id for case_id in self.case_ids}
        return {item.case_id: item.cluster_id for item in self.cluster_assignments}


class StudyArm(_FrozenModel):
    """One exact model revision x cohort x protocol run binding."""

    arm_id: NonEmptyString
    cohort_id: NonEmptyString
    model_key: NonEmptyString
    model_registry_sha256: Sha256
    model_registry_entry_sha256: Sha256
    served_model_version: NonEmptyString
    run_id: NonEmptyString
    run_identity_sha256: Sha256
    suitability: Suitability


class PlannedComparison(_FrozenModel):
    """One prespecified A-minus-B contrast across two cohorts."""

    comparison_id: NonEmptyString
    cohort_a_id: NonEmptyString
    cohort_b_id: NonEmptyString
    model_a_key: NonEmptyString
    model_b_key: NonEmptyString
    claim_name: NonEmptyString = "cohort_change"
    orientation: Literal["cohort_b_delta_minus_cohort_a_delta"] = (
        "cohort_b_delta_minus_cohort_a_delta"
    )

    @model_validator(mode="after")
    def _distinct_axes(self) -> PlannedComparison:
        if self.cohort_a_id == self.cohort_b_id:
            raise ValueError("planned comparison requires two distinct cohorts")
        if self.model_a_key == self.model_b_key:
            raise ValueError("planned comparison requires two distinct models")
        return self


class Multiplicity(_FrozenModel):
    """Frozen planned-comparison family correction."""

    method: MultiplicityMethod
    alpha: float = Field(default=0.05, gt=0, lt=1)

    @field_validator("alpha")
    @classmethod
    def _finite_alpha(cls, value: float) -> float:
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("alpha must be finite")
        return value


class StudySpec(_FrozenModel):
    """Complete reproducible specification for a study report."""

    schema_version: Literal[StudySchemaVersion.SPEC_V1] = STUDY_SPEC_SCHEMA_VERSION
    study_id: NonEmptyString
    study_revision: NonEmptyString
    mode: StudyMode
    protocol: StudyProtocol
    cohorts: tuple[StudyCohort, ...] = Field(min_length=2)
    arms: tuple[StudyArm, ...] = Field(min_length=2)
    planned_comparisons: tuple[PlannedComparison, ...] = Field(min_length=1)
    multiplicity: Multiplicity
    replicates: int = Field(default=5000, gt=0)
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    seed: int

    @field_validator("replicates", "seed")
    @classmethod
    def _integer_fields(cls, value: int) -> int:
        if type(value) is not int:
            raise ValueError("replicates and seed must be integers")
        return value

    @field_validator("confidence_level")
    @classmethod
    def _finite_confidence(cls, value: float) -> float:
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("confidence_level must be finite")
        return value

    @model_validator(mode="after")
    def _references_are_unique(self) -> StudySpec:
        cohort_ids = tuple(cohort.cohort_id for cohort in self.cohorts)
        if len(cohort_ids) != len(set(cohort_ids)):
            raise ValueError("cohort IDs must be unique")
        arm_ids = tuple(arm.arm_id for arm in self.arms)
        if len(arm_ids) != len(set(arm_ids)):
            raise ValueError("arm IDs must be unique")
        cohort_model_pairs = tuple((arm.cohort_id, arm.model_key) for arm in self.arms)
        if len(cohort_model_pairs) != len(set(cohort_model_pairs)):
            raise ValueError("each cohort/model pair may have only one study arm")
        comparison_ids = tuple(
            comparison.comparison_id for comparison in self.planned_comparisons
        )
        if len(comparison_ids) != len(set(comparison_ids)):
            raise ValueError("comparison IDs must be unique")
        cohort_set = set(cohort_ids)
        arm_cohorts = {arm.cohort_id for arm in self.arms}
        if not arm_cohorts <= cohort_set:
            raise ValueError("study arm references an unknown cohort")
        for comparison in self.planned_comparisons:
            if (
                not {
                    comparison.cohort_a_id,
                    comparison.cohort_b_id,
                }
                <= cohort_set
            ):
                raise ValueError("planned comparison references an unknown cohort")
            cohort_a = next(
                cohort
                for cohort in self.cohorts
                if cohort.cohort_id == comparison.cohort_a_id
            )
            cohort_b = next(
                cohort
                for cohort in self.cohorts
                if cohort.cohort_id == comparison.cohort_b_id
            )
            if cohort_a.benchmark_family_id != cohort_b.benchmark_family_id:
                raise ValueError(
                    "cohort change comparisons require one benchmark family"
                )
            if cohort_a.benchmark_version_id == cohort_b.benchmark_version_id:
                raise ValueError(
                    "cohort change comparisons require distinct benchmark versions"
                )
        if self.replicates < 2:
            raise ValueError("replicates must be at least two")
        if not math.isclose(
            self.confidence_level,
            1 - self.multiplicity.alpha,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("confidence_level must equal 1 - multiplicity.alpha")
        return self


@dataclass(frozen=True, slots=True)
class StudyArmInput:
    """Caller-captured public artifacts for one study arm.

    A missing run is represented by ``run_records=None``.  The artifacts are
    already parsed from public files; the study service still validates every
    immutable identity before scoring.
    """

    forecast_release: ForecastRelease
    labels_release: LabelsRelease
    manifest: BenchmarkRunManifest
    model_registry: ModelRegistry
    run_records: tuple[Mapping[str, Any], ...] | None
    expected_model_registry_sha256: str | None = None
    base_rate: float | None = None


class ArmObservation(_FrozenModel):
    """Authenticated arm outcome retained even when a comparison is refused."""

    arm_id: NonEmptyString
    cohort_id: NonEmptyString
    model_key: NonEmptyString
    suitability: SuitabilityStatus
    scoring_policy_digest: Sha256 | None = None
    status: ArmStatus
    reason: str | None = None
    expected_case_count: int = Field(ge=0)
    completed_case_count: int = Field(ge=0)
    expected_unit_count: int | None = Field(default=None, ge=0)
    completed_unit_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    observed_micro_brier: float | None = None


class StudyComparison(_FrozenModel):
    """One result or typed refusal for a planned comparison."""

    comparison_id: NonEmptyString
    cohort_a_id: NonEmptyString
    cohort_b_id: NonEmptyString
    model_a_key: NonEmptyString
    model_b_key: NonEmptyString
    claim_mode: StudyMode
    status: ComparisonStatus
    reason: str | None = None
    orientation: Literal["cohort_b_delta_minus_cohort_a_delta"] = (
        "cohort_b_delta_minus_cohort_a_delta"
    )
    planned_comparison_count: int = Field(gt=0)
    alpha: float = Field(gt=0, lt=1)
    adjusted_alpha: float = Field(gt=0, lt=1)
    seed_a: int
    seed_b: int
    replicates: int = Field(gt=0)
    confidence_level: float = Field(gt=0, lt=1)
    cluster_unit: ClusterUnit
    expected_case_count_a: int = Field(ge=0)
    completed_case_count_a: int = Field(ge=0)
    expected_unit_count_a: int | None = Field(default=None, ge=0)
    completed_unit_count_a: int = Field(ge=0)
    expected_case_count_b: int = Field(ge=0)
    completed_case_count_b: int = Field(ge=0)
    expected_unit_count_b: int | None = Field(default=None, ge=0)
    completed_unit_count_b: int = Field(ge=0)
    expected_cluster_count_a: int = Field(ge=0, default=0)
    completed_cluster_count_a: int = Field(ge=0, default=0)
    expected_cluster_count_b: int = Field(ge=0, default=0)
    completed_cluster_count_b: int = Field(ge=0, default=0)
    cluster_basis_a: NonEmptyString | None = None
    cluster_basis_b: NonEmptyString | None = None
    observed_delta_a: float | None = None
    observed_delta_b: float | None = None
    effect: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None

    @model_validator(mode="after")
    def _confidence_matches_alpha(self) -> StudyComparison:
        if not math.isclose(
            self.confidence_level,
            1 - self.alpha,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("confidence_level must equal 1 - alpha")
        return self


class StudyReport(_FrozenModel):
    """Canonical public projection of one reproducible study computation."""

    schema_version: Literal[StudySchemaVersion.REPORT_V1] = STUDY_REPORT_SCHEMA_VERSION
    study_id: NonEmptyString
    study_revision: NonEmptyString
    mode: StudyMode
    protocol_id: NonEmptyString
    protocol_settings_digest: Sha256
    scoring_policy_id: NonEmptyString
    seed: int
    replicates: int = Field(gt=0)
    confidence_level: float = Field(gt=0, lt=1)
    multiplicity_method: MultiplicityMethod
    planned_comparison_count: int = Field(gt=0)
    arm_observations: tuple[ArmObservation, ...]
    comparisons: tuple[StudyComparison, ...]

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-safe public result without evidence bytes."""

        return self.model_dump(mode="json")
