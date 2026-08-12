from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
from legalforecast.unitization.review import (
    canonical_sha256,
    require_finalized_envelopes,
)
from legalforecast.unitization.unitizer_terminal_review import (
    build_unitizer_terminal_review_queue_record,
)


def test_apply_unitizer_terminal_review_replays_raw_partitions_and_exact_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    _stub_authenticated_lineage(monkeypatch, fixture)
    journal_before = fixture["journal"].read_bytes()

    assert main(_argv(fixture, tmp_path / "applied")) == 0

    finalized_path = tmp_path / "applied/finalized-prediction-units.jsonl"
    finalized = _read_jsonl(finalized_path)
    assert [row["candidate_id"] for row in finalized] == ["ordinary", "terminal"]
    assert finalized[1]["schema_version"] == (
        "legalforecast.finalized_prediction_units.v4"
    )
    assert finalized[1]["prediction_units"][0]["unit_id"] == "terminal-contract"
    assert require_finalized_envelopes(finalized) == tuple(finalized)
    assert fixture["journal"].read_bytes() == journal_before

    card = json.loads(
        (tmp_path / "applied/run-cards/apply-unitizer-terminal-review.json").read_text()
    )
    assert card["record_count"] == 2
    assert card["ordinary_candidate_count"] == 1
    assert card["terminal_candidate_count"] == 1
    assert card["zero_provider_activity_evidence"] is True
    assert len(card["input_paths"]) == 11
    replay_args = argparse.Namespace(
        llm_unitization_run_card=fixture["unit_card"],
        llm_review_stage_a_run_card=fixture["structural_card"],
        provider_cycle_caps=fixture["caps"],
        provider_journal=fixture["journal"],
        controlled_private_root=None,
        purchase_ledger_initialization_receipt=None,
    )
    cli._verify_terminal_apply_run_card(  # pyright: ignore[reportPrivateUsage]
        replay_args,
        run_card_path=(
            tmp_path / "applied/run-cards/apply-unitizer-terminal-review.json"
        ),
        finalized_path=finalized_path,
        expected_selection_path=fixture["selection"],
        expected_parser_manifest_path=None,
        expected_markdown_root=fixture["markdown_root"],
    )

    finalized[1]["prediction_units"][0]["claim_name"] = "Tampered claim"
    _write_jsonl(finalized_path, finalized)
    with pytest.raises(cli.CommandError, match="commitments changed"):
        cli._verify_terminal_apply_run_card(  # pyright: ignore[reportPrivateUsage]
            replay_args,
            run_card_path=(
                tmp_path / "applied/run-cards/apply-unitizer-terminal-review.json"
            ),
            finalized_path=finalized_path,
            expected_selection_path=fixture["selection"],
            expected_parser_manifest_path=None,
            expected_markdown_root=fixture["markdown_root"],
        )


def test_terminal_successor_rejects_citation_drift_and_candidate_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    _stub_authenticated_lineage(monkeypatch, fixture)
    adjudications = _read_jsonl(fixture["terminal_adjudications"])
    adjudications[0]["finalized_units"][0]["source_citations"][0]["excerpt"] = (
        "A different claim."
    )
    _write_jsonl(fixture["terminal_adjudications"], adjudications)
    assert main(_argv(fixture, tmp_path / "bad-citation")) == 2

    fixture = _fixture(tmp_path / "exclude")
    _stub_authenticated_lineage(monkeypatch, fixture)
    exclusion = _read_jsonl(fixture["terminal_adjudications"])[0]
    exclusion["disposition"] = "CANDIDATE-EXCLUSION"
    exclusion["finalized_units"] = []
    exclusion["exclusion_reason"] = "settled case requires replacement"
    _write_jsonl(fixture["terminal_adjudications"], [exclusion])
    assert main(_argv(fixture, tmp_path / "excluded")) == 2
    assert not (tmp_path / "excluded/finalized-prediction-units.jsonl").exists()


@pytest.mark.parametrize("artifact", ("escalations", "terminal_queue"))
def test_terminal_successor_rejects_receipt_or_queue_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    fixture = _fixture(tmp_path)
    _stub_authenticated_lineage(monkeypatch, fixture)
    records = _read_jsonl(fixture[artifact])
    if artifact == "escalations":
        records[0]["failed_attempts"][0]["failure_message"] = "tampered"
    else:
        records[0]["reason"]["summary"] = "tampered"
    _write_jsonl(fixture[artifact], records)

    assert main(_argv(fixture, tmp_path / "rejected")) == 2
    assert not (tmp_path / "rejected/finalized-prediction-units.jsonl").exists()


