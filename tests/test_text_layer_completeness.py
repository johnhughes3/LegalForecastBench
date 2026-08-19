"""Text-layer completeness gate: what it refuses, and what it must not refuse.

Every PDF here is generated in-process by ``_pdf`` below (synthetic: true).  No
document from the corpus appears in this file; the corpus measurements that
chose the thresholds are recorded in the module docstring of
``legalforecast.ingestion.text_layer_completeness`` and in the pull request.
"""

from __future__ import annotations

from io import BytesIO

from legalforecast.ingestion.text_layer_completeness import (
    COMPLETENESS_BASIS_DOCUMENT,
    COMPLETENESS_BASIS_PAGE,
    MINIMUM_PAGE_TEXT_LAYER_CHARACTERS,
    MINIMUM_TEXT_LAYER_RETENTION_RATIO,
    PAGE_ATTRIBUTION_MALFORMED,
    PAGE_ATTRIBUTION_PREAMBLE,
    PAGE_VERDICT_ACCOUNTED,
    PAGE_VERDICT_EXEMPT_IMAGE_PAGE,
    PAGE_VERDICT_EXEMPT_THIN_LAYER,
    PAGE_VERDICT_INCOMPLETE,
    assess_text_layer_completeness,
    attribute_markdown_pages,
    markdown_page_sections,
)
from reportlab.pdfgen.canvas import Canvas

_BODY_LINES = (
    "MOTION TO DISMISS UNDER RULE 12(b)(6)",
    "COMES NOW Defendant Example Corporation, by counsel, and moves this",
    "Court to dismiss the First Amended Complaint in its entirety because it",
    "fails to state a claim upon which relief can be granted, and in support",
    "of that motion states the grounds set out in the accompanying brief.",
    "WHEREFORE Defendant respectfully requests that the Court dismiss each",
    "count of the First Amended Complaint with prejudice and award such",
    "further relief as the Court deems just and proper in the circumstances.",
)
_HEADER = "UNITED STATES DISTRICT COURT"
_DIVISION = "SOUTHERN DISTRICT OF EXAMPLE"


def _pdf(pages: tuple[tuple[str, ...], ...]) -> bytes:
    """Build a multi-page PDF whose text layer is exactly ``pages``."""

    output = BytesIO()
    canvas = Canvas(output)
    for lines in pages:
        offset = 720
        for line in lines:
            canvas.drawString(72, offset, line)
            offset -= 14
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def _markdown(pages: tuple[tuple[str, ...], ...]) -> str:
    blocks: list[str] = []
    for number, lines in enumerate(pages, start=1):
        body = "\n\n".join(lines)
        blocks.append(f"##### Page {number}\n\n{body}\n\n---\n")
    return "\n".join(blocks)


def _complete_document() -> tuple[bytes, str]:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES), ("CERTIFICATE OF SERVICE",))
    return _pdf(pages), _markdown(pages)


def test_a_faithful_conversion_is_accepted() -> None:
    source, markdown = _complete_document()

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=markdown
    )

    assert assessment.accepted
    assert assessment.basis == COMPLETENESS_BASIS_PAGE
    assert assessment.incomplete_page_numbers == ()
    assert assessment.pages[0].verdict == PAGE_VERDICT_ACCOUNTED


def test_a_conversion_that_dropped_a_page_body_is_refused() -> None:
    source, _complete = _complete_document()
    gutted = _markdown(((_HEADER, _DIVISION), ("CERTIFICATE OF SERVICE",)))

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=gutted
    )

    assert assessment.rejected
    assert assessment.incomplete_page_numbers == (1,)
    assert assessment.pages[0].verdict == PAGE_VERDICT_INCOMPLETE
    assert assessment.rejection_reasons == ("text_layer_pages_not_accounted:1",)


def test_a_missing_page_section_is_refused_rather_than_excused() -> None:
    source, _complete = _complete_document()
    without_page_one = "##### Page 2\n\nCERTIFICATE OF SERVICE\n"

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=without_page_one
    )

    assert assessment.rejected
    assert assessment.incomplete_page_numbers == (1,)


def test_a_thin_text_layer_page_is_exempt() -> None:
    pages = ((_HEADER,), (_HEADER, _DIVISION, *_BODY_LINES))
    source = _pdf(pages)
    body = "\n\n".join(pages[1])
    # Page 1 converted to nothing at all; its text layer is too thin to judge.
    markdown = f"##### Page 1\n\n---\n\n##### Page 2\n\n{body}\n"

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=markdown
    )

    assert assessment.pages[0].verdict == PAGE_VERDICT_EXEMPT_THIN_LAYER
    assert assessment.pages[0].text_layer_character_count < (
        MINIMUM_PAGE_TEXT_LAYER_CHARACTERS
    )
    assert assessment.accepted


def test_a_page_published_as_an_image_reference_is_exempt() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    imaged = "##### Page 1\n\nP.O. BOX 45881\n\n![img-2.jpeg](pdf-images/img-2.jpeg)\n"

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=imaged
    )

    assert assessment.accepted
    assert assessment.pages[0].verdict == PAGE_VERDICT_EXEMPT_IMAGE_PAGE
    assert assessment.pages[0].retention_ratio is not None
    assert assessment.pages[0].retention_ratio < MINIMUM_TEXT_LAYER_RETENTION_RATIO


def test_a_conversion_without_page_separators_is_compared_whole_document() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES), ("PAGE TWO BODY TEXT",))
    source = _pdf(pages)
    unpaginated = "\n\n".join(line for page in pages for line in page)

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=unpaginated
    )

    assert assessment.accepted
    assert assessment.basis == COMPLETENESS_BASIS_DOCUMENT
    assert assessment.pages == ()


