"""Convert acquired docket documents to Markdown with the local parser tool."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.ingestion.provenance import ExtractedTextArtifact, sha256_text

DEFAULT_PARSER_ROOT = Path("~/Development/tools/parser")
DEFAULT_PARSER_TIMEOUT_SECONDS = 600
_PARSER_COMMAND = ("uv", "run", "parser-pdf")


class MistralMarkdownConversionStatus(StrEnum):
    """Machine-readable result for one parser conversion."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class MistralParserConfig:
    """Configuration for the local Mistral parser wrapper."""

    parser_root: Path = DEFAULT_PARSER_ROOT
    timeout_seconds: int = DEFAULT_PARSER_TIMEOUT_SECONDS
    debug: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class MistralMarkdownConversionRequest:
    """One acquired source document that should be converted to Markdown."""

    candidate_id: str
    source_document_id: str
    input_path: Path
    markdown_output_path: Path


@dataclass(frozen=True, slots=True)
class ParserProcessResult:
    """Subprocess result returned by a parser runner."""

    return_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class ParserProcessRunner(Protocol):
    """Explicit dependency for invoking the parser subprocess."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> ParserProcessResult: ...


ParserRunner = ParserProcessRunner


@dataclass(frozen=True, slots=True)
class MistralMarkdownConversionRecord:
    """Markdown conversion result plus reproducibility metadata."""

    candidate_id: str
    source_document_id: str
    status: MistralMarkdownConversionStatus
    input_path: str
    markdown_path: str
    metadata_path: str
    parser_config: dict[str, Any]
    quality_flags: tuple[str, ...]
    extracted_text: ExtractedTextArtifact | None
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "status": self.status.value,
            "input_path": self.input_path,
            "markdown_path": self.markdown_path,
            "metadata_path": self.metadata_path,
            "parser_config": self.parser_config,
            "quality_flags": list(self.quality_flags),
            "extracted_text": (
                None if self.extracted_text is None else self.extracted_text.to_record()
            ),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_message": self.error_message,
        }


class SubprocessParserRunner:
    """Run the parser through ``uv`` with a hard per-document timeout."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> ParserProcessResult:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=os.environ.copy(),
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return ParserProcessResult(
                return_code=124,
                stdout=_coerce_process_text(exc.stdout),
                stderr=_coerce_process_text(exc.stderr),
                timed_out=True,
            )
        return ParserProcessResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def convert_documents_to_markdown(
    requests: tuple[MistralMarkdownConversionRequest, ...],
    *,
    config: MistralParserConfig | None = None,
    runner: ParserProcessRunner | None = None,
    extracted_at: datetime | None = None,
) -> tuple[MistralMarkdownConversionRecord, ...]:
    """Convert documents independently so one parser failure cannot poison a run."""

    parser_config = MistralParserConfig() if config is None else config
    process_runner: ParserProcessRunner = (
        SubprocessParserRunner() if runner is None else runner
    )
    parser_root = parser_config.parser_root.expanduser().resolve()
    if runner is None:
        _require_parser_root(parser_root)
    extraction_time = datetime.now(UTC) if extracted_at is None else extracted_at
    _require_aware(extraction_time, "extracted_at")
    version = _parser_version(parser_root)
    return tuple(
        _convert_one(
            request,
            config=parser_config,
            parser_root=parser_root,
            parser_version=version,
            runner=process_runner,
            extracted_at=extraction_time,
        )
        for request in requests
    )


