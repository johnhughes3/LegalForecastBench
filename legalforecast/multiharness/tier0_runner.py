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
import json
import os
import shutil
import stat
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
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
    EvaluatorRunner,
    HarveyLabEvaluationHosts,
    HarveyLabEvaluationIdentity,
    HarveyLabIsolatedEvaluation,
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
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
from legalforecast.multiharness.local_cli_identity import (
    ObservedExecutableIdentity,
    verify_executable_digest,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.receipt_authority import (
    EvaluatorIssuerAuthority,
    ReceiptAuthorityError,
)
from legalforecast.multiharness.run_metadata import (
    BinaryRunIdentity,
    PrivateRunMetadata,
    ReceiptMetadataBinding,
    RunMetadataError,
    bind_execution_receipt,
    build_private_run_metadata,
    write_private_run_metadata,
)
from legalforecast.multiharness.scoring import (
    ScoreArtifact,
    build_harvey_lab_metric_definition,
)
from legalforecast.multiharness.spend import (
    JudgeCriterionCeiling,
    PaidCall,
    PricingSnapshot,
    SpendConfigurationError,
    SpendController,
    SpendDeniedError,
    SpendPolicy,
    SpendReservation,
    SpendSettlementError,
    UsageObservation,
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
_ALLOWED_COMMAND_TOKENS = frozenset(
    {"{sandbox_root}", "{output_root}", "{max_cost_usd}"}
)
_DIGEST_PREFIX = "sha256:"
_DEFAULT_ISSUER_CONFIG = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "adapters"
    / "harvey-lab"
    / "evaluator-issuer-authority.json"
)
_HARVEY_LAB_JUDGE_CRITERION_COUNT = 23


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
    solver_executable_version: str | None = None
    version_probe_args: tuple[str, ...] = ()

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
        if self.solver_executable_version is not None:
            _require_text(self.solver_executable_version, "solver_executable_version")
            if not self.version_probe_args:
                raise Tier0RunnerError(
                    "version_probe_args are required for a pinned executable version"
                )
        for value in self.version_probe_args:
            if not value:
                raise Tier0RunnerError(
                    "version_probe_args must contain non-empty strings"
                )
        if self.timeout_seconds <= 0:
            raise Tier0RunnerError("timeout_seconds must be positive")
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
        if self.solver_executable_version is not None:
            record["solver_executable_version"] = self.solver_executable_version
        if self.version_probe_args:
            record["version_probe_args"] = list(self.version_probe_args)
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
            optional={"solver_executable_version", "version_probe_args"},
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
        probe_args = record.get("version_probe_args")
        if probe_args is None:
            parsed_probe_args: tuple[str, ...] = ()
        elif not isinstance(probe_args, list) or any(
            not isinstance(item, str) for item in cast(list[object], probe_args)
        ):
            raise Tier0RunnerError("version_probe_args must be an array of strings")
        else:
            parsed_probe_args = tuple(cast(list[str], probe_args))
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
            solver_executable_version=(
                None
                if record.get("solver_executable_version") is None
                else _text(record, "solver_executable_version")
            ),
            version_probe_args=parsed_probe_args,
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
    pricing_snapshot_sha256: str | None = None
    spend_policy_sha256: str | None = None
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
        if self.pricing_snapshot_sha256 is not None:
            _require_digest(self.pricing_snapshot_sha256, "pricing_snapshot_sha256")
        if self.spend_policy_sha256 is not None:
            _require_digest(self.spend_policy_sha256, "spend_policy_sha256")
        names = tuple(arm.adapter for arm in self.arms)
        if names != (CLAUDE_CODE_REGISTRY_NAME, HARVEY_LAB_REGISTRY_NAME):
            raise Tier0RunnerError(
                "executable spec must pair clean-native and native-thin"
            )

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
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
        if self.pricing_snapshot_sha256 is not None:
            record["pricing_snapshot_sha256"] = self.pricing_snapshot_sha256
        if self.spend_policy_sha256 is not None:
            record["spend_policy_sha256"] = self.spend_policy_sha256
        return record

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
            optional={
                "artifact_sha256",
                "pricing_snapshot_sha256",
                "spend_policy_sha256",
            },
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
            pricing_snapshot_sha256=(
                None
                if record.get("pricing_snapshot_sha256") is None
                else _digest(
                    record["pricing_snapshot_sha256"], "pricing_snapshot_sha256"
                )
            ),
            spend_policy_sha256=(
                None
                if record.get("spend_policy_sha256") is None
                else _digest(record["spend_policy_sha256"], "spend_policy_sha256")
            ),
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
    run_metadata: PrivateRunMetadata | None = field(default=None, repr=False)
    receipt_metadata_binding: ReceiptMetadataBinding | None = field(
        default=None, repr=False
    )

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


def load_spend_artifacts(
    spec_path: Path,
    spec: Tier0ExecutableSpec,
) -> tuple[SpendPolicy, PricingSnapshot]:
    """Load deterministic sibling sidecars bound by the executable spec."""

    if spec.pricing_snapshot_sha256 is None:
        raise Tier0RunnerError("executable spec must bind the pricing sidecar hash")
    if spec.spend_policy_sha256 is None:
        raise Tier0RunnerError("executable spec must bind the spend policy hash")
    pricing_path = spec_path.with_name(f"{spec_path.stem}.pricing-snapshot.json")
    policy_path = spec_path.with_name(f"{spec_path.stem}.spend-policy.json")
    try:
        pricing_record = read_json_object(
            pricing_path,
            error_factory=Tier0RunnerError,
            missing_message=lambda path: (
                f"pricing snapshot does not exist: {path.name}"
            ),
            non_object_message=lambda path: (
                f"pricing snapshot must be an object: {path.name}"
            ),
        )
        policy_record = read_json_object(
            policy_path,
            error_factory=Tier0RunnerError,
            missing_message=lambda path: f"spend policy does not exist: {path.name}",
            non_object_message=lambda path: (
                f"spend policy must be an object: {path.name}"
            ),
        )
        pricing = PricingSnapshot.from_record(pricing_record)
        policy = SpendPolicy.from_record(policy_record)
    except (SpendConfigurationError, json.JSONDecodeError) as exc:
        raise Tier0RunnerError("pricing or spend sidecar is invalid") from exc
    if pricing.snapshot_sha256 != spec.pricing_snapshot_sha256:
        raise Tier0RunnerError("pricing sidecar hash does not match executable spec")
    # The detached approval binds only the spec, so the ceilings are authorized
    # solely through this digest.  Without it an operator could raise the
    # request and dollar caps after approval and still pass every other check.
    if policy.policy_sha256 != spec.spend_policy_sha256:
        raise Tier0RunnerError("spend policy hash does not match executable spec")
    if policy.pricing_snapshot_sha256 != pricing.snapshot_sha256:
        raise Tier0RunnerError("spend policy does not bind the pricing sidecar")
    if policy.experiment_id != spec.experiment_id:
        raise Tier0RunnerError("spend policy experiment does not match executable spec")
    if policy.executable_spec_sha256 != spec.artifact_sha256:
        raise Tier0RunnerError("spend policy does not bind the executable artifact")
    try:
        policy.validate_before_credentials(pricing)
    except SpendConfigurationError as exc:
        raise Tier0RunnerError("spend policy is not executable") from exc
    return policy, pricing


def load_approved_issuer_authority(
    *,
    secret_loader: Callable[[str, str, str], str | bytes] | None = None,
    config_path: Path = _DEFAULT_ISSUER_CONFIG,
) -> IssuerAuthority:
    """Load public issuer config and attach only an injected secret wrapper.

    The runner never discovers credentials.  A supported operator wrapper must
    provide ``secret_loader`` explicitly; ambient environment and ``.env``
    fallbacks are intentionally absent.  Pending public configuration fails
    before the callback can be invoked.
    """

    try:
        authority = EvaluatorIssuerAuthority.from_json_file(config_path)
        if authority.status != "configured":
            raise Tier0RunnerError(
                "evaluator issuer authority is pending human provisioning"
            )
        if secret_loader is None:
            raise Tier0RunnerError(
                "approved issuer requires an injected Infisical wrapper callback"
            )
        return authority.with_signing_secret_loader(secret_loader)
    except (ReceiptAuthorityError, OSError) as exc:
        raise Tier0RunnerError(
            "approved evaluator issuer authority is unavailable"
        ) from exc


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
    spend_policy: SpendPolicy | None = None,
    pricing_snapshot: PricingSnapshot | None = None,
    evaluator_runner: EvaluatorRunner | None = None,
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
    if spec.pricing_snapshot_sha256 is not None:
        if spend_policy is None or pricing_snapshot is None:
            raise Tier0RunnerError(
                "executable Tier-0 runs require loaded spend and pricing sidecars"
            )
        if spec.spend_policy_sha256 is None:
            raise Tier0RunnerError(
                "executable Tier-0 runs require a spend policy hash binding"
            )
        if spec.pricing_snapshot_sha256 != pricing_snapshot.snapshot_sha256:
            raise Tier0RunnerError("pricing snapshot does not match executable spec")
        if spend_policy.policy_sha256 != spec.spend_policy_sha256:
            raise Tier0RunnerError("spend policy hash does not match executable spec")
        if spend_policy.executable_spec_sha256 != spec_sha256:
            raise Tier0RunnerError("spend policy does not bind executable spec")
        try:
            controller: SpendController | None = SpendController(
                spend_policy, pricing_snapshot
            )
        except SpendConfigurationError as exc:
            raise Tier0RunnerError("spend policy is not executable") from exc
    elif approval.status == "approved":
        raise Tier0RunnerError(
            "approved Tier-0 runs require pricing and spend sidecar bindings"
        )
    else:
        # Legacy provider-free fixtures do not make paid requests.  Production
        # artifacts always take the controller branch above.
        controller = None
    if controller is not None:
        if evaluator_runner is None:
            raise Tier0RunnerError(
                "paid evaluator requires an injected per-criterion evaluator runner"
            )
        for arm in spec.arms:
            _judge_ceilings_for(controller.policy, arm.arm_id)
    try:
        authority_public_key = authority.public_key
    except Exception as exc:
        raise Tier0RunnerError(
            "approved evaluator issuer public key is unavailable"
        ) from exc
    _require_fresh_root(private_root, "private root")
    _require_fresh_root(archive_root, "archive root")
    if _overlap(private_root, archive_root):
        raise Tier0RunnerError("private and archive roots must be disjoint")

    registry = builtin_adapter_registry()
    for arm in spec.arms:
        registry.require_known(arm.adapter)
    executable_identities = _preflight_executables(spec, parent_env)
    _preflight_evaluator(spec, parent_env)

    private_root.mkdir(parents=True)
    archive_root.mkdir(parents=True)
    env = dict(os.environ if parent_env is None else parent_env)
    results: list[Tier0ArmResult] = []
    partial_metadata: dict[str, PrivateRunMetadata] = {}
    partial_capabilities: dict[str, object] = {}
    # Every reservation that has been taken but not yet settled.  A paid call
    # can fail after the provider was invoked (evaluator timeout, nonzero exit,
    # adapter error), and those paths must not leave the reservation dangling
    # with neither an observed nor an unknown cost recorded against it.
    outstanding = _OutstandingReservations()
    evaluator_boundaries = (
        {
            arm.arm_id: _PerCriterionEvaluatorSpendBoundary(
                controller=controller,
                spec=spec,
                arm=arm,
                outstanding=outstanding,
            )
            for arm in spec.arms
        }
        if controller is not None
        else {}
    )
    try:
        for arm in spec.arms:
            paths = _arm_paths(private_root, arm.arm_id)
            ceiling = _solver_ceiling(controller, arm)
            reservation = _reserve_solver(
                controller,
                spec=spec,
                arm=arm,
                ceiling=ceiling,
            )
            _track_reservation(outstanding, reservation)
            metadata_ref: dict[str, object] = {}
            binding_ref: dict[str, object] = {}
            capability_ref: dict[str, object] = {}

            def before_solver(
                run_spec: RunSpec,
                *,
                _arm: Tier0ArmSpec = arm,
                _paths: Mapping[str, Path] = paths,
                _metadata_ref: dict[str, object] = metadata_ref,
                _capability_ref: dict[str, object] = capability_ref,
            ) -> None:
                metadata = _start_run_metadata(
                    spec=spec,
                    spec_sha256=spec_sha256,
                    arm=_arm,
                    run_spec=run_spec,
                    paths=_paths,
                    executable_identity=executable_identities[_arm.arm_id],
                    spend_policy=spend_policy,
                    pricing_snapshot=pricing_snapshot,
                    capability_record=_capability_ref.get("value"),
                )
                _metadata_ref["value"] = metadata
                partial_metadata[_arm.arm_id] = metadata
                partial_capabilities[_arm.arm_id] = _capability_ref.get("value")
                write_private_run_metadata(_paths["metadata"], metadata)
                write_json_object(
                    _paths["capability"],
                    {
                        "schema_version": (
                            # contract-ratchet: allow capability sidecar
                            "legalforecast.multiharness.tier0_capability.v1"
                        ),
                        "arm_id": _arm.arm_id,
                        "adapter": _arm.adapter,
                        "run_spec_sha256": run_spec.spec_sha256,
                        "metadata_sha256": metadata.metadata_sha256,
                        "capability": _capability_ref.get("value"),
                    },
                )

            def after_solver(
                run_spec: RunSpec,
                execution: ExecutionReceipt,
                *,
                _metadata_ref: dict[str, object] = metadata_ref,
                _binding_ref: dict[str, object] = binding_ref,
                _reservation: Any | None = reservation,
            ) -> ExecutionReceipt:
                metadata_value = _metadata_ref.get("value")
                if not isinstance(metadata_value, PrivateRunMetadata):
                    raise Tier0RunnerError(
                        "solver metadata was not created before execution"
                    )
                metadata = metadata_value
                if controller is not None and _reservation is not None:
                    _release_reservation(outstanding, _reservation)
                    _settle_solver(
                        controller, _reservation, execution, pricing_snapshot
                    )
                bound = replace(execution, config_sha256=metadata.config_sha256)
                try:
                    binding = bind_execution_receipt(bound, metadata)
                except RunMetadataError as exc:
                    raise Tier0RunnerError(
                        "solver receipt metadata binding failed"
                    ) from exc
                _binding_ref["value"] = binding
                return bound

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
                capability_ref["value"] = {
                    "manifest": adapter.local_manifest.to_record(),
                    "executable": {
                        "name": arm.solver_executable,
                        "sha256": arm.solver_executable_sha256,
                        "version": arm.solver_executable_version,
                    },
                }
                if ceiling is None and controller is None:
                    max_budget = None
                else:
                    assert ceiling is not None
                    max_budget = ceiling.invocation_budget.argument_value_usd
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
                    issuer_public_key=authority_public_key,
                    pin=spec.source_pin,
                    model=arm.requested_model,
                    timeout_seconds=arm.timeout_seconds,
                    evaluator_command=spec.evaluator_command,
                    max_budget_usd=max_budget,
                    before_solver=before_solver,
                    after_solver=after_solver,
                    judge_request_boundary=evaluator_boundaries.get(arm.arm_id),
                    evaluator_runner=evaluator_runner,
                )
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
                        run_metadata=cast(
                            PrivateRunMetadata, metadata_ref.get("value")
                        ),
                        receipt_metadata_binding=cast(
                            ReceiptMetadataBinding, binding_ref.get("value")
                        ),
                    )
                )
            else:
                capability_ref["value"] = {
                    "command": list(arm.command),
                    "executable": {
                        "name": arm.solver_executable,
                        "sha256": arm.solver_executable_sha256,
                        "version": arm.solver_executable_version,
                    },
                }
                results.append(
                    _run_native_thin(
                        arm=arm,
                        spec=spec,
                        source_root=source_root,
                        paths=paths,
                        service=service,
                        authority=authority,
                        max_cost_usd=(
                            None if ceiling is None else ceiling.max_cost_usd
                        ),
                        budget_argument_name=(
                            None
                            if ceiling is None
                            else ceiling.invocation_budget.argument_name
                        ),
                        before_solver=before_solver,
                        after_solver=after_solver,
                        judge_request_boundary=evaluator_boundaries.get(arm.arm_id),
                        evaluator_runner=evaluator_runner,
                    )
                )
            arm_boundary = evaluator_boundaries.get(arm.arm_id)
            if arm_boundary is not None:
                arm_boundary.require_every_criterion_settled()
    except Exception as exc:
        _terminalize_outstanding(controller, outstanding, str(exc))
        _write_archive(
            spec=spec,
            spec_sha256=spec_sha256,
            approval=approval,
            results=tuple(results),
            archive_root=archive_root,
            matched=False,
            spend_controller=controller,
            terminal_error=str(exc),
            partial_metadata=partial_metadata,
            partial_capabilities=partial_capabilities,
            authority_record=_authority_record(authority),
        )
        raise Tier0RunnerError(str(exc)) from exc
    matched = _identities_match(results, spec)
    archive_manifest = _write_archive(
        spec=spec,
        spec_sha256=spec_sha256,
        approval=approval,
        results=tuple(results),
        archive_root=archive_root,
        matched=matched,
        spend_controller=controller,
        partial_metadata=partial_metadata,
        partial_capabilities=partial_capabilities,
        authority_record=_authority_record(authority),
    )
    return Tier0RunResult(
        spec_sha256=spec_sha256,
        approval=approval,
        arms=(results[0], results[1]),
        archive_manifest=archive_manifest,
        matched=matched,
    )


