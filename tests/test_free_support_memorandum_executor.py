from __future__ import annotations

import hashlib
import json
from pathlib import Path

import legalforecast.cli as cli
import legalforecast.ingestion.free_support_memorandum_executor as executor
import legalforecast.ingestion.free_support_memorandum_executor_cli as executor_cli
import legalforecast.ingestion.free_support_memorandum_recovery as planner
import pytest
from legalforecast.ingestion.cohort_document_materializer import (
    DocumentSource,
    prepare_cohort_document_materialization,
)
from legalforecast.ingestion.disclosure_clearance import DisclosurePdfScan
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.target_raw_docket_auxiliary_provenance import (
    VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
)

_URL = (
    "https://storage.courtlistener.com/recap/gov.uscourts.nysd.1/"
    "gov.uscourts.nysd.1.14.0.pdf"
)


def _raw_html() -> bytes:
    return f"""
    <html><body><div id="docket-entry-table"><div id="entry-14" class="row">
    <div class="col-xs-1">14</div><div class="col-xs-3">Jul 6, 2026</div>
    <div class="col-xs-8">MEMORANDUM OF LAW in Support re: 13 FIRST MOTION to Dismiss.
    <div class="row recap-documents"><div>Main Document</div><div>Memo</div>
    <a href="{_URL}">Download PDF</a></div></div></div></div></body></html>
    """.encode()


def _bridge(tmp_path: Path) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    old_selection = _selection()
    selection_path = tmp_path / "old-selection.jsonl"
    selection_path.write_bytes(old_selection)
    descriptor = {
        "schema_version": (
            "legalforecast.target_raw_docket_auxiliary_provenance_bridge.v1"
        ),
        "bridge": {
            "selection": {
                "path": "old-selection.jsonl",
                "sha256": hashlib.sha256(old_selection).hexdigest(),
                "candidate_count": 100,
                "candidate_id_set_sha256": "a" * 64,
            }
        },
        "bridge_sha256": "b" * 64,
    }
    descriptor_path = tmp_path / "bridge.json"
    descriptor_path.write_bytes(json.dumps(descriptor, sort_keys=True).encode())
    return VerifiedTargetRawDocketAuxiliaryProvenanceBridge(
        bridge_path=descriptor_path,
        bridge_sha256=hashlib.sha256(descriptor_path.read_bytes()).hexdigest(),
        raw_artifacts_manifest_path=tmp_path / "raw-artifacts.jsonl",
        raw_artifacts_manifest_sha256="c" * 64,
        run_card_path=tmp_path / "bridge-run-card.json",
        run_card_sha256="d" * 64,
        source_snapshot_path=tmp_path / "source",
        source_snapshot_manifest_sha256="e" * 64,
        source_raw_html_dir=tmp_path / "raw-html",
        selected_candidate_ids=("courtlistener-docket-73327542",),
        raw_artifact_bytes_by_candidate={"courtlistener-docket-73327542": _raw_html()},
        raw_artifact_bytes_by_path={},
    )


def _selection() -> bytes:
    rows: list[dict[str, object]] = []
    for number in range(100):
        candidate_id = "73327542" if number == 0 else f"8{number:07d}"
        documents = [
            {
                "source_document_id": f"{candidate_id}-entry-1-complaint",
                "document_role": "complaint",
            }
        ]
        row: dict[str, object] = {
            "candidate_id": candidate_id,
            "selected": True,
            "documents": documents,
            "target_motion_entry_numbers": [13] if number == 0 else [2],
        }
        rows.append(row)
    return b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for row in rows
    )


def _materializer_v2_projection(tmp_path: Path, selection: bytes) -> dict[str, object]:
    successor_root = tmp_path / "successor"
    successor_root.mkdir()
    selection_path = successor_root / "target-cohort-selection.jsonl"
    selection_path.write_bytes(selection)
    return {
        "run_card": {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2)
        },
        "selection_path": selection_path,
        "selection_records": tuple(
            json.loads(line) for line in selection.splitlines() if line
        ),
    }


@pytest.fixture
def verified_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, bytes]:
    bridge = _bridge(tmp_path)
    monkeypatch.setattr(
        planner,
        "load_verified_target_raw_docket_auxiliary_provenance_bridge",
        lambda _: bridge,
    )
    plan = planner.derive_free_support_memorandum_recovery_plan(
        bridge_descriptor_path=bridge.bridge_path
    )
    return bridge.bridge_path, plan.record_bytes


