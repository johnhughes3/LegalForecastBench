from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from legalforecast.labeling.unitizer_terminal import (
    LlmStageAUnitizerTerminalEscalation,
    UnitizerTerminalEscalationError,
    read_llm_stage_a_unitizer_terminal_failure_evidence,
)


def _attempt(ordinal: int) -> dict[str, Any]:
    return {
        "attempt_ordinal": ordinal,
        "raw_response_sha256": "sha256:" + str(ordinal) * 64,
        "normalized_response_sha256": "sha256:" + chr(96 + ordinal) * 64,
        "failure_type": "ValueError",
        "failure_message": f"failed {ordinal}",
    }


def _escalation() -> LlmStageAUnitizerTerminalEscalation:
    return LlmStageAUnitizerTerminalEscalation(
        candidate_id="candidate-1",
        case_id="case-1",
        unitizer_model_key="anthropic:unitizer",
        model_registry_sha256="b" * 64,
        provider_attempt_namespace="claim-ontology-v5",
        prompt="frozen prompt",
        prompt_sha256=hashlib.sha256(b"frozen prompt").hexdigest(),
        predecision_source_commitments=(
            {
                "source_document_id": "complaint",
                "document_role": "complaint",
                "docket_entry_number": 1,
                "description": "Complaint",
                "markdown_sha256": "sha256:" + "d" * 64,
            },
        ),
        failed_attempts=tuple(_attempt(ordinal) for ordinal in (1, 2, 3)),
    )


def test_unitizer_terminal_escalation_binds_exactly_three_failed_attempts() -> None:
    escalation = _escalation()

    record = escalation.to_record()

    assert record["schema_version"] == (
        "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1"
    )
    assert record["provider_attempt_namespace"] == "claim-ontology-v5"
    assert [attempt["attempt_ordinal"] for attempt in record["failed_attempts"]] == [
        1,
        2,
        3,
    ]
    assert escalation.predecision_source_document_ids == ("complaint",)
    assert len(escalation.escalation_sha256) == 64


@pytest.mark.parametrize(
    "attempts",
    (
        (_attempt(1), _attempt(2)),
        (_attempt(1), _attempt(2), _attempt(3), _attempt(4)),
        (_attempt(1), _attempt(3), _attempt(2)),
    ),
)
def test_unitizer_terminal_escalation_rejects_nonexhausted_attempt_set(
    attempts: tuple[dict[str, Any], ...],
) -> None:
    escalation = _escalation()
    object.__setattr__(escalation, "failed_attempts", attempts)

    with pytest.raises(
        UnitizerTerminalEscalationError,
        match="exactly attempts 1, 2, and 3",
    ):
        escalation.to_record()


def test_unitizer_terminal_escalation_rejects_prompt_commitment_mismatch() -> None:
    escalation = _escalation()
    object.__setattr__(escalation, "prompt", "changed prompt")

    with pytest.raises(UnitizerTerminalEscalationError, match="prompt_sha256"):
        escalation.to_record()


def test_unitizer_terminal_escalation_rejects_duplicate_source_document() -> None:
    escalation = _escalation()
    source = escalation.predecision_source_commitments[0]
    object.__setattr__(
        escalation,
        "predecision_source_commitments",
        (source, dict(source)),
    )

    with pytest.raises(UnitizerTerminalEscalationError, match="unique"):
        escalation.to_record()


def test_terminal_failure_reader_is_provider_free_and_byte_preserving(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    identity = ProviderCallIdentity(
        stage="llm-unitize",
        candidate_id="candidate-1",
        model_key="anthropic:unitizer",
        prompt="frozen prompt",
        model_registry_sha256="b" * 64,
        prompt_contract="claim-ontology-v5",
    )
    with ProviderAttemptJournal(
        path,
        identity=identity,
        provider="anthropic",
        reservation_usd=0.1,
        cycle_cap_usd=1.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:frozen-caps",
    ) as journal:
        for ordinal in (1, 2, 3):
            if ordinal > 1:
                journal.prepare_reconstruction_retry(max_attempts=3)
            journal.run_attempt(1, lambda ordinal=ordinal: {"ordinal": ordinal})
            journal.settle_attempt(
                journal.durable_attempt_ordinal(1),
                input_tokens=1,
                output_tokens=1,
                actual_cost_usd=0.01,
                raw_output=f"invalid-{ordinal}",
            )
            journal.record_reconstruction_failure(ValueError(f"failure-{ordinal}"))
    before = path.read_bytes()

    evidence = read_llm_stage_a_unitizer_terminal_failure_evidence(
        path,
        identity=identity,
        provider="anthropic",
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:frozen-caps",
    )

    assert path.read_bytes() == before
    assert tuple(attempt.attempt_ordinal for attempt in evidence.attempts) == (1, 2, 3)
    assert evidence.failure_messages == ("failure-1", "failure-2", "failure-3")
