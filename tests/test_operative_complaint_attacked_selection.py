"""Attacked-pleading selection and the v3 fallback claim-bearing role.

Cohort policy v3 requires selection to follow the pleading the target motion
actually attacks rather than a generic complaint slot, and lists
``other_claim_bearing_filing`` in the recognition vocabulary. These tests pin
both, including the deliberate fallback to the latest pre-motion pleading when
the motion names no candidate.
"""

from __future__ import annotations

from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    motion_attacked_entry_numbers,
    pleading_body_matches_kind,
    select_operative_complaint_entry,
)

_AO440_SUMMONS_EXCERPT = (
    "AO 440 (Rev. 06/12) Summons in a Civil Action\n"
    "UNITED STATES DISTRICT COURT\n"
    "PROOF OF SERVICE\n"
    "This summons for (name of individual and title, if any)\n"
)


def _document(description: str) -> CourtListenerWebDocument:
    return CourtListenerWebDocument(
        kind="Main Document",
        description=description,
        href="https://storage.courtlistener.com/recap/document.pdf",
        action_label="Download PDF",
        pacer_only=False,
    )


def _entry(
    number: int,
    text: str,
    *,
    description: str,
) -> CourtListenerWebDocketEntry:
    return CourtListenerWebDocketEntry(
        row_id=f"entry-{number}",
        entry_number=str(number),
        filed_at="Jan 1, 2026",
        text=text,
        documents=(_document(description),),
    )


def test_a_later_counterclaim_does_not_displace_the_attacked_complaint() -> None:
    """The motion names ECF 1, so the ECF 12 counterclaim must not win."""

    complaint = _entry(
        1,
        "1 COMPLAINT against Defendant filed by Plaintiff.",
        description="Complaint",
    )
    counterclaim = _entry(
        12,
        "12 Answer to Complaint AND Counterclaim",
        description="Answer to Complaint AND Counterclaim",
    )
    motion = _entry(
        30,
        "Defendant moves to dismiss the Complaint [ECF No. 1] under Rule 12(b)(6).",
        description="Dismiss for Failure to State a Claim",
    )
    entries = (complaint, counterclaim, motion)

    attacked = motion_attacked_entry_numbers(entries, target_entry_numbers=(30,))
    assert attacked == frozenset({1})

    selected = select_operative_complaint_entry(
        entries,
        before_entry=30,
        attacked_entry_numbers=attacked,
    )
    assert selected is not None
    assert selected.entry is complaint
    assert selected.kind is OperativeComplaintKind.COMPLAINT

    fallback = select_operative_complaint_entry(entries, before_entry=30)
    assert fallback is not None
    assert fallback.entry is counterclaim


def test_attacked_preference_falls_back_when_no_candidate_is_named() -> None:
    """An unnumbered attack keeps the pre-existing latest-pleading behaviour."""

    complaint = _entry(
        1,
        "1 COMPLAINT against Defendant filed by Plaintiff.",
        description="Complaint",
    )
    counterclaim = _entry(
        12,
        "12 Answer to Complaint AND Counterclaim",
        description="Answer to Complaint AND Counterclaim",
    )
    motion = _entry(
        30,
        "Defendant moves to dismiss the operative pleading. See ECF No. 27.",
        description="Dismiss for Failure to State a Claim",
    )
    entries = (complaint, counterclaim, motion)

    attacked = motion_attacked_entry_numbers(entries, target_entry_numbers=(30,))
    assert attacked == frozenset({27})

    selected = select_operative_complaint_entry(
        entries,
        before_entry=30,
        attacked_entry_numbers=attacked,
    )
    assert selected is not None
    assert selected.entry is counterclaim


def test_other_claim_bearing_filing_admits_only_claim_asserting_bytes() -> None:
    """The v3 fallback role is body-validated, never label-inferred."""

    assert pleading_body_matches_kind(
        "PETITION TO ENFORCE\nFIRST CAUSE OF ACTION\nWHEREFORE Petitioner prays "
        "for relief.",
        OperativeComplaintKind.OTHER_CLAIM_BEARING_FILING,
    )
    assert not pleading_body_matches_kind(
        "NOTICE OF APPEARANCE\nPlease enter the appearance of counsel.",
        OperativeComplaintKind.OTHER_CLAIM_BEARING_FILING,
    )
    assert not pleading_body_matches_kind(
        _AO440_SUMMONS_EXCERPT + "\nFIRST CAUSE OF ACTION",
        OperativeComplaintKind.OTHER_CLAIM_BEARING_FILING,
    )
    assert not pleading_body_matches_kind(
        "MOTION TO DISMISS\nPlaintiff's claims for relief should be dismissed.",
        OperativeComplaintKind.OTHER_CLAIM_BEARING_FILING,
    )
    assert not pleading_body_matches_kind(
        "MOTION TO DISMISS\nWHEREFORE, Defendant prays that the complaint be "
        "dismissed.",
        OperativeComplaintKind.OTHER_CLAIM_BEARING_FILING,
    )
