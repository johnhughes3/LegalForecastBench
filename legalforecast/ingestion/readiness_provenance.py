"""Fail-closed Stage A and Stage B provenance gates for corpus readiness."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, cast

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.labeling.llm_pipeline import (
    LlmPipelineError,
    merge_structural_flags_into_review_queue,
    validate_unitizer_terminal_preserved_audit_record,
)
from legalforecast.unitization.review import (
    canonical_records_sha256,
    canonical_sha256,
    verify_finalized_prediction_units,
    verify_terminal_unitizer_finalized_units,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_STRUCTURAL_FLAG_FIELDS = (
    "flag_type",
    "affected_unit_ids",
    "source_document_ids",
    "citation_excerpt",
    "explanation",
)


class ReadinessProvenanceError(ValueError):
    """Raised when labeling provenance could be omitted, substituted, or tampered."""


def verify_stage_a_readiness_provenance(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    raw_prediction_unit_records: Iterable[Mapping[str, Any]],
    original_review_records: Iterable[Mapping[str, Any]],
    structural_flag_records: Iterable[Mapping[str, Any]],
    structural_review_audit_records: Iterable[Mapping[str, Any]],
    merged_review_records: Iterable[Mapping[str, Any]],
    finalized_prediction_unit_records: Iterable[Mapping[str, Any]],
    adjudication_records: Iterable[Mapping[str, Any]],
    reviewer_registry_entries: Sequence[ModelRegistryEntry],
    reviewer_registry_sha256: str,
    reviewer_model_key: str,
    terminal_review_records: Iterable[Mapping[str, Any]] = (),
    terminal_escalation_records: Iterable[Mapping[str, Any]] = (),
    terminal_adjudication_records: Iterable[Mapping[str, Any]] = (),
) -> None:
    """Require complete Gemini review and bind final units to its merged queue."""

    selections = _unique_by_candidate(selection_records, "selection")
    raw_units = _unique_by_candidate(raw_prediction_unit_records, "raw Stage A units")
    if not set(raw_units).issubset(selections):
        raise ReadinessProvenanceError(
            "Stage A structural-review candidate is absent from selections"
        )
    terminal_reviews = tuple(dict(record) for record in terminal_review_records)
    terminal_escalations = tuple(dict(record) for record in terminal_escalation_records)
    terminal_adjudications = tuple(
        dict(record) for record in terminal_adjudication_records
    )
    terminal_ids = {
        _required_str(record, "candidate_id") for record in terminal_reviews
    }
    if terminal_ids:
        if not terminal_ids.issubset(raw_units):
            raise ReadinessProvenanceError(
                "terminal Stage A candidate is absent from raw units"
            )
        if any(
            raw_units[candidate_id].get("prediction_units") != []
            for candidate_id in terminal_ids
        ):
            raise ReadinessProvenanceError(
                "terminal Stage A raw envelope must contain zero accepted units"
            )
    ordinary_raw_units = {
        candidate_id: record
        for candidate_id, record in raw_units.items()
        if candidate_id not in terminal_ids
    }
    finalized_records = tuple(
        dict(record) for record in finalized_prediction_unit_records
    )
    finalized_by_candidate = _unique_by_candidate(
        finalized_records, "finalized Stage A units"
    )
    if set(finalized_by_candidate) != set(raw_units):
        raise ReadinessProvenanceError(
            "finalized Stage A units do not exactly cover raw candidates"
        )
    terminal_finalized = [
        finalized_by_candidate[candidate_id] for candidate_id in terminal_ids
    ]
    ordinary_finalized = [
        finalized_by_candidate[candidate_id] for candidate_id in ordinary_raw_units
    ]
    try:
        verify_terminal_unitizer_finalized_units(
            terminal_finalized,
            terminal_reviews,
            terminal_escalations,
            terminal_adjudications,
        )
    except ValueError as exc:
        raise ReadinessProvenanceError(str(exc)) from exc

    reviewer = _registry_entry(reviewer_registry_entries, reviewer_model_key)
    _sha(reviewer_registry_sha256, "reviewer_registry_sha256")

    original = tuple(dict(record) for record in original_review_records)
    flags = tuple(dict(record) for record in structural_flag_records)
    merged = tuple(dict(record) for record in merged_review_records)
    expected_merged = merge_structural_flags_into_review_queue(original, flags)
    if merged != expected_merged:
        raise ReadinessProvenanceError(
            "Stage A review queue is not the verified original-plus-structural merge"
        )

    flags_by_candidate: dict[str, list[Mapping[str, Any]]] = {
        candidate_id: [] for candidate_id in ordinary_raw_units
    }
    for flag in flags:
        candidate_id = _required_str(flag, "candidate_id")
        if candidate_id not in flags_by_candidate:
            raise ReadinessProvenanceError(
                f"structural flag references unknown candidate: {candidate_id}"
            )
        if flag.get("schema_version") != "legalforecast.stage_a_structural_flag.v1":
            raise ReadinessProvenanceError("unsupported Stage A structural flag schema")
        if flag.get("reviewer_model_key") != reviewer_model_key:
            raise ReadinessProvenanceError("structural flag reviewer model mismatch")
        if flag.get("model_registry_sha256") != reviewer_registry_sha256:
            raise ReadinessProvenanceError("structural flag registry hash mismatch")
        raw = ordinary_raw_units[candidate_id]
        if flag.get("raw_prediction_units_sha256") != canonical_sha256(raw):
            raise ReadinessProvenanceError("structural flag raw-unit hash mismatch")
        flag_content = {field: flag.get(field) for field in _STRUCTURAL_FLAG_FIELDS}
        if flag.get("flag_sha256") != canonical_sha256(flag_content):
            raise ReadinessProvenanceError("structural flag content hash mismatch")
        flags_by_candidate[candidate_id].append(flag)

    all_audits = _unique_by_candidate(
        structural_review_audit_records, "Stage A structural-review audit"
    )
    if set(all_audits) != set(raw_units):
        raise ReadinessProvenanceError(
            "Stage A structural-review audit does not cover every candidate"
        )
    for candidate_id in terminal_ids:
        try:
            validate_unitizer_terminal_preserved_audit_record(
                all_audits[candidate_id],
                candidate_id=candidate_id,
                case_id=_required_str(selections[candidate_id], "case_id"),
                reviewer_model_key=reviewer_model_key,
                model_registry_sha256=reviewer_registry_sha256,
                raw_prediction_units=raw_units[candidate_id],
            )
        except LlmPipelineError as exc:
            raise ReadinessProvenanceError(str(exc)) from exc
    audits = {
        candidate_id: audit
        for candidate_id, audit in all_audits.items()
        if candidate_id not in terminal_ids
    }
    for candidate_id, audit in audits.items():
        expected_flags = flags_by_candidate[candidate_id]
        if audit.get("stage") != "llm-review-stage-a" or audit.get("status") not in {
            "passed",
            "flags_pending",
        }:
            raise ReadinessProvenanceError(
                f"Stage A structural review is incomplete: {candidate_id}"
            )
        if audit.get("model_key") != reviewer_model_key:
            raise ReadinessProvenanceError("Stage A reviewer model key mismatch")
        if audit.get("model_registry_sha256") != reviewer_registry_sha256:
            raise ReadinessProvenanceError("Stage A reviewer registry hash mismatch")
        served_version = _required_str(audit, "served_model_version")
        metadata = _mapping(audit.get("metadata"), "Stage A audit metadata")
        if (
            served_version != reviewer.model_version_or_snapshot
            or metadata.get("served_model_version") != served_version
        ):
            raise ReadinessProvenanceError("Stage A served model version mismatch")
        if audit.get("raw_prediction_units_sha256") != canonical_sha256(
            ordinary_raw_units[candidate_id]
        ):
            raise ReadinessProvenanceError("Stage A audit raw-unit hash mismatch")
        _sha(audit.get("prompt_sha256"), "Stage A prompt_sha256")
        _sha(audit.get("raw_output_sha256"), "Stage A raw_output_sha256")
        if audit.get("structural_flags_sha256") != canonical_records_sha256(
            expected_flags
        ):
            raise ReadinessProvenanceError("Stage A structural flags hash mismatch")
        if audit.get("flag_count") != len(expected_flags):
            raise ReadinessProvenanceError("Stage A structural flag count mismatch")

    verify_finalized_prediction_units(
        ordinary_finalized,
        ordinary_raw_units.values(),
        adjudication_records,
        merged,
    )


def verify_stage_b_readiness_provenance(
    *,
    finalized_prediction_unit_records: Iterable[Mapping[str, Any]],
    label_audit_records: Iterable[Mapping[str, Any]],
    judge_registry_entries: Sequence[ModelRegistryEntry],
    judge_registry_sha256: str,
    decision_text_by_candidate_and_document: Mapping[tuple[str, str], str],
) -> None:
    """Require unanimous frozen-panel evidence with per-voter verbatim excerpts."""

    if len(judge_registry_entries) != 2:
        raise ReadinessProvenanceError(
            "Stage B readiness requires the frozen two-model judge panel"
        )
    expected_keys = tuple(entry.registry_key for entry in judge_registry_entries)
    if len(set(expected_keys)) != 2:
        raise ReadinessProvenanceError("Stage B judge panel contains duplicate models")
    _sha(judge_registry_sha256, "judge_registry_sha256")
    entry_by_key = {entry.registry_key: entry for entry in judge_registry_entries}

    finalized = _unique_by_candidate(
        finalized_prediction_unit_records, "finalized Stage A units"
    )
    required_units: dict[str, set[str]] = {}
    for candidate_id, record in finalized.items():
        if record.get("status") != "finalized":
            continue
        required_units[candidate_id] = {
            _required_str(unit, "unit_id")
            for unit in _records(record.get("prediction_units"), "prediction_units")
            if unit.get("should_score") is True
        }

    audits = {
        candidate_id: audit
        for candidate_id, audit in _unique_by_candidate(
            (
                record
                for record in label_audit_records
                if record.get("stage") == "llm-label"
            ),
            "Stage B label audit",
        ).items()
        if candidate_id in required_units
    }
    if set(audits) != set(required_units):
        raise ReadinessProvenanceError(
            "Stage B label audit does not cover every finalized candidate"
        )

    consensus_commitment = canonical_sha256(
        {
            "consensus_policy": "unanimous",
            "model_keys": list(expected_keys),
            "model_registry_sha256": judge_registry_sha256,
        }
    )
    for candidate_id, audit in audits.items():
        if audit.get("status") not in {"succeeded", "adjudication_pending"}:
            raise ReadinessProvenanceError(
                f"Stage B audit is incomplete: {candidate_id}"
            )
        if audit.get("consensus_policy") != "unanimous":
            raise ReadinessProvenanceError("Stage B consensus policy is not unanimous")
        if audit.get("model_registry_sha256") != judge_registry_sha256:
            raise ReadinessProvenanceError("Stage B judge registry hash mismatch")
        if tuple(_strings(audit.get("model_keys"), "model_keys")) != expected_keys:
            raise ReadinessProvenanceError("Stage B frozen judge panel mismatch")
        if audit.get("consensus_policy_sha256") != consensus_commitment:
            raise ReadinessProvenanceError("Stage B consensus commitment mismatch")

        outputs = _records(audit.get("model_outputs"), "model_outputs")
        outputs_by_key = {
            _required_str(output, "model_key"): output for output in outputs
        }
        if len(outputs_by_key) != len(outputs) or set(outputs_by_key) != set(
            expected_keys
        ):
            raise ReadinessProvenanceError("Stage B model-output panel mismatch")
        for model_key in expected_keys:
            output = outputs_by_key[model_key]
            entry = entry_by_key[model_key]
            _sha(output.get("raw_output_sha256"), "Stage B raw_output_sha256")
            metadata = _mapping(output.get("metadata"), "Stage B model metadata")
            if metadata.get("served_model_version") != entry.model_version_or_snapshot:
                raise ReadinessProvenanceError("Stage B served model version mismatch")
            voter_labels = _records(output.get("labels"), "Stage B voter labels")
            labels_by_unit = {
                _required_str(label, "unit_id"): label for label in voter_labels
            }
            if (
                len(labels_by_unit) != len(voter_labels)
                or set(labels_by_unit) != required_units[candidate_id]
            ):
                raise ReadinessProvenanceError(
                    "Stage B voter labels do not cover every scorable unit"
                )
            for label in voter_labels:
                citations = _records(
                    label.get("supporting_citations"), "supporting_citations"
                )
                if not citations:
                    raise ReadinessProvenanceError(
                        "Stage B voter label lacks disposition evidence"
                    )
                for citation in citations:
                    document_id = _required_str(citation, "document_id")
                    excerpt = _required_str(citation, "excerpt")
                    decision_text = decision_text_by_candidate_and_document.get(
                        (candidate_id, document_id)
                    )
                    if decision_text is None or excerpt not in decision_text:
                        raise ReadinessProvenanceError(
                            "Stage B voter excerpt is not verbatim disposition text"
                        )


def _registry_entry(
    entries: Sequence[ModelRegistryEntry], model_key: str
) -> ModelRegistryEntry:
    matches = [entry for entry in entries if entry.registry_key == model_key]
    if len(matches) != 1:
        raise ReadinessProvenanceError(
            "Stage A reviewer model key is not unique in the frozen registry"
        )
    return matches[0]


def _unique_by_candidate(
    records: Iterable[Mapping[str, Any]], description: str
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in indexed:
            raise ReadinessProvenanceError(
                f"duplicate {description} candidate: {candidate_id}"
            )
        indexed[candidate_id] = record
    return indexed


def _mapping(value: object, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReadinessProvenanceError(f"{description} must be an object")
    return cast(Mapping[str, Any], value)


def _records(value: object, description: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReadinessProvenanceError(f"{description} must be a list")
    result: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise ReadinessProvenanceError(f"{description} must contain objects")
        result.append(cast(Mapping[str, Any], item))
    return tuple(result)


def _strings(value: object, description: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReadinessProvenanceError(f"{description} must be a list")
    result: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item:
            raise ReadinessProvenanceError(
                f"{description} must contain nonempty strings"
            )
        result.append(item)
    return tuple(result)


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ReadinessProvenanceError(f"{field} is required")
    return value


def _sha(value: object, description: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ReadinessProvenanceError(f"{description} must be a SHA-256 digest")
    return value
