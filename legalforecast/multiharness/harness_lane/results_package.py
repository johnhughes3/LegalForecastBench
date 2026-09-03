"""Package one containerized harness-lane run for upload to the results bucket.

The lane's question is whether an agentic CLI beats the bare provider API on the
same task, so the interesting evidence is exactly the evidence that cannot be
published: the harness's own transcripts.  They carry the operator's container
environment, and on a Harvey LAB row the staged case documents too.  So the run
splits in two, and this module is the split:

``<run>/full-results.zip``
    Every byte the run wrote -- run manifest, canonical rows, release receipts,
    LFB score rows, per-row container logs and private logs.  Private.  It
    travels the way :mod:`legalforecast.publication.manifest_run_source_package`
    already moves private source into an OIDC job: one deterministic archive,
    age-encrypted, uploaded as an asset on a never-published *draft* release, and
    pinned by exact digest at dispatch.  ``.github/workflows/
    stage-harness-lane-results.yaml`` is the other half.

``harness-lane-summary.json``
    Constructed, not scrubbed.  Every field is copied from an adapter
    ``public_summary`` that already passed
    :func:`~legalforecast.multiharness.validation.validate_public_record`, or is
    a count or a digest computed here.  Nothing is read out of
    ``row-results.jsonl``, whose ``workspace`` field is an absolute host path.
    This file is safe to commit to this public repository, and the workflow
    stages the repository's own tracked copy rather than one that travelled --
    so what lands in S3 beside the archive is the reviewed bytes.

The two are bound by ``package_sha256``: the summary names the archive it
describes, the archive is content-addressed into its own prefix, and the
workflow refuses a ciphertext that does not decrypt to that digest.  Re-running
a dispatch therefore rewrites the same keys with the same bytes, which is what
makes it safe under create-only puts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._json_io import read_json_object, read_jsonl_objects
from legalforecast.multiharness.validation import validate_public_record
from legalforecast.protocol.freeze import sha256_file

HARNESS_LANE_RESULTS_SCHEMA_VERSION: Final = "legalforecast-harness-lane-results-v1"

#: Results-bucket root for this lane.  Deliberately NOT under
#: ``cycle-1/manifest-runs/``: that namespace is create-once with no delete
#: grant on any role, is fenced as a two-lane space by
#: ``.github/scripts/assert-manifest-run-lane.sh``, and is inside the read scope
#: of the cell and prepare-inputs roles, whose charter is corpus manifests and
#: model packets rather than harness transcripts.
RESULTS_PREFIX_ROOT: Final = "cycle-1/harness-lane"
ARCHIVE_OBJECT_NAME: Final = "full-results.zip"
SUMMARY_OBJECT_NAME: Final = "harness-lane-summary.json"

# An order of magnitude above a realistic 100-row lane run (a few hundred MB of
# transcripts across a few thousand files), and well inside the 2 GiB GitHub
# release-asset limit.  Tight enough that a runaway transcript is refused here
# rather than at upload time.
MAX_MEMBER_BYTES: Final = 256 * 1024 * 1024
MAX_TOTAL_BYTES: Final = 1024 * 1024 * 1024
MAX_MEMBER_COUNT: Final = 50_000

RUN_MANIFEST_NAME: Final = "run-manifest.json"
CANONICAL_RUNS_NAME: Final = "canonical-runs.jsonl"
RELEASE_RECEIPTS_NAME: Final = "release-harness-receipts.jsonl"
LFB_RUNS_NAME: Final = "lfb/runs.jsonl"
ARCHIVE_MEMBER_ROOT: Final = "run"

#: Identity fields copied verbatim from ``public_summary``.  Every row in one
#: harness group must agree on all of them; a disagreement means two different
#: things were labelled one harness and is refused rather than averaged.
_IDENTITY_FIELDS: Final = (
    "adapter_id",
    "adapter_version",
    "auth_mode",
    "container_image_digest",
    "executable",
    "execution_backend",
    "harness",
    "harness_track",
    "model_key",
    "native_tools_enabled",
    "server_side_web_tools_disabled",
    "tool_policy",
    "tool_use_reporting",
)

# Two or more slash-separated segments after a leading slash, or a leading "~/".
# Catches /home/<user>/..., /Users/..., /run/user/<uid>/..., ~/.claude/... while
# leaving registry references such as ghcr.io/owner/image@sha256:... alone,
# because those do not start with a separator.
_ABSOLUTE_PATH: Final = re.compile(
    r"(?:(?<=^)|(?<=[\s\"'=,]))(?:~/|(?:/[^\s/\"']+){2})"
)


class HarnessLaneResultsError(ValueError):
    """Raised when a run directory cannot form a safe results package."""


@dataclass(frozen=True, slots=True)
class HarnessLaneResultsPackage:
    """What the operator pins at dispatch after one local build."""

    package_path: Path
    package_sha256: str
    package_size_bytes: int
    summary_path: Path
    summary_sha256: str

    @property
    def prefix(self) -> str:
        """Return the content-addressed results-bucket prefix."""

        return f"{RESULTS_PREFIX_ROOT}/{self.package_sha256}"

    @property
    def asset_name(self) -> str:
        """Return the draft-release asset name the workflow requires."""

        return source_asset_name(self.package_sha256)

    def to_record(self) -> dict[str, Any]:
        """Return the operator-facing record printed by ``build``."""

        return {
            "schema_version": HARNESS_LANE_RESULTS_SCHEMA_VERSION,
            "asset_name": self.asset_name,
            "package_path": self.package_path.as_posix(),
            "package_sha256": self.package_sha256,
            "package_size_bytes": self.package_size_bytes,
            "prefix": self.prefix,
            "summary_path": self.summary_path.as_posix(),
            "summary_sha256": self.summary_sha256,
        }


def source_asset_name(package_sha256: str) -> str:
    """Return the digest-bound ciphertext asset name for a dispatch."""

    _require_sha256(package_sha256, "package_sha256")
    return f"harness-lane-results-{package_sha256}.zip.age"


def build_harness_lane_results_package(
    *, run_dir: Path, output_dir: Path
) -> HarnessLaneResultsPackage:
    """Write the private archive and the public summary for one run directory."""

    summary = harness_lane_public_summary(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / ARCHIVE_OBJECT_NAME
    summary_path = output_dir / SUMMARY_OBJECT_NAME
    for path in (package_path, summary_path):
        if path.exists():
            raise HarnessLaneResultsError(f"refusing to replace {path}")
    _write_archive(package_path, _archive_members(run_dir))
    package_sha256 = sha256_file(package_path)
    summary["package_sha256"] = package_sha256
    summary_bytes = _canonical_summary_bytes(summary)
    summary_path.write_bytes(summary_bytes)
    return HarnessLaneResultsPackage(
        package_path=package_path,
        package_sha256=package_sha256,
        package_size_bytes=package_path.stat().st_size,
        summary_path=summary_path,
        summary_sha256=hashlib.sha256(summary_bytes).hexdigest(),
    )


def harness_lane_public_summary(run_dir: Path) -> dict[str, Any]:
    """Return the publishable description of one harness-lane run.

    Built only from ``run-manifest.json`` and the ``public_summary`` of each
    canonical result.  ``row-results.jsonl`` is never read: its ``workspace``
    field is an absolute path on the operator's machine.
    """

    manifest = _read_object(run_dir / RUN_MANIFEST_NAME)
    results = _read_records(run_dir / CANONICAL_RUNS_NAME)
    if not results:
        raise HarnessLaneResultsError(f"{run_dir} holds no canonical run rows")
    summary: dict[str, Any] = {
        "schema_version": HARNESS_LANE_RESULTS_SCHEMA_VERSION,
        "run_id": _require_str(manifest, "run_id"),
        "selection_sha256": _require_str(manifest, "selection_sha256"),
        "run_config_sha256": _require_str(manifest, "run_config_sha256"),
        "run_manifest_sha256": sha256_file(run_dir / RUN_MANIFEST_NAME),
        "result_count": len(results),
        "status_counts": _counts(str(row.get("status", "")) for row in results),
        "release_receipt_count": _line_count(run_dir / RELEASE_RECEIPTS_NAME),
        "lfb_row_count": _line_count(run_dir / LFB_RUNS_NAME),
        "harnesses": _harness_groups(results),
    }
    validate_public_record(summary, "harness_lane_public_summary")
    _require_no_host_paths(summary, "harness_lane_public_summary")
    return summary


def _harness_groups(results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in results:
        public = row.get("public_summary")
        if not isinstance(public, Mapping):
            raise HarnessLaneResultsError(
                f"canonical result {row.get('result_id')!r} carries no public summary"
            )
        typed = cast(Mapping[str, Any], public)
        key = (
            _require_str(typed, "adapter_id"),
            _require_str(typed, "adapter_version"),
            _require_str(typed, "model_key"),
        )
        grouped.setdefault(key, []).append(typed)
    return [_harness_group(grouped[key]) for key in sorted(grouped)]


def _harness_group(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    group: dict[str, Any] = {}
    # Adapter-raised failures and web-fence refusals may omit identity fields
    # or carry a different observed posture.  The harness identity is the
    # succeeded rows'; failed rows still count in status and failure_class.
    identity_rows = [row for row in rows if row.get("failure_class") is None]
    source = identity_rows or list(rows)
    for field in _IDENTITY_FIELDS:
        present = [row[field] for row in source if field in row]
        if not present:
            raise HarnessLaneResultsError(
                f"rows of one harness all omit {field}; refusing to summarize"
            )
        values = {json.dumps(value, sort_keys=True) for value in present}
        if len(values) != 1:
            raise HarnessLaneResultsError(
                f"rows of one harness disagree on {field}; refusing to summarize"
            )
        group[field] = present[0]
    allowlist_rows = [row for row in source if "egress_allowlist" in row] or [
        row for row in rows if "egress_allowlist" in row
    ]
    allowlists = {
        json.dumps(row["egress_allowlist"], sort_keys=True) for row in allowlist_rows
    }
    if allowlist_rows and len(allowlists) != 1:
        raise HarnessLaneResultsError(
            "rows of one harness ran under different egress allowlists"
        )
    group["egress_allowlist"] = (
        allowlist_rows[0]["egress_allowlist"] if allowlist_rows else None
    )
    group["egress_allowed_hosts"] = sorted(
        {host for row in rows for host in _str_list(row, "egress_allowed_hosts")}
    )
    group["egress_refused"] = _unique_records(
        record for row in rows for record in _record_list(row, "egress_refused")
    )
    group["tools_observed"] = sorted(
        {tool for row in rows for tool in _str_list(row, "allowed_tools")}
    )
    group["row_count"] = len(rows)
    group["failure_class_counts"] = _counts(
        "none" if row.get("failure_class") is None else str(row.get("failure_class"))
        for row in rows
    )
    group["timed_out_count"] = sum(1 for row in rows if row.get("timed_out") is True)
    group["nonzero_exit_count"] = sum(1 for row in rows if row.get("exit_code") != 0)
    group["duration_seconds_total"] = round(
        sum(float(row.get("duration_seconds") or 0.0) for row in rows), 3
    )
    return group


def _archive_members(run_dir: Path) -> dict[str, bytes]:
    if not run_dir.is_dir() or run_dir.is_symlink():
        raise HarnessLaneResultsError(f"run directory is not a directory: {run_dir}")
    members: dict[str, bytes] = {}
    total = 0
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink():
            # Refused rather than followed: a symlink in a run directory would
            # pull bytes from outside the run into a private upload.
            raise HarnessLaneResultsError(f"run directory contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(run_dir).as_posix()
        size = path.stat().st_size
        if size > MAX_MEMBER_BYTES:
            raise HarnessLaneResultsError(
                f"run file exceeds the size limit: {relative}"
            )
        total += size
        if total > MAX_TOTAL_BYTES:
            raise HarnessLaneResultsError("run directory exceeds the total size limit")
        members[f"{ARCHIVE_MEMBER_ROOT}/{relative}"] = path.read_bytes()
        if len(members) > MAX_MEMBER_COUNT:
            raise HarnessLaneResultsError("run directory exceeds the member limit")
    if not members:
        raise HarnessLaneResultsError(f"run directory holds no files: {run_dir}")
    return members


def _write_archive(package_out: Path, members: Mapping[str, bytes]) -> None:
    """Write a stored-only archive with a fixed timestamp.

    Deterministic on purpose: the dispatch pins this archive's digest, so two
    builds of the same run directory have to produce the same bytes or the pin
    is only verifiable by whoever built it.
    """

    with zipfile.ZipFile(package_out, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(members.items()):
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, payload)


def _canonical_summary_bytes(summary: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(summary), indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _require_no_host_paths(value: Any, path: str) -> None:
    """Refuse any string that reads as a filesystem path on somebody's machine."""

    if isinstance(value, Mapping):
        typed_map = cast(Mapping[str, Any], value)
        for key, child in typed_map.items():
            _require_no_host_paths(str(key), f"{path}.key")
            _require_no_host_paths(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        typed_seq = cast(Sequence[Any], value)
        for index, child in enumerate(typed_seq):
            _require_no_host_paths(child, f"{path}[{index}]")
        return
    if isinstance(value, str) and _ABSOLUTE_PATH.search(value) is not None:
        raise HarnessLaneResultsError(
            f"{path} contains a host filesystem path; it must not be published"
        )


def _counts(values: Iterable[object]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values).items()))


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return len(_read_records(path))


