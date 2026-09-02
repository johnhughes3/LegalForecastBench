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
from legalforecast.multiharness.harness_vocab import (
    LOCAL_CLI_CONTAINER_EXECUTION,
    LOCAL_CLI_NATIVE_TOOLS_ENABLED,
    LOCAL_CLI_RESTRICTED_EGRESS,
    LOCAL_CLI_SERVER_SIDE_WEB_TOOLS_DISABLED,
)
from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    project_structured_stdout_deliverable,
)
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
        return AdapterPreparation(
            manifest=manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def container_spec(
        self, request: RunRequest, workspace: Path
    ) -> ContainerHarnessSpec:
        """Return the fully declared container topology for one row."""

        parent_env = self.environment()
        container_workspace = workspace / "container-workspace"
        container_workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        argv = self.local_manifest.invocation.render_argv(
            prompt=_solver_prompt(request.task),
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
        """Run one row in its container and project the canonical result."""

        self.prepare(request, workspace)
        spec = self.container_spec(request, workspace)
        result = self._execute(spec)
        deliverable, failure = self._deliverable(result, spec.workspace)
        return self._run_result(request, result, deliverable, failure)

    def _execute(self, spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        if self.runner is not None:
            return self.runner(spec)
        return run_container_harness(spec, backend=self.backend)

    def _deliverable(
        self, result: ContainerHarnessResult, workspace: Path
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
                    result.stdout_path.read_text(encoding="utf-8", errors="replace"),
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
    ) -> RunResult:
        manifest = self.manifest
        summary: dict[str, Any] = {
            "adapter_id": manifest.adapter_id,
            "adapter_version": manifest.adapter_version,
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
            "exit_code": result.exit_code,
            "failure_class": None if failure is None else failure.value,
            "harness": self.identity.registry_name,
            "model_key": request.model_key,
            "native_tools_enabled": True,
            "server_side_web_tools_disabled": True,
            "timed_out": result.timed_out,
        }
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
            public_summary=summary,
        )


def _solver_prompt(task: CanonicalTask) -> str:
    value = task.metadata.get("solver_prompt")
    if not isinstance(value, str) or not value.strip():
        raise ContainerCliAdapterError(
            "task metadata solver_prompt must be a non-empty string"
        )
    return value
