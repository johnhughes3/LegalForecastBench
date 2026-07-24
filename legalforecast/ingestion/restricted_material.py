"""Fail-closed restricted-material classification for acquisition records."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

_BOOLEAN_RESTRICTION_FIELDS = frozenset(
    {
        "isprivate",
        "isrestricted",
        "issealed",
    }
)
_STATUS_FIELDS = frozenset(
    {
        "accessstatus",
        "availabilitystatus",
        "privacy",
        "privacystatus",
        "redactionorsealstatus",
        "restrictionstatus",
        "sealstatus",
        "visibility",
    }
)
_RESTRICTED_TEXT = re.compile(
    r"\bunder[\s_-]+seal\b|"
    r"\b(?:sealed|restricted|private)\s+"
    r"(?:document|filing|entry|access|view|download)\b|"
    r"\b(?:document|filing|entry|access|view|download)\s+"
    r"(?:is\s+|was\s+)?(?:sealed|restricted|private)\b",
    re.IGNORECASE,
)
_ACCESS_LABEL_RESTRICTED_TEXT = re.compile(
    r"\b(?:under[\s_-]+seal|sealed|restricted|private)\b",
    re.IGNORECASE,
)
_PUBLIC_HEARING_SANCTION_WARNING = re.compile(
    r"\bviolation\s+of\s+these\s+prohibitions\s+may\s+result\s+in\s+sanctions"
    r"\s*,\s*including\s+removal\s+of\s+court(?:[\s-]+)issued\s+media"
    r"\s+credentials\s*,\s*restricted\s+entry\s+to\s+future\s+hearings"
    r"\s*,\s*denial\s+of\s+entry\s+to\s+future\s+hearings\s*,\s*or\s+any"
    r"\s+other\s+sanctions\s+deemed\s+necessary\s+by\s+the\s+court\b"
    r"(?=\s*(?:[.!?]|$))",
    re.IGNORECASE,
)


def restricted_material_markers(
    *,
    records: Iterable[Mapping[str, object]] = (),
    text_fields: Iterable[str] = (),
    access_label_fields: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return stable evidence markers for explicit or textual restrictions."""

    markers: set[str] = set()
    for record in records:
        for key, value in record.items():
            normalized_key = _identifier(str(key))
            if normalized_key in _BOOLEAN_RESTRICTION_FIELDS:
                if value is True:
                    markers.add(f"field_{normalized_key}")
                elif value is not None and value is not False:
                    markers.add(f"field_{normalized_key}_malformed")
                continue
            if normalized_key not in _STATUS_FIELDS or value is None:
                continue
            match = _ACCESS_LABEL_RESTRICTED_TEXT.search(str(value))
            if match is not None:
                markers.add(f"status_{normalized_key}_{_identifier(match.group(0))}")
    for text in text_fields:
        for match in _RESTRICTED_TEXT.finditer(text):
            if _is_prospective_hearing_sanction_warning(text, match):
                continue
            markers.add(f"text_{_identifier(match.group(0))}")
    for text in access_label_fields:
        for match in _ACCESS_LABEL_RESTRICTED_TEXT.finditer(text):
            markers.add(f"access_{_identifier(match.group(0))}")
    return tuple(sorted(markers))


def contains_prospective_hearing_sanction_warning(text: str) -> bool:
    """Return whether text contains the narrow public-hearing warning shape."""

    return any(
        _is_prospective_hearing_sanction_warning(text, match)
        for match in _RESTRICTED_TEXT.finditer(text)
    )


def _is_prospective_hearing_sanction_warning(
    text: str,
    match: re.Match[str],
) -> bool:
    """Recognize only the frozen public-hearing warning boilerplate."""

    if _identifier(match.group(0)) != "restrictedentry":
        return False
    return any(
        warning.start() <= match.start() and match.end() <= warning.end()
        for warning in _PUBLIC_HEARING_SANCTION_WARNING.finditer(text)
    )


def _identifier(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())
