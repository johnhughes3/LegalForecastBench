"""Repeat, coverage, estimand, and claim policy for community publication.

Bead ``LegalForecastBench-dm0g.4.1.13`` owns this enforcement layer. It consumes
the contamination-tier vocabulary from ``dm0g.7.10`` / PR #715 and the
scoped/partial-run labels from PR #730. An aggregate that would overclaim is
refused at publication time.

Tier-0 may report only the observed task/run difference under a matching key.
Ranking, superiority, or generalized-effect language requires the repeat
threshold. A scoped or interrupted run claims only its slice. A preliminary
contamination tier cannot be published as contamination-resistant and must
carry the asterisk plus standard caveat.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from legalforecast.multiharness.run_progress import (
    CLAIM_FULL,
    CLAIM_PARTIAL,
    CLAIM_SCOPED,
    COVERAGE_SCOPED,
    require_coverage_kind,
    require_honest_coverage_claim,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_schema_version,
    require_str,
    validate_public_record,
    validate_sha256,
)
from legalforecast.reporting.contamination_tiers import (
    PRELIMINARY_CAVEAT,
    PRELIMINARY_MARKER,
    ContaminationTier,
    reported_model_label,
)

EXPERIMENT_SPEC_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative claim-policy sidecar
    "legalforecast.multiharness.experiment_spec.v1"
)
COMPARISON_ANALYSIS_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative claim-policy sidecar
    "legalforecast.multiharness.comparison_analysis.v1"
)

PRIMARY_ESTIMAND_OBSERVED_DIFFERENCE = "observed_task_run_difference"
MATCHING_KEY_MATCHED_HARNESS = "matched_harness_identity"
MATCHING_KEY_SYSTEM_BUNDLE = "system_bundle_label"
RANKING_MIN_REPEATS = 2
_RANKING_CLAIM = re.compile(
    r"\b(?:outperforms|superior(?:ity)?|best[- ]performing|ranked (?:first|above)|"
    r"winner|rank(?:ing)? (?:#|no\.?)\s*1)\b",
    re.IGNORECASE,
)
_RESISTANT_CLAIM = re.compile(
    r"\bcontamination[- ]resistant\b",
    re.IGNORECASE,
)
_FULL_SUITE_CLAIM = re.compile(
    r"\b(?:full[- ]suite|full coverage|complete suite)\b",
    re.IGNORECASE,
)
_MATCHED_HARNESS_CLAIM = re.compile(
    r"\bmatched[- ]harness\b",
    re.IGNORECASE,
)
_EXPERIMENT_REQUIRED = frozenset(
    {
        "schema_version",
        "spec_id",
        "primary_estimand",
        "matching_key",
        "missingness_rule",
        "repeat_threshold_for_ranking",
        "coverage_claim",
    }
)
_ANALYSIS_REQUIRED = frozenset(
    {
        "schema_version",
        "experiment_spec_sha256",
        "claimed_estimand",
        "claimed_coverage",
        "claimed_contamination_tier",
        "claims_ranking",
        "claims_matched_harness",
        "repeat_count",
        "served_model_resolved",
    }
)


class ClaimPolicyError(MultiHarnessValidationError):
    """Publication would overclaim relative to coverage, tier, or repeats."""


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """Prespecified estimand, matching key, and claim bounds."""

    spec_id: str
    primary_estimand: str
    matching_key: str
    missingness_rule: str
    coverage_claim: str
    repeat_threshold_for_ranking: int = RANKING_MIN_REPEATS
    schema_version: str = EXPERIMENT_SPEC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXPERIMENT_SPEC_SCHEMA_VERSION:
            raise ClaimPolicyError("unsupported experiment spec schema_version")
        if not self.spec_id.strip():
            raise ClaimPolicyError("spec_id must be a non-empty string")
        if self.primary_estimand != PRIMARY_ESTIMAND_OBSERVED_DIFFERENCE:
            raise ClaimPolicyError(
                "Tier-0 primary estimand must be the observed task/run difference"
            )
        if self.matching_key not in {
            MATCHING_KEY_MATCHED_HARNESS,
            MATCHING_KEY_SYSTEM_BUNDLE,
        }:
            raise ClaimPolicyError("matching_key is not a supported identity")
        if not self.missingness_rule.strip():
            raise ClaimPolicyError("missingness_rule must be prespecified")
        if self.coverage_claim not in {CLAIM_FULL, CLAIM_SCOPED, CLAIM_PARTIAL}:
            raise ClaimPolicyError("coverage_claim must be full, scoped, or partial")
        if (
            type(self.repeat_threshold_for_ranking) is not int
            or self.repeat_threshold_for_ranking < RANKING_MIN_REPEATS
        ):
            raise ClaimPolicyError(
                "repeat_threshold_for_ranking must be at least the ranking minimum"
            )
        validate_public_record(self.to_record(), "experiment_spec")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "primary_estimand": self.primary_estimand,
            "matching_key": self.matching_key,
            "missingness_rule": self.missingness_rule,
            "repeat_threshold_for_ranking": self.repeat_threshold_for_ranking,
            "coverage_claim": self.coverage_claim,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_EXPERIMENT_REQUIRED,
            field_name="experiment spec",
        )
        require_schema_version(record, EXPERIMENT_SPEC_SCHEMA_VERSION)
        return cls(
            spec_id=require_str(record, "spec_id"),
            primary_estimand=require_str(record, "primary_estimand"),
            matching_key=require_str(record, "matching_key"),
            missingness_rule=require_str(record, "missingness_rule"),
            coverage_claim=require_str(record, "coverage_claim"),
            repeat_threshold_for_ranking=_require_int(
                record,
                "repeat_threshold_for_ranking",
            ),
            schema_version=require_str(record, "schema_version"),
        )


@dataclass(frozen=True, slots=True)
class ComparisonAnalysisArtifact:
    """Claim-bearing analysis that publication policy enforces."""

    experiment_spec_sha256: str
    claimed_estimand: str
    claimed_coverage: str
    claimed_contamination_tier: str
    claims_ranking: bool
    claims_matched_harness: bool
    repeat_count: int
    served_model_resolved: bool
    schema_version: str = COMPARISON_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COMPARISON_ANALYSIS_SCHEMA_VERSION:
            raise ClaimPolicyError("unsupported comparison analysis schema_version")
        validate_sha256(self.experiment_spec_sha256, "experiment_spec_sha256")
        if self.claimed_estimand != PRIMARY_ESTIMAND_OBSERVED_DIFFERENCE:
            raise ClaimPolicyError(
                "analysis estimand must remain the observed task/run difference"
            )
        if self.claimed_coverage not in {CLAIM_FULL, CLAIM_SCOPED, CLAIM_PARTIAL}:
            raise ClaimPolicyError("claimed_coverage must be full, scoped, or partial")
        ContaminationTier(self.claimed_contamination_tier)
        if type(self.repeat_count) is not int or self.repeat_count < 1:
            raise ClaimPolicyError("repeat_count must be a positive integer")
        validate_public_record(self.to_record(), "comparison_analysis")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_spec_sha256": self.experiment_spec_sha256,
            "claimed_estimand": self.claimed_estimand,
            "claimed_coverage": self.claimed_coverage,
            "claimed_contamination_tier": self.claimed_contamination_tier,
            "claims_ranking": self.claims_ranking,
            "claims_matched_harness": self.claims_matched_harness,
            "repeat_count": self.repeat_count,
            "served_model_resolved": self.served_model_resolved,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_ANALYSIS_REQUIRED,
            field_name="comparison analysis",
        )
        require_schema_version(record, COMPARISON_ANALYSIS_SCHEMA_VERSION)
        return cls(
            experiment_spec_sha256=require_str(record, "experiment_spec_sha256"),
            claimed_estimand=require_str(record, "claimed_estimand"),
            claimed_coverage=require_str(record, "claimed_coverage"),
            claimed_contamination_tier=require_str(
                record,
                "claimed_contamination_tier",
            ),
            claims_ranking=_require_bool(record, "claims_ranking"),
            claims_matched_harness=_require_bool(record, "claims_matched_harness"),
            repeat_count=_require_int(record, "repeat_count"),
            served_model_resolved=_require_bool(record, "served_model_resolved"),
            schema_version=require_str(record, "schema_version"),
        )


def enforce_publication_claims(
    *,
    spec: ExperimentSpec,
    analysis: ComparisonAnalysisArtifact,
    selection_label: str,
    coverage_kind: str,
    interrupted: bool,
    contamination_tier: ContaminationTier,
    rendered_text: str,
    model_key: str,
) -> None:
    """Refuse publication that overclaims coverage, contamination, or ranking."""

    require_coverage_kind(coverage_kind)
    try:
        require_honest_coverage_claim(
            selection_label=selection_label,
            coverage_kind=coverage_kind,
            interrupted=interrupted,
        )
    except ValueError as exc:
        raise ClaimPolicyError(str(exc)) from exc
    _enforce_coverage_claim(
        spec=spec,
        analysis=analysis,
        coverage_kind=coverage_kind,
        interrupted=interrupted,
        rendered_text=rendered_text,
    )
    _enforce_contamination_claim(
        analysis=analysis,
        contamination_tier=contamination_tier,
        rendered_text=rendered_text,
        model_key=model_key,
    )
    _enforce_ranking_claim(spec=spec, analysis=analysis, rendered_text=rendered_text)
    _enforce_matching_claim(spec=spec, analysis=analysis, rendered_text=rendered_text)


def _enforce_coverage_claim(
    *,
    spec: ExperimentSpec,
    analysis: ComparisonAnalysisArtifact,
    coverage_kind: str,
    interrupted: bool,
    rendered_text: str,
) -> None:
    if coverage_kind == COVERAGE_SCOPED or interrupted:
        if analysis.claimed_coverage == CLAIM_FULL:
            raise ClaimPolicyError(
                "scoped or interrupted run cannot claim full-suite coverage"
            )
        if spec.coverage_claim == CLAIM_FULL:
            raise ClaimPolicyError(
                "experiment spec cannot prespecify full coverage for a scoped run"
            )
        if _FULL_SUITE_CLAIM.search(rendered_text):
            raise ClaimPolicyError(
                "scoped fixture run cannot be published with full-suite language"
            )
    if coverage_kind == COVERAGE_SCOPED and analysis.claimed_coverage not in {
        CLAIM_SCOPED,
        CLAIM_PARTIAL,
    }:
        raise ClaimPolicyError("scoped run must claim only its slice")
    if interrupted and analysis.claimed_coverage != CLAIM_PARTIAL:
        raise ClaimPolicyError("interrupted run must claim partial coverage")


def _enforce_contamination_claim(
    *,
    analysis: ComparisonAnalysisArtifact,
    contamination_tier: ContaminationTier,
    rendered_text: str,
    model_key: str,
) -> None:
    claimed = ContaminationTier(analysis.claimed_contamination_tier)
    if (
        contamination_tier is ContaminationTier.PRELIMINARY
        and claimed is ContaminationTier.RESISTANT
    ):
        raise ClaimPolicyError(
            "preliminary contamination-tier result cannot be published as "
            "contamination-resistant"
        )
    if contamination_tier is ContaminationTier.PRELIMINARY:
        expected = reported_model_label(
            model_key,
            {model_key: ContaminationTier.PRELIMINARY},
        )
        if expected not in rendered_text or PRELIMINARY_MARKER not in rendered_text:
            raise ClaimPolicyError(
                "preliminary (tier-2) result must be published with its asterisk"
            )
        if PRELIMINARY_CAVEAT not in rendered_text:
            raise ClaimPolicyError(
                "preliminary contamination-tier result must include the standard caveat"
            )
    if (
        contamination_tier is ContaminationTier.PRELIMINARY
        and _RESISTANT_CLAIM.search(rendered_text)
        and "non-contamination-resistant" not in rendered_text
    ):
        raise ClaimPolicyError(
            "preliminary result cannot use unqualified contamination-resistant language"
        )


def _enforce_ranking_claim(
    *,
    spec: ExperimentSpec,
    analysis: ComparisonAnalysisArtifact,
    rendered_text: str,
) -> None:
    ranking_present = analysis.claims_ranking or bool(
        _RANKING_CLAIM.search(rendered_text)
    )
    if ranking_present and analysis.repeat_count < spec.repeat_threshold_for_ranking:
        raise ClaimPolicyError(
            "ranking language is refused below the repeat threshold; n=1 "
            "has observed values only"
        )


def _enforce_matching_claim(
    *,
    spec: ExperimentSpec,
    analysis: ComparisonAnalysisArtifact,
    rendered_text: str,
) -> None:
    matched_language = analysis.claims_matched_harness or bool(
        _MATCHED_HARNESS_CLAIM.search(rendered_text)
    )
    if matched_language and spec.matching_key != MATCHING_KEY_MATCHED_HARNESS:
        raise ClaimPolicyError(
            "matched-harness language requires the matched-harness identity key"
        )
    if matched_language and not analysis.served_model_resolved:
        raise ClaimPolicyError(
            "unresolved served models cannot use matched-harness language"
        )


def _require_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or isinstance(value, bool):
        raise ClaimPolicyError(f"{field_name} must be an integer")
    return value


def _require_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if type(value) is not bool:
        raise ClaimPolicyError(f"{field_name} must be a boolean")
    return value
