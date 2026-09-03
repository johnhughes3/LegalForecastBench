"""Normalize one containerized harness answer into release-protocol evidence.

``release_harness.project_release_harness_result`` is the only route from an
adapter result to an LFB score row, and it authenticates rather than trusts:
it re-reads both private artifacts off disk, re-hashes them against the sizes
and digests the result declared, and refuses a transcript that does not bind
``request``/``packet``/``prompt``/``response`` together.  This module produces
exactly that evidence for the container lane, so the lane scores through the
same door as every other harness instead of a parallel one.

The prompt is never written into the published record.  It arrives from the
private solver-input tree, is proved against the task's own ``prompt_sha256``
commitment, and only its digest travels onward.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    ReleaseHarnessError,
    read_release_regular_file,
    release_bytes_sha256,
    release_canonical_bytes,
    write_release_create_only,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import ArtifactRecord, RunRequest

PRIVATE_LOGS_DIRECTORY: Final = "private-logs"
FORECAST_OUTPUT_PATH: Final = "private-logs/release-forecast-output.json"
TRANSCRIPT_PATH: Final = "private-logs/harness-lane-transcript.json"
# "native" is the release protocol's word for "a real CLI harness ran this",
# as opposed to the credential-free neutral fixture.  Separating this lane
# from the clean-native one is the adapter identity's job -- every receipt
# carries ``treatment_id`` = track:adapter_id:version:model_key, and this
# lane's adapter IDs all end in ``-container-tools-on``.
CONTAINER_HARNESS_TRACK: Final = "native"
CONTAINER_EXECUTION_BACKEND: Final = "container_cli_tools_on"


@dataclass(frozen=True, slots=True)
class ContainerReleaseEvidence:
    """The two private artifacts a release projection re-reads and re-hashes."""

    artifacts: tuple[ArtifactRecord, ...]
    transcript_sha256: str
    output_sha256: str


def read_solver_input_prompt(solver_input_root: Path, expected_sha256: str) -> str:
    """Return the exact private prompt bytes, or refuse a broken commitment."""

    payload = read_release_regular_file(solver_input_root / SOLVER_INPUT_ENTRY_PATH)
    if release_bytes_sha256(payload) != expected_sha256:
        raise ReleaseHarnessError(
            "containerized harness prompt commitment does not match the task"
        )
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ReleaseHarnessError("solver-input prompt must be strict UTF-8") from exc


def write_container_release_evidence(
    *,
    request: RunRequest,
    workspace: Path,
    deliverable: str,
    prompt_sha256: str,
    stdout_bytes: bytes = b"",
) -> ContainerReleaseEvidence:
    """Persist the private forecast output and its binding transcript."""

    private_logs = workspace / PRIVATE_LOGS_DIRECTORY
    private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_bytes = deliverable.encode("utf-8")
    write_release_create_only(
        workspace / FORECAST_OUTPUT_PATH, output_bytes, mode=0o600
    )
    output_sha256 = release_bytes_sha256(output_bytes)
    transcript_bytes = release_canonical_bytes(
        {
            "request_sha256": request.request_sha256,
            "packet_sha256": request.task.task_sha256,
            "prompt_sha256": prompt_sha256,
            "response_sha256": output_sha256,
            "stdout_sha256": release_bytes_sha256(stdout_bytes),
        }
    )
    write_release_create_only(workspace / TRANSCRIPT_PATH, transcript_bytes, mode=0o600)
    transcript_sha256 = release_bytes_sha256(transcript_bytes)
    return ContainerReleaseEvidence(
        artifacts=(
            ArtifactRecord(
                artifact_id=RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
                path=FORECAST_OUTPUT_PATH,
                sha256=output_sha256,
                media_type="application/json",
                public=False,
                size_bytes=len(output_bytes),
            ),
            ArtifactRecord(
                artifact_id=RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
                path=TRANSCRIPT_PATH,
                sha256=transcript_sha256,
                media_type="application/json",
                public=False,
                size_bytes=len(transcript_bytes),
            ),
        ),
        transcript_sha256=transcript_sha256,
        output_sha256=output_sha256,
    )
