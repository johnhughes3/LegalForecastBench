from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT / ".github" / "workflows" / "official-paid-labeling-authority-smoke.yaml"
)


def test_smoke_has_no_provider_secret_or_provider_call() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "legalforecastbench-official-labeling-authority-smoke" in text
    assert "runs-on: ubuntu-latest" in text
    assert "CI_RUNNER" not in text
    assert "provider_call_made:false" in text
    assert "secrets." not in text
    assert "OPENAI_API_KEY" not in text
    assert "ANTHROPIC_API_KEY" not in text
    assert "GEMINI_API_KEY" not in text
    assert "uv run legalforecast" not in text


def test_smoke_exercises_exact_allowlist_and_required_denials() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for command in (
        "dynamodb describe-table",
        "dynamodb get-item",
        "dynamodb put-item",
        "dynamodb update-item",
        "dynamodb transact-write-items",
    ):
        assert command in text
    for denied in (
        "dynamodb scan",
        "dynamodb delete-item",
        "LFB_OUTSIDE_AUTHORITY_TABLE",
        "dynamodb list-tables",
    ):
        assert denied in text
    assert "resource_identity_sha256" in text
    assert "sha256sum" in text


def test_smoke_redacts_denials_and_clears_credentials_before_upload() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'if "$@" >"${denial_error}" 2>&1; then' in text
    assert "grep -Eqi 'AccessDenied|not authorized'" in text
    assert 'rm -f "${denial_error}"' in text
    assert text.index("Clear temporary AWS credentials") < text.index(
        "Upload redacted smoke evidence"
    )
    for credential in (
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "AWS_SESSION_TOKEN=",
        "AWS_SECURITY_TOKEN=",
    ):
        assert credential in text


def test_smoke_actions_are_sha_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    uses = re.findall(r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", text, re.MULTILINE)

    assert uses
    for action in uses:
        _, reference = action.rsplit("@", 1)
        assert len(reference) == 40
        assert all(character in "0123456789abcdef" for character in reference)
