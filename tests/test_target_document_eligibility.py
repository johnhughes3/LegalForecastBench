"""Tests for semantic Stage A target-document eligibility."""

import pytest
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.target_document_eligibility import (
    TargetDocumentEligibilityError,
    is_stipulated_or_voluntary_target_document,
)


def test_stipulation_predicate_rejects_unsupported_document_role() -> None:
    """Invalid roles are input errors, not evidence of a stipulation."""

    with pytest.raises(
        TargetDocumentEligibilityError,
        match="unsupported target document role: unsupported_role",
    ):
        is_stipulated_or_voluntary_target_document(
            candidate_id="candidate",
            source_document_id="document",
            document_role="unsupported_role",
            markdown="[Proposed] Stipulation for Dismissal",
        )


def test_stipulation_predicate_returns_true_for_stipulated_target_document() -> None:
    assert is_stipulated_or_voluntary_target_document(
        candidate_id="candidate",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown="[Proposed] Stipulation of Dismissal",
    )


def test_stipulation_predicate_returns_false_for_ordinary_target_document() -> None:
    assert not is_stipulated_or_voluntary_target_document(
        candidate_id="candidate",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown="Memorandum in Support of Motion to Dismiss",
    )
