"""Pinned OpenClaw community adapter contracts and result normalization."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast._canonical import canonical_json
from legalforecast._json_io import write_json_object
from legalforecast.evals.output_parser import parse_model_output
from legalforecast.multiharness.spec import (
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse
from legalforecast.multiharness.validation import validate_public_record

ADAPTER_ID = "openclaw-pinned-bridge"
ADAPTER_VERSION = "1.0.0"
OPENCLAW_VERSION = "2026.9.6"
OPENCLAW_COMMIT = "eb377ac59e6c9fd6c7705028034812becf00271b"
TOOL_NAME = "lfb_read_task"


class OpenClawError(RuntimeError):
    """The requested runtime or its output did not satisfy the contract."""


class ToolTransport(Protocol):
    """Existing host-owned container protocol, without provider credentials."""

    def execute(self, request: ToolRequest) -> ToolResponse:
        """Read the staged solver prompt through the host tool runtime."""
        ...


def record_digest(record: Mapping[str, Any]) -> str:
    """Commit canonical adapter data using the shared JSON representation."""
    return "sha256:" + hashlib.sha256(canonical_json(record).encode()).hexdigest()


def capabilities() -> AdapterCapabilities:
    """Advertise the narrow real adapter; ordinary run remains offline only."""
    return AdapterCapabilities(
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
        supports_sandbox_policy=True,
        tool_protocol_version=TOOL_REQUEST_SCHEMA_VERSION,
        capabilities_sha256=record_digest(
            {
                "adapter": ADAPTER_ID,
                "version": ADAPTER_VERSION,
                "runtime": OPENCLAW_VERSION,
                "commit": OPENCLAW_COMMIT,
                "tool": TOOL_NAME,
            }
        ),
    )


def validate_request(request: RunRequest) -> None:
    """Reject requests outside this adapter's declared family and identity."""
    if (request.adapter.adapter_id, request.adapter.adapter_version) != (
        ADAPTER_ID,
        ADAPTER_VERSION,
    ):
        raise OpenClawError("OpenClaw adapter identity mismatch")
    if (request.task.family, request.task.scoring_mode) != (
        "legalforecast_mtd",
        "lfb_brier",
    ):
        raise OpenClawError("OpenClaw supports only legalforecast_mtd/lfb_brier")


def unit_ids(request: RunRequest) -> tuple[str, ...]:
    """Require an explicit, unique forecast unit census."""
    value = request.task.metadata.get("required_unit_ids")
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise OpenClawError("required_unit_ids must be an array")
    items = cast(Sequence[object], value)
    if not items or any(not isinstance(v, str) or not v.strip() for v in items):
        raise OpenClawError("required_unit_ids must contain non-empty strings")
    result = tuple(cast(Sequence[str], value))
    if len(result) != len(set(result)):
        raise OpenClawError("required_unit_ids must be unique")
    return result


def offline_fixture(request: RunRequest) -> RunResult:
    """Exercise only the public protocol without pretending to run OpenClaw."""
    validate_request(request)
    if request.task.metadata.get("fixture") != "adapter-conformance":
        raise OpenClawError("ordinary run is restricted to adapter conformance")
    if request.sandbox_policy.allowed_provider_env_vars:
        raise OpenClawError("offline conformance cannot receive provider credentials")
    summary = {
        "adapter_id": ADAPTER_ID,
        "offline_protocol_fixture": True,
        "provider_request_count": 0,
        "task_id": request.task.task_id,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
    }
    return RunResult(
        result_id=f"{request.request_id}:openclaw:fixture",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=record_digest(summary),
        public_summary=summary,
    )


def normalize_result(
    request: RunRequest,
    workspace: Path,
    envelope: Mapping[str, Any],
    *,
    tool_reads: int,
    prompt_complete: bool,
) -> RunResult:
    """Reject failed/drifted runs and retain predictions only as private data."""
    model = request.model_key.removeprefix("openai:")
    if envelope.get("ok") is not True or envelope.get("status") != "ok":
        raise OpenClawError("OpenClaw run did not succeed")
    if envelope.get("provider") != "openai" or envelope.get("model") != model:
        raise OpenClawError("OpenClaw served model or provider mismatch")
    if not prompt_complete or tool_reads < 2:
        raise OpenClawError("OpenClaw must acknowledge every solver prompt page")
    raw = envelope.get("final")
    if not isinstance(raw, str):
        raise OpenClawError("OpenClaw final output is missing")
    parsed = parse_model_output(raw, required_unit_ids=unit_ids(request))
    if not parsed.is_valid or parsed.defaulted_unit_ids:
        raise OpenClawError("OpenClaw forecast output is invalid")
    private = workspace / "private-logs"
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = private / "openclaw-forecast.json"
    write_json_object(
        output,
        {
            "case_assessment": parsed.case_assessment,
            "predictions": [
                prediction.to_record() for prediction in parsed.predictions
            ],
        },
    )
    output.chmod(0o600)
    data = output.read_bytes()
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    summary: dict[str, Any] = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "openclaw_version": OPENCLAW_VERSION,
        "openclaw_commit": OPENCLAW_COMMIT,
        "selected_native_runtime": "openclaw",
        "invocation": "agent exec",
        "auth_mode": "api-key-environment-isolated-home",
        "provider": "openai",
        "requested_model": model,
        "served_model": model,
        "tool_policy": "host-container-solver-prompt-only",
        "tool_call_count": tool_reads,
        "prompt_delivery_complete": prompt_complete,
        "transcript_mirror_behavior": "private-state-only",
        "task_id": request.task.task_id,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "forecast_sha256": digest,
    }
    validate_public_record(summary, "openclaw.public_summary")
    return RunResult(
        result_id=f"{request.request_id}:openclaw",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=record_digest(
            {
                "request_sha256": request.request_sha256,
                "parsed_output": parsed.to_record(),
                "public_summary": summary,
            }
        ),
        artifacts=(
            ArtifactRecord(
                artifact_id="openclaw-forecast-private",
                path="private-logs/openclaw-forecast.json",
                sha256=digest,
                media_type="application/json",
                public=False,
                size_bytes=len(data),
            ),
        ),
        public_summary=summary,
    )
