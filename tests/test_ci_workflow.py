from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
CI_RUNNER_CLAMP = (
    "runs-on: ${{ (vars.CI_RUNNER == 'ubuntu-latest' || "
    "startsWith(vars.CI_RUNNER, 'ubicloud-')) && vars.CI_RUNNER || "
    "'ubicloud-standard-2' }}"
)


def test_ci_workflow_uses_ci_runner_clamp_with_ubicloud_fallback() -> None:
    assert CI_RUNNER_CLAMP in WORKFLOW
    assert "runs-on: ubuntu-latest" not in WORKFLOW
    assert "runs-on: ${{ vars.CI_RUNNER }}" not in WORKFLOW


def test_ci_workflow_runs_contract_ratchet_before_typecheck() -> None:
    ratchet_step = (
        "- name: Contract ratchet\n"
        "        run: uv run python -m legalforecast.contracts.ratchet"
    )
    assert ratchet_step in WORKFLOW
    assert WORKFLOW.index(ratchet_step) < WORKFLOW.index(
        "- name: Type-check\n        run: uv run pyright"
    )


def test_ci_workflow_does_not_run_retired_acquisition_config_fence() -> None:
    assert "acquisition-config fence" not in WORKFLOW
    assert "legalforecast.config.fence" not in WORKFLOW
