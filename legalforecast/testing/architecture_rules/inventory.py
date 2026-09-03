"""Repository-wide file inventory, package lanes, and directory ceilings."""

from __future__ import annotations

import hashlib
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from legalforecast.testing.architecture_rules.cli_compatibility import (
    CliMetrics,
    CompatibilityInventory,
    scan_cli_metrics,
    scan_test_compatibility,
    scan_upward_cli_dependencies,
)
from legalforecast.testing.architecture_rules.imports import (
    cycle_membership,
    literal_legalforecast_python_paths,
    production_import_graph,
    reverse_adapter_dependencies,
    strongly_connected_components,
    tracked_python_files,
    uses_file_relative_resolution,
)
from legalforecast.testing.architecture_rules.symbols import (
    FileMetrics,
    measure_python_file,
    python_paths,
)

BASELINE_PATH: Path = Path("legalforecast/testing/architecture_baseline.json")
WATCH_LINE_THRESHOLD = 500
OVERSIZED_LINE_THRESHOLD = 1000
MONOLITH_LINE_THRESHOLD = 2000
LARGE_SYMBOL_THRESHOLD = 400
NO_MOVE_PATHS: frozenset[str] = frozenset(
    {
        "legalforecast/ingestion/canonical_json.py",
        "legalforecast/ingestion/provenance.py",
        "legalforecast/_canonical.py",
    }
)
_LANE_BEADS: dict[str, str] = {
    "cli": "LegalForecastBench-cwdv",
    "console": "LegalForecastBench-cwdv",
    "ingestion": "LegalForecastBench-l8qv.15",
    "labeling": "legalforecastbench-m1pv.3",
    "unitization": "legalforecastbench-m1pv.4",
    "evals": "legalforecastbench-m1pv.5",
    "publication": "legalforecastbench-m1pv.5",
    "multiharness": "legalforecastbench-m1pv.6",
    "tests": "legalforecastbench-m1pv.7",
    "scripts": "legalforecastbench-m1pv.7",
    "examples": "legalforecastbench-m1pv.7",
    "testing": "legalforecastbench-m1pv.1",
    "protocol": "LegalForecastBench-l8qv.9",
    "config": "legalforecastbench-m1pv",
    "contracts": "legalforecastbench-m1pv",
    "document_need": "legalforecastbench-m1pv",
    "extraction": "legalforecastbench-m1pv",
    "reporting": "legalforecastbench-m1pv",
    "selection": "legalforecastbench-m1pv",
    "root": "legalforecastbench-m1pv",
    "other": "legalforecastbench-m1pv",
}


@dataclass(frozen=True, slots=True)
class FileInventoryRecord:
    """Measured ownership and risk flags for one tracked Python file."""

    path: str
    line_count: int
    nonblank_line_count: int
    top_level_definition_count: int
    largest_symbol: str
    largest_symbol_lines: int
    lane_owner: str
    layer: str
    fan_in: int
    fan_out: int
    cycle_id: str
    churn_90d: int
    flags: tuple[str, ...]
    disposition_kind: str
    disposition_owner: str


@dataclass(frozen=True, slots=True)
class DirectoryRecord:
    """Flat Python-file count for one directory."""

    path: str
    python_file_count: int


@dataclass(frozen=True, slots=True)
class RepositoryInventory:
    """CLI ratchet facts plus the repository-wide generated inventory."""

    cli_metrics: CliMetrics
    upward_cli_dependencies: tuple[str, ...]
    compatibility: CompatibilityInventory
    files: tuple[FileInventoryRecord, ...]
    directories: tuple[DirectoryRecord, ...]
    cycles: tuple[tuple[str, ...], ...]


_GIT_SCAN_CACHE: dict[str, RepositoryInventory] = {}


def scan_repository(root: Path) -> RepositoryInventory:
    """Measure CLI structure, test coupling, and every tracked Python file."""

    resolved_root = root.resolve()
    cacheable = (resolved_root / BASELINE_PATH).is_file()
    cache_key = _scan_cache_key(resolved_root) if cacheable else None
    if cache_key is not None:
        cached = _GIT_SCAN_CACHE.get(cache_key)
        if cached is not None:
            return cached
    snapshot = _scan_repository(resolved_root)
    if cache_key is not None:
        _GIT_SCAN_CACHE[cache_key] = snapshot
    return snapshot


