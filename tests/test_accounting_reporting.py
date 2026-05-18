from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from legalforecast.evals.accounting import (
    ModelRunAccountingRecord,
    OutputValidityStatus,
    accounting_records_from_harness_records,
    accounting_result_key,
)
from legalforecast.reporting.leaderboard import (
    accounting_leaderboard_records,
    summarize_accounting_leaderboard,
)

EVALUATION_TIMESTAMP = datetime(2026, 5, 14, 18, 30, tzinfo=UTC)


def test_accounting_records_emit_complete_operational_fields() -> None:
    harness_record = _harness_record(
        case_id="case-1",
        tool_logs=(
            {"status": "allowed", "tool_name": "list_available_docket_entries"},
            {"status": "denied", "tool_name": "read_docket_entry"},
        ),
    )
    result_key = accounting_result_key(harness_record)

    records = accounting_records_from_harness_records(
        (harness_record,),
        evaluation_timestamp=EVALUATION_TIMESTAMP,
        latency_ms_by_result_key={result_key: 123.5},
        output_status_by_raw_hash={
            "sha256:case1": OutputValidityStatus(
                invalid_output=True,
                refusal=True,
                invalid_output_reason="model_refusal",
            )
        },
    )
    record = records[0].to_record()

    assert record["provider"] == "example-provider"
    assert record["model_id"] == "example-model"
    assert record["model_version_or_snapshot"] == "2026-05-14"
    assert record["evaluation_timestamp"] == "2026-05-14T18:30:00Z"
    assert record["prompt_tokens"] == 1_000
    assert record["completion_tokens"] == 200
    assert record["total_tokens"] == 1_200
    assert record["tool_call_count"] == 2
    assert record["allowed_tool_call_count"] == 1
    assert record["denied_tool_call_count"] == 1
    assert record["latency_ms"] == 123.5
    assert record["estimated_cost"] == pytest.approx(0.06)
    assert record["cost_per_case"] == pytest.approx(0.06)
    assert record["cost_per_prediction_unit"] == pytest.approx(0.02)
    assert record["invalid_output"] is True
    assert record["refusal"] is True
    assert record["invalid_output_reason"] == "model_refusal"
    assert record["execution_backend"] == "local_fixture"


def test_accounting_records_fall_back_to_solver_identity_for_mock_outputs() -> None:
    harness_record = _harness_record(
        solver_id="mock-calibrated",
        solver_kind="offline_mock",
        metadata={},
    )

    record = accounting_records_from_harness_records(
        (harness_record,),
        evaluation_timestamp=EVALUATION_TIMESTAMP,
    )[0]

    assert record.provider == "offline_mock"
    assert record.model_id == "mock-calibrated"
    assert record.model_version_or_snapshot == "fixture"
    assert record.latency_ms == 0
    assert record.execution_backend == "local_fixture"


def test_accounting_records_read_latency_from_solver_metadata() -> None:
    harness_record = _harness_record()
    metadata = dict(cast(dict[str, str], harness_record["metadata"]))
    metadata["latency_ms"] = "345.25"
    harness_record["metadata"] = metadata

    record = accounting_records_from_harness_records(
        (harness_record,),
        evaluation_timestamp=EVALUATION_TIMESTAMP,
    )[0]

    assert record.latency_ms == 345.25


