"""Keep artifact archival inside the protected publication boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_artifact_archive_is_manual_protected_and_provider_free() -> None:
    workflow = (ROOT / ".github/workflows/archive-github-artifacts.yaml").read_text()
    assert "  workflow_dispatch:\n" in workflow
    assert "  schedule:" not in workflow
    assert "  push:" not in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
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