def _scan_cache_key(resolved_root: Path) -> str | None:
    fingerprint = _repository_scan_fingerprint(resolved_root)
    if fingerprint is None:
        return None
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    return f"{resolved_root}::{digest}"


def _repository_scan_fingerprint(resolved_root: Path) -> str | None:
    head = subprocess.run(
        ["git", "-C", str(resolved_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if head.returncode != 0:
        return None
    status = subprocess.run(
        ["git", "-C", str(resolved_root), "status", "--porcelain=v1", "-z"],
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        return None
    return f"{head.stdout}\0{status.stdout}"


def _scan_repository(resolved_root: Path) -> RepositoryInventory:
    graph = production_import_graph(resolved_root)
    cycles = strongly_connected_components(graph)
    cycle_members = cycle_membership(cycles)
    cycle_ids = {
        path: ",".join(component) for component in cycles for path in component
    }
    fan_out = {path: len(targets) for path, targets in graph.items()}
    fan_in_counts: Counter[str] = Counter()
    for targets in graph.values():
        fan_in_counts.update(targets)
    reverse_edges = frozenset(reverse_adapter_dependencies(resolved_root))
    churn = commit_counts_90d(resolved_root)
    tracked = python_files_for_inventory(resolved_root)
    records: list[FileInventoryRecord] = []
    for relative in tracked:
        metrics = measure_python_file(resolved_root, relative)
        if metrics is None:
            continue
        records.append(
            _record_from_metrics(
                metrics,
                fan_in=fan_in_counts.get(relative, 0),
                fan_out=fan_out.get(relative, 0),
                cycle_id=cycle_ids.get(relative, ""),
                in_cycle=relative in cycle_members,
                churn_90d=churn.get(relative, 0),
                reverse_edge=relative in reverse_edges,
                relative_path=uses_file_relative_resolution(resolved_root / relative)
                or bool(literal_legalforecast_python_paths(resolved_root / relative)),
            )
        )
    directories = directory_records(tracked)
    return RepositoryInventory(
        cli_metrics=scan_cli_metrics(resolved_root),
        upward_cli_dependencies=scan_upward_cli_dependencies(resolved_root),
        compatibility=scan_test_compatibility(resolved_root),
        files=tuple(records),
        directories=directories,
        cycles=cycles,
    )


def python_files_for_inventory(root: Path) -> tuple[str, ...]:
    """Return tracked Python files, or a filesystem walk when git is unavailable."""

    tracked = tracked_python_files(root)
    if tracked:
        return tracked
    collected: list[str] = []
    for package in ("legalforecast", "tests", "scripts", "examples"):
        directory = root / package
        if directory.is_dir():
            collected.extend(python_paths(directory))
    return tuple(sorted(collected))


def directory_records(paths: tuple[str, ...]) -> tuple[DirectoryRecord, ...]:
    """Count Python files in each parent directory."""

    counts: Counter[str] = Counter()
    for path in paths:
        parent = str(Path(path).parent)
        if parent == ".":
            parent = ""
        counts[parent] += 1
    return tuple(
        DirectoryRecord(path=directory, python_file_count=count)
        for directory, count in sorted(counts.items())
    )


def commit_counts_90d(root: Path) -> dict[str, int]:
    """Count commits touching each Python file in the trailing 90 days."""

    since = (datetime.now(UTC) - timedelta(days=90)).date().isoformat()
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "log",
            f"--since={since}",
            "--name-only",
            "--pretty=format:",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {}
    counts: Counter[str] = Counter()
    for line in completed.stdout.splitlines():
        if line.endswith(".py") and not line.startswith(".github/"):
            counts[line] += 1
    return dict(counts)


def lane_owner(path: str) -> str:
    """Return the package-lane owner for ``path``."""

    if path.startswith("tests/"):
        return "tests"
    if path.startswith("scripts/"):
        return "scripts"
    if path.startswith("examples/"):
        return "examples"
    if path == "legalforecast/cli.py" or path.startswith("legalforecast/cli_commands/"):
        return "cli"
    if path.startswith("legalforecast/console/"):
        return "console"
    prefixes = (
        "ingestion",
        "labeling",
        "unitization",
        "evals",
        "publication",
        "multiharness",
        "testing",
        "protocol",
        "config",
        "contracts",
        "document_need",
        "extraction",
        "reporting",
        "selection",
    )
    for name in prefixes:
        prefix = f"legalforecast/{name}"
        if path == f"{prefix}.py" or path.startswith(f"{prefix}/"):
            return name
    if path.startswith("legalforecast/"):
        return "root"
    return "other"


def architectural_layer(path: str) -> str:
    """Return a coarse architectural layer derived from path."""

    if path.startswith(("tests/", "legalforecast/testing/")):
        return "test"
    if (
        path in {"legalforecast/cli.py", "legalforecast/__init__.py"}
        or path.startswith(("scripts/", "examples/"))
        or path.endswith("/infisical_systemd_launcher.py")
    ):
        return "entrypoint"
    if path.startswith(
        ("legalforecast/console/", "legalforecast/cli_commands/")
    ) or path.endswith("_cli.py"):
        return "adapter"
    if path.startswith(
        (
            "legalforecast/contracts/",
            "legalforecast/protocol/",
            "legalforecast/config/",
            "legalforecast/document_need/",
            "legalforecast/extraction/",
            "legalforecast/selection/",
            "legalforecast/reporting/",
        )
    ) or path in {
        "legalforecast/_hashing.py",
        "legalforecast/_json_io.py",
        "legalforecast/_datetime.py",
        "legalforecast/_record_validation.py",
        "legalforecast/path_safety.py",
        "legalforecast/logging.py",
    }:
        return "domain"
    return "application"


def is_reviewed_inventory_record(record: FileInventoryRecord) -> bool:
    """Return whether a measured file belongs in the reviewed inventory gate."""

    if record.line_count >= WATCH_LINE_THRESHOLD:
        return True
    if record.disposition_kind in {"planned-seam", "no-move", "exemption"}:
        return True
    if set(record.flags) & {"authenticated-path", "cycle", "reverse-edge"}:
        return True
    return "relative-path" in record.flags and not record.path.startswith("tests/")


def requires_manual_disposition(
    *,
    line_count: int,
    largest_symbol_lines: int,
    flags: tuple[str, ...],
) -> bool:
    """Return whether a file crosses a manual-disposition threshold."""

    return (
        line_count >= OVERSIZED_LINE_THRESHOLD
        or largest_symbol_lines >= LARGE_SYMBOL_THRESHOLD
        or bool(
            set(flags)
            & {
                "authenticated-path",
                "cycle",
                "reverse-edge",
            }
        )
    )


def _record_from_metrics(
    metrics: FileMetrics,
    *,
    fan_in: int,
    fan_out: int,
    cycle_id: str,
    in_cycle: bool,
    churn_90d: int,
    reverse_edge: bool,
    relative_path: bool,
) -> FileInventoryRecord:
    flags: list[str] = []
    if metrics.path in NO_MOVE_PATHS:
        flags.append("authenticated-path")
    if relative_path:
        flags.append("relative-path")
    if in_cycle:
        flags.append("cycle")
    if reverse_edge:
        flags.append("reverse-edge")
    if metrics.line_count >= MONOLITH_LINE_THRESHOLD:
        flags.append("monolith")
    elif metrics.line_count >= OVERSIZED_LINE_THRESHOLD:
        flags.append("oversized")
    elif metrics.line_count >= WATCH_LINE_THRESHOLD:
        flags.append("watch")
    flag_tuple = tuple(flags)
    owner = lane_owner(metrics.path)
    if metrics.path in NO_MOVE_PATHS:
        kind = "no-move"
        disposition_owner = metrics.path
    elif requires_manual_disposition(
        line_count=metrics.line_count,
        largest_symbol_lines=metrics.largest_symbol_lines,
        flags=flag_tuple,
    ):
        kind = "planned-seam"
        disposition_owner = _LANE_BEADS.get(owner, "legalforecastbench-m1pv")
    elif metrics.line_count >= WATCH_LINE_THRESHOLD:
        kind = "watch"
        disposition_owner = owner
    else:
        kind = "below-watch"
        disposition_owner = owner
    return FileInventoryRecord(
        path=metrics.path,
        line_count=metrics.line_count,
        nonblank_line_count=metrics.nonblank_line_count,
        top_level_definition_count=metrics.top_level_definition_count,
        largest_symbol=metrics.largest_symbol,
        largest_symbol_lines=metrics.largest_symbol_lines,
        lane_owner=owner,
        layer=architectural_layer(metrics.path),
        fan_in=fan_in,
        fan_out=fan_out,
        cycle_id=cycle_id,
        churn_90d=churn_90d,
        flags=flag_tuple,
        disposition_kind=kind,
        disposition_owner=disposition_owner,
    )
