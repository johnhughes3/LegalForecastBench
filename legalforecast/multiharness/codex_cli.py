"""Offline Codex CLI adapter: invocation plan, JSONL envelope, fail-closed results.

Invocation plans are rendered from B1's closed
``legalforecast.multiharness.local_cli_adapter_manifest.v1`` instance shipped
with this adapter. Shared execution-service types belong to B2
(``LegalForecastBench-dm0g.4.2.7``) and must not be duplicated here; the
Codex-prefixed Protocol below is the consumer seam until that service lands.
Do not copy sibling ``local_cli_contracts`` drafts onto this branch.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.multiharness.adapters import AdapterError, AdapterPreparation
from legalforecast.multiharness.deliverables import (
    DeliverableArtifactProjection,
    seal_deliverable,
)
from legalforecast.multiharness.local_cli_manifest import LocalCliAdapterManifest
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    ContributorCredit,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

CODEX_CLI_ADAPTER_ID = "codex-cli-offline"
CODEX_CLI_ADAPTER_VERSION = "0.1.0"
CODEX_CLI_EXECUTABLE = "codex"
CODEX_MODEL_KEY_PREFIX = "codex:"
CODEX_DEFAULT_REASONING_EFFORT = "medium"
CODEX_REASONING_EFFORTS = frozenset({"low", "medium", "high"})
CODEX_SANDBOX_MODE = "workspace-write"
CODEX_APPROVAL_POLICY = "never"
CODEX_FAILURE_CLASSES = frozenset(
    {
        "timeout",
        "refusal",
        "schema_violation",
        "crash",
        "sandbox_denial",
    }
)
_FORBIDDEN_FLAGS = frozenset(
    {
        "--add-dir",
        "--approve-for-me",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "--last",
        "--local-provider",
        "--oss",
        "--profile",
        "--remote",
        "--search",
    }
)
_REQUIRED_EVENTS = ("thread.started", "turn.started")
_ALLOWED_EVENT_TYPES = frozenset(
    {
        "error",
        "item.completed",
        "item.started",
        "thread.started",
        "turn.completed",
        "turn.failed",
        "turn.started",
    }
)
_REFUSAL_MARKERS = ("refus", "i cannot help", "i must decline", "i won't help")
_SANDBOX_MARKERS = ("sandbox denied", "sandbox denial", "landlock", "seccomp")
_AUTH_BASENAMES = frozenset({"auth.json", "auth.json.age"})
CODEX_LOCAL_CLI_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "adapters"
    / "codex-cli"
    / "local-cli-manifest.json"
)
_LAST_MESSAGE_RELATIVE_PATH = Path("private-logs") / "codex-last-message.txt"
_REASONING_EFFORT_PREFIX = "model_reasoning_effort="


class CodexCliAdapterError(AdapterError):
    """Raised when the offline Codex CLI adapter cannot run safely."""


@dataclass(frozen=True, slots=True)
class CodexCliExecutionRequest:
    """One argv-array invocation for the shared local CLI execution service."""

    argv: tuple[str, ...]
    cwd: Path
    stdin: str
    timeout_seconds: float
    environment: Mapping[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class CodexCliExecutionOutcome:
    """Raw bytes-and-status returned by one fake or real CLI execution."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    crashed: bool = False


class CodexCliExecutionService(Protocol):
    """B2 execution seam. Tests inject a fake; this adapter never spawns."""

    def execute(self, request: CodexCliExecutionRequest) -> CodexCliExecutionOutcome:
        """Run one planned argv without the adapter importing subprocess."""

        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class CodexCliInvocationPlan:
    """Deterministic, shell-free `codex exec` argv and stdin."""

    argv: tuple[str, ...]
    stdin: str
    working_directory: Path
    last_message_path: Path
    requested_model: str
    reasoning_effort: str
    timeout_seconds: float

    def public_config(self) -> dict[str, str]:
        """Path-independent invocation identity for deliverable binding."""

        return {
            "approval_policy": CODEX_APPROVAL_POLICY,
            "color": "never",
            "ephemeral": "true",
            "executable": CODEX_CLI_EXECUTABLE,
            "ignore_rules": "true",
            "ignore_user_config": "true",
            "json": "true",
            "model": self.requested_model,
            "reasoning_effort": self.reasoning_effort,
            "sandbox": CODEX_SANDBOX_MODE,
            "skip_git_repo_check": "true",
            "strict_config": "true",
            "subcommand": "exec",
        }


