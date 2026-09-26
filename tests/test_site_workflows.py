"""Exercise the CI classifier and public site artifact boundary."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / ".github/scripts/classify-python-changes.sh"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["site/src/index.ts"], "false"),
        (["site/src/index.ts", "legalforecast/scoring.py"], "true"),
        (["docs/schemas/site-export-v1.schema.json"], "true"),
        (["pnpm-lock.yaml"], "true"),
    ],
)
def test_python_classifier_skips_only_frontend_changes(
    tmp_path: Path, changed: list[str], expected: str
) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(
        tmp_path, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "base"
    )
    base = _git(tmp_path, "rev-parse", "HEAD")
    for name in changed:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-m", "change")
    output = tmp_path / "output"
    subprocess.run(
        ["bash", str(CLASSIFIER)],
        cwd=tmp_path,
        env={
            **os.environ,
            "EVENT_NAME": "pull_request",
            "BASE_SHA": base,
            "HEAD_SHA": "HEAD",
            "GITHUB_OUTPUT": str(output),
        },
        check=True,
    )
    assert output.read_text() == f"run_python={expected}\n"


def test_python_classifier_runs_for_dispatch_without_a_base(tmp_path: Path) -> None:
    output = tmp_path / "output"
    subprocess.run(
        ["bash", str(CLASSIFIER)],
        cwd=ROOT,
        env={
            **os.environ,
            "EVENT_NAME": "workflow_dispatch",
            "BASE_SHA": "",
            "HEAD_SHA": "HEAD",
            "GITHUB_OUTPUT": str(output),
        },
        check=True,
    )
    assert output.read_text() == "run_python=true\n"


def test_site_export_consumes_only_successful_published_source() -> None:
    producer = (ROOT / ".github/workflows/fan-in-publish.yaml").read_text()
    source_step = producer.split("- name: Upload published site export inputs", 1)[1]
    source_step = source_step.split("- name:", 1)[0]
    assert "if: ${{ inputs.publish }}" in source_step
    assert (
        "name: site-source-${{ github.run_id }}-${{ github.run_attempt }}"
        in source_step
    )
    assert producer.index("- name: Publish verified report once") < producer.index(
        "- name: Prepare published site export inputs"
    )
    workflow = (ROOT / ".github/workflows/site-export.yaml").read_text()
    for guard in (
        "workflow_run.conclusion == 'success'",
        "workflow_run.event == 'workflow_dispatch'",
        "workflow_run.path == '.github/workflows/fan-in-publish.yaml'",
        "workflow_run.head_branch == 'main'",
        "workflow_run.head_repository.full_name == github.repository",
    ):
        assert guard in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "id-token: write" not in workflow
    assert "secrets." not in workflow
    assert "--scores /tmp/lfb-site-source/scores.json" in workflow
    assert "--model-registry /tmp/lfb-site-source/model-registry.json" in workflow
    assert "path: /tmp/lfb-site/site-export.json" in workflow
    assert "steps.source.outputs.found == 'true'" in workflow


@pytest.mark.parametrize(
    ("listing", "expected", "succeeds"),
    [
        ("", "false", True),
        ("site-source-123-1\tfalse\n", "true", True),
        ("site-source-123-1\ttrue\n", "", False),
        (
            "site-source-123-1\tfalse\nsite-source-123-1\tfalse\n",
            "",
            False,
        ),
    ],
)
def test_published_source_lookup_handles_missing_and_expired_artifacts(
    tmp_path: Path, listing: str, expected: str, succeeds: bool
) -> None:
    import textwrap

    workflow = (ROOT / ".github/workflows/site-export.yaml").read_text()
    section = workflow.split("- name: Find the published source artifact", 1)[1]
    script = textwrap.dedent(
        section.split("run: |\n", 1)[1].split("\n      - name:", 1)[0]
    )
    # Keep workflow temporary files isolated under xdist.
    script = script.replace("/tmp/site-artifacts.tsv", str(tmp_path / "artifacts.tsv"))
    fake_gh = tmp_path / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\nprintf "%s" "$ARTIFACT_LISTING"\n')
    fake_gh.chmod(0o755)
    output = tmp_path / "output"
    result = subprocess.run(
        ["bash", "-c", script],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "ARTIFACT_LISTING": listing,
            "SOURCE_REPOSITORY": "example/benchmark",
            "SOURCE_RUN_ID": "123",
            "SOURCE_ATTEMPT": "1",
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        },
        check=False,
    )
    assert (result.returncode == 0) is succeeds
    if succeeds:
        assert output.read_text() == f"found={expected}\n"
