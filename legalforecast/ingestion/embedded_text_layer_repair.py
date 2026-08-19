"""Repair a conversion that dropped pages, from the PDF's own embedded layer.

When :mod:`legalforecast.ingestion.text_layer_completeness` refuses a
conversion, the dropped text is not lost — it is sitting in bytes the
repository already holds and has already committed by digest.  This module
recovers exactly the pages the converter dropped and splices them into the
conversion, so the repaired document keeps the converter's structure on every
page that converted correctly.

Two properties are deliberate.

**Page-scoped, not whole-document.**  Re-extracting an entire document would
discard good structured output for the pages that were fine — 27 correct pages
of a 28-page brief to repair one.  The splice touches only the refused pages.

**Supersession, never mutation.**  This produces a new Markdown payload and a
new record for a new parse root.  The prior conversion's bytes are unchanged
and its record is untouched; the repaired record names its own extraction
method, its repaired page numbers, and the digest of the conversion it
supersedes, so the substitution is legible in the manifest rather than
inferred.

The method name is never "mistral_parser_markdown": a record that claims a
provider conversion it did not receive is exactly the provenance defect this
repair exists to answer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.ingestion.provenance import sha256_text
from legalforecast.ingestion.text_layer_completeness import (
    COMPLETENESS_BASIS_PAGE,
    assess_text_layer_completeness,
    page_section_number,
)

EMBEDDED_TEXT_LAYER_REPAIR_METHOD = "mistral_markdown_embedded_text_layer_page_repair"
EMBEDDED_TEXT_LAYER_REPAIR_ENGINE = "embedded_text_layer_page_repair"
EMBEDDED_TEXT_LAYER_REPAIR_REVISION = "text-layer-page-repair-v1"
EMBEDDED_TEXT_LAYER_EXTRACTION_METHOD = "pypdf_page_text_v2"

_HORIZONTAL_RULE_RE = re.compile(r"(?:-{3,}|\*{3,}|_{3,})")


@dataclass(frozen=True, slots=True)
class EmbeddedTextLayerRepair:
    """A verified page-scoped repair of one conversion."""

    markdown: str
    repaired_page_numbers: tuple[int, ...]
    parsed_page_count: int
    superseded_text_sha256: str

    @property
    def notes(self) -> str:
        pages = ", ".join(str(number) for number in self.repaired_page_numbers)
        return (
            f"pages {pages} recovered from the PDF's embedded text layer after the "
            "pinned-parser conversion failed the text-layer completeness gate; every "
            "other page is the superseded conversion's bytes unchanged"
        )


def plan_embedded_text_layer_repair(
    *, source_pdf_bytes: bytes, markdown: str
) -> EmbeddedTextLayerRepair | None:
    """Return a verified repair for one conversion, or ``None``.

    ``None`` means "this lane cannot repair this document", never "this
    document is fine".  Callers must keep treating an unrepaired refusal as a
    refusal.  The three ``None`` cases are: the conversion already accounts for
    its text layer; the loss could not be attributed to specific pages, so a
    splice would be a guess; or the spliced result still fails the gate.
    """

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source_pdf_bytes, markdown=markdown
    )
    if assessment.accepted or assessment.basis != COMPLETENESS_BASIS_PAGE:
        return None
    # Imported here rather than at module scope.  ``disclosure_clearance``
    # reaches into ``legalforecast.extraction``, which imports back into the
    # ``legalforecast.ingestion`` package, so a module-scope import would make
    # importing either package first depend on the other having finished.  The
    # repository already uses this remedy for the same reason (see
    # ``stage_a_replay_executor/lineage.py``).
    from legalforecast.ingestion.disclosure_clearance import (
        extract_disclosure_pdf_pages,
    )

    extraction = extract_disclosure_pdf_pages(source_pdf_bytes)
    layer_by_page = {page.page_number: page.text for page in extraction.pages}
    incomplete = tuple(assessment.incomplete_page_numbers)
    if not incomplete or any(number not in layer_by_page for number in incomplete):
        return None
    repaired = _splice_pages(
        markdown, layer_by_page=layer_by_page, pages=set(incomplete)
    )
    verification = assess_text_layer_completeness(
        source_pdf_bytes=source_pdf_bytes, markdown=repaired
    )
    if verification.rejected:
        return None
    return EmbeddedTextLayerRepair(
        markdown=repaired,
        repaired_page_numbers=incomplete,
        parsed_page_count=extraction.parsed_page_count,
        superseded_text_sha256=sha256_text(markdown),
    )


def embedded_text_layer_repair_parser_config(
    repair: EmbeddedTextLayerRepair, *, pinned_parser_revision: str
) -> dict[str, Any]:
    """Build the parser-config record a repaired conversion publishes.

    ``pinned_parser_revision`` is the parser generation this repair was
    produced under, not a claim about what produced the conversion being
    superseded.  A repair can itself be superseded by a later repair — after a
    threshold or role change — and asserting "the thing I replaced came from
    the provider" would be false on that second hop.  The predecessor is
    identified by ``superseded_text_sha256``, which is exact and needs no
    claim about its origin.
    """

    return {
        "engine": EMBEDDED_TEXT_LAYER_REPAIR_ENGINE,
        "extraction_method": EMBEDDED_TEXT_LAYER_EXTRACTION_METHOD,
        "repair_revision": EMBEDDED_TEXT_LAYER_REPAIR_REVISION,
        "repaired_page_numbers": list(repair.repaired_page_numbers),
        "parsed_page_count": repair.parsed_page_count,
        "pinned_parser_revision": pinned_parser_revision,
        "superseded_text_sha256": repair.superseded_text_sha256,
    }


def embedded_text_layer_repair_record_problem(
    record: Mapping[str, object], *, markdown: str, expected_parser_revision: str
) -> str | None:
    """Return why a repaired conversion record is unacceptable, or ``None``.

    Pinned exactly as tightly as the live-Mistral shape it stands beside: a
    loose repair shape would be a second, weaker route into the authenticated
    lineage, which is the failure mode the reuse validators exist to prevent.
    """

    raw_config = record.get("parser_config")
    raw_extracted = record.get("extracted_text")
    if not isinstance(raw_config, Mapping) or not isinstance(raw_extracted, Mapping):
        return "repaired conversion lacks embedded-text-layer repair provenance"
    config = cast(Mapping[str, object], raw_config)
    extracted = cast(Mapping[str, object], raw_extracted)
    pages = config.get("repaired_page_numbers")
    parsed_page_count = config.get("parsed_page_count")
    if (
        config.get("engine") != EMBEDDED_TEXT_LAYER_REPAIR_ENGINE
        or config.get("extraction_method") != EMBEDDED_TEXT_LAYER_EXTRACTION_METHOD
        or config.get("repair_revision") != EMBEDDED_TEXT_LAYER_REPAIR_REVISION
        or config.get("pinned_parser_revision") != expected_parser_revision
        or not _is_sha256(config.get("superseded_text_sha256"))
        or not isinstance(parsed_page_count, int)
        or isinstance(parsed_page_count, bool)
        or parsed_page_count <= 0
        or not isinstance(pages, list)
        or not pages
        or any(
            not isinstance(page, int) or isinstance(page, bool) or page < 1
            for page in cast(list[object], pages)
        )
        or sorted(set(cast(list[int], pages))) != cast(list[int], pages)
        or max(cast(list[int], pages)) > parsed_page_count
    ):
        return "repaired conversion has an unclean embedded-text-layer repair config"
    quality_flags = record.get("quality_flags")
    if (
        quality_flags != []
        or extracted.get("quality_flags") != []
        or extracted.get("extraction_method") != EMBEDDED_TEXT_LAYER_REPAIR_METHOD
        or extracted.get("source_document_id") != record.get("source_document_id")
        or extracted.get("page_count") != parsed_page_count
        or extracted.get("text_sha256") != sha256_text(markdown)
    ):
        return "repaired conversion Markdown text provenance mismatch"
    if config.get("superseded_text_sha256") == sha256_text(markdown):
        return "repaired conversion did not change the superseded Markdown"
    return None


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _splice_pages(
    markdown: str, *, layer_by_page: dict[int, str], pages: set[int]
) -> str:
    """Replace each named page's converted text with its embedded text layer."""

    output: list[str] = []
    buffered: list[str] = []
    current: int | None = None

    def flush(page: int | None) -> None:
        nonlocal buffered
        if page is not None and page in pages:
            output.append("")
            output.extend(layer_by_page[page].splitlines())
            output.append("")
            populated = [line for line in buffered if line.strip()]
            if populated and _HORIZONTAL_RULE_RE.fullmatch(populated[-1].strip()):
                output.append(populated[-1])
                output.append("")
        else:
            output.extend(buffered)
        buffered = []

    for raw_line in markdown.splitlines():
        page_number = page_section_number(raw_line)
        if page_number is not None:
            flush(current)
            output.append(raw_line)
            current = page_number
            continue
        buffered.append(raw_line)
    flush(current)
    spliced = "\n".join(output)
    return spliced + "\n" if markdown.endswith("\n") else spliced


__all__ = [
    "EMBEDDED_TEXT_LAYER_EXTRACTION_METHOD",
    "EMBEDDED_TEXT_LAYER_REPAIR_ENGINE",
    "EMBEDDED_TEXT_LAYER_REPAIR_METHOD",
    "EMBEDDED_TEXT_LAYER_REPAIR_REVISION",
    "EmbeddedTextLayerRepair",
    "embedded_text_layer_repair_parser_config",
    "embedded_text_layer_repair_record_problem",
    "plan_embedded_text_layer_repair",
]
