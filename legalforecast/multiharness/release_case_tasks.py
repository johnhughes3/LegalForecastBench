"""Outcome-blinded case task construction and solver-input staging."""

from __future__ import annotations

import json
import mimetypes
from collections.abc import Callable, Sequence
from pathlib import Path

from legalforecast.multiharness.solver_inputs import (
    SolverInputPayload,
    SolverInputStore,
    SolverInputVisibleFile,
    write_solver_input_store,
)
from legalforecast.multiharness.spec import CanonicalTask, TaskIndex
from legalforecast.multiharness.validation import validate_unique_ids
from legalforecast.release.models import ForecastPredictionUnit, ReleaseCase
from legalforecast.release.service import ForecastExecution


def build_case_task_index(
    execution: ForecastExecution,
    *,
    suite_version: str,
    index_digest: Callable[[Sequence[CanonicalTask]], str],
    bytes_digest: Callable[[bytes], str],
    index_id: str = "legalforecast-release-cases",
    selection_namespace: str = "legalforecast_mtd",
) -> TaskIndex:
    """Build one outcome-blinded task for each release case."""

    units_by_case: dict[str, list[ForecastPredictionUnit]] = {}
    for unit in execution.release.prediction_units:
        units_by_case.setdefault(unit.case_id, []).append(unit)
    case_by_id = {case.case_id: case for case in execution.release.cases}
    tasks = tuple(
        build_case_task(
            execution,
            case_by_id[case_id],
            units,
            suite_version=suite_version,
            bytes_digest=bytes_digest,
        )
        for case_id, units in sorted(units_by_case.items())
    )
    if not tasks:
        raise ValueError("forecast release must contain at least one case task")
    validate_unique_ids((task.task_id for task in tasks), "tasks")
    return TaskIndex(
        index_id=index_id,
        selection_namespace=selection_namespace,
        tasks=tasks,
        index_sha256=index_digest(tasks),
    )


def write_case_solver_inputs(
    execution: ForecastExecution,
    *,
    task_index: TaskIndex,
    destination_root: Path,
) -> SolverInputStore:
    """Stage one shared prompt and every permitted case document per task."""

    units_by_case = _release_units_by_case(execution)
    cases_by_id = {case.case_id: case for case in execution.release.cases}
    payloads: list[SolverInputPayload] = []
    for task in task_index.tasks:
        case_id = task.metadata.get("case_id")
        if not isinstance(case_id, str) or case_id not in cases_by_id:
            raise ValueError("release case task does not match forecast release")
        units = units_by_case[case_id]
        prompt = _shared_release_prompt(execution, units)
        case = cases_by_id[case_id]
        visible_indexes = _shared_model_visible_document_indexes(case, units)
        visible_files = tuple(
            _case_solver_file(
                execution,
                case=case,
                units=units,
                document_index=index,
            )
            for index in visible_indexes
        )
        payloads.append(
            SolverInputPayload(
                task=task,
                prompt=prompt,
                source_packet_bytes=_case_source_packet_bytes(
                    execution,
                    case=case,
                    units=units,
                ),
                visible_files=visible_files,
            )
        )
    return write_solver_input_store(
        destination_root=destination_root,
        task_index_sha256=task_index.index_sha256,
        payloads=tuple(payloads),
    )


def build_case_task(
    execution: ForecastExecution,
    case: ReleaseCase,
    units: Sequence[ForecastPredictionUnit],
    *,
    suite_version: str,
    bytes_digest: Callable[[bytes], str],
) -> CanonicalTask:
    """Project one case envelope while retaining per-unit requirements."""

    if not units:
        raise ValueError("case task requires at least one prediction unit")
    ordered_units = tuple(sorted(units, key=lambda unit: unit.unit_id))
    prompt_bytes = _shared_release_prompt_bytes(execution, ordered_units)
    visible_indexes = _shared_model_visible_document_indexes(case, ordered_units)
    source_packet = _case_source_packet_bytes(
        execution,
        case=case,
        units=ordered_units,
    )
    packet_sha256 = bytes_digest(source_packet)
    prompt_sha256 = bytes_digest(prompt_bytes)
    unit_records = [
        {
            "unit_id": unit.unit_id,
            "case_id": unit.case_id,
            "claim_name": unit.claim_name,
            "defendant_group": unit.defendant_group,
            "count": unit.count,
            "should_score": unit.should_score,
            "model_visible_document_indexes": list(unit.model_visible_document_indexes),
        }
        for unit in ordered_units
    ]
    metadata = {
        "suite": "legalforecast_mtd",
        "release_schema_version": execution.release.schema_version,
        "release_id": execution.release.release_id,
        "forecast_release_digest": execution.release.release_digest,
        "case_id": case.case_id,
        "case_batch": True,
        "unit_ids": [unit.unit_id for unit in ordered_units],
        "required_unit_ids": [unit.unit_id for unit in ordered_units],
        "scoreable_unit_ids": [
            unit.unit_id for unit in ordered_units if unit.should_score
        ],
        "unit_metadata": unit_records,
        "should_score": any(unit.should_score for unit in ordered_units),
        "ablation": "none",
        "packet_sha256": packet_sha256,
        "packet_byte_count": len(source_packet),
        "prompt_sha256": prompt_sha256,
        "prompt_byte_count": len(prompt_bytes),
        "model_visible_documents": [
            {
                "document_id": document.document_id,
                "role": document.role,
                "sha256": f"sha256:{document.sha256}",
                "byte_count": document.byte_count,
            }
            for index, document in enumerate(case.documents)
            if index in visible_indexes
        ],
    }
    return CanonicalTask(
        task_id=f"lfb-release:{execution.release.release_id}:case:{case.case_id}",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version=suite_version,
        source_id=case.case_id,
        task_sha256=packet_sha256,
        metadata=metadata,
    )


