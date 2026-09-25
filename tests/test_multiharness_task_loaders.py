from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast._json_io import write_jsonl_objects
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.evals.prediction_units import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.task_loaders import (
    HarveyLabTaskLoader,
    LfbTaskLoader,
    ReleaseLfbTaskLoader,
)
from legalforecast.release import (
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    LabelsDraft,
    PredictionUnitDraft,
    ScoringPolicy,
    UnitOutcome,
    issue_release,
)
from legalforecast.release.synthetic import issue_synthetic_release


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


def test_lfb_task_loader_writes_private_solver_input_store(tmp_path: Path) -> None:
    packet = _model_packet().to_record()
    packet_path = tmp_path / "packets.jsonl"
    solver_root = tmp_path / "solver-inputs"
    write_jsonl_objects(packet_path, (packet,))

    index = LfbTaskLoader(suite_version="fixture-suite").load_packet_jsonl(
        packet_path,
        solver_input_root=solver_root,
    )

    solver_index = json.loads(
        (solver_root / "solver-input-index.json").read_text(encoding="utf-8")
    )
    entry = solver_index["entries"][0]
    assert solver_index["task_index_sha256"] == index.index_sha256
    assert entry["task_id"] == index.tasks[0].task_id
    assert entry["task_sha256"] == index.tasks[0].task_sha256
    prompt_file = next(
        item for item in entry["files"] if item["destination_path"] == "prompt.txt"
    )
    source_file = next(
        item
        for item in entry["files"]
        if item["destination_path"] == "source/model-packet.json"
    )
    assert "complaint text" in (solver_root / prompt_file["source_path"]).read_text(
        encoding="utf-8"
    )
    assert (
        json.loads(
            (solver_root / source_file["source_path"]).read_text(encoding="utf-8")
        )
        == packet
    )
    assert "complaint text" not in json.dumps(index.to_record(), sort_keys=True)


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


def test_release_task_loader_binds_exact_public_release_without_labels(
    tmp_path: Path,
) -> None:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    (release_root / "labels-release.json").unlink()
    solver_root = tmp_path / "solver-inputs"

    index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )

    assert len(index.tasks) == 3
    first = index.tasks[0]
    assert first.task_id == "lfb-release:synthetic-three-case-v1:unit-001"
    assert first.task_sha256 == first.metadata["packet_sha256"]
    assert first.metadata["required_unit_ids"] == ["unit-001"]
    assert first.metadata["should_score"] is True
    assert index.tasks[2].metadata["should_score"] is False
    public = json.dumps(index.to_record(), sort_keys=True)
    assert "Forecast whether" not in public
    assert "decision_date" not in public
    assert "labels-release" not in public

    solver_index = json.loads(
        (solver_root / "solver-input-index.json").read_text(encoding="utf-8")
    )
    entry = next(
        item for item in solver_index["entries"] if item["task_id"] == first.task_id
    )
    packet_file = next(
        item
        for item in entry["files"]
        if item["destination_path"] == "source/model-packet.json"
    )
    prompt_file = next(
        item for item in entry["files"] if item["destination_path"] == "prompt.txt"
    )
    assert (solver_root / packet_file["source_path"]).read_bytes() == (
        release_root / "packets/unit-001.json"
    ).read_bytes()
    assert (solver_root / prompt_file["source_path"]).read_bytes() == (
        release_root / "prompts/unit-001.txt"
    ).read_bytes()


def test_release_case_loader_batches_units_and_stages_only_shared_visible_documents(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    documents = (
        DocumentDraft(
            document_id="complaint",
            role="complaint",
            path="documents/case-001/complaint.txt",
        ),
        DocumentDraft(
            document_id="opposition",
            role="opposition",
            path="documents/case-001/opposition.txt",
        ),
    )
    (artifact_root / documents[0].path).parent.mkdir(parents=True)
    (artifact_root / documents[0].path).write_bytes(b"complaint visible")
    (artifact_root / documents[1].path).write_bytes(b"opposition excluded")
    prompt_path = "prompts/case-001.txt"
    packet_paths = ("packets/unit-001.json", "packets/unit-002.json")
    (artifact_root / prompt_path).parent.mkdir(parents=True)
    (artifact_root / prompt_path).write_bytes(b"shared blinded case prompt")
    for unit_id, packet_path in zip(
        ("unit-001", "unit-002"), packet_paths, strict=True
    ):
        (artifact_root / packet_path).parent.mkdir(parents=True, exist_ok=True)
        (artifact_root / packet_path).write_bytes(
            ARTIFACT_CANONICAL_JSON_V1.encode(
                {
                    "case_id": "case-001",
                    "claim_name": f"Claim {unit_id}",
                    "count": unit_id,
                    "decision_date": "2026-08-23",
                    "defendant_group": "defendants",
                    "model_visible_document_ids": ["complaint"],
                    "policy_digest": "1" * 64,
                    "unit_id": unit_id,
                }
            )
        )
    issued = issue_release(
        ForecastDraft(
            release_id="case-batch-fixture-v1",
            policy_digest="1" * 64,
            code_version="fixture-code-v1",
            packet_builder_version="fixture-packet-v1",
            cases=(CaseDraft(case_id="case-001", documents=documents),),
            prediction_units=tuple(
                PredictionUnitDraft(
                    unit_id=unit_id,
                    case_id="case-001",
                    claim_name=f"Claim {unit_id}",
                    defendant_group="defendants",
                    count=unit_id,
                    should_score=True,
                    model_visible_document_ids=("complaint",),
                    packet_path=packet_path,
                    prompt_path=prompt_path,
                )
                for unit_id, packet_path in zip(
                    ("unit-001", "unit-002"), packet_paths, strict=True
                )
            ),
        ),
        LabelsDraft(
            release_id="case-batch-fixture-v1",
            scoring_policy=ScoringPolicy(policy_id="fixture-brier-v1"),
            unit_outcomes=(
                UnitOutcome(unit_id="unit-001", outcome=0),
                UnitOutcome(unit_id="unit-002", outcome=1),
            ),
        ),
        artifact_root=artifact_root,
    )
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "forecast-release.json").write_bytes(
        issued.payloads["forecast-release.json"]
    )
    solver_root = tmp_path / "solver-inputs"

    index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=artifact_root,
        solver_input_root=solver_root,
        case_batching=True,
    )

    assert len(index.tasks) == 1
    task = index.tasks[0]
    assert task.metadata["required_unit_ids"] == ["unit-001", "unit-002"]
    assert task.metadata["scoreable_unit_ids"] == ["unit-001", "unit-002"]
    assert [doc["document_id"] for doc in task.metadata["model_visible_documents"]] == [
        "complaint"
    ]
    solver_index = json.loads(
        (solver_root / "solver-input-index.json").read_text(encoding="utf-8")
    )
    entry = solver_index["entries"][0]
    visible_paths = {
        file["destination_path"] for file in entry["files"] if file["solver_visible"]
    }
    assert visible_paths == {"prompt.txt", "documents/0000-complaint.txt"}
    assert "opposition" not in json.dumps(solver_index, sort_keys=True)


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
