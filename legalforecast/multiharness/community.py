"""Community submission packaging and validation for multi-harness runs."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self, cast
from urllib.parse import unquote, urlsplit

from legalforecast._json_io import (
    read_json_object,
    read_jsonl_objects,
    write_json_object,
    write_jsonl_objects,
)
from legalforecast.multiharness.container_runtime import validate_container_resume
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliContractError,
)
from legalforecast.multiharness.materialization import (
    TASK_MATERIALIZATION_SCHEMA_VERSION,
)
from legalforecast.multiharness.run_progress import (
    CLAIM_FULL,
    CLAIM_PARTIAL,
    CLAIM_SCOPED,
    COVERAGE_FULL,
    COVERAGE_SCOPED,
    is_scoped_label,
    require_coverage_kind,
    require_honest_coverage_claim,
)
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SOLVER_INPUT_EXECUTION_MANIFEST_SCHEMA_VERSION,
    SOLVER_INPUT_LAYOUT_ID,
    SolverInputEntry,
)
from legalforecast.multiharness.spec import (
    RUN_COMPATIBILITY_SCHEMA_VERSION,
    SCORING_MODES,
    TOOL_REQUEST_SCHEMA_VERSION,
    AdapterCapabilities,
    ArtifactRecord,
    ConformanceReport,
    ContributorCredit,
    RunManifest,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import (
    MultiHarnessValidationError,
    optional_bool,
    optional_mapping,
    optional_non_negative_int,
    optional_sequence,
    optional_str,
    require_known_fields,
    require_mapping,
    require_schema_version,
    require_sequence,
    require_str,
    validate_public_record,
    validate_safe_relative_path,
    validate_sha256,
    validate_unique_ids,
)
from legalforecast.publication.accounting import (
    AccountingError,
    observation_from_receipts,
)
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)

COMMUNITY_SUBMISSION_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_submission_manifest.v1"
)
COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_run_summary.v1"
)
COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2 = (
    # contract-ratchet: allow community run-summary v2 artifact bindings
    "legalforecast.multiharness.community_run_summary.v2"
)
COMMUNITY_SHARD_SCHEMA_VERSION = "legalforecast.multiharness.community_shard.v1"
COMMUNITY_ARTIFACT_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_artifact_manifest.v1"
)
COMMUNITY_PUBLIC_SUMMARY_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_public_summary.v1"
)
COMMUNITY_SELECTION_MANIFEST_SCHEMA_VERSION = (
    "legalforecast.multiharness.community_selection_manifest.v1"
)
HF_UPLOAD_PLAN_SCHEMA_VERSION = "legalforecast.multiharness.hf_upload_plan.v1"
COMMUNITY_ARTIFACT_MIRROR = (
    "https://huggingface.co/datasets/johnhughes3/legalforecastbench-community-artifacts"
)
_HF_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")

ATTEST_NOT_OFFICIAL = "not_official_legalforecastbench_result"
ATTEST_NO_PRIVATE_OR_SEALED = "no_private_or_sealed_material_in_public_artifacts"
ATTEST_RIGHT_TO_SUBMIT = "right_to_submit_artifacts"
ATTEST_PROVIDER_TERMS = "provider_terms_acknowledged"
REQUIRED_ATTESTATIONS = frozenset(
    {
        ATTEST_NOT_OFFICIAL,
        ATTEST_NO_PRIVATE_OR_SEALED,
        ATTEST_RIGHT_TO_SUBMIT,
        ATTEST_PROVIDER_TERMS,
    }
)
REQUIRED_CONTRIBUTOR_ROLES = frozenset(
    {
        "run_operator",
        "adapter_author",
        "task_source",
        "benchmark_infrastructure",
    }
)

_SUBMISSION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,96}$")


@dataclass(frozen=True, slots=True)
class CommunityArtifactReference:
    """Artifact reference included in a community submission package."""

    artifact_id: str
    path: str
    sha256: str
    media_type: str
    public: bool = True
    size_bytes: int | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.artifact_id, "artifact_id")
        validate_safe_relative_path(self.path, "path")
        validate_sha256(self.sha256, "sha256")
        _require_non_empty(self.media_type, "media_type")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise MultiHarnessValidationError("size_bytes must be non-negative")
        if self.source_url is not None:
            _validate_immutable_url(self.source_url)
        if self.public:
            _validate_public_artifact_path(self.path)
            validate_public_record(self.to_record(), "community_artifact")

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
        if self.source_url is not None:
            record["source_url"] = self.source_url
        return record

    def to_artifact_record(self) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=self.artifact_id,
            path=self.path,
            sha256=self.sha256,
            media_type=self.media_type,
            public=self.public,
            size_bytes=self.size_bytes,
        )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return cls(
            artifact_id=require_str(record, "artifact_id"),
            path=require_str(record, "path"),
            sha256=require_str(record, "sha256"),
            media_type=require_str(record, "media_type"),
            public=optional_bool(record, "public"),
            size_bytes=optional_non_negative_int(record, "size_bytes"),
            source_url=optional_str(record, "source_url"),
        )


_V2_SUMMARY_REQUIRED = frozenset(
    {
        "schema_version",
        "run_id",
        "run_manifest_sha256",
        "selection_sha256",
        "selection_label",
        "run_config_sha256",
        "row_count",
        "result_status_counts",
        "families",
        "scoring_modes",
        "adapter_ids",
        "model_keys",
        "artifact_bindings",
        "coverage_kind",
        "claim_kind",
    }
)
_V2_SUMMARY_OPTIONAL = frozenset({"identity_bindings"})
_BINDING_OPTIONAL = frozenset(
    {
        "run_spec_sha256",
        "execution_receipt_sha256",
        "deliverable_manifest_sha256",
        "evaluation_receipt_sha256",
        "score_artifact_sha256",
    }
)
_IDENTITY_REQUIRED = frozenset(
    {
        "task_identity_key",
        "solver_identity_key",
        "run_identity_key",
    }
)


@dataclass(frozen=True, slots=True)
class CanonicalArtifactBindings:
    """Canonical hashes for the artifacts that back a v2 run summary."""

    run_spec_sha256: str | None = None
    execution_receipt_sha256: str | None = None
    deliverable_manifest_sha256: str | None = None
    evaluation_receipt_sha256: str | None = None
    score_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        present = tuple(
            digest
            for digest in (
                self.run_spec_sha256,
                self.execution_receipt_sha256,
                self.deliverable_manifest_sha256,
                self.evaluation_receipt_sha256,
                self.score_artifact_sha256,
            )
            if digest is not None
        )
        if not present:
            raise MultiHarnessValidationError(
                "v2 summaries cannot omit applicable artifact bindings"
            )
        for field_name, digest in (
            ("run_spec_sha256", self.run_spec_sha256),
            ("execution_receipt_sha256", self.execution_receipt_sha256),
            ("deliverable_manifest_sha256", self.deliverable_manifest_sha256),
            ("evaluation_receipt_sha256", self.evaluation_receipt_sha256),
            ("score_artifact_sha256", self.score_artifact_sha256),
        ):
            if digest is not None:
                validate_sha256(digest, field_name)

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {}
        for field_name in (
            "run_spec_sha256",
            "execution_receipt_sha256",
            "deliverable_manifest_sha256",
            "evaluation_receipt_sha256",
            "score_artifact_sha256",
        ):
            digest = getattr(self, field_name)
            if digest is not None:
                record[field_name] = digest
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=frozenset(),
            optional=_BINDING_OPTIONAL,
            field_name="artifact_bindings",
        )
        return cls(
            run_spec_sha256=optional_str(record, "run_spec_sha256"),
            execution_receipt_sha256=optional_str(record, "execution_receipt_sha256"),
            deliverable_manifest_sha256=optional_str(
                record,
                "deliverable_manifest_sha256",
            ),
            evaluation_receipt_sha256=optional_str(
                record,
                "evaluation_receipt_sha256",
            ),
            score_artifact_sha256=optional_str(record, "score_artifact_sha256"),
        )


@dataclass(frozen=True, slots=True)
class BoundIdentityKeys:
    """Identity keys that are authoritative only when bound to artifact hashes."""

    task_identity_key: str
    solver_identity_key: str
    run_identity_key: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("task_identity_key", self.task_identity_key),
            ("solver_identity_key", self.solver_identity_key),
            ("run_identity_key", self.run_identity_key),
        ):
            validate_sha256(value, field_name)

    def to_record(self) -> dict[str, Any]:
        return {
            "task_identity_key": self.task_identity_key,
            "solver_identity_key": self.solver_identity_key,
            "run_identity_key": self.run_identity_key,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_IDENTITY_REQUIRED,
            field_name="identity_bindings",
        )
        return cls(
            task_identity_key=require_str(record, "task_identity_key"),
            solver_identity_key=require_str(record, "solver_identity_key"),
            run_identity_key=require_str(record, "run_identity_key"),
        )


@dataclass(frozen=True, slots=True)
class CommunityRunSummary:
    """Public summary for one submitted multi-harness run."""

    run_id: str
    run_manifest_sha256: str
    selection_sha256: str
    selection_label: str
    run_config_sha256: str
    row_count: int
    result_status_counts: Mapping[str, int]
    families: tuple[str, ...]
    scoring_modes: tuple[str, ...]
    adapter_ids: tuple[str, ...]
    model_keys: tuple[str, ...]
    schema_version: str = COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION
    artifact_bindings: CanonicalArtifactBindings | None = None
    identity_bindings: BoundIdentityKeys | None = None
    coverage_kind: str | None = None
    claim_kind: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, "run_id")
        validate_sha256(self.run_manifest_sha256, "run_manifest_sha256")
        validate_sha256(self.selection_sha256, "selection_sha256")
        _require_non_empty(self.selection_label, "selection_label")
        validate_sha256(self.run_config_sha256, "run_config_sha256")
        if self.row_count <= 0:
            raise MultiHarnessValidationError("row_count must be positive")
        _validate_int_mapping(self.result_status_counts, "result_status_counts")
        for field_name, values in (
            ("families", self.families),
            ("adapter_ids", self.adapter_ids),
            ("model_keys", self.model_keys),
        ):
            _require_non_empty_tuple(values, field_name)
        for value in self.scoring_modes:
            _require_non_empty(value, "scoring_modes")
        if self.schema_version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION:
            if (
                self.artifact_bindings is not None
                or self.identity_bindings is not None
                or self.coverage_kind is not None
                or self.claim_kind is not None
            ):
                raise MultiHarnessValidationError(
                    "v1 community run summaries cannot carry v2 artifact bindings"
                )
        elif self.schema_version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2:
            if self.artifact_bindings is None:
                raise MultiHarnessValidationError(
                    "v2 summaries cannot omit applicable artifact bindings"
                )
            if self.coverage_kind is None or self.claim_kind is None:
                raise MultiHarnessValidationError(
                    "v2 summaries require coverage_kind and claim_kind"
                )
            require_coverage_kind(self.coverage_kind)
            if self.claim_kind not in {CLAIM_FULL, CLAIM_SCOPED, CLAIM_PARTIAL}:
                raise MultiHarnessValidationError(
                    "claim_kind must be full, scoped, or partial"
                )
            if self.identity_bindings is not None:
                if self.artifact_bindings.execution_receipt_sha256 is None:
                    raise MultiHarnessValidationError(
                        "identity keys are authoritative only when bound to "
                        "canonical execution-receipt hashes"
                    )
        else:
            raise MultiHarnessValidationError(
                "schema_version must be "
                f"{COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION!r} or "
                f"{COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2!r}, got "
                f"{self.schema_version!r}"
            )
        validate_public_record(self.to_record(), "community_run_summary")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_manifest_sha256": self.run_manifest_sha256,
            "selection_sha256": self.selection_sha256,
            "selection_label": self.selection_label,
            "run_config_sha256": self.run_config_sha256,
            "row_count": self.row_count,
            "result_status_counts": dict(sorted(self.result_status_counts.items())),
            "families": list(self.families),
            "scoring_modes": list(self.scoring_modes),
            "adapter_ids": list(self.adapter_ids),
            "model_keys": list(self.model_keys),
        }
        if self.schema_version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2:
            assert self.artifact_bindings is not None
            record["artifact_bindings"] = self.artifact_bindings.to_record()
            record["coverage_kind"] = self.coverage_kind
            record["claim_kind"] = self.claim_kind
            if self.identity_bindings is not None:
                record["identity_bindings"] = self.identity_bindings.to_record()
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        version = require_str(record, "schema_version")
        if version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION:
            return cls._from_v1(record)
        if version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2:
            return cls._from_v2(record)
        raise MultiHarnessValidationError(
            f"schema_version must be {COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION!r} "
            f"or {COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2!r}, got {version!r}"
        )

    @classmethod
    def from_v2_record(cls, record: Mapping[str, Any]) -> Self:
        """Explicit v2 reader. v1 from_record rewrite stays characterization-exact."""

        return cls._from_v2(record)

    @classmethod
    def _from_v1(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION)
        row_count = optional_non_negative_int(record, "row_count")
        if row_count is None:
            raise MultiHarnessValidationError("row_count is required")
        return cls(
            run_id=require_str(record, "run_id"),
            run_manifest_sha256=require_str(record, "run_manifest_sha256"),
            selection_sha256=require_str(record, "selection_sha256"),
            selection_label=require_str(record, "selection_label"),
            run_config_sha256=require_str(record, "run_config_sha256"),
            row_count=row_count,
            result_status_counts=_int_mapping(
                require_mapping(record, "result_status_counts"),
                "result_status_counts",
            ),
            families=_str_tuple(require_sequence(record, "families"), "families"),
            scoring_modes=_str_tuple(
                optional_sequence(record, "scoring_modes") or (),
                "scoring_modes",
            ),
            adapter_ids=_str_tuple(
                require_sequence(record, "adapter_ids"),
                "adapter_ids",
            ),
            model_keys=_str_tuple(require_sequence(record, "model_keys"), "model_keys"),
        )

    @classmethod
    def _from_v2(cls, record: Mapping[str, Any]) -> Self:
        require_known_fields(
            record,
            required=_V2_SUMMARY_REQUIRED,
            optional=_V2_SUMMARY_OPTIONAL,
            field_name="community_run_summary",
        )
        require_schema_version(record, COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2)
        row_count = optional_non_negative_int(record, "row_count")
        if row_count is None:
            raise MultiHarnessValidationError("row_count is required")
        identity_record = optional_mapping(record, "identity_bindings")
        return cls(
            run_id=require_str(record, "run_id"),
            run_manifest_sha256=require_str(record, "run_manifest_sha256"),
            selection_sha256=require_str(record, "selection_sha256"),
            selection_label=require_str(record, "selection_label"),
            run_config_sha256=require_str(record, "run_config_sha256"),
            row_count=row_count,
            result_status_counts=_int_mapping(
                require_mapping(record, "result_status_counts"),
                "result_status_counts",
            ),
            families=_str_tuple(require_sequence(record, "families"), "families"),
            scoring_modes=_str_tuple(
                optional_sequence(record, "scoring_modes") or (),
                "scoring_modes",
            ),
            adapter_ids=_str_tuple(
                require_sequence(record, "adapter_ids"),
                "adapter_ids",
            ),
            model_keys=_str_tuple(require_sequence(record, "model_keys"), "model_keys"),
            schema_version=COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2,
            artifact_bindings=CanonicalArtifactBindings.from_record(
                require_mapping(record, "artifact_bindings"),
            ),
            identity_bindings=(
                None
                if identity_record is None
                else BoundIdentityKeys.from_record(identity_record)
            ),
            coverage_kind=require_str(record, "coverage_kind"),
            claim_kind=require_str(record, "claim_kind"),
        )


@dataclass(frozen=True, slots=True)
class CommunitySubmissionShard:
    """One compatible partial-run shard in a community submission."""

    shard_id: str
    compatible_shard_group_id: str
    selection_sha256: str
    selection_label: str
    source_suite: str
    suite_version: str
    task_selectors: Mapping[str, Any]
    task_ids: tuple[str, ...]
    adapter_id: str
    adapter_version: str
    model_key: str
    sandbox_policy_hash: str
    run_config_hash: str
    contributor_credits: tuple[ContributorCredit, ...]
    run_compatibility_hash: str | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("shard_id", self.shard_id),
            ("compatible_shard_group_id", self.compatible_shard_group_id),
            ("selection_label", self.selection_label),
            ("source_suite", self.source_suite),
            ("suite_version", self.suite_version),
            ("adapter_id", self.adapter_id),
            ("adapter_version", self.adapter_version),
            ("model_key", self.model_key),
        ):
            _require_non_empty(value, field_name)
        validate_sha256(self.selection_sha256, "selection_sha256")
        validate_sha256(self.sandbox_policy_hash, "sandbox_policy_hash")
        validate_sha256(self.run_config_hash, "run_config_hash")
        group_parts = self.compatible_shard_group_id.split(":", 2)
        if len(group_parts) != 3:
            raise MultiHarnessValidationError(
                "compatible_shard_group_id must contain family, scoring mode, "
                "and suite identity"
            )
        group_family, group_scoring_mode, group_suite_identity = group_parts
        if group_family != self.source_suite:
            raise MultiHarnessValidationError(
                "compatible_shard_group_id family must match source_suite"
            )
        if group_scoring_mode not in SCORING_MODES:
            raise MultiHarnessValidationError(
                "compatible_shard_group_id scoring mode is invalid"
            )
        if self.run_compatibility_hash is not None:
            validate_sha256(
                self.run_compatibility_hash,
                "run_compatibility_hash",
            )
            if group_suite_identity != self.suite_version:
                raise MultiHarnessValidationError(
                    "compatible_shard_group_id suite identity must match "
                    "suite_version when run_compatibility_hash is present"
                )
        _require_non_empty_tuple(self.task_ids, "task_ids")
        validate_unique_ids(self.task_ids, "task_ids")
        _require_contributor_roles(
            self.contributor_credits,
            REQUIRED_CONTRIBUTOR_ROLES,
            "contributor_credits",
        )
        validate_public_record(dict(self.task_selectors), "task_selectors")
        validate_public_record(self.to_record(), "community_shard")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema_version": COMMUNITY_SHARD_SCHEMA_VERSION,
            "shard_id": self.shard_id,
            "compatible_shard_group_id": self.compatible_shard_group_id,
            "selection_sha256": self.selection_sha256,
            "selection_label": self.selection_label,
            "source_suite": self.source_suite,
            "suite_version": self.suite_version,
            "task_selectors": dict(self.task_selectors),
            "task_ids": list(self.task_ids),
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "model_key": self.model_key,
            "sandbox_policy_hash": self.sandbox_policy_hash,
            "run_config_hash": self.run_config_hash,
            "contributor_credits": [
                credit.to_record() for credit in self.contributor_credits
            ],
        }
        if self.run_compatibility_hash is not None:
            record["run_compatibility_hash"] = self.run_compatibility_hash
        return record

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_SHARD_SCHEMA_VERSION)
        return cls(
            shard_id=require_str(record, "shard_id"),
            compatible_shard_group_id=require_str(
                record,
                "compatible_shard_group_id",
            ),
            selection_sha256=require_str(record, "selection_sha256"),
            selection_label=require_str(record, "selection_label"),
            source_suite=require_str(record, "source_suite"),
            suite_version=require_str(record, "suite_version"),
            task_selectors=optional_mapping(record, "task_selectors") or {},
            task_ids=_str_tuple(require_sequence(record, "task_ids"), "task_ids"),
            adapter_id=require_str(record, "adapter_id"),
            adapter_version=require_str(record, "adapter_version"),
            model_key=require_str(record, "model_key"),
            sandbox_policy_hash=require_str(record, "sandbox_policy_hash"),
            run_config_hash=require_str(record, "run_config_hash"),
            contributor_credits=_credit_tuple(
                require_sequence(record, "contributor_credits")
            ),
            run_compatibility_hash=optional_str(record, "run_compatibility_hash"),
        )


@dataclass(frozen=True, slots=True)
class CommunitySubmissionManifest:
    """PR-reviewed community submission manifest."""

    submission_id: str
    submitter: ContributorCredit
    contributors: tuple[ContributorCredit, ...]
    benchmark_credit: tuple[ContributorCredit, ...]
    run_summary: CommunityRunSummary
    artifacts: tuple[CommunityArtifactReference, ...]
    attestations: tuple[str, ...]
    shards: tuple[CommunitySubmissionShard, ...]

    def __post_init__(self) -> None:
        if _SUBMISSION_ID_PATTERN.fullmatch(self.submission_id) is None:
            raise MultiHarnessValidationError(
                "submission_id must be lowercase URL-safe text"
            )
        _require_contributor_roles(
            self.contributors,
            REQUIRED_CONTRIBUTOR_ROLES,
            "contributors",
        )
        _require_contributor_roles(
            self.benchmark_credit,
            frozenset({"benchmark_infrastructure"}),
            "benchmark_credit",
        )
        validate_unique_ids(
            (artifact.artifact_id for artifact in self.artifacts),
            "artifacts",
        )
        validate_unique_ids((shard.shard_id for shard in self.shards), "shards")
        missing = REQUIRED_ATTESTATIONS.difference(self.attestations)
        if missing:
            formatted = ", ".join(sorted(missing))
            raise MultiHarnessValidationError(
                f"attestations missing required value(s): {formatted}"
            )
        validate_public_record(self.to_record(), "community_submission_manifest")

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": COMMUNITY_SUBMISSION_MANIFEST_SCHEMA_VERSION,
            "submission_id": self.submission_id,
            "submitter": self.submitter.to_record(),
            "contributors": [credit.to_record() for credit in self.contributors],
            "benchmark_credit": [
                credit.to_record() for credit in self.benchmark_credit
            ],
            "run_summary": self.run_summary.to_record(),
            "artifacts": [artifact.to_record() for artifact in self.artifacts],
            "attestations": list(self.attestations),
            "shards": [shard.to_record() for shard in self.shards],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        require_schema_version(record, COMMUNITY_SUBMISSION_MANIFEST_SCHEMA_VERSION)
        validate_public_record(record, "community_submission_manifest")
        return cls(
            submission_id=require_str(record, "submission_id"),
            submitter=ContributorCredit.from_record(
                require_mapping(record, "submitter")
            ),
            contributors=_credit_tuple(require_sequence(record, "contributors")),
            benchmark_credit=_credit_tuple(
                require_sequence(record, "benchmark_credit")
            ),
            run_summary=CommunityRunSummary.from_record(
                require_mapping(record, "run_summary")
            ),
            artifacts=_community_artifact_tuple(require_sequence(record, "artifacts")),
            attestations=_str_tuple(
                require_sequence(record, "attestations"),
                "attestations",
            ),
            shards=_community_shard_tuple(require_sequence(record, "shards")),
        )


@dataclass(frozen=True, slots=True)
class CommunityPackageConfig:
    """Inputs for turning a local run directory into a PR-ready package."""

    run_dir: Path
    output_dir: Path
    submission_id: str
    submitter: ContributorCredit
    contributors: tuple[ContributorCredit, ...]
    benchmark_credit: tuple[ContributorCredit, ...]
    attestations: tuple[str, ...]
    conformance_report_path: Path | None = None
    hf_upload_plan: bool = False


@dataclass(frozen=True, slots=True)
class CommunityPackageResult:
    """Files generated for a community submission package."""

    manifest: CommunitySubmissionManifest
    output_dir: Path
    artifact_manifest_path: Path
    submission_path: Path


def package_community_submission(
    config: CommunityPackageConfig,
) -> CommunityPackageResult:
    """Create a PR-ready community submission package from a local run directory."""

    if not config.run_dir.is_dir():
        raise ValueError(f"run directory does not exist: {config.run_dir}")
    config.output_dir.mkdir(parents=True, exist_ok=True)

    run_manifest_source = config.run_dir / "run-manifest.json"
    row_results_source = config.run_dir / "row-results.jsonl"
    run_manifest = RunManifest.from_record(_read_json(run_manifest_source, "run"))
    rows = _read_jsonl(row_results_source, "row results")
    if not rows:
        raise ValueError("row-results.jsonl must contain at least one row")
    _validate_live_run_receipts(config.run_dir, rows)
    conformance_source = config.conformance_report_path or (
        config.run_dir / "conformance-report.json"
    )
    conformance = ConformanceReport.from_record(
        _read_json(conformance_source, "conformance report")
    )

    copied_paths = _copy_run_public_artifacts(config.run_dir, config.output_dir)
    observation_path = _write_efficiency_observation_if_possible(
        config.run_dir,
        config.output_dir,
    )
    if observation_path is not None:
        copied_paths.append(observation_path)
    conformance_path = config.output_dir / "conformance-report.json"
    shutil.copy2(conformance_source, conformance_path)
    copied_paths.append(conformance_path)

    request_records = _request_records_for_rows(config.run_dir, rows)
    public_summary = _public_summary_record(
        run_manifest=run_manifest,
        rows=rows,
        requests=request_records,
        conformance=conformance,
        submission_id=config.submission_id,
        run_dir=config.run_dir,
    )
    public_summary_path = config.output_dir / "public-summary.json"
    write_json_object(public_summary_path, public_summary)

    selection_manifest = _selection_manifest_record(
        run_manifest=run_manifest,
        rows=rows,
        requests=request_records,
        run_dir=config.run_dir,
    )
    selection_manifest_path = config.output_dir / "selection-manifest.json"
    write_json_object(selection_manifest_path, selection_manifest)

    base_paths = [
        *copied_paths,
        public_summary_path,
        selection_manifest_path,
    ]
    base_artifacts = tuple(
        _artifact_reference_for(config.output_dir, path) for path in base_paths
    )
    artifact_manifest_path = config.output_dir / "artifact-manifest.json"
    write_json_object(
        artifact_manifest_path,
        {
            "schema_version": COMMUNITY_ARTIFACT_MANIFEST_SCHEMA_VERSION,
            "artifacts": [artifact.to_record() for artifact in base_artifacts],
        },
    )
    artifact_manifest_artifact = _artifact_reference_for(
        config.output_dir,
        artifact_manifest_path,
    )
    if config.hf_upload_plan:
        write_json_object(
            config.output_dir / "hf-upload-plan.json",
            _hf_upload_plan_record((*base_artifacts, artifact_manifest_artifact)),
        )

    manifest = CommunitySubmissionManifest(
        submission_id=config.submission_id,
        submitter=config.submitter,
        contributors=config.contributors,
        benchmark_credit=config.benchmark_credit,
        run_summary=CommunityRunSummary.from_record(public_summary["run_summary"]),
        artifacts=(*base_artifacts, artifact_manifest_artifact),
        attestations=tuple(sorted(set(config.attestations))),
        shards=_submission_shards(
            run_manifest=run_manifest,
            rows=rows,
            requests=request_records,
            contributors=config.contributors,
            run_dir=config.run_dir,
        ),
    )
    submission_path = config.output_dir / "submission.json"
    write_json_object(submission_path, manifest.to_record())
    validate_submission_file(submission_path)
    return CommunityPackageResult(
        manifest=manifest,
        output_dir=config.output_dir,
        artifact_manifest_path=artifact_manifest_path,
        submission_path=submission_path,
    )


def _validate_live_run_receipts(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Revalidate private live receipts before publishing their commitments."""

    live_rows = tuple(
        row
        for row in rows
        if (
            (execution := optional_mapping(row, "container_execution")) is not None
            and optional_str(execution, "mode") == "live_tools"
            and require_str(row, "status") == "succeeded"
        )
    )
    if not live_rows:
        return
    compatibility = _read_json(
        run_dir / "run-compatibility.json",
        "run compatibility",
    )
    run_config = require_mapping(compatibility, "run_config")
    expected_solver_index = optional_str(
        run_config,
        "solver_input_index_sha256",
    )
    for row in live_rows:
        execution = optional_mapping(row, "container_execution")
        if execution is None:
            raise AssertionError("live row lost its container execution record")
        if require_str(execution, "status") != "succeeded":
            raise ValueError("successful live row has no successful container receipt")
        expected_receipt = require_str(execution, "receipt_sha256")
        validate_sha256(expected_receipt, "container_execution.receipt_sha256")
        row_id = require_str(row, "row_id")
        validate_safe_relative_path(row_id, "row_id")
        row_dir = run_dir / "rows" / row_id
        request = RunRequest.from_record(
            _read_json(row_dir / "request.json", "live row request")
        )
        result = RunResult.from_record(
            _read_json(row_dir / "result.json", "live row result")
        )
        input_manifest = _read_json(
            row_dir / "private-logs" / "solver-input-manifest.json",
            "live row solver-input manifest",
        )
        _require_exact_fields(
            input_manifest,
            frozenset(
                {
                    "schema_version",
                    "task_id",
                    "task_sha256",
                    "entrypoint_path",
                    "input_tree_sha256",
                    "solver_input_index_sha256",
                    "solver_input_entry",
                    "materialization",
                }
            ),
            "solver-input manifest",
        )
        require_schema_version(
            input_manifest,
            SOLVER_INPUT_EXECUTION_MANIFEST_SCHEMA_VERSION,
        )
        if require_str(input_manifest, "task_id") != request.task.task_id:
            raise ValueError("solver-input manifest task ID does not match")
        if require_str(input_manifest, "task_sha256") != request.task.task_sha256:
            raise ValueError("solver-input manifest task sha256 does not match")
        input_tree_sha256 = require_str(input_manifest, "input_tree_sha256")
        validate_sha256(input_tree_sha256, "input_tree_sha256")
        solver_index_sha256 = require_str(
            input_manifest,
            "solver_input_index_sha256",
        )
        validate_sha256(solver_index_sha256, "solver_input_index_sha256")
        if (
            expected_solver_index is None
            or solver_index_sha256 != expected_solver_index
        ):
            raise ValueError(
                "solver-input manifest index does not match run compatibility"
            )
        solver_entry = SolverInputEntry.from_record(
            require_mapping(input_manifest, "solver_input_entry")
        )
        if (
            solver_entry.task_id != request.task.task_id
            or solver_entry.task_sha256 != request.task.task_sha256
        ):
            raise ValueError("solver-input entry task identity does not match")
        prompt_sha256 = request.task.metadata.get("prompt_sha256")
        if (
            not isinstance(prompt_sha256, str)
            or solver_entry.prompt_sha256 != prompt_sha256
        ):
            raise ValueError("solver-input entry prompt commitment does not match")
        if (
            solver_entry.entrypoint_path
            != require_str(input_manifest, "entrypoint_path")
            or solver_entry.tree_sha256 != input_tree_sha256
        ):
            raise ValueError("solver-input entry tree commitment does not match")
        _validate_solver_materialization(
            require_mapping(input_manifest, "materialization"),
            solver_entry,
        )
        actual_receipt = validate_container_resume(
            row_dir / "private-logs" / "tool-container" / "execution-receipt.json",
            request=request,
            result=result,
            policy=request.sandbox_policy,
            input_tree_sha256=input_tree_sha256,
        )
        if actual_receipt != expected_receipt:
            raise ValueError(
                "container receipt commitment does not match successful live row"
            )


