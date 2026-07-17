"""Finalize one immutable official-evaluation shard receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from legalforecast.path_safety import safe_path_component
from legalforecast.protocol.manifest import hash_payload
from legalforecast.protocol.policy_artifacts import (
    PolicyArtifactError,
    policy_content_sha256,
    require_repeat_case_coverage,
)

JsonRecord = dict[str, Any]
RECEIPT_SCHEMA_VERSION = "legalforecast.shard_receipt.v1"
CELL_SCHEMA_VERSION = "legalforecast.shard_cell_completion.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RESULT_NAMES = ("accounting", "metrics", "runs")


class ShardReceiptError(ValueError):
    """Raised when a shard cannot be finalized safely."""


class ReceiptAlreadyExistsError(ShardReceiptError):
    """Raised when a write-once receipt key already exists."""


def derive_expected_cells(
    *,
    manifest: Mapping[str, Any],
    model_key: str,
    ablation: str,
    repeat_policy: Mapping[str, Any],
) -> tuple[JsonRecord, ...]:
    """Derive the exact frozen cell set for one model/ablation shard."""

    case_ids = _string_list(repeat_policy, "case_ids")
    repeat_count = _positive_int(repeat_policy, "count")
    packets = manifest.get("model_packets")
    if not isinstance(packets, list):
        raise ShardReceiptError("frozen manifest model_packets must be an array")
    try:
        require_repeat_case_coverage(
            cast(list[object], packets),
            repeat_case_ids=case_ids,
            requested_ablations=(ablation,),
        )
    except PolicyArtifactError as exc:
        raise ShardReceiptError(str(exc)) from exc
    expected: list[JsonRecord] = []
    seen: set[str] = set()
    for raw in cast(list[object], packets):
        packet = _mapping(raw, "model packet")
        packet_ablation = _optional_str(packet, "ablation") or "full_packet"
        if packet_ablation != ablation:
            continue
        case_id = _required_str(packet, "case_id")
        if case_id in seen:
            raise ShardReceiptError(f"duplicate expected cell: {case_id}")
        seen.add(case_id)
        object_key = (
            _optional_str(packet, "packet_object_key")
            or _optional_str(packet, "object_key")
            or _optional_str(packet, "key")
        )
        if object_key is None or not object_key.startswith("model-packets/"):
            raise ShardReceiptError("expected cell requires model-packets/ object key")
        packet_sha256 = _optional_str(packet, "sha256") or _optional_str(
            packet, "packet_sha256"
        )
        _require_sha256(packet_sha256, "packet_sha256")
        expected.append(
            {
                "case_id": case_id,
                "model_key": model_key,
                "ablation": ablation,
                "packet_object_key": object_key,
                "packet_sha256": packet_sha256,
                "repeat_count": repeat_count if case_id in case_ids else 1,
            }
        )
    if not expected:
        raise ShardReceiptError("frozen manifest produced no expected shard cells")
    return tuple(sorted(expected, key=lambda cell: cast(str, cell["case_id"])))


def build_shard_receipt(
    *,
    provenance: Mapping[str, Any],
    manifest: Mapping[str, Any],
    completions: Sequence[Mapping[str, Any]],
    frozen_manifest_sha256: str,
    labels_sha256: str,
    model_registry_sha256: str,
    current_workflow_run_id: str | None = None,
    current_workflow_run_attempt: int | None = None,
) -> JsonRecord:
    """Validate an exact successful matrix and build its current-attempt receipt."""

    if provenance.get("dispatch_mode") != "shard_only":
        raise ShardReceiptError("finalize-shard requires shard_only provenance")
    shard = _mapping(provenance.get("requested_shard"), "requested_shard")
    model_key = _required_str(shard, "model_key")
    ablation = _required_str(shard, "ablation")
    repeat_policy = _mapping(provenance.get("repeat_policy"), "repeat_policy")
    repeat_policy_sha256 = _required_sha256(provenance, "repeat_policy_sha256")
    execution_policy_sha256 = _required_sha256(provenance, "execution_policy_sha256")
    frozen_inputs = _mapping(
        provenance.get("frozen_result_inputs"), "frozen_result_inputs"
    )
    supplied_inputs = {
        "frozen_manifest_sha256": _require_sha256(
            frozen_manifest_sha256, "frozen_manifest_sha256"
        ),
        "labels_sha256": _require_sha256(labels_sha256, "labels_sha256"),
        "model_registry_sha256": _require_sha256(
            model_registry_sha256, "model_registry_sha256"
        ),
    }
    for field, supplied in supplied_inputs.items():
        if _required_sha256(frozen_inputs, field) != supplied:
            raise ShardReceiptError(
                f"{field} does not match frozen dispatch provenance"
            )
    if policy_content_sha256(repeat_policy) != repeat_policy_sha256:
        raise ShardReceiptError("repeat policy hash does not match provenance")
    expected = derive_expected_cells(
        manifest=manifest,
        model_key=model_key,
        ablation=ablation,
        repeat_policy=repeat_policy,
    )
    dispatches = provenance.get("dispatches")
    if not isinstance(dispatches, list) or not dispatches:
        raise ShardReceiptError("provenance dispatches must be non-empty")
    current = _mapping(cast(list[object], dispatches)[-1], "current dispatch")
    dispatch_workflow_run_id = _required_str(current, "workflow_run_id")
    dispatch_workflow_run_attempt = _positive_int(current, "workflow_run_attempt")
    workflow_run_id = (
        dispatch_workflow_run_id
        if current_workflow_run_id is None
        else _required_str(
            {"workflow_run_id": current_workflow_run_id}, "workflow_run_id"
        )
    )
    if workflow_run_id != dispatch_workflow_run_id:
        raise ShardReceiptError("current workflow_run_id does not match provenance")
    workflow_run_attempt = _positive_int(
        {
            "workflow_run_attempt": (
                dispatch_workflow_run_attempt
                if current_workflow_run_attempt is None
                else current_workflow_run_attempt
            )
        },
        "workflow_run_attempt",
    )
    if workflow_run_attempt < dispatch_workflow_run_attempt:
        raise ShardReceiptError(
            "current workflow_run_attempt precedes dispatch provenance"
        )
    expected_by_case = {cast(str, cell["case_id"]): cell for cell in expected}
    candidates_by_case: dict[str, list[JsonRecord]] = {}
    object_records: list[JsonRecord] = []
    object_identities: set[tuple[str, str]] = set()
    for raw_completion in completions:
        completion = _validate_completion(
            raw_completion,
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
            repeat_policy_sha256=repeat_policy_sha256,
            execution_policy_sha256=execution_policy_sha256,
            cycle_id=_required_str(provenance, "cycle_id"),
        )
        case_id = cast(str, completion["case_id"])
        expected_cell = expected_by_case.get(case_id)
        if expected_cell is None:
            raise ShardReceiptError(f"extra completion cell: {case_id}")
        for field in (
            "model_key",
            "ablation",
            "packet_object_key",
            "packet_sha256",
            "repeat_count",
        ):
            if completion[field] != expected_cell[field]:
                raise ShardReceiptError(
                    f"completion {case_id} {field} does not match frozen cell"
                )
        candidates_by_case.setdefault(case_id, []).append(completion)
    missing = sorted(set(expected_by_case) - set(candidates_by_case))
    if missing:
        raise ShardReceiptError(f"missing completion cells: {missing}")
    observed_by_case = {
        case_id: _select_completion_candidate(case_id, candidates)
        for case_id, candidates in candidates_by_case.items()
    }
    for completion in observed_by_case.values():
        producer_attempt = _positive_int(completion, "workflow_run_attempt")
        completion["producer_workflow_run_attempt"] = producer_attempt
        completion["receipt_adoption_state"] = (
            "current_attempt"
            if producer_attempt == workflow_run_attempt
            else "adopted_prior_attempt"
        )
        for object_record in cast(list[JsonRecord], completion["objects"]):
            identity = (
                cast(str, object_record["uri"]),
                cast(str, object_record["version_id"]),
            )
            if identity in object_identities:
                raise ShardReceiptError("result object version is reused across cells")
            object_identities.add(identity)
            object_records.append(object_record)
    sorted_completions = [observed_by_case[key] for key in sorted(observed_by_case)]
    receipt: JsonRecord = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "cycle_id": _required_str(provenance, "cycle_id"),
        "model_key": model_key,
        "ablation": ablation,
        "workflow_run_id": workflow_run_id,
        "workflow_run_attempt": workflow_run_attempt,
        "freeze_bundle_sha256": _required_sha256(
            provenance, "current_freeze_bundle_sha256"
        ),
        "execution_policy_sha256": execution_policy_sha256,
        "execution_policy_artifact_sha256": _required_sha256(
            provenance, "execution_policy_artifact_sha256"
        ),
        "repeat_policy_sha256": repeat_policy_sha256,
        "attempt_policy_sha256": _required_sha256(provenance, "attempt_policy_sha256"),
        "receipt_policy_sha256": _required_sha256(provenance, "receipt_policy_sha256"),
        **supplied_inputs,
        "expected_cell_count": len(expected),
        "cells": sorted_completions,
        "result_commitment_sha256": hash_payload(
            {"objects": sorted(object_records, key=_object_sort_key)}
        ),
    }
    receipt["receipt_key"] = receipt_key(receipt)
    receipt["receipt_sha256"] = hash_payload(receipt)
    return receipt


def receipt_key(receipt: Mapping[str, Any]) -> str:
    """Return the immutable path for one workflow run attempt."""

    cycle_id = safe_path_component(
        _required_str(receipt, "cycle_id"), field_name="cycle_id"
    )
    model_key = _required_str(receipt, "model_key")
    ablation = _required_str(receipt, "ablation")
    shard_digest = hash_payload({"model_key": model_key, "ablation": ablation})[:16]
    shard_label = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{model_key}-{ablation}")
    shard_slug = safe_path_component(
        f"{shard_label.strip('-')}-{shard_digest}", field_name="shard_id"
    )
    run_id = safe_path_component(
        _required_str(receipt, "workflow_run_id"), field_name="workflow_run_id"
    )
    attempt = _positive_int(receipt, "workflow_run_attempt")
    return f"shard-receipts/{cycle_id}/{shard_slug}/{run_id}/{attempt}.json"


def verify_committed_objects(receipt: Mapping[str, Any]) -> None:
    """Re-read every exact result version and verify content commitments."""

    cells = receipt.get("cells")
    if not isinstance(cells, list):
        raise ShardReceiptError("receipt cells must be an array")
    seen: set[tuple[str, str]] = set()
    for raw_cell in cast(list[object], cells):
        cell = _mapping(raw_cell, "receipt cell")
        objects = cell.get("objects")
        if not isinstance(objects, list):
            raise ShardReceiptError("receipt cell objects must be an array")
        for raw_object in cast(list[object], objects):
            commitment = _mapping(raw_object, "result object")
            identity = (
                _required_str(commitment, "uri"),
                _required_str(commitment, "version_id"),
            )
            if identity in seen:
                raise ShardReceiptError("result object version is reused across cells")
            seen.add(identity)
            payload = _read_exact_object(commitment)
            if len(payload) != _positive_int(commitment, "size_bytes", minimum=0):
                raise ShardReceiptError("result object size commitment mismatch")
            if hashlib.sha256(payload).hexdigest() != _required_sha256(
                commitment, "sha256"
            ):
                raise ShardReceiptError("result object content commitment mismatch")
            if _required_str(commitment, "name") == "metrics":
                _verify_metrics_identity(payload, cell)


def write_receipt_once(root: str, receipt: Mapping[str, Any]) -> str:
    """Write a receipt with atomic create-only semantics."""

    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ShardReceiptError("unsupported shard receipt schema")
    without_hash = dict(receipt)
    supplied_hash = _required_sha256(without_hash, "receipt_sha256")
    without_hash.pop("receipt_sha256")
    if hash_payload(without_hash) != supplied_hash:
        raise ShardReceiptError("receipt_sha256 does not match receipt content")
    key = receipt_key(receipt)
    if receipt.get("receipt_key") != key:
        raise ShardReceiptError("receipt_key does not match receipt identity")
    payload = (
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if root.startswith("s3://"):
        parsed = urlparse(root.rstrip("/") + "/" + key)
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(payload)
            handle.flush()
            result = subprocess.run(
                [
                    "aws",
                    "s3api",
                    "put-object",
                    "--bucket",
                    parsed.netloc,
                    "--key",
                    unquote(parsed.path.lstrip("/")),
                    "--body",
                    handle.name,
                    "--content-type",
                    "application/json",
                    "--if-none-match",
                    "*",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            message = result.stderr.strip()
            if "PreconditionFailed" in message or "412" in message:
                raise ReceiptAlreadyExistsError(f"receipt already exists: {key}")
            raise ShardReceiptError(f"receipt S3 write failed: {message}")
        return f"s3://{parsed.netloc}/{unquote(parsed.path.lstrip('/'))}"
    destination = Path(root) / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ReceiptAlreadyExistsError(
            f"receipt already exists: {destination}"
        ) from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return str(destination)


def _validate_completion(
    raw: Mapping[str, Any],
    *,
    workflow_run_id: str,
    workflow_run_attempt: int,
    repeat_policy_sha256: str,
    execution_policy_sha256: str,
    cycle_id: str,
) -> JsonRecord:
    completion = dict(raw)
    _exact_keys(
        completion,
        {
            "schema_version",
            "status",
            "origin",
            "workflow_run_id",
            "workflow_run_attempt",
            "cycle_id",
            "model_key",
            "case_id",
            "ablation",
            "run_id",
            "packet_object_key",
            "packet_sha256",
            "repeat_count",
            "repeat_policy_sha256",
            "execution_policy_sha256",
            "objects",
            "result_commitment_sha256",
        },
        "cell completion",
    )
    if completion.get("schema_version") != CELL_SCHEMA_VERSION:
        raise ShardReceiptError("unsupported cell completion schema")
    if completion.get("status") != "success":
        raise ShardReceiptError("cell completion status must be success")
    if completion.get("origin") not in {"fresh", "resumed"}:
        raise ShardReceiptError("cell completion origin must be fresh or resumed")
    if _required_str(completion, "cycle_id") != cycle_id:
        raise ShardReceiptError("cell completion cycle_id mismatch")
    if _required_str(completion, "workflow_run_id") != workflow_run_id:
        raise ShardReceiptError("cell completion workflow_run_id mismatch")
    producer_attempt = _positive_int(completion, "workflow_run_attempt")
    if producer_attempt > workflow_run_attempt:
        raise ShardReceiptError("cell completion comes from a future workflow attempt")
    if _required_sha256(completion, "repeat_policy_sha256") != repeat_policy_sha256:
        raise ShardReceiptError("cell completion repeat policy mismatch")
    if (
        _required_sha256(completion, "execution_policy_sha256")
        != execution_policy_sha256
    ):
        raise ShardReceiptError("cell completion execution policy mismatch")
    for field in (
        "case_id",
        "model_key",
        "ablation",
        "run_id",
        "packet_object_key",
    ):
        _required_str(completion, field)
    _required_sha256(completion, "packet_sha256")
    _positive_int(completion, "repeat_count")
    raw_objects = completion.get("objects")
    if not isinstance(raw_objects, list):
        raise ShardReceiptError("cell completion objects must be an array")
    run_id = _required_str(completion, "run_id")
    objects = [
        _validate_object(_mapping(value, "result object"), run_id=run_id)
        for value in cast(list[object], raw_objects)
    ]
    if tuple(sorted(cast(str, value["name"]) for value in objects)) != _RESULT_NAMES:
        raise ShardReceiptError("cell completion must commit runs/accounting/metrics")
    if len({cast(str, value["name"]) for value in objects}) != 3:
        raise ShardReceiptError("cell completion result objects contain duplicates")
    completion["objects"] = sorted(objects, key=_object_sort_key)
    expected_commitment = hash_payload({"objects": completion["objects"]})
    if _required_sha256(completion, "result_commitment_sha256") != expected_commitment:
        raise ShardReceiptError("cell result commitment hash mismatch")
    return completion


def _select_completion_candidate(
    case_id: str, candidates: Sequence[JsonRecord]
) -> JsonRecord:
    """Choose the highest valid producer attempt without input-order ambiguity."""

    highest_attempt = max(
        _positive_int(candidate, "workflow_run_attempt") for candidate in candidates
    )
    highest = [
        candidate
        for candidate in candidates
        if _positive_int(candidate, "workflow_run_attempt") == highest_attempt
    ]
    identities = {hash_payload(candidate) for candidate in highest}
    if len(identities) != 1:
        raise ShardReceiptError(
            f"ambiguous completion cells at attempt {highest_attempt}: {case_id}"
        )
    return dict(highest[0])


def _validate_object(raw: Mapping[str, Any], *, run_id: str) -> JsonRecord:
    record = dict(raw)
    _exact_keys(
        record,
        {"name", "uri", "version_id", "sha256", "size_bytes"},
        "result object",
    )
    name = _required_str(record, "name")
    if name not in _RESULT_NAMES:
        raise ShardReceiptError("unsupported result object name")
    uri = _required_str(record, "uri")
    if not uri.startswith("s3://"):
        raise ShardReceiptError("official result object URI must be s3://")
    suffixes = {
        "runs": ".runs.jsonl",
        "accounting": ".accounting.jsonl",
        "metrics": ".metrics.json",
    }
    if not urlparse(uri).path.endswith(f"/{run_id}{suffixes[name]}"):
        raise ShardReceiptError("result object URI does not match cell run_id")
    version_id = _required_str(record, "version_id")
    if version_id == "null":
        raise ShardReceiptError("result object VersionId must be durable")
    _required_sha256(record, "sha256")
    _positive_int(record, "size_bytes", minimum=0)
    return record


def _read_exact_object(commitment: Mapping[str, Any]) -> bytes:
    uri = _required_str(commitment, "uri")
    version_id = _required_str(commitment, "version_id")
    parsed = urlparse(uri)
    with tempfile.TemporaryDirectory(prefix="lfb-receipt-verify-") as directory:
        destination = Path(directory) / "object"
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                parsed.netloc,
                "--key",
                unquote(parsed.path.lstrip("/")),
                "--version-id",
                version_id,
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ShardReceiptError(
                f"exact result version could not be read: {result.stderr.strip()}"
            )
        return destination.read_bytes()


def _verify_metrics_identity(payload: bytes, cell: Mapping[str, Any]) -> None:
    try:
        raw: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShardReceiptError("committed metrics object is invalid JSON") from exc
    metrics = _mapping(raw, "committed metrics")
    for field in (
        "run_id",
        "cycle_id",
        "case_id",
        "model_key",
        "ablation",
        "packet_object_key",
        "packet_sha256",
        "repeat_count",
        "repeat_policy_sha256",
        "execution_policy_sha256",
    ):
        if metrics.get(field) != cell.get(field):
            raise ShardReceiptError(
                f"committed metrics {field} does not match cell completion"
            )


def _load_json(path: Path) -> Mapping[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def _load_completions(root: Path) -> tuple[Mapping[str, Any], ...]:
    paths = sorted(root.rglob("cell-completion.json"))
    if not paths:
        raise ShardReceiptError("no cell-completion.json artifacts found")
    return tuple(_load_json(path) for path in paths)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch-provenance", type=Path, required=True)
    parser.add_argument("--frozen-manifest", type=Path, required=True)
    parser.add_argument("--completions-root", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--receipt-root", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest_path = cast(Path, args.frozen_manifest)
    receipt = build_shard_receipt(
        provenance=_load_json(cast(Path, args.dispatch_provenance)),
        manifest=_load_json(manifest_path),
        completions=_load_completions(cast(Path, args.completions_root)),
        frozen_manifest_sha256=_sha256_file(manifest_path),
        labels_sha256=_sha256_file(cast(Path, args.labels)),
        model_registry_sha256=_sha256_file(cast(Path, args.model_registry)),
        current_workflow_run_id=cast(str, args.workflow_run_id),
        current_workflow_run_attempt=cast(int, args.workflow_run_attempt),
    )
    verify_committed_objects(receipt)
    destination = write_receipt_once(cast(str, args.receipt_root), receipt)
    print(json.dumps({"receipt": destination}, sort_keys=True))
    return 0


def _object_sort_key(value: Mapping[str, Any]) -> tuple[str, str]:
    return cast(str, value["name"]), cast(str, value["uri"])


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ShardReceiptError(f"{name} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ShardReceiptError(f"{field} must be a non-empty string")
    return value


def _optional_str(record: Mapping[str, Any], field: str) -> str | None:
    value = record.get(field)
    return value if isinstance(value, str) and value else None


def _positive_int(record: Mapping[str, Any], field: str, *, minimum: int = 1) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ShardReceiptError(f"{field} must be an integer >= {minimum}")
    return value


def _required_sha256(record: Mapping[str, Any], field: str) -> str:
    return _require_sha256(record.get(field), field)


def _require_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ShardReceiptError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _string_list(record: Mapping[str, Any], field: str) -> tuple[str, ...]:
    raw = record.get(field)
    if not isinstance(raw, list):
        raise ShardReceiptError(f"{field} must be an array")
    values = tuple(
        _required_str({field: value}, field) for value in cast(list[object], raw)
    )
    if len(set(values)) != len(values):
        raise ShardReceiptError(f"{field} contains duplicates")
    return values


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact_keys(record: Mapping[str, Any], expected: set[str], name: str) -> None:
    actual = set(record)
    if actual != expected:
        raise ShardReceiptError(
            f"{name} fields mismatch: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
