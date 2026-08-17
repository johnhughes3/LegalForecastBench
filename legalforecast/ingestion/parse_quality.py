"""Provider-free quality checks for parser-produced Markdown.

The parser's byte and hash commitments prove that the right source document was
processed.  They do not prove that the conversion contains usable pleading
text.  This module removes the small amount of deterministic PDF boilerplate
that commonly survives conversion and applies conservative role-aware density
thresholds to the remaining text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

PARSE_QUALITY_REJECTION_FLAG = "parse_quality_rejected"

_PAGE_MARKER_RE = re.compile(r"^\s*#{0,6}\s*page\s+\d+\s*$", re.IGNORECASE)
_PAGE_LABEL_RE = re.compile(
    r"^\s*(?:[-_=*]\s*){0,4}page\s+\d+(?:\s+of\s+\d+)?\s*(?:[-_=*]\s*)*$",
    re.IGNORECASE,
)
_CASE_PAGE_HEADER_RE = re.compile(
    r"^\s*case\b.*\bdocument\b.*\bfiled\b.*\bpage\s+\d+\s+of\s+\d+"
    r"(?:\s+pageid\s*#?:?\s*\d+)?\s*$",
    re.IGNORECASE,
)
_CASE_PAGE_HEADER_PENDING_RE = re.compile(
    r"^\s*case\b.*\bpageid\s*#?:?\s*$", re.IGNORECASE
)
_PAGE_ID_CONTINUATION_RE = re.compile(r"^\s*\d{1,9}\s*$")
_CERTIFICATE_START_RE = re.compile(
    r"^\s*(?:certificate\s+of\s+service|i\s+hereby\s+certify\b|"
    r"i\s+certify\s+that\b)",
    re.IGNORECASE,
)

# These are deliberately keyed by the stable role strings written in the
# acquisition manifests.  Unknown roles use the conservative default.
_PLEADING_AND_BRIEF_ROLES = frozenset(
    {
        "complaint",
        "amended_complaint",
        "counterclaim",
        "crossclaim",
        "third_party_complaint",
        "interpleader_complaint",
        "other_claim_bearing_filing",
        "motion_to_dismiss_notice",
        "motion_to_dismiss_memorandum",
        "opposition",
        "reply",
        "surreply",
        "supplemental_brief",
    }
)
_OUTCOME_ROLES = frozenset({"order", "decision"})
_FIXTURE_PARSER_ENGINES = frozenset({"fixture", "fixture_markdown"})


@dataclass(frozen=True, slots=True)
class ParseQualityAssessment:
    """Deterministic parse-quality result suitable for audit evidence."""

    document_role: str | None
    substantive_character_count: int
    substantive_line_count: int
    total_character_count: int
    boilerplate_character_count: int
    boilerplate_line_count: int
    minimum_character_count: int
    minimum_line_count: int
    accepted: bool
    rejection_reasons: tuple[str, ...]

    @property
    def rejected(self) -> bool:
        return not self.accepted

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible audit record."""

        return {
            "document_role": self.document_role,
            "substantive_character_count": self.substantive_character_count,
            "substantive_line_count": self.substantive_line_count,
            "total_character_count": self.total_character_count,
            "boilerplate_character_count": self.boilerplate_character_count,
            "boilerplate_line_count": self.boilerplate_line_count,
            "minimum_character_count": self.minimum_character_count,
            "minimum_line_count": self.minimum_line_count,
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
        }


def assess_parsed_text(
    text: str,
    document_role: str | None = None,
    *,
    enforce_role_thresholds: bool = True,
) -> ParseQualityAssessment:
    """Assess whether converted Markdown has usable substantive text.

    ``enforce_role_thresholds=False`` is reserved for deterministic synthetic
    fixture parsers, where short prose is intentional.  Even in that mode,
    boilerplate-only output is rejected.  Live parser and packet-planner paths
    always use the strict default.
    """

    role = document_role.strip().lower() if document_role else None
    lines = text.splitlines()
    substantive_lines: list[str] = []
    boilerplate_lines: list[str] = []
    certificate_started = False
    page_header_pending = False
    for raw_line in lines:
        line = raw_line.strip()
        if certificate_started:
            boilerplate_lines.append(raw_line)
            continue
        if page_header_pending and _PAGE_ID_CONTINUATION_RE.fullmatch(line):
            boilerplate_lines.append(raw_line)
            page_header_pending = False
            continue
        if _is_boilerplate_line(line):
            boilerplate_lines.append(raw_line)
            page_header_pending = bool(_CASE_PAGE_HEADER_PENDING_RE.fullmatch(line))
            continue
        page_header_pending = False
        if _CERTIFICATE_START_RE.match(line):
            certificate_started = True
            boilerplate_lines.append(raw_line)
            continue
        substantive_lines.append(raw_line)

    substantive_text = "\n".join(substantive_lines)
    substantive_character_count = sum(
        character.isalnum() for character in substantive_text
    )
    substantive_line_count = sum(
        any(character.isalnum() for character in line) for line in substantive_lines
    )
    total_character_count = sum(character.isalnum() for character in text)
    boilerplate_character_count = sum(
        character.isalnum() for character in "\n".join(boilerplate_lines)
    )

    if not enforce_role_thresholds or role is None:
        minimum_character_count, minimum_line_count = 1, 1
    elif role in _PLEADING_AND_BRIEF_ROLES:
        minimum_character_count, minimum_line_count = 200, 3
    elif role in _OUTCOME_ROLES:
        minimum_character_count, minimum_line_count = 120, 2
    else:
        minimum_character_count, minimum_line_count = 120, 2

    reasons: list[str] = []
    if substantive_character_count == 0:
        reasons.append("no_substantive_text")
    elif substantive_character_count < minimum_character_count:
        reasons.append("insufficient_substantive_characters")
    if substantive_line_count == 0:
        if "no_substantive_text" not in reasons:
            reasons.append("no_substantive_lines")
    elif substantive_line_count < minimum_line_count:
        reasons.append("insufficient_substantive_lines")

    return ParseQualityAssessment(
        document_role=role,
        substantive_character_count=substantive_character_count,
        substantive_line_count=substantive_line_count,
        total_character_count=total_character_count,
        boilerplate_character_count=boilerplate_character_count,
        boilerplate_line_count=len(boilerplate_lines),
        minimum_character_count=minimum_character_count,
        minimum_line_count=minimum_line_count,
        accepted=not reasons,
        rejection_reasons=tuple(reasons),
    )


def enforce_role_thresholds_for_parser_config(parser_config: object) -> bool:
    """Return whether a parser record must satisfy role-aware thresholds.

    Only the two explicitly named synthetic fixture engines may use relaxed
    thresholds.  Missing, malformed, or unknown parser configuration is
    treated as live/strict so a damaged provenance record cannot create a
    quality-gate bypass.
    """

    return not (
        isinstance(parser_config, Mapping)
        and cast(Mapping[str, object], parser_config).get("engine")
        in _FIXTURE_PARSER_ENGINES
    )


def _is_boilerplate_line(line: str) -> bool:
    if not line:
        return True
    return bool(
        _PAGE_MARKER_RE.fullmatch(line)
        or _PAGE_LABEL_RE.fullmatch(line)
        or _CASE_PAGE_HEADER_RE.fullmatch(line)
        or _CASE_PAGE_HEADER_PENDING_RE.fullmatch(line)
    )


__all__ = [
    "PARSE_QUALITY_REJECTION_FLAG",
    "ParseQualityAssessment",
    "assess_parsed_text",
    "enforce_role_thresholds_for_parser_config",
]
