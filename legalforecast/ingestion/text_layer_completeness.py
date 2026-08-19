"""Fail-closed check that a conversion accounts for the PDF's own text layer.

The parse-quality gate measures the *density* of the published Markdown.  That
answers "is there usable text here?" and cannot answer "is any of the document
missing?", because a law-firm letterhead and a certificate of service are
dense.  A pinned-parser conversion that silently dropped an entire page's body
therefore passed every gate: the provider returned success, no fallback banner
was recorded, and the surviving header lines cleared the density floor.

This module answers the missing question with evidence the repository already
holds: the PDF's own embedded text layer.  The comparison is deliberately
coarse — presence of body text per page, not similarity — because a converter
legitimately re-orders, re-wraps and re-styles text, and any similarity metric
would either miss real losses or refuse honest conversions.

**What it detects, stated honestly.**  Whole-page-body loss on pages whose text
layer is body-dominated.  That is the defect class this was built for and the
class the corpus measurement supports.  It is not a general guarantee that a
conversion accounts for its source, and two limits follow directly from the
coarseness above.  A page that keeps its caption, letterhead and attorney block
while losing its body can retain enough characters to clear the floor, because
those blocks count as retained content on both sides.  And partial loss within
a page — a dropped sentence, even a dispositive one — is far above any floor a
whole-page test can set.  Detecting either of those needs a different
instrument, not a lower threshold here: lowering the floor would refuse honest
conversions long before it caught them.

Three exemptions keep the check honest rather than merely strict:

* a page whose stripped text layer is thin (a scanned page, an exhibit
  separator, a signature page) carries no evidence of loss and is exempt;
* a page the converter published as an image reference is exempt, because the
  converter has declared that page to be image content — a scanned insert whose
  "text layer" is scanner noise is the correct case for this;
* a conversion with no usable page separators is compared whole-document
  instead of per page, so an unpaginated but complete conversion is not
  refused for a formatting difference.

Thresholds are measured, not assumed.  Over the 322 succeeded conversions of
materialization root 47, the worst page of each document separates cleanly:
confirmed defects run 0.059 to 0.227 retention, the one image-declared page
sits at 0.134 and is exempted by the image rule, and the next legitimate row is
at 0.719.  A 0.35 floor sits inside that gap with margin on both sides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from legalforecast.ingestion.parse_quality import substantive_alphanumeric_count

TEXT_LAYER_COMPLETENESS_REJECTION_FLAG = "text_layer_incomplete"

#: A page whose stripped text layer holds fewer alphanumeric characters than
#: this carries no usable evidence about what the conversion should contain.
MINIMUM_PAGE_TEXT_LAYER_CHARACTERS = 300

#: The published Markdown must retain at least this share of the stripped text
#: layer's alphanumeric characters.  See the module docstring for the measured
#: separation this sits inside.
MINIMUM_TEXT_LAYER_RETENTION_RATIO = 0.35

#: A page the converter published as an image is exempt only while its own text
#: layer is weak evidence.  Beyond twice the per-page floor the layer is
#: substantial enough to demand accounting whatever the converter emitted, so
#: an image reference can never buy an exemption for a page of real text.
MAXIMUM_IMAGE_PAGE_TEXT_LAYER_CHARACTERS = 2 * MINIMUM_PAGE_TEXT_LAYER_CHARACTERS

COMPLETENESS_BASIS_PAGE = "page"
COMPLETENESS_BASIS_DOCUMENT = "document"

PAGE_VERDICT_ACCOUNTED = "accounted"
PAGE_VERDICT_INCOMPLETE = "incomplete"
PAGE_VERDICT_EXEMPT_THIN_LAYER = "exempt_thin_text_layer"
PAGE_VERDICT_EXEMPT_IMAGE_PAGE = "exempt_image_page"

PAGE_ATTRIBUTION_USABLE = "usable"
PAGE_ATTRIBUTION_UNPAGINATED = "unpaginated"
PAGE_ATTRIBUTION_MALFORMED = "malformed"
PAGE_ATTRIBUTION_PREAMBLE = "preamble"

_PAGE_SECTION_RE = re.compile(r"\s*#{1,6}\s*page\s+(\d+)\s*", re.IGNORECASE)
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


@dataclass(frozen=True, slots=True)
class TextLayerPageFinding:
    """One page's comparison between the PDF text layer and the Markdown."""

    page_number: int
    text_layer_character_count: int
    markdown_character_count: int
    retention_ratio: float | None
    verdict: str

    def to_record(self) -> dict[str, object]:
        return {
            "page_number": self.page_number,
            "text_layer_character_count": self.text_layer_character_count,
            "markdown_character_count": self.markdown_character_count,
            "retention_ratio": self.retention_ratio,
            "verdict": self.verdict,
        }


