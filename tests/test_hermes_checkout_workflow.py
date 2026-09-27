"""Execute the workflow's pinned-tag guard against local Git remotes."""

import subprocess
import textwrap

import pytest

from test_terminal_paid_workflow import _job


@pytest.mark.parametrize("tag", ["correct", "missing", "wrong"])
def test_workflow_fetches_exact_tag_before_runtime_install(tmp_path, tag):
    terminal = _job("run-terminal", "run-openai")
    start = terminal.index("      - name: Verify pinned Hermes tag")
    end = terminal.index("      - name: Install locked Hermes", start)
    step = terminal[start:end]
    assert "inputs.execution_mode == 'hermes-agent'" in step
    script = textwrap.dedent(step.split("        run: |\n", 1)[1])
    assert "${{" not in script
    assert "refs/tags/v2026.9.24:refs/tags/v2026.9.24" in script

    def git(*args, cwd=tmp_path):
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

    remote = tmp_path / "remote"
    git("init", str(remote))
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-m",
        "pin",
        cwd=remote,
    )
    pin = git("rev-parse", "HEAD", cwd=remote)
    if tag == "wrong":
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "wrong",
            cwd=remote,
        )
    if tag != "missing":
        git("tag", "v2026.9.24", cwd=remote)
    git("clone", "--no-tags", str(remote), "hermes-runtime")
    git("checkout", "--detach", pin, cwd=tmp_path / "hermes-runtime")
    script = script.replace("f97608f178d1ffeca59860195ab7da295f7c8e5f", pin)
    result = subprocess.run(["bash", "-e", "-c", script], cwd=tmp_path, check=False)
    assert (result.returncode == 0) is (tag == "correct")
