"""Claim policy refuses overclaiming coverage, contamination, and ranking."""

from __future__ import annotations

import pytest
from legalforecast.multiharness.run_progress import (
    CLAIM_FULL,
    CLAIM_SCOPED,
    COVERAGE_SCOPED,
)
from legalforecast.publication.claim_policy import (
    MATCHING_KEY_SYSTEM_BUNDLE,
    PRIMARY_ESTIMAND_OBSERVED_DIFFERENCE,
    ClaimPolicyError,
    ComparisonAnalysisArtifact,
    ExperimentSpec,
    enforce_publication_claims,
)
from legalforecast.reporting.contamination_tiers import (
    PRELIMINARY_CAVEAT,
    ContaminationTier,
)

DIGEST = "sha256:" + "a" * 64
DISCLAIMER = (
    "Compatible composites are grouped by family, scoring mode, and suite "
    "version and are not ranked across incompatible metrics."
)


def _spec(*, coverage_claim: str = CLAIM_SCOPED) -> ExperimentSpec:
    return ExperimentSpec(
        spec_id="fixture-spec",
        primary_estimand=PRIMARY_ESTIMAND_OBSERVED_DIFFERENCE,
        matching_key=MATCHING_KEY_SYSTEM_BUNDLE,
        missingness_rule="visible_under_policy",
        coverage_claim=coverage_claim,
    )


def _analysis(
    spec: ExperimentSpec,
    *,
    claimed_coverage: str = CLAIM_SCOPED,
    claimed_contamination_tier: str = ContaminationTier.RESISTANT.value,
    claims_ranking: bool = False,
    repeat_count: int = 1,
) -> ComparisonAnalysisArtifact:
    return ComparisonAnalysisArtifact(
        experiment_spec_sha256=DIGEST,
        claimed_estimand=PRIMARY_ESTIMAND_OBSERVED_DIFFERENCE,
        claimed_coverage=claimed_coverage,
        claimed_contamination_tier=claimed_contamination_tier,
        claims_ranking=claims_ranking,
        claims_matched_harness=False,
        repeat_count=repeat_count,
        served_model_resolved=False,
    )


def test_full_coverage_claim_from_scoped_run_is_refused() -> None:
    spec = _spec(coverage_claim=CLAIM_FULL)
    analysis = _analysis(spec, claimed_coverage=CLAIM_FULL)
    with pytest.raises(ClaimPolicyError, match="full-suite"):
        enforce_publication_claims(
            spec=spec,
            analysis=analysis,
            selection_label="scoped:fixture-slice",
            coverage_kind=COVERAGE_SCOPED,
            interrupted=False,
            contamination_tier=ContaminationTier.RESISTANT,
            rendered_text=DISCLAIMER,
            model_key="fixture-model",
        )


def test_preliminary_result_without_asterisk_is_refused() -> None:
    spec = _spec()
    analysis = _analysis(
        spec,
        claimed_contamination_tier=ContaminationTier.PRELIMINARY.value,
    )
    with pytest.raises(ClaimPolicyError, match="asterisk"):
        enforce_publication_claims(
            spec=spec,
            analysis=analysis,
            selection_label="scoped:fixture-slice",
            coverage_kind=COVERAGE_SCOPED,
            interrupted=False,
            contamination_tier=ContaminationTier.PRELIMINARY,
            rendered_text="fixture-model scored 0.12. " + DISCLAIMER,
            model_key="fixture-model",
        )


def test_ranking_language_below_repeat_threshold_is_refused() -> None:
    spec = _spec()
    analysis = _analysis(spec, claims_ranking=False)
    with pytest.raises(ClaimPolicyError, match="repeat threshold"):
        enforce_publication_claims(
            spec=spec,
            analysis=analysis,
            selection_label="scoped:fixture-slice",
            coverage_kind=COVERAGE_SCOPED,
            interrupted=False,
            contamination_tier=ContaminationTier.RESISTANT,
            rendered_text="fixture-model outperforms the baseline. " + DISCLAIMER,
            model_key="fixture-model",
        )


def test_incompatible_metric_disclaimer_is_not_ranking_language() -> None:
    spec = _spec()
    analysis = _analysis(spec)
    enforce_publication_claims(
        spec=spec,
        analysis=analysis,
        selection_label="scoped:fixture-slice",
        coverage_kind=COVERAGE_SCOPED,
        interrupted=False,
        contamination_tier=ContaminationTier.RESISTANT,
        rendered_text=DISCLAIMER,
        model_key="fixture-model",
    )


def test_preliminary_result_with_asterisk_and_caveat_is_allowed() -> None:
    spec = _spec()
    analysis = _analysis(
        spec,
        claimed_contamination_tier=ContaminationTier.PRELIMINARY.value,
    )
    enforce_publication_claims(
        spec=spec,
        analysis=analysis,
        selection_label="scoped:fixture-slice",
        coverage_kind=COVERAGE_SCOPED,
        interrupted=False,
        contamination_tier=ContaminationTier.PRELIMINARY,
        rendered_text="fixture-model* " + PRELIMINARY_CAVEAT,
        model_key="fixture-model",
    )
