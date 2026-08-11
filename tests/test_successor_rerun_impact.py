"""Focused tests for the provider-free successor rerun impact planner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.ingestion.successor_rerun_impact import (
    ADVISORY_WARNING,
    PROPOSAL_SCHEMA_VERSION,
    RerunInputs,
    SuccessorRerunImpactError,
    current_documents_from_parser_records,
    failed_successor_rerun_impact,
    load_successor_proposal,
    parser_output_sha256_from_records,
    parser_revision_from_records,
    plan_successor_rerun_impact,
)
from legalforecast.labeling.provider_journal import ProviderCallIdentity


def test_one_document_replacement_reuses_unaffected_parser_and_provider_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current, proposal_path, prompts, rows = _fixture(tmp_path, replace_document=True)
    before = _tree_bytes(tmp_path)

    def provider_forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("planner constructed a provider client")

    monkeypatch.setattr(
        "legalforecast.labeling.provider_journal.ProviderAttemptJournal.__init__",
        provider_forbidden,
    )
    proposal = load_successor_proposal(proposal_path)
    first = plan_successor_rerun_impact(
        current=current,
        proposed=proposal,
        settled_provider_rows=rows,
        current_prompt_sha256_by_candidate=prompts,
    )
    second = plan_successor_rerun_impact(
        current=current,
        proposed=load_successor_proposal(proposal_path),
        settled_provider_rows=rows,
        current_prompt_sha256_by_candidate=prompts,
    )

    assert first.json_text() == second.json_text()
    assert first.text() == second.text()
    assert first.record["first_invalidated_stage"] == "parse-documents"
    assert first.record["affected_cases"] == ["case-b"]
    assert first.record["affected_candidates"] == ["candidate-b"]
    assert first.record["affected_documents"] == ["candidate-b/document-b"]
    assert first.record["reusable_documents"] == ["candidate-a/document-a"]
    reusable_calls = first.record["reusable_logical_calls"]
    assert isinstance(reusable_calls, list)
    typed_reusable_calls = cast(list[dict[str, object]], reusable_calls)
    assert [item["candidate_id"] for item in typed_reusable_calls] == ["candidate-a"]
    assert first.record["provider_logical_call_gaps"] == [
        {"candidate_id": "candidate-b", "reason": "candidate_inputs_changed"}
    ]
    assert first.record["advisory"] is True
    assert first.record["authority"] == {
        "artifact": False,
        "dispatch": False,
        "execution": False,
        "freeze": False,
        "provider": False,
        "publication": False,
        "purchase": False,
    }
    assert first.text().startswith(ADVISORY_WARNING)
    assert _tree_bytes(tmp_path) == before


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("source", "proposed document bytes differ"),
        ("selection", "proposed selection bytes differ"),
        ("proposal", "successor proposal must use canonical JSON"),
    ],
)
def test_proposed_evidence_tamper_fails_closed_deterministically(
    tmp_path: Path, mutation: str, message: str
) -> None:
    _current, proposal_path, _prompts, _rows = _fixture(
        tmp_path, replace_document=False
    )
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    if mutation == "source":
        downloads = _jsonl(Path(proposal["download_manifest_path"]))
        Path(downloads[0]["local_path"]).write_bytes(b"tampered")
    elif mutation == "selection":
        Path(proposal["selection_path"]).write_bytes(b"{}\n")
    else:
        proposal_path.write_text(
            json.dumps(proposal, indent=2, sort_keys=True), encoding="utf-8"
        )

    diagnostics: list[str] = []
    for _ in range(2):
        with pytest.raises(SuccessorRerunImpactError) as raised:
            load_successor_proposal(proposal_path)
        diagnostics.append(str(raised.value))
    assert diagnostics == [diagnostics[0], diagnostics[0]]
    assert message in diagnostics[0]


def test_ambiguous_or_failed_provider_evidence_is_not_reusable(
    tmp_path: Path,
) -> None:
    current, proposal_path, prompts, rows = _fixture(tmp_path, replace_document=False)
    duplicate = [*rows, dict(rows[0])]
    with pytest.raises(
        SuccessorRerunImpactError, match="settled call is ambiguous: candidate-a"
    ):
        plan_successor_rerun_impact(
            current=current,
            proposed=load_successor_proposal(proposal_path),
            settled_provider_rows=duplicate,
            current_prompt_sha256_by_candidate=prompts,
        )

    failed = [dict(row, status="reconstruction_failed") for row in rows]
    report = plan_successor_rerun_impact(
        current=current,
        proposed=load_successor_proposal(proposal_path),
        settled_provider_rows=failed,
        current_prompt_sha256_by_candidate=prompts,
    )
    assert report.record["reusable_logical_calls"] == []
    assert report.record["provider_logical_call_gaps"] == [
        {"candidate_id": "candidate-a", "reason": "settled_exact_identity_missing"},
        {"candidate_id": "candidate-b", "reason": "settled_exact_identity_missing"},
    ]


def test_parser_projection_rejects_failed_or_ambiguous_revision() -> None:
    records = _parser_records()
    records[0]["status"] = "failed"
    with pytest.raises(SuccessorRerunImpactError, match="non-successful"):
        current_documents_from_parser_records(records)
    records = _parser_records()
    records[1]["parser_config"] = {"parser_revision": "different"}
    with pytest.raises(SuccessorRerunImpactError, match="ambiguous"):
        parser_revision_from_records(records)


def test_invalid_prerequisite_blocks_every_descendant_deterministically() -> None:
    report = failed_successor_rerun_impact("active lineage is ambiguous")

    assert report.record["first_invalidated_stage"] == "lineage"
    assert report.record["stages"] == [
        {
            "stage": "lineage",
            "status": "FAILED",
            "diagnostics": [
                {
                    "code": "EVIDENCE_INVALID",
                    "message": "active lineage is ambiguous",
                }
            ],
        },
        {
            "stage": "selection",
            "status": "NOT_EVALUATED",
            "blocked_by": ["lineage"],
        },
        {
            "stage": "parse-documents",
            "status": "NOT_EVALUATED",
            "blocked_by": ["lineage"],
        },
        {
            "stage": "llm-unitize",
            "status": "NOT_EVALUATED",
            "blocked_by": ["lineage"],
        },
    ]
    assert report.json_text() == report.json_text()


def test_cli_missing_lineage_is_stable_json_and_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "acquisition",
        "explain-successor-rerun",
        "--index",
        str(tmp_path / "missing-index.json"),
        "--cycle-id",
        "cycle-1",
        "--llm-unitize-run-card",
        str(tmp_path / "missing-card.json"),
        "--proposed-inputs",
        str(tmp_path / "missing-proposal.json"),
        "--format",
        "json",
    ]

    assert main(argv) == 1
    first = capsys.readouterr().out
    assert main(argv) == 1
    second = capsys.readouterr().out
    assert first == second
    record = json.loads(first)
    assert [node["status"] for node in record["stages"]] == [
        "FAILED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]


def _fixture(
    tmp_path: Path, *, replace_document: bool
) -> tuple[RerunInputs, Path, dict[str, str], list[dict[str, object]]]:
    parser_records = _parser_records()
    selection_records: list[dict[str, Any]] = [
        {"candidate_id": "candidate-a", "case_id": "case-a"},
        {"candidate_id": "candidate-b", "case_id": "case-b"},
    ]
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    document_payloads = {
        "document-a": b"source-a",
        "document-b": b"replacement-b" if replace_document else b"source-b",
    }
    downloads: list[dict[str, object]] = []
    for index, (document_id, payload) in enumerate(document_payloads.items()):
        path = documents_dir / f"{document_id}.pdf"
        path.write_bytes(payload)
        downloads.append(
            {
                "candidate_id": f"candidate-{'a' if index == 0 else 'b'}",
                "source_document_id": document_id,
                "local_path": str(path),
                "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "byte_count": len(payload),
            }
        )
    selection_path = tmp_path / "selection.jsonl"
    download_path = tmp_path / "downloads.jsonl"
    selection_path.write_bytes(_jsonl_bytes(selection_records))
    download_path.write_bytes(_jsonl_bytes(downloads))
    registry_path = tmp_path / "registry.json"
    policy_path = tmp_path / "policy.json"
    registry_path.write_bytes(b'{"models":[]}')
    policy_path.write_bytes(b'{"policy":"frozen"}')
    proposal_record = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "cycle_id": "cycle-1",
        "selection_path": str(selection_path),
        "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        "download_manifest_path": str(download_path),
        "download_manifest_sha256": hashlib.sha256(
            download_path.read_bytes()
        ).hexdigest(),
        "parser_revision": "revision-1",
        "provider_attempt_namespace": "claim-ontology-v4",
        "model_registry_path": str(registry_path),
        "model_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "model_key": "openai:unitizer",
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "successor_output_root": str(tmp_path / "successor"),
        "next_commands": [
            {
                "stage": "plan-parse-documents",
                "argv": [
                    "uv",
                    "run",
                    "legalforecast",
                    "acquisition",
                    "plan-parse-documents",
                    "--selection",
                    str(selection_path),
                ],
                "execution_authority": False,
                "requires_separate_authorization": False,
            },
            {
                "stage": "parse-documents",
                "argv": [
                    "uv",
                    "run",
                    "legalforecast",
                    "acquisition",
                    "parse-documents",
                    "--reuse-live-mistral-run-card",
                    "/authenticated/parse-card.json",
                ],
                "execution_authority": False,
                "requires_separate_authorization": False,
            },
            {
                "stage": "llm-unitize",
                "argv": [
                    "uv",
                    "run",
                    "legalforecast",
                    "acquisition",
                    "llm-unitize",
                    "--selection",
                    str(selection_path),
                ],
                "execution_authority": False,
                "requires_separate_authorization": True,
            },
        ],
        "non_authoritative": True,
    }
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(proposal_record))
    current = RerunInputs(
        cycle_id="cycle-1",
        selection_records=tuple(selection_records),
        documents=current_documents_from_parser_records(parser_records),
        parser_revision=parser_revision_from_records(parser_records),
        provider_attempt_namespace="claim-ontology-v4",
        model_key="openai:unitizer",
        model_registry_sha256=hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        policy_sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        parser_output_sha256_by_document=parser_output_sha256_from_records(
            parser_records
        ),
    )
    prompts = {
        candidate: "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
        for candidate, prompt in {
            "candidate-a": "prompt-a",
            "candidate-b": "prompt-b",
        }.items()
    }
    rows = [
        _settled_row(current, candidate_id=candidate, prompt=prompt)
        for candidate, prompt in (
            ("candidate-a", "prompt-a"),
            ("candidate-b", "prompt-b"),
        )
    ]
    return current, proposal_path, prompts, rows


def _parser_records() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "candidate-a",
            "source_document_id": "document-a",
            "status": "succeeded",
            "source_sha256": hashlib.sha256(b"source-a").hexdigest(),
            "source_byte_count": len(b"source-a"),
            "parser_config": {"parser_revision": "revision-1"},
            "extracted_text": {
                "text_sha256": hashlib.sha256(b"markdown-a").hexdigest()
            },
        },
        {
            "candidate_id": "candidate-b",
            "source_document_id": "document-b",
            "status": "succeeded",
            "source_sha256": hashlib.sha256(b"source-b").hexdigest(),
            "source_byte_count": len(b"source-b"),
            "parser_config": {"parser_revision": "revision-1"},
            "extracted_text": {
                "text_sha256": hashlib.sha256(b"markdown-b").hexdigest()
            },
        },
    ]


def _settled_row(
    current: RerunInputs, *, candidate_id: str, prompt: str
) -> dict[str, object]:
    identity = ProviderCallIdentity(
        stage="llm-unitize",
        candidate_id=candidate_id,
        model_key=current.model_key,
        prompt=prompt,
        model_registry_sha256=current.model_registry_sha256,
        prompt_contract=current.provider_attempt_namespace,
    )
    return {
        "candidate_id": candidate_id,
        "status": "settled",
        "prompt_text": prompt,
        "logical_call_key": identity.logical_call_key,
        "model_key": current.model_key,
        "model_registry_sha256": current.model_registry_sha256,
    }


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
