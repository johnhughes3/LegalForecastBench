"""Harness-independent identity keys for community and official runs.

Bead ``LegalForecastBench-dm0g.4.1.4`` owns these keys. Local CLI
``RunSpec`` / ``ExecutionReceipt`` types in
``legalforecast.multiharness.local_cli_contracts`` remain the execution
records shipped by PR #685; this module is the shared identity layer both
community submissions and official runs attach. It does not import
publication envelopes.

Task, solver, and run keys are always derivable. A matched-harness key
additionally requires a resolved served model. Unresolved served models
still permit labeled system-bundle rows. Harness-intrinsic prompt, context
management, loop, tool API, and tool implementation are treatment and are
not mixed into the matched-harness key. ``clean-native`` and
``mcp-mediated`` outer envelopes are distinct identities.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Self

from legalforecast.contracts import ARTIFACT_PREFIXED_SHA256_V1, SchemaIdentifier
from legalforecast.multiharness.spec import SCORING_MODES, TASK_FAMILIES
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_known_fields,
    require_schema_version,
    require_str,
    validate_public_record,
    validate_sha256,
)

TASK_IDENTITY_SCHEMA_VERSION = (
    # contract-ratchet: allow identity-key schema until contracts registry
    "legalforecast.multiharness.task_identity.v1"
)
SOLVER_IDENTITY_SCHEMA_VERSION = (
    # contract-ratchet: allow identity-key schema until contracts registry
    "legalforecast.multiharness.solver_identity.v1"
)
RUN_IDENTITY_SCHEMA_VERSION = (
    # contract-ratchet: allow identity-key schema until contracts registry
    "legalforecast.multiharness.run_identity.v1"
)
MATCHED_HARNESS_IDENTITY_SCHEMA_VERSION = (
    # contract-ratchet: allow identity-key schema until contracts registry
    "legalforecast.multiharness.matched_harness_identity.v1"
)
SYSTEM_BUNDLE_LABEL_SCHEMA_VERSION = (
    # contract-ratchet: allow identity-key schema until contracts registry
    "legalforecast.multiharness.system_bundle_label.v1"
)

OUTER_ENVELOPES = frozenset({"clean-native", "mcp-mediated"})
UNRESOLVED_SERVED_MODEL_SENTINELS = frozenset(
    {"", "unknown", "unresolved", "none", "*", "null"}
)
_REFUSED_FIELD_ALIASES = frozenset(
    {
        "task_hash",
        "taskHash",
        "servedModel",
        "served_model_id",
        "model",
        "clean_native",
        "mcp",
        "mcp_mediated",
        "outerEnvelope",
    }
)
_TASK_REQUIRED = frozenset(
    {
        "schema_version",
        "task_id",
        "family",
        "scoring_mode",
        "suite_version",
        "task_sha256",
        "key",
    }
)
_SOLVER_REQUIRED = frozenset(
    {
        "schema_version",
        "provider",
        "requested_model",
        "served_model",
        "settings_sha256",
        "key",
    }
)
_RUN_REQUIRED = frozenset(
    {
        "schema_version",
        "task_identity_key",
        "solver_identity_key",
        "runtime_policy_sha256",
        "config_sha256",
        "temporal_block",
        "order",
        "repeat_index",
        "key",
    }
)
_MATCHED_REQUIRED = frozenset(
    {
        "schema_version",
        "task_identity_key",
        "provider",
        "served_model",
        "settings_sha256",
        "evaluator_identity",
        "temporal_block",
        "outer_envelope",
        "order",
        "repeat_index",
        "key",
    }
)
_BUNDLE_REQUIRED = frozenset(
    {
        "schema_version",
        "adapter_id",
        "adapter_version",
        "requested_model",
        "family",
        "label",
        "key",
    }
)


class IdentityError(MultiHarnessValidationError):
    """An identity key was missing, ambiguous, unresolved, or mismatched."""


@dataclass(frozen=True, slots=True)
class HarnessTreatment:
    """Harness-intrinsic variation that is treatment, not identity.

    Changing these fields must not change a matched-harness key. They exist so
    callers can pass the treatment they froze without mixing it into identity.
    """

    prompt_sha256: str | None = None
    context_management_sha256: str | None = None
    loop_sha256: str | None = None
    tool_api_sha256: str | None = None
    tool_implementation_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class TaskIdentity:
    """Canonical task identity over family, suite, and task bytes."""

    task_id: str
    family: str
    scoring_mode: str
    suite_version: str
    task_sha256: str
    key: str

    def __post_init__(self) -> None:
        _require_token(self.task_id, "task_id")
        _require_member(self.family, TASK_FAMILIES, "family")
        _require_member(self.scoring_mode, SCORING_MODES, "scoring_mode")
        _require_token(self.suite_version, "suite_version")
        _require_prefixed_digest(self.task_sha256, "task_sha256")
        expected = _identity_key(self._hash_payload(), _TASK_DOMAIN)
        _require_prefixed_digest(self.key, "key")
        if self.key != expected:
            raise IdentityError("task identity key does not match inputs")
        validate_public_record(self.to_record(), "task_identity")

    def _hash_payload(self) -> dict[str, object]:
        return {
            "family": self.family,
            "schema_version": TASK_IDENTITY_SCHEMA_VERSION,
            "scoring_mode": self.scoring_mode,
            "suite_version": self.suite_version,
            "task_id": self.task_id,
            "task_sha256": self.task_sha256,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._hash_payload(), "key": self.key}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return _parse_identity_record(
            record,
            required=_TASK_REQUIRED,
            field_name="task identity",
            schema_version=TASK_IDENTITY_SCHEMA_VERSION,
            construct=lambda: cls(
                task_id=require_str(record, "task_id"),
                family=require_str(record, "family"),
                scoring_mode=require_str(record, "scoring_mode"),
                suite_version=require_str(record, "suite_version"),
                task_sha256=require_str(record, "task_sha256"),
                key=require_str(record, "key"),
            ),
        )


@dataclass(frozen=True, slots=True)
class SolverIdentity:
    """Served-model identity independent of harness treatment."""

    provider: str
    requested_model: str
    served_model: str | None
    settings_sha256: str
    key: str

    def __post_init__(self) -> None:
        _require_token(self.provider, "provider")
        _require_token(self.requested_model, "requested_model")
        if self.served_model is not None:
            _require_resolved_served_model(self.served_model)
        _require_prefixed_digest(self.settings_sha256, "settings_sha256")
        expected = _identity_key(self._hash_payload(), _SOLVER_DOMAIN)
        _require_prefixed_digest(self.key, "key")
        if self.key != expected:
            raise IdentityError("solver identity key does not match inputs")
        validate_public_record(self.to_record(), "solver_identity")

    def served_model_is_resolved(self) -> bool:
        """Return whether this identity names a concrete served model."""

        return self.served_model is not None

    def _hash_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "requested_model": self.requested_model,
            "schema_version": SOLVER_IDENTITY_SCHEMA_VERSION,
            "served_model": self.served_model,
            "settings_sha256": self.settings_sha256,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._hash_payload(), "key": self.key}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        def construct() -> Self:
            served_model = record.get("served_model")
            if served_model is not None:
                served_model = require_str(record, "served_model")
            return cls(
                provider=require_str(record, "provider"),
                requested_model=require_str(record, "requested_model"),
                served_model=served_model,
                settings_sha256=require_str(record, "settings_sha256"),
                key=require_str(record, "key"),
            )

        return _parse_identity_record(
            record,
            required=_SOLVER_REQUIRED,
            field_name="solver identity",
            schema_version=SOLVER_IDENTITY_SCHEMA_VERSION,
            construct=construct,
        )


@dataclass(frozen=True, slots=True)
class RunIdentity:
    """One execution's identity over task, solver, config, policy, and slot."""

    task_identity_key: str
    solver_identity_key: str
    runtime_policy_sha256: str
    config_sha256: str
    temporal_block: str
    order: int
    repeat_index: int
    key: str

    def __post_init__(self) -> None:
        _require_prefixed_digest(self.task_identity_key, "task_identity_key")
        _require_prefixed_digest(self.solver_identity_key, "solver_identity_key")
        _require_prefixed_digest(self.runtime_policy_sha256, "runtime_policy_sha256")
        _require_prefixed_digest(self.config_sha256, "config_sha256")
        _require_token(self.temporal_block, "temporal_block")
        _require_non_negative_int(self.order, "order")
        _require_non_negative_int(self.repeat_index, "repeat_index")
        expected = _identity_key(self._hash_payload(), _RUN_DOMAIN)
        _require_prefixed_digest(self.key, "key")
        if self.key != expected:
            raise IdentityError("run identity key does not match inputs")
        validate_public_record(self.to_record(), "run_identity")

    def _hash_payload(self) -> dict[str, object]:
        return {
            "config_sha256": self.config_sha256,
            "order": self.order,
            "repeat_index": self.repeat_index,
            "runtime_policy_sha256": self.runtime_policy_sha256,
            "schema_version": RUN_IDENTITY_SCHEMA_VERSION,
            "solver_identity_key": self.solver_identity_key,
            "task_identity_key": self.task_identity_key,
            "temporal_block": self.temporal_block,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._hash_payload(), "key": self.key}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return _parse_identity_record(
            record,
            required=_RUN_REQUIRED,
            field_name="run identity",
            schema_version=RUN_IDENTITY_SCHEMA_VERSION,
            construct=lambda: cls(
                task_identity_key=require_str(record, "task_identity_key"),
                solver_identity_key=require_str(record, "solver_identity_key"),
                runtime_policy_sha256=require_str(record, "runtime_policy_sha256"),
                config_sha256=require_str(record, "config_sha256"),
                temporal_block=require_str(record, "temporal_block"),
                order=_require_record_int(record, "order"),
                repeat_index=_require_record_int(record, "repeat_index"),
                key=require_str(record, "key"),
            ),
        )


