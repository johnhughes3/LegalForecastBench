"""Provider-free tests for the manifest/document-store unitizer adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest.unitizer import (
    ManifestUnitizerInputError,
    _provider_account,
    prepare_manifest_unitizer_inputs,
)
from legalforecast.labeling.provider_journal import load_provider_cycle_caps

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    selection_path = tmp_path / "selection.jsonl"
    store = tmp_path / "store"
    verdict_path = tmp_path / "verdicts.jsonl"
    verdicts: list[dict[str, object]] = []
    selection: list[dict[str, object]] = []
    for number in (1, 2):
        candidate = f"synthetic-candidate-{number}"
        complaint = f"{candidate}-complaint"
        motion = f"{candidate}-motion"
        documents: list[dict[str, object]] = []
        for document_id, role, entry, text in (
            (complaint, "complaint", 1, "Count I\nThe complaint alleges a claim."),
            (
                motion,
                "motion_to_dismiss_memorandum",
                2,
                "The motion challenges Count I.",
            ),
        ):
            pdf_path = store / candidate / f"{document_id}.pdf"
            markdown_path = store / candidate / f"{document_id}.md"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_bytes = f"%PDF synthetic {document_id}".encode()
            pdf_path.write_bytes(pdf_bytes)
            markdown_path.write_text(text, encoding="utf-8")
            markdown_path.with_suffix(".metadata.json").write_text(
                json.dumps(
                    {
                        "candidate_id": candidate,
                        "source_document_id": document_id,
                        "status": "succeeded",
                        "input_path": str(pdf_path),
                        "markdown_path": markdown_path.name,
                        "source_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )
            documents.append(
                {
                    "source_document_id": document_id,
                    "document_role": role,
                    "model_visible": True,
                    "docket_entry_number": entry,
                }
            )
            verdicts.append(
                {
                    "source_document_id": document_id,
                    "verdict": "match",
                    "expected_role": role,
                }
            )
        selection.append(
            {
                "candidate_id": candidate,
                "case_id": f"case-{number}",
                "court": "D. Synthetic",
                "docket_number": f"1:26-cv-{number:05d}",
                "target_motion_entry_numbers": [2],
                "decision_entry_numbers": [9],
                "selected": True,
                "documents": documents,
            }
        )
    selection_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in selection),
        encoding="utf-8",
    )
    _write_jsonl(verdict_path, verdicts)
    return selection_path, store, verdict_path


def test_manifest_unitizer_uses_default_account_for_legacy_caps() -> None:
    caps = load_provider_cycle_caps(
        REPO_ROOT
        / "model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json"
    )

    assert _provider_account(caps, "anthropic") == "default"


def test_prepare_manifest_unitizer_inputs_binds_exact_selection_and_bytes(
    tmp_path: Path,
) -> None:
    selection, store, verdicts = _fixture(tmp_path)

    prepared = prepare_manifest_unitizer_inputs(
        selection_path=selection,
        document_store_roots=(store,),
        verdict_sources=(verdicts,),
        target_case_count=2,
    )

    assert [row["candidate_id"] for row in prepared.selection_records] == [
        "synthetic-candidate-1",
        "synthetic-candidate-2",
    ]
    assert len(prepared.parser_records) == 4
    assert len(prepared.markdown_bytes) == 4
    assert (
        prepared.selection_sha256 == hashlib.sha256(selection.read_bytes()).hexdigest()
    )
    assert all(
        commitment["pdf_sha256"]
        for commitment in prepared.document_commitments.values()
    )


def test_prepare_manifest_unitizer_inputs_trusts_certified_not_claimed_role(
    tmp_path: Path,
) -> None:
    selection, store, verdicts = _fixture(tmp_path)
    rows = [json.loads(line) for line in verdicts.read_text().splitlines()]
    rows[0]["manifest_role"] = "complaint"
    rows[0]["expected_role"] = "cover_sheet"
    _write_jsonl(verdicts, rows)

    with pytest.raises(ManifestUnitizerInputError, match="certified role"):
        prepare_manifest_unitizer_inputs(
            selection_path=selection,
            document_store_roots=(store,),
            verdict_sources=(verdicts,),
            target_case_count=2,
        )
