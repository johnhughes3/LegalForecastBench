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
    assert "workflow_dispatch:" not in WORKFLOW
    assert "inputs.publish" not in WORKFLOW


def test_publish_package_runs_only_after_release_check() -> None:
    assert "release-check:" in WORKFLOW
    assert "uv run scripts/release_check.py --output-dir tmp/release-check" in WORKFLOW
    assert "publish:" in WORKFLOW
    assert "needs: release-check" in WORKFLOW


def test_publish_package_pins_actions_to_full_commit_shas() -> None:
    uses_lines = [
        line.strip()
        for line in WORKFLOW.splitlines()
        if line.strip().startswith("uses:")
    ]
    assert uses_lines
    for line in uses_lines:
        revision = line.split("@", maxsplit=1)[1].split(maxsplit=1)[0]
        assert len(revision) == 40
        assert all(character in "0123456789abcdef" for character in revision)


def test_publish_package_uses_trusted_publishing_and_records_hashes() -> None:
    assert "permissions:\n  contents: read" in WORKFLOW
    assert "contents: write" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert (
        "pypa/gh-action-pypi-publish@ba38be9e461d3875417946c167d0b5f3d385a247"
        in WORKFLOW
    )
    assert "packages-dir: tmp/release-check/dist" in WORKFLOW
    assert (
        "softprops/action-gh-release@718ea10b132b3b2eba29c1007bb80653f286566b"
        in WORKFLOW
    )
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
