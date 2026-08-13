"""Correct-behavior goldens for exact-100 document-selection defects.

These tests encode the repaired contract for ``legalforecastbench-3ak.2``.
They are marked ``xfail`` against the live classifiers and selectors so the
stack stays green; later fix PRs flip them to passing without rewriting the
assertions. ``strict=False`` keeps an accidental XPASS from failing CI.

Defects frozen here (see the epic plan):

* Generic opposition/reply titles are dropped because every briefing branch
  of ``classify_courtlistener_entry_role`` requires a literal MTD keyword.
* ``brief_targets_motion`` silently assumes linkage when a brief names no
  entry and the case has one target, and silently denies it when there are
  two or more.
* Operative-pleading selection trusts the docket label: 70754103 entry 4 is
  admitted as an amended complaint even though the bytes are AO 440 summons
  forms; the real complaint is entry 1.
* Claim-bearing vocabulary is only ``complaint`` / ``amended_complaint``, so
  71212565 motion 30's attacked crossclaim (ECF 23) and originating
  interpleader counterclaim (ECF 12) are never selected.
"""

from __future__ import annotations

import pytest
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    CourtListenerWebDocument,
    brief_targets_motion,
    classify_courtlistener_entry_role,
    explicit_motion_reference_numbers,
    is_substantive_mtd_opposition_entry,
)
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    select_operative_complaint_entry,
)

_XFAIL_MISSED_BRIEFING = pytest.mark.xfail(
    strict=False,
    reason=(
        "legalforecast/ingestion/courtlistener_web.py:249 and :624: "
        "classify_courtlistener_entry_role gates every opposition/reply/memo "
        "branch on a literal MTD-keyword match, so generic titles and PACER "
        "event labels become OTHER"
    ),
)
_XFAIL_SILENT_LINKAGE = pytest.mark.xfail(
    strict=False,
    reason=(
        "legalforecast/ingestion/courtlistener_web.py:116: brief_targets_motion "
        "silently assumes linkage when a brief names no entry and there is "
        "one target, and silently denies linkage when there are two or more"
    ),
)
_XFAIL_WRONG_BYTES = pytest.mark.xfail(
    strict=False,
    reason=(
        "legalforecast/ingestion/operative_complaint.py:31 and :98: no "
        "byte-vs-role check; 70754103 entry 4 is admitted as an amended "
        "complaint although the body is AO 440 summons forms (the operative "
        "complaint is entry 1)"
    ),
)
_XFAIL_PLEADING_VOCAB = pytest.mark.xfail(
    strict=False,
    reason=(
        "legalforecast/ingestion/operative_complaint.py:16 and :98: operative-"
        "pleading vocabulary is only complaint/amended_complaint, so "
        "counterclaim, crossclaim, third-party, and interpleader filings are "
        "dropped"
    ),
)

_AO440_SUMMONS_EXCERPT = (
    "AO 440 (Rev. 06/12) Summons in a Civil Action\n"
    "UNITED STATES DISTRICT COURT\n"
    "PROOF OF SERVICE\n"
    "This summons for (name of individual and title, if any)\n"
)

_CLAIM_BEARING_KINDS = frozenset(
    {
        "complaint",
        "amended_complaint",
        "counterclaim",
        "crossclaim",
        "third_party_complaint",
        "interpleader_complaint",
    }
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
    narrative_text: str | None = None,
) -> CourtListenerWebDocketEntry:
    return CourtListenerWebDocketEntry(
        row_id=f"entry-{number}",
        entry_number=str(number),
        filed_at="Jan 1, 2026",
        text=text,
        documents=(_document(description),),
        narrative_text=narrative_text,
    )