@dataclass(frozen=True, slots=True)
class MatchedHarnessIdentity:
    """Comparability key with harness-intrinsic treatment held aside."""

    task_identity_key: str
    provider: str
    served_model: str
    settings_sha256: str
    evaluator_identity: str
    temporal_block: str
    outer_envelope: str
    order: int
    repeat_index: int
    key: str

    def __post_init__(self) -> None:
        _require_prefixed_digest(self.task_identity_key, "task_identity_key")
        _require_token(self.provider, "provider")
        _require_resolved_served_model(self.served_model)
        _require_prefixed_digest(self.settings_sha256, "settings_sha256")
        _require_token(self.evaluator_identity, "evaluator_identity")
        _require_token(self.temporal_block, "temporal_block")
        _require_member(self.outer_envelope, OUTER_ENVELOPES, "outer_envelope")
        _require_non_negative_int(self.order, "order")
        _require_non_negative_int(self.repeat_index, "repeat_index")
        expected = _identity_key(self._hash_payload(), _MATCHED_DOMAIN)
        _require_prefixed_digest(self.key, "key")
        if self.key != expected:
            raise IdentityError("matched-harness identity key does not match inputs")
        validate_public_record(self.to_record(), "matched_harness_identity")

    def _hash_payload(self) -> dict[str, object]:
        return {
            "evaluator_identity": self.evaluator_identity,
            "order": self.order,
            "outer_envelope": self.outer_envelope,
            "provider": self.provider,
            "repeat_index": self.repeat_index,
            "schema_version": MATCHED_HARNESS_IDENTITY_SCHEMA_VERSION,
            "served_model": self.served_model,
            "settings_sha256": self.settings_sha256,
            "task_identity_key": self.task_identity_key,
            "temporal_block": self.temporal_block,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._hash_payload(), "key": self.key}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return _parse_identity_record(
            record,
            required=_MATCHED_REQUIRED,
            field_name="matched-harness identity",
            schema_version=MATCHED_HARNESS_IDENTITY_SCHEMA_VERSION,
            construct=lambda: cls(
                task_identity_key=require_str(record, "task_identity_key"),
                provider=require_str(record, "provider"),
                served_model=require_str(record, "served_model"),
                settings_sha256=require_str(record, "settings_sha256"),
                evaluator_identity=require_str(record, "evaluator_identity"),
                temporal_block=require_str(record, "temporal_block"),
                outer_envelope=require_str(record, "outer_envelope"),
                order=_require_record_int(record, "order"),
                repeat_index=_require_record_int(record, "repeat_index"),
                key=require_str(record, "key"),
            ),
        )


