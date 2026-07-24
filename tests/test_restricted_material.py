from __future__ import annotations

import pytest
from legalforecast.ingestion.restricted_material import restricted_material_markers

_PUBLIC_HEARING_SANCTION_BOILERPLATE = (
    "MINUTE entry before the Honorable Jorge L. Alonso: Telephonic motion hearing "
    "held. For the reasons stated on the record, Defendants' Motion to dismiss [45] "
    "is denied as moot. Telephonic Status hearing previously set for 7/30/26 is "
    "stricken and reset to 8/25/2026 at 9:30 a.m. The parties are directed to file "
    "a joint status report by 8/21/26. Members of the public and media will be able "
    "to call in to listen to this hearing. The call-in number is 650-479-3207 and "
    "the access code is 1804010308. Persons granted remote access to proceedings "
    "are reminded of the general prohibition against photographing, recording, and "
    "rebroadcasting of court proceedings. Violation of these prohibitions may "
    "result in sanctions, including removal of court issued media credentials, "
    "restricted entry to future hearings, denial of entry to future hearings, or "
    "any other sanctions deemed necessary by the Court. Notice mailed by Judge's "
    "staff (lf, )"
)


@pytest.mark.parametrize(
    "record",
    (
        {},
        {"is_sealed": None},
        {"is_private": None},
        {"is_restricted": None},
        {"is_sealed": False, "is_private": False, "is_restricted": False},
    ),
)
def test_missing_null_or_false_restriction_flags_are_not_affirmative_evidence(
    record: dict[str, object],
) -> None:
    assert restricted_material_markers(records=(record,)) == ()


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("is_sealed", "true"),
        ("is_sealed", "false"),
        ("is_private", 1),
        ("is_private", 0),
        ("is_restricted", []),
    ),
)
def test_malformed_non_null_restriction_flags_fail_closed(
    field_name: str,
    value: object,
) -> None:
    assert restricted_material_markers(records=({field_name: value},)) == (
        f"field_{field_name.replace('_', '')}_malformed",
    )


def test_public_hearing_sanction_boilerplate_is_not_restricted_material() -> None:
    assert (
        restricted_material_markers(text_fields=(_PUBLIC_HEARING_SANCTION_BOILERPLATE,))
        == ()
    )


def test_public_hearing_sanction_boilerplate_allows_formatting_variants() -> None:
    text = _PUBLIC_HEARING_SANCTION_BOILERPLATE.replace(
        "court issued media credentials, restricted entry",
        "court-issued media credentials,\nrestricted entry",
    )

    assert restricted_material_markers(text_fields=(text,)) == ()


@pytest.mark.parametrize(
    "text",
    (
        "This filing is a restricted entry.",
        "Restricted entry available only to case participants.",
        "The Court orders restricted entry to future hearings.",
        "Violation may result in sanctions. Restricted entry to future hearings "
        "is ordered.",
        "Violation may result in sanctions for misconduct, and the Court orders "
        "restricted entry to future hearings.",
        "Violation may result in sanctions, including fines and restricted entry "
        "to future hearings, which the Court now orders.",
        "Violation may result in sanctions, including restricted entry to future "
        "hearings, now ordered by the Court.",
        "Violation may result in sanctions, including restricted entry to future "
        "hearings; such restriction is now ordered.",
        "Violation may result in sanctions, including restricted entry to future "
        "hearings, and that restriction is hereby imposed.",
        "Violation may result in sanctions, including the Court-ordered restricted "
        "entry to future hearings.",
        "Violation may result in sanctions, including the currently effective "
        "restricted entry to future hearings.",
        "Violation may result in sanctions, including maintaining the imposed "
        "restricted entry to future hearings.",
        "Violation may result in sanctions, including an extension of restricted "
        "entry to future hearings.",
        "Violation may result in sanctions, including restricted entry to future "
        "hearings, even though that restriction is already in force.",
        _PUBLIC_HEARING_SANCTION_BOILERPLATE.replace(
            "Court. Notice",
            "Court and now imposed. Notice",
        ),
        _PUBLIC_HEARING_SANCTION_BOILERPLATE.replace(
            "Court. Notice",
            "Court, which has already imposed this restriction. Notice",
        ),
    ),
)
def test_genuine_restricted_entry_text_remains_affirmative_evidence(
    text: str,
) -> None:
    assert restricted_material_markers(text_fields=(text,)) == ("text_restrictedentry",)


def test_actual_restriction_alongside_sanction_warning_still_fails_closed() -> None:
    text = (
        "Violation may result in sanctions, including restricted entry to future "
        "hearings. This filing is a restricted entry available only to case "
        "participants."
    )

    assert restricted_material_markers(text_fields=(text,)) == ("text_restrictedentry",)


def test_sealed_document_alongside_sanction_warning_still_fails_closed() -> None:
    text = _PUBLIC_HEARING_SANCTION_BOILERPLATE + " The attached document is sealed."

    assert restricted_material_markers(text_fields=(text,)) == (
        "text_documentissealed",
    )
