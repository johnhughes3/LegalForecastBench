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
    assert re.search(r"\bsecrets\s*\[", text) is None
    assert "OPENAI_API_KEY" not in text
    assert "ANTHROPIC_API_KEY" not in text
    assert "GEMINI_API_KEY" not in text
    assert "uv run legalforecast" not in text


def test_smoke_exercises_exact_allowlist_and_required_denials() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for command in (
        "dynamodb describe-table",
        "dynamodb describe-time-to-live",
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
    assert "{ConditionCheck:{" in text
    assert 'record_key:{S:"get-put-update"}' in text
    assert 'ConditionExpression:"smoke_state = :updated"' in text
    assert "condition_check_item:true" in text
    assert '[[ "${ttl_status}" != "ENABLED" ]]' in text
    assert '[[ "${ttl_attribute}" != "expires_at" ]]' in text
    assert "describe_time_to_live:true" in text
    for receipt_field in (
        "outside_table_get_item:true",
        "outside_table_put_item:true",
        "outside_table_update_item:true",
        "outside_table_transact_write_items:true",
    ):
        assert receipt_field in text
    assert text.count("dynamodb get-item") == 2
    assert text.count("dynamodb put-item") == 2
    assert text.count("dynamodb update-item") == 2
    assert text.count("dynamodb transact-write-items") == 2
    assert "outside_key=" in text
    assert "outside_item=" in text
    assert "outside_transaction=" in text


def test_smoke_binds_execution_to_exact_current_main_commit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert '[[ "${GITHUB_REF}" != "refs/heads/main" ]]' in text
    assert '[[ "${RELEASE_SHA}" != "${GITHUB_SHA}" ]]' in text
    assert '[[ "$(git rev-parse HEAD)" != "${GITHUB_SHA}" ]]' in text
    assert "git merge-base --is-ancestor" not in text
    assert "git fetch --no-tags origin main" not in text


def test_smoke_redacts_denials_and_clears_credentials_before_upload() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'if "$@" >"${denial_error}" 2>&1; then' in text
    assert "grep -Eqi 'AccessDenied|not authorized'" in text
    assert 'rm -f "${denial_error}"' in text
    assert text.index("Clear temporary AWS credentials") < text.index(
        "Upload redacted smoke evidence"
    )
    assert "id: clear_credentials" in text
    assert "steps.clear_credentials.outcome == 'success'" in text
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
