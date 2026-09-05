"""Typed public forecast and labels release contracts."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from legalforecast.contracts import (
    FORECAST_RELEASE_V1,
    LABELS_RELEASE_V1,
    PUBLIC_RUN_MANIFEST_V1,
)

FORECAST_RELEASE_SCHEMA = cast(
    Literal[
        "legalforecast.forecast-release.v1"  # contract-ratchet: allow typed registry
    ],
    str(FORECAST_RELEASE_V1),
)
LABELS_RELEASE_SCHEMA = cast(
    Literal[
        "legalforecast.labels-release.v1"  # contract-ratchet: allow typed registry
    ],
    str(LABELS_RELEASE_V1),
)
type PublicRunManifestSchema = Literal[
    # contract-ratchet: allow imported public contract
    "legalforecast.public-run-manifest.v1"
]

PleadingRole = Literal[
    "complaint",
    "amended_complaint",
    "counterclaim",
    "crossclaim",
    "third_party_complaint",
    "interpleader_complaint",
    "other_claim_bearing_filing",
]
BriefingRole = Literal[
    "motion_to_dismiss_notice",
    "motion_to_dismiss_memorandum",
    "opposition",
    "reply",
    "surreply",
    "supplemental_brief",
]
SupportingDocumentSide = Literal["opening", "opposition", "reply"]
SupportingDocumentKind = Literal[
    "declaration",
    "affidavit",
    "affirmation",
    "exhibit",
    "appendix",
    "attachment",
    "other",
]
ModelVisibleRole = (
    PleadingRole | BriefingRole | Literal["docket_history", "supporting_document"]
)

PLEADING_ROLES = frozenset(
    {
        "complaint",
        "amended_complaint",
        "counterclaim",
        "crossclaim",
        "third_party_complaint",
        "interpleader_complaint",
        "other_claim_bearing_filing",
    }
)
BRIEFING_ROLES = frozenset(
    {
        "motion_to_dismiss_notice",
        "motion_to_dismiss_memorandum",
        "opposition",
        "reply",
        "surreply",
        "supplemental_brief",
    }
)
SUPPORTED_MODEL_VISIBLE_ROLES = (
    PLEADING_ROLES
    | BRIEFING_ROLES
    | frozenset({"docket_history", "supporting_document"})
)

NonEmptyString = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]
Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
FullRevision = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{40}$"),
]
RelativePath = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]


class ReleaseModel(BaseModel):
    """Strict immutable base for all release boundary values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _validate_relative_path(value: str) -> str:
    parts = value.split("/")
    if (
        value.startswith("/")
        or "\\" in value
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("artifact path must be a safe relative POSIX path")
    return value


def _exclude_none(value: object) -> bool:
    """Keep legacy canonical JSON stable when an optional field is absent."""

    return value is None


class DocumentDraft(ReleaseModel):
    """Issuer input for one model-visible predecision document."""

    document_id: NonEmptyString
    role: ModelVisibleRole
    path: RelativePath
    supporting_side: SupportingDocumentSide | None = Field(
        default=None, exclude_if=_exclude_none
    )
    supporting_kind: SupportingDocumentKind | None = Field(
        default=None, exclude_if=_exclude_none
    )
    target_motion_document_id: NonEmptyString | None = Field(
        default=None, exclude_if=_exclude_none
    )

    _path_is_relative = field_validator("path")(_validate_relative_path)

    @model_validator(mode="after")
    def require_supporting_metadata(self) -> DocumentDraft:
        fields = (
            self.supporting_side,
            self.supporting_kind,
            self.target_motion_document_id,
        )
        if self.role == "supporting_document" and any(
            value is None for value in fields
        ):
            raise ValueError(
                "supporting documents require side, kind, and target motion "
                "document identity"
            )
        if self.role != "supporting_document" and any(
            value is not None for value in fields
        ):
            raise ValueError(
                "supporting metadata is only valid for supporting_document role"
            )
        return self


class CaseDraft(ReleaseModel):
    """Issuer input for a case and its public model-visible document index."""

    case_id: NonEmptyString
    documents: tuple[DocumentDraft, ...] = Field(min_length=1)


class PredictionUnitDraft(ReleaseModel):
    """Issuer input for one prediction unit and its execution artifacts."""

    unit_id: NonEmptyString
    case_id: NonEmptyString
    claim_name: NonEmptyString
    defendant_group: NonEmptyString
    count: NonEmptyString
    should_score: bool
    model_visible_document_ids: tuple[NonEmptyString, ...] = Field(min_length=1)
    packet_path: RelativePath
    prompt_path: RelativePath

    _paths_are_relative = field_validator("packet_path", "prompt_path")(
        _validate_relative_path
    )


class ForecastManifestBinding(ReleaseModel):
    """Exact locked-run identity carried by an outcome-blinded release.

    The manifest SHA commits to the complete public run-manifest payload,
    including selected cases, provider IDs, role-bearing opaque locators and
    version IDs.  The duplicated typed fields make the most important
    identity values inspectable without introducing a second manifest
    contract or per-document hashes.
    """

    schema_version: PublicRunManifestSchema = cast(
        PublicRunManifestSchema, str(PUBLIC_RUN_MANIFEST_V1)
    )
    release_id: NonEmptyString
    run_id: UUID
    policy_version: NonEmptyString
    code_revision: FullRevision
    manifest_sha256: Sha256


class ForecastDraft(ReleaseModel):
    """Uncommitted issuer input; not a persisted runtime contract."""

    release_id: NonEmptyString
    policy_digest: Sha256
    code_version: NonEmptyString
    packet_builder_version: NonEmptyString
    run_manifest_binding: ForecastManifestBinding | None = None
    cases: tuple[CaseDraft, ...] = Field(min_length=1)
    prediction_units: tuple[PredictionUnitDraft, ...] = Field(min_length=1)


class ScoringPolicy(ReleaseModel):
    """Minimal scoring semantics bound into a labels release."""

    policy_id: NonEmptyString
    metric: Literal["brier"] = "brier"
    positive_label: Literal["grant"] = "grant"
    negative_label: Literal["deny"] = "deny"


class UnitOutcome(ReleaseModel):
    """One binary unit outcome kept exclusively in the labels release."""

    unit_id: NonEmptyString
    outcome: Literal[0, 1]


class LabelsDraft(ReleaseModel):
    """Uncommitted labels issuer input; never passed to forecast execution."""

    release_id: NonEmptyString
    scoring_policy: ScoringPolicy
    unit_outcomes: tuple[UnitOutcome, ...] = Field(min_length=1)


class ReleaseDocument(ReleaseModel):
    """One immutable model-visible document commitment."""

    document_id: NonEmptyString
    role: ModelVisibleRole
    path: RelativePath
    sha256: Sha256
    byte_count: Annotated[int, Field(strict=True, gt=0)]
    supporting_side: SupportingDocumentSide | None = Field(
        default=None, exclude_if=_exclude_none
    )
    supporting_kind: SupportingDocumentKind | None = Field(
        default=None, exclude_if=_exclude_none
    )
    target_motion_document_id: NonEmptyString | None = Field(
        default=None, exclude_if=_exclude_none
    )

    _path_is_relative = field_validator("path")(_validate_relative_path)

    @model_validator(mode="after")
    def require_supporting_metadata(self) -> ReleaseDocument:
        fields = (
            self.supporting_side,
            self.supporting_kind,
            self.target_motion_document_id,
        )
        if self.role == "supporting_document" and any(
            value is None for value in fields
        ):
            raise ValueError(
                "supporting documents require side, kind, and target motion "
                "document identity"
            )
        if self.role != "supporting_document" and any(
            value is not None for value in fields
        ):
            raise ValueError(
                "supporting metadata is only valid for supporting_document role"
            )
        return self


class ReleaseCase(ReleaseModel):
    """One case and its canonical document index."""

    case_id: NonEmptyString
    documents: tuple[ReleaseDocument, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_canonical_documents(self) -> ReleaseCase:
        identifiers = tuple(document.document_id for document in self.documents)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate document in release case")
        if identifiers != tuple(sorted(identifiers)):
            raise ValueError("documents are not in canonical document order")
        for document in self.documents:
            if document.role != "supporting_document":
                continue
            target_id = document.target_motion_document_id
            assert target_id is not None
            target = next(
                (
                    candidate
                    for candidate in self.documents
                    if candidate.document_id == target_id
                ),
                None,
            )
            if target is None or target.role not in {
                "motion_to_dismiss_notice",
                "motion_to_dismiss_memorandum",
            }:
                raise ValueError(
                    "supporting document target_motion_document_id must name "
                    "a motion document"
                )
        return self


class ForecastPredictionUnit(ReleaseModel):
    """One public prediction unit and its exact execution byte commitments."""

    unit_id: NonEmptyString
    case_id: NonEmptyString
    claim_name: NonEmptyString
    defendant_group: NonEmptyString
    count: NonEmptyString
    should_score: bool
    model_visible_document_indexes: tuple[
        Annotated[int, Field(strict=True, ge=0)], ...
    ] = Field(min_length=1)
    packet_path: RelativePath
    packet_sha256: Sha256
    packet_byte_count: Annotated[int, Field(strict=True, gt=0)]
    prompt_path: RelativePath
    prompt_sha256: Sha256
    prompt_byte_count: Annotated[int, Field(strict=True, gt=0)]

    _paths_are_relative = field_validator("packet_path", "prompt_path")(
        _validate_relative_path
    )

    @model_validator(mode="after")
    def require_canonical_indexes(self) -> ForecastPredictionUnit:
        indexes = self.model_visible_document_indexes
        if indexes != tuple(sorted(set(indexes))):
            raise ValueError("model-visible document indexes must be unique and sorted")
        return self


class ForecastRelease(ReleaseModel):
    """The complete outcome-blinded public execution contract."""

    # contract-ratchet: allow registered public release schema identifier
    schema_version: Literal["legalforecast.forecast-release.v1"] = (
        FORECAST_RELEASE_SCHEMA
    )
    release_id: NonEmptyString
    policy_digest: Sha256
    code_version: NonEmptyString
    packet_builder_version: NonEmptyString
    run_manifest_binding: ForecastManifestBinding | None = None
    case_count: Annotated[int, Field(strict=True, gt=0)]
    unit_count: Annotated[int, Field(strict=True, gt=0)]
    cases: tuple[ReleaseCase, ...] = Field(min_length=1)
    prediction_units: tuple[ForecastPredictionUnit, ...] = Field(min_length=1)
    release_digest: Sha256

    @model_validator(mode="after")
    def require_canonical_release(self) -> ForecastRelease:
        case_ids = tuple(case.case_id for case in self.cases)
        if self.case_count != len(self.cases):
            raise ValueError("case_count does not match cases")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("duplicate case in forecast release")
        if case_ids != tuple(sorted(case_ids)):
            raise ValueError("cases are not in canonical case order")

        unit_ids = tuple(unit.unit_id for unit in self.prediction_units)
        if self.unit_count != len(self.prediction_units):
            raise ValueError("unit_count does not match prediction_units")
        if len(set(unit_ids)) != len(unit_ids):
            raise ValueError("duplicate prediction unit in forecast release")
        if unit_ids != tuple(sorted(unit_ids)):
            raise ValueError("prediction_units are not in canonical unit order")

        cases_by_id = {case.case_id: case for case in self.cases}
        document_ids: set[str] = set()
        artifact_paths: set[str] = set()
        for case in self.cases:
            for document in case.documents:
                if document.document_id in document_ids:
                    raise ValueError("duplicate document across forecast release")
                document_ids.add(document.document_id)
                if document.path in artifact_paths:
                    raise ValueError(f"artifact path is reused: {document.path}")
                artifact_paths.add(document.path)
        for unit in self.prediction_units:
            case = cases_by_id.get(unit.case_id)
            if case is None:
                raise ValueError("prediction unit references an unknown case")
            if unit.model_visible_document_indexes[-1] >= len(case.documents):
                raise ValueError("model-visible document index is out of range")
            for path in (unit.packet_path, unit.prompt_path):
                if path in artifact_paths:
                    raise ValueError(f"artifact path is reused: {path}")
                artifact_paths.add(path)
        return self


class LabelsRelease(ReleaseModel):
    """The separate outcome-bearing scoring contract."""

    # contract-ratchet: allow registered public release schema identifier
    schema_version: Literal["legalforecast.labels-release.v1"] = LABELS_RELEASE_SCHEMA
    release_id: NonEmptyString
    forecast_release_digest: Sha256
    scoring_policy: ScoringPolicy
    unit_count: Annotated[int, Field(strict=True, gt=0)]
    unit_outcomes: tuple[UnitOutcome, ...] = Field(min_length=1)
    release_digest: Sha256

    @model_validator(mode="after")
    def require_canonical_labels(self) -> LabelsRelease:
        identifiers = tuple(outcome.unit_id for outcome in self.unit_outcomes)
        if self.unit_count != len(self.unit_outcomes):
            raise ValueError("unit_count does not match unit_outcomes")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate labels unit outcome")
        if identifiers != tuple(sorted(identifiers)):
            raise ValueError("unit_outcomes are not in canonical unit order")
        return self
