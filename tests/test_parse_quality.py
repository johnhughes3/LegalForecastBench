from __future__ import annotations

from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRequest,
    MistralMarkdownConversionStatus,
    MistralParserConfig,
    ParserProcessResult,
    convert_documents_to_markdown,
)
from legalforecast.ingestion.parse_quality import assess_parsed_text


def test_page_stamps_only_are_rejected_after_boilerplate_stripping() -> None:
    assessment = assess_parsed_text(
        "\n".join(
            (
                "##### Page 1",
                "Case 1:26-cv-1 Document 7 Filed 06/01/26 Page 1 of 3",
                "##### Page 2",
                "Case 1:26-cv-1 Document 7 Filed 06/01/26 Page 2 of 3",
            )
        ),
        "complaint",
    )

    assert assessment.rejected
    assert assessment.substantive_character_count == 0
    assert "no_substantive_text" in assessment.rejection_reasons


def test_short_substantive_text_without_a_known_role_is_accepted() -> None:
    assessment = assess_parsed_text("The complaint alleges breach of contract.")

    assert assessment.accepted
    assert assessment.substantive_character_count > 0


def test_short_substantive_text_for_a_known_role_is_rejected() -> None:
    assessment = assess_parsed_text("A short allegation.", "complaint")

    assert assessment.rejected
    assert "insufficient_substantive_characters" in assessment.rejection_reasons


def test_certificate_only_pleading_is_rejected() -> None:
    assessment = assess_parsed_text(
        "CERTIFICATE OF SERVICE\nI hereby certify that a copy was served.",
        "complaint",
    )

    assert assessment.rejected
    assert assessment.substantive_character_count == 0


class _Runner:
    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd,
        timeout_seconds: int,
    ) -> ParserProcessResult:
        del cwd, timeout_seconds
        from pathlib import Path

        source = Path(command[command.index("--file") + 1])
        source.with_suffix(".md").write_text(
            "##### Page 1\nCase 1:26-cv-1 Document 7 Filed 06/01/26 Page 1 of 1",
            encoding="utf-8",
        )
        return ParserProcessResult(return_code=0)


def test_parser_conversion_rejects_stamps_only_and_publishes_no_markdown(
    tmp_path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF fixture")
    output = tmp_path / "markdown" / "source.md"

    (record,) = convert_documents_to_markdown(
        (
            MistralMarkdownConversionRequest(
                candidate_id="candidate",
                source_document_id="source",
                input_path=source,
                markdown_output_path=output,
                document_role="complaint",
            ),
        ),
        config=MistralParserConfig(parser_root=tmp_path / "parser"),
        runner=_Runner(),
    )

    assert record.status is MistralMarkdownConversionStatus.FAILED
    assert record.quality_flags == ("parse_quality_rejected",)
    assert not output.exists()
