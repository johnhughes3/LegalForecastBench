"""Static checks for the protected, scoreless Claude Code workflow lane."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = (
        WORKFLOW.index(f"  {next_name}:", start)
        if next_name is not None
        else len(WORKFLOW)
    )
    return WORKFLOW[start:end]


def test_terminal_job_reuses_locked_inputs_and_gates_native_matrix() -> None:
    terminal = _job("run-terminal", "run-openai")
    assert "inputs.execution_mode == 'claude-code-terminal'" in terminal
    assert "needs.prepare-inputs.outputs.locked_inputs_artifact_id" in terminal
    assert "run-manifest.json" in terminal
    assert "forecast-release.json" in terminal
    assert "model-registry.json" in terminal
    assert "paid_gateway_descriptor" in terminal
    assert "legalforecast multiharness release-execute" in terminal
    assert "--auth-profile published-api-key" in terminal
    assert "--paid-config /tmp/lfb-terminal-paid/paid-gateway.json" in terminal
    assert '--gateway-image "${LFB_GATEWAY_IMAGE}"' in terminal
    assert "ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}" in terminal
    assert "Preserve locked scoreless package inputs" in terminal
    assert "input_root=/tmp/lfb-terminal-paid/release/inputs" in terminal
    assert (
        "official-terminal-forecast-results-${{ github.run_id }}-attempt-" in terminal
    )
    assert "if: ${{ always() }}" in terminal
    assert "labels" not in terminal.lower()
    assert "--labels" not in terminal

    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "run-gateway"),
        ("run-gateway", None),
    ):
        job = _job(name, next_name)
        assert "inputs.execution_mode == 'native'" in job

    persist = _job("persist-forecast-results")
    assert "inputs.execution_mode == 'native'" in persist


def test_terminal_workflow_keeps_labels_out_of_forecast_inputs() -> None:
    prepare = _job("prepare-inputs", "run-openai")
    terminal = _job("run-terminal", "run-openai")
    assert "labels" not in prepare.lower()
    assert "labels_release_uri" not in WORKFLOW
    assert "labels" not in terminal.lower()
    assert "actions/download-artifact@" in terminal
    assert "actions/upload-artifact@" in terminal


def test_terminal_workflow_builds_and_verifies_local_pinned_images() -> None:
    terminal = _job("run-terminal", "run-openai")
    assert (
        "docker build --pull=false -f infra/claude-code-runtime/Containerfile"
        in terminal
    )
    assert (
        "docker build --pull=false -f infra/model-gateway-runtime/Containerfile"
        in terminal
    )
    assert terminal.count("=~ ^sha256:[0-9a-f]{64}$") == 2
    assert 'LFB_PROTECTED_TERMINAL_RELEASE: "1"' in terminal
    assert "id-token: write" in terminal


def test_terminal_case_selector_is_quoted_and_rejected_for_native_mode() -> None:
    import os
    import subprocess
    import textwrap

    terminal = _job("run-terminal", "run-openai")
    assert "TERMINAL_CASE_ID: ${{ inputs.terminal_case_id }}" in terminal
    assert 'case_args+=(--case-id "${TERMINAL_CASE_ID}")' in terminal
    assert 'release-execute "${case_args[@]}"' in terminal
    prepare = _job("prepare-inputs", "run-terminal")
    start = prepare.index('          if [[ -n "${TERMINAL_CASE_ID}"')
    end = prepare.index("          fi", start) + len("          fi")
    guard = textwrap.dedent(prepare[start:end])
    for mode, case_id, accepted in (
        ("native", "case-001", False),
        ("native", "", True),
        ("claude-code-terminal", "case-001", True),
    ):
        result = subprocess.run(
            ["bash", "-c", guard],
            env={**os.environ, "EXECUTION_MODE": mode, "TERMINAL_CASE_ID": case_id},
            capture_output=True,
            text=True,
            check=False,
        )
        assert (result.returncode == 0) is accepted
