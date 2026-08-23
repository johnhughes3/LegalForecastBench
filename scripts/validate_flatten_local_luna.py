"""Validate and flatten local Luna result envelopes for ``legalforecast score``.

The local Luna runner stores one Inspect-compatible run record inside a
hash-bound result envelope.  This provider-free adapter validates the envelope
and the runner's derived verification summaries before emitting the unchanged
inner run record as score input.  It never creates or infers outcome labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.response_verification import (
    output_statuses_from_run_records,
    response_verification_summary_from_run_records,
)

RESULT_SCHEMA_VERSION = "legalforecast.local_luna_result.v1"
MODEL_ID = "openai:gpt-5.6-luna"
_FORBIDDEN_SAMPLING_KEYS = frozenset({"temperature", "top_p", "topP"})


class LocalLunaResultError(ValueError):
    """Raised when a local result cannot be admitted to the score stream."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise LocalLunaResultError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _require_string(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LocalLunaResultError(f"{field} must be a non-empty string")
    return value


def _require_hex_digest(record: Mapping[str, object], field: str) -> str:
    value = _require_string(record, field)
    if len(value) != 64 or value != value.lower():
        raise LocalLunaResultError(f"{field} must be a lowercase SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise LocalLunaResultError(
            f"{field} must be a lowercase SHA-256 digest"
        ) from exc
    return value


def _require_string_list(record: Mapping[str, object], field: str) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise LocalLunaResultError(f"{field} must be a list of strings")
    result = tuple(
        item
        for item in cast(Sequence[object], value)
        if isinstance(item, str) and item.strip()
    )
    if len(result) != len(cast(Sequence[object], value)):
        raise LocalLunaResultError(f"{field} must contain non-empty strings")
    if len(result) != len(set(result)):
        raise LocalLunaResultError(f"{field} must not contain duplicates")
    if not result:
        raise LocalLunaResultError(f"{field} must not be empty")
    return result