@dataclass(frozen=True, slots=True)
class SystemBundleLabel:
    """Labeled system-bundle row that does not require a served model."""

    adapter_id: str
    adapter_version: str
    requested_model: str
    family: str
    label: str
    key: str

    def __post_init__(self) -> None:
        _require_token(self.adapter_id, "adapter_id")
        _require_token(self.adapter_version, "adapter_version")
        _require_token(self.requested_model, "requested_model")
        _require_member(self.family, TASK_FAMILIES, "family")
        expected_label = _system_bundle_label(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            requested_model=self.requested_model,
            family=self.family,
        )
        if self.label != expected_label:
            raise IdentityError("system-bundle label does not match inputs")
        expected = _identity_key(self._hash_payload(), _BUNDLE_DOMAIN)
        _require_prefixed_digest(self.key, "key")
        if self.key != expected:
            raise IdentityError("system-bundle key does not match inputs")
        validate_public_record(self.to_record(), "system_bundle_label")

    def _hash_payload(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "family": self.family,
            "label": self.label,
            "requested_model": self.requested_model,
            "schema_version": SYSTEM_BUNDLE_LABEL_SCHEMA_VERSION,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._hash_payload(), "key": self.key}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return _parse_identity_record(
            record,
            required=_BUNDLE_REQUIRED,
            field_name="system-bundle label",
            schema_version=SYSTEM_BUNDLE_LABEL_SCHEMA_VERSION,
            construct=lambda: cls(
                adapter_id=require_str(record, "adapter_id"),
                adapter_version=require_str(record, "adapter_version"),
                requested_model=require_str(record, "requested_model"),
                family=require_str(record, "family"),
                label=require_str(record, "label"),
                key=require_str(record, "key"),
            ),
        )