def _convert_one(
    request: MistralMarkdownConversionRequest,
    *,
    config: MistralParserConfig,
    parser_root: Path,
    parser_version: str | None,
    runner: ParserProcessRunner,
    extracted_at: datetime,
) -> MistralMarkdownConversionRecord:
    input_path = request.input_path.expanduser().resolve()
    markdown_path = request.markdown_output_path.expanduser().resolve()
    metadata_path = markdown_path.with_suffix(".metadata.json")
    artifact_root = markdown_path.parent.parent
    parser_config = _parser_config_record(
        config,
        parser_root=parser_root,
        parser_version=parser_version,
    )

    if not input_path.exists():
        record = _failure_record(
            request,
            input_path=input_path,
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            artifact_root=artifact_root,
            parser_config=parser_config,
            status=MistralMarkdownConversionStatus.FAILED,
            quality_flags=("input_missing",),
            error_message=f"input document not found: {input_path}",
        )
        _write_metadata(metadata_path, record)
        return record

    command = _parser_command(input_path, config)
    result = runner.run(
        command, cwd=parser_root, timeout_seconds=config.timeout_seconds
    )
    parser_config = {**parser_config, "command": list(command)}
    if result.timed_out:
        record = _failure_record(
            request,
            input_path=input_path,
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            artifact_root=artifact_root,
            parser_config=parser_config,
            status=MistralMarkdownConversionStatus.TIMED_OUT,
            quality_flags=("parser_timeout",),
            error_message="parser timed out",
            stdout=result.stdout,
            stderr=result.stderr,
        )
        _write_metadata(metadata_path, record)
        return record
    if result.return_code != 0:
        error_message = (
            result.stderr.strip() or result.stdout.strip() or "parser failed"
        )
        record = _failure_record(
            request,
            input_path=input_path,
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            artifact_root=artifact_root,
            parser_config=parser_config,
            status=MistralMarkdownConversionStatus.FAILED,
            quality_flags=("parser_failed",),
            error_message=error_message,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        _write_metadata(metadata_path, record)
        return record

    generated_markdown_path = input_path.with_suffix(".md")
    if not generated_markdown_path.exists() and markdown_path.exists():
        generated_markdown_path = markdown_path
    if not generated_markdown_path.exists():
        record = _failure_record(
            request,
            input_path=input_path,
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            artifact_root=artifact_root,
            parser_config=parser_config,
            status=MistralMarkdownConversionStatus.FAILED,
            quality_flags=("output_missing",),
            error_message="parser completed without writing markdown",
            stdout=result.stdout,
            stderr=result.stderr,
        )
        _write_metadata(metadata_path, record)
        return record

    markdown = generated_markdown_path.read_text(encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    if generated_markdown_path != markdown_path:
        markdown_path.write_text(markdown, encoding="utf-8")
    quality_flags = () if markdown.strip() else ("empty_markdown",)
    extracted_text = ExtractedTextArtifact(
        source_document_id=request.source_document_id,
        extracted_at=extracted_at,
        extraction_method="mistral_parser_markdown",
        text_sha256=sha256_text(markdown),
        quality_flags=quality_flags,
    )
    record = MistralMarkdownConversionRecord(
        candidate_id=request.candidate_id,
        source_document_id=request.source_document_id,
        status=MistralMarkdownConversionStatus.SUCCEEDED,
        input_path=_relative_or_absolute(input_path, artifact_root),
        markdown_path=_relative_or_absolute(markdown_path, artifact_root),
        metadata_path=_relative_or_absolute(metadata_path, artifact_root),
        parser_config=parser_config,
        quality_flags=quality_flags,
        extracted_text=extracted_text,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    _write_metadata(metadata_path, record)
    return record


def _parser_command(input_path: Path, config: MistralParserConfig) -> tuple[str, ...]:
    command = (
        *_PARSER_COMMAND,
        "--file",
        str(input_path),
        "--mistral",
        "--no-ocr",
    )
    if config.debug:
        return (*command, "--debug")
    return command


def _failure_record(
    request: MistralMarkdownConversionRequest,
    *,
    input_path: Path,
    markdown_path: Path,
    metadata_path: Path,
    artifact_root: Path,
    parser_config: dict[str, Any],
    status: MistralMarkdownConversionStatus,
    quality_flags: tuple[str, ...],
    error_message: str,
    stdout: str = "",
    stderr: str = "",
) -> MistralMarkdownConversionRecord:
    return MistralMarkdownConversionRecord(
        candidate_id=request.candidate_id,
        source_document_id=request.source_document_id,
        status=status,
        input_path=_relative_or_absolute(input_path, artifact_root),
        markdown_path=_relative_or_absolute(markdown_path, artifact_root),
        metadata_path=_relative_or_absolute(metadata_path, artifact_root),
        parser_config=parser_config,
        quality_flags=quality_flags,
        extracted_text=None,
        stdout=stdout,
        stderr=stderr,
        error_message=error_message,
    )


def _write_metadata(
    metadata_path: Path,
    record: MistralMarkdownConversionRecord,
) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(record.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser_config_record(
    config: MistralParserConfig,
    *,
    parser_root: Path,
    parser_version: str | None,
) -> dict[str, Any]:
    return {
        "parser_root": str(parser_root),
        "parser_version": parser_version,
        "timeout_seconds": config.timeout_seconds,
        "debug": config.debug,
        "engine": "mistral",
    }


def _parser_version(parser_root: Path) -> str | None:
    pyproject_path = parser_root / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    with pyproject_path.open("rb") as handle:
        data = cast(dict[str, object], tomllib.load(handle))
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    project_data = cast(dict[str, object], project)
    version = project_data.get("version")
    return version if isinstance(version, str) else None


def _require_parser_root(parser_root: Path) -> None:
    if not (parser_root / "pyproject.toml").is_file():
        raise FileNotFoundError(
            "parser_root must point to the local parser repo with pyproject.toml"
        )


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _coerce_process_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
