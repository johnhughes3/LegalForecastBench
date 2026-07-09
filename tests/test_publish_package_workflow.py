from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/publish-package.yaml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def test_publish_package_workflow_is_tag_triggered() -> None:
    assert WORKFLOW.startswith("name: Publish Python Package\n")
    assert "push:" in WORKFLOW
    assert "tags:" in WORKFLOW
    assert '"v*"' in WORKFLOW
    assert "workflow_dispatch:" in WORKFLOW


def test_publish_package_runs_only_after_release_check() -> None:
    assert "release-check:" in WORKFLOW
    assert "uv run scripts/release_check.py --output-dir tmp/release-check" in WORKFLOW
    assert "publish:" in WORKFLOW
    assert "needs: release-check" in WORKFLOW
    assert "github.event_name == 'push' || inputs.publish == true" in WORKFLOW


def test_publish_package_uses_trusted_publishing_and_records_hashes() -> None:
    assert "permissions:\n  contents: read" in WORKFLOW
    assert "contents: write" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "pypa/gh-action-pypi-publish@release/v1" in WORKFLOW
    assert "packages-dir: tmp/release-check/dist" in WORKFLOW
    assert "softprops/action-gh-release@v2" in WORKFLOW
    assert "tmp/release-check/package-artifact-hashes.json" in WORKFLOW
    assert "tmp/release-check/dist/package-artifact-hashes.json" not in WORKFLOW


def test_publish_package_workflow_does_not_use_official_eval_credentials() -> None:
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
    ):
        assert forbidden not in WORKFLOW
