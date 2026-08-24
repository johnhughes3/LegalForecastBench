"""Provider-free contract for exhausted Stage A unitizer attempts."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.labeling.provider_journal import (
    ExhaustedReconstructionFailureEvidence,
    ProviderCallIdentity,
    ProviderJournalError,
    ReconstructionFailureEvidence,
    open_provider_journal_snapshot,
    provider_prompt_logical_call_scope,
    verify_provider_journal_identity,
)
from legalforecast.unitization.review import canonical_sha256

JsonRecord = dict[str, Any]
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PREFIXED_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


class UnitizerTerminalEscalationError(ValueError):
    """Raised when exhausted-unitizer evidence violates its closed contract."""


@dataclass(frozen=True, slots=True)
class LlmStageAUnitizerTerminalEscalation:
    """Authenticated evidence for attorney reconstruction of one candidate.

    This receipt contains no inferred prediction unit.  It binds the exact
    unitizer identity, prompt, predecision sources, and all three failed
    responses so downstream code can authorize only attorney ADD or candidate
    exclusion without another provider call.
    """

    candidate_id: str
    case_id: str
    unitizer_model_key: str
    model_registry_sha256: str
    provider_attempt_namespace: str
    prompt: str
    prompt_sha256: str
    predecision_source_commitments: tuple[JsonRecord, ...]
    failed_attempts: tuple[JsonRecord, ...]
    schema_version: str = str(LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1)

    def to_record(self) -> JsonRecord:
        """Return the closed receipt after validating all bound evidence."""

        self._validate()
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "unitizer_model_key": self.unitizer_model_key,
            "model_registry_sha256": self.model_registry_sha256,
            "provider_attempt_namespace": self.provider_attempt_namespace,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
            "predecision_source_commitments": [
                dict(commitment) for commitment in self.predecision_source_commitments
            ],
            "failed_attempts": [dict(attempt) for attempt in self.failed_attempts],
        }

    @property
    def escalation_sha256(self) -> str:
        """Return the canonical digest stored by queue and adjudication rows."""

        return canonical_sha256(self.to_record())

    @property
    def predecision_source_document_ids(self) -> tuple[str, ...]:
        """Return source IDs in the receipt's committed order."""

        self._validate()
        return tuple(
            _required_str(record, "source_document_id")
            for record in self.predecision_source_commitments
        )

    def _validate(self) -> None:
        if self.schema_version != str(LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1):
            raise UnitizerTerminalEscalationError(
                "unitizer terminal escalation schema is invalid"
            )
        for value, field in (
            (self.candidate_id, "candidate_id"),
            (self.case_id, "case_id"),
            (self.unitizer_model_key, "unitizer_model_key"),
            (self.provider_attempt_namespace, "provider_attempt_namespace"),
            (self.prompt, "prompt"),
        ):
            if not value.strip():
                raise UnitizerTerminalEscalationError(f"{field} must be nonempty")
        if _HEX_SHA256.fullmatch(self.model_registry_sha256) is None:
            raise UnitizerTerminalEscalationError(
                "model_registry_sha256 must be a lowercase SHA-256"
            )
        expected_prompt_sha256 = hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()
        if self.prompt_sha256 != expected_prompt_sha256:
            raise UnitizerTerminalEscalationError(
                "prompt_sha256 does not bind the frozen prompt"
            )
        if not self.predecision_source_commitments:
            raise UnitizerTerminalEscalationError(
                "predecision source commitments must be nonempty"
            )
        source_ids: list[str] = []
        for source in self.predecision_source_commitments:
            if set(source) != {
                "source_document_id",
                "document_role",
                "docket_entry_number",
                "description",
                "markdown_sha256",
            }:
                raise UnitizerTerminalEscalationError(
                    "predecision source commitment fields are invalid"
                )
            source_ids.append(_required_str(source, "source_document_id"))
            _required_str(source, "document_role")
            _required_str(source, "description")
            docket_entry_number = source["docket_entry_number"]
            if docket_entry_number is not None and (
                type(docket_entry_number) is not int or docket_entry_number <= 0
            ):
                raise UnitizerTerminalEscalationError(
                    "docket_entry_number must be a positive integer or null"
                )
            _required_prefixed_sha256(source, "markdown_sha256")
        if len(set(source_ids)) != len(source_ids):
            raise UnitizerTerminalEscalationError(
                "predecision source document IDs must be unique"
            )
        if tuple(
            _required_positive_int(attempt, "attempt_ordinal")
            for attempt in self.failed_attempts
        ) != (1, 2, 3):
            raise UnitizerTerminalEscalationError(
                "terminal escalation requires exactly attempts 1, 2, and 3"
            )
        for attempt in self.failed_attempts:
            if set(attempt) != {
                "attempt_ordinal",
                "raw_response_sha256",
                "normalized_response_sha256",
                "failure_type",
                "failure_message",
            }:
                raise UnitizerTerminalEscalationError(
                    "failed attempt evidence fields are invalid"
                )
            _required_prefixed_sha256(attempt, "raw_response_sha256")
            _required_prefixed_sha256(attempt, "normalized_response_sha256")
            _required_str(attempt, "failure_type")
            _required_str(attempt, "failure_message")


