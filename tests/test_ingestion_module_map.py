"""Keep the ingestion module map aligned with the package it documents."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGESTION_ROOT = ROOT / "legalforecast" / "ingestion"
MODULE_MAP = ROOT / "docs" / "ingestion-module-map.md"
DOCS_INDEX = ROOT / "docs" / "README.md"

MODULE_LINK = re.compile(
    r"^\| \[`(?P<module>[^`]+\.py)`\]"
    r"\(\.\./legalforecast/ingestion/(?P=module)\) \|",
    flags=re.MULTILINE,
)


def test_ingestion_module_map_covers_every_python_module_exactly_once() -> None:
    mapped_modules = MODULE_LINK.findall(MODULE_MAP.read_text(encoding="utf-8"))
    actual_modules = sorted(
        path.relative_to(INGESTION_ROOT).as_posix()
        for path in INGESTION_ROOT.rglob("*.py")
    )

    assert all(count == 1 for count in Counter(mapped_modules).values())
    assert sorted(mapped_modules) == actual_modules


def test_ingestion_module_map_exposes_ownership_and_entry_points() -> None:
    module_map = MODULE_MAP.read_text(encoding="utf-8")
    concern_sections = re.findall(r"^## \d+\. .+$", module_map, flags=re.MULTILINE)

    assert len(concern_sections) >= 8
    assert module_map.count("**Owns:**") == len(concern_sections)
    assert module_map.count("**Start with:**") == len(concern_sections)
    assert "[Ingestion module map](ingestion-module-map.md)" in DOCS_INDEX.read_text(
        encoding="utf-8"
    )
