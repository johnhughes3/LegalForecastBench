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
GITHUB_ROOT = ROOT / ".github"
WORKFLOW = (ROOT / ".github/workflows/dependabot-auto-merge.yaml").read_text(
    encoding="utf-8",
)
CI_RUNNER_CLAMP = (
    "runs-on: ${{ (vars.CI_RUNNER == 'ubuntu-latest' || "
    "startsWith(vars.CI_RUNNER, 'ubicloud-')) && vars.CI_RUNNER || "
    "'ubicloud-standard-2' }}"
)
DEPENDABOT = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
FETCH_METADATA_SHA = "25dd0e34f4fe68f24cc83900b1fe3fe149efef98"
PROVIDER_CONTRACT_DEPENDENCIES = ("anthropic", "claude-agent-sdk", "openai")

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


def test_dependabot_ignores_provider_contract_dependencies() -> None:
    for dependency_name in PROVIDER_CONTRACT_DEPENDENCIES:
        assert DEPENDABOT.count(f"- dependency-name: {dependency_name}") == 1


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
    assert CI_RUNNER_CLAMP in WORKFLOW
    assert "vars.CI_RUNNER" in WORKFLOW
    assert "runs-on: ${{ vars.CI_RUNNER }}" not in WORKFLOW
    assert "runs-on: ubuntu-latest" not in WORKFLOW
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


def test_external_actions_use_immutable_commit_pins() -> None:
    mutable_uses: list[str] = []
    uses_pattern = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)

    for action_path in sorted(GITHUB_ROOT.rglob("*.y*ml")):
        for use in uses_pattern.findall(action_path.read_text(encoding="utf-8")):
            if use.startswith(("./", "docker://")):
                continue
            _, separator, revision = use.rpartition("@")
            if separator != "@" or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
                mutable_uses.append(f"{action_path.relative_to(ROOT)}: {use}")

    assert not mutable_uses, (
        "external GitHub Actions must use immutable 40-character commit pins: "
        + ", ".join(mutable_uses)
    )


def test_dependabot_auto_merge_workflow_gates_the_trusted_source() -> None:
    resolve = _step_run("Resolve Dependabot pull request")
    assert 'select(.user.login=="dependabot[bot]"' in resolve
    assert '.state=="open"' in resolve
    assert ".draft!=true" in resolve
    assert '.base.ref=="main"' in resolve
    assert ".head.sha==" in resolve
    assert '[ "${count}" -ne 1 ]' in resolve
    assert "skip=true" in resolve
    assert "skip=false" in resolve


def test_dependabot_auto_merge_workflow_queues_only_non_major_updates() -> None:
    classify = _step_run("Classify dependencies and update type")
    assert "DEPENDENCY_NAMES" in classify
    for dependency_name in PROVIDER_CONTRACT_DEPENDENCIES:
        assert dependency_name in classify
    assert "version-update:semver-patch|version-update:semver-minor" in classify
    assert "eligible=true" in classify
    assert "eligible=false" in classify
    assert "Skipping auto-merge for update-type=" in classify
    assert "version-update:semver-major" not in classify.split("case", maxsplit=1)[1]


def test_dependabot_auto_merge_workflow_requires_complete_non_failing_checks() -> None:
    gates = _step_run(
        "Require every check on the head SHA to be complete and non-failing"
    )
    assert 'gh api "repos/${REPO}/commits/${SHA}/check-runs" --paginate --jq' in gates
    assert '.status != "completed"' in gates
    assert 'name=="Python quality gates"' in gates
    assert '.conclusion != "success"' in gates
    assert '.conclusion != "neutral"' in gates
    assert '.conclusion != "skipped"' in gates
    assert "ok=false" in gates
    assert "ok=true" in gates
    assert "exit 0" in gates
    merge = _step_run("Enable auto-merge (squash)")
    assert (
        'gh pr merge "$PR" --repo "$REPO" --auto --squash --match-head-commit "$SHA"'
        in merge
    )
    assert "--admin" not in merge


def test_dependabot_auto_merge_workflow_disables_stale_ineligible_requests() -> None:
    disable_step = WORKFLOW.split(
        "      - name: Disable stale auto-merge for ineligible updates\n",
        maxsplit=1,
    )[1].split("\n      - name:", maxsplit=1)[0]

    assert "if: always() && steps.pr.outputs.skip != 'true'" in disable_step
    assert "steps.class.outputs.eligible != 'true'" in disable_step
    assert "steps.gates.outputs.ok != 'true'" in disable_step
    assert "--json autoMergeRequest" in disable_step
    assert "--jq '.autoMergeRequest != null'" in disable_step
    assert 'gh pr merge --disable-auto --repo "$REPO" "$PR"' in disable_step


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
        script=_step_run("Classify dependencies and update type"),
        env={"DEPENDENCY_NAMES": "cryptography", "UPDATE_TYPE": update_type},
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == f"eligible={eligible}\n"
    if eligible == "false":
        assert f"Skipping auto-merge for update-type='{update_type}'" in result.stdout


