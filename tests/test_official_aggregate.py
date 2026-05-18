from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.accounting import ModelRunAccountingRecord
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.publication.official_aggregate import (
    OfficialAggregationConfig,
    OfficialAggregationError,
    aggregate_official_results,
)
from legalforecast.publication.official_aggregate import (
    main as official_aggregate_main,
)
from legalforecast.reporting.cadence import CycleSeries


def test_official_aggregate_writes_public_bundle_and_private_debug(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    result = aggregate_official_results(
        OfficialAggregationConfig(
            per_case_dir=per_case_dir,
            run_input_manifest_path=manifest_path,
            labels_path=labels_path,
            output_dir=tmp_path / "official-bundle",
            cycle_id="cycle-1",
            cycle_series=CycleSeries.PILOT,
            clean_motion_count=25,
            prediction_unit_count=1,
            ablation="full_packet",
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    assert result.expected_case_count == 1
    assert result.aggregated_case_count == 1
    assert result.artifact_manifest_path.is_file()
    assert result.cycle_power_path.is_file()
    assert result.leaderboard_path.is_file()
    assert result.run_card_path.is_file()
    assert (result.private_debug_dir / "runs.jsonl").is_file()
    assert (result.private_debug_dir / "accounting.jsonl").is_file()

    cycle_power = json.loads(result.cycle_power_path.read_text(encoding="utf-8"))
    assert cycle_power["cycle_power"]["series"] == "pilot"
    assert cycle_power["cycle_power"]["clean_motion_count"] == 25
    assert cycle_power["cycle_power"]["prediction_unit_count"] == 1
    assert cycle_power["cycle_power"]["claim_strength"] == "feasibility_only"
    assert cycle_power["cycle_power"]["strong_ranking_claim_allowed"] is False

    leaderboard = json.loads(result.leaderboard_path.read_text(encoding="utf-8"))
    assert leaderboard["cycle_id"] == "cycle-1"
    assert leaderboard["cycle_power"]["claim_strength"] == "feasibility_only"
    assert leaderboard["cycle_power"]["strong_ranking_claim_allowed"] is False
    assert leaderboard["rows"][0]["model_id"] == "fixture-model"
    assert math.isclose(leaderboard["rows"][0]["micro_brier"], 0.025)
    assert math.isclose(leaderboard["rows"][0]["cost_per_case"], 0.02)

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["ablation_filter"] == "full_packet"
    assert run_card["expected_matrix_rows"] == 1
    assert run_card["cycle_power"]["claim_strength"] == "feasibility_only"
    assert run_card["cycle_power"]["strong_ranking_claim_allowed"] is False
    assert "runs.jsonl" in run_card["private_debug_outputs"]

    artifact_index = json.loads(
        (result.public_dir / "artifact-index.json").read_text(encoding="utf-8")
    )
    indexed_paths = {record["path"] for record in artifact_index["artifacts"]}
    assert {
        "cycle-power.json",
        "scores.json",
        "unit-scores.jsonl",
        "report/leaderboard.json",
        "run-cards/aggregate-run-card.json",
    } <= indexed_paths
    for record in artifact_index["artifacts"]:
        path = result.public_dir / record["path"]
        assert record["sha256"] == _file_sha256(path)

    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.public_dir.rglob("*")
        if path.is_file()
    )
    private_text = (result.private_debug_dir / "runs.jsonl").read_text(encoding="utf-8")
    assert "case_assessment" in private_text
    assert '"raw_output"' not in public_text
    assert "case_assessment" not in public_text
    assert "CASE_DEV_API_KEY" not in public_text


def test_official_aggregate_cli_writes_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    assert (
        official_aggregate_main(
            [
                "--per-case-dir",
                str(per_case_dir),
                "--run-input-manifest",
                str(manifest_path),
                "--labels",
                str(labels_path),
                "--output-dir",
                str(tmp_path / "official-bundle"),
                "--cycle-id",
                "cycle-1",
                "--cycle-series",
                "pilot",
                "--clean-motion-count",
                "25",
                "--prediction-unit-count",
                "1",
                "--ablation",
                "full_packet",
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    assert Path(summary["artifact_manifest"]).is_file()
    assert Path(summary["cycle_power"]).is_file()
    assert Path(summary["leaderboard"]).is_file()
    assert summary["expected_case_count"] == 1
    assert summary["aggregated_case_count"] == 1


def test_official_aggregate_fails_on_missing_case_output(tmp_path: Path) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    labels_path = _write_labels(tmp_path)

    with pytest.raises(OfficialAggregationError, match="missing per-case outputs"):
        aggregate_official_results(
            OfficialAggregationConfig(
                per_case_dir=tmp_path / "empty-artifacts",
                run_input_manifest_path=manifest_path,
                labels_path=labels_path,
                output_dir=tmp_path / "official-bundle",
                cycle_id="cycle-1",
                cycle_series=CycleSeries.PILOT,
                clean_motion_count=25,
                prediction_unit_count=1,
                ablation="full_packet",
            )
        )


def test_official_aggregate_fails_on_hash_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    case_dir = _write_case_artifacts(per_case_dir)
    runs = _read_jsonl(case_dir / "runs.jsonl")
    runs[0]["raw_output_sha256"] = "sha256:" + ("0" * 64)
    _write_jsonl(case_dir / "runs.jsonl", runs)

    with pytest.raises(OfficialAggregationError, match="raw_output_sha256 mismatch"):
        aggregate_official_results(
            OfficialAggregationConfig(
                per_case_dir=per_case_dir,
                run_input_manifest_path=manifest_path,
                labels_path=labels_path,
                output_dir=tmp_path / "official-bundle",
                cycle_id="cycle-1",
                cycle_series=CycleSeries.PILOT,
                clean_motion_count=25,
                prediction_unit_count=1,
                ablation="full_packet",
            )
        )


def _write_run_input_manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "run-inputs.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": "model-packets/cycle-1/case-1/full_packet.json",
                    "sha256": "a" * 64,
                }
            ],
        },
    )
    return manifest_path


def _write_labels(tmp_path: Path) -> Path:
    labels_path = tmp_path / "labels.jsonl"
    _write_jsonl(
        labels_path,
        [
            _label("unit-dismissed", True).to_record(),
            _label("unit-survives", False).to_record(),
        ],
    )
    return labels_path


def _write_case_artifacts(per_case_dir: Path) -> Path:
    case_dir = per_case_dir / "official-eval-case-1-full_packet"
    raw_output = json.dumps(
        {
            "case_assessment": "Fixture.",
            "predictions": [
                {
                    "unit_id": "unit-dismissed",
                    "probability_fully_dismissed": 0.9,
                },
                {
                    "unit_id": "unit-survives",
                    "probability_fully_dismissed": 0.2,
                },
            ],
        }
    )
    raw_output_sha256 = _text_sha256_prefixed(raw_output)
    run_record: dict[str, Any] = {
        "sample_id": "sample-1",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "related_family_id": None,
        "mdl_family_id": None,
        "solver_id": "fixture:solver",
        "solver_kind": "offline_fixture",
        "model_id": "fixture-model",
        "run_label": "full_packet",
        "ablation": "full_packet",
        "raw_output": raw_output,
        "raw_output_sha256": raw_output_sha256,
        "required_unit_ids": ["unit-dismissed", "unit-survives"],
        "request_count": 1,
        "input_tokens": 100,
        "output_tokens": 25,
        "estimated_total_tokens": 125,
        "estimated_cost": 0.02,
        "tool_call_logs": [],
        "metadata": {},
        "execution_backend": "local_fixture",
    }
    accounting = ModelRunAccountingRecord(
        sample_id="sample-1",
        candidate_id="candidate-1",
        case_id="case-1",
        solver_id="fixture:solver",
        solver_kind="offline_fixture",
        provider="fixture",
        model_id="fixture-model",
        model_version_or_snapshot="2026-05-17",
        evaluation_timestamp=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        raw_output_sha256=raw_output_sha256,
        prediction_unit_count=2,
        request_count=1,
        prompt_tokens=100,
        completion_tokens=25,
        total_tokens=125,
        tool_call_count=0,
        allowed_tool_call_count=0,
        denied_tool_call_count=0,
        latency_ms=250.0,
        estimated_cost=0.02,
        cost_per_case=0.02,
        cost_per_prediction_unit=0.01,
        invalid_output=False,
        refusal=False,
        content_filter=False,
        invalid_output_reason=None,
        run_label="full_packet",
        ablation="full_packet",
        execution_backend="local_fixture",
    )
    _write_jsonl(case_dir / "runs.jsonl", [run_record])
    _write_jsonl(case_dir / "accounting.jsonl", [accounting.to_record()])
    _write_json(
        case_dir / "metrics.json",
        {
            "schema_version": "legalforecast.per_case_metrics.v1",
            "run_id": "cycle-1-case-1-full_packet-fixture",
            "cycle_id": "cycle-1",
            "case_id": "case-1",
            "ablation": "full_packet",
            "solver_id": "fixture:solver",
            "evaluation_timestamp": "2026-05-17T12:00:00Z",
            "packet_object_key": "model-packets/cycle-1/case-1/full_packet.json",
            "packet_sha256": "a" * 64,
            "run_record_count": 1,
            "raw_output_sha256": [raw_output_sha256],
            "tool_call_count": 0,
        },
    )
    return case_dir


def _label(unit_id: str, dismissed: bool) -> OutcomeLabel:
    return OutcomeLabel(
        unit_id=unit_id,
        fully_dismissed=dismissed,
        amendment_class=(
            AmendmentClass.DISMISSED_WITHOUT_EXPRESS_AMENDMENT_OPPORTUNITY
            if dismissed
            else AmendmentClass.NOT_FULLY_DISMISSED
        ),
        ambiguous=False,
        label_confidence=0.98,
        supporting_citations=(OutcomeCitation(document_id="decision-1", page=1),),
        first_written_disposition_id="decision-1",
        first_written_disposition_date="2026-05-17",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _text_sha256_prefixed(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
