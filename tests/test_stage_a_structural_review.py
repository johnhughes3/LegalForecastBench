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


def test_structural_citation_allows_only_apostrophe_and_whitespace_drift() -> None:
    source_excerpt = (
        "Plaintiff\u2019s state law claims against Gage in his individual capacity "
        "are barred."
    )
    documents = [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="motion",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss",
            markdown="Before.\n\n" + source_excerpt + "\n\nAfter.",
        )
    ]
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion"],
        "explanation": "A separately challenged theory is absent.",
        "citation_excerpt": (
            "Plaintiff's  state law claims against Gage in his individual capacity "
            "are barred."
        ),
    }

    [validated] = validate_structural_review_flags(
        {"structural_flags": [flag]},
        units=[_unit()],
        documents=documents,
        response=_response(),
    )

    assert validated["citation_excerpt"] == source_excerpt


def test_structural_citation_accepts_explicit_ordered_multidocument_composite() -> None:
    first_source_excerpt = (
        "The first memorandum explains that Plaintiff\u2019s initial theory fails "
        "as a matter of law."
    )
    second_source_excerpt = (
        "The reply further explains that the remaining alternative theory is "
        "independently barred."
    )
    documents = [
        _LlmDocument(
            candidate_id="72270301",
            source_document_id="478193908",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss memorandum",
            markdown="Before.\n\n" + first_source_excerpt + "\n\nAfter.",
        ),
        _LlmDocument(
            candidate_id="72270301",
            source_document_id="468614730",
            document_role=DocumentRole.REPLY,
            docket_entry_number=9,
            description="Reply memorandum",
            markdown="Before.\n\n" + second_source_excerpt + "\n\nAfter.",
        ),
    ]
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["478193908", "468614730"],
        "explanation": "The sources identify a separately challenged theory.",
        "citation_excerpt": (
            "The first memorandum explains that Plaintiff's initial theory fails "
            "as a matter of law. ... The reply further explains that the remaining "
            "alternative theory is independently barred."
        ),
    }

    with pytest.raises(LlmResponseValidationError, match="does not appear"):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=documents,
            response=_response(),
        )

    [validated] = validate_structural_review_flags(
        {"structural_flags": [flag]},
        units=[_unit()],
        documents=documents,
        response=_response(),
        allow_composite_citations=True,
    )

    assert validated["citation_excerpt"] == (
        first_source_excerpt + " ... " + second_source_excerpt
    )


@pytest.mark.parametrize(
    ("citation_excerpt", "source_document_ids"),
    [
        (
            "short ... The reply further explains that the remaining alternative "
            "theory is independently barred.",
            ["478193908", "468614730"],
        ),
        (
            "The first memorandum explains that Plaintiff's initial theory fails "
            "as a matter of law. ...  ... The reply further explains that the "
            "remaining alternative theory is independently barred.",
            ["478193908", "468614730", "478193908"],
        ),
        (
            "The first memorandum explains that Plaintiff's initial theory fails "
            "as a matter of law. ... The reply further explains that the remaining "
            "alternative theory is independently barred. ... An uncited third passage.",
            ["478193908", "468614730"],
        ),
        (
            "the first memorandum explains that Plaintiff's initial theory fails "
            "as a matter of law. ... The reply further explains that the remaining "
            "alternative theory is independently barred.",
            ["478193908", "468614730"],
        ),
        (
            "The first memorandum explains that Plaintiff's initial-theory fails "
            "as a matter of law. ... The reply further explains that the remaining "
            "alternative theory is independently barred.",
            ["478193908", "468614730"],
        ),
        (
            "The first memorandum explains that Plaintiff's initial theory fails "
            "as a matter of law. ... The reply further explains that the remaining "
            "alternative theory is independently barred.",
            ["468614730", "478193908"],
        ),
        (
            "The first memorandum explains that Plaintiff's initial theory fails "
            "as a matter of law. ... A wholly unsupported second passage appears here.",
            ["478193908", "468614730"],
        ),
    ],
)
def test_structural_citation_rejects_invalid_multidocument_composite(
    citation_excerpt: str,
    source_document_ids: list[str],
) -> None:
    documents = [
        _LlmDocument(
            candidate_id="72270301",
            source_document_id="478193908",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss memorandum",
            markdown=(
                "short\n\nThe first memorandum explains that Plaintiff\u2019s initial "
                "theory fails as a matter of law."
            ),
        ),
        _LlmDocument(
            candidate_id="72270301",
            source_document_id="468614730",
            document_role=DocumentRole.REPLY,
            docket_entry_number=9,
            description="Reply memorandum",
            markdown=(
                "The reply further explains that the remaining alternative theory "
                "is independently barred."
            ),
        ),
    ]
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": source_document_ids,
        "explanation": "The sources identify a separately challenged theory.",
        "citation_excerpt": citation_excerpt,
    }

    with pytest.raises(LlmResponseValidationError, match="citation_excerpt"):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=documents,
            response=_response(),
            allow_composite_citations=True,
        )


def test_ordinary_structural_validation_retains_multisource_single_slice_behavior() -> (
    None
):
    source_excerpt = (
        "The first memorandum explains that Plaintiff\u2019s initial theory fails "
        "... as a matter of law."
    )
    documents = [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="first",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss memorandum",
            markdown=source_excerpt,
        ),
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="second",
            document_role=DocumentRole.REPLY,
            docket_entry_number=9,
            description="Reply memorandum",
            markdown="A different predecision source.",
        ),
    ]
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["first", "second"],
        "explanation": "A separately challenged theory is absent.",
        "citation_excerpt": (
            "The first memorandum explains that Plaintiff's initial theory fails "
            "... as a matter of law."
        ),
    }

    [validated] = validate_structural_review_flags(
        {"structural_flags": [flag]},
        units=[_unit()],
        documents=documents,
        response=_response(),
    )

    assert validated["citation_excerpt"] == source_excerpt


@pytest.mark.parametrize(
    "citation_excerpt",
    [
        (
            "plaintiff's state law claims against Gage in his individual capacity "
            "are barred."
        ),
        (
            "Plaintiff's federal law claims against Gage in his individual capacity "
            "are barred."
        ),
        (
            "Plaintiff's state-law claims against Gage in his individual capacity "
            "are barred."
        ),
    ],
)
def test_structural_citation_rejects_non_equivalent_text(
    citation_excerpt: str,
) -> None:
    source_excerpt = (
        "Plaintiff\u2019s state law claims against Gage in his individual capacity "
        "are barred."
    )
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion"],
        "explanation": "A separately challenged theory is absent.",
        "citation_excerpt": citation_excerpt,
    }
    documents = [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="motion",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss",
            markdown=source_excerpt,
        )
    ]

    with pytest.raises(LlmResponseValidationError, match="does not appear"):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=documents,
            response=_response(),
        )