def _read_object(path: Path) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=HarnessLaneResultsError,
        missing_message=lambda item: f"harness-lane run is missing {item.name}",
        non_object_message=lambda item: f"{item.name} is not a JSON object",
    )


def _read_records(path: Path) -> list[dict[str, Any]]:
    return read_jsonl_objects(
        path,
        error_factory=HarnessLaneResultsError,
        missing_message=lambda item: f"harness-lane run is missing {item.name}",
        non_object_message=lambda item, line: (
            f"{item.name} line {line} is not an object"
        ),
    )


def _str_list(row: Mapping[str, Any], field: str) -> list[str]:
    raw = row.get(field, [])
    if not isinstance(raw, (list, tuple)):
        raise HarnessLaneResultsError(f"public summary {field} is not a list")
    return [str(item) for item in cast(Sequence[Any], raw)]


def _record_list(row: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    raw = row.get(field, [])
    if not isinstance(raw, (list, tuple)):
        raise HarnessLaneResultsError(f"public summary {field} is not a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[Any], raw):
        if not isinstance(item, Mapping):
            raise HarnessLaneResultsError(f"public summary {field} holds a non-object")
        records.append(cast(Mapping[str, Any], item))
    return records


def _unique_records(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for record in records:
        seen[json.dumps(dict(record), sort_keys=True)] = dict(record)
    return [seen[key] for key in sorted(seen)]


def _require_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise HarnessLaneResultsError(f"{field} must be a non-empty string")
    return value


def _require_sha256(value: str, field: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise HarnessLaneResultsError(f"{field} must be a lowercase SHA-256 digest")


BUILD_DESCRIPTION: Final = (
    "Package one containerized harness-lane run: a deterministic private archive "
    "of the whole run directory, and the public summary that describes it. The "
    "archive is private -- age-encrypt it and upload only the ciphertext as an "
    "asset on a never-published DRAFT release; never commit it. Commit the "
    "summary, and pass the printed package_sha256 and asset_name to "
    "stage-harness-lane-results.yaml."
)


def main(argv: Sequence[str] | None = None) -> int:
    """Build one results package from a completed run directory."""

    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.multiharness.harness_lane.results_package",
        description=BUILD_DESCRIPTION,
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    package = build_harness_lane_results_package(
        run_dir=args.run_dir, output_dir=args.output_dir
    )
    json.dump(package.to_record(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