@pytest.mark.parametrize(
    "dependency_names",
    [
        "anthropic",
        "claude-agent-sdk",
        "openai",
        "cryptography, openai",
        "OPENAI",
    ],
)
def test_classifier_never_auto_lands_provider_contract_dependencies(
    tmp_path: Path,
    dependency_names: str,
) -> None:
    result = _run_snippet(
        tmp_path,
        script=_step_run("Classify dependencies and update type"),
        env={
            "DEPENDENCY_NAMES": dependency_names,
            "UPDATE_TYPE": "version-update:semver-patch",
        },
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "eligible=false\n"
    assert "Skipping auto-merge for provider-contract dependencies=" in result.stdout


def _dependabot_pr(
    *,
    number: int,
    sha: str,
    login: str = "dependabot[bot]",
    state: str = "open",
    draft: bool = False,
    base: str = "main",
) -> dict[str, object]:
    return {
        "number": number,
        "state": state,
        "draft": draft,
        "user": {"login": login},
        "head": {"sha": sha},
        "base": {"ref": base},
    }


@requires_jq
def test_resolver_selects_open_dependabot_pr_for_exact_sha(tmp_path: Path) -> None:
    sha = "a" * 40
    payload = [
        _dependabot_pr(number=12, sha=sha),
        _dependabot_pr(number=13, sha=sha, login="someone-else"),
        _dependabot_pr(number=14, sha=sha, base="release"),
        _dependabot_pr(number=15, sha=sha, draft=True),
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
    payload = [_dependabot_pr(number=14, sha=sha, state="closed")]
    result = _run_snippet(
        tmp_path,
        script=_step_run("Resolve Dependabot pull request"),
        env={"REPO": "johnhughes3/LegalForecastBench", "SHA": sha},
        gh_json=json.dumps(payload),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "skip=true\n"
    assert f"Expected exactly one open Dependabot PR for {sha} on main; found 0" in (
        result.stdout
    )


@requires_jq
def test_resolver_skips_when_multiple_main_dependabot_prs_match(
    tmp_path: Path,
) -> None:
    sha = "d" * 40
    payload = [
        _dependabot_pr(number=21, sha=sha),
        _dependabot_pr(number=22, sha=sha),
    ]
    result = _run_snippet(
        tmp_path,
        script=_step_run("Resolve Dependabot pull request"),
        env={"REPO": "johnhughes3/LegalForecastBench", "SHA": sha},
        gh_json=json.dumps(payload),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "skip=true\n"
    assert f"Expected exactly one open Dependabot PR for {sha} on main; found 2" in (
        result.stdout
    )


def _check(name: str, status: str, conclusion: str | None) -> dict[str, str | None]:
    return {"name": name, "status": status, "conclusion": conclusion}


PYTHON_OK = _check("Python quality gates", "completed", "success")


@requires_jq
@pytest.mark.parametrize(
    ("check_runs", "ok", "notice"),
    [
        (
            [_check("Analyze python", "in_progress", None)],
            "false",
            "Not merging: pending=1 python_ok=0 failed=0",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "in_progress", None)],
            "false",
            "Not merging: pending=1 python_ok=1 failed=0",
        ),
        (
            [_check("Analyze python", "completed", "success")],
            "false",
            "Not merging: pending=0 python_ok=0 failed=0",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "completed", "failure")],
            "false",
            "Not merging: pending=0 python_ok=1 failed=1",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "completed", "cancelled")],
            "false",
            "Not merging: pending=0 python_ok=1 failed=1",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "completed", "timed_out")],
            "false",
            "Not merging: pending=0 python_ok=1 failed=1",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "completed", "startup_failure")],
            "false",
            "Not merging: pending=0 python_ok=1 failed=1",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "completed", "action_required")],
            "false",
            "Not merging: pending=0 python_ok=1 failed=1",
        ),
        (
            [PYTHON_OK, _check("Analyze python", "completed", "stale")],
            "false",
            "Not merging: pending=0 python_ok=1 failed=1",
        ),
        (
            [
                PYTHON_OK,
                _check("Analyze python", "completed", "neutral"),
                _check("CodeQL", "completed", "skipped"),
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