def _model_visible_entry_numbers(
    entries: tuple[CourtListenerWebDocketEntry, ...],
    *,
    target: int,
    decision: int,
) -> set[int]:
    """Compose the public selection hooks the later fix PRs will repair."""

    selected: set[int] = set()
    pleading = select_operative_complaint_entry(entries, before_entry=target)
    if pleading is not None and pleading.entry.entry_number is not None:
        selected.add(int(pleading.entry.entry_number))
    for entry in entries:
        if entry.entry_number is None:
            continue
        number = int(entry.entry_number)
        if number >= decision:
            continue
        role = classify_courtlistener_entry_role(entry)
        if number == target and role in {
            CourtListenerEntryRole.MTD_NOTICE,
            CourtListenerEntryRole.MTD_MEMORANDUM,
        }:
            selected.add(number)
        elif (
            role is CourtListenerEntryRole.OPPOSITION
            and is_substantive_mtd_opposition_entry(entry)
            and brief_targets_motion(entry, (target,))
        ):
            selected.add(number)
        elif role is CourtListenerEntryRole.REPLY and brief_targets_motion(
            entry, (target,)
        ):
            selected.add(number)
    return selected


@_XFAIL_MISSED_BRIEFING
@pytest.mark.parametrize(
    ("text", "description"),
    (
        (
            "12 Sep 8, 2025 Main Document Response to Motion Buy on PACER",
            "Response to Motion",
        ),
        (
            "RESPONSE in Opposition re Motion.",
            "Response in Opposition",
        ),
        ("Opposition to Motion", "Opposition to Motion"),
    ),
)
def test_generic_opposition_title_is_classified_without_mtd_keyword(
    text: str,
    description: str,
) -> None:
    """70754103 entry 12 class: briefing is not gated on an MTD keyword."""

    entry = _entry(12, text, description=description)

    assert classify_courtlistener_entry_role(entry) is (
        CourtListenerEntryRole.OPPOSITION
    )
    assert is_substantive_mtd_opposition_entry(entry) is True


@_XFAIL_MISSED_BRIEFING
@pytest.mark.parametrize(
    ("text", "description"),
    (
        (
            "13 Sep 15, 2025 Main Document Reply to Response to Motion Buy on PACER",
            "Reply to Response to Motion",
        ),
        ("REPLY in support of Motion.", "Reply in Support"),
        ("Surreply to Motion", "Surreply"),
    ),
)
def test_generic_reply_title_is_classified_without_mtd_keyword(
    text: str,
    description: str,
) -> None:
    """70754103 entry 13 class: reply/surreply titles do not need 'MTD'."""

    entry = _entry(13, text, description=description)

    assert classify_courtlistener_entry_role(entry) is CourtListenerEntryRole.REPLY


@_XFAIL_MISSED_BRIEFING
def test_separate_memorandum_in_support_is_mtd_memorandum() -> None:
    """A standalone supporting memo is a required motion document."""

    entry = _entry(
        11,
        "11 Memorandum in Support",
        description="Memorandum in Support",
    )

    assert classify_courtlistener_entry_role(entry) is (
        CourtListenerEntryRole.MTD_MEMORANDUM
    )


def test_memorandum_that_names_the_mtd_is_already_a_memorandum() -> None:
    """Already-correct path: keep the explicit-MTD memo classification."""

    entry = _entry(
        11,
        "11 Memorandum in Support of Motion to Dismiss",
        description="Memorandum in Support of Motion to Dismiss",
    )

    assert classify_courtlistener_entry_role(entry) is (
        CourtListenerEntryRole.MTD_MEMORANDUM
    )


@_XFAIL_MISSED_BRIEFING
@pytest.mark.parametrize(
    "text",
    (
        "10 Sep 3, 2025 Main Document Dismiss for Failure to State a Claim "
        "Buy on PACER",
        "30 Dismiss for Failure to State a Claim AND Dismiss/Lack of Jurisdiction",
    ),
)
def test_pacer_event_label_is_a_dispositive_motion(text: str) -> None:
    """AZD/FLSD event labels are 12(b) motions even without the word 'motion'."""

    entry = _entry(10, text, description="Dismiss for Failure to State a Claim")

    assert classify_courtlistener_entry_role(entry) is (
        CourtListenerEntryRole.MTD_NOTICE
    )