def _validate_solver_materialization(
    record: Mapping[str, Any],
    entry: SolverInputEntry,
) -> None:
    expected_fields = frozenset(
        {
            "schema_version",
            "task_id",
            "task_sha256",
            "layout_id",
            "entries",
            "evaluator_private_artifact_ids",
            "semantic_bytes_sha256",
            "total_size_bytes",
            "manifest_sha256",
        }
    )
    _require_exact_fields(record, expected_fields, "solver-input materialization")
    require_schema_version(record, TASK_MATERIALIZATION_SCHEMA_VERSION)
    if (
        require_str(record, "task_id") != entry.task_id
        or require_str(record, "task_sha256") != entry.task_sha256
        or require_str(record, "layout_id") != SOLVER_INPUT_LAYOUT_ID
    ):
        raise ValueError("solver-input materialization identity does not match")
    visible_files = tuple(item for item in entry.files if item.solver_visible)
    materialized_entries = require_sequence(record, "entries")
    if len(visible_files) != 1 or len(materialized_entries) != 1:
        raise ValueError("solver-input materialization must contain one prompt")
    materialized = materialized_entries[0]
    if not isinstance(materialized, Mapping):
        raise ValueError("solver-input materialization entry must be an object")
    materialized_record = cast(Mapping[str, Any], materialized)
    materialized_size = materialized_record.get("size_bytes")
    prompt = visible_files[0]
    if (
        require_str(materialized_record, "destination_path") != SOLVER_INPUT_ENTRY_PATH
        or require_str(materialized_record, "sha256")
        != prompt.sha256.removeprefix("sha256:")
        or type(materialized_size) is not int
        or materialized_size != prompt.size_bytes
    ):
        raise ValueError("solver-input materialized prompt does not match")
    content = dict(record)
    manifest_sha256 = require_str(content, "manifest_sha256")
    del content["manifest_sha256"]
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if manifest_sha256 != hashlib.sha256(encoded).hexdigest():
        raise ValueError("solver-input materialization sha256 does not match")


