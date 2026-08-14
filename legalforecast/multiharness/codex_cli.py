"""Offline Codex CLI adapter: invocation plan, JSONL envelope, fail-closed results.

Invocation plans are rendered from B1's closed
``legalforecast.multiharness.local_cli_adapter_manifest.v1`` instance shipped
with this adapter. Shared execution types live in
``legalforecast.multiharness.local_cli_contracts``
(``LegalForecastBench-dm0g.4.4.26``). This adapter calls
``LocalCliExecutionService.execute(RunSpec)`` and never spawns ``codex``.
Tests inject ``FakeLocalCliExecutionService``; production injects B2's
contained runtime. Auth binding (``LegalForecastBench-dm0g.4.4.10``)
resolves ``fixture-none`` or ``published-api-key`` at plan time; credential
values stay with the contained execution service. Do not copy a parallel
contracts module onto this branch.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from legalforecast.multiharness.adapters import AdapterError, AdapterPreparation
from legalforecast.multiharness.auth_binding import (
    bind_adapter_auth_profile,
    public_auth_mode,
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
    seal_deliverable,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliExecutionService,
    LocalCliFailureClass,
    RunSpec,
    coerce_local_cli_failure_class,
    declared_local_cli_failure_classes,
    is_local_cli_sandbox_denial,
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
CODEX_FAILURE_CLASSES = declared_local_cli_failure_classes()
_ALLOWED_SUBCOMMANDS = frozenset({"exec"})
_ALLOWED_BARE_FLAGS = frozenset(
    {
        "-",
        "--ephemeral",
        "--ignore-rules",
        "--ignore-user-config",
        "--json",
        "--skip-git-repo-check",
        "--strict-config",
    }
)
_ALLOWED_VALUE_FLAGS = frozenset(
    {
        "--cd",
        "--color",
        "--model",
        "--output-last-message",
        "--sandbox",
        "-c",
    }
)
_INTERACTIVE_FLAGS = frozenset(
    {
        "--approve-for-me",
        "--ask-for-approval",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
    }
)
_FORBIDDEN_FLAGS = frozenset(
    {
        "--add-dir",
        "--last",
        "--local-provider",
        "--oss",
        "--profile",
        "--remote",
        "--search",
        *_INTERACTIVE_FLAGS,
    }
)
_REQUIRED_NONINTERACTIVE = (
    ("--color", "never"),
    ("--sandbox", CODEX_SANDBOX_MODE),
)
_REQUIRED_EVENTS = ("thread.started", "turn.started")
_ERROR_EVENT_TYPES = frozenset({"error", "turn.failed"})
_ALLOWED_EVENT_TYPES = frozenset(
    {
        "error",
        "item.completed",
        "item.started",
        "item.updated",
        "thread.started",
        "turn.completed",
        "turn.failed",
        "turn.started",
    }
)
_REFUSAL_MARKERS = (
    "i cannot help",
    "i can't help",
    "i must decline",
    "i must refuse",
    "i refuse",
    "i will not help",
    "i won't help",
    "i'm not able to help",
    "i am unable to help",
)
_AUTH_BASENAMES = frozenset({"auth.json", "auth.json.age"})
CODEX_LOCAL_CLI_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "adapters"
    / "codex-cli"
    / "local-cli-manifest.json"
)
_LAST_MESSAGE_RELATIVE_PATH = Path("codex-last-message.txt")
_REASONING_EFFORT_PREFIX = "model_reasoning_effort="


class CodexCliAdapterError(AdapterError):
    """Raised when the offline Codex CLI adapter cannot run safely."""


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
    auth_profile: str = FIXTURE_NONE

    def public_config(self) -> dict[str, str]:
        """Path-independent invocation identity for deliverable binding."""

        return {
            "approval_policy": CODEX_APPROVAL_POLICY,
            "auth_profile": self.auth_profile,
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


def build_codex_run_spec(
    request: RunRequest,
    plan: CodexCliInvocationPlan,
    workspace: Path,
) -> RunSpec:
    """Bind a planned exec invocation to a credential-free RunSpec."""

    if request.sandbox_policy.allowed_provider_env_vars:
        raise CodexCliAdapterError(
            "offline Codex CLI adapter must not receive provider environment grants"
        )
    return RunSpec(
        spec_id=request.request_id,
        argv=plan.argv,
        working_directory=workspace,
        environment={},
        timeout_seconds=plan.timeout_seconds,
        output_format="json",
        stdin_bytes=plan.stdin.encode("utf-8"),
    )


def _parser_execution_flags(receipt: ExecutionReceipt) -> tuple[int, bool, bool]:
    """Map a B2 receipt onto the JSONL parser's returncode/timeout/crash flags."""

    timed_out = receipt.status == "timeout"
    crashed = receipt.status == "failed" and not receipt.stdout.strip()
    if receipt.returncode is not None:
        returncode = receipt.returncode
    elif receipt.status != "succeeded":
        returncode = 1
    else:
        returncode = 0
    return returncode, timed_out, crashed


