from __future__ import annotations

import hashlib
import json

from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.llm_pipeline import (
    STAGE_A_CLAIM_ONTOLOGY_V2_PROMPT_CONTRACT,
    STAGE_A_CLAIM_ONTOLOGY_V3_PROMPT_CONTRACT,
    _LlmDocument,
    _stage_a_seed,
    _stage_a_structural_review_prompt,
    _stage_a_structural_review_response_json_schema,
    _unitization_prompt,
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