def test_terminal_successor_card_dispatches_stage_b_chain_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    card_path = tmp_path / "terminal-card.json"
    card_path.write_text(json.dumps({"stage": "apply-unitizer-terminal-review"}))
    finalized_path = tmp_path / "finalized.jsonl"
    finalized_path.write_text("")
    expected = (object(), tmp_path / "unit-card.json", tmp_path / "queue.jsonl")
    calls: list[tuple[Path, Path]] = []

    def verify_terminal(_args: object, **kwargs: Any) -> tuple[object, Path, Path]:
        calls.append((kwargs["run_card_path"], kwargs["finalized_path"]))
        return expected

    monkeypatch.setattr(cli, "_verify_terminal_apply_run_card", verify_terminal)
    result = cli._verify_finalized_stage_a_provider_chain(  # pyright: ignore[reportPrivateUsage]
        argparse.Namespace(unitization_review_run_card=card_path),
        finalized_prediction_units_path=finalized_path,
    )
    assert result == expected
    assert calls == [(card_path, finalized_path)]


def _fixture(tmp_path: Path) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    complaint_text = "Page 1\nCount I pleads breach of contract.\n"
    motion_text = "Page 2\nDefendant moves to dismiss Count I.\n"
    (markdown_root / "complaint.md").write_text(complaint_text)
    (markdown_root / "motion.md").write_text(motion_text)
    documents = [
        _document("complaint", "complaint", 1),
        _document("motion", "motion_to_dismiss_memorandum", 5),
    ]
    selection = [
        {
            "candidate_id": "ordinary",
            "case_id": "case-ordinary",
            "documents": documents,
        },
        {
            "candidate_id": "terminal",
            "case_id": "case-terminal",
            "documents": documents,
        },
    ]
    receipt = _receipt(complaint_text, motion_text)
    queue = build_unitizer_terminal_review_queue_record(receipt)
    adjudication = _adjudication(receipt, queue)
    raw: list[dict[str, Any]] = [
        {
            "candidate_id": "ordinary",
            "case_id": "case-ordinary",
            "prediction_units": [_unit("ordinary-contract")],
        },
        {
            "candidate_id": "terminal",
            "case_id": "case-terminal",
            "prediction_units": [],
        },
    ]
    paths = {
        name: tmp_path / filename
        for name, filename in {
            "selection": "selection.jsonl",
            "raw": "prediction-units.jsonl",
            "ordinary_queue": "ordinary-queue.jsonl",
            "ordinary_adjudications": "ordinary-adjudications.jsonl",
            "escalations": "terminal-escalations.jsonl",
            "terminal_queue": "terminal-queue.jsonl",
            "terminal_adjudications": "terminal-adjudications.jsonl",
            "unit_card": "llm-unitize.json",
            "structural_card": "llm-review.json",
            "caps": "caps.json",
            "journal": "provider.sqlite3",
        }.items()
    }
    record_groups: tuple[tuple[str, list[dict[str, Any]]], ...] = (
        ("selection", selection),
        ("raw", raw),
        ("ordinary_queue", []),
        ("ordinary_adjudications", []),
        ("escalations", [receipt]),
        ("terminal_queue", [queue]),
        ("terminal_adjudications", [adjudication]),
    )
    for key, records in record_groups:
        _write_jsonl(paths[key], records)
    paths["unit_card"].write_text(
        json.dumps(
            {"model_execution": {"provider_attempt_namespace": "claim-ontology-v5"}}
        )
    )
    paths["structural_card"].write_text("{}")
    paths["caps"].write_text("{}")
    paths["journal"].write_bytes(b"provider-journal-unchanged")
    return {
        **paths,
        "markdown_root": markdown_root,
        "selection_records": selection,
        "receipt": receipt,
    }


