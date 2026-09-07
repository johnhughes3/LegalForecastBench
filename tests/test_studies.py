"""Provider-free public-artifact tests for the evaluation-study domain."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from legalforecast.contracts import ARTIFACT_RAW_SHA256_V1, PUBLIC_RUN_RECEIPT_V1
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    ToolPolicy,
    TrainingCutoffStatus,
    load_model_registry_bytes,
    model_registry_entry_sha256,
    model_registry_sha256,
)
from legalforecast.evals.output_parser import parse_model_output, public_parser_record
from legalforecast.release import (
    BenchmarkRunManifest,
    CaseDraft,
    DocumentDraft,
    DocumentRole,
    ForecastDraft,
    ForecastManifestBinding,
    LabelsDraft,
    OpaqueObjectLocator,
    OppositionStatus,
    PredictionUnitDraft,
    QCStatus,
    RoleObjectLocator,
    ScoringPolicy,
    SelectedCase,
    UnitOutcome,
    issue_release,
    serialize_run_manifest,
)
from legalforecast.studies import (
    ClusterAssignment,
    Multiplicity,
    PlannedComparison,
    StudyArm,
    StudyArmInput,
    StudyCohort,
    StudyProtocol,
    StudySpec,
    Suitability,
    SuitabilityBinding,
    evaluate_study,
)

RUN_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_study_spec_is_immutable_and_keeps_full_planned_family(tmp_path: Path) -> None:
    spec = _spec(_artifacts(tmp_path), mode="clean", comparisons=2)
    with pytest.raises(ValueError, match="immutable"):
        spec.model_copy(update={"study_id": "changed"})
    assert len(spec.planned_comparisons) == 2
    assert len(spec.protocol.settings_digest) == 64


def test_study_computes_cross_cohort_change_from_strict_scores(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="clean")
    report = evaluate_study(spec, arm_inputs=artifacts)
    comparison = report.comparisons[0]
    assert comparison.status == "complete"
    assert comparison.effect is not None
    assert comparison.observed_delta_a is not None
    assert comparison.observed_delta_b is not None
    assert comparison.ci_low is not None
    assert comparison.ci_high is not None
    assert comparison.planned_comparison_count == 1
    assert comparison.adjusted_alpha == pytest.approx(0.05)
    assert comparison.expected_cluster_count_a == 2
    assert comparison.expected_unit_count_a == 2
    assert report.to_record()["comparisons"][0]["orientation"] == (
        "cohort_b_delta_minus_cohort_a_delta"
    )


def test_study_scores_the_protocols_exact_later_repeat(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path, repeat_index=2)
    spec = _spec(artifacts, mode="clean", repeat_index=2)

    report = evaluate_study(spec, arm_inputs=artifacts)

    assert all(
        observation.status == "complete" for observation in report.arm_observations
    )
    assert report.comparisons[0].status == "complete"


def test_same_model_entry_can_span_distinct_registry_snapshots(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="clean")
    original = artifacts["b-a"]
    entry = original.model_registry.entries[0]
    registry_bytes = json.dumps(
        [entry.to_record(), _registry_entry("unrelated-model").to_record()],
        sort_keys=True,
    ).encode()
    registry = load_model_registry_bytes(registry_bytes)
    registry_sha256 = model_registry_sha256(registry_bytes)
    changed_inputs = dict(artifacts)
    changed_inputs["b-a"] = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=registry,
        run_records=tuple(
            {**record, "model_registry_sha256": registry_sha256}
            for record in (original.run_records or ())
        ),
    )
    changed_arms = []
    for arm in spec.arms:
        if arm.arm_id != "b-a":
            changed_arms.append(arm)
            continue
        binding = arm.suitability.binding.model_dump(mode="python")
        binding["model_registry_sha256"] = registry_sha256
        suitability = arm.suitability.model_dump(mode="python")
        suitability["binding"] = binding
        arm_record = arm.model_dump(mode="python")
        arm_record["model_registry_sha256"] = registry_sha256
        arm_record["suitability"] = suitability
        changed_arms.append(StudyArm.model_validate(arm_record))
    changed_spec = StudySpec.model_validate(
        {**spec.model_dump(mode="python"), "arms": tuple(changed_arms)}
    )

    report = evaluate_study(changed_spec, arm_inputs=changed_inputs)

    assert report.arm_observations[2].status == "complete"
    assert report.comparisons[0].status == "complete"


def test_linked_matter_clusters_are_explicit_and_order_invariant(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    first = _spec(artifacts, mode="exploratory")
    reversed_cohort = first.cohorts[0].model_dump()
    reversed_cohort["cluster_assignments"] = list(
        reversed(reversed_cohort["cluster_assignments"])
    )
    # A canonical public mapping is sorted by case ID at construction time.
    reversed_cohort["cluster_assignments"] = tuple(
        sorted(
            reversed_cohort["cluster_assignments"],
            key=lambda item: item["case_id"],
        )
    )
    cohorts = (StudyCohort.model_validate(reversed_cohort), *first.cohorts[1:])
    second = first.model_validate({**first.model_dump(), "cohorts": cohorts})
    assert evaluate_study(first, arm_inputs=artifacts).comparisons[0].effect == (
        evaluate_study(second, arm_inputs=artifacts).comparisons[0].effect
    )


def test_missing_arm_is_reported_and_bonferroni_denominator_is_preserved(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory", comparisons=2)
    missing = dict(artifacts)
    original_missing = artifacts["b-a"]
    missing["b-a"] = StudyArmInput(
        forecast_release=original_missing.forecast_release,
        labels_release=original_missing.labels_release,
        manifest=original_missing.manifest,
        model_registry=original_missing.model_registry,
        run_records=None,
    )
    report = evaluate_study(spec, arm_inputs=missing)
    assert report.comparisons[0].status == "missing_arm"
    assert report.comparisons[0].planned_comparison_count == 2
    assert report.comparisons[0].adjusted_alpha == pytest.approx(0.025)
    assert report.arm_observations[2].status == "missing"


def test_clean_unknown_suitability_refuses_claim_but_exploratory_reports_result(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    clean = _spec(artifacts, mode="clean", suitability="unknown")
    exploratory = _spec(artifacts, mode="exploratory", suitability="unknown")
    clean_report = evaluate_study(clean, arm_inputs=artifacts)
    exploratory_report = evaluate_study(exploratory, arm_inputs=artifacts)
    assert clean_report.comparisons[0].status == "refused"
    assert "suitable_under_policy" in (clean_report.comparisons[0].reason or "")
    assert exploratory_report.comparisons[0].status == "exploratory"


def test_shared_linked_matter_cluster_is_typed_unsupported_dependence(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory", shared_cluster=True)
    report = evaluate_study(spec, arm_inputs=artifacts)
    assert report.comparisons[0].status == "unsupported_dependence"
    assert "clusters overlap" in (report.comparisons[0].reason or "")


def test_protocol_mismatch_is_refused_before_scientific_contrast(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    bad = dict(artifacts)
    original = artifacts["a-a"]
    records = tuple(
        {**record, "ablation": "ablation"} for record in (original.run_records or ())
    )
    bad["a-a"] = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=records,
    )
    report = evaluate_study(spec, arm_inputs=bad)
    assert report.comparisons[0].status == "refused"
    assert report.arm_observations[0].status == "invalid"
    assert "ablation" in (report.arm_observations[0].reason or "")


def test_invalid_off_diagonal_companion_is_refused_not_missing(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    bad = dict(artifacts)
    original = artifacts["a-b"]
    records = tuple(
        {**record, "ablation": "corrupt"} for record in (original.run_records or ())
    )
    bad["a-b"] = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=records,
    )
    report = evaluate_study(spec, arm_inputs=bad)
    assert report.comparisons[0].status == "refused"
    assert "ablation" in (report.comparisons[0].reason or "")


def test_study_spec_rejects_duplicate_cohort_model_pair(tmp_path: Path) -> None:
    spec = _spec(_artifacts(tmp_path), mode="exploratory")
    duplicate = StudyArm.model_validate(
        {
            **spec.arms[1].model_dump(mode="python"),
            "arm_id": "duplicate-arm",
            "cohort_id": spec.arms[0].cohort_id,
            "model_key": spec.arms[0].model_key,
        }
    )
    with pytest.raises(ValueError, match="cohort/model pair"):
        StudySpec.model_validate(
            {
                **spec.model_dump(mode="python"),
                "arms": (*spec.arms, duplicate),
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("benchmark_family_id", "different-family"),
        ("benchmark_version_id", "version-a"),
    ),
)
def test_study_spec_rejects_invalid_cohort_change_axes(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    spec = _spec(_artifacts(tmp_path), mode="exploratory")
    cohort_b = {
        **spec.cohorts[1].model_dump(mode="python"),
        field: value,
    }
    with pytest.raises(ValueError, match="cohort change comparisons"):
        StudySpec.model_validate(
            {
                **spec.model_dump(mode="python"),
                "cohorts": (spec.cohorts[0], cohort_b),
            }
        )


def test_study_spec_requires_confidence_complement(tmp_path: Path) -> None:
    spec = _spec(_artifacts(tmp_path), mode="exploratory")
    with pytest.raises(ValueError, match="confidence_level"):
        StudySpec.model_validate(
            {
                **spec.model_dump(mode="python"),
                "confidence_level": 0.90,
            }
        )


def test_protocol_settings_digest_is_computed_from_frozen_settings() -> None:
    protocol = StudyProtocol(
        protocol_id="protocol-v1",
        scoring_policy_id="policy-v1",
    )
    changed = StudyProtocol(
        protocol_id="protocol-v1",
        scoring_policy_id="policy-v1",
        ablation="ablation-v1",
    )
    assert len(protocol.settings_digest) == 64
    assert protocol.settings_digest != changed.settings_digest
    assert "settings_digest" not in protocol.model_dump(mode="json")
    with pytest.raises(ValueError, match="settings_digest"):
        StudyProtocol.model_validate(
            {
                "protocol_id": "protocol-v1",
                "scoring_policy_id": "policy-v1",
                "settings_digest": "a" * 64,
            }
        )


def test_stale_suitability_binding_invalidates_only_that_arm(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    stale_binding = {
        **spec.arms[0].suitability.binding.model_dump(mode="python"),
        "benchmark_version_id": "version-stale",
    }
    stale_suitability = {
        **spec.arms[0].suitability.model_dump(mode="python"),
        "binding": stale_binding,
    }
    stale_arm = StudyArm.model_validate(
        {
            **spec.arms[0].model_dump(mode="python"),
            "suitability": stale_suitability,
        }
    )
    changed_arms = (stale_arm, *spec.arms[1:])
    changed_spec = StudySpec.model_validate(
        {**spec.model_dump(mode="python"), "arms": changed_arms}
    )
    report = evaluate_study(changed_spec, arm_inputs=artifacts)
    assert report.arm_observations[0].status == "invalid"
    assert "suitability binding" in (report.arm_observations[0].reason or "")
    assert report.arm_observations[1].status == "complete"


def test_suitability_binding_rejects_stale_protocol_id_with_same_settings(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    stale_binding = {
        **spec.arms[0].suitability.binding.model_dump(mode="python"),
        "protocol_id": "protocol-stale",
    }
    stale_suitability = {
        **spec.arms[0].suitability.model_dump(mode="python"),
        "binding": stale_binding,
    }
    stale_arm = StudyArm.model_validate(
        {
            **spec.arms[0].model_dump(mode="python"),
            "suitability": stale_suitability,
        }
    )
    changed_spec = StudySpec.model_validate(
        {
            **spec.model_dump(mode="python"),
            "arms": (stale_arm, *spec.arms[1:]),
        }
    )
    report = evaluate_study(changed_spec, arm_inputs=artifacts)
    assert report.arm_observations[0].status == "invalid"
    assert "suitability binding" in (report.arm_observations[0].reason or "")


def test_invalid_release_denominator_does_not_erase_other_arm(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    original = artifacts["a-a"]
    forecast = original.forecast_release
    malformed_forecast = forecast.model_copy(
        update={
            "unit_count": forecast.unit_count + 1,
            "prediction_units": (
                *forecast.prediction_units,
                forecast.prediction_units[-1],
            ),
        }
    )
    malformed = StudyArmInput(
        forecast_release=malformed_forecast,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=original.run_records,
    )
    changed = dict(artifacts)
    changed["a-a"] = malformed
    report = evaluate_study(spec, arm_inputs=changed)
    assert report.arm_observations[0].status == "invalid"
    assert report.arm_observations[0].expected_unit_count == 2
    assert report.arm_observations[1].status == "complete"
    assert report.arm_observations[1].expected_unit_count == 2


def test_empty_authenticated_receipts_are_missing(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    original = artifacts["a-a"]
    empty = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=(),
    )
    changed = dict(artifacts)
    changed["a-a"] = empty
    report = evaluate_study(spec, arm_inputs=changed)
    observation = report.arm_observations[0]
    assert observation.status == "missing"
    assert observation.completed_case_count == 0
    assert observation.completed_unit_count == 0
    assert observation.expected_unit_count == 2


def test_partial_valid_receipts_are_missing_with_completed_denominators(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    original = artifacts["a-a"]
    partial = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=(original.run_records or ())[:1],
    )
    changed = dict(artifacts)
    changed["a-a"] = partial
    report = evaluate_study(spec, arm_inputs=changed)
    observation = report.arm_observations[0]
    assert observation.status == "missing"
    assert observation.completed_case_count == 1
    assert observation.completed_unit_count == 1
    assert observation.expected_case_count == 2
    assert observation.expected_unit_count == 2
    assert report.comparisons[0].status == "missing_arm"


def test_partial_model_refusal_keeps_missing_run_classification(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    original = artifacts["a-a"]
    source_record = (original.run_records or ())[0]
    required_unit_id = source_record["required_unit_ids"][0]
    refusal = parse_model_output(
        "I cannot complete this assessment.",
        required_unit_ids=(required_unit_id,),
    )
    refusal_record = {
        **source_record,
        "parser_output": public_parser_record(refusal),
    }
    partial = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=(refusal_record,),
    )
    changed = dict(artifacts)
    changed["a-a"] = partial
    report = evaluate_study(spec, arm_inputs=changed)
    observation = report.arm_observations[0]
    assert observation.status == "missing"
    assert observation.completed_case_count == 1
    assert observation.completed_unit_count == 1


def test_malformed_partial_receipts_remain_invalid(
    tmp_path: Path,
) -> None:
    artifacts = _artifacts(tmp_path)
    spec = _spec(artifacts, mode="exploratory")
    original = artifacts["a-a"]
    source_record = (original.run_records or ())[0]
    malformed_record = {**source_record, "prompt_sha256": "0" * 64}
    malformed = StudyArmInput(
        forecast_release=original.forecast_release,
        labels_release=original.labels_release,
        manifest=original.manifest,
        model_registry=original.model_registry,
        run_records=(malformed_record,),
    )
    changed = dict(artifacts)
    changed["a-a"] = malformed
    report = evaluate_study(spec, arm_inputs=changed)
    observation = report.arm_observations[0]
    assert observation.status == "invalid"
    assert observation.completed_case_count == 0
    assert report.comparisons[0].status == "refused"


def _spec(
    artifacts: dict[str, StudyArmInput],
    *,
    mode: str,
    suitability: str = "suitable_under_policy",
    comparisons: int = 1,
    shared_cluster: bool = False,
    repeat_index: int = 1,
) -> StudySpec:
    cohorts = (
        _cohort("a", artifacts["a-a"], shared_cluster=shared_cluster),
        _cohort("b", artifacts["b-a"], shared_cluster=shared_cluster),
    )
    planned = [
        PlannedComparison(
            comparison_id="comparison-1",
            cohort_a_id="cohort-a",
            cohort_b_id="cohort-b",
            model_a_key="fixture:model-a",
            model_b_key="fixture:model-b",
        )
    ]
    if comparisons == 2:
        planned.append(
            PlannedComparison(
                comparison_id="comparison-2",
                cohort_a_id="cohort-a",
                cohort_b_id="cohort-b",
                model_a_key="fixture:model-b",
                model_b_key="fixture:model-a",
            )
        )
    protocol = StudyProtocol(
        protocol_id="protocol-v1",
        scoring_policy_id="policy-v1",
        repeat_index=repeat_index,
    )
    cohorts_by_id = {cohort.cohort_id: cohort for cohort in cohorts}
    arms = tuple(
        _study_arm(
            arm_id,
            cohort_id,
            model_key,
            artifacts[arm_id],
            cohort=cohorts_by_id[cohort_id],
            protocol=protocol,
            suitability=suitability,
        )
        for arm_id, cohort_id, model_key in (
            ("a-a", "cohort-a", "fixture:model-a"),
            ("a-b", "cohort-a", "fixture:model-b"),
            ("b-a", "cohort-b", "fixture:model-a"),
            ("b-b", "cohort-b", "fixture:model-b"),
        )
    )
    return StudySpec(
        study_id="study-fixture",
        study_revision="revision-1",
        mode=mode,
        protocol=protocol,
        cohorts=cohorts,
        arms=arms,
        planned_comparisons=tuple(planned),
        multiplicity=Multiplicity(method="bonferroni"),
        replicates=25,
        confidence_level=0.95,
        seed=20260907,
    )


def _cohort(
    prefix: str,
    captured: StudyArmInput,
    *,
    shared_cluster: bool,
) -> StudyCohort:
    forecast = captured.forecast_release
    labels = captured.labels_release
    case_ids = tuple(case.case_id for case in forecast.cases)
    return StudyCohort(
        cohort_id=f"cohort-{prefix}",
        benchmark_family_id="family-v1",
        benchmark_version_id=f"version-{prefix}",
        forecast_release_id=forecast.release_id,
        forecast_release_digest=forecast.release_digest,
        labels_release_id=labels.release_id,
        labels_release_digest=labels.release_digest,
        manifest_sha256=hashlib.sha256(
            serialize_run_manifest(captured.manifest)
        ).hexdigest(),
        case_ids=case_ids,
        expected_unit_count=sum(
            unit.should_score for unit in forecast.prediction_units
        ),
        cluster_unit="linked_matter",
        cluster_basis="public linked-matter census fixture",
        cluster_assignments=tuple(
            ClusterAssignment(
                case_id=case_id,
                cluster_id=(
                    "shared-cluster" if shared_cluster else f"{prefix}-matter-{index}"
                ),
            )
            for index, case_id in enumerate(case_ids)
        ),
    )


def _study_arm(
    arm_id: str,
    cohort_id: str,
    model_key: str,
    captured: StudyArmInput,
    *,
    cohort: StudyCohort,
    protocol: StudyProtocol,
    suitability: str,
) -> StudyArm:
    provider, _, model_id = model_key.partition(":")
    entry = captured.model_registry.get(provider, model_id)
    assert captured.run_records
    identity = captured.run_records[0]["run_identity_sha256"]
    assert isinstance(identity, str)
    return StudyArm(
        arm_id=arm_id,
        cohort_id=cohort_id,
        model_key=model_key,
        model_registry_sha256=captured.model_registry.source_sha256 or "0" * 64,
        model_registry_entry_sha256=model_registry_entry_sha256(entry),
        served_model_version=entry.model_version_or_snapshot,
        run_id=str(captured.manifest.run_id),
        run_identity_sha256=identity,
        suitability=Suitability(
            status=suitability,
            policy_id="policy-v1",
            basis="public suitability fixture",
            binding=SuitabilityBinding(
                benchmark_family_id=cohort.benchmark_family_id,
                benchmark_version_id=cohort.benchmark_version_id,
                forecast_release_digest=cohort.forecast_release_digest,
                manifest_sha256=cohort.manifest_sha256,
                model_key=model_key,
                model_registry_sha256=captured.model_registry.source_sha256 or "0" * 64,
                model_registry_entry_sha256=model_registry_entry_sha256(entry),
                served_model_version=entry.model_version_or_snapshot,
                protocol_id=protocol.protocol_id,
                protocol_settings_digest=protocol.settings_digest,
                scoring_policy_id=protocol.scoring_policy_id,
            ),
        ),
    )


def _artifacts(tmp_path: Path, *, repeat_index: int = 1) -> dict[str, StudyArmInput]:
    return _build_artifacts(tmp_path, repeat_index=repeat_index)


def _build_artifacts(
    tmp_path: Path, *, repeat_index: int = 1
) -> dict[str, StudyArmInput]:
    result: dict[str, StudyArmInput] = {}
    for prefix, case_ids in (
        ("a", ("a-case-001", "a-case-002")),
        ("b", ("b-case-001", "b-case-002")),
    ):
        release, manifest = _issue_release(tmp_path, case_ids, prefix)
        for model_id, arm_id, identity, probability in (
            ("model-a", f"{prefix}-a", "a" * 64, 0.2),
            ("model-b", f"{prefix}-b", "b" * 64, 0.8),
        ):
            registry, registry_bytes = _registry(model_id)
            records = tuple(
                _receipt(
                    release,
                    manifest,
                    registry,
                    registry_bytes,
                    identity,
                    probability,
                    unit,
                    repeat_index=repeat_index,
                )
                for unit in release.forecast.prediction_units
            )
            result[arm_id] = StudyArmInput(
                forecast_release=release.forecast,
                labels_release=release.labels,
                manifest=manifest,
                model_registry=registry,
                run_records=records,
            )
    # Match the public arm IDs used by _spec.
    return {
        "a-a": result["a-a"],
        "a-b": result["a-b"],
        "b-a": result["b-a"],
        "b-b": result["b-b"],
    }


def _issue_release(tmp_path: Path, case_ids: tuple[str, ...], prefix: str):
    artifact_root = tmp_path / f"artifacts-{prefix}"
    artifact_root.mkdir()
    cases = []
    units = []
    outcomes = []
    for index, case_id in enumerate(case_ids, start=1):
        complaint = DocumentDraft(
            document_id=f"{case_id}-complaint",
            role="complaint",
            path=f"documents/{case_id}/complaint.txt",
        )
        motion = DocumentDraft(
            document_id=f"{case_id}-motion",
            role="motion_to_dismiss_memorandum",
            path=f"documents/{case_id}/motion.txt",
        )
        cases.append(CaseDraft(case_id=case_id, documents=(complaint, motion)))
        unit_id = f"{prefix}-unit-{index:03d}"
        units.append(
            PredictionUnitDraft(
                unit_id=unit_id,
                case_id=case_id,
                claim_name="claim",
                defendant_group="defendant",
                count="Count I",
                should_score=True,
                model_visible_document_ids=(complaint.document_id, motion.document_id),
                packet_path=f"packets/{unit_id}.json",
                prompt_path=f"prompts/{unit_id}.txt",
            )
        )
        outcomes.append(UnitOutcome(unit_id=unit_id, outcome=index % 2))
    manifest = BenchmarkRunManifest(
        run_id=RUN_ID
        if prefix == "a"
        else UUID("22345678-1234-5678-1234-567812345678"),
        selected_cases=tuple(
            SelectedCase(
                case_id=case_id,
                provider_id="public-fixture",
                qc_status=QCStatus.ACCEPTED,
                role_locators=tuple(
                    RoleObjectLocator(
                        role=role,
                        locator=OpaqueObjectLocator(
                            provider_id="public-fixture",
                            object_locator=f"{case_id}/{role.value}",
                            version_id=f"{case_id}-{role.value}-v1",
                        ),
                    )
                    for role in (
                        DocumentRole.DECISION,
                        DocumentRole.MOTION,
                        DocumentRole.COMPLAINT,
                    )
                ),
                opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
            )
            for case_id in case_ids
        ),
        policy_version="policy-v1",
        code_revision="a" * 40,
        created_at=datetime(2026, 9, 7, tzinfo=UTC),
        locked_at=datetime(2026, 9, 7, 0, 1, tzinfo=UTC),
    )
    manifest_digest = hashlib.sha256(serialize_run_manifest(manifest)).hexdigest()
    payloads = {}
    for case in cases:
        for document in case.documents:
            payloads[document.path] = b"public fixture document"
    for unit in units:
        payloads[unit.packet_path] = b"public fixture packet"
        payloads[unit.prompt_path] = b"public fixture prompt"
    for relative_path, payload in payloads.items():
        path = artifact_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    forecast_draft = ForecastDraft(
        release_id=f"release-{prefix}",
        policy_digest="1" * 64,
        code_version="code-v1",
        packet_builder_version="packet-v1",
        run_manifest_binding=ForecastManifestBinding(
            release_id=f"release-{prefix}",
            run_id=manifest.run_id,
            policy_version=manifest.policy_version,
            code_revision=manifest.code_revision,
            manifest_sha256=manifest_digest,
        ),
        cases=tuple(cases),
        prediction_units=tuple(units),
    )
    labels_draft = LabelsDraft(
        release_id=f"release-{prefix}",
        scoring_policy=ScoringPolicy(policy_id="policy-v1"),
        unit_outcomes=tuple(outcomes),
    )
    return issue_release(
        forecast_draft, labels_draft, artifact_root=artifact_root
    ), manifest


def _registry(model_id: str) -> tuple[ModelRegistry, bytes]:
    entry = _registry_entry(model_id)
    payload = json.dumps([entry.to_record()], sort_keys=True).encode()
    return load_model_registry_bytes(payload), payload


def _registry_entry(model_id: str) -> ModelRegistryEntry:
    return ModelRegistryEntry(
        provider="fixture",
        model_id=model_id,
        display_name=model_id,
        model_version_or_snapshot="fixture-1",
        release_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        release_timestamp_source="public fixture",
        provider_training_cutoff_status=TrainingCutoffStatus.NOT_DISCLOSED,
        max_output_tokens=256,
        network_disabled=True,
        search_disabled=True,
        tool_policy=ToolPolicy.NO_TOOLS,
        context_limit=4096,
        pricing_source="fixture",
        input_token_price=0,
        output_token_price=0,
    )


def _receipt(
    release,
    manifest,
    registry,
    registry_bytes,
    identity,
    probability,
    unit,
    *,
    repeat_index: int = 1,
):
    entry = registry.entries[0]
    cell_id = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "case_id": unit.case_id,
                "repeat_index": repeat_index,
                "run_identity_sha256": identity,
                "unit_id": unit.unit_id,
            },
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )
    parsed = parse_model_output(
        json.dumps(
            {
                "case_assessment": "public fixture",
                "predictions": [
                    {
                        "unit_id": unit.unit_id,
                        "probability_fully_dismissed": probability,
                    }
                ],
            }
        ),
        required_unit_ids=(unit.unit_id,),
    )
    return {
        "release_id": release.forecast.release_id,
        "forecast_release_digest": release.forecast.release_digest,
        "run_identity_sha256": identity,
        "schema_version": str(PUBLIC_RUN_RECEIPT_V1),
        "cell_id": cell_id,
        "case_id": unit.case_id,
        "unit_id": unit.unit_id,
        "required_unit_ids": [unit.unit_id],
        "model_key": entry.registry_key,
        "model_id": entry.registry_key,
        "harness": "native",
        "ablation": "none",
        "repeat_index": repeat_index,
        "model_registry_sha256": model_registry_sha256(registry_bytes),
        "model_registry_entry_sha256": model_registry_entry_sha256(entry),
        "prompt_sha256": unit.prompt_sha256,
        "request_body_sha256": "f" * 64,
        "served_model_version": entry.model_version_or_snapshot,
        "parser_output": public_parser_record(parsed),
    }