def build_llm_stage_a_unitizer_terminal_escalation(
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
    provider_logical_call_scope: str | None = None,
) -> LlmStageAUnitizerTerminalEscalation:
    """Build one provider-free receipt from exactly three durable failures.

    Imports of private prompt/source helpers are intentionally local to keep
    the new receipt model independent from the main provider execution module.
    The journal object authenticates the logical call and reads existing rows;
    this function never reserves, retries, settles, or rewrites an attempt.
    """

    from legalforecast.labeling import llm_pipeline

    llm_pipeline._require_stage_a_provider_attempt_namespace(  # pyright: ignore[reportPrivateUsage]
        "llm-unitize", provider_attempt_namespace
    )
    candidate_id = _required_str(selection_record, "candidate_id")
    case_id = _required_str(selection_record, "case_id")
    parser_by_key = llm_pipeline._parser_records_by_candidate_and_document(  # pyright: ignore[reportPrivateUsage]
        parser_records
    )
    documents = llm_pipeline._predecision_documents(  # pyright: ignore[reportPrivateUsage]
        selection_record,
        parser_by_key=parser_by_key,
        markdown_root=Path(markdown_root),
        markdown_bytes=markdown_bytes,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    prompt = llm_pipeline._unitization_prompt(  # pyright: ignore[reportPrivateUsage]
        selection_record,
        documents,
        provider_attempt_namespace=provider_attempt_namespace,
    )
    namespace = _required_namespace(provider_attempt_namespace)
    del provider_cycle_cap_usd
    logical_call_scope = None
    if provider_logical_call_scope is not None:
        logical_call_scope = provider_prompt_logical_call_scope(prompt)
        if provider_logical_call_scope != logical_call_scope:
            raise UnitizerTerminalEscalationError(
                "provider logical-call scope differs from the exact prompt"
            )
    identity = ProviderCallIdentity(
        stage="llm-unitize",
        candidate_id=candidate_id,
        model_key=registry_entry.registry_key,
        prompt=prompt,
        model_registry_sha256=model_registry_sha256,
        account=provider_account,
        prompt_contract=namespace,
        logical_call_scope=logical_call_scope,
    )
    evidence = read_llm_stage_a_unitizer_terminal_failure_evidence(
        provider_journal_path,
        identity=identity,
        provider=registry_entry.provider,
        cycle_id=provider_cycle_id,
        provider_cycle_caps_sha256=provider_cycle_caps_sha256,
    )
    return _receipt_from_evidence(
        candidate_id=candidate_id,
        case_id=case_id,
        documents=documents,
        registry_entry=registry_entry,
        model_registry_sha256=model_registry_sha256,
        provider_attempt_namespace=namespace,
        prompt=prompt,
        evidence=evidence,
    )


def _receipt_from_evidence(
    *,
    candidate_id: str,
    case_id: str,
    documents: Iterable[Any],
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_attempt_namespace: str,
    prompt: str,
    evidence: ExhaustedReconstructionFailureEvidence,
) -> LlmStageAUnitizerTerminalEscalation:
    source_commitments = tuple(
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
            evidence.attempts,
            evidence.failure_types,
            evidence.failure_messages,
            strict=True,
        )
    )
    escalation = LlmStageAUnitizerTerminalEscalation(
        candidate_id=candidate_id,
        case_id=case_id,
        unitizer_model_key=registry_entry.registry_key,
        model_registry_sha256=model_registry_sha256,
        provider_attempt_namespace=provider_attempt_namespace,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        predecision_source_commitments=source_commitments,
        failed_attempts=failed_attempts,
    )
    escalation.to_record()
    return escalation


