from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/dependabot-auto-merge.yaml").read_text(
    encoding="utf-8",
)
DEPENDABOT = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
FETCH_METADATA_SHA = "25dd0e34f4fe68f24cc83900b1fe3fe149efef98"

requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="jq is required to execute the workflow bash snippets",
)


@dataclass(frozen=True)
class SnippetResult:
    returncode: int
    stdout: str
    stderr: str
    github_output: str


def _step_run(name: str) -> str:
    marker = f"      - name: {name}\n"
    assert marker in WORKFLOW, f"missing step {name!r}"
    rest = WORKFLOW.split(marker, maxsplit=1)[1]
    run_block = rest.split("        run: |\n", maxsplit=1)[1]
    if "\n      - name:" in run_block:
        run_block = run_block.split("\n      - name:", maxsplit=1)[0]
    return textwrap.dedent(run_block)


_GH_STUB = r"""#!/usr/bin/env bash
set -euo pipefail
jq_filter=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --jq)
      jq_filter="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
if [ -n "${jq_filter}" ]; then
  printf '%s\n' "${FAKE_GH_JSON}" | jq -r "${jq_filter}"
else
  printf '%s\n' "${FAKE_GH_JSON}"
fi
"""


def _run_snippet(
    tmp_path: Path,
    *,
    script: str,
    env: dict[str, str],
    gh_json: str = "",
) -> SnippetResult:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(_GH_STUB, encoding="utf-8")
    fake_gh.chmod(0o755)
    github_output = tmp_path / "github-output"
    result = subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        env={
            **os.environ,
            **env,
            "FAKE_GH_JSON": gh_json,
            "GITHUB_OUTPUT": str(github_output),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
        text=True,
    )
    return SnippetResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        github_output=(
            github_output.read_text(encoding="utf-8") if github_output.exists() else ""
        ),
    )


def test_dependabot_groups_restrict_minor_and_patch() -> None:
    assert "package-ecosystem: github-actions" in DEPENDABOT
    assert "package-ecosystem: pip" in DEPENDABOT
    assert "github-actions-minor-patch:" in DEPENDABOT
    assert "pip-minor-patch:" in DEPENDABOT
    assert DEPENDABOT.count("update-types:") == 2
    assert DEPENDABOT.count("- minor") == 2
    assert DEPENDABOT.count("- patch") == 2
    assert DEPENDABOT.count("open-pull-requests-limit: 5") == 2
    assert "major" not in DEPENDABOT


def test_dependabot_auto_merge_workflow_uses_default_branch_workflow_run() -> None:
    assert WORKFLOW.startswith("name: Dependabot auto-merge\n")
    assert "workflow_run:" in WORKFLOW
    assert "types: [completed]" in WORKFLOW
    assert "- CI\n" in WORKFLOW
    assert "- CodeQL\n" in WORKFLOW
    assert "- Community Multi-Harness Validation\n" in WORKFLOW
    assert "pull_request_target:" not in WORKFLOW
    assert re.search(r"^on:\n  pull_request:", WORKFLOW, re.MULTILINE) is None
    assert "github.event.workflow_run.event == 'pull_request'" in WORKFLOW
    assert "github.event.workflow_run.conclusion == 'success'" in WORKFLOW
    assert "github.event.workflow_run.name != 'Dependabot auto-merge'" in WORKFLOW
    assert (
        "github.event.workflow_run.head_repository.full_name == github.repository"
        in WORKFLOW
    )
    assert "runs-on: ubuntu-latest" in WORKFLOW
    assert "vars.CI_RUNNER" in WORKFLOW
    assert "runs-on: ${{ vars.CI_RUNNER }}" not in WORKFLOW
    assert "actions/checkout" not in WORKFLOW
    assert "--admin" not in WORKFLOW
    assert "gh pr merge --admin" not in WORKFLOW


def test_dependabot_auto_merge_workflow_is_narrowly_privileged() -> None:
    assert (
        "permissions:\n"
        "  actions: read\n"
        "  checks: read\n"
        "  contents: read\n"
        "  pull-requests: read\n"
    ) in WORKFLOW
    assert "contents: write" in WORKFLOW
    assert "pull-requests: write" in WORKFLOW
    assert WORKFLOW.index("contents: read") < WORKFLOW.index("contents: write")


