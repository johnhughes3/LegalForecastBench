"""Deterministic visible-text extraction from a sealed LAB deliverable.

The Harvey LAB deliverable contract requires a ``.docx`` (see
``harvey_lab_output_discovery``), which is an OOXML zip container rather than
text.  A paid judge has to be shown the candidate's actual work product, so
those bytes must be turned into text before they can reach a provider.

This module is therefore *judge-input-determining* code: what it returns is
what the judge grades, so every ambiguous case fails closed rather than
returning a partial document.  A silently truncated or silently empty
extraction would produce a confident, billed verdict about text nobody sent,
which is the failure mode the per-criterion seam exists to prevent.

Provider-free, dependency-free, and deterministic: the standard library only,
no network, no credentials, and the same bytes always yield the same string.
"""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

# The main document part every WordprocessingML package must contain.
DOCX_DOCUMENT_PART = "word/document.xml"
# Parts that carry body text this extractor does not render. The document part
# references a footnote by ID only, so footnote prose never appears in it: a memo
# arguing in its footnotes would otherwise be graded without that argument.
DOCX_UNRENDERED_TEXT_PARTS = ("word/footnotes.xml", "word/endnotes.xml")
_WORDPROCESSING_NAMESPACE = (
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
)

# A LAB memo is a text document; anything near this size is not one. The cap is
# applied to the *declared* and the *decompressed* size, so a zip bomb is
# refused before it is expanded rather than after.
DOCX_MAX_DOCUMENT_PART_BYTES = 8 * 1024 * 1024


class DeliverableTextError(ValueError):
    """Raised when deliverable text cannot be extracted fail-closed."""


def _qualified(tag: str) -> str:
    return f"{{{_WORDPROCESSING_NAMESPACE}}}{tag}"


def docx_visible_text(
    payload: bytes,
    *,
    max_document_part_bytes: int = DOCX_MAX_DOCUMENT_PART_BYTES,
) -> str:
    """Return the visible text of a ``.docx`` payload in document order.

    Only genuinely visible runs are returned: ``w:t`` text, ``w:tab`` tabs, and
    ``w:br``/``w:cr`` breaks, with each ``w:p`` starting a new line. Field
    instructions (``w:instrText``) and tracked deletions (``w:delText``) are
    excluded because neither is part of the delivered work product. Table text
    is included, since table cells are built from ordinary paragraphs.

    Raises ``DeliverableTextError`` for anything that would otherwise yield a
    partial or empty rendering.
    """

    if type(payload) is not bytes or not payload:
        raise DeliverableTextError("deliverable payload must be non-empty bytes")
    parts = _read_package_parts(payload, max_document_part_bytes)
    for name in DOCX_UNRENDERED_TEXT_PARTS:
        note_part = parts.get(name)
        if note_part is not None and _has_text(_parse_document_part(note_part)):
            # Refuse rather than render around it. Extracting notes correctly
            # means deciding where they belong in reading order, which is a
            # design question; grading a memo without its footnotes is not a
            # question at all -- it is the silent-partial-input failure this
            # module exists to prevent.
            raise DeliverableTextError(
                "deliverable carries footnote or endnote text this extractor "
                "does not render"
            )
    root = _parse_document_part(parts[DOCX_DOCUMENT_PART])
    text = _visible_text(root)
    if not text:
        # A structurally valid file that renders to nothing must not be graded:
        # the judge would return a confident verdict about an empty document.
        raise DeliverableTextError("deliverable contains no extractable text")
    return text


def _read_package_parts(
    payload: bytes, max_document_part_bytes: int
) -> dict[str, bytes]:
    """Read the document part, plus any note parts, under one byte cap each."""

    if type(max_document_part_bytes) is not int or max_document_part_bytes <= 0:
        raise DeliverableTextError("document part byte cap must be positive")
    parts: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())
            if DOCX_DOCUMENT_PART not in names:
                raise DeliverableTextError(
                    "deliverable is not a WordprocessingML package"
                )
            wanted = (DOCX_DOCUMENT_PART, *DOCX_UNRENDERED_TEXT_PARTS)
            for name in wanted:
                if name not in names:
                    continue
                info = archive.getinfo(name)
                if info.file_size > max_document_part_bytes:
                    raise DeliverableTextError("deliverable part is too large")
                with archive.open(info) as handle:
                    # Read one byte past the cap so a lying zip header is caught
                    # by the decompressed length rather than trusted at face value.
                    body = handle.read(max_document_part_bytes + 1)
                if len(body) > max_document_part_bytes:
                    raise DeliverableTextError("deliverable part is too large")
                parts[name] = body
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise DeliverableTextError("deliverable is not a readable zip package") from exc
    return parts


def _parse_document_part(document: bytes) -> ElementTree.Element:
    # A WordprocessingML part never carries a DTD. Refusing one outright keeps
    # entity-expansion attacks out of the standard-library parser entirely,
    # rather than relying on parser configuration to contain them.
    if b"<!DOCTYPE" in document or b"<!ENTITY" in document:
        raise DeliverableTextError("deliverable document part declares a DTD")
    try:
        return ElementTree.fromstring(document)
    except ElementTree.ParseError as exc:
        raise DeliverableTextError(
            "deliverable document part is not well-formed XML"
        ) from exc


def _has_text(root: ElementTree.Element) -> bool:
    """Report whether a part carries any non-whitespace text run.

    Word writes a footnotes part into every document containing only empty
    separator stubs, so presence of the part proves nothing; presence of actual
    ``w:t`` content does.
    """

    text_run = _qualified("t")
    return any(
        (element.text or "").strip()
        for element in root.iter()
        if element.tag == text_run
    )


def _visible_text(root: ElementTree.Element) -> str:
    paragraph = _qualified("p")
    text_run = _qualified("t")
    tab = _qualified("tab")
    breaks = {_qualified("br"), _qualified("cr")}
    parts: list[str] = []
    started = False
    for element in root.iter():
        if element.tag == paragraph:
            if started:
                parts.append("\n")
            started = True
        elif element.tag == text_run:
            parts.append(element.text or "")
        elif element.tag == tab:
            parts.append("\t")
        elif element.tag in breaks:
            parts.append("\n")
    rendered = "".join(parts)
    return "\n".join(line.rstrip() for line in rendered.split("\n")).strip()
