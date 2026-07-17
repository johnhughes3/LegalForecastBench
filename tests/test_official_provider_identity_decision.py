from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "docs/security/official-provider-identity-decision.md"
ROADMAP_PATH = ROOT / "docs/plans/2026-07-16-dual-track-launch-roadmap.md"


def _decision() -> str:
    return DECISION_PATH.read_text(encoding="utf-8")


def _roadmap() -> str:
    return ROADMAP_PATH.read_text(encoding="utf-8")


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
    assert "`model_registries/cycle-1-provider-caps-2026-07-12.json`" in decision
    assert "USD 215 for OpenAI" in decision
    assert "USD 200 each for Anthropic and Gemini" in decision
    assert "Those caps limit economic exposure" in decision
    assert "They do not prevent credential replay" in decision
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
        "issuer, audience, repository, ref, caller `workflow_ref`, and environment"
        in decision
    )
    assert (
        "johnhughes3/LegalForecastBench/.github/workflows/"
        "run-benchmark.yaml@refs/heads/main" in decision
    )
    assert (
        "johnhughes3/LegalForecastBench/.github/workflows/"
        "official-provider-cell.yaml@refs/heads/main" in decision
    )
    assert "`job_workflow_ref`" in decision
    assert "`job_workflow_sha`" in decision
    assert (
        "The provider mapping must pin `job_workflow_ref` to "
        "`johnhughes3/LegalForecastBench/.github/workflows/"
        "official-provider-cell.yaml@refs/heads/main`" in decision
    )
    assert (
        "`LegalForecastBench-5qd6.100` remains blocked pending resolution" in decision
    )
    assert "it does not substitute for binding token issuance" in decision
    assert "environment `legalforecastbench-official-eval-openai`" in decision
    assert "`ANTHROPIC_API_KEY` must be unset" in decision


def test_roadmap_decision_register_points_to_live_security_gates() -> None:
    roadmap = _roadmap()
    decision_register = roadmap.split(
        "### DEC-07: issue #37 dispatch status", maxsplit=1
    )[1].split("### DEC-08:", maxsplit=1)[0]

    assert (
        "Decision: implementation required for the selected OpenAI smoke"
        in decision_register
    )
    assert "`LegalForecastBench-5qd6.100`" in decision_register
    assert "`LegalForecastBench-5qd6.101`" in decision_register
    assert "docs/security/official-provider-identity-decision.md" in decision_register


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
