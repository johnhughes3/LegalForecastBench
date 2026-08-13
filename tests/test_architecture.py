from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from legalforecast.testing import architecture as architecture_module
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
        "legalforecast/cli_commands/score.py",
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
    assert "legalforecast.cli.argparse._SubParsersAction" not in (
        snapshot.compatibility.private_cli_targets
    )
    assert "legalforecast.cli.os.link" in snapshot.compatibility.monkeypatch_targets
    assert "legalforecast.cli.sys.stdin" in (snapshot.compatibility.monkeypatch_targets)
    assert (
        "tests/test_disclosure_review_bundle_cli.py::legalforecast.cli.sys.stdin"
        in snapshot.compatibility.monkeypatch_occurrences
    )


def test_architecture_scanner_distinguishes_cli_members_from_nested_modules(
    tmp_path: Path,
) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        """\
import legalforecast.cli
from legalforecast import cli as cli_module

_private = legalforecast.cli._private
stdlib_private = cli_module.argparse._SubParsersAction
monkeypatch.setattr(cli_module.os, "link", replacement)
for name in ("first", "second"):
    monkeypatch.setattr(cli_module, name, replacement)
for name in ("third", "fourth"):
    monkeypatch.setattr(f"legalforecast.cli.{name}", replacement)
monkeypatch.setattr(target=cli_module, name="fifth", value=replacement)
""",
        encoding="utf-8",
    )

    inventory = architecture_module._scan_test_compatibility(tmp_path)

    assert inventory.private_cli_targets == ("legalforecast.cli._private",)
    assert inventory.monkeypatch_targets == (
        "legalforecast.cli.fifth",
        "legalforecast.cli.first",
        "legalforecast.cli.fourth",
        "legalforecast.cli.os.link",
        "legalforecast.cli.second",
        "legalforecast.cli.third",
    )
    assert inventory.cli_import_occurrences == (
        "tests/test_probe.py",
        "tests/test_probe.py",
    )
    assert inventory.private_cli_occurrences == (
        "tests/test_probe.py::legalforecast.cli._private",
    )
    assert inventory.monkeypatch_occurrences == (
        "tests/test_probe.py::legalforecast.cli.fifth",
        "tests/test_probe.py::legalforecast.cli.first",
        "tests/test_probe.py::legalforecast.cli.fourth",
        "tests/test_probe.py::legalforecast.cli.os.link",
        "tests/test_probe.py::legalforecast.cli.second",
        "tests/test_probe.py::legalforecast.cli.third",
    )


def test_architecture_scanner_tracks_dynamically_imported_test_facade(
    tmp_path: Path,
) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        """\
import importlib as loader

cli_module = loader.import_module(name="legalforecast.cli")
private = cli_module._private
monkeypatch.setattr(cli_module, "main", replacement)
""",
        encoding="utf-8",
    )

    inventory = architecture_module._scan_test_compatibility(tmp_path)

    assert inventory.cli_import_files == ("tests/test_probe.py",)
    assert inventory.cli_import_occurrences == ("tests/test_probe.py",)
    assert inventory.private_cli_targets == ("legalforecast.cli._private",)
    assert inventory.monkeypatch_targets == ("legalforecast.cli.main",)


def test_architecture_scanner_ignores_dynamically_imported_console_as_cli(
    tmp_path: Path,
) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        """\
import importlib

console = importlib.import_module("legalforecast.console")
private = console._private
monkeypatch.setattr(console, "main", replacement)
""",
        encoding="utf-8",
    )

    inventory = architecture_module._scan_test_compatibility(tmp_path)

    assert inventory.cli_import_files == ()
    assert inventory.private_cli_targets == ()
    assert inventory.monkeypatch_targets == ()


def test_console_source_detection_respects_package_boundary() -> None:
    assert architecture_module._is_console_adapter_source(
        "legalforecast/console/parser.py"
    )
    assert not architecture_module._is_console_adapter_source(
        "legalforecast/ingestion/purchase.py"
    )


def test_console_adapter_scan_rejects_facade_cycles_but_allows_composition(
    tmp_path: Path,
) -> None:
    console = tmp_path / "legalforecast" / "console"
    console.mkdir(parents=True)
    module = console / "command.py"
    module.write_text("from legalforecast.console import parser\n", encoding="utf-8")
    assert not architecture_module._imports_cli(module, include_console=False)

    module.write_text("from legalforecast.cli import handler\n", encoding="utf-8")
    assert architecture_module._imports_cli(module, include_console=False)


@pytest.mark.parametrize(
    "statement",
    [
        "from .. import cli",
        "from ..cli import main",
        "from .. import console",
        "from ..console import app",
        "from legalforecast import cli",
        "from legalforecast.cli import main",
        "from legalforecast import console",
        "from legalforecast.console import app",
        "from legalforecast.console.commands import app",
        "import legalforecast.console",
        "import legalforecast.console.commands",
        'import importlib\nimportlib.import_module("legalforecast.cli")',
        (
            "import importlib as loader\n"
            'loader.import_module("legalforecast.console.commands")'
        ),
        'from importlib import import_module\nimport_module("legalforecast.console")',
        'from importlib import import_module as load\nload("legalforecast.cli")',
        'import importlib\nimportlib.import_module(name="legalforecast.cli")',
        (
            "from importlib import import_module as load\n"
            'load(name="legalforecast.console.commands")'
        ),
        '__import__("legalforecast.cli")',
    ],
)
def test_upward_dependency_scanner_resolves_cli_import_forms(
    tmp_path: Path, statement: str
) -> None:
    module = tmp_path / "legalforecast" / "ingestion" / "probe.py"
    module.parent.mkdir(parents=True)
    module.write_text(statement + "\n", encoding="utf-8")

    assert architecture_module._imports_cli(module)


