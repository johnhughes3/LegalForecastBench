from __future__ import annotations

import os
import shutil
import subprocess
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


def test_paper_workflow_updates_the_pdf_only_on_main() -> None:
    workflow = (ROOT / ".github" / "workflows" / "paper.yaml").read_text(
        encoding="utf-8"
    )
    assert workflow.count("fetch-depth: 0") == 2
    publish = workflow.split("  publish:", 1)[1]
    assert "github.event_name != 'pull_request'" in publish
    assert "github.ref == 'refs/heads/main'" in publish


def test_build_refuses_a_shallow_checkout(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    env = _git_env(tmp_path)
    subprocess.run(["git", "init", "-b", "main", str(origin)], check=True, env=env)
    paper = origin / "docs" / "paper"
    paper.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "paper" / "build.sh", paper / "build.sh")
    (paper / "LegalForecastBench-paper.tex").write_text(
        "Settled prose.\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(origin), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(origin), "commit", "-m", "paper"],
        check=True,
        env=_commit_env(env),
    )
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", origin.as_uri(), str(shallow)],
        check=True,
        env=env,
    )
    result = subprocess.run(
        ["bash", str(shallow / "docs" / "paper" / "build.sh")],
        cwd=shallow,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 1
    assert "shallow checkout" in result.stderr


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
        repo / "site" / "public" / "papers" / "legalforecastbench-working.pdf"
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


def _git_env(tmp_path: Path) -> dict[str, str]:
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    return {
        **os.environ,
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_SYSTEM": str(gitconfig),
    }


def _commit_env(env: dict[str, str]) -> dict[str, str]:
    return {
        **env,
        "GIT_AUTHOR_NAME": "Paper Test",
        "GIT_AUTHOR_EMAIL": "paper-test@example.com",
        "GIT_COMMITTER_NAME": "Paper Test",
        "GIT_COMMITTER_EMAIL": "paper-test@example.com",
    }


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


def _build_preview(tmp_path: Path, manuscript: str) -> subprocess.CompletedProcess[str]:
    paper_dir = tmp_path / "docs" / "paper"
    paper_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "paper" / "build.sh", paper_dir / "build.sh")
    (paper_dir / "LegalForecastBench-paper.tex").write_text(manuscript)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    compiler = bin_dir / "latexmk"
    compiler.write_text('#!/usr/bin/env bash\ntouch "$PAPER_TEST_COMPILED"\n')
    compiler.chmod(0o755)
    return subprocess.run(
        ["bash", str(paper_dir / "build.sh"), "--release"],
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "SOURCE_DATE_EPOCH": "1",
            "PAPER_TEST_COMPILED": str(tmp_path / "compiled"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
