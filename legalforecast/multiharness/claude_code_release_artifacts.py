"""Release artifact projection for the contained Claude Code adapter."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from legalforecast.evals.output_parser import parse_model_output
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    ReleaseHarnessError,
    read_release_object,
    read_release_regular_file,
    release_bytes_sha256,
    release_canonical_bytes,
    release_record_sha256,
    require_release_metadata_str,
    write_release_create_only,
)
from legalforecast.multiharness.spec import ArtifactRecord, RunRequest, RunResult
from legalforecast.multiharness.validation import (
    validate_public_record,
    validate_safe_relative_path,
)


def project_successful_container_result(
    result: RunResult,
    *,
    request: RunRequest,
    workspace: Path,
    output_root: Path,
) -> RunResult:
    """Bind the generic Claude deliverable to the release artifact contract.

    The container runtime publishes the forecast under ``deliverable-sealed``
    and keeps the container, gateway, and fence records beside its logs.  The
    release harness intentionally accepts only private, release-named
    artifacts, so this boundary validates the generic output and copies its
    bytes into that contract while retaining the original evidence artifacts.
    """

    forecast_artifact = _delegate_forecast_artifact(result)
    forecast_bytes = _read_workspace_artifact(
        workspace,
        forecast_artifact,
        label="Claude forecast output",
    )
    required_unit_ids = _required_unit_ids(request.task.metadata)
    try:
        parsed = parse_model_output(
            forecast_bytes.decode("utf-8", errors="strict"),
            required_unit_ids=required_unit_ids,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ReleaseHarnessError(
            "Claude forecast output cannot be parsed for the selected units"
        ) from exc
    if not parsed.is_valid or parsed.defaulted_unit_ids:
        raise ReleaseHarnessError(
            "Claude forecast output is invalid or contains defaulted units"
        )

    container_record, fence_record, proxy_record, stdout, stderr = (
        _read_container_evidence(output_root, request.request_id)
    )
    tool_call_count = _summary_tool_call_count(result.public_summary)
    allowed_tools = _fence_allowed_tools(fence_record)
    tool_policy = _fence_tool_policy(fence_record)
    packet_sha256 = require_release_metadata_str(request.task.metadata, "packet_sha256")
    prompt_sha256 = require_release_metadata_str(request.task.metadata, "prompt_sha256")
    forecast_sha256 = release_bytes_sha256(forecast_bytes)

    private_logs = workspace / "private-logs"
    private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path = private_logs / "release-forecast-output.json"
    write_release_create_only(output_path, forecast_bytes, mode=0o600)
    transcript = {
        "request_sha256": request.request_sha256,
        "packet_sha256": packet_sha256,
        "prompt_sha256": prompt_sha256,
        "response_sha256": forecast_sha256,
        "delegate_result_sha256": result.result_sha256,
        "container_result": container_record,
        "fence": fence_record,
        "proxy_logs": proxy_record,
        "stdout_sha256": release_bytes_sha256(stdout),
        "stderr_sha256": release_bytes_sha256(stderr),
    }
    transcript_bytes = release_canonical_bytes(transcript)
    transcript_path = private_logs / "release-harness-transcript.json"
    write_release_create_only(transcript_path, transcript_bytes, mode=0o600)
    transcript_sha256 = release_bytes_sha256(transcript_bytes)

    summary = {
        **dict(result.public_summary),
        "harness_track": "native",
        "allowed_tools": list(allowed_tools),
        "tool_policy": tool_policy,
        "tool_call_count": tool_call_count,
        "transcript_sha256": transcript_sha256,
        "execution_backend": "claude_code_container",
        "container_evidence": {
            "result": container_record,
            "fence": fence_record,
            "proxy_logs": proxy_record,
            "stdout_sha256": release_bytes_sha256(stdout),
            "stderr_sha256": release_bytes_sha256(stderr),
        },
    }
    validate_public_record(summary, "Claude Code container release summary")
    output_record = ArtifactRecord(
        artifact_id=RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
        path="private-logs/release-forecast-output.json",
        sha256=forecast_sha256,
        media_type="application/json",
        public=False,
        size_bytes=len(forecast_bytes),
    )
    transcript_record = ArtifactRecord(
        artifact_id=RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
        path="private-logs/release-harness-transcript.json",
        sha256=transcript_sha256,
        media_type="application/json",
        public=False,
        size_bytes=len(transcript_bytes),
    )
    commitment = {
        "delegate_result_sha256": result.result_sha256,
        "public_summary": summary,
        "forecast_output_sha256": output_record.sha256,
        "transcript_sha256": transcript_sha256,
    }
    return RunResult(
        result_id=result.result_id,
        request_id=result.request_id,
        status=result.status,
        result_sha256=release_record_sha256(commitment),
        artifacts=(*result.artifacts, output_record, transcript_record),
        public_summary=summary,
    )


def _delegate_forecast_artifact(result: RunResult) -> ArtifactRecord:
    matches = tuple(
        artifact
        for artifact in result.artifacts
        if artifact.artifact_id == "claude-code-forecast"
    )
    if len(matches) != 1:
        raise ReleaseHarnessError(
            "successful Claude result must contain one generic forecast artifact"
        )
    artifact = matches[0]
    if not artifact.public or artifact.media_type != "application/json":
        raise ReleaseHarnessError(
            "successful Claude forecast artifact must be public JSON"
        )
    if artifact.path.startswith("private-logs/"):
        raise ReleaseHarnessError(
            "generic Claude forecast artifact must not use private release paths"
        )
    return artifact


def _read_workspace_artifact(
    workspace: Path,
    artifact: ArtifactRecord,
    *,
    label: str,
) -> bytes:
    validate_safe_relative_path(artifact.path, f"{label} path")
    payload = read_release_regular_file(workspace / artifact.path)
    if artifact.size_bytes is None or len(payload) != artifact.size_bytes:
        raise ReleaseHarnessError(f"{label} size does not match its artifact record")
    if release_bytes_sha256(payload) != artifact.sha256:
        raise ReleaseHarnessError(f"{label} sha256 does not match its artifact record")
    return payload


def _read_container_evidence(
    output_root: Path,
    request_id: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], bytes, bytes]:
    run_key = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]
    run_root = output_root / run_key
    package_root = run_root / "package"
    result_record = read_release_object(
        package_root / "result.json", "container result evidence"
    )
    fence_record = read_release_object(
        package_root / "fence.json", "container fence evidence"
    )
    proxy_record = read_release_object(
        package_root / "proxy-logs.json", "container gateway evidence"
    )
    if (
        type(result_record.get("exit_code")) is not int
        or result_record["exit_code"] != 0
    ):
        raise ReleaseHarnessError("successful Claude result has nonzero container exit")
    if type(result_record.get("timed_out")) is not bool or result_record["timed_out"]:
        raise ReleaseHarnessError("successful Claude result has timeout evidence")
    logs_root = run_root / "logs"
    stdout = _read_container_log(logs_root, result_record, "stdout_file")
    stderr = _read_container_log(logs_root, result_record, "stderr_file")
    return result_record, fence_record, proxy_record, stdout, stderr


def _read_container_log(
    logs_root: Path,
    result_record: Mapping[str, object],
    field_name: str,
) -> bytes:
    filename = result_record.get(field_name)
    if not isinstance(filename, str):
        raise ReleaseHarnessError(f"container result {field_name} is missing")
    safe_filename = validate_safe_relative_path(filename, f"container {field_name}")
    return read_release_regular_file(logs_root / safe_filename)


def _required_unit_ids(metadata: Mapping[str, object]) -> tuple[str, ...]:
    raw = metadata.get("required_unit_ids")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise ReleaseHarnessError("task metadata required_unit_ids is missing")
    values = tuple(cast(Sequence[object], raw))
    if not values or any(
        type(value) is not str or not value.strip() for value in values
    ):
        raise ReleaseHarnessError("task metadata required_unit_ids is invalid")
    if len(values) != len(set(values)):
        raise ReleaseHarnessError("task metadata required_unit_ids are duplicated")
    return cast(tuple[str, ...], values)


def _summary_tool_call_count(summary: Mapping[str, object]) -> int:
    value = summary.get("tool_call_count")
    if type(value) is not int or value < 0:
        raise ReleaseHarnessError(
            "Claude delegate tool_call_count must be a non-negative integer"
        )
    return value


def _fence_allowed_tools(fence_record: Mapping[str, object]) -> tuple[str, ...]:
    parser_fields = fence_record.get("parser_fields")
    if not isinstance(parser_fields, Mapping):
        raise ReleaseHarnessError("container fence is missing parser fields")
    parser_values = cast(Mapping[str, object], parser_fields)
    raw_tools = parser_values.get("tools_available")
    if not isinstance(raw_tools, Sequence) or isinstance(
        raw_tools, (str, bytes, bytearray)
    ):
        raise ReleaseHarnessError("container fence tools_available is invalid")
    tools = tuple(cast(Sequence[object], raw_tools))
    if not tools or any(type(tool) is not str or not tool.strip() for tool in tools):
        raise ReleaseHarnessError("container fence tools_available is invalid")
    if len(tools) != len(set(tools)):
        raise ReleaseHarnessError("container fence tools_available is duplicated")
    return cast(tuple[str, ...], tools)


def _fence_tool_policy(fence_record: Mapping[str, object]) -> str:
    source = fence_record.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ReleaseHarnessError("container fence source is missing")
    return f"container_fence:{source}"


__all__ = ["project_successful_container_result"]
