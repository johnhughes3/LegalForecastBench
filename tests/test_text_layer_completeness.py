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
    PAGE_VERDICT_ACCOUNTED,
    PAGE_VERDICT_EXEMPT_IMAGE_PAGE,
    PAGE_VERDICT_EXEMPT_THIN_LAYER,
    PAGE_VERDICT_INCOMPLETE,
    assess_text_layer_completeness,
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


def test_duplicate_page_separators_fall_back_to_the_document_comparison() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    body = "\n\n".join(pages[0])
    duplicated = f"##### Page 1\n\n{body}\n\n##### Page 1\n\n{body}\n"

    assert markdown_page_sections(duplicated) is None
    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=duplicated
    )

    assert assessment.basis == COMPLETENESS_BASIS_DOCUMENT
    assert assessment.accepted


def test_out_of_range_page_separators_fall_back_to_the_document_comparison() -> None:
    pages = ((_HEADER, _DIVISION, *_BODY_LINES),)
    source = _pdf(pages)
    body = "\n\n".join(pages[0])

    assessment = assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=f"##### Page 7\n\n{body}\n"
    )

    assert assessment.basis == COMPLETENESS_BASIS_DOCUMENT
    assert assessment.accepted


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