@_XFAIL_SILENT_LINKAGE
def test_brief_without_entry_number_does_not_silently_assume_single_motion() -> None:
    """One target is not evidence that an unlabeled brief attacks it."""

    entry = _entry(12, "Response to Motion", description="Response to Motion")

    assert explicit_motion_reference_numbers(entry) == frozenset()
    assert brief_targets_motion(entry, (10,)) is False


@_XFAIL_SILENT_LINKAGE
def test_brief_without_entry_number_does_not_silently_deny_multi_motion() -> None:
    """Two targets plus no entry number is unresolved, not a boolean drop."""

    entry = _entry(12, "Response to Motion", description="Response to Motion")

    assert explicit_motion_reference_numbers(entry) == frozenset()
    assert brief_targets_motion(entry, (10, 41)) is not False


def test_explicit_ecf_reference_still_targets_that_motion() -> None:
    entry = _entry(
        12,
        "Opposition re 10 Motion to Dismiss",
        description="Opposition",
    )

    assert explicit_motion_reference_numbers(entry) == frozenset({10})
    assert brief_targets_motion(entry, (10, 41)) is True
    assert brief_targets_motion(entry, (41,)) is False


@_XFAIL_PLEADING_VOCAB
@pytest.mark.parametrize(
    ("number", "text", "description", "kind"),
    (
        (
            12,
            "12 Answer to Complaint AND Counterclaim",
            "Answer to Complaint AND Counterclaim",
            "counterclaim",
        ),
        (
            23,
            "23 Answer to Counterclaim AND Crossclaim",
            "Answer to Counterclaim AND Crossclaim",
            "crossclaim",
        ),
        (
            22,
            "22 CROSSCLAIM against Plaintiff filed by Defendant.",
            "Crossclaim",
            "crossclaim",
        ),
        (
            15,
            "15 COUNTERCLAIM against Plaintiff filed by Defendant.",
            "Counterclaim",
            "counterclaim",
        ),
        (
            8,
            "8 THIRD-PARTY COMPLAINT against Third Party filed by Defendant.",
            "Third-Party Complaint",
            "third_party_complaint",
        ),
        (
            9,
            "9 INTERPLEADER COMPLAINT against Claimants filed by Stakeholder.",
            "Interpleader Complaint",
            "interpleader_complaint",
        ),
    ),
)
def test_claim_bearing_pleading_vocabulary(
    number: int,
    text: str,
    description: str,
    kind: str,
) -> None:
    """Expanded attacked-pleading vocabulary required by the successor policy."""

    selected = select_operative_complaint_entry(
        (_entry(number, text, description=description),),
        before_entry=30,
    )

    assert selected is not None
    assert selected.kind.value == kind
    assert selected.kind.value in _CLAIM_BEARING_KINDS


@_XFAIL_MISSED_BRIEFING
def test_70754103_selects_complaint_motion_opposition_and_reply() -> None:
    """Select 1, 10, 12, 13; later briefing on motions 41+ stays out."""

    entries = (
        _entry(
            1,
            "1 Jul 10, 2025 Main Document Complaint Buy on PACER",
            description="Complaint",
        ),
        _entry(
            4,
            "4 Jul 18, 2025 Main Document Amended Complaint Buy on PACER",
            description="Amended Complaint",
            narrative_text=_AO440_SUMMONS_EXCERPT,
        ),
        _entry(
            10,
            "10 Sep 3, 2025 Main Document Dismiss for Failure to State a "
            "Claim Buy on PACER",
            description="Dismiss for Failure to State a Claim",
        ),
        _entry(
            12,
            "12 Sep 8, 2025 Main Document Response to Motion Buy on PACER",
            description="Response to Motion",
        ),
        _entry(
            13,
            "13 Sep 15, 2025 Main Document Reply to Response to Motion Buy on PACER",
            description="Reply to Response to Motion",
        ),
        _entry(
            41,
            "41 Nov 6, 2025 Main Document Dismiss/Lack of Jurisdiction AND "
            "Quash Buy on PACER",
            description="Dismiss/Lack of Jurisdiction AND Quash",
        ),
        _entry(
            44,
            "44 Nov 19, 2025 Main Document Response to Motion Buy on PACER",
            description="Response to Motion",
        ),
        _entry(
            46,
            "46 Nov 24, 2025 Main Document Reply to Response to Motion Buy on PACER",
            description="Reply to Response to Motion",
        ),
        _entry(
            64,
            "64 ORDER on Motion to Dismiss for Failure to State a Claim",
            description="Order on Motion to Dismiss",
        ),
    )

    assert _model_visible_entry_numbers(entries, target=10, decision=64) == {
        1,
        10,
        12,
        13,
    }


