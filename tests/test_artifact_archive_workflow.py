"""Keep artifact archival inside the protected publication boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


WORKFLOW = (ROOT / ".github/workflows/archive-github-artifacts.yaml").read_text()


def test_private_draft_access_is_scoped_to_protected_preservation_job() -> None:
    workflow = (ROOT / ".github/workflows/preserve-retained-package.yaml").read_text()
    defaults, job = workflow.split("jobs:\n", 1)
    assert "permissions:\n  contents: read" in defaults
    assert "github.ref == 'refs/heads/main'" in job
    assert "environment: legalforecastbench-official-eval-fan-in" in job
    assert "      contents: write\n      id-token: write" in job
    assert "persist-credentials: false" in job
    download, publication = job.split(
        "      - name: Assume protected storage role after validation", 1
    )
    assert "GH_TOKEN: ${{ github.token }}" in download
    assert "GH_TOKEN" not in publication
    assert "--sha256" in download and "--source-run-id" in download
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in publication
    assert "--upload-only" in publication


def test_every_result_producing_workflow_triggers_an_archive() -> None:
    triggers = WORKFLOW.split("  workflow_run:\n", 1)[1].split("types:", 1)[0]
    for path in (
        "run-benchmark.yaml",
        "recover-benchmark.yaml",
        "fan-in-publish.yaml",
        "score-terminal-release.yaml",
        "prepare-jev-summaries.yaml",
    ):
        source = (ROOT / ".github/workflows" / path).read_text()
        name = source.split("\n", 1)[0].removeprefix("name: ")
        assert "upload-artifact@" in source
        assert f"      - {name}\n" in triggers
    assert "types: [completed]" in WORKFLOW
    # Per-source-run groups: a shared group would replace pending archives.
    assert "group: archive-github-artifacts-${{ github.event.workflow_run.id" in (
        WORKFLOW
    )
    assert (
        "github.event.workflow_run.head_repository.full_name == github.repository"
        in WORKFLOW
    )
    assert (
        "SOURCE_RUN_ID: ${{ github.event.workflow_run.id || inputs.source_run_id }}"
        in WORKFLOW
    )
    assert WORKFLOW.count('${SOURCE_RUN_ID:+--source-run-id "$SOURCE_RUN_ID"}') == 2


def test_artifact_archive_is_protected_and_provider_free() -> None:
    workflow = WORKFLOW
    assert "  workflow_dispatch:\n" in workflow
    assert "  schedule:" not in workflow
    assert "  push:" not in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "environment: legalforecastbench-official-eval-fan-in" in workflow
    assert "persist-credentials: false" in workflow
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "id-token: write" in workflow
    assert "secrets." not in workflow
    assert '--repository "$SOURCE_REPOSITORY"' in workflow
    assert "SOURCE_REPOSITORY: ${{ github.repository }}" in workflow
    assert '--bucket "$LFB_RESULTS_BUCKET"' in workflow
    assert "legalforecast.artifact_archive" in workflow
    assert "role-duration-seconds: 3600" in workflow
    assert "timeout-minutes: 210" in workflow
    assert "timeout-minutes: 150" in workflow
    assert "timeout-minutes: 45" in workflow
    assert workflow.index("--download-only") < workflow.index(
        "configure-aws-credentials@"
    )
    assert workflow.index("configure-aws-credentials@") < workflow.index(
        "--upload-only"
    )
    assert "steps.download.outcome == 'failure'" in workflow
    assert "if: ${{ always() }}" in workflow
