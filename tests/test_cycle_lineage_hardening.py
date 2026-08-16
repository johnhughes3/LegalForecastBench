from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from legalforecast.ingestion.cycle_lineage_index import (
    CycleLineageIndexError,
    locate_cycle_lineage,
    register_cycle_stage_head,
)
from legalforecast.ingestion.cycle_orchestrator import authenticate_output_paths
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes

COMMIT_A = "a" * 40


def _write_stage_card(
    root: Path, *, commitments: Mapping[str, object] | None = None
) -> Path:
    output = root / "output.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("authentic\n", encoding="utf-8")
    card = root / "run-cards/parse.json"
    card.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "parse-documents",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "resume": True,
        "paid_activity_executed": False,
        "output_paths": [str(output)],
    }
    if commitments is not None:
        body["output_commitments"] = commitments
    card.write_bytes(canonical_json_bytes(body))
    return card


def test_stage_head_registration_rejects_broken_declared_commitment(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "artifacts/29-old-lineage-v1"
    card = _write_stage_card(
        stage_root,
        commitments={
            "artifact": {
                "path": str(stage_root / "output.jsonl"),
                "sha256": f"sha256:{'0' * 64}",
            }
        },
    )
    with pytest.raises(
        CycleLineageIndexError, match="commitment differs from bytes on disk"
    ):
        register_cycle_stage_head(
            index_path=tmp_path / "lineage-index.json",
            cycle_id="cycle-1",
            command="parse-documents",
            run_card_path=card,
            code_commit=COMMIT_A,
        )


def test_locate_rejects_registered_head_when_later_stage_directory_exists(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "artifacts/29-old-lineage-v1"
    card = _write_stage_card(stage_root)
    (stage_root.parent / "30-new-lineage-v1").mkdir()
    index = tmp_path / "lineage-index.json"
    register_cycle_stage_head(
        index_path=index,
        cycle_id="cycle-1",
        command="parse-documents",
        run_card_path=card,
        code_commit=COMMIT_A,
    )
    with pytest.raises(
        CycleLineageIndexError, match="unregistered later stages exist: 30"
    ):
        locate_cycle_lineage(index_path=index, cycle_id="cycle-1")


def test_locate_ignores_later_numbered_regular_file(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "artifacts/29-old-lineage-v1"
    card = _write_stage_card(stage_root)
    (stage_root.parent / "30-notes.txt").write_text("not a stage\n", encoding="utf-8")
    index = tmp_path / "lineage-index.json"
    register_cycle_stage_head(
        index_path=index,
        cycle_id="cycle-1",
        command="parse-documents",
        run_card_path=card,
        code_commit=COMMIT_A,
    )

    status = locate_cycle_lineage(index_path=index, cycle_id="cycle-1")
    assert status["verification"] == "VERIFIED"


def test_stage_head_registration_rejects_broken_nested_commitment(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "artifacts/29-old-lineage-v1"
    output = stage_root / "output.jsonl"
    card = _write_stage_card(
        stage_root,
        commitments={
            "stage_a_lineage": {
                "disclosure_clearance": {
                    "path": str(output),
                    "sha256": f"sha256:{'0' * 64}",
                }
            }
        },
    )
    with pytest.raises(
        CycleLineageIndexError, match="commitment differs from bytes on disk"
    ):
        register_cycle_stage_head(
            index_path=tmp_path / "lineage-index.json",
            cycle_id="cycle-1",
            command="parse-documents",
            run_card_path=card,
            code_commit=COMMIT_A,
        )


def test_stage_head_registration_accepts_prefixed_directory_tree_commitment(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "artifacts/29-old-lineage-v1"
    output = stage_root / "documents"
    output.mkdir(parents=True)
    (output / "document.txt").write_text("authentic\n", encoding="utf-8")
    actual = authenticate_output_paths((output,))[0]
    card = _write_stage_card(
        stage_root,
        commitments={
            "documents": {
                "path": str(output),
                "kind": "directory",
                "tree_sha256": f"sha256:{actual['tree_sha256']}",
                "entry_count": actual["entry_count"],
                "file_count": actual["file_count"],
            }
        },
    )
    result = register_cycle_stage_head(
        index_path=tmp_path / "lineage-index.json",
        cycle_id="cycle-1",
        command="parse-documents",
        run_card_path=card,
        code_commit=COMMIT_A,
    )
    assert result["root_identity_sha256"]