@dataclass(frozen=True, slots=True)
class CodexCliParsedEnvelope:
    """Fail-closed classification of one Codex JSONL stream."""

    failure_class: str | None
    last_message: str
    events: tuple[Mapping[str, Any], ...]
    input_tokens: int
    output_tokens: int
    served_model: str | None
    thread_id: str | None


def codex_cli_manifest() -> AdapterManifest:
    """Return the built-in offline Codex CLI adapter manifest."""

    return AdapterManifest(
        adapter_id=CODEX_CLI_ADAPTER_ID,
        display_name="Codex CLI Offline Adapter",
        adapter_version=CODEX_CLI_ADAPTER_VERSION,
        command=("python", "-m", "legalforecast.multiharness.codex_cli_cli"),
        contributors=(
            ContributorCredit(
                role="adapter_author",
                name="LegalForecastBench maintainers",
            ),
        ),
    )


def load_codex_local_cli_manifest(
    path: Path | None = None,
) -> LocalCliAdapterManifest:
    """Load the offline Codex instance of B1's local CLI adapter manifest."""

    manifest_path = path or CODEX_LOCAL_CLI_MANIFEST_PATH
    decoded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise CodexCliAdapterError("local CLI manifest must be a JSON object")
    manifest = LocalCliAdapterManifest.from_record(cast(Mapping[str, Any], decoded))
    if manifest.manifest_id != CODEX_CLI_ADAPTER_ID:
        raise CodexCliAdapterError("local CLI manifest_id does not match adapter id")
    if manifest.executable.basename != CODEX_CLI_EXECUTABLE:
        raise CodexCliAdapterError("local CLI executable basename must be 'codex'")
    return manifest


def build_capabilities() -> AdapterCapabilities:
    """Return public capabilities projected from the local CLI manifest."""

    return load_codex_local_cli_manifest().to_adapter_capabilities()


def requested_model(model_key: str) -> str:
    """Strip the required ``codex:`` namespace from a live model key."""

    if not model_key.startswith(CODEX_MODEL_KEY_PREFIX) or model_key == (
        CODEX_MODEL_KEY_PREFIX
    ):
        raise CodexCliAdapterError("model_key must use the codex:<model> namespace")
    return model_key[len(CODEX_MODEL_KEY_PREFIX) :]


def build_codex_invocation_plan(
    request: RunRequest,
    workspace: Path,
    *,
    prompt: str,
    executable: str = CODEX_CLI_EXECUTABLE,
    local_cli_manifest: LocalCliAdapterManifest | None = None,
) -> CodexCliInvocationPlan:
    """Build a deterministic argv array from the local CLI manifest."""

    if not prompt.strip():
        raise CodexCliAdapterError("prompt must be non-empty")
    _reject_forbidden_executable(executable)
    manifest = local_cli_manifest or load_codex_local_cli_manifest()
    if manifest.executable.basename != executable:
        raise CodexCliAdapterError(
            "Codex CLI executable must match the local CLI manifest basename"
        )
    if manifest.invocation.headless_mode != "exec_subcommand":
        raise CodexCliAdapterError("offline Codex CLI adapter requires exec_subcommand")
    model = requested_model(request.model_key)
    effort = _reasoning_effort(request)
    prompt_for_argv = (
        prompt if manifest.invocation.prompt_delivery == "argv_placeholder" else ""
    )
    rendered = manifest.invocation.render_argv(
        prompt=prompt_for_argv,
        model=model,
        workspace=str(workspace),
        output_schema_path="",
    )
    argv = _apply_reasoning_effort((executable, *rendered), effort)
    _reject_forbidden_argv(argv)
    stdin = prompt if manifest.invocation.prompt_delivery == "stdin" else ""
    return CodexCliInvocationPlan(
        argv=argv,
        stdin=stdin,
        working_directory=workspace,
        last_message_path=workspace / _LAST_MESSAGE_RELATIVE_PATH,
        requested_model=model,
        reasoning_effort=effort,
        timeout_seconds=float(request.sandbox_policy.timeout_seconds),
    )


