from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRequest,
    MistralMarkdownConversionStatus,
    MistralParserConfig,
    ParserProcessResult,
    convert_documents_to_markdown,
)


def test_parser_wrapper_writes_markdown_metadata_and_quality_flags(tmp_path) -> None:
    source_pdf = tmp_path / "doc-1.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nfixture\n%%EOF\n")
    runner = _FixtureRunner({"doc-1.pdf": _FixtureAction(markdown="# Parsed\n\nText")})

    records = convert_documents_to_markdown(
        (
            MistralMarkdownConversionRequest(
                candidate_id="cand-1",
                source_document_id="doc-1",
                input_path=source_pdf,
                markdown_output_path=tmp_path / "markdown" / "doc-1.md",
            ),
        ),
        config=MistralParserConfig(
            parser_root=tmp_path / "parser",
            timeout_seconds=12,
        ),
        runner=runner,
        extracted_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    record = records[0]
    assert record.status is MistralMarkdownConversionStatus.SUCCEEDED
    assert (tmp_path / "markdown" / "doc-1.md").read_text(encoding="utf-8") == (
        "# Parsed\n\nText"
    )
    assert record.metadata_path == "markdown/doc-1.metadata.json"
    assert (tmp_path / "markdown" / "doc-1.metadata.json").is_file()
    assert record.extracted_text is not None
    assert record.extracted_text.extraction_method == "mistral_parser_markdown"
    assert record.extracted_text.quality_flags == ()
    assert record.parser_config["timeout_seconds"] == 12
    assert runner.commands[0][0:3] == ("uv", "run", "parser-pdf")
    assert "--mistral" in runner.commands[0]


def test_parser_wrapper_records_failures_without_corrupting_other_documents(
    tmp_path,
) -> None:
    ok_pdf = tmp_path / "ok.pdf"
    bad_pdf = tmp_path / "bad.pdf"
    ok_pdf.write_bytes(b"%PDF-1.4\nok\n%%EOF\n")
    bad_pdf.write_bytes(b"%PDF-1.4\nbad\n%%EOF\n")
    runner = _FixtureRunner(
        {
            "ok.pdf": _FixtureAction(markdown="ok markdown"),
            "bad.pdf": _FixtureAction(return_code=1, stderr="parser failed"),
        }
    )

    records = convert_documents_to_markdown(
        (
            _request("ok", ok_pdf, tmp_path / "out" / "ok.md"),
            _request("bad", bad_pdf, tmp_path / "out" / "bad.md"),
        ),
        config=MistralParserConfig(parser_root=tmp_path / "parser"),
        runner=runner,
        extracted_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert [record.status for record in records] == [
        MistralMarkdownConversionStatus.SUCCEEDED,
        MistralMarkdownConversionStatus.FAILED,
    ]
    assert records[1].quality_flags == ("parser_failed",)
    assert records[1].error_message == "parser failed"
    assert records[1].extracted_text is None
    assert not (tmp_path / "out" / "bad.md").exists()


def test_parser_wrapper_records_timeout_as_document_failure(tmp_path) -> None:
    source_pdf = tmp_path / "timeout.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\ntimeout\n%%EOF\n")
    runner = _FixtureRunner({"timeout.pdf": _FixtureAction(timed_out=True)})

    records = convert_documents_to_markdown(
        (_request("timeout", source_pdf, tmp_path / "out" / "timeout.md"),),
        config=MistralParserConfig(parser_root=tmp_path / "parser", timeout_seconds=1),
        runner=runner,
        extracted_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert records[0].status is MistralMarkdownConversionStatus.TIMED_OUT
    assert records[0].quality_flags == ("parser_timeout",)
    assert records[0].error_message == "parser timed out"


def test_each_source_is_rehashed_immediately_before_its_spawn(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"%PDF first")
    second.write_bytes(b"%PDF second")
    second_digest = hashlib.sha256(second.read_bytes()).hexdigest()
    runner = _MutatingRunner(second)

    with pytest.raises(ValueError, match="source hash changed before spawn"):
        convert_documents_to_markdown(
            (
                _request("first", first, tmp_path / "out" / "first.md"),
                MistralMarkdownConversionRequest(
                    candidate_id="cand-1",
                    source_document_id="second",
                    input_path=second,
                    markdown_output_path=tmp_path / "out" / "second.md",
                    expected_sha256=second_digest,
                    expected_byte_count=second.stat().st_size,
                ),
            ),
            config=MistralParserConfig(parser_root=tmp_path / "parser"),
            runner=runner,
        )


@pytest.mark.skipif(
    os.environ.get("LEGALFORECAST_RUN_REAL_MISTRAL_PARSER") != "1",
    reason="Real Mistral parser smoke is opt-in; fixture tests cover default CI.",
)
def test_real_mistral_parser_optional_smoke() -> None:
    assert Path("~/Development/tools/parser").expanduser().exists()


def _request(
    source_document_id: str,
    input_path: Path,
    output_path: Path,
) -> MistralMarkdownConversionRequest:
    return MistralMarkdownConversionRequest(
        candidate_id="cand-1",
        source_document_id=source_document_id,
        input_path=input_path,
        markdown_output_path=output_path,
    )


class _FixtureAction:
    def __init__(
        self,
        *,
        markdown: str | None = None,
        return_code: int = 0,
        stdout: str = '{"status":"ok"}',
        stderr: str = "",
        timed_out: bool = False,
    ) -> None:
        self.markdown = markdown
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


class _FixtureRunner:
    def __init__(self, actions_by_filename: dict[str, _FixtureAction]) -> None:
        self.actions_by_filename = actions_by_filename
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> ParserProcessResult:
        del cwd, timeout_seconds
        self.commands.append(command)
        input_path = Path(command[command.index("--file") + 1])
        action = self.actions_by_filename[input_path.name]
        if action.markdown is not None:
            input_path.with_suffix(".md").write_text(action.markdown, encoding="utf-8")
        return ParserProcessResult(
            return_code=action.return_code,
            stdout=action.stdout,
            stderr=action.stderr,
            timed_out=action.timed_out,
        )


class _MutatingRunner:
    def __init__(self, target: Path) -> None:
        self.target = target

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> ParserProcessResult:
        del command, cwd, timeout_seconds
        self.target.write_bytes(b"tampered while first document parsed")
        return ParserProcessResult(return_code=1, stderr="fixture failure")
