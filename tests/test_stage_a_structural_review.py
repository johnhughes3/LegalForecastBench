from __future__ import annotations

from typing import Any

import pytest
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.llm_pipeline import (
    LlmResponseValidationError,
    _LlmDocument,
    merge_structural_flags_into_review_queue,
    validate_structural_review_flags,
)
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="unit-1",
        count="Count I",
        claim_name="Retaliation",
        defendant_group="Acme",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="motion"),),
    )


def _response() -> SolverResponse:
    return SolverResponse(raw_output="{}", input_tokens=1, output_tokens=1)


def _documents() -> list[_LlmDocument]:
    return [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="motion",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss",
            markdown="The Court should dismiss the alternative theory.",
        )
    ]


def test_structural_reviewer_flags_are_hash_linked_into_john_queue() -> None:
    flag: dict[str, Any] = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "reviewer_model_key": "google:gemini-flash",
        "model_registry_sha256": "registry-hash",
        "raw_prediction_units_sha256": "raw-hash",
        "flag_sha256": "abcdef0123456789" * 4,
        "flag_type": "combined",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion"],
        "explanation": "Count I contains separately challenged theories.",
        "citation_excerpt": "dismiss each theory",
    }

    [queued] = merge_structural_flags_into_review_queue([], [flag])

    assert queued["unit_id"] == "unit-1"
    assert queued["route_reason"] == "structural_combined"
    assert queued["structural_flag_sha256"] == flag["flag_sha256"]
    assert queued["raw_prediction_units_sha256"] == "raw-hash"


def test_structural_reviewer_cannot_rewrite_or_reference_unknown_units() -> None:
    base: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion"],
        "explanation": "A separately challenged theory is absent.",
        "citation_excerpt": "dismiss the alternative theory",
    }
    with pytest.raises(LlmResponseValidationError, match="may not rewrite"):
        validate_structural_review_flags(
            {"structural_flags": [{**base, "replacement_units": []}]},
            units=[_unit()],
            documents=_documents(),
            response=_response(),
        )
    with pytest.raises(LlmResponseValidationError, match="existing frozen units"):
        validate_structural_review_flags(
            {"structural_flags": [{**base, "affected_unit_ids": ["invented-unit"]}]},
            units=[_unit()],
            documents=_documents(),
            response=_response(),
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"source_document_ids": ["invented-document"]}, "supplied predecision"),
        ({"citation_excerpt": "language not found anywhere"}, "does not appear"),
    ],
)
def test_structural_reviewer_requires_verbatim_citations_from_supplied_documents(
    override: dict[str, Any], message: str
) -> None:
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion"],
        "explanation": "A separately challenged theory is absent.",
        "citation_excerpt": "dismiss the alternative theory",
        **override,
    }

    with pytest.raises(LlmResponseValidationError, match=message):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=_documents(),
            response=_response(),
        )