def _complete_scan(_: bytes) -> DisclosurePdfScan:
    return DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=(),
    )


def test_executes_one_additive_public_source_and_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verified_plan: tuple[Path, bytes],
) -> None:
    bridge_path, plan_bytes = verified_plan
    monkeypatch.setattr(executor, "scan_disclosure_document", _complete_scan)
    selection = _selection()
    output_root = tmp_path / "augmentation"
    result = executor.execute_free_support_memorandum_source_augmentation(
        persisted_plan_bytes=plan_bytes,
        bridge_descriptor_path=bridge_path,
        corrected_selection_bytes=selection,
        output_root=output_root,
        source=FixtureFreeDocumentSource({_URL: b"%PDF-1.7\npublic memo"}),
    )
    for name, payload in (
        ("free-document-request.json", result.request_bytes),
        ("free-document-download.json", result.download_bytes),
        ("disclosure-clearance.json", result.clearance_bytes),
        ("source-augmentation.json", result.projection_bytes),
    ):
        (output_root / name).write_bytes(payload)
    replay = executor.verify_free_support_memorandum_source_augmentation(
        persisted_plan_bytes=plan_bytes,
        bridge_descriptor_path=bridge_path,
        corrected_selection_bytes=selection,
        output_root=output_root,
    )
    assert replay.projection["base_selected_candidate_count"] == 100
    assert replay.projection["base_selection_document_count"] == 100
    assert replay.projection["augmented_selection_document_count"] == 101
    assert replay.clearance.to_record()["status"] == "cleared"

    v2_projection = _materializer_v2_projection(tmp_path, selection)
    source, snapshots, metadata, restriction = (
        cli._materializer_successor_v2_source_augmentation(
            augmentation_root=output_root,
            plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_path,
            projection=v2_projection,
            selection_bytes=selection,
            authoritative_available_keys={
                (str(row["candidate_id"]), str(document["source_document_id"]))
                for row in v2_projection["selection_records"]
                for document in row["documents"]
            },
        )
    )
    assert source.manifest == (replay.download.to_record(),)
    assert source.clearance == (replay.clearance.to_record(),)
    assert set(snapshots) == {
        output_root / "source-augmentation.json",
        output_root / "free-document-download.json",
        output_root / "disclosure-clearance.json",
    }
    assert metadata["materializable_document_count"] == 101
    assert restriction == {
        "candidate_id": "73327542",
        "source_document_id": "73327542-entry-14-motion-to-dismiss-memorandum",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "is_sealed": False,
        "is_private": False,
    }

    materialization = prepare_cohort_document_materialization(
        (
            DocumentSource(
                phase="free",
                document_root=output_root / "documents",
                manifest=(replay.download.to_record(),),
                clearance=(replay.clearance.to_record(),),
            ),
        ),
        selected_document_keys={
            ("73327542", "73327542-entry-14-motion-to-dismiss-memorandum")
        },
        output_root=tmp_path / "materialized",
    )
    assert len(materialization.documents) == 1


def test_materializer_rejects_tampered_augmentation_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verified_plan: tuple[Path, bytes],
) -> None:
    bridge_path, plan_bytes = verified_plan
    monkeypatch.setattr(executor, "scan_disclosure_document", _complete_scan)
    selection = _selection()
    output_root = tmp_path / "augmentation"
    result = executor.execute_free_support_memorandum_source_augmentation(
        persisted_plan_bytes=plan_bytes,
        bridge_descriptor_path=bridge_path,
        corrected_selection_bytes=selection,
        output_root=output_root,
        source=FixtureFreeDocumentSource({_URL: b"%PDF-1.7\npublic memo"}),
    )
    for name, payload in (
        ("free-document-request.json", result.request_bytes),
        ("free-document-download.json", result.download_bytes),
        ("disclosure-clearance.json", result.clearance_bytes),
        ("source-augmentation.json", result.projection_bytes),
    ):
        (output_root / name).write_bytes(payload)
    (output_root / "source-augmentation.json").write_bytes(b"{}\n")
    v2_projection = _materializer_v2_projection(tmp_path, selection)

    with pytest.raises(
        cli.CommandError, match="source augmentation package did not replay"
    ):
        cli._materializer_successor_v2_source_augmentation(
            augmentation_root=output_root,
            plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_path,
            projection=v2_projection,
            selection_bytes=selection,
            authoritative_available_keys={
                (str(row["candidate_id"]), str(document["source_document_id"]))
                for row in v2_projection["selection_records"]
                for document in row["documents"]
            },
        )


