from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.llm_pipeline import (
    STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    LlmResponseValidationError,
    _LlmDocument,
    merge_structural_flags_into_review_queue,
    reconstruct_stage_a_structural_review_response,
    stage_a_structural_flag_records,
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


def _authenticated_replay_inputs() -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, bytes],
]:
    selection: dict[str, object] = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "documents": [
            {
                "source_document_id": "motion",
                "document_role": DocumentRole.MTD_MEMORANDUM.value,
                "docket_entry_number": 4,
                "description": "Motion to dismiss",
                "contains_target_outcome": False,
                "model_visible": True,
            }
        ],
    }
    parser_records: list[dict[str, object]] = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "motion",
            "status": "succeeded",
            "markdown_path": "cand-1/motion.md",
        }
    ]
    prediction_unit_records = [{"candidate_id": "cand-1", **_unit().to_record()}]
    markdown_bytes = {
        "cand-1/motion.md": b"The Court should dismiss the alternative theory."
    }
    return selection, parser_records, prediction_unit_records, markdown_bytes


def _normalized_v4_structural_response(*, source_document_id: str = "motion") -> str:
    raw_output = {
        "structural_flags": [
            {
                "flag_type": "spurious",
                "affected_unit_ids": ["unit-1"],
                "evidence_spans": [
                    {
                        "source_document_id": source_document_id,
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
                "explanation": "Untimeliness is a ground, not a claim.",
            }
        ]
    }
    return json.dumps(
        {
            "raw_output": json.dumps(raw_output),
            "request_count": 1,
            "input_tokens": 10,
            "output_tokens": 5,
            "actual_cost_usd": 0.01,
        }
    )


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


def test_v4_flag_v2_and_queue_preserve_all_document_bound_evidence() -> None:
    evidence_spans = [
        {
            "source_document_id": "complaint",
            "document_role": "complaint",
            "start_line": 4,
            "end_line": 5,
            "citation_page": 2,
            "citation_excerpt": "Count II asserts breach of contract.",
        },
        {
            "source_document_id": "motion",
            "document_role": "motion_to_dismiss_memorandum",
            "start_line": 10,
            "end_line": 11,
            "citation_page": 4,
            "citation_excerpt": "Count II should be dismissed.",
        },
    ]
    [flag] = stage_a_structural_flag_records(
        candidate_id="cand-1",
        case_id="case-1",
        reviewer_model_key="google:gemini-flash",
        model_registry_sha256="registry-hash",
        raw_prediction_units_sha256="raw-hash",
        structural_flags=[
            {
                "flag_type": "omitted",
                "affected_unit_ids": ["unit-1"],
                "source_document_ids": ["complaint", "motion"],
                "explanation": "A separately challenged count is absent.",
                "citation_excerpt": "Count II asserts breach of contract.",
                "evidence_spans": evidence_spans,
            }
        ],
    )

    assert flag["schema_version"] == "legalforecast.stage_a_structural_flag.v2"
    [queued] = merge_structural_flags_into_review_queue([], [flag])
    assert queued["review_item"]["source_document_ids"] == [
        "complaint",
        "motion",
    ]
    assert queued["review_item"]["evidence_spans"] == evidence_spans


def test_structural_reviewer_accepts_spurious_nonunit_flag() -> None:
    [flag] = validate_structural_review_flags(
        {
            "structural_flags": [
                {
                    "flag_type": "spurious",
                    "affected_unit_ids": ["unit-1"],
                    "source_document_ids": ["motion"],
                    "explanation": "Untimeliness is a ground, not a claim.",
                    "citation_excerpt": "dismiss the alternative theory",
                }
            ]
        },
        units=[_unit()],
        documents=_documents(),
        response=_response(),
    )

    assert flag["flag_type"] == "spurious"


def test_v3_structural_reviewer_requires_one_cited_document() -> None:
    flag: dict[str, Any] = {
        "flag_type": "spurious",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion", "motion"],
        "explanation": "Untimeliness is a ground, not a claim.",
        "citation_excerpt": "dismiss the alternative theory",
    }

    validate_structural_review_flags(
        {"structural_flags": [flag]},
        units=[_unit()],
        documents=_documents(),
        response=_response(),
    )
    with pytest.raises(LlmResponseValidationError, match="exactly one"):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=_documents(),
            response=_response(),
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
        )


def test_v4_structural_reviewer_reconstructs_exact_line_span() -> None:
    [flag] = validate_structural_review_flags(
        {
            "structural_flags": [
                {
                    "flag_type": "spurious",
                    "affected_unit_ids": ["unit-1"],
                    "evidence_spans": [
                        {
                            "source_document_id": "motion",
                            "start_line": 1,
                            "end_line": 1,
                        }
                    ],
                    "explanation": "Untimeliness is a ground, not a claim.",
                }
            ]
        },
        units=[_unit()],
        documents=_documents(),
        response=_response(),
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    )

    assert flag["source_document_ids"] == ["motion"]
    assert flag["evidence_spans"] == [
        {
            "source_document_id": "motion",
            "document_role": "motion_to_dismiss_memorandum",
            "start_line": 1,
            "end_line": 1,
            "citation_page": None,
            "citation_excerpt": "The Court should dismiss the alternative theory.",
        }
    ]
    assert flag["citation_excerpt"] == (
        "The Court should dismiss the alternative theory."
    )


def test_v4_structural_response_replay_reconstructs_from_normalized_raw_output(
    tmp_path: Path,
) -> None:
    selection, parser_records, units, markdown_bytes = _authenticated_replay_inputs()

    [flag] = reconstruct_stage_a_structural_review_response(
        selection_record=selection,
        parser_records=parser_records,
        prediction_unit_records=units,
        markdown_root=tmp_path,
        markdown_bytes=markdown_bytes,
        normalized_response_json=_normalized_v4_structural_response(),
    )

    assert flag["source_document_ids"] == ["motion"]
    assert flag["citation_excerpt"] == (
        "The Court should dismiss the alternative theory."
    )


def test_v4_structural_response_replay_rejects_tampered_raw_selector(
    tmp_path: Path,
) -> None:
    selection, parser_records, units, markdown_bytes = _authenticated_replay_inputs()

    with pytest.raises(LlmResponseValidationError, match="supplied predecision"):
        reconstruct_stage_a_structural_review_response(
            selection_record=selection,
            parser_records=parser_records,
            prediction_unit_records=units,
            markdown_root=tmp_path,
            markdown_bytes=markdown_bytes,
            normalized_response_json=_normalized_v4_structural_response(
                source_document_id="invented"
            ),
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"source_document_id": "invented"}, "supplied predecision"),
        ({"start_line": 2, "end_line": 2}, "outside the source document"),
        ({"start_line": 1, "end_line": 13}, "outside the source document"),
    ],
)
def test_v4_structural_reviewer_rejects_invalid_line_spans(
    override: dict[str, object], message: str
) -> None:
    flag: dict[str, object] = {
        "flag_type": "spurious",
        "affected_unit_ids": ["unit-1"],
        "evidence_spans": [
            {
                "source_document_id": "motion",
                "start_line": 1,
                "end_line": 1,
                **override,
            }
        ],
        "explanation": "Untimeliness is a ground, not a claim.",
    }

    with pytest.raises(LlmResponseValidationError, match=message):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=_documents(),
            response=_response(),
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
        )


