from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from legalforecast.cli import main
from legalforecast.contracts import ARTIFACT_RAW_SHA256_V1, PUBLIC_RUN_RECEIPT_V1
from legalforecast.evals.output_parser import parse_model_output, public_parser_record
from legalforecast.evals.run_record_scoring import (
    score_run_records_against_labels_release,
)
from legalforecast.release import (
    RUN_MANIFEST_SCHEMA_VERSION,
    BenchmarkRunManifest,
    DocumentRole,
    IssuedRelease,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    enumerate_forecast_worker_inputs,
    issue_synthetic_release,
    serialize_run_manifest,
    validate_manifest_against_forecast,
    validate_run_manifest_structure,
)


def _manifest(*case_ids: str) -> BenchmarkRunManifest:
    selected_cases = tuple(
        {
            "case_id": case_id,
            "provider_id": "corpus-store",
            "qc_status": QCStatus.ACCEPTED,
            "role_locators": tuple(
                RoleObjectLocator(
                    role=role,
                    locator=OpaqueObjectLocator(
                        provider_id="object-store",
                        object_locator=f"cases/{case_id}/{role.value}",
                        version_id=f"version-{case_id}-{role.value}",
                    ),
                )
                for role in (
                    DocumentRole.DECISION,
                    DocumentRole.MOTION,
                    DocumentRole.COMPLAINT,
                )
            ),
            "opposition_status": OppositionStatus.CONFIRMED_UNOPPOSED,
        }
        for case_id in case_ids
    )
    return BenchmarkRunManifest(
        run_id=UUID("12345678-1234-5678-1234-567812345678"),
        selected_cases=selected_cases,
        policy_version="federal-mtd-v1",
        code_revision="a" * 40,
        created_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        locked_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
    )