class _OutstandingReservations:
    """Thread-safe ledger of reservations not yet handed to ``settle``."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._values: dict[str, SpendReservation] = {}

    def add(self, reservation: SpendReservation) -> None:
        with self._lock:
            self._values[reservation.reservation_id] = reservation

    def remove(self, reservation: SpendReservation) -> None:
        with self._lock:
            self._values.pop(reservation.reservation_id, None)

    def snapshot(self) -> tuple[SpendReservation, ...]:
        with self._lock:
            return tuple(self._values.values())

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


def _track_reservation(
    outstanding: _OutstandingReservations | dict[str, Any],
    reservation: SpendReservation | None,
) -> None:
    """Remember a reservation until it has been settled or terminalized."""

    if reservation is not None:
        if isinstance(outstanding, _OutstandingReservations):
            outstanding.add(reservation)
        else:
            outstanding[reservation.reservation_id] = reservation


def _release_reservation(
    outstanding: _OutstandingReservations | dict[str, Any], reservation: Any
) -> None:
    """Forget a reservation that is about to be handed to ``settle``.

    ``SpendController.settle`` consumes the reservation before it can fail, so
    the entry is dropped first; a failed settlement already carries its own
    terminal evidence and must not be settled a second time.
    """

    if isinstance(outstanding, _OutstandingReservations):
        outstanding.remove(reservation)
    else:
        outstanding.pop(reservation.reservation_id, None)


def _terminalize_outstanding(
    controller: SpendController | None,
    outstanding: _OutstandingReservations | dict[str, Any],
    reason: str,
) -> None:
    """Record unknown cost for every reservation left open by a failure.

    A paid call can fail after the provider was invoked, so an unsettled
    reservation is not evidence that nothing was spent.  Settling it as unknown
    cost makes the controller terminal and keeps the denial evidence in the
    archive instead of silently dropping the request.
    """

    if controller is None:
        if isinstance(outstanding, _OutstandingReservations):
            outstanding.clear()
        else:
            outstanding.clear()
        return
    reservations = (
        outstanding.snapshot()
        if isinstance(outstanding, _OutstandingReservations)
        else tuple(outstanding.values())
    )
    for reservation in reservations:
        try:
            controller.settle(reservation, UsageObservation.unknown(reason))
        except (SpendSettlementError, SpendConfigurationError):
            # ``settle`` records the evidence before it raises, and the caller
            # is already unwinding a terminal failure.
            pass
    outstanding.clear()


def _solver_ceiling(
    controller: SpendController | None,
    arm: Tier0ArmSpec,
) -> Any | None:
    if controller is None:
        return None
    try:
        ceiling = controller.policy.solver_for(arm.arm_id)
    except SpendConfigurationError as exc:
        raise Tier0RunnerError(
            f"missing solver spend ceiling for {arm.arm_id}"
        ) from exc
    if ceiling.model != arm.requested_model:
        raise Tier0RunnerError(
            f"solver model does not match spend policy for {arm.arm_id}"
        )
    if ceiling.invocation_budget.mode != "adapter_argument":
        raise Tier0RunnerError(
            f"solver budget is not mechanically enforced for {arm.arm_id}"
        )
    return ceiling


def _reserve_solver(
    controller: SpendController | None,
    *,
    spec: Tier0ExecutableSpec,
    arm: Tier0ArmSpec,
    ceiling: Any | None,
) -> Any | None:
    if controller is None:
        return None
    assert ceiling is not None
    try:
        return controller.reserve(
            PaidCall(
                call_id=f"{arm.arm_id}-solver-0",
                surface="solver",
                arm_id=arm.arm_id,
                provider=ceiling.provider,
                model=ceiling.model,
                executable_spec_sha256=spec.artifact_sha256 or "",
                pricing_snapshot_sha256=controller.pricing.snapshot_sha256,
            )
        )
    except (SpendDeniedError, SpendConfigurationError) as exc:
        raise Tier0RunnerError(
            f"solver spend reservation denied for {arm.arm_id}"
        ) from exc


def _judge_ceilings_for(
    policy: SpendPolicy, arm_id: str
) -> tuple[JudgeCriterionCeiling, ...]:
    """Return judge ceilings in policy tuple order, one for each LAB criterion."""

    ceilings = tuple(item for item in policy.judge_ceilings if item.arm_id == arm_id)
    if len(ceilings) != _HARVEY_LAB_JUDGE_CRITERION_COUNT:
        raise Tier0RunnerError(
            f"evaluator requires exactly {_HARVEY_LAB_JUDGE_CRITERION_COUNT} "
            f"per-criterion judge ceilings for {arm_id}; got {len(ceilings)}"
        )
    return ceilings


class _PerCriterionEvaluatorSpendBoundary(HarveyLabJudgeRequestBoundary):
    """Reserve and settle one mechanical spend scope for each LAB criterion."""

    def __init__(
        self,
        *,
        controller: SpendController | None,
        spec: Tier0ExecutableSpec,
        arm: Tier0ArmSpec,
        outstanding: _OutstandingReservations,
    ) -> None:
        if controller is None:
            raise Tier0RunnerError(
                "per-criterion evaluator boundary requires spend controller"
            )
        self._controller = controller
        self._spec = spec
        self._arm = arm
        self._outstanding = outstanding
        self._ceilings = _judge_ceilings_for(controller.policy, arm.arm_id)
        # The judge surface is deliberately not tied to ``arm.requested_model``.
        # A policy may score a solver arm with a different judging model, and
        # every reservation is validated against its own judge ceiling's
        # provider/model by ``SpendController.reserve``.
        self._ledger_lock = threading.RLock()
        self._seen_call_ids: set[str] = set()
        self._settled_criteria: set[str] = set()

    def _ceiling_for(self, request: HarveyLabJudgeRequest) -> JudgeCriterionCeiling:
        if request.ordinal > len(self._ceilings):
            raise Tier0RunnerError(
                f"judge criterion ordinal {request.ordinal} exceeds the pinned "
                f"{len(self._ceilings)}-criterion LAB evaluator"
            )
        ceiling = self._ceilings[request.ordinal - 1]
        if request.criterion_id != ceiling.criterion_id:
            raise Tier0RunnerError(
                "judge criterion identity does not match its pinned ordinal"
            )
        return ceiling

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> SpendReservation:
        ceiling = self._ceiling_for(request)
        call_id = (
            f"{self._arm.arm_id}-evaluator-{request.ordinal}-{request.attempt_index}"
        )
        with self._ledger_lock:
            if call_id in self._seen_call_ids:
                raise Tier0RunnerError("judge call identity was already used")
            self._seen_call_ids.add(call_id)
        try:
            reservation = self._controller.reserve(
                PaidCall(
                    call_id=call_id,
                    surface="judge",
                    arm_id=self._arm.arm_id,
                    provider=ceiling.provider,
                    model=ceiling.model,
                    executable_spec_sha256=self._spec.artifact_sha256 or "",
                    pricing_snapshot_sha256=self._controller.pricing.snapshot_sha256,
                    attempt_index=request.attempt_index,
                    criterion_id=ceiling.criterion_id,
                )
            )
        except SpendDeniedError:
            with self._ledger_lock:
                self._seen_call_ids.remove(call_id)
            raise
        except SpendConfigurationError as exc:
            with self._ledger_lock:
                self._seen_call_ids.remove(call_id)
            raise Tier0RunnerError(
                f"evaluator spend reservation is not executable for {self._arm.arm_id}"
            ) from exc
        self._outstanding.add(reservation)
        return reservation

    def after_judge_call(
        self,
        request: HarveyLabJudgeRequest,
        reservation: object,
        observation: object,
    ) -> None:
        ceiling = self._ceiling_for(request)
        if not isinstance(reservation, SpendReservation):
            raise Tier0RunnerError("evaluator returned an invalid judge reservation")
        if not isinstance(observation, UsageObservation):
            raise Tier0RunnerError(
                "evaluator must provide a UsageObservation for every judge call"
            )
        call = reservation.call
        if (
            call.surface != "judge"
            or call.arm_id != self._arm.arm_id
            or call.criterion_id != ceiling.criterion_id
            or call.attempt_index != request.attempt_index
        ):
            raise Tier0RunnerError(
                "judge reservation does not match the criterion request"
            )
        self._outstanding.remove(reservation)
        try:
            self._controller.settle(reservation, observation)
        except SpendSettlementError as exc:
            raise Tier0RunnerError("judge spend settlement failed closed") from exc
        with self._ledger_lock:
            self._settled_criteria.add(ceiling.criterion_id)

    def require_every_criterion_settled(self) -> None:
        """Refuse an evaluation that skipped any pinned criterion boundary.

        The evaluator owns the criterion loop, so a runner that silently omits
        a callback would leave that provider call outside the ledger entirely:
        unreserved before the request and unsettled afterwards.  A scores file
        can still look complete in that case, so the arm is only accepted once
        every pinned criterion has been reserved *and* settled through this
        boundary.
        """

        with self._ledger_lock:
            missing = tuple(
                ceiling.criterion_id
                for ceiling in self._ceilings
                if ceiling.criterion_id not in self._settled_criteria
            )
        if missing:
            raise Tier0RunnerError(
                f"evaluator settled {len(self._ceilings) - len(missing)} of "
                f"{len(self._ceilings)} per-criterion judge calls for "
                f"{self._arm.arm_id}; unaccounted criteria: {', '.join(missing)}"
            )


def _settle_solver(
    controller: SpendController,
    reservation: Any,
    execution: ExecutionReceipt,
    pricing: PricingSnapshot | None,
) -> None:
    if pricing is None:
        raise Tier0RunnerError("solver settlement has no pricing snapshot")
    try:
        controller.settle(
            reservation,
            _usage_observation_from_execution(execution, pricing),
        )
    except SpendSettlementError as exc:
        raise Tier0RunnerError("solver spend settlement failed closed") from exc


def _usage_observation_from_execution(
    execution: ExecutionReceipt,
    pricing: PricingSnapshot,
) -> UsageObservation:
    input_tokens = execution.usage.get("input_tokens")
    output_tokens = execution.usage.get("output_tokens")
    if type(input_tokens) is not int or type(output_tokens) is not int:
        return UsageObservation.unknown("solver did not report auditable token usage")
    if execution.cost_usd is None:
        return UsageObservation(
            basis="estimated_from_pricing_snapshot",
            pricing_snapshot_sha256=pricing.snapshot_sha256,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    amount = Decimal(str(execution.cost_usd)).quantize(Decimal("0.000001"))
    return UsageObservation(
        basis="provider_reported",
        pricing_snapshot_sha256=pricing.snapshot_sha256,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reported_cost_usd=format(amount, "f"),
    )


def _start_run_metadata(
    *,
    spec: Tier0ExecutableSpec,
    spec_sha256: str,
    arm: Tier0ArmSpec,
    run_spec: RunSpec,
    paths: Mapping[str, Path],
    executable_identity: ObservedExecutableIdentity,
    spend_policy: SpendPolicy | None,
    pricing_snapshot: PricingSnapshot | None,
    capability_record: object,
) -> PrivateRunMetadata:
    config_records: dict[str, object] = {
        "executable_spec": spec.to_record(),
        "arm_settings": dict(arm.settings),
        "boundary": {
            "containment": "posix_process_group.v1",
            "network_policy": "provider_egress_host_only",
            "auth_profile": arm.auth_profile,
        },
        "capability": capability_record,
    }
    if spend_policy is not None:
        config_records["spend_policy"] = spend_policy.to_record()
    if pricing_snapshot is not None:
        config_records["pricing_snapshot"] = pricing_snapshot.to_record()
    version = arm.solver_executable_version or "unversioned-fixture"
    return build_private_run_metadata(
        run_id=f"{spec.experiment_id}:{arm.arm_id}",
        run_spec=run_spec,
        executable_identities=(
            BinaryRunIdentity(
                executable_name=executable_identity.basename,
                executable_version=version,
                executable_sha256=f"sha256:{executable_identity.sha256.removeprefix('sha256:')}",
                capability_sha256=(
                    _record_hash(cast(Mapping[str, object], capability_record))
                    if isinstance(capability_record, Mapping)
                    else None
                ),
            ),
        ),
        boundary_identity={
            "containment": "posix_process_group.v1",
            "network_policy": "provider_egress_host_only",
            "auth_profile": arm.auth_profile,
        },
        config_records=config_records,
    )


def _authority_record(authority: IssuerAuthority) -> Mapping[str, object]:
    record = getattr(authority, "to_record", None)
    if callable(record):
        value = record()
        if isinstance(value, Mapping):
            return cast(Mapping[str, object], value)
    return {
        "schema_version": "external-authority.v1",
        "authority_type": type(authority).__name__,
    }


def _run_native_thin(
    *,
    arm: Tier0ArmSpec,
    spec: Tier0ExecutableSpec,
    source_root: Path,
    paths: Mapping[str, Path],
    service: LocalCliExecutionService,
    authority: IssuerAuthority,
    max_cost_usd: str | None = None,
    budget_argument_name: str | None = None,
    before_solver: Callable[[RunSpec], None] | None = None,
    after_solver: Callable[[RunSpec, ExecutionReceipt], ExecutionReceipt] | None = None,
    before_evaluator: Callable[[], None] | None = None,
    after_evaluator: Callable[[HarveyLabIsolatedEvaluation], None] | None = None,
    judge_request_boundary: HarveyLabJudgeRequestBoundary | None = None,
    evaluator_runner: EvaluatorRunner | None = None,
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
        max_cost_usd=max_cost_usd,
        argument_name=budget_argument_name,
    )
    solver_spec = RunSpec(
        spec_id=f"{spec.experiment_id}:{arm.arm_id}:solver",
        argv=argv,
        working_directory=sandbox_root.resolve(),
        timeout_seconds=arm.timeout_seconds,
    )
    if before_solver is not None:
        before_solver(solver_spec)
    execution = service.execute(solver_spec)
    if after_solver is not None:
        execution = after_solver(solver_spec, execution)
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
    if before_evaluator is not None:
        before_evaluator()
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
        judge_request_boundary=judge_request_boundary,
        evaluator_runner=evaluator_runner,
    )
    if after_evaluator is not None:
        after_evaluator(evaluation)
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
) -> dict[str, ObservedExecutableIdentity]:
    identities: dict[str, ObservedExecutableIdentity] = {}
    for arm in spec.arms:
        path = _resolve_on_path(arm.solver_executable, parent_env)
        try:
            pin = _pin_for_arm(arm)
            observed = verify_executable_digest(
                # The digest-only bind intentionally cannot launch a probe or
                # resolve credentials.  Full capability probes happen in the
                # contained runtime immediately before execution.
                _pin_for_arm(arm),
                (arm.solver_executable,),
                search_path=(parent_env or os.environ).get("PATH", "/usr/bin"),
            )
            if arm.solver_executable_version is not None:
                from legalforecast.multiharness.local_cli_identity import (
                    bind_executable_identity,
                )

                with tempfile.TemporaryDirectory(prefix="lfb-tier0-probe-") as probe:
                    observed = bind_executable_identity(
                        pin,
                        (arm.solver_executable,),
                        version_probe_args=arm.version_probe_args,
                        scratch_root=Path(probe),
                        parent_env=parent_env,
                        requested_model=arm.requested_model,
                    )
        except Exception as exc:
            raise Tier0RunnerError(
                f"{arm.arm_id} solver executable identity does not match spec"
            ) from exc
        if _hash_file(path) != arm.solver_executable_sha256:
            raise Tier0RunnerError(
                f"{arm.arm_id} solver executable hash does not match spec"
            )
        identities[arm.arm_id] = observed
    return identities


def _pin_for_arm(arm: Tier0ArmSpec) -> Any:
    from legalforecast.multiharness.local_cli_identity import ExecutableIdentityPin

    return ExecutableIdentityPin(
        basename=arm.solver_executable,
        version=arm.solver_executable_version or "unversioned-fixture",
        sha256=arm.solver_executable_sha256.removeprefix("sha256:"),
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
        "metadata": arm / "run-metadata.json",
        "capability": arm / "capability-record.json",
    }


def _render_command(
    command: Sequence[str],
    *,
    sandbox_root: Path,
    output_root: Path,
    max_cost_usd: str | None = None,
    argument_name: str | None = None,
) -> tuple[str, ...]:
    values = {"{sandbox_root}": str(sandbox_root), "{output_root}": str(output_root)}
    if max_cost_usd is not None:
        values["{max_cost_usd}"] = max_cost_usd
    rendered = tuple(values.get(token, token) for token in command)
    if not rendered or any(not item for item in rendered):
        raise Tier0RunnerError("native-thin command is empty")
    if any(item in {"sh", "bash"} for item in rendered):
        raise Tier0RunnerError("native-thin command must not invoke a shell")
    if max_cost_usd is not None:
        if argument_name is None:
            raise Tier0RunnerError("native-thin budget argument name is missing")
        try:
            index = rendered.index(argument_name)
        except ValueError as exc:
            raise Tier0RunnerError(
                "native-thin command does not enforce its frozen budget argument"
            ) from exc
        if index + 1 >= len(rendered) or rendered[index + 1] != max_cost_usd:
            raise Tier0RunnerError(
                "native-thin budget argument does not equal the frozen ceiling"
            )
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
    spend_controller: SpendController | None = None,
    terminal_error: str | None = None,
    partial_metadata: Mapping[str, PrivateRunMetadata] | None = None,
    partial_capabilities: Mapping[str, object] | None = None,
    authority_record: Mapping[str, object] | None = None,
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
    if authority_record is not None:
        write_json_object(private / "issuer-authority.json", authority_record)
    if spend_controller is not None:
        write_json_object(
            private / "spend-controller.json", spend_controller.archive_record()
        )
    if terminal_error is not None:
        write_json_object(
            private / "terminal-denial.json",
            {
                # contract-ratchet: allow non-authoritative terminal denial sidecar
                "schema_version": "legalforecast.multiharness.tier0_terminal_denial.v1",
                "error": terminal_error,
                "spend": (
                    None
                    if spend_controller is None
                    else spend_controller.archive_record()
                ),
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
        if result.run_metadata is not None:
            write_json_object(
                arm_private / "run-metadata.json",
                result.run_metadata.to_record(),
            )
        if result.receipt_metadata_binding is not None:
            write_json_object(
                arm_private / "receipt-metadata-binding.json",
                result.receipt_metadata_binding.to_record(),
            )
    archived_arm_ids = {result.arm_id for result in results}
    for arm_id, metadata in (partial_metadata or {}).items():
        if arm_id in archived_arm_ids:
            continue
        arm_private = private / arm_id
        arm_private.mkdir(exist_ok=True)
        write_json_object(arm_private / "run-metadata.json", metadata.to_record())
        capability = (partial_capabilities or {}).get(arm_id)
        if capability is not None:
            write_json_object(
                arm_private / "capability-record.json",
                {
                    # contract-ratchet: allow non-authoritative capability sidecar
                    "schema_version": "legalforecast.multiharness.tier0_capability.v1",
                    "arm_id": arm_id,
                    "capability": capability,
                },
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
