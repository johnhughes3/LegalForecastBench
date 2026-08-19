"""Convert acquired docket documents to Markdown with the local parser tool."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import subprocess
import tomllib
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.ingestion.parse_quality import (
    PARSE_QUALITY_REJECTION_FLAG,
    assess_parsed_text,
)
from legalforecast.ingestion.provenance import ExtractedTextArtifact, sha256_text

DEFAULT_PARSER_ROOT = Path("~/Development/tools/parser")
DEFAULT_PARSER_TIMEOUT_SECONDS = 600
_PARSER_COMMAND = ("uv", "run", "parser-pdf")
EXPECTED_PARSER_REVISION = "9402306972462a5bdd0da7f687c5e6b4cea373a0"
_ENV_ONLY_API_KEYS_VARIABLE = "PARSER_API_KEYS_FROM_ENV_ONLY"
_PARSER_LOCALE_ENV_NAMES = ("LANG", "LC_ALL")
_PARSER_IMAGE_DIRECTORY = "pdf-images"


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
    expected_sha256: str | None = None
    expected_byte_count: int | None = None
    captured_source_bytes: bytes | None = None
    # Optional trailing field preserves positional compatibility with existing
    # callers while allowing role-aware quality thresholds for live manifests.
    document_role: str | None = None
    # True only when the *authenticated* materialization manifest marks this
    # document ``parser_eligible: false``.  Those rows state no ``document_role``
    # anywhere upstream, so the live path must be able to tell an authenticated
    # role-less row apart from an unauthenticated one instead of refusing both.
    parser_role_exempt: bool = False


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
    source_sha256: str | None = None
    source_byte_count: int | None = None
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
            "source_sha256": self.source_sha256,
            "source_byte_count": self.source_byte_count,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_message": self.error_message,
        }


class SubprocessParserRunner:
    """Run the parser through ``uv`` with a hard per-document timeout."""

    def __init__(self, *, parent_env: Mapping[str, str] | None = None) -> None:
        source_env = os.environ if parent_env is None else parent_env
        self._child_env = _build_parser_subprocess_env(source_env)

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
                env=self._child_env,
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
    """Isolate ordinary failures; abort on staging or output safety violations."""

    if not requests:
        return ()
    parser_config = MistralParserConfig() if config is None else config
    process_runner: ParserProcessRunner = (
        SubprocessParserRunner() if runner is None else runner
    )
    parser_root = parser_config.parser_root.expanduser().resolve()
    parser_revision: str | None = None
    if runner is None:
        _require_parser_root(parser_root)
        parser_revision = _require_parser_revision(parser_root)
    extraction_time = datetime.now(UTC) if extracted_at is None else extracted_at
    _require_aware(extraction_time, "extracted_at")
    version = _parser_version(parser_root)
    return tuple(
        _convert_one(
            request,
            config=parser_config,
            parser_root=parser_root,
            parser_version=version,
            parser_revision=parser_revision,
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
    parser_revision: str | None,
    runner: ParserProcessRunner,
    extracted_at: datetime,
) -> MistralMarkdownConversionRecord:
    input_path = request.input_path.expanduser().resolve()
    markdown_path = Path(os.path.abspath(request.markdown_output_path.expanduser()))
    metadata_path = markdown_path.with_suffix(".metadata.json")
    artifact_root = markdown_path.parent.parent
    parser_config = _parser_config_record(
        config,
        parser_root=parser_root,
        parser_version=parser_version,
        parser_revision=parser_revision,
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

    if request.captured_source_bytes is None:
        _verify_source_commitments(request, input_path)
    with _parser_input_snapshot(
        request, input_path=input_path, artifact_root=artifact_root
    ) as (parser_input_path, parser_input_directory_fd):
        record, markdown_payload = _run_verified_conversion(
            request,
            input_path=input_path,
            parser_input_path=parser_input_path,
            parser_input_directory_fd=parser_input_directory_fd,
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            artifact_root=artifact_root,
            parser_config=parser_config,
            config=config,
            parser_root=parser_root,
            runner=runner,
            extracted_at=extracted_at,
        )
    if markdown_payload is not None:
        _write_unique_regular_file(markdown_path, markdown_payload)
    _write_metadata(metadata_path, record)
    return record


def _run_verified_conversion(
    request: MistralMarkdownConversionRequest,
    *,
    input_path: Path,
    parser_input_path: Path,
    parser_input_directory_fd: int | None,
    markdown_path: Path,
    metadata_path: Path,
    artifact_root: Path,
    parser_config: dict[str, Any],
    config: MistralParserConfig,
    parser_root: Path,
    runner: ParserProcessRunner,
    extracted_at: datetime,
) -> tuple[MistralMarkdownConversionRecord, bytes | None]:
    generated_markdown_path = parser_input_path.with_suffix(".md")
    if parser_input_directory_fd is not None and _entry_exists_at(
        parser_input_directory_fd, generated_markdown_path.name
    ):
        _safe_unlink_staging_entry(
            parser_input_directory_fd, generated_markdown_path.name
        )
    elif parser_input_path != input_path and generated_markdown_path.exists():
        _safe_unlink_staging_file(generated_markdown_path, artifact_root=artifact_root)
    command = _parser_command(parser_input_path, config)
    result = runner.run(
        command, cwd=parser_root, timeout_seconds=config.timeout_seconds
    )
    if request.captured_source_bytes is not None:
        if parser_input_directory_fd is None:
            raise AssertionError("captured parser source lacks pinned directory")
        _require_stage_directory_unchanged(
            parser_input_path.parent, parser_input_directory_fd
        )
        _require_staged_source_unchanged_at(
            parser_input_directory_fd,
            parser_input_path.name,
            bytes(request.captured_source_bytes),
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
        return record, None
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
        return record, None

    generated_markdown: bytes | None = None
    try:
        if parser_input_directory_fd is not None:
            if _entry_exists_at(
                parser_input_directory_fd, generated_markdown_path.name
            ):
                generated_markdown = _read_unique_regular_file_at(
                    parser_input_directory_fd, generated_markdown_path.name
                )
        else:
            if not generated_markdown_path.exists() and markdown_path.exists():
                generated_markdown_path = markdown_path
            if generated_markdown_path.exists():
                generated_markdown = _read_unique_regular_file(generated_markdown_path)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"parser Markdown output is unsafe: {generated_markdown_path}"
        ) from exc
    if generated_markdown is None:
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
        return record, None

    try:
        markdown = generated_markdown.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            f"parser Markdown output is unsafe: {generated_markdown_path}"
        ) from exc
    # Preserve the output-path safety boundary even when the quality gate
    # rejects the payload and therefore intentionally publishes no Markdown.
    _validate_existing_output_path(markdown_path)
    assessment = assess_parsed_text(markdown, request.document_role)
    if assessment.rejected:
        record = _failure_record(
            request,
            input_path=input_path,
            markdown_path=markdown_path,
            metadata_path=metadata_path,
            artifact_root=artifact_root,
            parser_config=parser_config,
            status=MistralMarkdownConversionStatus.FAILED,
            quality_flags=(PARSE_QUALITY_REJECTION_FLAG,),
            error_message=(
                "parser output failed parse-quality gate: "
                + ", ".join(assessment.rejection_reasons)
            ),
            stdout=result.stdout,
            stderr=result.stderr,
        )
        return record, None
    quality_flags = ()
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
        source_sha256=request.expected_sha256,
        source_byte_count=request.expected_byte_count,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    return record, generated_markdown


def _verify_source_commitments(
    request: MistralMarkdownConversionRequest, input_path: Path
) -> None:
    """Verify this document immediately before its parser subprocess starts."""

    if request.expected_sha256 is None and request.expected_byte_count is None:
        return
    if request.expected_sha256 is None or request.expected_byte_count is None:
        raise ValueError("parser source commitments require hash and byte count")
    data = input_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != request.expected_sha256:
        raise ValueError(
            f"parser source hash changed before spawn: {request.source_document_id}"
        )
    if len(data) != request.expected_byte_count:
        raise ValueError(
            "parser source byte count changed before spawn: "
            f"{request.source_document_id}"
        )


def _verify_captured_source_commitments(
    request: MistralMarkdownConversionRequest, payload: bytes
) -> None:
    if request.expected_sha256 is None or request.expected_byte_count is None:
        raise ValueError("captured parser source requires hash and byte count")
    if hashlib.sha256(payload).hexdigest() != request.expected_sha256:
        raise ValueError(
            f"captured parser source hash mismatch: {request.source_document_id}"
        )
    if len(payload) != request.expected_byte_count:
        raise ValueError(
            f"captured parser source byte count mismatch: {request.source_document_id}"
        )


@contextmanager
def _parser_input_snapshot(
    request: MistralMarkdownConversionRequest,
    *,
    input_path: Path,
    artifact_root: Path,
) -> Generator[tuple[Path, int | None]]:
    if request.captured_source_bytes is None:
        yield input_path, None
        return
    payload = bytes(request.captured_source_bytes)
    _verify_captured_source_commitments(request, payload)
    stage_path, directory_fd = _stage_captured_source(
        request,
        payload=payload,
        artifact_root=artifact_root,
        suffix=input_path.suffix,
    )
    try:
        yield stage_path, directory_fd
    except BaseException:
        try:
            _cleanup_parser_input_snapshot(stage_path, directory_fd)
        except BaseException:
            # Teardown must not replace the parser or verification failure that
            # caused this context to unwind.
            pass
        raise
    else:
        _cleanup_parser_input_snapshot(stage_path, directory_fd)


def _cleanup_parser_input_snapshot(stage_path: Path, directory_fd: int) -> None:
    cleanup_error: Exception | None = None
    directory_is_current = False
    try:
        for name in (stage_path.with_suffix(".md").name, stage_path.name):
            try:
                if _entry_exists_at(directory_fd, name):
                    _safe_unlink_staging_entry(directory_fd, name)
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        try:
            _drain_parser_image_staging_entries(
                directory_fd, expected_stem=stage_path.stem
            )
        except Exception as exc:
            if cleanup_error is None:
                cleanup_error = exc
        try:
            _drain_unique_regular_staging_entries(directory_fd)
        except Exception as exc:
            if cleanup_error is None:
                cleanup_error = exc
        directory_is_current = _stage_directory_is_current(
            stage_path.parent, directory_fd
        )
    finally:
        os.close(directory_fd)

    if directory_is_current:
        digest_dir = stage_path.parent
        stage_root = digest_dir.parent
        try:
            digest_dir.rmdir()
        except OSError as exc:
            if cleanup_error is None:
                cleanup_error = exc
        else:
            try:
                stage_root.rmdir()
            except OSError:
                # Another conversion may still own the shared staging root.
                pass
    if cleanup_error is not None:
        raise cleanup_error


def _drain_parser_image_staging_entries(
    directory_fd: int, *, expected_stem: str
) -> None:
    """Remove only the pinned parser's documented image-output directory."""

    if not _entry_exists_at(directory_fd, _PARSER_IMAGE_DIRECTORY):
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        images_fd = os.open(_PARSER_IMAGE_DIRECTORY, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise ValueError(
            f"parser staging cleanup found an unsafe alias: {_PARSER_IMAGE_DIRECTORY}"
        ) from exc
    try:
        image_roots = os.listdir(images_fd)
        if image_roots != [expected_stem]:
            raise ValueError(
                "parser staging cleanup found an unsafe image directory: "
                + ", ".join(sorted(image_roots))
            )
        try:
            image_root_fd = os.open(expected_stem, flags, dir_fd=images_fd)
        except OSError as exc:
            raise ValueError(
                f"parser staging cleanup found an unsafe alias: {expected_stem}"
            ) from exc
        try:
            for name in sorted(os.listdir(image_root_fd)):
                metadata = os.stat(name, dir_fd=image_root_fd, follow_symlinks=False)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError(
                        f"parser staging cleanup found an unsafe alias: {name}"
                    )
                os.unlink(name, dir_fd=image_root_fd)
        finally:
            os.close(image_root_fd)
        os.rmdir(expected_stem, dir_fd=images_fd)
    finally:
        os.close(images_fd)
    os.rmdir(_PARSER_IMAGE_DIRECTORY, dir_fd=directory_fd)


def _drain_unique_regular_staging_entries(directory_fd: int) -> None:
    cleanup_error: Exception | None = None
    for name in sorted(os.listdir(directory_fd)):
        try:
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(
                    f"parser staging cleanup found an unsafe alias: {name}"
                )
            os.unlink(name, dir_fd=directory_fd)
            raise ValueError(f"unexpected parser staging residue: {name}")
        except Exception as exc:
            if cleanup_error is None:
                cleanup_error = exc
    if cleanup_error is not None:
        raise cleanup_error


def _stage_captured_source(
    request: MistralMarkdownConversionRequest,
    *,
    payload: bytes,
    artifact_root: Path,
    suffix: str,
) -> tuple[Path, int]:
    digest = hashlib.sha256(payload).hexdigest()
    stage_root = artifact_root / ".parser-source-snapshots"
    stage_dir = stage_root / f"{digest}-{secrets.token_hex(8)}"
    directory_fd = _open_or_create_directory_fd(stage_dir)
    stage_path = stage_dir / f"source{suffix or '.bin'}"
    try:
        _write_unique_regular_file_at(directory_fd, stage_path.name, payload)
        _require_staged_source_unchanged_at(directory_fd, stage_path.name, payload)
    except BaseException:
        os.close(directory_fd)
        raise
    return stage_path, directory_fd


def _safe_unlink_staging_file(path: Path, *, artifact_root: Path) -> None:
    if not Path(os.path.abspath(path)).is_relative_to(
        Path(os.path.abspath(artifact_root))
    ):
        raise ValueError(f"parser staging cleanup escapes artifact root: {path}")
    metadata = path.lstat()
    if stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"parser staging cleanup found a directory: {path}")
    if stat.S_ISREG(metadata.st_mode):
        path.chmod(0o600, follow_symlinks=False)
    path.unlink()


