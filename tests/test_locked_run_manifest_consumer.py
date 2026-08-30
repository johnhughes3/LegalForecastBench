from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from legalforecast.cli import main
from legalforecast.evals.output_parser import parse_model_output, public_parser_record
from legalforecast.release import (
    RUN_MANIFEST_SCHEMA_VERSION,
    BenchmarkRunManifest,
    DocumentRole,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    issue_synthetic_release,
    serialize_run_manifest,
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
    records = []
    for case_id, unit_id, probability in (
        ("case-001", "unit-001", 0.25),
        ("case-002", "unit-002", 0.75),
    ):
        parsed = parse_model_output(
            json.dumps(
                {
                    "case_assessment": "provider output",
                    "predictions": [
                        {
                            "unit_id": unit_id,
                            "probability_fully_dismissed": probability,
                        }
                    ],
                }
            ),
            required_unit_ids=(unit_id,),
        )
        records.append(
            {
                "case_id": case_id,
                "model_id": "fixture-model",
                "required_unit_ids": [unit_id],
                "parser_output": public_parser_record(parsed),
            }
        )
    runs_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    output_path = tmp_path / "scores.json"

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
                "--approval-reference",
                "owner-approved-fixture",
                "--dry-run",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["completed_cells"] == 3
    assert summary["run_identity_sha256"]