@_XFAIL_WRONG_BYTES
def test_70754103_rejects_summons_bytes_labeled_amended_complaint() -> None:
    """Wrong bytes behind a trusted label: entry 4 is AO 440 summons forms."""

    complaint = _entry(
        1,
        "1 COMPLAINT against Defendant filed by Plaintiff.",
        description="Complaint",
    )
    labeled_summons = _entry(
        4,
        "4 AMENDED COMPLAINT against Defendant filed by Plaintiff.",
        description="Amended Complaint",
        narrative_text=_AO440_SUMMONS_EXCERPT,
    )

    selected = select_operative_complaint_entry(
        (complaint, labeled_summons),
        before_entry=10,
    )

    assert selected is not None
    assert selected.entry is complaint
    assert selected.kind is OperativeComplaintKind.COMPLAINT


@_XFAIL_WRONG_BYTES
def test_ao440_summons_body_mismatches_amended_complaint_role() -> None:
    """Byte-vs-role hook: AO 440 body cannot satisfy an amended-complaint label."""

    from legalforecast.ingestion.operative_complaint import (
        pleading_body_matches_kind,
    )

    assert (
        pleading_body_matches_kind(
            _AO440_SUMMONS_EXCERPT,
            OperativeComplaintKind.AMENDED_COMPLAINT,
        )
        is False
    )


def test_71212565_motion_text_cites_interpleader_and_crossclaim() -> None:
    """Already-correct path: ECF No. extraction from the motion caption."""

    motion = _entry(
        30,
        (
            "Cross-Defendants move to dismiss the Crossclaim [ECF No. 23]. "
            "As framed by the Interpleader Counterclaim [ECF No. 12], the "
            "sole issue is control of the stakeholder entity."
        ),
        description=(
            "Dismiss for Failure to State a Claim AND Dismiss/Lack of Jurisdiction"
        ),
    )

    assert explicit_motion_reference_numbers(motion) == frozenset({12, 23})


@_XFAIL_PLEADING_VOCAB
def test_71212565_requires_interpleader_12_and_crossclaim_23() -> None:
    """Motion 30 attacks ECF 23; the originating interpleader is ECF 12."""

    complaint = _entry(
        1,
        "1 COMPLAINT against Defendant filed by Plaintiff.",
        description="Complaint",
    )
    interpleader = _entry(
        12,
        "12 Answer to Complaint AND Counterclaim",
        description="Answer to Complaint AND Counterclaim",
    )
    crossclaim = _entry(
        23,
        "23 Answer to Counterclaim AND Crossclaim",
        description="Answer to Counterclaim AND Crossclaim",
    )
    motion = _entry(
        30,
        (
            "Cross-Defendants move to dismiss the Crossclaim [ECF No. 23]. "
            "As framed by the Interpleader Counterclaim [ECF No. 12]."
        ),
        description="Dismiss for Failure to State a Claim",
    )

    cited = explicit_motion_reference_numbers(motion)
    assert cited == frozenset({12, 23})

    required: set[int] = set()
    for entry in (complaint, interpleader, crossclaim):
        selected = select_operative_complaint_entry((entry,), before_entry=30)
        if selected is not None and selected.kind.value in _CLAIM_BEARING_KINDS - {
            "complaint",
            "amended_complaint",
        }:
            assert selected.entry.entry_number is not None
            required.add(int(selected.entry.entry_number))

    assert required == {12, 23}

    attacked = select_operative_complaint_entry(
        (complaint, interpleader, crossclaim),
        before_entry=30,
    )
    assert attacked is not None
    assert attacked.entry is crossclaim
    assert attacked.kind.value == "crossclaim"
