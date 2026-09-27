"""Public summary comparison inputs reproduce the displayed native exports."""

import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "reproduce_summary_comparisons",
    Path(__file__).parents[1] / "scripts/reproduce_summary_comparisons.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_public_summary_comparisons_reproduce_displayed_exports(tmp_path: Path) -> None:
    """Exercise frozen registries, prediction census, canonical scoring and export."""
    site = Path(__file__).parents[1] / "site"
    MODULE.reproduce(site / "public/data/summary-comparison", tmp_path)
    exports = sorted(tmp_path.glob("*.json"))
    assert len(exports) == 3
    for export in exports:
        expected = site / "src/data/exports" / export.name
        assert json.loads(export.read_text()) == json.loads(expected.read_text())
