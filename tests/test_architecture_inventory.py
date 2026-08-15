from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from legalforecast.testing.architecture_rules.baseline import (
    check_baseline,
    write_baseline,
)
from legalforecast.testing.architecture_rules.imports import (
    production_import_graph,
    strongly_connected_components,
)
from legalforecast.testing.architecture_rules.inventory import (
    BASELINE_PATH,
    lane_owner,
    scan_repository,
)
from legalforecast.testing.architecture_rules.reporting import ranked_queue
from legalforecast.testing.architecture_rules.symbols import measure_python_file


def _init_git_repository(path: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "architecture-fixture",
        "GIT_AUTHOR_EMAIL": "architecture-fixture@example.com",
        "GIT_COMMITTER_NAME": "architecture-fixture",
        "GIT_COMMITTER_EMAIL": "architecture-fixture@example.com",
    }
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=architecture-fixture",
            "-c",
            "user.email=architecture-fixture@example.com",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
        env=env,
    )


def _write_module(path: Path, body: str, *, lines: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    filler = "\n".join(f"x{index} = {index}" for index in range(max(0, lines - 2)))
    path.write_text(body.rstrip() + "\n" + filler + "\n", encoding="utf-8")


def _cli_source(*, lines: int = 8) -> str:
    return "def build_parser():\n    return None\n" + "\n".join(
        f"x{index} = {index}" for index in range(max(0, lines - 2))
    )


def test_measure_python_file_records_the_largest_top_level_symbol(
    tmp_path: Path,
) -> None:
    relative = "legalforecast/probe.py"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        "def small():\n    return 1\n\ndef large():\n    a = 1\n    b = 2\n    c = 3\n",
        encoding="utf-8",
    )

    metrics = measure_python_file(tmp_path, relative)

    assert metrics is not None
    assert metrics.largest_symbol == "large"
    assert metrics.largest_symbol_lines == 4
    assert metrics.top_level_definition_count == 2


def test_lane_owner_assigns_package_lanes() -> None:
    assert lane_owner("legalforecast/ingestion/store.py") == "ingestion"
    assert lane_owner("legalforecast/cli.py") == "cli"
    assert lane_owner("tests/test_architecture.py") == "tests"
    assert lane_owner("scripts/release_check.py") == "scripts"


def test_import_graph_detects_a_two_module_cycle(tmp_path: Path) -> None:
    package = tmp_path / "legalforecast" / "labeling"
    package.mkdir(parents=True)
    (package / "llm_pipeline.py").write_text(
        "from legalforecast.labeling import unitizer_terminal\n",
        encoding="utf-8",
    )
    (package / "unitizer_terminal.py").write_text(
        "from legalforecast.labeling import llm_pipeline\n",
        encoding="utf-8",
    )

    components = strongly_connected_components(production_import_graph(tmp_path))

    assert components == (
        (
            "legalforecast/labeling/llm_pipeline.py",
            "legalforecast/labeling/unitizer_terminal.py",
        ),
    )


def test_inventory_assigns_watch_tier_lane_without_manual_disposition(
    tmp_path: Path,
) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    _write_module(
        tmp_path / "legalforecast" / "labeling" / "stage.py",
        "def run():\n    return None\n",
        lines=520,
    )
    _init_git_repository(tmp_path)

    snapshot = scan_repository(tmp_path)
    record = next(
        item
        for item in snapshot.files
        if item.path == "legalforecast/labeling/stage.py"
    )

    assert record.lane_owner == "labeling"
    assert record.disposition_kind == "watch"
    assert "watch" in record.flags
    assert record.line_count >= 500


def test_inventory_requires_manual_disposition_for_oversized_and_cycles(
    tmp_path: Path,
) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    labeling = tmp_path / "legalforecast" / "labeling"
    _write_module(
        labeling / "llm_pipeline.py",
        (
            "from legalforecast.labeling import unitizer_terminal\n"
            "\ndef run():\n    return None\n"
        ),
        lines=1200,
    )
    _write_module(
        labeling / "unitizer_terminal.py",
        (
            "from legalforecast.labeling import llm_pipeline\n"
            "\ndef run():\n    return None\n"
        ),
        lines=80,
    )
    _write_module(
        tmp_path / "legalforecast" / "ingestion" / "canonical_json.py",
        "VALUE = 1\n",
        lines=40,
    )
    _init_git_repository(tmp_path)

    snapshot = scan_repository(tmp_path)
    by_path = {item.path: item for item in snapshot.files}

    oversized = by_path["legalforecast/labeling/llm_pipeline.py"]
    assert oversized.disposition_kind == "planned-seam"
    assert oversized.disposition_owner == "legalforecastbench-m1pv.3"
    assert "cycle" in oversized.flags
    assert "oversized" in oversized.flags
    assert by_path["legalforecast/ingestion/canonical_json.py"].disposition_kind == (
        "no-move"
    )


