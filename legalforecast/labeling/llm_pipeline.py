"""Registry-backed LLM unitization and outcome-labeling helpers."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.live_model_solver import (
    LiveModelTransport,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.ensemble import (
    DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    EnsembleLabelVote,
    evaluate_labeling_ensemble,
)
from legalforecast.labeling.label_outcomes import (
    AmendmentSignal,
    OutcomeLabel,
    StageBDecisionText,
    StageBLabelingInput,
    StageBMissingUnitFlag,
    StageBUnitFinding,
    UnitResolution,
    label_stage_b_outcomes,
)
from legalforecast.unitization.construct_units import (
    StageAConstructionInput,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    construct_stage_a_units,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)

JsonRecord = dict[str, Any]


class LlmConsensusPolicy(StrEnum):
    """How LLM-only outcome labels are selected from multiple judge votes."""

    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    FIRST_MODEL = "first_model"


class LlmPipelineError(ValueError):
    """Raised when an LLM response cannot produce validated benchmark artifacts."""


class LlmResponseValidationError(LlmPipelineError):
    """Raised when a provider response exists but fails local validation."""

    def __init__(self, message: str, *, response: SolverResponse) -> None:
        super().__init__(message)
        self.response = response


@dataclass(frozen=True, slots=True)
class LlmBatchResult:
    """Records and audit rows produced by one LLM batch stage."""

    records: tuple[JsonRecord, ...]
    audit_records: tuple[JsonRecord, ...]

    @property
    def succeeded_count(self) -> int:
        return len(self.records)

    @property
    def failed_count(self) -> int:
        return sum(
            1
            for record in self.audit_records
            if record.get("status") not in {"succeeded", "dry_run"}
        )

    @property
    def total_estimated_cost(self) -> float:
        return sum(
            _float(record.get("estimated_cost")) for record in self.audit_records
        )


@dataclass(frozen=True, slots=True)
class _LlmDocument:
    candidate_id: str
    source_document_id: str
    document_role: DocumentRole
    docket_entry_number: int | None
    description: str
    markdown: str

    def stage_a_source(self) -> StageASourceDocument:
        return StageASourceDocument(
            document_id=self.source_document_id,
            role=StageADocumentRole(self.document_role.value),
            docket_entry_number=self.docket_entry_number,
            title=self.description,
        )

    def prompt_record(self) -> JsonRecord:
        return {
            "source_document_id": self.source_document_id,
            "document_role": self.document_role.value,
            "docket_entry_number": self.docket_entry_number,
            "description": self.description,
            "markdown": self.markdown,
        }


def llm_unitize_cases(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str | None = None,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = 120.0,
    continue_on_error: bool = False,
) -> LlmBatchResult:
    """Generate and validate Stage A prediction units from predecision materials."""

    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    records: list[JsonRecord] = []
    audit_records: list[JsonRecord] = []
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        response: SolverResponse | None = None
        try:
            documents = _predecision_documents(
                selection,
                parser_by_key=parser_by_key,
                markdown_root=Path(markdown_root),
            )
            prompt = _unitization_prompt(selection, documents)
            response = complete_live_prompt(
                registry_entry,
                prompt,
                model_registry_sha256=model_registry_sha256,
                transport=transport,
                environ=environ,
                timeout_seconds=timeout_seconds,
            )
            payload = _json_object_from_response(
                response.raw_output,
                top_level_sequence_field="unit_seeds",
            )
            result = construct_stage_a_units(
                StageAConstructionInput(
                    candidate_id=candidate_id,
                    case_id=_required_str(selection, "case_id"),
                    source_documents=tuple(
                        document.stage_a_source() for document in documents
                    ),
                    unit_seeds=tuple(
                        _stage_a_seed(record)
                        for record in _record_sequence(
                            payload.get("unit_seeds"), "unit_seeds"
                        )
                    ),
                    metadata={"llm_unitizer_model_key": registry_entry.registry_key},
                )
            )
            if not any(unit.should_score for unit in result.units):
                raise LlmPipelineError("LLM unitization produced no scorable units")
            records.append(
                {
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "prediction_units": [unit.to_record() for unit in result.units],
                }
            )
            audit_records.append(
                {
                    "stage": "llm-unitize",
                    "status": "succeeded",
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "model_key": registry_entry.registry_key,
                    "model_registry_sha256": model_registry_sha256 or "unrecorded",
                    "human_verified": False,
                    "unit_count": len(result.units),
                    "scorable_unit_count": sum(
                        unit.should_score for unit in result.units
                    ),
                    "review_items": [item.to_record() for item in result.review_items],
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "estimated_cost": response.estimated_cost,
                    "raw_output_sha256": response.raw_output_sha256,
                    "metadata": dict(response.metadata or {}),
                }
            )
        except Exception as exc:
            failure_record = _failure_audit_record(
                    stage="llm-unitize",
                    selection=selection,
                    model_key=registry_entry.registry_key,
                    error=exc,
                    model_registry_sha256=model_registry_sha256,
            )
            if response is not None:
                failure_record.update(_response_audit_fields(response))
            audit_records.append(failure_record)
            if not continue_on_error:
                raise
    return LlmBatchResult(records=tuple(records), audit_records=tuple(audit_records))


def llm_label_cases(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    registry_entries: Sequence[ModelRegistryEntry],
    model_registry_sha256: str | None = None,
    consensus_policy: LlmConsensusPolicy = LlmConsensusPolicy.UNANIMOUS,
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = 120.0,
    continue_on_error: bool = False,
) -> LlmBatchResult:
    """Generate Stage B outcome labels with registry-backed LLM judges."""

    if not registry_entries:
        raise LlmPipelineError("at least one registry entry is required")
    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    units_by_candidate = _prediction_units_by_candidate(prediction_unit_records)
    records: list[JsonRecord] = []
    audit_records: list[JsonRecord] = []
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        try:
            frozen_units = units_by_candidate.get(candidate_id)
            if not frozen_units:
                raise LlmPipelineError(f"prediction units missing for {candidate_id}")
            decision = _decision_document(
                selection,
                parser_by_key=parser_by_key,
                markdown_root=Path(markdown_root),
            )
            decision_text = StageBDecisionText(
                document_id=decision.source_document_id,
                entered_date=_decision_date(selection),
                text=decision.markdown,
            )
            model_outputs: list[JsonRecord] = []
            votes: list[EnsembleLabelVote] = []
            labels_by_model: dict[str, tuple[OutcomeLabel, ...]] = {}
            for entry in registry_entries:
                labels, response, finding_count, missing_flag_count = (
                    _llm_label_one_model(
                        selection=selection,
                        decision_text=decision_text,
                        frozen_units=tuple(frozen_units),
                        registry_entry=entry,
                    model_registry_sha256=model_registry_sha256,
                    transport=transport,
                    environ=environ,
                    timeout_seconds=timeout_seconds,
                )
                )
                labels_by_model[entry.registry_key] = labels
                model_outputs.append(
                    {
                        "model_key": entry.registry_key,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "estimated_cost": response.estimated_cost,
                        "raw_output_sha256": response.raw_output_sha256,
                        "finding_count": finding_count,
                        "missing_unit_flag_count": missing_flag_count,
                        "metadata": dict(response.metadata or {}),
                    }
                )
                votes.extend(
                    EnsembleLabelVote(
                        model_id=entry.registry_key,
                        unit_id=label.unit_id,
                        label=label,
                        confidence=label.label_confidence,
                        rationale="LLM-only Stage B outcome label.",
                        raw_response_id=response.raw_output_sha256,
                    )
                    for label in labels
                )
            ensemble = evaluate_labeling_ensemble(
                votes,
                high_confidence_threshold=high_confidence_threshold,
                required_model_count=len(registry_entries),
            )
            selected_labels = _selected_labels(
                labels_by_model,
                votes,
                consensus_policy=consensus_policy,
                first_model_key=registry_entries[0].registry_key,
            )
            ambiguous = [label.unit_id for label in selected_labels if label.ambiguous]
            if ambiguous:
                raise LlmPipelineError(
                    f"LLM-only labels include ambiguous units: {ambiguous}"
                )
            records.extend(label.to_record() for label in selected_labels)
            audit_records.append(
                {
                    "stage": "llm-label",
                    "status": "succeeded",
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "model_keys": [entry.registry_key for entry in registry_entries],
                    "model_registry_sha256": model_registry_sha256 or "unrecorded",
                    "human_verified": False,
                    "consensus_policy": consensus_policy.value,
                    "label_count": len(selected_labels),
                    "unit_count": len(frozen_units),
                    "model_outputs": model_outputs,
                    "ensemble": ensemble.to_record(),
                    "selected_labels": [label.to_record() for label in selected_labels],
                    "estimated_cost": sum(
                        _float(output.get("estimated_cost")) for output in model_outputs
                    ),
                }
            )
        except Exception as exc:
            failure_record = _failure_audit_record(
                    stage="llm-label",
                    selection=selection,
                    model_key=",".join(
                        entry.registry_key for entry in registry_entries
                    ),
                    error=exc,
                    model_registry_sha256=model_registry_sha256,
                )
            if isinstance(exc, LlmResponseValidationError):
                failure_record.update(_response_audit_fields(exc.response))
            audit_records.append(failure_record)
            if not continue_on_error:
                raise
    return LlmBatchResult(records=tuple(records), audit_records=tuple(audit_records))


def _llm_label_one_model(
    *,
    selection: Mapping[str, Any],
    decision_text: StageBDecisionText,
    frozen_units: tuple[PredictionUnit, ...],
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str | None,
    transport: LiveModelTransport | None,
    environ: Mapping[str, str] | None,
    timeout_seconds: float,
) -> tuple[tuple[OutcomeLabel, ...], SolverResponse, int, int]:
    prompt = _labeling_prompt(selection, decision_text, frozen_units)
    response = complete_live_prompt(
        registry_entry,
        prompt,
        model_registry_sha256=model_registry_sha256,
        transport=transport,
        environ=environ,
        timeout_seconds=timeout_seconds,
    )
    try:
        payload = _json_object_from_response(
            response.raw_output,
            top_level_sequence_field="unit_findings",
        )
        findings = tuple(
            _stage_b_finding(record, decision_text=decision_text)
            for record in _record_sequence(
                payload.get("unit_findings"),
                "unit_findings",
            )
        )
        missing_flags = tuple(
            _stage_b_missing_flag(record, decision_text=decision_text)
            for record in _optional_record_sequence(payload.get("missing_unit_flags"))
        )
        result = label_stage_b_outcomes(
            StageBLabelingInput(
                candidate_id=_required_str(selection, "candidate_id"),
                case_id=_required_str(selection, "case_id"),
                frozen_units=frozen_units,
                decision_text=decision_text,
                unit_findings=findings,
                missing_unit_flags=missing_flags,
            )
        )
    except Exception as exc:
        raise LlmResponseValidationError(str(exc), response=response) from exc
    return result.labels, response, len(findings), len(missing_flags)


def _unitization_prompt(
    selection: Mapping[str, Any],
    documents: Sequence[_LlmDocument],
) -> str:
    payload = {
        "task": "Construct frozen Stage A LegalForecastBench prediction units.",
        "rules": [
            "Use only the predecision documents supplied in this prompt.",
            "Do not read or infer from the later decision or any outside source.",
            (
                "A prediction unit is a challenged claim-defendant or claim-defendant "
                "group whose disposition can later be scored as fully dismissed or not."
            ),
            (
                "Create units only for claims actually challenged by the target motion "
                "to dismiss or motion for judgment on the pleadings."
            ),
            (
                "Use grouped defendants only when the pleadings/motion treat them "
                "together on materially identical legal grounds."
            ),
            (
                "Every unit_seed must include count, claim_name, defendant_names, "
                "source_document_ids, challenged_by_motion, challenge_scope, "
                "unit_confidence, and grouping. If a pleading does not number "
                "claims, set count to Unnumbered claim."
            ),
            (
                "defendant_names and source_document_ids must always be JSON "
                "arrays of strings, even when there is only one value."
            ),
            "Return only valid JSON. Do not wrap it in markdown fences.",
        ],
        "output_schema": {
            "unit_seeds": [
                {
                    "count": "string count label, e.g. Count I or Claim 1",
                    "claim_name": "string legal claim name",
                    "defendant_names": ["one or more defendant names"],
                    "source_document_ids": ["ids from allowed_source_document_ids"],
                    "challenged_by_motion": True,
                    "challenge_scope": [
                        "entire_claim",
                        "partial_theory_only",
                        "separable_subclaim",
                        "unclear",
                    ],
                    "unit_confidence": "number from 0 to 1",
                    "grouping": ["individual", "grouped"],
                    "grouping_rationale": "required for grouped, otherwise null",
                    "group_label": "optional display label",
                    "separable_subclaim": "required only for separable_subclaim",
                    "uncertainty_notes": "required only for unclear",
                    "citation_page": "optional positive integer",
                    "citation_paragraph": "optional positive integer",
                    "citation_excerpt": "optional short excerpt from a source document",
                }
            ]
        },
        "case": _case_prompt_record(selection),
        "allowed_source_document_ids": [
            document.source_document_id for document in documents
        ],
        "documents": [document.prompt_record() for document in documents],
    }
    return json.dumps(payload, sort_keys=True, indent=2)


def _labeling_prompt(
    selection: Mapping[str, Any],
    decision_text: StageBDecisionText,
    frozen_units: Sequence[PredictionUnit],
) -> str:
    payload = {
        "task": "Create Stage B outcome labels for frozen LegalForecastBench units.",
        "rules": [
            "Use only the first written disposition text supplied in this prompt.",
            "Do not add prediction units in unit_findings.",
            (
                "For each scoreable frozen unit, decide whether that unit was fully "
                "dismissed by this disposition."
            ),
            (
                "Partial narrowing, dismissal of some theories, or survival in any "
                "material respect is partial_dismissal_only or "
                "survives_in_material_respect, "
                "not fully_dismissed."
            ),
            (
                "supporting_excerpt must be copied verbatim from the decision_text so "
                "the validator can locate it."
            ),
            (
                "If resolution is fully_dismissed, amendment_signal must be one of "
                "express_leave_to_amend, express_invitation_to_seek_leave, "
                "express_denial_of_leave, or silent."
            ),
            (
                "If resolution is survives_in_material_respect or "
                "partial_dismissal_only, amendment_signal must be not_applicable."
            ),
            (
                "If resolution is ambiguous, amendment_signal must be ambiguous."
            ),
            (
                "Return only a JSON object with unit_findings and "
                "missing_unit_flags arrays."
            ),
        ],
        "resolution_values": [value.value for value in UnitResolution],
        "amendment_signal_values": [value.value for value in AmendmentSignal],
        "case": _case_prompt_record(selection),
        "frozen_units": [
            unit.to_record() for unit in frozen_units if unit.should_score
        ],
        "decision_text": {
            "document_id": decision_text.document_id,
            "entered_date": decision_text.entered_date,
            "text": decision_text.text,
        },
        "output_schema": {
            "unit_findings": [
                {
                    "unit_id": "unit_id from frozen_units",
                    "resolution": "one resolution value",
                    "amendment_signal": "one amendment signal value",
                    "supporting_excerpt": "verbatim excerpt from decision_text",
                    "labeler_confidence": "number from 0 to 1",
                    "page": "optional positive integer",
                    "paragraph": "optional positive integer",
                    "notes": "optional short rationale",
                }
            ],
            "missing_unit_flags": [
                {
                    "missing_unit_description": "material unit omitted from Stage A",
                    "supporting_excerpt": "verbatim excerpt from decision_text",
                    "page": "optional positive integer",
                    "paragraph": "optional positive integer",
                    "notes": "optional short rationale",
                }
            ],
        },
    }
    return json.dumps(payload, sort_keys=True, indent=2)


def _predecision_documents(
    selection: Mapping[str, Any],
    *,
    parser_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    markdown_root: Path,
) -> tuple[_LlmDocument, ...]:
    candidate_id = _required_str(selection, "candidate_id")
    documents: list[_LlmDocument] = []
    for document in _record_sequence(selection.get("documents"), "documents"):
        role = DocumentRole(_required_str(document, "document_role"))
        if role in {DocumentRole.DECISION, DocumentRole.ORDER}:
            continue
        if _bool(document.get("contains_target_outcome")):
            continue
        if not _bool(document.get("model_visible")):
            continue
        source_document_id = _required_str(document, "source_document_id")
        parser_record = _required_parser_record(
            parser_by_key,
            candidate_id=candidate_id,
            source_document_id=source_document_id,
        )
        documents.append(
            _LlmDocument(
                candidate_id=candidate_id,
                source_document_id=source_document_id,
                document_role=role,
                docket_entry_number=_optional_int(document, "docket_entry_number"),
                description=_optional_str(document, "description") or role.value,
                markdown=_markdown_text(parser_record, markdown_root=markdown_root),
            )
        )
    if not documents:
        raise LlmPipelineError(
            f"no predecision model-visible documents: {candidate_id}"
        )
    return tuple(documents)


def _decision_document(
    selection: Mapping[str, Any],
    *,
    parser_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    markdown_root: Path,
) -> _LlmDocument:
    candidate_id = _required_str(selection, "candidate_id")
    decision_entries = set(_int_tuple(selection.get("decision_entry_numbers")))
    candidates: list[Mapping[str, Any]] = []
    for document in _record_sequence(selection.get("documents"), "documents"):
        role = DocumentRole(_required_str(document, "document_role"))
        if _bool(document.get("contains_target_outcome")) or role in {
            DocumentRole.DECISION,
            DocumentRole.ORDER,
        }:
            candidates.append(document)
    if not candidates:
        raise LlmPipelineError(f"decision document missing for {candidate_id}")
    candidates.sort(
        key=lambda record: (
            _optional_int(record, "docket_entry_number") not in decision_entries,
            _optional_int(record, "docket_entry_number") or 10**9,
        )
    )
    document = candidates[0]
    source_document_id = _required_str(document, "source_document_id")
    parser_record = _required_parser_record(
        parser_by_key,
        candidate_id=candidate_id,
        source_document_id=source_document_id,
    )
    return _LlmDocument(
        candidate_id=candidate_id,
        source_document_id=source_document_id,
        document_role=DocumentRole(_required_str(document, "document_role")),
        docket_entry_number=_optional_int(document, "docket_entry_number"),
        description=_optional_str(document, "description") or "decision",
        markdown=_markdown_text(parser_record, markdown_root=markdown_root),
    )


def _parser_records_by_candidate_and_document(
    records: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        if _optional_str(record, "status") != "succeeded":
            continue
        indexed[
            (
                _required_str(record, "candidate_id"),
                _required_str(record, "source_document_id"),
            )
        ] = record
    return indexed


def _prediction_units_by_candidate(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[PredictionUnit, ...]]:
    grouped: dict[str, list[PredictionUnit]] = defaultdict(list)
    for record in records:
        candidate_id = _required_str(record, "candidate_id")
        if "prediction_units" in record:
            grouped[candidate_id].extend(
                _prediction_unit(unit)
                for unit in _record_sequence(
                    record.get("prediction_units"), "prediction_units"
                )
            )
        else:
            grouped[candidate_id].append(_prediction_unit(record))
    return {candidate_id: tuple(units) for candidate_id, units in grouped.items()}


def _required_parser_record(
    records: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    candidate_id: str,
    source_document_id: str,
) -> Mapping[str, Any]:
    try:
        return records[(candidate_id, source_document_id)]
    except KeyError as exc:
        raise LlmPipelineError(
            f"parser markdown missing for {candidate_id}/{source_document_id}"
        ) from exc


def _markdown_text(record: Mapping[str, Any], *, markdown_root: Path) -> str:
    markdown_path = Path(_required_str(record, "markdown_path"))
    resolved = (
        markdown_path if markdown_path.is_absolute() else markdown_root / markdown_path
    )
    if not resolved.is_file():
        raise LlmPipelineError(f"markdown file missing: {resolved}")
    text = resolved.read_text(encoding="utf-8")
    if not text.strip():
        raise LlmPipelineError(f"markdown file is empty: {resolved}")
    return text


def _stage_a_seed(record: Mapping[str, Any]) -> StageAUnitSeed:
    return StageAUnitSeed(
        count=_required_str(record, "count"),
        claim_name=_required_str(record, "claim_name"),
        defendant_names=_str_tuple(record.get("defendant_names"), "defendant_names"),
        source_document_ids=_str_tuple(
            record.get("source_document_ids"),
            "source_document_ids",
        ),
        challenged_by_motion=_optional_bool(
            record,
            "challenged_by_motion",
            default=True,
        ),
        challenge_scope=ChallengeScope(
            _optional_str(record, "challenge_scope")
            or ChallengeScope.ENTIRE_CLAIM.value
        ),
        unit_confidence=_optional_float(record, "unit_confidence", default=0.8),
        grouping=DefendantGrouping(
            _optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
        ),
        grouping_rationale=_optional_str(record, "grouping_rationale"),
        group_label=_optional_str(record, "group_label"),
        separable_subclaim=_optional_str(record, "separable_subclaim"),
        uncertainty_notes=_optional_str(record, "uncertainty_notes"),
        unit_id=_optional_str(record, "unit_id"),
        citation_page=_optional_int(record, "citation_page"),
        citation_paragraph=_optional_int(record, "citation_paragraph"),
        citation_excerpt=_optional_str(record, "citation_excerpt"),
    )


def _stage_b_finding(
    record: Mapping[str, Any],
    *,
    decision_text: StageBDecisionText,
) -> StageBUnitFinding:
    return StageBUnitFinding(
        unit_id=_required_str(record, "unit_id"),
        resolution=UnitResolution(_required_str(record, "resolution")),
        amendment_signal=AmendmentSignal(_required_str(record, "amendment_signal")),
        supporting_excerpt=_coerced_excerpt(
            decision_text.text,
            _required_str(record, "supporting_excerpt"),
        ),
        labeler_confidence=_required_float(record, "labeler_confidence"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        notes=_optional_str(record, "notes"),
    )


def _stage_b_missing_flag(
    record: Mapping[str, Any],
    *,
    decision_text: StageBDecisionText,
) -> StageBMissingUnitFlag:
    return StageBMissingUnitFlag(
        missing_unit_description=_required_str(record, "missing_unit_description"),
        supporting_excerpt=_coerced_excerpt(
            decision_text.text,
            _required_str(record, "supporting_excerpt"),
        ),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        notes=_optional_str(record, "notes"),
    )


def _selected_labels(
    labels_by_model: Mapping[str, tuple[OutcomeLabel, ...]],
    votes: Sequence[EnsembleLabelVote],
    *,
    consensus_policy: LlmConsensusPolicy,
    first_model_key: str,
) -> tuple[OutcomeLabel, ...]:
    if consensus_policy is LlmConsensusPolicy.FIRST_MODEL:
        return labels_by_model[first_model_key]

    votes_by_unit: dict[str, list[EnsembleLabelVote]] = defaultdict(list)
    for vote in votes:
        votes_by_unit[vote.unit_id].append(vote)

    selected: list[OutcomeLabel] = []
    for unit_id in sorted(votes_by_unit):
        unit_votes = votes_by_unit[unit_id]
        by_signature: dict[tuple[object, ...], list[EnsembleLabelVote]] = defaultdict(
            list
        )
        for vote in unit_votes:
            by_signature[vote.signature].append(vote)
        ranked = sorted(
            by_signature.values(),
            key=lambda group: (len(group), sum(vote.confidence for vote in group)),
            reverse=True,
        )
        if not ranked:
            raise LlmPipelineError(f"no votes for unit {unit_id}")
        best = ranked[0]
        if consensus_policy is LlmConsensusPolicy.UNANIMOUS and len(best) != len(
            unit_votes
        ):
            raise LlmPipelineError(f"LLM judges were not unanimous for {unit_id}")
        if (
            consensus_policy is LlmConsensusPolicy.MAJORITY
            and len(best) <= len(unit_votes) / 2
        ):
            raise LlmPipelineError(f"LLM judges had no majority for {unit_id}")
        selected.append(max(best, key=lambda vote: vote.confidence).label)
    return tuple(selected)


def _prediction_unit(record: Mapping[str, Any]) -> PredictionUnit:
    return PredictionUnit(
        unit_id=_required_str(record, "unit_id"),
        count=_required_str(record, "count"),
        claim_name=_required_str(record, "claim_name"),
        defendant_group=_required_str(record, "defendant_group"),
        challenged_by_motion=_required_bool(record, "challenged_by_motion"),
        challenge_scope=ChallengeScope(_required_str(record, "challenge_scope")),
        unit_confidence=_required_float(record, "unit_confidence"),
        source_citations=tuple(
            _source_citation(citation)
            for citation in _record_sequence(
                record.get("source_citations"), "source_citations"
            )
        ),
        grouping=DefendantGrouping(
            _optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
        ),
        grouping_rationale=_optional_str(record, "grouping_rationale"),
        separable_subclaim=_optional_str(record, "separable_subclaim"),
        uncertainty_notes=_optional_str(record, "uncertainty_notes"),
    )


def _source_citation(record: Mapping[str, Any]) -> SourceCitation:
    return SourceCitation(
        document_id=_required_str(record, "document_id"),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        excerpt=_optional_str(record, "excerpt"),
    )


def _case_prompt_record(selection: Mapping[str, Any]) -> JsonRecord:
    return {
        "candidate_id": _required_str(selection, "candidate_id"),
        "case_id": _required_str(selection, "case_id"),
        "case_name": _optional_str(selection, "case_name"),
        "court": _required_str(selection, "court"),
        "docket_number": _required_str(selection, "docket_number"),
        "target_motion_entry_numbers": list(
            _int_tuple(selection.get("target_motion_entry_numbers"))
        ),
        "decision_entry_numbers": list(
            _int_tuple(selection.get("decision_entry_numbers"))
        ),
    }


def _decision_date(selection: Mapping[str, Any]) -> str:
    value = _optional_str(selection, "decision_date") or _optional_str(
        selection,
        "decision_entered_date",
    )
    if value:
        return value
    entries = _int_tuple(selection.get("decision_entry_numbers"))
    if entries:
        return f"docket-entry-{entries[0]}"
    return "not-recorded"


def _json_object_from_response(
    raw_output: str,
    *,
    top_level_sequence_field: str | None = None,
) -> Mapping[str, Any]:
    text = raw_output.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise LlmPipelineError(
                "LLM response did not contain a JSON object"
            ) from exc
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LlmPipelineError("LLM response JSON object was invalid") from exc
    if (
        top_level_sequence_field is not None
        and isinstance(parsed, Sequence)
        and not isinstance(parsed, str)
    ):
        sequence = cast(Sequence[object], parsed)
        if all(isinstance(item, Mapping) for item in sequence):
            return {
                top_level_sequence_field: [
                    cast(Mapping[str, Any], item) for item in sequence
                ]
            }
    if not isinstance(parsed, Mapping):
        raise LlmPipelineError("LLM response must be a JSON object")
    return cast(Mapping[str, Any], parsed)


def _coerced_excerpt(text: str, excerpt: str) -> str:
    stripped = excerpt.strip()
    if stripped in text:
        return stripped
    normalized_excerpt = " ".join(stripped.split())
    if not normalized_excerpt:
        raise LlmPipelineError("supporting_excerpt is required")
    normalized_chars: list[str] = []
    source_positions: list[int] = []
    in_space = False
    for index, char in enumerate(text):
        if char.isspace():
            if not in_space:
                normalized_chars.append(" ")
                source_positions.append(index)
            in_space = True
        else:
            normalized_chars.append(char)
            source_positions.append(index)
            in_space = False
    normalized_text = "".join(normalized_chars).strip()
    offset = normalized_text.find(normalized_excerpt)
    if offset < 0:
        raise LlmPipelineError("supporting_excerpt does not appear in decision text")
    start = source_positions[offset]
    end_offset = offset + len(normalized_excerpt) - 1
    end = source_positions[min(end_offset, len(source_positions) - 1)] + 1
    return text[start:end].strip()


def _failure_audit_record(
    *,
    stage: str,
    selection: Mapping[str, Any],
    model_key: str,
    error: Exception,
    model_registry_sha256: str | None,
) -> JsonRecord:
    return {
        "stage": stage,
        "status": "failed",
        "candidate_id": _optional_str(selection, "candidate_id"),
        "case_id": _optional_str(selection, "case_id"),
        "model_key": model_key,
        "model_registry_sha256": model_registry_sha256 or "unrecorded",
        "human_verified": False,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "estimated_cost": 0.0,
    }


def _response_audit_fields(response: SolverResponse) -> JsonRecord:
    return {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "estimated_cost": response.estimated_cost,
        "raw_output_sha256": response.raw_output_sha256,
        "metadata": dict(response.metadata or {}),
    }


def _record_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise LlmPipelineError(f"{field_name} must be a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise LlmPipelineError(f"{field_name} must contain objects")
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _optional_record_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    return _record_sequence(value, "missing_unit_flags")


def _str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return (stripped,)
        raise LlmPipelineError(f"{field_name} must contain strings")
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise LlmPipelineError(f"{field_name} must be a list")
    values = tuple(
        item.strip()
        for item in cast(Sequence[object], value)
        if isinstance(item, str) and item.strip()
    )
    if not values:
        raise LlmPipelineError(f"{field_name} must contain strings")
    return values


def _int_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    numbers: list[int] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, int) and not isinstance(item, bool):
            numbers.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            numbers.append(int(item.strip()))
    return tuple(numbers)


def _required_str(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LlmPipelineError(f"{key} is required")
    return value.strip()


def _optional_str(record: Mapping[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_bool(record: Mapping[str, Any], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise LlmPipelineError(f"{key} must be a boolean")
    return value


def _optional_bool(
    record: Mapping[str, Any],
    key: str,
    *,
    default: bool,
) -> bool:
    value = record.get(key)
    return value if isinstance(value, bool) else default


def _bool(value: object) -> bool:
    return value if isinstance(value, bool) else False


def _optional_int(record: Mapping[str, Any], key: str) -> int | None:
    value = record.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _required_float(record: Mapping[str, Any], key: str) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LlmPipelineError(f"{key} must be a number")
    return float(value)


def _optional_float(
    record: Mapping[str, Any],
    key: str,
    *,
    default: float,
) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)
