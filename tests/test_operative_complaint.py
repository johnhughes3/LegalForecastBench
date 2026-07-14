from __future__ import annotations

import pytest
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    select_operative_complaint_document,
    select_operative_complaint_entry,
)


@pytest.mark.parametrize(
    ("text", "description", "kind"),
    (
        ("1 COMPLAINT against Defendant filed by Plaintiff.", "Complaint", "complaint"),
        ("1 PRO SE COMPLAINT against Defendant.", "Complaint - Pro Se", "complaint"),
        (
            "1 TRANSFERREDCOMPLAINT against All Defendants filed by Plaintiff.",
            "",
            "complaint",
        ),
        (
            "4 Petition (Removal/Transfer) Received From: County Court, "
            "filed by Plaintiff.",
            "Complaint (Removal/Transfer) - COURT USE ONLY",
            "complaint",
        ),
        (
            "9 FIRST AMENDED COMPLAINT against Defendant filed by Plaintiff.",
            "Amended Complaint",
            "amended_complaint",
        ),
        (
            "78 Civil Case - Complaint, Amended filed by Plaintiff.",
            "Civil Case - Complaint, Amended",
            "amended_complaint",
        ),
    ),
)
def test_select_operative_complaint_entry_accepts_strict_pleading_variants(
    text: str,
    description: str,
    kind: str,
) -> None:
    entry = _entry(1, text=text, description=description)

    selected = select_operative_complaint_entry((entry,), before_entry=5)

    assert selected is not None
    assert selected.entry == entry
    assert selected.kind is OperativeComplaintKind(kind)


@pytest.mark.parametrize(
    "text",
    (
        "3 OPINION AND ORDER granting leave and discussing the complaint.",
        "17 ORDER granting an extension to respond to Plaintiff's complaint.",
        "23 AMENDED MEMORANDUM DECISION dismissing claims in the complaint.",
        "66 MEMO ENDORSEMENT regarding motion to amend the complaint.",
        "91 ORDER granting Motion to Strike Amended Complaint.",
        "32 Answer to Complaint filed by Defendant.",
        "29 Certificate of Service Complaints filed by Plaintiff.",
    ),
)
def test_select_operative_complaint_entry_rejects_procedural_mentions(
    text: str,
) -> None:
    entry = _entry(3, text=text, description="Order")

    assert select_operative_complaint_entry((entry,), before_entry=5) is None


def test_select_operative_complaint_entry_uses_pre_target_floor() -> None:
    complaint = _entry(
        1,
        text="1 COMPLAINT against Defendant filed by Plaintiff.",
        description="Complaint",
        free=False,
    )
    later_order = _entry(
        3,
        text="3 OPINION AND ORDER discussing the complaint.",
        description="Opinion and Order",
    )
    post_target_amendment = _entry(
        12,
        text="12 AMENDED COMPLAINT against Defendant filed by Plaintiff.",
        description="Amended Complaint",
    )

    selected = select_operative_complaint_entry(
        (complaint, later_order, post_target_amendment),
        before_entry=11,
    )

    assert selected is not None
    assert selected.entry == complaint


def test_select_operative_complaint_document_respects_free_requirement() -> None:
    entry = _entry(
        1,
        text="1 PRO SE COMPLAINT against Defendant.",
        description="Complaint - Pro Se",
        free=False,
    )

    assert select_operative_complaint_document(entry, require_free=True) is None
    assert (
        select_operative_complaint_document(entry, require_free=False)
        == entry.documents[0]
    )


def test_exact_main_pleading_description_can_identify_sparse_docket_text() -> None:
    entry = _entry(
        1,
        text="1 Main Document Pro Se Complaint Buy on PACER",
        description="Pro Se Complaint",
        free=False,
    )

    selected = select_operative_complaint_entry((entry,), before_entry=5)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.COMPLAINT


def test_complaint_named_attachment_on_motion_is_not_a_pleading() -> None:
    entry = _entry(
        3,
        text="3 MOTION to supplement the complaint filed by Plaintiff.",
        description="Complaint",
    )

    assert select_operative_complaint_entry((entry,), before_entry=5) is None


def test_removal_petition_attachment_identifies_the_operative_pleading() -> None:
    entry = _removal_entry(petition_free=False)

    selected = select_operative_complaint_entry((entry,), before_entry=49)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.COMPLAINT
    assert (
        select_operative_complaint_document(entry, require_free=False)
        == entry.documents[2]
    )
    assert select_operative_complaint_document(entry, require_free=True) is None


