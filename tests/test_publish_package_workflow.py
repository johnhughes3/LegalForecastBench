from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/publish-package.yaml"
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")
TRUSTED_PUBLISHING_DOC = ROOT / "docs/security/pypi-trusted-publishing.md"
CI_RUNNER_CLAMP = (
    "runs-on: ${{ (vars.CI_RUNNER == 'ubuntu-latest' || "
    "startsWith(vars.CI_RUNNER, 'ubicloud-')) && vars.CI_RUNNER || "
    "'ubicloud-standard-2' }}"
)


def test_publish_package_workflow_is_tag_triggered() -> None:
    assert WORKFLOW.startswith("name: Publish Python Package\n")
    assert "push:" in WORKFLOW
    assert "tags:" in WORKFLOW
    assert '"v*"' in WORKFLOW
    assert "workflow_dispatch:" not in WORKFLOW
    assert "inputs.publish" not in WORKFLOW


def test_publish_package_keeps_protected_pypi_job_on_github_hosted() -> None:
    assert CI_RUNNER_CLAMP in WORKFLOW
    assert "environment:\n      name: pypi" in WORKFLOW
    publish_job = WORKFLOW.split("  publish:\n", maxsplit=1)[1]
    assert "runs-on: ubuntu-latest" in publish_job
    assert "vars.CI_RUNNER" not in publish_job


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
    assert re.search(
        r"^\s*uses: pypa/gh-action-pypi-publish@[0-9a-f]{40}\s*$",
        WORKFLOW,
        flags=re.MULTILINE,
    )
    assert "packages-dir: tmp/release-check/dist" in WORKFLOW
    assert (
        "softprops/action-gh-release@3d0d9888cb7fd7b750713d6e236d1fcb99157228"
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


def test_publish_job_declines_a_non_tag_ref() -> None:
    """The tag-only trigger is backed by a guard on the job itself."""

    assert "if: startsWith(github.ref, 'refs/tags/v')" in WORKFLOW


def test_trusted_publisher_doc_matches_the_registered_claim_set() -> None:
    """The documented claim set is bound to the values PyPI actually matches.

    A trusted-publisher registration fails closed on any mismatch, and the
    mismatch surfaces only at upload time -- after a tag is pushed. Binding the
    doc to the workflow filename, the environment name, and the distribution
    name means a rename reddens here instead of at release.
    """

    doc = TRUSTED_PUBLISHING_DOC.read_text(encoding="utf-8")
    project_name = re.search(
        r'^name = "([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )

    assert project_name is not None
    for claim in (
        f"`{project_name.group(1)}`",
        "`LegalForecastBench`",
        f"`{WORKFLOW_PATH.name}`",
        "`pypi`",
    ):
        assert claim in doc
    # The owner claim is described rather than named: this repository is public
    # and AGENTS.md forbids committing account identifiers, so the doc points at
    # GitHub's ``repository_owner`` claim instead of a maintainer literal.
    assert "repository_owner" in doc
    assert "environment:\n      name: pypi" in WORKFLOW
    assert "startsWith(github.ref, 'refs/tags/v')" in doc


def test_trusted_publisher_doc_forbids_a_static_pypi_credential() -> None:
    """No API token may be reintroduced without contradicting the doc."""

    doc = TRUSTED_PUBLISHING_DOC.read_text(encoding="utf-8")

    assert "Adding a PyPI API token" in doc
    for forbidden in ("PYPI_API_TOKEN", "TWINE_PASSWORD", "password:"):
        assert forbidden not in WORKFLOW
