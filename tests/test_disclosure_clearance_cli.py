from __future__ import annotations

import hashlib
import json
from pathlib import Path

from legalforecast.cli import main


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_clearance_cli_and_parse_gate_bind_actual_bytes(tmp_path: Path) -> None:
    document_root = tmp_path / "documents"
    document_path = document_root / "cand-1" / "doc-1.pdf"
    document_path.parent.mkdir(parents=True)
    content = (
        b"%PDF-1.4\n/Type /Page\n<< >>\nstream\n"
        b"BT (Motion memorandum in support) Tj ET\nendstream"
    )
    document_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    manifest = tmp_path / "downloads.jsonl"
    reviews = tmp_path / "reviews.jsonl"
    restrictions = tmp_path / "restrictions.jsonl"
    output = tmp_path / "output"
    _write_jsonl(
        manifest,
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": "doc-1",
                "local_path": "cand-1/doc-1.pdf",
                "sha256": digest,
                "byte_count": len(content),
                "free_or_purchased": "free",
            }
        ],
    )
    _write_jsonl(
        reviews,
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": "doc-1",
                "sha256": digest,
                "status": "cleared",
                "controlled_store_provenance": "review-store:cycle1/batch-001",
                "reviewed_at": "2026-07-12T18:00:00Z",
                "restriction_status": "public",
                "restriction_evidence": "courtlistener-public-docket",
            }
        ],
    )
    _write_jsonl(
        restrictions,
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": "doc-1",
                "restriction_status": "public",
                "restriction_evidence": "courtlistener-public-docket",
            }
        ],
    )
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(manifest),
                "--document-root",
                str(document_root),
                "--reviews",
                str(reviews),
                "--restriction-evidence",
                str(restrictions),
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 0
    )
    clearance = output / "disclosure-clearance.jsonl"
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(document_root),
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 0
    )
    document_path.write_bytes(b"tampered")
    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "doc-1.md").write_text("fixture", encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(output / "parse-document-requests.jsonl"),
                "--disclosure-clearance",
                str(clearance),
                "--fixture-markdown-dir",
                str(fixture_markdown),
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(document_root),
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 2
    )


def test_finalize_requires_disclosure_clearance_argument() -> None:
    try:
        main(["acquisition", "finalize-corpus"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("finalize-corpus accepted missing required artifacts")
