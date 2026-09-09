"""Behavioral coverage for prepare-time benchmark state recovery."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from legalforecast.runner import execute_release_run
from legalforecast.runner.fixture import FixtureModelTransport
from legalforecast.runner.ledger import RunValidationError
from tests.test_public_runner import _config, _fixture_environ

SCRIPT_PATH = Path(__file__).parents[1] / ".github/scripts/restore-forecast-state.py"


def _load_restore_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "restore_forecast_state_batch", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("restore helper could not be imported")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_cells(tmp_path: Path) -> tuple[Path, list[dict[str, Any]], str]:
    config = _config(tmp_path / "source")
    execute_release_run(
        config,
        transport=FixtureModelTransport(),
        environ=_fixture_environ(),
    )
    receipts = sorted(config.receipts_dir.glob("*.json"))
    assert len(receipts) == 3
    cells: list[dict[str, Any]] = []
    for receipt_path in receipts:
        receipt = json.loads(receipt_path.read_bytes())
        cells.append(
            {
                "provider": "openai",
                "model_key": config.model_key,
                "model_id": "legalforecast-fixture",
                "cell_id": receipt["cell_id"],
                "cell_id_slug": receipt["cell_id"],
                "unit_id": receipt["unit_id"],
                "required_unit_ids": receipt["required_unit_ids"],
                "case_id": receipt["case_id"],
                "repeat_index": receipt["repeat_index"],
                "ablation": "none",
            }
        )
    return config.ledger_path, cells, receipt["run_identity_sha256"]


def _materialize_state(
    source_ledger: Path,
    source_receipts: Path,
    cell: dict[str, Any],
    destination: Path,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_ledger, destination / "ledger.sqlite3")
    (destination / "state.json").write_text(
        json.dumps(
            {
                "provider": cell["provider"],
                "cell_id": cell["cell_id"],
                "status": "completed",
                "run_id": "source-run",
                "run_attempt": 1,
            }
        )
    )
    (destination / "failure-summary.json").write_text('{"status":"completed"}')
    (destination / "run-summary.json").write_text('{"status":"completed"}')
    receipts = destination / "receipts"
    receipts.mkdir()
    shutil.copyfile(
        source_receipts / f"{cell['cell_id']}.json",
        receipts / f"{cell['cell_id']}.json",
    )


def _prepare_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source_ledger: Path,
    source_receipts: Path,
    complete_cells: set[str],
    cells: list[dict[str, Any]],
    module: ModuleType,
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    (tmp_path / "runner").mkdir()

    def fake_api(_endpoint: str, *, paginate: bool = False) -> object:
        assert paginate
        return [{"total_count": 0, "artifacts": []}]

    def fake_restore() -> None:
        cell_id = os.environ["CELL_ID"]
        if cell_id not in complete_cells:
            return
        cell = next(candidate for candidate in cells if candidate["cell_id"] == cell_id)
        _materialize_state(
            source_ledger,
            source_receipts,
            cell,
            Path(os.environ["LFB_RUN_ROOT"]),
        )

    monkeypatch.setattr(module, "_api_json", fake_api)
    monkeypatch.setattr(module, "restore", fake_restore)


def test_prepare_filters_two_completed_cells_and_keeps_one_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_restore_script()
    source_ledger, cells, identity = _fixture_cells(tmp_path)
    source_receipts = tmp_path / "source" / "receipts"
    matrices = {
        "openai": cells.copy(),
        "anthropic": [],
        "gemini": [],
        "gateway": [],
    }
    _prepare_environment(
        monkeypatch,
        tmp_path,
        source_ledger,
        source_receipts,
        {cells[0]["cell_id"], cells[1]["cell_id"]},
        cells,
        module,
    )

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    bundle = tmp_path / "bundle"
    module.prepare(matrices, identity, inputs, bundle)

    assert [cell["cell_id"] for cell in matrices["openai"]] == [cells[2]["cell_id"]]
    assert sorted(path.stem for path in bundle.glob("*.zip")) == sorted(
        cell["cell_id"] for cell in cells[:2]
    )
    expected = json.loads((inputs / "expected-cells.json").read_text())
    assert {cell["cell_id"] for cell in expected} == {cell["cell_id"] for cell in cells}


def test_prepare_all_completed_cells_leaves_no_workers_and_round_trips_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_restore_script()
    source_ledger, cells, identity = _fixture_cells(tmp_path)
    source_receipts = tmp_path / "source" / "receipts"
    matrices = {
        "openai": cells.copy(),
        "anthropic": [],
        "gemini": [],
        "gateway": [],
    }
    _prepare_environment(
        monkeypatch,
        tmp_path,
        source_ledger,
        source_receipts,
        {cell["cell_id"] for cell in cells},
        cells,
        module,
    )

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    bundle = tmp_path / "bundle"
    module.prepare(matrices, identity, inputs, bundle)

    assert matrices["openai"] == []
    expanded = tmp_path / "expanded"
    module.expand_bundle(bundle, expanded)
    expanded_cells = sorted(
        json.loads((path / "state.json").read_text())["cell_id"]
        for path in expanded.iterdir()
    )
    assert expanded_cells == sorted(cell["cell_id"] for cell in cells)
    assert all(
        (path / "receipts" / f"{path.name.removeprefix('restored-')}.json").is_file()
        for path in expanded.iterdir()
    )


def test_validate_completed_rejects_changed_receipt_bytes(
    tmp_path: Path,
) -> None:
    module = _load_restore_script()
    source_ledger, cells, identity = _fixture_cells(tmp_path)
    source_receipts = tmp_path / "source" / "receipts"
    root = tmp_path / "state"
    _materialize_state(source_ledger, source_receipts, cells[0], root)
    receipt_path = root / "receipts" / f"{cells[0]['cell_id']}.json"
    receipt_path.write_bytes(b"{}")

    with pytest.raises(RunValidationError, match="receipt bytes changed"):
        module.validate_completed(root, cells[0], identity)


def test_validate_completed_rejects_completed_ledger_without_receipt_evidence(
    tmp_path: Path,
) -> None:
    module = _load_restore_script()
    source_ledger, cells, identity = _fixture_cells(tmp_path)
    source_receipts = tmp_path / "source" / "receipts"
    root = tmp_path / "state"
    _materialize_state(source_ledger, source_receipts, cells[0], root)
    with sqlite3.connect(root / "ledger.sqlite3") as connection:
        connection.execute(
            "UPDATE public_runner_cells SET receipt_sha256 = NULL, "
            "receipt_payload = NULL"
        )
        connection.commit()

    with pytest.raises(RunValidationError, match="lacks durable receipt evidence"):
        module.validate_completed(root, cells[0], identity)
