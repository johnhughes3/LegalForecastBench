from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.courtlistener_dates import parse_courtlistener_filed_date


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("June 30, 2026", date(2026, 6, 30)),
        ("Jun 30, 2026", date(2026, 6, 30)),
        ("Jun. 30, 2026, 9:39 a.m.", date(2026, 6, 30)),
        ("July 1, 2026, noon", date(2026, 7, 1)),
        ("Jul 1, 2026, midnight", date(2026, 7, 1)),
        ("Jul. 1, 2026, 1:48 p.m.", date(2026, 7, 1)),
        ("September 2, 2026", date(2026, 9, 2)),
        ("Sep 2, 2026", date(2026, 9, 2)),
        ("Sep. 2, 2026", date(2026, 9, 2)),
        ("Sept 2, 2026", date(2026, 9, 2)),
        ("Sept. 2, 2026", date(2026, 9, 2)),
        ("2026-07-01T13:48:00Z", date(2026, 7, 1)),
    ),
)
def test_parse_courtlistener_filed_date_accepts_supported_renderings(
    value: str,
    expected: date,
) -> None:
    assert parse_courtlistener_filed_date(value) == expected


@pytest.mark.parametrize(
    "value",
    (
        None,
        "",
        "June 31, 2026",
        "Jul 1, 2026, breakfast",
        "Jul 1, 2026, 25:00 p.m.",
        "Septober 2, 2026",
        "not a date",
    ),
)
def test_parse_courtlistener_filed_date_fails_closed(value: str | None) -> None:
    assert parse_courtlistener_filed_date(value) is None