def validate_submission_file(path: Path) -> CommunitySubmissionManifest:
    """Validate a submission manifest and its local artifact hashes."""

    manifest = CommunitySubmissionManifest.from_record(
        _read_json(path, "community submission")
    )
    validate_submission_manifest(manifest, root=path.parent)
    return manifest


def validate_submission_manifest(
    manifest: CommunitySubmissionManifest,
    *,
    root: Path | None = None,
) -> None:
    """Validate a parsed community submission manifest."""

    validate_public_record(manifest.to_record(), "community_submission_manifest")
    if root is None:
        return
    public_paths: list[Path] = []
    for artifact in manifest.artifacts:
        if artifact.source_url is not None:
            continue
        artifact_path = root / artifact.path
        if not artifact_path.is_file():
            raise ValueError(f"artifact does not exist: {artifact.path}")
        actual_sha256 = _file_sha256(artifact_path)
        if actual_sha256 != artifact.sha256:
            raise ValueError(
                f"artifact hash mismatch for {artifact.path}: "
                f"expected {artifact.sha256}, got {actual_sha256}"
            )
        if artifact.public:
            public_paths.append(artifact_path)
    _validate_local_run_provenance(manifest, root)
    _validate_coverage_claim(manifest, root)
    _validate_v2_artifact_bindings(manifest, root)
    if public_paths:
        enforce_publication_guardrails(PublicationGuardrailConfig(public_paths=(root,)))