def derive_task_identity(
    *,
    task_id: str,
    family: str,
    scoring_mode: str,
    suite_version: str,
    task_sha256: str,
) -> TaskIdentity:
    """Derive a task identity key from canonical task fields and task bytes."""

    payload = {
        "family": family,
        "schema_version": TASK_IDENTITY_SCHEMA_VERSION,
        "scoring_mode": scoring_mode,
        "suite_version": suite_version,
        "task_id": task_id,
        "task_sha256": task_sha256,
    }
    return TaskIdentity(
        task_id=task_id,
        family=family,
        scoring_mode=scoring_mode,
        suite_version=suite_version,
        task_sha256=task_sha256,
        key=_identity_key(payload, _TASK_DOMAIN),
    )


def derive_solver_identity(
    *,
    provider: str,
    requested_model: str,
    settings_sha256: str,
    served_model: str | None = None,
) -> SolverIdentity:
    """Derive a solver identity. ``served_model=None`` is unresolved."""

    payload = {
        "provider": provider,
        "requested_model": requested_model,
        "schema_version": SOLVER_IDENTITY_SCHEMA_VERSION,
        "served_model": served_model,
        "settings_sha256": settings_sha256,
    }
    return SolverIdentity(
        provider=provider,
        requested_model=requested_model,
        served_model=served_model,
        settings_sha256=settings_sha256,
        key=_identity_key(payload, _SOLVER_DOMAIN),
    )


