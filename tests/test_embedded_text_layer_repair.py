"""Page-scoped repair of a conversion that dropped pages, and its provenance.

Every PDF here is generated in-process (synthetic: true); no corpus document
appears in this file.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from legalforecast.ingestion.embedded_text_layer_repair import (
    EMBEDDED_TEXT_LAYER_REPAIR_ENGINE,
    EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
    EMBEDDED_TEXT_LAYER_REPAIR_REVISION,
    embedded_text_layer_repair_parser_config,
    embedded_text_layer_repair_record_problem,
    plan_embedded_text_layer_repair,
)
from legalforecast.ingestion.live_parse_record_provenance import (
    live_parse_record_provenance_problem,
)
from legalforecast.ingestion.mistral_markdown_parser import (
    EXPECTED_PARSER_REVISION,
    MistralMarkdownConversionRequest,
    MistralMarkdownConversionStatus,
    convert_documents_to_markdown,
    with_embedded_text_layer_repairs,
)
from legalforecast.ingestion.provenance import sha256_text
from legalforecast.ingestion.text_layer_completeness import (
    assess_text_layer_completeness,
)
from reportlab.pdfgen.canvas import Canvas

_TITLE = "MOTION TO DISMISS UNDER RULES 12(b)(5) AND 12(b)(6)"
_BODY = (
    "UNITED STATES DISTRICT COURT",
    "SOUTHERN DISTRICT OF EXAMPLE",
    _TITLE,
    "COMES NOW Defendant Example Corporation, by counsel, and moves this",
    "Court to dismiss the First Amended Complaint because it fails to state",
    "a claim upon which relief can be granted under the governing standard.",
    "WHEREFORE Defendant respectfully requests dismissal with prejudice and",
    "such further relief as the Court deems just and proper in the premises.",
)
_PAGE_TWO = (
    "SIGNED this day by counsel of record for the moving defendant, whose",
    "name, bar number, address, telephone number and electronic mail address",
    "appear below in the manner required by the local rules of this Court.",
)


def _pdf(pages: tuple[tuple[str, ...], ...]) -> bytes:
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


def _source() -> bytes:
    return _pdf((_BODY, _PAGE_TWO))


def _gutted_markdown() -> str:
    page_two = "\n\n".join(_PAGE_TWO)
    return (
        "##### Page 1\n\n"
        "# UNITED STATES DISTRICT COURT\nSOUTHERN DISTRICT OF EXAMPLE\n\n"
        "---\n\n"
        f"##### Page 2\n\n{page_two}\n\n---\n"
    )


def test_the_repair_recovers_the_dropped_page_and_keeps_the_others() -> None:
    source = _source()
    gutted = _gutted_markdown()

    repair = plan_embedded_text_layer_repair(source_pdf_bytes=source, markdown=gutted)

    assert repair is not None
    assert repair.repaired_page_numbers == (1,)
    assert repair.parsed_page_count == 2
    assert repair.superseded_text_sha256 == sha256_text(gutted)
    # The dropped title and operative paragraph are back.
    assert _TITLE in repair.markdown
    assert "COMES NOW Defendant Example Corporation" in repair.markdown
    # The page that converted correctly is untouched, character for character.
    assert _PAGE_TWO[0] in repair.markdown
    assert repair.markdown.count("##### Page 2") == 1
    assert assess_text_layer_completeness(
        source_pdf_bytes=source, markdown=repair.markdown
    ).accepted


def test_a_faithful_conversion_has_nothing_to_repair() -> None:
    source = _source()
    faithful = (
        "##### Page 1\n\n"
        + "\n\n".join(_BODY)
        + "\n\n---\n\n##### Page 2\n\n"
        + "\n\n".join(_PAGE_TWO)
        + "\n\n---\n"
    )

    assert (
        plan_embedded_text_layer_repair(source_pdf_bytes=source, markdown=faithful)
        is None
    )


def test_loss_that_cannot_be_attributed_to_pages_is_not_repaired() -> None:
    # No page separators: the loss is real but a page splice would be a guess.
    assert (
        plan_embedded_text_layer_repair(
            source_pdf_bytes=_source(),
            markdown="UNITED STATES DISTRICT COURT\nSOUTHERN DISTRICT OF EXAMPLE\n",
        )
        is None
    )


def test_a_document_with_no_text_layer_is_not_repairable() -> None:
    assert (
        plan_embedded_text_layer_repair(
            source_pdf_bytes=_pdf(((), ())),
            markdown="##### Page 1\n\nnothing\n\n---\n",
        )
        is None
    )


def _repair_request(tmp_path: Path) -> MistralMarkdownConversionRequest:
    source = _source()
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(source)
    return MistralMarkdownConversionRequest(
        candidate_id="70310251",
        source_document_id="468158052",
        input_path=source_path,
        markdown_output_path=tmp_path / "markdown" / "70310251" / "468158052.md",
        expected_sha256=hashlib.sha256(source).hexdigest(),
        expected_byte_count=len(source),
        captured_source_bytes=source,
        document_role="motion_to_dismiss_memorandum",
    )


def test_a_repaired_conversion_never_starts_the_parser_subprocess(
    tmp_path: Path,
) -> None:
    def _explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("the parser subprocess must not run for a repair")

    class _RefusingRunner:
        run = _explode

    request = _repair_request(tmp_path)
    requests = with_embedded_text_layer_repairs(
        (request,),
        superseded_markdown_by_key={
            (
                request.candidate_id,
                request.source_document_id,
                str(request.expected_sha256),
                int(request.expected_byte_count or 0),
            ): _gutted_markdown().encode()
        },
    )
    assert requests[0].embedded_text_layer_repair is not None

    (record,) = convert_documents_to_markdown(
        requests,
        runner=_RefusingRunner(),
        extracted_at=datetime(2026, 8, 19, tzinfo=UTC),
    )

    assert record.status is MistralMarkdownConversionStatus.SUCCEEDED
    assert record.stdout == ""
    assert record.stderr == ""
    published = requests[0].markdown_output_path.read_text(encoding="utf-8")
    assert _TITLE in published
    assert record.extracted_text is not None
    assert record.extracted_text.extraction_method == EMBEDDED_TEXT_LAYER_REPAIR_METHOD
    assert record.extracted_text.page_count == 2
    assert record.parser_config["repaired_page_numbers"] == [1]
    assert record.parser_config["pinned_parser_revision"] == EXPECTED_PARSER_REVISION
    # The repair must not claim what produced the conversion it supersedes: a
    # repair can supersede another repair.
    assert "superseded_engine" not in record.parser_config


def test_the_repaired_record_is_reusable_and_names_its_own_method(
    tmp_path: Path,
) -> None:
    source = _source()
    gutted = _gutted_markdown()
    repair = plan_embedded_text_layer_repair(source_pdf_bytes=source, markdown=gutted)
    assert repair is not None
    record = {
        "status": "succeeded",
        "source_document_id": "468158052",
        "quality_flags": [],
        "parser_config": embedded_text_layer_repair_parser_config(
            repair, pinned_parser_revision=EXPECTED_PARSER_REVISION
        ),
        "extracted_text": {
            "source_document_id": "468158052",
            "extraction_method": EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
            "text_sha256": sha256_text(repair.markdown),
            "page_count": 2,
            "quality_flags": [],
            "notes": repair.notes,
        },
    }

    assert (
        live_parse_record_provenance_problem(record, markdown=repair.markdown) is None
    )
    assert record["parser_config"]["engine"] == EMBEDDED_TEXT_LAYER_REPAIR_ENGINE
    assert record["parser_config"]["repair_revision"] == (
        EMBEDDED_TEXT_LAYER_REPAIR_REVISION
    )


def test_a_repair_record_that_claims_a_provider_conversion_is_refused() -> None:
    source = _source()
    repair = plan_embedded_text_layer_repair(
        source_pdf_bytes=source, markdown=_gutted_markdown()
    )
    assert repair is not None
    config = embedded_text_layer_repair_parser_config(
        repair, pinned_parser_revision=EXPECTED_PARSER_REVISION
    )
    record = {
        "status": "succeeded",
        "source_document_id": "468158052",
        "quality_flags": [],
        "parser_config": {**config, "engine": "mistral"},
        "extracted_text": {
            "source_document_id": "468158052",
            "extraction_method": EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
            "text_sha256": sha256_text(repair.markdown),
            "page_count": 2,
            "quality_flags": [],
            "notes": repair.notes,
        },
    }

    problem = embedded_text_layer_repair_record_problem(
        record,
        markdown=repair.markdown,
        expected_parser_revision=EXPECTED_PARSER_REVISION,
    )

    assert problem is not None
    assert "unclean" in problem


def test_a_repair_record_that_changed_nothing_is_refused() -> None:
    source = _source()
    gutted = _gutted_markdown()
    repair = plan_embedded_text_layer_repair(source_pdf_bytes=source, markdown=gutted)
    assert repair is not None
    config = embedded_text_layer_repair_parser_config(
        repair, pinned_parser_revision=EXPECTED_PARSER_REVISION
    )
    record = {
        "status": "succeeded",
        "source_document_id": "468158052",
        "quality_flags": [],
        "parser_config": {**config, "superseded_text_sha256": sha256_text(gutted)},
        "extracted_text": {
            "source_document_id": "468158052",
            "extraction_method": EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
            "text_sha256": sha256_text(gutted),
            "page_count": 2,
            "quality_flags": [],
            "notes": repair.notes,
        },
    }

    problem = embedded_text_layer_repair_record_problem(
        record,
        markdown=gutted,
        expected_parser_revision=EXPECTED_PARSER_REVISION,
    )

    assert problem == "repaired conversion did not change the superseded Markdown"


def test_a_repair_of_a_repair_does_not_claim_a_provider_predecessor() -> None:
    """The second hop must not assert that it superseded a provider conversion.

    A repaired record is reusable, so it can itself be superseded later — after
    a threshold or role change — and be repaired again.  Hardcoding the
    predecessor's engine would make that second record state something false
    about provenance, which is the ambiguity this module exists to remove.
    """

    source = _source()
    repair = plan_embedded_text_layer_repair(
        source_pdf_bytes=source, markdown=_gutted_markdown()
    )
    assert repair is not None
    config = embedded_text_layer_repair_parser_config(
        repair, pinned_parser_revision=EXPECTED_PARSER_REVISION
    )

    assert "superseded_engine" not in config
    # The predecessor is named exactly, by digest, with no claim about origin.
    assert config["superseded_text_sha256"] == repair.superseded_text_sha256
    assert config["pinned_parser_revision"] == EXPECTED_PARSER_REVISION


def test_a_repair_record_pinned_to_another_parser_generation_is_refused() -> None:
    source = _source()
    repair = plan_embedded_text_layer_repair(
        source_pdf_bytes=source, markdown=_gutted_markdown()
    )
    assert repair is not None
    record = {
        "status": "succeeded",
        "source_document_id": "468158052",
        "quality_flags": [],
        "parser_config": embedded_text_layer_repair_parser_config(
            repair, pinned_parser_revision="0" * 40
        ),
        "extracted_text": {
            "source_document_id": "468158052",
            "extraction_method": EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
            "text_sha256": sha256_text(repair.markdown),
            "page_count": 2,
            "quality_flags": [],
            "notes": repair.notes,
        },
    }

    problem = embedded_text_layer_repair_record_problem(
        record,
        markdown=repair.markdown,
        expected_parser_revision=EXPECTED_PARSER_REVISION,
    )

    assert problem is not None
    assert "unclean" in problem


def test_a_conversion_with_unattributable_pages_is_never_page_repaired() -> None:
    """Loss the gate could not attribute to pages must not be spliced.

    Splicing over a guess would republish unattributed text a second time, so
    the repair refuses rather than improvising.
    """

    source = _source()
    body = "\n\n".join(_BODY)
    preamble = f"{body}\n\n##### Page 1\n\n---\n\n##### Page 2\n\n" + "\n\n".join(
        _PAGE_TWO
    )

    assert (
        plan_embedded_text_layer_repair(source_pdf_bytes=source, markdown=preamble)
        is None
    )
