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