def derive_run_identity(
    *,
    task: TaskIdentity,
    solver: SolverIdentity,
    runtime_policy_sha256: str,
    config_sha256: str,
    temporal_block: str,
    order: int,
    repeat_index: int,
) -> RunIdentity:
    """Derive a run identity from task, solver, config, policy, and slot."""

    payload = {
        "config_sha256": config_sha256,
        "order": order,
        "repeat_index": repeat_index,
        "runtime_policy_sha256": runtime_policy_sha256,
        "schema_version": RUN_IDENTITY_SCHEMA_VERSION,
        "solver_identity_key": solver.key,
        "task_identity_key": task.key,
        "temporal_block": temporal_block,
    }
    return RunIdentity(
        task_identity_key=task.key,
        solver_identity_key=solver.key,
        runtime_policy_sha256=runtime_policy_sha256,
        config_sha256=config_sha256,
        temporal_block=temporal_block,
        order=order,
        repeat_index=repeat_index,
        key=_identity_key(payload, _RUN_DOMAIN),
    )


def derive_matched_harness_identity(
    *,
    task: TaskIdentity,
    solver: SolverIdentity,
    evaluator_identity: str,
    temporal_block: str,
    outer_envelope: str,
    order: int,
    repeat_index: int,
    treatment: HarnessTreatment | None = None,
) -> MatchedHarnessIdentity:
    """Derive a matched-harness key, refusing unresolved served models.

    ``treatment`` is accepted so callers can freeze harness-intrinsic prompt,
    context, loop, and tools without folding them into the key.
    """

    del treatment
    if not solver.served_model_is_resolved():
        raise IdentityError("unresolved served_model prevents matched-harness identity")
    served_model = solver.served_model
    if served_model is None:
        raise IdentityError("unresolved served_model prevents matched-harness identity")
    payload = {
        "evaluator_identity": evaluator_identity,
        "order": order,
        "outer_envelope": outer_envelope,
        "provider": solver.provider,
        "repeat_index": repeat_index,
        "schema_version": MATCHED_HARNESS_IDENTITY_SCHEMA_VERSION,
        "served_model": served_model,
        "settings_sha256": solver.settings_sha256,
        "task_identity_key": task.key,
        "temporal_block": temporal_block,
    }
    return MatchedHarnessIdentity(
        task_identity_key=task.key,
        provider=solver.provider,
        served_model=served_model,
        settings_sha256=solver.settings_sha256,
        evaluator_identity=evaluator_identity,
        temporal_block=temporal_block,
        outer_envelope=outer_envelope,
        order=order,
        repeat_index=repeat_index,
        key=_identity_key(payload, _MATCHED_DOMAIN),
    )


def derive_system_bundle_label(
    *,
    adapter_id: str,
    adapter_version: str,
    requested_model: str,
    family: str,
) -> SystemBundleLabel:
    """Label a system-bundle row without requiring a resolved served model."""

    label = _system_bundle_label(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        requested_model=requested_model,
        family=family,
    )
    payload = {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "family": family,
        "label": label,
        "requested_model": requested_model,
        "schema_version": SYSTEM_BUNDLE_LABEL_SCHEMA_VERSION,
    }
    return SystemBundleLabel(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        requested_model=requested_model,
        family=family,
        label=label,
        key=_identity_key(payload, _BUNDLE_DOMAIN),
    )


def validate_resume_binding(*, requested: RunIdentity, prior: RunIdentity) -> None:
    """Refuse resume that would cross task bytes, config, or runtime policy."""

    if requested.task_identity_key != prior.task_identity_key:
        raise IdentityError("resume cannot cross task identity")
    if requested.config_sha256 != prior.config_sha256:
        raise IdentityError("resume cannot cross config_sha256")
    if requested.runtime_policy_sha256 != prior.runtime_policy_sha256:
        raise IdentityError("resume cannot cross runtime_policy_sha256")