def _entry_exists_at(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _safe_unlink_staging_entry(directory_fd: int, name: str) -> None:
    metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"parser staging cleanup found a directory: {name}")
    os.unlink(name, dir_fd=directory_fd)


def _stage_directory_is_current(path: Path, directory_fd: int) -> bool:
    try:
        current = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    pinned = os.fstat(directory_fd)
    return (
        stat.S_ISDIR(current.st_mode)
        and current.st_dev == pinned.st_dev
        and current.st_ino == pinned.st_ino
    )


def _require_stage_directory_unchanged(path: Path, directory_fd: int) -> None:
    if not _stage_directory_is_current(path, directory_fd):
        raise ValueError(f"parser source staging directory changed: {path}")


def _require_staged_source_unchanged_at(
    directory_fd: int, name: str, payload: bytes
) -> None:
    if _read_unique_regular_file_at(directory_fd, name) != payload:
        raise ValueError(f"parser source staging bytes changed: {name}")


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
        source_sha256=request.expected_sha256,
        source_byte_count=request.expected_byte_count,
        stdout=stdout,
        stderr=stderr,
        error_message=error_message,
    )


def _write_metadata(
    metadata_path: Path,
    record: MistralMarkdownConversionRecord,
) -> None:
    _write_unique_regular_file(
        metadata_path,
        (json.dumps(record.to_record(), indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )


def _write_unique_regular_file(path: Path, payload: bytes) -> None:
    """Atomically publish bytes without following links or writing hardlinks."""

    directory_fd = _open_or_create_directory_fd(path.parent)
    temporary_name = f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    try:
        try:
            existing_fd = os.open(
                path.name,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            existing_fd = None
        if existing_fd is not None:
            try:
                metadata = os.fstat(existing_fd)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError(f"parser output path is unsafe: {path}")
            finally:
                os.close(existing_fd)
        temporary_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            view = memoryview(payload)
            while view:
                written = os.write(temporary_fd, view)
                view = view[written:]
            os.fsync(temporary_fd)
        finally:
            os.close(temporary_fd)
        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
        if not _stage_directory_is_current(path.parent, directory_fd):
            raise ValueError(
                f"parser output parent changed during publish: {path.parent}"
            )
    finally:
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except FileNotFoundError:
            # Atomic publication may already have consumed the temporary name.
            pass
        os.close(directory_fd)


def _validate_existing_output_path(path: Path) -> None:
    """Reject a pre-existing output alias before any quality decision."""

    parent_fd: int | None = None
    existing_fd: int | None = None
    try:
        parent_fd = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        existing_fd = os.open(
            path.name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return
    except OSError:
        # Preserve the kernel's O_NOFOLLOW error for symlink and alias tests.
        raise
    else:
        try:
            metadata = os.fstat(existing_fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(f"parser output path is unsafe: {path}")
        finally:
            os.close(existing_fd)
    finally:
        if parent_fd is not None:
            os.close(parent_fd)


def _write_unique_regular_file_at(directory_fd: int, name: str, payload: bytes) -> None:
    file_fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(file_fd, view)
            view = view[written:]
        os.fsync(file_fd)
    finally:
        os.close(file_fd)
    os.fsync(directory_fd)


def _open_or_create_directory_fd(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory_fd = os.open(absolute.anchor, flags)
    try:
        for component in absolute.parts[1:]:
            try:
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            except FileNotFoundError:
                os.mkdir(component, mode=0o700, dir_fd=directory_fd)
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
    except BaseException:
        os.close(directory_fd)
        raise
    return directory_fd


def _read_unique_regular_file(path: Path) -> bytes:
    absolute = Path(os.path.abspath(path))
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
    directory_fd = os.open(absolute.anchor, directory_flags)
    file_fd: int | None = None
    try:
        for component in absolute.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(absolute.name, file_flags, dir_fd=directory_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError(f"parser artifact is not a unique regular file: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(file_fd)
        if (
            after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
            or after.st_size != before.st_size
            or after.st_nlink != 1
        ):
            raise ValueError(f"parser artifact changed during read: {path}")
        return b"".join(chunks)
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(directory_fd)


def _read_unique_regular_file_at(directory_fd: int, name: str) -> bytes:
    file_fd = os.open(
        name,
        os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=directory_fd,
    )
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError(f"parser artifact is not a unique regular file: {name}")
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(file_fd)
        if (
            after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
            or after.st_size != before.st_size
            or after.st_nlink != 1
        ):
            raise ValueError(f"parser artifact changed during read: {name}")
        return b"".join(chunks)
    finally:
        os.close(file_fd)


def _parser_config_record(
    config: MistralParserConfig,
    *,
    parser_root: Path,
    parser_version: str | None,
    parser_revision: str | None,
) -> dict[str, Any]:
    return {
        "parser_root": str(parser_root),
        "parser_version": parser_version,
        "parser_revision": parser_revision,
        "expected_parser_revision": EXPECTED_PARSER_REVISION,
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


def _require_parser_revision(parser_root: Path) -> str:
    path = os.environ.get("PATH")
    if path is None or not path.strip():
        raise ValueError("PATH must be present and nonempty to verify parser revision")
    revision_check = _run_parser_git_check(
        parser_root, ("rev-parse", "HEAD"), path=path, purpose="revision"
    )
    revision = revision_check.stdout.strip()
    if revision != EXPECTED_PARSER_REVISION:
        raise ValueError(
            "parser checkout revision mismatch: expected "
            f"{EXPECTED_PARSER_REVISION}, got {revision or 'unavailable'}"
        )
    status_check = _run_parser_git_check(
        parser_root, ("status", "--porcelain"), path=path, purpose="working tree"
    )
    if status_check.stdout.strip():
        raise ValueError("parser checkout working tree is dirty")
    return revision


def _run_parser_git_check(
    parser_root: Path,
    arguments: tuple[str, ...],
    *,
    path: str,
    purpose: str,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            ("git", "-C", str(parser_root), *arguments),
            env={"PATH": path},
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "git executable not found; cannot verify parser checkout"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"git {purpose} check timed out after 10 seconds") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "no stderr"
        raise ValueError(
            f"git {purpose} check failed with exit {completed.returncode}: {stderr}"
        )
    return completed


def _build_parser_subprocess_env(parent_env: Mapping[str, str]) -> dict[str, str]:
    api_key = parent_env.get("MISTRAL_API_KEY")
    if api_key is None or not api_key.strip():
        raise ValueError("MISTRAL_API_KEY must be present and nonempty before spawn")
    path = parent_env.get("PATH")
    if path is None or not path.strip():
        raise ValueError("PATH must be present and nonempty before parser spawn")
    child_env = {
        "MISTRAL_API_KEY": api_key,
        _ENV_ONLY_API_KEYS_VARIABLE: "1",
        "PATH": path,
    }
    for name in _PARSER_LOCALE_ENV_NAMES:
        value = parent_env.get(name)
        if value is not None and value.strip():
            child_env[name] = value
    return child_env


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
