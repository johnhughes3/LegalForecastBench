"""Offline-first Claude Code CLI adapter.

This adapter loads B1's frozen local CLI manifest, translates a benchmark
task into a deterministic ``claude -p`` argv via ``LocalCliInvocation.render_argv``,
asks B2's ``LocalCliExecutionService.execute(RunSpec)`` to run it, and parses
the JSON envelope into existing solver/result types. It never starts a
process and never reads credentials. Auth binding
(``LegalForecastBench-dm0g.4.4.9``) resolves ``fixture-none`` or
``published-api-key`` at plan time; credential values stay with the
contained execution service. Tests inject the in-process fake service;
production injects the contained runtime service.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from legalforecast.evals.inspect_task import (
    HarnessRequest,
    SolverKind,
    SolverResponse,
)
from legalforecast.evals.output_parser import ParserStatus, parse_model_output
from legalforecast.multiharness.adapters import AdapterError, AdapterPreparation
from legalforecast.multiharness.auth_binding import (
    bind_adapter_auth_profile,
    public_auth_mode,
    require_credentialed_network_policy,
    require_execution_service_profile,
)
from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
    AuthProfileError,
    require_auth_profile_id,
)
from legalforecast.multiharness.deliverables import (
    DeliverableArtifactProjection,
    DeliverableManifest,
    seal_deliverable,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliFailureClass,
    RunSpec,
    declared_local_cli_failure_classes,
    is_local_cli_sandbox_denial,
)
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    LocalCliUsageReporting,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.sandbox import NETWORK_NONE
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    CanonicalTask,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

CLAUDE_CODE_ADAPTER_ID = "claude-code-clean-native"
CLAUDE_CODE_ADAPTER_VERSION = "1.0.0"
CLAUDE_CODE_EXECUTABLE_NAME = "claude"
CLAUDE_CODE_OUTPUT_CONTRACT_VERSION = (
    # contract-ratchet: allow adapter-local observational schema
    "legalforecast.claude_code.output.v1"
)
CLAUDE_CODE_PROMPT_VERSION = (
    # contract-ratchet: allow adapter-local observational schema
    "legalforecast.claude_code.prompt.v1"
)
CLAUDE_CODE_OUTPUT_SCHEMA_NAME = "output-schema.json"
CLAUDE_FORECAST_SOURCE_PATH = "forecast.json"
CLAUDE_FORECAST_SEALED_PATH = "forecast.json"
CLAUDE_CODE_WRAPPER_COMMAND = (
    "legalforecast.multiharness.claude_code:ClaudeCodeCliAdapter",
)
_FORECAST_OBJECT_KEYS = frozenset({"case_assessment", "predictions"})
_PREDICTION_REQUIRED_KEYS = frozenset({"unit_id", "probability_fully_dismissed"})
_PREDICTION_ALLOWED_KEYS = _PREDICTION_REQUIRED_KEYS | frozenset({"rationale"})
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLAUDE_CODE_MANIFEST_PATH = (
    _REPO_ROOT
    / "examples"
    / "adapters"
    / "claude-code"
    / "local-cli-adapter-manifest.json"
)
_FORBIDDEN_SESSION_FLAGS = frozenset(
    {
        "--bare",
        "--continue",
        "-c",
        "--resume",
        "-r",
        "--session-id",
        "--fork-session",
    }
)
_ALLOWED_VALUE_FLAGS = frozenset(
    {
        "-p",
        "--print",
        "--output-format",
        "--json-schema",
        "--tools",
        "--setting-sources",
        "--model",
        "--add-dir",
    }
)
_ALLOWED_BARE_FLAGS = frozenset(
    {
        "--strict-mcp-config",
        "--no-session-persistence",
    }
)
_ALLOWED_CLAUDE_FLAGS = _ALLOWED_VALUE_FLAGS | _ALLOWED_BARE_FLAGS


class ClaudeCodeCliAdapterError(AdapterError):
    """A Claude Code CLI adapter request or envelope violated the contract."""

    def __init__(
        self,
        message: str,
        *,
        failure_class: LocalCliFailureClass | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_class = failure_class


@dataclass(frozen=True, slots=True)
class ClaudeInvocationPlan:
    """Deterministic argv plan for one headless ``claude -p`` invocation."""

    argv: tuple[str, ...]
    prompt: str
    model: str
    json_schema: Mapping[str, Any]
    output_schema_path: str
    allowed_tools: tuple[str, ...]
    auth_profile: str
    output_format: str = "json"

    def __post_init__(self) -> None:
        require_auth_profile_id(self.auth_profile)
        if not self.argv:
            raise ClaudeCodeCliAdapterError("invocation argv must not be empty")
        if self.argv[0] != CLAUDE_CODE_EXECUTABLE_NAME:
            raise ClaudeCodeCliAdapterError(
                "invocation executable must be the claude basename"
            )
        if "-p" not in self.argv:
            raise ClaudeCodeCliAdapterError("invocation must use headless -p")
        if any(flag in self.argv for flag in _FORBIDDEN_SESSION_FLAGS):
            raise ClaudeCodeCliAdapterError(
                "invocation must not persist, resume, or use --bare"
            )
        _require_flag_value(self.argv, "--output-format", "json")
        if "--json-schema" not in self.argv:
            raise ClaudeCodeCliAdapterError("invocation must enforce JSON schema")
        _require_inline_json_schema(self.argv)
        if "--no-session-persistence" not in self.argv:
            raise ClaudeCodeCliAdapterError(
                "invocation must disable session persistence"
            )
        if "--tools" not in self.argv:
            raise ClaudeCodeCliAdapterError("invocation must declare --tools")
        if "--strict-mcp-config" not in self.argv:
            raise ClaudeCodeCliAdapterError("invocation must set --strict-mcp-config")
        if "sh" in self.argv or "bash" in self.argv or "-c" in self.argv:
            raise ClaudeCodeCliAdapterError("invocation must not invoke a shell")
        _reject_unallowlisted_argv(self.argv)


@dataclass(frozen=True, slots=True)
class ClassifiedClaudeResult:
    """Parsed envelope plus fail-closed classification."""

    failure_class: LocalCliFailureClass | None
    raw_output: str
    structured_output: Mapping[str, Any] | None
    receipt: ExecutionReceipt
    spec: RunSpec
    deliverable_manifest: DeliverableManifest | None = None


def load_claude_code_local_manifest(
    path: Path | None = None,
) -> LocalCliAdapterManifest:
    """Load and pin B1's Claude Code local CLI manifest."""

    manifest_path = path or DEFAULT_CLAUDE_CODE_MANIFEST_PATH
    record = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ClaudeCodeCliAdapterError("local CLI adapter manifest must be an object")
    manifest = LocalCliAdapterManifest.from_record(cast(Mapping[str, Any], record))
    _require_offline_claude_manifest(manifest)
    return manifest


