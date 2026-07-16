from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import legalforecast.cli as cli
import legalforecast.ingestion.cycle_acquisition_assembler as assembler
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import generate_case_dev_purchase_policy
from legalforecast.ingestion.cycle_acquisition_assembler import (
    COMPONENT_PROVENANCE_FILENAME,
    write_component_provenance,
)

_TEST_CYCLE_HASH = "a" * 64


def test_assemble_cycle_acquisition_rebases_and_reconciles_two_batches(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
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
    _bind_component_chain([batch_1, batch_2])

    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--expected-cycle-hash",
                _TEST_CYCLE_HASH,
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
    assert [batch["batch_root"] for batch in summary["batches"]] == [
        "batch-001",
        "batch-002",
    ]

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
        materialization_card = authenticated_downstream_fixture.materialize(
            manifest=root / "document-downloads-merged.jsonl",
            clearance=root / "disclosure-clearance.jsonl",
            document_root=cycle / "documents",
            name=root.name,
        )
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
                    "--materialization-run-card",
                    str(materialization_card),
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
    purchase_policy, purchase_ledger, cohort_policy = _purchase_policy(tmp_path)
    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(cycle / "missing-core-budget-plan.json"),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
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


def test_assemble_cycle_acquisition_prunes_artifacts_for_later_exclusion(
    tmp_path: Path,
) -> None:
    batch_1 = tmp_path / "batch-001"
    batch_2 = tmp_path / "batch-002"
    _write_batch(
        batch_1,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[_selection("case-1")],
        relevance=[_relevance("case-1", requires_paid_recovery=True)],
        documents=[("case-1", "doc-1", b"stale")],
        paid_gaps=[{"candidate_id": "case-1", "paid_gap_reasons": ["missing"]}],
        core_filters=[{"candidate_id": "case-1", "included": True}],
    )
    _write_batch(
        batch_2,
        screened=[],
        exclusions=[
            {
                "candidate_id": "case-1",
                "primary_exclusion_reason": "strict_clean_screen_failed",
            }
        ],
        selections=[],
        relevance=[],
        documents=[],
    )
    cycle = tmp_path / "cycle"

    assert _assemble_batches([batch_1, batch_2], cycle) == 0
    assert _read_jsonl(cycle / "screened-cases.jsonl") == []
    assert (
        _read_jsonl(cycle / "discovery-exclusions.jsonl")[0]["candidate_id"] == "case-1"
    )
    for filename in (
        "public-packet-selection.jsonl",
        "public-packet-paid-gaps.jsonl",
        "case-relevance.jsonl",
        "core-filter-results.jsonl",
        "document-downloads-merged.jsonl",
    ):
        assert _read_jsonl(cycle / filename) == []


def test_assemble_cycle_acquisition_preserves_immutable_exclusion(
    tmp_path: Path,
) -> None:
    batches = [tmp_path / f"batch-{ordinal:03d}" for ordinal in range(1, 4)]
    _write_batch(
        batches[0],
        screened=[],
        exclusions=[
            {
                "candidate_id": "case-1",
                "primary_exclusion_reason": "decision_before_release_anchor",
            }
        ],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_batch(
        batches[1],
        screened=[],
        exclusions=[
            {"candidate_id": "case-1", "primary_exclusion_reason": "fetch_error"}
        ],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_batch(
        batches[2],
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    cycle = tmp_path / "cycle"

    assert _assemble_batches(batches, cycle) == 0
    assert _read_jsonl(cycle / "screened-cases.jsonl") == []
    assert _read_jsonl(cycle / "discovery-exclusions.jsonl") == [
        {
            "candidate_id": "case-1",
            "primary_exclusion_reason": "decision_before_release_anchor",
        }
    ]


def test_assemble_cycle_acquisition_rejects_duplicate_discovery_rows(
    tmp_path: Path, capsys: Any
) -> None:
    for artifact, filename, rows, count_key in (
        (
            "screened",
            "screened-cases.jsonl",
            [{"candidate_id": "case-1"}, {"candidate_id": "case-1"}],
            "accepted_case_count",
        ),
        (
            "discovery-exclusion",
            "exclusions.jsonl",
            [
                {"candidate_id": "case-1", "reason": "fetch_error"},
                {"candidate_id": "case-1", "reason": "fetch_error"},
            ],
            "excluded_case_count",
        ),
    ):
        batch = tmp_path / artifact
        _write_batch(
            batch,
            screened=[],
            exclusions=[],
            selections=[],
            relevance=[],
            documents=[],
        )
        _write_jsonl(batch / filename, rows)
        summary_path = batch / "summary.json"
        summary = json.loads(summary_path.read_text())
        summary[count_key] = 2
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        _refresh_snapshot_commitments(batch)

        assert _assemble(batch, tmp_path / f"cycle-{artifact}") == 2
        assert "duplicate candidate_id" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_output_overlap_both_directions(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "inputs" / "batch"
    _write_batch(
        batch,
        screened=[],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )

    assert _assemble(batch, batch / "cycle") == 2
    assert "output root must not contain or equal" in capsys.readouterr().err
    assert _assemble(batch, tmp_path / "inputs") == 2
    assert "output root must not contain or equal" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_preexisting_temporary_symlink(
    tmp_path: Path, capsys: Any
) -> None:
    batch = tmp_path / "batch"
    content = b"safe source"
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[("case-1", "doc-1", content)],
    )
    digest = hashlib.sha256(content).hexdigest()
    destination = tmp_path / "cycle/documents/sha256" / digest[:2] / f"{digest}.pdf"
    destination.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_bytes(b"must remain unchanged")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.symlink_to(outside)

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "temporary publication path already exists" in capsys.readouterr().err
    assert outside.read_bytes() == b"must remain unchanged"
    assert temporary.is_symlink()


def test_assemble_cycle_acquisition_keys_documents_by_candidate(
    tmp_path: Path,
) -> None:
    batch = tmp_path / "batch"
    _write_batch(
        batch,
        screened=[{"candidate_id": "case-1"}, {"candidate_id": "case-2"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[
            ("case-1", "shared-doc-id", b"first"),
            ("case-2", "shared-doc-id", b"second"),
        ],
    )
    cycle = tmp_path / "cycle"

    assert _assemble(batch, cycle) == 0
    manifest = _read_jsonl(cycle / "document-downloads-merged.jsonl")
    assert {row["candidate_id"] for row in manifest} == {"case-1", "case-2"}
    assert len({row["local_path"] for row in manifest}) == 2


def test_assemble_cycle_acquisition_composes_split_snapshot_and_artifact_roots(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "immutable-screening-snapshot"
    downstream = tmp_path / "standardized-free-v3"
    cycle = tmp_path / "cycle"
    screened = [
        _courtlistener_screened(candidate_id) for candidate_id in ("123", "789", "901")
    ]
    _write_batch(
        snapshot,
        screened=screened,
        exclusions=[
            {
                "candidate_id": "courtlistener-docket-456",
                "case_id": "courtlistener-docket-456",
                "primary_exclusion_reason": "decision_before_release_anchor",
            }
        ],
        selections=[],
        relevance=[],
        documents=[],
    )
    (snapshot / "summary.json").write_text(
        json.dumps(
            {
                "accepted_count": 3,
                "excluded_count": 1,
                "processed_count": 4,
                "reconciliation_complete": True,
            }
        ),
        encoding="utf-8",
    )
    _write_batch(
        downstream,
        screened=[],
        exclusions=[],
        selections=[_selection("123")],
        relevance=[_relevance("123", requires_paid_recovery=False)],
        core_filters=[{"candidate_id": "123", "included": True}],
        documents=[
            ("123", "selected-doc", b"selected"),
            ("789", "bridge-excluded-doc", b"excluded"),
        ],
        is_snapshot=False,
    )
    _write_jsonl(downstream / "screened-cases.jsonl", [])
    (downstream / "summary.json").unlink()
    _write_jsonl(
        downstream / "pacer-gap-bridge-exclusions.jsonl",
        [
            {
                "candidate_id": "789",
                "primary_exclusion_reason": "case_dev_caption_conflict",
            }
        ],
    )
    _write_jsonl(
        downstream / "public-packet-exclusions.jsonl",
        [
            {
                "candidate_id": "901",
                "exclusion_reasons": [None, " ", "sealed_or_restricted_material"],
            }
        ],
    )

    assert _assemble_batches([snapshot, downstream], cycle) == 0

    assert [
        record["candidate_id"] for record in _read_jsonl(cycle / "screened-cases.jsonl")
    ] == ["123"]
    exclusions = _read_jsonl(cycle / "discovery-exclusions.jsonl")
    assert [record["candidate_id"] for record in exclusions] == ["456", "789", "901"]
    assert exclusions[0]["source_candidate_id"] == "courtlistener-docket-456"
    assert [
        record["candidate_id"]
        for record in _read_jsonl(cycle / "public-packet-selection.jsonl")
    ] == ["123"]
    assert [
        record["candidate_id"]
        for record in _read_jsonl(cycle / "document-downloads-merged.jsonl")
    ] == ["123"]


def test_assemble_cycle_acquisition_preserves_accepted_case_after_bridge_transient(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "immutable-screening-snapshot"
    downstream = tmp_path / "standardized-free-v3"
    cycle = tmp_path / "cycle"
    _write_batch(
        snapshot,
        screened=[_courtlistener_screened("123")],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_batch(
        downstream,
        screened=[],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
        is_snapshot=False,
    )
    _write_jsonl(downstream / "screened-cases.jsonl", [])
    (downstream / "summary.json").unlink()
    _write_jsonl(
        downstream / "pacer-gap-bridge-exclusions.jsonl",
        [
            {
                "candidate_id": "123",
                "primary_exclusion_reason": ("case_dev_server_error_retries_exhausted"),
            }
        ],
    )

    assert _assemble_batches([snapshot, downstream], cycle) == 0

    assert [
        record["candidate_id"] for record in _read_jsonl(cycle / "screened-cases.jsonl")
    ] == ["123"]
    assert _read_jsonl(cycle / "discovery-exclusions.jsonl") == []


def test_assemble_cycle_acquisition_rejects_downstream_root_before_snapshot(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "immutable-screening-snapshot"
    downstream = tmp_path / "standardized-free-v3"
    _write_batch(
        snapshot,
        screened=[_courtlistener_screened("123")],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_batch(
        downstream,
        screened=[],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
        is_snapshot=False,
    )
    _write_jsonl(downstream / "screened-cases.jsonl", [])
    (downstream / "summary.json").unlink()
    _write_jsonl(
        downstream / "pacer-gap-bridge-exclusions.jsonl",
        [
            {
                "candidate_id": "123",
                "primary_exclusion_reason": "case_dev_caption_conflict",
            }
        ],
    )

    assert _assemble_batches([downstream, snapshot], tmp_path / "cycle") == 2
    assert (
        "downstream-only batch root must immediately follow" in capsys.readouterr().err
    )


def test_assemble_cycle_acquisition_accepts_multiple_ordered_split_pairs(
    tmp_path: Path,
) -> None:
    roots: list[Path] = []
    for candidate_id in ("123", "456"):
        snapshot = tmp_path / f"snapshot-{candidate_id}"
        downstream = tmp_path / f"downstream-{candidate_id}"
        _write_batch(
            snapshot,
            screened=[_courtlistener_screened(candidate_id)],
            exclusions=[],
            selections=[],
            relevance=[],
            documents=[],
        )
        _write_batch(
            downstream,
            screened=[],
            exclusions=[],
            selections=[_selection(candidate_id)],
            relevance=[_relevance(candidate_id, requires_paid_recovery=False)],
            documents=[],
            is_snapshot=False,
        )
        _write_jsonl(downstream / "screened-cases.jsonl", [])
        (downstream / "summary.json").unlink()
        roots.extend((snapshot, downstream))

    cycle = tmp_path / "cycle"
    assert _assemble_batches(roots, cycle) == 0
    assert [
        record["candidate_id"] for record in _read_jsonl(cycle / "screened-cases.jsonl")
    ] == ["123", "456"]
    assert [
        record["candidate_id"]
        for record in _read_jsonl(cycle / "public-packet-selection.jsonl")
    ] == ["123", "456"]


def test_assemble_cycle_acquisition_composes_ordered_multi_component_roots(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "screening-snapshot"
    plan = tmp_path / "public-plan"
    free_download = tmp_path / "free-download"
    bridge = tmp_path / "gap-bridge"
    core_filter = tmp_path / "core-filter"
    roots = (snapshot, plan, free_download, bridge, core_filter)
    _write_batch(
        snapshot,
        screened=[
            _courtlistener_screened("123"),
            _courtlistener_screened("456"),
        ],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(
        plan,
        selections=[_selection("123")],
        paid_gaps=[{"candidate_id": "123", "paid_gap_reasons": ["missing_motion"]}],
    )
    _write_downstream_component(
        free_download,
        documents=[("123", "decision", b"free decision")],
    )
    _write_downstream_component(
        bridge,
        relevance=[_relevance("123", requires_paid_recovery=True)],
    )
    _write_downstream_component(
        core_filter,
        core_filters=[{"candidate_id": "123", "included": True}],
    )
    _write_jsonl(
        core_filter / "pacer-gap-bridge-exclusions.jsonl",
        [
            {
                "candidate_id": "456",
                "primary_exclusion_reason": "missing_core_documents",
            }
        ],
    )

    cycle = tmp_path / "cycle"
    assert _assemble_batches(list(roots), cycle) == 0
    assert [
        record["candidate_id"] for record in _read_jsonl(cycle / "screened-cases.jsonl")
    ] == ["123"]
    assert [
        record["candidate_id"]
        for record in _read_jsonl(cycle / "discovery-exclusions.jsonl")
    ] == ["456"]
    assert [
        record["candidate_id"]
        for record in _read_jsonl(cycle / "public-packet-selection.jsonl")
    ] == ["123"]
    assert [
        record["candidate_id"]
        for record in _read_jsonl(cycle / "document-downloads-merged.jsonl")
    ] == ["123"]
    summary = json.loads(
        (cycle / "cycle-acquisition-summary.json").read_text(encoding="utf-8")
    )
    assert [
        batch["screening_snapshot_batch_ordinal"] for batch in summary["batches"]
    ] == [
        1,
        1,
        1,
        1,
        1,
    ]
    assert [batch["downstream_component_ordinal"] for batch in summary["batches"]] == [
        0,
        1,
        2,
        3,
        4,
    ]


def test_assemble_cycle_acquisition_empty_component_preserves_snapshot_binding(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "screening-snapshot"
    empty = tmp_path / "empty"
    downstream = tmp_path / "public-plan"
    _write_batch(
        snapshot,
        screened=[_courtlistener_screened("123")],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(empty)
    _write_downstream_component(
        downstream,
        selections=[_selection("123")],
        relevance=[_relevance("123", requires_paid_recovery=False)],
    )

    cycle = tmp_path / "cycle"
    assert _assemble_batches([snapshot, empty, downstream], cycle) == 0
    summary = json.loads(
        (cycle / "cycle-acquisition-summary.json").read_text(encoding="utf-8")
    )
    assert [batch["downstream_component_ordinal"] for batch in summary["batches"]] == [
        0,
        1,
        2,
    ]


def test_assemble_cycle_acquisition_unrecognized_empty_root_breaks_binding(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "screening-snapshot"
    empty = tmp_path / "empty"
    downstream = tmp_path / "public-plan"
    _write_batch(
        snapshot,
        screened=[_courtlistener_screened("123")],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    empty.mkdir()
    _write_downstream_component(downstream, selections=[_selection("123")])

    assert _assemble_batches([snapshot, empty, downstream], tmp_path / "cycle") == 2
    assert "non-empty screening snapshot root" in capsys.readouterr().err


def test_assemble_cycle_acquisition_help_documents_split_root_order(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "assemble-cycle-acquisition", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "non-empty screening snapshot" in output
    assert "plan/download/bridge/filter component roots" in output
    assert "downstream-only root remains tied" in output
    assert "--expected-cycle-hash" in output
    assert "cryptographically" in output


def test_assemble_cycle_acquisition_requires_expected_cycle_hash(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--batch-root",
                str(snapshot),
                "--output-root",
                str(tmp_path / "cycle"),
                "--execute",
            ]
        )
    assert exc_info.value.code == 2
    assert "--expected-cycle-hash" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_mixed_snapshot_cycle_hashes(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshots = [tmp_path / "snapshot-1", tmp_path / "snapshot-2"]
    for ordinal, snapshot in enumerate(snapshots, start=1):
        _write_batch(
            snapshot,
            screened=[{"candidate_id": f"case-{ordinal}"}],
            exclusions=[],
            selections=[],
            relevance=[],
            documents=[],
        )
    manifest_path = snapshots[1] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cycle_hash"] = "b" * 64
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    assert _assemble_batches(snapshots, tmp_path / "cycle") == 2
    assert "snapshot cycle hash mismatch" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_screening_root_without_manifest(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    (snapshot / "manifest.json").unlink()

    assert _assemble(snapshot, tmp_path / "cycle") == 2
    assert "missing a verified snapshot manifest" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_tampered_snapshot_artifact(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_jsonl(
        snapshot / "screened-cases.jsonl",
        [{"candidate_id": "case-1", "tampered": True}],
    )

    assert _assemble(snapshot, tmp_path / "cycle") == 2
    assert "snapshot file commitment mismatch" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_unbound_downstream_root(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    downstream = tmp_path / "downstream"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(downstream, selections=[_selection("case-1")])

    assert (
        _assemble_batches(
            [snapshot, downstream],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 2
    )
    assert "missing or invalid downstream component provenance" in (
        capsys.readouterr().err
    )


def test_bind_component_cli_builds_real_multi_stage_provenance_chain(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    plan = tmp_path / "plan"
    download = tmp_path / "download"
    bridge = tmp_path / "bridge"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(plan, selections=[_selection("case-1")])
    _write_downstream_component(
        download, documents=[("case-1", "decision", b"decision")]
    )
    _write_downstream_component(
        bridge, relevance=[_relevance("case-1", requires_paid_recovery=False)]
    )

    predecessor: Path | None = None
    for ordinal, (stage, root) in enumerate(
        (("plan", plan), ("download", download), ("bridge", bridge)), start=1
    ):
        predecessor_args = (
            []
            if predecessor is None
            else ["--predecessor-provenance", str(predecessor)]
        )
        assert (
            main(
                [
                    "acquisition",
                    "bind-acquisition-component",
                    "--snapshot",
                    str(snapshot),
                    "--expected-cycle-hash",
                    _TEST_CYCLE_HASH,
                    "--component-stage",
                    stage,
                    "--component-ordinal",
                    str(ordinal),
                    *predecessor_args,
                    "--output-root",
                    str(root),
                    "--execute",
                ]
            )
            == 0
        )
        predecessor = root / COMPONENT_PROVENANCE_FILENAME

    assert (
        _assemble_batches(
            [snapshot, plan, download, bridge],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 0
    )


def test_assemble_cycle_acquisition_rejects_reordered_downstream_components(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(first, selections=[_selection("case-1")])
    _write_downstream_component(
        second, relevance=[_relevance("case-1", requires_paid_recovery=False)]
    )
    _bind_component_chain([snapshot, first, second])

    assert (
        _assemble_batches(
            [snapshot, second, first],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 2
    )
    assert "component_ordinal mismatch" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_downstream_batch_digest_mismatch(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    downstream = tmp_path / "downstream"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(downstream, selections=[_selection("case-1")])
    _bind_component_chain([snapshot, downstream])
    provenance_path = downstream / COMPONENT_PROVENANCE_FILENAME
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["source_snapshot_batch_digest"] = "b" * 64
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    assert (
        _assemble_batches(
            [snapshot, downstream],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 2
    )
    assert "source_snapshot_batch_digest mismatch" in capsys.readouterr().err


@pytest.mark.parametrize(
    "field",
    ("source_snapshot_cycle_hash", "source_snapshot_manifest_sha256"),
)
def test_assemble_cycle_acquisition_rejects_other_downstream_binding_mismatches(
    tmp_path: Path,
    capsys: Any,
    field: str,
) -> None:
    snapshot = tmp_path / "snapshot"
    downstream = tmp_path / "downstream"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(downstream, selections=[_selection("case-1")])
    _bind_component_chain([snapshot, downstream])
    provenance_path = downstream / COMPONENT_PROVENANCE_FILENAME
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance[field] = "b" * 64
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    assert (
        _assemble_batches(
            [snapshot, downstream],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 2
    )
    assert f"{field} mismatch" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_semantically_reversed_stage_chain(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    filter_root = tmp_path / "filter"
    plan_root = tmp_path / "plan"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(
        filter_root, core_filters=[{"candidate_id": "case-1", "included": True}]
    )
    _write_downstream_component(plan_root, selections=[_selection("case-1")])
    _bind_component_chain([snapshot, filter_root, plan_root])

    assert (
        _assemble_batches(
            [snapshot, filter_root, plan_root],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 2
    )
    assert "component stage order is invalid" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_duplicate_snapshot_batch_digest(
    tmp_path: Path,
    capsys: Any,
) -> None:
    first = tmp_path / "snapshot-1"
    second = tmp_path / "snapshot-2"
    for ordinal, root in enumerate((first, second), start=1):
        _write_batch(
            root,
            screened=[{"candidate_id": f"case-{ordinal}"}],
            exclusions=[],
            selections=[],
            relevance=[],
            documents=[],
        )
    first_manifest = json.loads((first / "manifest.json").read_text())
    second_manifest_path = second / "manifest.json"
    second_manifest = json.loads(second_manifest_path.read_text())
    second_manifest["batch_digest"] = first_manifest["batch_digest"]
    second_manifest_path.write_text(json.dumps(second_manifest), encoding="utf-8")

    assert _assemble_batches([first, second], tmp_path / "cycle") == 2
    assert "duplicate snapshot batch digest" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_coherent_mid_read_replacement(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "snapshot"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    original = assembler._read_first_jsonl
    replaced = False

    def replacing_read(root: Path, filenames: Sequence[str]) -> list[Mapping[str, Any]]:
        nonlocal replaced
        records = original(root, filenames)
        if not replaced and filenames == assembler._SCREENED_ARTIFACTS:
            replaced = True
            _write_jsonl(
                snapshot / "screened-cases.jsonl",
                [{"candidate_id": "case-1", "replacement": True}],
            )
            _refresh_snapshot_commitments(snapshot)
        return records

    monkeypatch.setattr(assembler, "_read_first_jsonl", replacing_read)
    assert _assemble(snapshot, tmp_path / "cycle") == 2
    assert "batch root changed during assembly" in capsys.readouterr().err


def test_assemble_cycle_acquisition_rejects_tampered_downstream_artifact(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    downstream = tmp_path / "downstream"
    _write_batch(
        snapshot,
        screened=[{"candidate_id": "case-1"}],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    _write_downstream_component(downstream, selections=[_selection("case-1")])
    _bind_component_chain([snapshot, downstream])
    _write_jsonl(
        downstream / "public-packet-selection-reconciled.jsonl",
        [_selection("case-1"), _selection("case-2")],
    )

    assert (
        _assemble_batches(
            [snapshot, downstream],
            tmp_path / "cycle",
            bind_components=False,
        )
        == 2
    )
    assert "component artifact commitment mismatch" in capsys.readouterr().err


def test_assemble_cycle_acquisition_validates_current_screening_summary_counts(
    tmp_path: Path,
    capsys: Any,
) -> None:
    snapshot = tmp_path / "snapshot"
    _write_batch(
        snapshot,
        screened=[_courtlistener_screened("123")],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )
    (snapshot / "summary.json").write_text(
        json.dumps({"accepted_count": 2, "excluded_count": 0}),
        encoding="utf-8",
    )
    _refresh_snapshot_commitments(snapshot)

    assert _assemble(snapshot, tmp_path / "cycle") == 2
    assert "snapshot summary counts do not reconcile" in capsys.readouterr().err


@pytest.mark.parametrize(
    "screened_record",
    (
        {
            "candidate_id": "courtlistener-docket-123",
            "candidate": {"docket_id": "999"},
        },
        {
            "candidate_id": "999",
            "case_id": "courtlistener-docket-123",
        },
    ),
)
def test_assemble_cycle_acquisition_rejects_conflicting_identity_aliases(
    tmp_path: Path,
    capsys: Any,
    screened_record: dict[str, object],
) -> None:
    batch = tmp_path / "batch"
    _write_batch(
        batch,
        screened=[screened_record],
        exclusions=[],
        selections=[],
        relevance=[],
        documents=[],
    )

    assert _assemble(batch, tmp_path / "cycle") == 2
    assert "CourtListener identity alias conflict" in capsys.readouterr().err


def _assemble(batch: Path, output: Path) -> int:
    return _assemble_batches([batch], output)


def _assemble_batches(
    batches: list[Path], output: Path, *, bind_components: bool = True
) -> int:
    if bind_components:
        _bind_component_chain(batches)
    batch_args = [item for batch in batches for item in ("--batch-root", str(batch))]
    return main(
        [
            "acquisition",
            "assemble-cycle-acquisition",
            "--expected-cycle-hash",
            _TEST_CYCLE_HASH,
            *batch_args,
            "--output-root",
            str(output),
            "--execute",
        ]
    )


def _bind_component_chain(batches: Sequence[Path]) -> None:
    snapshot_manifest: Path | None = None
    predecessor_sha256: str | None = None
    component_ordinal = 0
    for root in batches:
        manifest_path = root / "manifest.json"
        if manifest_path.is_file():
            snapshot_manifest = manifest_path
            predecessor_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            component_ordinal = 0
        has_downstream_files = any(
            (root / filename).is_file()
            for filename in (
                "public-packet-exclusions.jsonl",
                "pacer-gap-bridge-exclusions.jsonl",
                "public-packet-selection-reconciled.jsonl",
                "public-packet-selection.jsonl",
                "public-packet-paid-gaps.jsonl",
                "case-relevance.jsonl",
                "core-filter-results.jsonl",
                "document-downloads-merged.jsonl",
                "free-document-downloads.jsonl",
            )
        )
        if (
            not has_downstream_files
            and not (root / COMPONENT_PROVENANCE_FILENAME).is_file()
        ):
            continue
        if snapshot_manifest is None or predecessor_sha256 is None:
            continue
        component_ordinal += 1
        if manifest_path.is_file():
            component_stage = "combined"
        elif (root / "core-filter-results.jsonl").is_file():
            component_stage = "filter"
        elif any(
            (root / filename).is_file()
            for filename in (
                "case-relevance.jsonl",
                "pacer-gap-bridge-exclusions.jsonl",
            )
        ):
            component_stage = "bridge"
        elif any(
            (root / filename).is_file()
            for filename in (
                "document-downloads-merged.jsonl",
                "free-document-downloads.jsonl",
            )
        ):
            component_stage = "download"
        else:
            component_stage = "plan"
        provenance_path = write_component_provenance(
            root,
            source_snapshot_manifest=snapshot_manifest,
            component_ordinal=component_ordinal,
            predecessor_sha256=predecessor_sha256,
            component_stage=component_stage,
        )
        predecessor_sha256 = hashlib.sha256(provenance_path.read_bytes()).hexdigest()


def _write_batch(
    root: Path,
    *,
    screened: list[dict[str, object]],
    exclusions: list[dict[str, object]],
    selections: list[dict[str, object]],
    relevance: list[dict[str, object]],
    documents: list[tuple[str, str, bytes]],
    paid_gaps: list[dict[str, object]] | None = None,
    core_filters: list[dict[str, object]] | None = None,
    is_snapshot: bool = True,
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
    if selections:
        _write_jsonl(root / "public-packet-selection-reconciled.jsonl", selections)
    if paid_gaps:
        _write_jsonl(root / "public-packet-paid-gaps.jsonl", paid_gaps)
    if relevance:
        _write_jsonl(root / "case-relevance.jsonl", relevance)
    if core_filters:
        _write_jsonl(root / "core-filter-results.jsonl", core_filters)
    manifest: list[dict[str, object]] = []
    for candidate_id, document_id, content in documents:
        path = root / "documents" / candidate_id / f"{document_id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest.append(_manifest(candidate_id, document_id, content))
    if manifest:
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
    if is_snapshot:
        _write_snapshot_manifest(root, screened_by_id, exclusions)


def _write_downstream_component(
    root: Path,
    *,
    selections: list[dict[str, object]] | None = None,
    relevance: list[dict[str, object]] | None = None,
    documents: list[tuple[str, str, bytes]] | None = None,
    paid_gaps: list[dict[str, object]] | None = None,
    core_filters: list[dict[str, object]] | None = None,
) -> None:
    _write_batch(
        root,
        screened=[],
        exclusions=[],
        selections=selections or [],
        relevance=relevance or [],
        documents=documents or [],
        paid_gaps=paid_gaps,
        core_filters=core_filters,
        is_snapshot=False,
    )
    _write_jsonl(root / "screened-cases.jsonl", [])
    (root / "summary.json").unlink()
    if not any(
        (root / filename).is_file()
        for filename in (
            "public-packet-selection-reconciled.jsonl",
            "public-packet-paid-gaps.jsonl",
            "case-relevance.jsonl",
            "core-filter-results.jsonl",
            "free-document-downloads.jsonl",
        )
    ):
        _write_jsonl(root / "public-packet-selection.jsonl", [])


def _write_snapshot_manifest(
    root: Path,
    screened_by_id: Mapping[str, Mapping[str, object]],
    exclusions: Sequence[Mapping[str, object]],
) -> None:
    screened_ids = set(screened_by_id)
    candidate_records = [
        {"candidate_id": candidate_id, "state": "accepted"}
        for candidate_id in screened_ids
    ]
    candidate_records.extend(
        {"candidate_id": str(record["candidate_id"]), "state": "excluded"}
        for record in exclusions
    )
    _write_jsonl(root / "candidates.jsonl", candidate_records)
    _write_jsonl(root / "observations.jsonl", [])
    _write_jsonl(root / "raw-artifacts.jsonl", [])
    (root / "summary.json").write_text(
        json.dumps(
            {
                "accepted_count": len(screened_ids),
                "excluded_count": len(exclusions),
                "processed_count": len(screened_ids) + len(exclusions),
                "reconciliation_complete": True,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    files: dict[str, dict[str, object]] = {}
    for filename in (
        "screened-cases.jsonl",
        "exclusions.jsonl",
        "summary.json",
        "candidates.jsonl",
        "observations.jsonl",
        "raw-artifacts.jsonl",
    ):
        payload = (root / filename).read_bytes()
        files[filename] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "row_count": payload.count(b"\n"),
        }
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "legalforecast-cycle-acquisition-v1",
                "cycle_hash": _TEST_CYCLE_HASH,
                "batch_id": root.name,
                "batch_digest": hashlib.sha256(root.name.encode()).hexdigest(),
                "complete": True,
                "saturated": True,
                "files": files,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _refresh_snapshot_commitments(root: Path) -> None:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for filename in manifest["files"]:
        payload = (root / filename).read_bytes()
        manifest["files"][filename] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "row_count": payload.count(b"\n"),
        }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def _courtlistener_screened(candidate_id: str) -> dict[str, object]:
    namespaced = f"courtlistener-docket-{candidate_id}"
    return {
        "candidate_id": namespaced,
        "candidate": {
            "docket_id": candidate_id,
            "candidate_key": candidate_id,
            "metadata": {"case_id": namespaced},
        },
    }


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


def _write_jsonl(path: Path, records: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _purchase_policy(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    path = tmp_path / "purchase-policy.json"
    cohort_path = tmp_path / "cohort-policy.json"
    decisions = cli._fixture_cohort_policy_decisions()
    decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "2250.00",
        "max_per_case_usd": "73.20",
        "reservation_headroom_required": True,
    }
    cohort = cli.generate_cohort_policy(decisions)
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")
    path.write_text(
        json.dumps(
            generate_case_dev_purchase_policy(
                {
                    "cycle_id": "cycle-1",
                    "cohort_policy_sha256": cohort["policy_sha256"],
                    "canonical_ledger_path": str(ledger),
                    "hard_cap_usd": "2250.00",
                    "opening_committed_spend_usd": "0.00",
                    "opening_case_committed_spend_usd": {},
                    "max_per_case_usd": "73.20",
                    "per_document_reservation_usd": "3.05",
                    "fee_schedule": {
                        "source_citation": "case.dev pricing docs",
                        "verified_at_utc": "2026-07-13T00:00:00Z",
                        "includes_pacer_fees": True,
                        "includes_service_fees": True,
                        "includes_rounding": True,
                    },
                }
            ),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path, ledger, cohort_path