@pytest.mark.parametrize(
    "statement",
    [
        "import legalforecast.console_utils",
        'import importlib\nimportlib.import_module("legalforecast.console_utils")',
    ],
)
def test_upward_dependency_scanner_respects_adapter_package_boundaries(
    tmp_path: Path, statement: str
) -> None:
    module = tmp_path / "legalforecast" / "ingestion" / "probe.py"
    module.parent.mkdir(parents=True)
    module.write_text(statement + "\n", encoding="utf-8")

    assert not architecture_module._imports_cli(module)


def test_architecture_scanner_allows_build_parser_to_move_from_facade(
    tmp_path: Path,
) -> None:
    package = tmp_path / "legalforecast"
    package.mkdir()
    (package / "cli.py").write_text(
        "from legalforecast.console import build_parser\n", encoding="utf-8"
    )

    snapshot = scan_repository(tmp_path)

    assert snapshot.cli_metrics.parser_line_count == 0


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


def test_architecture_baseline_requires_reduced_metrics_to_shrink(
    tmp_path: Path,
) -> None:
    baseline = load_baseline(ROOT / BASELINE_PATH)
    payload = {
        "schema_version": 1,
        "cli_metrics": {
            **asdict(baseline.cli_metrics),
            "line_count": baseline.cli_metrics.line_count + 1,
        },
        "upward_cli_dependencies": list(baseline.upward_cli_dependencies),
        "compatibility": asdict(baseline.compatibility),
    }
    path = tmp_path / "architecture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    violations = check_baseline(ROOT, path)

    assert (
        "stale cli_metrics.line_count must be reduced: "
        f"reviewed {baseline.cli_metrics.line_count + 1} "
        f"> observed {baseline.cli_metrics.line_count}" in violations
    )


def test_architecture_baseline_rejects_an_extra_known_patch_occurrence(
    tmp_path: Path,
) -> None:
    baseline = load_baseline(ROOT / BASELINE_PATH)
    occurrence = baseline.compatibility.monkeypatch_occurrences[0]
    payload = {
        "schema_version": 1,
        "cli_metrics": asdict(baseline.cli_metrics),
        "upward_cli_dependencies": list(baseline.upward_cli_dependencies),
        "compatibility": {
            **asdict(baseline.compatibility),
            "monkeypatch_occurrences": [
                *baseline.compatibility.monkeypatch_occurrences[1:],
            ],
        },
    }
    path = tmp_path / "architecture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    violations = check_baseline(ROOT, path)

    assert any(
        violation.startswith("new compatibility.monkeypatch_occurrences:")
        and occurrence in violation
        for violation in violations
    )


def test_architecture_baseline_requires_removed_upward_edges_to_shrink(
    tmp_path: Path,
) -> None:
    baseline = load_baseline(ROOT / BASELINE_PATH)
    removed = baseline.upward_cli_dependencies[0]
    payload = {
        "schema_version": 1,
        "cli_metrics": asdict(baseline.cli_metrics),
        "upward_cli_dependencies": [
            *baseline.upward_cli_dependencies,
            "legalforecast/obsolete_cli_import.py",
        ],
        "compatibility": asdict(baseline.compatibility),
    }
    path = tmp_path / "architecture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    violations = check_baseline(ROOT, path)

    assert any(
        violation
        == (
            "stale upward CLI dependencies must be removed: "
            "legalforecast/obsolete_cli_import.py"
        )
        for violation in violations
    )
    assert removed not in "\n".join(violations)


def test_architecture_baseline_requires_removed_compatibility_to_shrink(
    tmp_path: Path,
) -> None:
    baseline = load_baseline(ROOT / BASELINE_PATH)
    stale_target = "legalforecast.cli._obsolete"
    stale_occurrence = f"tests/test_obsolete.py::{stale_target}"
    payload = {
        "schema_version": 1,
        "cli_metrics": asdict(baseline.cli_metrics),
        "upward_cli_dependencies": list(baseline.upward_cli_dependencies),
        "compatibility": {
            **asdict(baseline.compatibility),
            "private_cli_targets": [
                *baseline.compatibility.private_cli_targets,
                stale_target,
            ],
            "private_cli_occurrences": [
                *baseline.compatibility.private_cli_occurrences,
                stale_occurrence,
            ],
        },
    }
    path = tmp_path / "architecture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    violations = check_baseline(ROOT, path)

    assert (
        "stale compatibility.private_cli_targets must be removed: " + stale_target
        in violations
    )
    assert (
        "stale compatibility.private_cli_occurrences must be removed: "
        + stale_occurrence
        in violations
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