def _release_units_by_case(
    execution: ForecastExecution,
) -> dict[str, tuple[ForecastPredictionUnit, ...]]:
    grouped: dict[str, list[ForecastPredictionUnit]] = {}
    for unit in execution.release.prediction_units:
        grouped.setdefault(unit.case_id, []).append(unit)
    return {
        case_id: tuple(sorted(units, key=lambda unit: unit.unit_id))
        for case_id, units in grouped.items()
    }


def _shared_release_prompt_bytes(
    execution: ForecastExecution,
    units: Sequence[ForecastPredictionUnit],
) -> bytes:
    if not units:
        raise ValueError("case task requires at least one prediction unit")
    first = units[0]
    prompt = execution.prompt_bytes(first.unit_id)
    for unit in units[1:]:
        if (
            unit.prompt_path,
            unit.prompt_sha256,
            unit.prompt_byte_count,
        ) != (first.prompt_path, first.prompt_sha256, first.prompt_byte_count):
            raise ValueError("prediction units in one case must share one prompt")
        if execution.prompt_bytes(unit.unit_id) != prompt:
            raise ValueError("prediction units in one case have different prompt bytes")
    return prompt


def _shared_release_prompt(
    execution: ForecastExecution,
    units: Sequence[ForecastPredictionUnit],
) -> str:
    try:
        return _shared_release_prompt_bytes(execution, units).decode(
            "utf-8", errors="strict"
        )
    except UnicodeDecodeError as exc:
        raise ValueError("release prompt must be strict UTF-8") from exc


def _case_source_packet_bytes(
    execution: ForecastExecution,
    *,
    case: ReleaseCase,
    units: Sequence[ForecastPredictionUnit],
) -> bytes:
    """Encode only public outcome-blinded case metadata for the hidden envelope."""

    _shared_release_prompt_bytes(execution, units)
    record = {
        "case_id": case.case_id,
        "documents": [
            {
                "document_id": document.document_id,
                "role": document.role,
                "path": document.path,
                "sha256": document.sha256,
                "byte_count": document.byte_count,
            }
            for document in case.documents
        ],
        "prediction_units": [
            {
                "unit_id": unit.unit_id,
                "case_id": unit.case_id,
                "claim_name": unit.claim_name,
                "defendant_group": unit.defendant_group,
                "count": unit.count,
                "should_score": unit.should_score,
                "model_visible_document_indexes": list(
                    unit.model_visible_document_indexes
                ),
            }
            for unit in sorted(units, key=lambda item: item.unit_id)
        ],
    }
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _case_solver_file(
    execution: ForecastExecution,
    *,
    case: ReleaseCase,
    units: Sequence[ForecastPredictionUnit],
    document_index: int,
) -> SolverInputVisibleFile:
    document = case.documents[document_index]
    source_unit = next(
        (
            unit
            for unit in units
            if document_index in unit.model_visible_document_indexes
        ),
        None,
    )
    if source_unit is None:
        raise ValueError(
            "case document is not permitted for any required prediction unit: "
            f"{document.document_id}"
        )
    payload = execution.document_bytes(source_unit.unit_id, document_index)
    suffix = Path(document.path).suffix.lower() or ".bin"
    safe_document_id = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in document.document_id
    )
    return SolverInputVisibleFile(
        destination_path=f"documents/{document_index:04d}-{safe_document_id}{suffix}",
        media_type=mimetypes.guess_type(document.path)[0] or "application/octet-stream",
        content=payload,
    )


def _shared_model_visible_document_indexes(
    case: ReleaseCase,
    units: Sequence[ForecastPredictionUnit],
) -> tuple[int, ...]:
    """Return the one committed visible-document set for a case batch."""

    if not units:
        raise ValueError("case task requires at least one prediction unit")
    expected = units[0].model_visible_document_indexes
    if any(unit.model_visible_document_indexes != expected for unit in units[1:]):
        raise ValueError(
            "prediction units in one case must share one visible-document set"
        )
    if any(index >= len(case.documents) for index in expected):
        raise ValueError("model-visible document index is out of range")
    return expected
