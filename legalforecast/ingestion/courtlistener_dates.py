"""Fail-closed parsing for CourtListener docket-entry filed dates."""

from __future__ import annotations

import re
from datetime import date

_MONTH_DATE = re.compile(
    r"^(?P<month>[A-Z][a-z]+)\.?(?:\s+)"
    r"(?P<day>\d{1,2}),\s+(?P<year>\d{4})"
    r"(?:,\s+(?:noon|midnight|(?:1[0-2]|[1-9])(?::[0-5]\d)?\s+[ap]\.m\.))?$"
)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def parse_courtlistener_filed_date(value: str | None) -> date | None:
    """Parse a CourtListener filed-date field, returning ``None`` on drift.

    CourtListener renders both full and abbreviated English month names and may
    add a validated display-time suffix. ISO timestamps from API-backed sources
    are also accepted by their leading calendar date. Unknown renderings remain
    unparseable so every eligibility caller fails closed.
    """

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized[:10])
    except ValueError:
        pass

    match = _MONTH_DATE.fullmatch(normalized)
    if match is None:
        return None
    month = _MONTHS.get(match.group("month").lower())
    if month is None:
        return None
    try:
        return date(
            int(match.group("year")),
            month,
            int(match.group("day")),
        )
    except ValueError:
        return None
