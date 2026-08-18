"""Canonical current byte-role validation verdict view.

Fixtures are hand-authored (``synthetic: true``) but reproduce the exact record
shapes found in the needs-human adjudication overlay: the legacy validator
spelling (``verdict`` with ``heuristic_verdict``/``matched_pattern``) and the
later exact-role validator spelling (``byte_role_verdict`` with
``observed_heading``/``validation_basis``), including the newer records'
absence of ``docket_entry_number``.
"""

from __future__ import annotations

from typing import Any

from legalforecast.ingestion.adjudication_validation_view import (
    NOT_VALIDATED,
    CandidateValidationView,
    build_candidate_validation_view,
    build_validation_views,
    current_validation_verdict,
)

SYNTHETIC: dict[str, bool] = {"synthetic": True}


def _legacy_validation(
    *, candidate_id: str, entry: int, role: str, verdict: str = "match"
) -> dict[str, Any]:
    """A validation record in the original heuristic validator's spelling."""

    return {
        "byte_count": 4096,
        "candidate_id": candidate_id,
        "docket_entry_number": entry,
        "expected_role": role,
        "heuristic_verdict": verdict,
        "matched_pattern": "MOTION TO DISMISS",
        "source_document_id": f"doc-{entry}",
        "source_sha256": "0" * 64,
        "title_excerpt": "MOTION TO DISMISS",
        "verdict": verdict,
    }


def _exact_role_validation(
    *,
    candidate_id: str,
    role: str,
    source_document_id: str,
    verdict: str = "match",
    basis: str = "rendered_first_page",
) -> dict[str, Any]:
    """A validation record in the later exact-role validator's spelling.

    Note the absence of ``docket_entry_number`` -- the entry number can only be
    recovered from the enclosing document-status row.
    """

    return {
        "byte_role_verdict": verdict,
        "candidate_id": candidate_id,
        "expected_role": role,
        "observed_heading": "DEFENDANT'S MOTION TO DISMISS",
        "source_document_id": source_document_id,
        "source_sha256": "1" * 64,
        "text_sha256": "2" * 64,
        "validation_basis": basis,
    }


def _status(
    *,
    entry: int,
    role: str,
    acquisition_status: str = "acquired",
    validation: dict[str, Any] | None = None,
    source_document_id: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "acquired_document_role": role,
        "acquired_evidence": {
            "docket_entry_number": entry,
            "source_document_id": source_document_id or f"doc-{entry}",
        },
        "acquisition_status": acquisition_status,
        "entry": entry,
        "role": role,
    }
    if validation is not None:
        row["byte_role_validation"] = validation
    return row


def test_reads_the_legacy_verdict_spelling() -> None:
    record = _legacy_validation(candidate_id="70000001", entry=9, role="target_motion")
    assert current_validation_verdict(record) == "match"


def test_reads_the_later_byte_role_verdict_spelling() -> None:
    record = _exact_role_validation(
        candidate_id="73000896", role="target_motion", source_document_id="483774810"
    )
    assert current_validation_verdict(record) == "match"


def test_newer_spelling_wins_when_both_are_present() -> None:
    record = _legacy_validation(
        candidate_id="70000001", entry=9, role="target_motion", verdict="mismatch"
    )
    record["byte_role_verdict"] = "match"
    assert current_validation_verdict(record) == "match"


def test_missing_or_empty_record_reports_not_validated() -> None:
    assert current_validation_verdict(None) == NOT_VALIDATED
    assert current_validation_verdict({}) == NOT_VALIDATED
    assert current_validation_verdict({"verdict": "   "}) == NOT_VALIDATED


def _ponce_row() -> dict[str, Any]:
    """71843630-shaped row: reply validated ``match`` in the newer spelling."""

    return {
        "candidate_id": "71843630",
        "byte_mismatches": [],
        "missing_document_status": [
            _status(
                entry=13,
                role="reply",
                source_document_id="464830586",
                validation=_exact_role_validation(
                    candidate_id="71843630",
                    role="reply",
                    source_document_id="464830586",
                    basis="parsed_heading",
                ),
            )
        ],
    }


