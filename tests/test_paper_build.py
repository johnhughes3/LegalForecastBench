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
