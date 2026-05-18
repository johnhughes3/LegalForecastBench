"""Guardrails for public artifacts and workflow logs."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

PUBLICATION_GUARDRAIL_SCHEMA_VERSION = "legalforecast-publication-guardrails-v1"

PRIVATE_PATH_SEGMENTS = frozenset(
    {
        "audit-bundles",
        "extracted-text",
        "model-packets",
        "quarantine",
        "source-documents",
        "withdrawn",
    }
)
RAW_DOCUMENT_SUFFIXES = frozenset(
    {
        ".doc",
        ".docx",
        ".jpeg",
        ".jpg",
        ".pdf",
        ".png",
        ".rtf",
        ".tif",
        ".tiff",
    }
)
RAW_TEXT_SUFFIXES = frozenset({".text", ".txt"})
TEXT_SUFFIXES = frozenset(
    {
        ".csv",
        ".html",
        ".json",
        ".jsonl",
        ".log",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
    }
)
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "named_secret",
        re.compile(
            r"\b(?:CASE_DEV_API_KEY|PACER_PASSWORD|AWS_ACCESS_KEY_ID|"
            r"AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "assignment_secret",
        re.compile(
            r"\b(?:api[_-]?key|secret[_-]?access[_-]?key|access[_-]?token|"
            r"client[_-]?secret)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{8,}",
            re.IGNORECASE,
        ),
    ),
    (
        "authorization_header",
        re.compile(r"\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9_./+=:-]{8,}"),
    ),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)
PROVIDER_ACCOUNT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "provider_account_id",
        re.compile(
            r"\b(?:provider_account_id|account_id|organization_id|org_id|"
            r"project_id)\b['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9_./:-]{4,}",
            re.IGNORECASE,
        ),
    ),
)
AUDIT_ONLY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("audit_only", re.compile(r"\baudit[-_ ]only\b", re.IGNORECASE)),
)


class PublicationGuardrailCode(StrEnum):
    """Machine-readable guardrail finding categories."""

    AUDIT_ONLY_MATERIAL = "audit_only_material"
    HIDDEN_FILE = "hidden_file"
    PRIVATE_PATH = "private_path"
    PROVIDER_ACCOUNT_ID = "provider_account_id"
    RAW_DOCUMENT = "raw_document"
    SECRET = "secret"


@dataclass(frozen=True, slots=True)
class PublicationGuardrailFinding:
    """One public-artifact or log guardrail finding."""

    code: PublicationGuardrailCode
    path: Path
    message: str
    line_number: int | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "path": self.path.as_posix(),
            "line_number": self.line_number,
            "message": self.message,
        }


class PublicationGuardrailError(ValueError):
    """Raised when public artifacts or logs violate publication boundaries."""

    def __init__(self, findings: Sequence[PublicationGuardrailFinding]) -> None:
        if not findings:
            raise ValueError("findings must not be empty")
        self.findings = tuple(findings)
        super().__init__(_format_error_message(self.findings))


@dataclass(frozen=True, slots=True)
class PublicationGuardrailConfig:
    """Inputs for scanning public artifacts and workflow logs."""

    public_paths: tuple[Path, ...] = ()
    log_paths: tuple[Path, ...] = ()
    max_text_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        if not self.public_paths and not self.log_paths:
            raise ValueError("at least one public path or log path is required")
        if self.max_text_bytes <= 0:
            raise ValueError("max_text_bytes must be positive")


def scan_publication_guardrails(
    config: PublicationGuardrailConfig,
) -> tuple[PublicationGuardrailFinding, ...]:
    """Return guardrail findings for public artifacts and log files."""

    findings: list[PublicationGuardrailFinding] = []
    for path in config.public_paths:
        findings.extend(
            _scan_path(
                path,
                role="public artifact",
                max_text_bytes=config.max_text_bytes,
            )
        )
    for path in config.log_paths:
        findings.extend(
            _scan_path(path, role="workflow log", max_text_bytes=config.max_text_bytes)
        )
    return tuple(findings)


def enforce_publication_guardrails(config: PublicationGuardrailConfig) -> None:
    """Raise if any public artifact or log violates publication guardrails."""

    findings = scan_publication_guardrails(config)
    if findings:
        raise PublicationGuardrailError(findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan public artifacts and workflow logs for publication leaks."
    )
    parser.add_argument("--public-dir", action="append", type=Path, default=[])
    parser.add_argument("--public-file", action="append", type=Path, default=[])
    parser.add_argument("--log-dir", action="append", type=Path, default=[])
    parser.add_argument("--log-file", action="append", type=Path, default=[])
    parser.add_argument("--max-text-bytes", type=int, default=2_000_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    public_paths = tuple(args.public_dir) + tuple(args.public_file)
    log_paths = tuple(args.log_dir) + tuple(args.log_file)
    config = PublicationGuardrailConfig(
        public_paths=public_paths,
        log_paths=log_paths,
        max_text_bytes=args.max_text_bytes,
    )
    findings = scan_publication_guardrails(config)
    print(
        json.dumps(
            {
                "schema_version": PUBLICATION_GUARDRAIL_SCHEMA_VERSION,
                "finding_count": len(findings),
                "findings": [finding.to_record() for finding in findings],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if findings else 0


def _scan_path(
    path: Path,
    *,
    role: str,
    max_text_bytes: int,
) -> tuple[PublicationGuardrailFinding, ...]:
    if path.is_dir():
        files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
        return tuple(
            finding
            for file_path in files
            for finding in _scan_file(
                file_path,
                role=role,
                root=path,
                max_text_bytes=max_text_bytes,
            )
        )
    return _scan_file(path, role=role, root=path.parent, max_text_bytes=max_text_bytes)


def _scan_file(
    path: Path,
    *,
    role: str,
    root: Path,
    max_text_bytes: int,
) -> tuple[PublicationGuardrailFinding, ...]:
    findings: list[PublicationGuardrailFinding] = []
    relative_path = _safe_relative(path, root)
    parts = tuple(part.lower() for part in relative_path.parts)

    if any(part.startswith(".") for part in relative_path.parts):
        findings.append(
            _finding(
                PublicationGuardrailCode.HIDDEN_FILE,
                path,
                f"{role} includes hidden file path {relative_path.as_posix()}",
            )
        )
    private_segments = sorted(set(parts) & PRIVATE_PATH_SEGMENTS)
    if private_segments:
        findings.append(
            _finding(
                PublicationGuardrailCode.PRIVATE_PATH,
                path,
                f"{role} includes private path segment(s): {private_segments}",
            )
        )
    suffix = path.suffix.lower()
    if suffix in RAW_DOCUMENT_SUFFIXES or (
        role == "public artifact" and suffix in RAW_TEXT_SUFFIXES
    ):
        findings.append(
            _finding(
                PublicationGuardrailCode.RAW_DOCUMENT,
                path,
                f"{role} includes raw-document-like suffix {path.suffix}",
            )
        )
    if any(_audit_only_marker(part) for part in parts):
        findings.append(
            _finding(
                PublicationGuardrailCode.AUDIT_ONLY_MATERIAL,
                path,
                f"{role} includes audit-only path {relative_path.as_posix()}",
            )
        )

    if _should_scan_text(path, max_text_bytes=max_text_bytes):
        findings.extend(_scan_text_content(path, role=role))
    return tuple(findings)


def _scan_text_content(
    path: Path,
    *,
    role: str,
) -> tuple[PublicationGuardrailFinding, ...]:
    findings: list[PublicationGuardrailFinding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return tuple(findings)
    for line_number, line in enumerate(lines, start=1):
        findings.extend(
            _pattern_findings(
                path,
                line,
                line_number=line_number,
                role=role,
                code=PublicationGuardrailCode.SECRET,
                patterns=SECRET_PATTERNS,
            )
        )
        findings.extend(
            _pattern_findings(
                path,
                line,
                line_number=line_number,
                role=role,
                code=PublicationGuardrailCode.PROVIDER_ACCOUNT_ID,
                patterns=PROVIDER_ACCOUNT_PATTERNS,
            )
        )
        findings.extend(
            _pattern_findings(
                path,
                line,
                line_number=line_number,
                role=role,
                code=PublicationGuardrailCode.AUDIT_ONLY_MATERIAL,
                patterns=AUDIT_ONLY_PATTERNS,
            )
        )
        findings.extend(_private_path_findings(path, line, line_number, role=role))
    return tuple(findings)


def _pattern_findings(
    path: Path,
    line: str,
    *,
    line_number: int,
    role: str,
    code: PublicationGuardrailCode,
    patterns: Iterable[tuple[str, re.Pattern[str]]],
) -> tuple[PublicationGuardrailFinding, ...]:
    return tuple(
        _finding(
            code,
            path,
            f"{role} contains {pattern_name}",
            line_number=line_number,
        )
        for pattern_name, pattern in patterns
        if pattern.search(line)
    )


def _private_path_findings(
    path: Path,
    line: str,
    line_number: int,
    *,
    role: str,
) -> tuple[PublicationGuardrailFinding, ...]:
    lowered = line.lower()
    return tuple(
        _finding(
            PublicationGuardrailCode.PRIVATE_PATH,
            path,
            f"{role} references private path segment {segment}",
            line_number=line_number,
        )
        for segment in sorted(PRIVATE_PATH_SEGMENTS)
        if f"{segment}/" in lowered
    )


def _should_scan_text(path: Path, *, max_text_bytes: int) -> bool:
    return (
        path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= max_text_bytes
    )


def _audit_only_marker(value: str) -> bool:
    normalized = value.replace("_", "-").replace(" ", "-")
    return "audit-only" in normalized


def _finding(
    code: PublicationGuardrailCode,
    path: Path,
    message: str,
    *,
    line_number: int | None = None,
) -> PublicationGuardrailFinding:
    return PublicationGuardrailFinding(
        code=code,
        path=path,
        message=message,
        line_number=line_number,
    )


def _safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _format_error_message(findings: Sequence[PublicationGuardrailFinding]) -> str:
    first = findings[0]
    location = first.path.as_posix()
    if first.line_number is not None:
        location = f"{location}:{first.line_number}"
    return (
        f"publication guardrails found {len(findings)} issue(s); "
        f"first {first.code.value} at {location}: {first.message}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
