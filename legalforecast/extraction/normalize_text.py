"""Text normalization helpers for extracted court-filing text."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """Normalized text plus quality flags observed during cleanup."""

    text: str
    quality_flags: tuple[str, ...]

    @property
    def line_count(self) -> int:
        if not self.text:
            return 0
        return len(self.text.splitlines())


def normalize_extracted_text(text: str) -> NormalizedText:
    """Normalize extracted filing text while preserving page breaks.

    The normalizer is intentionally conservative. It fixes control characters,
    whitespace churn, and a few common OCR substitutions that appear in the
    synthetic fixture corpus, but it does not rewrite arbitrary digits because
    docket numbers and citations are legal signal.
    """

    quality_flags: list[str] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    if normalized != text:
        quality_flags.append("control_characters_removed")

    pages = normalized.split("\f")
    cleaned_pages = [_normalize_page(page) for page in pages]
    normalized = "\f".join(page for page in cleaned_pages if page)
    if normalized != text:
        quality_flags.append("whitespace_normalized")

    repaired = _repair_common_ocr_terms(normalized)
    if repaired != normalized:
        quality_flags.append("ocr_noise_repaired")
        normalized = repaired

    if not normalized.strip():
        quality_flags.append("empty_text")

    return NormalizedText(text=normalized.strip(), quality_flags=tuple(quality_flags))


def _normalize_page(page: str) -> str:
    lines: list[str] = []
    for line in page.split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _repair_common_ocr_terms(text: str) -> str:
    replacements = (
        (re.compile(r"\bm[0o]t[1i]?[0o]n\b", re.IGNORECASE), _motion_term),
        (re.compile(r"\bt[0o]\b", re.IGNORECASE), _to_term),
        (re.compile(r"\bd[1i]sm[1i]ss(?:al)?\b", re.IGNORECASE), _dismiss_term),
        (re.compile(r"\bc[0o]unt\b", re.IGNORECASE), _count_term),
    )
    repaired = text
    for pattern, replacement in replacements:
        repaired = pattern.sub(replacement, repaired)
    return repaired


def _motion_term(match: re.Match[str]) -> str:
    return _preserve_initial_case(match.group(0), "motion")


def _to_term(match: re.Match[str]) -> str:
    return _preserve_initial_case(match.group(0), "to")


def _dismiss_term(match: re.Match[str]) -> str:
    value = match.group(0).lower()
    if value.endswith("al"):
        return _preserve_initial_case(match.group(0), "dismissal")
    return _preserve_initial_case(match.group(0), "dismiss")


def _count_term(match: re.Match[str]) -> str:
    return _preserve_initial_case(match.group(0), "count")


def _preserve_initial_case(original: str, replacement: str) -> str:
    if original[:1].isupper():
        return replacement.capitalize()
    return replacement