def test_dependabot_auto_merge_pins_fetch_metadata() -> None:
    uses = re.findall(r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", WORKFLOW, re.MULTILINE)
    assert uses == [f"dependabot/fetch-metadata@{FETCH_METADATA_SHA}"]
    assert "# v3.1.0" in WORKFLOW
    assert "pr-number: ${{ steps.pr.outputs.number }}" in WORKFLOW


def test_dependabot_auto_merge_workflow_gates_the_trusted_source() -> None:
    resolve = _step_run("Resolve Dependabot pull request")
    assert 'select(.user.login=="dependabot[bot]"' in resolve
    assert '.state=="open"' in resolve
    assert ".head.sha==" in resolve
    assert "skip=true" in resolve
    assert "skip=false" in resolve


def test_dependabot_auto_merge_workflow_queues_only_non_major_updates() -> None:
    classify = _step_run("Classify update-type")
    assert "version-update:semver-patch|version-update:semver-minor" in classify
    assert "eligible=true" in classify
    assert "eligible=false" in classify
    assert "Skipping auto-merge for update-type=" in classify
    assert "version-update:semver-major" not in classify.split("case", maxsplit=1)[1]


def test_dependabot_auto_merge_workflow_requires_complete_non_failing_checks() -> None:
    gates = _step_run(
        "Require every check on the head SHA to be complete and non-failing"
    )
    assert 'gh api "repos/${REPO}/commits/${SHA}/check-runs" --paginate' in gates
    assert '.status != "completed"' in gates
    assert 'conclusion=="failure"' in gates
    assert 'conclusion=="cancelled"' in gates
    assert 'conclusion=="timed_out"' in gates
    assert 'conclusion=="startup_failure"' in gates
    assert "ok=false" in gates
    assert "ok=true" in gates
    assert "exit 0" in gates
    merge = _step_run("Enable auto-merge (squash)")
    assert 'gh pr merge "$PR" --repo "$REPO" --auto --squash' in merge
    assert "--admin" not in merge


@pytest.mark.parametrize(
    ("update_type", "eligible"),
    [
        ("version-update:semver-patch", "true"),
        ("version-update:semver-minor", "true"),
        ("version-update:semver-major", "false"),
        ("", "false"),
        ("version-update:unknown", "false"),
    ],
)
def test_classifier_auto_lands_only_explicit_patch_and_minor(
    tmp_path: Path,
    update_type: str,
    eligible: str,
) -> None:
    result = _run_snippet(
        tmp_path,
        script=_step_run("Classify update-type"),
        env={"UPDATE_TYPE": update_type},
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == f"eligible={eligible}\n"
    if eligible == "false":
        assert f"Skipping auto-merge for update-type='{update_type}'" in result.stdout


@requires_jq
def test_resolver_selects_open_dependabot_pr_for_exact_sha(tmp_path: Path) -> None:
    sha = "a" * 40
    payload = [
        {
            "number": 12,
            "state": "open",
            "user": {"login": "dependabot[bot]"},
            "head": {"sha": sha},
        },
        {
            "number": 13,
            "state": "open",
            "user": {"login": "someone-else"},
            "head": {"sha": sha},
        },
    ]
    result = _run_snippet(
        tmp_path,
        script=_step_run("Resolve Dependabot pull request"),
        env={"REPO": "johnhughes3/LegalForecastBench", "SHA": sha},
        gh_json=json.dumps(payload),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "number=12\nskip=false\n"


@requires_jq
def test_resolver_skips_when_no_open_dependabot_pr_matches_sha(tmp_path: Path) -> None:
    sha = "b" * 40
    payload = [
        {
            "number": 14,
            "state": "closed",
            "user": {"login": "dependabot[bot]"},
            "head": {"sha": sha},
        }
    ]
    result = _run_snippet(
        tmp_path,
        script=_step_run("Resolve Dependabot pull request"),
        env={"REPO": "johnhughes3/LegalForecastBench", "SHA": sha},
        gh_json=json.dumps(payload),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "skip=true\n"
    assert f"No open Dependabot PR for {sha}" in result.stdout


@requires_jq
@pytest.mark.parametrize(
    ("check_runs", "ok", "notice"),
    [
        (
            [{"status": "in_progress", "conclusion": None}],
            "false",
            "Not merging: pending=1 failed=0",
        ),
        (
            [{"status": "completed", "conclusion": "failure"}],
            "false",
            "Not merging: pending=0 failed=1",
        ),
        (
            [{"status": "completed", "conclusion": "cancelled"}],
            "false",
            "Not merging: pending=0 failed=1",
        ),
        (
            [{"status": "completed", "conclusion": "timed_out"}],
            "false",
            "Not merging: pending=0 failed=1",
        ),
        (
            [{"status": "completed", "conclusion": "startup_failure"}],
            "false",
            "Not merging: pending=0 failed=1",
        ),
        (
            [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "neutral"},
                {"status": "completed", "conclusion": "skipped"},
            ],
            "true",
            None,
        ),
    ],
)
def test_gates_require_complete_non_failing_check_runs(
    tmp_path: Path,
    check_runs: list[dict[str, str | None]],
    ok: str,
    notice: str | None,
) -> None:
    payload = {"check_runs": check_runs}
    result = _run_snippet(
        tmp_path,
        script=_step_run(
            "Require every check on the head SHA to be complete and non-failing"
        ),
        env={"REPO": "johnhughes3/LegalForecastBench", "SHA": "c" * 40},
        gh_json=json.dumps(payload),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == f"ok={ok}\n"
    if notice is not None:
        assert notice in result.stdout