def test_v4_omitted_flag_requires_complaint_and_target_motion_evidence() -> None:
    documents = [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="complaint",
            document_role=DocumentRole.COMPLAINT,
            docket_entry_number=1,
            description="Complaint",
            markdown="Count II asserts breach of contract.",
        ),
        *_documents(),
    ]
    raw_flag = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "evidence_spans": [
            {
                "source_document_id": "complaint",
                "start_line": 1,
                "end_line": 1,
            },
            {
                "source_document_id": "motion",
                "start_line": 1,
                "end_line": 1,
            },
        ],
        "explanation": "The separately challenged contract count is absent.",
    }

    [flag] = validate_structural_review_flags(
        {"structural_flags": [raw_flag]},
        units=[_unit()],
        documents=documents,
        response=_response(),
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    )

    assert flag["source_document_ids"] == ["complaint", "motion"]
    assert [span["document_role"] for span in flag["evidence_spans"]] == [
        "complaint",
        "motion_to_dismiss_memorandum",
    ]


@pytest.mark.parametrize(
    ("evidence_spans", "message"),
    [
        (
            [{"source_document_id": "motion", "start_line": 1, "end_line": 1}],
            "complaint or amended-complaint",
        ),
        (
            [
                {
                    "source_document_id": "complaint",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            "target motion-to-dismiss",
        ),
        (
            [
                {
                    "source_document_id": "motion",
                    "start_line": 1,
                    "end_line": 1,
                },
                {
                    "source_document_id": "motion",
                    "start_line": 1,
                    "end_line": 1,
                },
            ],
            "unique document ids",
        ),
    ],
)
def test_v4_omitted_flag_rejects_incomplete_or_duplicate_evidence(
    evidence_spans: list[dict[str, object]], message: str
) -> None:
    documents = [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="complaint",
            document_role=DocumentRole.COMPLAINT,
            docket_entry_number=1,
            description="Complaint",
            markdown="Count II asserts breach of contract.",
        ),
        *_documents(),
    ]

    with pytest.raises(LlmResponseValidationError, match=message):
        validate_structural_review_flags(
            {
                "structural_flags": [
                    {
                        "flag_type": "omitted",
                        "affected_unit_ids": ["unit-1"],
                        "evidence_spans": evidence_spans,
                        "explanation": "The contract count is absent.",
                    }
                ]
            },
            units=[_unit()],
            documents=documents,
            response=_response(),
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
        )


def test_structural_queue_order_is_canonical_across_flag_permutations() -> None:
    flags = [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "reviewer_model_key": "google:gemini-flash",
            "model_registry_sha256": "registry-hash",
            "raw_prediction_units_sha256": "raw-hash",
            "flag_sha256": digest * 64,
            "flag_type": "spurious",
            "affected_unit_ids": ["unit-1"],
            "source_document_ids": ["motion"],
            "explanation": f"Spurious unit {digest}.",
            "citation_excerpt": "dismiss the alternative theory",
        }
        for digest in ("a", "b")
    ]

    assert merge_structural_flags_into_review_queue([], flags) == (
        merge_structural_flags_into_review_queue([], reversed(flags))
    )


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


def test_structural_citation_rejects_composite_ellipsis_quote() -> None:
    documents = [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="motion",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss",
            markdown="First factual proposition. Second factual proposition.",
        )
    ]
    flag: dict[str, Any] = {
        "flag_type": "omitted",
        "affected_unit_ids": ["unit-1"],
        "source_document_ids": ["motion"],
        "explanation": "A separately challenged theory is absent.",
        "citation_excerpt": "First factual proposition ... Second factual proposition.",
    }

    with pytest.raises(LlmResponseValidationError, match="does not appear"):
        validate_structural_review_flags(
            {"structural_flags": [flag]},
            units=[_unit()],
            documents=documents,
            response=_response(),
        )
