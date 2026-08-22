"""Predecessor download-manifest binding for stipulated exact-100 exclusions."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_stipulated_parser_lineage import (
    StipulatedParserLineageError,
    parser_record_for_document,
    require_stipulated_source_matches_predecessor_download,
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _jsonl(*records: dict[str, Any]) -> bytes:
    return b"".join(
        canonical_json_bytes(
            record,
            error_type=ValueError,
            error_message="test JSONL serialization failed",
        )
        for record in records
    )


def _parser_record(
    *,
    candidate_id: str = "C001",
    source_document_id: str = "C001-motion",
    source: bytes = b"%PDF-stipulated-source",
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "source_sha256": _sha(source),
        "source_byte_count": len(source),
    }


def _download_row(
    *,
    candidate_id: str = "C001",
    source_document_id: str = "C001-motion",
    source: bytes = b"%PDF-stipulated-source",
    sha256: str | None = None,
    byte_count: int | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "sha256": f"sha256:{sha256 or _sha(source)}",
        "byte_count": len(source) if byte_count is None else byte_count,
        "local_path": f"{candidate_id}/{source_document_id}.pdf",
    }


def test_parser_record_for_document_requires_one_row() -> None:
    record = _parser_record()
    found = parser_record_for_document(
        (record,),
        candidate_id="C001",
        source_document_id="C001-motion",
    )
    assert found is record
    with pytest.raises(
        StipulatedParserLineageError, match="lacks one authenticated parser record"
    ):
        parser_record_for_document(
            (record, dict(record)),
            candidate_id="C001",
            source_document_id="C001-motion",
        )


def test_stipulated_source_accepts_predecessor_prefixed_sha() -> None:
    source = b"%PDF-authenticated-predecessor"
    require_stipulated_source_matches_predecessor_download(
        candidate_id="C001",
        source_document_id="C001-motion",
        parser_record=_parser_record(source=source),
        predecessor_download_manifest_bytes=_jsonl(
            _download_row(candidate_id="other", source_document_id="x", source=b"no"),
            _download_row(source=source),
        ),
    )


def test_stipulated_source_rejects_self_consistent_invented_pdf() -> None:
    """A hash-consistent invented PDF is not the predecessor download."""

    invented = b"%PDF-caller-owned-stipulation"
    with pytest.raises(
        StipulatedParserLineageError,
        match="differs from authenticated predecessor download",
    ):
        require_stipulated_source_matches_predecessor_download(
            candidate_id="C001",
            source_document_id="C001-motion",
            parser_record=_parser_record(source=invented),
            predecessor_download_manifest_bytes=_jsonl(
                _download_row(source=b"%PDF-real-predecessor-bytes")
            ),
        )


def test_stipulated_source_rejects_missing_predecessor_row() -> None:
    with pytest.raises(
        StipulatedParserLineageError,
        match="lacks one authenticated predecessor download",
    ):
        require_stipulated_source_matches_predecessor_download(
            candidate_id="C001",
            source_document_id="C001-motion",
            parser_record=_parser_record(),
            predecessor_download_manifest_bytes=_jsonl(
                _download_row(candidate_id="other", source_document_id="C001-motion")
            ),
        )


def test_stipulated_source_rejects_byte_count_drift() -> None:
    source = b"%PDF-authenticated-predecessor"
    with pytest.raises(
        StipulatedParserLineageError,
        match="differs from authenticated predecessor download",
    ):
        require_stipulated_source_matches_predecessor_download(
            candidate_id="C001",
            source_document_id="C001-motion",
            parser_record=_parser_record(source=source),
            predecessor_download_manifest_bytes=_jsonl(
                _download_row(source=source, byte_count=len(source) + 1)
            ),
        )


def test_production_stipulated_replay_binds_predecessor_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The public replay refuses when only selection bytes match the predecessor."""

    from legalforecast import cli
    from tests.test_exact100_successor_replacement_cli import (
        _completed_authenticated_stipulated_audit,
    )

    root, selection_bytes = _completed_authenticated_stipulated_audit(
        tmp_path, monkeypatch
    )
    card = json.loads(
        (root / "run-cards/audit-stage-a-target-eligibility.json").read_text(
            encoding="utf-8"
        )
    )
    authentic_manifest = Path(card["input_paths"][2]).read_bytes()
    evidence = cli._replay_exact100_stipulated_eligibility(
        root, selection_bytes, authentic_manifest
    )
    assert evidence.reason.value == "stipulated_ineligible"

    tampered_rows = [
        json.loads(line)
        for line in authentic_manifest.decode("utf-8").splitlines()
        if line
    ]
    target = next(
        row
        for row in tampered_rows
        if row["source_document_id"] == evidence.source_document_id
        and row["candidate_id"] == evidence.candidate_id
    )
    target["sha256"] = "sha256:" + _sha(
        b"invented PDF bytes with a fabricated dismissal"
    )
    tampered = _jsonl(*tampered_rows)
    assert tampered != authentic_manifest

    with pytest.raises(
        ValueError, match="differs from authenticated predecessor download"
    ):
        cli._replay_exact100_stipulated_eligibility(root, selection_bytes, tampered)
