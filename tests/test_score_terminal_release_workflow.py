from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

WORKFLOW_PATH = Path(".github/workflows/score-terminal-release.yaml")
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def _section(start: str, end: str | None = None) -> str:
    start_index = WORKFLOW.index(start)
    end_index = len(WORKFLOW) if end is None else WORKFLOW.index(end, start_index)
    return WORKFLOW[start_index:end_index]


def test_score_workflow_is_manual_and_protected() -> None:
    assert "name: Score Terminal Release" in WORKFLOW
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "workflow_run:" not in WORKFLOW
    assert "schedule:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval-fan-in" in WORKFLOW
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "actions: write" not in WORKFLOW
    for provider_secret in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
    ):
        assert provider_secret not in WORKFLOW


def test_dispatch_contract_has_locked_inputs_and_no_free_form_artifact_name() -> None:
    for input_name in (
        "release_sha:",
        "cycle_id:",
        "forecast_run_id:",
        "forecast_run_attempt:",
        "forecast_artifact_id:",
        "manifest_uri:",
        "forecast_release_uri:",
        "artifact_root_uri:",
        "labels_release_uri:",
        "model_key:",
    ):
        assert input_name in WORKFLOW
    assert "forecast_artifact_name:" not in WORKFLOW
    assert "official-terminal-forecast-results-{run_id}-attempt-{attempt}" in WORKFLOW
    assert "artifact_root_uri must be a prefix ending in /" in WORKFLOW
    assert "labels and forecast releases must be separate objects" in WORKFLOW


def test_source_run_and_artifact_are_bound_before_any_label_fetch() -> None:
    run_validation = _section(
        "- name: Validate exact forecast workflow attempt",
        "- name: Download exact terminal scoreless artifact",
    )
    for required in (
        'run.get("id") == run_id',
        'run.get("run_attempt") == attempt',
        '"--is-ancestor", head_sha, "origin/main"',
        'run.get("head_branch") == "main"',
        'run.get("event") == "workflow_dispatch"',
        'run.get("path") == ".github/workflows/run-benchmark.yaml"',
        'run.get("status") == "completed"',
        'run.get("conclusion") in {"success", "failure", "neutral"}',
    ):
        assert required in run_validation

    artifact_download = _section(
        "- name: Download exact terminal scoreless artifact",
        "- name: Configure protected fan-in read access",
    )
    for required in (
        "actions/runs/{run_id}/artifacts?per_page=100",
        'item.get("id") == artifact_id',
        'item.get("name") == expected_name',
        "terminal artifact contains an unsafe path",
        "terminal artifact contains a duplicate path",
        "terminal artifact contains a non-regular file",
        "run-compatibility.json",
        "selection-manifest.json",
        "task-index.json",
        "row-results.jsonl",
        "inputs/run-manifest.json",
        "inputs/forecast-release.json",
        "inputs/model-registry.json",
        "inputs/artifacts",
        "labels or scores",
        'models[0].get("model_key")',
        'run_config.get("container_execution") != "headless_cli"',
        'item.get("adapter_id") == "claude-code-container"',
    ):
        assert required in artifact_download

    fetch_start = WORKFLOW.index(
        "- name: Fetch locked releases and labels inside protected fan-in"
    )
    assert (
        WORKFLOW.index("- name: Validate exact forecast workflow attempt") < fetch_start
    )
    assert (
        WORKFLOW.index("- name: Download exact terminal scoreless artifact")
        < fetch_start
    )
    assert 'fetch_file "${LABELS_RELEASE_URI}"' in WORKFLOW[fetch_start:]
    assert "configure-aws-credentials@" in WORKFLOW[:fetch_start]


