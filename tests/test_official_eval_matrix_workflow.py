from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_official_evaluation_has_one_manual_protected_dispatch_boundary() -> None:
    assert WORKFLOW.startswith("name: Run Benchmark\n")
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "environment: legalforecastbench-official-eval-fan-in" in WORKFLOW
    assert "run_input_manifest_uri:" not in WORKFLOW
    assert "labels_uri:" not in WORKFLOW
    assert "approval-reference" not in WORKFLOW


def test_forecast_jobs_are_bounded_resumable_provider_cells() -> None:
    for provider, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "score-and-report"),
    ):
        job = _job(provider, next_name)
        assert "strategy:" in job
        assert "fail-fast: false" in job
        assert "max-parallel: ${{ fromJSON(inputs.max_parallel) }}" in job
        assert "Restore resumable" in job
        assert "Persist" in job
        assert "if: ${{ always() }}" in job
        assert "ledger.sqlite3" in job
        assert "receipts" in job


def test_fan_in_requires_provider_completion_and_is_the_label_boundary() -> None:
    fan_in = _job("score-and-report")
    assert "needs: [prepare-inputs, run-openai, run-anthropic, run-gemini]" in fan_in
    assert "needs.prepare-inputs.result == 'success'" in fan_in
    assert "needs.run-openai.result == 'success'" in fan_in
    assert "needs.run-anthropic.result == 'success'" in fan_in
    assert "needs.run-gemini.result == 'success'" in fan_in
    assert "--labels-release" in fan_in
    assert "legalforecast score" in fan_in
    assert "legalforecast report" in fan_in
