"""Deterministic multi-harness run orchestration."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import legalforecast.multiharness.release_harness as release_harness
from legalforecast._json_io import (
    read_json_object_safe,
    write_json_object_safe,
    write_jsonl_objects_safe,
)
from legalforecast.contracts import FORECAST_RELEASE_V1
from legalforecast.evals.inspect_task import HarnessSolver
from legalforecast.evals.packet_builder import ModelPacket
from legalforecast.immutable_io import (
    ImmutableIOError,
    ensure_private_directory,
    read_single_link_file,
    write_file_replace_safe,
)
from legalforecast.multiharness.adapters import HarnessAdapter, LiveToolAdapter
from legalforecast.multiharness.artifacts import AdapterRunResult
from legalforecast.multiharness.auth_profiles import (
    PUBLISHED_API_KEY,
    AuthProfileError,
    require_infisical_environment,
)
from legalforecast.multiharness.command_adapter import (
    CommandAdapter,
    CommandAdapterCancelled,
)
from legalforecast.multiharness.container_execution import container_execution_record
from legalforecast.multiharness.container_runtime import (
    ContainerRuntimeError,
    ContainerToolSession,
    validate_container_resume,
)
from legalforecast.multiharness.host_environment import (
    build_container_backend_environment,
    require_local_pinned_container_image,
    require_provider_environment_values,
    require_rootless_container_daemon,
)
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.process_containment import (
    preflight_process_containment,
)
from legalforecast.multiharness.release_adapters import (
    NEUTRAL_FIXTURE_ADAPTER_ID,
    NativeReleaseAdapter,
    NeutralApiFixtureAdapter,
)
from legalforecast.multiharness.run_progress import (
    CLAIM_PARTIAL,
    IdentityBinding,
    ResumeRefusedError,
    RunProgressJournal,
    bind_run_identity,
    is_partial_label,
    load_progress_journal,
    refuse_resume_identity_drift,
    signal_boundary,
    write_progress_journal,
)
from legalforecast.multiharness.sandbox import (
    PROVIDER_EGRESS_HOST_ONLY,
    build_container_plan,
    live_container_public_plan,
    resolve_container_backend,
    validate_live_container_policy,
)
from legalforecast.multiharness.selection import SelectionResult, TaskSelection
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    PreparedSolverInput,
    SolverInputEntry,
    SolverInputStore,
    prepare_solver_input,
)
from legalforecast.multiharness.spec import (
    POSIX_PROCESS_GROUP_CONTAINMENT,
    RUN_COMPATIBILITY_SCHEMA_VERSION,
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    CanonicalTask,
    RunManifest,
    RunRequest,
    RunResult,
    SandboxPolicy,
    TaskIndex,
)
from legalforecast.multiharness.validation import (
    validate_no_secret_values,
    validate_public_record,
)

INCOMPLETE_RUN_POLICIES = frozenset({"record_failure", "fail_fast"})
CONTAINER_EXECUTION_MODES = frozenset({"plan_only", "live_tools"})
_FORECAST_RELEASE_SCHEMA_VERSION = str(FORECAST_RELEASE_V1)
_OPENAI_RELEASE_ADAPTER_ID = "openai-responses-baseline"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """One adapter/model route in a multi-harness run matrix."""

    model_key: str
    adapter_id: str | None = None
    lfb_packet: ModelPacket | None = None
    lfb_solver: HarnessSolver | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.model_key, "model_key")
        if self.adapter_id is not None:
            _require_non_empty(self.adapter_id, "adapter_id")
        if (self.lfb_packet is None) != (self.lfb_solver is None):
            raise ValueError("lfb_packet and lfb_solver must be provided together")

    def to_record(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "model_key": self.model_key,
            "lfb_fixture": self.lfb_packet is not None,
        }


@dataclass(frozen=True, slots=True)
class MultiHarnessRunConfig:
    """Configuration for one deterministic multi-harness run."""

    task_index: TaskIndex
    adapters: tuple[HarnessAdapter, ...]
    model_configs: tuple[ModelConfig, ...]
    sandbox_policy: SandboxPolicy
    output_dir: Path
    selection: TaskSelection = field(default_factory=TaskSelection.full)
    run_id: str = "multiharness-run"
    max_parallelism: int = 1
    resume: bool = False
    incomplete_run_policy: str = "record_failure"
    container_execution: str = "plan_only"
    solver_inputs: SolverInputStore | None = None

    def __post_init__(self) -> None:
        if not self.adapters:
            raise ValueError("adapters must not be empty")
        if not self.model_configs:
            raise ValueError("model_configs must not be empty")
        _require_non_empty(self.run_id, "run_id")
        if self.max_parallelism <= 0:
            raise ValueError("max_parallelism must be positive")
        if self.incomplete_run_policy not in INCOMPLETE_RUN_POLICIES:
            allowed = ", ".join(sorted(INCOMPLETE_RUN_POLICIES))
            raise ValueError(f"incomplete_run_policy must be one of: {allowed}")
        if self.container_execution not in CONTAINER_EXECUTION_MODES:
            allowed = ", ".join(sorted(CONTAINER_EXECUTION_MODES))
            raise ValueError(f"container_execution must be one of: {allowed}")
        if self.container_execution == "live_tools" and self.solver_inputs is None:
            raise ValueError(
                "live tool execution requires a private solver-input store"
            )
        if (
            self.solver_inputs is not None
            and self.solver_inputs.index.task_index_sha256
            != self.task_index.index_sha256
        ):
            raise ValueError("solver-input index does not match the task index")
        if self.solver_inputs is not None:
            expected_tasks = {
                task.task_id: task.task_sha256 for task in self.task_index.tasks
            }
            solver_tasks = {
                entry.task_id: entry.task_sha256
                for entry in self.solver_inputs.index.entries
            }
            if solver_tasks != expected_tasks:
                raise ValueError(
                    "solver-input entries do not exactly match the task index"
                )
        validate_provider_environment_scope(
            sandbox_policy=self.sandbox_policy,
            adapter_count=len(self.adapters),
            model_count=len(self.model_configs),
        )

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "task_index": {
                "index_id": self.task_index.index_id,
                "index_sha256": self.task_index.index_sha256,
                "selection_namespace": self.task_index.selection_namespace,
            },
            "selection": self.selection.to_record(),
            "adapters": [
                adapter.manifest.to_record()
                for adapter in _ordered_adapters(self.adapters)
            ],
            "model_configs": [
                model.to_record()
                for model in _ordered_model_configs(self.model_configs)
            ],
            "sandbox_policy": self.sandbox_policy.to_record(),
            "run_id": self.run_id,
            "max_parallelism": self.max_parallelism,
            "incomplete_run_policy": self.incomplete_run_policy,
            "container_execution": self.container_execution,
        }
        if self.solver_inputs is not None:
            record["solver_input_index_sha256"] = self.solver_inputs.index.index_sha256
        return record


@dataclass(frozen=True, slots=True)
class MultiHarnessRunRow:
    """One executed or resumed row in a multi-harness matrix."""

    row_id: str
    task: CanonicalTask
    adapter_manifest: AdapterManifest
    model_config: ModelConfig
    request: RunRequest
    result: RunResult
    workspace: Path
    resumed: bool = False
    lfb_record: Mapping[str, Any] | None = None
    container_execution: str = "plan_only"
    container_receipt_sha256: str | None = None
    selection_label: str = "full"
    coverage_kind: str = "full"

    def to_record(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "task_id": self.task.task_id,
            "family": self.task.family,
            "scoring_mode": self.task.scoring_mode,
            "adapter_id": self.adapter_manifest.adapter_id,
            "adapter_version": self.adapter_manifest.adapter_version,
            "model_key": self.model_config.model_key,
            "request_id": self.request.request_id,
            "request_sha256": self.request.request_sha256,
            "result_id": self.result.result_id,
            "status": self.result.status,
            "workspace": self.workspace.as_posix(),
            "resumed": self.resumed,
            "selection_label": self.selection_label,
            "coverage_kind": self.coverage_kind,
            "container_execution": container_execution_record(
                configured_mode=self.container_execution,
                receipt_sha256=self.container_receipt_sha256,
            ),
        }


@dataclass(frozen=True, slots=True)
class MultiHarnessRun:
    """Completed multi-harness run artifacts."""

    manifest: RunManifest
    selection: SelectionResult
    rows: tuple[MultiHarnessRunRow, ...]
    output_dir: Path
    interrupted: bool = False


@dataclass(frozen=True, slots=True)
class _RowPlan:
    row_id: str
    task: CanonicalTask
    adapter: HarnessAdapter
    capabilities: AdapterCapabilities
    model_config: ModelConfig
    request: RunRequest
    workspace: Path


def run_multi_harness(config: MultiHarnessRunConfig) -> MultiHarnessRun:
    """Execute a deterministic multi-harness run and write run artifacts."""

    with signal_boundary():
        return _MultiHarnessRunner(config).run()


def _ensure_private_run_directory(path: Path) -> Path:
    try:
        return ensure_private_directory(path)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc


def validate_provider_environment_scope(
    *,
    sandbox_policy: SandboxPolicy,
    adapter_count: int,
    model_count: int,
) -> None:
    """Fail closed until credential grants can be scoped to individual rows."""

    if not sandbox_policy.allowed_provider_env_vars:
        return
    if sandbox_policy.network_policy != PROVIDER_EGRESS_HOST_ONLY:
        raise ValueError(
            "allowed_provider_env_vars requires provider egress "
            "(--allow-provider-egress in the CLI)"
        )
    if adapter_count != 1 or model_count != 1:
        raise ValueError(
            "allowed_provider_env_vars currently supports one adapter and one model "
            "per run; use separate runs until row-scoped credential grants exist"
        )


def _validate_live_release_adapter_routes(
    *,
    container_execution: str,
    tasks: Sequence[CanonicalTask],
    adapters: Sequence[HarnessAdapter],
    model_configs: Sequence[ModelConfig],
) -> None:
    if container_execution != "live_tools" or not any(
        task.metadata.get("release_schema_version") == _FORECAST_RELEASE_SCHEMA_VERSION
        for task in tasks
    ):
        return
    routed_adapter_ids = {
        adapter.manifest.adapter_id
        for adapter in adapters
        if any(
            model.adapter_id in {None, adapter.manifest.adapter_id}
            for model in model_configs
        )
    }
    unsupported = sorted(routed_adapter_ids.difference({_OPENAI_RELEASE_ADAPTER_ID}))
    if unsupported:
        raise ValueError(
            "live forecast-release.v1 execution supports only "
            f"{_OPENAI_RELEASE_ADAPTER_ID}; unsupported adapter route(s): "
            + ", ".join(unsupported)
        )


def _validate_known_release_adapter_routes(
    *,
    tasks: Sequence[CanonicalTask],
    adapters: Sequence[HarnessAdapter],
    model_configs: Sequence[ModelConfig],
) -> None:
    """Reject known release routes before creating any run artifacts."""

    if not any(
        task.metadata.get("release_schema_version") == _FORECAST_RELEASE_SCHEMA_VERSION
        for task in tasks
    ):
        return
    if not any(
        isinstance(adapter, LfbNativeAdapter)
        and any(
            model.adapter_id in {None, adapter.manifest.adapter_id}
            for model in model_configs
        )
        for adapter in adapters
    ):
        return
    raise ValueError(
        "LfbNativeAdapter does not support release-backed tasks; "
        "use an authenticated release adapter"
    )


def _prepare_incomplete_release_retry(plan: _RowPlan) -> None:
    """Remove only known adapter-owned release files before a resumed rerun."""

    adapter = plan.adapter
    adapter_id = adapter.manifest.adapter_id
    if isinstance(adapter, NeutralApiFixtureAdapter) or adapter_id == (
        NEUTRAL_FIXTURE_ADAPTER_ID
    ):
        relative_paths = (
            "private-logs/release-forecast-output.json",
            "private-logs/neutral-api-transcript.json",
        )
    elif isinstance(adapter, NativeReleaseAdapter):
        relative_paths = (
            "private-logs/release-forecast-output.json",
            "private-logs/release-harness-transcript.json",
        )
    elif adapter_id == _OPENAI_RELEASE_ADAPTER_ID:
        relative_paths = (
            "private-logs/openai-forecast.json",
            "private-logs/openai-transcript.json",
        )
    elif isinstance(adapter, CommandAdapter):
        relative_paths = (
            "private-logs/release-forecast-output.json",
            "private-logs/neutral-api-transcript.json",
            SOLVER_INPUT_ENTRY_PATH,
        )
    else:
        raise ResumeRefusedError(
            "resume refused: incomplete release row uses an unsupported adapter"
        )
    for relative in relative_paths:
        try:
            (plan.workspace / relative).unlink(missing_ok=True)
        except OSError as exc:
            raise ResumeRefusedError(
                f"resume refused: stale release artifact is unsafe: {relative}"
            ) from exc


@dataclass(slots=True)
class _MultiHarnessRunner:
    config: MultiHarnessRunConfig

    def run(self) -> MultiHarnessRun:
        adapters = _ordered_adapters(self.config.adapters)
        selection = self.config.selection.select(self.config.task_index)
        _validate_known_release_adapter_routes(
            tasks=selection.tasks,
            adapters=adapters,
            model_configs=self.config.model_configs,
        )
        _validate_live_release_adapter_routes(
            container_execution=self.config.container_execution,
            tasks=selection.tasks,
            adapters=adapters,
            model_configs=self.config.model_configs,
        )
        if self.config.container_execution == "live_tools":
            validate_live_container_policy(self.config.sandbox_policy)
            _preflight_live_container(self.config.sandbox_policy)
        requested_containment = self.config.sandbox_policy.host_process_containment
        if requested_containment != POSIX_PROCESS_GROUP_CONTAINMENT:
            unsupported = tuple(
                adapter.manifest.adapter_id
                for adapter in adapters
                if not isinstance(adapter, (CommandAdapter, LfbNativeAdapter))
            )
            if unsupported:
                formatted = ", ".join(unsupported)
                raise ValueError(
                    "strong host process containment is unsupported for "
                    f"adapters: {formatted}"
                )
            if any(isinstance(adapter, CommandAdapter) for adapter in adapters):
                preflight_process_containment(requested_containment)
        provider_values = require_provider_environment_values(
            self.config.sandbox_policy.allowed_provider_env_vars
        )
        secret_values = tuple(provider_values.values())
        build_container_plan(self.config.sandbox_policy)
        identity = _identity_binding_for(self.config, selection.selection_sha256)
        _ensure_private_run_directory(self.config.output_dir)
        (self.config.output_dir / "artifact-index.json").unlink(missing_ok=True)
        journal = self._prepare_journal(selection=selection, identity=identity)
        with signal_boundary((self.config.output_dir, journal)):
            with tempfile.TemporaryDirectory(
                prefix="multiharness-capabilities-"
            ) as root:
                capability_root = Path(root)
                _ensure_private_run_directory(capability_root)
                capabilities, capability_artifacts = self._load_capabilities(
                    adapters,
                    capability_root,
                )
                row_plans = self._build_row_plans(selection, adapters, capabilities)
            self._write_capabilities(capabilities, capability_artifacts)
            _ensure_private_run_directory(self.config.output_dir / "rows")
            run_config_sha256 = _record_sha256(self.config.to_record(), prefixed=True)
            run_compatibility_record = _run_compatibility_record(
                self.config,
                capabilities,
            )
            validate_no_secret_values(
                run_compatibility_record,
                secret_values,
                "run compatibility",
            )
            run_compatibility_sha256 = _record_sha256(
                run_compatibility_record,
                prefixed=True,
            )
            write_json_object_safe(
                self.config.output_dir / "run-compatibility.json",
                run_compatibility_record,
            )
            initial_manifest = RunManifest(
                run_id=self.config.run_id,
                selection_sha256=selection.selection_sha256,
                run_config_sha256=run_config_sha256,
                request_ids=tuple(plan.request.request_id for plan in row_plans),
                run_compatibility_sha256=run_compatibility_sha256,
            )
            write_json_object_safe(
                self.config.output_dir / "run-manifest.json",
                initial_manifest.to_record(),
            )
            write_json_object_safe(
                self.config.output_dir / "selection-manifest.json",
                _selection_manifest_record(selection, journal),
            )

        rows: list[MultiHarnessRunRow] = []
        interrupted = False
        with signal_boundary() as stop_requested:
            try:
                for plan in row_plans:
                    if stop_requested() or interrupted:
                        interrupted = True
                        break
                    row = self._execute_row(
                        plan,
                        selection_label=selection.selection_label,
                        coverage_kind=selection.coverage_kind,
                        journal=journal,
                    )
                    rows.append(row)
                    if row.result.status == "succeeded":
                        journal = journal.with_completed_row(plan.row_id)
                    elif row.result.status == "interrupted":
                        journal = journal.with_interrupted_row(plan.row_id)
                        interrupted = True
                    write_progress_journal(self.config.output_dir, journal)
                    if interrupted:
                        break
            except KeyboardInterrupt:
                interrupted = True

        if interrupted or len(rows) < len(row_plans):
            interrupted = True
            if journal.status != "interrupted":
                journal = journal.mark_stopped()
                write_progress_journal(self.config.output_dir, journal)
        else:
            journal = journal.mark_completed()
            write_progress_journal(self.config.output_dir, journal)
        write_json_object_safe(
            self.config.output_dir / "selection-manifest.json",
            _selection_manifest_record(selection, journal),
        )

        final_manifest = RunManifest(
            run_id=self.config.run_id,
            selection_sha256=selection.selection_sha256,
            run_config_sha256=run_config_sha256,
            request_ids=tuple(plan.request.request_id for plan in row_plans),
            result_ids=tuple(row.result.result_id for row in rows),
            run_compatibility_sha256=run_compatibility_sha256,
        )
        self._write_run_outputs(final_manifest, tuple(rows))
        return MultiHarnessRun(
            manifest=final_manifest,
            selection=selection,
            rows=tuple(rows),
            output_dir=self.config.output_dir,
            interrupted=interrupted,
        )

    def _prepare_journal(
        self,
        *,
        selection: SelectionResult,
        identity: IdentityBinding,
    ) -> RunProgressJournal:
        existing = load_progress_journal(self.config.output_dir)
        if self.config.resume:
            if existing is None:
                raise ResumeRefusedError("resume refused: no progress journal")
            refuse_resume_identity_drift(prior=existing.identity, requested=identity)
            return existing
        journal = RunProgressJournal(
            run_id=self.config.run_id,
            identity=identity,
            coverage_kind=selection.coverage_kind,
            selection_label=selection.selection_label,
            completed_row_ids=(),
            status="in_progress",
        )
        write_progress_journal(self.config.output_dir, journal)
        return journal

    def _load_capabilities(
        self,
        adapters: tuple[HarnessAdapter, ...],
        workspace_root: Path,
    ) -> tuple[
        dict[str, AdapterCapabilities],
        dict[str, dict[str, bytes]],
    ]:
        seen: set[str] = set()
        capabilities: dict[str, AdapterCapabilities] = {}
        artifacts: dict[str, dict[str, bytes]] = {}
        for adapter in adapters:
            adapter_id = adapter.manifest.adapter_id
            if adapter_id in seen:
                raise ValueError(f"duplicate adapter_id: {adapter_id}")
            seen.add(adapter_id)
            workspace = workspace_root / _slug(adapter_id)
            _ensure_private_run_directory(workspace)
            if isinstance(adapter, CommandAdapter):
                requested_containment = (
                    self.config.sandbox_policy.host_process_containment
                )
                if requested_containment == POSIX_PROCESS_GROUP_CONTAINMENT:
                    value = adapter.capabilities(workspace)
                else:
                    value = adapter.capabilities(
                        workspace,
                        host_process_containment=requested_containment,
                    )
            else:
                value = adapter.capabilities(workspace)
            if value.adapter_id != adapter.manifest.adapter_id:
                raise ValueError("adapter capabilities ID does not match manifest")
            if value.adapter_version != adapter.manifest.adapter_version:
                raise ValueError("adapter capabilities version does not match manifest")
            provider_values = require_provider_environment_values(
                self.config.sandbox_policy.allowed_provider_env_vars
            )
            validate_no_secret_values(
                value.to_record(),
                tuple(provider_values.values()),
                "adapter capabilities",
            )
            if self.config.container_execution == "live_tools":
                if value.tool_protocol_version != TOOL_REQUEST_SCHEMA_VERSION:
                    raise ValueError(
                        "live tool container requires adapter tool protocol "
                        f"{TOOL_REQUEST_SCHEMA_VERSION}"
                    )
                if not isinstance(adapter, LiveToolAdapter):
                    raise ValueError(
                        "adapter advertises the live tool protocol but does not "
                        "implement run_with_tools"
                    )
            capabilities[adapter_id] = value
            artifacts[adapter_id] = _snapshot_capability_artifacts(workspace)
        return capabilities, artifacts

    def _write_capabilities(
        self,
        capabilities: Mapping[str, AdapterCapabilities],
        artifacts: Mapping[str, Mapping[str, bytes]],
    ) -> None:
        root = self.config.output_dir / "adapter-capabilities"
        _ensure_private_run_directory(root)
        for adapter_id, value in capabilities.items():
            workspace = root / _slug(adapter_id)
            _ensure_private_run_directory(workspace)
            for relative, payload in artifacts[adapter_id].items():
                destination = workspace / relative
                _ensure_private_run_directory(destination.parent)
                write_file_replace_safe(destination, payload)
            write_json_object_safe(
                workspace / "adapter-capabilities.json",
                value.to_record(),
            )

    def _build_row_plans(
        self,
        selection: SelectionResult,
        adapters: tuple[HarnessAdapter, ...],
        capabilities: Mapping[str, AdapterCapabilities],
    ) -> tuple[_RowPlan, ...]:
        adapter_ids = {adapter.manifest.adapter_id for adapter in adapters}
        for model in self.config.model_configs:
            if model.adapter_id is not None and model.adapter_id not in adapter_ids:
                raise ValueError(
                    f"model_config references unknown adapter_id: {model.adapter_id}"
                )

        plans: list[_RowPlan] = []
        for task in selection.tasks:
            compatible_count = 0
            for adapter in adapters:
                caps = capabilities[adapter.manifest.adapter_id]
                if not _supports_task(caps, task):
                    continue
                for model in _matching_model_configs(
                    adapter.manifest.adapter_id,
                    self.config.model_configs,
                ):
                    self._validate_native_lfb_inputs(adapter, task, model)
                    compatible_count += 1
                    row_id = _row_id(
                        task=task,
                        adapter=adapter.manifest,
                        model=model,
                        selection_sha256=selection.selection_sha256,
                        live=getattr(adapter, "auth_profile", None)
                        == PUBLISHED_API_KEY,
                        stage=_resume_stage(adapter),
                    )
                    request = _run_request(
                        row_id=row_id,
                        task=task,
                        adapter=adapter.manifest,
                        capabilities=caps,
                        model=model,
                        sandbox_policy=self.config.sandbox_policy,
                    )
                    plans.append(
                        _RowPlan(
                            row_id=row_id,
                            task=task,
                            adapter=adapter,
                            capabilities=caps,
                            model_config=model,
                            request=request,
                            workspace=self.config.output_dir / "rows" / row_id,
                        )
                    )
            if compatible_count == 0:
                raise ValueError(
                    f"no compatible adapter/model rows for task {task.task_id}"
                )
        return tuple(plans)

    def _validate_native_lfb_inputs(
        self,
        adapter: HarnessAdapter,
        task: CanonicalTask,
        model: ModelConfig,
    ) -> None:
        if not isinstance(adapter, LfbNativeAdapter):
            return
        if task.family != "legalforecast_mtd":
            return
        if (
            task.metadata.get("release_schema_version")
            == _FORECAST_RELEASE_SCHEMA_VERSION
        ):
            raise ValueError(
                "LfbNativeAdapter does not support release-backed tasks; "
                "use an authenticated release adapter"
            )
        if model.lfb_packet is None or model.lfb_solver is None:
            raise ValueError("LfbNativeAdapter rows require lfb_packet and lfb_solver")

    def _execute_row(
        self,
        plan: _RowPlan,
        *,
        selection_label: str,
        coverage_kind: str,
        journal: RunProgressJournal,
    ) -> MultiHarnessRunRow:
        # Unsafe output paths are fatal even under ``record_failure``: there is
        # no trusted location in which to persist failure evidence, and
        # continuing would let the aggregate artifact walk inspect hostile
        # pre-existing row contents.
        _ensure_private_run_directory(plan.workspace)
        private_logs = plan.workspace / "private-logs"
        _ensure_private_run_directory(private_logs)

        resumed = False
        lfb_record: Mapping[str, Any] | None = None
        container_receipt_sha256: str | None = None
        prepared_input = PreparedSolverInput()
        try:
            prepared_input = prepare_solver_input(
                self.config.solver_inputs,
                plan.task,
                private_logs,
            )
            resumed_result = self._resume_result(
                plan,
                solver_input_root=prepared_input.root,
                solver_input_entry=prepared_input.entry,
                solver_input_tree_sha256=prepared_input.tree_sha256,
                journal=journal,
            )
            write_json_object_safe(
                plan.workspace / "request.json",
                plan.request.to_record(),
            )
            write_json_object_safe(
                plan.workspace / "sandbox.plan.json",
                (
                    live_container_public_plan(plan.request.sandbox_policy)
                    if self.config.container_execution == "live_tools"
                    else build_container_plan(plan.request.sandbox_policy).to_record()
                ),
            )
            if resumed_result is not None:
                result, lfb_record, container_receipt_sha256 = resumed_result
                resumed = True
            else:
                result, lfb_record, container_receipt_sha256 = self._run_adapter(
                    plan,
                    solver_input_root=prepared_input.root,
                    solver_input_entry=prepared_input.entry,
                    solver_input_tree_sha256=prepared_input.tree_sha256,
                )
            provider_values = require_provider_environment_values(
                plan.request.sandbox_policy.allowed_provider_env_vars
            )
            validate_no_secret_values(
                result.to_record(),
                tuple(provider_values.values()),
                "run result",
            )
        except ResumeRefusedError:
            raise
        except (CommandAdapterCancelled, KeyboardInterrupt) as exc:
            container_receipt_sha256 = None
            result = _interrupted_result(plan, exc)
            write_json_object_safe(plan.workspace / "result.json", result.to_record())
        except Exception as exc:
            container_receipt_sha256 = None
            if self.config.incomplete_run_policy == "fail_fast":
                try:
                    (plan.workspace / "result.json").unlink(missing_ok=True)
                except OSError:
                    # Preserve the original failure if best-effort cleanup fails.
                    pass
                raise
            write_file_replace_safe(
                private_logs / "error.txt",
                _plain_error(exc).encode("utf-8"),
            )
            result = _failure_result(plan, exc)
            write_json_object_safe(plan.workspace / "result.json", result.to_record())
        finally:
            prepared_input.cleanup()

        return MultiHarnessRunRow(
            row_id=plan.row_id,
            task=plan.task,
            adapter_manifest=plan.adapter.manifest,
            model_config=plan.model_config,
            request=plan.request,
            result=result,
            workspace=plan.workspace,
            resumed=resumed,
            lfb_record=lfb_record,
            container_execution=self.config.container_execution,
            container_receipt_sha256=container_receipt_sha256,
            selection_label=selection_label,
            coverage_kind=coverage_kind,
        )

    def _resume_result(
        self,
        plan: _RowPlan,
        *,
        solver_input_root: Path | None,
        solver_input_entry: SolverInputEntry | None,
        solver_input_tree_sha256: str | None,
        journal: RunProgressJournal,
    ) -> tuple[RunResult, Mapping[str, Any] | None, str | None] | None:
        if not self.config.resume:
            return None
        request_path = plan.workspace / "request.json"
        result_path = plan.workspace / "result.json"
        completed = plan.row_id in journal.completed_row_ids
        if completed and (not request_path.is_file() or not result_path.is_file()):
            raise ResumeRefusedError(
                "resume refused: completed row is missing durable artifacts"
            )
        if not request_path.is_file():
            return None
        try:
            existing_request = RunRequest.from_record(
                _read_json(request_path, "request")
            )
        except (OSError, ValueError) as exc:
            if completed:
                raise ResumeRefusedError(
                    "resume refused: completed row is missing durable artifacts"
                ) from exc
            return None
        if existing_request.to_record() != plan.request.to_record():
            return None
        if not result_path.is_file():
            if release_harness.is_release_task(plan.request):
                _prepare_incomplete_release_retry(plan)
            return None
        try:
            result = RunResult.from_record(_read_json(result_path, "result"))
        except (OSError, ValueError) as exc:
            if completed:
                raise ResumeRefusedError(
                    "resume refused: completed row is missing durable artifacts"
                ) from exc
            if release_harness.is_release_task(plan.request):
                _prepare_incomplete_release_retry(plan)
            return None
        try:
            provider_values = require_provider_environment_values(
                plan.request.sandbox_policy.allowed_provider_env_vars
            )
            validate_no_secret_values(
                result.to_record(),
                tuple(provider_values.values()),
                "resumed run result",
            )
        except (OSError, ValueError):
            if release_harness.is_release_task(plan.request):
                _prepare_incomplete_release_retry(plan)
            return None
        if result.request_id != plan.request.request_id or result.status != "succeeded":
            if release_harness.is_release_task(plan.request):
                _prepare_incomplete_release_retry(plan)
            return None
        container_receipt_sha256: str | None = None
        if self.config.container_execution == "live_tools":
            try:
                container_receipt_sha256 = validate_container_resume(
                    plan.workspace
                    / "private-logs"
                    / "tool-container"
                    / "execution-receipt.json",
                    request=plan.request,
                    result=result,
                    policy=plan.request.sandbox_policy,
                    input_tree_sha256=solver_input_tree_sha256,
                )
            except (OSError, ValueError, ContainerRuntimeError) as exc:
                raise ResumeRefusedError(
                    "resume refused: successful live-tool row has an invalid "
                    "container receipt"
                ) from exc
        lfb_record_path = plan.workspace / "lfb-inspect-record.json"
        if release_harness.is_release_task(plan.request):
            try:
                lfb_record = release_harness.validate_resumed_release_harness_result(
                    plan.request,
                    result,
                    plan.workspace,
                    solver_input_root,
                    solver_input_entry,
                )
            except (OSError, ValueError) as exc:
                if completed:
                    raise ResumeRefusedError(
                        "resume refused: completed release evidence is invalid"
                    ) from exc
                try:
                    lfb_record = release_harness.repair_resumed_release_harness_result(
                        plan.request,
                        result,
                        plan.workspace,
                        solver_input_root,
                        solver_input_entry,
                    )
                except (OSError, ValueError) as repair_exc:
                    raise ResumeRefusedError(
                        "resume refused: partial release evidence is invalid"
                    ) from repair_exc
            return result, lfb_record, container_receipt_sha256
        if lfb_record_path.is_file():
            return (
                result,
                _read_json(lfb_record_path, "lfb inspect record"),
                container_receipt_sha256,
            )
        return result, None, container_receipt_sha256

    def _run_adapter(
        self,
        plan: _RowPlan,
        *,
        solver_input_root: Path | None,
        solver_input_entry: SolverInputEntry | None,
        solver_input_tree_sha256: str | None,
    ) -> tuple[RunResult, Mapping[str, Any] | None, str | None]:
        if self.config.container_execution == "live_tools":
            if (
                solver_input_root is None
                or solver_input_entry is None
                or solver_input_tree_sha256 is None
            ):
                raise ValueError("live row solver input is unavailable")
            session = ContainerToolSession(
                policy=plan.request.sandbox_policy,
                run_request=plan.request,
                workspace=plan.workspace,
                solver_input_root=solver_input_root,
                solver_input=solver_input_entry,
                input_tree_sha256=solver_input_tree_sha256,
            )
            try:
                result = cast(LiveToolAdapter, plan.adapter).run_with_tools(
                    plan.request,
                    plan.workspace,
                    session,
                )
                if result.request_id != plan.request.request_id:
                    raise ValueError("run result request_id does not match request")
                provider_values = require_provider_environment_values(
                    plan.request.sandbox_policy.allowed_provider_env_vars
                )
                validate_public_record(result.to_record(), "live run result")
                validate_no_secret_values(
                    result.to_record(),
                    tuple(provider_values.values()),
                    "live run result",
                )
                receipt = session.finalize(result)
                receipt_sha256 = receipt.receipt_sha256
            except BaseException as exc:
                try:
                    session.abort()
                except ContainerRuntimeError as cleanup_error:
                    raise cleanup_error from exc
                raise
            write_json_object_safe(plan.workspace / "result.json", result.to_record())
            lfb_record = release_harness.project_and_write_release_harness_result(
                plan.request,
                result,
                plan.workspace,
                solver_input_root,
                solver_input_entry,
            )
            return result, lfb_record, receipt_sha256
        if isinstance(plan.adapter, LfbNativeAdapter):
            projected = self._run_lfb_native(plan)
            result = projected.result
            lfb_record = projected.inspect_record
            provider_values = require_provider_environment_values(
                plan.request.sandbox_policy.allowed_provider_env_vars
            )
            validate_no_secret_values(
                result.to_record(),
                tuple(provider_values.values()),
                "native run result",
            )
            write_json_object_safe(plan.workspace / "result.json", result.to_record())
            write_json_object_safe(
                plan.workspace / "lfb-inspect-record.json",
                lfb_record,
            )
            return result, lfb_record, None
        result, lfb_record = release_harness.run_and_project_solver_input_adapter(
            plan.adapter,
            plan.request,
            plan.workspace,
            solver_input_root,
            solver_input_entry,
        )
        return result, lfb_record, None

    def _run_lfb_native(self, plan: _RowPlan) -> AdapterRunResult:
        packet = plan.model_config.lfb_packet
        solver = plan.model_config.lfb_solver
        if packet is None or solver is None:
            raise ValueError("LfbNativeAdapter rows require lfb_packet and lfb_solver")
        native_run = cast(LfbNativeAdapter, plan.adapter).run_fixture_packet(
            request=plan.request,
            packet=packet,
            solver=solver,
            workspace=plan.workspace,
        )
        if len(native_run.projected_results) != 1:
            raise ValueError("LfbNativeAdapter runner expects one projected result")
        return native_run.projected_results[0]

    def _write_run_outputs(
        self,
        manifest: RunManifest,
        rows: tuple[MultiHarnessRunRow, ...],
    ) -> None:
        provider_values = require_provider_environment_values(
            self.config.sandbox_policy.allowed_provider_env_vars
        )
        secret_values = tuple(provider_values.values())
        for row in rows:
            validate_no_secret_values(
                row.to_record(),
                secret_values,
                "run row",
            )
        write_json_object_safe(
            self.config.output_dir / "run-manifest.json",
            manifest.to_record(),
        )
        write_jsonl_objects_safe(
            self.config.output_dir / "canonical-runs.jsonl",
            [row.result.to_record() for row in rows],
        )
        lfb_records = [row.lfb_record for row in rows if row.lfb_record is not None]
        if lfb_records:
            _ensure_private_run_directory(self.config.output_dir / "lfb")
            write_jsonl_objects_safe(
                self.config.output_dir / "lfb" / "runs.jsonl",
                [record for record in lfb_records],
            )
        release_receipts = release_harness.collect_release_harness_receipts(
            (row.request, row.result, row.workspace) for row in rows
        )
        if release_receipts:
            write_jsonl_objects_safe(
                self.config.output_dir / "release-harness-receipts.jsonl",
                release_receipts,
            )
        lab_records = [
            _lab_result_record(row) for row in rows if row.task.family == "harvey_lab"
        ]
        if lab_records:
            _ensure_private_run_directory(self.config.output_dir / "lab")
            write_jsonl_objects_safe(
                self.config.output_dir / "lab" / "task-results.jsonl",
                lab_records,
            )
        write_jsonl_objects_safe(
            self.config.output_dir / "row-results.jsonl",
            [row.to_record() for row in rows],
        )
        write_json_object_safe(
            self.config.output_dir / "artifact-index.json",
            {"artifacts": _artifact_index(self.config.output_dir)},
        )


def _snapshot_capability_artifacts(workspace: Path) -> dict[str, bytes]:
    """Capture exact safe probe artifacts before deleting the preflight root."""

    artifacts: dict[str, bytes] = {}
    for path in sorted(workspace.rglob("*")):
        if path.is_symlink():
            raise ValueError("adapter capability output must not contain symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(workspace).as_posix()
        try:
            artifacts[relative] = read_single_link_file(
                path,
                label="adapter capability output",
            )
        except ImmutableIOError as exc:
            raise ValueError("adapter capability output is unsafe") from exc
    return artifacts


def _ordered_adapters(adapters: Sequence[HarnessAdapter]) -> tuple[HarnessAdapter, ...]:
    return tuple(
        sorted(
            adapters,
            key=lambda adapter: (
                adapter.manifest.adapter_id,
                adapter.manifest.adapter_version,
            ),
        )
    )


def _preflight_live_container(policy: SandboxPolicy) -> None:
    """Prove the rootless daemon and exact local image before any adapter starts."""

    environment = build_container_backend_environment()
    backend_path = resolve_container_backend(policy)
    require_rootless_container_daemon(
        backend_path,
        policy.backend,
        environment,
    )
    require_local_pinned_container_image(
        backend_path,
        policy.image,
        environment,
    )


def _ordered_model_configs(models: Sequence[ModelConfig]) -> tuple[ModelConfig, ...]:
    return tuple(
        sorted(models, key=lambda model: (model.adapter_id or "", model.model_key))
    )


def _matching_model_configs(
    adapter_id: str,
    models: Sequence[ModelConfig],
) -> tuple[ModelConfig, ...]:
    return tuple(
        model
        for model in _ordered_model_configs(models)
        if model.adapter_id is None or model.adapter_id == adapter_id
    )


def _supports_task(capabilities: AdapterCapabilities, task: CanonicalTask) -> bool:
    return (
        task.family in capabilities.supported_families
        and task.scoring_mode in capabilities.supported_scoring_modes
    )


def _run_request(
    *,
    row_id: str,
    task: CanonicalTask,
    adapter: AdapterManifest,
    capabilities: AdapterCapabilities,
    model: ModelConfig,
    sandbox_policy: SandboxPolicy,
) -> RunRequest:
    payload = {
        "request_id": row_id,
        "task": task.to_record(),
        "adapter": adapter.to_record(),
        "adapter_capabilities_sha256": capabilities.capabilities_sha256,
        "model_key": model.model_key,
        "model_config": model.to_record(),
        "sandbox_policy": sandbox_policy.to_record(),
    }
    return RunRequest(
        request_id=row_id,
        task=task,
        adapter=adapter,
        model_key=model.model_key,
        sandbox_policy=sandbox_policy,
        request_sha256=_record_sha256(payload, prefixed=True),
    )


def _resume_stage(adapter: object) -> str | None:
    service = getattr(adapter, "execution_service", None)
    raw = getattr(service, "infisical_env", None) if service is not None else None
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise AuthProfileError("Infisical environment is not an allowed sandbox stage")
    stage = require_infisical_environment(raw)
    if stage == "staging":
        return "staging"
    if stage == "sandbox":
        return "sandbox"
    return None


def _row_id(
    *,
    task: CanonicalTask,
    adapter: AdapterManifest,
    model: ModelConfig,
    selection_sha256: str,
    live: bool = False,
    stage: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "family": task.family,
        "task_id": task.task_id,
        "adapter_id": adapter.adapter_id,
        "adapter_version": adapter.adapter_version,
        "model_key": model.model_key,
        "selection_sha256": selection_sha256,
    }
    if live:
        payload["live"] = "1"
        if stage == "staging":
            payload["stage"] = "staging"
        elif stage == "sandbox":
            payload["stage"] = "sandbox"
    digest = _record_sha256(
        payload,
        prefixed=False,
    )[:16]
    return f"row-{digest}"


def _failure_result(plan: _RowPlan, exc: Exception) -> RunResult:
    provider_values = require_provider_environment_values(
        plan.request.sandbox_policy.allowed_provider_env_vars
    )
    secret_values = tuple(provider_values.values())
    summary = {
        "task_id": plan.task.task_id,
        "adapter_id": plan.adapter.manifest.adapter_id,
        "model_key": plan.model_config.model_key,
        "error_type": exc.__class__.__name__,
        "error_message": _plain_error(exc),
    }
    try:
        validate_public_record(summary, "failure.public_summary")
        validate_no_secret_values(
            summary,
            secret_values,
            "failure.public_summary",
        )
    except ValueError:
        summary = {
            "error_type": exc.__class__.__name__,
            "error_message": "adapter failed; see private logs",
        }
        try:
            validate_no_secret_values(
                summary,
                secret_values,
                "failure.public_summary",
            )
        except ValueError:
            summary = {}
    return RunResult(
        result_id=f"{plan.row_id}:result",
        request_id=plan.request.request_id,
        status="failed",
        result_sha256=_record_sha256(summary, prefixed=True),
        public_summary=summary,
    )


def _interrupted_result(plan: _RowPlan, exc: BaseException) -> RunResult:
    summary = {
        "task_id": plan.task.task_id,
        "adapter_id": plan.adapter.manifest.adapter_id,
        "model_key": plan.model_config.model_key,
        "interrupt_class": "interrupted",
        "error_type": exc.__class__.__name__,
        "error_message": _plain_error(exc),
    }
    try:
        validate_public_record(summary, "interrupt.public_summary")
    except ValueError:
        summary = {
            "interrupt_class": "interrupted",
            "error_message": "run was interrupted",
        }
    return RunResult(
        result_id=f"{plan.row_id}:result",
        request_id=plan.request.request_id,
        status="interrupted",
        result_sha256=_record_sha256(summary, prefixed=True),
        public_summary=summary,
    )


def _lab_result_record(row: MultiHarnessRunRow) -> dict[str, Any]:
    return {
        "row_id": row.row_id,
        "task_id": row.task.task_id,
        "adapter_id": row.adapter_manifest.adapter_id,
        "adapter_version": row.adapter_manifest.adapter_version,
        "model_key": row.model_config.model_key,
        "request_sha256": row.request.request_sha256,
        "result": row.result.to_record(),
    }


def _artifact_index(root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(
        item for item in root.rglob("*") if not item.is_symlink() and item.is_file()
    ):
        if path.name == "artifact-index.json":
            continue
        relative = path.relative_to(root).as_posix()
        parts = relative.split("/")
        if "private-logs" in parts:
            private_logs_index = parts.index("private-logs")
            hidden_indexes = tuple(
                index for index, part in enumerate(parts) if part.startswith(".")
            )
            if hidden_indexes and min(hidden_indexes) > private_logs_index:
                continue
        artifacts.append(
            ArtifactRecord(
                artifact_id=_artifact_id(relative),
                path=relative,
                sha256=_file_sha256(path),
                media_type=_media_type(path),
                public=_is_public_artifact(root, relative),
                size_bytes=path.stat().st_size,
            ).to_record()
        )
    return artifacts


def _is_public_artifact(root: Path, relative_path: str) -> bool:
    """Keep private diagnostics out of the public artifact set by default."""

    parts = relative_path.split("/")
    if "private-logs" in parts or parts[-1] == "lab-command-capabilities.json":
        return False
    if len(parts) >= 4 and parts[0] == "rows":
        row_root = root / parts[0] / parts[1]
        if (row_root / "release-harness-receipt.json").is_file() and parts[2] in {
            "codex-output",
            "sealed-deliverable",
        }:
            return False
    if parts[0] == "adapter-capabilities":
        return len(parts) == 3 and parts[-1] == "adapter-capabilities.json"
    return True


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object_safe(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _artifact_id(relative_path: str) -> str:
    stem = relative_path.removesuffix(".json").removesuffix(".jsonl")
    return _slug(stem) or "artifact"


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/jsonl"
    if suffix in {".txt", ".log"}:
        return "text/plain"
    return "application/octet-stream"


def _plain_error(exc: BaseException) -> str:
    text = str(exc).strip()
    if not text:
        text = exc.__class__.__name__
    return text


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:96]


def _file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _record_sha256(record: Mapping[str, Any], *, prefixed: bool) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if prefixed:
        return f"sha256:{digest}"
    return digest


def _run_compatibility_record(
    config: MultiHarnessRunConfig,
    capabilities: Mapping[str, AdapterCapabilities],
) -> dict[str, Any]:
    """Record execution semantics while excluding selection and run-local identity."""

    record = config.to_record()
    compatibility_record: dict[str, Any] = {
        "schema_version": RUN_COMPATIBILITY_SCHEMA_VERSION,
        "run_config": {
            "task_index": record["task_index"],
            "adapters": [
                {
                    "adapter_id": adapter.manifest.adapter_id,
                    "adapter_version": adapter.manifest.adapter_version,
                }
                for adapter in _ordered_adapters(config.adapters)
            ],
            "model_configs": record["model_configs"],
            "sandbox_policy": {
                "policy_id": config.sandbox_policy.policy_id,
                "policy_sha256": _record_sha256(
                    config.sandbox_policy.to_record(),
                    prefixed=True,
                ),
            },
            "incomplete_run_policy": config.incomplete_run_policy,
            "container_execution": config.container_execution,
        },
        "adapter_capabilities": [
            capabilities[adapter_id].to_record() for adapter_id in sorted(capabilities)
        ],
    }
    if config.solver_inputs is not None:
        compatibility_record["run_config"]["solver_input_index_sha256"] = (
            config.solver_inputs.index.index_sha256
        )
    validate_public_record(compatibility_record, "run_compatibility")
    return compatibility_record


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


def _identity_binding_for(
    config: MultiHarnessRunConfig,
    selection_sha256: str,
) -> IdentityBinding:
    adapters = _ordered_adapters(config.adapters)
    models = _ordered_model_configs(config.model_configs)
    config_record = dict(config.to_record())
    adapter_timeouts = _adapter_timeout_records(adapters)
    if adapter_timeouts:
        config_record["adapter_timeout_seconds"] = adapter_timeouts
    return bind_run_identity(
        adapter_ids=tuple(adapter.manifest.adapter_id for adapter in adapters),
        adapter_versions=tuple(
            adapter.manifest.adapter_version for adapter in adapters
        ),
        model_keys=tuple(model.model_key for model in models),
        config_record=config_record,
        policy_record=config.sandbox_policy.to_record(),
        policy_sha256=_record_sha256(
            config.sandbox_policy.to_record(),
            prefixed=True,
        ),
        selection_sha256=selection_sha256,
    )


def _adapter_timeout_records(
    adapters: Sequence[HarnessAdapter],
) -> list[dict[str, str | float]]:
    records: list[dict[str, str | float]] = []
    for adapter in adapters:
        timeout = getattr(adapter, "timeout_seconds", None)
        if isinstance(timeout, int | float) and not isinstance(timeout, bool):
            records.append(
                {
                    "adapter_id": adapter.manifest.adapter_id,
                    "timeout_seconds": float(timeout),
                }
            )
    return records


def _selection_manifest_record(
    selection: SelectionResult,
    journal: RunProgressJournal,
) -> dict[str, Any]:
    claim_kind = journal.claim_kind()
    selection_label = selection.selection_label
    if claim_kind == CLAIM_PARTIAL and not is_partial_label(selection_label):
        selection_label = f"{CLAIM_PARTIAL}+{selection_label}"
    return {
        "schema_version": (
            # contract-ratchet: allow non-authoritative selection-manifest sidecar
            "legalforecast.multiharness.selection_manifest.v1"
        ),
        "selection_sha256": selection.selection_sha256,
        "selection_label": selection_label,
        "coverage_kind": selection.coverage_kind,
        "claim_kind": claim_kind,
        "task_ids": [task.task_id for task in selection.tasks],
        "run_status": journal.status,
    }