def test_baseline_rejects_new_watch_file_and_new_cycle(tmp_path: Path) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    _write_module(
        tmp_path / "legalforecast" / "labeling" / "stage.py",
        "def run():\n    return None\n",
        lines=520,
    )
    _init_git_repository(tmp_path)
    baseline_path = tmp_path / "architecture.json"
    write_baseline(baseline_path, scan_repository(tmp_path))

    _write_module(
        tmp_path / "legalforecast" / "labeling" / "extra.py",
        "def run():\n    return None\n",
        lines=530,
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)

    violations = check_baseline(tmp_path, baseline_path)

    assert any(
        violation.startswith("new inventory file legalforecast/labeling/extra.py")
        for violation in violations
    )


def test_baseline_allows_watch_tier_growth_below_one_thousand(tmp_path: Path) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    module = tmp_path / "legalforecast" / "labeling" / "stage.py"
    _write_module(module, "def run():\n    return None\n", lines=520)
    _init_git_repository(tmp_path)
    baseline_path = tmp_path / "architecture.json"
    write_baseline(baseline_path, scan_repository(tmp_path))
    _write_module(module, "def run():\n    return None\n", lines=580)

    assert check_baseline(tmp_path, baseline_path) == ()


def test_baseline_rejects_unreviewed_directory_growth_past_twenty(
    tmp_path: Path,
) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    package = tmp_path / "legalforecast" / "config"
    package.mkdir()
    for index in range(20):
        (package / f"mod_{index}.py").write_text(f"VALUE = {index}\n", encoding="utf-8")
    _init_git_repository(tmp_path)
    baseline_path = tmp_path / "architecture.json"
    write_baseline(baseline_path, scan_repository(tmp_path))
    (package / "mod_20.py").write_text("VALUE = 20\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)

    violations = check_baseline(tmp_path, baseline_path)

    assert any(
        "directory legalforecast/config python_file_count:" in violation
        for violation in violations
    )


def test_baseline_rejects_new_directory_past_twenty(tmp_path: Path) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    _init_git_repository(tmp_path)
    baseline_path = tmp_path / "architecture.json"
    write_baseline(baseline_path, scan_repository(tmp_path))
    package = tmp_path / "legalforecast" / "brand_new"
    package.mkdir()
    for index in range(21):
        (package / f"mod_{index}.py").write_text(f"VALUE = {index}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)

    violations = check_baseline(tmp_path, baseline_path)

    assert any(
        "directory legalforecast/brand_new python_file_count:" in violation
        for violation in violations
    )


def test_baseline_rejects_new_reverse_edge_on_inventoried_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    module = tmp_path / "legalforecast" / "labeling" / "stage.py"
    _write_module(module, "def run():\n    return None\n", lines=520)
    _init_git_repository(tmp_path)
    baseline_path = tmp_path / "architecture.json"
    write_baseline(baseline_path, scan_repository(tmp_path))
    _write_module(
        module,
        "import tests\n\ndef run():\n    return None\n",
        lines=520,
    )

    violations = check_baseline(tmp_path, baseline_path)

    assert any(
        "inventory legalforecast/labeling/stage.py new flags:" in violation
        and "reverse-edge" in violation
        for violation in violations
    )


def test_scan_repository_cache_invalidates_after_git_status_change(
    tmp_path: Path,
) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    _write_module(
        tmp_path / "legalforecast" / "labeling" / "stage.py",
        "def run():\n    return None\n",
        lines=520,
    )
    _init_git_repository(tmp_path)
    write_baseline(tmp_path / BASELINE_PATH, scan_repository(tmp_path))
    first = scan_repository(tmp_path)
    extra_relative = Path("legalforecast") / "labeling" / "extra.py"
    assert extra_relative.as_posix() not in {item.path for item in first.files}

    _write_module(
        tmp_path / extra_relative,
        "def run():\n    return None\n",
        lines=530,
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    second = scan_repository(tmp_path)

    assert extra_relative.as_posix() in {item.path for item in second.files}


def test_ranked_queue_lists_monoliths_before_watch_files(tmp_path: Path) -> None:
    (tmp_path / "legalforecast").mkdir()
    (tmp_path / "legalforecast" / "cli.py").write_text(_cli_source(), encoding="utf-8")
    _write_module(
        tmp_path / "legalforecast" / "labeling" / "stage.py",
        "def run():\n    return None\n",
        lines=520,
    )
    _write_module(
        tmp_path / "legalforecast" / "ingestion" / "store.py",
        "def run():\n    return None\n",
        lines=2100,
    )
    _init_git_repository(tmp_path)

    queue = ranked_queue(scan_repository(tmp_path))

    assert queue[0].path == "legalforecast/ingestion/store.py"
    assert "legalforecast/labeling/stage.py" in {item.path for item in queue}


def test_schema_version_one_payloads_without_inventory_remain_loadable(
    tmp_path: Path,
) -> None:
    from legalforecast.testing.architecture import BASELINE_PATH, load_baseline

    root = Path(__file__).resolve().parents[1]
    baseline = load_baseline(root / BASELINE_PATH)
    payload = {
        "schema_version": 1,
        "cli_metrics": asdict(baseline.cli_metrics),
        "upward_cli_dependencies": list(baseline.upward_cli_dependencies),
        "compatibility": asdict(baseline.compatibility),
    }
    path = tmp_path / "v1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_baseline(path)

    assert loaded.files == ()
    assert loaded.directories == ()
    assert loaded.cycles == ()