def parse_codex_jsonl(
    stdout: str,
    *,
    requested_model_name: str,
    returncode: int,
    timed_out: bool,
    crashed: bool,
    last_message_file: str | None = None,
) -> CodexCliParsedEnvelope:
    """Parse a Codex JSONL envelope and classify failures fail-closed."""

    if timed_out:
        return _failed_envelope("timeout", ())
    if crashed:
        return _failed_envelope("crash", ())

    events, parse_failure = _load_events(stdout)
    if parse_failure is not None:
        return _failed_envelope(parse_failure, events)

    joined_text = _event_text(events)
    if _is_sandbox_denial(joined_text):
        return _failed_envelope("sandbox_denial", events)
    if _is_refusal(joined_text):
        return _failed_envelope("refusal", events)

    types = tuple(str(event.get("type", "")) for event in events)
    if any(event_type not in _ALLOWED_EVENT_TYPES for event_type in types):
        return _failed_envelope("schema_violation", events)
    if any(required not in types for required in _REQUIRED_EVENTS):
        return _failed_envelope("schema_violation", events)

    started: Mapping[str, Any] = events[0] if events else {}
    served_model = _optional_str(started, "actual_model")
    requested_observed = _optional_str(started, "requested_model")
    if requested_observed is not None and requested_observed != requested_model_name:
        return _failed_envelope("schema_violation", events)
    if served_model is not None and served_model != requested_model_name:
        return _failed_envelope("schema_violation", events)

    last_message = last_message_file if last_message_file is not None else ""
    if not last_message.strip():
        last_message = _agent_message(events)
    if _is_refusal(last_message):
        return _failed_envelope("refusal", events, last_message=last_message)

    if "turn.failed" in types or "error" in types:
        return _failed_envelope(_failure_from_errors(events, returncode), events)
    if returncode != 0:
        return _failed_envelope("crash", events)
    if "turn.completed" not in types or not last_message.strip():
        return _failed_envelope("schema_violation", events)

    usage = _usage(events)
    return CodexCliParsedEnvelope(
        failure_class=None,
        last_message=last_message,
        events=events,
        input_tokens=usage[0],
        output_tokens=usage[1],
        served_model=served_model or requested_model_name,
        thread_id=_optional_str(started, "thread_id"),
    )


def run_offline_protocol_fixture(request: RunRequest, workspace: Path) -> RunResult:
    """Return a credential-free fixture result for standard conformance."""

    _validate_request(request, require_codex_model=False)
    if request.task.metadata.get("fixture") != "adapter-conformance":
        raise CodexCliAdapterError(
            "ordinary run is restricted to the adapter conformance fixture"
        )
    if request.sandbox_policy.allowed_provider_env_vars:
        raise CodexCliAdapterError(
            "offline conformance must not receive provider environment grants"
        )
    workspace.mkdir(parents=True, exist_ok=True)
    summary = _public_summary(
        request,
        auth_mode="none-offline-protocol-fixture",
        requested_model=request.model_key,
        served_model=None,
        failure_class=None,
        input_tokens=0,
        output_tokens=0,
        offline_protocol_fixture=True,
        deliverable_manifest_sha256=None,
    )
    return RunResult(
        result_id=f"{request.request_id}:codex-cli:offline-fixture",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_commitment_digest(summary),
        public_summary=summary,
    )


