from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from legalforecast.cli import main
from legalforecast.evals.model_registry import (
    load_model_registry,
    model_registry_entry_sha256,
    model_registry_sha256,
)
from legalforecast.release import (
    BenchmarkRunManifest,
    DocumentRole,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    SelectedCase,
    serialize_run_manifest,
    validate_release,
)
from legalforecast.runner import issue_runner_fixture
from legalforecast.studies.models import (
    Multiplicity,
    PlannedComparison,
    StudyArm,
    StudyCohort,
    StudyProtocol,
    StudySpec,
    Suitability,
    SuitabilityBinding,
)

_DIGEST = "a" * 64


def test_study_report_cli_preserves_omitted_arms_as_missing(
    tmp_path: Path,
) -> None:
    spec = _spec()
    spec_path = tmp_path / "study-spec.json"
    inputs_path = tmp_path / "study-inputs.json"
    output_path = tmp_path / "study-report.json"
    spec_path.write_text(spec.model_dump_json(), encoding="utf-8")
    inputs_path.write_text(
        json.dumps({"arms": {"arm-a": {"run_records": None}, "arm-b": None}}) + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "study",
                "report",
                "--spec",
                str(spec_path),
                "--inputs",
                str(inputs_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["status"] for item in report["arm_observations"]] == [
        "missing",
        "missing",
    ]
    assert all(
        item["reason"] == "run records are missing"
        for item in report["arm_observations"]
    )
    assert report["comparisons"][0]["status"] == "missing_arm"


def test_study_report_cli_loads_public_artifacts_for_explicit_missing_run(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    artifact_root = fixture / "release"
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_bytes(serialize_run_manifest(_manifest()))
    forecast_path = artifact_root / "forecast-release.json"
    labels_path = artifact_root / "labels-release.json"
    forecast, labels = validate_release(
        forecast_path,
        labels_path,
        artifact_root=artifact_root,
    )
    registry_path = fixture / "model-registry.json"
    registry = load_model_registry(registry_path)
    registry_bytes = registry_path.read_bytes()
    registry_sha256 = model_registry_sha256(registry_bytes)
    model_key = registry.entries[0].registry_key
    model_entry_sha256 = model_registry_entry_sha256(registry.entries[0])

    spec = _spec(
        forecast_release_id=forecast.release_id,
        forecast_release_digest=forecast.release_digest,
        labels_release_id=labels.release_id,
        labels_release_digest=labels.release_digest,
        manifest_sha256=_sha256(manifest_path.read_bytes()),
        model_key=model_key,
        model_registry_sha256=registry_sha256,
        model_registry_entry_sha256=model_entry_sha256,
        served_model_version=registry.entries[0].model_version_or_snapshot,
        case_ids=tuple(case.case_id for case in forecast.cases),
        cohort_b_case_ids=tuple(case.case_id for case in forecast.cases),
    )
    spec_path = tmp_path / "study-spec.json"
    spec_path.write_text(spec.model_dump_json(), encoding="utf-8")
    inputs_path = tmp_path / "study-inputs.json"
    inputs_path.write_text(
        json.dumps(
            {
                "artifact_root": "fixture/release",
                "arms": {
                    "arm-a": {
                        "forecast_release": "fixture/release/forecast-release.json",
                        "labels_release": "fixture/release/labels-release.json",
                        "manifest": "run-manifest.json",
                        "model_registry": "fixture/model-registry.json",
                        "run_records": None,
                    },
                    "arm-b": {
                        "forecast_release": "fixture/release/forecast-release.json",
                        "labels_release": "fixture/release/labels-release.json",
                        "manifest": "run-manifest.json",
                        "model_registry": "fixture/model-registry.json",
                        "run_records": None,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "study-report.json"

    assert (
        main(
            [
                "study",
                "report",
                "--spec",
                str(spec_path),
                "--inputs",
                str(inputs_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["arm_observations"][0]["expected_case_count"] == 3
    assert report["arm_observations"][0]["expected_unit_count"] == 3
    assert report["arm_observations"][0]["status"] == "missing"


def test_study_report_cli_refuses_malformed_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec_path = tmp_path / "study-spec.json"
    inputs_path = tmp_path / "study-inputs.json"
    output_path = tmp_path / "study-report.json"
    spec_path.write_text("[]\n", encoding="utf-8")
    inputs_path.write_text("{}\n", encoding="utf-8")

    assert (
        main(
            [
                "study",
                "report",
                "--spec",
                str(spec_path),
                "--inputs",
                str(inputs_path),
                "--output",
                str(output_path),
            ]
        )
        == 2
    )
    assert "study specification must contain a JSON object" in capsys.readouterr().err
    assert not output_path.exists()


def _spec(
    *,
    forecast_release_id: str = "forecast-a",
    forecast_release_digest: str = _DIGEST,
    labels_release_id: str = "labels-a",
    labels_release_digest: str = _DIGEST,
    manifest_sha256: str = _DIGEST,
    model_key: str = "provider:model-a",
    model_registry_sha256: str = _DIGEST,
    model_registry_entry_sha256: str = _DIGEST,
    served_model_version: str = "model-a-v1",
    case_ids: tuple[str, ...] = ("case-a-1",),
    cohort_b_case_ids: tuple[str, ...] | None = None,
) -> StudySpec:
    if cohort_b_case_ids is None:
        cohort_b_case_ids = tuple(f"{case_id}-b" for case_id in case_ids)
    cohorts = (
        StudyCohort(
            cohort_id="cohort-a",
            benchmark_family_id="family",
            benchmark_version_id="version-a",
            forecast_release_id=forecast_release_id,
            forecast_release_digest=forecast_release_digest,
            labels_release_id=labels_release_id,
            labels_release_digest=labels_release_digest,
            manifest_sha256=manifest_sha256,
            case_ids=case_ids,
            expected_unit_count=len(case_ids),
            cluster_basis="public case census",
        ),
        StudyCohort(
            cohort_id="cohort-b",
            benchmark_family_id="family",
            benchmark_version_id="version-b",
            forecast_release_id=forecast_release_id,
            forecast_release_digest=forecast_release_digest,
            labels_release_id=labels_release_id,
            labels_release_digest=labels_release_digest,
            manifest_sha256=manifest_sha256,
            case_ids=cohort_b_case_ids,
            expected_unit_count=len(cohort_b_case_ids),
            cluster_basis="public case census",
        ),
    )
    protocol = StudyProtocol(
        protocol_id="protocol",
        scoring_policy_id="policy",
    )
    suitability = Suitability(
        status="suitable_under_policy",
        policy_id="policy",
        basis="public fixture",
        binding=SuitabilityBinding(
            benchmark_family_id="family",
            benchmark_version_id="version-a",
            forecast_release_digest=forecast_release_digest,
            manifest_sha256=manifest_sha256,
            model_key=model_key,
            model_registry_sha256=model_registry_sha256,
            model_registry_entry_sha256=model_registry_entry_sha256,
            served_model_version=served_model_version,
            protocol_id=protocol.protocol_id,
            protocol_settings_digest=protocol.settings_digest,
            scoring_policy_id="policy",
        ),
    )
    suitability_b = Suitability(
        status="suitable_under_policy",
        policy_id="policy",
        basis="public fixture",
        binding=SuitabilityBinding(
            benchmark_family_id="family",
            benchmark_version_id="version-b",
            forecast_release_digest=forecast_release_digest,
            manifest_sha256=manifest_sha256,
            model_key="provider:model-b",
            model_registry_sha256=model_registry_sha256,
            model_registry_entry_sha256=model_registry_entry_sha256,
            served_model_version=served_model_version,
            protocol_id=protocol.protocol_id,
            protocol_settings_digest=protocol.settings_digest,
            scoring_policy_id="policy",
        ),
    )
    arms = (
        StudyArm(
            arm_id="arm-a",
            cohort_id="cohort-a",
            model_key=model_key,
            model_registry_sha256=model_registry_sha256,
            model_registry_entry_sha256=model_registry_entry_sha256,
            served_model_version=served_model_version,
            run_id="run-a",
            run_identity_sha256=_DIGEST,
            suitability=suitability,
        ),
        StudyArm(
            arm_id="arm-b",
            cohort_id="cohort-b",
            model_key="provider:model-b",
            model_registry_sha256=model_registry_sha256,
            model_registry_entry_sha256=model_registry_entry_sha256,
            served_model_version=served_model_version,
            run_id="run-b",
            run_identity_sha256=_DIGEST,
            suitability=suitability_b,
        ),
    )
    return StudySpec(
        study_id="study-cli",
        study_revision="1",
        mode="exploratory",
        protocol=protocol,
        cohorts=cohorts,
        arms=arms,
        planned_comparisons=(
            PlannedComparison(
                comparison_id="comparison",
                cohort_a_id="cohort-a",
                cohort_b_id="cohort-b",
                model_a_key=model_key,
                model_b_key="provider:model-b",
            ),
        ),
        multiplicity=Multiplicity(method="none"),
        replicates=2,
        seed=7,
    )


def _manifest() -> BenchmarkRunManifest:
    return BenchmarkRunManifest(
        run_id=UUID("12345678-1234-5678-1234-567812345678"),
        selected_cases=tuple(
            SelectedCase(
                case_id=f"case-{index:03d}",
                provider_id="corpus-store",
                qc_status=QCStatus.ACCEPTED,
                role_locators=tuple(
                    RoleObjectLocator(
                        role=role,
                        locator=OpaqueObjectLocator(
                            provider_id="object-store",
                            object_locator=f"cases/case-{index:03d}/{role.value}",
                            version_id=f"version-case-{index:03d}-{role.value}",
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
            for index in range(1, 4)
        ),
        policy_version="federal-mtd-v1",
        code_revision="a" * 40,
        created_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        locked_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
    )


def _sha256(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()
