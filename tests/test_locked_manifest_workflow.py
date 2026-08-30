from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark-manifest.yaml").read_text(
    encoding="utf-8"
)


def test_locked_manifest_workflow_exposes_public_contract_inputs() -> None:
    for input_name in (
        "manifest_uri:",
        "forecast_release_uri:",
        "labels_release_uri:",
        "artifact_root_uri:",
        "model_registry_uri:",
        "model_key:",
        "ceiling_microusd:",
    ):
        assert input_name in WORKFLOW
    assert "run_input_manifest_uri:" not in WORKFLOW
    assert "labels_uri:" not in WORKFLOW


def test_forecast_worker_does_not_download_labels() -> None:
    worker = WORKFLOW.split("  run-forecast:", maxsplit=1)[1].split(
        "  score-and-report:", maxsplit=1
    )[0]
    assert "locked-manifest-forecast-inputs" in worker
    assert "locked-manifest-labels" not in worker
    assert "labels-release" not in worker
    assert "--manifest" in worker
    assert "--forecast" in worker


def test_fan_in_uses_labels_release_for_score_and_report() -> None:
    fan_in = WORKFLOW.split("  score-and-report:", maxsplit=1)[1]
    assert "locked-manifest-labels" in fan_in
    assert "--labels-release" in fan_in
    assert "legalforecast score" in fan_in
    assert "legalforecast report" in fan_in
