from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_official_evaluation_has_one_manual_outcome_blinded_dispatch_boundary() -> None:
    assert WORKFLOW.startswith("name: Run Benchmark\n")
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "environment: legalforecastbench-official-eval-prepare-inputs" in WORKFLOW
    assert "LFB_GITHUB_PREPARE_INPUTS_ROLE_ARN" in WORKFLOW
    assert "labels_release_uri" not in WORKFLOW
    assert "approval-reference" not in WORKFLOW


def test_forecast_jobs_use_real_dynamic_logical_cell_matrices() -> None:
    for provider, next_name in (
        ("openai", "run-anthropic"),
        ("anthropic", "run-gemini"),
        ("gemini", None),
    ):
        job = _job(f"run-{provider}", next_name)
        assert "strategy:" in job
        assert "fail-fast: false" in job
        assert (
            "max-parallel: ${{ fromJSON(needs.prepare-inputs.outputs.max_parallel) }}"
            in job
        )
        assert (
            "matrix: ${{ fromJSON(needs.prepare-inputs.outputs."
            + f"{provider}_matrix) }}"
            in job
        )
        assert "Restore newest prior valid attempt" in job
        assert "Persist" in job
        assert "if: ${{ always() }}" in job
        assert "ledger.sqlite3" in job
        assert "receipts" in job
        assert "cell: [run]" not in job


def test_provider_jobs_are_the_only_secret_boundaries() -> None:
    jobs = {
        "openai": ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"),
        "anthropic": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"),
        "gemini": ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    }
    for name, (own, other_a, other_b) in jobs.items():
        block = _job(
            f"run-{name}",
            {"openai": "run-anthropic", "anthropic": "run-gemini", "gemini": None}[
                name
            ],
        )
        assert block.count(f"secrets.{own}") == 1
        assert f"secrets.{other_a}" not in block
        assert f"secrets.{other_b}" not in block
        assert "secrets: inherit" not in block
        assert "labels_release_uri" not in block
        assert "GITHUB_EVENT_PATH" not in block
        assert "--cell-id" in block
        assert "--unit-id" in block
        assert "--repeat-index" in block
        assert "--ablation" in block


def test_forecast_workflow_ends_at_durable_state_not_scoring() -> None:
    assert "score-and-report:" not in WORKFLOW
    assert "legalforecast score" not in WORKFLOW
    assert "legalforecast report" not in WORKFLOW
    assert "/tmp/lfb-run/failure-summary.json" in WORKFLOW
    assert "if-no-files-found: error" in WORKFLOW
    assert "continue-on-error" not in WORKFLOW
