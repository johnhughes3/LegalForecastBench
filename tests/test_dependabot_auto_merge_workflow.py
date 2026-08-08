from __future__ import annotations

import json
import os
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

# The classifier tests execute the workflow's own bash snippet, which pipes
# through jq.  Only `gh` is stubbed, so jq must come from the host.  GitHub
# runners ship it; skip with a clear reason elsewhere rather than failing with
# an opaque bash error.
requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="jq is required to execute the workflow classifier snippet",
)


@dataclass(frozen=True)
class ClassifierResult:
    returncode: int
    stdout: str
    stderr: str
    github_output: str


def _classification_script() -> str:
    step = WORKFLOW.split(
        "      - name: Classify verified Dependabot update\n",
        maxsplit=1,
    )[1]
    run_block = step.split("        run: |\n", maxsplit=1)[1].split(
        "\n      - name:",
        maxsplit=1,
    )[0]
    return textwrap.dedent(run_block)


def _run_classifier(
    tmp_path: Path,
    *,
    commit_json: str,
) -> ClassifierResult:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"${FAKE_COMMIT_JSON}\"\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    github_output = tmp_path / "github-output"
    env = {
        **os.environ,
        "FAKE_COMMIT_JSON": commit_json,
        "GITHUB_OUTPUT": str(github_output),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PR_NUMBER": "408",
        "REPOSITORY": "johnhughes3/LegalForecastBench",
    }
    result = subprocess.run(
        ["bash", "-c", _classification_script()],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    return ClassifierResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        github_output=(
            github_output.read_text(encoding="utf-8") if github_output.exists() else ""
        ),
    )


def _commit_json(
    *, message: str, author: str = "dependabot[bot]", verified: bool = True
) -> str:
    return json.dumps({"author": author, "verified": verified, "message": message})


def _commits_json(*commits: str) -> str:
    return f"[{','.join(commits)}]"


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
    assert "pulls/${PR_NUMBER}/commits?per_page=2" in WORKFLOW
    assert ".author.login" in WORKFLOW
    assert ".commit.verification.verified" in WORKFLOW
    assert "must contain exactly one commit" in WORKFLOW
    assert "not a verified Dependabot commit" in WORKFLOW


def test_dependabot_auto_merge_workflow_queues_only_non_major_updates() -> None:
    assert "version-update:semver-patch" in WORKFLOW
    assert "version-update:semver-minor" in WORKFLOW
    assert "version-update:semver-major" in WORKFLOW
    assert "eligible=false" in WORKFLOW
    assert "steps.metadata.outputs.eligible == 'true'" in WORKFLOW
    assert "Unknown Dependabot update type" in WORKFLOW


@pytest.mark.parametrize(
    ("update_type", "eligible"),
    [
        ("version-update:semver-patch", "true"),
        ("version-update:semver-minor", "true"),
        ("version-update:semver-major", "false"),
    ],
)
@requires_jq
def test_classifier_handles_legacy_update_type_trailers(
    tmp_path: Path,
    update_type: str,
    eligible: str,
) -> None:
    result = _run_classifier(
        tmp_path,
        commit_json=_commits_json(
            _commit_json(message=f"Bump dependency\n\nupdate-type: {update_type}")
        ),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == f"eligible=false\neligible={eligible}\n"


@requires_jq
def test_classifier_marks_verified_uv_group_commit_without_trailers_ineligible(
    tmp_path: Path,
) -> None:
    result = _run_classifier(
        tmp_path,
        commit_json=_commits_json(
            _commit_json(
                message=(
                    "chore(deps): bump cryptography in the uv group\n\n"
                    "updated-dependencies:\n- dependency-name: cryptography\n"
                    "  dependency-version: 50.0.0\n  dependency-group: uv"
                )
            )
        ),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "eligible=false\neligible=false\n"
    assert "no update-type metadata; leaving auto-merge disabled" in result.stdout


@requires_jq
def test_classifier_marks_unknown_verified_update_type_ineligible(
    tmp_path: Path,
) -> None:
    result = _run_classifier(
        tmp_path,
        commit_json=_commits_json(
            _commit_json(
                message="Bump dependency\n\nupdate-type: version-update:unknown",
            )
        ),
    )

    assert result.returncode == 0, result.stderr
    assert result.github_output == "eligible=false\neligible=false\n"
    assert "Unknown Dependabot update type" in result.stdout


@pytest.mark.parametrize(
    "commit_json",
    [
        _commits_json(
            _commit_json(
                message="update-type: version-update:semver-patch", author="attacker"
            )
        ),
        _commits_json(
            _commit_json(
                message="update-type: version-update:semver-patch", verified=False
            )
        ),
        _commits_json(
            _commit_json(message="update-type: version-update:semver-patch"),
            _commit_json(message="update-type: version-update:semver-major"),
        ),
        "not-json",
    ],
)
@requires_jq
def test_classifier_rejects_untrusted_or_malformed_commit_evidence(
    tmp_path: Path,
    commit_json: str,
) -> None:
    result = _run_classifier(tmp_path, commit_json=commit_json)

    assert result.returncode != 0
    assert result.github_output == "eligible=false\n"


def test_dependabot_auto_merge_workflow_disables_stale_ineligible_requests() -> None:
    disable_step = WORKFLOW.split(
        "      - name: Disable stale auto-merge for ineligible updates\n",
        maxsplit=1,
    )[1].split("\n      - name:", maxsplit=1)[0]

    assert "if: always() && steps.metadata.outputs.eligible != 'true'" in disable_step
    assert "--json autoMergeRequest" in disable_step
    assert "--jq '.autoMergeRequest != null'" in disable_step
    assert 'if [[ "${auto_merge_enabled}" == "true" ]]; then' in disable_step
    assert 'gh pr merge --disable-auto "${PR_URL}"' in disable_step


def test_dependabot_auto_merge_workflow_skips_when_repo_setting_is_disabled() -> None:
    merge_step = WORKFLOW.split(
        "      - name: Enable auto-merge for patch and minor updates\n",
        maxsplit=1,
    )[1]

    assert "REPOSITORY: ${{ github.repository }}" in merge_step
    assert "PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in merge_step
    assert "set -euo pipefail" in merge_step
    assert "--jq '.allow_auto_merge'" in merge_step
    assert 'if [[ "${allow_auto_merge}" != "true" ]]; then' in merge_step
    assert "::notice::Repository auto-merge is disabled; skipping." in merge_step
    assert "exit 0" in merge_step
    assert "|| true" not in merge_step
    assert '--match-head-commit "${PR_HEAD_SHA}"' in merge_step
    assert merge_step.index("if [[") < merge_step.index("gh pr merge \\")
