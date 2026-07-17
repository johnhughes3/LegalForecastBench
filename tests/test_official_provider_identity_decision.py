from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "docs/security/official-provider-identity-decision.md"


def _decision() -> str:
    return DECISION_PATH.read_text(encoding="utf-8")


def test_decision_explicitly_blocks_the_live_smoke() -> None:
    decision = _decision()

    assert "Status: implementation required" in decision
    assert "Authority: `LegalForecastBench-dm0g.5.3`" in decision
    assert "Successor: `LegalForecastBench-5qd6.100`" in decision
    assert (
        "`LegalForecastBench-5qd6.35` depends on `LegalForecastBench-5qd6.100`"
        in decision
    )
    assert (
        "`LegalForecastBench-5qd6.35` also depends on `LegalForecastBench-5qd6.101`"
        in decision
    )
    assert "No static-key waiver is authorized" in decision


def test_decision_records_the_current_threat_model_evidence() -> None:
    decision = _decision()

    assert "`.github/workflows/official-provider-cell.yaml`" in decision
    assert "`PROVIDER_API_KEY`" in decision
    assert "`docs/security/model-provider-budget-caps.md` does not exist" in decision
    assert "credential replay" in decision
    assert "provider isolation is necessary but does not bound" in decision


def test_decision_routes_each_provider_and_exact_reactivation_conditions() -> None:
    decision = _decision()

    assert "OpenAI | Cycle 1 gate" in decision
    assert "Anthropic | Residual issue #37 work" in decision
    assert "Gemini | Residual issue #37 work" in decision
    assert (
        "before an Anthropic registry row is approved for official dispatch" in decision
    )
    assert "before a Gemini registry row is approved for official dispatch" in decision
    assert (
        "issuer, audience, repository, ref, workflow_ref, and environment" in decision
    )
    assert "`ANTHROPIC_API_KEY` must be unset" in decision


def test_decision_links_primary_provider_guidance() -> None:
    decision = _decision()

    assert (
        "https://developers.openai.com/api/docs/guides/"
        "workload-identity-federation/github-actions" in decision
    )
    assert (
        "https://platform.claude.com/docs/en/manage-claude/"
        "workload-identity-federation" in decision
    )
    assert (
        "https://docs.cloud.google.com/iam/docs/workload-identity-federation"
        in decision
    )
