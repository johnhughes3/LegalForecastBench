"""Canonical records for the multi-harness community benchmark."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Self, cast

from legalforecast.multiharness.validation import (
    optional_bool,
    optional_mapping,
    optional_non_negative_int,
    optional_sequence,
    optional_str,
    require_mapping,
    require_schema_version,
    require_sequence,
    require_str,
    validate_env_var_names,
    validate_public_record,
    validate_safe_relative_path,
    validate_sha256,
    validate_unique_ids,
)

TASK_SCHEMA_VERSION = "legalforecast.multiharness.task.v1"
TASK_INDEX_SCHEMA_VERSION = "legalforecast.multiharness.task_index.v1"
ADAPTER_MANIFEST_SCHEMA_VERSION = "legalforecast.multiharness.adapter_manifest.v1"
ADAPTER_CAPABILITIES_SCHEMA_VERSION = (
    "legalforecast.multiharness.adapter_capabilities.v1"
)
SANDBOX_POLICY_SCHEMA_VERSION = "legalforecast.multiharness.sandbox_policy.v1"
RUN_REQUEST_SCHEMA_VERSION = "legalforecast.multiharness.run_request.v1"
RUN_RESULT_SCHEMA_VERSION = "legalforecast.multiharness.run_result.v1"
RUN_MANIFEST_SCHEMA_VERSION = "legalforecast.multiharness.run_manifest.v1"
CONFORMANCE_REPORT_SCHEMA_VERSION = "legalforecast.multiharness.conformance_report.v1"
COMMUNITY_SUBMISSION_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_submission.v1"
)
COMMUNITY_AGGREGATE_SCHEMA_VERSION = "legalforecast.multiharness.community_aggregate.v1"

SCHEMA_VERSIONS: Mapping[str, str] = {
    "task": TASK_SCHEMA_VERSION,
    "task_index": TASK_INDEX_SCHEMA_VERSION,
    "adapter_manifest": ADAPTER_MANIFEST_SCHEMA_VERSION,
    "adapter_capabilities": ADAPTER_CAPABILITIES_SCHEMA_VERSION,
    "sandbox_policy": SANDBOX_POLICY_SCHEMA_VERSION,
    "run_request": RUN_REQUEST_SCHEMA_VERSION,
    "run_result": RUN_RESULT_SCHEMA_VERSION,
    "run_manifest": RUN_MANIFEST_SCHEMA_VERSION,
    "conformance_report": CONFORMANCE_REPORT_SCHEMA_VERSION,
    "community_submission": COMMUNITY_SUBMISSION_SCHEMA_VERSION,
    "community_aggregate": COMMUNITY_AGGREGATE_SCHEMA_VERSION,
}

TASK_FAMILIES = frozenset({"legalforecast_mtd", "harvey_lab", "contract_only"})
SCORING_MODES = frozenset({"lfb_brier", "lab_native", "contract_only"})
RUN_RESULT_STATUSES = frozenset({"succeeded", "failed", "skipped"})
CONFORMANCE_STATUSES = frozenset({"passed", "failed", "warning"})


@dataclass(frozen=True, slots=True)
class ContributorCredit:
    """A person or organization credited for a benchmark artifact."""

    role: str
    name: str
    identifiers: Mapping[str, str] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        _require_non_empty(self.role, "role")
        _require_non_empty(self.name, "name")
        for key, value in self.identifiers.items():
            _require_non_empty(key, "identifiers key")
            _require_non_empty(value, f"identifier {key}")
        validate_public_record(self.to_record(), "contributor")

    def to_record(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "identifiers": dict(sorted(self.identifiers.items())),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        identifiers = optional_mapping(record, "identifiers") or {}
        return cls(
            role=require_str(record, "role"),
            name=require_str(record, "name"),
            identifiers=_str_mapping(identifiers, "identifiers"),
        )


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """A hashed artifact referenced by a multi-harness record."""

    artifact_id: str
    path: str
    sha256: str
    media_type: str
    public: bool = False
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.artifact_id, "artifact_id")
        validate_safe_relative_path(self.path, "path")
        validate_sha256(self.sha256, "sha256")
        _require_non_empty(self.media_type, "media_type")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        if self.public:
            validate_public_record(self.to_record(), "artifact")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "public": self.public,
        }
        if self.size_bytes is not None:
            record["size_bytes"] = self.size_bytes
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return cls(
            artifact_id=require_str(record, "artifact_id"),
            path=require_str(record, "path"),
            sha256=require_str(record, "sha256"),
            media_type=require_str(record, "media_type"),
            public=optional_bool(record, "public"),
            size_bytes=optional_non_negative_int(record, "size_bytes"),
        )


@dataclass(frozen=True, slots=True)
class CanonicalTask:
    """A suite-specific task projected into the multi-harness task contract."""

    task_id: str
    family: str
    scoring_mode: str
    suite_version: str
    source_id: str
    task_sha256: str
    metadata: Mapping[str, Any] = field(default_factory=lambda: {})
    artifacts: tuple[ArtifactRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.task_id, "task_id")
        _require_member(self.family, TASK_FAMILIES, "family")
        _require_member(self.scoring_mode, SCORING_MODES, "scoring_mode")
        _require_non_empty(self.suite_version, "suite_version")
        _require_non_empty(self.source_id, "source_id")
        validate_sha256(self.task_sha256, "task_sha256")
        validate_public_record(dict(self.metadata), "task.metadata")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "family": self.family,
            "scoring_mode": self.scoring_mode,
            "suite_version": self.suite_version,
            "source_id": self.source_id,
            "task_sha256": self.task_sha256,
            "metadata": dict(self.metadata),
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, TASK_SCHEMA_VERSION)
        return cls(
            task_id=require_str(record, "task_id"),
            family=require_str(record, "family"),
            scoring_mode=require_str(record, "scoring_mode"),
            suite_version=require_str(record, "suite_version"),
            source_id=require_str(record, "source_id"),
            task_sha256=require_str(record, "task_sha256"),
            metadata=optional_mapping(record, "metadata") or {},
            artifacts=_artifact_tuple(optional_sequence(record, "artifacts") or ()),
        )


@dataclass(frozen=True, slots=True)
class TaskIndex:
    """An ordered collection of canonical tasks for a suite or selection namespace."""

    index_id: str
    selection_namespace: str
    tasks: tuple[CanonicalTask, ...]
    index_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.index_id, "index_id")
        _require_non_empty(self.selection_namespace, "selection_namespace")
        if not self.tasks:
            raise ValueError("tasks must not be empty")
        validate_unique_ids((task.task_id for task in self.tasks), "tasks")
        validate_sha256(self.index_sha256, "index_sha256")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_INDEX_SCHEMA_VERSION,
            "index_id": self.index_id,
            "selection_namespace": self.selection_namespace,
            "tasks": [task.to_record() for task in self.tasks],
            "index_sha256": self.index_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, TASK_INDEX_SCHEMA_VERSION)
        return cls(
            index_id=require_str(record, "index_id"),
            selection_namespace=require_str(record, "selection_namespace"),
            tasks=_task_tuple(require_sequence(record, "tasks")),
            index_sha256=require_str(record, "index_sha256"),
        )


@dataclass(frozen=True, slots=True)
class AdapterManifest:
    """Public manifest for an in-process or command adapter."""

    adapter_id: str
    display_name: str
    adapter_version: str
    command: tuple[str, ...]
    contributors: tuple[ContributorCredit, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.adapter_id, "adapter_id")
        _require_non_empty(self.display_name, "display_name")
        _require_non_empty(self.adapter_version, "adapter_version")
        if not self.command:
            raise ValueError("command must not be empty")
        for index, value in enumerate(self.command):
            _require_non_empty(value, f"command[{index}]")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": ADAPTER_MANIFEST_SCHEMA_VERSION,
            "adapter_id": self.adapter_id,
            "display_name": self.display_name,
            "adapter_version": self.adapter_version,
            "command": list(self.command),
            "contributors": [credit.to_record() for credit in self.contributors],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, ADAPTER_MANIFEST_SCHEMA_VERSION)
        return cls(
            adapter_id=require_str(record, "adapter_id"),
            display_name=require_str(record, "display_name"),
            adapter_version=require_str(record, "adapter_version"),
            command=_str_tuple(require_sequence(record, "command"), "command"),
            contributors=_credit_tuple(optional_sequence(record, "contributors") or ()),
        )


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """Capabilities an adapter declares before a run is scheduled."""

    adapter_id: str
    adapter_version: str
    supported_families: tuple[str, ...]
    supported_scoring_modes: tuple[str, ...]
    capabilities_sha256: str
    supports_sandbox_policy: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(self.adapter_id, "adapter_id")
        _require_non_empty(self.adapter_version, "adapter_version")
        if not self.supported_families:
            raise ValueError("supported_families must not be empty")
        if not self.supported_scoring_modes:
            raise ValueError("supported_scoring_modes must not be empty")
        for value in self.supported_families:
            _require_member(value, TASK_FAMILIES, "supported_families")
        for value in self.supported_scoring_modes:
            _require_member(value, SCORING_MODES, "supported_scoring_modes")
        validate_sha256(self.capabilities_sha256, "capabilities_sha256")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": ADAPTER_CAPABILITIES_SCHEMA_VERSION,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "supported_families": list(self.supported_families),
            "supported_scoring_modes": list(self.supported_scoring_modes),
            "supports_sandbox_policy": self.supports_sandbox_policy,
            "capabilities_sha256": self.capabilities_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, ADAPTER_CAPABILITIES_SCHEMA_VERSION)
        return cls(
            adapter_id=require_str(record, "adapter_id"),
            adapter_version=require_str(record, "adapter_version"),
            supported_families=_str_tuple(
                require_sequence(record, "supported_families"),
                "supported_families",
            ),
            supported_scoring_modes=_str_tuple(
                require_sequence(record, "supported_scoring_modes"),
                "supported_scoring_modes",
            ),
            supports_sandbox_policy=optional_bool(record, "supports_sandbox_policy"),
            capabilities_sha256=require_str(record, "capabilities_sha256"),
        )


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    """Host-owned sandbox policy recorded for each multi-harness row."""

    policy_id: str
    backend: str
    image: str
    network_policy: str
    timeout_seconds: int
    allowed_provider_env_vars: tuple[str, ...] = ()
    policy_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.policy_id, "policy_id")
        _require_non_empty(self.backend, "backend")
        _require_non_empty(self.image, "image")
        _require_non_empty(self.network_policy, "network_policy")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        validate_env_var_names(
            self.allowed_provider_env_vars,
            "allowed_provider_env_vars",
        )
        if self.policy_sha256 is not None:
            validate_sha256(self.policy_sha256, "policy_sha256")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": SANDBOX_POLICY_SCHEMA_VERSION,
            "policy_id": self.policy_id,
            "backend": self.backend,
            "image": self.image,
            "network_policy": self.network_policy,
            "timeout_seconds": self.timeout_seconds,
            "allowed_provider_env_vars": list(self.allowed_provider_env_vars),
        }
        if self.policy_sha256 is not None:
            record["policy_sha256"] = self.policy_sha256
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, SANDBOX_POLICY_SCHEMA_VERSION)
        timeout = optional_non_negative_int(record, "timeout_seconds")
        if timeout is None:
            raise ValueError("timeout_seconds is required")
        return cls(
            policy_id=require_str(record, "policy_id"),
            backend=require_str(record, "backend"),
            image=require_str(record, "image"),
            network_policy=require_str(record, "network_policy"),
            timeout_seconds=timeout,
            allowed_provider_env_vars=_str_tuple(
                optional_sequence(record, "allowed_provider_env_vars") or (),
                "allowed_provider_env_vars",
            ),
            policy_sha256=optional_str(record, "policy_sha256"),
        )


@dataclass(frozen=True, slots=True)
class RunRequest:
    """A serialized request for one adapter/model/task row."""

    request_id: str
    task: CanonicalTask
    adapter: AdapterManifest
    model_key: str
    sandbox_policy: SandboxPolicy
    request_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.request_id, "request_id")
        _require_non_empty(self.model_key, "model_key")
        validate_sha256(self.request_sha256, "request_sha256")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_REQUEST_SCHEMA_VERSION,
            "request_id": self.request_id,
            "task": self.task.to_record(),
            "adapter": self.adapter.to_record(),
            "model_key": self.model_key,
            "sandbox_policy": self.sandbox_policy.to_record(),
            "request_sha256": self.request_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, RUN_REQUEST_SCHEMA_VERSION)
        return cls(
            request_id=require_str(record, "request_id"),
            task=CanonicalTask.from_record(require_mapping(record, "task")),
            adapter=AdapterManifest.from_record(require_mapping(record, "adapter")),
            model_key=require_str(record, "model_key"),
            sandbox_policy=SandboxPolicy.from_record(
                require_mapping(record, "sandbox_policy")
            ),
            request_sha256=require_str(record, "request_sha256"),
        )


@dataclass(frozen=True, slots=True)
class RunResult:
    """A canonical result for one adapter/model/task row."""

    result_id: str
    request_id: str
    status: str
    result_sha256: str
    artifacts: tuple[ArtifactRecord, ...] = ()
    public_summary: Mapping[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        _require_non_empty(self.result_id, "result_id")
        _require_non_empty(self.request_id, "request_id")
        _require_member(self.status, RUN_RESULT_STATUSES, "status")
        validate_sha256(self.result_sha256, "result_sha256")
        validate_public_record(dict(self.public_summary), "public_summary")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_RESULT_SCHEMA_VERSION,
            "result_id": self.result_id,
            "request_id": self.request_id,
            "status": self.status,
            "result_sha256": self.result_sha256,
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
            "public_summary": dict(self.public_summary),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, RUN_RESULT_SCHEMA_VERSION)
        return cls(
            result_id=require_str(record, "result_id"),
            request_id=require_str(record, "request_id"),
            status=require_str(record, "status"),
            result_sha256=require_str(record, "result_sha256"),
            artifacts=_artifact_tuple(optional_sequence(record, "artifacts") or ()),
            public_summary=optional_mapping(record, "public_summary") or {},
        )


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Top-level manifest for a deterministic multi-harness run."""

    run_id: str
    selection_sha256: str
    run_config_sha256: str
    request_ids: tuple[str, ...]
    result_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, "run_id")
        validate_sha256(self.selection_sha256, "selection_sha256")
        validate_sha256(self.run_config_sha256, "run_config_sha256")
        validate_unique_ids(self.request_ids, "request_ids")
        validate_unique_ids(self.result_ids, "result_ids")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "run_id": self.run_id,
            "selection_sha256": self.selection_sha256,
            "run_config_sha256": self.run_config_sha256,
            "request_ids": list(self.request_ids),
            "result_ids": list(self.result_ids),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, RUN_MANIFEST_SCHEMA_VERSION)
        return cls(
            run_id=require_str(record, "run_id"),
            selection_sha256=require_str(record, "selection_sha256"),
            run_config_sha256=require_str(record, "run_config_sha256"),
            request_ids=_str_tuple(
                require_sequence(record, "request_ids"), "request_ids"
            ),
            result_ids=_str_tuple(
                optional_sequence(record, "result_ids") or (),
                "result_ids",
            ),
        )


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    """Adapter conformance result consumed by community submission validation."""

    report_id: str
    adapter_id: str
    adapter_version: str
    status: str
    checks: Mapping[str, str]
    artifacts: tuple[ArtifactRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.report_id, "report_id")
        _require_non_empty(self.adapter_id, "adapter_id")
        _require_non_empty(self.adapter_version, "adapter_version")
        _require_member(self.status, CONFORMANCE_STATUSES, "status")
        if not self.checks:
            raise ValueError("checks must not be empty")
        for key, value in self.checks.items():
            _require_non_empty(key, "check key")
            _require_non_empty(value, f"check {key}")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": CONFORMANCE_REPORT_SCHEMA_VERSION,
            "report_id": self.report_id,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "status": self.status,
            "checks": dict(sorted(self.checks.items())),
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, CONFORMANCE_REPORT_SCHEMA_VERSION)
        return cls(
            report_id=require_str(record, "report_id"),
            adapter_id=require_str(record, "adapter_id"),
            adapter_version=require_str(record, "adapter_version"),
            status=require_str(record, "status"),
            checks=_str_mapping(require_mapping(record, "checks"), "checks"),
            artifacts=_artifact_tuple(optional_sequence(record, "artifacts") or ()),
        )


