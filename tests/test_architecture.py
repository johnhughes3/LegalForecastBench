from __future__ import annotations

from pathlib import Path

from legalforecast.testing.architecture import (
    BASELINE_PATH,
    check_baseline,
    load_baseline,
    scan_repository,
)

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_baseline_is_current() -> None:
    assert check_baseline(ROOT) == ()


def test_architecture_baseline_records_the_known_migration_edges() -> None:
    snapshot = load_baseline(ROOT / BASELINE_PATH)
    assert snapshot.upward_cli_dependencies == (
        "legalforecast/ingestion/purchase_approval.py",
        "legalforecast/ingestion/recovered_public_replay.py",
        "legalforecast/ingestion/resolved_post_recovery.py",
    )
    assert snapshot.cli_metrics.line_count == 76043
    assert snapshot.cli_metrics.command_handler_count == 167


def test_architecture_scanner_finds_private_cli_test_coupling() -> None:
    snapshot = scan_repository(ROOT)
    assert "tests/conftest.py" in snapshot.compatibility.cli_import_files
    assert snapshot.compatibility.private_cli_targets
    assert snapshot.compatibility.monkeypatch_targets