@dataclass(frozen=True, slots=True)
class CodexCliAdapter:
    """In-process Codex CLI adapter that never spawns a process."""

    execution_service: CodexCliExecutionService
    manifest: AdapterManifest = field(default_factory=codex_cli_manifest)

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        workspace.mkdir(parents=True, exist_ok=True)
        return build_capabilities()

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        workspace.mkdir(parents=True, exist_ok=True)
        capabilities = self.capabilities(workspace)
        _validate_request(request, require_codex_model=True)
        if request.adapter.adapter_id != self.manifest.adapter_id:
            raise CodexCliAdapterError("run request adapter ID does not match manifest")
        if request.adapter.adapter_version != self.manifest.adapter_version:
            raise CodexCliAdapterError(
                "run request adapter version does not match manifest"
            )
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        """Plan, fake-execute, parse, and bind a canonical result."""

        self.prepare(request, workspace)
        if request.sandbox_policy.allowed_provider_env_vars:
            raise CodexCliAdapterError(
                "offline Codex CLI adapter must not receive provider environment grants"
            )
        prompt = _prompt_for(workspace, request)
        plan = build_codex_invocation_plan(request, workspace, prompt=prompt)
        private_logs = workspace / "private-logs"
        private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_logs.chmod(0o700)
        outcome = self.execution_service.execute(
            CodexCliExecutionRequest(
                argv=plan.argv,
                cwd=workspace,
                stdin=plan.stdin,
                timeout_seconds=plan.timeout_seconds,
                environment={},
            )
        )
        _write_private_text(private_logs / "codex-stdout.jsonl", outcome.stdout)
        _write_private_text(private_logs / "codex-stderr.log", outcome.stderr)
        last_message_file = _optional_existing_text(plan.last_message_path)
        envelope = parse_codex_jsonl(
            outcome.stdout,
            requested_model_name=plan.requested_model,
            returncode=outcome.returncode,
            timed_out=outcome.timed_out,
            crashed=outcome.crashed,
            last_message_file=last_message_file,
        )
        if envelope.failure_class is not None:
            return _failed_result(request, envelope)
        return _successful_result(request, workspace, plan, envelope)


def adapter_bundle_sha256() -> str:
    """Commit to the executable adapter, manifest, and locked dependency state."""

    project_root = Path(__file__).resolve().parents[2]
    relative_paths = (
        "legalforecast/multiharness/codex_cli.py",
        "legalforecast/multiharness/codex_cli_cli.py",
        "examples/adapters/codex-cli/adapter-manifest.json",
        "examples/adapters/codex-cli/local-cli-manifest.json",
        "pyproject.toml",
        "uv.lock",
    )
    digest = hashlib.sha256()
    for relative_path in relative_paths:
        name = relative_path.encode("utf-8")
        payload = (project_root / relative_path).read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def _validate_request(request: RunRequest, *, require_codex_model: bool) -> None:
    if request.adapter.adapter_id != CODEX_CLI_ADAPTER_ID:
        raise CodexCliAdapterError("request adapter id does not match")
    if request.adapter.adapter_version != CODEX_CLI_ADAPTER_VERSION:
        raise CodexCliAdapterError("request adapter version does not match")
    if request.task.family != "legalforecast_mtd":
        raise CodexCliAdapterError("Codex CLI adapter supports only legalforecast_mtd")
    if request.task.scoring_mode != "lfb_brier":
        raise CodexCliAdapterError("Codex CLI adapter supports only lfb_brier")
    if require_codex_model:
        requested_model(request.model_key)


def _reasoning_effort(request: RunRequest) -> str:
    value = request.task.metadata.get(
        "reasoning_effort", CODEX_DEFAULT_REASONING_EFFORT
    )
    if not isinstance(value, str) or value not in CODEX_REASONING_EFFORTS:
        raise CodexCliAdapterError("reasoning_effort must be low, medium, or high")
    return value


def _prompt_for(workspace: Path, request: RunRequest) -> str:
    prompt_path = workspace / SOLVER_INPUT_ENTRY_PATH
    _reject_auth_path(prompt_path)
    if prompt_path.is_file():
        text = prompt_path.read_text(encoding="utf-8")
        if text.strip():
            return text
    metadata_prompt = request.task.metadata.get("prompt")
    if isinstance(metadata_prompt, str) and metadata_prompt.strip():
        return metadata_prompt
    raise CodexCliAdapterError("solver prompt.txt is missing")


def _reject_auth_path(path: Path) -> None:
    if path.name in _AUTH_BASENAMES:
        raise CodexCliAdapterError("Codex CLI adapter must not read auth stores")


def _reject_forbidden_executable(executable: str) -> None:
    if executable != CODEX_CLI_EXECUTABLE:
        raise CodexCliAdapterError(
            "Codex CLI executable must be the unqualified basename 'codex'"
        )


