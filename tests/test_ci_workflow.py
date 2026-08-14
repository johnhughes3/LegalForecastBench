from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")


def test_ci_workflow_runs_contract_ratchet_before_typecheck() -> None:
    ratchet_step = (
        "- name: Contract ratchet\n"
        "        run: uv run python -m legalforecast.contracts.ratchet"
    )
    assert ratchet_step in WORKFLOW
    assert WORKFLOW.index(ratchet_step) < WORKFLOW.index(
        "- name: Type-check\n        run: uv run pyright"
    )


def test_ci_workflow_fetches_origin_main_before_acquisition_config_fence() -> None:
    fetch_step = (
        "- name: Fetch origin/main for the acquisition-config fence\n"
        "        run: git fetch --no-tags origin main:refs/remotes/origin/main"
    )
    fence_step = (
        "- name: Acquisition config fence\n"
        "        run: uv run python -m legalforecast.config.fence"
    )
    assert fetch_step in WORKFLOW
    assert WORKFLOW.index(fetch_step) < WORKFLOW.index(fence_step)
