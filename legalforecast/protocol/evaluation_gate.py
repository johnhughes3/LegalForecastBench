"""Evaluation readiness gates for frozen preregistration artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, cast

from legalforecast.evals.model_registry import ModelRegistry
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeDrift,
    FrozenArtifactName,
    detect_freeze_drift,
)
from legalforecast.protocol.preregistration import (
    PreregistrationValidationIssue,
    PreregistrationValidationResult,
    validate_preregistration_record,
)


class EvaluationGateMode(StrEnum):
    OFFICIAL = "official"
    RAPID = "rapid"


RAPID_REQUIRED_PROTOCOL_FIELDS = (
    "cycle_id",
    "claim_level",
    "publication_claim_language",
    "anchors.model_release",
    "eligibility_rules",
    "exclusion_rules",
    "model_registry.path",
    "model_registry.sha256",
    "frozen_artifacts.manifest_sha256",
    "frozen_artifacts.units_sha256",
    "frozen_artifacts.scorer_sha256",
)
RAPID_FROZEN_HASH_FIELDS = (
    "manifest_sha256",
    "units_sha256",
    "scorer_sha256",
)
_DRIFT_FIELD_BY_NAME: Mapping[FrozenArtifactName, str] = {
    FrozenArtifactName.MANIFEST: "frozen_artifacts.manifest_sha256",
    FrozenArtifactName.UNITS: "frozen_artifacts.units_sha256",
    FrozenArtifactName.LABELS: "frozen_artifacts.labels_sha256",
    FrozenArtifactName.PROMPT: "frozen_artifacts.prompt_sha256",
    FrozenArtifactName.SCORER: "frozen_artifacts.scorer_sha256",
    FrozenArtifactName.HARNESS: "frozen_artifacts.harness_sha256",
    FrozenArtifactName.MODEL_REGISTRY: "model_registry.sha256",
    FrozenArtifactName.BASELINES: "baselines.sha256",
}


def validate_evaluation_gate(
    record: Mapping[str, Any],
    *,
    mode: EvaluationGateMode = EvaluationGateMode.OFFICIAL,
    freeze_bundle: FreezeBundle | None = None,
    expected_hashes: Mapping[str, str] | None = None,
    model_registry: ModelRegistry | None = None,
    template_text: str | None = None,
) -> PreregistrationValidationResult:
    """Validate that a run may proceed without mutable protocol artifacts."""

    effective_hashes = (
        freeze_bundle.frozen_artifact_hashes()
        if freeze_bundle is not None and expected_hashes is None
        else expected_hashes
    )
    if mode is EvaluationGateMode.OFFICIAL:
        result = validate_preregistration_record(
            record,
            model_registry=model_registry,
            expected_hashes=effective_hashes,
            template_text=template_text,
        )
        issues = list(result.issues)
    else:
        issues = _validate_rapid_preregistration(record, effective_hashes)

    if freeze_bundle is not None:
        issues.extend(_drift_issues(detect_freeze_drift(freeze_bundle)))

    return PreregistrationValidationResult(tuple(issues))


def assert_evaluation_ready(
    record: Mapping[str, Any],
    *,
    mode: EvaluationGateMode = EvaluationGateMode.OFFICIAL,
    freeze_bundle: FreezeBundle | None = None,
    expected_hashes: Mapping[str, str] | None = None,
    model_registry: ModelRegistry | None = None,
    template_text: str | None = None,
) -> None:
    """Raise if a model-evaluation run would violate the freeze protocol."""

    validate_evaluation_gate(
        record,
        mode=mode,
        freeze_bundle=freeze_bundle,
        expected_hashes=expected_hashes,
        model_registry=model_registry,
        template_text=template_text,
    ).raise_for_errors()


def _validate_rapid_preregistration(
    record: Mapping[str, Any],
    expected_hashes: Mapping[str, str] | None,
) -> list[PreregistrationValidationIssue]:
    issues: list[PreregistrationValidationIssue] = []
    for field_path in RAPID_REQUIRED_PROTOCOL_FIELDS:
        if _is_missing(_get_path(record, field_path)):
            issues.append(_issue(field_path, "required rapid field is missing"))

    claim_level = _get_path(record, "claim_level")
    if isinstance(claim_level, str) and claim_level.strip().lower() != "rapid":
        issues.append(_issue("claim_level", "rapid gate requires claim_level=rapid"))

    _validate_hash_fields(
        record,
        field_names=RAPID_FROZEN_HASH_FIELDS,
        expected_hashes=expected_hashes,
        issues=issues,
    )
    _validate_section_hash(record, "model_registry.sha256", issues)
    return issues


def _validate_hash_fields(
    record: Mapping[str, Any],
    *,
    field_names: tuple[str, ...],
    expected_hashes: Mapping[str, str] | None,
    issues: list[PreregistrationValidationIssue],
) -> None:
    frozen_artifacts = _get_path(record, "frozen_artifacts")
    if not isinstance(frozen_artifacts, Mapping):
        return
    artifact_hashes = cast(Mapping[str, Any], frozen_artifacts)
    for field_name in field_names:
        path = f"frozen_artifacts.{field_name}"
        value = artifact_hashes.get(field_name)
        if not isinstance(value, str) or not _is_sha256(value):
            issues.append(_issue(path, "must be a lowercase SHA-256 hash"))
            continue
        if expected_hashes is not None and expected_hashes.get(field_name) != value:
            issues.append(_issue(path, "hash does not match frozen artifact"))


def _validate_section_hash(
    record: Mapping[str, Any],
    field_path: str,
    issues: list[PreregistrationValidationIssue],
) -> None:
    value = _get_path(record, field_path)
    if not isinstance(value, str) or not _is_sha256(value):
        issues.append(_issue(field_path, "must be a lowercase SHA-256 hash"))


def _drift_issues(
    drift: tuple[FreezeDrift, ...],
) -> list[PreregistrationValidationIssue]:
    return [
        _issue(
            _DRIFT_FIELD_BY_NAME[item.name],
            (
                "frozen artifact is missing"
                if item.is_missing
                else "frozen artifact changed after freeze"
            ),
        )
        for item in drift
    ]


def _get_path(record: Mapping[str, Any], field_path: str) -> object:
    current: object = record
    for part in field_path.split("."):
        if not isinstance(current, Mapping):
            return None
        mapping = cast(Mapping[str, object], current)
        if part not in mapping:
            return None
        current = mapping[part]
    return current


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _issue(path: str, message: str) -> PreregistrationValidationIssue:
    return PreregistrationValidationIssue(path=path, message=message)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
