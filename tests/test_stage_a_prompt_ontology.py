from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.target_document_eligibility import (
    TargetDocumentIneligibilityReason,
    evaluate_target_document_eligibility,
)
from legalforecast.labeling.llm_pipeline import (
    STAGE_A_CLAIM_ONTOLOGY_V2_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    LlmPipelineError,
    _document_line_span,
    _LlmDocument,
    _predecision_documents,
    _require_eligible_stage_a_target_document,
    _stage_a_seed,
    _stage_a_structural_review_prompt,
    _stage_a_structural_review_response_json_schema,
    _unitization_prompt,
    stage_a_unitization_prompt_records,
)
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation


def _selection() -> dict[str, object]:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "Plaintiff v. Defendant",
        "court": "Example District Court",
        "docket_number": "1:26-cv-1",
        "target_motion_entry_numbers": [4],
        "decision_entry_numbers": [9],
    }


def _documents() -> list[_LlmDocument]:
    return [
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="complaint",
            document_role=DocumentRole.COMPLAINT,
            docket_entry_number=1,
            description="Complaint",
            markdown="Count I asserts retaliation against Defendant.",
        ),
        _LlmDocument(
            candidate_id="cand-1",
            source_document_id="motion",
            document_role=DocumentRole.MTD_MEMORANDUM,
            docket_entry_number=4,
            description="Motion to dismiss",
            markdown="Defendant moves to dismiss Count I as untimely.",
        ),
    ]


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="unit-1",
        count="Count I",
        claim_name="Retaliation",
        defendant_group="Defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint"),),
    )


def _rules(prompt: str) -> str:
    return " ".join(json.loads(prompt)["rules"])


def test_unitizer_prompt_defines_claim_ground_boundary() -> None:
    rules = _rules(_unitization_prompt(_selection(), _documents()))

    assert "independently enforceable legal right" in rules
    assert "never itself a prediction unit" in rules
    assert "Section 230" in rules
    assert "SLUSA" in rules
    assert "partial_theory_only" in rules
    assert "actual moving defendant" in rules
    assert "nonmoving defendant" in rules
    assert "remedy" in rules


def test_unitizer_prompt_preserves_legacy_bytes_before_v4() -> None:
    legacy = _unitization_prompt(_selection(), _documents())
    v2 = _unitization_prompt(
        _selection(),
        _documents(),
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V2_PROMPT_CONTRACT,
    )
    v3 = _unitization_prompt(
        _selection(),
        _documents(),
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
    )

    assert legacy == v2 == v3
    assert hashlib.sha256(legacy.encode("utf-8")).hexdigest() == (
        "d63b6bba6068f68fc5aba55106598fcd502f30bc5a313f315e4a711c12f046df"
    )


def test_v4_unitizer_uses_purported_claims_and_line_selectors() -> None:
    prompt = _unitization_prompt(
        _selection(),
        _documents(),
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    )
    payload = json.loads(prompt)
    rules = " ".join(payload["rules"])

    assert "independently enforceable legal right" not in rules
    assert "purports to assert" in rules
    assert "no cause of action exists" in rules
    assert "Opposition abandonment" in rules
    assert "willfulness" in rules
    assert "numbered_markdown" in payload["documents"][0]
    assert "markdown" not in payload["documents"][0]
    assert payload["documents"][0]["numbered_markdown"].startswith("L000001\t")
    schema = payload["output_schema"]["unit_seeds"][0]
    assert "source_citations" in schema
    assert "citation_excerpt" not in schema
    assert "scope" in schema
    assert "challenge_scope" not in schema


@pytest.mark.parametrize(
    "markdown",
    [
        "# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL",
        "# STIPULATED MOTION TO DISMISS",
        ("The parties agree to dismiss all claims under Rule 41(a)(1)(A)(ii)."),
    ],
)
def test_stage_a_rejects_mislabeled_stipulated_target_body(markdown: str) -> None:
    document = _LlmDocument(
        candidate_id="cand-1",
        source_document_id="motion",
        document_role=DocumentRole.MTD_MEMORANDUM,
        docket_entry_number=4,
        description="Motion to dismiss",
        markdown=markdown,
    )

    with pytest.raises(LlmPipelineError, match="stipulated or voluntary"):
        _require_eligible_stage_a_target_document(document)


