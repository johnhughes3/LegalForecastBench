"""Provider-free composition runner for the frozen paired Tier-0 smoke.

The Tier-0 runner is intentionally a sidecar around the landed LAB bridge.  It
does not define a second execution or evaluation receipt.  A run is authorized
by one immutable executable-spec blob and one detached approval record; model,
adapter, command, timeout, and settings values are never accepted as run-time
options.

The production signer is supplied by the caller as an external authority.  In
particular, this module never reads a private key, Infisical, or provider
credential.  A provider-free fake-binary test can inject a test authority, but
the command entrypoint refuses to continue when no approved authority loader
is installed.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol, cast

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.adapter_registry import (
    CLAUDE_CODE_REGISTRY_NAME,
    HARVEY_LAB_REGISTRY_NAME,
    builtin_adapter_registry,
)
from legalforecast.multiharness.auth_profiles import require_auth_profile_id
from legalforecast.multiharness.claude_code import (
    CLAUDE_CODE_EXECUTABLE_NAME,
    ClaudeCodeCliAdapter,
)
from legalforecast.multiharness.claude_code_harvey_lab import (
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID,
    harvey_lab_issuer_policy_sha256,
    verify_authorized_harvey_lab_receipt,
)
from legalforecast.multiharness.harvey_lab_evaluator import (
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    HarveyLabIsolatedEvaluation,
    invoke_isolated_harvey_lab_evaluator,
)
from legalforecast.multiharness.harvey_lab_output_discovery import (
    HarveyLabOutputDiscoveryResult,
    discover_harvey_lab_outputs,
    require_harvey_lab_sandbox_hosts,
)
from legalforecast.multiharness.harvey_lab_projection import (
    ISSUE_196_LAB_TASK_ID,
    HarveyLabPin,
    HarveyLabProjectionResult,
    project_harvey_lab_suite,
    verify_harvey_lab_projection,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.scoring import (
    ScoreArtifact,
    build_harvey_lab_metric_definition,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    validate_public_record,
    validate_sha256,
)

TIER0_EXECUTABLE_SPEC_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative Tier-0 sidecar
    "legalforecast.multiharness.tier0_executable_spec.v1"
)
TIER0_SPEND_APPROVAL_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative Tier-0 sidecar
    "legalforecast.multiharness.tier0_detached_spend_approval.v1"
)
TIER0_ARCHIVE_MANIFEST_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative Tier-0 sidecar
    "legalforecast.multiharness.tier0_archive_manifest.v1"
)

_ARM_IDS = ("arm-opaque-01", "arm-opaque-02")
_ARM_ADAPTERS = frozenset({CLAUDE_CODE_REGISTRY_NAME, HARVEY_LAB_REGISTRY_NAME})
_ALLOWED_COMMAND_TOKENS = frozenset({"{sandbox_root}", "{output_root}"})
_DIGEST_PREFIX = "sha256:"


class Tier0RunnerError(ValueError):
    """A frozen Tier-0 run cannot proceed without violating a boundary."""


class IssuerAuthority(Protocol):
    """External issuer authority used to sign evaluator receipts."""

    @property
    def public_key(self) -> Ed25519PublicKey:
        """Return the public verification key for the approved signer."""
        ...

    def sign(self, payload: bytes) -> bytes:
        """Sign receipt bytes using an external, approved authority."""
        ...


@dataclass(frozen=True, slots=True)
class Tier0ArmSpec:
    """One immutable arm declaration from the executable-spec artifact."""

    arm_id: str
    adapter: str
    auth_profile: str
    requested_model: str
    solver_executable: str
    solver_executable_sha256: str
    command: tuple[str, ...] = ()
    settings: Mapping[str, object] = field(
        default_factory=lambda: cast(Mapping[str, object], {})
    )
    timeout_seconds: float = 300.0
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.arm_id, "arm_id")
        if self.arm_id not in _ARM_IDS:
            raise Tier0RunnerError("arm_id must be one of the two opaque arm IDs")
        if self.adapter not in _ARM_ADAPTERS:
            raise Tier0RunnerError("executable spec contains an unsupported adapter")
        try:
            require_auth_profile_id(self.auth_profile)
        except ValueError as exc:
            raise Tier0RunnerError(str(exc)) from exc
        _require_text(self.requested_model, "requested_model")
        _require_executable_basename(self.solver_executable, "solver_executable")
        _require_digest(self.solver_executable_sha256, "solver_executable_sha256")
        if self.timeout_seconds <= 0:
            raise Tier0RunnerError("timeout_seconds must be positive")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise Tier0RunnerError("max_cost_usd must be non-negative")
        if not self.command and self.adapter == HARVEY_LAB_REGISTRY_NAME:
            raise Tier0RunnerError("native-thin arm must declare a frozen command")
        if self.command and self.adapter == CLAUDE_CODE_REGISTRY_NAME:
            raise Tier0RunnerError("clean-native arm must use its registered adapter")
        if self.adapter == CLAUDE_CODE_REGISTRY_NAME:
            if self.solver_executable != CLAUDE_CODE_EXECUTABLE_NAME:
                raise Tier0RunnerError(
                    "clean-native arm must pin the Claude Code executable"
                )
        elif self.command[0] != self.solver_executable:
            raise Tier0RunnerError(
                "native-thin command must start with its pinned solver executable"
            )
        for token in self.command:
            if not token:
                raise Tier0RunnerError("arm command must contain non-empty strings")
            if token.startswith("{") and token not in _ALLOWED_COMMAND_TOKENS:
                raise Tier0RunnerError("arm command contains an unknown placeholder")
        validate_public_record(dict(self.settings), "Tier-0 arm settings")

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "arm_id": self.arm_id,
            "adapter": self.adapter,
            "auth_profile": self.auth_profile,
            "requested_model": self.requested_model,
            "solver_executable": self.solver_executable,
            "solver_executable_sha256": self.solver_executable_sha256,
            "command": list(self.command),
            "settings": dict(self.settings),
            "timeout_seconds": self.timeout_seconds,
        }
        if self.max_cost_usd is not None:
            record["max_cost_usd"] = self.max_cost_usd
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Tier0ArmSpec:
        _closed_record(
            record,
            required={
                "arm_id",
                "adapter",
                "auth_profile",
                "requested_model",
                "solver_executable",
                "solver_executable_sha256",
                "command",
                "settings",
                "timeout_seconds",
            },
            optional={"max_cost_usd"},
            field_name="Tier-0 arm",
        )
        command = record["command"]
        settings = record["settings"]
        if not isinstance(command, list) or any(
            not isinstance(item, str) for item in cast(list[object], command)
        ):
            raise Tier0RunnerError("Tier-0 arm command must be an array of strings")
        if not isinstance(settings, Mapping):
            raise Tier0RunnerError("Tier-0 arm settings must be an object")
        timeout = record["timeout_seconds"]
        if not isinstance(timeout, int | float) or isinstance(timeout, bool):
            raise Tier0RunnerError("Tier-0 arm timeout_seconds must be a number")
        cost = record.get("max_cost_usd")
        if cost is not None and (
            not isinstance(cost, int | float) or isinstance(cost, bool)
        ):
            raise Tier0RunnerError("Tier-0 arm max_cost_usd must be a number")
        return cls(
            arm_id=_text(record, "arm_id"),
            adapter=_text(record, "adapter"),
            auth_profile=_text(record, "auth_profile"),
            requested_model=_text(record, "requested_model"),
            solver_executable=_text(record, "solver_executable"),
            solver_executable_sha256=_text(record, "solver_executable_sha256"),
            command=tuple(cast(list[str], command)),
            settings=dict(cast(Mapping[str, object], settings)),
            timeout_seconds=float(timeout),
            max_cost_usd=None if cost is None else float(cost),
        )


@dataclass(frozen=True, slots=True)
class Tier0ExecutableSpec:
    """Path-free executable specification loaded from one frozen JSON blob."""

    experiment_id: str
    source_pin: HarveyLabPin
    evaluator_command: str
    evaluator_wrapper_sha256: str
    issuer_key_id: str
    issuer_policy_sha256: str
    arms: tuple[Tier0ArmSpec, ...]
    order: tuple[str, ...] = _ARM_IDS
    schema_version: str = TIER0_EXECUTABLE_SPEC_SCHEMA_VERSION
    artifact_sha256: str | None = field(default=None, repr=False, compare=False)
    loaded_record_sha256: str | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_text(self.experiment_id, "experiment_id")
        _require_executable_basename(self.evaluator_command, "evaluator_command")
        _require_digest(self.evaluator_wrapper_sha256, "evaluator_wrapper_sha256")
        _require_text(self.issuer_key_id, "issuer_key_id")
        _require_digest(self.issuer_policy_sha256, "issuer_policy_sha256")
        if self.schema_version != TIER0_EXECUTABLE_SPEC_SCHEMA_VERSION:
            raise Tier0RunnerError("unsupported Tier-0 executable spec schema")
        if tuple(arm.arm_id for arm in self.arms) != _ARM_IDS:
            raise Tier0RunnerError("executable spec must contain both opaque arms once")
        if self.order != _ARM_IDS:
            raise Tier0RunnerError(
                "executable spec order must be the frozen opaque order"
            )
        names = tuple(arm.adapter for arm in self.arms)
        if names != (CLAUDE_CODE_REGISTRY_NAME, HARVEY_LAB_REGISTRY_NAME):
            raise Tier0RunnerError(
                "executable spec must pair clean-native and native-thin"
            )

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "source_pin": self.source_pin.to_record(),
            "evaluator_command": self.evaluator_command,
            "evaluator_wrapper_sha256": self.evaluator_wrapper_sha256,
            "issuer_key_id": self.issuer_key_id,
            "issuer_policy_sha256": self.issuer_policy_sha256,
            "arms": [arm.to_record() for arm in self.arms],
            "order": list(self.order),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Tier0ExecutableSpec:
        _closed_record(
            record,
            required={
                "schema_version",
                "experiment_id",
                "source_pin",
                "evaluator_command",
                "evaluator_wrapper_sha256",
                "issuer_key_id",
                "issuer_policy_sha256",
                "arms",
                "order",
            },
            optional={"artifact_sha256"},
            field_name="Tier-0 executable spec",
        )
        pin = cast(Mapping[str, object], record["source_pin"])
        arms = record["arms"]
        order = record["order"]
        if not isinstance(arms, list) or any(
            not isinstance(item, Mapping) for item in cast(list[object], arms)
        ):
            raise Tier0RunnerError("arms must be an array of objects")
        if not isinstance(order, list) or any(
            not isinstance(item, str) for item in cast(list[object], order)
        ):
            raise Tier0RunnerError("order must be an array of strings")
        _closed_record(
            pin,
            required={"repository", "commit", "tree"},
            optional=set(),
            field_name="source pin",
        )
        try:
            source_pin = HarveyLabPin(
                repository=_text(pin, "repository"),
                commit=_text(pin, "commit"),
                tree=_text(pin, "tree"),
            )
        except ValueError as exc:
            raise Tier0RunnerError(str(exc)) from exc
        return cls(
            schema_version=_text(record, "schema_version"),
            experiment_id=_text(record, "experiment_id"),
            source_pin=source_pin,
            evaluator_command=_text(record, "evaluator_command"),
            evaluator_wrapper_sha256=_text(record, "evaluator_wrapper_sha256"),
            issuer_key_id=_text(record, "issuer_key_id"),
            issuer_policy_sha256=_text(record, "issuer_policy_sha256"),
            arms=tuple(
                Tier0ArmSpec.from_record(cast(Mapping[str, object], item))
                for item in cast(list[object], arms)
            ),
            order=tuple(cast(list[str], order)),
            artifact_sha256=(
                _digest(record["artifact_sha256"], "artifact_sha256")
                if "artifact_sha256" in record
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class Tier0SpendApproval:
    """Detached approval bound to the exact executable-spec blob."""

    approval_id: str
    spec_sha256: str
    status: str
    authority: str
    schema_version: str = TIER0_SPEND_APPROVAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_text(self.approval_id, "approval_id")
        _require_digest(self.spec_sha256, "spec_sha256")
        if self.status not in {"approved", "provider_free"}:
            raise Tier0RunnerError("detached approval status is not executable")
        _require_text(self.authority, "authority")
        if self.schema_version != TIER0_SPEND_APPROVAL_SCHEMA_VERSION:
            raise Tier0RunnerError("unsupported detached approval schema")

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> Tier0SpendApproval:
        _closed_record(
            record,
            required={
                "schema_version",
                "approval_id",
                "spec_sha256",
                "status",
                "authority",
            },
            optional=set(),
            field_name="detached approval",
        )
        return cls(
            schema_version=_text(record, "schema_version"),
            approval_id=_text(record, "approval_id"),
            spec_sha256=_text(record, "spec_sha256"),
            status=_text(record, "status"),
            authority=_text(record, "authority"),
        )


@dataclass(frozen=True, slots=True)
class Tier0ArmResult:
    """Private result handles and public score for one arm."""

    arm_id: str
    adapter: str
    auth_profile: str
    projection: HarveyLabProjectionResult
    solver_spec: Any
    solver_execution: ExecutionReceipt
    discovery: HarveyLabOutputDiscoveryResult
    evaluation: HarveyLabIsolatedEvaluation
    score: ScoreArtifact

    def public_record(self) -> dict[str, object]:
        return {
            "arm_id": self.arm_id,
            "adapter": self.adapter,
            "auth_profile": self.auth_profile,
            "projection_manifest_sha256": self.projection.manifest.manifest_sha256,
            "task_sha256": self.discovery.sealed.task_sha256,
            "solver_spec_sha256": self.solver_spec.spec_sha256,
            "solver_execution": self.solver_execution.to_public_record(),
            "discovery": self.discovery.to_record(),
            "evaluation_receipt": self.evaluation.receipt.to_record(),
            "score": self.score.to_record(),
        }


@dataclass(frozen=True, slots=True)
class Tier0RunResult:
    """Completed provider-free or externally authorized paired run."""

    spec_sha256: str
    approval: Tier0SpendApproval
    arms: tuple[Tier0ArmResult, Tier0ArmResult]
    archive_manifest: Path
    matched: bool


def load_executable_spec(
    path: Path, expected_sha256: str
) -> tuple[Tier0ExecutableSpec, str]:
    """Load a spec only when its exact file bytes match the supplied hash."""

    expected = _digest(expected_sha256, "expected spec hash")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise Tier0RunnerError(f"executable spec cannot be read: {path.name}") from exc
    actual = _hash_bytes(payload)
    if actual != expected:
        raise Tier0RunnerError("executable spec hash does not match the supplied hash")
    try:
        record = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Tier0RunnerError("executable spec must be UTF-8 JSON") from exc
    if not isinstance(record, Mapping):
        raise Tier0RunnerError("executable spec must be a JSON object")
    typed_record = cast(Mapping[str, object], record)
    embedded = typed_record.get("artifact_sha256")
    if embedded is not None and _digest(embedded, "artifact_sha256") != actual:
        raise Tier0RunnerError("artifact_sha256 does not match executable spec bytes")
    spec = Tier0ExecutableSpec.from_record(typed_record)
    return (
        replace(
            spec,
            artifact_sha256=actual,
            loaded_record_sha256=_record_hash(spec.to_record()),
        ),
        actual,
    )


def load_detached_approval(path: Path, *, spec_sha256: str) -> Tier0SpendApproval:
    """Load an approval and require its exact executable-spec binding."""

    try:
        record = read_json_object(
            path,
            error_factory=Tier0RunnerError,
            missing_message=lambda item: (
                f"detached approval does not exist: {item.name}"
            ),
            non_object_message=lambda item: (
                f"detached approval must be an object: {item.name}"
            ),
        )
    except json.JSONDecodeError as exc:
        raise Tier0RunnerError("detached approval must be valid JSON") from exc
    approval = Tier0SpendApproval.from_record(record)
    if _digest(approval.spec_sha256, "approval spec hash") != spec_sha256:
        raise Tier0RunnerError(
            "detached approval is bound to a different executable spec"
        )
    return approval


def load_approved_issuer_authority() -> IssuerAuthority:
    """Resolve the approved external issuer authority, never a local key.

    The authority module is intentionally supplied by the receipt-authority
    lane. Keeping this import lazy lets provider-free tests inject a fake
    authority without giving the runner a private-key or secret-loading path.
    """

    try:
        issuer_authority = importlib.import_module(
            "legalforecast.multiharness.issuer_authority"
        )
    except ImportError as exc:
        raise Tier0RunnerError(
            "approved external issuer authority is not installed"
        ) from exc
    loader = cast(
        Callable[[], IssuerAuthority],
        issuer_authority.load_approved_issuer_authority,
    )
    authority = loader()
    if not callable(getattr(authority, "sign", None)):
        raise Tier0RunnerError("issuer loader did not return an approved authority")
    return authority


def run_tier0(
    *,
    spec: Tier0ExecutableSpec,
    spec_sha256: str,
    approval: Tier0SpendApproval,
    source_root: Path,
    private_root: Path,
    archive_root: Path,
    authority: IssuerAuthority,
    parent_env: Mapping[str, str] | None = None,
) -> Tier0RunResult:
    """Execute both frozen arms and emit a hash-complete archive sidecar."""

    if _digest(spec_sha256, "spec hash") != spec_sha256:
        raise Tier0RunnerError("spec_sha256 must use the sha256: prefix")
    if spec.artifact_sha256 is None:
        raise Tier0RunnerError(
            "Tier-0 execution requires a spec loaded from its exact artifact bytes"
        )
    if spec.artifact_sha256 != spec_sha256:
        raise Tier0RunnerError("executable spec object is not bound to spec_sha256")
    if spec.loaded_record_sha256 is None:
        raise Tier0RunnerError(
            "Tier-0 execution requires the loaded executable-spec record"
        )
    if _record_hash(spec.to_record()) != spec.loaded_record_sha256:
        raise Tier0RunnerError("executable spec object was mutated after loading")
    if _digest(approval.spec_sha256, "approval spec hash") != spec_sha256:
        raise Tier0RunnerError("detached approval does not bind this executable spec")
    if approval.status not in {"approved", "provider_free"}:
        raise Tier0RunnerError("detached approval is not executable")
    if not callable(getattr(authority, "sign", None)):
        raise Tier0RunnerError("approved external issuer authority is required")
    _require_fresh_root(private_root, "private root")
    _require_fresh_root(archive_root, "archive root")
    if _overlap(private_root, archive_root):
        raise Tier0RunnerError("private and archive roots must be disjoint")

    registry = builtin_adapter_registry()
    for arm in spec.arms:
        registry.require_known(arm.adapter)
    _preflight_executables(spec, parent_env)
    _preflight_evaluator(spec, parent_env)

    private_root.mkdir(parents=True)
    archive_root.mkdir(parents=True)
    env = dict(os.environ if parent_env is None else parent_env)
    results: list[Tier0ArmResult] = []
    for arm in spec.arms:
        paths = _arm_paths(private_root, arm.arm_id)
        service = LocalCliExecutionService(
            auth_profile=arm.auth_profile,
            parent_env=env,
        )
        adapter = registry.get(
            arm.adapter,
            execution_service=service,
            parent_env=env,
            lab_command=arm.command,
            lab_root=source_root,
            timeout_seconds=arm.timeout_seconds,
        )
        if arm.adapter == CLAUDE_CODE_REGISTRY_NAME:
            if not isinstance(adapter, ClaudeCodeCliAdapter):
                raise Tier0RunnerError(
                    "registry returned the wrong clean-native adapter"
                )
            adapter = replace(adapter, auth_profile=arm.auth_profile)
            result = run_claude_code_clean_native_harvey_lab(
                adapter=adapter,
                source_root=source_root,
                solver_root=paths["solver"],
                evaluator_private_root=paths["evaluator_private"],
                sandbox_root=paths["sandbox"],
                sealed_root=paths["sealed"],
                quarantine_root=paths["quarantine"],
                overlay_root=paths["overlay"],
                evaluator_working_directory=paths["evaluator_work"],
                signer=authority.sign,
                issuer_public_key=authority.public_key,
                pin=spec.source_pin,
                model=arm.requested_model,
                timeout_seconds=arm.timeout_seconds,
                evaluator_command=spec.evaluator_command,
            )
            if (
                result.solver_execution.cost_usd is not None
                and arm.max_cost_usd is not None
                and result.solver_execution.cost_usd > arm.max_cost_usd
            ):
                raise Tier0RunnerError("clean-native solver exceeded its frozen budget")
            results.append(
                Tier0ArmResult(
                    arm_id=arm.arm_id,
                    adapter=arm.adapter,
                    auth_profile=arm.auth_profile,
                    projection=result.projection,
                    solver_spec=result.solver_spec,
                    solver_execution=result.solver_execution,
                    discovery=result.discovery,
                    evaluation=result.evaluation,
                    score=result.score,
                )
            )
        else:
            results.append(
                _run_native_thin(
                    arm=arm,
                    spec=spec,
                    source_root=source_root,
                    paths=paths,
                    service=service,
                    authority=authority,
                )
            )
    matched = _identities_match(results, spec)
    archive_manifest = _write_archive(
        spec=spec,
        spec_sha256=spec_sha256,
        approval=approval,
        results=tuple(results),
        archive_root=archive_root,
        matched=matched,
    )
    return Tier0RunResult(
        spec_sha256=spec_sha256,
        approval=approval,
        arms=(results[0], results[1]),
        archive_manifest=archive_manifest,
        matched=matched,
    )


def _run_native_thin(
    *,
    arm: Tier0ArmSpec,
    spec: Tier0ExecutableSpec,
    source_root: Path,
    paths: Mapping[str, Path],
    service: LocalCliExecutionService,
    authority: IssuerAuthority,
) -> Tier0ArmResult:
    projection = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=paths["solver"],
        evaluator_private_root=paths["evaluator_private"],
        pin=spec.source_pin,
        lab_task_ids=(ISSUE_196_LAB_TASK_ID,),
    )
    task = projection.manifest.tasks[0]
    if task.lab_task_id != ISSUE_196_LAB_TASK_ID:
        raise Tier0RunnerError("native-thin arm did not select the frozen LAB task")
    sandbox_root = paths["sandbox"]
    sandbox_root.mkdir(parents=True)
    output_root = sandbox_root / "output"
    resolved_output = require_harvey_lab_sandbox_hosts(
        sandbox_root=sandbox_root,
        output_root=output_root,
    )
    _copy_projection_task(projection.solver_root / task.relative_path, sandbox_root)
    argv = _render_command(
        arm.command,
        sandbox_root=sandbox_root,
        output_root=resolved_output,
    )
    solver_spec = RunSpec(
        spec_id=f"{spec.experiment_id}:{arm.arm_id}:solver",
        argv=argv,
        working_directory=sandbox_root.resolve(),
        timeout_seconds=arm.timeout_seconds,
    )
    execution = service.execute(solver_spec)
    if execution.status != "succeeded" or execution.returncode not in {0, None}:
        raise Tier0RunnerError("native-thin solver execution failed")
    discovery = discover_harvey_lab_outputs(
        sandbox_root=sandbox_root,
        output_root=resolved_output,
        quarantine_root=paths["quarantine"],
        sealed_root=paths["sealed"],
        task=task,
        task_sha256=_prefixed(task.task_sha256),
        run_sha256=solver_spec.spec_sha256,
        config_sha256=_settings_digest(arm.settings),
        layout="native",
        evaluator_private_root=paths["evaluator_private"],
        projection_root=projection.solver_root,
    )
    identity = HarveyLabEvaluationIdentity(
        lab_task_id=task.lab_task_id,
        task_sha256=_prefixed(task.task_sha256),
        expected_deliverable_basename=task.expected_deliverable,
        projection_manifest_sha256=projection.manifest.manifest_sha256,
        wrapper_sha256=spec.evaluator_wrapper_sha256,
        run_sha256=solver_spec.spec_sha256,
        config_sha256=_settings_digest(arm.settings),
        pin=projection.manifest.pin,
    )
    evaluation = invoke_isolated_harvey_lab_evaluator(
        hosts=HarveyLabEvaluationHosts(
            sealed_deliverable_root=paths["sealed"],
            evaluator_private_root=paths["evaluator_private"],
            overlay_root=paths["overlay"],
            working_directory=paths["evaluator_work"],
            solver_projection_root=projection.solver_root,
        ),
        sealed_manifest=discovery.sealed,
        identity=identity,
        execution_service=service,
        signer=authority.sign,
        issuer_key_id=spec.issuer_key_id,
        issuer_policy_sha256=spec.issuer_policy_sha256,
        evaluator_command=spec.evaluator_command,
        timeout_seconds=arm.timeout_seconds,
    )
    metric = build_harvey_lab_metric_definition(
        rubric_sha256=evaluation.spec.rubric_sha256,
        criteria_sha256=evaluation.spec.criteria_sha256,
        aggregation_sha256=evaluation.spec.aggregation_sha256,
        output_schema_sha256=evaluation.spec.judge_output_schema_sha256,
    )
    score = verify_authorized_harvey_lab_receipt(
        evaluation.receipt.to_record(),
        raw_result=evaluation.raw_result,
        spec=evaluation.spec,
        metric=metric,
        issuer_public_key=authority.public_key,
        expected_measurement_id=evaluation.receipt.measurement_id,
        expected_evaluation_attempt_id=evaluation.receipt.evaluation_attempt_id,
        expected_attempt_nonce=evaluation.receipt.attempt_nonce,
        expected_repeat_index=evaluation.receipt.repeat_index,
        expected_deliverable_manifest_sha256=discovery.sealed.manifest_sha256,
        expected_runtime_policy_sha256=evaluation.spec.runtime_policy_sha256,
    )
    if execution.cost_usd is not None and arm.max_cost_usd is not None:
        if execution.cost_usd > arm.max_cost_usd:
            raise Tier0RunnerError("native-thin solver exceeded its frozen budget")
    return Tier0ArmResult(
        arm_id=arm.arm_id,
        adapter=arm.adapter,
        auth_profile=arm.auth_profile,
        projection=projection,
        solver_spec=solver_spec,
        solver_execution=execution,
        discovery=discovery,
        evaluation=evaluation,
        score=score,
    )


def _copy_projection_task(source: Path, sandbox_root: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        raise Tier0RunnerError("projected LAB task must be a real directory")
    destination = sandbox_root / source.relative_to(source.parents[1])
    if destination.exists() or destination.is_symlink():
        raise Tier0RunnerError("native-thin sandbox task destination is not fresh")
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_symlink() or (not item.is_dir() and not item.is_file()):
            raise Tier0RunnerError("projected LAB task contains an unsafe entry")
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target, follow_symlinks=False)


def _preflight_executables(
    spec: Tier0ExecutableSpec, parent_env: Mapping[str, str] | None
) -> None:
    for arm in spec.arms:
        path = _resolve_on_path(arm.solver_executable, parent_env)
        if _hash_file(path) != arm.solver_executable_sha256:
            raise Tier0RunnerError(
                f"{arm.arm_id} solver executable hash does not match spec"
            )


def _preflight_evaluator(
    spec: Tier0ExecutableSpec, parent_env: Mapping[str, str] | None
) -> None:
    path = _resolve_on_path(spec.evaluator_command, parent_env)
    if _hash_file(path) != spec.evaluator_wrapper_sha256:
        raise Tier0RunnerError("evaluator wrapper hash does not match executable spec")
    if spec.issuer_key_id != HARVEY_LAB_EVALUATOR_ISSUER_KEY_ID:
        raise Tier0RunnerError("issuer key ID is not the authorized LAB issuer")
    if spec.issuer_policy_sha256 != harvey_lab_issuer_policy_sha256():
        raise Tier0RunnerError(
            "issuer policy hash does not match the authorized policy"
        )


def _resolve_on_path(name: str, parent_env: Mapping[str, str] | None) -> Path:
    _require_executable_basename(name, "executable")
    path = shutil.which(name, path=(parent_env or os.environ).get("PATH", "/usr/bin"))
    if path is None:
        raise Tier0RunnerError(f"executable is not on PATH: {name}")
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise Tier0RunnerError(f"executable is not a regular file: {name}")
    mode = candidate.stat().st_mode
    if not (mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
        raise Tier0RunnerError(f"executable is not executable: {name}")
    return candidate


def _arm_paths(private_root: Path, arm_id: str) -> dict[str, Path]:
    arm = private_root / arm_id
    return {
        "solver": arm / "solver",
        "evaluator_private": arm / "evaluator-private",
        "sandbox": arm / "scratch",
        "output": arm / "output",
        "quarantine": arm / "quarantine",
        "sealed": arm / "sealed",
        "overlay": private_root / "evaluator" / "overlay" / arm_id,
        "evaluator_work": private_root / "evaluator" / "work" / arm_id,
    }


def _render_command(
    command: Sequence[str], *, sandbox_root: Path, output_root: Path
) -> tuple[str, ...]:
    values = {"{sandbox_root}": str(sandbox_root), "{output_root}": str(output_root)}
    rendered = tuple(values.get(token, token) for token in command)
    if not rendered or any(not item for item in rendered):
        raise Tier0RunnerError("native-thin command is empty")
    if any(item in {"sh", "bash"} for item in rendered):
        raise Tier0RunnerError("native-thin command must not invoke a shell")
    return rendered


def _identities_match(
    results: Sequence[Tier0ArmResult], spec: Tier0ExecutableSpec
) -> bool:
    if len(results) != 2:
        return False
    try:
        verified_manifests = tuple(
            verify_harvey_lab_projection(item.projection.solver_root)
            for item in results
        )
    except (OSError, ValueError):
        return False
    if any(
        verified.to_record() != item.projection.manifest.to_record()
        for verified, item in zip(verified_manifests, results, strict=True)
    ):
        return False
    if verified_manifests[0].to_record() != verified_manifests[1].to_record():
        return False
    task_identities = tuple(
        tuple(
            (
                task.task_id,
                task.lab_task_id,
                task.category,
                task.relative_path,
                task.task_sha256,
                task.expected_deliverable,
                tuple(tuple(sorted(file.to_record().items())) for file in task.files),
            )
            for task in manifest.tasks
        )
        for manifest in verified_manifests
    )
    if task_identities[0] != task_identities[1]:
        return False
    try:
        solver_content = tuple(
            _solver_visible_content_identity(item.projection.solver_root)
            for item in results
        )
    except (OSError, ValueError):
        return False
    if solver_content[0] != solver_content[1]:
        return False
    if results[0].auth_profile != results[1].auth_profile:
        return False
    solver_models = tuple(item.solver_execution.served_model for item in results)
    requested = tuple(arm.requested_model for arm in spec.arms)
    if any(value is None for value in solver_models) or requested[0] != requested[1]:
        return False
    if solver_models[0] != solver_models[1] or solver_models[0] != requested[0]:
        return False
    if _settings_digest(spec.arms[0].settings) != _settings_digest(
        spec.arms[1].settings
    ):
        return False
    if _evaluation_contract_identity(results[0]) != _evaluation_contract_identity(
        results[1]
    ):
        return False
    return all(
        item.evaluation.receipt.judge_resolved_identity
        == results[0].evaluation.receipt.judge_resolved_identity
        for item in results
    )


def _solver_visible_content_identity(root: Path) -> tuple[tuple[str, str, int], ...]:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or root.is_symlink():
        raise Tier0RunnerError("solver projection root is not a real directory")
    entries: list[tuple[str, str, int]] = []
    for path in sorted(resolved.rglob("*")):
        if path.is_symlink():
            raise Tier0RunnerError("solver projection contains a symlink")
        if path.is_file():
            relative = path.relative_to(resolved).as_posix()
            entries.append((relative, _hash_file(path), path.stat().st_size))
    return tuple(entries)


def _evaluation_contract_identity(
    result: Tier0ArmResult,
) -> tuple[object, ...]:
    spec = result.evaluation.spec
    return tuple(
        getattr(spec, field_name)
        for field_name in (
            "schema_version",
            "evaluation_id",
            "evaluator_repository",
            "evaluator_commit",
            "evaluator_tree",
            "evaluator_file_manifest_sha256",
            "evaluator_image_digest",
            "wrapper_sha256",
            "rubric_sha256",
            "criteria_sha256",
            "aggregation_sha256",
            "judge_requested_identity",
            "judge_settings_sha256",
            "judge_prompt_sha256",
            "judge_output_schema_sha256",
            "runtime_policy_sha256",
            "egress_policy_sha256",
            "resource_policy_sha256",
            "token_accounting_policy_sha256",
        )
    )


def _write_archive(
    *,
    spec: Tier0ExecutableSpec,
    spec_sha256: str,
    approval: Tier0SpendApproval,
    results: tuple[Tier0ArmResult, ...],
    archive_root: Path,
    matched: bool,
) -> Path:
    private = archive_root / "private"
    public = archive_root / "public"
    private.mkdir()
    public.mkdir()
    public_record: dict[str, object] = {
        # contract-ratchet: allow non-authoritative Tier-0 sidecar
        "schema_version": "legalforecast.multiharness.tier0_public_summary.v1",
        "spec_sha256": spec_sha256,
        "experiment_id": spec.experiment_id,
        "claim_language": (
            "matched observed paired difference"
            if matched
            else "system-bundle / plumbing-only; matched identity was not established"
        ),
        "matched": matched,
        "arms": [
            {
                "arm_id": result.arm_id,
                "adapter": result.adapter,
                "auth_profile": result.auth_profile,
                "projection_manifest_sha256": (
                    result.projection.manifest.manifest_sha256
                ),
                "solver_execution": result.solver_execution.to_public_record(),
                "evaluation_receipt": result.evaluation.receipt.to_record(),
                "score": result.score.to_record(),
            }
            for result in results
        ],
    }
    write_json_object(public / "summary.json", public_record)
    write_json_object(
        private / "executable-spec.json",
        {**spec.to_record(), "artifact_sha256": spec_sha256},
    )
    write_json_object(
        private / "detached-approval.json",
        {
            "schema_version": approval.schema_version,
            "approval_id": approval.approval_id,
            "spec_sha256": approval.spec_sha256,
            "status": approval.status,
            "authority": approval.authority,
        },
    )
    for result in results:
        arm_private = private / result.arm_id
        arm_private.mkdir()
        write_json_object(
            arm_private / "solver-execution.json",
            result.solver_execution.to_record(),
        )
        write_json_object(arm_private / "discovery.json", result.discovery.to_record())
        write_json_object(
            arm_private / "evaluation-receipt.json",
            result.evaluation.receipt.to_record(),
        )
        write_json_object(arm_private / "score.json", result.score.to_record())
        write_json_object(
            arm_private / "projection-manifest.json",
            result.projection.manifest.to_record(),
        )
    entries: list[dict[str, object]] = []
    for path in sorted(item for item in archive_root.rglob("*") if item.is_file()):
        relative = path.relative_to(archive_root).as_posix()
        entries.append(
            {
                "path": relative,
                "sha256": _hash_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    manifest: dict[str, object] = {
        "schema_version": TIER0_ARCHIVE_MANIFEST_SCHEMA_VERSION,
        "experiment_id": spec.experiment_id,
        "spec_sha256": spec_sha256,
        "approval_id": approval.approval_id,
        "matched": matched,
        "files": entries,
    }
    manifest_path = archive_root / "archive-manifest.json"
    write_json_object(manifest_path, manifest)
    return manifest_path


def _require_fresh_root(path: Path, label: str) -> None:
    if path.exists() or path.is_symlink():
        raise Tier0RunnerError(f"{label} must be a fresh, absent path")
    if not path.parent.exists() or path.parent.is_symlink():
        raise Tier0RunnerError(f"{label} parent must be a real directory")


def _overlap(first: Path, second: Path) -> bool:
    a, b = first.resolve(strict=False), second.resolve(strict=False)
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def _settings_digest(settings: Mapping[str, object]) -> str:
    payload = json.dumps(
        dict(settings), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return _hash_bytes(payload)


def _record_hash(record: Mapping[str, object]) -> str:
    payload = json.dumps(
        dict(record), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return _hash_bytes(payload)


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _hash_bytes(payload: bytes) -> str:
    return _DIGEST_PREFIX + hashlib.sha256(payload).hexdigest()


def _prefixed(value: str) -> str:
    return value if value.startswith(_DIGEST_PREFIX) else _DIGEST_PREFIX + value


def _digest(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise Tier0RunnerError(f"{field_name} must be a SHA-256 digest")
    normalized = _prefixed(value)
    try:
        validate_sha256(normalized, field_name)
    except MultiHarnessValidationError as exc:
        raise Tier0RunnerError(str(exc)) from exc
    return normalized


def _require_digest(value: str, field_name: str) -> None:
    _digest(value, field_name)


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise Tier0RunnerError(f"{field_name} must be a non-empty string")


def _text(record: Mapping[str, object], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str):
        raise Tier0RunnerError(f"{field_name} must be a string")
    return value


def _require_executable_basename(value: str, field_name: str) -> None:
    _require_text(value, field_name)
    if "/" in value or "\\" in value or value in {".", ".."}:
        raise Tier0RunnerError(f"{field_name} must be a basename")


def _closed_record(
    record: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str],
    field_name: str,
) -> None:
    missing = sorted(required - set(record))
    extra = sorted(set(record) - required - optional)
    if missing:
        raise Tier0RunnerError(f"{field_name} is missing: {', '.join(missing)}")
    if extra:
        raise Tier0RunnerError(
            f"{field_name} contains unsupported fields: {', '.join(extra)}"
        )
