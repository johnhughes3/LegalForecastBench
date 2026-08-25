"""Neutral fixture and native wrappers for release-backed harness rows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legalforecast.multiharness.adapters import AdapterPreparation, HarnessAdapter
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    ReleaseHarnessError,
    read_release_regular_file,
    release_bytes_sha256,
    release_canonical_bytes,
    release_record_sha256,
    require_release_metadata_str,
    write_release_create_only,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

NEUTRAL_FIXTURE_ADAPTER_ID = "neutral-api-fixture"
NEUTRAL_FIXTURE_ADAPTER_VERSION = "1.0.0"
_NATIVE_DELEGATE_SUMMARY_FIELDS = frozenset(
    {
        "adapter_bundle_sha256",
        "approval_policy",
        "auth_mode",
        "auth_profile",
        "deliverable_manifest_sha256",
        "executable",
        "input_tokens",
        "model_key",
        "offline_protocol_fixture",
        "output_tokens",
        "provider",
        "requested_model",
        "returncode",
        "sandbox_mode",
        "sandbox_policy_id",
        "served_model",
        "subscription_login_claimed",
        "total_tokens",
    }
)


@dataclass(frozen=True, slots=True)
class NeutralApiFixtureAdapter:
    """Credential-free neutral API fixture for release protocol conformance."""

    raw_output: str = field(repr=False)
    manifest: AdapterManifest = field(
        default_factory=lambda: AdapterManifest(
            adapter_id=NEUTRAL_FIXTURE_ADAPTER_ID,
            display_name="Neutral API Release Fixture",
            adapter_version=NEUTRAL_FIXTURE_ADAPTER_VERSION,
            command=("in-process-neutral-api-fixture",),
        )
    )

    def __post_init__(self) -> None:
        if not self.raw_output.strip():
            raise ValueError("raw_output must be non-empty")

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        workspace.mkdir(parents=True, exist_ok=True)
        content = {
            "adapter_id": self.manifest.adapter_id,
            "adapter_version": self.manifest.adapter_version,
            "supported_families": ["legalforecast_mtd"],
            "supported_scoring_modes": ["lfb_brier"],
        }
        return AdapterCapabilities(
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            supported_families=("legalforecast_mtd",),
            supported_scoring_modes=("lfb_brier",),
            capabilities_sha256=release_record_sha256(content),
        )

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        capabilities = self.capabilities(workspace)
        if request.adapter.to_record() != self.manifest.to_record():
            raise ReleaseHarnessError("neutral fixture adapter manifest does not match")
        if request.task.family != "legalforecast_mtd":
            raise ReleaseHarnessError("neutral fixture requires an LFB task")
        if request.task.scoring_mode != "lfb_brier":
            raise ReleaseHarnessError("neutral fixture requires LFB scoring")
        if request.sandbox_policy.allowed_provider_env_vars:
            raise ReleaseHarnessError("neutral fixture must not receive credentials")
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        self.prepare(request, workspace)
        raise ReleaseHarnessError(
            "neutral release fixture requires authenticated solver input"
        )

    def run_with_solver_input(
        self,
        request: RunRequest,
        workspace: Path,
        solver_input_root: Path,
    ) -> RunResult:
        self.prepare(request, workspace)
        prompt = read_release_regular_file(solver_input_root / SOLVER_INPUT_ENTRY_PATH)
        prompt_sha256 = release_bytes_sha256(prompt)
        if prompt_sha256 != require_release_metadata_str(
            request.task.metadata, "prompt_sha256"
        ):
            raise ReleaseHarnessError(
                "neutral fixture prompt commitment does not match"
            )
        private_logs = workspace / "private-logs"
        private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
        output_bytes = self.raw_output.encode("utf-8")
        output_path = private_logs / "release-forecast-output.json"
        write_release_create_only(output_path, output_bytes, mode=0o600)
        transcript = {
            "request_sha256": request.request_sha256,
            "prompt_sha256": prompt_sha256,
            "packet_sha256": request.task.task_sha256,
            "response_sha256": release_bytes_sha256(output_bytes),
        }
        transcript_bytes = release_canonical_bytes(transcript)
        transcript_path = private_logs / "neutral-api-transcript.json"
        write_release_create_only(transcript_path, transcript_bytes, mode=0o600)
        summary: dict[str, Any] = {
            "adapter_id": self.manifest.adapter_id,
            "adapter_version": self.manifest.adapter_version,
            "model_key": request.model_key,
            "sandbox_policy_id": request.sandbox_policy.policy_id,
            "harness_track": "neutral",
            "execution_backend": "neutral_api_fixture",
            "provider_request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": 0.0,
            "allowed_tools": [],
            "tool_policy": "none",
            "tool_call_count": 0,
            "transcript_sha256": release_bytes_sha256(transcript_bytes),
        }
        validate_public_record(summary, "neutral release fixture summary")
        commitment = {
            "request_sha256": request.request_sha256,
            "output_sha256": release_bytes_sha256(output_bytes),
            "summary": summary,
        }
        return RunResult(
            result_id=f"{request.request_id}:{self.manifest.adapter_id}",
            request_id=request.request_id,
            status="succeeded",
            result_sha256=release_record_sha256(commitment),
            artifacts=(
                ArtifactRecord(
                    artifact_id=RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
                    path="private-logs/release-forecast-output.json",
                    sha256=release_bytes_sha256(output_bytes),
                    media_type="application/json",
                    public=False,
                    size_bytes=len(output_bytes),
                ),
                ArtifactRecord(
                    artifact_id=RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
                    path="private-logs/neutral-api-transcript.json",
                    sha256=release_bytes_sha256(transcript_bytes),
                    media_type="application/json",
                    public=False,
                    size_bytes=len(transcript_bytes),
                ),
            ),
            public_summary=summary,
        )


@dataclass(frozen=True, slots=True)
class NativeReleaseAdapter:
    """Bind an existing native CLI adapter to authenticated release inputs."""

    delegate: HarnessAdapter
    tool_policy: str = "native_cli_builtins"
    allowed_tools: tuple[str, ...] = ("native_cli_builtin",)

    def __post_init__(self) -> None:
        if not self.tool_policy.strip():
            raise ValueError("tool_policy must be non-empty")
        if not self.allowed_tools or any(
            not tool.strip() for tool in self.allowed_tools
        ):
            raise ValueError("allowed_tools must contain non-empty tool IDs")
        if len(self.allowed_tools) != len(set(self.allowed_tools)):
            raise ValueError("allowed_tools must be unique")

    @property
    def manifest(self) -> AdapterManifest:
        return self.delegate.manifest

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        return self.delegate.capabilities(workspace)

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        return self.delegate.prepare(request, workspace)

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        raise ReleaseHarnessError(
            "native release adapter requires authenticated solver input"
        )

    def run_with_solver_input(
        self,
        request: RunRequest,
        workspace: Path,
        solver_input_root: Path,
    ) -> RunResult:
        """Stage only the exact prompt, run the delegate, and normalize evidence."""

        prompt = read_release_regular_file(solver_input_root / SOLVER_INPUT_ENTRY_PATH)
        prompt_sha256 = require_release_metadata_str(
            request.task.metadata, "prompt_sha256"
        )
        if release_bytes_sha256(prompt) != prompt_sha256:
            raise ReleaseHarnessError("native prompt commitment does not match")
        prompt_path = workspace / SOLVER_INPUT_ENTRY_PATH
        workspace.mkdir(parents=True, exist_ok=True)
        write_release_create_only(prompt_path, prompt, mode=0o400)
        try:
            result = self.delegate.run(request, workspace)
            if result.status == "succeeded":
                try:
                    final_prompt = read_release_regular_file(prompt_path)
                except ReleaseHarnessError as exc:
                    raise ReleaseHarnessError(
                        "native staged prompt is unavailable after execution"
                    ) from exc
                if release_bytes_sha256(final_prompt) != prompt_sha256:
                    raise ReleaseHarnessError(
                        "native staged prompt changed during execution"
                    )
        finally:
            prompt_path.unlink(missing_ok=True)
        if result.status != "succeeded":
            return result
        forecast_path = workspace / "sealed-deliverable/work-product/answer.md"
        forecast_bytes = read_release_regular_file(forecast_path)
        stdout = read_release_regular_file(
            workspace / "private-logs/codex-stdout.jsonl"
        )
        stderr = read_release_regular_file(workspace / "private-logs/codex-stderr.log")
        output_path = workspace / "private-logs/release-forecast-output.json"
        write_release_create_only(output_path, forecast_bytes, mode=0o600)
        transcript_bytes = release_canonical_bytes(
            {
                "request_sha256": request.request_sha256,
                "packet_sha256": request.task.task_sha256,
                "prompt_sha256": require_release_metadata_str(
                    request.task.metadata,
                    "prompt_sha256",
                ),
                "response_sha256": release_bytes_sha256(forecast_bytes),
                "stdout_sha256": release_bytes_sha256(stdout),
                "stderr_sha256": release_bytes_sha256(stderr),
            }
        )
        transcript_path = workspace / "private-logs/release-harness-transcript.json"
        write_release_create_only(transcript_path, transcript_bytes, mode=0o600)
        transcript_sha256 = release_bytes_sha256(transcript_bytes)
        summary = {
            **{
                key: value
                for key, value in result.public_summary.items()
                if key in _NATIVE_DELEGATE_SUMMARY_FIELDS
            },
            "adapter_id": self.manifest.adapter_id,
            "adapter_version": self.manifest.adapter_version,
            "model_key": request.model_key,
            "sandbox_policy_id": request.sandbox_policy.policy_id,
            "allowed_tools": list(self.allowed_tools),
            "harness_track": "native",
            "execution_backend": "native_cli",
            "tool_policy": self.tool_policy,
            "tool_call_count": _delegate_tool_call_count(result.public_summary),
            "transcript_sha256": transcript_sha256,
        }
        artifact = ArtifactRecord(
            artifact_id=RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
            path="private-logs/release-forecast-output.json",
            sha256=release_bytes_sha256(forecast_bytes),
            media_type="application/json",
            public=False,
            size_bytes=len(forecast_bytes),
        )
        transcript_artifact = ArtifactRecord(
            artifact_id=RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
            path="private-logs/release-harness-transcript.json",
            sha256=transcript_sha256,
            media_type="application/json",
            public=False,
            size_bytes=len(transcript_bytes),
        )
        approved_artifacts = _approved_native_delegate_artifacts(result)
        artifacts = (*approved_artifacts, artifact, transcript_artifact)
        commitment = {
            "delegate_result_sha256": result.result_sha256,
            "public_summary": summary,
            "forecast_output_sha256": artifact.sha256,
        }
        return RunResult(
            result_id=result.result_id,
            request_id=result.request_id,
            status=result.status,
            result_sha256=release_record_sha256(commitment),
            artifacts=artifacts,
            public_summary=summary,
        )


def _delegate_tool_call_count(summary: Mapping[str, Any]) -> int:
    value = summary.get("tool_call_count")
    if type(value) is not int or value < 0:
        raise ReleaseHarnessError(
            "native delegate tool_call_count must be a non-negative integer"
        )
    return value


def _approved_native_delegate_artifacts(
    result: RunResult,
) -> tuple[ArtifactRecord, ...]:
    approved: list[ArtifactRecord] = []
    for artifact in result.artifacts:
        if artifact.artifact_id == RELEASE_FORECAST_OUTPUT_ARTIFACT_ID:
            raise ReleaseHarnessError(
                "native delegate must not issue release artifacts"
            )
        if artifact.public or not artifact.path.startswith("private-logs/"):
            raise ReleaseHarnessError(
                "native delegate artifacts must be private runtime artifacts"
            )
        approved.append(artifact)
    return tuple(approved)