def _identity_key(payload: Mapping[str, object], domain: SchemaIdentifier) -> str:
    return str(ARTIFACT_PREFIXED_SHA256_V1.commit(dict(payload), domain=domain).digest)


def _system_bundle_label(
    *,
    adapter_id: str,
    adapter_version: str,
    requested_model: str,
    family: str,
) -> str:
    return f"{adapter_id}/{adapter_version}/{family}/{requested_model}"


def _parse_identity_record[T](
    record: Mapping[str, Any],
    *,
    required: frozenset[str],
    field_name: str,
    schema_version: str,
    construct: Callable[[], T],
) -> T:
    try:
        _reject_aliases(record, field_name)
        _require_identity_record(
            record,
            required=required,
            field_name=field_name,
            schema_version=schema_version,
        )
        return construct()
    except IdentityError:
        raise
    except MultiHarnessValidationError as exc:
        raise IdentityError(str(exc)) from exc


def _require_identity_record(
    record: Mapping[str, Any],
    *,
    required: frozenset[str],
    field_name: str,
    schema_version: str,
) -> None:
    try:
        require_known_fields(record, required=required, field_name=field_name)
        require_schema_version(record, schema_version)
    except MultiHarnessValidationError as exc:
        raise IdentityError(str(exc)) from exc


def _reject_aliases(record: Mapping[str, Any], field_name: str) -> None:
    overlap = sorted(_REFUSED_FIELD_ALIASES.intersection(record))
    if overlap:
        raise IdentityError(
            f"{field_name} has ambiguous alias field(s): {', '.join(overlap)}"
        )


def _require_token(value: str, field_name: str) -> None:
    if not value.strip() or value != value.strip():
        raise IdentityError(f"{field_name} must be a non-empty trimmed string")


def _require_member(value: str, allowed: frozenset[str], field_name: str) -> None:
    if value not in allowed:
        formatted = ", ".join(sorted(allowed))
        raise IdentityError(f"{field_name} must be one of: {formatted}")


def _require_prefixed_digest(value: str, field_name: str) -> None:
    try:
        validate_sha256(value, field_name, allow_prefix=True)
    except MultiHarnessValidationError as exc:
        raise IdentityError(str(exc)) from exc
    if not value.startswith("sha256:"):
        raise IdentityError(f"{field_name} must use the sha256: prefix")


def _require_resolved_served_model(value: str) -> None:
    if value.strip().lower() in UNRESOLVED_SERVED_MODEL_SENTINELS or (
        value != value.strip()
    ):
        raise IdentityError("served_model is unresolved or ambiguous")
    _require_token(value, "served_model")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise IdentityError(f"{field_name} must be a non-negative integer")


def _require_record_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or value < 0:
        raise IdentityError(f"{field_name} must be a non-negative integer")
    return value


# contract-ratchet: allow identity-key schema until contracts registry
_TASK_DOMAIN = SchemaIdentifier(TASK_IDENTITY_SCHEMA_VERSION)
# contract-ratchet: allow identity-key schema until contracts registry
_SOLVER_DOMAIN = SchemaIdentifier(SOLVER_IDENTITY_SCHEMA_VERSION)
# contract-ratchet: allow identity-key schema until contracts registry
_RUN_DOMAIN = SchemaIdentifier(RUN_IDENTITY_SCHEMA_VERSION)
# contract-ratchet: allow identity-key schema until contracts registry
_MATCHED_DOMAIN = SchemaIdentifier(MATCHED_HARNESS_IDENTITY_SCHEMA_VERSION)
# contract-ratchet: allow identity-key schema until contracts registry
_BUNDLE_DOMAIN = SchemaIdentifier(SYSTEM_BUNDLE_LABEL_SCHEMA_VERSION)
