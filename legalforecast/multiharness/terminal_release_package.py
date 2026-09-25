"""Portable loader for saved scoreless terminal-release run packages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    MANIFEST_RAW_SHA256_V1,
    MULTIHARNESS_SELECTION_MANIFEST_V1,
)
from legalforecast.contracts.schemas import FORECAST_RUN_V1
from legalforecast.immutable_io import read_single_link_file
from legalforecast.multiharness import release_harness
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRun,
    MultiHarnessRunRow,
)
from legalforecast.multiharness.selection import SelectionResult, TaskSelection
from legalforecast.multiharness.spec import (
    ArtifactRecord,
    RunManifest,
    RunRequest,
    RunResult,
    TaskIndex,
)


def load_terminal_release_run(run_dir: Path) -> MultiHarnessRun:
    """Reconstruct a release run from its durable, portable package.

    Workspace paths recorded by the runner may be absolute on the machine that
    executed the run.  The package layout is the authority for this loader:
    row request/result files are resolved below ``run_dir/rows/<row_id>``.
    """

    if not run_dir.is_dir() or run_dir.is_symlink():
        raise ValueError("--run-dir must be an existing run directory")
    artifacts = _load_artifact_index(run_dir)
    manifest = RunManifest.from_record(
        _read_indexed_object(run_dir, "run-manifest.json", artifacts)
    )
    _validate_run_compatibility(run_dir, manifest, artifacts)
    selection_record = _read_indexed_object(
        run_dir, "selection-manifest.json", artifacts
    )
    task_index = TaskIndex.from_record(
        _read_indexed_object(run_dir, "task-index.json", artifacts)
    )
    selection = _selection_from_record(selection_record, task_index, manifest)
    row_records = _read_indexed_jsonl(run_dir, "row-results.jsonl", artifacts)
    lfb_records = _read_indexed_jsonl_if_present(run_dir, "lfb/runs.jsonl", artifacts)
    lfb_by_key = _index_lfb_records(lfb_records)
    selected_tasks = {task.task_id: task for task in selection.tasks}
    rows_root = run_dir / "rows"
    if rows_root.is_symlink() or not rows_root.is_dir():
        raise ValueError("saved run rows directory is unavailable")

    rows: list[MultiHarnessRunRow] = []
    seen_row_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    seen_result_ids: set[str] = set()
    for row_record in row_records:
        row_id = _required_string(row_record, "row_id")
        if row_id in seen_row_ids:
            raise ValueError(f"saved run contains duplicate row_id: {row_id}")
        seen_row_ids.add(row_id)
        workspace = _row_workspace(rows_root, row_id)
        request = RunRequest.from_record(
            _read_indexed_object(run_dir, f"rows/{row_id}/request.json", artifacts)
        )
        result = RunResult.from_record(
            _read_indexed_object(run_dir, f"rows/{row_id}/result.json", artifacts)
        )
        _validate_row_record(row_record, request=request, result=result)
        selected_task = selected_tasks.get(request.task.task_id)
        if selected_task is None:
            raise ValueError("saved run row references an unselected task")
        if request.task.to_record() != selected_task.to_record():
            raise ValueError("saved run row task does not match task-index selection")
        if request.task.task_id in seen_task_ids:
            raise ValueError("saved run contains duplicate task rows")
        seen_task_ids.add(request.task.task_id)
        if result.result_id in seen_result_ids:
            raise ValueError(
                f"saved run contains duplicate result_id: {result.result_id}"
            )
        seen_result_ids.add(result.result_id)
        container_mode, receipt_sha256 = _container_record(row_record)
        case_id = request.task.metadata.get("case_id")
        lfb_record = None
        if isinstance(case_id, str):
            lfb_record = lfb_by_key.get(
                (case_id, f"{request.adapter.adapter_id}:{request.model_key}")
            )
        rows.append(
            MultiHarnessRunRow(
                row_id=row_id,
                task=request.task,
                adapter_manifest=request.adapter,
                model_config=ModelConfig(
                    adapter_id=request.adapter.adapter_id,
                    model_key=request.model_key,
                ),
                request=request,
                result=result,
                workspace=workspace,
                resumed=bool(row_record.get("resumed", False)),
                lfb_record=lfb_record,
                container_execution=container_mode,
                container_receipt_sha256=receipt_sha256,
                selection_label=selection.selection_label,
                coverage_kind=selection.coverage_kind,
            )
        )

    _validate_indexed_row_evidence(rows, run_dir, artifacts)
    _validate_saved_release_evidence(rows, lfb_by_key, run_dir, artifacts)

    if seen_result_ids != set(manifest.result_ids):
        raise ValueError("saved run result census does not match run-manifest.json")
    request_ids = {row.request.request_id for row in rows}
    if not request_ids.issubset(set(manifest.request_ids)):
        raise ValueError("saved run row request is absent from run-manifest.json")
    run_status = selection_record.get("run_status")
    interrupted = run_status != "completed"
    return MultiHarnessRun(
        manifest=manifest,
        selection=selection,
        rows=tuple(rows),
        output_dir=run_dir,
        interrupted=interrupted,
    )


def _selection_from_record(
    record: Mapping[str, Any],
    task_index: TaskIndex,
    manifest: RunManifest,
) -> SelectionResult:
    if record.get("schema_version") != str(MULTIHARNESS_SELECTION_MANIFEST_V1):
        raise ValueError("saved run selection manifest schema is invalid")
    selection_sha256 = _required_string(record, "selection_sha256")
    if selection_sha256 != manifest.selection_sha256:
        raise ValueError("saved run selection digest does not match manifest")
    raw_task_ids_value = record.get("task_ids")
    if not isinstance(raw_task_ids_value, list):
        raise ValueError("saved run selection task_ids are invalid")
    raw_task_ids = cast(list[object], raw_task_ids_value)
    if any(not isinstance(value, str) for value in raw_task_ids):
        raise ValueError("saved run selection task_ids are invalid")
    task_ids = tuple(cast(str, value) for value in raw_task_ids)
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("saved run selection task_ids are duplicated")
    tasks_by_id = {task.task_id: task for task in task_index.tasks}
    try:
        tasks = tuple(tasks_by_id[task_id] for task_id in task_ids)
    except KeyError as exc:
        raise ValueError("saved run selection references an unknown task") from exc
    selection_label = _required_string(record, "selection_label")
    coverage_kind = _required_string(record, "coverage_kind")
    calculated = TaskSelection(
        task_ids=task_ids,
        allow_empty=not task_ids,
    ).select(task_index)
    if calculated.selection_sha256 != selection_sha256:
        raise ValueError("saved run selection digest does not match task-index")
    return SelectionResult(
        tasks=tasks,
        selection_sha256=selection_sha256,
        selection_label=selection_label,
        coverage_kind=coverage_kind,
    )


def _validate_row_record(
    record: Mapping[str, Any],
    *,
    request: RunRequest,
    result: RunResult,
) -> None:
    if result.request_id != request.request_id:
        raise ValueError("saved run result request does not match request.json")
    expected = {
        "task_id": request.task.task_id,
        "adapter_id": request.adapter.adapter_id,
        "model_key": request.model_key,
        "request_id": request.request_id,
        "request_sha256": request.request_sha256,
        "result_id": result.result_id,
        "status": result.status,
    }
    for field_name, expected_value in expected.items():
        if record.get(field_name) != expected_value:
            raise ValueError(f"saved run row {field_name} does not match its files")


def _container_record(record: Mapping[str, Any]) -> tuple[str, str | None]:
    raw_value = record.get("container_execution")
    raw = cast(Mapping[str, Any], raw_value) if isinstance(raw_value, Mapping) else None
    if not isinstance(raw, Mapping):
        return "headless_cli", None
    mode = raw.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("saved run container execution mode is invalid")
    receipt = raw.get("receipt_sha256")
    if receipt is not None and not isinstance(receipt, str):
        raise ValueError("saved run container receipt digest is invalid")
    return mode, receipt


def _index_lfb_records(
    records: tuple[dict[str, Any], ...],
) -> dict[tuple[str, str | None], dict[str, Any]]:
    indexed: dict[tuple[str, str | None], dict[str, Any]] = {}
    for record in records:
        case_id = record.get("case_id")
        solver_id = record.get("solver_id")
        if not isinstance(case_id, str):
            continue
        key = (case_id, solver_id if isinstance(solver_id, str) else None)
        if key[1] is None:
            raise ValueError("saved run LFB projection lacks a solver identity")
        if key in indexed:
            raise ValueError("saved run contains duplicate LFB projection records")
        indexed[key] = record
    return indexed


def _validate_saved_release_evidence(
    rows: list[MultiHarnessRunRow],
    lfb_records: Mapping[tuple[str, str | None], dict[str, Any]],
    run_dir: Path,
    artifacts: Mapping[str, ArtifactRecord],
) -> None:
    """Revalidate per-row receipts before handing the package to scoring."""

    projections = release_harness.collect_release_harness_projections(
        (row.request, row.result, row.workspace) for row in rows
    )
    projected_by_key: dict[tuple[str, str | None], dict[str, Any]] = {}
    expected_receipts: dict[str, Mapping[str, Any]] = {}
    for projection in projections:
        receipt = projection.receipt.to_record()
        receipt_id = receipt["receipt_id"]
        if not isinstance(receipt_id, str) or receipt_id in expected_receipts:
            raise ValueError("saved run contains duplicate release receipt IDs")
        expected_receipts[receipt_id] = receipt
        lfb_record = projection.lfb_record
        if lfb_record is None:
            continue
        case_id = lfb_record.get("case_id")
        solver_id = lfb_record.get("solver_id")
        if not isinstance(case_id, str) or not isinstance(solver_id, str):
            raise ValueError("saved run LFB projection identity is invalid")
        key = (case_id, solver_id)
        if key in projected_by_key:
            raise ValueError("saved run contains duplicate release projections")
        projected_by_key[key] = dict(lfb_record)
    if set(projected_by_key) != set(lfb_records):
        raise ValueError("saved run LFB projection census does not match receipts")
    for key, record in projected_by_key.items():
        if lfb_records.get(key) != record:
            raise ValueError("saved run LFB projection does not match row receipt")

    aggregate_path = run_dir / "release-harness-receipts.jsonl"
    if not aggregate_path.exists() and not aggregate_path.is_symlink():
        if expected_receipts:
            raise ValueError("saved run release receipt aggregate is missing")
        return
    aggregate = _read_indexed_jsonl(
        run_dir, "release-harness-receipts.jsonl", artifacts
    )
    aggregate_by_id: dict[str, dict[str, Any]] = {}
    for receipt in aggregate:
        receipt_id = receipt.get("receipt_id")
        if not isinstance(receipt_id, str) or receipt_id in aggregate_by_id:
            raise ValueError("saved run receipt aggregate contains duplicate IDs")
        release_harness.ReleaseHarnessReceipt.from_record(receipt)
        aggregate_by_id[receipt_id] = receipt
    if aggregate_by_id != expected_receipts:
        raise ValueError("saved run receipt aggregate does not match row receipts")


def _validate_run_compatibility(
    run_dir: Path,
    manifest: RunManifest,
    artifacts: Mapping[str, ArtifactRecord],
) -> None:
    """Authenticate the compatibility record before reconstructing any rows."""

    expected = manifest.run_compatibility_sha256
    if expected is None:
        raise ValueError("saved run is missing run-compatibility commitment")
    compatibility = _read_indexed_object(
        run_dir,
        "run-compatibility.json",
        artifacts,
    )
    actual = "sha256:" + str(
        MANIFEST_RAW_SHA256_V1.commit(
            compatibility,
            domain=FORECAST_RUN_V1,
        ).digest
    )
    if actual != expected:
        raise ValueError("saved run run-compatibility commitment does not match")


def _validate_indexed_row_evidence(
    rows: list[MultiHarnessRunRow],
    run_dir: Path,
    artifacts: Mapping[str, ArtifactRecord],
) -> None:
    """Require every row evidence path consumed by projection in the index."""

    for row in rows:
        row_prefix = f"rows/{row.row_id}/"
        for result_artifact in row.result.artifacts:
            indexed_path = f"{row_prefix}{result_artifact.path}"
            indexed = _require_indexed_artifact(indexed_path, artifacts)
            if indexed.sha256 != result_artifact.sha256:
                raise ValueError(
                    "saved run indexed result artifact digest does not match: "
                    f"{indexed_path}"
                )
            if indexed.size_bytes != result_artifact.size_bytes:
                raise ValueError(
                    "saved run indexed result artifact size does not match: "
                    f"{indexed_path}"
                )

        workspace = run_dir / "rows" / row.row_id
        for relative_path in (
            release_harness.RELEASE_HARNESS_RECEIPT_NAME,
            release_harness.RELEASE_HARNESS_LFB_RECORD_NAME,
            release_harness.RELEASE_HARNESS_PRIVATE_LFB_RECORD_NAME,
        ):
            path = workspace / relative_path
            if path.exists() or path.is_symlink():
                _require_indexed_artifact(f"{row_prefix}{relative_path}", artifacts)


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(
            read_single_link_file(path, label="terminal release run artifact").decode(
                "utf-8"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"saved run artifact is unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"saved run artifact must be an object: {path}")
    return cast(dict[str, Any], value)


def _load_artifact_index(run_dir: Path) -> dict[str, ArtifactRecord]:
    """Verify every indexed package file before consuming any run records."""

    index_record = _read_object(run_dir / "artifact-index.json")
    raw_artifacts = index_record.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise ValueError("saved run artifact index is invalid")
    records: dict[str, ArtifactRecord] = {}
    for raw_record in cast(list[object], raw_artifacts):
        if not isinstance(raw_record, Mapping):
            raise ValueError("saved run artifact index contains an invalid record")
        artifact = ArtifactRecord.from_record(cast(Mapping[str, Any], raw_record))
        if artifact.path in records:
            raise ValueError("saved run artifact index contains duplicate paths")
        records[artifact.path] = artifact
        path = run_dir / artifact.path
        if path.is_symlink() or not path.is_file():
            raise ValueError(
                f"saved run indexed artifact is unavailable: {artifact.path}"
            )
        payload = read_single_link_file(path, label="saved run indexed artifact")
        if len(payload) != artifact.size_bytes:
            raise ValueError(f"saved run artifact size does not match: {artifact.path}")
        if release_harness.release_bytes_sha256(payload) != artifact.sha256:
            raise ValueError(
                f"saved run artifact digest does not match: {artifact.path}"
            )
    return records


def _read_indexed_object(
    run_dir: Path,
    relative_path: str,
    artifacts: Mapping[str, ArtifactRecord],
) -> dict[str, Any]:
    _require_indexed_artifact(relative_path, artifacts)
    return _read_object(run_dir / relative_path)


def _read_indexed_jsonl(
    run_dir: Path,
    relative_path: str,
    artifacts: Mapping[str, ArtifactRecord],
) -> tuple[dict[str, Any], ...]:
    _require_indexed_artifact(relative_path, artifacts)
    return _read_jsonl(run_dir / relative_path)


def _read_indexed_jsonl_if_present(
    run_dir: Path,
    relative_path: str,
    artifacts: Mapping[str, ArtifactRecord],
) -> tuple[dict[str, Any], ...]:
    path = run_dir / relative_path
    if not path.exists() and not path.is_symlink():
        return ()
    return _read_indexed_jsonl(run_dir, relative_path, artifacts)


def _require_indexed_artifact(
    relative_path: str,
    artifacts: Mapping[str, ArtifactRecord],
) -> ArtifactRecord:
    artifact = artifacts.get(relative_path)
    if artifact is None:
        raise ValueError(f"saved run artifact is absent from index: {relative_path}")
    return artifact


def _row_workspace(rows_root: Path, row_id: str) -> Path:
    """Resolve one row directory without permitting package path traversal."""

    if (
        not row_id
        or row_id in {".", ".."}
        or "/" in row_id
        or "\\" in row_id
        or Path(row_id).is_absolute()
    ):
        raise ValueError("saved run row_id is not a safe path component")
    workspace = rows_root / row_id
    if workspace.is_symlink() or not workspace.is_dir():
        raise ValueError(f"saved run row workspace is unavailable: {row_id}")
    return workspace


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        payload = read_single_link_file(path, label="terminal release JSONL")
        lines = payload.decode("utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"saved run JSONL is unavailable: {path}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"saved run JSONL is invalid: {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise ValueError(
                f"saved run JSONL row is not an object: {path}:{line_number}"
            )
        records.append(cast(dict[str, Any], value))
    return tuple(records)


def _required_string(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"saved run {field_name} is missing")
    return value


__all__ = ["load_terminal_release_run"]