def _nalder_row() -> dict[str, Any]:
    """72001561-shaped row: stale mismatch on E13 resolved by later validation.

    The stale finding records ``selected_role=motion_to_dismiss_memorandum``
    while the resolving validation records ``expected_role=target_motion``, so
    only an entry-number join links them.
    """

    return {
        "candidate_id": "72001561",
        "byte_mismatches": [
            {
                "confidence": "high",
                "entry": 13,
                "evidence": "certificate of service only; no substantive motion text",
                "observed_role": "unknown",
                "selected_role": "motion_to_dismiss_memorandum",
                "verdict": "unverifiable",
            }
        ],
        "missing_document_status": [
            _status(
                entry=13,
                role="motion_to_dismiss_notice",
                source_document_id="466999143",
                validation=_exact_role_validation(
                    candidate_id="72001561",
                    role="target_motion",
                    source_document_id="466999143",
                ),
            )
        ],
    }


def _driver_row() -> dict[str, Any]:
    """70754103-shaped row: reused acquisitions with no validation record.

    Its E4 mismatch is a real, unresolved finding -- nothing later validated
    entry 4 -- so it must stay open.
    """

    return {
        "candidate_id": "70754103",
        "byte_mismatches": [
            {
                "confidence": "high",
                "entry": 4,
                "evidence": "AO 440 summons, 52 pages of blank proof-of-service forms",
                "observed_role": "summons",
                "selected_role": "amended_complaint",
                "verdict": "mismatch",
            }
        ],
        "missing_document_status": [
            _status(entry=1, role="complaint", source_document_id="445361327"),
            _status(entry=12, role="response", source_document_id="451661600"),
            _status(entry=13, role="reply", source_document_id="452376443"),
        ],
    }


def test_newer_spelling_is_not_rendered_as_unvalidated() -> None:
    view = build_candidate_validation_view(_ponce_row())
    assert view.verdict_for_entry(13) == "match"
    assert view.unvalidated_documents == ()
    assert view.documents[0].validated is True
    assert view.documents[0].validation_basis == "parsed_heading"


def test_stale_mismatch_is_superseded_by_later_validation() -> None:
    view = build_candidate_validation_view(_nalder_row())
    (mismatch,) = view.mismatches
    assert mismatch.superseded is True
    assert mismatch.current_verdict == "match"
    assert mismatch.unresolved_role is False
    assert view.open_mismatches == ()
    assert view.unresolved_role_mismatches == ()
    assert view.superseded_mismatches == (mismatch,)


def test_supersession_joins_on_entry_not_role() -> None:
    """The stale role and the validated role differ; the join must still hold."""

    row = _nalder_row()
    mismatch = row["byte_mismatches"][0]
    validation = row["missing_document_status"][0]["byte_role_validation"]
    assert mismatch["selected_role"] != validation["expected_role"]
    view = build_candidate_validation_view(row)
    assert view.mismatches[0].superseded is True


def test_entry_number_recovered_when_validation_omits_it() -> None:
    row = _nalder_row()
    assert (
        "docket_entry_number"
        not in row["missing_document_status"][0]["byte_role_validation"]
    )
    view = build_candidate_validation_view(row)
    assert view.documents[0].entry_number == 13


def test_real_mismatch_stays_open_without_a_resolving_validation() -> None:
    view = build_candidate_validation_view(_driver_row())
    (mismatch,) = view.mismatches
    assert mismatch.superseded is False
    assert mismatch.open is True
    assert mismatch.current_verdict == NOT_VALIDATED


def test_acquired_documents_without_validation_are_reported() -> None:
    view = build_candidate_validation_view(_driver_row())
    assert [document.entry_number for document in view.unvalidated_documents] == [
        1,
        12,
        13,
    ]
    assert view.verdict_for_entry(1) == NOT_VALIDATED


def test_unacquired_documents_are_not_counted_as_unvalidated() -> None:
    row = _driver_row()
    row["missing_document_status"].append(
        _status(entry=16, role="reply", acquisition_status="pacer_purchase")
    )
    view = build_candidate_validation_view(row)
    assert 16 not in [document.entry_number for document in view.unvalidated_documents]


def _shared_entry_row(*, main_verdict: str, attachment_verdict: str) -> dict[str, Any]:
    """One docket entry carrying a main reply plus an unrelated exhibit."""

    row = _ponce_row()
    row["missing_document_status"][0]["byte_role_validation"]["byte_role_verdict"] = (
        main_verdict
    )
    row["missing_document_status"].append(
        _status(
            entry=13,
            role="reply_exhibit",
            source_document_id="464830587",
            validation=_legacy_validation(
                candidate_id="71843630",
                entry=13,
                role="reply_exhibit",
                verdict=attachment_verdict,
            ),
        )
    )
    return row


