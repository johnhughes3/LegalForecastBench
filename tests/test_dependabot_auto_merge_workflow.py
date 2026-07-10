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
    assert "uses:" not in WORKFLOW


def test_dependabot_auto_merge_workflow_gates_the_trusted_source() -> None:
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in WORKFLOW
    assert "github.repository == 'johnhughes3/LegalForecastBench'" in WORKFLOW
    assert "github.event.pull_request.base.ref == 'main'" in WORKFLOW
    assert "github.event.pull_request.draft == false" in WORKFLOW
    assert "pulls/${PR_NUMBER}/commits?per_page=1" in WORKFLOW
    assert ".author.login" in WORKFLOW
    assert ".commit.verification.verified" in WORKFLOW
    assert "not a verified Dependabot commit" in WORKFLOW


def test_dependabot_auto_merge_workflow_queues_only_non_major_updates() -> None:
    assert "version-update:semver-patch" in WORKFLOW
    assert "version-update:semver-minor" in WORKFLOW
    assert "version-update:semver-major" in WORKFLOW
    assert "eligible=false" in WORKFLOW
    assert "steps.metadata.outputs.eligible == 'true'" in WORKFLOW
    assert "Unknown Dependabot update type" in WORKFLOW
    assert 'gh pr merge --auto --squash "$PR_URL"' in WORKFLOW


def test_dependabot_auto_merge_workflow_skips_when_repo_setting_is_disabled() -> None:
    merge_step = WORKFLOW.split(
        "      - name: Enable auto-merge for patch and minor updates\n",
        maxsplit=1,
    )[1]

    assert "REPOSITORY: ${{ github.repository }}" in merge_step
    assert "set -euo pipefail" in merge_step
    assert "--jq '.allow_auto_merge'" in merge_step
    assert 'if [[ "${allow_auto_merge}" != "true" ]]; then' in merge_step
    assert "::notice::Repository auto-merge is disabled; skipping." in merge_step
    assert "exit 0" in merge_step
    assert "|| true" not in merge_step
    assert merge_step.index("if [[") < merge_step.index("gh pr merge --auto")
