from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "annotation",
    [
        "% TODO: revise abstract",
        "  % TODO revise abstract",
        r"\draft{provisional}",
        r"\checkcite{citation}",
        r"\checknum{number}",
        r"\todo[inline]{unfinished}",
    ],
)
def test_release_build_rejects_unresolved_annotations(
    tmp_path: Path, annotation: str
) -> None:
    result = _build_preview(tmp_path, annotation)
    assert result.returncode == 1
    assert "Resolve the draft annotations" in result.stderr
    assert not (tmp_path / "compiled").exists()


def test_release_build_allows_resolved_manuscript(tmp_path: Path) -> None:
    result = _build_preview(tmp_path, "% Ordinary comment\nSettled prose.")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "compiled").exists()


def test_paper_workflow_does_not_push_the_pdf() -> None:
    workflow = (ROOT / ".github" / "workflows" / "paper.yaml").read_text(
        encoding="utf-8"
    )
    assert "git push" not in workflow
    assert "contents: write" not in workflow
    assert "cmp -s" in workflow


def test_pdf_date_comes_from_the_manuscript(tmp_path: Path) -> None:
    result = _build_preview(
        tmp_path,
        "\\date{Working paper --- September 29, 2026}\nSettled prose.\n",
        record_epoch=True,
        source_date_epoch=None,
    )
    assert result.returncode == 0, result.stderr
    expected = str(int(datetime(2026, 9, 29, tzinfo=UTC).timestamp()))
    assert (tmp_path / "epoch").read_text(encoding="utf-8").strip() == expected


def test_container_build_retries_a_stalled_image_pull(tmp_path: Path) -> None:
    paper_dir = tmp_path / "docs" / "paper"
    paper_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "paper" / "build.sh", paper_dir / "build.sh")
    shutil.copy2(
        ROOT / "docs" / "paper" / "texlive-image.txt", paper_dir / "texlive-image.txt"
    )
    log = tmp_path / "docker.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    timeout_cmd = bin_dir / "timeout"
    timeout_cmd.write_text(
        '#!/usr/bin/env bash\nwhile [[ $1 == -* ]]; do shift; done\nshift\nexec "$@"\n'
    )
    timeout_cmd.chmod(0o755)
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$1" >> "$PAPER_TEST_DOCKER_LOG"\n'
        "if [[ $1 == pull ]]; then\n"
        '  pulls=$(grep -c "^pull$" "$PAPER_TEST_DOCKER_LOG")\n'
        "  if [[ $pulls -lt 2 ]]; then exit 124; fi\n"
        "  exit 0\n"
        "fi\n"
        'if [[ $1 == run ]]; then touch "$PAPER_TEST_COMPILED"; exit 0; fi\n'
        "exit 1\n"
    )
    docker.chmod(0o755)
    result = subprocess.run(
        ["bash", str(paper_dir / "build.sh"), "--container"],
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "SOURCE_DATE_EPOCH": "1",
            "PAPER_IMAGE_PULL_BACKOFF_SECONDS": "0",
            "PAPER_TEST_DOCKER_LOG": str(log),
            "PAPER_TEST_COMPILED": str(tmp_path / "compiled"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "pull",
        "pull",
        "info",
        "run",
    ]
    assert "attempt 1 did not finish" in result.stderr
    assert (tmp_path / "compiled").exists()


def test_container_build_runs_as_mapped_root_under_rootless_docker(
    tmp_path: Path,
) -> None:
    paper_dir = tmp_path / "docs" / "paper"
    paper_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "paper" / "build.sh", paper_dir / "build.sh")
    shutil.copy2(
        ROOT / "docs" / "paper" / "texlive-image.txt", paper_dir / "texlive-image.txt"
    )
    args = tmp_path / "run-args"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "case $1 in\n"
        "  pull) exit 0 ;;\n"
        '  info) echo "[name=seccomp,profile=builtin name=rootless]"; exit 0 ;;\n'
        '  run) printf "%s\\n" "$@" > "$PAPER_TEST_RUN_ARGS"; exit 0 ;;\n'
        "esac\n"
        "exit 1\n"
    )
    docker.chmod(0o755)
    result = subprocess.run(
        ["bash", str(paper_dir / "build.sh"), "--container"],
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "SOURCE_DATE_EPOCH": "1",
            "PAPER_TEST_RUN_ARGS": str(args),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    run_args = args.read_text(encoding="utf-8").splitlines()
    assert run_args[run_args.index("--user") + 1] == "0:0"


def test_pdf_date_requires_a_manuscript_date(tmp_path: Path) -> None:
    result = _build_preview(tmp_path, "Settled prose.\n", source_date_epoch=None)
    assert result.returncode == 1
    assert "manuscript needs a" in result.stderr
    assert not (tmp_path / "compiled").exists()


def test_publish_working_copy_commits_only_a_changed_pdf(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    paper_dir = repo / "docs" / "paper"
    build_dir = paper_dir / "build"
    build_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "paper" / "publish-working-copy.sh", paper_dir)
    pdf = build_dir / "LegalForecastBench-paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfirst\n")
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("")
    (tmp_path / "home").mkdir()
    env = {
        **os.environ,
        "CI": "true",
        "HOME": str(tmp_path / "home"),
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_SYSTEM": str(gitconfig),
    }
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, env=env)
    first = _publish(repo, env)
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == "UPDATED"
    assert (
        repo / "site" / "public" / "paper" / "legalforecastbench-working.pdf"
    ).read_bytes() == pdf.read_bytes()
    second = _publish(repo, env)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "UNCHANGED"
    pdf.write_bytes(b"%PDF-1.4\nsecond\n")
    third = _publish(repo, env)
    assert third.returncode == 0, third.stderr
    assert third.stdout.strip() == "UPDATED"
    log = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert log.stdout.strip() == "2"


def _publish(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "docs" / "paper" / "publish-working-copy.sh")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _build_preview(
    tmp_path: Path,
    manuscript: str,
    *,
    record_epoch: bool = False,
    source_date_epoch: str | None = "1",
) -> subprocess.CompletedProcess[str]:
    paper_dir = tmp_path / "docs" / "paper"
    paper_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "paper" / "build.sh", paper_dir / "build.sh")
    (paper_dir / "LegalForecastBench-paper.tex").write_text(manuscript)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    compiler = bin_dir / "latexmk"
    recorder = (
        'printf "%s\\n" "$SOURCE_DATE_EPOCH" > "$PAPER_TEST_EPOCH"\n'
        if record_epoch
        else ""
    )
    compiler.write_text(
        f'#!/usr/bin/env bash\n{recorder}touch "$PAPER_TEST_COMPILED"\n'
    )
    compiler.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PAPER_TEST_COMPILED": str(tmp_path / "compiled"),
        "PAPER_TEST_EPOCH": str(tmp_path / "epoch"),
    }
    if source_date_epoch is not None:
        env["SOURCE_DATE_EPOCH"] = source_date_epoch
    else:
        env.pop("SOURCE_DATE_EPOCH", None)
    return subprocess.run(
        ["bash", str(paper_dir / "build.sh"), "--release"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
