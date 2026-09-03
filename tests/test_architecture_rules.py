from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from legalforecast.testing.architecture import BASELINE_PATH, check_baseline
from legalforecast.testing.architecture_rules.inventory import (
    WATCH_LINE_THRESHOLD,
    lane_owner,
    python_files_for_inventory,
    scan_repository,
)
from legalforecast.testing.architecture_rules.symbols import measure_python_file

ROOT = Path(__file__).resolve().parents[1]

# Every module that exposes a ``--write-baseline`` ratchet CLI. A module without
# an ``if __name__ == "__main__"`` guard still exits 0 under ``python -m``, so a
# regenerate command silently does nothing; these entrypoints must dispatch.
RATCHET_ENTRYPOINT_MODULES = (
    "legalforecast.contracts.ratchet",
    "legalforecast.testing.architecture",
    "legalforecast.testing.architecture_rules",
    "legalforecast.testing.architecture_rules.reporting",
)

WRITE_BASELINE_ENTRYPOINT_MODULES = (
    "legalforecast.testing.architecture_rules",
    "legalforecast.testing.architecture_rules.reporting",
)


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


def _run_module(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a repository module through ``python -m`` in a child process."""

    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        # Python 3.14 argparse colorizes help; NO_COLOR keeps assertions stable.
        env={**os.environ, "NO_COLOR": "1"},
    )


def _write_minimal_repository(root: Path) -> None:
    """Create the smallest tree the architecture scanner can inventory."""

    package = root / "legalforecast"
    package.mkdir(parents=True)
    (package / "cli.py").write_text(
        "def main() -> int:\n    return 0\n", encoding="utf-8"
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_placeholder.py").write_text(
        "def test_placeholder() -> None:\n    assert True\n", encoding="utf-8"
    )


@pytest.mark.parametrize("module", RATCHET_ENTRYPOINT_MODULES)
def test_ratchet_entrypoints_dispatch_under_python_dash_m(module: str) -> None:
    completed = _run_module(module, "--help")
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout, (module, completed.stdout)
    assert "--write-baseline" in completed.stdout, (module, completed.stdout)


@pytest.mark.parametrize("module", WRITE_BASELINE_ENTRYPOINT_MODULES)
def test_write_baseline_entrypoint_writes_a_baseline(
    module: str, tmp_path: Path
) -> None:
    scanned_root = tmp_path / "repo"
    _write_minimal_repository(scanned_root)
    baseline = tmp_path / "baseline.json"

    completed = _run_module(
        module,
        "--root",
        str(scanned_root),
        "--baseline",
        str(baseline),
        "--write-baseline",
    )

    assert completed.returncode == 0, completed.stderr
    assert str(baseline) in completed.stdout
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "inventory" in payload
