"""The small public input contract for one locked benchmark run.

This contract is deliberately about *what* a run selects, not how a private
corpus was acquired or how its bytes were authenticated.  Each selected case
names its stable identifier, completeness QC, and the provider-owned object
version for each semantic document role.  Locators are opaque to the public
runner: it must not infer a local filesystem path or a content digest from
them.

Only a locked manifest is public.  There is no public draft, approval, or
lineage/replay stage in this module.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1, PUBLIC_RUN_MANIFEST_V1

RUN_MANIFEST_SCHEMA_VERSION = str(PUBLIC_RUN_MANIFEST_V1)

NonEmptyString = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]


class DocumentRole(StrEnum):
    """Document roles admitted by the benchmark-run boundary."""

    DECISION = "decision"
    COMPLAINT = "complaint"
    MOTION = "motion"
    OPENING_MEMORANDUM = "opening_memorandum"
    MOTION_TO_DISMISS_NOTICE = "motion_to_dismiss_notice"
    MOTION_TO_DISMISS_MEMORANDUM = "motion_to_dismiss_memorandum"
    OPPOSITION = "opposition"
    REPLY = "reply"
    SURREPLY = "surreply"
    SUPPLEMENTAL_BRIEF = "supplemental_brief"


class QCStatus(StrEnum):
    """Completeness QC states; only accepted states can enter a run."""

    ACCEPTED = "accepted"
    COMPLETE = "complete"
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class OppositionStatus(StrEnum):
    """Whether an opposition is expected for the selected case."""

    DOCKETED = "docketed"
    CONFIRMED_UNOPPOSED = "confirmed_unopposed"


_ACCEPTED_QC = frozenset({QCStatus.ACCEPTED})
_MOTION_ROLES = frozenset(
    {
        DocumentRole.MOTION,
        DocumentRole.OPENING_MEMORANDUM,
        DocumentRole.MOTION_TO_DISMISS_MEMORANDUM,
    }
)
_WINDOW_PATH = re.compile(r"(?:^|[\\/])\.\.?(?:$|[\\/])")
_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class RunManifestError(ValueError):
    """Raised when a public benchmark-run manifest is not executable."""


class ManifestLockedError(RunManifestError):
    """Raised when a caller attempts to replace a locked manifest value."""


class _PublicModel(BaseModel):
    """Strict, immutable base for all public run-manifest values."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


def _reject_private_locator(value: str) -> str:
    """Reject URLs, local paths, and encoded paths from opaque key fields."""

    if (
        value.startswith(("/", "\\", "~"))
        or _DRIVE_PATH.match(value) is not None
        or _URI_SCHEME.match(value) is not None
        or "?" in value
        or "#" in value
        or "\x00" in value
        or "%" in value
        or _WINDOW_PATH.search(value) is not None
    ):
        raise ValueError(
            "opaque locators must be provider object keys or version IDs, "
            "not URLs or paths"
        )
    return value


class OpaqueObjectLocator(_PublicModel):
    """One provider-owned object reference and its opaque version token."""

    provider_id: NonEmptyString
    object_locator: NonEmptyString
    version_id: NonEmptyString

    _locator_is_not_private = field_validator(
        "provider_id", "object_locator", "version_id"
    )(_reject_private_locator)


class RoleObjectLocator(_PublicModel):
    """One semantic document role bound to one opaque object version."""

    role: DocumentRole
    locator: OpaqueObjectLocator


class SelectedCase(_PublicModel):
    """One stable, completeness-accepted case selected for a benchmark run."""

    case_id: NonEmptyString = Field(
        description="Provider-stable case identifier",
    )
    provider_id: NonEmptyString
    qc_status: QCStatus
    role_locators: tuple[RoleObjectLocator, ...] = Field(
        min_length=1,
    )
    opposition_status: OppositionStatus

    @model_validator(mode="after")
    def _require_roles(self) -> Self:
        roles = tuple(item.role for item in self.role_locators)
        if len(roles) != len(set(roles)):
            raise ValueError("selected case role locators must have unique roles")
        role_set = set(roles)
        if DocumentRole.DECISION not in role_set:
            raise ValueError("selected case requires a decision locator")
        if not role_set.intersection(_MOTION_ROLES):
            raise ValueError(
                "selected case requires a motion or opening memorandum locator"
            )
        if DocumentRole.COMPLAINT not in role_set:
            raise ValueError("selected case requires a complaint locator")
        has_opposition = DocumentRole.OPPOSITION in role_set
        if self.opposition_status == OppositionStatus.DOCKETED and not has_opposition:
            raise ValueError("docketed opposition requires an opposition locator")
        if (
            self.opposition_status == OppositionStatus.CONFIRMED_UNOPPOSED
            and has_opposition
        ):
            raise ValueError(
                "confirmed-unopposed case must not include an opposition locator"
            )
        if self.qc_status not in _ACCEPTED_QC:
            raise ValueError("selected case QC must be completeness-accepted")
        return self


class BenchmarkRunManifest(_PublicModel):
    """The sole locked public input snapshot for one benchmark run."""

    schema_version: str = RUN_MANIFEST_SCHEMA_VERSION
    run_id: UUID
    selected_cases: tuple[SelectedCase, ...] = Field(
        min_length=1,
    )
    policy_version: NonEmptyString
    code_revision: str
    created_at: datetime
    locked_at: datetime

    @field_validator("schema_version")
    @classmethod
    def _require_schema_version(cls, value: str) -> str:
        if value != RUN_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {RUN_MANIFEST_SCHEMA_VERSION!r}")
        return value

    @field_validator("code_revision")
    @classmethod
    def _require_full_commit_revision(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ValueError(
                "code_revision must be a full lowercase 40-character commit SHA"
            )
        return value

    @field_validator("created_at", "locked_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run manifest timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _require_locked_and_consistent(self) -> Self:
        if self.locked_at < self.created_at:
            raise ValueError("locked_at must be at or after created_at")
        case_ids = tuple(item.case_id for item in self.selected_cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("run manifest selected cases must have unique stable IDs")
        return self

    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        """Prevent Pydantic's unvalidated copy escape hatch from unlocking it."""

        if update:
            raise ManifestLockedError("locked run manifest cannot be changed")
        return super().model_copy(update=update, deep=deep)


def validate_run_manifest_structure(
    payload: bytes | str | Mapping[str, object],
) -> BenchmarkRunManifest:
    """Validate one locked manifest without reading private corpus state."""

    try:
        if isinstance(payload, bytes):
            manifest = BenchmarkRunManifest.model_validate_json(payload)
        elif isinstance(payload, str):
            manifest = BenchmarkRunManifest.model_validate_json(payload)
        else:
            manifest = BenchmarkRunManifest.model_validate(payload)
    except (TypeError, ValueError) as error:
        if isinstance(error, RunManifestError):
            raise
        raise RunManifestError("run manifest structure is invalid") from error
    return manifest


def serialize_run_manifest(manifest: BenchmarkRunManifest) -> bytes:
    """Serialize one locked manifest as canonical artifact JSON."""

    return ARTIFACT_CANONICAL_JSON_V1.encode(manifest.model_dump(mode="json"))
