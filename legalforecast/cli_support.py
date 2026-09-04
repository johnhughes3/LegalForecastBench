"""Small helpers shared by the retained public CLI command adapters.

The benchmark CLI used to be the home of the entire corpus-construction
pipeline.  Public scoring and reporting only need a few JSON and artifact
helpers, so they live here instead of importing a retired acquisition facade.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.reporting.leaderboard import BenchmarkLeaderboardReport

JsonRecord = dict[str, Any]


def read_records(path: Path) -> list[JsonRecord]:
    """Read a JSONL file containing object records."""

    if not path.is_file():
        raise FileNotFoundError(path)
    records: list[JsonRecord] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        records.append(dict(cast(Mapping[str, Any], value)))
    return records


def read_json_object(path: Path) -> JsonRecord:
    """Read one JSON object from ``path``."""

    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(cast(Mapping[str, Any], value))


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    """Write canonical object-per-line JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(dict(record), sort_keys=True, allow_nan=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one readable JSON object."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def required_record_sequence(
    record: Mapping[str, Any], field_name: str
) -> tuple[JsonRecord, ...]:
    """Decode a required JSON array of objects."""

    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list")
    result: list[JsonRecord] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} items must be objects")
        result.append(dict(cast(Mapping[str, Any], item)))
    return tuple(result)


def write_dry_run_plan(
    command: str,
    plan_path: Path,
    *,
    output_paths: Sequence[Path],
    record_count: int,
    input_path: Path | None = None,
    log_record_count: int | None = None,
    **extra: Any,
) -> int:
    """Write the stable dry-run description used by public adapters."""

    record: JsonRecord = {
        "command": command,
        "dry_run": True,
        "record_count": record_count,
        "output_paths": [str(path) for path in output_paths],
    }
    if input_path is not None:
        record["input_path"] = str(input_path)
    record.update(extra)
    write_json(plan_path, record)
    log_event(command, "dry_run", plan_path, log_record_count)
    return 0


def log_event(
    stage: str,
    event: str,
    artifact_path: Path,
    record_count: int | None = None,
) -> None:
    """Emit one machine-readable progress event on stderr."""

    payload: JsonRecord = {
        "stage": stage,
        "event": event,
        "artifact_path": str(artifact_path),
    }
    if record_count is not None:
        payload["record_count"] = record_count
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)


def report_paths(output_dir: Path) -> tuple[Path, Path, Path, Path]:
    """Return the four standard leaderboard artifact paths."""

    return tuple(
        output_dir / name
        for name in (
            "leaderboard.json",
            "leaderboard.csv",
            "leaderboard.md",
            "leaderboard.html",
        )
    )  # type: ignore[return-value]


def write_report_artifacts(
    report: BenchmarkLeaderboardReport,
    *,
    json_path: Path,
    csv_path: Path,
    markdown_path: Path,
    html_path: Path,
    generated_at: datetime,
) -> None:
    """Persist all standard leaderboard formats."""

    write_json(
        json_path,
        {"generated_at": iso_datetime(generated_at), **report.to_record()},
    )
    for path, text in (
        (csv_path, report.to_csv()),
        (markdown_path, report.to_markdown()),
        (html_path, report.to_html()),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def artifact_generated_at(
    *,
    locked_at: datetime | None = None,
    recorded_generated_at: object | None = None,
) -> datetime:
    """Stamp score and report JSON from the locked run, not the wall clock.

    Fan-in retries compare exact object bytes. A clock reading would change
    ``generated_at`` on every rerun and make reconcile refuse the already
    published scores and report.
    """

    if locked_at is not None:
        if locked_at.tzinfo is None or locked_at.utcoffset() is None:
            raise ValueError("locked run timestamp must be timezone-aware")
        return locked_at
    if recorded_generated_at is None:
        return datetime.now(UTC)
    if not isinstance(recorded_generated_at, str) or not recorded_generated_at:
        raise ValueError("score artifact generated_at must be a timestamp")
    parsed = datetime.fromisoformat(recorded_generated_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("score artifact generated_at must be timezone-aware")
    return parsed


def iso_datetime(value: datetime) -> str:
    """Format an aware datetime in the repository's canonical UTC form."""

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