def claude_code_local_manifest() -> LocalCliAdapterManifest:
    """Return the frozen Claude Code local CLI manifest."""

    return load_claude_code_local_manifest()


def claude_code_manifest() -> AdapterManifest:
    """Return the community AdapterManifest projection."""

    return claude_code_local_manifest().to_adapter_manifest(
        command=CLAUDE_CODE_WRAPPER_COMMAND,
    )


def forecast_output_schema(required_unit_ids: Sequence[str]) -> dict[str, Any]:
    """Return the JSON schema enforced on Claude Code structured output."""

    unit_ids = list(required_unit_ids)
    return {
        "type": "object",
        "properties": {
            "case_assessment": {"type": "string", "minLength": 1},
            "predictions": {
                "type": "array",
                "minItems": len(unit_ids),
                "maxItems": len(unit_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "unit_id": {
                            "type": "string",
                            "enum": unit_ids,
                        },
                        "probability_fully_dismissed": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["unit_id", "probability_fully_dismissed"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["case_assessment", "predictions"],
        "additionalProperties": False,
    }


def encode_forecast_output_schema(required_unit_ids: Sequence[str]) -> str:
    """Return compact JSON for Claude Code's ``--json-schema`` argv token."""

    schema = forecast_output_schema(required_unit_ids)
    return json.dumps(schema, sort_keys=True, separators=(",", ":"), allow_nan=False)


def write_forecast_output_schema(
    path: Path,
    required_unit_ids: Sequence[str],
) -> dict[str, Any]:
    """Write an audit copy of the forecast schema; argv still uses inline JSON."""

    schema = forecast_output_schema(required_unit_ids)
    path.write_text(
        json.dumps(schema, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return schema


def build_claude_invocation_plan(
    *,
    prompt: str,
    model: str,
    required_unit_ids: Sequence[str],
    workspace: Path,
    output_schema_path: Path,
    allowed_tools: Sequence[str] = (),
    manifest: LocalCliAdapterManifest | None = None,
    auth_profile: object = FIXTURE_NONE,
) -> ClaudeInvocationPlan:
    """Translate one task into a shell-safe argv from the frozen template."""

    if not prompt.strip():
        raise ClaudeCodeCliAdapterError("prompt must be non-empty")
    if not model.strip() or "/" in model or "\\" in model:
        raise ClaudeCodeCliAdapterError("model must be a non-empty basename")
    local_manifest = manifest or claude_code_local_manifest()
    try:
        bound = bind_adapter_auth_profile(local_manifest, auth_profile)
    except AuthProfileError as exc:
        raise ClaudeCodeCliAdapterError(str(exc)) from exc
    schema = forecast_output_schema(required_unit_ids)
    schema_token = encode_forecast_output_schema(required_unit_ids)
    tools = _validated_tools(allowed_tools)
    rendered = local_manifest.invocation.render_argv(
        prompt=prompt,
        model=model,
        workspace=workspace.as_posix(),
        output_schema=schema_token,
    )
    argv = _apply_allowed_tools(
        (local_manifest.executable.basename, *rendered),
        tools,
    )
    return ClaudeInvocationPlan(
        argv=argv,
        prompt=prompt,
        model=model,
        json_schema=schema,
        output_schema_path=output_schema_path.as_posix(),
        allowed_tools=tools,
        auth_profile=bound.profile_id,
    )


def build_run_spec(
    request: RunRequest,
    plan: ClaudeInvocationPlan,
    workspace: Path,
    *,
    timeout_seconds: float,
) -> RunSpec:
    """Bind an invocation plan to a credential-free RunSpec."""

    if request.sandbox_policy.allowed_provider_env_vars:
        raise ClaudeCodeCliAdapterError(
            "offline Claude Code adapter must not receive provider environment grants"
        )
    return RunSpec(
        spec_id=request.request_id,
        argv=plan.argv,
        working_directory=workspace,
        environment={},
        timeout_seconds=timeout_seconds,
        output_format="json",
        json_schema=plan.json_schema,
    )


def classify_execution(
    spec: RunSpec,
    receipt: ExecutionReceipt,
    *,
    required_unit_ids: Sequence[str],
    requested_model: str,
) -> ClassifiedClaudeResult:
    """Classify one execution fail-closed into the declared failure set."""

    if receipt.spec_sha256 != spec.spec_sha256:
        raise ClaudeCodeCliAdapterError("execution receipt does not bind the RunSpec")
    if receipt.status == "timeout":
        return _classified(
            LocalCliFailureClass.TIMEOUT,
            raw_output=receipt.stdout or "timeout",
            spec=spec,
            receipt=receipt,
        )
    envelope = _parse_json_envelope(receipt.stdout)
    if envelope is None:
        if is_local_cli_sandbox_denial(_failure_text(receipt, None)):
            return _classified(
                LocalCliFailureClass.SANDBOX_DENIAL,
                raw_output=receipt.stdout or receipt.stderr or "sandbox_denial",
                spec=spec,
                receipt=receipt,
            )
        return _classified(
            LocalCliFailureClass.CRASH,
            raw_output=receipt.stdout or "crash",
            spec=spec,
            receipt=receipt,
        )
    if _is_error_like(receipt, envelope):
        if envelope.get("is_error") is True and envelope.get("subtype") == "timeout":
            return _classified(
                LocalCliFailureClass.TIMEOUT,
                raw_output=_result_text(envelope) or "timeout",
                spec=spec,
                receipt=receipt,
            )
        if is_local_cli_sandbox_denial(_failure_text(receipt, envelope)):
            return _classified(
                LocalCliFailureClass.SANDBOX_DENIAL,
                raw_output=receipt.stdout or receipt.stderr or "sandbox_denial",
                spec=spec,
                receipt=receipt,
            )
        return _classified(
            LocalCliFailureClass.CRASH,
            raw_output=receipt.stdout or "crash",
            spec=spec,
            receipt=receipt,
        )
    if _served_model_drifted(envelope, receipt, requested_model):
        return _classified(
            LocalCliFailureClass.CRASH,
            raw_output=_result_text(envelope) or "model drift",
            spec=spec,
            receipt=receipt,
        )
    raw_output = _encoded_result_payload(envelope)
    if raw_output is None:
        return _classified(
            LocalCliFailureClass.SCHEMA_VIOLATION,
            raw_output=receipt.stdout or "schema violation",
            spec=spec,
            receipt=receipt,
        )
    parsed = parse_model_output(raw_output, required_unit_ids=required_unit_ids)
    if parsed.status is ParserStatus.REFUSAL:
        return _classified(
            LocalCliFailureClass.REFUSAL,
            raw_output=raw_output,
            spec=spec,
            receipt=receipt,
        )
    if not parsed.is_valid:
        return _classified(
            LocalCliFailureClass.SCHEMA_VIOLATION,
            raw_output=raw_output,
            spec=spec,
            receipt=receipt,
        )
    structured = json.loads(raw_output)
    if not isinstance(structured, dict) or not _forecast_matches_declared_schema(
        cast(Mapping[str, Any], structured),
        required_unit_ids,
    ):
        return _classified(
            LocalCliFailureClass.SCHEMA_VIOLATION,
            raw_output=raw_output,
            spec=spec,
            receipt=receipt,
        )
    return ClassifiedClaudeResult(
        failure_class=None,
        raw_output=raw_output,
        structured_output=cast(Mapping[str, Any], structured),
        spec=spec,
        receipt=receipt,
    )


def declared_failure_classes() -> tuple[str, ...]:
    """Return the failure classes this adapter classifies fail-closed."""

    return declared_local_cli_failure_classes()


@dataclass(frozen=True, slots=True)
class ClaudeCodeCliAdapter:
    """In-process Claude Code adapter that executes only through B2's service."""

    execution_service: LocalCliExecutionService
    local_manifest: LocalCliAdapterManifest = field(
        default_factory=claude_code_local_manifest
    )
    auth_profile: str = FIXTURE_NONE

    def __post_init__(self) -> None:
        _require_offline_claude_manifest(self.local_manifest)
        try:
            bind_adapter_auth_profile(self.local_manifest, self.auth_profile)
        except AuthProfileError as exc:
            raise ClaudeCodeCliAdapterError(str(exc)) from exc

    @property
    def manifest(self) -> AdapterManifest:
        return self.local_manifest.to_adapter_manifest(
            command=CLAUDE_CODE_WRAPPER_COMMAND,
        )

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        workspace.mkdir(parents=True, exist_ok=True)
        return self.local_manifest.to_adapter_capabilities()

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        workspace.mkdir(parents=True, exist_ok=True)
        capabilities = self.capabilities(workspace)
        if request.adapter.adapter_id != self.manifest.adapter_id:
            raise ClaudeCodeCliAdapterError("request adapter id does not match")
        if request.adapter.adapter_version != self.manifest.adapter_version:
            raise ClaudeCodeCliAdapterError("request adapter version does not match")
        if request.task.family not in capabilities.supported_families:
            raise ClaudeCodeCliAdapterError(
                f"adapter does not support task family: {request.task.family}"
            )
        if request.task.scoring_mode not in capabilities.supported_scoring_modes:
            raise ClaudeCodeCliAdapterError(
                f"adapter does not support scoring mode: {request.task.scoring_mode}"
            )
        _required_unit_ids(request.task)
        _solver_prompt(request.task)
        _requested_model(request.model_key)
        try:
            bound = bind_adapter_auth_profile(self.local_manifest, self.auth_profile)
            require_execution_service_profile(
                self.execution_service,
                bound.profile_id,
                projected_env_vars=bound.profile.projected_env_vars,
            )
            require_credentialed_network_policy(
                bound.profile_id, request.sandbox_policy.network_policy
            )
        except AuthProfileError as exc:
            raise ClaudeCodeCliAdapterError(str(exc)) from exc
        if request.sandbox_policy.allowed_provider_env_vars:
            raise ClaudeCodeCliAdapterError(
                "offline Claude Code adapter must not receive provider "
                "environment grants"
            )
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        self.prepare(request, workspace)
        classified = self._execute_request(request, workspace)
        if classified.failure_class is None:
            classified = _with_deliverable(classified, request, workspace)
        return _run_result(
            request,
            classified,
            usage_reporting=self.local_manifest.usage_reporting,
            auth_profile=self.auth_profile,
        )

    def _execute_request(
        self,
        request: RunRequest,
        workspace: Path,
    ) -> ClassifiedClaudeResult:
        required_unit_ids = _required_unit_ids(request.task)
        schema_path = workspace / CLAUDE_CODE_OUTPUT_SCHEMA_NAME
        write_forecast_output_schema(schema_path, required_unit_ids)
        plan = build_claude_invocation_plan(
            prompt=_solver_prompt(request.task),
            model=_requested_model(request.model_key),
            required_unit_ids=required_unit_ids,
            workspace=workspace,
            output_schema_path=schema_path,
            allowed_tools=_allowed_tools(request.task),
            manifest=self.local_manifest,
            auth_profile=self.auth_profile,
        )
        spec = build_run_spec(
            request,
            plan,
            workspace,
            timeout_seconds=_timeout_seconds(request, self.local_manifest),
        )
        receipt = self.execution_service.execute(spec)
        return classify_execution(
            spec,
            receipt,
            required_unit_ids=required_unit_ids,
            requested_model=plan.model,
        )


@dataclass(frozen=True, slots=True)
class ClaudeCodeCliSolver:
    """HarnessSolver that uses the Claude Code CLI adapter without forking it."""

    execution_service: LocalCliExecutionService
    model_key: str
    workspace: Path | None = None
    adapter: ClaudeCodeCliAdapter | None = None
    network_policy: str = NETWORK_NONE

    def __post_init__(self) -> None:
        _requested_model(self.model_key)
        if self.adapter is None:
            service_profile = getattr(
                self.execution_service, "auth_profile", FIXTURE_NONE
            )
            if not isinstance(service_profile, str) or not service_profile:
                service_profile = FIXTURE_NONE
            object.__setattr__(
                self,
                "adapter",
                ClaudeCodeCliAdapter(
                    execution_service=self.execution_service,
                    auth_profile=service_profile,
                ),
            )
        adapter = self.adapter
        if adapter is None:
            return
        try:
            require_credentialed_network_policy(
                adapter.auth_profile, self.network_policy
            )
        except AuthProfileError as exc:
            raise ClaudeCodeCliAdapterError(str(exc)) from exc

    @property
    def solver_id(self) -> str:
        return f"{CLAUDE_CODE_ADAPTER_ID}:{self.model_key}"

    @property
    def solver_kind(self) -> SolverKind:
        return SolverKind.INSPECT_AI

    def solve(self, request: HarnessRequest) -> SolverResponse:
        adapter = self.adapter
        if adapter is None:
            raise ClaudeCodeCliAdapterError("Claude Code solver adapter is missing")
        if request.sample.use_docket_tool:
            raise ClaudeCodeCliAdapterError(
                "Claude Code CLI solver does not implement controlled "
                "docket-tool samples"
            )
        if self.workspace is None:
            with TemporaryDirectory() as tmp:
                return self._solve_in(adapter, request, Path(tmp))
        return self._solve_in(adapter, request, self.workspace)

    def _solve_in(
        self,
        adapter: ClaudeCodeCliAdapter,
        request: HarnessRequest,
        workspace: Path,
    ) -> SolverResponse:
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            bound = bind_adapter_auth_profile(
                adapter.local_manifest, adapter.auth_profile
            )
            require_execution_service_profile(
                adapter.execution_service,
                bound.profile_id,
                projected_env_vars=bound.profile.projected_env_vars,
            )
            require_credentialed_network_policy(bound.profile_id, self.network_policy)
        except AuthProfileError as exc:
            raise ClaudeCodeCliAdapterError(str(exc)) from exc
        required_unit_ids = request.sample.required_unit_ids
        schema_path = workspace / CLAUDE_CODE_OUTPUT_SCHEMA_NAME
        write_forecast_output_schema(schema_path, required_unit_ids)
        plan = build_claude_invocation_plan(
            prompt=request.sample.prompt,
            model=_requested_model(self.model_key),
            required_unit_ids=required_unit_ids,
            workspace=workspace,
            output_schema_path=schema_path,
            manifest=adapter.local_manifest,
            auth_profile=adapter.auth_profile,
        )
        spec = RunSpec(
            spec_id=request.sample.sample_id,
            argv=plan.argv,
            working_directory=workspace,
            environment={},
            timeout_seconds=float(adapter.local_manifest.timeout_retry.timeout_seconds),
            json_schema=plan.json_schema,
        )
        receipt = adapter.execution_service.execute(spec)
        classified = classify_execution(
            spec,
            receipt,
            required_unit_ids=required_unit_ids,
            requested_model=plan.model,
        )
        if classified.failure_class is not None:
            raise ClaudeCodeCliAdapterError(
                "Claude Code CLI solver failed: "
                f"{classified.failure_class.value} "
                f"task_id={request.sample.sample_id} "
                f"returncode={classified.receipt.returncode!r}",
                failure_class=classified.failure_class,
            )
        usage = _usage_from_envelope(
            classified.receipt,
            adapter.local_manifest.usage_reporting,
        )
        return SolverResponse(
            raw_output=classified.raw_output,
            request_count=1,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            estimated_cost=usage["estimated_cost"],
            metadata={
                "adapter_id": CLAUDE_CODE_ADAPTER_ID,
                "auth_profile": bound.profile_id,
                "spec_sha256": classified.spec.spec_sha256,
                "receipt_id": classified.receipt.receipt_id,
            },
        )


def _with_deliverable(
    classified: ClassifiedClaudeResult,
    request: RunRequest,
    workspace: Path,
) -> ClassifiedClaudeResult:
    if classified.structured_output is None:
        raise ClaudeCodeCliAdapterError(
            "successful result is missing structured output"
        )
    source_root = workspace / "deliverable-source"
    sealed_root = workspace / "deliverable-sealed"
    source_root.mkdir(parents=True, exist_ok=True)
    payload = _encoded_structured_output(classified.structured_output)
    (source_root / CLAUDE_FORECAST_SOURCE_PATH).write_bytes(payload)
    manifest = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=request.task.task_sha256,
        run_sha256=request.request_sha256,
        config_sha256=classified.spec.spec_sha256,
        artifacts=(
            DeliverableArtifactProjection(
                artifact_id="claude-code-forecast",
                source_path=CLAUDE_FORECAST_SOURCE_PATH,
                path=CLAUDE_FORECAST_SEALED_PATH,
                media_type="application/json",
                max_size_bytes=1_048_576,
            ),
        ),
    )
    bound_receipt = ExecutionReceipt(
        receipt_id=classified.receipt.receipt_id,
        spec_sha256=classified.receipt.spec_sha256,
        status=classified.receipt.status,
        returncode=classified.receipt.returncode,
        executable_name=classified.receipt.executable_name,
        stdout=classified.receipt.stdout,
        stderr=classified.receipt.stderr,
        stdout_sha256=classified.receipt.stdout_sha256,
        stderr_sha256=classified.receipt.stderr_sha256,
        duration_ms=classified.receipt.duration_ms,
        served_model=classified.receipt.served_model,
        executable_version=classified.receipt.executable_version,
        usage=classified.receipt.usage,
        cost_usd=classified.receipt.cost_usd,
        runtime_policy_sha256=classified.receipt.runtime_policy_sha256,
        deliverable_manifest_sha256=manifest.manifest_sha256,
        failure_class=None,
    )
    return ClassifiedClaudeResult(
        failure_class=None,
        raw_output=classified.raw_output,
        structured_output=classified.structured_output,
        spec=classified.spec,
        receipt=bound_receipt,
        deliverable_manifest=manifest,
    )


def _run_result(
    request: RunRequest,
    classified: ClassifiedClaudeResult,
    *,
    usage_reporting: LocalCliUsageReporting,
    auth_profile: str,
) -> RunResult:
    artifacts: tuple[ArtifactRecord, ...] = ()
    if classified.deliverable_manifest is not None:
        forecast = classified.deliverable_manifest.artifacts[0]
        artifacts = (
            ArtifactRecord(
                artifact_id=forecast.artifact_id,
                path=f"deliverable-sealed/{forecast.path}",
                sha256=forecast.sha256,
                media_type=forecast.media_type,
                public=True,
                size_bytes=forecast.size_bytes,
            ),
        )
    summary = _public_summary(
        request,
        classified,
        usage_reporting=usage_reporting,
        auth_profile=auth_profile,
    )
    validate_public_record(summary, "claude_code.public_summary")
    commitment = {
        "public_summary": summary,
        "request_sha256": request.request_sha256,
        "spec_sha256": classified.spec.spec_sha256,
        "receipt": classified.receipt.to_public_record(),
    }
    status = "succeeded" if classified.failure_class is None else "failed"
    return RunResult(
        result_id=f"{request.request_id}:{CLAUDE_CODE_ADAPTER_ID}",
        request_id=request.request_id,
        status=status,
        result_sha256=_record_sha256(commitment),
        artifacts=artifacts,
        public_summary=summary,
    )


def _public_summary(
    request: RunRequest,
    classified: ClassifiedClaudeResult,
    *,
    usage_reporting: LocalCliUsageReporting,
    auth_profile: str,
) -> dict[str, Any]:
    usage = _usage_from_envelope(classified.receipt, usage_reporting)
    profile_id = require_auth_profile_id(auth_profile)
    summary: dict[str, Any] = {
        "adapter_id": CLAUDE_CODE_ADAPTER_ID,
        "adapter_version": CLAUDE_CODE_ADAPTER_VERSION,
        "auth_mode": public_auth_mode(profile_id, fixture_mode="none-offline"),
        "auth_profile": profile_id,
        "model_key": request.model_key,
        "output_contract_version": CLAUDE_CODE_OUTPUT_CONTRACT_VERSION,
        "prompt_version": CLAUDE_CODE_PROMPT_VERSION,
        "provider": "anthropic",
        "requested_model": _requested_model(request.model_key),
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "spec_sha256": classified.spec.spec_sha256,
        "task_id": request.task.task_id,
        "tool_call_count": 0,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "estimated_cost": usage["estimated_cost"],
    }
    if classified.receipt.served_model is not None:
        summary["served_model"] = classified.receipt.served_model
    if classified.receipt.deliverable_manifest_sha256 is not None:
        summary["deliverable_manifest_sha256"] = (
            classified.receipt.deliverable_manifest_sha256
        )
    if classified.failure_class is not None:
        summary["failure_class"] = classified.failure_class.value
    summary["returncode"] = classified.receipt.returncode
    return summary


def _classified(
    failure_class: LocalCliFailureClass,
    *,
    raw_output: str,
    spec: RunSpec,
    receipt: ExecutionReceipt,
) -> ClassifiedClaudeResult:
    bound = ExecutionReceipt(
        receipt_id=receipt.receipt_id,
        spec_sha256=receipt.spec_sha256,
        status="timeout" if failure_class is LocalCliFailureClass.TIMEOUT else "failed",
        returncode=receipt.returncode,
        executable_name=receipt.executable_name,
        stdout=receipt.stdout,
        stderr=receipt.stderr,
        stdout_sha256=receipt.stdout_sha256,
        stderr_sha256=receipt.stderr_sha256,
        duration_ms=receipt.duration_ms,
        served_model=receipt.served_model,
        executable_version=receipt.executable_version,
        usage=receipt.usage,
        cost_usd=receipt.cost_usd,
        runtime_policy_sha256=receipt.runtime_policy_sha256,
        deliverable_manifest_sha256=None,
        failure_class=failure_class.value,
    )
    return ClassifiedClaudeResult(
        failure_class=failure_class,
        raw_output=raw_output,
        structured_output=None,
        spec=spec,
        receipt=bound,
    )


def _is_error_like(receipt: ExecutionReceipt, envelope: Mapping[str, Any]) -> bool:
    return (
        receipt.status == "failed"
        or (receipt.returncode is not None and receipt.returncode != 0)
        or envelope.get("type") != "result"
        or envelope.get("is_error") is True
    )


def _failure_text(
    receipt: ExecutionReceipt,
    envelope: Mapping[str, Any] | None,
) -> str:
    if envelope is None:
        return "\n".join((receipt.stdout, receipt.stderr))
    parts = [receipt.stderr]
    if envelope.get("is_error") is True:
        parts.append(_result_text(envelope))
    return "\n".join(parts)


def _parse_json_envelope(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    return cast(dict[str, Any], decoded)


def _result_text(envelope: Mapping[str, Any]) -> str:
    result = envelope.get("result")
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        return _encoded_structured_output(cast(Mapping[str, Any], result)).decode(
            "utf-8"
        )
    return ""


def _encoded_result_payload(envelope: Mapping[str, Any]) -> str | None:
    result = envelope.get("result")
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        try:
            return _encoded_structured_output(cast(Mapping[str, Any], result)).decode(
                "utf-8"
            )
        except ClaudeCodeCliAdapterError:
            return None
    return None


def _encoded_structured_output(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                dict(value),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ClaudeCodeCliAdapterError(
            "Claude Code structured output must be JSON"
        ) from None


def _required_unit_ids(task: CanonicalTask) -> tuple[str, ...]:
    value = task.metadata.get("required_unit_ids")
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ClaudeCodeCliAdapterError(
            "task metadata required_unit_ids must be an array"
        )
    unit_ids: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ClaudeCodeCliAdapterError(
                "task metadata required_unit_ids must contain non-empty strings"
            )
        unit_ids.append(item)
    if not unit_ids or len(unit_ids) != len(set(unit_ids)):
        raise ClaudeCodeCliAdapterError(
            "task metadata required_unit_ids must be non-empty and unique"
        )
    return tuple(unit_ids)


def _solver_prompt(task: CanonicalTask) -> str:
    value = task.metadata.get("solver_prompt")
    if not isinstance(value, str) or not value.strip():
        raise ClaudeCodeCliAdapterError(
            "task metadata solver_prompt must be a non-empty string"
        )
    return value


def _allowed_tools(task: CanonicalTask) -> tuple[str, ...]:
    if "allowed_tools" not in task.metadata:
        return ()
    value = task.metadata["allowed_tools"]
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ClaudeCodeCliAdapterError("task metadata allowed_tools must be an array")
    tools: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ClaudeCodeCliAdapterError(
                "task metadata allowed_tools must contain non-empty strings"
            )
        tools.append(item)
    return _validated_tools(tools)


def _requested_model(model_key: str) -> str:
    prefix = "anthropic:"
    if not model_key.startswith(prefix) or len(model_key) == len(prefix):
        raise ClaudeCodeCliAdapterError(
            "model_key must use the anthropic:<model> namespace"
        )
    return model_key[len(prefix) :]


def _timeout_seconds(request: RunRequest, manifest: LocalCliAdapterManifest) -> float:
    requested = float(request.sandbox_policy.timeout_seconds)
    declared = float(manifest.timeout_retry.timeout_seconds)
    return min(requested, declared)


def _usage_from_envelope(
    receipt: ExecutionReceipt,
    reporting: LocalCliUsageReporting,
) -> dict[str, Any]:
    envelope = _parse_json_envelope(receipt.stdout)
    input_tokens = _lookup_int(
        envelope,
        reporting.input_tokens_field,
        receipt.usage.get("input_tokens", 0),
    )
    output_tokens = _lookup_int(
        envelope,
        reporting.output_tokens_field,
        receipt.usage.get("output_tokens", 0),
    )
    estimated_cost = receipt.cost_usd if receipt.cost_usd is not None else 0.0
    if reporting.cost_usd_field is not None and envelope is not None:
        raw_cost = _dotted_lookup(envelope, reporting.cost_usd_field)
        parsed_cost = _non_negative_number(raw_cost)
        if parsed_cost is not None:
            estimated_cost = parsed_cost
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": estimated_cost,
    }


def _lookup_int(envelope: Mapping[str, Any] | None, path: str, default: int) -> int:
    if envelope is None:
        if type(default) is not int or default < 0:
            raise ClaudeCodeCliAdapterError(f"usage {path} is invalid")
        return default
    raw = _dotted_lookup(envelope, path)
    if type(raw) is int and raw >= 0:
        return raw
    if type(default) is not int or default < 0:
        raise ClaudeCodeCliAdapterError(f"usage {path} is invalid")
    return default


def _dotted_lookup(record: Mapping[str, Any], path: str) -> object:
    current: Mapping[str, Any] = record
    parts = path.split(".")
    for index, part in enumerate(parts):
        if part not in current:
            return None
        value: object = current[part]
        if index == len(parts) - 1:
            return value
        if not isinstance(value, dict):
            return None
        current = cast(dict[str, Any], value)
    return None


def _non_negative_number(value: object) -> float | None:
    if type(value) is int and value >= 0:
        return float(value)
    if type(value) is float and math.isfinite(value) and value >= 0:
        return value
    return None


def _validated_tools(allowed_tools: Sequence[str]) -> tuple[str, ...]:
    tools = tuple(allowed_tools)
    for index, tool_name in enumerate(tools):
        if (
            not tool_name
            or "," in tool_name
            or " " in tool_name
            or not tool_name[0].isalpha()
        ):
            raise ClaudeCodeCliAdapterError(f"allowed_tools[{index}] is not safe")
        if not all(
            character.isalnum() or character in {"_", "-"} for character in tool_name
        ):
            raise ClaudeCodeCliAdapterError(f"allowed_tools[{index}] is not safe")
    return tools


def _apply_allowed_tools(
    argv: tuple[str, ...],
    allowed_tools: tuple[str, ...],
) -> tuple[str, ...]:
    if not allowed_tools:
        return argv
    try:
        index = argv.index("--tools")
    except ValueError as exc:
        raise ClaudeCodeCliAdapterError("manifest argv is missing --tools") from exc
    if index + 1 >= len(argv):
        raise ClaudeCodeCliAdapterError("manifest --tools flag is missing a value")
    mutable = list(argv)
    mutable[index + 1] = ",".join(allowed_tools)
    return tuple(mutable)


def _reject_unallowlisted_argv(argv: Sequence[str]) -> None:
    """Refuse flags the frozen clean-native template does not name."""

    index = 1
    while index < len(argv):
        token = argv[index]
        if token in _ALLOWED_BARE_FLAGS:
            index += 1
            continue
        if token in _ALLOWED_VALUE_FLAGS:
            if index + 1 >= len(argv):
                raise ClaudeCodeCliAdapterError(f"flag {token} is missing a value")
            index += 2
            continue
        if token.startswith("-"):
            raise ClaudeCodeCliAdapterError(
                f"un-allowlisted flag refused at plan time: {token}"
            )
        raise ClaudeCodeCliAdapterError(
            f"un-allowlisted argv token refused at plan time: {token}"
        )


def _require_flag_value(argv: Sequence[str], flag: str, expected: str) -> None:
    try:
        index = argv.index(flag)
    except ValueError as exc:
        raise ClaudeCodeCliAdapterError(f"invocation must set {flag}") from exc
    if index + 1 >= len(argv) or argv[index + 1] != expected:
        raise ClaudeCodeCliAdapterError(f"invocation {flag} must be {expected}")


def _require_offline_claude_manifest(manifest: LocalCliAdapterManifest) -> None:
    if manifest.manifest_id != CLAUDE_CODE_ADAPTER_ID:
        raise ClaudeCodeCliAdapterError(
            "local CLI manifest_id must be claude-code-clean-native"
        )
    if manifest.harness_binding.adapter_version != CLAUDE_CODE_ADAPTER_VERSION:
        raise ClaudeCodeCliAdapterError("local CLI adapter_version must be 1.0.0")
    if manifest.executable.basename != CLAUDE_CODE_EXECUTABLE_NAME:
        raise ClaudeCodeCliAdapterError("local CLI executable basename must be claude")
    if manifest.auth_profile_name != FIXTURE_NONE:
        raise ClaudeCodeCliAdapterError(
            "offline Claude Code adapter requires auth_profile_name fixture-none"
        )
    if FIXTURE_NONE not in manifest.supported_auth_profiles:
        raise ClaudeCodeCliAdapterError("Claude Code adapter must support fixture-none")
    if PUBLISHED_API_KEY not in manifest.supported_auth_profiles:
        raise ClaudeCodeCliAdapterError(
            "Claude Code adapter must support published-api-key"
        )
    if manifest.harness_binding.solver_kind != SolverKind.INSPECT_AI.value:
        raise ClaudeCodeCliAdapterError("solver_kind must be inspect_ai")
    if manifest.containment.session_persistence != "forbidden":
        raise ClaudeCodeCliAdapterError("session persistence must be forbidden")
    if manifest.invocation.output_format != "json":
        raise ClaudeCodeCliAdapterError("invocation output_format must be json")
    if manifest.invocation.schema_enforcement == "none":
        raise ClaudeCodeCliAdapterError("invocation must enforce JSON schema")


def _require_inline_json_schema(argv: Sequence[str]) -> None:
    try:
        index = argv.index("--json-schema")
    except ValueError as exc:
        raise ClaudeCodeCliAdapterError("invocation must enforce JSON schema") from exc
    if index + 1 >= len(argv):
        raise ClaudeCodeCliAdapterError("flag --json-schema is missing a value")
    token = argv[index + 1]
    try:
        decoded = json.loads(token)
    except json.JSONDecodeError as exc:
        raise ClaudeCodeCliAdapterError(
            "--json-schema must be inline JSON, not a filesystem path"
        ) from exc
    if not isinstance(decoded, dict):
        raise ClaudeCodeCliAdapterError("--json-schema must be a JSON object")


def _served_model_drifted(
    envelope: Mapping[str, Any],
    receipt: ExecutionReceipt,
    requested_model: str,
) -> bool:
    reported: list[str] = []
    envelope_model = envelope.get("model")
    if isinstance(envelope_model, str) and envelope_model.strip():
        reported.append(envelope_model)
    if isinstance(receipt.served_model, str) and receipt.served_model.strip():
        reported.append(receipt.served_model)
    return any(model != requested_model for model in reported)


def _forecast_matches_declared_schema(
    payload: Mapping[str, Any],
    required_unit_ids: Sequence[str],
) -> bool:
    if frozenset(payload) != _FORECAST_OBJECT_KEYS:
        return False
    assessment = payload.get("case_assessment")
    if not isinstance(assessment, str) or not assessment.strip():
        return False
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        return False
    prediction_items = cast(list[object], predictions)
    if len(prediction_items) != len(required_unit_ids):
        return False
    observed: list[str] = []
    allowed_units = set(required_unit_ids)
    for item in prediction_items:
        if not isinstance(item, dict):
            return False
        prediction = cast(dict[str, Any], item)
        keys = set(prediction)
        if not _PREDICTION_REQUIRED_KEYS.issubset(keys):
            return False
        if not keys.issubset(_PREDICTION_ALLOWED_KEYS):
            return False
        unit_id = prediction["unit_id"]
        probability = prediction["probability_fully_dismissed"]
        if not isinstance(unit_id, str) or unit_id not in allowed_units:
            return False
        if (
            not isinstance(probability, int | float)
            or isinstance(probability, bool)
            or not math.isfinite(float(probability))
            or not 0 <= float(probability) <= 1
        ):
            return False
        if "rationale" in prediction and not isinstance(prediction["rationale"], str):
            return False
        observed.append(unit_id)
    return len(observed) == len(set(observed)) and set(observed) == allowed_units


# contract-ratchet: allow non-persisted local-cli result digest
def _record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
