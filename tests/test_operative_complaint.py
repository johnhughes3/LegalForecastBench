from __future__ import annotations

import re

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
        (
            "1 Adversary COMPLAINT filed by Trustee.",
            "Adversary Complaint",
            "complaint",
        ),
        ("1 Complaint (fee)", "Complaint (fee)", "complaint"),
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
        (
            "25 REPLY to Response to Motion, filed by Defendant, re 22 Opposed "
            "MOTION for Extension of Time to File Answer re 1 Complaint, filed "
            "by Defendant."
        ),
        (
            "17 STIPULATION for Extension of Time to Answer Plaintiff's Complaint "
            "filed by Defendant."
        ),
        (
            "11 ENDORSED LETTER regarding the deadline to respond to the Complaint "
            "filed by Defendant."
        ),
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


def test_docket_69736298_selects_exhibit_a_complaint_from_removal() -> None:
    complaint = _document(
        kind="Attachment 2",
        description="Exhibit A- Complaint",
        free=False,
    )
    entry = CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Mar 13, 2025",
        text=(
            "1 March 13, 2025, 3:14 p.m. 1 Mar 13, 2025 NOTICE OF REMOVAL "
            "Filing fee $405; Receipt #AWAEDC-4754077 Filed by Nate Spiering, "
            "Craig Meidl, City of Spokane Police Department, Todd Belitz. "
            "(Attachments: # 1 Civil Cover Sheet, # 2 Exhibit A- Complaint) "
            "Main Document Notice of Removal Download PDF Attachment 1 Civil "
            "Cover Sheet Buy on PACER Attachment 2 Exhibit A- Complaint Buy on PACER"
        ),
        documents=(
            _document(description="Notice of Removal"),
            _document(
                kind="Attachment 1",
                description="Civil Cover Sheet",
                free=False,
            ),
            complaint,
        ),
    )

    selected = select_operative_complaint_entry((entry,), before_entry=47)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.COMPLAINT
    assert select_operative_complaint_document(entry, require_free=False) == complaint
    assert select_operative_complaint_document(entry, require_free=True) is None


def test_docket_69830319_ignores_proposed_summons_attachment_text() -> None:
    complaint = _document(description="Complaint", free=False)
    entry = CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Apr 1, 2025",
        text=(
            "1 April 1, 2025, 1:14 p.m. 1 Apr 1, 2025 COMPLAINT Denise Yeye "
            "against Newrez LLC, PHH Mortgage Corporation filing fee $405 filed "
            "by Denise Yeye. (Attachments: # 1 Exhibit 1 Mortgage, # 6 Proposed "
            "Summons, # 7 Civil Cover Sheet) Main Document Complaint Buy on PACER "
            "Attachment 6 Proposed Summons Buy on PACER"
        ),
        documents=(
            complaint,
            _document(
                kind="Attachment 1", description="Exhibit 1 Mortgage", free=False
            ),
            _document(kind="Attachment 6", description="Proposed Summons", free=False),
            _document(kind="Attachment 7", description="Civil Cover Sheet", free=False),
        ),
    )

    selected = select_operative_complaint_entry((entry,), before_entry=21)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.COMPLAINT
    assert select_operative_complaint_document(entry, require_free=False) == complaint


def test_docket_71221919_selects_attorney_complaint_label() -> None:
    complaint = _document(
        description="ATTORNEY Complaint (Credit Card Required)",
        free=False,
    )
    entry = CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Aug 28, 2025",
        text=(
            "1 Aug. 28, 2025, 2:22 p.m. 1 Aug 28, 2025 Main Document "
            "ATTORNEY Complaint (Credit Card Required) Buy on PACER"
        ),
        documents=(complaint,),
    )

    selected = select_operative_complaint_entry((entry,), before_entry=28)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.COMPLAINT
    assert select_operative_complaint_document(entry, require_free=False) == complaint
    assert select_operative_complaint_document(entry, require_free=True) is None