def test_petition_attachment_outside_removal_does_not_identify_a_complaint() -> None:
    entry = _removal_entry(petition_free=True, text="1 MOTION with exhibits filed.")

    assert select_operative_complaint_entry((entry,), before_entry=49) is None
    assert select_operative_complaint_document(entry, require_free=False) is None


def test_multiple_removal_pleading_attachments_fail_closed() -> None:
    entry = _removal_entry(petition_free=True, include_complaint=True)

    assert select_operative_complaint_entry((entry,), before_entry=49) is None
    assert select_operative_complaint_document(entry, require_free=False) is None


def test_exact_removal_complaint_outranks_generic_exhibit_labels() -> None:
    complaint = CourtListenerWebDocument(
        kind="Main Document",
        description="Complaint (Removal/Transfer) - COURT USE ONLY",
        href="https://storage.courtlistener.com/recap/complaint.pdf",
        action_label="Download PDF",
        pacer_only=False,
    )
    entry = CourtListenerWebDocketEntry(
        row_id="entry-4",
        entry_number="4",
        filed_at="Jul 2, 2026",
        text=(
            "4 Jul 2, 2026 4 Jul 2, 2026 Petition (Removal/Transfer) Received "
            "From: State Court, filed by Plaintiff."
        ),
        documents=(
            complaint,
            CourtListenerWebDocument(
                kind="Attachment 1",
                description="Exhibit A",
                href="https://storage.courtlistener.com/recap/exhibit-a.pdf",
                action_label="Download PDF",
                pacer_only=False,
            ),
            CourtListenerWebDocument(
                kind="Attachment 2",
                description="Exhibit B",
                href="https://storage.courtlistener.com/recap/exhibit-b.pdf",
                action_label="Download PDF",
                pacer_only=False,
            ),
        ),
    )

    selected = select_operative_complaint_entry((entry,), before_entry=10)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.COMPLAINT
    assert select_operative_complaint_document(entry, require_free=True) == complaint


def _entry(
    number: int,
    *,
    text: str,
    description: str,
    free: bool = True,
) -> CourtListenerWebDocketEntry:
    return CourtListenerWebDocketEntry(
        row_id=f"entry-{number}",
        entry_number=str(number),
        filed_at="Jan 1, 2026",
        text=text,
        documents=(
            CourtListenerWebDocument(
                kind="Main Document",
                description=description,
                href=(
                    "https://storage.courtlistener.com/recap/document.pdf"
                    if free
                    else "https://ecf.example.invalid/doc1"
                ),
                action_label="Download PDF" if free else "Buy on PACER",
                pacer_only=not free,
            ),
        ),
    )


def _removal_entry(
    *,
    petition_free: bool,
    text: str = (
        "1 Dec 11, 2025 1 Dec 11, 2025 NOTICE OF REMOVAL WITH JURY DEMAND "
        "filed by Defendant."
    ),
    include_complaint: bool = False,
) -> CourtListenerWebDocketEntry:
    documents = [
        CourtListenerWebDocument(
            kind="Main Document",
            description="Notice of Removal",
            href="https://storage.courtlistener.com/recap/notice.pdf",
            action_label="Download PDF",
            pacer_only=False,
        ),
        CourtListenerWebDocument(
            kind="Attachment 1",
            description="Exhibit(s) A - Civil Cover Sheet",
            href="https://storage.courtlistener.com/recap/cover.pdf",
            action_label="Download PDF",
            pacer_only=False,
        ),
        CourtListenerWebDocument(
            kind="Attachment 5",
            description="Exhibit(s) C - Petition",
            href=(
                "https://storage.courtlistener.com/recap/petition.pdf"
                if petition_free
                else "https://ecf.example.invalid/petition"
            ),
            action_label="Download PDF" if petition_free else "Buy on PACER",
            pacer_only=not petition_free,
        ),
    ]
    if include_complaint:
        documents.append(
            CourtListenerWebDocument(
                kind="Attachment 6",
                description="Complaint",
                href="https://storage.courtlistener.com/recap/complaint.pdf",
                action_label="Download PDF",
                pacer_only=False,
            )
        )
    return CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Jul 1, 2026",
        text=text,
        documents=tuple(documents),
    )
