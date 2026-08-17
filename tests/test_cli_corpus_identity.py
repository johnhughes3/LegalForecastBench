from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from legalforecast.testing.cli_corpus.entry_points import (
    ENTRY_POINTS,
    checkout_entry_points,
    expected_entry_points,
    missing_entry_points,
    resolve_entry_point_callables,
    sdist_entry_points,
    wheel_entry_points,
)
from legalforecast.testing.cli_corpus.path_identity import (
    identity_covers_authenticated_cli,
    scan_path_identity,
)
from legalforecast.testing.cli_corpus.paths import IDENTITY_PATH, TIMING_PATH, load_json
from legalforecast.testing.cli_corpus.xdist_timing import (
    critical_path,
    parse_collect_only,
    parse_duration_lines,
    timing_payload,
)

ROOT = Path(__file__).resolve().parents[1]

_DURATION_SAMPLE = """
0.40s call     tests/test_cli.py::test_help
0.10s setup    tests/test_cli.py::test_help
1.50s call     tests/test_cycle_acquisition_store.py::test_commit
0.05s call     tests/test_package_skeleton.py::test_cli_placeholder_prints_help
"""
_COLLECT_SAMPLE = """
tests/test_cli.py::test_help
tests/test_cycle_acquisition_store.py::test_commit
tests/test_cycle_acquisition_store.py::test_replay
tests/test_package_skeleton.py::test_cli_placeholder_prints_help
"""


def test_path_identity_inventory_is_current() -> None:
    generated = scan_path_identity(ROOT)
    checked_in = load_json(ROOT / IDENTITY_PATH)
    assert generated == checked_in
    assert identity_covers_authenticated_cli(generated)
    assert generated["entry_point_names"] == [name for name, _target in ENTRY_POINTS]
    assert "legalforecast/cli.py" in generated["literal_implementation_paths"].get(
        "legalforecast/ingestion/firecrawl_screening_identity.py", []
    )


def test_checkout_entry_points_resolve_all_three_scripts() -> None:
    observed = checkout_entry_points()
    assert observed == expected_entry_points()
    assert missing_entry_points(observed) == ()
    resolved = resolve_entry_point_callables()
    assert set(resolved) == {name for name, _target in ENTRY_POINTS}


def test_installed_entry_points_smoke_help_and_version() -> None:
    version = subprocess.run(
        ["uv", "run", "legalforecast", "--version"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert version.returncode == 0
    assert version.stdout.startswith("legalforecast-mtd ")
    launcher = subprocess.run(
        ["uv", "run", "legalforecast-acquisition-systemd-run", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert launcher.returncode == 0
    assert "--sandbox-path" in launcher.stdout
    provider = subprocess.run(
        ["uv", "run", "legalforecast-provider-env-run", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert provider.returncode == 0
    assert "--provider" in provider.stdout


def test_wheel_and_sdist_entry_points_match_checkout(tmp_path: Path) -> None:
    built = subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stderr
    wheels = list(tmp_path.glob("*.whl"))
    sdists = list(tmp_path.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1
    expected = expected_entry_points()
    assert wheel_entry_points(wheels[0]) == expected
    assert sdist_entry_points(sdists[0]) == expected


def test_xdist_timing_parser_and_critical_path() -> None:
    durations, _rows = parse_duration_lines(_DURATION_SAMPLE)
    counts = parse_collect_only(_COLLECT_SAMPLE)
    payload = timing_payload(test_counts=counts, durations=durations)
    assert payload["command"].endswith("--dist=loadscope --durations=0")
    assert payload["dist"] == "loadscope"
    assert payload["workers"] == 4
    assert payload["critical_path"][0] == "tests/test_cycle_acquisition_store.py"
    assert payload["modules"]["tests/test_cli.py"]["duration_seconds"] == 0.5
    assert (
        payload["modules"]["tests/test_cycle_acquisition_store.py"]["test_count"] == 2
    )
    ranked = critical_path(payload["modules"], limit=2)
    assert ranked[0] == "tests/test_cycle_acquisition_store.py"
    assert payload["durations_recorded"] is True
    assert payload["critical_path_rank"] == "duration"

    counts_only = timing_payload(test_counts=counts)
    assert counts_only["durations_recorded"] is False
    assert counts_only["critical_path_rank"] == "test_count"


def test_xdist_timing_baseline_exists_and_names_loadscope_shards() -> None:
    payload = load_json(ROOT / TIMING_PATH)
    assert payload["schema_version"] == 1
    assert payload["dist"] == "loadscope"
    assert payload["workers"] == 4
    assert payload["durations_recorded"] is True
    assert payload["critical_path_rank"] == "duration"
    modules = payload["modules"]
    assert "tests/test_architecture.py" in modules
    assert "tests/test_cycle_acquisition_store.py" in modules
    assert payload["critical_path"]
    assert all(path in modules for path in payload["critical_path"])
    # A duration-ranked baseline must actually be ordered by runtime, and the
    # head of the critical path must carry a measured duration rather than the
    # nulls a --collect-only-only capture leaves behind.
    ranked = [modules[path]["duration_seconds"] for path in payload["critical_path"]]
    assert ranked[0] is not None
    measured = [seconds for seconds in ranked if seconds is not None]
    assert measured == sorted(measured, reverse=True)
    assert len(measured) == len(ranked)


def test_write_timing_requires_durations_file() -> None:
    from legalforecast.testing.cli_corpus.reporting import main

    with pytest.raises(SystemExit) as excinfo:
        main(["--write-timing"])
    assert excinfo.value.code == 2


def test_write_timing_records_durations_from_supplied_files(tmp_path: Path) -> None:
    from legalforecast.testing.cli_corpus.reporting import main

    collect = tmp_path / "collect.txt"
    collect.write_text(_COLLECT_SAMPLE.lstrip(), encoding="utf-8")
    durations = tmp_path / "durations.txt"
    durations.write_text(_DURATION_SAMPLE.lstrip(), encoding="utf-8")
    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "--write-timing",
                "--collect-only-file",
                str(collect),
                "--durations-file",
                str(durations),
            ]
        )
        == 0
    )
    payload = load_json(tmp_path / TIMING_PATH)
    assert payload["durations_recorded"] is True
    assert payload["critical_path_rank"] == "duration"
    assert payload["modules"]["tests/test_cli.py"]["duration_seconds"] == 0.5
