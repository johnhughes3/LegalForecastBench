"""Bounded command wrapper for the exact-100 noncharging recovery producer."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, cast

from legalforecast.contracts import EXACT100_ZERO_COST_RECOVERY_PUBLIC_DOCUMENT_V1
from legalforecast.ingestion.courtlistener_client import (
    DEFAULT_COURTLISTENER_BASE_URL,
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
)
from legalforecast.ingestion.exact100_zero_cost_recovery import (
    Exact100ZeroCostRecoveryError,
    execute_exact100_zero_cost_recovery,
    issue_exact100_zero_cost_recovery_request,
    require_exact100_public_document_url,
)
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    UrlLibFreeDocumentSource,
)
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    PostSelectionTerminalExclusionError,
    verify_terminal_recovery_evidence,
)


class Exact100ZeroCostRecoveryCliError(ValueError):
    """Raised when the bounded recovery command cannot publish its result."""


def add_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "recover-exact100-target-document-zero-cost",
        help="Run only the plan-derived noncharging CourtListener recovery.",
    )
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--fixture-courtlistener-responses",
        type=Path,
        help="test-only recorded CourtListener JSONL; never use for live recovery",
    )
    parser.add_argument(
        "--fixture-public-documents",
        type=Path,
        help="test-only JSON map of public URL to base64 document bytes",
    )
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    selection = _read(cast(Path, args.selection))
    plan = _read(cast(Path, args.plan))
    output_root = cast(Path, args.output_root)
    if _overlaps(output_root, cast(Path, args.selection)) or _overlaps(
        output_root, cast(Path, args.plan)
    ):
        raise Exact100ZeroCostRecoveryCliError(
            "recovery output overlaps immutable input"
        )
    request = issue_exact100_zero_cost_recovery_request(
        selection_bytes=selection, plan_bytes=plan
    )
    if _resume_if_complete(
        output_root=output_root,
        selection_bytes=selection,
        request_bytes=request.record_bytes,
    ):
        if not args.resume:
            raise Exact100ZeroCostRecoveryCliError(
                "immutable recovery output already exists and resume is disabled"
            )
        print(
            json.dumps(
                {
                    "output_root": str(output_root),
                    "resumed": True,
                    "paid_activity_executed": False,
                    "pacer_activity_executed": False,
                    "recap_fetch_activity_executed": False,
                    "fee_acknowledged": False,
                },
                sort_keys=True,
            )
        )
        return 0
    response_fixture = cast(Path | None, args.fixture_courtlistener_responses)
    document_fixture = cast(Path | None, args.fixture_public_documents)
    transport = (
        CourtListenerFixtureTransport.from_jsonl(response_fixture)
        if response_fixture
        else None
    )
    config = CourtListenerConfig.from_env()
    if config.base_url != DEFAULT_COURTLISTENER_BASE_URL:
        raise Exact100ZeroCostRecoveryCliError(
            "exact100 recovery requires the canonical CourtListener REST v4 base"
        )
    client = CourtListenerClient(
        config=config,
        transport=transport,
        max_retries=0 if transport else 2,
    )
    source = (
        _fixture_source(document_fixture)
        if document_fixture
        else (
            None
            if transport
            else UrlLibFreeDocumentSource(
                final_url_validator=lambda url: require_exact100_public_document_url(
                    url, document_id="480673755"
                )
            )
        )
    )
    try:
        result = execute_exact100_zero_cost_recovery(
            selection_bytes=selection,
            plan_bytes=plan,
            courtlistener=client,
            public_document_source=source,
            public_output_root=output_root / "documents" if source else None,
        )
    except Exact100ZeroCostRecoveryError as exc:
        raise Exact100ZeroCostRecoveryCliError(str(exc)) from exc
    outputs = {"recovery-request.json": result.request.record_bytes}
    terminal = result.receipt_bytes is not None
    if terminal:
        assert (
            result.receipt_bytes
            and result.run_card_bytes
            and result.rest_observation_bytes
            and result.rest_observation_transcript_bytes
            and result.rest_observation_response_bytes is not None
        )
        outputs.update(
            {
                "recovery-receipt.json": result.receipt_bytes,
                "recovery-run-card.json": result.run_card_bytes,
                "rest-observation.json": result.rest_observation_bytes,
                "rest-observation-transcript.jsonl": (
                    result.rest_observation_transcript_bytes
                ),
                "rest-observation-response.bin": (
                    result.rest_observation_response_bytes
                ),
            }
        )
    else:
        if (
            result.public_document_manifest_bytes is None
            or result.public_download is None
        ):
            raise Exact100ZeroCostRecoveryCliError(
                "public recovery lacks a document handoff"
            )
        outputs["public-document-manifest.json"] = result.public_document_manifest_bytes
    for name, payload in outputs.items():
        _write(output_root / name, payload, resume=args.resume)
    _resume_if_complete(
        output_root=output_root,
        selection_bytes=selection,
        request_bytes=request.record_bytes,
    )
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "terminal": terminal,
                "paid_activity_executed": False,
                "pacer_activity_executed": False,
                "recap_fetch_activity_executed": False,
                "fee_acknowledged": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _fixture_source(path: Path) -> FixtureFreeDocumentSource:
    raw = json.loads(_read(path))
    if not isinstance(raw, dict):
        raise Exact100ZeroCostRecoveryCliError(
            "fixture public documents must map URL to base64 text"
        )
    encoded_documents: dict[str, str] = {}
    for key, value in cast(dict[object, object], raw).items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise Exact100ZeroCostRecoveryCliError(
                "fixture public documents must map URL to base64 text"
            )
        encoded_documents[key] = value
    try:
        return FixtureFreeDocumentSource(
            {
                key: base64.b64decode(value, validate=True)
                for key, value in encoded_documents.items()
            }
        )
    except ValueError as exc:
        raise Exact100ZeroCostRecoveryCliError(
            "fixture public document is not base64"
        ) from exc


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Exact100ZeroCostRecoveryCliError(f"missing regular file: {path}")
    return path.read_bytes()


def _resume_if_complete(
    *, output_root: Path, selection_bytes: bytes, request_bytes: bytes
) -> bool:
    """Verify immutable completed output before deciding whether a GET is needed."""

    if not output_root.exists():
        return False
    if output_root.is_symlink() or not output_root.is_dir():
        raise Exact100ZeroCostRecoveryCliError(
            "recovery output root must be a regular directory"
        )
    names = {path.name for path in output_root.iterdir()}
    terminal_names = {
        "recovery-request.json",
        "recovery-receipt.json",
        "recovery-run-card.json",
        "rest-observation.json",
        "rest-observation-transcript.jsonl",
        "rest-observation-response.bin",
    }
    public_names = {
        "recovery-request.json",
        "public-document-manifest.json",
        "documents",
    }
    if not names:
        return False
    if names == terminal_names:
        _verify_terminal_resume(
            output_root=output_root,
            selection_bytes=selection_bytes,
            request_bytes=request_bytes,
        )
        return True
    if names == public_names:
        _verify_public_resume(output_root=output_root, request_bytes=request_bytes)
        return True
    raise Exact100ZeroCostRecoveryCliError(
        "recovery output is partial, mixed, or contains unexpected paths"
    )


def _verify_terminal_resume(
    *, output_root: Path, selection_bytes: bytes, request_bytes: bytes
) -> None:
    request_path = output_root / "recovery-request.json"
    if _read(request_path) != request_bytes:
        raise Exact100ZeroCostRecoveryCliError(
            "saved recovery request binds different immutable inputs"
        )
    try:
        verify_terminal_recovery_evidence(
            selection_bytes=selection_bytes,
            request=_object(_read(request_path), request_path),
            request_bytes=request_bytes,
            receipt=_object(
                _read(output_root / "recovery-receipt.json"),
                output_root / "recovery-receipt.json",
            ),
            receipt_bytes=_read(output_root / "recovery-receipt.json"),
            run_card=_object(
                _read(output_root / "recovery-run-card.json"),
                output_root / "recovery-run-card.json",
            ),
            run_card_bytes=_read(output_root / "recovery-run-card.json"),
            rest_observation=_object(
                _read(output_root / "rest-observation.json"),
                output_root / "rest-observation.json",
            ),
            rest_observation_bytes=_read(output_root / "rest-observation.json"),
            rest_observation_transcript_bytes=_read(
                output_root / "rest-observation-transcript.jsonl"
            ),
            rest_observation_response_bytes=_read(
                output_root / "rest-observation-response.bin"
            ),
        )
    except PostSelectionTerminalExclusionError as exc:
        raise Exact100ZeroCostRecoveryCliError(
            "saved terminal recovery output is invalid"
        ) from exc


def _verify_public_resume(*, output_root: Path, request_bytes: bytes) -> None:
    request_path = output_root / "recovery-request.json"
    if _read(request_path) != request_bytes:
        raise Exact100ZeroCostRecoveryCliError(
            "saved recovery request binds different immutable inputs"
        )
    manifest_path = output_root / "public-document-manifest.json"
    manifest = _object(_read(manifest_path), manifest_path)
    required = {
        "schema_version",
        "recovery_request_sha256",
        "candidate_id",
        "source_document_id",
        "courtlistener_docket_id",
        "courtlistener_docket_entry_id",
        "document",
        "terminal_exclusion_authority",
    }
    document = manifest.get("document")
    if (
        set(manifest) != required
        or manifest.get("schema_version")
        != str(EXACT100_ZERO_COST_RECOVERY_PUBLIC_DOCUMENT_V1)
        or manifest.get("recovery_request_sha256") != _sha(request_bytes)
        or manifest.get("candidate_id") != "72449171"
        or manifest.get("source_document_id") != "480673755"
        or manifest.get("courtlistener_docket_id") != "72449171"
        or manifest.get("courtlistener_docket_entry_id") != "465468661"
        or manifest.get("terminal_exclusion_authority") is not False
        or not isinstance(document, Mapping)
    ):
        raise Exact100ZeroCostRecoveryCliError(
            "saved public recovery output is invalid"
        )
    document_record = cast(Mapping[str, object], document)
    local_path = document_record.get("local_path")
    digest = document_record.get("sha256")
    byte_count = document_record.get("byte_count")
    if (
        not isinstance(local_path, str)
        or not isinstance(digest, str)
        or not isinstance(byte_count, int)
        or document_record.get("candidate_id") != "72449171"
        or document_record.get("source_document_id") != "480673755"
        or document_record.get("free_or_purchased") != "free"
    ):
        raise Exact100ZeroCostRecoveryCliError(
            "saved public document handoff is invalid"
        )
    relative = PurePosixPath(local_path)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise Exact100ZeroCostRecoveryCliError("saved public document path is unsafe")
    document_path = output_root / "documents" / relative
    payload = _read(document_path)
    expected_digest = digest.removeprefix("sha256:")
    if (
        len(payload) != byte_count
        or hashlib.sha256(payload).hexdigest() != expected_digest
    ):
        raise Exact100ZeroCostRecoveryCliError("saved public document bytes differ")
    checkpoint = output_root / "documents" / ".download-checkpoint.jsonl"
    if checkpoint.is_symlink() or not checkpoint.is_file():
        raise Exact100ZeroCostRecoveryCliError("saved public checkpoint is missing")
    expected_files = {
        "recovery-request.json",
        "public-document-manifest.json",
        "documents/.download-checkpoint.jsonl",
        f"documents/{local_path}",
    }
    entries = tuple(output_root.rglob("*"))
    if any(
        path.is_symlink() or not (path.is_file() or path.is_dir()) for path in entries
    ):
        raise Exact100ZeroCostRecoveryCliError(
            "saved public recovery output contains unexpected paths"
        )
    actual_files = {
        path.relative_to(output_root).as_posix() for path in entries if path.is_file()
    }
    expected_directories = {"documents"}
    expected_directories.update(
        "documents/" + PurePosixPath(local_path).parents[index].as_posix()
        for index in range(len(PurePosixPath(local_path).parents) - 1)
    )
    actual_directories = {
        path.relative_to(output_root).as_posix() for path in entries if path.is_dir()
    }
    if actual_files != expected_files or actual_directories != expected_directories:
        raise Exact100ZeroCostRecoveryCliError(
            "saved public recovery output contains unexpected paths"
        )


def _object(payload: bytes, path: Path) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exact100ZeroCostRecoveryCliError(f"{path} is not JSON") from exc
    if not isinstance(value, dict):
        raise Exact100ZeroCostRecoveryCliError(f"{path} is not a JSON object")
    canonical = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    if canonical.encode() != payload:
        raise Exact100ZeroCostRecoveryCliError(f"{path} is not canonical JSON")
    return cast(dict[str, object], value)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write(path: Path, payload: bytes, *, resume: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not resume or _read(path) != payload:
            raise Exact100ZeroCostRecoveryCliError(
                f"immutable recovery output differs: {path}"
            )
        return
    path.write_bytes(payload)


def _overlaps(left: Path, right: Path) -> bool:
    a, b = left.absolute(), right.absolute()
    return a == b or a in b.parents or b in a.parents
