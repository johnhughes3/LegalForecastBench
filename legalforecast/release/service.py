"""Issue, publish, load, and validate public release artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    FORECAST_RELEASE_V1,
    LABELS_RELEASE_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.immutable_io import (
    ImmutableIOError,
    publish_tree_create_only,
    read_single_link_file,
)

from .models import (
    CaseDraft,
    ForecastDraft,
    ForecastPredictionUnit,
    ForecastRelease,
    LabelsDraft,
    LabelsRelease,
    ReleaseCase,
    ReleaseDocument,
)


class ReleaseValidationError(ValueError):
    """Raised when release structure, commitments, or paired semantics fail."""


@dataclass(frozen=True, slots=True)
class IssuedRelease:
    """A validated forecast/labels pair ready for create-only publication."""

    forecast: ForecastRelease
    labels: LabelsRelease

    @property
    def payloads(self) -> dict[str, bytes]:
        """Return the canonical two-file public release tree."""

        return {
            "forecast-release.json": ARTIFACT_CANONICAL_JSON_V1.encode(
                self.forecast.model_dump(mode="json")
            ),
            "labels-release.json": ARTIFACT_CANONICAL_JSON_V1.encode(
                self.labels.model_dump(mode="json")
            ),
        }


@dataclass(frozen=True, slots=True)
class ForecastExecution:
    """Outcome-blinded execution input; labels have no API path into this object."""

    release: ForecastRelease
    artifact_root: Path

    def packet_bytes(self, unit_id: str) -> bytes:
        """Read and reverify one packet immediately before execution."""

        unit = self._unit(unit_id)
        return _read_verified_artifact(
            self.artifact_root,
            unit.packet_path,
            expected_digest=unit.packet_sha256,
            expected_byte_count=unit.packet_byte_count,
            label="packet",
        )

    def prompt_bytes(self, unit_id: str) -> bytes:
        """Read and reverify one prompt immediately before execution."""

        unit = self._unit(unit_id)
        return _read_verified_artifact(
            self.artifact_root,
            unit.prompt_path,
            expected_digest=unit.prompt_sha256,
            expected_byte_count=unit.prompt_byte_count,
            label="prompt",
        )

    def document_bytes(self, unit_id: str, document_index: int) -> bytes:
        """Read one unit-visible document by its committed case index."""

        unit = self._unit(unit_id)
        if document_index not in unit.model_visible_document_indexes:
            raise ReleaseValidationError(
                "document index is not model-visible for prediction unit"
            )
        case = next(case for case in self.release.cases if case.case_id == unit.case_id)
        document = case.documents[document_index]
        return _read_verified_artifact(
            self.artifact_root,
            document.path,
            expected_digest=document.sha256,
            expected_byte_count=document.byte_count,
            label=f"document {document.document_id}",
        )

    def _unit(self, unit_id: str) -> ForecastPredictionUnit:
        try:
            return next(
                unit
                for unit in self.release.prediction_units
                if unit.unit_id == unit_id
            )
        except StopIteration as exc:
            raise ReleaseValidationError(f"unknown prediction unit: {unit_id}") from exc


def issue_release(
    forecast_draft: ForecastDraft,
    labels_draft: LabelsDraft,
    *,
    artifact_root: Path,
) -> IssuedRelease:
    """Issue one deterministic committed release pair from concrete artifacts."""

    cases = tuple(
        _issue_case(case, artifact_root=artifact_root)
        for case in sorted(forecast_draft.cases, key=lambda item: item.case_id)
    )
    cases_by_id = {case.case_id: case for case in cases}
    units: list[ForecastPredictionUnit] = []
    for draft in sorted(forecast_draft.prediction_units, key=lambda item: item.unit_id):
        case = cases_by_id.get(draft.case_id)
        if case is None:
            raise ReleaseValidationError("prediction unit references an unknown case")
        index_by_document_id = {
            document.document_id: index for index, document in enumerate(case.documents)
        }
        try:
            indexes = tuple(
                sorted(
                    index_by_document_id[value]
                    for value in draft.model_visible_document_ids
                )
            )
        except KeyError as exc:
            raise ReleaseValidationError(
                "prediction unit references an unknown model-visible document"
            ) from exc
        if len(set(draft.model_visible_document_ids)) != len(
            draft.model_visible_document_ids
        ):
            raise ReleaseValidationError(
                "prediction unit repeats a model-visible document"
            )
        packet = _read_artifact(
            artifact_root, draft.packet_path, label=f"packet for {draft.unit_id}"
        )
        prompt = _read_artifact(
            artifact_root, draft.prompt_path, label=f"prompt for {draft.unit_id}"
        )
        units.append(
            ForecastPredictionUnit(
                unit_id=draft.unit_id,
                case_id=draft.case_id,
                claim_name=draft.claim_name,
                defendant_group=draft.defendant_group,
                count=draft.count,
                should_score=draft.should_score,
                model_visible_document_indexes=indexes,
                packet_path=draft.packet_path,
                packet_sha256=_raw_bytes_digest(packet),
                packet_byte_count=len(packet),
                prompt_path=draft.prompt_path,
                prompt_sha256=_raw_bytes_digest(prompt),
                prompt_byte_count=len(prompt),
            )
        )

    forecast = ForecastRelease(
        release_id=forecast_draft.release_id,
        policy_digest=forecast_draft.policy_digest,
        code_version=forecast_draft.code_version,
        packet_builder_version=forecast_draft.packet_builder_version,
        run_manifest_binding=forecast_draft.run_manifest_binding,
        case_count=len(cases),
        unit_count=len(units),
        cases=cases,
        prediction_units=tuple(units),
        release_digest="0" * 64,
    )
    forecast = forecast.model_copy(
        update={"release_digest": _forecast_digest(forecast)}
    )

    if labels_draft.release_id != forecast.release_id:
        raise ReleaseValidationError("forecast and labels release_id do not match")
    outcomes = tuple(sorted(labels_draft.unit_outcomes, key=lambda item: item.unit_id))
    labels = LabelsRelease(
        release_id=labels_draft.release_id,
        forecast_release_digest=forecast.release_digest,
        scoring_policy=labels_draft.scoring_policy,
        unit_count=len(outcomes),
        unit_outcomes=outcomes,
        release_digest="0" * 64,
    )
    labels = labels.model_copy(update={"release_digest": _labels_digest(labels)})
    _validate_pair(forecast, labels, artifact_root=artifact_root)
    return IssuedRelease(forecast=forecast, labels=labels)


def publish_release(
    output_dir: Path,
    issued: IssuedRelease,
    *,
    artifact_root: Path,
) -> None:
    """Reverify source bytes, then publish a pair as one create-only tree."""

    _validate_pair(issued.forecast, issued.labels, artifact_root=artifact_root)
    publish_tree_create_only(output_dir, issued.payloads)


def validate_release(
    forecast_path: Path,
    labels_path: Path,
    *,
    artifact_root: Path,
) -> tuple[ForecastRelease, LabelsRelease]:
    """Load and validate a paired release and every referenced public byte."""

    forecast = _load_forecast(forecast_path)
    labels = _load_labels(labels_path)
    _validate_pair(forecast, labels, artifact_root=artifact_root)
    return forecast, labels


def load_forecast_execution(
    forecast_path: Path, *, artifact_root: Path
) -> ForecastExecution:
    """Load only the outcome-blinded execution side of a release."""

    forecast = _load_forecast(forecast_path)
    _validate_forecast(forecast, artifact_root=artifact_root)
    return ForecastExecution(release=forecast, artifact_root=artifact_root)


def load_forecast_draft(path: Path) -> ForecastDraft:
    """Load a strict generic forecast issuer draft."""

    return _model_from_path(path, ForecastDraft, label="forecast draft")


def load_labels_draft(path: Path) -> LabelsDraft:
    """Load a strict generic labels issuer draft."""

    return _model_from_path(path, LabelsDraft, label="labels draft")


def _issue_case(draft: CaseDraft, *, artifact_root: Path) -> ReleaseCase:
    documents: list[ReleaseDocument] = []
    for document in sorted(draft.documents, key=lambda item: item.document_id):
        payload = _read_artifact(
            artifact_root, document.path, label=f"document {document.document_id}"
        )
        documents.append(
            ReleaseDocument(
                document_id=document.document_id,
                role=document.role,
                path=document.path,
                sha256=_raw_bytes_digest(payload),
                byte_count=len(payload),
            )
        )
    return ReleaseCase(case_id=draft.case_id, documents=tuple(documents))


def _load_forecast(path: Path) -> ForecastRelease:
    return _canonical_release_from_path(path, ForecastRelease, label="forecast release")


def _load_labels(path: Path) -> LabelsRelease:
    return _canonical_release_from_path(path, LabelsRelease, label="labels release")


def _canonical_release_from_path[ReleaseModelT: BaseModel](
    path: Path, model_type: type[ReleaseModelT], *, label: str
) -> ReleaseModelT:
    try:
        payload = read_single_link_file(path, label=label)
        model = model_type.model_validate_json(payload)
    except (ImmutableIOError, ValidationError) as exc:
        raise ReleaseValidationError(f"invalid {label}: {exc}") from exc
    if ARTIFACT_CANONICAL_JSON_V1.encode(model.model_dump(mode="json")) != payload:
        raise ReleaseValidationError(f"{label} is not canonical artifact JSON")
    return model


def _model_from_path[ReleaseModelT: BaseModel](
    path: Path, model_type: type[ReleaseModelT], *, label: str
) -> ReleaseModelT:
    try:
        payload = read_single_link_file(path, label=label)
        return model_type.model_validate_json(payload)
    except (ImmutableIOError, ValidationError) as exc:
        raise ReleaseValidationError(f"invalid {label}: {exc}") from exc


def _validate_pair(
    forecast: ForecastRelease,
    labels: LabelsRelease,
    *,
    artifact_root: Path,
) -> None:
    _validate_forecast(forecast, artifact_root=artifact_root)
    if _labels_digest(labels) != labels.release_digest:
        raise ReleaseValidationError("labels release digest does not match")
    if labels.release_id != forecast.release_id:
        raise ReleaseValidationError("forecast and labels release_id do not match")
    if labels.forecast_release_digest != forecast.release_digest:
        raise ReleaseValidationError("labels bind the wrong forecast release digest")
    forecast_units = {
        unit.unit_id for unit in forecast.prediction_units if unit.should_score
    }
    label_units = {outcome.unit_id for outcome in labels.unit_outcomes}
    if forecast_units != label_units:
        raise ReleaseValidationError(
            "labels unit set does not match scoreable forecast unit set"
        )


def _validate_forecast(forecast: ForecastRelease, *, artifact_root: Path) -> None:
    if _forecast_digest(forecast) != forecast.release_digest:
        raise ReleaseValidationError("forecast release digest does not match")
    for case in forecast.cases:
        for document in case.documents:
            _verify_artifact(
                artifact_root,
                document.path,
                expected_digest=document.sha256,
                expected_byte_count=document.byte_count,
                label=f"document {document.document_id}",
            )
    for unit in forecast.prediction_units:
        _verify_artifact(
            artifact_root,
            unit.packet_path,
            expected_digest=unit.packet_sha256,
            expected_byte_count=unit.packet_byte_count,
            label="packet",
        )
        _verify_artifact(
            artifact_root,
            unit.prompt_path,
            expected_digest=unit.prompt_sha256,
            expected_byte_count=unit.prompt_byte_count,
            label="prompt",
        )


def _verify_artifact(
    root: Path,
    relative_path: str,
    *,
    expected_digest: str,
    expected_byte_count: int,
    label: str,
) -> None:
    _read_verified_artifact(
        root,
        relative_path,
        expected_digest=expected_digest,
        expected_byte_count=expected_byte_count,
        label=label,
    )


def _read_verified_artifact(
    root: Path,
    relative_path: str,
    *,
    expected_digest: str,
    expected_byte_count: int,
    label: str,
) -> bytes:
    payload = _read_artifact(root, relative_path, label=label)
    if len(payload) != expected_byte_count:
        raise ReleaseValidationError(f"{label} byte count mismatch: {relative_path}")
    if _raw_bytes_digest(payload) != expected_digest:
        raise ReleaseValidationError(f"{label} SHA-256 mismatch: {relative_path}")
    return payload


def _read_artifact(root: Path, relative_path: str, *, label: str) -> bytes:
    try:
        return read_single_link_file(root / relative_path, label=label)
    except ImmutableIOError as exc:
        raise ReleaseValidationError(str(exc)) from exc


def _forecast_digest(forecast: ForecastRelease) -> str:
    value = forecast.model_dump(mode="json", exclude={"release_digest"})
    commitment = ARTIFACT_RAW_SHA256_V1.commit(value, domain=FORECAST_RELEASE_V1)
    return str(commitment.digest)


def _labels_digest(labels: LabelsRelease) -> str:
    value = labels.model_dump(mode="json", exclude={"release_digest"})
    commitment = ARTIFACT_RAW_SHA256_V1.commit(value, domain=LABELS_RELEASE_V1)
    return str(commitment.digest)


def _raw_bytes_digest(payload: bytes) -> str:
    commitment = RAW_BYTES_RAW_SHA256_V1.commit(payload, domain=FORECAST_RELEASE_V1)
    return str(commitment.digest)