def test_an_unpaginated_conversion_that_lost_its_body_is_still_refused() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES), ("PAGE TWO BODY TEXT",))
    source = _pdf(pages)

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=f"{_HEADER}\n\n{_DIVISION}\n"
    )

    assert assessment.rejected
    assert assessment.basis == COMPLETENESS_BASIS_DOCUMENT
    assert assessment.rejection_reasons == ("text_layer_document_not_accounted",)


def test_duplicate_page_separators_are_refused_not_downgraded() -> None:
    """A converter that claimed pagination and produced nonsense is refused.

    Routing this to the whole-document comparison would let a malformed
    conversion pick the weaker of the two tests, which is the opposite of
    fail-closed.
    """

    pages = ((_HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    body = "\n\n".join(pages[0])
    duplicated = f"##### Page 1\n\n{body}\n\n##### Page 1\n\n{body}\n"

    assert markdown_page_sections(duplicated) is None
    assert attribute_markdown_pages(duplicated)[0] == PAGE_ATTRIBUTION_MALFORMED
    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=duplicated
    )

    assert assessment.rejected
    assert assessment.rejection_reasons == ("text_layer_page_attribution_malformed",)


def test_out_of_range_page_separators_are_refused_not_downgraded() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    body = "\n\n".join(pages[0])

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=f"##### Page 7\n\n{body}\n"
    )

    assert assessment.rejected
    assert assessment.rejection_reasons == ("text_layer_page_attribution_malformed",)


def test_a_pdf_without_a_readable_text_layer_produces_no_verdict() -> None:
    source = _pdf(((), ()))

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown="##### Page 1\n\nanything at all\n"
    )

    assert assessment.accepted
    assert assessment.rejection_reasons == ()


def test_unreadable_bytes_do_not_crash_the_gate() -> None:
    assessment = assess_text_layer_completeness(
        source_pdf_bytes=b"not a pdf at all", markdown="##### Page 1\n\nbody\n"
    )

    assert assessment.accepted
    assert assessment.parsed_page_count == 0


def test_ecf_page_header_stamps_are_stripped_from_both_sides() -> None:
    stamp = "Case 4:25-cv-00170-SEB-KMB Document 22 Filed 12/29/25 Page 1 of 1"
    pages = ((stamp, _HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    # The conversion kept only boilerplate: the stamp plus the centred header.
    gutted = f"##### Page 1\n\n{stamp}\n\n# {_HEADER}\n{_DIVISION}\n"

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=gutted
    )

    assert assessment.rejected
    assert assessment.incomplete_page_numbers == (1,)


def test_an_incidental_image_does_not_exempt_a_page_that_lost_its_body() -> None:
    """A seal or a signature graphic must not buy an exemption.

    This is the difference between "the converter published this page AS an
    image" and "an image happens to appear on this page".  Only the first is
    the converter declaring image content; treating the second as exempt would
    reopen the exact defect this gate closes, because legal filings routinely
    carry small embedded images alongside real body text.
    """

    pages = ((_HEADER, _DIVISION, *_BODY_LINES, *_BODY_LINES, *_BODY_LINES),)
    source = _pdf(pages)
    retained = "\n\n".join(_BODY_LINES[3:6])
    gutted = (
        f"##### Page 1\n\n# {_HEADER}\n{_DIVISION}\n\n"
        f"![img-0.jpeg](pdf-images/img-0.jpeg)\n\n{retained}\n"
    )

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=gutted
    )

    assert assessment.rejected
    assert assessment.incomplete_page_numbers == (1,)
    assert assessment.pages[0].verdict == PAGE_VERDICT_INCOMPLETE


def test_image_markup_is_not_counted_as_retained_document_text() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    long_reference = "![" + "caption " * 40 + "](pdf-images/" + "x" * 300 + ".jpeg)"

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=f"##### Page 1\n\n{long_reference}\n"
    )

    # The reference is long enough to clear the floor on raw character count,
    # but none of it is the document's text.
    assert assessment.pages[0].markdown_character_count == 0
    assert assessment.pages[0].verdict == PAGE_VERDICT_EXEMPT_IMAGE_PAGE


def test_content_before_the_first_page_separator_is_not_attributed() -> None:
    """Unattributable content falls back rather than being blamed on page 1.

    Guessing would be wrong twice over: it would refuse a complete document,
    and a page-scoped repair over that guess would republish the unattributed
    text a second time.
    """

    pages = ((_HEADER, _DIVISION, *_BODY_LINES), ("PAGE TWO BODY TEXT HERE",))
    source = _pdf(pages)
    body = "\n\n".join(pages[0])
    with_preamble = (
        f"{body}\n\n##### Page 1\n\n---\n\n##### Page 2\n\nPAGE TWO BODY TEXT HERE\n"
    )

    assert attribute_markdown_pages(with_preamble)[0] == PAGE_ATTRIBUTION_PREAMBLE
    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=with_preamble
    )

    assert assessment.basis == COMPLETENESS_BASIS_DOCUMENT
    assert assessment.accepted


def test_a_middle_page_is_measured_like_any_other() -> None:
    pages = (
        ("PAGE ONE " + " ".join(_BODY_LINES),),
        (_HEADER, _DIVISION, *_BODY_LINES),
        ("PAGE THREE " + " ".join(_BODY_LINES),),
    )
    source = _pdf(pages)
    markdown = (
        f"##### Page 1\n\n{pages[0][0]}\n\n---\n\n"
        f"##### Page 2\n\n# {_HEADER}\n{_DIVISION}\n\n---\n\n"
        f"##### Page 3\n\n{pages[2][0]}\n"
    )

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=markdown
    )

    assert assessment.rejected
    assert assessment.incomplete_page_numbers == (2,)
