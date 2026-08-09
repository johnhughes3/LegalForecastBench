"""Registry-backed LLM unitization and outcome-labeling helpers."""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1,
    LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2,
)
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.live_model_solver import (
    DEFAULT_MAX_ATTEMPTS,
    LiveModelTransport,
    complete_live_prompt,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    CompositeProviderAttemptHandler,
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    ProviderSpendAuthority,
    ProviderSpendKey,
)
from legalforecast.ingestion.decision_text_artifact import (
    SCHEMA_VERSION as DECISION_TEXT_SCHEMA_VERSION,
)
from legalforecast.ingestion.decision_text_artifact import (
    VerifiedDecisionTextArtifact,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.ensemble import (
    DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    EnsembleDecisionStatus,
    EnsembleLabelVote,
    EnsembleRouteReason,
    EnsembleRunResult,
    EnsembleUnitDecision,
    audit_ensemble_labels,
    enforce_label_audit_acceptance,
    evaluate_labeling_ensemble,
    sample_unanimous_labels_for_audit,
)
from legalforecast.labeling.label_outcomes import (
    AmendmentClass,
    AmendmentSignal,
    LaterProceduralChange,
    OutcomeCitation,
    OutcomeLabel,
    StageBDecisionText,
    StageBLabelingInput,
    StageBLabelingResult,
    StageBMissingUnitFlag,
    StageBUnitFinding,
    UnitResolution,
    label_stage_b_outcomes,
)
from legalforecast.labeling.lawyer_review import (
    AdjudicatedReview,
    LawyerReviewPacket,
    LawyerReviewResponse,
    ReviewerExpertise,
    ReviewMaterial,
    ReviewMaterialKind,
)
from legalforecast.labeling.provider_journal import (
    DEFAULT_CYCLE_PROVIDER_CAP_USD,
    ExhaustedReconstructionFailureEvidence,
    ProviderAttemptJournal,
    ProviderCallIdentity,
    ProviderJournalError,
    RepeatedReconstructionFailureEvidence,
    maximum_call_cost_usd,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)
from legalforecast.unitization.adjudication import (
    FrozenUnitRepairResult,
    FrozenUnitStatus,
    exclude_for_missing_stage_a_unit,
)
from legalforecast.unitization.construct_units import (
    StageAConstructionInput,
    StageAConstructionResult,
    StageADocumentRole,
    StageASourceDocument,
    StageAUnitSeed,
    UnitizationReviewReason,
    construct_stage_a_units,
)
from legalforecast.unitization.review import (
    canonical_records_sha256,
    canonical_sha256,
    require_finalized_envelopes,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)

JsonRecord = dict[str, Any]
DEFAULT_LABEL_AUDIT_SAMPLE_SIZE = 30
STAGE_A_CLAIM_ONTOLOGY_V2_PROMPT_CONTRACT = "claim-ontology-v2"
STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT = "claim-ontology-v3"
STAGE_A_PROVIDER_ATTEMPT_CONTRACTS = (
    STAGE_A_CLAIM_ONTOLOGY_V2_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
)
_STAGE_A_PROVIDER_ATTEMPT_CONTRACTS = frozenset(STAGE_A_PROVIDER_ATTEMPT_CONTRACTS)


def stage_a_provider_attempt_stage(
    base_stage: str, provider_attempt_namespace: str | None
) -> str:
    """Return the durable provider stage for one versioned Stage A contract.

    An absent namespace preserves the historical logical-call identity exactly.
    A named successor remains in the same cycle-wide journal and under the same
    provider cap, but cannot replay a response produced for a different prompt
    contract.
    """

    if provider_attempt_namespace is None:
        return base_stage
    if provider_attempt_namespace not in _STAGE_A_PROVIDER_ATTEMPT_CONTRACTS:
        raise LlmPipelineError(
            "unknown Stage A provider attempt namespace; expected one of: "
            + ", ".join(sorted(_STAGE_A_PROVIDER_ATTEMPT_CONTRACTS))
        )
    return f"{base_stage}:{provider_attempt_namespace}"


def _reconstruction_retry_max_attempts(
    journal: ProviderAttemptJournal | None,
) -> int:
    """Return the fixed provider-attempt budget after reconstruction failures.

    A settled or merely validated response remains replayable without another
    provider call.  A response that has already failed semantic reconstruction,
    however, is only useful after a code correction; the live labeling stages
    instead consume one of the same bounded provider attempts for a fresh
    response.  The journal records the durable ordinal and preserves the old
    response/accounting evidence.
    """

    if journal is None:
        return DEFAULT_MAX_ATTEMPTS
    return journal.prepare_reconstruction_retry(max_attempts=DEFAULT_MAX_ATTEMPTS)


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


class FrozenUnitWorkflowRequiredError(LlmPipelineError):
    """Raised when Stage B labels expose a missing frozen unit."""

    def __init__(
        self,
        *,
        response: SolverResponse,
        labeling_result: StageBLabelingResult,
        repair_result: FrozenUnitRepairResult,
    ) -> None:
        super().__init__(
            "requires_frozen_unit_workflow: Stage B reported missing_unit_flags; "
            "route through blinded frozen-unit repair or exclusion before scoring"
        )
        self.response = response
        self.labeling_result = labeling_result
        self.repair_result = repair_result


@dataclass(frozen=True, slots=True)
class LlmBatchResult:
    """Records and audit rows produced by one LLM batch stage."""

    records: tuple[JsonRecord, ...]
    audit_records: tuple[JsonRecord, ...]
    terminal_review_queue_records: tuple[JsonRecord, ...] = ()

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
class LlmUnitizationReconstructionRecovery:
    """Provider-free recovery of one exact journaled Stage A response."""

    candidate_id: str
    case_id: str
    attempt_ordinal: int
    raw_response_sha256: str
    normalized_response_sha256: str
    prediction_units: tuple[JsonRecord, ...]
    review_items: tuple[JsonRecord, ...]

    def to_record(self) -> JsonRecord:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "attempt_ordinal": self.attempt_ordinal,
            "raw_response_sha256": self.raw_response_sha256,
            "normalized_response_sha256": self.normalized_response_sha256,
            "prediction_units": list(self.prediction_units),
            "review_items": list(self.review_items),
        }


@dataclass(frozen=True, slots=True)
class LlmStageAStructuralReviewReconstructionRecovery:
    """Provider-free recovery of one exact journaled structural review."""

    candidate_id: str
    case_id: str
    attempt_ordinal: int
    raw_response_sha256: str
    normalized_response_sha256: str
    structural_flags: tuple[JsonRecord, ...]

    def to_record(self) -> JsonRecord:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "attempt_ordinal": self.attempt_ordinal,
            "raw_response_sha256": self.raw_response_sha256,
            "normalized_response_sha256": self.normalized_response_sha256,
            "structural_flags": list(self.structural_flags),
        }


@dataclass(frozen=True, slots=True)
class LlmStageAStructuralReviewTerminalEscalation:
    """Provider-free evidence that routes one invalid reviewer call to John.

    The payload deliberately contains only blinded, predecision material plus
    commitments to the two invalid provider responses.  It never turns either
    response into an accepted structural flag.
    """

    candidate_id: str
    case_id: str
    reviewer_model_key: str
    model_registry_sha256: str
    raw_prediction_units_sha256: str
    prompt: str
    prompt_sha256: str
    frozen_units: tuple[JsonRecord, ...]
    predecision_source_commitments: tuple[JsonRecord, ...]
    failed_attempts: tuple[JsonRecord, ...]
    provider_attempt_namespace: str | None = None
    schema_version: str = str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1)

    def to_record(self) -> JsonRecord:
        if self.schema_version not in {
            str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1),
            str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2),
        }:
            raise LlmPipelineError("Stage A terminal escalation schema is invalid")
        record: JsonRecord = {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "reviewer_model_key": self.reviewer_model_key,
            "model_registry_sha256": self.model_registry_sha256,
            "raw_prediction_units_sha256": self.raw_prediction_units_sha256,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
            "frozen_units": [dict(unit) for unit in self.frozen_units],
            "predecision_source_commitments": [
                dict(commitment) for commitment in self.predecision_source_commitments
            ],
            "failed_attempts": [dict(attempt) for attempt in self.failed_attempts],
        }
        if self.provider_attempt_namespace is not None:
            record["provider_attempt_namespace"] = self.provider_attempt_namespace
        return record

    @property
    def escalation_sha256(self) -> str:
        """Return the canonical identity used in immutable John queue rows."""

        return canonical_sha256(self.to_record())


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
    markdown_bytes: Mapping[str, bytes] | None = None,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str | None = None,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = 120.0,
    continue_on_error: bool = False,
    provider_journal_path: str | Path | None = None,
    provider_cycle_cap_usd: float = DEFAULT_CYCLE_PROVIDER_CAP_USD,
    provider_cycle_caps_usd: Mapping[str, float] | None = None,
    provider_cycle_id: str | None = None,
    provider_cycle_caps_sha256: str | None = None,
    provider_spend_authorities: Mapping[str, ProviderSpendAuthority] | None = None,
    provider_accounts: Mapping[str, str] | None = None,
    provider_attempt_namespace: str | None = None,
) -> LlmBatchResult:
    """Generate and validate Stage A prediction units from predecision materials."""

    provider_stage = stage_a_provider_attempt_stage(
        "llm-unitize", provider_attempt_namespace
    )
    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    records: list[JsonRecord] = []
    audit_records: list[JsonRecord] = []
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        response: SolverResponse | None = None
        journal: ProviderAttemptJournal | None = None
        try:
            documents = _predecision_documents(
                selection,
                parser_by_key=parser_by_key,
                markdown_root=Path(markdown_root),
                markdown_bytes=markdown_bytes,
            )
            prompt = _unitization_prompt(selection, documents)
            prompt_sha256 = (
                "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            )
            journal = _provider_attempt_journal(
                path=provider_journal_path,
                stage="llm-unitize",
                candidate_id=candidate_id,
                prompt=prompt,
                registry_entry=registry_entry,
                account=(provider_accounts or {}).get(
                    registry_entry.provider.lower(), "default"
                ),
                model_registry_sha256=model_registry_sha256,
                cycle_cap_usd=_provider_cycle_cap(
                    registry_entry.provider,
                    fallback=provider_cycle_cap_usd,
                    caps=provider_cycle_caps_usd,
                ),
                cycle_id=provider_cycle_id,
                provider_cycle_caps_sha256=provider_cycle_caps_sha256,
                provider_attempt_namespace=provider_attempt_namespace,
            )
            _require_successor_or_completed_legacy_attempt(
                journal,
                provider_attempt_namespace=provider_attempt_namespace,
                stage="unitization",
            )
            max_attempts = _reconstruction_retry_max_attempts(journal)
            response = complete_live_prompt(
                registry_entry,
                prompt,
                model_registry_sha256=model_registry_sha256,
                transport=transport,
                environ=environ,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                attempt_handler=_combined_attempt_handler(
                    journal=journal,
                    authorities=provider_spend_authorities,
                    accounts=provider_accounts,
                    cycle_id=provider_cycle_id,
                    stage=provider_stage,
                    candidate_id=candidate_id,
                    registry_entry=registry_entry,
                ),
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
            if not any(unit.should_score for unit in result.units) and (
                not result.review_items
                or any(
                    unit.challenge_scope is not ChallengeScope.UNCLEAR
                    for unit in result.units
                )
            ):
                raise LlmPipelineError("LLM unitization produced no scorable units")
            if journal is not None and journal.has_validated_response:
                journal.commit_reconstruction(
                    {
                        "prediction_units": [unit.to_record() for unit in result.units],
                        "review_items": [
                            item.to_record() for item in result.review_items
                        ],
                    }
                )
            if journal is not None:
                journal.close()
                journal = None
            review_queue = _unitization_review_queue_records(
                candidate_id=candidate_id,
                case_id=_required_str(selection, "case_id"),
                result=result,
            )
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
                    "status": ("adjudication_pending" if review_queue else "succeeded"),
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "model_key": registry_entry.registry_key,
                    "model_registry_sha256": model_registry_sha256 or "unrecorded",
                    "provider_prompt_sha256": prompt_sha256,
                    "human_verified": _unitization_human_verified(result),
                    "unit_count": len(result.units),
                    "scorable_unit_count": sum(
                        unit.should_score for unit in result.units
                    ),
                    "review_items": [item.to_record() for item in result.review_items],
                    "unitization_review_queue": review_queue,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "estimated_cost": response.estimated_cost,
                    "raw_output_sha256": response.raw_output_sha256,
                    "metadata": dict(response.metadata or {}),
                }
            )
        except Exception as exc:
            if journal is not None:
                if journal.has_validated_response:
                    journal.record_reconstruction_failure(exc)
                journal.close()
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


def stage_a_unitization_prompt_records(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    markdown_bytes: Mapping[str, bytes] | None = None,
) -> tuple[JsonRecord, ...]:
    """Reconstruct exact Stage A prompts from authenticated parser inputs."""

    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    prompts: list[JsonRecord] = []
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        prompt = _unitization_prompt(
            selection,
            _predecision_documents(
                selection,
                parser_by_key=parser_by_key,
                markdown_root=Path(markdown_root),
                markdown_bytes=markdown_bytes,
            ),
        )
        prompts.append(
            {
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "prompt": prompt,
                "prompt_sha256": "sha256:"
                + hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            }
        )
    return tuple(prompts)


