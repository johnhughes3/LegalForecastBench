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
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Self, cast

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1, PUBLIC_RUN_MANIFEST_V1
from legalforecast.immutable_io import read_single_link_file, write_file_create_only

RUN_MANIFEST_SCHEMA_VERSION = str(PUBLIC_RUN_MANIFEST_V1)
# Keep the short name discoverable for the private importer and older callers.
MANIFEST_SCHEMA_VERSION = RUN_MANIFEST_SCHEMA_VERSION

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

    NOT_DOCKETED = "not_docketed"
    DOCKETED = "docketed"
    CONFIRMED_UNOPPOSED = "confirmed_unopposed"


_ACCEPTED_QC = frozenset({QCStatus.ACCEPTED, QCStatus.COMPLETE, QCStatus.PASSED})
_MOTION_ROLES = frozenset(
    {
        DocumentRole.MOTION,
        DocumentRole.OPENING_MEMORANDUM,
        DocumentRole.MOTION_TO_DISMISS_NOTICE,
        DocumentRole.MOTION_TO_DISMISS_MEMORANDUM,
    }
)
_ROLE_ALIASES = {
    "opening memo": "opening_memorandum",
    "opening memorandum": "opening_memorandum",
    "motion/opening memo": "opening_memorandum",
    "motion/opening memorandum": "opening_memorandum",
    "motion to dismiss": "motion",
    "motion-to-dismiss": "motion",
    "motion_to_dismiss": "motion",
    "target": "complaint",
}
_WINDOW_PATH = re.compile(r"(?:^|/)\.\.?(?:/|$)")
_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


class RunManifestError(ValueError):
    """Raised when a public benchmark-run manifest is not executable."""


class ManifestLockedError(RunManifestError):
    """Raised when a caller attempts to replace a locked manifest value."""