def test_stage_a_target_body_gate_does_not_reject_rule_41_argument() -> None:
    document = _LlmDocument(
        candidate_id="cand-1",
        source_document_id="motion",
        document_role=DocumentRole.MTD_MEMORANDUM,
        docket_entry_number=4,
        description="Motion to dismiss",
        markdown=(
            "# Memorandum in Support of Motion to Dismiss\n"
            "Plaintiff cannot rely on Rule 41(a)(1)(A)(ii) after an answer."
        ),
    )

    _require_eligible_stage_a_target_document(document)


def test_target_document_eligibility_distinguishes_69736298_shape() -> None:
    """A genuine contested MTD must not be confused with proposed dismissal text."""

    contested_mtd = evaluate_target_document_eligibility(
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "# Defendant's Motion to Dismiss\n"
            "Defendant moves under Rule 12(b)(6) to dismiss the complaint.\n"
            "Plaintiff cannot rely on Rule 41(a)(1)(A)(ii) after an answer."
        ),
    )
    proposed_dismissal = evaluate_target_document_eligibility(
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown="# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n",
    )
    rule_41_stipulation = evaluate_target_document_eligibility(
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "The parties agree to dismiss all claims under Rule 41(a)(1)(A)(ii)."
        ),
    )

    assert contested_mtd.is_eligible
    assert contested_mtd.reason is None
    assert not proposed_dismissal.is_eligible
    assert (
        proposed_dismissal.reason
        is TargetDocumentIneligibilityReason.STIPULATED_OR_VOLUNTARY_DISMISSAL_TITLE
    )
    assert not rule_41_stipulation.is_eligible
    assert (
        rule_41_stipulation.reason
        is TargetDocumentIneligibilityReason.RULE_41_A_1_A_II_STIPULATION
    )


