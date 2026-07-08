from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast._json_io import write_jsonl_objects
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.task_loaders import HarveyLabTaskLoader, LfbTaskLoader
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_lfb_task_loader_indexes_packet_jsonl_without_public_packet_text(
    tmp_path: Path,
) -> None:
    packet = _model_packet().to_record()
    packet_path = tmp_path / "packets.jsonl"
    write_jsonl_objects(packet_path, (packet,))

    index = LfbTaskLoader(suite_version="fixture-suite").load_packet_jsonl(packet_path)

    assert index.index_id == "legalforecast-mtd"
    assert len(index.tasks) == 1
    task = index.tasks[0]
    assert task.family == "legalforecast_mtd"
    assert task.scoring_mode == "lfb_brier"
    assert task.suite_version == "fixture-suite"
    assert task.metadata["candidate_id"] == "cand-1"
    assert task.metadata["case_id"] == "case-1"
    assert task.metadata["required_unit_ids"] == ["count_i_issuer"]
    assert task.metadata["document_hashes"] == {
        "complaint": sha256_text("complaint source"),
        "mtd-memo": sha256_text("mtd-memo source"),
    }
    public_metadata = json.dumps(task.metadata, sort_keys=True)
    assert "complaint text" not in public_metadata
    assert "motion text" not in public_metadata


def test_lfb_task_loader_accepts_run_input_manifest_packet_rows() -> None:
    task = LfbTaskLoader().task_from_record(
        {"model_packet": _model_packet().to_record()}
    )

    assert task.task_id == "lfb:cand-1:full_packet"
    assert task.metadata["prompt_sha256"]
    assert task.metadata["packet_sha256"] == task.task_sha256


def test_lfb_task_loader_rejects_duplicate_task_ids() -> None:
    packet = _model_packet().to_record()

    with pytest.raises(ValueError, match="duplicate"):
        LfbTaskLoader().from_records((packet, packet))


def test_harvey_lab_task_loader_indexes_tasks_and_infers_taxonomy(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "corporate" / "merger_review"
    _write_json(
        task_dir / "task.json",
        {
            "id": "merger-review-1",
            "metadata": {"practice_area": "m-and-a"},
        },
    )
    _write_text(task_dir / "documents" / "agreement.md", "agreement text")

    index = HarveyLabTaskLoader(tmp_path, suite_version="lab-fixture").load_task_index()

    assert len(index.tasks) == 1
    task = index.tasks[0]
    assert task.task_id == "harvey_lab:corporate/merger_review"
    assert task.family == "harvey_lab"
    assert task.scoring_mode == "lab_native"
    assert task.suite_version == "lab-fixture"
    assert task.source_id == "merger-review-1"
    assert task.metadata["module"] == "corporate"
    assert task.metadata["practice_area"] == "m-and-a"
    assert task.metadata["document_count"] == 1
    assert task.metadata["lab_commit"] == "unknown"
    assert {artifact.artifact_id for artifact in task.artifacts} == {
        "task_json",
        "document:documents/agreement.md",
    }


def test_harvey_lab_task_loader_rejects_missing_documents_dir(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "litigation" / "motion"
    _write_json(task_dir / "task.json", {"id": "motion-1"})

    with pytest.raises(ValueError, match="documents"):
        HarveyLabTaskLoader(tmp_path).load_task_index()


def test_harvey_lab_task_loader_rejects_missing_task_json(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "litigation" / "motion"
    _write_text(task_dir / "documents" / "memo.md", "memo")

    with pytest.raises(ValueError, match=r"task\.json"):
        HarveyLabTaskLoader(tmp_path).load_task_directory(task_dir)


def _model_packet():
    return build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            generated_at=datetime(2026, 5, 14, tzinfo=UTC),
            documents=(
                _document("complaint", DocumentRole.COMPLAINT, 1),
                _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
                _document(
                    "decision",
                    DocumentRole.DECISION,
                    50,
                    mounted=False,
                    predecision=False,
                    outcome=True,
                ),
            ),
        ),
        prediction_units=(_unit(),),
        texts=(
            PacketText(source_document_id="complaint", text="complaint text"),
            PacketText(source_document_id="mtd-memo", text="motion text"),
        ),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
    *,
    mounted: bool = True,
    predecision: bool = True,
    outcome: bool = False,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
        source_url_or_reference=f"case.dev://{document_id}",
        sha256=sha256_text(f"{document_id} source"),
        is_predecision_material=predecision,
        is_mounted_for_model=mounted,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=outcome,
        packet_section="filings",
    )


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="count_i_issuer",
        count="I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
