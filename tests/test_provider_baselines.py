"""Contract tests for the public provider baseline guidance."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "docs" / "adapters" / "provider-baselines.md"


def _policy() -> str:
    return POLICY_PATH.read_text(encoding="utf-8")


def test_provider_guidance_names_current_community_surfaces() -> None:
    policy = _policy()

    for required_surface in (
        "examples/adapters/openai-responses/adapter-manifest.json",
        "examples/adapters/claude-agent-sdk/adapter-manifest.json",
        "community/submissions/2026/",
        "tests/fixtures/community_submissions/2026/",
        "credential-free conformance",
        "run-with-tools",
        "gpt-5.6-sol",
        "Vercel AI Gateway",
        "OPENAI_API_KEY",
        "2026-09-18 UTC",
        "2026-09-19 UTC",
    ):
        assert required_surface in policy


def test_provider_guidance_preserves_public_credential_boundary() -> None:
    policy = _policy()

    for required_boundary in (
        "consumer subscription login is not a general third-party API entitlement",
        "Public repository CI must not install cached interactive or "
        "subscription credentials",
        "Do not report subscription usage as API spend",
        "provider sponsorship",
        "raw transcript",
    ):
        assert required_boundary in policy

    assert "/home/" not in policy
    assert "/work/" not in policy
