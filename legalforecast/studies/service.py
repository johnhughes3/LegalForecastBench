"""Compute prespecified cross-cohort studies from public locked run records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from legalforecast.evals.bootstrap import (
    BootstrapConfig,
    ModelScoreInput,
    paired_clustered_bootstrap,
    quantile,
)
from legalforecast.evals.model_registry import (
    model_registry_entry_sha256,
)
from legalforecast.evals.run_record_scoring import (
    IncompleteLockedRun,
    score_run_records_against_labels_release,
)
from legalforecast.evals.scorers import ScoreSummary, UnitScore
from legalforecast.release import (
    ForecastRelease,
    LabelsRelease,
    serialize_run_manifest,
    validate_manifest_against_forecast,
)

from .models import (
    ArmObservation,
    StudyArm,
    StudyArmInput,
    StudyCohort,
    StudyComparison,
    StudyMode,
    StudyReport,
    StudySpec,
)


class StudyEvaluationError(ValueError):
    """Raised when the study specification itself is not evaluable."""


def evaluate_study(
    spec: StudySpec,
    *,
    arm_inputs: Mapping[str, StudyArmInput],
) -> StudyReport:
    """Evaluate a frozen study specification over caller-captured public inputs.

    The function uses the strict locked scorer for every available arm.  A
    missing, incomplete, or identity-inconsistent arm becomes an explicit arm
    observation and cannot be converted into a zero score or a complete-case
    contrast.  Inputs contain only public releases, manifests, registries, and
    persisted receipt records; no provider or Corpus API is reachable here.
    The specification is an ordinary computation input that may be assembled
    post hoc; it is not a preregistration record or an execution prerequisite.
    """

    cohorts = {cohort.cohort_id: cohort for cohort in spec.cohorts}
    arms = {arm.arm_id: arm for arm in spec.arms}
    _validate_arm_layout(spec, cohorts, arms)

    observations: dict[str, ArmObservation] = {}
    summaries: dict[str, ScoreSummary] = {}
    for arm in spec.arms:
        cohort = cohorts[arm.cohort_id]
        captured = arm_inputs.get(arm.arm_id)
        observation, summary = _score_arm(
            spec,
            arm=arm,
            cohort=cohort,
            captured=captured,
        )
        observations[arm.arm_id] = observation
        if summary is not None:
            summaries[arm.arm_id] = summary

    comparisons = tuple(
        _evaluate_comparison(
            spec,
            comparison=comparison,
            cohorts=cohorts,
            arms=arms,
            observations=observations,
            summaries=summaries,
        )
        for comparison in spec.planned_comparisons
    )
    return StudyReport(
        study_id=spec.study_id,
        study_revision=spec.study_revision,
        mode=spec.mode,
        protocol_id=spec.protocol.protocol_id,
        protocol_settings_digest=spec.protocol.settings_digest,
        scoring_policy_id=spec.protocol.scoring_policy_id,
        seed=spec.seed,
        replicates=spec.replicates,
        confidence_level=spec.confidence_level,
        multiplicity_method=spec.multiplicity.method,
        planned_comparison_count=len(spec.planned_comparisons),
        arm_observations=tuple(observations[arm.arm_id] for arm in spec.arms),
        comparisons=comparisons,
    )


def _validate_arm_layout(
    spec: StudySpec,
    cohorts: Mapping[str, StudyCohort],
    arms: Mapping[str, StudyArm],
) -> None:
    for cohort in spec.cohorts:
        if not cohort.case_ids:
            raise StudyEvaluationError(f"cohort {cohort.cohort_id} has no case census")
    for comparison in spec.planned_comparisons:
        candidates_a = [
            arm
            for arm in arms.values()
            if arm.cohort_id == comparison.cohort_a_id
            and arm.model_key == comparison.model_a_key
        ]
        candidates_b = [
            arm
            for arm in arms.values()
            if arm.cohort_id == comparison.cohort_b_id
            and arm.model_key == comparison.model_b_key
        ]
        if len(candidates_a) > 1 or len(candidates_b) > 1:
            raise StudyEvaluationError(
                f"comparison {comparison.comparison_id} has duplicate model/cohort arms"
            )
        if (
            comparison.cohort_a_id not in cohorts
            or comparison.cohort_b_id not in cohorts
        ):
            raise StudyEvaluationError(
                f"comparison {comparison.comparison_id} references an unknown cohort"
            )


def _score_arm(
    spec: StudySpec,
    *,
    arm: StudyArm,
    cohort: StudyCohort,
    captured: StudyArmInput | None,
) -> tuple[ArmObservation, ScoreSummary | None]:
    expected_units = cohort.expected_unit_count
    expected_cases = len(cohort.case_ids)
    try:
        _validate_suitability_binding(spec, arm=arm, cohort=cohort)
    except ValueError as exc:
        return (
            ArmObservation(
                arm_id=arm.arm_id,
                cohort_id=arm.cohort_id,
                model_key=arm.model_key,
                suitability=arm.suitability.status,
                status="invalid",
                reason=str(exc),
                expected_case_count=expected_cases,
                completed_case_count=0,
                expected_unit_count=expected_units,
                completed_unit_count=0,
                cluster_count=len(set(cohort.cluster_by_case.values())),
            ),
            None,
        )
    if captured is None:
        return (
            ArmObservation(
                arm_id=arm.arm_id,
                cohort_id=arm.cohort_id,
                model_key=arm.model_key,
                suitability=arm.suitability.status,
                status="missing",
                reason="run records are missing",
                expected_case_count=expected_cases,
                completed_case_count=0,
                expected_unit_count=expected_units,
                completed_unit_count=0,
                cluster_count=len(set(cohort.cluster_by_case.values())),
            ),
            None,
        )
    if captured.run_records is None:
        return (
            ArmObservation(
                arm_id=arm.arm_id,
                cohort_id=arm.cohort_id,
                model_key=arm.model_key,
                suitability=arm.suitability.status,
                status="missing",
                reason="run records are missing",
                expected_case_count=expected_cases,
                completed_case_count=0,
                expected_unit_count=expected_units,
                completed_unit_count=0,
                cluster_count=len(set(cohort.cluster_by_case.values())),
            ),
            None,
        )

    try:
        _validate_captured_identity(spec, arm=arm, cohort=cohort, captured=captured)
        # The release and manifest census are authenticated by the preceding
        # identity checks.  Only now may this arm contribute a derived unit
        # denominator to its report.
        expected_units = _expected_scored_units(captured.forecast_release)
        scored = score_run_records_against_labels_release(
            captured.run_records,
            captured.labels_release,
            base_rate=captured.base_rate,
            forecast_release=captured.forecast_release,
            manifest=captured.manifest,
            expected_run_identity_sha256=arm.run_identity_sha256,
            model_registry=captured.model_registry,
            expected_model_registry_sha256=arm.model_registry_sha256,
            expected_repeat_index=spec.protocol.repeat_index,
        )
        summary = _single_model_summary(scored, arm.model_key)
        unit_scores = _apply_cluster_projection(
            summary.unit_scores,
            cohort=cohort,
        )
        summary = replace(summary, unit_scores=unit_scores)
    except IncompleteLockedRun as exc:
        expected_scoreable_ids = {
            unit.unit_id
            for unit in captured.forecast_release.prediction_units
            if unit.should_score
        }
        completed_scoreable_ids = (
            exc.completed_unit_ids_by_model.get(arm.model_key, frozenset())
            & expected_scoreable_ids
        )
        units_by_id = {
            unit.unit_id: unit for unit in captured.forecast_release.prediction_units
        }
        completed_case_ids = {
            units_by_id[unit_id].case_id for unit_id in completed_scoreable_ids
        }
        return (
            ArmObservation(
                arm_id=arm.arm_id,
                cohort_id=arm.cohort_id,
                model_key=arm.model_key,
                suitability=arm.suitability.status,
                status="missing",
                reason=(
                    f"{exc}: completed {len(completed_case_ids)}/{expected_cases} "
                    f"cases and {len(completed_scoreable_ids)}/{expected_units} "
                    "scoreable units"
                ),
                expected_case_count=expected_cases,
                completed_case_count=len(completed_case_ids),
                expected_unit_count=expected_units,
                completed_unit_count=len(completed_scoreable_ids),
                cluster_count=len(
                    {cohort.cluster_by_case[case_id] for case_id in completed_case_ids}
                ),
            ),
            None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return (
            ArmObservation(
                arm_id=arm.arm_id,
                cohort_id=arm.cohort_id,
                model_key=arm.model_key,
                suitability=arm.suitability.status,
                status="invalid",
                reason=str(exc),
                expected_case_count=expected_cases,
                completed_case_count=0,
                expected_unit_count=expected_units,
                completed_unit_count=0,
                cluster_count=len(set(cohort.cluster_by_case.values())),
            ),
            None,
        )

    expected_case_ids = {
        unit.case_id
        for unit in captured.forecast_release.prediction_units
        if unit.should_score
    }
    completed_case_ids = {unit.case_id for unit in unit_scores}
    if completed_case_ids != expected_case_ids:
        reason = (
            "strict score did not cover the complete scoreable case census: "
            f"missing={sorted(expected_case_ids - completed_case_ids)}, "
            f"extra={sorted(completed_case_ids - expected_case_ids)}"
        )
        return (
            ArmObservation(
                arm_id=arm.arm_id,
                cohort_id=arm.cohort_id,
                model_key=arm.model_key,
                suitability=arm.suitability.status,
                status="invalid",
                reason=reason,
                expected_case_count=expected_cases,
                completed_case_count=len(completed_case_ids),
                expected_unit_count=expected_units,
                completed_unit_count=len(unit_scores),
                cluster_count=len(
                    {_cluster_id_for_unit(unit, cohort=cohort) for unit in unit_scores}
                ),
            ),
            None,
        )

    return (
        ArmObservation(
            arm_id=arm.arm_id,
            cohort_id=arm.cohort_id,
            model_key=arm.model_key,
            suitability=arm.suitability.status,
            status="complete",
            expected_case_count=expected_cases,
            completed_case_count=len(completed_case_ids),
            expected_unit_count=expected_units,
            completed_unit_count=len(unit_scores),
            cluster_count=len(
                {_cluster_id_for_unit(unit, cohort=cohort) for unit in unit_scores}
            ),
            scoring_policy_digest=_scoring_policy_digest(captured.labels_release),
            observed_micro_brier=summary.micro_brier,
        ),
        summary,
    )


def _validate_suitability_binding(
    spec: StudySpec,
    *,
    arm: StudyArm,
    cohort: StudyCohort,
) -> None:
    """Reject a suitability snapshot copied from another public arm."""

    binding = arm.suitability.binding
    expected = (
        cohort.benchmark_family_id,
        cohort.benchmark_version_id,
        cohort.forecast_release_digest,
        cohort.manifest_sha256,
        arm.model_key,
        arm.model_registry_sha256,
        arm.model_registry_entry_sha256,
        arm.served_model_version,
        spec.protocol.protocol_id,
        spec.protocol.settings_digest,
        spec.protocol.scoring_policy_id,
    )
    actual = (
        binding.benchmark_family_id,
        binding.benchmark_version_id,
        binding.forecast_release_digest,
        binding.manifest_sha256,
        binding.model_key,
        binding.model_registry_sha256,
        binding.model_registry_entry_sha256,
        binding.served_model_version,
        binding.protocol_id,
        binding.protocol_settings_digest,
        binding.scoring_policy_id,
    )
    if actual != expected:
        raise ValueError("suitability binding does not match the study arm")


def _validate_captured_identity(
    spec: StudySpec,
    *,
    arm: StudyArm,
    cohort: StudyCohort,
    captured: StudyArmInput,
) -> None:
    forecast = captured.forecast_release
    labels = captured.labels_release
    manifest = captured.manifest
    registry = captured.model_registry
    if forecast.release_id != cohort.forecast_release_id:
        raise ValueError("forecast release ID does not match cohort")
    if forecast.release_digest != cohort.forecast_release_digest:
        raise ValueError("forecast release digest does not match cohort")
    if labels.release_id != cohort.labels_release_id:
        raise ValueError("labels release ID does not match cohort")
    if labels.release_digest != cohort.labels_release_digest:
        raise ValueError("labels release digest does not match cohort")
    if (
        hashlib.sha256(serialize_run_manifest(manifest)).hexdigest()
        != cohort.manifest_sha256
    ):
        raise ValueError("run manifest digest does not match cohort")
    if str(manifest.run_id) != arm.run_id:
        raise ValueError("run manifest ID does not match study arm")
    if forecast.run_manifest_binding is None:
        raise ValueError("forecast release lacks a locked manifest binding")
    validate_manifest_against_forecast(manifest, forecast)
    if forecast.run_manifest_binding.manifest_sha256 != cohort.manifest_sha256:
        raise ValueError("forecast release manifest binding differs from cohort")
    if labels.forecast_release_digest != forecast.release_digest:
        raise ValueError("labels release is bound to a different forecast release")
    if tuple(sorted(case.case_id for case in forecast.cases)) != cohort.case_ids:
        raise ValueError("forecast release case census differs from study cohort")
    if registry.source_sha256 != arm.model_registry_sha256:
        raise ValueError("model registry digest does not match study arm")
    if captured.expected_model_registry_sha256 not in {
        None,
        arm.model_registry_sha256,
    }:
        raise ValueError("captured model registry digest differs from study arm")
    provider, separator, model_id = arm.model_key.partition(":")
    if not separator or not provider or not model_id:
        raise ValueError("study arm model_key must be provider:model_id")
    entry = registry.get(provider, model_id)
    if model_registry_entry_sha256(entry) != arm.model_registry_entry_sha256:
        raise ValueError("model registry entry digest does not match study arm")
    if entry.model_version_or_snapshot != arm.served_model_version:
        raise ValueError("served model version does not match study arm")
    if labels.scoring_policy.policy_id != spec.protocol.scoring_policy_id:
        raise ValueError("labels scoring policy differs from study protocol")
    if (
        cohort.expected_unit_count is not None
        and cohort.expected_unit_count != _expected_scored_units(forecast)
    ):
        raise ValueError("forecast scoreable unit count differs from cohort")
    records = captured.run_records
    if records is None:
        raise ValueError("captured run records are required for identity validation")
    for record in records:
        if record.get("harness") != spec.protocol.harness:
            raise ValueError("run receipt harness differs from study protocol")
        if record.get("ablation") != spec.protocol.ablation:
            raise ValueError("run receipt ablation differs from study protocol")
        if record.get("repeat_index") != spec.protocol.repeat_index:
            raise ValueError("run receipt repeat index differs from study protocol")
        if record.get("model_key") != arm.model_key:
            raise ValueError("run receipt model differs from study arm")


def _single_model_summary(
    summaries: Sequence[ScoreSummary],
    model_key: str,
) -> ScoreSummary:
    if len(summaries) != 1:
        raise ValueError("one study arm must contain exactly one model score")
    summary = summaries[0]
    if summary.model_id != model_key:
        raise ValueError("strict score model identity differs from study arm")
    return summary


def _expected_scored_units(forecast: ForecastRelease) -> int:
    return sum(unit.should_score for unit in forecast.prediction_units)


def _apply_cluster_projection(
    unit_scores: Sequence[UnitScore],
    *,
    cohort: StudyCohort,
) -> tuple[UnitScore, ...]:
    mapping = cohort.cluster_by_case
    score_case_ids = {score.case_id for score in unit_scores}
    if score_case_ids != set(cohort.case_ids):
        missing = sorted(set(cohort.case_ids) - score_case_ids)
        extra = sorted(score_case_ids - set(cohort.case_ids))
        raise ValueError(
            f"scored case census differs from cohort: missing={missing}, extra={extra}"
        )
    if cohort.cluster_unit == "case":
        return tuple(unit_scores)
    return tuple(
        replace(
            unit_score,
            candidate_id=None,
            related_family_id=mapping[unit_score.case_id],
            mdl_family_id=None,
        )
        for unit_score in unit_scores
    )


def _cluster_id_for_unit(unit: UnitScore, *, cohort: StudyCohort) -> str:
    return cohort.cluster_by_case[unit.case_id]


def _evaluate_comparison(
    spec: StudySpec,
    *,
    comparison: Any,
    cohorts: Mapping[str, StudyCohort],
    arms: Mapping[str, StudyArm],
    observations: Mapping[str, ArmObservation],
    summaries: Mapping[str, ScoreSummary],
) -> StudyComparison:
    arm_a = _find_arm(arms.values(), comparison.cohort_a_id, comparison.model_a_key)
    arm_b = _find_arm(arms.values(), comparison.cohort_b_id, comparison.model_b_key)
    cohort_a = cohorts[comparison.cohort_a_id]
    cohort_b = cohorts[comparison.cohort_b_id]
    observed_a = observations.get(arm_a.arm_id) if arm_a else None
    observed_b = observations.get(arm_b.arm_id) if arm_b else None
    planned_count = len(spec.planned_comparisons)
    adjusted_alpha = (
        spec.multiplicity.alpha / planned_count
        if spec.multiplicity.method == "bonferroni"
        else spec.multiplicity.alpha
    )
    base = _comparison_base(
        comparison=comparison,
        mode=spec.mode,
        planned_count=planned_count,
        alpha=spec.multiplicity.alpha,
        adjusted_alpha=adjusted_alpha,
        spec=spec,
        cohort_a=cohort_a,
        cohort_b=cohort_b,
        observation_a=observed_a,
        observation_b=observed_b,
    )
    if arm_a is None or arm_b is None:
        return _replace_model(
            base, updates={"status": "refused", "reason": "planned arm is absent"}
        )
    if observed_a is None or observed_b is None:
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": "planned arm observation is absent",
            },
        )
    if observed_a.status == "missing" or observed_b.status == "missing":
        return _replace_model(
            base,
            updates={
                "status": "missing_arm",
                "reason": "one or more run records are missing",
            },
        )
    if observed_a.status != "complete" or observed_b.status != "complete":
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": _arm_failure_reason(observed_a, observed_b),
            },
        )
    if (
        observed_a.scoring_policy_digest is None
        or observed_b.scoring_policy_digest is None
        or observed_a.scoring_policy_digest != observed_b.scoring_policy_digest
    ):
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": "scoring policy differs across cohorts",
            },
        )
    if cohort_a.cluster_unit != cohort_b.cluster_unit:
        return _replace_model(
            base, updates={"status": "refused", "reason": "cohort cluster units differ"}
        )
    case_overlap = set(cohort_a.case_ids).intersection(cohort_b.case_ids)
    if case_overlap:
        return _replace_model(
            base,
            updates={
                "status": "unsupported_dependence",
                "reason": f"cohort cases overlap: {sorted(case_overlap)}",
            },
        )
    cluster_overlap = set(cohort_a.cluster_by_case.values()).intersection(
        cohort_b.cluster_by_case.values()
    )
    if cluster_overlap:
        return _replace_model(
            base,
            updates={
                "status": "unsupported_dependence",
                "reason": (
                    f"cohort independence clusters overlap: {sorted(cluster_overlap)}"
                ),
            },
        )
    # Each cohort needs both model arms; the planned comparison names their
    # exact registry bindings.  A changed served revision is a different model
    # and cannot be smuggled into a cross-cohort change estimate.
    model_a_other = _find_arm(
        arms.values(), comparison.cohort_b_id, comparison.model_a_key
    )
    model_b_other = _find_arm(
        arms.values(), comparison.cohort_a_id, comparison.model_b_key
    )
    if model_a_other is None or model_b_other is None:
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": "both model arms are required in both cohorts",
            },
        )
    obs_a_other = observations[model_b_other.arm_id]
    obs_b_other = observations[model_a_other.arm_id]
    companion_observations = (obs_a_other, obs_b_other)
    if any(observation.status == "invalid" for observation in companion_observations):
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": _arm_failure_reason(*companion_observations),
            },
        )
    if any(observation.status == "missing" for observation in companion_observations):
        return _replace_model(
            base,
            updates={
                "status": "missing_arm",
                "reason": "one model arm is missing or incomplete in a cohort",
            },
        )
    policy_digests = {
        observation.scoring_policy_digest
        for observation in (observed_a, observed_b, obs_a_other, obs_b_other)
    }
    if len(policy_digests) != 1 or None in policy_digests:
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": "scoring policy differs across model/cohort arms",
            },
        )
    if spec.mode == "clean" and any(
        observation.suitability != "suitable_under_policy"
        for observation in (observed_a, observed_b, obs_a_other, obs_b_other)
    ):
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": (
                    "clean comparison requires suitable_under_policy for every arm"
                ),
            },
        )
    if not _same_model_binding(arm_a, model_a_other) or not _same_model_binding(
        arm_b, model_b_other
    ):
        return _replace_model(
            base,
            updates={
                "status": "refused",
                "reason": "model entry or served revision differs across cohorts",
            },
        )
    model_a_summary_in_a = summaries[arm_a.arm_id]
    model_b_summary_in_a = summaries[model_b_other.arm_id]
    model_a_summary_in_b = summaries[model_a_other.arm_id]
    model_b_summary_in_b = summaries[arm_b.arm_id]
    try:
        seed_a = _derived_seed(spec.seed, comparison.comparison_id, cohort_a.cohort_id)
        seed_b = _derived_seed(spec.seed, comparison.comparison_id, cohort_b.cohort_id)
        inference_a = paired_clustered_bootstrap(
            (
                ModelScoreInput(
                    comparison.model_a_key, tuple(model_a_summary_in_a.unit_scores)
                ),
                ModelScoreInput(
                    comparison.model_b_key, tuple(model_b_summary_in_a.unit_scores)
                ),
            ),
            config=BootstrapConfig(
                replicates=spec.replicates,
                seed=seed_a,
                ci_level=spec.confidence_level,
                rank_tier_correction="none",
            ),
        )
        inference_b = paired_clustered_bootstrap(
            (
                ModelScoreInput(
                    comparison.model_a_key, tuple(model_a_summary_in_b.unit_scores)
                ),
                ModelScoreInput(
                    comparison.model_b_key, tuple(model_b_summary_in_b.unit_scores)
                ),
            ),
            config=BootstrapConfig(
                replicates=spec.replicates,
                seed=seed_b,
                ci_level=spec.confidence_level,
                rank_tier_correction="none",
            ),
        )
    except ValueError as exc:
        return _replace_model(base, updates={"status": "refused", "reason": str(exc)})
    delta_a = inference_a.pairwise_deltas[0]
    delta_b = inference_b.pairwise_deltas[0]
    draws = tuple(
        replicate_b.micro_briers[comparison.model_a_key]
        - replicate_b.micro_briers[comparison.model_b_key]
        - (
            replicate_a.micro_briers[comparison.model_a_key]
            - replicate_a.micro_briers[comparison.model_b_key]
        )
        for replicate_a, replicate_b in zip(
            inference_a.replicates,
            inference_b.replicates,
            strict=True,
        )
    )
    return _replace_model(
        base,
        updates={
            "status": ("complete" if spec.mode == "clean" else "exploratory"),
            "seed_a": seed_a,
            "seed_b": seed_b,
            "observed_delta_a": delta_a.observed_delta,
            "observed_delta_b": delta_b.observed_delta,
            "effect": delta_b.observed_delta - delta_a.observed_delta,
            "ci_low": quantile(draws, adjusted_alpha / 2),
            "ci_high": quantile(draws, 1 - adjusted_alpha / 2),
        },
    )


def _replace_model(
    model: StudyComparison, *, updates: Mapping[str, Any]
) -> StudyComparison:
    """Construct a validated immutable result with a small set of changes."""

    record = model.model_dump(mode="python")
    record.update(updates)
    return StudyComparison.model_validate(record)


def _comparison_base(
    *,
    comparison: Any,
    mode: StudyMode,
    planned_count: int,
    alpha: float,
    adjusted_alpha: float,
    spec: StudySpec,
    cohort_a: StudyCohort,
    cohort_b: StudyCohort,
    observation_a: ArmObservation | None,
    observation_b: ArmObservation | None,
) -> StudyComparison:
    return StudyComparison(
        comparison_id=comparison.comparison_id,
        cohort_a_id=comparison.cohort_a_id,
        cohort_b_id=comparison.cohort_b_id,
        model_a_key=comparison.model_a_key,
        model_b_key=comparison.model_b_key,
        claim_mode=mode,
        status="refused",
        planned_comparison_count=planned_count,
        alpha=alpha,
        adjusted_alpha=adjusted_alpha,
        seed_a=_derived_seed(spec.seed, comparison.comparison_id, cohort_a.cohort_id),
        seed_b=_derived_seed(spec.seed, comparison.comparison_id, cohort_b.cohort_id),
        replicates=spec.replicates,
        confidence_level=spec.confidence_level,
        cluster_unit=cohort_a.cluster_unit,
        expected_case_count_a=len(cohort_a.case_ids),
        completed_case_count_a=observation_a.completed_case_count
        if observation_a
        else 0,
        expected_unit_count_a=(
            observation_a.expected_unit_count
            if observation_a
            else cohort_a.expected_unit_count
        ),
        completed_unit_count_a=observation_a.completed_unit_count
        if observation_a
        else 0,
        expected_case_count_b=len(cohort_b.case_ids),
        completed_case_count_b=observation_b.completed_case_count
        if observation_b
        else 0,
        expected_unit_count_b=(
            observation_b.expected_unit_count
            if observation_b
            else cohort_b.expected_unit_count
        ),
        completed_unit_count_b=observation_b.completed_unit_count
        if observation_b
        else 0,
        expected_cluster_count_a=len(set(cohort_a.cluster_by_case.values())),
        completed_cluster_count_a=observation_a.cluster_count if observation_a else 0,
        expected_cluster_count_b=len(set(cohort_b.cluster_by_case.values())),
        completed_cluster_count_b=observation_b.cluster_count if observation_b else 0,
        cluster_basis_a=cohort_a.cluster_basis,
        cluster_basis_b=cohort_b.cluster_basis,
    )


def _find_arm(
    arms: Iterable[StudyArm],
    cohort_id: str,
    model_key: str,
) -> StudyArm | None:
    matches = tuple(
        arm for arm in arms if arm.cohort_id == cohort_id and arm.model_key == model_key
    )
    if len(matches) > 1:
        raise StudyEvaluationError(
            f"multiple study arms match cohort/model pair {cohort_id}/{model_key}"
        )
    return matches[0] if matches else None


def _same_model_binding(left: StudyArm, right: StudyArm) -> bool:
    return (
        left.model_key,
        left.model_registry_entry_sha256,
        left.served_model_version,
    ) == (
        right.model_key,
        right.model_registry_entry_sha256,
        right.served_model_version,
    )


def _arm_failure_reason(
    left: ArmObservation | None,
    right: ArmObservation | None,
) -> str:
    reasons = [
        observation.reason
        for observation in (left, right)
        if observation is not None and observation.reason
    ]
    return "; ".join(reasons) or "one or more arms are not complete"


def _derived_seed(base: int, comparison_id: str, cohort_id: str) -> int:
    payload = f"legalforecast.study.v1\0{base}\0{comparison_id}\0{cohort_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _scoring_policy_digest(labels: LabelsRelease) -> str:
    payload = json.dumps(
        labels.scoring_policy.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