@dataclass(frozen=True, slots=True)
class CommunitySubmission:
    """A reviewed community submission manifest."""

    submission_id: str
    submitter: ContributorCredit
    contributors: tuple[ContributorCredit, ...]
    run_manifest_sha256: str
    artifacts: tuple[ArtifactRecord, ...]
    attestations: tuple[str, ...]
    public_summary: Mapping[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        _require_non_empty(self.submission_id, "submission_id")
        validate_sha256(self.run_manifest_sha256, "run_manifest_sha256")
        if not self.contributors:
            raise ValueError("contributors must not be empty")
        if not self.attestations:
            raise ValueError("attestations must not be empty")
        validate_unique_ids(
            (artifact.artifact_id for artifact in self.artifacts),
            "artifacts",
        )
        validate_public_record(self.to_record(), "community_submission")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": COMMUNITY_SUBMISSION_SCHEMA_VERSION,
            "submission_id": self.submission_id,
            "submitter": self.submitter.to_record(),
            "contributors": [credit.to_record() for credit in self.contributors],
            "run_manifest_sha256": self.run_manifest_sha256,
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
            "attestations": list(self.attestations),
            "public_summary": dict(self.public_summary),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_SUBMISSION_SCHEMA_VERSION)
        return cls(
            submission_id=require_str(record, "submission_id"),
            submitter=ContributorCredit.from_record(
                require_mapping(record, "submitter")
            ),
            contributors=_credit_tuple(require_sequence(record, "contributors")),
            run_manifest_sha256=require_str(record, "run_manifest_sha256"),
            artifacts=_artifact_tuple(require_sequence(record, "artifacts")),
            attestations=_str_tuple(
                require_sequence(record, "attestations"), "attestations"
            ),
            public_summary=optional_mapping(record, "public_summary") or {},
        )


