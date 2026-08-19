"""Every top-level package must import first, in a fresh interpreter.

``tests/conftest.py`` imports ``legalforecast.cli`` before any test module
runs, so by the time a normal test executes, ``legalforecast.ingestion`` is
always already initialised.  That masks import cycles completely: a change can
make ``import legalforecast.extraction`` fail for every real consumer while the
whole suite stays green.  One such regression was introduced and caught only in
review, so this test exists to make the next one visible.

Each import runs in its own subprocess — a fresh interpreter is the only way to
observe first-import order, and the suite runs under xdist workers where
``os.fork`` is unsafe.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_PACKAGES = (
    "legalforecast",
    "legalforecast.cli",
    "legalforecast.extraction",
    "legalforecast.extraction.ocr",
    "legalforecast.extraction.pdf_text",
    "legalforecast.ingestion",
    "legalforecast.ingestion.disclosure_clearance",
    "legalforecast.ingestion.embedded_text_layer_repair",
    "legalforecast.ingestion.mistral_markdown_parser",
    "legalforecast.ingestion.text_layer_completeness",
    "legalforecast.labeling",
    "legalforecast.selection",
)

#: ``legalforecast.protocol`` cannot be imported first on ``main`` either --
#: ``protocol/__init__`` imports ``protocol.manifest``, which imports back
#: through the package.  That is a pre-existing cycle, unrelated to any change
#: in this file's lane, so it is recorded here rather than silently omitted or
#: opportunistically fixed.  Tracked as legalforecastbench-19cs.
_KNOWN_UNIMPORTABLE_FIRST = ("legalforecast.protocol",)


def _import_first(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


@pytest.mark.parametrize("module", _PACKAGES)
def test_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    completed = _import_first(module)

    assert completed.returncode == 0, (
        f"{module} cannot be imported first:\n{completed.stderr}"
    )


@pytest.mark.parametrize("module", _KNOWN_UNIMPORTABLE_FIRST)
def test_the_recorded_pre_existing_cycle_is_still_exactly_that(module: str) -> None:
    """Pin the known defect so fixing it is noticed rather than absorbed."""

    completed = _import_first(module)

    assert completed.returncode != 0
    assert "circular import" in completed.stderr