def test_stipulated_target_body_gate_is_v4_only(tmp_path: Path) -> None:
    markdown = tmp_path / "motion.md"
    markdown.write_text(
        "# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n",
        encoding="utf-8",
    )
    selection = {
        **_selection(),
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
    parser_by_key = {
        ("cand-1", "motion"): {
            "candidate_id": "cand-1",
            "source_document_id": "motion",
            "status": "succeeded",
            "markdown_path": markdown.name,
        }
    }

    legacy = _predecision_documents(
        selection,
        parser_by_key=parser_by_key,
        markdown_root=tmp_path,
    )
    assert legacy[0].markdown.startswith("# [PROPOSED]")
    with pytest.raises(LlmPipelineError, match="stipulated or voluntary"):
        _predecision_documents(
            selection,
            parser_by_key=parser_by_key,
            markdown_root=tmp_path,
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
        )

    [identity_only_prompt] = stage_a_unitization_prompt_records(
        selection_records=[selection],
        parser_records=list(parser_by_key.values()),
        markdown_root=tmp_path,
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
        enforce_target_document_eligibility=False,
    )
    assert identity_only_prompt["prompt_sha256"].startswith("sha256:")


def test_structural_reviewer_prompt_uses_same_claim_ground_boundary() -> None:
    rules = _rules(
        _stage_a_structural_review_prompt(_selection(), _documents(), [_unit()])
    )

    assert "claim-defendant ledger" in rules
    assert "motion-scope matrix" in rules
    assert "never itself a prediction unit" in rules
    assert "independently enforceable legal right" in rules
    assert "nonmoving defendant" in rules


def test_structural_reviewer_prompt_requires_one_contiguous_citation_span() -> None:
    rules = _rules(
        _stage_a_structural_review_prompt(
            _selection(),
            _documents(),
            [_unit()],
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
        )
    )

    assert "one contiguous literal span" in rules
    assert "Never use an ellipsis" in rules
    assert "Never join fragments" in rules
    assert "Never paraphrase" in rules


def test_v4_structural_reviewer_uses_purported_claims_and_line_selectors() -> None:
    prompt = _stage_a_structural_review_prompt(
        _selection(),
        _documents(),
        [_unit()],
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    )
    payload = json.loads(prompt)
    rules = " ".join(payload["rules"])

    assert "independently enforceable legal right" not in rules
    assert "purported claim" in rules
    assert "no-cause-of-action is a dismissal ground" in rules
    assert "induced infringement and contributory infringement" in rules
    assert "Willfulness is ordinarily an enhancement" in rules
    assert "source_document_id" in payload["output_schema"]["structural_flags"][0]
    assert "citation_excerpt" not in payload["output_schema"]["structural_flags"][0]
    assert "numbered_markdown" in payload["documents"][0]


def test_structural_reviewer_prompt_preserves_v2_bytes_and_versions_v3_delta() -> None:
    legacy = _stage_a_structural_review_prompt(_selection(), _documents(), [_unit()])
    v2 = _stage_a_structural_review_prompt(
        _selection(),
        _documents(),
        [_unit()],
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V2_PROMPT_CONTRACT,
    )
    v3 = _stage_a_structural_review_prompt(
        _selection(),
        _documents(),
        [_unit()],
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
    )

    assert legacy == v2
    assert hashlib.sha256(v2.encode("utf-8")).hexdigest() == (
        "11bc410b477fe5d33efae9363dadfd46805eadf6b000aa330216f0f7d77ffb32"
    )
    assert v3 != v2
    assert "one contiguous literal span" not in _rules(v2)
    assert "one contiguous literal span" in _rules(v3)


def test_structural_reviewer_response_schema_is_bound_to_frozen_inputs() -> None:
    schema = _stage_a_structural_review_response_json_schema(_documents(), [_unit()])
    item = schema["properties"]["structural_flags"]["items"]

    assert schema["required"] == ["structural_flags"]
    assert schema["additionalProperties"] is False
    assert item["additionalProperties"] is False
    assert item["required"] == [
        "flag_type",
        "affected_unit_ids",
        "source_document_ids",
        "explanation",
        "citation_excerpt",
    ]
    assert item["properties"]["affected_unit_ids"]["items"]["enum"] == ["unit-1"]
    assert item["properties"]["source_document_ids"]["items"]["enum"] == [
        "complaint",
        "motion",
    ]
    assert item["properties"]["source_document_ids"]["minItems"] == 1
    assert item["properties"]["source_document_ids"]["maxItems"] == 1


def test_v4_structural_response_schema_uses_document_line_span() -> None:
    schema = _stage_a_structural_review_response_json_schema(
        _documents(),
        [_unit()],
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    )
    item = schema["properties"]["structural_flags"]["items"]

    assert item["required"] == [
        "flag_type",
        "affected_unit_ids",
        "explanation",
        "source_document_id",
        "start_line",
        "end_line",
    ]
    assert "source_document_ids" not in item["properties"]
    assert "citation_excerpt" not in item["properties"]
    assert item["properties"]["source_document_id"]["enum"] == [
        "complaint",
        "motion",
    ]


def test_v4_provider_seed_reconstructs_document_bound_citations() -> None:
    seed = _stage_a_seed(
        {
            "count": "Count I",
            "claim_name": "Retaliation",
            "defendant_names": ["Acme Corp."],
            "source_citations": [
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
            "challenged_by_motion": True,
            "scope": {"kind": "entire_claim"},
            "unit_confidence": 0.9,
            "grouping": "individual",
        },
        documents=_documents(),
        provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
    )

    assert seed.source_document_ids == ("complaint", "motion")
    assert seed.citation_excerpt is None
    assert seed.source_citations is not None
    assert [citation.excerpt for citation in seed.source_citations] == [
        "Count I asserts retaliation against Defendant.",
        "Defendant moves to dismiss Count I as untimely.",
    ]


def test_v4_line_span_preserves_source_line_endings_and_reads_bare_page_marker() -> (
    None
):
    document = _LlmDocument(
        candidate_id="cand-1",
        source_document_id="motion",
        document_role=DocumentRole.MTD_MEMORANDUM,
        docket_entry_number=4,
        description="Motion to dismiss",
        markdown="Page 2 of 2\r\nFirst cited line.\r\nSecond cited line.\r\n",
    )

    excerpt, page = _document_line_span(document, start_line=2, end_line=3)

    assert excerpt == "First cited line.\r\nSecond cited line."
    assert excerpt in document.markdown
    assert page == 2


@pytest.mark.parametrize(
    ("source_citations", "message"),
    [
        (
            [
                {
                    "source_document_id": "invented",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            "supplied predecision",
        ),
        (
            [
                {
                    "source_document_id": "complaint",
                    "start_line": 2,
                    "end_line": 2,
                }
            ],
            "outside the source document",
        ),
        (
            [
                {
                    "source_document_id": "complaint",
                    "start_line": 1,
                    "end_line": 1,
                },
                {
                    "source_document_id": "complaint",
                    "start_line": 1,
                    "end_line": 1,
                },
            ],
            "duplicate citation",
        ),
        (
            [
                {
                    "source_document_id": "complaint",
                    "start_line": 1,
                    "end_line": 1,
                    "citation_excerpt": "model-authored text",
                }
            ],
            "unsupported fields",
        ),
    ],
)
def test_v4_provider_seed_rejects_invalid_line_selectors(
    source_citations: list[dict[str, object]], message: str
) -> None:
    with pytest.raises(LlmPipelineError, match=message):
        _stage_a_seed(
            {
                "count": "Count I",
                "claim_name": "Retaliation",
                "defendant_names": ["Acme Corp."],
                "source_citations": source_citations,
                "challenged_by_motion": True,
                "scope": {"kind": "entire_claim"},
                "unit_confidence": 0.9,
                "grouping": "individual",
            },
            documents=_documents(),
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
        )


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "entire_claim", "subclaim_name": "Retaliatory transfer"},
        {"kind": "separable_subclaim"},
        {"kind": "unclear", "reason": ""},
    ],
)
def test_v4_provider_seed_rejects_contradictory_scope_states(
    scope: dict[str, object],
) -> None:
    with pytest.raises(LlmPipelineError):
        _stage_a_seed(
            {
                "count": "Count I",
                "claim_name": "Retaliation",
                "defendant_names": ["Acme Corp."],
                "source_citations": [
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
                "challenged_by_motion": True,
                "scope": scope,
                "unit_confidence": 0.9,
                "grouping": "individual",
            },
            documents=_documents(),
            provider_attempt_namespace=STAGE_A_CLAIM_ONTOLOGY_V4_PROMPT_CONTRACT,
        )


def test_provider_seed_routes_individual_grouping_metadata_to_review() -> None:
    seed = _stage_a_seed(
        {
            "count": "Count I",
            "claim_name": "Retaliation",
            "defendant_names": ["Acme Corp."],
            "source_document_ids": ["complaint", "motion"],
            "challenged_by_motion": True,
            "challenge_scope": "entire_claim",
            "unit_confidence": 0.9,
            "grouping": "individual",
            "grouping_rationale": "Shared corporate status",
            "group_label": "Corporate defendants",
            "separable_subclaim": None,
            "uncertainty_notes": None,
        }
    )

    assert seed.group_label is None
    assert seed.grouping_rationale is None
    assert seed.challenge_scope is ChallengeScope.UNCLEAR
    assert seed.separable_subclaim is None
    assert seed.review_reason is not None


def test_provider_seed_normalizes_unchallenged_unit_before_review() -> None:
    seed = _stage_a_seed(
        {
            "count": "Count I",
            "claim_name": "Retaliation",
            "defendant_names": ["Acme Corp."],
            "source_document_ids": ["complaint", "motion"],
            "challenged_by_motion": False,
            "challenge_scope": "separable_subclaim",
            "unit_confidence": 0.9,
            "grouping": "individual",
            "grouping_rationale": None,
            "group_label": None,
            "separable_subclaim": "Retaliation theory",
            "uncertainty_notes": None,
        }
    )

    assert seed.challenged_by_motion is False
    assert seed.challenge_scope is ChallengeScope.UNCLEAR
    assert seed.separable_subclaim is None
    assert seed.review_reason is not None
    assert "not challenged by the target motion" in (seed.uncertainty_notes or "")