def recover_llm_unitization_reconstruction(
    *,
    selection_record: Mapping[str, Any],
    parser_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    markdown_bytes: Mapping[str, bytes] | None,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_journal_path: str | Path,
    provider_cycle_cap_usd: float,
    provider_cycle_id: str,
    provider_cycle_caps_sha256: str,
    provider_account: str,
    provider_attempt_namespace: str | None = None,
) -> LlmUnitizationReconstructionRecovery:
    """Revalidate and settle the latest failed Stage A response without a call."""

    candidate_id = _required_str(selection_record, "candidate_id")
    case_id = _required_str(selection_record, "case_id")
    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    documents = _predecision_documents(
        selection_record,
        parser_by_key=parser_by_key,
        markdown_root=Path(markdown_root),
        markdown_bytes=markdown_bytes,
    )
    prompt = _unitization_prompt(selection_record, documents)
    journal = _provider_attempt_journal(
        path=provider_journal_path,
        stage="llm-unitize",
        candidate_id=candidate_id,
        prompt=prompt,
        registry_entry=registry_entry,
        account=provider_account,
        model_registry_sha256=model_registry_sha256,
        cycle_cap_usd=provider_cycle_cap_usd,
        cycle_id=provider_cycle_id,
        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    if journal is None:
        raise LlmPipelineError("provider reconstruction recovery requires a journal")
    try:
        evidence = journal.latest_reconstruction_recovery_evidence()
        try:
            normalized_value: object = json.loads(evidence.normalized_response_json)
        except json.JSONDecodeError as exc:
            raise LlmPipelineError(
                "journaled normalized provider response is invalid"
            ) from exc
        if not isinstance(normalized_value, Mapping):
            raise LlmPipelineError(
                "journaled normalized provider response must be an object"
            )
        raw_output = cast(Mapping[str, object], normalized_value).get("raw_output")
        if not isinstance(raw_output, str):
            raise LlmPipelineError(
                "journaled normalized provider response lacks raw_output"
            )
        payload = _json_object_from_response(
            raw_output,
            top_level_sequence_field="unit_seeds",
        )
        result = construct_stage_a_units(
            StageAConstructionInput(
                candidate_id=candidate_id,
                case_id=case_id,
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
        if not any(unit.should_score for unit in result.units) and (
            not result.review_items
            or any(
                unit.challenge_scope is not ChallengeScope.UNCLEAR
                for unit in result.units
            )
        ):
            raise LlmPipelineError("LLM unitization produced no scorable units")
        prediction_units = tuple(unit.to_record() for unit in result.units)
        review_items = tuple(item.to_record() for item in result.review_items)
        journal.commit_reconstruction_recovery(
            evidence.attempt_ordinal,
            raw_response_json=evidence.raw_response_json,
            normalized_response_json=evidence.normalized_response_json,
            record={
                "prediction_units": list(prediction_units),
                "review_items": list(review_items),
            },
        )
        return LlmUnitizationReconstructionRecovery(
            candidate_id=candidate_id,
            case_id=case_id,
            attempt_ordinal=evidence.attempt_ordinal,
            raw_response_sha256="sha256:"
            + hashlib.sha256(evidence.raw_response_json.encode()).hexdigest(),
            normalized_response_sha256="sha256:"
            + hashlib.sha256(evidence.normalized_response_json.encode()).hexdigest(),
            prediction_units=prediction_units,
            review_items=review_items,
        )
    finally:
        journal.close()


def recover_llm_stage_a_structural_review_reconstruction(
    *,
    selection_record: Mapping[str, Any],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    markdown_bytes: Mapping[str, bytes] | None,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_journal_path: str | Path,
    provider_cycle_cap_usd: float,
    provider_cycle_id: str,
    provider_cycle_caps_sha256: str,
    provider_account: str,
    provider_attempt_namespace: str | None = None,
) -> LlmStageAStructuralReviewReconstructionRecovery:
    """Revalidate and settle one failed structural-review response without a call."""

    candidate_id = _required_str(selection_record, "candidate_id")
    case_id = _required_str(selection_record, "case_id")
    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    documents = _predecision_documents(
        selection_record,
        parser_by_key=parser_by_key,
        markdown_root=Path(markdown_root),
        markdown_bytes=markdown_bytes,
    )
    units = _prediction_units_by_candidate(prediction_unit_records).get(
        candidate_id, ()
    )
    if not units:
        raise LlmPipelineError(f"no Stage A units for candidate {candidate_id}")
    prompt = _stage_a_structural_review_prompt(
        selection_record,
        documents,
        units,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    journal = _provider_attempt_journal(
        path=provider_journal_path,
        stage="llm-review-stage-a",
        candidate_id=candidate_id,
        prompt=prompt,
        registry_entry=registry_entry,
        account=provider_account,
        model_registry_sha256=model_registry_sha256,
        cycle_cap_usd=provider_cycle_cap_usd,
        cycle_id=provider_cycle_id,
        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    if journal is None:
        raise LlmPipelineError("provider reconstruction recovery requires a journal")
    try:
        evidence = journal.latest_reconstruction_recovery_evidence()
        try:
            normalized_value: object = json.loads(evidence.normalized_response_json)
        except json.JSONDecodeError as exc:
            raise LlmPipelineError(
                "journaled normalized provider response is invalid"
            ) from exc
        if not isinstance(normalized_value, Mapping):
            raise LlmPipelineError(
                "journaled normalized provider response must be an object"
            )
        normalized = cast(Mapping[str, object], normalized_value)
        raw_output = normalized.get("raw_output")
        if not isinstance(raw_output, str):
            raise LlmPipelineError(
                "journaled normalized provider response lacks raw_output"
            )
        payload = _json_object_from_response(raw_output)
        response = SolverResponse(
            raw_output=raw_output,
            request_count=_optional_int(normalized, "request_count") or 1,
            input_tokens=_optional_int(normalized, "input_tokens") or 0,
            output_tokens=_optional_int(normalized, "output_tokens") or 0,
            estimated_cost=_float(normalized.get("actual_cost_usd")),
        )
        flags = validate_structural_review_flags(
            payload, units=units, documents=documents, response=response
        )
        journal.commit_reconstruction_recovery(
            evidence.attempt_ordinal,
            raw_response_json=evidence.raw_response_json,
            normalized_response_json=evidence.normalized_response_json,
            record={"structural_flags": list(flags)},
        )
        return LlmStageAStructuralReviewReconstructionRecovery(
            candidate_id=candidate_id,
            case_id=case_id,
            attempt_ordinal=evidence.attempt_ordinal,
            raw_response_sha256="sha256:"
            + hashlib.sha256(evidence.raw_response_json.encode()).hexdigest(),
            normalized_response_sha256="sha256:"
            + hashlib.sha256(evidence.normalized_response_json.encode()).hexdigest(),
            structural_flags=flags,
        )
    finally:
        journal.close()


def build_llm_stage_a_structural_review_terminal_escalation(
    *,
    selection_record: Mapping[str, Any],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    markdown_bytes: Mapping[str, bytes] | None,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_journal_path: str | Path,
    provider_cycle_cap_usd: float,
    provider_cycle_id: str,
    provider_cycle_caps_sha256: str,
    provider_account: str,
    provider_attempt_namespace: str | None = None,
) -> LlmStageAStructuralReviewTerminalEscalation:
    """Build one narrow, provider-free escalation from durable failures.

    Ordinary structural-review retries remain the default.  The early receipt
    is available after exactly two byte-identical failed reconstructions.  A
    separately versioned receipt is available only after all three normal
    reconstruction attempts have failed; it binds each attempt's own validator
    evidence and still accepts no structural flag.
    """

    candidate_id = _required_str(selection_record, "candidate_id")
    case_id = _required_str(selection_record, "case_id")
    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    documents = _predecision_documents(
        selection_record,
        parser_by_key=parser_by_key,
        markdown_root=Path(markdown_root),
        markdown_bytes=markdown_bytes,
    )
    raw_records = tuple(prediction_unit_records)
    raw_by_candidate = {
        _required_str(record, "candidate_id"): record for record in raw_records
    }
    if len(raw_by_candidate) != len(raw_records):
        raise LlmPipelineError("duplicate raw Stage A candidate records")
    raw_record = raw_by_candidate.get(candidate_id)
    if raw_record is None:
        raise LlmPipelineError(f"no raw Stage A unit record for {candidate_id}")
    units = _prediction_units_by_candidate(raw_records).get(candidate_id, ())
    if not units:
        raise LlmPipelineError(f"no Stage A units for candidate {candidate_id}")
    prompt = _stage_a_structural_review_prompt(
        selection_record,
        documents,
        units,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    journal = _provider_attempt_journal(
        path=provider_journal_path,
        stage="llm-review-stage-a",
        candidate_id=candidate_id,
        prompt=prompt,
        registry_entry=registry_entry,
        account=provider_account,
        model_registry_sha256=model_registry_sha256,
        cycle_cap_usd=provider_cycle_cap_usd,
        cycle_id=provider_cycle_id,
        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    if journal is None:
        raise LlmPipelineError("provider terminal escalation requires a journal")
    with journal:
        try:
            evidence: (
                RepeatedReconstructionFailureEvidence
                | ExhaustedReconstructionFailureEvidence
            ) = journal.repeated_identical_reconstruction_failure_evidence()
        except ProviderJournalError:
            evidence = journal.exhausted_reconstruction_failure_evidence()
    source_commitments: list[JsonRecord] = []
    for document in documents:
        source_commitments.append(
            {
                "source_document_id": document.source_document_id,
                "document_role": document.document_role.value,
                "docket_entry_number": document.docket_entry_number,
                "description": document.description,
                "markdown_sha256": "sha256:"
                + hashlib.sha256(document.markdown.encode("utf-8")).hexdigest(),
            }
        )
    if isinstance(evidence, RepeatedReconstructionFailureEvidence):
        schema_version = str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1)
        failure_types = (evidence.failure_type,) * len(evidence.attempts)
        failure_messages = (evidence.failure_message,) * len(evidence.attempts)
    else:
        schema_version = str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2)
        failure_types = evidence.failure_types
        failure_messages = evidence.failure_messages
    failed_attempts = tuple(
        {
            "attempt_ordinal": attempt.attempt_ordinal,
            "raw_response_sha256": "sha256:"
            + hashlib.sha256(attempt.raw_response_json.encode("utf-8")).hexdigest(),
            "normalized_response_sha256": "sha256:"
            + hashlib.sha256(
                attempt.normalized_response_json.encode("utf-8")
            ).hexdigest(),
            "failure_type": failure_type,
            "failure_message": failure_message,
        }
        for attempt, failure_type, failure_message in zip(
            evidence.attempts, failure_types, failure_messages, strict=True
        )
    )
    return LlmStageAStructuralReviewTerminalEscalation(
        candidate_id=candidate_id,
        case_id=case_id,
        reviewer_model_key=registry_entry.registry_key,
        model_registry_sha256=model_registry_sha256,
        raw_prediction_units_sha256=canonical_sha256(raw_record),
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        frozen_units=tuple(unit.to_record() for unit in units),
        predecision_source_commitments=tuple(source_commitments),
        failed_attempts=failed_attempts,
        provider_attempt_namespace=provider_attempt_namespace,
        schema_version=schema_version,
    )


def structural_review_terminal_escalation_queue_records(
    escalation: LlmStageAStructuralReviewTerminalEscalation,
    *,
    receipt_commitment: Mapping[str, Any] | None = None,
) -> tuple[JsonRecord, ...]:
    """Route every affected frozen unit to John without accepting a flag."""

    receipt = dict(receipt_commitment or {})
    if receipt and set(receipt) != {"path", "sha256"}:
        raise LlmPipelineError("terminal escalation receipt commitment is invalid")
    if escalation.schema_version not in {
        str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1),
        str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2),
    }:
        raise LlmPipelineError("Stage A terminal escalation schema is invalid")
    route_reason = "structural_reviewer_terminal_reconstruction_failure"
    notes = (
        "Two byte-identical normalized structural-review responses failed local "
        "reconstruction. No structural flag was accepted; review this frozen unit "
        "using only the blinded predecision materials below."
        if escalation.schema_version
        == str(LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1)
        else (
            "The structural reviewer exhausted all three reconstruction attempts. "
            "No structural flag was accepted; review this frozen unit using only "
            "the blinded predecision materials below."
        )
    )
    return tuple(
        {
            "schema_version": "legalforecast.unitization_review_queue.v1",
            "status": "pending_adjudication",
            "candidate_id": escalation.candidate_id,
            "case_id": escalation.case_id,
            "unit_id": _required_str(unit, "unit_id"),
            "review_id": (
                f"{escalation.candidate_id}:{_required_str(unit, 'unit_id')}:"
                f"structural-terminal:{escalation.escalation_sha256[:16]}"
            ),
            "route_reason": route_reason,
            "review_item": {
                "unit_id": _required_str(unit, "unit_id"),
                "reason": route_reason,
                "notes": notes,
                "frozen_unit": dict(unit),
                "reviewer_prompt": escalation.prompt,
                "reviewer_prompt_sha256": escalation.prompt_sha256,
                "predecision_source_commitments": [
                    dict(commitment)
                    for commitment in escalation.predecision_source_commitments
                ],
                "failed_attempts": [
                    dict(attempt) for attempt in escalation.failed_attempts
                ],
            },
            "terminal_escalation_sha256": escalation.escalation_sha256,
            "raw_prediction_units_sha256": escalation.raw_prediction_units_sha256,
            "reviewer_model_key": escalation.reviewer_model_key,
            "model_registry_sha256": escalation.model_registry_sha256,
            **({"terminal_escalation_receipt": receipt} if receipt else {}),
        }
        for unit in escalation.frozen_units
    )


def structural_review_terminal_escalation_audit_record(
    escalation: LlmStageAStructuralReviewTerminalEscalation,
    *,
    receipt_commitment: Mapping[str, Any],
) -> JsonRecord:
    """Build the replayable no-provider audit row for a terminal escalation."""

    receipt = dict(receipt_commitment)
    if set(receipt) != {"path", "sha256"}:
        raise LlmPipelineError("terminal escalation receipt commitment is invalid")
    return {
        "stage": "llm-review-stage-a",
        "status": "terminal_escalation",
        "candidate_id": escalation.candidate_id,
        "case_id": escalation.case_id,
        "model_key": escalation.reviewer_model_key,
        "model_registry_sha256": escalation.model_registry_sha256,
        "raw_prediction_units_sha256": escalation.raw_prediction_units_sha256,
        "prompt_sha256": escalation.prompt_sha256,
        "structural_flags_sha256": canonical_records_sha256(()),
        "flag_count": 0,
        "terminal_escalation": escalation.to_record(),
        "terminal_escalation_sha256": escalation.escalation_sha256,
        "terminal_escalation_receipt": receipt,
    }


def llm_review_stage_a_units(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str | None = None,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = 120.0,
    provider_journal_path: str | Path | None = None,
    provider_cycle_cap_usd: float = DEFAULT_CYCLE_PROVIDER_CAP_USD,
    provider_cycle_caps_usd: Mapping[str, float] | None = None,
    provider_cycle_id: str | None = None,
    provider_cycle_caps_sha256: str | None = None,
    provider_spend_authorities: Mapping[str, ProviderSpendAuthority] | None = None,
    provider_accounts: Mapping[str, str] | None = None,
    terminal_escalations: Mapping[
        str,
        tuple[LlmStageAStructuralReviewTerminalEscalation, Mapping[str, Any]],
    ]
    | None = None,
    provider_attempt_namespace: str | None = None,
) -> LlmBatchResult:
    """Flag structural defects without permitting the reviewer to rewrite Stage A."""

    provider_stage = stage_a_provider_attempt_stage(
        "llm-review-stage-a", provider_attempt_namespace
    )
    selections = tuple(selection_records)
    parser_rows = tuple(parser_records)
    parser_by_key = _parser_records_by_candidate_and_document(parser_rows)
    raw_unit_records = tuple(prediction_unit_records)
    units_by_candidate = _prediction_units_by_candidate(raw_unit_records)
    prompt_by_candidate = {
        _required_str(record, "candidate_id"): _required_str(record, "prompt")
        for record in stage_a_structural_review_prompt_records(
            selection_records=selections,
            parser_records=parser_rows,
            prediction_unit_records=raw_unit_records,
            markdown_root=markdown_root,
            provider_attempt_namespace=provider_attempt_namespace,
        )
    }
    records: list[JsonRecord] = []
    audits: list[JsonRecord] = []
    terminal_queue_records: list[JsonRecord] = []
    terminal_by_candidate = dict(terminal_escalations or {})
    if not set(terminal_by_candidate) <= {
        _required_str(selection, "candidate_id") for selection in selections
    }:
        raise LlmPipelineError("terminal escalation contains an unselected candidate")
    for selection in selections:
        candidate_id = _required_str(selection, "candidate_id")
        documents = _predecision_documents(
            selection,
            parser_by_key=parser_by_key,
            markdown_root=Path(markdown_root),
        )
        units = units_by_candidate.get(candidate_id, ())
        if not units:
            raise LlmPipelineError(f"no Stage A units for candidate {candidate_id}")
        prompt = prompt_by_candidate[candidate_id]
        raw_record = next(
            record
            for record in raw_unit_records
            if _required_str(record, "candidate_id") == candidate_id
        )
        raw_sha = canonical_sha256(raw_record)
        terminal = terminal_by_candidate.get(candidate_id)
        if terminal is not None:
            escalation, receipt_commitment = terminal
            expected_sources = tuple(
                {
                    "source_document_id": document.source_document_id,
                    "document_role": document.document_role.value,
                    "docket_entry_number": document.docket_entry_number,
                    "description": document.description,
                    "markdown_sha256": "sha256:"
                    + hashlib.sha256(document.markdown.encode("utf-8")).hexdigest(),
                }
                for document in documents
            )
            if (
                escalation.candidate_id != candidate_id
                or escalation.case_id != _required_str(selection, "case_id")
                or escalation.reviewer_model_key != registry_entry.registry_key
                or escalation.model_registry_sha256
                != (model_registry_sha256 or "unrecorded")
                or escalation.raw_prediction_units_sha256 != raw_sha
                or escalation.prompt != prompt
                or escalation.prompt_sha256
                != hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                or escalation.provider_attempt_namespace != provider_attempt_namespace
                or escalation.frozen_units != tuple(unit.to_record() for unit in units)
                or escalation.predecision_source_commitments != expected_sources
            ):
                raise LlmPipelineError(
                    "terminal escalation does not match Stage A input"
                )
            terminal_queue_records.extend(
                structural_review_terminal_escalation_queue_records(
                    escalation,
                    receipt_commitment=receipt_commitment,
                )
            )
            audits.append(
                structural_review_terminal_escalation_audit_record(
                    escalation,
                    receipt_commitment=receipt_commitment,
                )
            )
            continue
        journal = _provider_attempt_journal(
            path=provider_journal_path,
            stage="llm-review-stage-a",
            candidate_id=candidate_id,
            prompt=prompt,
            registry_entry=registry_entry,
            account=(provider_accounts or {}).get(
                registry_entry.provider.lower(), "default"
            ),
            model_registry_sha256=model_registry_sha256,
            cycle_cap_usd=_provider_cycle_cap(
                registry_entry.provider,
                fallback=provider_cycle_cap_usd,
                caps=provider_cycle_caps_usd,
            ),
            cycle_id=provider_cycle_id,
            provider_cycle_caps_sha256=provider_cycle_caps_sha256,
            provider_attempt_namespace=provider_attempt_namespace,
        )
        try:
            _require_successor_or_completed_legacy_attempt(
                journal,
                provider_attempt_namespace=provider_attempt_namespace,
                stage="structural review",
            )
            max_attempts = _reconstruction_retry_max_attempts(journal)
            response_json_schema = (
                _stage_a_structural_review_response_json_schema(documents, units)
                if (
                    provider_attempt_namespace
                    == STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT
                    and registry_entry.provider.strip().lower() in {"google", "gemini"}
                )
                else None
            )
            response = complete_live_prompt(
                registry_entry,
                prompt,
                model_registry_sha256=model_registry_sha256,
                transport=transport,
                environ=environ,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                response_json_schema=response_json_schema,
                attempt_handler=_combined_attempt_handler(
                    journal=journal,
                    authorities=provider_spend_authorities,
                    accounts=provider_accounts,
                    cycle_id=provider_cycle_id,
                    stage=provider_stage,
                    candidate_id=candidate_id,
                    registry_entry=registry_entry,
                ),
            )
            payload = _json_object_from_response(response.raw_output)
            flags = validate_structural_review_flags(
                payload, units=units, documents=documents, response=response
            )
            if journal is not None and journal.has_validated_response:
                journal.commit_reconstruction({"structural_flags": list(flags)})
        except Exception as exc:
            if journal is not None and journal.has_validated_response:
                journal.record_reconstruction_failure(exc)
            raise
        finally:
            if journal is not None:
                journal.close()
        candidate_flag_records = list(
            stage_a_structural_flag_records(
                candidate_id=candidate_id,
                case_id=_required_str(selection, "case_id"),
                reviewer_model_key=registry_entry.registry_key,
                model_registry_sha256=model_registry_sha256 or "unrecorded",
                raw_prediction_units_sha256=raw_sha,
                structural_flags=flags,
            )
        )
        records.extend(candidate_flag_records)
        response_metadata = dict(response.metadata or {})
        audits.append(
            {
                "stage": "llm-review-stage-a",
                "status": "flags_pending" if flags else "passed",
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "model_key": registry_entry.registry_key,
                "model_registry_sha256": model_registry_sha256 or "unrecorded",
                "served_model_version": response_metadata.get("served_model_version"),
                "raw_prediction_units_sha256": raw_sha,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "structural_flags_sha256": canonical_records_sha256(
                    candidate_flag_records
                ),
                "flag_count": len(flags),
                **_response_audit_fields(response),
            }
        )
    return LlmBatchResult(
        records=tuple(records),
        audit_records=tuple(audits),
        terminal_review_queue_records=tuple(terminal_queue_records),
    )


def stage_a_structural_review_prompt_records(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    parser_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    markdown_root: str | Path,
    provider_attempt_namespace: str | None = None,
) -> tuple[JsonRecord, ...]:
    """Reconstruct exact structural-review prompts from authenticated Stage A."""

    parser_by_key = _parser_records_by_candidate_and_document(parser_records)
    units_by_candidate = _prediction_units_by_candidate(prediction_unit_records)
    output: list[JsonRecord] = []
    for selection in selection_records:
        candidate_id = _required_str(selection, "candidate_id")
        units = units_by_candidate.get(candidate_id, ())
        if not units:
            raise LlmPipelineError(f"no Stage A units for candidate {candidate_id}")
        documents = _predecision_documents(
            selection,
            parser_by_key=parser_by_key,
            markdown_root=Path(markdown_root),
        )
        prompt = _stage_a_structural_review_prompt(
            selection,
            documents,
            units,
            provider_attempt_namespace=provider_attempt_namespace,
        )
        output.append(
            {
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            }
        )
    return tuple(output)


def stage_a_structural_flag_records(
    *,
    candidate_id: str,
    case_id: str,
    reviewer_model_key: str,
    model_registry_sha256: str,
    raw_prediction_units_sha256: str,
    structural_flags: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Envelope reconstructed flags exactly as the live producer does."""

    output: list[JsonRecord] = []
    for flag in structural_flags:
        flag_record = dict(flag)
        output.append(
            {
                "schema_version": "legalforecast.stage_a_structural_flag.v1",
                "candidate_id": candidate_id,
                "case_id": case_id,
                "reviewer_model_key": reviewer_model_key,
                "model_registry_sha256": model_registry_sha256,
                "raw_prediction_units_sha256": raw_prediction_units_sha256,
                "flag_sha256": canonical_sha256(flag_record),
                **flag_record,
            }
        )
    return tuple(output)


def merge_structural_flags_into_review_queue(
    queue_records: Iterable[Mapping[str, Any]],
    flag_records: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Union reviewer flags into the immutable John review queue."""

    merged = [dict(record) for record in queue_records]
    existing_ids = {_required_str(record, "review_id") for record in merged}
    ordered_flags = sorted(
        (dict(flag) for flag in flag_records),
        key=lambda flag: (
            _required_str(flag, "candidate_id"),
            _str_tuple(flag.get("affected_unit_ids"), "affected_unit_ids"),
            _required_str(flag, "flag_sha256"),
        ),
    )
    for flag in ordered_flags:
        for unit_id in _str_tuple(flag.get("affected_unit_ids"), "affected_unit_ids"):
            review_id = (
                f"{_required_str(flag, 'candidate_id')}:{unit_id}:structural:"
                f"{_required_str(flag, 'flag_sha256')[:16]}"
            )
            if review_id in existing_ids:
                continue
            merged.append(
                {
                    "schema_version": "legalforecast.unitization_review_queue.v1",
                    "status": "pending_adjudication",
                    "candidate_id": _required_str(flag, "candidate_id"),
                    "case_id": _required_str(flag, "case_id"),
                    "unit_id": unit_id,
                    "review_id": review_id,
                    "route_reason": f"structural_{_required_str(flag, 'flag_type')}",
                    "review_item": {
                        "unit_id": unit_id,
                        "reason": f"structural_{_required_str(flag, 'flag_type')}",
                        "notes": _required_str(flag, "explanation"),
                        "citation_excerpt": _required_str(flag, "citation_excerpt"),
                        "source_document_ids": list(
                            _str_tuple(
                                flag.get("source_document_ids"), "source_document_ids"
                            )
                        ),
                    },
                    "structural_flag_sha256": _required_str(flag, "flag_sha256"),
                    "raw_prediction_units_sha256": _required_str(
                        flag, "raw_prediction_units_sha256"
                    ),
                    "reviewer_model_key": _required_str(flag, "reviewer_model_key"),
                    "model_registry_sha256": _required_str(
                        flag, "model_registry_sha256"
                    ),
                }
            )
            existing_ids.add(review_id)
    return tuple(merged)


def merge_stage_a_review_queue(
    queue_records: Iterable[Mapping[str, Any]],
    flag_records: Iterable[Mapping[str, Any]],
    terminal_queue_records: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Union ordinary flags and terminal evidence into one consumable queue row/unit."""

    merged = list(merge_structural_flags_into_review_queue(queue_records, flag_records))
    existing_by_id = {
        _required_str(record, "review_id"): dict(record) for record in merged
    }
    review_indexes_by_unit: dict[tuple[str, str], list[int]] = {}
    for index, record in enumerate(merged):
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "unit_id"),
        )
        review_indexes_by_unit.setdefault(key, []).append(index)
    for terminal_record in terminal_queue_records:
        record = dict(terminal_record)
        review_id = _required_str(record, "review_id")
        existing = existing_by_id.get(review_id)
        if existing is not None:
            if existing != record:
                raise LlmPipelineError("terminal escalation review queue conflict")
            continue
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "unit_id"),
        )
        matching_indexes = review_indexes_by_unit.get(key, [])
        if len(matching_indexes) > 1:
            raise LlmPipelineError(
                "terminal escalation cannot coalesce ambiguous unit reviews"
            )
        if matching_indexes:
            index = matching_indexes[0]
            existing_review = dict(merged[index])
            existing_terminal = existing_review.get("terminal_escalation")
            if existing_terminal is not None and existing_terminal != record:
                raise LlmPipelineError("terminal escalation review queue conflict")
            existing_review["terminal_escalation"] = record
            merged[index] = existing_review
            existing_by_id[_required_str(existing_review, "review_id")] = (
                existing_review
            )
            continue
        merged.append(record)
        existing_by_id[review_id] = record
        review_indexes_by_unit.setdefault(key, []).append(len(merged) - 1)
    return tuple(merged)


def _stage_a_structural_review_prompt(
    selection: Mapping[str, Any],
    documents: Sequence[_LlmDocument],
    units: Sequence[PredictionUnit],
    *,
    provider_attempt_namespace: str | None = None,
) -> str:
    rules = [
        "Use only supplied predecision documents; never infer from a disposition.",
        (
            "The Sonnet-authored units are immutable. Do not return replacements "
            "or edits."
        ),
        (
            "Return a flag only for an omitted, improperly combined, improperly "
            "split, or spurious unit. A spurious unit is not an asserted legal "
            "right and should be removed."
        ),
        (
            "As non-authoritative reasoning, first reconstruct an internal "
            "complaint claim-defendant ledger and motion-scope matrix: identify "
            "each asserted legal right, the actual moving defendant and capacity, "
            "and whether the target motion challenges all or only a portion of "
            "that right."
        ),
        (
            "A dismissal ground, defense, procedural predicate, claim element, "
            "factual theory, requested remedy, or generic declaratory relief is "
            "never itself a prediction unit. Examples include limitations, "
            "standing, exhaustion, immunity, service, personal jurisdiction, "
            "venue, arbitration, preemption, Section 230, SLUSA, and release."
        ),
        (
            "Apply the independent-disposition test: split only when one "
            "proposition could be dismissed while another survives as an "
            "independently enforceable legal right against the same defendant. "
            "A nonseparable theory remains one claim-level unit."
        ),
        (
            "Flag units that name a ground, element, remedy, theory, or nonmoving "
            "defendant as though it were a scored claim as spurious."
        ),
        (
            "Every flag must cite one or more existing affected unit_ids so a "
            "lawyer can adjudicate it."
        ),
    ]
    if provider_attempt_namespace == STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT:
        rules.append(
            "citation_excerpt must be one contiguous literal span copied from one "
            "cited supplied predecision document. Never use an ellipsis. Never join "
            "fragments. Never paraphrase or normalize case or punctuation."
        )
    rules.append("Return only JSON with a structural_flags array.")
    payload = {
        "task": "Review frozen Stage A units for structural completeness only.",
        "rules": rules,
        "output_schema": {
            "structural_flags": [
                {
                    "flag_type": ["omitted", "combined", "mis_split", "spurious"],
                    "affected_unit_ids": ["existing unit_id"],
                    "source_document_ids": ["predecision document id"],
                    "explanation": "specific structural defect; no proposed rewrite",
                    "citation_excerpt": "short verbatim predecision excerpt",
                }
            ]
        },
        "case": _case_prompt_record(selection),
        "frozen_units": [unit.to_record() for unit in units],
        "documents": [document.prompt_record() for document in documents],
    }
    return json.dumps(payload, sort_keys=True, indent=2)


def _stage_a_structural_review_response_json_schema(
    documents: Sequence[_LlmDocument],
    units: Sequence[PredictionUnit],
) -> JsonRecord:
    """Build Gemini's constrained structural-response schema from frozen inputs."""

    return {
        "type": "object",
        "properties": {
            "structural_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flag_type": {
                            "type": "string",
                            "enum": ["omitted", "combined", "mis_split", "spurious"],
                        },
                        "affected_unit_ids": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [unit.unit_id for unit in units],
                            },
                        },
                        "source_document_ids": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    document.source_document_id
                                    for document in documents
                                ],
                            },
                        },
                        "explanation": {"type": "string"},
                        "citation_excerpt": {"type": "string"},
                    },
                    "required": [
                        "flag_type",
                        "affected_unit_ids",
                        "source_document_ids",
                        "explanation",
                        "citation_excerpt",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["structural_flags"],
        "additionalProperties": False,
    }


def validate_structural_review_flags(
    payload: Mapping[str, Any],
    *,
    units: Sequence[PredictionUnit],
    documents: Sequence[_LlmDocument],
    response: SolverResponse,
) -> tuple[JsonRecord, ...]:
    allowed_unit_ids = {unit.unit_id for unit in units}
    documents_by_id = {document.source_document_id: document for document in documents}
    allowed_types = {"omitted", "combined", "mis_split", "spurious"}
    forbidden = {"replacement_units", "proposed_units", "rewritten_units", "unit_seeds"}
    output: list[JsonRecord] = []
    for raw in _record_sequence(payload.get("structural_flags"), "structural_flags"):
        if forbidden.intersection(raw):
            raise LlmResponseValidationError(
                "structural reviewer may not rewrite units", response=response
            )
        flag_type = _required_str(raw, "flag_type")
        if flag_type not in allowed_types:
            raise LlmResponseValidationError(
                f"unsupported structural flag_type: {flag_type}", response=response
            )
        affected = _str_tuple(raw.get("affected_unit_ids"), "affected_unit_ids")
        if not affected or not set(affected) <= allowed_unit_ids:
            raise LlmResponseValidationError(
                "affected_unit_ids must reference existing frozen units",
                response=response,
            )
        source_ids = _str_tuple(raw.get("source_document_ids"), "source_document_ids")
        if not source_ids:
            raise LlmResponseValidationError(
                "structural flag requires source_document_ids", response=response
            )
        if not set(source_ids) <= documents_by_id.keys():
            raise LlmResponseValidationError(
                "structural flag source_document_ids must reference supplied "
                "predecision documents",
                response=response,
            )
        cited_excerpt = _required_str(raw, "citation_excerpt")
        verbatim_excerpt: str | None = None
        for source_id in source_ids:
            try:
                verbatim_excerpt = _coerced_structural_citation_excerpt(
                    documents_by_id[source_id].markdown, cited_excerpt
                )
            except LlmPipelineError:
                continue
            break
        if verbatim_excerpt is None:
            raise LlmResponseValidationError(
                "structural flag citation_excerpt does not appear in any cited "
                "predecision document",
                response=response,
            )
        output.append(
            {
                "flag_type": flag_type,
                "affected_unit_ids": list(affected),
                "source_document_ids": list(source_ids),
                "explanation": _required_str(raw, "explanation"),
                "citation_excerpt": verbatim_excerpt,
            }
        )
    return tuple(output)


def llm_label_cases(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    decision_text_artifact: VerifiedDecisionTextArtifact,
    registry_entries: Sequence[ModelRegistryEntry],
    model_registry_sha256: str | None = None,
    consensus_policy: LlmConsensusPolicy = LlmConsensusPolicy.UNANIMOUS,
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    transport: LiveModelTransport | None = None,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = 120.0,
    continue_on_error: bool = False,
    provider_journal_path: str | Path | None = None,
    provider_cycle_cap_usd: float = DEFAULT_CYCLE_PROVIDER_CAP_USD,
    provider_cycle_caps_usd: Mapping[str, float] | None = None,
    provider_cycle_id: str | None = None,
    provider_cycle_caps_sha256: str | None = None,
    provider_spend_authorities: Mapping[str, ProviderSpendAuthority] | None = None,
    provider_accounts: Mapping[str, str] | None = None,
    execution_provider: str | None = None,
    defer_consensus: bool = False,
) -> LlmBatchResult:
    """Generate Stage B labels or one provider-isolated judge shard.

    A provider shard always receives the complete frozen judge registry but
    executes only entries belonging to ``execution_provider``.  It emits no
    selected labels; consensus must be reconstructed from every authenticated
    provider shard in a provider-free finalization step.
    """

    if not registry_entries:
        raise LlmPipelineError("at least one registry entry is required")
    if defer_consensus != (execution_provider is not None):
        raise LlmPipelineError(
            "provider-sharded labeling requires both execution_provider and "
            "defer_consensus"
        )
    normalized_execution_provider = (
        execution_provider.strip().lower() if execution_provider is not None else None
    )
    execution_entries = (
        tuple(
            entry
            for entry in registry_entries
            if entry.provider.lower() == normalized_execution_provider
        )
        if normalized_execution_provider is not None
        else tuple(registry_entries)
    )
    if not execution_entries:
        raise LlmPipelineError(
            "execution_provider has no entries in the frozen judge registry"
        )
    selections = tuple(selection_records)
    finalized_unit_records = require_finalized_envelopes(prediction_unit_records)
    units_by_candidate = _prediction_units_by_candidate(finalized_unit_records)
    decisions_by_candidate = _verified_stage_b_decisions(decision_text_artifact)
    selection_candidate_ids = [
        _required_str(record, "candidate_id") for record in selections
    ]
    if len(selection_candidate_ids) != len(set(selection_candidate_ids)):
        raise LlmPipelineError("selection contains duplicate candidates")
    finalized_candidate_ids = [
        _required_str(record, "candidate_id") for record in finalized_unit_records
    ]
    if len(finalized_candidate_ids) != len(set(finalized_candidate_ids)):
        raise LlmPipelineError(
            "finalized prediction units contain duplicate candidates"
        )
    if not (
        set(selection_candidate_ids)
        == set(finalized_candidate_ids)
        == set(decisions_by_candidate)
    ):
        raise LlmPipelineError(
            "decision text, selection, and finalized-unit candidate coverage differ"
        )
    finalized_cases = {
        _required_str(record, "candidate_id"): _required_str(record, "case_id")
        for record in finalized_unit_records
    }
    for selection in selections:
        candidate_id = _required_str(selection, "candidate_id")
        case_id = _required_str(selection, "case_id")
        _, commitment = decisions_by_candidate[candidate_id]
        if (
            finalized_cases[candidate_id] != case_id
            or commitment["decision_text_case_id"] != case_id
        ):
            raise LlmPipelineError(
                f"Stage B candidate/case provenance mismatch: {candidate_id}"
            )
    excluded_candidates = {
        _required_str(record, "candidate_id")
        for record in finalized_unit_records
        if record.get("status") == "candidate_excluded"
    }
    records: list[JsonRecord] = []
    audit_records: list[JsonRecord] = []
    for selection in selections:
        candidate_id = _required_str(selection, "candidate_id")
        decision_text, decision_commitment = decisions_by_candidate[candidate_id]
        model_outputs: list[JsonRecord] = []
        attempted_entry: ModelRegistryEntry | None = None
        attempted_prompt_sha256: str | None = None
        try:
            if candidate_id in excluded_candidates:
                audit_records.append(
                    {
                        "stage": (
                            "llm-label-provider-shard"
                            if defer_consensus
                            else "llm-label"
                        ),
                        "status": "candidate_excluded",
                        "candidate_id": candidate_id,
                        "case_id": _required_str(selection, "case_id"),
                        "model_keys": [
                            entry.registry_key for entry in execution_entries
                        ],
                        **(
                            {
                                "execution_provider": normalized_execution_provider,
                                "frozen_panel_model_keys": [
                                    entry.registry_key for entry in registry_entries
                                ],
                                "model_registry_sha256": (
                                    model_registry_sha256 or "unrecorded"
                                ),
                            }
                            if defer_consensus
                            else {}
                        ),
                        "label_count": 0,
                        "unit_count": 0,
                        "estimated_cost": 0.0,
                        "decision_text_commitment": decision_commitment,
                    }
                )
                continue
            frozen_units = units_by_candidate.get(candidate_id)
            if not frozen_units:
                raise LlmPipelineError(f"prediction units missing for {candidate_id}")
            if decision_text.entered_date != _decision_date(selection):
                raise LlmPipelineError(
                    f"verified decision text date mismatch for {candidate_id}"
                )
            votes: list[EnsembleLabelVote] = []
            labels_by_model: dict[str, tuple[OutcomeLabel, ...]] = {}
            provider_prompt = _labeling_prompt(
                selection,
                decision_text,
                tuple(frozen_units),
                decision_text_commitment=decision_commitment,
            )
            attempted_prompt_sha256 = (
                "sha256:" + hashlib.sha256(provider_prompt.encode("utf-8")).hexdigest()
            )
            for entry in execution_entries:
                attempted_entry = entry
                labels, response, finding_count, missing_flag_count, prompt_sha256 = (
                    _llm_label_one_model(
                        selection=selection,
                        decision_text=decision_text,
                        decision_text_commitment=decision_commitment,
                        frozen_units=tuple(frozen_units),
                        prompt=provider_prompt,
                        registry_entry=entry,
                        model_registry_sha256=model_registry_sha256,
                        transport=transport,
                        environ=environ,
                        timeout_seconds=timeout_seconds,
                        provider_journal_path=provider_journal_path,
                        provider_cycle_cap_usd=_provider_cycle_cap(
                            entry.provider,
                            fallback=provider_cycle_cap_usd,
                            caps=provider_cycle_caps_usd,
                        ),
                        provider_cycle_id=provider_cycle_id,
                        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
                        provider_spend_authorities=provider_spend_authorities,
                        provider_accounts=provider_accounts,
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
                        "provider_prompt_sha256": prompt_sha256,
                        "metadata": dict(response.metadata or {}),
                        "labels": [label.to_record() for label in labels],
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
            if defer_consensus:
                audit_records.append(
                    {
                        "stage": "llm-label-provider-shard",
                        "status": "succeeded",
                        "candidate_id": candidate_id,
                        "case_id": _required_str(selection, "case_id"),
                        "execution_provider": normalized_execution_provider,
                        "model_keys": [
                            entry.registry_key for entry in execution_entries
                        ],
                        "frozen_panel_model_keys": [
                            entry.registry_key for entry in registry_entries
                        ],
                        "model_registry_sha256": model_registry_sha256 or "unrecorded",
                        "decision_text_commitment": decision_commitment,
                        "label_count": 0,
                        "unit_count": len(frozen_units),
                        "model_outputs": model_outputs,
                        "estimated_cost": sum(
                            _float(output.get("estimated_cost"))
                            for output in model_outputs
                        ),
                    }
                )
                continue
            ensemble = evaluate_labeling_ensemble(
                votes,
                high_confidence_threshold=high_confidence_threshold,
                required_model_count=len(registry_entries),
            )
            lawyer_review_packets = _lawyer_review_packets(
                candidate_id=candidate_id,
                ensemble=ensemble,
            )
            # Reliability sampling is deliberately cycle-level. Sampling here
            # would create one independent sample per case and make the audit
            # universe depend on processing order.
            label_audit_packets: tuple[LawyerReviewPacket, ...] = ()
            if lawyer_review_packets:
                selected_labels = tuple(ensemble.auto_labels)
            else:
                selected_labels = _selected_labels(
                    labels_by_model,
                    votes,
                    consensus_policy=consensus_policy,
                    first_model_key=registry_entries[0].registry_key,
                )
            all_review_packets = (*lawyer_review_packets, *label_audit_packets)
            pending_unit_ids = [packet.unit_id for packet in all_review_packets]
            pending_review_count = len(all_review_packets)
            adjudicated_review_count = 0
            queue_records = _lawyer_review_queue_records(
                candidate_id=candidate_id,
                selection=selection,
                lawyer_review_packets=lawyer_review_packets,
                label_audit_packets=label_audit_packets,
                ensemble=ensemble,
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
                    "status": (
                        "adjudication_pending" if all_review_packets else "succeeded"
                    ),
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "model_keys": [entry.registry_key for entry in registry_entries],
                    "model_registry_sha256": model_registry_sha256 or "unrecorded",
                    "decision_text_commitment": decision_commitment,
                    "human_verified": _human_verified_from_review_counts(
                        adjudicated_review_count=adjudicated_review_count,
                        pending_review_count=pending_review_count,
                    ),
                    "lawyer_review_packets": [
                        packet.to_record() for packet in lawyer_review_packets
                    ],
                    "lawyer_review_queue": queue_records,
                    "pending_adjudication_unit_ids": pending_unit_ids,
                    "pending_adjudication_count": pending_review_count,
                    "adjudicated_review_count": adjudicated_review_count,
                    "label_audit_gate": {
                        "required": True,
                        "cycle_level": True,
                        "status": "awaiting_cycle_level_plan",
                        "sample_unit_ids": [],
                    },
                    "consensus_policy": consensus_policy.value,
                    "consensus_policy_sha256": canonical_sha256(
                        {
                            "consensus_policy": consensus_policy.value,
                            "model_keys": [
                                entry.registry_key for entry in registry_entries
                            ],
                            "model_registry_sha256": (
                                model_registry_sha256 or "unrecorded"
                            ),
                        }
                    ),
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
                stage=("llm-label-provider-shard" if defer_consensus else "llm-label"),
                selection=selection,
                model_key=",".join(entry.registry_key for entry in execution_entries),
                error=exc,
                model_registry_sha256=model_registry_sha256,
            )
            if defer_consensus:
                failure_record.update(
                    {
                        "execution_provider": normalized_execution_provider,
                        "frozen_panel_model_keys": [
                            entry.registry_key for entry in registry_entries
                        ],
                    }
                )
            if isinstance(exc, LlmResponseValidationError):
                failure_record.update(_response_audit_fields(exc.response))
            elif isinstance(exc, FrozenUnitWorkflowRequiredError):
                failure_record.update(_response_audit_fields(exc.response))
                failure_record.update(_frozen_unit_workflow_audit_fields(exc))
            if isinstance(
                exc, (LlmResponseValidationError, FrozenUnitWorkflowRequiredError)
            ):
                if attempted_entry is None or attempted_prompt_sha256 is None:
                    raise LlmPipelineError(
                        "validated provider failure lacks attempted model identity"
                    ) from exc
                failure_record["model_outputs"] = [
                    *model_outputs,
                    {
                        "status": "validation_failed",
                        "model_key": attempted_entry.registry_key,
                        "provider_prompt_sha256": attempted_prompt_sha256,
                        **_response_audit_fields(exc.response),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                ]
            failure_record["decision_text_commitment"] = decision_commitment
            audit_records.append(failure_record)
            if not continue_on_error:
                raise
    return LlmBatchResult(records=tuple(records), audit_records=tuple(audit_records))


def merge_llm_label_provider_shards(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    decision_text_artifact: VerifiedDecisionTextArtifact,
    registry_entries: Sequence[ModelRegistryEntry],
    provider_shard_audit_records: Iterable[Mapping[str, Any]],
    model_registry_sha256: str,
    consensus_policy: LlmConsensusPolicy = LlmConsensusPolicy.UNANIMOUS,
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
) -> LlmBatchResult:
    """Merge every provider shard without loading a provider credential.

    The caller must authenticate each shard run card before passing its audit
    rows here.  This function revalidates the frozen panel, prompt commitment,
    decision-text commitment, model coverage, and labels before selecting any
    consensus output.
    """

    if not registry_entries:
        raise LlmPipelineError("at least one registry entry is required")
    selections = tuple(selection_records)
    finalized_unit_records = require_finalized_envelopes(prediction_unit_records)
    units_by_candidate = _prediction_units_by_candidate(finalized_unit_records)
    decisions_by_candidate = _verified_stage_b_decisions(decision_text_artifact)
    selection_by_candidate: dict[str, Mapping[str, Any]] = {}
    for selection in selections:
        candidate_id = _required_str(selection, "candidate_id")
        if candidate_id in selection_by_candidate:
            raise LlmPipelineError("selection contains duplicate candidates")
        selection_by_candidate[candidate_id] = selection
    finalized_by_candidate: dict[str, Mapping[str, Any]] = {}
    for record in finalized_unit_records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in finalized_by_candidate:
            raise LlmPipelineError(
                "finalized prediction units contain duplicate candidates"
            )
        finalized_by_candidate[candidate_id] = record
    expected_candidates = set(selection_by_candidate)
    if (
        set(finalized_by_candidate) != expected_candidates
        or set(decisions_by_candidate) != expected_candidates
    ):
        raise LlmPipelineError(
            "decision text, selection, and finalized-unit candidate coverage differ"
        )

    entries_by_provider: dict[str, tuple[ModelRegistryEntry, ...]] = {}
    for provider in sorted({entry.provider.lower() for entry in registry_entries}):
        entries_by_provider[provider] = tuple(
            entry for entry in registry_entries if entry.provider.lower() == provider
        )
    frozen_panel_model_keys = tuple(entry.registry_key for entry in registry_entries)
    shard_rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in provider_shard_audit_records:
        if row.get("stage") != "llm-label-provider-shard":
            raise LlmPipelineError("provider shard audit contains a non-shard row")
        candidate_id = _required_str(row, "candidate_id")
        provider = _required_str(row, "execution_provider").lower()
        key = (candidate_id, provider)
        if key in shard_rows:
            raise LlmPipelineError(
                f"duplicate provider shard audit row: {candidate_id}/{provider}"
            )
        shard_rows[key] = row
    expected_keys = {
        (candidate_id, provider)
        for candidate_id in expected_candidates
        for provider in entries_by_provider
    }
    if set(shard_rows) != expected_keys:
        raise LlmPipelineError(
            "provider shard audit coverage differs from the frozen candidate/panel "
            "cross-product"
        )

    excluded_candidates = {
        candidate_id
        for candidate_id, record in finalized_by_candidate.items()
        if record.get("status") == "candidate_excluded"
    }
    records: list[JsonRecord] = []
    audit_records: list[JsonRecord] = []
    for candidate_id, selection in selection_by_candidate.items():
        decision_text, decision_commitment = decisions_by_candidate[candidate_id]
        frozen_units = units_by_candidate.get(candidate_id)
        rows = [
            shard_rows[(candidate_id, provider)] for provider in entries_by_provider
        ]
        for provider, row in zip(entries_by_provider, rows, strict=True):
            expected_model_keys = [
                entry.registry_key for entry in entries_by_provider[provider]
            ]
            if (
                row.get("model_registry_sha256") != model_registry_sha256
                or row.get("frozen_panel_model_keys") != list(frozen_panel_model_keys)
                or row.get("model_keys") != expected_model_keys
                or row.get("case_id") != _required_str(selection, "case_id")
                or row.get("decision_text_commitment") != decision_commitment
            ):
                raise LlmPipelineError(
                    f"provider shard frozen lineage differs: {candidate_id}/{provider}"
                )
        if candidate_id in excluded_candidates:
            if any(row.get("status") != "candidate_excluded" for row in rows):
                raise LlmPipelineError(
                    f"excluded candidate has a non-excluded provider shard: "
                    f"{candidate_id}"
                )
            audit_records.append(
                {
                    "stage": "llm-label",
                    "status": "candidate_excluded",
                    "candidate_id": candidate_id,
                    "case_id": _required_str(selection, "case_id"),
                    "model_keys": list(frozen_panel_model_keys),
                    "model_registry_sha256": model_registry_sha256,
                    "label_count": 0,
                    "unit_count": 0,
                    "estimated_cost": 0.0,
                    "decision_text_commitment": decision_commitment,
                }
            )
            continue
        if not frozen_units:
            raise LlmPipelineError(f"prediction units missing for {candidate_id}")
        if decision_text.entered_date != _decision_date(selection):
            raise LlmPipelineError(
                f"verified decision text date mismatch for {candidate_id}"
            )
        if any(row.get("status") != "succeeded" for row in rows):
            raise LlmPipelineError(
                f"provider shard did not succeed for candidate {candidate_id}"
            )

        provider_prompt = _labeling_prompt(
            selection,
            decision_text,
            tuple(frozen_units),
            decision_text_commitment=decision_commitment,
        )
        prompt_sha256 = (
            "sha256:" + hashlib.sha256(provider_prompt.encode("utf-8")).hexdigest()
        )
        outputs_by_model: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            raw_outputs = _record_sequence(
                row.get("model_outputs"),
                "model_outputs",
            )
            if row.get("unit_count") != len(frozen_units):
                raise LlmPipelineError(
                    f"provider shard unit count differs for {candidate_id}"
                )
            for output in raw_outputs:
                model_key = _required_str(output, "model_key")
                if model_key in outputs_by_model:
                    raise LlmPipelineError(
                        f"duplicate provider shard model output: "
                        f"{candidate_id}/{model_key}"
                    )
                outputs_by_model[model_key] = output
        if set(outputs_by_model) != set(frozen_panel_model_keys):
            raise LlmPipelineError(
                f"provider shard model coverage differs for {candidate_id}"
            )

        model_outputs: list[JsonRecord] = []
        labels_by_model: dict[str, tuple[OutcomeLabel, ...]] = {}
        votes: list[EnsembleLabelVote] = []
        expected_unit_ids = {unit.unit_id for unit in frozen_units}
        for entry in registry_entries:
            output = outputs_by_model[entry.registry_key]
            if output.get("provider_prompt_sha256") != prompt_sha256:
                raise LlmPipelineError(
                    f"provider shard prompt differs for "
                    f"{candidate_id}/{entry.registry_key}"
                )
            labels = tuple(
                _outcome_label(label)
                for label in _record_sequence(output.get("labels"), "labels")
            )
            if {label.unit_id for label in labels} != expected_unit_ids or len(
                labels
            ) != len(expected_unit_ids):
                raise LlmPipelineError(
                    f"provider shard labels differ from frozen units for "
                    f"{candidate_id}/{entry.registry_key}"
                )
            labels_by_model[entry.registry_key] = labels
            model_outputs.append(dict(output))
            raw_output_sha256 = _required_str(output, "raw_output_sha256")
            votes.extend(
                EnsembleLabelVote(
                    model_id=entry.registry_key,
                    unit_id=label.unit_id,
                    label=label,
                    confidence=label.label_confidence,
                    rationale="LLM-only Stage B outcome label.",
                    raw_response_id=raw_output_sha256,
                )
                for label in labels
            )

        ensemble = evaluate_labeling_ensemble(
            votes,
            high_confidence_threshold=high_confidence_threshold,
            required_model_count=len(registry_entries),
        )
        lawyer_review_packets = _lawyer_review_packets(
            candidate_id=candidate_id,
            ensemble=ensemble,
        )
        selected_labels = (
            tuple(ensemble.auto_labels)
            if lawyer_review_packets
            else _selected_labels(
                labels_by_model,
                votes,
                consensus_policy=consensus_policy,
                first_model_key=registry_entries[0].registry_key,
            )
        )
        ambiguous = [label.unit_id for label in selected_labels if label.ambiguous]
        if ambiguous:
            raise LlmPipelineError(
                f"LLM-only labels include ambiguous units: {ambiguous}"
            )
        pending_unit_ids = [packet.unit_id for packet in lawyer_review_packets]
        queue_records = _lawyer_review_queue_records(
            candidate_id=candidate_id,
            selection=selection,
            lawyer_review_packets=lawyer_review_packets,
            label_audit_packets=(),
            ensemble=ensemble,
        )
        records.extend(label.to_record() for label in selected_labels)
        audit_records.append(
            {
                "stage": "llm-label",
                "status": (
                    "adjudication_pending" if lawyer_review_packets else "succeeded"
                ),
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "model_keys": list(frozen_panel_model_keys),
                "model_registry_sha256": model_registry_sha256,
                "decision_text_commitment": decision_commitment,
                "human_verified": _human_verified_from_review_counts(
                    adjudicated_review_count=0,
                    pending_review_count=len(lawyer_review_packets),
                ),
                "lawyer_review_packets": [
                    packet.to_record() for packet in lawyer_review_packets
                ],
                "lawyer_review_queue": queue_records,
                "pending_adjudication_unit_ids": pending_unit_ids,
                "pending_adjudication_count": len(lawyer_review_packets),
                "adjudicated_review_count": 0,
                "label_audit_gate": {
                    "required": True,
                    "cycle_level": True,
                    "status": "awaiting_cycle_level_plan",
                    "sample_unit_ids": [],
                },
                "consensus_policy": consensus_policy.value,
                "consensus_policy_sha256": canonical_sha256(
                    {
                        "consensus_policy": consensus_policy.value,
                        "model_keys": list(frozen_panel_model_keys),
                        "model_registry_sha256": model_registry_sha256,
                    }
                ),
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
    return LlmBatchResult(records=tuple(records), audit_records=tuple(audit_records))


def stage_b_labeling_prompt_records(
    *,
    selection_records: Iterable[Mapping[str, Any]],
    prediction_unit_records: Iterable[Mapping[str, Any]],
    decision_text_artifact: VerifiedDecisionTextArtifact,
) -> tuple[JsonRecord, ...]:
    """Reconstruct exact Stage B prompts from finalized fixture or live inputs."""

    selections = tuple(selection_records)
    selection_candidate_ids = tuple(
        _required_str(selection, "candidate_id") for selection in selections
    )
    finalized_records = require_finalized_envelopes(prediction_unit_records)
    finalized_candidate_ids = tuple(
        _required_str(record, "candidate_id") for record in finalized_records
    )
    units_by_candidate = _prediction_units_by_candidate(finalized_records)
    decisions_by_candidate = _verified_stage_b_decisions(decision_text_artifact)
    expected_candidates = set(decisions_by_candidate)
    if (
        len(selection_candidate_ids) != len(set(selection_candidate_ids))
        or len(finalized_candidate_ids) != len(set(finalized_candidate_ids))
        or set(selection_candidate_ids) != expected_candidates
        or set(finalized_candidate_ids) != expected_candidates
    ):
        raise LlmPipelineError(
            "Stage B prompt candidate coverage differs across inputs"
        )
    output: list[JsonRecord] = []
    for selection in selections:
        candidate_id = _required_str(selection, "candidate_id")
        units = units_by_candidate.get(candidate_id)
        decision = decisions_by_candidate.get(candidate_id)
        if not units or decision is None:
            raise LlmPipelineError(
                f"Stage B prompt inputs missing for candidate {candidate_id}"
            )
        decision_text, decision_commitment = decision
        prompt = _labeling_prompt(
            selection,
            decision_text,
            tuple(units),
            decision_text_commitment=decision_commitment,
        )
        output.append(
            {
                "candidate_id": candidate_id,
                "case_id": _required_str(selection, "case_id"),
                "prompt": prompt,
                "prompt_sha256": "sha256:"
                + hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            }
        )
    if len(output) != len(decisions_by_candidate):
        raise LlmPipelineError(
            "Stage B prompt candidate coverage differs from decision texts"
        )
    return tuple(output)


def _llm_label_one_model(
    *,
    selection: Mapping[str, Any],
    decision_text: StageBDecisionText,
    decision_text_commitment: Mapping[str, str],
    frozen_units: tuple[PredictionUnit, ...],
    prompt: str,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str | None,
    transport: LiveModelTransport | None,
    environ: Mapping[str, str] | None,
    timeout_seconds: float,
    provider_journal_path: str | Path | None,
    provider_cycle_cap_usd: float,
    provider_cycle_id: str | None,
    provider_cycle_caps_sha256: str | None,
    provider_spend_authorities: Mapping[str, ProviderSpendAuthority] | None,
    provider_accounts: Mapping[str, str] | None,
) -> tuple[tuple[OutcomeLabel, ...], SolverResponse, int, int, str]:
    prompt_sha256 = "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    journal = _provider_attempt_journal(
        path=provider_journal_path,
        stage="llm-label",
        candidate_id=_required_str(selection, "candidate_id"),
        prompt=prompt,
        registry_entry=registry_entry,
        account=(provider_accounts or {}).get(
            registry_entry.provider.lower(), "default"
        ),
        model_registry_sha256=model_registry_sha256,
        cycle_cap_usd=provider_cycle_cap_usd,
        cycle_id=provider_cycle_id,
        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
    )
    try:
        max_attempts = _reconstruction_retry_max_attempts(journal)
        response = complete_live_prompt(
            registry_entry,
            prompt,
            model_registry_sha256=model_registry_sha256,
            transport=transport,
            environ=environ,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            attempt_handler=_combined_attempt_handler(
                journal=journal,
                authorities=provider_spend_authorities,
                accounts=provider_accounts,
                cycle_id=provider_cycle_id,
                stage="llm-label",
                candidate_id=_required_str(selection, "candidate_id"),
                registry_entry=registry_entry,
            ),
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
                for record in _optional_record_sequence(
                    payload.get("missing_unit_flags")
                )
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
            if result.requires_frozen_unit_workflow:
                raise _frozen_unit_workflow_required_error(
                    selection=selection,
                    decision_text=decision_text,
                    frozen_units=frozen_units,
                    response=response,
                    labeling_result=result,
                )
        except FrozenUnitWorkflowRequiredError:
            raise
        except Exception as exc:
            if journal is not None and journal.has_validated_response:
                journal.record_reconstruction_failure(exc)
            raise LlmResponseValidationError(str(exc), response=response) from exc
        if journal is not None and journal.has_validated_response:
            journal.commit_reconstruction(
                {
                    "labels": [label.to_record() for label in result.labels],
                    "finding_count": len(findings),
                    "missing_unit_flag_count": len(missing_flags),
                    "decision_text_commitment": dict(decision_text_commitment),
                }
            )
        return (
            result.labels,
            response,
            len(findings),
            len(missing_flags),
            prompt_sha256,
        )
    finally:
        if journal is not None:
            journal.close()


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
                "A unit must represent one asserted legal right, or one independently "
                "disposable subclaim, against an actual moving defendant in the "
                "pleaded capacity."
            ),
            (
                "A dismissal ground, defense, procedural predicate, claim element, "
                "factual theory, requested remedy, or generic declaratory relief is "
                "never "
                "itself a prediction unit. Examples include limitations, standing, "
                "exhaustion, qualified or sovereign immunity, service, personal "
                "jurisdiction, venue, arbitration, preemption, Section 230, SLUSA, and "
                "release. Attach those concepts to the challenged claim in your "
                "analysis; do not emit them as unit_seeds."
            ),
            (
                "Apply the independent-disposition test: create separate units only "
                "when the court could dismiss one asserted proposition while another "
                "survives as an independently enforceable legal right against the same "
                "defendant."
            ),
            (
                "If the motion attacks only an element, factual theory, or "
                "application of law within one claim, keep one claim-level unit and "
                "use partial_theory_only."
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
                "defendant_names must contain actual party names. A single defendant "
                "is individual. Never put a claim, theory, ground, role, or capacity "
                "label in defendant_names; do not emit claims against a nonmoving "
                "defendant. Use "
                "group_label only for two or more actual defendants."
            ),
            (
                "Examples: exhaustion and limitations attacking one retaliation count "
                "produce one unit; Section 230 applied to six state-law claims "
                "produces six claim units and no Section 230 unit; duty to defend and "
                "duty to indemnify may be separable coverage units; induced and "
                "contributory "
                "infringement "
                "may be separable statutory subclaims."
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


def _provider_attempt_journal(
    *,
    path: str | Path | None,
    stage: str,
    candidate_id: str,
    prompt: str,
    registry_entry: ModelRegistryEntry,
    account: str = "default",
    model_registry_sha256: str | None,
    cycle_cap_usd: float,
    cycle_id: str | None,
    provider_cycle_caps_sha256: str | None,
    provider_attempt_namespace: str | None = None,
) -> ProviderAttemptJournal | None:
    if path is None:
        return None
    if not cycle_id or not provider_cycle_caps_sha256:
        raise LlmPipelineError(
            "provider journal requires authenticated cycle_id and caps artifact hash"
        )
    return ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage=stage,
            candidate_id=candidate_id,
            model_key=registry_entry.registry_key,
            prompt=prompt,
            model_registry_sha256=model_registry_sha256 or "unrecorded",
            account=account,
            prompt_contract=provider_attempt_namespace,
        ),
        provider=registry_entry.provider,
        reservation_usd=maximum_call_cost_usd(
            context_limit=registry_entry.context_limit,
            max_output_tokens=registry_entry.max_output_tokens,
            input_token_price=registry_entry.input_token_price,
            output_token_price=registry_entry.output_token_price,
        ),
        cycle_cap_usd=cycle_cap_usd,
        cycle_id=cycle_id,
        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
    )


def _require_successor_or_completed_legacy_attempt(
    journal: ProviderAttemptJournal | None,
    *,
    provider_attempt_namespace: str | None,
    stage: str,
) -> None:
    """Keep the historical Stage A logical-call namespace replay-only."""

    if provider_attempt_namespace is not None:
        return
    if journal is None or journal.has_settled_attempt:
        return
    raise LlmPipelineError(
        f"live Stage A {stage} requires the closed successor provider-attempt "
        "namespace; the historical namespace permits only an exact completed "
        "journal replay"
    )


def _combined_attempt_handler(
    *,
    journal: ProviderAttemptJournal | None,
    authorities: Mapping[str, ProviderSpendAuthority] | None,
    accounts: Mapping[str, str] | None,
    cycle_id: str | None,
    stage: str,
    candidate_id: str,
    registry_entry: ModelRegistryEntry,
) -> (
    ProviderAttemptJournal
    | ProviderSpendAttemptHandler
    | CompositeProviderAttemptHandler
    | None
):
    if authorities is None:
        return journal
    provider = registry_entry.provider.lower()
    try:
        authority = authorities[provider]
        account = (accounts or {})[provider]
    except KeyError as exc:
        raise LlmPipelineError(
            f"remote provider spend authority is incomplete for {provider}"
        ) from exc
    if not cycle_id:
        raise LlmPipelineError("remote provider spend authority requires cycle_id")
    spend_handler = ProviderSpendAttemptHandler(
        authority=authority,
        key=ProviderSpendKey(
            cycle_id=cycle_id,
            provider=provider,
            account=account,
            stage=stage,
            model_key=registry_entry.registry_key,
            case_id=candidate_id,
            ablation="labeling",
            repeat_index=1,
        ),
        reservation_microusd=conservative_reservation_microusd(
            context_limit=registry_entry.context_limit,
            max_output_tokens=registry_entry.max_output_tokens,
            input_token_price=registry_entry.input_token_price,
            output_token_price=registry_entry.output_token_price,
        ),
    )
    if journal is None:
        return spend_handler
    return CompositeProviderAttemptHandler(
        replay_handler=journal,
        spend_handler=spend_handler,
    )


def _labeling_prompt(
    selection: Mapping[str, Any],
    decision_text: StageBDecisionText,
    frozen_units: Sequence[PredictionUnit],
    *,
    decision_text_commitment: Mapping[str, str],
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
                "If the first written disposition does not address a frozen unit, "
                "use resolution not_addressed_by_this_disposition with "
                "amendment_signal not_applicable; do not infer an outcome from "
                "silence or later docket activity."
            ),
            ("If resolution is ambiguous, amendment_signal must be ambiguous."),
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
            "commitment": dict(decision_text_commitment),
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


def _frozen_unit_workflow_required_error(
    *,
    selection: Mapping[str, Any],
    decision_text: StageBDecisionText,
    frozen_units: tuple[PredictionUnit, ...],
    response: SolverResponse,
    labeling_result: StageBLabelingResult,
) -> FrozenUnitWorkflowRequiredError:
    missing_descriptions = "; ".join(
        flag.missing_unit_description for flag in labeling_result.missing_unit_flags
    )
    source_entry_ids = tuple(
        str(item) for item in _int_tuple(selection.get("decision_entry_numbers"))
    ) or (decision_text.document_id,)
    repair_result = exclude_for_missing_stage_a_unit(
        candidate_id=_required_str(selection, "candidate_id"),
        case_id=_required_str(selection, "case_id"),
        court=_optional_str(selection, "court"),
        frozen_units=frozen_units,
        source_entry_ids=source_entry_ids,
        source_document_ids=(decision_text.document_id,),
        notes=(
            "Stage B judge reported material missing units; blinded frozen-unit "
            "repair or exclusion is required before scoring: "
            f"{missing_descriptions}"
        ),
    )
    return FrozenUnitWorkflowRequiredError(
        response=response,
        labeling_result=labeling_result,
        repair_result=repair_result,
    )


def _frozen_unit_workflow_audit_fields(
    error: FrozenUnitWorkflowRequiredError,
) -> JsonRecord:
    status = error.repair_result.status
    return {
        "requires_frozen_unit_workflow": True,
        "missing_unit_flag_count": len(error.labeling_result.missing_unit_flags),
        "missing_unit_flags": [
            flag.to_record(error.labeling_result.decision_text)
            for flag in error.labeling_result.missing_unit_flags
        ],
        "frozen_unit_workflow": error.repair_result.to_manifest_fields(),
        "frozen_unit_repaired_count": int(status is FrozenUnitStatus.REPAIRED),
        "frozen_unit_excluded_count": int(status is FrozenUnitStatus.EXCLUDED),
    }


def _predecision_documents(
    selection: Mapping[str, Any],
    *,
    parser_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    markdown_root: Path,
    markdown_bytes: Mapping[str, bytes] | None = None,
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
                markdown=_markdown_text(
                    parser_record,
                    markdown_root=markdown_root,
                    markdown_bytes=markdown_bytes,
                ),
            )
        )
    if not documents:
        raise LlmPipelineError(
            f"no predecision model-visible documents: {candidate_id}"
        )
    return tuple(documents)


def _verified_stage_b_decisions(
    artifact: VerifiedDecisionTextArtifact,
) -> dict[str, tuple[StageBDecisionText, JsonRecord]]:
    output: dict[str, tuple[StageBDecisionText, JsonRecord]] = {}
    seen_document_ids: set[str] = set()
    for record in artifact.records:
        candidate_id = _required_str(record, "candidate_id")
        if candidate_id in output:
            raise LlmPipelineError(f"duplicate decision text candidate: {candidate_id}")
        if record.get("schema_version") != DECISION_TEXT_SCHEMA_VERSION:
            raise LlmPipelineError(
                f"unsupported verified decision text schema: {candidate_id}"
            )
        if (
            record.get("is_first_written_disposition") is not True
            or record.get("contains_target_outcome") is not True
            or record.get("model_visible") is not False
        ):
            raise LlmPipelineError(
                "verified decision text violates Stage B visibility gates: "
                f"{candidate_id}"
            )
        document_id = _required_str(record, "document_id")
        if document_id in seen_document_ids:
            raise LlmPipelineError(
                f"decision document_id is not globally unique: {document_id}"
            )
        seen_document_ids.add(document_id)
        decision_text = StageBDecisionText(
            document_id=document_id,
            entered_date=_required_str(record, "entered_date"),
            text=_required_str(record, "text"),
        )
        recorded_text_sha256 = _required_str(record, "text_sha256").removeprefix(
            "sha256:"
        )
        if recorded_text_sha256 != decision_text.text_sha256:
            raise LlmPipelineError(
                f"verified decision text hash mismatch: {candidate_id}"
            )
        output[candidate_id] = (
            decision_text,
            {
                "decision_texts_sha256": artifact.decision_texts_sha256,
                "decision_texts_manifest_sha256": artifact.manifest_sha256,
                "decision_texts_run_card_sha256": artifact.run_card_sha256,
                "decision_text_record_sha256": artifact.record_commitment(record),
                "decision_text_sha256": "sha256:" + decision_text.text_sha256,
                "decision_text_case_id": _required_str(record, "case_id"),
                "finalized_prediction_units_sha256": (
                    artifact.finalized_prediction_units_sha256
                ),
                "finalized_unit_envelope_sha256": (
                    artifact.finalized_unit_envelope_sha256s[candidate_id]
                ),
            },
        )
    if not output:
        raise LlmPipelineError("verified decision text artifact is empty")
    return output


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


def _markdown_text(
    record: Mapping[str, Any],
    *,
    markdown_root: Path,
    markdown_bytes: Mapping[str, bytes] | None = None,
) -> str:
    markdown_path = Path(_required_str(record, "markdown_path"))
    if ".." in markdown_path.parts:
        raise LlmPipelineError(
            f"markdown snapshot path may not traverse parents: {markdown_path}"
        )
    lexical_path = (
        markdown_path if markdown_path.is_absolute() else markdown_root / markdown_path
    )
    root = Path(os.path.abspath(markdown_root))
    try:
        relative_path = Path(os.path.abspath(lexical_path)).relative_to(root).as_posix()
    except ValueError as exc:
        raise LlmPipelineError(
            f"markdown path is outside markdown_root: {lexical_path}"
        ) from exc
    if markdown_bytes is None:
        try:
            payload = read_unique_regular_file(lexical_path)
        except ReviewBundleError as exc:
            raise LlmPipelineError(
                f"markdown file cannot be safely read: {lexical_path}"
            ) from exc
    else:
        try:
            payload = markdown_bytes[relative_path]
        except KeyError as exc:
            raise LlmPipelineError(
                f"markdown snapshot missing or outside root: {lexical_path}"
            ) from exc
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LlmPipelineError(f"markdown file is not UTF-8: {lexical_path}") from exc
    if not text.strip():
        raise LlmPipelineError(f"markdown file is empty: {lexical_path}")
    return text


def _stage_a_seed(record: Mapping[str, Any]) -> StageAUnitSeed:
    challenged_by_motion = _required_bool(record, "challenged_by_motion")
    challenge_scope = ChallengeScope(_required_str(record, "challenge_scope"))
    provider_challenge_scope = challenge_scope
    defendant_names = _str_tuple(record.get("defendant_names"), "defendant_names")
    grouping = DefendantGrouping(
        _optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
    )
    grouping_rationale = _optional_str(record, "grouping_rationale")
    group_label = _optional_str(record, "group_label")
    separable_subclaim = _optional_str(record, "separable_subclaim")
    uncertainty_notes = _optional_str(record, "uncertainty_notes")
    review_reason: UnitizationReviewReason | None = None
    if (
        separable_subclaim is not None
        and challenge_scope is not ChallengeScope.SEPARABLE_SUBCLAIM
    ):
        conflict_note = (
            "Provider response supplied separable_subclaim for "
            f"challenge_scope={challenge_scope.value}: {separable_subclaim}"
        )
        uncertainty_notes = (
            f"{uncertainty_notes} {conflict_note}"
            if uncertainty_notes is not None
            else conflict_note
        )
        challenge_scope = ChallengeScope.UNCLEAR
        separable_subclaim = None
        review_reason = UnitizationReviewReason.UNCLEAR_CLAIM_OR_DEFENDANT
    if grouping is DefendantGrouping.GROUPED and len(defendant_names) == 1:
        grouping_details = [
            f"defendant_names={','.join(defendant_names)}",
            f"challenge_scope={provider_challenge_scope.value}",
        ]
        if group_label is not None:
            grouping_details.append(f"group_label={group_label}")
        if grouping_rationale is not None:
            grouping_details.append(f"grouping_rationale={grouping_rationale}")
        if separable_subclaim is not None:
            grouping_details.append(f"separable_subclaim={separable_subclaim}")
        conflict_note = (
            "Provider response marked a single-defendant seed as grouped; "
            + "; ".join(grouping_details)
        )
        uncertainty_notes = (
            f"{uncertainty_notes} {conflict_note}"
            if uncertainty_notes is not None
            else conflict_note
        )
        grouping = DefendantGrouping.INDIVIDUAL
        grouping_rationale = None
        group_label = None
        challenge_scope = ChallengeScope.UNCLEAR
        separable_subclaim = None
        review_reason = review_reason or UnitizationReviewReason.UNCLEAR_GROUPING
    elif grouping is DefendantGrouping.INDIVIDUAL and (
        group_label is not None or grouping_rationale is not None
    ):
        conflict_note = (
            "Provider response supplied grouping metadata for an individual defendant; "
            f"defendant_names={','.join(defendant_names)}; "
            f"group_label={group_label}; grouping_rationale={grouping_rationale}"
        )
        uncertainty_notes = (
            f"{uncertainty_notes} {conflict_note}"
            if uncertainty_notes is not None
            else conflict_note
        )
        group_label = None
        grouping_rationale = None
        challenge_scope = ChallengeScope.UNCLEAR
        separable_subclaim = None
        review_reason = review_reason or UnitizationReviewReason.UNCLEAR_GROUPING
    if not challenged_by_motion:
        conflict_note = (
            "Provider response emitted a unit not challenged by the target motion."
        )
        uncertainty_notes = (
            f"{uncertainty_notes} {conflict_note}"
            if uncertainty_notes is not None
            else conflict_note
        )
        review_reason = (
            review_reason or UnitizationReviewReason.UNCLEAR_CLAIM_OR_DEFENDANT
        )
        challenge_scope = ChallengeScope.UNCLEAR
        separable_subclaim = None
    return StageAUnitSeed(
        count=_required_str(record, "count"),
        claim_name=_required_str(record, "claim_name"),
        defendant_names=defendant_names,
        source_document_ids=_str_tuple(
            record.get("source_document_ids"),
            "source_document_ids",
        ),
        challenged_by_motion=challenged_by_motion,
        challenge_scope=challenge_scope,
        unit_confidence=_required_float(record, "unit_confidence"),
        grouping=grouping,
        grouping_rationale=grouping_rationale,
        group_label=group_label,
        separable_subclaim=separable_subclaim,
        uncertainty_notes=uncertainty_notes,
        unit_id=_optional_str(record, "unit_id"),
        citation_page=_optional_int(record, "citation_page"),
        citation_paragraph=_optional_int(record, "citation_paragraph"),
        citation_excerpt=_optional_str(record, "citation_excerpt"),
        review_reason=review_reason,
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


def _unitization_human_verified(result: StageAConstructionResult) -> bool:
    return _human_verified_from_review_counts(
        adjudicated_review_count=0,
        pending_review_count=len(result.review_items),
    )


def _lawyer_review_packets(
    *,
    candidate_id: str,
    ensemble: EnsembleRunResult,
) -> tuple[LawyerReviewPacket, ...]:
    packets: list[LawyerReviewPacket] = []
    for decision in ensemble.decisions:
        if decision.status is not EnsembleDecisionStatus.LAWYER_ADJUDICATION:
            continue
        packets.append(
            LawyerReviewPacket(
                review_id=f"{candidate_id}:{decision.unit_id}:lawyer-adjudication",
                candidate_id=candidate_id,
                unit_id=decision.unit_id,
                review_reason=decision.route_reason.value,
                materials=(
                    ReviewMaterial(
                        material_id=f"{decision.unit_id}:disagreement-summary",
                        kind=ReviewMaterialKind.DISAGREEMENT_SUMMARY,
                        text=(
                            "LAWYER_ADJUDICATION required because the LLM label "
                            "ensemble routed this unit for "
                            f"{decision.route_reason.value}."
                        ),
                    ),
                ),
            )
        )
    return tuple(packets)


def _lawyer_review_queue_records(
    *,
    candidate_id: str,
    selection: Mapping[str, Any],
    lawyer_review_packets: Sequence[LawyerReviewPacket],
    label_audit_packets: Sequence[LawyerReviewPacket],
    ensemble: EnsembleRunResult,
) -> list[JsonRecord]:
    if not lawyer_review_packets and not label_audit_packets:
        return []
    decisions_by_unit = {decision.unit_id: decision for decision in ensemble.decisions}
    return [
        {
            "schema_version": "legalforecast.lawyer_review_queue.v1",
            "status": "pending_adjudication",
            "candidate_id": candidate_id,
            "case_id": _required_str(selection, "case_id"),
            "unit_id": packet.unit_id,
            "review_id": packet.review_id,
            "route_reason": (
                "label_audit_sample"
                if packet in label_audit_packets
                else decisions_by_unit[packet.unit_id].route_reason.value
            ),
            "packet": packet.to_record(),
        }
        for packet in (*lawyer_review_packets, *label_audit_packets)
    ]


def _unitization_review_queue_records(
    *,
    candidate_id: str,
    case_id: str,
    result: StageAConstructionResult,
) -> list[JsonRecord]:
    return list(
        unitization_review_queue_records_from_items(
            candidate_id=candidate_id,
            case_id=case_id,
            review_items=(item.to_record() for item in result.review_items),
        )
    )


def unitization_review_queue_records_from_items(
    *,
    candidate_id: str,
    case_id: str,
    review_items: Iterable[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Build the canonical blinded queue from journaled Stage A review items."""

    return tuple(
        {
            "schema_version": "legalforecast.unitization_review_queue.v1",
            "status": "pending_adjudication",
            "candidate_id": candidate_id,
            "case_id": case_id,
            "unit_id": _required_str(item, "unit_id"),
            "review_id": (
                f"{candidate_id}:{_required_str(item, 'unit_id')}:stage-a-review"
            ),
            "route_reason": _required_str(item, "reason"),
            "review_item": dict(item),
        }
        for item in review_items
    )


def unitization_review_queue_records(
    audit_records: Sequence[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Extract durable Stage A blinded-review queue rows from unitization audits."""

    records: list[JsonRecord] = []
    for audit_record in audit_records:
        queue_value = audit_record.get("unitization_review_queue")
        if queue_value is None:
            continue
        for queue_record in _record_sequence(
            queue_value,
            "unitization_review_queue",
        ):
            records.append(dict(queue_record))
    return tuple(records)


def lawyer_review_queue_records(
    audit_records: Sequence[Mapping[str, Any]],
) -> tuple[JsonRecord, ...]:
    """Extract durable lawyer-review queue rows from llm-label audit records."""

    records: list[JsonRecord] = []
    for audit_record in audit_records:
        queue_value = audit_record.get("lawyer_review_queue")
        if queue_value is None:
            continue
        for queue_record in _record_sequence(queue_value, "lawyer_review_queue"):
            records.append(dict(queue_record))
    return tuple(records)


def apply_adjudicated_reviews(
    *,
    label_records: Iterable[Mapping[str, Any]],
    adjudication_records: Iterable[Mapping[str, Any]],
    decision_texts: Mapping[str, StageBDecisionText],
    label_audit_records: Iterable[Mapping[str, Any]] = (),
    audit_sample_size: int = DEFAULT_LABEL_AUDIT_SAMPLE_SIZE,
    human_blind_disagreement_rate: float = 0.0,
) -> LlmBatchResult:
    """Merge lawyer adjudication records into the locked label JSONL.

    ``decision_texts`` maps first-written-disposition ``document_id`` to the
    decision text. Every adjudicated citation excerpt is validated against it,
    the same verbatim-excerpt check applied to LLM Stage B findings, so every
    published label -- human or LLM -- carries a citation an auditor can check.
    """

    if audit_sample_size <= 0:
        raise ValueError("audit_sample_size must be positive")
    labels_by_unit = {
        _required_str(record, "unit_id"): dict(record) for record in label_records
    }
    audit_records: list[JsonRecord] = []
    adjudications_by_unit_id: dict[str, AdjudicatedReview] = {}
    for record in adjudication_records:
        adjudication = _adjudicated_review(record)
        _validate_adjudicated_excerpts(adjudication, decision_texts)
        if adjudication.unit_id in adjudications_by_unit_id:
            raise ValueError(
                f"duplicate adjudication records for unit: {adjudication.unit_id}"
            )
        adjudications_by_unit_id[adjudication.unit_id] = adjudication
        # Blind reliability-audit responses measure the frozen auto label; they
        # must never rewrite it. Only routed merits adjudications replace labels.
        if not adjudication.review_id.endswith(":label-audit"):
            labels_by_unit[adjudication.unit_id] = (
                adjudication.adjudicated_label.to_record()
            )
        audit_records.append(
            {
                "stage": "lawyer-review-resume",
                "status": "succeeded",
                "candidate_id": adjudication.candidate_id,
                "unit_id": adjudication.unit_id,
                "review_id": adjudication.review_id,
                "human_verified": _human_verified_from_review_counts(
                    adjudicated_review_count=1,
                    pending_review_count=0,
                ),
                "adjudicated_review": adjudication.to_record(),
            }
        )
    audit_records.extend(
        _label_audit_gate_records(
            label_audit_records,
            adjudications_by_unit_id=adjudications_by_unit_id,
            audit_sample_size=audit_sample_size,
            human_blind_disagreement_rate=human_blind_disagreement_rate,
        )
    )
    return LlmBatchResult(
        records=tuple(labels_by_unit[unit_id] for unit_id in sorted(labels_by_unit)),
        audit_records=tuple(audit_records),
    )


def _label_audit_gate_records(
    label_audit_records: Iterable[Mapping[str, Any]],
    *,
    adjudications_by_unit_id: Mapping[str, AdjudicatedReview],
    audit_sample_size: int,
    human_blind_disagreement_rate: float,
) -> tuple[JsonRecord, ...]:
    records: list[JsonRecord] = []
    for audit_record in label_audit_records:
        if audit_record.get("stage") != "llm-label":
            continue
        ensemble = _ensemble_run_result(
            _mapping(audit_record.get("ensemble"), "ensemble")
        )
        sample_decisions = sample_unanimous_labels_for_audit(
            ensemble,
            sample_size=audit_sample_size,
        )
        sampled_unit_ids = [decision.unit_id for decision in sample_decisions]
        if not sampled_unit_ids:
            records.append(
                {
                    "stage": "label-audit-gate",
                    "status": "skipped",
                    "candidate_id": _optional_str(audit_record, "candidate_id"),
                    "case_id": _optional_str(audit_record, "case_id"),
                    "human_verified": _human_verified_from_review_counts(
                        adjudicated_review_count=0,
                        pending_review_count=0,
                    ),
                    "reason": "no_unanimous_auto_labels",
                    "audited_label_error_rate": None,
                    "sample_unit_ids": [],
                }
            )
            continue

        missing_unit_ids = [
            unit_id
            for unit_id in sampled_unit_ids
            if unit_id not in adjudications_by_unit_id
        ]
        if missing_unit_ids:
            raise ValueError(
                "label audit gate missing adjudications for sampled auto-label "
                f"units: {missing_unit_ids}"
            )

        gate = _label_audit_gate_record(
            ensemble,
            adjudicated_labels_by_unit_id={
                unit_id: adjudications_by_unit_id[unit_id].adjudicated_label
                for unit_id in sampled_unit_ids
            },
            human_blind_disagreement_rate=human_blind_disagreement_rate,
            sample_size=audit_sample_size,
        )
        records.append(
            {
                "stage": "label-audit-gate",
                "status": gate["status"],
                "candidate_id": _optional_str(audit_record, "candidate_id"),
                "case_id": _optional_str(audit_record, "case_id"),
                "human_verified": _human_verified_from_review_counts(
                    adjudicated_review_count=len(sampled_unit_ids),
                    pending_review_count=0,
                ),
                "audited_label_error_rate": gate["audited_label_error_rate"],
                "sample_unit_ids": gate["sample_unit_ids"],
                "label_audit_gate": gate,
            }
        )
    return tuple(records)


def _validate_adjudicated_excerpts(
    adjudication: AdjudicatedReview,
    decision_texts: Mapping[str, StageBDecisionText],
) -> None:
    """Reject an adjudicated label whose citation excerpts are not verbatim.

    Mirrors ``label_outcomes._validate_excerpts`` for LLM Stage B findings.
    Human adjudications were previously trusted without checking that
    ``supporting_citations[].excerpt`` actually appears in the decision text;
    this closes that gap so every published label has a checkable citation.
    Fail-closed: every adjudicated label needs at least one non-empty excerpt,
    and a cited document with no decision text to verify against is an error,
    not a skip.
    """

    found_excerpt = False
    for citation in adjudication.adjudicated_label.supporting_citations:
        excerpt = citation.excerpt
        if excerpt is None or not excerpt.strip():
            continue
        found_excerpt = True
        decision_text = decision_texts.get(citation.document_id)
        if decision_text is None:
            raise ValueError(
                "adjudicated citation references document_id "
                f"{citation.document_id!r} with no decision text to verify the "
                f"supporting excerpt for unit {adjudication.unit_id}"
            )
        if not decision_text.contains_excerpt(excerpt):
            raise ValueError(
                "adjudicated supporting excerpt must appear verbatim in the "
                f"decision text for unit {adjudication.unit_id}"
            )
    if not found_excerpt:
        raise ValueError(
            "adjudicated label must include at least one non-empty supporting "
            f"excerpt for unit {adjudication.unit_id}"
        )


def _adjudicated_review(record: Mapping[str, Any]) -> AdjudicatedReview:
    label_record = _mapping(record.get("adjudicated_label"), "adjudicated_label")
    return AdjudicatedReview(
        review_id=_required_str(record, "review_id"),
        candidate_id=_required_str(record, "candidate_id"),
        unit_id=_required_str(record, "unit_id"),
        reviewer_responses=tuple(
            _lawyer_review_response(response)
            for response in _record_sequence(
                record.get("reviewer_responses"),
                "reviewer_responses",
            )
        ),
        adjudicated_label=_outcome_label(label_record),
        adjudicator_id=_required_str(record, "adjudicator_id"),
        adjudication_notes=_required_str(record, "adjudication_notes"),
    )


def _lawyer_review_response(record: Mapping[str, Any]) -> LawyerReviewResponse:
    return LawyerReviewResponse(
        review_id=_required_str(record, "review_id"),
        reviewer_id=_required_str(record, "reviewer_id"),
        reviewer_expertise=ReviewerExpertise(
            _required_str(record, "reviewer_expertise")
        ),
        proposed_label=_outcome_label(_mapping(record.get("proposed_label"), "label")),
        confidence=_required_float(record, "confidence"),
        minutes_spent=_required_float(record, "minutes_spent"),
        notes=_required_str(record, "notes"),
    )


def _outcome_label(record: Mapping[str, Any]) -> OutcomeLabel:
    first_written_disposition_locked = _optional_bool(
        record,
        "first_written_disposition_locked",
        default=True,
    )
    if first_written_disposition_locked is None:
        first_written_disposition_locked = True
    return OutcomeLabel(
        unit_id=_required_str(record, "unit_id"),
        unit_resolution=UnitResolution(_required_str(record, "unit_resolution")),
        fully_dismissed=_optional_bool(record, "fully_dismissed"),
        amendment_class=AmendmentClass(_required_str(record, "amendment_class")),
        ambiguous=_required_bool(record, "ambiguous"),
        label_confidence=_required_float(record, "label_confidence"),
        supporting_citations=tuple(
            _outcome_citation(citation)
            for citation in _record_sequence(
                record.get("supporting_citations"),
                "supporting_citations",
            )
        ),
        first_written_disposition_id=_required_str(
            record,
            "first_written_disposition_id",
        ),
        first_written_disposition_date=_required_str(
            record,
            "first_written_disposition_date",
        ),
        first_written_disposition_locked=first_written_disposition_locked,
        later_procedural_changes=tuple(
            LaterProceduralChange(_required_str_value(change))
            for change in _optional_sequence(record.get("later_procedural_changes"))
        ),
        notes=_optional_str(record, "notes"),
    )


def _outcome_citation(record: Mapping[str, Any]) -> OutcomeCitation:
    return OutcomeCitation(
        document_id=_required_str(record, "document_id"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        excerpt=_optional_str(record, "excerpt"),
    )


def _ensemble_run_result(record: Mapping[str, Any]) -> EnsembleRunResult:
    return EnsembleRunResult(
        decisions=tuple(
            _ensemble_unit_decision(decision)
            for decision in _record_sequence(record.get("decisions"), "decisions")
        ),
        high_confidence_threshold=_required_float(
            record,
            "high_confidence_threshold",
        ),
        required_model_count=_required_int(record, "required_model_count"),
    )


def _ensemble_unit_decision(record: Mapping[str, Any]) -> EnsembleUnitDecision:
    unanimous_label_value = record.get("unanimous_label")
    unanimous_label = (
        _outcome_label(_mapping(unanimous_label_value, "unanimous_label"))
        if unanimous_label_value is not None
        else None
    )
    return EnsembleUnitDecision(
        unit_id=_required_str(record, "unit_id"),
        votes=tuple(
            _ensemble_label_vote(vote)
            for vote in _record_sequence(record.get("votes"), "votes")
        ),
        status=EnsembleDecisionStatus(_required_str(record, "status")),
        route_reason=EnsembleRouteReason(_required_str(record, "route_reason")),
        unanimous_label=unanimous_label,
    )


def _ensemble_label_vote(record: Mapping[str, Any]) -> EnsembleLabelVote:
    return EnsembleLabelVote(
        model_id=_required_str(record, "model_id"),
        unit_id=_required_str(record, "unit_id"),
        label=_outcome_label(_mapping(record.get("label"), "label")),
        confidence=_required_float(record, "confidence"),
        rationale=_required_str(record, "rationale"),
        raw_response_id=_optional_str(record, "raw_response_id"),
    )


def _label_audit_sample_decisions(
    ensemble: EnsembleRunResult,
    *,
    sample_size: int,
) -> tuple[EnsembleUnitDecision, ...]:
    if ensemble.auto_label_count == 0:
        return ()
    return sample_unanimous_labels_for_audit(
        ensemble,
        sample_size=min(sample_size, ensemble.auto_label_count),
    )


def _planned_label_audit_gate(
    ensemble: EnsembleRunResult,
    *,
    sample_size: int = DEFAULT_LABEL_AUDIT_SAMPLE_SIZE,
) -> JsonRecord:
    sample_decisions = _label_audit_sample_decisions(
        ensemble,
        sample_size=sample_size,
    )
    sample_unit_ids = [decision.unit_id for decision in sample_decisions]
    return {
        "required": True,
        "status": (
            "awaiting_human_adjudicated_labels"
            if sample_unit_ids
            else "no_unanimous_auto_labels"
        ),
        "audit_function": audit_ensemble_labels.__name__,
        "acceptance_function": enforce_label_audit_acceptance.__name__,
        "requested_sample_size": sample_size,
        "audit_sample_size": len(sample_unit_ids),
        "unanimous_auto_label_count": ensemble.auto_label_count,
        "sample_unit_ids": sample_unit_ids,
        "audited_label_error_rate": None,
    }


def _label_audit_gate_record(
    ensemble: EnsembleRunResult,
    *,
    adjudicated_labels_by_unit_id: Mapping[str, OutcomeLabel],
    human_blind_disagreement_rate: float = 0.0,
    sample_size: int = DEFAULT_LABEL_AUDIT_SAMPLE_SIZE,
) -> JsonRecord:
    record = _planned_label_audit_gate(ensemble, sample_size=sample_size)
    sample_unit_ids = list(cast(list[str], record["sample_unit_ids"]))
    if not sample_unit_ids or not adjudicated_labels_by_unit_id:
        return record
    missing_unit_ids = [
        unit_id
        for unit_id in sample_unit_ids
        if unit_id not in adjudicated_labels_by_unit_id
    ]
    if missing_unit_ids:
        raise ValueError(
            "label audit gate missing adjudications for sampled auto-label units: "
            f"{missing_unit_ids}"
        )
    summary = audit_ensemble_labels(
        ensemble,
        adjudicated_labels_by_unit_id={
            unit_id: adjudicated_labels_by_unit_id[unit_id]
            for unit_id in sample_unit_ids
        },
        human_blind_disagreement_rate=human_blind_disagreement_rate,
    )
    enforce_label_audit_acceptance(summary)
    return {
        **record,
        "status": "passed",
        "audit_summary": summary.to_record(),
        "audited_label_error_rate": summary.llm_audited_error_rate,
        "sample_unit_ids": sample_unit_ids,
    }


def _human_verified_from_review_counts(
    *,
    adjudicated_review_count: int,
    pending_review_count: int,
) -> bool:
    return adjudicated_review_count > 0 and pending_review_count == 0


def _labeling_exclusion_entries(
    selection: Mapping[str, Any],
    error: Exception,
) -> list[JsonRecord]:
    if not isinstance(error, LlmPipelineError):
        return []
    if isinstance(error, FrozenUnitWorkflowRequiredError):
        exclusion_entry = error.repair_result.exclusion_entry
        return [exclusion_entry.to_record()] if exclusion_entry is not None else []
    reason = _labeling_exclusion_reason(error)
    entry = ExclusionLedgerEntry(
        candidate_id=_optional_str(selection, "candidate_id") or "unknown-candidate",
        case_id=_optional_str(selection, "case_id") or "unknown-case",
        court=_optional_str(selection, "court"),
        decision_date=None,
        stage=ExclusionStage.LABELING,
        reason=reason,
        source_entry_ids=tuple(
            str(item) for item in _int_tuple(selection.get("decision_entry_numbers"))
        ),
        notes=f"LLM labeling/unitization failed closed ({reason}): {error}",
    )
    return [entry.to_record()]


def _labeling_exclusion_reason(error: LlmPipelineError) -> str:
    message = str(error).lower()
    if isinstance(error, LlmResponseValidationError):
        return ExclusionReason.PARSE_ERROR.value
    if "lawyer adjudication" in message:
        return ExclusionReason.ADJUDICATION_PENDING.value
    if "not unanimous" in message or "no majority" in message:
        return ExclusionReason.JUDGE_DISAGREEMENT.value
    if "ambiguous" in message:
        return ExclusionReason.AMBIGUOUS.value
    return ExclusionReason.LABEL_DIFFICULTY.value


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
    if value is None:
        raise LlmPipelineError(
            "selection is missing the first written MTD disposition decision_date"
        )
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise LlmPipelineError(
            "selection decision_date must be an ISO date (YYYY-MM-DD)"
        ) from exc
    return value


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
        candidate = _extract_balanced_json_value(
            text,
            allow_array=top_level_sequence_field is not None,
        )
        if candidate is None:
            raise LlmPipelineError(
                "LLM response did not contain a JSON object"
            ) from exc
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            repaired_candidate = _repair_unescaped_json_string_quotes(candidate)
            if repaired_candidate is None:
                raise LlmPipelineError("LLM response JSON object was invalid") from exc
            try:
                parsed = json.loads(repaired_candidate)
            except json.JSONDecodeError as repaired_exc:
                raise LlmPipelineError(
                    "LLM response JSON object was invalid"
                ) from repaired_exc
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


def _extract_balanced_json_value(text: str, *, allow_array: bool) -> str | None:
    candidates: list[tuple[str, str]] = [("{", "}")]
    if allow_array:
        candidates.append(("[", "]"))
    starts = [
        (index, opening, closing)
        for opening, closing in candidates
        if (index := text.find(opening)) >= 0
    ]
    if not starts:
        return None
    start, opening, closing = min(starts, key=lambda item: item[0])
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _repair_unescaped_json_string_quotes(text: str) -> str | None:
    """Repair only syntactically unambiguous literal quotes in JSON strings.

    A provider occasionally emits a literal double quote inside a string without
    escaping it.  This helper is deliberately narrower than a general JSON repair:
    it escapes a quote only while inside a string when its next non-whitespace
    character cannot legally follow a closing JSON string.  All other malformed
    output remains subject to strict ``json.loads`` validation by the caller.
    """

    repaired: list[str] = []
    in_string = False
    escaped = False
    changed = False
    closing_followers = frozenset({":", ",", "}", "]"})

    for index, char in enumerate(text):
        if not in_string:
            repaired.append(char)
            if char == '"':
                in_string = True
            continue

        if escaped:
            repaired.append(char)
            escaped = False
            continue
        if char == "\\":
            repaired.append(char)
            escaped = True
            continue
        if char != '"':
            repaired.append(char)
            continue

        next_index = index + 1
        while next_index < len(text) and text[next_index].isspace():
            next_index += 1
        next_character = text[next_index] if next_index < len(text) else None
        if next_character == '"':
            return None
        if next_character is None or next_character in closing_followers:
            repaired.append(char)
            in_string = False
            continue

        repaired.append('\\"')
        changed = True

    return "".join(repaired) if changed else None


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
        fuzzy = _closest_verbatim_excerpt(text, normalized_excerpt)
        if fuzzy is None:
            raise LlmPipelineError(
                "supporting_excerpt does not appear in decision text"
            )
        return fuzzy
    start = source_positions[offset]
    end_offset = offset + len(normalized_excerpt) - 1
    end = source_positions[min(end_offset, len(source_positions) - 1)] + 1
    return text[start:end].strip()


_STRUCTURAL_CITATION_APOSTROPHES = frozenset({"'", "\u2018", "\u2019", "\u02bc"})


def _coerced_structural_citation_excerpt(text: str, excerpt: str) -> str:
    """Return the exact source slice for the narrow Stage-A citation rule.

    Structural-review citations are not Stage B outcome excerpts.  They may
    differ only in whitespace representation and in the four interchangeable
    apostrophe code points that routinely drift through model JSON.  In
    particular, this deliberately has no case folding, Unicode normalization,
    punctuation substitution, or fuzzy fallback.
    """

    stripped = excerpt.strip()
    if not stripped:
        raise LlmPipelineError("structural citation_excerpt is required")
    exact_offset = text.find(stripped)
    if exact_offset >= 0:
        return text[exact_offset : exact_offset + len(stripped)]

    def normalized_characters(value: str) -> tuple[str, list[int]]:
        characters: list[str] = []
        positions: list[int] = []
        in_whitespace = False
        for index, char in enumerate(value):
            if char.isspace():
                if not in_whitespace:
                    characters.append(" ")
                    positions.append(index)
                in_whitespace = True
                continue
            characters.append("'" if char in _STRUCTURAL_CITATION_APOSTROPHES else char)
            positions.append(index)
            in_whitespace = False
        start = 0
        while start < len(characters) and characters[start] == " ":
            start += 1
        end = len(characters)
        while end > start and characters[end - 1] == " ":
            end -= 1
        return "".join(characters[start:end]), positions[start:end]

    normalized_excerpt, _ = normalized_characters(stripped)
    if not normalized_excerpt:
        raise LlmPipelineError("structural citation_excerpt is required")
    normalized_text, source_positions = normalized_characters(text)
    offset = normalized_text.find(normalized_excerpt)
    if offset < 0:
        raise LlmPipelineError(
            "structural citation_excerpt does not appear in source text"
        )
    start = source_positions[offset]
    end = source_positions[offset + len(normalized_excerpt) - 1] + 1
    return text[start:end]


def _closest_verbatim_excerpt(text: str, normalized_excerpt: str) -> str | None:
    normalized_target = normalized_excerpt.lower()
    if len(normalized_target) < 30:
        return None
    best_score = 0.0
    best_line: str | None = None
    for line in text.splitlines():
        candidate = line.strip()
        normalized_candidate = " ".join(candidate.split()).lower()
        if len(normalized_candidate) < 30 or len(normalized_candidate) > 600:
            continue
        score = SequenceMatcher(None, normalized_target, normalized_candidate).ratio()
        containment_score = _excerpt_containment_score(
            normalized_target,
            normalized_candidate,
        )
        score = max(score, containment_score)
        if score > best_score:
            best_score = score
            best_line = candidate
    if best_score < 0.88:
        return None
    return best_line


def _excerpt_containment_score(target: str, candidate: str) -> float:
    shorter, longer = (
        (target, candidate) if len(target) <= len(candidate) else (candidate, target)
    )
    if shorter not in longer:
        return 0.0
    return len(shorter) / len(longer)


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
        "human_verified": _human_verified_from_review_counts(
            adjudicated_review_count=0,
            pending_review_count=0,
        ),
        "exclusion_ledger_entries": _labeling_exclusion_entries(
            selection,
            error,
        ),
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


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LlmPipelineError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _optional_record_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    return _record_sequence(value, "missing_unit_flags")


def _optional_sequence(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise LlmPipelineError("value must be a list")
    return tuple(cast(Sequence[object], value))


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
    return _required_str_value(value, key)


def _required_str_value(value: object, key: str = "value") -> str:
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
    default: bool | None = None,
) -> bool | None:
    value = record.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise LlmPipelineError(f"{key} must be a boolean")
    return value


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


def _required_int(record: Mapping[str, Any], key: str) -> int:
    value = _optional_int(record, key)
    if value is None:
        raise LlmPipelineError(f"{key} must be an integer")
    return value


def _required_float(record: Mapping[str, Any], key: str) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LlmPipelineError(f"{key} must be a number")
    return float(value)


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _provider_cycle_cap(
    provider: str,
    *,
    fallback: float,
    caps: Mapping[str, float] | None,
) -> float:
    if caps is None:
        return fallback
    matches = [value for key, value in caps.items() if key.lower() == provider.lower()]
    if len(matches) != 1:
        raise LlmPipelineError(
            f"provider cycle caps must have exactly one entry for {provider!r}"
        )
    return matches[0]
