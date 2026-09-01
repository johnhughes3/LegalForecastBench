"""Manifest-driven HarnessAdapter for the containerized, tools-on lane.

Everything provider-specific stays in the local-CLI adapter manifest: argv is
rendered from ``invocation.argv_template``, the answer is projected with
``task_projection``, and the image is the manifest's own pinned digest.  This
module knows no harness names beyond the identity table it is handed, which is
the point -- the clean-native adapters spent ~2,700 lines on per-harness glue,
and cloning that for five more CLIs is how a lane stops being maintainable.

Three postures are enforced before a run, because each one is a way to publish
a number that answers a different question than the one asked:

* ``native_tools_enabled`` -- strip the tools and this lane measures the bare
  API, which is the main benchmark's job.
* ``server_side_web_tools_disabled`` -- a provider-executed ``web_search``
  runs on the provider's infrastructure, downstream of every container egress
  rule, and these are real federal cases whose outcomes are one search away.
* ``container_execution`` + ``restricted_egress`` -- the run is the image, not
  whatever happened to be on the operator's PATH, and it can reach the
  provider and nothing else.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from legalforecast.contracts import (
    ARTIFACT_PREFIXED_SHA256_V1,
    MULTIHARNESS_CONTAINER_HARNESS_RESULT_V1,
)
from legalforecast.multiharness.adapters import AdapterError, AdapterPreparation
from legalforecast.multiharness.auth_binding import public_auth_mode
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
    run_container_harness,
)
from legalforecast.multiharness.container_harness.plan import WORKSPACE_TARGET
from legalforecast.multiharness.harness_lane.auth import (
    container_child_env,
    container_credentials,
    resolve_lane_auth_profile,
)
from legalforecast.multiharness.harness_lane.harnesses import ContainerHarnessIdentity
from legalforecast.multiharness.harness_lane.lab_workspace import (
    stage_projected_lab_task,
)
from legalforecast.multiharness.harness_lane.release_evidence import (
    CONTAINER_EXECUTION_BACKEND,
    CONTAINER_HARNESS_TRACK,
    ContainerReleaseEvidence,
    read_solver_input_prompt,
    write_container_release_evidence,
)
from legalforecast.multiharness.harness_lane.tool_accounting import (
    HarnessToolUse,
    harness_tool_use,
)
from legalforecast.multiharness.harness_lane.usage_accounting import (
    HarnessUsage,
    harness_usage,
)
from legalforecast.multiharness.harness_vocab import (
    LOCAL_CLI_CONTAINER_EXECUTION,
    LOCAL_CLI_NATIVE_TOOLS_ENABLED,
    LOCAL_CLI_PROJECTED_TASK_INSTRUCTIONS,
    LOCAL_CLI_RESTRICTED_EGRESS,
    LOCAL_CLI_SERVER_SIDE_WEB_TOOLS_DISABLED,
    LOCAL_CLI_SOLVER_INPUT_PROMPT,
)
from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    project_structured_stdout_deliverable,
)
from legalforecast.multiharness.release_harness import require_release_metadata_str
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    CanonicalTask,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

CONTAINER_WRAPPER_COMMAND: Final[tuple[str, ...]] = (
    "legalforecast.multiharness.harness_lane.adapter:ContainerCliAdapter",
)
REQUIRED_LANE_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        LOCAL_CLI_CONTAINER_EXECUTION,
        LOCAL_CLI_NATIVE_TOOLS_ENABLED,
        LOCAL_CLI_RESTRICTED_EGRESS,
        LOCAL_CLI_SERVER_SIDE_WEB_TOOLS_DISABLED,
    }
)
DEFAULT_ALLOWED_PORTS: Final[tuple[int, ...]] = (443,)
HARVEY_LAB_FAMILY: Final = "harvey_lab"

HarnessRunner = Callable[[ContainerHarnessSpec], ContainerHarnessResult]


class ContainerCliAdapterError(AdapterError, ValueError):
    """Raised when a containerized tools-on run cannot be set up or projected.

    Also a ``ValueError`` so a bad manifest reaches an operator as
    ``legalforecast: <message>`` and exit 2 rather than as a traceback:
    :func:`legalforecast.cli.main` maps ``ValueError`` to a clean refusal, and
    ``AdapterError`` alone is a ``RuntimeError``, which it re-raises.
    """


def require_lane_manifest(
    manifest: LocalCliAdapterManifest, identity: ContainerHarnessIdentity
) -> str:
    """Return the pinned image, or refuse a manifest that is not this lane's.

    A clean-native manifest registered under a container family name would run
    the wrong program under the right label, so the posture tokens and the
    executable identity are both checked before anything is constructed.
    """

    missing = REQUIRED_LANE_CAPABILITIES.difference(manifest.capabilities)
    if missing:
        formatted = ", ".join(sorted(missing))
        raise ContainerCliAdapterError(
            f"{manifest.manifest_id} is not a containerized tools-on manifest; "
            f"missing capabilities: {formatted}"
        )
    if manifest.executable.basename != identity.executable_basename:
        raise ContainerCliAdapterError(
            f"{identity.registry_name} runs {identity.executable_basename!r}, but "
            f"{manifest.manifest_id} pins {manifest.executable.basename!r}"
        )
    image = manifest.executable.container_image_digest
    if image is None:  # pragma: no cover - container_execution guarantees this
        raise ContainerCliAdapterError(
            f"{manifest.manifest_id} declares container_execution without "
            "executable.container_image_digest"
        )
    if manifest.invocation.prompt_delivery != "argv_placeholder":
        raise ContainerCliAdapterError(
            f"{manifest.manifest_id} delivers the prompt by "
            f"{manifest.invocation.prompt_delivery!r}; the container plan has no "
            "stdin channel, so this lane needs an {prompt} argv placeholder"
        )
    if manifest.invocation.schema_enforcement != "none":
        raise ContainerCliAdapterError(
            f"{manifest.manifest_id} declares schema_enforcement "
            f"{manifest.invocation.schema_enforcement!r}; this lane renders argv "
            "without an output schema, so only 'none' is supported today"
        )
    return image


@dataclass(frozen=True, slots=True)
class ContainerCliAdapter:
    """Run one agentic CLI in a container with its own local tools live."""

    identity: ContainerHarnessIdentity
    local_manifest: LocalCliAdapterManifest
    auth_profile: str = FIXTURE_NONE
    allow_hosts: tuple[str, ...] = ()
    allow_subdomains: tuple[str, ...] = ()
    allow_ports: tuple[int, ...] = DEFAULT_ALLOWED_PORTS
    parent_env: Mapping[str, str] | None = None
    lab_projection_root: Path | None = None
    backend: str = "docker"
    runner: HarnessRunner | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        require_lane_manifest(self.local_manifest, self.identity)
        resolve_lane_auth_profile(self.auth_profile, self.local_manifest)

    @property
    def image(self) -> str:
        """Return the manifest's pinned container image digest."""

        return require_lane_manifest(self.local_manifest, self.identity)

    @property
    def manifest(self) -> AdapterManifest:
        """Return the public wrapper identity, not the target CLI argv."""

        return self.local_manifest.to_adapter_manifest(
            command=CONTAINER_WRAPPER_COMMAND
        )

    def environment(self) -> Mapping[str, str]:
        """Return the operator environment the login is proved against."""

        return os.environ if self.parent_env is None else self.parent_env

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        """Return the manifest's sealed capability advertisement."""

        workspace.mkdir(parents=True, exist_ok=True)
        return self.local_manifest.to_adapter_capabilities()

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        """Validate one row against this adapter before anything is launched."""

        workspace.mkdir(parents=True, exist_ok=True)
        manifest = self.manifest
        capabilities = self.capabilities(workspace)
        if request.adapter.adapter_id != manifest.adapter_id:
            raise ContainerCliAdapterError("run request adapter ID does not match")
        if request.adapter.adapter_version != manifest.adapter_version:
            raise ContainerCliAdapterError("run request adapter version does not match")
        if request.task.family not in capabilities.supported_families:
            raise ContainerCliAdapterError(
                f"adapter does not support task family: {request.task.family}"
            )
        if request.task.scoring_mode not in capabilities.supported_scoring_modes:
            raise ContainerCliAdapterError(
                f"adapter does not support scoring mode: {request.task.scoring_mode}"
            )
        self._require_prompt_source(request)
        return AdapterPreparation(
            manifest=manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def _require_prompt_source(self, request: RunRequest) -> None:
        """Refuse a manifest whose declared prompt source this row cannot use.

        A projected LAB task has no private solver-input store, and an LFB row
        must never fall back to task metadata for its prompt.  Each family has
        exactly one honest source, so a manifest that names the other one is a
        mislabeled run rather than a variant configuration.
        """

        declared = self.local_manifest.task_projection.prompt_source
        expected = (
            LOCAL_CLI_PROJECTED_TASK_INSTRUCTIONS
            if request.task.family == HARVEY_LAB_FAMILY
            else LOCAL_CLI_SOLVER_INPUT_PROMPT
        )
        if declared != expected:
            raise ContainerCliAdapterError(
                f"{self.local_manifest.manifest_id} declares prompt_source "
                f"{declared!r}, but a {request.task.family!r} row takes its "
                f"prompt from {expected!r}"
            )

    def container_spec(
        self,
        request: RunRequest,
        workspace: Path,
        *,
        prompt: str | None = None,
    ) -> ContainerHarnessSpec:
        """Return the fully declared container topology for one row.

        ``prompt`` is the authenticated task text when the caller already holds
        it -- from the private solver-input tree, or from a projected LAB
        task's instructions.  Without it the task's own ``solver_prompt``
        metadata is used, which is how the adapter-level probes drive a spec.
        """

        parent_env = self.environment()
        container_workspace = workspace / "container-workspace"
        container_workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        argv = self.local_manifest.invocation.render_argv(
            prompt=prompt if prompt is not None else _metadata_prompt(request.task),
            model=request.model_key,
            workspace=WORKSPACE_TARGET,
        )
        return ContainerHarnessSpec(
            run_id=self.run_id(request),
            image=self.image,
            harness_argv=argv,
            workspace=container_workspace,
            log_root=workspace / "container-logs",
            allow_hosts=self.allow_hosts,
            allow_subdomains=self.allow_subdomains,
            allow_ports=self.allow_ports,
            credentials=container_credentials(
                self.identity, self.auth_profile, parent_env
            ),
            environment=container_child_env(self.identity, self.auth_profile),
            timeout_seconds=self.local_manifest.timeout_retry.timeout_seconds,
        )

    def run_id(self, request: RunRequest) -> str:
        """Return a Docker-safe per-row run id that still names the harness."""

        digest = hashlib.sha256(request.request_id.encode("utf-8")).hexdigest()
        return f"{self.identity.executable_basename}-{digest[:10]}"

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        """Run one row whose prompt does not come from a solver-input store."""

        self.prepare(request, workspace)
        return self._execute_row(
            request,
            workspace,
            prompt=self._unauthenticated_prompt(request, workspace),
            prompt_sha256=None,
        )

    def run_with_solver_input(
        self,
        request: RunRequest,
        workspace: Path,
        solver_input_root: Path,
    ) -> RunResult:
        """Run one row on the exact private prompt bytes and bind the evidence.

        This is what makes the lane scoreable.  ``release_harness`` will only
        project an LFB score row from a result that carries a private forecast
        output plus a transcript binding request, packet, prompt and response,
        and it re-reads and re-hashes both before it believes any of it.  The
        prompt itself never enters the task record or the published summary --
        only its digest does.
        """

        self.prepare(request, workspace)
        prompt_sha256 = require_release_metadata_str(
            request.task.metadata, "prompt_sha256"
        )
        return self._execute_row(
            request,
            workspace,
            prompt=read_solver_input_prompt(solver_input_root, prompt_sha256),
            prompt_sha256=prompt_sha256,
        )

    def _execute_row(
        self,
        request: RunRequest,
        workspace: Path,
        *,
        prompt: str,
        prompt_sha256: str | None,
    ) -> RunResult:
        spec = self.container_spec(request, workspace, prompt=prompt)
        result = self._execute(spec)
        stdout = _read_stdout(result)
        deliverable, failure = self._deliverable(result, spec.workspace, stdout)
        tools = harness_tool_use(self.identity.executable_basename, stdout)
        usage = harness_usage(self.identity.executable_basename, stdout)
        evidence = (
            write_container_release_evidence(
                request=request,
                workspace=workspace,
                deliverable=deliverable,
                prompt_sha256=prompt_sha256,
            )
            if prompt_sha256 is not None and deliverable is not None
            else None
        )
        return self._run_result(
            request, result, deliverable, failure, tools, usage, evidence
        )

    def _unauthenticated_prompt(self, request: RunRequest, workspace: Path) -> str:
        """Return the prompt for a task with no private solver-input store."""

        if request.task.family == HARVEY_LAB_FAMILY:
            if self.lab_projection_root is None:
                raise ContainerCliAdapterError(
                    f"{request.task.task_id} is a projected Harvey LAB task; "
                    "this adapter needs the projection root its documents live "
                    "in (--projected-root)"
                )
            return stage_projected_lab_task(
                request.task,
                projection_root=self.lab_projection_root,
                destination=workspace / "container-workspace",
            ).prompt
        return _metadata_prompt(request.task)

    def _execute(self, spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        if self.runner is not None:
            return self.runner(spec)
        return run_container_harness(spec, backend=self.backend)

    def _deliverable(
        self, result: ContainerHarnessResult, workspace: Path, stdout: str
    ) -> tuple[str | None, LocalCliFailureClass | None]:
        if result.timed_out:
            return None, LocalCliFailureClass.TIMEOUT
        if result.exit_code != 0:
            return None, LocalCliFailureClass.CRASH
        projection = self.local_manifest.task_projection
        try:
            if projection.deliverable_source == "workspace_relative_file":
                relative = projection.deliverable_relative_path
                if relative is None:  # pragma: no cover - manifest guarantees this
                    raise ContainerCliAdapterError("deliverable_relative_path is unset")
                text = (workspace / relative).read_text(encoding="utf-8")
            else:
                text = project_structured_stdout_deliverable(
                    stdout,
                    output_format=self.local_manifest.invocation.output_format,
                    projection=projection,
                )
        except (OSError, ValueError):
            # from-None is deliberate: the message can embed a host path or a
            # transcript fragment, and this result is published.
            return None, LocalCliFailureClass.SCHEMA_VIOLATION
        if not text.strip():
            return None, LocalCliFailureClass.SCHEMA_VIOLATION
        return text, None

    def _run_result(
        self,
        request: RunRequest,
        result: ContainerHarnessResult,
        deliverable: str | None,
        failure: LocalCliFailureClass | None,
        tools: HarnessToolUse,
        usage: HarnessUsage,
        evidence: ContainerReleaseEvidence | None,
    ) -> RunResult:
        manifest = self.manifest
        summary: dict[str, Any] = {
            "adapter_id": manifest.adapter_id,
            "adapter_version": manifest.adapter_version,
            "allowed_tools": list(tools.tools),
            "auth_mode": public_auth_mode(
                self.auth_profile, fixture_mode="none-offline"
            ),
            "container_image_digest": self.image,
            "container_image_id": result.image_id,
            "duration_seconds": result.duration_seconds,
            "egress_allowed_hosts": list(result.allowed_hosts),
            "egress_allowlist": dict(result.allowlist),
            "egress_refused": [dict(record) for record in result.refused],
            "executable": self.identity.executable_basename,
            "execution_backend": CONTAINER_EXECUTION_BACKEND,
            "exit_code": result.exit_code,
            "failure_class": None if failure is None else failure.value,
            "harness": self.identity.registry_name,
            "harness_track": CONTAINER_HARNESS_TRACK,
            "model_key": request.model_key,
            "native_tools_enabled": True,
            "server_side_web_tools_disabled": True,
            "timed_out": result.timed_out,
            "tool_call_count": tools.call_count,
            "tool_policy": tools.policy,
            "tool_use_reporting": tools.reporting,
        }
        summary.update(
            usage.summary_fields(
                cost_basis=self.local_manifest.usage_reporting.cost_basis
            )
        )
        if evidence is not None:
            summary["transcript_sha256"] = evidence.transcript_sha256
        validate_public_record(summary, "container_cli.public_summary")
        commitment = {
            "deliverable_sha256": None
            if deliverable is None
            else hashlib.sha256(deliverable.encode("utf-8")).hexdigest(),
            "public_summary": summary,
            "request_sha256": request.request_sha256,
        }
        return RunResult(
            result_id=f"{request.request_id}:{manifest.adapter_id}",
            request_id=request.request_id,
            status="failed" if failure is not None else "succeeded",
            result_sha256=str(
                ARTIFACT_PREFIXED_SHA256_V1.commit(
                    commitment, domain=MULTIHARNESS_CONTAINER_HARNESS_RESULT_V1
                ).digest
            ),
            artifacts=() if evidence is None else evidence.artifacts,
            public_summary=summary,
        )


def _read_stdout(result: ContainerHarnessResult) -> str:
    try:
        return result.stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        # A missing stdout file is a failed run, not a crash of the projector;
        # ``_deliverable`` turns the empty transcript into a schema violation.
        return ""


def _metadata_prompt(task: CanonicalTask) -> str:
    value = task.metadata.get("solver_prompt")
    if not isinstance(value, str) or not value.strip():
        raise ContainerCliAdapterError(
            f"{task.task_id} carries no solver_prompt metadata; an LFB task's "
            "prompt comes from the private solver-input store, so pass "
            "--solver-input-root rather than putting the prompt in the task"
        )
    return value