def test_leaderboard_summarizes_tool_calls_cost_and_latency() -> None:
    records = [
        _accounting_record(
            case_id="case-1",
            prediction_unit_count=2,
            tool_call_count=0,
            estimated_cost=0.01,
            latency_ms=100,
        ),
        _accounting_record(
            case_id="case-2",
            prediction_unit_count=1,
            tool_call_count=2,
            estimated_cost=0.02,
            latency_ms=200,
            invalid_output=True,
            refusal=True,
            invalid_output_reason="model_refusal",
        ),
        _accounting_record(
            case_id="case-3",
            prediction_unit_count=3,
            tool_call_count=5,
            estimated_cost=0.03,
            latency_ms=300,
        ),
    ]

    summary = summarize_accounting_leaderboard(
        tuple(record.to_record() for record in records)
    )[0]

    assert summary.run_count == 3
    assert summary.case_count == 3
    assert summary.prediction_unit_count == 6
    assert summary.mean_tool_calls_per_case == pytest.approx(7 / 3)
    assert summary.median_tool_calls_per_case == 2
    assert summary.p95_tool_calls_per_case == 5
    assert summary.mean_latency_ms == 200
    assert summary.p95_latency_ms == 300
    assert summary.total_estimated_cost == pytest.approx(0.06)
    assert summary.cost_per_case == pytest.approx(0.02)
    assert summary.cost_per_prediction_unit == pytest.approx(0.01)
    assert summary.invalid_output_rate == pytest.approx(1 / 3)
    assert summary.refusal_rate == pytest.approx(1 / 3)

    assert accounting_leaderboard_records(
        tuple(record.to_record() for record in records)
    )[0]["cost_per_case"] == pytest.approx(0.02)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda record: record.pop("sample_id"), "sample_id is required"),
        (
            lambda record: record.__setitem__("request_count", True),
            "request_count must be an integer",
        ),
        (
            lambda record: record.__setitem__("solver_id", " "),
            "solver_id must be a non-empty string",
        ),
        (
            lambda record: record.__setitem__("estimated_cost", "expensive"),
            "estimated_cost must be a number",
        ),
        (
            lambda record: record.__setitem__("estimated_cost", -0.01),
            "estimated_cost cannot be negative",
        ),
    ),
)
def test_accounting_record_scalar_validation_messages(
    mutation,
    message: str,
) -> None:
    record = _harness_record()
    mutation(record)

    with pytest.raises(ValueError, match=message):
        accounting_records_from_harness_records(
            (record,),
            evaluation_timestamp=EVALUATION_TIMESTAMP,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda record: record.__setitem__("metadata", "provider=example"),
            "metadata must be an object",
        ),
        (
            lambda record: record.__setitem__("metadata", {"provider": " "}),
            "metadata\\[provider\\] must be a non-empty string",
        ),
        (
            lambda record: record.__setitem__("tool_call_logs", "allowed"),
            "tool_call_logs must be a sequence",
        ),
        (
            lambda record: record.__setitem__("tool_call_logs", [42]),
            "tool_call_logs\\[0\\] must be an object",
        ),
        (
            lambda record: record.__setitem__(
                "tool_call_logs",
                [{"status": "throttled"}],
            ),
            "unknown tool call status: throttled",
        ),
        (
            lambda record: record.__setitem__("required_unit_ids", []),
            "prediction_unit_count must be positive",
        ),
    ),
)
def test_accounting_record_metadata_and_tool_log_validation_messages(
    mutation,
    message: str,
) -> None:
    record = _harness_record()
    mutation(record)

    with pytest.raises(ValueError, match=message):
        accounting_records_from_harness_records(
            (record,),
            evaluation_timestamp=EVALUATION_TIMESTAMP,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda record: record.pop("model_id"), "model_id is required"),
        (
            lambda record: record.__setitem__("prediction_unit_count", True),
            "prediction_unit_count must be an integer",
        ),
        (
            lambda record: record.__setitem__("provider", " "),
            "provider must be a non-empty string",
        ),
        (
            lambda record: record.__setitem__("latency_ms", "slow"),
            "latency_ms must be a number",
        ),
        (
            lambda record: record.__setitem__("latency_ms", -1.0),
            "latency_ms cannot be negative",
        ),
    ),
)
def test_leaderboard_record_scalar_validation_messages(mutation, message: str) -> None:
    record = _accounting_record(
        case_id="case-1",
        prediction_unit_count=2,
        tool_call_count=0,
        estimated_cost=0.01,
        latency_ms=100,
    ).to_record()
    mutation(record)

    with pytest.raises(ValueError, match=message):
        summarize_accounting_leaderboard((record,))


def _harness_record(
    *,
    case_id: str = "case-1",
    solver_id: str = "example-provider:example-model",
    solver_kind: str = "configured_model_stub",
    metadata: dict[str, str] | None = None,
    tool_logs: tuple[dict[str, str], ...] = (
        {"status": "allowed", "tool_name": "list_available_docket_entries"},
    ),
) -> dict[str, object]:
    return {
        "sample_id": f"sample-{case_id}",
        "candidate_id": f"candidate-{case_id}",
        "case_id": case_id,
        "solver_id": solver_id,
        "solver_kind": solver_kind,
        "run_label": "full_packet",
        "ablation": "full_packet",
        "raw_output_sha256": f"sha256:{case_id.replace('-', '')}",
        "required_unit_ids": ["unit-1", "unit-2", "unit-3"],
        "request_count": 1,
        "input_tokens": 1_000,
        "output_tokens": 200,
        "estimated_total_tokens": 1_200,
        "estimated_cost": 0.06,
        "tool_call_logs": list(tool_logs),
        "execution_backend": "local_fixture",
        "metadata": metadata
        if metadata is not None
        else {
            "provider": "example-provider",
            "model_id": "example-model",
            "model_version_or_snapshot": "2026-05-14",
        },
    }


def _accounting_record(
    *,
    case_id: str,
    prediction_unit_count: int,
    tool_call_count: int,
    estimated_cost: float,
    latency_ms: float,
    invalid_output: bool = False,
    refusal: bool = False,
    invalid_output_reason: str | None = None,
) -> ModelRunAccountingRecord:
    return ModelRunAccountingRecord(
        sample_id=f"sample-{case_id}",
        candidate_id=f"candidate-{case_id}",
        case_id=case_id,
        solver_id="example-provider:example-model",
        solver_kind="configured_model_stub",
        provider="example-provider",
        model_id="example-model",
        model_version_or_snapshot="2026-05-14",
        evaluation_timestamp=EVALUATION_TIMESTAMP,
        raw_output_sha256=f"sha256:{case_id.replace('-', '')}",
        prediction_unit_count=prediction_unit_count,
        request_count=1,
        prompt_tokens=1_000,
        completion_tokens=200,
        total_tokens=1_200,
        tool_call_count=tool_call_count,
        allowed_tool_call_count=tool_call_count,
        denied_tool_call_count=0,
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
        cost_per_case=estimated_cost,
        cost_per_prediction_unit=estimated_cost / prediction_unit_count,
        invalid_output=invalid_output,
        refusal=refusal,
        content_filter=False,
        invalid_output_reason=invalid_output_reason,
        run_label="full_packet",
        ablation="full_packet",
    )
