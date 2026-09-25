from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("docker") is None
    or not os.environ.get("LFB_CLAUDE_CODE_RUNTIME_IMAGE"),
    reason="set LFB_CLAUDE_CODE_RUNTIME_IMAGE to run the built-image permission probe",
)
def test_built_runtime_uid_can_read_staged_solver_tree(tmp_path: Path) -> None:
    image = os.environ["LFB_CLAUDE_CODE_RUNTIME_IMAGE"]
    workspace = tmp_path / "workspace"
    documents = workspace / "documents"
    documents.mkdir(parents=True, mode=0o755)
    workspace.chmod(0o755)
    (workspace / "prompt.txt").write_text("authenticated prompt\n")
    (workspace / "prompt.txt").chmod(0o444)
    (documents / "opinion.txt").write_text("visible opinion\n")
    (documents / "opinion.txt").chmod(0o444)

    completed = subprocess.run(
        (
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--user",
            "65532:65532",
            "--mount",
            f"type=bind,src={workspace},dst=/workspace,readonly",
            "--entrypoint",
            "/bin/sh",
            image,
            "-eu",
            "-c",
            "cat /workspace/prompt.txt /workspace/documents/opinion.txt",
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "authenticated prompt\nvisible opinion\n"


@pytest.mark.skipif(
    shutil.which("docker") is None
    or not os.environ.get("LFB_CLAUDE_CODE_RUNTIME_IMAGE"),
    reason="set LFB_CLAUDE_CODE_RUNTIME_IMAGE to run the built-image mount probe",
)
def test_built_runtime_cannot_mutate_read_only_staged_submounts(
    tmp_path: Path,
) -> None:
    image = os.environ["LFB_CLAUDE_CODE_RUNTIME_IMAGE"]
    workspace = tmp_path / "workspace"
    documents = workspace / "documents"
    output = workspace / "output"
    documents.mkdir(parents=True, mode=0o755)
    output.mkdir(mode=0o777)
    workspace.chmod(0o755)
    prompt = workspace / "prompt.txt"
    opinion = documents / "opinion.txt"
    prompt.write_text("authenticated prompt\n")
    prompt.chmod(0o444)
    opinion.write_text("visible opinion\n")
    opinion.chmod(0o444)

    completed = subprocess.run(
        (
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--user",
            "0:0",
            "--mount",
            f"type=bind,src={workspace},dst=/workspace",
            "--mount",
            f"type=bind,src={prompt},dst=/workspace/prompt.txt,readonly",
            "--mount",
            f"type=bind,src={documents},dst=/workspace/documents,readonly",
            "--entrypoint",
            "/bin/sh",
            image,
            "-eu",
            "-c",
            "if chmod 0644 /workspace/prompt.txt; then exit 11; fi; "
            "if printf changed > /workspace/documents/opinion.txt; then exit 12; fi; "
            "printf output > /workspace/output/result.txt; "
            'test "$(cat /workspace/prompt.txt)" = "authenticated prompt"; '
            'test "$(cat /workspace/documents/opinion.txt)" = "visible opinion"; '
            'test "$(cat /workspace/output/result.txt)" = output',
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert prompt.read_text() == "authenticated prompt\n"
    assert opinion.read_text() == "visible opinion\n"
    assert (output / "result.txt").read_text() == "output"