def _validate_result(
    path: Path,
    *,
    expected_registry_sha256: str | None,
    derive_missing_output_statuses: frozenset[str],
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise LocalLunaResultError(f"result must be a regular non-symlink file: {path}")
    try:
        decoded: object = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise LocalLunaResultError(f"result is not readable JSON: {path}") from exc
    envelope = _require_mapping(decoded, f"result envelope {path}")
    if envelope.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise LocalLunaResultError(f"unsupported result schema: {path}")
    identity = _require_string(envelope, "identity")
    if ":" not in identity:
        raise LocalLunaResultError(f"result identity must be case:ablation: {path}")
    case_id, ablation = identity.split(":", maxsplit=1)
    if not case_id or not ablation:
        raise LocalLunaResultError(f"result identity must be case:ablation: {path}")
    if path.stem != f"{case_id}--{ablation}":
        raise LocalLunaResultError(
            f"result filename does not match its identity: {path.name}"
        )
    _require_hex_digest(envelope, "packet_sha256")
    _require_hex_digest(envelope, "prompt_sha256")
    _require_hex_digest(envelope, "plan_identity_sha256")

    raw_runs = envelope.get("runs")
    if not isinstance(raw_runs, Sequence) or isinstance(raw_runs, str):
        raise LocalLunaResultError(f"runs must be a list: {path}")
    runs_sequence = cast(Sequence[object], raw_runs)
    if len(runs_sequence) != 1:
        raise LocalLunaResultError(f"result must contain exactly one run: {path}")
    run = _require_mapping(runs_sequence[0], f"runs[0] in {path}")
    if _require_string(run, "case_id") != case_id:
        raise LocalLunaResultError(f"nested case_id differs from envelope: {path}")
    if _require_string(run, "ablation") != ablation:
        raise LocalLunaResultError(f"nested ablation differs from envelope: {path}")
    if _require_string(run, "solver_id") != MODEL_ID:
        raise LocalLunaResultError(f"unexpected solver identity: {path}")
    if run.get("execution_backend") != "inspect_ai":
        raise LocalLunaResultError(
            f"result was not produced by live Inspect execution: {path}"
        )
    _require_string_list(run, "required_unit_ids")
    raw_output = _require_string(run, "raw_output")
    if (
        _require_string(run, "raw_output_sha256")
        != f"sha256:{_sha256(raw_output.encode())}"
    ):
        raise LocalLunaResultError(f"raw output hash mismatch: {path}")
    tool_call_logs = run.get("tool_call_logs")
    if not isinstance(tool_call_logs, Sequence) or isinstance(tool_call_logs, str):
        raise LocalLunaResultError(f"tool_call_logs must be a list: {path}")
    if tool_call_logs:
        raise LocalLunaResultError(
            f"tool calls are not allowed in local Luna results: {path}"
        )

    metadata = _require_mapping(run.get("metadata"), f"metadata in {path}")
    if (
        metadata.get("provider") != "openai"
        or metadata.get("provider_sampling_policy") != "provider_default"
    ):
        raise LocalLunaResultError(
            f"provider-default OpenAI metadata is missing: {path}"
        )
    if set(metadata).intersection(_FORBIDDEN_SAMPLING_KEYS):
        raise LocalLunaResultError(f"custom sampling parameters are present: {path}")
    registry_sha256 = _require_hex_digest(metadata, "model_registry_sha256")
    if (
        expected_registry_sha256 is not None
        and registry_sha256 != expected_registry_sha256
    ):
        raise LocalLunaResultError(f"model registry hash mismatch: {path}")

    runs = [dict(run)]
    expected_response = response_verification_summary_from_run_records(runs)
    response_verification = _require_mapping(
        envelope.get("response_verification"), f"response_verification in {path}"
    )
    if dict(response_verification) != expected_response:
        raise LocalLunaResultError(f"response verification summary mismatch: {path}")
    expected_statuses = {
        digest: status.to_record()
        for digest, status in output_statuses_from_run_records(runs).items()
    }
    raw_output_statuses = envelope.get("output_statuses")
    if raw_output_statuses is None:
        if identity not in derive_missing_output_statuses:
            raise LocalLunaResultError(f"output status summary is missing: {path}")
    else:
        output_statuses = _require_mapping(
            raw_output_statuses, f"output_statuses in {path}"
        )
        if dict(output_statuses) != expected_statuses:
            raise LocalLunaResultError(f"output status summary mismatch: {path}")
    return dict(run)


def flatten_results(
    results_dir: Path,
    output_path: Path,
    *,
    expected_count: int | None = None,
    expected_registry_sha256: str | None = None,
    derive_missing_output_statuses: frozenset[str] = frozenset(),
) -> int:
    """Validate all result envelopes and write a create-only flat JSONL stream."""

    if results_dir.is_symlink() or not results_dir.is_dir():
        raise LocalLunaResultError(
            f"results directory is not a regular directory: {results_dir}"
        )
    if output_path.exists() or output_path.is_symlink():
        raise LocalLunaResultError(
            f"output already exists; refusing overwrite: {output_path}"
        )
    paths = sorted(results_dir.glob("*--*.json"), key=lambda path: path.name)
    if not paths:
        raise LocalLunaResultError(f"no local result envelopes found: {results_dir}")
    records = [
        _validate_result(
            path,
            expected_registry_sha256=expected_registry_sha256,
            derive_missing_output_statuses=derive_missing_output_statuses,
        )
        for path in paths
    ]
    identities = [(record["case_id"], record["ablation"]) for record in records]
    if len(identities) != len(set(identities)):
        raise LocalLunaResultError("duplicate case/ablation identities in results")
    if expected_count is not None and len(records) != expected_count:
        raise LocalLunaResultError(
            f"expected {expected_count} result envelopes, found {len(records)}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(output_path, flags, 0o600)
    except FileExistsError as exc:
        raise LocalLunaResultError(
            f"output already exists; refusing overwrite: {output_path}"
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for record in sorted(
            records, key=lambda row: (str(row["case_id"]), str(row["ablation"]))
        ):
            json.dump(record, handle, sort_keys=True)
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return len(records)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--expected-registry-sha256")
    parser.add_argument(
        "--derive-missing-output-statuses-for",
        action="append",
        default=[],
        metavar="CASE:ABLATION",
        help=(
            "Allow deterministic status derivation only for this explicitly "
            "named legacy envelope. Repeat for each approved identity."
        ),
    )
    args = parser.parse_args(argv)
    count = flatten_results(
        args.results_dir,
        args.output,
        expected_count=args.expected_count,
        expected_registry_sha256=args.expected_registry_sha256,
        derive_missing_output_statuses=frozenset(
            cast(list[str], args.derive_missing_output_statuses_for)
        ),
    )
    print(
        json.dumps({"result_count": count, "output": str(args.output)}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
