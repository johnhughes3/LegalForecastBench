# pyright: reportPrivateUsage=false

"""Body-vs-role admission rules for the v2 document-body role validator.

The validator decides whether observed bytes can carry the role an approved
repair slot requested. v2 stops admitting an ``opposition`` or ``reply`` on a
single incidental keyword and recognizes the cohort-policy v3 fallback role
``other_claim_bearing_filing``.
"""

from __future__ import annotations

from legalforecast.ingestion.missing_document_successor import (
    project_missing_document_successor,
)
from tests.test_missing_document_successor import (
    _approval,
    _base_selection,
    _manifest_bytes,
    _observation,
)


def test_single_incidental_opposition_keyword_is_not_an_opposition_brief() -> None:
    """Role validator v2: the word alone is not evidence of a responsive brief."""

    manifest = _manifest_bytes()

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(
            _observation(
                markdown=(
                    "DECLARATION OF JANE ROE\nI have reviewed the opposition "
                    "filed in this matter and attach it as Exhibit A."
                )
            ),
        ),
    )

    assert len(result.inclusion_ledger) == 0
    assert "acquired_bytes_mismatch_requested_role" in [
        row["reason"] for row in result.exclusion_ledger
    ]


def test_single_incidental_reply_keyword_is_not_a_reply_brief() -> None:
    manifest = _manifest_bytes(role="reply")

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(
            _observation(
                requested_role="reply",
                markdown=(
                    "ORDER\nThe Court has received no reply from the parties "
                    "and sets a status conference."
                ),
            ),
        ),
    )

    assert len(result.inclusion_ledger) == 0
    assert "acquired_bytes_mismatch_requested_role" in [
        row["reason"] for row in result.exclusion_ledger
    ]


def test_captioned_reply_brief_is_still_admitted() -> None:
    manifest = _manifest_bytes(role="reply")

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(
            _observation(
                requested_role="reply",
                markdown=(
                    "REPLY MEMORANDUM IN FURTHER SUPPORT OF DEFENDANT'S "
                    "MOTION TO DISMISS"
                ),
            ),
        ),
    )

    assert len(result.inclusion_ledger) == 1
    assert result.inclusion_ledger[0]["admitted_role"] == "reply"
    assert result.inclusion_ledger[0]["role_validator_version"] == (
        "legalforecast.document_body_role_validator.v2"
    )


def test_other_claim_bearing_filing_role_is_wired_into_the_validator() -> None:
    manifest = _manifest_bytes(role="other_claim_bearing_filing")

    result = project_missing_document_successor(
        base_selection=_base_selection(),
        manifest_bytes=manifest,
        approval=_approval(manifest),
        acquisitions=(
            _observation(
                requested_role="other_claim_bearing_filing",
                markdown=(
                    "AMENDED PETITION IN INTERVENTION\nFIRST CAUSE OF ACTION\n"
                    "WHEREFORE, Intervenor prays for judgment."
                ),
            ),
        ),
    )

    assert len(result.inclusion_ledger) == 1
    assert result.inclusion_ledger[0]["admitted_role"] == "other_claim_bearing_filing"
