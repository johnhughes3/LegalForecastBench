"""Tests for semantic Stage A target-document eligibility."""

from typing import TypedDict

import pytest
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.target_document_eligibility import (
    TargetDocumentEligibilityError,
    is_stipulated_or_voluntary_target_document,
)


class _NqrFixture(TypedDict):
    candidate_id: str
    generated_by: str
    markdown: str
    synthetic: bool


_NQR_RECURRENCE_FIXTURES: tuple[_NqrFixture, ...] = (
    {
        "candidate_id": "68941639",
        "generated_by": (
            "hand-authored from authenticated source quotations; no provider "
            "generation command"
        ),
        "markdown": """# STIPULATION TO DISMISS

        IT IS HEREBY STIPULATED AND AGREED by and between the parties that
        the above-entitled action is voluntarily dismissed, with prejudice.
        """,
        "synthetic": True,
    },
    {
        "candidate_id": "73209444",
        "generated_by": (
            "hand-authored from authenticated source quotations; no provider "
            "generation command"
        ),
        "markdown": """# PLAINTIFF'S MOTION TO DISMISS WITH PREJUDICE

        Plaintiff moves to dismiss this action. The parties have reached a
        full and final settlement resolving all claims, and a written
        Settlement Agreement and Mutual Release was executed.
        """,
        "synthetic": True,
    },
    {
        "candidate_id": "73325674",
        "generated_by": (
            "hand-authored from authenticated source quotations; no provider "
            "generation command"
        ),
        "markdown": """# MOTION TO DISMISS

        Plaintiff moves to dismiss. The parties have resolved this matter,
        entered a confidential release, and move to separate and dismiss
        the claims against this defendant.
        """,
        "synthetic": True,
    },
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


@pytest.mark.parametrize(
    "fixture",
    _NQR_RECURRENCE_FIXTURES,
    ids=[fixture["candidate_id"] for fixture in _NQR_RECURRENCE_FIXTURES],
)
def test_nqr_recurrence_regressions_are_ineligible(fixture: _NqrFixture) -> None:
    """Synthetic excerpts preserve the three independently observed NQR shapes."""

    assert fixture["synthetic"] is True
    assert fixture["generated_by"].endswith("no provider generation command")
    assert is_stipulated_or_voluntary_target_document(
        candidate_id=fixture["candidate_id"],
        source_document_id=f"{fixture['candidate_id']}-target",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=fixture["markdown"],
    )


def test_contested_motion_that_mentions_settlement_remains_eligible() -> None:
    assert not is_stipulated_or_voluntary_target_document(
        candidate_id="contested",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "Defendant's contested Motion to Dismiss argues the claims fail. "
            "Plaintiff disputes liability and reports that settlement negotiations "
            "did not resolve the case."
        ),
    )


def test_contested_motion_based_on_settlement_release_remains_eligible() -> None:
    assert not is_stipulated_or_voluntary_target_document(
        candidate_id="contested-release",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "Defendant's contested Motion to Dismiss argues that Plaintiff's "
            "claims are barred by a prior Settlement Agreement and Mutual Release. "
            "Plaintiff opposes the motion and disputes the release's scope."
        ),
    )


def test_plural_plaintiffs_settlement_dismissal_is_ineligible() -> None:
    assert is_stipulated_or_voluntary_target_document(
        candidate_id="plural-plaintiffs",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "# PLAINTIFFS' MOTION TO DISMISS\n\n"
            "Plaintiffs move to dismiss this action because they settled their "
            "claims with Defendant."
        ),
    )


def test_joint_agreement_to_dismiss_needs_no_second_dismissal_token() -> None:
    assert is_stipulated_or_voluntary_target_document(
        candidate_id="joint-dismissal",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "# MOTION TO DISMISS\n\n"
            "The parties have resolved the matter and agreed to dismiss it with "
            "prejudice."
        ),
    )


def test_defendant_motion_enforcing_prior_settlement_remains_eligible() -> None:
    assert not is_stipulated_or_voluntary_target_document(
        candidate_id="contested-prior-settlement",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "# DEFENDANT'S MOTION TO DISMISS\n\n"
            "The parties executed a Settlement Agreement and Mutual Release. "
            "Defendant moves to dismiss because that prior release bars Plaintiff's "
            "claims. Plaintiff contests the release's validity."
        ),
    )


def test_defendant_motion_quoting_plaintiff_dismissal_remains_eligible() -> None:
    assert not is_stipulated_or_voluntary_target_document(
        candidate_id="contested-quoted-dismissal",
        source_document_id="document",
        document_role=DocumentRole.MTD_MEMORANDUM,
        markdown=(
            "# DEFENDANT'S MOTION TO DISMISS\n\n"
            "Defendant moves to dismiss for failure to state a claim. The motion "
            "quotes another filing: 'Plaintiff moves to dismiss a related action "
            "after a settlement.' That procedural history does not resolve this "
            "contested motion."
        ),
    )