@dataclass(frozen=True, slots=True)
class CommunityAggregate:
    """Public aggregate derived from accepted community submissions."""

    aggregate_id: str
    submissions: tuple[str, ...]
    aggregate_sha256: str
    public_summary: Mapping[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        _require_non_empty(self.aggregate_id, "aggregate_id")
        if not self.submissions:
            raise ValueError("submissions must not be empty")
        validate_unique_ids(self.submissions, "submissions")
        validate_sha256(self.aggregate_sha256, "aggregate_sha256")
        validate_public_record(self.to_record(), "community_aggregate")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": COMMUNITY_AGGREGATE_SCHEMA_VERSION,
            "aggregate_id": self.aggregate_id,
            "submissions": list(self.submissions),
            "aggregate_sha256": self.aggregate_sha256,
            "public_summary": dict(self.public_summary),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_AGGREGATE_SCHEMA_VERSION)
        return cls(
            aggregate_id=require_str(record, "aggregate_id"),
            submissions=_str_tuple(
                require_sequence(record, "submissions"), "submissions"
            ),
            aggregate_sha256=require_str(record, "aggregate_sha256"),
            public_summary=optional_mapping(record, "public_summary") or {},
        )


def _artifact_tuple(records: Sequence[Any]) -> tuple[ArtifactRecord, ...]:
    return tuple(
        ArtifactRecord.from_record(_require_item_mapping(item, "artifacts"))
        for item in records
    )


def _credit_tuple(records: Sequence[Any]) -> tuple[ContributorCredit, ...]:
    return tuple(
        ContributorCredit.from_record(_require_item_mapping(item, "contributors"))
        for item in records
    )


def _task_tuple(records: Sequence[Any]) -> tuple[CanonicalTask, ...]:
    return tuple(
        CanonicalTask.from_record(_require_item_mapping(item, "tasks"))
        for item in records
    )


def _str_tuple(records: Sequence[Any], field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, value in enumerate(records):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        values.append(value)
    return tuple(values)


def _str_mapping(record: Mapping[str, Any], field_name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in record.items():
        if not key.strip():
            raise ValueError(f"{field_name} contains a non-string key")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}.{key} must be a non-empty string")
        result[key] = value
    return result


def _require_item_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} entries must be objects")
    return cast(Mapping[str, Any], value)


def _require_member(
    value: str, allowed: set[str] | frozenset[str], field_name: str
) -> None:
    if value not in allowed:
        formatted = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {formatted}")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
