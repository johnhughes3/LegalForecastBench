"""Deterministic multi-harness run orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import (
    read_json_object,
    write_json_object,
    write_jsonl_objects,
)
from legalforecast.evals.inspect_task import HarnessSolver
from legalforecast.evals.packet_builder import ModelPacket
from legalforecast.multiharness.adapters import HarnessAdapter
from legalforecast.multiharness.artifacts import AdapterRunResult
from legalforecast.multiharness.host_environment import (
    require_provider_environment_values,
)
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.sandbox import (
    PROVIDER_EGRESS_HOST_ONLY,
    build_container_plan,
)
from legalforecast.multiharness.selection import SelectionResult, TaskSelection
from legalforecast.multiharness.spec import (
    RUN_COMPATIBILITY_SCHEMA_VERSION,
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
        validate_provider_environment_scope(
            sandbox_policy=self.sandbox_policy,
            adapter_count=len(self.adapters),
            model_count=len(self.model_configs),
        )

    def to_record(self) -> dict[str, Any]:
        return {
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
        }


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
        }


@dataclass(frozen=True, slots=True)
class MultiHarnessRun:
    """Completed multi-harness run artifacts."""

    manifest: RunManifest
    selection: SelectionResult
    rows: tuple[MultiHarnessRunRow, ...]
    output_dir: Path


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

    return _MultiHarnessRunner(config).run()


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


@dataclass(slots=True)
class _MultiHarnessRunner:
    config: MultiHarnessRunConfig

    def run(self) -> MultiHarnessRun:
        (self.config.output_dir / "artifact-index.json").unlink(missing_ok=True)
        provider_values = require_provider_environment_values(
            self.config.sandbox_policy.allowed_provider_env_vars
        )
        secret_values = tuple(provider_values.values())
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        build_container_plan(self.config.sandbox_policy)
        selection = self.config.selection.select(self.config.task_index)
        adapters = _ordered_adapters(self.config.adapters)
        capabilities = self._load_capabilities(adapters)
        row_plans = self._build_row_plans(selection, adapters, capabilities)
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
        write_json_object(
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
        write_json_object(
            self.config.output_dir / "run-manifest.json",
            initial_manifest.to_record(),
        )

        rows: list[MultiHarnessRunRow] = []
        for plan in row_plans:
            rows.append(self._execute_row(plan))

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
        )

    def _load_capabilities(
        self,
        adapters: tuple[HarnessAdapter, ...],
    ) -> dict[str, AdapterCapabilities]:
        seen: set[str] = set()
        capabilities: dict[str, AdapterCapabilities] = {}
        for adapter in adapters:
            adapter_id = adapter.manifest.adapter_id
            if adapter_id in seen:
                raise ValueError(f"duplicate adapter_id: {adapter_id}")
            seen.add(adapter_id)
            workspace = (
                self.config.output_dir / "adapter-capabilities" / _slug(adapter_id)
            )
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
            capabilities[adapter_id] = value
            write_json_object(
                workspace / "adapter-capabilities.json",
                value.to_record(),
            )
        return capabilities

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
        if model.lfb_packet is None or model.lfb_solver is None:
            raise ValueError("LfbNativeAdapter rows require lfb_packet and lfb_solver")

    def _execute_row(self, plan: _RowPlan) -> MultiHarnessRunRow:
        plan.workspace.mkdir(parents=True, exist_ok=True)
        private_logs = plan.workspace / "private-logs"
        private_logs.mkdir(parents=True, exist_ok=True)

        resumed = False
        lfb_record: Mapping[str, Any] | None = None
        try:
            resumed_result = self._resume_result(plan)
            write_json_object(plan.workspace / "request.json", plan.request.to_record())
            write_json_object(
                plan.workspace / "sandbox.plan.json",
                build_container_plan(plan.request.sandbox_policy).to_record(),
            )
            if resumed_result is not None:
                result, lfb_record = resumed_result
                resumed = True
            else:
                result, lfb_record = self._run_adapter(plan)
            provider_values = require_provider_environment_values(
                plan.request.sandbox_policy.allowed_provider_env_vars
            )
            validate_no_secret_values(
                result.to_record(),
                tuple(provider_values.values()),
                "run result",
            )
        except Exception as exc:
            if self.config.incomplete_run_policy == "fail_fast":
                try:
                    (plan.workspace / "result.json").unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            (private_logs / "error.txt").write_text(_plain_error(exc), encoding="utf-8")
            result = _failure_result(plan, exc)
            write_json_object(plan.workspace / "result.json", result.to_record())

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
        )

    def _resume_result(
        self,
        plan: _RowPlan,
    ) -> tuple[RunResult, Mapping[str, Any] | None] | None:
        if not self.config.resume:
            return None
        request_path = plan.workspace / "request.json"
        result_path = plan.workspace / "result.json"
        if not request_path.is_file() or not result_path.is_file():
            return None
        try:
            existing_request = RunRequest.from_record(
                _read_json(request_path, "request")
            )
            result = RunResult.from_record(_read_json(result_path, "result"))
            provider_values = require_provider_environment_values(
                plan.request.sandbox_policy.allowed_provider_env_vars
            )
            validate_no_secret_values(
                result.to_record(),
                tuple(provider_values.values()),
                "resumed run result",
            )
        except (OSError, ValueError):
            return None
        if existing_request.to_record() != plan.request.to_record():
            return None
        if result.request_id != plan.request.request_id or result.status != "succeeded":
            return None
        lfb_record_path = plan.workspace / "lfb-inspect-record.json"
        if lfb_record_path.is_file():
            return result, _read_json(lfb_record_path, "lfb inspect record")
        return result, None

    def _run_adapter(
        self,
        plan: _RowPlan,
    ) -> tuple[RunResult, Mapping[str, Any] | None]:
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
            write_json_object(plan.workspace / "result.json", result.to_record())
            write_json_object(plan.workspace / "lfb-inspect-record.json", lfb_record)
            return result, lfb_record
        result = plan.adapter.run(plan.request, plan.workspace)
        if result.request_id != plan.request.request_id:
            raise ValueError("run result request_id does not match request")
        return result, None

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
        write_json_object(
            self.config.output_dir / "run-manifest.json",
            manifest.to_record(),
        )
        write_jsonl_objects(
            self.config.output_dir / "canonical-runs.jsonl",
            [row.result.to_record() for row in rows],
        )
        lfb_records = [row.lfb_record for row in rows if row.lfb_record is not None]
        if lfb_records:
            write_jsonl_objects(
                self.config.output_dir / "lfb" / "runs.jsonl",
                [record for record in lfb_records],
            )
        lab_records = [
            _lab_result_record(row) for row in rows if row.task.family == "harvey_lab"
        ]
        if lab_records:
            write_jsonl_objects(
                self.config.output_dir / "lab" / "task-results.jsonl",
                lab_records,
            )
        write_jsonl_objects(
            self.config.output_dir / "row-results.jsonl",
            [row.to_record() for row in rows],
        )
        write_json_object(
            self.config.output_dir / "artifact-index.json",
            {"artifacts": _artifact_index(self.config.output_dir)},
        )


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


def _row_id(
    *,
    task: CanonicalTask,
    adapter: AdapterManifest,
    model: ModelConfig,
    selection_sha256: str,
) -> str:
    digest = _record_sha256(
        {
            "family": task.family,
            "task_id": task.task_id,
            "adapter_id": adapter.adapter_id,
            "adapter_version": adapter.adapter_version,
            "model_key": model.model_key,
            "selection_sha256": selection_sha256,
        },
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
        artifacts.append(
            ArtifactRecord(
                artifact_id=_artifact_id(relative),
                path=relative,
                sha256=_file_sha256(path),
                media_type=_media_type(path),
                public=_is_public_artifact(relative),
                size_bytes=path.stat().st_size,
            ).to_record()
        )
    return artifacts


def _is_public_artifact(relative_path: str) -> bool:
    """Keep private diagnostics out of the public artifact set by default."""

    parts = relative_path.split("/")
    if "private-logs" in parts or parts[-1] == "lab-command-capabilities.json":
        return False
    if parts[0] == "adapter-capabilities":
        return len(parts) == 3 and parts[-1] == "adapter-capabilities.json"
    return True


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object(
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


def _plain_error(exc: Exception) -> str:
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
        },
        "adapter_capabilities": [
            capabilities[adapter_id].to_record() for adapter_id in sorted(capabilities)
        ],
    }
    validate_public_record(compatibility_record, "run_compatibility")
    return compatibility_record


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