def _bind_envelope_to_receipt(
    receipt: ExecutionReceipt,
    envelope: CodexCliParsedEnvelope,
) -> CodexCliParsedEnvelope:
    """Honor B2 receipt status even when JSONL looks complete."""

    if envelope.failure_class is not None:
        return envelope
    if receipt.status == "timeout":
        return _failed_envelope(LocalCliFailureClass.TIMEOUT.value, envelope.events)
    if receipt.status == "failed":
        return _failed_envelope(LocalCliFailureClass.CRASH.value, envelope.events)
    return envelope


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
    if manifest.auth_profile_name != FIXTURE_NONE:
        raise CodexCliAdapterError(
            "offline Codex CLI adapter requires auth_profile_name fixture-none"
        )
    if FIXTURE_NONE not in manifest.supported_auth_profiles:
        raise CodexCliAdapterError("Codex CLI adapter must support fixture-none")
    if PUBLISHED_API_KEY not in manifest.supported_auth_profiles:
        raise CodexCliAdapterError("Codex CLI adapter must support published-api-key")
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
    auth_profile: object = FIXTURE_NONE,
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
    try:
        bound = bind_adapter_auth_profile(manifest, auth_profile)
    except AuthProfileError as exc:
        raise CodexCliAdapterError(str(exc)) from exc
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
    _reject_unallowlisted_argv(argv)
    _require_noninteractive_argv(argv)
    stdin = prompt if manifest.invocation.prompt_delivery == "stdin" else ""
    return CodexCliInvocationPlan(
        argv=argv,
        stdin=stdin,
        working_directory=workspace,
        last_message_path=workspace / _LAST_MESSAGE_RELATIVE_PATH,
        requested_model=model,
        reasoning_effort=effort,
        timeout_seconds=float(request.sandbox_policy.timeout_seconds),
        auth_profile=bound.profile_id,
    )


