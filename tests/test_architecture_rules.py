from __future__ import annotations

from pathlib import Path

from legalforecast.testing.architecture import BASELINE_PATH, check_baseline
from legalforecast.testing.architecture_rules.inventory import (
    WATCH_LINE_THRESHOLD,
    lane_owner,
    python_files_for_inventory,
    scan_repository,
)
from legalforecast.testing.architecture_rules.symbols import measure_python_file

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_facade_stays_a_small_composition_root() -> None:
    metrics = measure_python_file(ROOT, "legalforecast/testing/architecture.py")
    assert metrics is not None
    assert metrics.line_count < 80


def test_architecture_rules_modules_are_not_a_new_monolith() -> None:
    rules = ROOT / "legalforecast" / "testing" / "architecture_rules"
    oversized = [
        (path.name, measure_python_file(ROOT, path.relative_to(ROOT).as_posix()))
        for path in sorted(rules.glob("*.py"))
    ]
    assert oversized
    for name, metrics in oversized:
        assert metrics is not None, name
        assert metrics.line_count < 1000, name


def test_inventory_measures_every_tracked_python_file() -> None:
    inventory = scan_repository(ROOT)
    tracked = python_files_for_inventory(ROOT)
    measured = {record.path for record in inventory.files}
    assert measured == set(tracked)


def test_watch_tier_files_have_package_lane_owners() -> None:
    inventory = scan_repository(ROOT)
    missing = [
        record.path
        for record in inventory.files
        if record.line_count >= WATCH_LINE_THRESHOLD and not record.lane_owner
    ]
    assert missing == []
    assert lane_owner("legalforecast/cli.py") == "cli"
    assert lane_owner("legalforecast/ingestion/cycle_orchestrator.py") == "ingestion"
    assert lane_owner("tests/test_architecture.py") == "tests"
    assert lane_owner("scripts/release_check.py") == "scripts"


def test_architecture_baseline_is_current_with_inventory() -> None:
    assert check_baseline(ROOT, ROOT / BASELINE_PATH) == ()
