from __future__ import annotations

from pathlib import Path

from legalforecast.multiharness.runner import ModelConfig, MultiHarnessRunRow
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    RunResult,
    SandboxPolicy,
)

SHA256 = "sha256:" + "a" * 64
RECEIPT = "sha256:" + "c" * 64


def test_row_with_container_receipt_does_not_serialize_as_plan_only_not_run() -> None:
    # No-Claim: this plants a receipt on a row. Green does not prove a live
    # Docker run.
    record = _row(
        container_execution="plan_only",
        container_receipt_sha256=RECEIPT,
    ).to_record()["container_execution"]

    assert record["mode"] != "plan_only"
    assert record["status"] != "not_run"
    assert record == {
        "mode": "live_tools",
        "status": "succeeded",
        "receipt_sha256": RECEIPT,
    }


def test_plan_only_row_without_receipt_still_serializes_as_not_run() -> None:
    record = _row(
        container_execution="plan_only",
        container_receipt_sha256=None,
    ).to_record()["container_execution"]

    assert record == {"mode": "plan_only", "status": "not_run"}


def test_live_tools_row_without_receipt_serializes_as_failed() -> None:
    record = _row(
        container_execution="live_tools",
        container_receipt_sha256=None,
    ).to_record()["container_execution"]

    assert record == {"mode": "live_tools", "status": "failed"}


def test_live_tools_row_with_receipt_serializes_as_succeeded() -> None:
    record = _row(
        container_execution="live_tools",
        container_receipt_sha256=RECEIPT,
    ).to_record()["container_execution"]

    assert record == {
        "mode": "live_tools",
        "status": "succeeded",
        "receipt_sha256": RECEIPT,
    }


def _row(
    *,
    container_execution: str,
    container_receipt_sha256: str | None,
) -> MultiHarnessRunRow:
    task = CanonicalTask(
        task_id="lfb.case-1",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture-v1",
        source_id="fixture-source",
        task_sha256=SHA256,
        metadata={"case_id": "case-1"},
    )
    adapter = AdapterManifest(
        adapter_id="fixture-adapter",
        display_name="Fixture Adapter",
        adapter_version="0.1.0",
        command=("fixture-adapter",),
    )
    model = ModelConfig(model_key="fixture-model")
    request = RunRequest(
        request_id="row-1",
        task=task,
        adapter=adapter,
        model_key=model.model_key,
        sandbox_policy=SandboxPolicy(
            policy_id="fixture-sandbox",
            backend="dry-run",
            image="python:3.12-slim",
            network_policy="none",
            timeout_seconds=60,
        ),
        request_sha256=SHA256,
    )
    result = RunResult(
        result_id="row-1-result",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=SHA256,
    )
    return MultiHarnessRunRow(
        row_id="row-1",
        task=task,
        adapter_manifest=adapter,
        model_config=model,
        request=request,
        result=result,
        workspace=Path("rows/row-1"),
        container_execution=container_execution,
        container_receipt_sha256=container_receipt_sha256,
    )