def _validate_local_run_provenance(
    manifest: CommunitySubmissionManifest,
    root: Path,
) -> None:
    run_manifest_artifacts = [
        artifact
        for artifact in manifest.artifacts
        if artifact.path == "run-manifest.json"
    ]
    if len(run_manifest_artifacts) > 1:
        raise ValueError("submission has multiple run-manifest.json artifacts")
    if not run_manifest_artifacts or run_manifest_artifacts[0].source_url is not None:
        if any(shard.run_compatibility_hash is not None for shard in manifest.shards):
            raise ValueError(
                "run_compatibility_hash requires a local run-manifest.json artifact"
            )
        return

    run_manifest = RunManifest.from_record(
        _read_json(root / run_manifest_artifacts[0].path, "run manifest")
    )
    run_compatibility_artifacts = [
        artifact
        for artifact in manifest.artifacts
        if artifact.path == "run-compatibility.json"
    ]
    if len(run_compatibility_artifacts) > 1:
        raise ValueError("submission has multiple run-compatibility.json artifacts")
    if run_manifest.run_compatibility_sha256 is None:
        if run_compatibility_artifacts:
            raise ValueError(
                "legacy run manifest must not include run-compatibility.json"
            )
    else:
        if (
            not run_compatibility_artifacts
            or run_compatibility_artifacts[0].source_url is not None
        ):
            raise ValueError(
                "run compatibility hash requires a local "
                "run-compatibility.json artifact"
            )
        compatibility_record = _read_json(
            root / run_compatibility_artifacts[0].path,
            "run compatibility",
        )
        require_schema_version(
            compatibility_record,
            RUN_COMPATIBILITY_SCHEMA_VERSION,
        )
        validate_public_record(compatibility_record, "run_compatibility")
        _require_exact_fields(
            compatibility_record,
            frozenset({"schema_version", "run_config", "adapter_capabilities"}),
            "run_compatibility",
        )
        compatibility_run_config = require_mapping(
            compatibility_record,
            "run_config",
        )
        _require_exact_fields(
            compatibility_run_config,
            frozenset(
                {
                    "task_index",
                    "adapters",
                    "model_configs",
                    "sandbox_policy",
                    "incomplete_run_policy",
                    *(
                        ("container_execution",)
                        if "container_execution" in compatibility_run_config
                        else ()
                    ),
                    *(
                        ("solver_input_index_sha256",)
                        if "solver_input_index_sha256" in compatibility_run_config
                        else ()
                    ),
                }
            ),
            "run_compatibility.run_config",
        )
        container_execution = (
            optional_str(compatibility_run_config, "container_execution") or "plan_only"
        )
        if container_execution not in {"plan_only", "live_tools"}:
            raise ValueError(
                "container_execution must be one of: live_tools, plan_only"
            )
        solver_input_index_sha256 = optional_str(
            compatibility_run_config,
            "solver_input_index_sha256",
        )
        if solver_input_index_sha256 is not None:
            validate_sha256(
                solver_input_index_sha256,
                "run_compatibility.solver_input_index_sha256",
            )
        task_index = require_mapping(compatibility_run_config, "task_index")
        _require_exact_fields(
            task_index,
            frozenset({"index_id", "index_sha256", "selection_namespace"}),
            "run_compatibility.task_index",
        )
        require_str(task_index, "index_id")
        validate_sha256(require_str(task_index, "index_sha256"), "index_sha256")
        require_str(task_index, "selection_namespace")
        adapters = require_sequence(compatibility_run_config, "adapters")
        model_configs = require_sequence(
            compatibility_run_config,
            "model_configs",
        )
        sandbox_policy = require_mapping(
            compatibility_run_config,
            "sandbox_policy",
        )
        _require_exact_fields(
            sandbox_policy,
            frozenset({"policy_id", "policy_sha256"}),
            "run_compatibility.sandbox_policy",
        )
        require_str(sandbox_policy, "policy_id")
        validate_sha256(
            require_str(sandbox_policy, "policy_sha256"),
            "policy_sha256",
        )
        incomplete_run_policy = require_str(
            compatibility_run_config,
            "incomplete_run_policy",
        )
        if incomplete_run_policy not in {"fail_fast", "record_failure"}:
            raise ValueError(
                "incomplete_run_policy must be one of: fail_fast, record_failure"
            )
        if not adapters or not model_configs:
            raise ValueError(
                "run-compatibility.json adapters and model_configs must not be empty"
            )
        adapter_keys: set[tuple[str, str]] = set()
        adapter_ids: set[str] = set()
        for adapter in adapters:
            adapter_record = _require_item_mapping(adapter, "adapters")
            _require_exact_fields(
                adapter_record,
                frozenset({"adapter_id", "adapter_version"}),
                "run_compatibility.adapter",
            )
            adapter_id = require_str(adapter_record, "adapter_id")
            adapter_key = (
                adapter_id,
                require_str(adapter_record, "adapter_version"),
            )
            if adapter_id in adapter_ids:
                raise ValueError("run-compatibility.json contains duplicate adapter_id")
            adapter_ids.add(adapter_id)
            adapter_keys.add(adapter_key)

        model_routes: set[tuple[str, str | None]] = set()
        for model in model_configs:
            model_record = _require_item_mapping(model, "model_configs")
            _require_exact_fields(
                model_record,
                frozenset({"adapter_id", "model_key", "lfb_fixture"}),
                "run_compatibility.model_config",
            )
            optional_bool(model_record, "lfb_fixture")
            model_route = (
                require_str(model_record, "model_key"),
                optional_str(model_record, "adapter_id"),
            )
            route_adapter_id = model_route[1]
            if route_adapter_id is not None and route_adapter_id not in adapter_ids:
                raise ValueError(
                    "run-compatibility.json model route references unknown adapter_id"
                )
            if model_route in model_routes:
                raise ValueError(
                    "run-compatibility.json contains duplicate model route"
                )
            model_key = model_route[0]
            if (
                route_adapter_id is None
                and any(route[0] == model_key for route in model_routes)
            ) or (route_adapter_id is not None and (model_key, None) in model_routes):
                raise ValueError(
                    "run-compatibility.json contains overlapping model routes"
                )
            model_routes.add(model_route)
        capabilities = require_sequence(
            compatibility_record,
            "adapter_capabilities",
        )
        if not capabilities:
            raise ValueError(
                "run-compatibility.json adapter_capabilities must not be empty"
            )
        parsed_capabilities_list: list[AdapterCapabilities] = []
        for capability in capabilities:
            capability_record = _require_item_mapping(
                capability,
                "adapter_capabilities",
            )
            _require_exact_fields(
                capability_record,
                frozenset(
                    {
                        "schema_version",
                        "adapter_id",
                        "adapter_version",
                        "supported_families",
                        "supported_scoring_modes",
                        "supports_sandbox_policy",
                        "capabilities_sha256",
                        *(
                            ("tool_protocol_version",)
                            if "tool_protocol_version" in capability_record
                            else ()
                        ),
                    }
                ),
                "run_compatibility.adapter_capability",
            )
            parsed_capabilities_list.append(
                AdapterCapabilities.from_record(capability_record)
            )
        parsed_capabilities = tuple(parsed_capabilities_list)
        if container_execution == "live_tools" and any(
            capability.tool_protocol_version != TOOL_REQUEST_SCHEMA_VERSION
            for capability in parsed_capabilities
        ):
            raise ValueError(
                "live_tools requires every adapter capability to declare "
                f"tool_protocol_version {TOOL_REQUEST_SCHEMA_VERSION}"
            )
        capability_keys = {
            (capability.adapter_id, capability.adapter_version)
            for capability in parsed_capabilities
        }
        if len(capability_keys) != len(parsed_capabilities):
            raise ValueError(
                "run-compatibility.json contains duplicate adapter capabilities"
            )
        if capability_keys != adapter_keys:
            raise ValueError(
                "run-compatibility.json adapter capabilities do not match adapters"
            )
        capabilities_by_adapter = {
            (capability.adapter_id, capability.adapter_version): capability
            for capability in parsed_capabilities
        }
        for shard in manifest.shards:
            adapter_key = (shard.adapter_id, shard.adapter_version)
            if adapter_key not in adapter_keys:
                raise ValueError(
                    f"shard {shard.shard_id} adapter is absent from "
                    "run-compatibility.json"
                )
            if not any(
                model_key == shard.model_key
                and (adapter_id is None or adapter_id == shard.adapter_id)
                for model_key, adapter_id in model_routes
            ):
                raise ValueError(
                    f"shard {shard.shard_id} model route is absent from "
                    "run-compatibility.json"
                )
            scoring_mode = shard.compatible_shard_group_id.split(":", 2)[1]
            capability = capabilities_by_adapter[adapter_key]
            if (
                shard.source_suite not in capability.supported_families
                or scoring_mode not in capability.supported_scoring_modes
            ):
                raise ValueError(
                    f"adapter capability does not support shard {shard.shard_id} "
                    f"family {shard.source_suite} and scoring mode {scoring_mode}"
                )
        actual_compatibility_sha256 = _file_sha256_from_record(compatibility_record)
        if actual_compatibility_sha256 != run_manifest.run_compatibility_sha256:
            raise ValueError(
                "run_compatibility_sha256 does not match run-compatibility.json"
            )
    summary = manifest.run_summary
    expected_summary_fields = {
        "run_id": run_manifest.run_id,
        "run_manifest_sha256": _file_sha256_from_record(run_manifest.to_record()),
        "selection_sha256": run_manifest.selection_sha256,
        "run_config_sha256": run_manifest.run_config_sha256,
    }
    actual_summary_fields = {
        "run_id": summary.run_id,
        "run_manifest_sha256": summary.run_manifest_sha256,
        "selection_sha256": summary.selection_sha256,
        "run_config_sha256": summary.run_config_sha256,
    }
    for field_name, expected in expected_summary_fields.items():
        actual = actual_summary_fields[field_name]
        if actual != expected:
            raise ValueError(
                f"run summary {field_name} does not match run-manifest.json: "
                f"expected {expected}, got {actual}"
            )

    for shard in manifest.shards:
        if shard.selection_sha256 != run_manifest.selection_sha256:
            raise ValueError(
                f"shard {shard.shard_id} selection_sha256 does not match "
                "run-manifest.json"
            )
        if shard.run_config_hash != run_manifest.run_config_sha256:
            raise ValueError(
                f"shard {shard.shard_id} run_config_hash does not match "
                "run-manifest.json"
            )
        if shard.run_compatibility_hash != run_manifest.run_compatibility_sha256:
            raise ValueError(
                f"shard {shard.shard_id} run_compatibility_hash does not match "
                "run-manifest.json"
            )


