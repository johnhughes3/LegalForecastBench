from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
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
    current = scan_repository(ROOT)
    assert current.cli_metrics.line_count <= snapshot.cli_metrics.line_count
    assert (
        current.cli_metrics.command_handler_count
        <= snapshot.cli_metrics.command_handler_count
    )


def test_architecture_scanner_finds_private_cli_test_coupling() -> None:
    snapshot = scan_repository(ROOT)
    assert "tests/conftest.py" in snapshot.compatibility.cli_import_files
    assert "tests/test_cycle_orchestrator_cli.py" in (
        snapshot.compatibility.private_cli_files
    )
    assert "legalforecast.cli._StageAUnitizationLineage" in (
        snapshot.compatibility.private_cli_targets
    )
    assert "legalforecast.cli.main" in snapshot.compatibility.monkeypatch_targets
    assert not any(
        target.endswith(".__file__")
        for target in snapshot.compatibility.private_cli_targets
    )


def test_architecture_baseline_reports_tightened_limits(tmp_path: Path) -> None:
    baseline = load_baseline(ROOT / BASELINE_PATH)
    payload = {
        "schema_version": 1,
        "cli_metrics": {
            **asdict(baseline.cli_metrics),
            "line_count": 1,
        },
        "upward_cli_dependencies": list(baseline.upward_cli_dependencies),
        "compatibility": asdict(baseline.compatibility),
    }
    path = tmp_path / "architecture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    violations = check_baseline(ROOT, path)
    assert any(
        violation.startswith("cli_metrics.line_count:")
        and violation.endswith("> reviewed 1")
        for violation in violations
    )


@pytest.mark.parametrize("payload", [{"schema_version": 2}, []])
def test_load_baseline_rejects_invalid_payloads(
    tmp_path: Path, payload: object
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_baseline(path)


def test_load_baseline_normalizes_json_arrays_to_tuples() -> None:
    snapshot = load_baseline(ROOT / BASELINE_PATH)
    assert isinstance(snapshot.upward_cli_dependencies, tuple)
    assert isinstance(snapshot.compatibility.cli_import_files, tuple)
    assert isinstance(snapshot.compatibility.private_cli_targets, tuple)