def test_rejects_selection_that_already_contains_the_fixed_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verified_plan: tuple[Path, bytes],
) -> None:
    bridge_path, plan_bytes = verified_plan
    monkeypatch.setattr(executor, "scan_disclosure_document", _complete_scan)
    rows = [json.loads(line) for line in _selection().splitlines()]
    rows[0]["documents"].append(
        {
            "source_document_id": "73327542-entry-14-motion-to-dismiss-memorandum",
            "document_role": "motion_to_dismiss_memorandum",
        }
    )
    selection = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for row in rows
    )
    source = FixtureFreeDocumentSource({_URL: b"%PDF-1.7\npublic memo"})
    with pytest.raises(
        executor.FreeSupportMemorandumExecutorError, match="differs from historical"
    ):
        executor.execute_free_support_memorandum_source_augmentation(
            persisted_plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_path,
            corrected_selection_bytes=selection,
            output_root=tmp_path / "augmentation",
            source=source,
        )
    assert source.requested_urls == ()


@pytest.mark.parametrize(
    ("field", "replacement", "match"),
    [
        (
            "source_url",
            "https://storage.courtlistener.com/recap/forged.pdf",
            "fixed request",
        ),
        ("local_path", "../forged.pdf", "fixed request"),
        ("reused_existing", True, "fixed request"),
    ],
)
def test_replay_rejects_tampered_persisted_download_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verified_plan: tuple[Path, bytes],
    field: str,
    replacement: str | bool,
    match: str,
) -> None:
    bridge_path, plan_bytes = verified_plan
    monkeypatch.setattr(executor, "scan_disclosure_document", _complete_scan)
    output_root = tmp_path / "augmentation"
    result = executor.execute_free_support_memorandum_source_augmentation(
        persisted_plan_bytes=plan_bytes,
        bridge_descriptor_path=bridge_path,
        corrected_selection_bytes=_selection(),
        output_root=output_root,
        source=FixtureFreeDocumentSource({_URL: b"%PDF-1.7\npublic memo"}),
    )
    download = result.download.to_record()
    download[field] = replacement
    for name, payload in (
        ("free-document-request.json", result.request_bytes),
        ("free-document-download.json", executor._canonical_bytes(download)),
        ("disclosure-clearance.json", result.clearance_bytes),
        ("source-augmentation.json", result.projection_bytes),
    ):
        (output_root / name).write_bytes(payload)

    with pytest.raises(executor.FreeSupportMemorandumExecutorError, match=match):
        executor.verify_free_support_memorandum_source_augmentation(
            persisted_plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_path,
            corrected_selection_bytes=_selection(),
            output_root=output_root,
        )


@pytest.mark.parametrize("mutated_row", [0, 1])
def test_cli_rejects_v2_selection_changed_after_authenticated_replay(
    tmp_path: Path,
    verified_plan: tuple[Path, bytes],
    mutated_row: int,
) -> None:
    """Both the ECF-14 row and unrelated rows are bound by v2 replay bytes."""

    bridge_path, _plan_bytes = verified_plan
    successor_root = tmp_path / "successor-v2"
    selection_path = successor_root / "target-cohort-selection.jsonl"
    selection = _selection()
    selection_path.parent.mkdir(parents=True)
    selection_path.write_bytes(selection)

    def verifier(root: Path) -> dict[str, object]:
        assert root == successor_root
        return {
            "selection_path": selection_path,
            "verified_artifact_bytes": {str(selection_path.absolute()): selection},
        }

    rows = [json.loads(line) for line in selection.splitlines()]
    rows[mutated_row]["mutation"] = "forged"
    selection_path.write_bytes(
        b"".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            for row in rows
        )
    )

    with pytest.raises(
        executor_cli.FreeSupportMemorandumExecutorCliError,
        match="selection changed during v2 replay",
    ):
        executor_cli._run_with_test_dependencies(
            successor_root=successor_root,
            plan_path=tmp_path / "plan.json",
            bridge_descriptor_path=bridge_path,
            output_root=tmp_path / "augmentation",
            source=FixtureFreeDocumentSource({_URL: b"unused"}),
            v2_projection_verifier=verifier,
        )
