from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from legalforecast.cli import main


def test_assemble_cycle_acquisition_rebases_and_reconciles_two_batches(
    tmp_path: Path,
) -> None:
    batch_1 = tmp_path / "batch-001"
    batch_2 = tmp_path / "batch-002"
    cycle = tmp_path / "cycle"
    _write_batch(
        batch_1,
        screened=[{"candidate_id": "overlap", "version": 1}],
        exclusions=[
            {
                "candidate_id": "later-accepted",
                "primary_exclusion_reason": "strict_clean_screen_failed",
            }
        ],
        selections=[_selection("free-case")],
        relevance=[_relevance("free-case", requires_paid_recovery=False)],
        documents=[("free-case", "free-doc", b"free pdf")],
    )
    _write_batch(
        batch_2,
        screened=[
            {"candidate_id": "overlap", "version": 2},
            {"candidate_id": "later-accepted", "version": 2},
            {"candidate_id": "paid-case", "version": 1},
        ],
        exclusions=[],
        selections=[_selection("paid-case")],
        relevance=[_relevance("paid-case", requires_paid_recovery=True)],
        documents=[("paid-case", "decision-doc", b"paid-gap free decision")],
        paid_gaps=[
            {
                "candidate_id": "paid-case",
                "paid_gap_reasons": ["no_free_target_mtd_document"],
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--batch-root",
                str(batch_1),
                "--batch-root",
                str(batch_2),
                "--output-root",
                str(cycle),
                "--execute",
            ]
        )
        == 0
    )

    screened = _read_jsonl(cycle / "screened-cases.jsonl")
    assert [(row["candidate_id"], row["version"]) for row in screened] == [
        ("free-case", 1),
        ("later-accepted", 2),
        ("overlap", 2),
        ("paid-case", 1),
    ]
    assert _read_jsonl(cycle / "discovery-exclusions.jsonl") == []
    manifest = _read_jsonl(cycle / "document-downloads-merged.jsonl")
    assert {row["candidate_id"] for row in manifest} == {"free-case", "paid-case"}
    for row in manifest:
        destination = cycle / "documents" / row["local_path"]
        assert destination.read_bytes()
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == row["sha256"]
        source = (
            (batch_1 if row["candidate_id"] == "free-case" else batch_2)
            / "documents"
            / f"{row['candidate_id']}/{row['source_document_id']}.pdf"
        )
        assert destination.stat().st_ino != source.stat().st_ino

    relevance = _read_jsonl(cycle / "case-relevance.jsonl")
    assert [row["candidate_id"] for row in relevance] == ["free-case", "paid-case"]
    summary = json.loads((cycle / "cycle-acquisition-summary.json").read_text())
    assert summary["schema"] == "legalforecast.cycle_acquisition_assembly.v1"
    assert summary["batch_count"] == 2
    assert summary["record_counts"]["screened_cases"] == 4

    single_batch = tmp_path / "single-batch-equivalent"
    single_batch.mkdir()
    (single_batch / "case-relevance.jsonl").write_bytes(
        (cycle / "case-relevance.jsonl").read_bytes()
    )
    _write_jsonl(
        cycle / "disclosure-clearance.jsonl",
        [_clearance(record) for record in manifest],
    )
    _write_jsonl(single_batch / "document-downloads-merged.jsonl", manifest)
    _write_jsonl(
        single_batch / "disclosure-clearance.jsonl",
        [_clearance(record) for record in manifest],
    )
    for root in (cycle, single_batch):
        assert (
            main(
                [
                    "acquisition",
                    "filter-core-documents",
                    "--case-relevance",
                    str(root / "case-relevance.jsonl"),
                    "--output-root",
                    str(root),
                    "--execute",
                ]
            )
            == 0
        )
        assert (
            main(
                [
                    "acquisition",
                    "plan-parse-documents",
                    "--download-manifest",
                    str(root / "document-downloads-merged.jsonl"),
                    "--disclosure-clearance",
                    str(root / "disclosure-clearance.jsonl"),
                    "--document-root",
                    str(cycle / "documents"),
                    "--output-root",
                    str(root),
                    "--execute",
                ]
            )
            == 0
        )
        assert (
            main(
                [
                    "acquisition",
                    "plan",
                    "--core-filter-results",
                    str(root / "core-filter-results.jsonl"),
                    "--output-root",
                    str(root),
                    "--execute",
                ]
            )
            == 0
        )
    assert (cycle / "core-filter-results.jsonl").read_bytes() == (
        single_batch / "core-filter-results.jsonl"
    ).read_bytes()
    assert (cycle / "missing-core-budget-plan.json").read_bytes() == (
        single_batch / "missing-core-budget-plan.json"
    ).read_bytes()
    assert (cycle / "parse-document-requests.jsonl").read_bytes() == (
        single_batch / "parse-document-requests.jsonl"
    ).read_bytes()
    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(cycle / "missing-core-budget-plan.json"),
                "--output-root",
                str(cycle / "purchase-parser-dry-run"),
            ]
        )
        == 0
    )


