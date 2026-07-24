"""Contract tests for the provider automation and publication decision."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "docs" / "adapters" / "provider-baselines.md"


def _policy() -> str:
    return POLICY_PATH.read_text(encoding="utf-8")


def test_provider_decision_is_dated_and_surface_specific() -> None:
    policy = _policy()

    assert "Decision reviewed: 2026-07-17" in policy
    assert "## Supported profile matrix" in policy
    for profile_id in (
        "codex-chatgpt-local",
        "codex-api-automation",
        "claude-subscription-local",
        "claude-api-automation",
    ):
        assert f"`{profile_id}`" in policy

    assert (
        "No provider statement is generalized beyond its documented product surface."
        in policy
    )
    assert "Ambiguity is a blocking result" in policy


def test_provider_decision_links_primary_auth_automation_and_terms_sources() -> None:
    policy = _policy()

    for source in (
        "https://learn.chatgpt.com/docs/auth",
        "https://learn.chatgpt.com/docs/non-interactive-mode",
        "https://openai.com/policies/terms-of-use/",
        "https://openai.com/policies/services-agreement/",
        "https://openai.com/policies/sharing-publication-policy/",
        "https://openai.com/brand/",
        "https://code.claude.com/docs/en/headless",
        "https://code.claude.com/docs/en/iam",
        "https://code.claude.com/docs/en/costs",
        "https://code.claude.com/docs/en/github-actions",
        "https://www.anthropic.com/legal/consumer-terms",
        "https://www.anthropic.com/legal/commercial-terms",
    ):
        assert source in policy


def test_provider_decision_pins_observed_cli_capabilities_without_host_paths() -> None:
    policy = _policy()

    assert "Codex CLI 0.144.5" in policy
    assert "058d616bde049c0648b72d53a22a54bf428eeb3f10e76cb4d6d4d4f81b764600" in policy
    assert "Claude Code 2.1.212" in policy
    assert "044a88cf3a5180776617fd3da1238dcbf9141ddec449a39cf7d2af1ac78e684e" in policy
    assert "codex exec" in policy
    assert "claude -p" in policy
    assert "/home/" not in policy
    assert "/work/" not in policy


def test_provider_decision_fails_closed_on_ci_billing_and_publication() -> None:
    policy = _policy()

    for required_boundary in (
        "Do not publish provider account identifiers",
        "Do not report subscription usage as API spend",
        "Do not copy or share a contributor's subscription credential",
        "public-repository CI",
        "provider endorsement",
        "raw transcripts remain private",
    ):
        assert required_boundary in policy

    assert (
        "The Consumer Terms require independently confirming accuracy before relying "
        "on output" in policy
    )
    assert "the Commercial Terms require evaluating output appropriateness" in policy


def test_each_profile_retains_auth_execution_and_publication_decisions() -> None:
    rows = {
        line.split("|")[1].strip().strip("`"): line
        for line in _policy().splitlines()
        if line.startswith("| `")
    }

    expected = {
        "codex-chatgpt-local": ("ChatGPT sign-in", "`codex exec`", "may publish"),
        "codex-api-automation": ("Platform API key", "isolated CI", "may publish"),
        "claude-subscription-local": (
            "Claude Code entitlement",
            "`claude -p`",
            "may publish",
        ),
        "claude-api-automation": ("Anthropic API key", "isolated CI", "may publish"),
    }
    assert rows.keys() == expected.keys()
    for profile_id, required_decisions in expected.items():
        for decision in required_decisions:
            assert decision in rows[profile_id]