def _copy_run_public_artifacts(run_dir: Path, output_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for relative in (
        "run-manifest.json",
        "run-compatibility.json",
        "row-results.jsonl",
        "canonical-runs.jsonl",
        "lab/task-results.jsonl",
        "lfb/runs.jsonl",
        "efficiency-observation.json",
        "score-artifacts.jsonl",
        "execution-receipts.jsonl",
        "evaluation-receipt.json",
    ):
        source = run_dir / relative
        if not source.is_file():
            continue
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative == "row-results.jsonl":
            _copy_scrubbed_jsonl(source, destination, forbidden_fields={"workspace"})
        elif relative == "canonical-runs.jsonl":
            _copy_public_canonical_runs(source, destination)
        elif relative == "lfb/runs.jsonl":
            _copy_scrubbed_jsonl(source, destination, forbidden_fields={"raw_output"})
        elif relative == "execution-receipts.jsonl":
            _copy_public_execution_receipts(source, destination)
        else:
            shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def _copy_public_execution_receipts(source: Path, destination: Path) -> None:
    records = _read_jsonl(source, "execution receipts")
    public_records: list[dict[str, Any]] = []
    for record in records:
        try:
            public_records.append(
                dict(ExecutionReceipt.from_record(record).to_public_record())
            )
        except (
            LocalCliContractError,
            MultiHarnessValidationError,
            TypeError,
            ValueError,
        ):
            public_records.append(
                _scrub_public_json_record(
                    record,
                    forbidden_fields={"stdout", "stderr", "stdin", "environment"},
                )
            )
    write_jsonl_objects(destination, public_records)


def _write_efficiency_observation_if_possible(
    run_dir: Path,
    output_dir: Path,
) -> Path | None:
    destination = output_dir / "efficiency-observation.json"
    if destination.is_file():
        return None
    receipts = _load_full_execution_receipts(run_dir / "execution-receipts.jsonl")
    if not receipts:
        return None
    try:
        observation = observation_from_receipts(receipts)
    except AccountingError:
        return None
    write_json_object(destination, observation.to_record())
    return destination


def _load_full_execution_receipts(path: Path) -> tuple[ExecutionReceipt, ...]:
    if not path.is_file():
        return ()
    loaded: list[ExecutionReceipt] = []
    for record in _read_jsonl(path, "execution receipts"):
        try:
            loaded.append(ExecutionReceipt.from_record(record))
        except (
            LocalCliContractError,
            MultiHarnessValidationError,
            TypeError,
            ValueError,
        ):
            continue
    return tuple(loaded)


def _v2_summary_fields(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    bindings, identity = _canonical_bindings_from_run(run_dir)
    if bindings is None:
        return {}
    run_selection = _run_selection_record(run_dir)
    coverage_kind = _coverage_kind_from_run(run_selection, rows)
    claim_kind = str(run_selection.get("claim_kind") or coverage_kind)
    fields: dict[str, Any] = {
        "schema_version": COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2,
        "artifact_bindings": bindings,
        "coverage_kind": coverage_kind,
        "claim_kind": claim_kind,
    }
    if identity is not None and bindings.execution_receipt_sha256 is not None:
        fields["identity_bindings"] = identity
    return fields


def _canonical_bindings_from_run(
    run_dir: Path,
) -> tuple[CanonicalArtifactBindings | None, BoundIdentityKeys | None]:
    receipt_sha256, identity, spec_sha256, deliverable_sha256 = (
        _execution_receipt_binding(run_dir / "execution-receipts.jsonl")
    )
    score_sha256, evaluation_sha256 = _score_artifact_binding(
        run_dir / "score-artifacts.jsonl"
    )
    if evaluation_sha256 is None:
        evaluation_sha256 = _optional_digest_field(
            run_dir / "evaluation-receipt.json",
            "receipt_sha256",
        )
    observation_path = run_dir / "efficiency-observation.json"
    if observation_path.is_file():
        observation = _read_json(observation_path, "efficiency observation")
        if receipt_sha256 is None:
            candidate = observation.get("execution_receipt_sha256")
            receipt_sha256 = candidate if isinstance(candidate, str) else None
        if evaluation_sha256 is None:
            candidate = observation.get("evaluation_receipt_sha256")
            evaluation_sha256 = candidate if isinstance(candidate, str) else None
        if deliverable_sha256 is None:
            candidate = observation.get("deliverable_manifest_sha256")
            deliverable_sha256 = candidate if isinstance(candidate, str) else None
    if not any(
        (
            spec_sha256,
            receipt_sha256,
            deliverable_sha256,
            evaluation_sha256,
            score_sha256,
        )
    ):
        return None, None
    return (
        CanonicalArtifactBindings(
            run_spec_sha256=spec_sha256,
            execution_receipt_sha256=receipt_sha256,
            deliverable_manifest_sha256=deliverable_sha256,
            evaluation_receipt_sha256=evaluation_sha256,
            score_artifact_sha256=score_sha256,
        ),
        identity,
    )


def _execution_receipt_binding(
    path: Path,
) -> tuple[str | None, BoundIdentityKeys | None, str | None, str | None]:
    if not path.is_file():
        return None, None, None, None
    records = _read_jsonl(path, "execution receipts")
    if not records:
        return None, None, None, None
    record = records[0]
    try:
        receipt = ExecutionReceipt.from_record(record)
        identity = _identity_from_keys(
            receipt.task_identity_key,
            receipt.solver_identity_key,
            receipt.run_identity_key,
        )
        return (
            receipt.public_sha256(),
            identity,
            receipt.spec_sha256,
            receipt.deliverable_manifest_sha256,
        )
    except (LocalCliContractError, MultiHarnessValidationError, TypeError, ValueError):
        identity = _identity_from_keys(
            record.get("task_identity_key"),
            record.get("solver_identity_key"),
            record.get("run_identity_key"),
        )
        spec_sha256 = record.get("spec_sha256")
        deliverable = record.get("deliverable_manifest_sha256")
        public = _scrub_public_json_record(
            record,
            forbidden_fields={"stdout", "stderr", "stdin", "environment"},
        )
        return (
            _cli_record_sha256(public),
            identity,
            spec_sha256 if isinstance(spec_sha256, str) else None,
            deliverable if isinstance(deliverable, str) else None,
        )


def _score_artifact_binding(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, None
    records = _read_jsonl(path, "score artifacts")
    if not records:
        return None, None
    record = records[0]
    score_sha256 = record.get("score_sha256")
    evaluation_sha256 = record.get("evaluation_receipt_sha256")
    return (
        score_sha256 if isinstance(score_sha256, str) else None,
        evaluation_sha256 if isinstance(evaluation_sha256, str) else None,
    )


def _optional_digest_field(path: Path, field_name: str) -> str | None:
    if not path.is_file():
        return None
    record = _read_json(path, field_name)
    value = record.get(field_name)
    return value if isinstance(value, str) else None


def _identity_from_keys(
    task_key: object,
    solver_key: object,
    run_key: object,
) -> BoundIdentityKeys | None:
    if not isinstance(task_key, str) or not isinstance(solver_key, str):
        return None
    if not isinstance(run_key, str):
        return None
    try:
        return BoundIdentityKeys(
            task_identity_key=task_key,
            solver_identity_key=solver_key,
            run_identity_key=run_key,
        )
    except MultiHarnessValidationError:
        return None


# contract-ratchet: allow non-persisted public execution-receipt digest
def _cli_record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _copy_scrubbed_jsonl(
    source: Path,
    destination: Path,
    *,
    forbidden_fields: set[str],
) -> None:
    records = _read_jsonl(source, "public run artifact")
    scrubbed = [
        _scrub_public_json_record(record, forbidden_fields=forbidden_fields)
        for record in records
    ]
    write_jsonl_objects(destination, scrubbed)


def _copy_public_canonical_runs(source: Path, destination: Path) -> None:
    records = _read_jsonl(source, "canonical run results")
    projected: list[dict[str, Any]] = []
    for record in records:
        result = dict(record)
        artifacts = optional_sequence(record, "artifacts") or ()
        public_artifacts: list[Mapping[str, Any]] = []
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                raise ValueError("canonical run artifact must be an object")
            artifact_record = cast(Mapping[str, Any], artifact)
            public = artifact_record.get("public")
            if type(public) is not bool:
                raise ValueError("canonical run artifact public must be a boolean")
            if public:
                _validate_public_artifact_path(require_str(artifact_record, "path"))
                public_artifacts.append(artifact_record)
        result["artifacts"] = public_artifacts
        projected.append(result)
    write_jsonl_objects(destination, projected)


def _scrub_public_json_record(
    record: Mapping[str, Any],
    *,
    forbidden_fields: set[str],
) -> dict[str, Any]:
    scrubbed: dict[str, Any] = {}
    for key, value in record.items():
        if key in forbidden_fields:
            continue
        scrubbed[key] = _scrub_public_json_value(
            value,
            forbidden_fields=forbidden_fields,
        )
    return scrubbed


def _scrub_public_json_value(
    value: Any,
    *,
    forbidden_fields: set[str],
) -> Any:
    if isinstance(value, Mapping):
        return _scrub_public_json_record(
            cast(Mapping[str, Any], value),
            forbidden_fields=forbidden_fields,
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        items = cast(Sequence[Any], value)
        return [
            _scrub_public_json_value(item, forbidden_fields=forbidden_fields)
            for item in items
        ]
    return value


def _public_summary_record(
    *,
    run_manifest: RunManifest,
    rows: Sequence[Mapping[str, Any]],
    requests: Mapping[str, Mapping[str, Any]],
    conformance: ConformanceReport,
    submission_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    summary = CommunityRunSummary(
        run_id=run_manifest.run_id,
        run_manifest_sha256=_file_sha256_from_record(run_manifest.to_record()),
        selection_sha256=run_manifest.selection_sha256,
        selection_label=_selection_label(requests, run_dir=run_dir),
        run_config_sha256=run_manifest.run_config_sha256,
        row_count=len(rows),
        result_status_counts=_counter_record(
            _required_row_str(row, "status") for row in rows
        ),
        families=_sorted_unique(_required_row_str(row, "family") for row in rows),
        scoring_modes=_sorted_unique(
            _request_task_field(request, "scoring_mode")
            for request in requests.values()
        ),
        adapter_ids=_sorted_unique(
            _required_row_str(row, "adapter_id") for row in rows
        ),
        model_keys=_sorted_unique(_required_row_str(row, "model_key") for row in rows),
        **_v2_summary_fields(run_dir, rows),
    )
    return {
        "schema_version": COMMUNITY_PUBLIC_SUMMARY_SCHEMA_VERSION,
        "submission_id": submission_id,
        "run_summary": summary.to_record(),
        "conformance": {
            "report_id": conformance.report_id,
            "adapter_id": conformance.adapter_id,
            "adapter_version": conformance.adapter_version,
            "status": conformance.status,
        },
    }


def _selection_manifest_record(
    *,
    run_manifest: RunManifest,
    rows: Sequence[Mapping[str, Any]],
    requests: Mapping[str, Mapping[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    task_ids = tuple(_required_row_str(row, "task_id") for row in rows)
    run_selection = _run_selection_record(run_dir)
    coverage_kind = _coverage_kind_from_run(run_selection, rows)
    claim_kind = str(run_selection.get("claim_kind") or coverage_kind)
    selection_label = _selection_label(requests, run_dir=run_dir)
    return {
        "schema_version": COMMUNITY_SELECTION_MANIFEST_SCHEMA_VERSION,
        "run_id": run_manifest.run_id,
        "selection_sha256": run_manifest.selection_sha256,
        "selection_label": selection_label,
        "coverage_kind": coverage_kind,
        "claim_kind": claim_kind,
        "task_ids": list(task_ids),
        "task_selectors": {"task_ids": list(task_ids), "coverage_kind": coverage_kind},
        "families": list(
            _sorted_unique(_required_row_str(row, "family") for row in rows)
        ),
        "scoring_modes": list(
            _sorted_unique(
                _request_task_field(request, "scoring_mode")
                for request in requests.values()
            )
        ),
    }


def _submission_shards(
    *,
    run_manifest: RunManifest,
    rows: Sequence[Mapping[str, Any]],
    requests: Mapping[str, Mapping[str, Any]],
    contributors: tuple[ContributorCredit, ...],
    run_dir: Path,
) -> tuple[CommunitySubmissionShard, ...]:
    groups: dict[tuple[str, str, str, str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        request = requests[_required_row_str(row, "row_id")]
        family = _required_row_str(row, "family")
        scoring_mode = _request_task_field(request, "scoring_mode")
        suite_version = _request_task_field(request, "suite_version")
        adapter_id = _required_row_str(row, "adapter_id")
        adapter_version = _required_row_str(row, "adapter_version")
        model_key = _required_row_str(row, "model_key")
        groups.setdefault(
            (
                family,
                scoring_mode,
                suite_version,
                adapter_id,
                adapter_version,
                model_key,
            ),
            [],
        ).append(row)

    shards: list[CommunitySubmissionShard] = []
    for index, (key, shard_rows) in enumerate(sorted(groups.items()), start=1):
        (
            family,
            scoring_mode,
            suite_version,
            adapter_id,
            adapter_version,
            model_key,
        ) = key
        task_ids = tuple(_required_row_str(row, "task_id") for row in shard_rows)
        sandbox_policy_hashes = tuple(
            sorted({_sandbox_policy_hash_for_row(row, requests) for row in shard_rows})
        )
        if len(sandbox_policy_hashes) != 1:
            raise MultiHarnessValidationError(
                "shard rows disagree on sandbox_policy_hash for "
                f"{family}:{scoring_mode}:{suite_version}:{adapter_id}:"
                f"{adapter_version}:{model_key}"
            )
        shards.append(
            CommunitySubmissionShard(
                shard_id=f"shard-{index:03d}",
                compatible_shard_group_id=_compatible_shard_group_id(
                    family=family,
                    scoring_mode=scoring_mode,
                    suite_version=suite_version,
                ),
                selection_sha256=run_manifest.selection_sha256,
                selection_label=_selection_label(requests, run_dir=run_dir),
                source_suite=family,
                suite_version=suite_version,
                task_selectors={"task_ids": list(task_ids)},
                task_ids=task_ids,
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                model_key=model_key,
                sandbox_policy_hash=sandbox_policy_hashes[0],
                run_config_hash=run_manifest.run_config_sha256,
                contributor_credits=contributors,
                run_compatibility_hash=run_manifest.run_compatibility_sha256,
            )
        )
    return tuple(shards)


def _compatible_shard_group_id(
    *,
    family: str,
    scoring_mode: str,
    suite_version: str,
) -> str:
    return f"{family}:{scoring_mode}:{suite_version}"


def _request_records_for_rows(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    requests: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        row_id = _required_row_str(row, "row_id")
        workspace = _row_workspace(row)
        if not workspace.is_dir():
            workspace = run_dir / "rows" / row_id
        requests[row_id] = _read_json(workspace / "request.json", "run request")
    return requests


def _row_workspace(row: Mapping[str, Any]) -> Path:
    value = row.get("workspace")
    if isinstance(value, str) and value.strip():
        return Path(value)
    return Path("rows") / _required_row_str(row, "row_id")


def _artifact_reference_for(root: Path, path: Path) -> CommunityArtifactReference:
    relative = path.relative_to(root).as_posix()
    return CommunityArtifactReference(
        artifact_id=_artifact_id(relative),
        path=relative,
        sha256=_file_sha256(path),
        media_type=_media_type(path),
        public=True,
        size_bytes=path.stat().st_size,
    )


def _hf_upload_plan_record(
    artifacts: Sequence[CommunityArtifactReference],
) -> dict[str, Any]:
    return {
        "schema_version": HF_UPLOAD_PLAN_SCHEMA_VERSION,
        "mirror_repository": COMMUNITY_ARTIFACT_MIRROR,
        "revision_policy": "immutable-commit",
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "path": artifact.path,
                "sha256": artifact.sha256,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
            }
            for artifact in artifacts
        ],
    }


def _read_json(path: Path, label: str) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    return read_jsonl_objects(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item, line: (
            f"{label} row {line} in {item} must be an object"
        ),
    )


def _credit_tuple(records: Sequence[Any]) -> tuple[ContributorCredit, ...]:
    return tuple(
        ContributorCredit.from_record(_require_item_mapping(item, "contributors"))
        for item in records
    )


def _community_artifact_tuple(
    records: Sequence[Any],
) -> tuple[CommunityArtifactReference, ...]:
    return tuple(
        CommunityArtifactReference.from_record(_require_item_mapping(item, "artifacts"))
        for item in records
    )


def _community_shard_tuple(
    records: Sequence[Any],
) -> tuple[CommunitySubmissionShard, ...]:
    return tuple(
        CommunitySubmissionShard.from_record(_require_item_mapping(item, "shards"))
        for item in records
    )


def _require_item_mapping(item: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(item, Mapping):
        raise MultiHarnessValidationError(f"{field_name} entries must be objects")
    return cast(Mapping[str, Any], item)


def _require_exact_fields(
    record: Mapping[str, Any],
    expected: frozenset[str],
    field_name: str,
) -> None:
    missing = sorted(expected.difference(record))
    if missing:
        raise MultiHarnessValidationError(
            f"{field_name} has missing field(s): {', '.join(missing)}"
        )
    unexpected = sorted(set(record).difference(expected))
    if unexpected:
        raise MultiHarnessValidationError(
            f"{field_name} has unexpected field(s): {', '.join(unexpected)}"
        )


def _str_tuple(records: Sequence[Any], field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for item in records:
        if not isinstance(item, str) or not item.strip():
            raise MultiHarnessValidationError(
                f"{field_name} must contain non-empty strings"
            )
        values.append(item)
    return tuple(values)


def _int_mapping(record: Mapping[str, Any], field_name: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, value in record.items():
        if not key.strip():
            raise MultiHarnessValidationError(f"{field_name} keys must be strings")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise MultiHarnessValidationError(
                f"{field_name}.{key} must be a non-negative integer"
            )
        result[key] = value
    return result


def _validate_int_mapping(record: Mapping[str, int], field_name: str) -> None:
    for key, value in record.items():
        _require_non_empty(key, f"{field_name} key")
        if isinstance(value, bool) or value < 0:
            raise MultiHarnessValidationError(
                f"{field_name}.{key} must be a non-negative integer"
            )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise MultiHarnessValidationError(f"{field_name} must be non-empty")


def _require_non_empty_tuple(values: Sequence[str], field_name: str) -> None:
    if not values:
        raise MultiHarnessValidationError(f"{field_name} must not be empty")
    for value in values:
        _require_non_empty(value, field_name)


def _require_contributor_roles(
    contributors: Sequence[ContributorCredit],
    required_roles: frozenset[str],
    field_name: str,
) -> None:
    if not contributors:
        raise MultiHarnessValidationError(f"{field_name} must not be empty")
    roles = {credit.role for credit in contributors}
    missing = required_roles.difference(roles)
    if missing:
        formatted = ", ".join(sorted(missing))
        raise MultiHarnessValidationError(
            f"{field_name} missing required role(s): {formatted}"
        )


def _validate_immutable_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        raise MultiHarnessValidationError(
            "source_url must be an https URL in the community artifact mirror"
        )
    if parsed.query or parsed.fragment:
        raise MultiHarnessValidationError(
            "source_url must not include query parameters or a fragment"
        )
    prefix = urlsplit(COMMUNITY_ARTIFACT_MIRROR).path.rstrip("/")
    path_parts = parsed.path.split("/")
    expected_parts = prefix.split("/")
    if path_parts[: len(expected_parts)] != expected_parts:
        raise MultiHarnessValidationError(
            f"source_url must use the designated mirror {COMMUNITY_ARTIFACT_MIRROR}"
        )
    suffix = path_parts[len(expected_parts) :]
    if len(suffix) < 3 or suffix[0] != "resolve" or not suffix[2]:
        raise MultiHarnessValidationError(
            "source_url must be a Hugging Face resolve URL pinned to a commit"
        )
    if _HF_COMMIT_PATTERN.fullmatch(suffix[1]) is None:
        raise MultiHarnessValidationError(
            "source_url must pin a 40- or 64-character lowercase commit SHA"
        )
    decoded_artifact_parts: list[str] = []
    for encoded_part in suffix[2:]:
        decoded_part = _decode_url_path_segment(encoded_part)
        if "/" in decoded_part or "\\" in decoded_part:
            raise MultiHarnessValidationError(
                "source_url artifact path must not contain percent-encoded separators"
            )
        decoded_artifact_parts.append(decoded_part)
    validate_safe_relative_path(
        "/".join(decoded_artifact_parts),
        "source_url artifact path",
    )


def _decode_url_path_segment(value: str) -> str:
    decoded = value
    for _ in range(4):
        next_value = unquote(decoded)
        if next_value == decoded:
            return decoded
        decoded = next_value
    raise MultiHarnessValidationError(
        "source_url artifact path must not use excessive percent encoding"
    )


def _validate_public_artifact_path(path: str) -> None:
    lowered_parts = tuple(part.lower() for part in path.split("/"))
    if any(part.startswith("private") for part in lowered_parts):
        raise MultiHarnessValidationError(
            "public artifact paths must not include private path segments"
        )


def _required_row_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _request_task_field(request: Mapping[str, Any], field_name: str) -> str:
    task = require_mapping(request, "task")
    return require_str(task, field_name)


def _sandbox_policy_hash_for_row(
    row: Mapping[str, Any],
    requests: Mapping[str, Mapping[str, Any]],
) -> str:
    request = requests[_required_row_str(row, "row_id")]
    sandbox_policy = require_mapping(request, "sandbox_policy")
    return _file_or_record_sha256(
        _row_workspace(row) / "sandbox.plan.json",
        sandbox_policy,
    )


def _selection_label(
    requests: Mapping[str, Mapping[str, Any]],
    *,
    run_dir: Path | None = None,
) -> str:
    if run_dir is not None:
        record = _run_selection_record(run_dir)
        value = record.get("selection_label")
        if isinstance(value, str) and value.strip():
            return value
    for request in requests.values():
        task = require_mapping(request, "task")
        metadata = optional_mapping(task, "metadata") or {}
        value = metadata.get("selection_label")
        if isinstance(value, str) and value.strip():
            return value
    return "submitted-run"


def _run_selection_record(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "selection-manifest.json"
    if not path.is_file():
        raise MultiHarnessValidationError(
            "run is missing selection-manifest.json; coverage cannot be claimed"
        )
    try:
        return dict(_read_json(path, "run selection manifest"))
    except ValueError as exc:
        raise MultiHarnessValidationError(
            "run selection-manifest.json is unreadable; coverage cannot be claimed"
        ) from exc


def _coverage_kind_from_run(
    run_selection: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> str:
    try:
        coverage_kind = require_coverage_kind(run_selection.get("coverage_kind"))
        for row in rows:
            raw = row.get("coverage_kind")
            if raw is None:
                continue
            if require_coverage_kind(raw) == COVERAGE_SCOPED:
                coverage_kind = COVERAGE_SCOPED
    except ValueError as exc:
        raise MultiHarnessValidationError(str(exc)) from exc
    return coverage_kind


def _validate_coverage_claim(
    manifest: CommunitySubmissionManifest,
    root: Path,
) -> None:
    selection_path = root / "selection-manifest.json"
    record: Mapping[str, Any] = {}
    if selection_path.is_file():
        try:
            record = _read_json(selection_path, "selection manifest")
        except ValueError as exc:
            raise MultiHarnessValidationError(str(exc)) from exc
    try:
        raw_coverage = record.get("coverage_kind")
        if raw_coverage is None:
            coverage_kind = (
                COVERAGE_SCOPED
                if is_scoped_label(manifest.run_summary.selection_label)
                else COVERAGE_FULL
            )
        else:
            coverage_kind = require_coverage_kind(raw_coverage)
    except ValueError as exc:
        raise MultiHarnessValidationError(str(exc)) from exc
    interrupted = any(
        status == "interrupted" and count
        for status, count in manifest.run_summary.result_status_counts.items()
    )
    claim_kind = record.get("claim_kind")
    if claim_kind == CLAIM_PARTIAL:
        interrupted = True
    try:
        require_honest_coverage_claim(
            selection_label=manifest.run_summary.selection_label,
            coverage_kind=coverage_kind,
            interrupted=interrupted,
        )
    except ValueError as exc:
        raise MultiHarnessValidationError(str(exc)) from exc


def _validate_v2_artifact_bindings(
    manifest: CommunitySubmissionManifest,
    root: Path,
) -> None:
    summary = manifest.run_summary
    if summary.schema_version != COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2:
        return
    bindings = summary.artifact_bindings
    if bindings is None:
        raise ValueError("v2 summaries cannot omit applicable artifact bindings")
    applicable = {
        "execution_receipt_sha256": (
            (root / "execution-receipts.jsonl").is_file()
            or (root / "efficiency-observation.json").is_file()
        ),
        "evaluation_receipt_sha256": (root / "evaluation-receipt.json").is_file(),
        "score_artifact_sha256": (root / "score-artifacts.jsonl").is_file(),
        "run_spec_sha256": (root / "run-spec.json").is_file(),
        "deliverable_manifest_sha256": (root / "deliverable-manifest.json").is_file(),
    }
    missing = [
        field_name
        for field_name, required in applicable.items()
        if required and getattr(bindings, field_name) is None
    ]
    if missing:
        raise ValueError(
            "v2 summaries cannot omit applicable artifact bindings: "
            + ", ".join(missing)
        )
    if (
        bindings.score_artifact_sha256 is not None
        and (root / "score-artifacts.jsonl").is_file()
    ):
        hashes = {
            record.get("score_sha256")
            for record in _read_jsonl(root / "score-artifacts.jsonl", "score artifacts")
        }
        if bindings.score_artifact_sha256 not in hashes:
            raise ValueError(
                "score_artifact_sha256 does not match score-artifacts.jsonl"
            )
    if (
        bindings.execution_receipt_sha256 is not None
        and (root / "execution-receipts.jsonl").is_file()
    ):
        hashes = {
            _cli_record_sha256(record)
            for record in _read_jsonl(
                root / "execution-receipts.jsonl",
                "execution receipts",
            )
        }
        if bindings.execution_receipt_sha256 not in hashes:
            raise ValueError(
                "execution_receipt_sha256 does not match execution-receipts.jsonl"
            )


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value.strip()}))


def _counter_record(values: Iterable[str]) -> dict[str, int]:
    counter: Counter[str] = Counter(values)
    return dict(sorted(counter.items()))


def _file_or_record_sha256(path: Path, record: Mapping[str, Any]) -> str:
    if path.is_file():
        return _file_sha256(path)
    return _file_sha256_from_record(record)


def _file_sha256_from_record(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _artifact_id(relative_path: str) -> str:
    return relative_path.removesuffix(".json").removesuffix(".jsonl").replace("/", ":")


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/jsonl"
    if suffix == ".md":
        return "text/markdown"
    if suffix in {".txt", ".log"}:
        return "text/plain"
    return "application/octet-stream"
