"""Tests for provider-free terminal Stage A unitizer attorney review."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from legalforecast.unitization.review import canonical_sha256
from legalforecast.unitization.unitizer_terminal_review import (
    UnitizerTerminalReviewError,
    build_unitizer_terminal_review_bundle,
    build_unitizer_terminal_review_queue_record,
)

JsonRecord = dict[str, Any]


def _prefixed_sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _receipt() -> JsonRecord:
    receipt: JsonRecord = {
        "schema_version": "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "unitizer_model_key": "anthropic:unitizer",
        "model_registry_sha256": "a" * 64,
        "provider_attempt_namespace": "claim-ontology-v5",
        "prompt": "Use only the supplied predecision sources.",
        "prompt_sha256": hashlib.sha256(
            b"Use only the supplied predecision sources."
        ).hexdigest(),
        "predecision_source_commitments": [
            {
                "source_document_id": "complaint",
                "document_role": "complaint",
                "docket_entry_number": 1,
                "description": "Complaint",
                "markdown_sha256": _prefixed_sha("Complaint text"),
            },
            {
                "source_document_id": "motion",
                "document_role": "motion_to_dismiss_memorandum",
                "docket_entry_number": 8,
                "description": "Motion to dismiss",
                "markdown_sha256": _prefixed_sha("Motion text"),
            },
        ],
        "failed_attempts": [
            {
                "attempt_ordinal": ordinal,
                "raw_response_sha256": _prefixed_sha(f"raw-{ordinal}"),
                "normalized_response_sha256": _prefixed_sha(f"normalized-{ordinal}"),
                "failure_type": "LlmResponseValidationError",
                "failure_message": "required complaint-role citation is absent",
            }
            for ordinal in (1, 2, 3)
        ],
    }
    return receipt


def _sources() -> list[JsonRecord]:
    return [
        {
            "source_document_id": "complaint",
            "document_role": "complaint",
            "docket_entry_number": 1,
            "description": "Complaint",
            "markdown": "Complaint text",
        },
        {
            "source_document_id": "motion",
            "document_role": "motion_to_dismiss_memorandum",
            "docket_entry_number": 8,
            "description": "Motion to dismiss",
            "markdown": "Motion text",
        },
    ]


def test_terminal_queue_is_candidate_level_and_offers_only_executable_actions() -> None:
    receipt = _receipt()

    item = build_unitizer_terminal_review_queue_record(receipt)

    digest = canonical_sha256(receipt)
    assert item == {
        "schema_version": "legalforecast.unitizer_terminal_review_queue.v1",
        "status": "pending_adjudication",
        "review_id": f"candidate-1:unitizer-terminal:{digest[:16]}",
        "review_subject": "candidate",
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "reason": {
            "code": "unitizer_terminal_reconstruction_failure",
            "class": "technical",
            "summary": (
                "Stage A unitization exhausted its authenticated reconstruction "
                "attempts without producing accepted prediction units."
            ),
        },
        "allowed_actions": ["ADD", "CANDIDATE-EXCLUSION"],
        "suggested_actions": [],
        "terminal_escalation_sha256": digest,
        "review_item": {
            "unitizer_model_key": "anthropic:unitizer",
            "model_registry_sha256": "a" * 64,
            "provider_attempt_namespace": "claim-ontology-v5",
            "prompt_sha256": receipt["prompt_sha256"],
            "predecision_source_document_ids": ["complaint", "motion"],
            "predecision_source_commitments": receipt["predecision_source_commitments"],
            "attempt_commitments": receipt["failed_attempts"],
            "notes": (
                "No prediction unit or legal conclusion was accepted from the "
                "failed responses. Review the authenticated predecision sources."
            ),
        },
    }
    assert "prompt" not in item["review_item"]
    assert "prediction_units" not in item


def test_terminal_queue_rejects_tampered_or_nonterminal_receipts() -> None:
    for mutate, message in (
        (lambda receipt: receipt.update(schema_version="invented"), "schema"),
        (lambda receipt: receipt.update(failed_attempts=[]), "failed attempt"),
        (
            lambda receipt: receipt["failed_attempts"][0].update(
                raw_response_sha256="bad"
            ),
            "SHA-256",
        ),
        (
            lambda receipt: receipt["predecision_source_commitments"].append(
                dict(receipt["predecision_source_commitments"][0])
            ),
            "source_document_id",
        ),
    ):
        receipt = _receipt()
        mutate(receipt)
        with pytest.raises(UnitizerTerminalReviewError, match=message):
            build_unitizer_terminal_review_queue_record(receipt)


def test_terminal_bundle_authenticates_every_predecision_source() -> None:
    receipt = _receipt()
    queue_item = build_unitizer_terminal_review_queue_record(receipt)

    bundle = build_unitizer_terminal_review_bundle(
        receipt=receipt,
        queue_record=queue_item,
        predecision_sources=_sources(),
    )

    assert bundle["schema_version"] == (
        "legalforecast.unitizer_terminal_review_bundle.v1"
    )
    assert bundle["review_id"] == queue_item["review_id"]
    assert bundle["terminal_escalation_sha256"] == canonical_sha256(receipt)
    assert bundle["review_item"] == queue_item["review_item"]
    assert bundle["allowed_actions"] == ["ADD", "CANDIDATE-EXCLUSION"]
    assert [
        source["source_document_id"] for source in bundle["cited_predecision_markdown"]
    ] == ["complaint", "motion"]
    assert bundle["cited_predecision_markdown"][0]["markdown"] == "Complaint text"


def test_terminal_bundle_fails_closed_on_source_or_queue_drift() -> None:
    receipt = _receipt()
    queue_item = build_unitizer_terminal_review_queue_record(receipt)
    bad_sources = _sources()
    bad_sources[0]["markdown"] = "Changed"
    with pytest.raises(UnitizerTerminalReviewError, match="markdown commitment"):
        build_unitizer_terminal_review_bundle(
            receipt=receipt,
            queue_record=queue_item,
            predecision_sources=bad_sources,
        )

    missing_sources = _sources()[1:]
    with pytest.raises(UnitizerTerminalReviewError, match="source coverage"):
        build_unitizer_terminal_review_bundle(
            receipt=receipt,
            queue_record=queue_item,
            predecision_sources=missing_sources,
        )

    tampered_queue = dict(queue_item)
    tampered_queue["allowed_actions"] = ["CANDIDATE-EXCLUSION"]
    with pytest.raises(UnitizerTerminalReviewError, match="queue record"):
        build_unitizer_terminal_review_bundle(
            receipt=receipt,
            queue_record=tampered_queue,
            predecision_sources=_sources(),
        )


@pytest.mark.parametrize("role", ("decision", "order", "other", "judgment"))
def test_terminal_bundle_rejects_nonallowlisted_material_even_if_committed(
    role: str,
) -> None:
    receipt = _receipt()
    receipt["predecision_source_commitments"][0].update(
        document_role=role,
        description="Order",
    )
    sources = _sources()
    sources[0].update(document_role=role, description="Order")
    queue_item = build_unitizer_terminal_review_queue_record(receipt)

    with pytest.raises(UnitizerTerminalReviewError, match="predecision"):
        build_unitizer_terminal_review_bundle(
            receipt=receipt,
            queue_record=queue_item,
            predecision_sources=sources,
        )
