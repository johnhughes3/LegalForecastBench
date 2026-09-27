"""Private Hermes output and transcript projection into the release contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from legalforecast.evals.output_parser import ParserStatus, parse_model_output
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    is_release_task,
    require_release_metadata_str,
)
from legalforecast.multiharness.release_runtime import (
    release_bytes_sha256,
    release_canonical_bytes,
    release_record_sha256,
    write_release_create_only,
)
from legalforecast.multiharness.spec import ArtifactRecord, RunRequest, RunResult
from legalforecast.multiharness.validation import validate_public_record


def build_result(
    request: RunRequest,
    workspace: Path,
    trajectory: Path,
    raw: bytes,
    execution: Mapping[str, object],
    output: str,
    required_units: Sequence[str],
    session_id: str,
    provenance: Mapping[str, object],
) -> RunResult:
    """Validate a forecast and retain private, request-bound release evidence."""

    parsed = parse_model_output(output, required_unit_ids=required_units)
    if parsed.status != ParserStatus.VALID:
        raise ValueError("Hermes returned an invalid forecast")
    output_bytes = output.encode("utf-8")
    output_digest = release_bytes_sha256(output_bytes)
    transcript: dict[str, object] = {"execution": dict(execution)}
    if is_release_task(request):
        transcript.update(
            request_sha256=request.request_sha256,
            packet_sha256=require_release_metadata_str(
                request.task.metadata, "packet_sha256"
            ),
            prompt_sha256=require_release_metadata_str(
                request.task.metadata, "prompt_sha256"
            ),
            response_sha256=output_digest,
        )
    transcript_bytes = release_canonical_bytes(transcript)
    transcript_digest = release_bytes_sha256(transcript_bytes)
    artifacts: list[ArtifactRecord] = []
    for name, artifact_id, payload in (
        ("forecast.json", RELEASE_FORECAST_OUTPUT_ARTIFACT_ID, output_bytes),
        ("transcript.json", RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID, transcript_bytes),
    ):
        path = trajectory.with_name(name)
        write_release_create_only(path, payload, mode=0o600)
        artifacts.append(
            ArtifactRecord(
                artifact_id=artifact_id,
                path=path.relative_to(workspace.absolute()).as_posix(),
                sha256=release_bytes_sha256(payload),
                media_type="application/json",
                public=False,
                size_bytes=len(payload),
            )
        )
    artifacts.append(
        ArtifactRecord(
            artifact_id="hermes-private-trajectory",
            path=trajectory.relative_to(workspace.absolute()).as_posix(),
            sha256=release_bytes_sha256(raw),
            media_type="application/json",
            public=False,
            size_bytes=len(raw),
        )
    )
    summary = {
        **provenance,
        "harness_track": "native",
        "allowed_tools": ["read_canonical_task", "read_release_document"]
        if provenance.get("auth_mode") == "host-gateway"
        else ["read_canonical_task"],
        "tool_policy": "host_read_staged_release_only"
        if provenance.get("auth_mode") == "host-gateway"
        else "host_read_canonical_task_only",
        "transcript_sha256": transcript_digest,
        "forecast_sha256": output_digest,
        "trajectory_sha256": release_bytes_sha256(raw),
        "session_sha256": release_bytes_sha256(session_id.encode()),
    }
    validate_public_record(summary, "hermes.public_summary")
    return RunResult(
        result_id=f"{request.request_id}:hermes",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=release_record_sha256(
            {
                "request": request.request_sha256,
                "parsed": parsed.to_record(),
                "summary": summary,
            }
        ),
        public_summary=summary,
        artifacts=tuple(artifacts),
    )
