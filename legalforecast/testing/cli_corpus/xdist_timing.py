"""Parse pytest durations and xdist loadscope module critical paths."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from legalforecast.testing.cli_corpus.paths import (
    TIMING_SCHEMA_VERSION,
    as_object_dict,
    load_json,
)

_DURATION_LINE = re.compile(
    r"^(?P<seconds>[0-9]+(?:\.[0-9]+)?)s\s+(?P<phase>\S+)\s+(?P<nodeid>\S+)\s*$"
)
_COLLECT_LINE = re.compile(r"^(?P<nodeid>tests/\S+::\S+)\s*$")
_CRITICAL_PATH_LIMIT = 25
SUPPORTED_XDIST_COMMAND = "uv run pytest -q -n 4 --dist=loadscope --durations=0"


def parse_duration_lines(text: str) -> tuple[dict[str, float], dict[str, int]]:
    """Sum pytest ``--durations`` rows by test module path."""

    durations: dict[str, float] = {}
    counts: Counter[str] = Counter()
    for line in text.splitlines():
        match = _DURATION_LINE.match(line.strip())
        if match is None:
            continue
        nodeid = match.group("nodeid")
        module = nodeid.split("::", 1)[0]
        durations[module] = durations.get(module, 0.0) + float(match.group("seconds"))
        counts[module] += 1
    return dict(sorted(durations.items())), dict(sorted(counts.items()))


def parse_collect_only(text: str) -> dict[str, int]:
    """Count collected tests per module from ``pytest --collect-only -q``."""

    counts: Counter[str] = Counter()
    for line in text.splitlines():
        match = _COLLECT_LINE.match(line.strip())
        if match is None:
            continue
        module = match.group("nodeid").split("::", 1)[0]
        counts[module] += 1
    return dict(sorted(counts.items()))


def critical_path(
    modules: Mapping[str, Mapping[str, object]],
    *,
    limit: int = _CRITICAL_PATH_LIMIT,
) -> tuple[str, ...]:
    """Rank loadscope shards by duration when present, else by test count."""

    ranked = sorted(
        modules.items(),
        key=lambda item: (
            -_optional_float(item[1].get("duration_seconds")),
            -_optional_int(item[1].get("test_count")),
            item[0],
        ),
    )
    return tuple(path for path, _record in ranked[:limit])


def timing_payload(
    *,
    test_counts: Mapping[str, int],
    durations: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Build the checked-in xdist module timing baseline."""

    modules: dict[str, dict[str, object]] = {}
    for path, count in sorted(test_counts.items()):
        record: dict[str, object] = {"test_count": count, "duration_seconds": None}
        if durations is not None and path in durations:
            record["duration_seconds"] = round(durations[path], 6)
        modules[path] = record
    if durations:
        for path, seconds in durations.items():
            modules.setdefault(
                path, {"test_count": 0, "duration_seconds": round(seconds, 6)}
            )
    payload_modules = dict(sorted(modules.items()))
    return {
        "schema_version": TIMING_SCHEMA_VERSION,
        "command": SUPPORTED_XDIST_COMMAND,
        "dist": "loadscope",
        "workers": 4,
        "critical_path": list(critical_path(payload_modules)),
        "modules": payload_modules,
    }


def load_timing_baseline(root: Path, relative: Path) -> dict[str, object]:
    """Load a checked-in timing baseline object."""

    return as_object_dict(load_json(root / relative))


def _optional_float(value: object) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _optional_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
