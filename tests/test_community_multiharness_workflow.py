from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/community-multiharness-validation.yaml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")
CI_RUNNER_CLAMP = (
    "runs-on: ${{ (vars.CI_RUNNER == 'ubuntu-latest' || "
    "startsWith(vars.CI_RUNNER, 'ubicloud-')) && vars.CI_RUNNER || "
    "'ubicloud-standard-2' }}"
)


def _trigger_paths(event_name: str) -> tuple[str, ...]:
    lines = WORKFLOW.splitlines()
    start = lines.index(f"  {event_name}:")
    paths: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and line.startswith("  ") and not line.startswith("    "):
            break
        if line.startswith("      - "):
            paths.append(line.removeprefix("      - "))
    return tuple(paths)


def test_community_workflow_uses_ci_runner_clamp_with_ubicloud_fallback() -> None:
    assert WORKFLOW.count(CI_RUNNER_CLAMP) == 2
    assert "runs-on: ubuntu-latest" not in WORKFLOW
    assert "runs-on: ${{ vars.CI_RUNNER }}" not in WORKFLOW


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


def test_community_workflow_covers_both_adapter_fixture_namespaces() -> None:
    required_paths = {
        "examples/adapters/**",
        "tests/fixtures/local_cli_adapters/**",
        "tests/fixtures/claude_code/**",
        "tests/fixtures/codex_cli_adapter/**",
    }
    official_only_paths = {
        ".github/workflows/run-benchmark.yaml",
        ".github/workflows/fan-in-publish.yaml",
    }

    for event_name in ("pull_request", "push"):
        paths = set(_trigger_paths(event_name))
        assert required_paths <= paths
        assert not paths & official_only_paths


def test_community_workflow_runs_adapter_manifest_and_example_tests() -> None:
    for test_path in (
        "tests/test_community_examples.py",
        "tests/test_local_cli_adapter_manifest.py",
        "tests/test_local_cli_contracts.py",
        "tests/test_multiharness_claude_code_adapter.py",
        "tests/test_multiharness_codex_cli.py",
    ):
        assert test_path in WORKFLOW


def test_community_workflow_pins_actions_to_full_commit_shas() -> None:
    uses_lines = [
        line.strip()
        for line in WORKFLOW.splitlines()
        if line.strip().startswith("uses:")
    ]
    assert uses_lines
    for line in uses_lines:
        revision = line.split("@", maxsplit=1)[1].split(maxsplit=1)[0]
        assert re.fullmatch(r"[0-9a-f]{40}", revision), line


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
    assert (
        "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9" in WORKFLOW
    )
    assert "community-multiharness-static-site" in WORKFLOW
