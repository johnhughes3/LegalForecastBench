from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/community-multiharness-validation.yaml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def test_community_workflow_triggers_on_relevant_public_surfaces() -> None:
    assert WORKFLOW.startswith("name: Community Multi-Harness Validation\n")
    assert "pull_request:" in WORKFLOW
    assert "push:" in WORKFLOW
    assert "branches: [main]" in WORKFLOW
    for path_filter in (
        "community/submissions/**",
        "legalforecast/multiharness/**",
        "legalforecast/publication/community_aggregate.py",
        "tests/test_community_*.py",
        "tests/test_multiharness_*.py",
    ):
        assert path_filter in WORKFLOW


def test_community_workflow_uses_read_only_permissions_and_no_official_boundary() -> (
    None
):
    assert "permissions:\n  contents: read" in WORKFLOW
    assert "id-token: write" not in WORKFLOW
    assert "environment:" not in WORKFLOW
    assert "legalforecastbench-official-eval" not in WORKFLOW
    assert "aws-actions/configure-aws-credentials" not in WORKFLOW
    for forbidden in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "LFB_PACKET_BUCKET",
        "LFB_RESULTS_BUCKET",
        "secrets.",
    ):
        assert forbidden not in WORKFLOW


def test_community_workflow_runs_relevant_quality_and_validation_steps() -> None:
    assert "uv sync --locked" in WORKFLOW
    assert "uv run ruff format --check" in WORKFLOW
    assert "uv run ruff check" in WORKFLOW
    assert "uv run pyright" in WORKFLOW
    assert "tests/test_multiharness_cli.py" in WORKFLOW
    assert "tests/test_community_submission.py" in WORKFLOW
    assert "tests/test_community_publication.py" in WORKFLOW
    assert "tests/test_community_multiharness_workflow.py" in WORKFLOW
    assert "validate_submission_file(path)" in WORKFLOW
    assert "PublicationGuardrailConfig(public_paths=roots)" in WORKFLOW


def test_community_workflow_plans_and_builds_aggregate_without_credentials() -> None:
    assert "community aggregate" in WORKFLOW
    assert "--submissions-dir community/submissions" in WORKFLOW
    assert "--output-dir tmp/community-aggregate-plan" in WORKFLOW
    assert "--dry-run" in WORKFLOW
    assert "publish-community-static-site:" in WORKFLOW
    assert "github.event_name == 'push'" in WORKFLOW
    assert "--output-dir tmp/community-site" in WORKFLOW
    assert "actions/upload-artifact@v7" in WORKFLOW
    assert "community-multiharness-static-site" in WORKFLOW