def test_assemble_cycle_acquisition_fails_closed_on_hash_mismatch(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "batch"
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[_selection("case-1")],
        relevance=[_relevance("case-1", requires_paid_recovery=False)],
        documents=[("case-1", "doc-1", b"expected")],
    )
    manifest_path = batch / "free-document-downloads.jsonl"
    [record] = _read_jsonl(manifest_path)
    record["sha256"] = "0" * 64
    _write_jsonl(manifest_path, [record])

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "hash mismatch" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_symlinked_document(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "batch"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[_selection("case-1")],
        relevance=[_relevance("case-1", requires_paid_recovery=False)],
        documents=[],
    )
    document = batch / "documents/case-1/doc-1.pdf"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.symlink_to(outside)
    _write_jsonl(
        batch / "free-document-downloads.jsonl",
        [_manifest("case-1", "doc-1", outside.read_bytes())],
    )

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "symlink" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_hardlinked_document(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "batch"
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[_selection("case-1")],
        relevance=[_relevance("case-1", requires_paid_recovery=False)],
        documents=[("case-1", "doc-1", b"linked")],
    )
    source = batch / "documents/case-1/doc-1.pdf"
    source.with_name("second-name.pdf").hardlink_to(source)

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "hardlinked source document" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_existing_hash_path_collision(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "batch"
    content = b"committed"
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[_selection("case-1")],
        relevance=[_relevance("case-1", requires_paid_recovery=False)],
        documents=[("case-1", "doc-1", content)],
    )
    digest = hashlib.sha256(content).hexdigest()
    collision = tmp_path / "cycle/documents/sha256" / digest[:2] / f"{digest}.pdf"
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"different")

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "destination collision" in capsys.readouterr().err


def test_assemble_cycle_acquisition_requires_exactly_one_relevance_record(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "batch"
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[_selection("case-1")],
        relevance=[],
        documents=[],
    )

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "exactly one relevance record" in capsys.readouterr().err


def _assemble(batch: Path, output: Path) -> int:
    return main(
        [
            "acquisition",
            "assemble-cycle-acquisition",
            "--batch-root",
            str(batch),
            "--output-root",
            str(output),
            "--execute",
        ]
    )


def _write_batch(
    root: Path,
    *,
    screened: list[dict[str, object]],
    exclusions: list[dict[str, object]],
    selections: list[dict[str, object]],
    relevance: list[dict[str, object]],
    documents: list[tuple[str, str, bytes]],
    paid_gaps: list[dict[str, object]] | None = None,
) -> None:
    root.mkdir(parents=True)
    selected_ids = {str(record["candidate_id"]) for record in selections}
    screened_by_id = {str(record["candidate_id"]): record for record in screened}
    for candidate_id in selected_ids:
        screened_by_id.setdefault(
            candidate_id, {"candidate_id": candidate_id, "version": 1}
        )
    _write_jsonl(root / "screened-cases.jsonl", list(screened_by_id.values()))
    _write_jsonl(root / "exclusions.jsonl", exclusions)
    _write_jsonl(root / "public-packet-selection-reconciled.jsonl", selections)
    _write_jsonl(root / "public-packet-paid-gaps.jsonl", paid_gaps or [])
    _write_jsonl(root / "case-relevance.jsonl", relevance)
    _write_jsonl(root / "core-filter-results.jsonl", [])
    manifest: list[dict[str, object]] = []
    for candidate_id, document_id, content in documents:
        path = root / "documents" / candidate_id / f"{document_id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest.append(_manifest(candidate_id, document_id, content))
    _write_jsonl(root / "free-document-downloads.jsonl", manifest)
    (root / "summary.json").write_text(
        json.dumps(
            {
                "schema": "legalforecast.courtlistener_discovery_summary.v1",
                "accepted_case_count": len(screened_by_id),
                "excluded_case_count": len(exclusions),
            }
        ),
        encoding="utf-8",
    )


def _manifest(candidate_id: str, document_id: str, content: bytes) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "source_provider": "courtlistener",
        "source_document_id": document_id,
        "document_role": "decision",
        "source_url": f"https://example.test/{document_id}.pdf",
        "local_path": f"{candidate_id}/{document_id}.pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_count": len(content),
        "free_or_purchased": "free",
    }


def _selection(candidate_id: str) -> dict[str, object]:
    return {"candidate_id": candidate_id, "documents": []}


def _relevance(candidate_id: str, *, requires_paid_recovery: bool) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "documents": [
            {
                "source_document_id": f"{candidate_id}-motion",
                "setup_runner_label": "core_mtd",
                "document_role": "motion_to_dismiss_memorandum",
                "availability_status": (
                    "missing" if requires_paid_recovery else "available"
                ),
                "requires_paid_recovery": requires_paid_recovery,
            }
        ],
    }


def _clearance(document: dict[str, Any]) -> dict[str, object]:
    return {
        "candidate_id": document["candidate_id"],
        "source_document_id": document["source_document_id"],
        "sha256": document["sha256"],
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "byte_count": document["byte_count"],
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["fixture-public-docket"],
        "reviewer_id": "reviewer:test",
        "controlled_store_provenance": "private-store://fixture/reviews",
        "reviewed_at": "2026-07-12T18:00:00Z",
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]