def test_docket_71648352_ignores_no_summons_requested_text() -> None:
    complaint = _document(description="Complaint")
    entry = CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Oct 14, 2025",
        text=(
            "1 Oct. 14, 2025, 8:35 p.m. 1 Oct 14, 2025 COMPLAINT (Filing fee "
            "$405). No Summons requested at this time, filed by NETWORK SYSTEM "
            "TECHNOLOGIES, LLC. (Attachments: # 1 Exhibit1, # 16 Civil Cover Sheet) "
            "Main Document Complaint Download PDF Attachment 1 Exhibit1 Buy on PACER"
        ),
        documents=(
            complaint,
            _document(kind="Attachment 1", description="Exhibit1", free=False),
            _document(
                kind="Attachment 16", description="Civil Cover Sheet", free=False
            ),
        ),
    )

    later_reply = _entry(
        25,
        text=(
            "25 Nov. 21, 2025 REPLY to Response to Motion, filed by SK hynix "
            "America Inc., re 22 Opposed MOTION for Extension of Time to File "
            "Answer re 1 Complaint, filed by Defendant SK hynix America Inc."
        ),
        description="Reply to Response to Motion",
        free=False,
    )

    selected = select_operative_complaint_entry((entry, later_reply), before_entry=28)

    assert selected is not None
    assert selected.entry == entry
    assert selected.kind is OperativeComplaintKind.COMPLAINT
    assert select_operative_complaint_document(entry, require_free=True) == complaint


def test_docket_72270301_keeps_complaint_over_later_notice() -> None:
    complaint = _entry(
        1,
        text="1 VERIFIED COMPLAINT against Defendant filed by Plaintiff.",
        description="Complaint",
        free=False,
    )
    notice = _entry(
        22,
        text=(
            "22 NOTICE of Voluntary Stay of Counts 7 and 8 of the Verified "
            "Complaint by Plaintiff."
        ),
        description="Notice (Other)",
        free=False,
    )

    selected = select_operative_complaint_entry((complaint, notice), before_entry=30)

    assert selected is not None
    assert selected.entry == complaint


def test_docket_72242510_accepts_verified_parenthetical() -> None:
    entry = _entry(
        1,
        text="1 COMPLAINT (Verified) against All Defendants filed by Plaintiff.",
        description="",
        free=False,
    )

    selected = select_operative_complaint_entry((entry,), before_entry=9)

    assert selected is not None
    assert selected.entry == entry
    assert selected.kind is OperativeComplaintKind.COMPLAINT


def test_docket_73117990_marks_prefixed_amended_removal_pleading() -> None:
    amended = _document(
        kind="Attachment 1",
        description="Exhibit 1 - First Amended Complaint",
        free=False,
    )
    entry = CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Jan 7, 2026",
        text="1 NOTICE OF REMOVAL filed by Defendant.",
        documents=(_document(description="Notice of Removal"), amended),
    )

    selected = select_operative_complaint_entry((entry,), before_entry=10)

    assert selected is not None
    assert selected.kind is OperativeComplaintKind.AMENDED_COMPLAINT
    assert select_operative_complaint_document(entry, require_free=False) == amended


def test_removal_with_original_and_amended_complaints_fails_closed() -> None:
    entry = CourtListenerWebDocketEntry(
        row_id="entry-1",
        entry_number="1",
        filed_at="Mar 13, 2025",
        text="1 NOTICE OF REMOVAL filed by Defendant.",
        documents=(
            _document(description="Notice of Removal"),
            _document(
                kind="Attachment 1",
                description="Exhibit A- Complaint",
                free=False,
            ),
            _document(
                kind="Attachment 2",
                description="Exhibit B- First Amended Complaint",
                free=False,
            ),
        ),
    )

    assert select_operative_complaint_entry((entry,), before_entry=10) is None
    assert select_operative_complaint_document(entry, require_free=False) is None


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


def _document(
    *,
    description: str,
    kind: str = "Main Document",
    free: bool = True,
) -> CourtListenerWebDocument:
    slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")
    return CourtListenerWebDocument(
        kind=kind,
        description=description,
        href=(
            f"https://storage.courtlistener.com/recap/{slug}.pdf"
            if free
            else f"https://ecf.example.invalid/{slug}"
        ),
        action_label="Download PDF" if free else "Buy on PACER",
        pacer_only=not free,
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