def read_llm_stage_a_unitizer_terminal_failure_evidence(
    provider_journal_path: str | Path,
    *,
    identity: ProviderCallIdentity,
    provider: str,
    cycle_id: str,
    provider_cycle_caps_sha256: str,
) -> ExhaustedReconstructionFailureEvidence:
    """Read exactly three authenticated failures without touching source bytes."""

    with closing(open_provider_journal_snapshot(provider_journal_path)) as snapshot:
        verify_provider_journal_identity(
            provider_journal_path,
            cycle_id=cycle_id,
            provider_cycle_caps_sha256=provider_cycle_caps_sha256,
            snapshot=snapshot,
        )
        rows = snapshot.execute(
            """
            SELECT * FROM provider_attempts
            WHERE logical_call_key = ?
            ORDER BY attempt_ordinal
            """,
            (identity.logical_call_key,),
        ).fetchall()
    if len(rows) != 3 or any(
        int(row["attempt_ordinal"]) != ordinal
        or row["status"] != "reconstruction_failed"
        for ordinal, row in enumerate(rows, start=1)
    ):
        raise ProviderJournalError(
            "unitizer terminal escalation requires exactly three exhausted "
            "failed reconstructions"
        )
    expected_identity = (
        identity.stage,
        identity.candidate_id,
        identity.model_key,
        identity.prompt_sha256,
        identity.prompt,
        identity.model_registry_sha256,
        provider,
        identity.account,
    )
    for row in rows:
        actual_identity = tuple(
            row[field]
            for field in (
                "stage",
                "candidate_id",
                "model_key",
                "prompt_sha256",
                "prompt_text",
                "model_registry_sha256",
                "provider",
                "account",
            )
        )
        if actual_identity != expected_identity:
            raise ProviderJournalError(
                "unitizer terminal attempt identity or frozen input changed"
            )
        if (
            row["reconstructed_result_json"] is not None
            or not isinstance(row["raw_response_json"], str)
            or not row["raw_response_json"]
            or not isinstance(row["normalized_response_json"], str)
            or not row["normalized_response_json"]
            or not isinstance(row["failure_type"], str)
            or not row["failure_type"]
            or not isinstance(row["failure_message"], str)
            or not row["failure_message"]
        ):
            raise ProviderJournalError(
                "unitizer terminal escalation requires complete failure evidence"
            )
    return ExhaustedReconstructionFailureEvidence(
        attempts=tuple(
            ReconstructionFailureEvidence(
                attempt_ordinal=int(row["attempt_ordinal"]),
                raw_response_json=cast(str, row["raw_response_json"]),
                normalized_response_json=cast(str, row["normalized_response_json"]),
                failure_type=cast(str, row["failure_type"]),
                failure_message=cast(str, row["failure_message"]),
            )
            for row in rows
        ),
        failure_types=tuple(cast(str, row["failure_type"]) for row in rows),
        failure_messages=tuple(cast(str, row["failure_message"]) for row in rows),
    )


def _required_namespace(value: str | None) -> str:
    if not isinstance(value, str) or not value:
        raise UnitizerTerminalEscalationError(
            "provider_attempt_namespace must be nonempty"
        )
    return value


def _required_str(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise UnitizerTerminalEscalationError(f"{field} must be a nonempty string")
    return value


def _required_positive_int(record: Mapping[str, Any], field: str) -> int:
    value = record.get(field)
    if type(value) is not int or value <= 0:
        raise UnitizerTerminalEscalationError(f"{field} must be a positive integer")
    return value


def _required_prefixed_sha256(record: Mapping[str, Any], field: str) -> str:
    value = _required_str(record, field)
    if _PREFIXED_SHA256.fullmatch(value) is None:
        raise UnitizerTerminalEscalationError(
            f"{field} must be a prefixed lowercase SHA-256"
        )
    return value
