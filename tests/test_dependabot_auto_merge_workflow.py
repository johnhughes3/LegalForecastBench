from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/dependabot-auto-merge.yaml").read_text(
    encoding="utf-8",
)


def test_dependabot_auto_merge_workflow_is_narrowly_privileged() -> None:
    assert WORKFLOW.startswith("name: Dependabot Auto-Merge\n")
    assert "pull_request:\n" in WORKFLOW
    assert "pull_request_target:" not in WORKFLOW
    assert "types: [opened, synchronize, reopened, ready_for_review]" in WORKFLOW
    assert "contents: write" in WORKFLOW
    assert "pull-requests: write" in WORKFLOW
    assert "actions/checkout" not in WORKFLOW


def test_dependabot_auto_merge_workflow_gates_the_trusted_source() -> None:
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in WORKFLOW
    assert "github.repository == 'johnhughes3/LegalForecastBench'" in WORKFLOW
    assert "github.event.pull_request.base.ref == 'main'" in WORKFLOW
    assert "github.event.pull_request.draft == false" in WORKFLOW
    assert (
        "dependabot/fetch-metadata@d7267f607e9d3fb96fc2fbe83e0af444713e90b7" in WORKFLOW
    )


def test_dependabot_auto_merge_workflow_queues_only_non_major_updates() -> None:
    assert "version-update:semver-patch" in WORKFLOW
    assert "version-update:semver-minor" in WORKFLOW
    assert "version-update:semver-major" not in WORKFLOW
    assert 'gh pr merge --auto --squash "$PR_URL"' in WORKFLOW