def _apply_reasoning_effort(argv: Sequence[str], effort: str) -> tuple[str, ...]:
    replaced = False
    tokens: list[str] = []
    for token in argv:
        if token.startswith(_REASONING_EFFORT_PREFIX):
            tokens.append(f'{_REASONING_EFFORT_PREFIX}"{effort}"')
            replaced = True
        else:
            tokens.append(token)
    if not replaced:
        raise CodexCliAdapterError(
            "local CLI argv template must pin model_reasoning_effort"
        )
    return tuple(tokens)


def _reject_forbidden_argv(argv: Sequence[str]) -> None:
    for token in argv:
        if token in _FORBIDDEN_FLAGS:
            raise CodexCliAdapterError(f"Codex CLI invocation must not include {token}")
        if "auth.json" in token:
            raise CodexCliAdapterError(
                "Codex CLI invocation must not reference auth.json"
            )


def _load_events(
    stdout: str,
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    events: list[Mapping[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError:
            return tuple(events), "schema_violation"
        if not isinstance(decoded, dict):
            return tuple(events), "schema_violation"
        events.append(cast(Mapping[str, Any], decoded))
    return tuple(events), None


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return None


def _event_text(events: Sequence[Mapping[str, Any]]) -> str:
    chunks: list[str] = []
    for event in events:
        message = event.get("message")
        if isinstance(message, str):
            chunks.append(message)
        error = _as_mapping(event.get("error"))
        if error is not None:
            nested = error.get("message")
            if isinstance(nested, str):
                chunks.append(nested)
        item = _as_mapping(event.get("item"))
        if item is not None:
            text = item.get("text")
            if isinstance(text, str):
                chunks.append(text)
            aggregated = item.get("aggregated_output")
            if isinstance(aggregated, str):
                chunks.append(aggregated)
    return "\n".join(chunks).casefold()


def _agent_message(events: Sequence[Mapping[str, Any]]) -> str:
    messages: list[str] = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = _as_mapping(event.get("item"))
        if item is None:
            continue
        if item.get("type") != "agent_message":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            messages.append(text)
    return messages[-1] if messages else ""


def _usage(events: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    for event in reversed(events):
        if event.get("type") != "turn.completed":
            continue
        usage = _as_mapping(event.get("usage"))
        if usage is None:
            return 0, 0
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        if type(input_tokens) is not int or type(output_tokens) is not int:
            return 0, 0
        if input_tokens < 0 or output_tokens < 0:
            return 0, 0
        return input_tokens, output_tokens
    return 0, 0


def _is_refusal(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in _REFUSAL_MARKERS)


def _is_sandbox_denial(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in _SANDBOX_MARKERS)


def _failure_from_errors(
    events: Sequence[Mapping[str, Any]],
    returncode: int,
) -> str:
    del returncode
    text = _event_text(events)
    if _is_sandbox_denial(text):
        return "sandbox_denial"
    if _is_refusal(text):
        return "refusal"
    return "crash"


def _failed_envelope(
    failure_class: str,
    events: Sequence[Mapping[str, Any]],
    *,
    last_message: str = "",
) -> CodexCliParsedEnvelope:
    if failure_class not in CODEX_FAILURE_CLASSES:
        failure_class = "schema_violation"
    return CodexCliParsedEnvelope(
        failure_class=failure_class,
        last_message=last_message,
        events=tuple(events),
        input_tokens=0,
        output_tokens=0,
        served_model=None,
        thread_id=None,
    )


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _optional_existing_text(path: Path) -> str | None:
    _reject_auth_path(path)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _write_private_text(path: Path, payload: str) -> None:
    _reject_auth_path(path)
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o600)


def _public_summary(
    request: RunRequest,
    *,
    auth_mode: str,
    requested_model: str,
    served_model: str | None,
    failure_class: str | None,
    input_tokens: int,
    output_tokens: int,
    offline_protocol_fixture: bool,
    deliverable_manifest_sha256: str | None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "adapter_id": CODEX_CLI_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": CODEX_CLI_ADAPTER_VERSION,
        "approval_policy": CODEX_APPROVAL_POLICY,
        "auth_mode": auth_mode,
        "executable": CODEX_CLI_EXECUTABLE,
        "input_tokens": input_tokens,
        "model_key": request.model_key,
        "offline_protocol_fixture": offline_protocol_fixture,
        "output_tokens": output_tokens,
        "provider": "openai",
        "provider_request_count": 0,
        "requested_model": requested_model,
        "sandbox_mode": CODEX_SANDBOX_MODE,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "subscription_login_claimed": False,
        "task_id": request.task.task_id,
        "tool_call_count": 0,
        "total_tokens": input_tokens + output_tokens,
    }
    if served_model is not None:
        summary["served_model"] = served_model
    if failure_class is not None:
        summary["failure_class"] = failure_class
    if deliverable_manifest_sha256 is not None:
        summary["deliverable_manifest_sha256"] = deliverable_manifest_sha256
    validate_public_record(summary, "codex_cli.public_summary")
    return summary


def _failed_result(
    request: RunRequest,
    envelope: CodexCliParsedEnvelope,
) -> RunResult:
    summary = _public_summary(
        request,
        auth_mode="none-offline-cli-adapter",
        requested_model=requested_model(request.model_key),
        served_model=envelope.served_model,
        failure_class=envelope.failure_class,
        input_tokens=0,
        output_tokens=0,
        offline_protocol_fixture=False,
        deliverable_manifest_sha256=None,
    )
    return RunResult(
        result_id=f"{request.request_id}:codex-cli",
        request_id=request.request_id,
        status="failed",
        result_sha256=_commitment_digest(summary),
        public_summary=summary,
    )


def _successful_result(
    request: RunRequest,
    workspace: Path,
    plan: CodexCliInvocationPlan,
    envelope: CodexCliParsedEnvelope,
) -> RunResult:
    source_root = workspace / "codex-output"
    source_root.mkdir(parents=True, exist_ok=True)
    submission = source_root / "submission.md"
    payload = (
        envelope.last_message
        if envelope.last_message.endswith("\n")
        else (f"{envelope.last_message}\n")
    )
    submission.write_text(payload, encoding="utf-8")
    sealed_root = workspace / "sealed-deliverable"
    manifest = seal_deliverable(
        source_root=source_root,
        sealed_root=sealed_root,
        task_sha256=request.task.task_sha256,
        run_sha256=request.request_sha256,
        config_sha256=_commitment_digest(plan.public_config()),
        artifacts=(
            DeliverableArtifactProjection(
                artifact_id="answer",
                source_path="submission.md",
                path="work-product/answer.md",
                media_type="text/markdown",
                max_size_bytes=1_048_576,
            ),
        ),
    )
    manifest_path = workspace / "private-logs" / "codex-deliverable-manifest.json"
    encoded = (
        json.dumps(manifest.to_record(), indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    manifest_path.write_bytes(encoded)
    manifest_path.chmod(0o600)
    artifact_digest = hashlib.sha256()
    artifact_digest.update(encoded)
    summary = _public_summary(
        request,
        auth_mode="none-offline-cli-adapter",
        requested_model=plan.requested_model,
        served_model=envelope.served_model,
        failure_class=None,
        input_tokens=envelope.input_tokens,
        output_tokens=envelope.output_tokens,
        offline_protocol_fixture=False,
        deliverable_manifest_sha256=manifest.manifest_sha256,
    )
    commitment = {
        "deliverable_manifest_sha256": manifest.manifest_sha256,
        "public_summary": summary,
        "request_sha256": request.request_sha256,
    }
    return RunResult(
        result_id=f"{request.request_id}:codex-cli",
        request_id=request.request_id,
        status="succeeded",
        result_sha256=_commitment_digest(commitment),
        artifacts=(
            ArtifactRecord(
                artifact_id="codex-deliverable-manifest-private",
                path="private-logs/codex-deliverable-manifest.json",
                sha256=f"sha256:{artifact_digest.hexdigest()}",
                media_type="application/json",
                public=False,
                size_bytes=len(encoded),
            ),
        ),
        public_summary=summary,
    )


def _commitment_digest(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(record),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(encoded)
    return f"sha256:{digest.hexdigest()}"
