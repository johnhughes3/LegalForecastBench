"""Bind interrupted provider attempts to cancelled GitHub execution steps."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import cast

from .protected_recovery import CancelledTransportEvidence, RecoveryCell, RecoveryRun
from .recovery_client import RecoveryError

_EXECUTION_STEPS = {
    "openai": "Execute exact OpenAI forecast cell",
    "anthropic": "Execute exact Anthropic forecast cell",
    "google": "Execute exact Google forecast cell",
    "vercel_ai_gateway": "Execute exact Gateway or TypeSafe Jev forecast cell",
    "typesafe": "Execute exact Gateway or TypeSafe Jev forecast cell",
}


def attach_cancelled_transport_evidence(
    run: RecoveryRun,
    cells: Sequence[RecoveryCell],
    *,
    expected_cells: Sequence[Mapping[str, object]],
    source_run: Mapping[str, object],
    source_head_sha: str,
    jobs: Sequence[Mapping[str, object]],
) -> tuple[RecoveryCell, ...]:
    """Accept only exact, completed source jobs; missing evidence stays blocked."""
    if (
        source_run.get("id") != run.source_run_id
        or source_run.get("run_attempt") != run.source_run_attempt
        or source_run.get("head_sha") != source_head_sha
        or source_run.get("status") != "completed"
        or source_run.get("conclusion") != "cancelled"
    ):
        raise RecoveryError("cancelled recovery source changed or is still active")
    expected = {str(item.get("cell_id")): item for item in expected_cells}
    if len(expected) != len(expected_cells):
        raise RecoveryError("cancelled recovery cell census contains duplicates")
    result: list[RecoveryCell] = []
    for cell in cells:
        record = expected.get(cell.cell_id)
        if cell.completed or cell.terminal_response is not None or record is None:
            result.append(cell)
            continue
        matches = [
            job for job in jobs if _matches_cell(job, cell, record, tuple(expected))
        ]
        evidence = None
        if len(matches) == 1:
            evidence = _cancelled_step(run, cell, matches[0], source_head_sha)
        result.append(replace(cell, cancelled_transport=evidence))
    return tuple(result)


def _matches_cell(
    job: Mapping[str, object],
    cell: RecoveryCell,
    record: Mapping[str, object],
    expected_ids: Sequence[str],
) -> bool:
    name = job.get("name")
    if not isinstance(name, str):
        return False
    # GitHub truncates long matrix job names, including the final cell digest.
    match = re.search(r"\(([^,]+), ([^,]+), ([a-f0-9]{20,64})(?:\.\.\.|\))$", name)
    if match is None:
        return False
    ablation, case_id, prefix = match.groups()
    return (
        ablation == cell.ablation == record.get("ablation")
        and case_id == record.get("case_id")
        and cell.repeat_index == record.get("repeat_index")
        and cell.cell_id.startswith(prefix)
        and sum(value.startswith(prefix) for value in expected_ids) == 1
    )


def _cancelled_step(
    run: RecoveryRun,
    cell: RecoveryCell,
    job: Mapping[str, object],
    source_head_sha: str,
) -> CancelledTransportEvidence | None:
    job_id = job.get("id")
    if (
        type(job_id) is not int
        or job_id <= 0
        or job.get("run_id") != run.source_run_id
        or job.get("run_attempt") != run.source_run_attempt
        or job.get("head_sha") != source_head_sha
        or job.get("status") != "completed"
        or job.get("conclusion") != "cancelled"
    ):
        return None
    step_name = _EXECUTION_STEPS.get(run.provider)
    steps = job.get("steps")
    if step_name is None or not isinstance(steps, list):
        return None
    matches = [
        cast(Mapping[str, object], step)
        for step in cast(list[object], steps)
        if isinstance(step, dict)
        and cast(Mapping[str, object], step).get("name") == step_name
    ]
    if len(matches) != 1:
        return None
    step = matches[0]
    if step.get("status") != "completed" or step.get("conclusion") != "cancelled":
        return None
    try:
        start = datetime.fromisoformat(str(step.get("started_at")))
        end = datetime.fromisoformat(str(step.get("completed_at")))
        job_start = datetime.fromisoformat(str(job.get("started_at")))
        job_end = datetime.fromisoformat(str(job.get("completed_at")))
        if any(value.tzinfo is None for value in (start, end, job_start, job_end)):
            return None
        if not job_start <= start < end <= job_end:
            return None
    except (ValueError, TypeError):
        return None
    return CancelledTransportEvidence(
        source_run_id=run.source_run_id,
        source_run_attempt=run.source_run_attempt,
        job_id=job_id,
        cell_id=cell.cell_id,
        started_at_epoch=start.timestamp(),
        completed_at_epoch=end.timestamp(),
    )