def test_manifest_validate_cli_consumes_canonical_locked_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_bytes(serialize_run_manifest(_manifest("case-001")))

    assert main(["manifest", "validate", "--manifest", str(manifest_path)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["manifest_schema_version"] == RUN_MANIFEST_SCHEMA_VERSION
    assert result["selected_case_count"] == 1
    assert result["valid"] is True
    assert result["manifest_sha256"]


def test_manifest_validate_accepts_structural_json_and_canonicalizes_identity(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "run-manifest.json"
    canonical = serialize_run_manifest(_manifest("case-001"))
    manifest_path.write_bytes(canonical + b"\n")

    assert main(["manifest", "validate", "--manifest", str(manifest_path)]) == 0


def test_supported_help_exposes_manifest_and_release_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["manifest", "validate", "--help"])
    manifest_help = capsys.readouterr().out
    assert "--manifest" in manifest_help
    assert "--forecast" in manifest_help
    assert "--labels" in manifest_help

    with pytest.raises(SystemExit, match="0"):
        main(["score", "--help"])
    score_help = capsys.readouterr().out
    assert "--labels-release" in score_help
    assert "--forecast-release" in score_help
    assert "--manifest" in score_help


def test_score_cli_consumes_labels_release_without_label_records(
    tmp_path: Path,
) -> None:
    release_dir = tmp_path / "release"
    issued = issue_synthetic_release(release_dir)
    runs_path = tmp_path / "runs.jsonl"
    records = _strict_receipts(issued)
    runs_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    output_path = tmp_path / "scores.json"
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_bytes(
        serialize_run_manifest(_manifest("case-001", "case-002", "case-003"))
    )

    assert (
        main(
            [
                "score",
                "--runs",
                str(runs_path),
                "--labels-release",
                str(release_dir / "labels-release.json"),
                "--forecast-release",
                str(release_dir / "forecast-release.json"),
                "--artifact-root",
                str(release_dir),
                "--manifest",
                str(manifest_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    score = json.loads(output_path.read_text(encoding="utf-8"))
    assert score["summaries"][0]["unit_count"] == 2
    assert score["summaries"][0]["model_id"] == "fixture-model"
    assert issued.labels.unit_count == 2


def test_run_cli_consumes_manifest_without_opening_labels(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = tmp_path / "fixture"
    assert main(["run", "issue-fixture", "--output-dir", str(fixture)]) == 0
    capsys.readouterr()
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_bytes(
        serialize_run_manifest(_manifest("case-001", "case-002", "case-003"))
    )
    (fixture / "release" / "labels-release.json").unlink()

    assert (
        main(
            [
                "run",
                "execute",
                "--manifest",
                str(manifest_path),
                "--forecast",
                str(fixture / "release" / "forecast-release.json"),
                "--artifact-root",
                str(fixture / "release"),
                "--model-registry",
                str(fixture / "model-registry.json"),
                "--model-key",
                "openai:legalforecast-fixture",
                "--ledger",
                str(tmp_path / "ledger.sqlite3"),
                "--receipts-dir",
                str(tmp_path / "receipts"),
                "--ceiling-microusd",
                "30000",
                "--dry-run",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["completed_cells"] == 3
    assert summary["run_identity_sha256"]
    with sqlite3.connect(tmp_path / "ledger.sqlite3") as connection:
        identity_json = connection.execute(
            "SELECT identity_json FROM public_runner_run"
        ).fetchone()[0]
    assert "approval_reference" not in json.loads(identity_json)


@pytest.mark.parametrize("mutation", ("run", "code", "provider", "version"))
def test_manifest_binding_rejects_identity_drift(
    mutation: str,
    tmp_path: Path,
) -> None:
    issued = issue_synthetic_release(tmp_path / "release")
    manifest = _manifest("case-001", "case-002", "case-003")
    manifest_payload = manifest.model_dump(mode="json")
    if mutation == "run":
        manifest_payload["run_id"] = "22345678-1234-5678-1234-567812345678"
    elif mutation == "code":
        manifest_payload["code_revision"] = "b" * 40
    else:
        selected = manifest_payload["selected_cases"][0]
        if mutation == "provider":
            selected["provider_id"] = "other-store"
        else:
            selected["role_locators"][0]["locator"]["version_id"] = "other-version"
    changed = validate_run_manifest_structure(json.dumps(manifest_payload))
    with pytest.raises(ValueError, match="manifest"):
        validate_manifest_against_forecast(changed, issued.forecast)


def test_manifest_binding_rejects_forecast_release_identity_drift(
    tmp_path: Path,
) -> None:
    issued = issue_synthetic_release(tmp_path / "release")
    changed_forecast = issued.forecast.model_copy(
        update={"release_id": "different-release"}
    )
    with pytest.raises(ValueError, match="identity"):
        validate_manifest_against_forecast(
            _manifest("case-001", "case-002", "case-003"),
            changed_forecast,
        )


def _strict_receipts(issued: IssuedRelease) -> list[dict[str, object]]:
    release = issued.forecast
    records: list[dict[str, object]] = []
    for unit in release.prediction_units:
        run_identity = "c" * 64
        cell_id = str(
            ARTIFACT_RAW_SHA256_V1.commit(
                {
                    "case_id": unit.case_id,
                    "repeat_index": 1,
                    "run_identity_sha256": run_identity,
                    "unit_id": unit.unit_id,
                },
                domain=PUBLIC_RUN_RECEIPT_V1,
            ).digest
        )
        parsed = parse_model_output(
            json.dumps(
                {
                    "case_assessment": "provider output",
                    "predictions": [
                        {
                            "unit_id": unit.unit_id,
                            "probability_fully_dismissed": 0.5,
                        }
                    ],
                }
            ),
            required_unit_ids=(unit.unit_id,),
        )
        records.append(
            {
                "release_id": release.release_id,
                "forecast_release_digest": release.release_digest,
                "run_identity_sha256": run_identity,
                "schema_version": str(PUBLIC_RUN_RECEIPT_V1),
                "cell_id": cell_id,
                "case_id": unit.case_id,
                "unit_id": unit.unit_id,
                "required_unit_ids": [unit.unit_id],
                "model_key": "fixture-model",
                "model_id": "fixture-model",
                "harness": "native",
                "ablation": "none",
                "repeat_index": 1,
                "model_registry_sha256": "d" * 64,
                "model_registry_entry_sha256": "e" * 64,
                "prompt_sha256": unit.prompt_sha256,
                "request_body_sha256": "f" * 64,
                "served_model_version": "fixture-model-v1",
                "parser_output": public_parser_record(parsed),
            }
        )
    return records


def test_locked_scoring_rejects_partial_wrong_extra_and_mixed_receipts(
    tmp_path: Path,
) -> None:
    issued = issue_synthetic_release(tmp_path / "release")
    manifest = _manifest("case-001", "case-002", "case-003")
    records = _strict_receipts(issued)
    kwargs = {
        "base_rate": None,
        "forecast_release": issued.forecast,
        "manifest": manifest,
    }
    with pytest.raises(ValueError, match="incomplete"):
        score_run_records_against_labels_release(records[:2], issued.labels, **kwargs)
    wrong_case = [*records]
    wrong_case[0] = {**wrong_case[0], "case_id": "case-002"}
    with pytest.raises(ValueError, match="case_id"):
        score_run_records_against_labels_release(wrong_case, issued.labels, **kwargs)
    extra = {
        **records[0],
        "unit_id": "unit-extra",
        "required_unit_ids": ["unit-extra"],
        "case_id": "case-001",
        "parser_output": public_parser_record(
            parse_model_output(
                json.dumps(
                    {
                        "case_assessment": "provider output",
                        "predictions": [
                            {
                                "unit_id": "unit-extra",
                                "probability_fully_dismissed": 0.5,
                            }
                        ],
                    }
                ),
                required_unit_ids=("unit-extra",),
            )
        ),
    }
    with pytest.raises(ValueError, match="outside forecast"):
        score_run_records_against_labels_release(
            [*records, extra], issued.labels, **kwargs
        )
    mixed = [*records]
    mixed[0] = {**mixed[0], "release_id": "different-release"}
    with pytest.raises(ValueError, match="release_id"):
        score_run_records_against_labels_release(mixed, issued.labels, **kwargs)


def test_locked_scoring_preserves_case_level_multi_unit_semantics(
    tmp_path: Path,
) -> None:
    issued = issue_synthetic_release(tmp_path / "release")
    release = issued.forecast
    first_unit = release.prediction_units[0]
    second_unit = release.prediction_units[1]
    first_case = release.cases[0]
    expanded_unit = second_unit.model_copy(update={"case_id": first_case.case_id})
    expanded_release = release.model_copy(
        update={
            "prediction_units": (
                first_unit,
                expanded_unit,
                release.prediction_units[2],
            )
        }
    )
    records = _strict_receipts(issued)
    second = {**records[1], "case_id": first_case.case_id}
    second["cell_id"] = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "case_id": first_case.case_id,
                "repeat_index": 1,
                "run_identity_sha256": second["run_identity_sha256"],
                "unit_id": second["unit_id"],
            },
            domain=PUBLIC_RUN_RECEIPT_V1,
        ).digest
    )
    records[1] = second
    manifest = _manifest("case-001", "case-002", "case-003")
    summaries = score_run_records_against_labels_release(
        records,
        issued.labels,
        base_rate=None,
        forecast_release=expanded_release,
        manifest=manifest,
    )
    assert len(summaries) == 1
    assert summaries[0].case_count == 1
    assert summaries[0].unit_count == 2


def test_worker_allowlist_is_release_declared_and_outcome_blind(
    tmp_path: Path,
) -> None:
    issued = issue_synthetic_release(tmp_path / "release")
    worker_inputs = enumerate_forecast_worker_inputs(issued.forecast)
    assert worker_inputs
    assert {item.kind for item in worker_inputs} == {"document", "packet", "prompt"}
    assert all(
        "label" not in item.relative_path.lower()
        and "outcome" not in item.relative_path.lower()
        for item in worker_inputs
    )
    paths = tuple(item.relative_path for item in worker_inputs)
    assert enumerate_forecast_worker_inputs(issued.forecast, requested_paths=paths)
    with pytest.raises(ValueError, match="exactly release-declared"):
        enumerate_forecast_worker_inputs(
            issued.forecast,
            requested_paths=(*paths, "labels-release.json"),
        )
    with pytest.raises(ValueError, match="safe relative"):
        enumerate_forecast_worker_inputs(
            issued.forecast,
            requested_paths=(*paths[:-1], "../labels-release.json"),
        )


def test_report_rejects_score_identity_mismatch(tmp_path: Path) -> None:
    release_dir = tmp_path / "release"
    issued = issue_synthetic_release(release_dir)
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_bytes(
        serialize_run_manifest(_manifest("case-001", "case-002", "case-003"))
    )
    runs_path = tmp_path / "runs.jsonl"
    runs_path.write_text(
        "".join(json.dumps(record) + "\n" for record in _strict_receipts(issued)),
        encoding="utf-8",
    )
    scores_path = tmp_path / "scores.json"
    assert (
        main(
            [
                "score",
                "--runs",
                str(runs_path),
                "--labels-release",
                str(release_dir / "labels-release.json"),
                "--forecast-release",
                str(release_dir / "forecast-release.json"),
                "--artifact-root",
                str(release_dir),
                "--manifest",
                str(manifest_path),
                "--output",
                str(scores_path),
            ]
        )
        == 0
    )
    score_payload = json.loads(scores_path.read_text(encoding="utf-8"))
    score_payload["identity"]["forecast_release_id"] = "different-release"
    scores_path.write_text(json.dumps(score_payload), encoding="utf-8")
    assert (
        main(
            [
                "report",
                "--scores",
                str(scores_path),
                "--output-dir",
                str(tmp_path / "report"),
                "--manifest",
                str(manifest_path),
                "--forecast-release",
                str(release_dir / "forecast-release.json"),
                "--labels-release",
                str(release_dir / "labels-release.json"),
                "--artifact-root",
                str(release_dir),
            ]
        )
        == 2
    )
