"""Assert that the fictional one-case withdrawal reached downloads and HTML."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def verify(
    expected: Path, reproduced: Path | None = None, *, producer: bool = False
) -> None:
    built = ROOT / "site/dist/data"
    downloads = {
        p.relative_to(built)
        for p in built.rglob("*")
        if p.suffix in {".json", ".jsonl"}
    }
    selected = {
        p.relative_to(expected)
        for p in expected.rglob("*")
        if p.suffix in {".json", ".jsonl"}
    }
    assert downloads == selected, "stale or missing downloadable files"
    for relative in downloads:
        data = (built / relative).read_bytes()
        if producer and relative.name == "comparison.json":
            result = json.loads(data)
            assert (
                result["case_count"],
                result["unit_count"],
                result["replicates"],
            ) == (1, 2, 1_000_000)
        elif producer and relative == Path("current.json"):
            selected_current = json.loads(data)
            reference_current = json.loads((expected / relative).read_bytes())
            assert selected_current["models"] == reference_current["models"]
        else:
            assert data == (expected / relative).read_bytes(), relative
        assert b"synthetic-case-b" not in data, relative
        assert b"synthetic-unit-b1" not in data, relative
    current = json.loads((built / "current.json").read_text())
    assert len(current["models"]) == 11
    assert (current["cohort"]["case_count"], current["cohort"]["unit_count"]) == (1, 2)
    assert all(math.isclose(row["micro_brier"], 0.1) for row in current["models"])
    if reproduced is not None:
        for path in reproduced.glob("*.json"):
            replay = json.loads(path.read_text())["results"][0]
            displayed = json.loads((built / "exports" / path.name).read_text())[
                "results"
            ][0]
            for field in (
                "case_count",
                "unit_count",
                "micro_brier",
                "equal_case_brier",
                "units",
                "calibration",
            ):
                assert replay[field] == displayed[field], (path.name, field)
    historical = json.loads((built / "historical-aggregates.json").read_text())
    assert historical["status"] == "superseded" and len(historical["models"]) == 7
    index = (built / "index.html").read_text()
    assert "10 models plus the GPT-4.1 reference, on 1 cases and 2 units" in index
    assert "historical-aggregates.json" in index
    summary = (ROOT / "site/dist/experiments/summary-pipelines/index.html").read_text()
    assert "Summary forecasts on the retained cohort" in summary and "0.1000" in summary
    assert "Jev is significantly worse than both controls" not in summary
    appendix = (built / "historical-results/index.html").read_text()
    assert "2 prediction units from 1 cases" in appendix
    assert "0.100000" in appendix
    assert not (ROOT / "site/dist/models/kimi-k3/index.html").exists()
    print(
        f"Verified {len(downloads)} exact backend downloads "
        "and refreshed current/summary/historical pages"
    )


if __name__ == "__main__":
    verify(
        Path(sys.argv[1]),
        Path(sys.argv[2]) if len(sys.argv) > 2 else None,
        producer="--producer" in sys.argv,
    )