def test_package_inputs_are_compared_with_locked_score_inputs() -> None:
    validation = _section(
        "- name: Validate locked releases before score-only command",
        "- name: Score saved terminal package without model or provider access",
    )
    for required in (
        '"inputs/run-manifest.json"',
        '"inputs/forecast-release.json"',
        '"inputs/artifacts"',
        '"terminal package manifest differs from locked manifest"',
        '"terminal package forecast differs from locked forecast"',
        '"terminal package artifacts differ from locked artifact root"',
        '"terminal package must not contain labels"',
        "legalforecast manifest validate",
    ):
        assert required in validation


def test_score_step_cannot_execute_a_model_or_write_official_storage() -> None:
    score = _section(
        "- name: Score saved terminal package without model or provider access",
        "- name: Upload score-only result package",
    )
    assert "uv run legalforecast multiharness release-score" in score
    for flag in (
        "--run-dir /tmp/lfb-terminal-scoreless",
        "--forecast-release /tmp/lfb-terminal-score-inputs/forecast-release.json",
        "--labels-release /tmp/lfb-terminal-score-inputs/labels-release.json",
        "--artifact-root /tmp/lfb-terminal-score-inputs/artifacts",
        "--output /tmp/lfb-terminal-score-result/scores.json",
    ):
        assert flag in score
    assert "release-run" not in score
    assert "release-execute" not in score
    assert "aws s3 cp" not in score
    assert "score_status=0" in score
    assert 'exit "${score_status}"' in score
    assert "put-object" not in WORKFLOW
    assert "reconcile-s3-object" not in WORKFLOW
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in WORKFLOW
    )
    assert "/tmp/lfb-terminal-score-result" in WORKFLOW
    assert "if: ${{ always() }}" in _section("- name: Upload score-only result package")


def test_score_result_requires_one_model_bound_to_dispatch_identity() -> None:
    identity = _section(
        "- name: Validate sole scored model identity",
        "- name: Upload score-only result package",
    )
    for required in (
        "if: ${{ always() }}",
        "/tmp/lfb-terminal-score-result/scores.json",
        'report.get("models")',
        "len(models) != 1",
        'model.get("model_key") != os.environ["EXPECTED_MODEL_KEY"]',
        "EXPECTED_MODEL_KEY: ${{ inputs.model_key }}",
    ):
        assert required in identity


def test_score_result_identity_script_rejects_mismatch_and_multiple_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _section(
        "- name: Validate sole scored model identity",
        "- name: Upload score-only result package",
    )
    script = textwrap.dedent(
        identity.split("uv run python - <<'PY'\n", 1)[1].split("          PY", 1)[0]
    )
    score_path = tmp_path / "scores.json"
    script = script.replace(
        'Path("/tmp/lfb-terminal-score-result/scores.json")',
        f"Path({str(score_path)!r})",
    )
    monkeypatch.setenv("EXPECTED_MODEL_KEY", "anthropic:fixture")

    score_path.write_text(
        json.dumps({"models": [{"model_key": "anthropic:fixture"}]}),
        encoding="utf-8",
    )
    exec(compile(script, "score-model-identity", "exec"), {})

    score_path.write_text(
        json.dumps({"models": [{"model_key": "anthropic:other"}]}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="model identity differs"):
        exec(compile(script, "score-model-identity", "exec"), {})

    score_path.write_text(
        json.dumps(
            {
                "models": [
                    {"model_key": "anthropic:fixture"},
                    {"model_key": "anthropic:fixture"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="exactly one model"):
        exec(compile(script, "score-model-identity", "exec"), {})


def test_result_metadata_binds_the_score_to_the_source_and_locked_inputs() -> None:
    score = _section(
        "- name: Score saved terminal package without model or provider access",
        "- name: Upload score-only result package",
    )
    for field in (
        '"source_forecast_run_id"',
        '"source_forecast_run_attempt"',
        '"source_forecast_artifact_id"',
        '"release_sha"',
        '"model_key"',
        '"manifest_uri"',
        '"forecast_release_uri"',
        '"artifact_root_uri"',
        '"labels_release_uri"',
        '"scores_sha256"',
    ):
        assert field in score