@dataclass(frozen=True, slots=True)
class TextLayerCompletenessAssessment:
    """Deterministic completeness result suitable for audit evidence."""

    basis: str
    parsed_page_count: int
    minimum_page_character_count: int
    minimum_retention_ratio: float
    pages: tuple[TextLayerPageFinding, ...]
    incomplete_page_numbers: tuple[int, ...]
    accepted: bool
    rejection_reasons: tuple[str, ...]

    @property
    def rejected(self) -> bool:
        return not self.accepted

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible audit record."""

        return {
            "basis": self.basis,
            "parsed_page_count": self.parsed_page_count,
            "minimum_page_character_count": self.minimum_page_character_count,
            "minimum_retention_ratio": self.minimum_retention_ratio,
            "pages": [page.to_record() for page in self.pages],
            "incomplete_page_numbers": list(self.incomplete_page_numbers),
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
        }


def page_section_number(line: str) -> int | None:
    """Return the page number a converter page separator introduces, if any."""

    match = _PAGE_SECTION_RE.fullmatch(line.strip())
    return None if match is None else int(match.group(1))


def markdown_page_sections(markdown: str) -> dict[int, str] | None:
    """Return Markdown text keyed by the page separator that introduced it.

    Returns ``None`` when the separators cannot attribute text to pages.  See
    :func:`attribute_markdown_pages` for the three distinct reasons that can
    happen; they are not interchangeable, and callers that need to tell them
    apart must use that function instead.
    """

    attribution, sections = attribute_markdown_pages(markdown)
    return sections if attribution == PAGE_ATTRIBUTION_USABLE else None


def attribute_markdown_pages(
    markdown: str,
) -> tuple[str, dict[int, str]]:
    """Classify how far a conversion's page separators can be trusted.

    Four outcomes, deliberately distinguished because they carry different
    priors about whether text was lost:

    ``usable``
        Every separator is unique and every line belongs to one.

    ``unpaginated``
        No separators at all.  The converter never claimed to paginate, so a
        whole-document comparison is the honest read.

    ``malformed``
        Separators are present but incoherent — a repeated page number.  The
        converter *did* claim to paginate and produced something that cannot be
        attributed, which is evidence of a defective conversion rather than of
        a different output mode, so this is refused rather than downgraded to
        the weaker whole-document comparison.

    ``preamble``
        Substantive text appears before the first separator, so some content
        belongs to no page.  Attribution would be a guess, and a page-scoped
        repair over that guess could duplicate the unattributed text, so this
        falls back to the whole-document comparison and is never repaired.
    """

    sections: dict[int, list[str]] = {}
    preamble: list[str] = []
    current: int | None = None
    for raw_line in markdown.splitlines():
        page_number = page_section_number(raw_line)
        if page_number is not None:
            if page_number in sections:
                return PAGE_ATTRIBUTION_MALFORMED, {}
            sections[page_number] = []
            current = page_number
            continue
        if current is None:
            preamble.append(raw_line)
            continue
        sections[current].append(raw_line)
    if not sections:
        return PAGE_ATTRIBUTION_UNPAGINATED, {}
    if _comparable_characters("\n".join(preamble)) > 0:
        return PAGE_ATTRIBUTION_PREAMBLE, {}
    return PAGE_ATTRIBUTION_USABLE, {
        number: "\n".join(lines) for number, lines in sections.items()
    }


def _comparable_characters(text: str) -> int:
    return substantive_alphanumeric_count(text, certificate_tail_is_boilerplate=False)


def assess_text_layer_completeness(
    *, source_pdf_bytes: bytes, markdown: str
) -> TextLayerCompletenessAssessment:
    """Assess whether ``markdown`` accounts for the PDF's embedded text layer.

    A PDF with no readable text layer produces no evidence either way and is
    accepted here; the parse-quality gate and the byte commitments remain the
    controls for those documents.
    """

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
    if extraction.parsed_page_count == 0:
        # No readable pages at all — an encrypted, damaged or unparseable PDF.
        # There is no text layer to account for, so there is no evidence either
        # way, and this check must not manufacture a verdict from its absence.
        # The byte commitments and the parse-quality gate remain the controls.
        return _assess_whole_document(
            layer_texts=(), markdown=markdown, parsed_page_count=0
        )
    layer_by_page = {page.page_number: page.text for page in extraction.pages}
    attribution, sections = attribute_markdown_pages(markdown)
    if attribution == PAGE_ATTRIBUTION_USABLE and any(
        not 1 <= number <= extraction.parsed_page_count for number in sections
    ):
        # A separator naming a page the PDF does not have is the same class of
        # incoherence as a repeated one: the converter claimed an attribution
        # its own source contradicts.
        attribution = PAGE_ATTRIBUTION_MALFORMED
    if attribution == PAGE_ATTRIBUTION_MALFORMED:
        return TextLayerCompletenessAssessment(
            basis=COMPLETENESS_BASIS_PAGE,
            parsed_page_count=extraction.parsed_page_count,
            minimum_page_character_count=MINIMUM_PAGE_TEXT_LAYER_CHARACTERS,
            minimum_retention_ratio=MINIMUM_TEXT_LAYER_RETENTION_RATIO,
            pages=(),
            incomplete_page_numbers=(),
            accepted=False,
            rejection_reasons=("text_layer_page_attribution_malformed",),
        )
    if attribution != PAGE_ATTRIBUTION_USABLE:
        ordered_pages = sorted(layer_by_page)
        return _assess_whole_document(
            layer_texts=tuple(layer_by_page[number] for number in ordered_pages),
            markdown=markdown,
            parsed_page_count=extraction.parsed_page_count,
        )

    findings: list[TextLayerPageFinding] = []
    incomplete: list[int] = []
    for page_number in range(1, extraction.parsed_page_count + 1):
        layer_characters = _comparable_characters(layer_by_page.get(page_number, ""))
        if layer_characters < MINIMUM_PAGE_TEXT_LAYER_CHARACTERS:
            findings.append(
                TextLayerPageFinding(
                    page_number=page_number,
                    text_layer_character_count=layer_characters,
                    markdown_character_count=_comparable_characters(
                        _MARKDOWN_IMAGE_RE.sub(" ", sections.get(page_number, ""))
                    ),
                    retention_ratio=None,
                    verdict=PAGE_VERDICT_EXEMPT_THIN_LAYER,
                )
            )
            continue
        section = sections.get(page_number, "")
        # Image markup is the converter's own filename, not the document's
        # text, so it is never counted as retained content — otherwise a page
        # reduced to a picture reference would earn credit for the reference.
        markdown_characters = _comparable_characters(
            _MARKDOWN_IMAGE_RE.sub(" ", section)
        )
        if (
            _MARKDOWN_IMAGE_RE.search(section) is not None
            and markdown_characters < MINIMUM_PAGE_TEXT_LAYER_CHARACTERS
            and layer_characters <= MAXIMUM_IMAGE_PAGE_TEXT_LAYER_CHARACTERS
        ):
            # The converter published this page AS an image: a picture and
            # nothing substantive beside it.  A page that kept real text and
            # also happens to carry a seal, a signature graphic or a letterhead
            # logo is NOT exempt — it is measured like any other page, because
            # an incidental image must never buy an exemption for missing body
            # text.
            findings.append(
                TextLayerPageFinding(
                    page_number=page_number,
                    text_layer_character_count=layer_characters,
                    markdown_character_count=markdown_characters,
                    retention_ratio=markdown_characters / layer_characters,
                    verdict=PAGE_VERDICT_EXEMPT_IMAGE_PAGE,
                )
            )
            continue
        ratio = markdown_characters / layer_characters
        accounted = ratio >= MINIMUM_TEXT_LAYER_RETENTION_RATIO
        if not accounted:
            incomplete.append(page_number)
        findings.append(
            TextLayerPageFinding(
                page_number=page_number,
                text_layer_character_count=layer_characters,
                markdown_character_count=markdown_characters,
                retention_ratio=ratio,
                verdict=(
                    PAGE_VERDICT_ACCOUNTED if accounted else PAGE_VERDICT_INCOMPLETE
                ),
            )
        )
    reasons = (
        (
            "text_layer_pages_not_accounted:"
            + ",".join(str(number) for number in incomplete),
        )
        if incomplete
        else ()
    )
    return TextLayerCompletenessAssessment(
        basis=COMPLETENESS_BASIS_PAGE,
        parsed_page_count=extraction.parsed_page_count,
        minimum_page_character_count=MINIMUM_PAGE_TEXT_LAYER_CHARACTERS,
        minimum_retention_ratio=MINIMUM_TEXT_LAYER_RETENTION_RATIO,
        pages=tuple(findings),
        incomplete_page_numbers=tuple(incomplete),
        accepted=not incomplete,
        rejection_reasons=reasons,
    )


def _assess_whole_document(
    *, layer_texts: tuple[str, ...], markdown: str, parsed_page_count: int
) -> TextLayerCompletenessAssessment:
    """Compare the whole conversion against the whole text layer.

    Used when page separators are absent or unusable.  The floor is the same
    per-page minimum: a document whose entire text layer is thinner than one
    page's worth of evidence cannot support a completeness verdict.
    """

    layer_characters = _comparable_characters("\n".join(layer_texts))
    markdown_characters = _comparable_characters(markdown)
    ratio = markdown_characters / layer_characters if layer_characters > 0 else None
    accepted = (
        layer_characters < MINIMUM_PAGE_TEXT_LAYER_CHARACTERS
        or ratio is None
        or ratio >= MINIMUM_TEXT_LAYER_RETENTION_RATIO
    )
    return TextLayerCompletenessAssessment(
        basis=COMPLETENESS_BASIS_DOCUMENT,
        parsed_page_count=parsed_page_count,
        minimum_page_character_count=MINIMUM_PAGE_TEXT_LAYER_CHARACTERS,
        minimum_retention_ratio=MINIMUM_TEXT_LAYER_RETENTION_RATIO,
        pages=(),
        incomplete_page_numbers=(),
        accepted=accepted,
        rejection_reasons=() if accepted else ("text_layer_document_not_accounted",),
    )


__all__ = [
    "COMPLETENESS_BASIS_DOCUMENT",
    "COMPLETENESS_BASIS_PAGE",
    "MAXIMUM_IMAGE_PAGE_TEXT_LAYER_CHARACTERS",
    "MINIMUM_PAGE_TEXT_LAYER_CHARACTERS",
    "MINIMUM_TEXT_LAYER_RETENTION_RATIO",
    "PAGE_ATTRIBUTION_MALFORMED",
    "PAGE_ATTRIBUTION_PREAMBLE",
    "PAGE_ATTRIBUTION_UNPAGINATED",
    "PAGE_ATTRIBUTION_USABLE",
    "PAGE_VERDICT_ACCOUNTED",
    "PAGE_VERDICT_EXEMPT_IMAGE_PAGE",
    "PAGE_VERDICT_EXEMPT_THIN_LAYER",
    "PAGE_VERDICT_INCOMPLETE",
    "TEXT_LAYER_COMPLETENESS_REJECTION_FLAG",
    "TextLayerCompletenessAssessment",
    "TextLayerPageFinding",
    "assess_text_layer_completeness",
    "attribute_markdown_pages",
    "markdown_page_sections",
    "page_section_number",
]