def _stub_authenticated_lineage(
    monkeypatch: pytest.MonkeyPatch, fixture: dict[str, Any]
) -> None:
    receipt = fixture["receipt"]
    parser_records = tuple(
        {
            "candidate_id": candidate,
            "source_document_id": document,
            "status": "succeeded",
            "markdown_path": f"{document}.md",
        }
        for candidate in ("ordinary", "terminal")
        for document in ("complaint", "motion")
    )
    lineage = SimpleNamespace(
        selection_records=tuple(fixture["selection_records"]),
        parser_records=parser_records,
        markdown_root=fixture["markdown_root"],
        markdown_bytes={
            "complaint.md": (fixture["markdown_root"] / "complaint.md").read_bytes(),
            "motion.md": (fixture["markdown_root"] / "motion.md").read_bytes(),
        },
        unitizer_terminal_escalations={
            "terminal": (
                SimpleNamespace(to_record=lambda: receipt),
                {"path": "receipt"},
            )
        },
        file_snapshots={},
        document_root=fixture["markdown_root"],
        document_tree=cli._materializer_tree_snapshot(fixture["markdown_root"]),  # pyright: ignore[reportPrivateUsage]
    )

    def verified_chain(*_args: Any, **_kwargs: Any) -> tuple[Any, Path]:
        return lineage, fixture["unit_card"]

    def verified_review(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(cli, "_verified_shared_provider_chain", verified_chain)
    monkeypatch.setattr(cli, "_verify_stage_a_review_run_card", verified_review)


def _argv(fixture: dict[str, Any], output_root: Path) -> list[str]:
    mapping = (
        ("selection", "selection"),
        ("prediction-units", "raw"),
        ("llm-unitization-run-card", "unit_card"),
        ("llm-review-stage-a-run-card", "structural_card"),
        ("provider-cycle-caps", "caps"),
        ("provider-journal", "journal"),
        ("unitization-review-queue", "ordinary_queue"),
        ("unitization-review-adjudications", "ordinary_adjudications"),
        ("terminal-escalations", "escalations"),
        ("unitizer-terminal-review-queue", "terminal_queue"),
        ("unitizer-terminal-adjudications", "terminal_adjudications"),
    )
    argv = [
        "acquisition",
        "apply-unitizer-terminal-review",
        "--output-root",
        str(output_root),
    ]
    for flag, key in mapping:
        argv.extend((f"--{flag}", str(fixture[key])))
    return [*argv, "--execute"]


def _document(document_id: str, role: str, docket: int) -> dict[str, Any]:
    return {
        "source_document_id": document_id,
        "document_role": role,
        "docket_entry_number": docket,
        "model_visible": True,
        "contains_target_outcome": False,
    }


def _unit(unit_id: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "count": "I",
        "claim_name": "Breach of contract",
        "defendant_group": "Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "separable_subclaim": None,
        "source_citations": [
            {
                "document_id": "complaint",
                "docket_entry_number": 1,
                "page": 1,
                "paragraph": None,
                "excerpt": "Count I pleads breach of contract.",
            },
            {
                "document_id": "motion",
                "docket_entry_number": 5,
                "page": 2,
                "paragraph": None,
                "excerpt": "Defendant moves to dismiss Count I.",
            },
        ],
        "grouping": "individual",
        "grouping_rationale": None,
        "uncertainty_notes": None,
        "should_score": True,
    }


def _receipt(complaint: str, motion: str) -> dict[str, Any]:
    prompt = "Use only supplied predecision sources."
    return {
        "schema_version": "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1",
        "candidate_id": "terminal",
        "case_id": "case-terminal",
        "unitizer_model_key": "anthropic:test",
        "model_registry_sha256": "1" * 64,
        "provider_attempt_namespace": "claim-ontology-v5",
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "predecision_source_commitments": [
            {
                "source_document_id": "complaint",
                "document_role": "complaint",
                "docket_entry_number": 1,
                "description": "Complaint",
                "markdown_sha256": "sha256:"
                + hashlib.sha256(complaint.encode()).hexdigest(),
            },
            {
                "source_document_id": "motion",
                "document_role": "motion_to_dismiss_memorandum",
                "docket_entry_number": 5,
                "description": "Motion",
                "markdown_sha256": "sha256:"
                + hashlib.sha256(motion.encode()).hexdigest(),
            },
        ],
        "failed_attempts": [
            {
                "attempt_ordinal": ordinal,
                "raw_response_sha256": f"sha256:{ordinal:064x}",
                "normalized_response_sha256": f"sha256:{ordinal + 3:064x}",
                "failure_type": "citation_reconstruction_failure",
                "failure_message": "invalid citation",
            }
            for ordinal in (1, 2, 3)
        ],
    }


def _adjudication(receipt: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "legalforecast.unitization_adjudication.v3",
        "adjudication_id": "adj-terminal",
        "candidate_id": "terminal",
        "case_id": "case-terminal",
        "review_ids": [queue["review_id"]],
        "disposition": "ADD",
        "finalized_units": [_unit("terminal-contract")],
        "adjudicator_id": "attorney",
        "adjudication_notes": "Reconstructed from complaint and motion.",
        "terminal_escalation_sha256": canonical_sha256(receipt),
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]
