"""Cancellation evidence must identify a terminal, exact source execution."""

from copy import deepcopy
from typing import Any

import pytest
from legalforecast.runner.cancelled_recovery import attach_cancelled_transport_evidence
from legalforecast.runner.protected_recovery import RecoveryCell, RecoveryRun
from legalforecast.runner.recovery_client import RecoveryError


def _fixture() -> tuple[RecoveryRun, RecoveryCell, dict[str, Any]]:
    run = RecoveryRun(
        123,
        2,
        "cycle",
        "vercel_ai_gateway:spacexai/grok-4.7",
        "vercel_ai_gateway",
        "default",
        "a" * 64,
        100_000_000,
        "table",
        "us-east-1",
        "b" * 64,
        "recover-run-123-attempt-2",
    )
    cell = RecoveryCell("916c6fa3f8b0df65c206" + "1" * 44, "harness", "none", 1)
    start = "2026-09-22T05:30:09Z"
    end = "2026-09-22T05:32:17Z"
    args: dict[str, Any] = {
        "expected_cells": [
            {
                "cell_id": cell.cell_id,
                "case_id": "69617129",
                "ablation": "none",
                "repeat_index": 1,
            }
        ],
        "source_run": {
            "id": 123,
            "run_attempt": 2,
            "head_sha": "c" * 40,
            "status": "completed",
            "conclusion": "cancelled",
        },
        "source_head_sha": "c" * 40,
        "jobs": [
            {
                "id": 456,
                "run_id": 123,
                "run_attempt": 2,
                "head_sha": "c" * 40,
                "status": "completed",
                "conclusion": "cancelled",
                "started_at": start,
                "completed_at": end,
                "name": (
                    "Vercel AI Gateway and TypeSafe Jev resumable forecast cells "
                    f"(none, 69617129, {cell.cell_id[:20]}..."
                ),
                "steps": [
                    {
                        "name": "Execute exact Gateway or TypeSafe Jev forecast cell",
                        "status": "completed",
                        "conclusion": "cancelled",
                        "started_at": start,
                        "completed_at": end,
                    }
                ],
            }
        ],
    }
    return run, cell, args


def test_cancelled_execution_is_bound_to_source_attempt_and_frozen_cell() -> None:
    run, cell, args = _fixture()
    evidence = attach_cancelled_transport_evidence(run, (cell,), **args)[
        0
    ].cancelled_transport
    assert evidence is not None
    assert (
        evidence.source_run_id,
        evidence.source_run_attempt,
        evidence.job_id,
        evidence.cell_id,
    ) == (123, 2, 456, cell.cell_id)
    assert evidence.started_at_epoch < evidence.completed_at_epoch


@pytest.mark.parametrize(
    "field,value",
    [("run_attempt", 3), ("status", "in_progress"), ("head_sha", "d" * 40)],
)
def test_changed_or_active_source_is_refused(field: str, value: object) -> None:
    run, cell, args = _fixture()
    args["source_run"][field] = value
    with pytest.raises(RecoveryError, match="source changed"):
        attach_cancelled_transport_evidence(run, (cell,), **args)


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "wrong_case",
        "wrong_attempt",
        "wrong_sha",
        "active",
        "wrong_step",
        "no_timezone",
        "reversed_window",
        "ambiguous_prefix",
    ],
)
def test_unbound_or_nonterminal_job_never_authorizes_classification(
    change: str,
) -> None:
    run, cell, args = _fixture()
    job = args["jobs"][0]
    step = job["steps"][0]
    if change == "duplicate":
        args["jobs"].append(deepcopy(job))
    elif change == "wrong_case":
        job["name"] = job["name"].replace("69617129", "99999999")
    elif change == "wrong_attempt":
        job["run_attempt"] = 3
    elif change == "wrong_sha":
        job["head_sha"] = "d" * 40
    elif change == "active":
        job["status"] = "in_progress"
    elif change == "wrong_step":
        step["name"] = "Persist failed cell"
    elif change == "no_timezone":
        step["started_at"] = "2026-09-22T05:30:09"
    elif change == "reversed_window":
        step["started_at"], step["completed_at"] = (
            step["completed_at"],
            step["started_at"],
        )
    else:
        args["expected_cells"].append(
            {**args["expected_cells"][0], "cell_id": cell.cell_id[:20] + "2" * 44}
        )
    assert (
        attach_cancelled_transport_evidence(run, (cell,), **args)[0].cancelled_transport
        is None
    )
