"""Closed local CLI adapter manifest for generic agentic CLIs.

This schema describes a local agentic CLI (Claude Code, Codex CLI, or a
future peer) to the existing multi-harness solver surface. It does not
replace frozen ``legalforecast.multiharness.adapter_manifest.v1``. B3
adapter cores load this record and implement ``HarnessAdapter`` /
``HarnessSolver``; they must not add provider-specific branches to the
root CLI.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Self, cast

from legalforecast.evals.inspect_task import SolverKind
from legalforecast.multiharness.harness_vocab import (
    AUTH_PROFILE_NAMES,
    LOCAL_CLI_ARGV_PLACEHOLDERS,
    LOCAL_CLI_AUTH_ENV_VARS,
    LOCAL_CLI_CAPABILITIES,
    LOCAL_CLI_CONTAINER_EXECUTION,
    LOCAL_CLI_COST_BASES,
    LOCAL_CLI_DELIVERABLE_SOURCES,
    LOCAL_CLI_DISTRIBUTION_KINDS,
    LOCAL_CLI_EMPTY_TOOLS,
    LOCAL_CLI_HEADLESS_MODES,
    LOCAL_CLI_NATIVE_TOOLS_ENABLED,
    LOCAL_CLI_OUTPUT_FORMATS,
    LOCAL_CLI_PROMPT_DELIVERY,
    LOCAL_CLI_PROMPT_SOURCES,
    LOCAL_CLI_RESTRICTED_EGRESS,
    LOCAL_CLI_SCHEMA_ENFORCEMENT,
    LOCAL_CLI_SERVER_SIDE_WEB_TOOLS_DISABLED,
    LOCAL_CLI_SESSION_PERSISTENCE,
    LOCAL_CLI_SETTING_SOURCES,
    LOCAL_CLI_TRANSCRIPT_POINTS,
    LOCAL_CLI_USAGE_SOLVER_FIELDS,
)
from legalforecast.multiharness.sandbox import NETWORK_NONE, PROVIDER_EGRESS_HOST_ONLY
from legalforecast.multiharness.spec import (
    HOST_PROCESS_CONTAINMENT_MODES,
    SCORING_MODES,
    TASK_FAMILIES,
    AdapterCapabilities,
    AdapterManifest,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    require_mapping,
    require_schema_version,
    require_sequence,
    require_str,
    validate_public_record,
    validate_safe_relative_path,
    validate_sha256,
    validate_unique_ids,
)

LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION = (
    # contract-ratchet: allow adapter description schema
    "legalforecast.multiharness.local_cli_adapter_manifest.v1"
)
LOCAL_CLI_ADAPTER_KIND = "local_cli"
SOLVER_RESPONSE_CONTRACT = "legalforecast.evals.inspect_task.SolverResponse"
HARNESS_ADAPTER_CONTRACT = "legalforecast.multiharness.adapters.HarnessAdapter"
HARNESS_SOLVER_CONTRACT = "legalforecast.evals.inspect_task.HarnessSolver"

_BASENAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")
_DOTTED_PATH_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*\Z")
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_id",
        "display_name",
        "adapter_kind",
        "executable",
        "capabilities",
        "capability_digest",
        "invocation",
        "auth_profile_name",
        "supported_auth_profiles",
        "auth_environment_variables",
        "containment",
        "timeout_retry",
        "transcript_capture",
        "usage_reporting",
        "task_projection",
        "harness_binding",
    }
)
_EXECUTABLE_FIELDS = frozenset(
    {
        "basename",
        "version",
        "sha256",
        "container_image_digest",
        "distribution_kind",
    }
)
# Exactly one of these is present on any manifest, so both are absent-allowed
# keys and the exactly-one rule below is what makes the pair required.
_EXECUTABLE_OPTIONAL_FIELDS = frozenset({"sha256", "container_image_digest"})
_INVOCATION_FIELDS = frozenset(
    {
        "headless_mode",
        "argv_template",
        "output_format",
        "schema_enforcement",
        "prompt_delivery",
        "working_directory_flag",
        "model_flag",
    }
)
_CONTAINMENT_FIELDS = frozenset(
    {
        "host_process_containment",
        "network_policy",
        "isolated_host_environment",
        "session_persistence",
        "setting_sources",
        "strict_mcp_config",
    }
)
_TIMEOUT_RETRY_FIELDS = frozenset(
    {
        "timeout_seconds",
        "max_attempts",
        "retry_backoff_seconds",
        "retryable_exit_codes",
    }
)
_TRANSCRIPT_FIELDS = frozenset({"points", "public_raw_transcript"})
_USAGE_FIELDS = frozenset(
    {
        "input_tokens_field",
        "output_tokens_field",
        "cache_read_tokens_field",
        "cache_write_tokens_field",
        "cost_usd_field",
        "cost_basis",
        "solver_response_fields",
    }
)
_TASK_PROJECTION_FIELDS = frozenset(
    {
        "prompt_source",
        "deliverable_source",
        "deliverable_relative_path",
        "deliverable_event_type",
        "deliverable_item_type",
        "deliverable_field",
    }
)
_HARNESS_BINDING_FIELDS = frozenset(
    {
        "adapter_id",
        "adapter_version",
        "supported_families",
        "supported_scoring_modes",
        "tool_protocol_version",
        "implements_harness_adapter",
        "implements_harness_solver",
        "harness_adapter_contract",
        "harness_solver_contract",
        "solver_response_contract",
        "solver_kind",
    }
)
_NETWORK_POLICIES = frozenset({NETWORK_NONE, PROVIDER_EGRESS_HOST_ONLY})
_SOLVER_KINDS = frozenset(member.value for member in SolverKind)


class LocalCliAdapterManifestError(MultiHarnessValidationError):
    """Raised when a local CLI adapter manifest is invalid."""


@dataclass(frozen=True, slots=True)
class LocalCliExecutableIdentity:
    """Public executable identity without host paths.

    A host-executed CLI is pinned by ``sha256`` over the executable bytes.  A
    containerized CLI is pinned by ``container_image_digest`` instead: the host
    binary is not what runs, so hashing it would verify the wrong file, and the
    image digest is the only identity that covers the interpreter, the CLI, and
    its dependencies together.  Exactly one of the two is set, so a manifest
    cannot quietly inherit the host-pin pattern into a container.
    """

    basename: str
    version: str
    sha256: str | None
    distribution_kind: str
    container_image_digest: str | None = None

    def __post_init__(self) -> None:
        if _BASENAME_RE.fullmatch(self.basename) is None:
            raise LocalCliAdapterManifestError(
                "executable.basename must be a pathless command name"
            )
        _require_non_empty(self.version, "executable.version")
        if (self.sha256 is None) == (self.container_image_digest is None):
            raise LocalCliAdapterManifestError(
                "executable must set exactly one of sha256 (host executable "
                "bytes) or container_image_digest (containerized harness)"
            )
        if self.sha256 is not None:
            validate_sha256(self.sha256, "executable.sha256", allow_prefix=False)
        if self.container_image_digest is not None:
            # The registry form, so an operator pastes `docker inspect` output
            # without transforming it, and so the two pins never look alike.
            if not self.container_image_digest.startswith("sha256:"):
                raise LocalCliAdapterManifestError(
                    "executable.container_image_digest must be sha256:-prefixed"
                )
            validate_sha256(
                self.container_image_digest, "executable.container_image_digest"
            )
        _require_member(
            self.distribution_kind,
            LOCAL_CLI_DISTRIBUTION_KINDS,
            "executable.distribution_kind",
        )

    def to_record(self) -> dict[str, str]:
        record = {
            "basename": self.basename,
            "version": self.version,
            "distribution_kind": self.distribution_kind,
        }
        if self.sha256 is not None:
            record["sha256"] = self.sha256
        if self.container_image_digest is not None:
            record["container_image_digest"] = self.container_image_digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            record,
            _EXECUTABLE_FIELDS,
            "executable",
            optional=_EXECUTABLE_OPTIONAL_FIELDS,
        )
        return cls(
            basename=require_str(record, "basename"),
            version=require_str(record, "version"),
            sha256=_optional_str(record, "sha256"),
            distribution_kind=require_str(record, "distribution_kind"),
            container_image_digest=_optional_str(record, "container_image_digest"),
        )


@dataclass(frozen=True, slots=True)
class LocalCliInvocation:
    """Headless invocation template with a closed placeholder vocabulary."""

    headless_mode: str
    argv_template: tuple[str, ...]
    output_format: str
    schema_enforcement: str
    prompt_delivery: str
    working_directory_flag: str | None
    model_flag: str | None

    def __post_init__(self) -> None:
        _require_member(self.headless_mode, LOCAL_CLI_HEADLESS_MODES, "headless_mode")
        if not self.argv_template:
            raise LocalCliAdapterManifestError(
                "invocation.argv_template must not be empty"
            )
        placeholders = _placeholders_in(self.argv_template)
        unknown = placeholders.difference(LOCAL_CLI_ARGV_PLACEHOLDERS)
        if unknown:
            formatted = ", ".join(sorted(unknown))
            raise LocalCliAdapterManifestError(
                f"invocation.argv_template has unknown placeholder(s): {formatted}"
            )
        for token in self.argv_template:
            if "/" in token or "\\" in token or token.startswith("~"):
                raise LocalCliAdapterManifestError(
                    "invocation.argv_template must not contain host paths"
                )
        _require_member(self.output_format, LOCAL_CLI_OUTPUT_FORMATS, "output_format")
        _require_member(
            self.schema_enforcement,
            LOCAL_CLI_SCHEMA_ENFORCEMENT,
            "schema_enforcement",
        )
        _require_member(
            self.prompt_delivery,
            LOCAL_CLI_PROMPT_DELIVERY,
            "prompt_delivery",
        )
        if self.prompt_delivery == "argv_placeholder" and "prompt" not in placeholders:
            raise LocalCliAdapterManifestError(
                "argv_placeholder prompt delivery requires {prompt}"
            )
        if self.prompt_delivery == "stdin" and "prompt" in placeholders:
            raise LocalCliAdapterManifestError(
                "stdin prompt delivery must not use {prompt}"
            )
        if self.schema_enforcement == "json_schema_flag":
            if "output_schema" not in placeholders:
                raise LocalCliAdapterManifestError(
                    "json_schema_flag requires {output_schema}"
                )
            if "output_schema_path" in placeholders:
                raise LocalCliAdapterManifestError(
                    "json_schema_flag must not use {output_schema_path}"
                )
        elif self.schema_enforcement == "output_schema_file":
            if "output_schema_path" not in placeholders:
                raise LocalCliAdapterManifestError(
                    "output_schema_file requires {output_schema_path}"
                )
            if "output_schema" in placeholders:
                raise LocalCliAdapterManifestError(
                    "output_schema_file must not use {output_schema}"
                )
        elif self.schema_enforcement == "none":
            if "output_schema" in placeholders or "output_schema_path" in placeholders:
                raise LocalCliAdapterManifestError(
                    "schema_enforcement none must not use {output_schema} or "
                    "{output_schema_path}"
                )
        if self.working_directory_flag is not None:
            _require_flag_name(self.working_directory_flag, "working_directory_flag")
            if "workspace" not in placeholders:
                raise LocalCliAdapterManifestError(
                    "working_directory_flag requires {workspace}"
                )
            if self.working_directory_flag not in self.argv_template:
                raise LocalCliAdapterManifestError(
                    "working_directory_flag must appear in argv_template"
                )
        if self.model_flag is not None:
            _require_flag_name(self.model_flag, "model_flag")
            if "model" not in placeholders:
                raise LocalCliAdapterManifestError("model_flag requires {model}")
            if self.model_flag not in self.argv_template:
                raise LocalCliAdapterManifestError(
                    "model_flag must appear in argv_template"
                )

    def to_record(self) -> dict[str, Any]:
        return {
            "headless_mode": self.headless_mode,
            "argv_template": list(self.argv_template),
            "output_format": self.output_format,
            "schema_enforcement": self.schema_enforcement,
            "prompt_delivery": self.prompt_delivery,
            "working_directory_flag": self.working_directory_flag,
            "model_flag": self.model_flag,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _INVOCATION_FIELDS, "invocation")
        return cls(
            headless_mode=require_str(record, "headless_mode"),
            argv_template=_str_tuple_allow_empty(
                require_sequence(record, "argv_template"),
                "invocation.argv_template",
            ),
            output_format=require_str(record, "output_format"),
            schema_enforcement=require_str(record, "schema_enforcement"),
            prompt_delivery=require_str(record, "prompt_delivery"),
            working_directory_flag=_optional_str(record, "working_directory_flag"),
            model_flag=_optional_str(record, "model_flag"),
        )

    def render_argv(
        self,
        *,
        prompt: str,
        model: str,
        workspace: str,
        output_schema: str | None = None,
        output_schema_path: str | None = None,
    ) -> tuple[str, ...]:
        """Substitute closed placeholders without shell interpolation."""

        values = {
            "prompt": prompt,
            "model": model,
            "workspace": workspace,
        }
        placeholders = _placeholders_in(self.argv_template)
        if "output_schema" in placeholders:
            if output_schema is None:
                raise LocalCliAdapterManifestError("{output_schema} is required")
            values["output_schema"] = output_schema
        if "output_schema_path" in placeholders:
            if output_schema_path is None:
                raise LocalCliAdapterManifestError("{output_schema_path} is required")
            values["output_schema_path"] = output_schema_path
        rendered: list[str] = []
        for token in self.argv_template:
            rendered.append(
                _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], token)
            )
        return tuple(rendered)


@dataclass(frozen=True, slots=True)
class LocalCliContainment:
    """Host-owned containment requirements referenced by sandbox policy."""

    host_process_containment: str
    network_policy: str
    isolated_host_environment: bool
    session_persistence: str
    setting_sources: tuple[str, ...]
    strict_mcp_config: bool

    def __post_init__(self) -> None:
        _require_member(
            self.host_process_containment,
            HOST_PROCESS_CONTAINMENT_MODES,
            "host_process_containment",
        )
        _require_member(self.network_policy, _NETWORK_POLICIES, "network_policy")
        _require_bool(self.isolated_host_environment, "isolated_host_environment")
        _require_member(
            self.session_persistence,
            LOCAL_CLI_SESSION_PERSISTENCE,
            "session_persistence",
        )
        validate_unique_ids(self.setting_sources, "setting_sources")
        for source in self.setting_sources:
            _require_member(source, LOCAL_CLI_SETTING_SOURCES, "setting_sources")
        _require_bool(self.strict_mcp_config, "strict_mcp_config")

    def to_record(self) -> dict[str, Any]:
        return {
            "host_process_containment": self.host_process_containment,
            "network_policy": self.network_policy,
            "isolated_host_environment": self.isolated_host_environment,
            "session_persistence": self.session_persistence,
            "setting_sources": list(self.setting_sources),
            "strict_mcp_config": self.strict_mcp_config,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _CONTAINMENT_FIELDS, "containment")
        return cls(
            host_process_containment=require_str(record, "host_process_containment"),
            network_policy=require_str(record, "network_policy"),
            isolated_host_environment=_require_bool_field(
                record, "isolated_host_environment"
            ),
            session_persistence=require_str(record, "session_persistence"),
            setting_sources=_str_tuple(
                require_sequence(record, "setting_sources"),
                "containment.setting_sources",
            ),
            strict_mcp_config=_require_bool_field(record, "strict_mcp_config"),
        )


@dataclass(frozen=True, slots=True)
class LocalCliTimeoutRetry:
    """Timeout and retry policy aligned with the live solver defaults."""

    timeout_seconds: int
    max_attempts: int
    retry_backoff_seconds: int
    retryable_exit_codes: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_positive_int(self.timeout_seconds, "timeout_seconds")
        _require_positive_int(self.max_attempts, "max_attempts")
        if self.retry_backoff_seconds < 0:
            raise LocalCliAdapterManifestError(
                "retry_backoff_seconds must be non-negative"
            )
        if type(self.retry_backoff_seconds) is not int:
            raise LocalCliAdapterManifestError(
                "retry_backoff_seconds must be an integer"
            )
        for code in self.retryable_exit_codes:
            if type(code) is not int or isinstance(code, bool) or code < 0:
                raise LocalCliAdapterManifestError(
                    "retryable_exit_codes must contain non-negative integers"
                )
        if self.max_attempts > 1 and not self.retryable_exit_codes:
            raise LocalCliAdapterManifestError(
                "max_attempts greater than 1 requires retryable_exit_codes"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "retry_backoff_seconds": self.retry_backoff_seconds,
            "retryable_exit_codes": list(self.retryable_exit_codes),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _TIMEOUT_RETRY_FIELDS, "timeout_retry")
        return cls(
            timeout_seconds=_require_int(record, "timeout_seconds"),
            max_attempts=_require_int(record, "max_attempts"),
            retry_backoff_seconds=_require_int(record, "retry_backoff_seconds"),
            retryable_exit_codes=_int_tuple(
                require_sequence(record, "retryable_exit_codes"),
                "timeout_retry.retryable_exit_codes",
            ),
        )


@dataclass(frozen=True, slots=True)
class LocalCliTranscriptCapture:
    """Where the adapter may copy CLI output. Raw transcripts stay private."""

    points: tuple[str, ...]
    public_raw_transcript: bool

    def __post_init__(self) -> None:
        if not self.points:
            raise LocalCliAdapterManifestError(
                "transcript_capture.points must not be empty"
            )
        validate_unique_ids(self.points, "transcript_capture.points")
        for point in self.points:
            _require_member(
                point, LOCAL_CLI_TRANSCRIPT_POINTS, "transcript_capture.points"
            )
        _require_bool(self.public_raw_transcript, "public_raw_transcript")
        if self.public_raw_transcript:
            raise LocalCliAdapterManifestError(
                "transcript_capture.public_raw_transcript must be false"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "points": list(self.points),
            "public_raw_transcript": self.public_raw_transcript,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _TRANSCRIPT_FIELDS, "transcript_capture")
        return cls(
            points=_str_tuple(
                require_sequence(record, "points"), "transcript_capture.points"
            ),
            public_raw_transcript=_require_bool_field(record, "public_raw_transcript"),
        )


@dataclass(frozen=True, slots=True)
class LocalCliUsageReporting:
    """Map CLI envelope fields onto SolverResponse accounting attributes."""

    input_tokens_field: str
    output_tokens_field: str
    cache_read_tokens_field: str | None
    cache_write_tokens_field: str | None
    cost_usd_field: str | None
    cost_basis: str
    solver_response_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_dotted_path(self.input_tokens_field, "input_tokens_field")
        _require_dotted_path(self.output_tokens_field, "output_tokens_field")
        if self.cache_read_tokens_field is not None:
            _require_dotted_path(
                self.cache_read_tokens_field, "cache_read_tokens_field"
            )
        if self.cache_write_tokens_field is not None:
            _require_dotted_path(
                self.cache_write_tokens_field, "cache_write_tokens_field"
            )
        if self.cost_usd_field is not None:
            _require_dotted_path(self.cost_usd_field, "cost_usd_field")
        _require_member(self.cost_basis, LOCAL_CLI_COST_BASES, "cost_basis")
        if not self.solver_response_fields:
            raise LocalCliAdapterManifestError(
                "usage_reporting.solver_response_fields must not be empty"
            )
        validate_unique_ids(self.solver_response_fields, "solver_response_fields")
        for field_name in self.solver_response_fields:
            _require_member(
                field_name,
                LOCAL_CLI_USAGE_SOLVER_FIELDS,
                "solver_response_fields",
            )
        required = {"input_tokens", "output_tokens"}
        missing = required.difference(self.solver_response_fields)
        if missing:
            formatted = ", ".join(sorted(missing))
            raise LocalCliAdapterManifestError(
                f"usage_reporting.solver_response_fields missing {formatted}"
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "input_tokens_field": self.input_tokens_field,
            "output_tokens_field": self.output_tokens_field,
            "cache_read_tokens_field": self.cache_read_tokens_field,
            "cache_write_tokens_field": self.cache_write_tokens_field,
            "cost_usd_field": self.cost_usd_field,
            "cost_basis": self.cost_basis,
            "solver_response_fields": list(self.solver_response_fields),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _USAGE_FIELDS, "usage_reporting")
        return cls(
            input_tokens_field=require_str(record, "input_tokens_field"),
            output_tokens_field=require_str(record, "output_tokens_field"),
            cache_read_tokens_field=_optional_str(record, "cache_read_tokens_field"),
            cache_write_tokens_field=_optional_str(record, "cache_write_tokens_field"),
            cost_usd_field=_optional_str(record, "cost_usd_field"),
            cost_basis=require_str(record, "cost_basis"),
            solver_response_fields=_str_tuple(
                require_sequence(record, "solver_response_fields"),
                "usage_reporting.solver_response_fields",
            ),
        )


@dataclass(frozen=True, slots=True)
class LocalCliTaskProjection:
    """Project solver-input prompt and sealed deliverable onto the CLI."""

    prompt_source: str
    deliverable_source: str
    deliverable_relative_path: str | None
    deliverable_event_type: str | None
    deliverable_item_type: str | None
    deliverable_field: str | None

    def __post_init__(self) -> None:
        _require_member(self.prompt_source, LOCAL_CLI_PROMPT_SOURCES, "prompt_source")
        _require_member(
            self.deliverable_source,
            LOCAL_CLI_DELIVERABLE_SOURCES,
            "deliverable_source",
        )
        if self.deliverable_event_type is not None:
            _require_dotted_path(self.deliverable_event_type, "deliverable_event_type")
        if self.deliverable_item_type is not None:
            _require_dotted_path(self.deliverable_item_type, "deliverable_item_type")
        if self.deliverable_field is not None:
            _require_dotted_path(self.deliverable_field, "deliverable_field")
        if self.deliverable_source == "workspace_relative_file":
            if self.deliverable_relative_path is None:
                raise LocalCliAdapterManifestError(
                    "workspace_relative_file requires deliverable_relative_path"
                )
            validate_safe_relative_path(
                self.deliverable_relative_path,
                "deliverable_relative_path",
            )
            if (
                self.deliverable_event_type is not None
                or self.deliverable_item_type is not None
                or self.deliverable_field is not None
            ):
                raise LocalCliAdapterManifestError(
                    "workspace_relative_file forbids deliverable event/field projection"
                )
        else:
            if self.deliverable_relative_path is not None:
                raise LocalCliAdapterManifestError(
                    "structured_stdout forbids deliverable_relative_path"
                )
            if self.deliverable_field is None:
                raise LocalCliAdapterManifestError(
                    "structured_stdout requires deliverable_field"
                )

    def to_record(self) -> dict[str, Any]:
        return {
            "prompt_source": self.prompt_source,
            "deliverable_source": self.deliverable_source,
            "deliverable_relative_path": self.deliverable_relative_path,
            "deliverable_event_type": self.deliverable_event_type,
            "deliverable_item_type": self.deliverable_item_type,
            "deliverable_field": self.deliverable_field,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _TASK_PROJECTION_FIELDS, "task_projection")
        return cls(
            prompt_source=require_str(record, "prompt_source"),
            deliverable_source=require_str(record, "deliverable_source"),
            deliverable_relative_path=_optional_str(
                record, "deliverable_relative_path"
            ),
            deliverable_event_type=_optional_str(record, "deliverable_event_type"),
            deliverable_item_type=_optional_str(record, "deliverable_item_type"),
            deliverable_field=_optional_str(record, "deliverable_field"),
        )


@dataclass(frozen=True, slots=True)
class LocalCliHarnessBinding:
    """Bind the CLI description to existing adapter/solver contracts."""

    adapter_id: str
    adapter_version: str
    supported_families: tuple[str, ...]
    supported_scoring_modes: tuple[str, ...]
    tool_protocol_version: str | None
    implements_harness_adapter: bool
    implements_harness_solver: bool
    harness_adapter_contract: str
    harness_solver_contract: str
    solver_response_contract: str
    solver_kind: str

    def __post_init__(self) -> None:
        _require_non_empty(self.adapter_id, "adapter_id")
        _require_non_empty(self.adapter_version, "adapter_version")
        if not self.supported_families:
            raise LocalCliAdapterManifestError("supported_families must not be empty")
        if not self.supported_scoring_modes:
            raise LocalCliAdapterManifestError(
                "supported_scoring_modes must not be empty"
            )
        validate_unique_ids(self.supported_families, "supported_families")
        validate_unique_ids(self.supported_scoring_modes, "supported_scoring_modes")
        for family in self.supported_families:
            _require_member(family, TASK_FAMILIES, "supported_families")
        for mode in self.supported_scoring_modes:
            _require_member(mode, SCORING_MODES, "supported_scoring_modes")
        if self.tool_protocol_version is not None:
            _require_non_empty(self.tool_protocol_version, "tool_protocol_version")
        _require_bool(self.implements_harness_adapter, "implements_harness_adapter")
        _require_bool(self.implements_harness_solver, "implements_harness_solver")
        if not self.implements_harness_adapter and not self.implements_harness_solver:
            raise LocalCliAdapterManifestError(
                "harness_binding must implement HarnessAdapter or HarnessSolver"
            )
        if self.harness_adapter_contract != HARNESS_ADAPTER_CONTRACT:
            raise LocalCliAdapterManifestError(
                "harness_adapter_contract must be the existing HarnessAdapter"
            )
        if self.harness_solver_contract != HARNESS_SOLVER_CONTRACT:
            raise LocalCliAdapterManifestError(
                "harness_solver_contract must be the existing HarnessSolver"
            )
        if self.solver_response_contract != SOLVER_RESPONSE_CONTRACT:
            raise LocalCliAdapterManifestError(
                "solver_response_contract must be the existing SolverResponse"
            )
        _require_member(self.solver_kind, _SOLVER_KINDS, "solver_kind")

    def to_record(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "supported_families": list(self.supported_families),
            "supported_scoring_modes": list(self.supported_scoring_modes),
            "tool_protocol_version": self.tool_protocol_version,
            "implements_harness_adapter": self.implements_harness_adapter,
            "implements_harness_solver": self.implements_harness_solver,
            "harness_adapter_contract": self.harness_adapter_contract,
            "harness_solver_contract": self.harness_solver_contract,
            "solver_response_contract": self.solver_response_contract,
            "solver_kind": self.solver_kind,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _HARNESS_BINDING_FIELDS, "harness_binding")
        return cls(
            adapter_id=require_str(record, "adapter_id"),
            adapter_version=require_str(record, "adapter_version"),
            supported_families=_str_tuple(
                require_sequence(record, "supported_families"),
                "harness_binding.supported_families",
            ),
            supported_scoring_modes=_str_tuple(
                require_sequence(record, "supported_scoring_modes"),
                "harness_binding.supported_scoring_modes",
            ),
            tool_protocol_version=_optional_str(record, "tool_protocol_version"),
            implements_harness_adapter=_require_bool_field(
                record, "implements_harness_adapter"
            ),
            implements_harness_solver=_require_bool_field(
                record, "implements_harness_solver"
            ),
            harness_adapter_contract=require_str(record, "harness_adapter_contract"),
            harness_solver_contract=require_str(record, "harness_solver_contract"),
            solver_response_contract=require_str(record, "solver_response_contract"),
            solver_kind=require_str(record, "solver_kind"),
        )

    def to_adapter_manifest(
        self, *, display_name: str, command: tuple[str, ...]
    ) -> AdapterManifest:
        """Public identity for the B3 wrapper, not CommandAdapter argv."""

        if not command:
            raise LocalCliAdapterManifestError(
                "adapter manifest command must not be empty"
            )
        return AdapterManifest(
            adapter_id=self.adapter_id,
            display_name=display_name,
            adapter_version=self.adapter_version,
            command=command,
        )

    def to_adapter_capabilities(
        self, *, capabilities_sha256: str
    ) -> AdapterCapabilities:
        """Capability advertisement consumed by CommandAdapter.prepare."""

        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            supported_families=self.supported_families,
            supported_scoring_modes=self.supported_scoring_modes,
            capabilities_sha256=capabilities_sha256,
            supports_sandbox_policy=True,
            tool_protocol_version=self.tool_protocol_version,
        )


@dataclass(frozen=True, slots=True)
class LocalCliAdapterManifest:
    """Closed generic local CLI adapter manifest."""

    manifest_id: str
    display_name: str
    executable: LocalCliExecutableIdentity
    capabilities: tuple[str, ...]
    capability_digest: str
    invocation: LocalCliInvocation
    auth_profile_name: str
    supported_auth_profiles: tuple[str, ...]
    auth_environment_variables: tuple[tuple[str, tuple[str, ...]], ...]
    containment: LocalCliContainment
    timeout_retry: LocalCliTimeoutRetry
    transcript_capture: LocalCliTranscriptCapture
    usage_reporting: LocalCliUsageReporting
    task_projection: LocalCliTaskProjection
    harness_binding: LocalCliHarnessBinding
    adapter_kind: str = LOCAL_CLI_ADAPTER_KIND
    schema_version: str = LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_non_empty(self.manifest_id, "manifest_id")
        _require_non_empty(self.display_name, "display_name")
        if self.adapter_kind != LOCAL_CLI_ADAPTER_KIND:
            raise LocalCliAdapterManifestError(
                f"adapter_kind must be {LOCAL_CLI_ADAPTER_KIND}"
            )
        if self.schema_version != LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION:
            raise LocalCliAdapterManifestError(
                f"schema_version must be {LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION}"
            )
        if not self.capabilities:
            raise LocalCliAdapterManifestError("capabilities must not be empty")
        validate_unique_ids(self.capabilities, "capabilities")
        declared = set(self.capabilities)
        unknown = declared.difference(LOCAL_CLI_CAPABILITIES)
        if unknown:
            formatted = ", ".join(sorted(unknown))
            raise LocalCliAdapterManifestError(
                f"capabilities contains unknown token(s): {formatted}"
            )
        if {LOCAL_CLI_EMPTY_TOOLS, LOCAL_CLI_NATIVE_TOOLS_ENABLED} <= declared:
            raise LocalCliAdapterManifestError(
                "capabilities must not declare both empty_tools and "
                "native_tools_enabled"
            )
        if (
            LOCAL_CLI_NATIVE_TOOLS_ENABLED in declared
            and LOCAL_CLI_SERVER_SIDE_WEB_TOOLS_DISABLED not in declared
        ):
            raise LocalCliAdapterManifestError(
                "native_tools_enabled requires server_side_web_tools_disabled: "
                "no container egress rule can stop provider-executed web search"
            )
        if (LOCAL_CLI_CONTAINER_EXECUTION in declared) != (
            self.executable.container_image_digest is not None
        ):
            raise LocalCliAdapterManifestError(
                "container_execution and executable.container_image_digest must "
                "be declared together"
            )
        if (
            LOCAL_CLI_RESTRICTED_EGRESS in declared
            and self.containment.network_policy != PROVIDER_EGRESS_HOST_ONLY
        ):
            raise LocalCliAdapterManifestError(
                "restricted_egress requires containment.network_policy "
                f"{PROVIDER_EGRESS_HOST_ONLY}"
            )
        _require_member(self.auth_profile_name, AUTH_PROFILE_NAMES, "auth_profile_name")
        if not self.supported_auth_profiles:
            raise LocalCliAdapterManifestError(
                "supported_auth_profiles must not be empty"
            )
        validate_unique_ids(self.supported_auth_profiles, "supported_auth_profiles")
        unknown_profiles = [
            name
            for name in self.supported_auth_profiles
            if name not in AUTH_PROFILE_NAMES
        ]
        if unknown_profiles:
            formatted = ", ".join(sorted(unknown_profiles))
            raise LocalCliAdapterManifestError(
                f"supported_auth_profiles contains unknown token(s): {formatted}"
            )
        if self.auth_profile_name not in self.supported_auth_profiles:
            raise LocalCliAdapterManifestError(
                "auth_profile_name must be listed in supported_auth_profiles"
            )
        env_profiles = {profile for profile, _names in self.auth_environment_variables}
        if env_profiles != set(self.supported_auth_profiles):
            raise LocalCliAdapterManifestError(
                "auth_environment_variables profiles must equal supported_auth_profiles"
            )
        for profile, names in self.auth_environment_variables:
            unknown_vars = [
                name for name in names if name not in LOCAL_CLI_AUTH_ENV_VARS
            ]
            if unknown_vars:
                formatted = ", ".join(sorted(unknown_vars))
                raise LocalCliAdapterManifestError(
                    f"auth_environment_variables.{profile} contains unknown "
                    f"env var(s): {formatted}"
                )
            if profile == "fixture-none" and names:
                raise LocalCliAdapterManifestError(
                    "fixture-none must not project environment variables"
                )
        validate_sha256(self.capability_digest, "capability_digest")
        expected = capability_digest_for(self.to_record())
        if self.capability_digest != expected:
            raise LocalCliAdapterManifestError(
                "capability_digest does not match the canonical capability payload"
            )
        if self.harness_binding.adapter_id != self.manifest_id:
            raise LocalCliAdapterManifestError(
                "harness_binding.adapter_id must equal manifest_id"
            )
        if (
            self.invocation.output_format == "json"
            and "json_output" not in self.capabilities
        ):
            raise LocalCliAdapterManifestError(
                "output_format json requires the json_output capability"
            )
        if (
            self.invocation.output_format == "stream_json"
            and "stream_json_output" not in self.capabilities
        ):
            raise LocalCliAdapterManifestError(
                "output_format stream_json requires the stream_json_output capability"
            )
        if self.task_projection.deliverable_source == "structured_stdout":
            if self.invocation.output_format == "stream_json":
                if self.task_projection.deliverable_event_type is None:
                    raise LocalCliAdapterManifestError(
                        "stream_json structured_stdout requires deliverable_event_type"
                    )
            elif self.invocation.output_format == "json":
                if (
                    self.task_projection.deliverable_event_type is not None
                    or self.task_projection.deliverable_item_type is not None
                ):
                    raise LocalCliAdapterManifestError(
                        "json structured_stdout must not set deliverable_event_type "
                        "or deliverable_item_type"
                    )
        validate_public_record(self.to_record(), "local_cli_adapter_manifest")

    def env_vars_for_profile(self, profile_id: str) -> tuple[str, ...]:
        """Return projected environment names declared for one profile."""

        for profile, names in self.auth_environment_variables:
            if profile == profile_id:
                return names
        raise LocalCliAdapterManifestError(
            f"auth_environment_variables has no entry for {profile_id}"
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "display_name": self.display_name,
            "adapter_kind": self.adapter_kind,
            "executable": self.executable.to_record(),
            "capabilities": list(self.capabilities),
            "capability_digest": self.capability_digest,
            "invocation": self.invocation.to_record(),
            "auth_profile_name": self.auth_profile_name,
            "supported_auth_profiles": list(self.supported_auth_profiles),
            "auth_environment_variables": [
                {"names": list(names), "profile": profile}
                for profile, names in self.auth_environment_variables
            ],
            "containment": self.containment.to_record(),
            "timeout_retry": self.timeout_retry.to_record(),
            "transcript_capture": self.transcript_capture.to_record(),
            "usage_reporting": self.usage_reporting.to_record(),
            "task_projection": self.task_projection.to_record(),
            "harness_binding": self.harness_binding.to_record(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        _require_exact_fields(record, _MANIFEST_FIELDS, "local_cli_adapter_manifest")
        require_schema_version(record, LOCAL_CLI_ADAPTER_MANIFEST_SCHEMA_VERSION)
        return cls(
            schema_version=require_str(record, "schema_version"),
            manifest_id=require_str(record, "manifest_id"),
            display_name=require_str(record, "display_name"),
            adapter_kind=require_str(record, "adapter_kind"),
            executable=LocalCliExecutableIdentity.from_record(
                require_mapping(record, "executable")
            ),
            capabilities=_str_tuple(
                require_sequence(record, "capabilities"), "capabilities"
            ),
            capability_digest=require_str(record, "capability_digest"),
            invocation=LocalCliInvocation.from_record(
                require_mapping(record, "invocation")
            ),
            auth_profile_name=require_str(record, "auth_profile_name"),
            supported_auth_profiles=_str_tuple(
                require_sequence(record, "supported_auth_profiles"),
                "supported_auth_profiles",
            ),
            auth_environment_variables=_auth_environment_variables_from_record(
                require_sequence(record, "auth_environment_variables"),
            ),
            containment=LocalCliContainment.from_record(
                require_mapping(record, "containment")
            ),
            timeout_retry=LocalCliTimeoutRetry.from_record(
                require_mapping(record, "timeout_retry")
            ),
            transcript_capture=LocalCliTranscriptCapture.from_record(
                require_mapping(record, "transcript_capture")
            ),
            usage_reporting=LocalCliUsageReporting.from_record(
                require_mapping(record, "usage_reporting")
            ),
            task_projection=LocalCliTaskProjection.from_record(
                require_mapping(record, "task_projection")
            ),
            harness_binding=LocalCliHarnessBinding.from_record(
                require_mapping(record, "harness_binding")
            ),
        )

    def to_adapter_manifest(self, *, command: Sequence[str]) -> AdapterManifest:
        """Wrapper identity for the B3 HarnessAdapter, not the target CLI."""

        if isinstance(command, (str, bytes, bytearray)):
            raise LocalCliAdapterManifestError(
                "adapter manifest command must be an argv sequence, not a string"
            )
        wrapper = tuple(command)
        basename = self.executable.basename
        for token in wrapper:
            names = {token, PurePosixPath(token).name, PureWindowsPath(token).name}
            if basename in names:
                raise LocalCliAdapterManifestError(
                    "adapter manifest command must not include the target CLI basename"
                )
        return self.harness_binding.to_adapter_manifest(
            display_name=self.display_name,
            command=wrapper,
        )

    def to_adapter_capabilities(self) -> AdapterCapabilities:
        """Existing AdapterCapabilities record for prepare/run gating."""

        return self.harness_binding.to_adapter_capabilities(
            capabilities_sha256=self.capability_digest,
        )


def capability_digest_for(record: Mapping[str, Any]) -> str:
    """Hash the capability payload, excluding executable identity."""

    payload = {
        "auth_environment_variables": record["auth_environment_variables"],
        "auth_profile_name": record["auth_profile_name"],
        "capabilities": record["capabilities"],
        "containment": record["containment"],
        "harness_binding": record["harness_binding"],
        "invocation": record["invocation"],
        "supported_auth_profiles": record["supported_auth_profiles"],
        "task_projection": record["task_projection"],
        "timeout_retry": record["timeout_retry"],
        "transcript_capture": record["transcript_capture"],
        "usage_reporting": record["usage_reporting"],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def project_structured_stdout_deliverable(
    stdout: str,
    *,
    output_format: str,
    projection: LocalCliTaskProjection,
) -> str:
    """Extract the deliverable text from JSON or JSONL stdout using the manifest.

    Wrappers must not hard-code provider event names. Codex JSONL uses
    ``item.completed`` / ``agent_message`` / ``item.text`` because the fixture
    says so, not because this helper knows about Codex.
    """

    if projection.deliverable_source != "structured_stdout":
        raise LocalCliAdapterManifestError(
            "deliverable_source must be structured_stdout"
        )
    field_path = projection.deliverable_field
    if field_path is None:
        raise LocalCliAdapterManifestError("deliverable_field is required")
    if output_format == "json":
        record = _parse_json_object(stdout)
        return _require_deliverable_text(
            _dotted_lookup(record, field_path),
            field_path,
        )
    if output_format == "stream_json":
        event_type = projection.deliverable_event_type
        if event_type is None:
            raise LocalCliAdapterManifestError(
                "stream_json structured_stdout requires deliverable_event_type"
            )
        matches: list[Mapping[str, Any]] = []
        for event in _parse_jsonl_objects(stdout):
            if event.get("type") != event_type:
                continue
            if projection.deliverable_item_type is not None:
                item = event.get("item")
                if not isinstance(item, dict):
                    continue
                item_record = cast(dict[str, Any], item)
                if item_record.get("type") != projection.deliverable_item_type:
                    continue
            matches.append(event)
        if not matches:
            raise LocalCliAdapterManifestError(
                "structured_stdout stream has no matching deliverable event"
            )
        return _require_deliverable_text(
            _dotted_lookup(matches[-1], field_path),
            field_path,
        )
    raise LocalCliAdapterManifestError(
        f"output_format {output_format} cannot project structured_stdout"
    )


def _placeholders_in(tokens: Sequence[str]) -> set[str]:
    names: set[str] = set()
    for token in tokens:
        names.update(_PLACEHOLDER_RE.findall(token))
    return names


def _parse_json_object(stdout: str) -> Mapping[str, Any]:
    text = stdout.strip()
    if not text:
        raise LocalCliAdapterManifestError("structured_stdout JSON is empty")
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LocalCliAdapterManifestError(
            "structured_stdout JSON is malformed"
        ) from exc
    if not isinstance(decoded, dict):
        raise LocalCliAdapterManifestError("structured_stdout JSON must be an object")
    return cast(Mapping[str, Any], decoded)


def _parse_jsonl_objects(stdout: str) -> tuple[Mapping[str, Any], ...]:
    events: list[Mapping[str, Any]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise LocalCliAdapterManifestError(
                "structured_stdout JSONL is malformed"
            ) from exc
        if not isinstance(decoded, dict):
            raise LocalCliAdapterManifestError(
                "structured_stdout JSONL events must be objects"
            )
        events.append(cast(Mapping[str, Any], decoded))
    return tuple(events)


def _dotted_lookup(record: Mapping[str, Any], path: str) -> object:
    current: Mapping[str, Any] = record
    parts = path.split(".")
    for index, part in enumerate(parts):
        if part not in current:
            return None
        value: object = current[part]
        if index == len(parts) - 1:
            return value
        if not isinstance(value, dict):
            return None
        current = cast(dict[str, Any], value)
    return None


def _require_deliverable_text(value: object, field_path: str) -> str:
    if isinstance(value, str):
        if not value.strip():
            raise LocalCliAdapterManifestError(
                f"deliverable_field {field_path} must be a non-empty string"
            )
        return value
    if isinstance(value, Mapping):
        record = cast(Mapping[str, Any], value)
        try:
            return (
                json.dumps(
                    dict(record),
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            )
        except (TypeError, ValueError) as exc:
            raise LocalCliAdapterManifestError(
                f"deliverable_field {field_path} must be JSON-serializable"
            ) from exc
    raise LocalCliAdapterManifestError(
        f"deliverable_field {field_path} must be a non-empty string or object"
    )


def _require_exact_fields(
    record: Mapping[str, Any],
    expected: frozenset[str],
    field_name: str,
    *,
    optional: frozenset[str] = frozenset(),
) -> None:
    missing = sorted(expected.difference(optional).difference(record))
    if missing:
        raise LocalCliAdapterManifestError(
            f"{field_name} has missing field(s): {', '.join(missing)}"
        )
    unexpected = sorted(set(record).difference(expected))
    if unexpected:
        raise LocalCliAdapterManifestError(
            f"{field_name} has unexpected field(s): {', '.join(unexpected)}"
        )


def _require_member(
    value: str, allowed: set[str] | frozenset[str], field_name: str
) -> None:
    if value not in allowed:
        formatted = ", ".join(sorted(allowed))
        raise LocalCliAdapterManifestError(f"{field_name} must be one of: {formatted}")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise LocalCliAdapterManifestError(f"{field_name} must be a non-empty string")


def _require_bool(value: bool, field_name: str) -> None:
    if type(value) is not bool:
        raise LocalCliAdapterManifestError(f"{field_name} must be a boolean")


def _require_bool_field(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if type(value) is not bool:
        raise LocalCliAdapterManifestError(f"{field_name} must be a boolean")
    return value


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int or isinstance(value, bool) or value <= 0:
        raise LocalCliAdapterManifestError(f"{field_name} must be a positive integer")


def _require_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if type(value) is not int or isinstance(value, bool):
        raise LocalCliAdapterManifestError(f"{field_name} must be an integer")
    return value


def _require_flag_name(value: str, field_name: str) -> None:
    if not value.startswith("--") or value.strip() != value or " " in value:
        raise LocalCliAdapterManifestError(
            f"{field_name} must be a long option such as --model"
        )


def _require_dotted_path(value: str, field_name: str) -> None:
    if _DOTTED_PATH_RE.fullmatch(value) is None:
        raise LocalCliAdapterManifestError(
            f"{field_name} must be a dotted envelope path"
        )


def _optional_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LocalCliAdapterManifestError(
            f"{field_name} must be a non-empty string or null"
        )
    return value


def _str_tuple(records: Sequence[Any], field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, value in enumerate(records):
        if not isinstance(value, str) or not value.strip():
            raise LocalCliAdapterManifestError(
                f"{field_name}[{index}] must be a non-empty string"
            )
        values.append(value)
    return tuple(values)


def _str_tuple_allow_empty(records: Sequence[Any], field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, value in enumerate(records):
        if not isinstance(value, str):
            raise LocalCliAdapterManifestError(
                f"{field_name}[{index}] must be a string"
            )
        values.append(value)
    return tuple(values)


def _int_tuple(records: Sequence[Any], field_name: str) -> tuple[int, ...]:
    values: list[int] = []
    for index, value in enumerate(records):
        if type(value) is not int or isinstance(value, bool) or value < 0:
            raise LocalCliAdapterManifestError(
                f"{field_name}[{index}] must be a non-negative integer"
            )
        values.append(value)
    return tuple(values)


def _auth_environment_variables_from_record(
    records: Sequence[Any],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    parsed: list[tuple[str, tuple[str, ...]]] = []
    seen: set[str] = set()
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            raise LocalCliAdapterManifestError(
                f"auth_environment_variables[{index}] must be an object"
            )
        entry = cast(Mapping[str, Any], item)
        _require_exact_fields(
            entry,
            frozenset({"names", "profile"}),
            f"auth_environment_variables[{index}]",
        )
        profile = require_str(entry, "profile")
        if profile in seen:
            raise LocalCliAdapterManifestError(
                f"auth_environment_variables contains duplicate profile {profile}"
            )
        seen.add(profile)
        names = _str_tuple_allow_empty(
            require_sequence(entry, "names"),
            f"auth_environment_variables[{index}].names",
        )
        parsed.append((profile, names))
    return tuple(sorted(parsed, key=lambda entry: entry[0]))
