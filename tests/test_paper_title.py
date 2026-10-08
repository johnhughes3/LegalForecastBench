"""The working papers' retired titles must not linger anywhere in the repository.

The paper was retitled "Law as a Verifiable Domain: Using Real-World Judicial
Outcomes to Evaluate AI Legal Reasoning" before going live. Its citation, PDF
metadata, the companion paper's reference, and the website all read the new
title. The LAB audit paper was likewise retitled "The Challenge of Deriving
Signal from Synthetic Legal Environments". This guard catches a stale copy of
either old title.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = re.compile(
    r"Forecasting\s+Judicial\s+Decisions(?:\s|\\\\)+as\s+a\s+Test\s+of\s+Legal"
    r"|Law\s+Can\s+Be\s+a\s+Verifiable\s+Domain"
    r"|Auditing\s+Harvey's\s+Legal\s+Agent\s+Benchmark:\s+Rubric",
    re.IGNORECASE,
)
# The issue tracker's export is a historical record, and this file names the
# retired title in order to forbid it.
SKIPPED = (".beads/", "tests/test_paper_title.py")


def test_the_retired_paper_title_appears_nowhere() -> None:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode()
    stale = []
    for name in filter(None, listed.split("\0")):
        if name.startswith(SKIPPED):
            continue
        path = ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        if RETIRED.search(text):
            stale.append(name)
    assert stale == []