def declared_failure_classes() -> tuple[str, ...]:
    """Return the closed fail-closed taxonomy, including sandbox_denial."""

    return declared_local_cli_failure_classes()


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

    events, parse_failure = _load_events(stdout)
    if timed_out:
        return _failed_envelope("timeout", events)
    if crashed:
        return _failed_envelope("crash", events)
    if parse_failure is not None:
        return _failed_envelope(parse_failure, events)

    types = tuple(str(event.get("type", "")) for event in events)
    if any(event_type not in _ALLOWED_EVENT_TYPES for event_type in types):
        return _failed_envelope("schema_violation", events)
    if any(required not in types for required in _REQUIRED_EVENTS):
        return _failed_envelope("schema_violation", events)
    started_events = tuple(
        event for event in events if event.get("type") == "thread.started"
    )
    if events[0].get("type") != "thread.started" or len(started_events) != 1:
        return _failed_envelope("schema_violation", events)

    started: Mapping[str, Any] = started_events[0]
    served_model = _optional_str(started, "actual_model")
    requested_observed = _optional_str(started, "requested_model")
    if requested_observed is not None and requested_observed != requested_model_name:
        return _failed_envelope("schema_violation", events)
    if served_model is not None and served_model != requested_model_name:
        return _failed_envelope("schema_violation", events)

    turn_started_indexes = tuple(
        index for index, event_type in enumerate(types) if event_type == "turn.started"
    )
    turn_completed_indexes = tuple(
        index
        for index, event_type in enumerate(types)
        if event_type == "turn.completed"
    )
    if len(turn_started_indexes) != 1:
        return _failed_envelope("schema_violation", events)
    if len(turn_completed_indexes) > 1:
        return _failed_envelope("schema_violation", events)
    if turn_completed_indexes and turn_completed_indexes[0] < turn_started_indexes[0]:
        return _failed_envelope("schema_violation", events)

    last_message = last_message_file if last_message_file is not None else ""
    if not last_message.strip():
        last_message = _agent_message(events)
    usage = _usage(events)
    usage_tokens = usage if usage is not None else (0, 0)
    if _is_refusal(last_message):
        return _failed_envelope(
            "refusal",
            events,
            last_message=last_message,
            input_tokens=usage_tokens[0],
            output_tokens=usage_tokens[1],
        )

    if "turn.failed" in types or "error" in types:
        return _failed_envelope(_failure_from_errors(events, returncode), events)
    if returncode != 0:
        return _failed_envelope("crash", events)
    if "turn.completed" not in types or not last_message.strip():
        return _failed_envelope("schema_violation", events)

    usage = _usage(events)
    if usage is None:
        return _failed_envelope("schema_violation", events)
    return CodexCliParsedEnvelope(
        failure_class=None,
        last_message=last_message,
        events=events,
        input_tokens=usage[0],
        output_tokens=usage[1],
        served_model=served_model,
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
        auth_profile=FIXTURE_NONE,
        requested_model=request.model_key,
        served_model=None,
        failure_class=None,
        input_tokens=0,
        output_tokens=0,
        returncode=0,
        offline_protocol_fixture=True,
        deliverable_manifest_sha256=None,
        tool_call_count=0,
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

    execution_service: LocalCliExecutionService
    manifest: AdapterManifest = field(default_factory=codex_cli_manifest)
    local_cli_manifest: LocalCliAdapterManifest = field(
        default_factory=load_codex_local_cli_manifest
    )
    auth_profile: str = FIXTURE_NONE

    def __post_init__(self) -> None:
        try:
            bind_adapter_auth_profile(self.local_cli_manifest, self.auth_profile)
        except AuthProfileError as exc:
            raise CodexCliAdapterError(str(exc)) from exc

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
        try:
            bound = bind_adapter_auth_profile(
                self.local_cli_manifest, self.auth_profile
            )
            require_execution_service_profile(self.execution_service, bound.profile_id)
        except AuthProfileError as exc:
            raise CodexCliAdapterError(str(exc)) from exc
        prompt = _prompt_for(workspace, request)
        private_logs = workspace / "private-logs"
        _ensure_real_directory(private_logs, label="private-logs")
        plan = build_codex_invocation_plan(
            request,
            workspace,
            prompt=prompt,
            local_cli_manifest=self.local_cli_manifest,
            auth_profile=bound.profile_id,
        )
        _clear_prior_last_message(plan.last_message_path)
        spec = build_codex_run_spec(request, plan, workspace)
        receipt = self.execution_service.execute(spec)
        if receipt.spec_sha256 != spec.spec_sha256:
            raise CodexCliAdapterError("execution receipt does not bind the RunSpec")
        _require_real_directory(private_logs, label="private-logs")
        _write_private_text(private_logs / "codex-stdout.jsonl", receipt.stdout)
        _write_private_text(private_logs / "codex-stderr.log", receipt.stderr)
        last_message_file = _optional_existing_text(plan.last_message_path)
        returncode, timed_out, crashed = _parser_execution_flags(receipt)
        envelope = parse_codex_jsonl(
            receipt.stdout,
            requested_model_name=plan.requested_model,
            returncode=returncode,
            timed_out=timed_out,
            crashed=crashed,
            last_message_file=last_message_file,
        )
        envelope = _bind_envelope_to_receipt(receipt, envelope)
        if envelope.failure_class is not None:
            return _failed_result(
                request,
                envelope,
                returncode=returncode,
                auth_profile=plan.auth_profile,
            )
        return _successful_result(
            request, workspace, plan, envelope, returncode=returncode
        )


# contract-ratchet: allow non-persisted adapter-bundle identity for capabilities
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
    text = _optional_existing_text(prompt_path)
    if text is not None and text.strip():
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


def _reject_unallowlisted_argv(argv: Sequence[str]) -> None:
    """Refuse flags the offline Codex template does not name."""

    if len(argv) < 2 or argv[0] != CODEX_CLI_EXECUTABLE:
        raise CodexCliAdapterError("invocation executable must be the basename 'codex'")
    if argv[1] not in _ALLOWED_SUBCOMMANDS:
        raise CodexCliAdapterError("offline Codex CLI adapter requires exec_subcommand")
    index = 2
    while index < len(argv):
        token = argv[index]
        if token in _FORBIDDEN_FLAGS or token in _INTERACTIVE_FLAGS:
            raise CodexCliAdapterError(
                f"interactive or forbidden flag refused at plan time: {token}"
            )
        if token in _ALLOWED_BARE_FLAGS:
            index += 1
            continue
        if token in _ALLOWED_VALUE_FLAGS:
            if index + 1 >= len(argv):
                raise CodexCliAdapterError(f"flag {token} is missing a value")
            _reject_interactive_config_value(argv[index + 1])
            index += 2
            continue
        if token.startswith("-"):
            raise CodexCliAdapterError(
                f"un-allowlisted flag refused at plan time: {token}"
            )
        raise CodexCliAdapterError(
            f"un-allowlisted argv token refused at plan time: {token}"
        )


def _reject_interactive_config_value(token: str) -> None:
    if token.startswith("approval_policy=") and token != (
        f'approval_policy="{CODEX_APPROVAL_POLICY}"'
    ):
        raise CodexCliAdapterError(
            "interactive approval mode refused at plan time: "
            "approval_policy must be never"
        )
    if "auth.json" in token:
        raise CodexCliAdapterError("Codex CLI invocation must not reference auth.json")


def _require_noninteractive_argv(argv: Sequence[str]) -> None:
    """Refuse any argv that could prompt a hung eval run."""

    if argv[-1] != "-":
        raise CodexCliAdapterError("offline Codex exec must read the prompt from stdin")
    if "--json" not in argv:
        raise CodexCliAdapterError("offline Codex exec must request JSONL via --json")
    if "--ephemeral" not in argv:
        raise CodexCliAdapterError(
            "offline Codex exec must disable session persistence"
        )
    if f'approval_policy="{CODEX_APPROVAL_POLICY}"' not in argv:
        raise CodexCliAdapterError(
            "offline Codex exec must pin approval_policy to never"
        )
    for flag, expected in _REQUIRED_NONINTERACTIVE:
        try:
            index = argv.index(flag)
        except ValueError as exc:
            raise CodexCliAdapterError(f"invocation must set {flag}") from exc
        if index + 1 >= len(argv) or argv[index + 1] != expected:
            raise CodexCliAdapterError(f"invocation {flag} must be {expected}")
    for token in argv:
        if token in _INTERACTIVE_FLAGS:
            raise CodexCliAdapterError(
                f"interactive or approval flag refused at plan time: {token}"
            )


def _load_events(
    stdout: str,
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    events: list[Mapping[str, Any]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        try:
            decoded = json.loads(stripped)
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


def _usage(events: Sequence[Mapping[str, Any]]) -> tuple[int, int] | None:
    for event in reversed(events):
        if event.get("type") != "turn.completed":
            continue
        usage = _as_mapping(event.get("usage"))
        if usage is None:
            return None
        if "input_tokens" not in usage or "output_tokens" not in usage:
            return None
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if type(input_tokens) is not int or type(output_tokens) is not int:
            return None
        if input_tokens < 0 or output_tokens < 0:
            return None
        return input_tokens, output_tokens
    return None


def _is_refusal(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in _REFUSAL_MARKERS)


def _is_sandbox_denial(text: str) -> bool:
    return is_local_cli_sandbox_denial(text)


def _failure_from_errors(
    events: Sequence[Mapping[str, Any]],
    returncode: int,
) -> str:
    del returncode
    text = _error_event_text(events)
    if _is_sandbox_denial(text):
        return LocalCliFailureClass.SANDBOX_DENIAL.value
    if _is_refusal(text):
        return LocalCliFailureClass.REFUSAL.value
    return LocalCliFailureClass.CRASH.value


def _error_event_text(events: Sequence[Mapping[str, Any]]) -> str:
    return _event_text(
        tuple(event for event in events if event.get("type") in _ERROR_EVENT_TYPES)
    )


def _failed_envelope(
    failure_class: str,
    events: Sequence[Mapping[str, Any]],
    *,
    last_message: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> CodexCliParsedEnvelope:
    if failure_class not in CODEX_FAILURE_CLASSES:
        failure_class = coerce_local_cli_failure_class(failure_class).value
    return CodexCliParsedEnvelope(
        failure_class=failure_class,
        last_message=last_message,
        events=tuple(events),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
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
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        raise CodexCliAdapterError("workspace path must not be a symlink")
    if not stat.S_ISREG(info.st_mode):
        raise CodexCliAdapterError("workspace path must be a regular file")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    file_descriptor = os.open(path, flags)
    try:
        with os.fdopen(file_descriptor, encoding="utf-8") as handle:
            file_descriptor = -1
            return handle.read()
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


def _write_private_text(path: Path, payload: str) -> None:
    _reject_auth_path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(info.st_mode):
            raise CodexCliAdapterError("workspace path must not be a symlink")
        if not stat.S_ISREG(info.st_mode):
            raise CodexCliAdapterError("workspace path must be a regular file")
        path.unlink()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    file_descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            file_descriptor = -1
            handle.write(payload)
            handle.flush()
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)


def _require_real_directory(path: Path, *, label: str) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CodexCliAdapterError(f"{label} must exist") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise CodexCliAdapterError(f"{label} must be a real directory")


def _ensure_real_directory(path: Path, *, label: str, mode: int = 0o700) -> None:
    if path.is_symlink():
        raise CodexCliAdapterError(f"{label} must be a real directory")
    path.mkdir(mode=mode, parents=True, exist_ok=True)
    _require_real_directory(path, label=label)
    path.chmod(mode)


def _command_execution_count(events: Sequence[Mapping[str, Any]]) -> int:
    completed: set[str] = set()
    anonymous = 0
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = _as_mapping(event.get("item"))
        if item is None or item.get("type") != "command_execution":
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            completed.add(item_id)
            continue
        anonymous += 1
    return len(completed) + anonymous


def _clear_prior_last_message(path: Path) -> None:
    _reject_auth_path(path)
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.exists():
        raise CodexCliAdapterError("Codex last-message path must be a regular file")


def _remove_prior_sealed_root(path: Path) -> None:
    """Remove a previous sealed tree so ``seal_deliverable`` can create a fresh root.

    Sealed directories are 0o555, so write bits must be restored on each directory
    before children can be unlinked. Do not follow symlinks out of the workspace.
    """

    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.is_dir():
        return
    directories = [path]
    for child in path.rglob("*"):
        if child.is_dir() and not child.is_symlink():
            directories.append(child)
    for directory in directories:
        directory.chmod(0o700)
    shutil.rmtree(path)


def _public_summary(
    request: RunRequest,
    *,
    auth_mode: str,
    auth_profile: str,
    requested_model: str,
    served_model: str | None,
    failure_class: str | None,
    input_tokens: int,
    output_tokens: int,
    returncode: int,
    offline_protocol_fixture: bool,
    deliverable_manifest_sha256: str | None,
    tool_call_count: int,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "adapter_id": CODEX_CLI_ADAPTER_ID,
        "adapter_bundle_sha256": adapter_bundle_sha256(),
        "adapter_version": CODEX_CLI_ADAPTER_VERSION,
        "approval_policy": CODEX_APPROVAL_POLICY,
        "auth_mode": auth_mode,
        "auth_profile": require_auth_profile_id(auth_profile),
        "executable": CODEX_CLI_EXECUTABLE,
        "input_tokens": input_tokens,
        "model_key": request.model_key,
        "offline_protocol_fixture": offline_protocol_fixture,
        "output_tokens": output_tokens,
        "provider": "openai",
        "requested_model": requested_model,
        "returncode": returncode,
        "sandbox_mode": CODEX_SANDBOX_MODE,
        "sandbox_policy_id": request.sandbox_policy.policy_id,
        "subscription_login_claimed": False,
        "task_id": request.task.task_id,
        "tool_call_count": tool_call_count,
        "total_tokens": input_tokens + output_tokens,
    }
    if served_model is not None:
        summary["served_model"] = served_model
    if failure_class is not None:
        summary["failure_class"] = failure_class
        summary["failure_detail"] = (
            f"{failure_class} task_id={request.task.task_id} returncode={returncode}"
        )
    if deliverable_manifest_sha256 is not None:
        summary["deliverable_manifest_sha256"] = deliverable_manifest_sha256
    validate_public_record(summary, "codex_cli.public_summary")
    return summary


def _failed_result(
    request: RunRequest,
    envelope: CodexCliParsedEnvelope,
    *,
    returncode: int,
    auth_profile: str,
) -> RunResult:
    profile_id = require_auth_profile_id(auth_profile)
    summary = _public_summary(
        request,
        auth_mode=public_auth_mode(profile_id, fixture_mode="none-offline-cli-adapter"),
        auth_profile=profile_id,
        requested_model=requested_model(request.model_key),
        served_model=envelope.served_model,
        failure_class=envelope.failure_class,
        input_tokens=envelope.input_tokens,
        output_tokens=envelope.output_tokens,
        returncode=returncode,
        offline_protocol_fixture=False,
        deliverable_manifest_sha256=None,
        tool_call_count=_command_execution_count(envelope.events),
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
    *,
    returncode: int,
) -> RunResult:
    source_root = workspace / "codex-output"
    _ensure_real_directory(source_root, label="codex-output")
    submission = source_root / "submission.md"
    payload = (
        envelope.last_message
        if envelope.last_message.endswith("\n")
        else (f"{envelope.last_message}\n")
    )
    _write_private_text(submission, payload)
    sealed_root = workspace / "sealed-deliverable"
    _remove_prior_sealed_root(sealed_root)
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
    encoded_text = (
        json.dumps(manifest.to_record(), indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )
    _write_private_text(manifest_path, encoded_text)
    encoded = encoded_text.encode("utf-8")
    artifact_digest = hashlib.sha256()
    artifact_digest.update(encoded)
    summary = _public_summary(
        request,
        auth_mode=public_auth_mode(
            plan.auth_profile, fixture_mode="none-offline-cli-adapter"
        ),
        auth_profile=plan.auth_profile,
        requested_model=plan.requested_model,
        served_model=envelope.served_model,
        failure_class=None,
        input_tokens=envelope.input_tokens,
        output_tokens=envelope.output_tokens,
        returncode=returncode,
        offline_protocol_fixture=False,
        deliverable_manifest_sha256=manifest.manifest_sha256,
        tool_call_count=_command_execution_count(envelope.events),
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
