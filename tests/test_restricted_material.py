from __future__ import annotations

import pytest
from legalforecast.ingestion.restricted_material import restricted_material_markers


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