class _PublicModel(BaseModel):
    """Strict, immutable base for all public run-manifest values."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        strict=True,
        str_strip_whitespace=True,
    )


def _reject_private_locator(value: str) -> str:
    """Reject local/private path spellings while retaining opaque object keys."""

    if (
        value.startswith(("/", "~"))
        or "\\" in value
        or _DRIVE_PATH.fullmatch(value) is not None
        or value.casefold().startswith(("file:", "file://"))
        or "\x00" in value
        or _WINDOW_PATH.search(value) is not None
    ):
        raise ValueError("opaque locators must not contain private filesystem paths")
    return value


class OpaqueObjectLocator(_PublicModel):
    """One provider-owned object reference and its opaque version token."""

    provider_id: NonEmptyString = Field(
        validation_alias=AliasChoices("provider_id", "provider")
    )
    object_locator: NonEmptyString = Field(
        validation_alias=AliasChoices(
            "object_locator", "locator", "object_key", "key", "object"
        )
    )
    version_id: NonEmptyString = Field(
        validation_alias=AliasChoices("version_id", "version")
    )

    _locator_is_not_private = field_validator(
        "provider_id", "object_locator", "version_id"
    )(_reject_private_locator)

    @property
    def provider(self) -> str:
        """Compatibility spelling for the provider identifier."""

        return self.provider_id

    @property
    def locator(self) -> str:
        """Compatibility spelling for the opaque object locator."""

        return self.object_locator

    @property
    def object_key(self) -> str:
        """Return the opaque object reference without treating it as a path."""

        return self.object_locator

    @property
    def version(self) -> str:
        """Compatibility spelling for the opaque provider version."""

        return self.version_id


class RoleObjectLocator(_PublicModel):
    """One semantic document role bound to one opaque object version."""

    role: DocumentRole
    locator: OpaqueObjectLocator

    @model_validator(mode="before")
    @classmethod
    def _normalize_flat_locator(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        source = cast(Mapping[str, object], value)
        nested = source.get("locator")
        if "role" not in source or isinstance(nested, Mapping):
            return source
        locator_fields = {
            key: source[key]
            for key in (
                "provider_id",
                "provider",
                "object_locator",
                "object_key",
                "key",
                "object",
                "version_id",
                "version",
            )
            if key in source
        }
        if isinstance(nested, str):
            locator_fields["object_locator"] = nested
        if not locator_fields:
            return source
        normalized = dict(source)
        normalized["locator"] = locator_fields
        for key in locator_fields:
            normalized.pop(key, None)
        return normalized

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = _ROLE_ALIASES.get(value.strip().casefold(), value.strip())
        try:
            return DocumentRole(normalized)
        except ValueError:
            return normalized


class SelectedCase(_PublicModel):
    """One stable, completeness-accepted case selected for a benchmark run."""

    case_id: NonEmptyString = Field(
        description="Provider-stable case identifier",
        validation_alias=AliasChoices(
            "case_id", "stable_case_id", "stable_id", "candidate_id"
        ),
    )
    provider_id: NonEmptyString = Field(
        validation_alias=AliasChoices("provider_id", "provider")
    )
    qc_status: QCStatus
    role_locators: tuple[RoleObjectLocator, ...] = Field(
        min_length=1,
        validation_alias=AliasChoices("role_locators", "object_locators", "locators"),
    )
    complaint_required: bool = True
    opposition_status: OppositionStatus = OppositionStatus.NOT_DOCKETED

    @model_validator(mode="before")
    @classmethod
    def _normalize_role_locators(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        source = cast(Mapping[str, object], value)
        raw = source.get(
            "role_locators", source.get("object_locators", source.get("locators"))
        )
        normalized = dict(source)
        for key in ("object_locators", "locators"):
            normalized.pop(key, None)
        if isinstance(raw, Mapping):
            normalized["role_locators"] = tuple(
                {"role": role, "locator": locator}
                for role, locator in cast(Mapping[object, object], raw).items()
            )
        elif isinstance(raw, (list, tuple)):
            normalized["role_locators"] = tuple(cast(Sequence[object], raw))

        if "opposition_status" not in normalized:
            confirmed_unopposed = normalized.pop("confirmed_unopposed", False)
            opposition_docketed = normalized.pop("opposition_docketed", False)
            if not isinstance(confirmed_unopposed, bool) or not isinstance(
                opposition_docketed, bool
            ):
                raise ValueError(
                    "opposition status aliases must be boolean when supplied"
                )
            if confirmed_unopposed:
                normalized["opposition_status"] = OppositionStatus.CONFIRMED_UNOPPOSED
            elif opposition_docketed:
                normalized["opposition_status"] = OppositionStatus.DOCKETED
        policy_requires_complaint = source.get("policy_requires_complaint")
        if (
            "complaint_required" not in normalized
            and policy_requires_complaint is not None
        ):
            normalized["complaint_required"] = policy_requires_complaint
        normalized.pop("policy_requires_complaint", None)
        return normalized

    @field_validator("qc_status", mode="before")
    @classmethod
    def _normalize_qc(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().casefold()
        try:
            return QCStatus(normalized)
        except ValueError:
            return normalized

    @field_validator("opposition_status", mode="before")
    @classmethod
    def _normalize_opposition_status(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().casefold()
        try:
            return OppositionStatus(normalized)
        except ValueError:
            return normalized

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
        if self.complaint_required and DocumentRole.COMPLAINT not in role_set:
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

    @property
    def stable_case_id(self) -> str:
        """Return the stable case identifier used for case uniqueness."""

        return self.case_id

    @property
    def is_completeness_accepted(self) -> bool:
        """Whether QC permits this case to enter a locked run manifest."""

        return self.qc_status in _ACCEPTED_QC


class BenchmarkRunManifest(_PublicModel):
    """The sole locked public input snapshot for one benchmark run."""

    schema_version: str = RUN_MANIFEST_SCHEMA_VERSION
    run_id: NonEmptyString = Field(
        validation_alias=AliasChoices("run_id", "manifest_id")
    )
    selected_cases: tuple[SelectedCase, ...] = Field(
        min_length=1,
        validation_alias=AliasChoices("selected_cases", "cases"),
    )
    policy_version: NonEmptyString = Field(
        validation_alias=AliasChoices("policy_version", "policy_id")
    )
    code_revision: NonEmptyString = Field(
        validation_alias=AliasChoices("code_revision", "code_version")
    )
    created_at: datetime
    locked_at: datetime | None = None

    @field_validator("schema_version")
    @classmethod
    def _require_schema_version(cls, value: str) -> str:
        if value != RUN_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {RUN_MANIFEST_SCHEMA_VERSION!r}")
        return value

    @field_validator("created_at", "locked_at", mode="before")
    @classmethod
    def _parse_timestamp(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    @field_validator("created_at", "locked_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run manifest timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _require_locked_and_consistent(self) -> Self:
        if self.locked_at is None:
            raise RunManifestError("run manifest must be locked before execution")
        if self.locked_at < self.created_at:
            raise ValueError("locked_at must be at or after created_at")
        case_ids = tuple(item.case_id for item in self.selected_cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("run manifest selected cases must have unique stable IDs")
        return self

    @model_validator(mode="before")
    @classmethod
    def _normalize_case_sequence(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        source = cast(Mapping[str, object], value)
        raw = source.get("selected_cases", source.get("cases"))
        if not isinstance(raw, (list, tuple)):
            return source
        normalized = dict(source)
        normalized["selected_cases"] = tuple(cast(Sequence[object], raw))
        normalized.pop("cases", None)
        return normalized

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Prevent Pydantic's unvalidated copy escape hatch from unlocking it."""

        if update:
            raise ManifestLockedError("locked run manifest cannot be changed")
        return super().model_copy(update=update, deep=deep)

    @property
    def is_locked(self) -> bool:
        """Whether this manifest can be consumed by a runner."""

        return self.locked_at is not None

    @property
    def locked(self) -> bool:
        """Alias for callers that use a boolean lock state."""

        return self.is_locked

    @property
    def cases(self) -> tuple[SelectedCase, ...]:
        """Compatibility spelling for ``selected_cases``."""

        return self.selected_cases

    @property
    def policy_id(self) -> str:
        """Compatibility spelling for ``policy_version``."""

        return self.policy_version

    @property
    def code_version(self) -> str:
        """Compatibility spelling for ``code_revision``."""

        return self.code_revision


# Readable aliases keep the contract easy for the private importer to discover.
RunManifest = BenchmarkRunManifest
ObjectLocator = OpaqueObjectLocator
RoleLocator = RoleObjectLocator


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

    if not manifest.is_locked:
        raise RunManifestError("only a locked run manifest can be serialized")
    return ARTIFACT_CANONICAL_JSON_V1.encode(manifest.model_dump(mode="json"))


def run_manifest_record(manifest: BenchmarkRunManifest) -> dict[str, object]:
    """Return the JSON-compatible record for a locked manifest."""

    return cast(dict[str, object], manifest.model_dump(mode="json"))


def write_run_manifest(manifest: BenchmarkRunManifest, path: Path) -> None:
    """Create one manifest file without allowing replacement."""

    write_file_create_only(path, serialize_run_manifest(manifest))


def load_run_manifest(path: Path) -> BenchmarkRunManifest:
    """Load and validate one canonical, create-only manifest file."""

    payload = read_single_link_file(path, label="run manifest")
    manifest = validate_run_manifest_structure(payload)
    if serialize_run_manifest(manifest) != payload:
        raise RunManifestError("run manifest is not canonical artifact JSON")
    return manifest