def test_role_scoped_lookup_answers_for_the_document_asked_about() -> None:
    view = build_candidate_validation_view(
        _shared_entry_row(main_verdict="match", attachment_verdict="unverifiable")
    )
    assert view.verdict_for_entry(13, role="reply") == "match"
    assert view.verdict_for_entry(13, role="reply_exhibit") == "unverifiable"


def test_a_matching_attachment_cannot_rescue_a_mismatched_required_document() -> None:
    """The one answer this view must never give.

    A required document that failed validation must not read as validated
    because an unrelated document at the same docket entry passed.
    """

    view = build_candidate_validation_view(
        _shared_entry_row(main_verdict="mismatch", attachment_verdict="match")
    )
    assert view.verdict_for_entry(13, role="reply") == "mismatch"
    assert view.verdict_for_entry(13) != "match"


def test_shared_entry_without_a_role_is_conservative() -> None:
    view = build_candidate_validation_view(
        _shared_entry_row(main_verdict="match", attachment_verdict="unverifiable")
    )
    assert view.verdict_for_entry(13) == "unverifiable"


def test_unanimous_match_at_a_shared_entry_still_reports_match() -> None:
    view = build_candidate_validation_view(
        _shared_entry_row(main_verdict="match", attachment_verdict="match")
    )
    assert view.verdict_for_entry(13) == "match"


def test_role_with_no_comparable_document_at_a_shared_entry_declines() -> None:
    view = build_candidate_validation_view(
        _shared_entry_row(main_verdict="match", attachment_verdict="match")
    )
    assert view.verdict_for_entry(13, role="opposition") == NOT_VALIDATED


def test_role_spelling_differences_still_resolve() -> None:
    """A validation recorded as target_motion answers the corpus spelling."""

    view = build_candidate_validation_view(_nalder_row())
    assert view.verdict_for_entry(13, role="motion_to_dismiss_memorandum") == "match"
    assert view.verdict_for_entry(13, role="target_motion") == "match"


def test_a_lone_document_answers_even_under_an_unmatched_role() -> None:
    """Corpus and validation role vocabularies differ; a sole record still answers."""

    view = build_candidate_validation_view(_ponce_row())
    assert view.verdict_for_entry(13, role="some_other_role") == "match"


def test_unrelated_attachment_cannot_supersede_a_genuine_mismatch() -> None:
    row = _driver_row()
    row["missing_document_status"].append(
        _status(
            entry=4,
            role="summons_exhibit",
            source_document_id="445361399",
            validation=_legacy_validation(
                candidate_id="70754103", entry=4, role="summons_exhibit"
            ),
        )
    )
    view = build_candidate_validation_view(row)
    (mismatch,) = view.mismatches
    assert mismatch.superseded is False


def test_docket_entry_zero_is_not_treated_as_unknown() -> None:
    row = {
        "candidate_id": "70000003",
        "byte_mismatches": [
            {
                "entry": 0,
                "observed_role": "unknown",
                "selected_role": "complaint",
                "verdict": "unverifiable",
            }
        ],
        "missing_document_status": [
            _status(
                entry=0,
                role="complaint",
                validation=_legacy_validation(
                    candidate_id="70000003", entry=0, role="complaint"
                ),
            )
        ],
    }
    view = build_candidate_validation_view(row)
    assert view.verdict_for_entry(0) == "match"
    assert view.mismatches[0].superseded is True


def test_unknown_entry_reports_not_validated() -> None:
    view = build_candidate_validation_view(_ponce_row())
    assert view.verdict_for_entry(99) == NOT_VALIDATED


def test_build_validation_views_keys_by_candidate() -> None:
    views = build_validation_views([_ponce_row(), _nalder_row(), _driver_row()])
    assert set(views) == {"71843630", "72001561", "70754103"}
    assert isinstance(views["71843630"], CandidateValidationView)


def test_view_tolerates_missing_sections() -> None:
    view = build_candidate_validation_view({"candidate_id": "70000002"})
    assert view.documents == ()
    assert view.mismatches == ()
    assert view.verdict_for_entry(1) == NOT_VALIDATED
