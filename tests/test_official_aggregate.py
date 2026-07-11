from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.accounting import ModelRunAccountingRecord
from legalforecast.evals.bootstrap import BONFERRONI_RANK_TIER_METHOD
from legalforecast.evals.response_verification import (
    RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD,
    RESPONSE_RETRYABLE_OPS_EVENT_FIELD,
    RESPONSE_VERIFICATION_SCHEMA_FIELD,
    RESPONSE_VERIFICATION_SCHEMA_VERSION,
)
from legalforecast.labeling import AmendmentClass, OutcomeCitation, OutcomeLabel
from legalforecast.publication.official_aggregate import (
    OfficialAggregationConfig,
    OfficialAggregationError,
    _ablation_delta_report,
    _score_row_type,
    aggregate_official_results,
)
from legalforecast.publication.official_aggregate import (
    main as official_aggregate_main,
)
from legalforecast.reporting.cadence import CycleSeries


def test_score_row_type_preserves_baseline_with_ablation_suffix() -> None:
    assert _score_row_type("judge_history::full_packet") == "baseline"
    assert _score_row_type("fixture-model::full_packet") == "model"


def test_official_aggregate_writes_public_bundle_and_private_debug(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
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
            model_registry_path=registry_path,
            allow_no_baselines=True,
            ablation="full_packet",
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    assert result.expected_case_count == 1
    assert result.aggregated_case_count == 1
    assert result.expected_matrix_row_count == 1
    assert result.aggregated_matrix_row_count == 1
    assert result.model_count == 1
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
    mde = cycle_power["cycle_power"]["mde_analysis"]
    assert mde["paired_delta_sd_source"] == "default_fallback"
    assert math.isclose(mde["paired_delta_sd"], 0.05)
    assert any(
        "paired_delta_sd fell back to the default 0.05" in warning
        for warning in cycle_power["cycle_power"]["warnings"]
    )

    leaderboard = json.loads(result.leaderboard_path.read_text(encoding="utf-8"))
    assert leaderboard["cycle_id"] == "cycle-1"
    assert leaderboard["cycle_power"]["claim_strength"] == "feasibility_only"
    assert leaderboard["cycle_power"]["strong_ranking_claim_allowed"] is False
    assert leaderboard["rows"][0]["model_id"] == "fixture-model"
    assert math.isclose(leaderboard["rows"][0]["micro_brier"], 0.025)
    assert math.isclose(leaderboard["rows"][0]["cost_per_case"], 0.02)

    scores = json.loads((result.public_dir / "scores.json").read_text(encoding="utf-8"))
    score_summary = scores["summaries"][0]
    assert score_summary["model_id"] == "fixture-model"
    assert math.isclose(score_summary["total_estimated_cost"], 0.02)
    assert math.isclose(score_summary["cost_per_case"], 0.02)
    assert math.isclose(score_summary["cost_per_prediction_unit"], 0.01)
    assert score_summary["prompt_tokens"] == 100
    assert score_summary["completion_tokens"] == 25
    assert score_summary["total_tokens"] == 125
    assert score_summary["allowed_tool_call_count"] == 0
    assert score_summary["denied_tool_call_count"] == 0

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["ablation_filter"] == "full_packet"
    assert run_card["expected_matrix_rows"] == 1
    assert run_card["model_keys"] == []
    assert run_card["registry_model_keys"] == ["fixture:solver"]
    assert run_card["expected_model_keys"] == ["fixture:solver"]
    assert run_card["allow_incomplete_model_set"] is False
    assert run_card["allow_no_baselines"] is True
    assert run_card["labels_sha256"] == _labels_sha256(_default_label_records())
    packet_budget = run_card["packet_token_budget"]
    assert packet_budget["overall"]["max"] == 1_024
    assert packet_budget["by_ablation"]["full_packet"]["count"] == 1
    assert packet_budget["smallest_context_limit"] == 200_000
    assert packet_budget["smallest_prompt_input_token_budget"] == 195_904
    assert packet_budget["registry_budgets"] == [
        {
            "context_limit": 200_000,
            "max_output_tokens": 4_096,
            "model_key": "fixture:solver",
            "prompt_input_token_budget": 195_904,
            "temperature": 0.0,
        }
    ]
    assert packet_budget["temperature_policy"]["all_registry_temperatures_zero"] is True
    assert (
        "reduce avoidable sampling variance"
        in packet_budget["temperature_policy"]["rationale"]
    )
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
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
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
                "--model-registry",
                str(registry_path),
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
                "--paired-delta-sd",
                "0.08",
                "--target-mde",
                "0.02",
                "--allow-no-baselines",
                "--ablation",
                "full_packet",
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    assert Path(summary["artifact_manifest"]).is_file()
    cycle_power_path = Path(summary["cycle_power"])
    assert cycle_power_path.is_file()
    assert Path(summary["leaderboard"]).is_file()
    assert summary["expected_case_count"] == 1
    assert summary["aggregated_case_count"] == 1
    assert summary["expected_matrix_row_count"] == 1
    assert summary["aggregated_matrix_row_count"] == 1
    cycle_power = json.loads(cycle_power_path.read_text(encoding="utf-8"))
    mde = cycle_power["cycle_power"]["mde_analysis"]
    assert math.isclose(mde["paired_delta_sd"], 0.08)
    assert math.isclose(mde["target_mde"], 0.02)
    assert mde["paired_delta_sd_source"] == "explicit_config"
    assert mde["target_mde_source"] == "explicit_config"
    assert mde["target_power_source"] == "explicit_config"
    assert mde["two_sided_alpha_source"] == "explicit_config"
    assert summary["model_count"] == 1
    assert not any(
        "paired_delta_sd fell back" in warning
        for warning in cycle_power["cycle_power"]["warnings"]
    )


def test_official_aggregate_scores_historical_baselines_as_pseudo_models(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path, include_baseline_features=True)
    baseline_training_path = _write_baseline_training_examples(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
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
            prediction_unit_count=2,
            model_registry_path=registry_path,
            baseline_training_examples_path=baseline_training_path,
            ablation="full_packet",
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    scores = json.loads((result.public_dir / "scores.json").read_text(encoding="utf-8"))
    rows_by_model = {row["model_id"]: row for row in scores["summaries"]}

    assert {
        "fixture-model",
        "global_base_rate",
        "court_nos_motion_base_rate",
        "metadata_only",
        "judge_history",
    } <= set(rows_by_model)
    assert (
        rows_by_model["fixture-model"]["brier_skill_score_reference_model_id"]
        == "judge_history"
    )
    assert rows_by_model["fixture-model"]["brier_skill_score_over_reference"] > 0
    assert rows_by_model["judge_history"]["cost_per_case"] == 0
    assert (result.private_debug_dir / "baseline-predictions.jsonl").is_file()
    cycle_training_rows = _read_jsonl(
        result.public_dir / "baseline-training-examples.jsonl"
    )
    assert [row["features"]["unit_id"] for row in cycle_training_rows] == [
        "unit-dismissed",
        "unit-survives",
    ]
    assert [row["fully_dismissed"] for row in cycle_training_rows] == [True, False]
    assert {row["decision_date"] for row in cycle_training_rows} == {"2026-05-17"}

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["baseline_model_ids"] == [
        "global_base_rate",
        "court_nos_motion_base_rate",
        "metadata_only",
        "judge_history",
    ]
    assert run_card["brier_skill_score_reference_model_id"] == "judge_history"
    assert run_card["cycle_baseline_training_example_count"] == 2
    assert "baseline-training-examples.jsonl" in run_card["public_outputs"]
    assert run_card["first_cycle_ablation_plan"] == {
        "required_ablations": ["full_packet", "metadata_only"],
        "deferred_ablations": ["judge_removed"],
        "defer_reason": (
            "judge_removed roughly doubles full-document model cost and is "
            "deferred until budget sign-off; metadata_only remains the "
            "required low-cost run-1 ablation."
        ),
    }
    assert run_card["baseline_training_period"] == {
        "training_period_start": "2024-01-01",
        "training_period_end": "2024-01-30",
        "judge_history_usage": run_card["baseline_training_period"][
            "judge_history_usage"
        ],
    }


def test_official_aggregate_deduplicates_cycle_baseline_training_examples(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(
        tmp_path,
        include_baseline_features=True,
        ablations=("full_packet", "metadata_only"),
    )
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    baseline_training_path = _write_baseline_training_examples(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet",
        ablation="full_packet",
        dismissed_probability=0.9,
    )
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-metadata_only",
        ablation="metadata_only",
        dismissed_probability=0.6,
    )

    result = aggregate_official_results(
        OfficialAggregationConfig(
            per_case_dir=per_case_dir,
            run_input_manifest_path=manifest_path,
            labels_path=labels_path,
            output_dir=tmp_path / "official-bundle",
            cycle_id="cycle-1",
            cycle_series=CycleSeries.PILOT,
            clean_motion_count=25,
            prediction_unit_count=2,
            model_registry_path=registry_path,
            baseline_training_examples_path=baseline_training_path,
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    cycle_training_rows = _read_jsonl(
        result.public_dir / "baseline-training-examples.jsonl"
    )
    assert [row["features"]["unit_id"] for row in cycle_training_rows] == [
        "unit-dismissed",
        "unit-survives",
    ]
    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["cycle_baseline_training_example_count"] == 2


def test_official_aggregate_fails_without_baselines_by_default(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(
        OfficialAggregationError,
        match="baseline_training_examples_path is required",
    ):
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
                model_registry_path=registry_path,
                ablation="full_packet",
            )
        )


def test_ablation_delta_report_compares_full_packet_to_metadata_only() -> None:
    full_packet = {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "model_id": "fixture-model",
        "run_label": "full_packet",
        "ablation": "full_packet",
        "raw_output": _fixture_raw_output(0.9),
        "required_unit_ids": ["unit-dismissed", "unit-survives"],
    }
    metadata_only = {
        **full_packet,
        "run_label": "metadata_only",
        "ablation": "metadata_only",
        "raw_output": _fixture_raw_output(0.6),
    }

    report = _ablation_delta_report(
        [full_packet, metadata_only],
        (_label("unit-dismissed", True), _label("unit-survives", False)),
        cycle_id="cycle-1",
        generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        base_rate=None,
    )

    assert report["comparison"] == "full_packet_minus_metadata_only_micro_brier"
    [row] = report["rows"]
    assert row["model_id"] == "fixture-model"
    assert math.isclose(row["full_packet_micro_brier"], 0.025)
    assert math.isclose(row["metadata_only_micro_brier"], 0.1)
    assert math.isclose(row["full_packet_minus_metadata_only_micro_brier"], -0.075)
    assert row["record_text_improves_brier"] is True


def test_ablation_delta_report_counts_exact_ties_as_half_probability() -> None:
    full_packet = {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "model_id": "fixture-model",
        "run_label": "full_packet",
        "ablation": "full_packet",
        "raw_output": _fixture_raw_output(0.7),
        "required_unit_ids": ["unit-dismissed", "unit-survives"],
    }
    metadata_only = {
        **full_packet,
        "run_label": "metadata_only",
        "ablation": "metadata_only",
    }

    report = _ablation_delta_report(
        [full_packet, metadata_only],
        (_label("unit-dismissed", True), _label("unit-survives", False)),
        cycle_id="cycle-1",
        generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        base_rate=None,
    )

    assert report["rows"][0]["probability_full_packet_better"] == 0.5


def test_official_aggregate_writes_multi_ablation_scores_and_delta_report(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(
        tmp_path,
        ablations=("full_packet", "metadata_only"),
    )
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet",
        ablation="full_packet",
        dismissed_probability=0.9,
    )
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-metadata_only",
        ablation="metadata_only",
        dismissed_probability=0.6,
    )

    result = aggregate_official_results(
        OfficialAggregationConfig(
            per_case_dir=per_case_dir,
            run_input_manifest_path=manifest_path,
            labels_path=labels_path,
            output_dir=tmp_path / "official-bundle",
            cycle_id="cycle-1",
            cycle_series=CycleSeries.PILOT,
            clean_motion_count=25,
            prediction_unit_count=2,
            model_registry_path=registry_path,
            allow_no_baselines=True,
            deferred_ablations=("judge_removed",),
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    scores = json.loads((result.public_dir / "scores.json").read_text(encoding="utf-8"))
    assert {row["model_id"] for row in scores["summaries"]} == {
        "fixture-model::full_packet",
        "fixture-model::metadata_only",
    }
    delta_report = json.loads(
        (result.public_dir / "ablation-deltas.json").read_text(encoding="utf-8")
    )
    assert delta_report["confidence_interval_method"] == "paired_clustered_bootstrap"
    [delta_row] = delta_report["rows"]
    assert delta_row["model_id"] == "fixture-model"
    assert math.isclose(
        delta_row["full_packet_minus_metadata_only_micro_brier"],
        -0.075,
    )
    assert "full_packet_minus_metadata_only_ci_low" in delta_row
    assert "full_packet_minus_metadata_only_ci_high" in delta_row
    assert "probability_full_packet_better" in delta_row

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["ablation_delta_count"] == 1
    assert run_card["deferred_ablations"] == ["judge_removed"]
    assert "ablation-deltas.json" in run_card["public_outputs"]


def test_official_aggregate_accepts_explicit_multi_model_matrix(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(
        tmp_path,
        ("fixture:model-a", "fixture:model-b"),
    )
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet-model-a",
        solver_id="fixture:model-a",
        model_id="model-a",
        dismissed_probability=0.9,
        estimated_cost=0.02,
    )
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet-model-b",
        solver_id="fixture:model-b",
        model_id="model-b",
        dismissed_probability=0.6,
        estimated_cost=0.04,
    )

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
            model_registry_path=registry_path,
            model_keys=("fixture:model-a", "fixture:model-b"),
            allow_no_baselines=True,
            ablation="full_packet",
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    assert result.expected_case_count == 1
    assert result.aggregated_case_count == 1
    assert result.expected_matrix_row_count == 2
    assert result.aggregated_matrix_row_count == 2
    assert result.model_count == 2

    leaderboard = json.loads(result.leaderboard_path.read_text(encoding="utf-8"))
    assert leaderboard["rank_tier_method"] == BONFERRONI_RANK_TIER_METHOD
    assert leaderboard["pairwise_deltas"]
    rows_by_model = {row["model_id"]: row for row in leaderboard["rows"]}
    assert set(rows_by_model) == {"model-a", "model-b"}
    assert rows_by_model["model-a"]["rank_tier"] is None
    assert rows_by_model["model-b"]["rank_tier"] is None
    assert leaderboard["small_cluster_warning"] is not None
    assert rows_by_model["model-b"]["delta_vs_best"] > 0
    assert rows_by_model["model-b"]["delta_vs_best_ci_low"] > 0
    assert math.isclose(rows_by_model["model-a"]["cost_per_case"], 0.02)
    assert math.isclose(rows_by_model["model-b"]["cost_per_case"], 0.04)

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["expected_matrix_rows"] == 2
    assert run_card["model_keys"] == ["fixture:model-a", "fixture:model-b"]
    assert run_card["registry_model_keys"] == ["fixture:model-a", "fixture:model-b"]
    assert run_card["expected_model_keys"] == ["fixture:model-a", "fixture:model-b"]


def test_official_aggregate_refuses_when_labels_hash_drifts(
    tmp_path: Path,
) -> None:
    # The run-input manifest froze a labels sha256 that does not match the labels
    # file handed to aggregation: labels were not locked before scoring, so
    # aggregation must fail closed instead of scoring a swapped label set.
    manifest_path = _write_run_input_manifest(
        tmp_path,
        labels_sha256="0" * 64,
    )
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(OfficialAggregationError, match="labels hash drift"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_refuses_when_labels_hash_missing(
    tmp_path: Path,
) -> None:
    # A manifest that never froze a labels hash cannot prove labels-before-scoring
    # ordering; aggregation refuses rather than trusting operator discipline.
    manifest_path = _write_run_input_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["labels_sha256"]
    _write_json(manifest_path, manifest)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(OfficialAggregationError, match="missing labels_sha256"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_rejects_strict_subset_explicit_model_set(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(
        tmp_path,
        ("fixture:model-a", "fixture:model-b"),
    )
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet-model-a",
        solver_id="fixture:model-a",
        model_id="model-a",
    )

    with pytest.raises(OfficialAggregationError, match="incomplete model set"):
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
                model_registry_path=registry_path,
                model_keys=("fixture:model-a",),
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_allows_explicit_partial_debug_bundle(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(
        tmp_path,
        ("fixture:model-a", "fixture:model-b"),
    )
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet-model-a",
        solver_id="fixture:model-a",
        model_id="model-a",
    )

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
            model_registry_path=registry_path,
            model_keys=("fixture:model-a",),
            allow_incomplete_model_set=True,
            allow_no_baselines=True,
            ablation="full_packet",
        )
    )

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert run_card["allow_incomplete_model_set"] is True
    assert run_card["registry_model_keys"] == ["fixture:model-a", "fixture:model-b"]
    assert run_card["expected_model_keys"] == ["fixture:model-a"]


def test_official_aggregate_requires_expected_model_set_by_default(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(OfficialAggregationError, match="expected model set"):
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
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_uses_registry_as_expected_model_set(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(
        tmp_path,
        ("fixture:model-a", "fixture:model-b"),
    )
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(
        per_case_dir,
        case_dir_name="official-eval-case-1-full_packet-model-a",
        solver_id="fixture:model-a",
        model_id="model-a",
    )

    with pytest.raises(OfficialAggregationError, match="fixture:model-b"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_rejects_packet_over_smallest_context_budget(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path, packet_size_bytes=800_000)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(OfficialAggregationError, match="packet token budget exceeded"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_reports_repeat_sampling_variance(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_repeated_case_artifacts(per_case_dir, probabilities=(0.9, 0.7, 0.6))

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
            model_registry_path=registry_path,
            allow_no_baselines=True,
            ablation="full_packet",
            generated_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        )
    )

    variance = json.loads(
        (result.public_dir / "variance" / "repeat-sampling.json").read_text(
            encoding="utf-8"
        )
    )
    assert variance["repeat_sampling_present"] is True
    assert variance["rows"][0]["repeat_count"] == 3
    assert variance["rows"][0]["repeat_indices"] == [1, 2, 3]
    assert variance["rows"][0]["sample_variance_micro_brier"] > 0
    summary = variance["summary_by_model"][0]
    assert summary["model_id"] == "fixture-model"
    assert summary["repeated_case_count"] == 1
    assert summary["repeat_run_count"] == 3
    cycle_power = json.loads(result.cycle_power_path.read_text(encoding="utf-8"))
    cycle_power_mde = cycle_power["cycle_power"]["mde_analysis"]
    assert cycle_power_mde["paired_delta_sd_source"] == "repeat_variance_report"
    assert math.isclose(
        cycle_power_mde["paired_delta_sd"],
        summary["root_mean_within_case_variance"],
    )

    scores = json.loads((result.public_dir / "scores.json").read_text(encoding="utf-8"))
    score_summary = scores["summaries"][0]
    assert score_summary["case_count"] == 1
    assert math.isclose(score_summary["micro_brier"], 0.025)

    leaderboard = json.loads(result.leaderboard_path.read_text(encoding="utf-8"))
    row = leaderboard["rows"][0]
    assert row["repeat_sample_case_count"] == 1
    assert row["repeat_sample_run_count"] == 3
    assert math.isclose(
        row["within_model_micro_brier_stddev"],
        summary["root_mean_within_case_variance"],
    )

    run_card = json.loads(result.run_card_path.read_text(encoding="utf-8"))
    assert "variance/repeat-sampling.json" in run_card["public_outputs"]
    assert run_card["repeat_variance_summary"] == [summary]
    assert len(_read_jsonl(result.private_debug_dir / "runs.jsonl")) == 3


def test_official_aggregate_fails_on_missing_case_output(tmp_path: Path) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_fails_on_hash_mismatch(tmp_path: Path) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


@pytest.mark.parametrize(
    ("metadata_field", "error_match"),
    (
        (RESPONSE_GROUNDING_ARTIFACTS_DETECTED_FIELD, "grounding artifacts"),
        (RESPONSE_RETRYABLE_OPS_EVENT_FIELD, "retryable response ops"),
    ),
)
def test_official_aggregate_fails_on_response_verification_flags(
    tmp_path: Path,
    metadata_field: str,
    error_match: str,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    case_dir = _write_case_artifacts(per_case_dir)
    runs = _read_jsonl(case_dir / "runs.jsonl")
    runs[0]["metadata"] = {
        RESPONSE_VERIFICATION_SCHEMA_FIELD: RESPONSE_VERIFICATION_SCHEMA_VERSION,
        metadata_field: "true",
    }
    _write_jsonl(case_dir / "runs.jsonl", runs)

    with pytest.raises(OfficialAggregationError, match=error_match):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_requires_response_verification_for_live_runs(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    case_dir = _write_case_artifacts(per_case_dir)
    runs = _read_jsonl(case_dir / "runs.jsonl")
    runs[0]["execution_backend"] = "inspect_ai"
    _write_jsonl(case_dir / "runs.jsonl", runs)

    with pytest.raises(OfficialAggregationError, match="metadata missing or invalid"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_fails_on_retryable_accounting_event(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(tmp_path)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    case_dir = _write_case_artifacts(per_case_dir)
    accounting = _read_jsonl(case_dir / "accounting.jsonl")
    accounting[0]["retryable_ops_event"] = True
    accounting[0]["retryable_ops_event_reason"] = "response_truncated:max_tokens"
    _write_jsonl(case_dir / "accounting.jsonl", accounting)

    with pytest.raises(OfficialAggregationError, match="official accounting"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_rejects_exporter_packet_sha256_mismatch(
    tmp_path: Path,
) -> None:
    manifest_path = _write_run_input_manifest(
        tmp_path,
        packet_hash_field="packet_sha256",
        packet_sha256="b" * 64,
    )
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(OfficialAggregationError, match="packet SHA-256 mismatch"):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def test_official_aggregate_requires_packet_hash_commitment(tmp_path: Path) -> None:
    manifest_path = _write_run_input_manifest(tmp_path, packet_hash_field=None)
    registry_path = _write_model_registry(tmp_path, ("fixture:solver",))
    labels_path = _write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    _write_case_artifacts(per_case_dir)

    with pytest.raises(
        OfficialAggregationError,
        match="requires sha256 or packet_sha256",
    ):
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
                model_registry_path=registry_path,
                allow_no_baselines=True,
                ablation="full_packet",
            )
        )


def _default_label_records() -> list[dict[str, Any]]:
    return [
        _label("unit-dismissed", True).to_record(),
        _label("unit-survives", False).to_record(),
    ]


def _labels_sha256(records: list[dict[str, Any]]) -> str:
    payload = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_run_input_manifest(
    tmp_path: Path,
    *,
    include_baseline_features: bool = False,
    ablations: tuple[str, ...] = ("full_packet",),
    packet_size_bytes: int = 4_096,
    labels_sha256: str | None = None,
    packet_hash_field: str | None = "sha256",
    packet_sha256: str = "a" * 64,
) -> Path:
    manifest_path = tmp_path / "run-inputs.json"
    packet_rows: list[dict[str, Any]] = []
    for ablation in ablations:
        packet_row: dict[str, Any] = {
            "case_id": "case-1",
            "ablation": ablation,
            "object_key": f"model-packets/cycle-1/case-1/{ablation}.json",
            "packet_size_bytes": packet_size_bytes,
        }
        if packet_hash_field is not None:
            packet_row[packet_hash_field] = packet_sha256
        if include_baseline_features:
            packet_row["candidate_id"] = "candidate-1"
            packet_row["baseline_features"] = [
                _baseline_feature_record("unit-dismissed"),
                _baseline_feature_record("unit-survives"),
            ]
        packet_rows.append(packet_row)
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "labels_sha256": (
                labels_sha256
                if labels_sha256 is not None
                else _labels_sha256(_default_label_records())
            ),
            "model_packets": packet_rows,
        },
    )
    return manifest_path


def _write_baseline_training_examples(tmp_path: Path) -> Path:
    path = tmp_path / "baseline-training.jsonl"
    rows: list[dict[str, Any]] = []
    for index in range(30):
        rows.append(
            {
                "features": _baseline_feature_record(
                    f"hist-unit-{index}",
                    case_id=f"hist-case-{index}",
                ),
                "fully_dismissed": index < 18,
                "decision_date": f"2024-01-{index + 1:02d}",
            }
        )
    _write_jsonl(path, rows)
    return path


def _baseline_feature_record(
    unit_id: str,
    *,
    case_id: str = "case-1",
) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "case_id": case_id,
        "court": "S.D.N.Y.",
        "district": "S.D.N.Y.",
        "circuit": "2d",
        "nos_macro_category": "contract",
        "motion_type": "12(b)(6)",
        "judge_id": "judge-fixture",
        "represented_party_status": "all_represented",
        "government_party_status": "no_government_party",
        "claim_count": 2,
        "defendant_count": 1,
        "motion_length_tokens": 4_000,
        "complaint_length_tokens": 8_000,
        "case_age_days": 120,
        "docket_entry_count": 24,
    }


def _write_labels(tmp_path: Path) -> Path:
    labels_path = tmp_path / "labels.jsonl"
    _write_jsonl(labels_path, _default_label_records())
    return labels_path


def _write_model_registry(tmp_path: Path, model_keys: tuple[str, ...]) -> Path:
    registry_path = tmp_path / "model-registry.json"
    records: list[dict[str, Any]] = []
    for model_key in model_keys:
        provider, model_id = model_key.split(":", 1)
        records.append(
            {
                "provider": provider,
                "model_id": model_id,
                "display_name": model_id,
                "model_version_or_snapshot": "2026-05-14",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "known",
                "provider_training_cutoff": "2026-04-01",
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": [],
            }
        )
    _write_json_list(registry_path, records)
    return registry_path


def _write_case_artifacts(
    per_case_dir: Path,
    *,
    case_dir_name: str = "official-eval-case-1-full_packet",
    solver_id: str = "fixture:solver",
    model_id: str = "fixture-model",
    ablation: str = "full_packet",
    dismissed_probability: float = 0.9,
    estimated_cost: float = 0.02,
) -> Path:
    case_dir = per_case_dir / case_dir_name
    raw_output = _fixture_raw_output(dismissed_probability)
    raw_output_sha256 = _text_sha256_prefixed(raw_output)
    run_record: dict[str, Any] = {
        "sample_id": "sample-1",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "related_family_id": None,
        "mdl_family_id": None,
        "solver_id": solver_id,
        "solver_kind": "offline_fixture",
        "model_id": model_id,
        "run_label": ablation,
        "ablation": ablation,
        "raw_output": raw_output,
        "raw_output_sha256": raw_output_sha256,
        "required_unit_ids": ["unit-dismissed", "unit-survives"],
        "request_count": 1,
        "input_tokens": 100,
        "output_tokens": 25,
        "estimated_total_tokens": 125,
        "estimated_cost": estimated_cost,
        "tool_call_logs": [],
        "metadata": {},
        "execution_backend": "local_fixture",
    }
    accounting = ModelRunAccountingRecord(
        sample_id="sample-1",
        candidate_id="candidate-1",
        case_id="case-1",
        solver_id=solver_id,
        solver_kind="offline_fixture",
        provider="fixture",
        model_id=model_id,
        model_version_or_snapshot="2026-05-17",
        served_model_version=None,
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
        estimated_cost=estimated_cost,
        cost_per_case=estimated_cost,
        cost_per_prediction_unit=estimated_cost / 2,
        invalid_output=False,
        refusal=False,
        content_filter=False,
        invalid_output_reason=None,
        run_label=ablation,
        ablation=ablation,
        execution_backend="local_fixture",
    )
    _write_jsonl(case_dir / "runs.jsonl", [run_record])
    _write_jsonl(case_dir / "accounting.jsonl", [accounting.to_record()])
    _write_json(
        case_dir / "metrics.json",
        {
            "schema_version": "legalforecast.per_case_metrics.v1",
            "run_id": f"cycle-1-case-1-{ablation}-fixture",
            "cycle_id": "cycle-1",
            "case_id": "case-1",
            "ablation": ablation,
            "solver_id": solver_id,
            "model_key": solver_id,
            "evaluation_timestamp": "2026-05-17T12:00:00Z",
            "packet_object_key": f"model-packets/cycle-1/case-1/{ablation}.json",
            "packet_sha256": "a" * 64,
            "run_record_count": 1,
            "raw_output_sha256": [raw_output_sha256],
            "tool_call_count": 0,
        },
    )
    return case_dir


def _write_repeated_case_artifacts(
    per_case_dir: Path,
    *,
    probabilities: tuple[float, ...],
) -> Path:
    if not probabilities:
        raise ValueError("probabilities must not be empty")
    case_dir = _write_case_artifacts(
        per_case_dir,
        dismissed_probability=probabilities[0],
    )
    base_run = _read_jsonl(case_dir / "runs.jsonl")[0]
    base_accounting = _read_jsonl(case_dir / "accounting.jsonl")[0]
    metrics = json.loads((case_dir / "metrics.json").read_text(encoding="utf-8"))

    run_records: list[dict[str, Any]] = []
    accounting_records: list[dict[str, Any]] = []
    raw_hashes: list[str] = []
    repeat_count = len(probabilities)
    for repeat_index, probability in enumerate(probabilities, start=1):
        raw_output = _fixture_raw_output(probability)
        raw_hash = _text_sha256_prefixed(raw_output)
        raw_hashes.append(raw_hash)
        repeat_fields = {
            "sample_id": f"sample-1__repeat_{repeat_index:02d}",
            "raw_output_sha256": raw_hash,
            "repeat_group_id": "sample-1",
            "repeat_index": repeat_index,
            "repeat_count": repeat_count,
            "repeat_sampling_role": ("primary" if repeat_index == 1 else "repeat"),
        }
        run_records.append(
            {
                **base_run,
                **repeat_fields,
                "raw_output": raw_output,
            }
        )
        accounting_records.append({**base_accounting, **repeat_fields})

    metrics.update(
        {
            "raw_output_sha256": raw_hashes,
            "repeat_count": repeat_count,
            "primary_run_record_count": 1,
            "run_record_count": repeat_count,
        }
    )
    _write_jsonl(case_dir / "runs.jsonl", run_records)
    _write_jsonl(case_dir / "accounting.jsonl", accounting_records)
    _write_json(case_dir / "metrics.json", metrics)
    return case_dir


def _fixture_raw_output(dismissed_probability: float) -> str:
    return json.dumps(
        {
            "case_assessment": "Fixture.",
            "predictions": [
                {
                    "unit_id": "unit-dismissed",
                    "probability_fully_dismissed": dismissed_probability,
                },
                {
                    "unit_id": "unit-survives",
                    "probability_fully_dismissed": 0.2,
                },
            ],
        }
    )


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


def _write_json_list(path: Path, payload: list[dict[str, Any]]) -> None:
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
