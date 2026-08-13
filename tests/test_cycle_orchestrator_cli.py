from __future__ import annotations

import fcntl
import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast
from urllib.request import Request

import legalforecast.ingestion.cycle_orchestrator as cycle_orchestrator_module
import legalforecast.ingestion.disclosure_model_review_authority as authority_module
import pytest
from legalforecast import cli
from legalforecast.cli import main
from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.ingestion.cycle_orchestrator import (
    COMMAND_BOUNDARIES,
    BoundaryPermissions,
    CycleOrchestratorError,
    CycleStage,
    _completion_card_view,  # pyright: ignore[reportPrivateUsage]
    _cycle_lock,  # pyright: ignore[reportPrivateUsage]
    _parse_stage,  # pyright: ignore[reportPrivateUsage]
    _verify_external_disclosure_review_completion,  # pyright: ignore[reportPrivateUsage]
    run_acquisition_cycle,
)
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.provenance_clearance import exception_review_worksheet_v3
from reportlab.pdfgen.canvas import Canvas

TARGET_CASE_COUNT = 100
ROOT = Path(__file__).resolve().parents[1]


class _CompletionFactory(Protocol):
    def __call__(
        self,
        root: Path,
        *,
        run_card: Path,
    ) -> tuple[list[str], tuple[Path, ...]]: ...


def _accept_external_stage(_stage: object, _run_card: object) -> None:
    """Isolate coordinator behavior; production CLI supplies semantic replay."""


def _write_config(
    path: Path,
    *,
    stages: list[dict[str, object]],
) -> Path:
    payload: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_cycle_config.v1",
        "cycle_id": "cycle-next",
        "eligibility_anchor": "2026-06-30",
        "target_case_count": TARGET_CASE_COUNT,
        "stages": stages,
    }
    path.write_bytes(canonical_json_bytes(payload))
    return path


def _stage(
    *,
    stage_id: str,
    command: str,
    boundary: str,
    arguments: list[str],
    run_card: Path,
    run_card_stage: str | None = None,
) -> dict[str, object]:
    return {
        "id": stage_id,
        "command": command,
        "boundary": boundary,
        "arguments": arguments,
        "run_card": str(run_card),
        "run_card_stage": run_card_stage or command,
    }


def _write_completion_card(
    path: Path,
    *,
    stage: str,
    output_paths: tuple[Path, ...] = (),
    paid_activity_executed: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": stage,
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "paid_activity_executed": paid_activity_executed,
                "output_paths": [str(output) for output in output_paths],
            }
        )
    )


def _receipt_initial_stage(
    *,
    config: Path,
    state_root: Path,
    init_run_card: Path,
) -> None:
    def execute_init(command: str, _arguments: tuple[str, ...]) -> int:
        assert command == "init-cycle"
        _write_completion_card(init_run_card, stage=command)
        return 0

    status = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=execute_init,
    )
    assert status["completed_stage_count"] == 1


def _disclosure_receipt_inputs() -> tuple[
    dict[str, object],
    bytes,
    dict[str, object],
    bytes,
    dict[tuple[str, str], bytes],
]:
    pdf_output = BytesIO()
    canvas = Canvas(pdf_output, invariant=1)
    canvas.drawString(72, 720, "medical record cited only as a public allegation")
    canvas.showPage()
    canvas.save()
    document_payload = pdf_output.getvalue()
    document: dict[str, object] = {
        "candidate_id": "case-a",
        "source_document_id": "document-1",
        "local_path": "case-a/document.pdf",
        "sha256": hashlib.sha256(document_payload).hexdigest(),
        "byte_count": len(document_payload),
        "free_or_purchased": "free",
        "source_provider": "courtlistener",
        "source_url": "https://storage.courtlistener.com/recap/a.pdf",
        "source_url_or_reference": ("https://storage.courtlistener.com/recap/a.pdf"),
        "restriction_status": "unknown",
        "restriction_evidence": sorted(
            [
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_true",
                "courtlistener_rest_recap_document_is_sealed_unknown",
                "courtlistener_rest_public_download_url_allowlisted",
            ]
        ),
        "is_sealed": None,
        "is_private": None,
        "model_visible": False,
        "contains_target_outcome": True,
        "disclosure_pdf_scan": {
            "schema_version": "legalforecast.disclosure_pdf_scan.v1",
            "method": "pypdf_page_text_v1",
            "parsed_page_count": 1,
            "text_scanned_page_numbers": [1],
            "text_scanned_page_count": 1,
            "ocr_scanned_page_numbers": [],
            "ocr_scanned_page_count": 0,
            "unscanned_page_numbers": [],
            "coverage_status": "complete",
            "diagnostics": [],
            "automated_markers": ["medical"],
        },
        "automated_markers": ["medical"],
        "route": "exception_review",
        "route_reasons": ["automated_marker_present"],
        "exception_clearance_permitted": True,
    }
    documents = [document]
    plan: dict[str, object] = {
        "schema_version": "legalforecast.disclosure_provenance_routing_plan.v3",
        "source_sha256": {
            "review_requests": "a" * 64,
            "download_manifest": "b" * 64,
            "restriction_evidence": "c" * 64,
            "case_relevance": "d" * 64,
        },
        "document_set_sha256": hashlib.sha256(
            canonical_json_bytes(documents)
        ).hexdigest(),
        "document_count": 1,
        "auto_clear_count": 0,
        "exception_review_count": 1,
        "documents": documents,
    }
    worksheet = exception_review_worksheet_v3(plan)
    return (
        plan,
        canonical_json_bytes(plan),
        worksheet,
        canonical_json_bytes(worksheet),
        {("case-a", "document-1"): document_payload},
    )


def _disclosure_provider_payload(document_sha256: str) -> dict[str, object]:
    response = {
        "schema_version": "legalforecast.disclosure_model_review_response.v1",
        "candidate_id": "case-a",
        "source_document_id": "document-1",
        "document_sha256": document_sha256,
        "model_id": "gemini-3.5-flash",
        "model_version": "gemini-3.5-flash",
        "decision": "cleared",
        "sensitive_content": "absent",
        "supporting_page_number": None,
        "supporting_excerpt": None,
    }
    semantic = {
        "schema_version": "legalforecast.disclosure_model_review_batch_response.v1",
        "model_id": "gemini-3.5-flash",
        "model_version": "gemini-3.5-flash",
        "document_count": 1,
        "items": [response],
    }
    raw_output = json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n"
    return {
        "modelVersion": "models/gemini-3.5-flash",
        "candidates": [{"content": {"parts": [{"text": raw_output}]}}],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
    }


def _adoptable_disclosure_review_completion(
    root: Path,
    *,
    run_card: Path,
) -> tuple[
    list[str],
    tuple[Path, ...],
    tuple[Path, Path],
    dict[str, object],
]:
    output_root = root / "review"
    private_root = root / "private"
    frozen_root = ROOT
    document_root = root / "documents"
    routing_plan = root / "inputs" / "routing-plan.json"
    worksheet = root / "inputs" / "worksheet.json"
    plan_run_card = root / "inputs" / "plan-run-card.json"
    authority = output_root / "disclosure-model-review-authority.json"
    private_records = private_root / "disclosure-model-review-private-records.json"
    journal = private_root / "provider-attempts.sqlite3"
    spend_authority = private_root / "provider-spend-authority.sqlite3"

    plan, plan_bytes, worksheet_record, worksheet_bytes, document_bytes = (
        _disclosure_receipt_inputs()
    )
    document = cast(list[dict[str, object]], plan["documents"])[0]
    document_payload = document_bytes[("case-a", "document-1")]
    routing_plan.parent.mkdir(parents=True)
    routing_plan.write_bytes(plan_bytes)
    worksheet.write_bytes(worksheet_bytes)
    document_path = document_root / cast(str, document["local_path"])
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(document_payload)
    document_tree = {
        cast(str, document["local_path"]): cli._bytes_sha256(document_payload)
    }
    plan_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "plan-disclosure-provenance",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "output_paths": [str(routing_plan.resolve()), str(worksheet.resolve())],
        "source_commitments": {
            "document_root": {
                "path": str(document_root.resolve()),
                "tree_sha256": cli._canonical_json_sha256(document_tree),
                "document_count": 1,
            }
        },
        "output_commitments": {
            "routing_plan": {
                "path": str(routing_plan.resolve()),
                "sha256": cli._bytes_sha256(plan_bytes),
            },
            "exception_worksheet": {
                "path": str(worksheet.resolve()),
                "sha256": cli._bytes_sha256(worksheet_bytes),
            },
        },
    }
    plan_run_card.write_text(
        json.dumps(plan_card, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    payload = _disclosure_provider_payload(cast(str, document["sha256"]))

    def transport(_request: Request, _timeout: float) -> dict[str, object]:
        return payload

    first = authority_module.authenticate_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet_record,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=document_bytes,
        provider_journal_path=journal,
        provider_spend_authority_path=spend_authority,
        source_root=frozen_root,
        transport=transport,
        environ={"GEMINI_API_KEY": "test-only"},
        retry_backoff_seconds=0.0,
    )
    assert authority_module.disclosure_model_review_provider_call_executed(first)
    replayed = authority_module.replay_authenticated_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet_record,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=document_bytes,
        provider_journal_path=journal,
        provider_spend_authority_path=spend_authority,
        source_root=frozen_root,
    )
    assert not authority_module.disclosure_model_review_provider_call_executed(replayed)
    authority_record = authority_module.public_disclosure_model_review_record(replayed)
    private_record_values = authority_module.private_disclosure_model_review_records(
        replayed
    )
    [private_record] = private_record_values
    authority.parent.mkdir(parents=True, exist_ok=True)
    private_records.parent.mkdir(parents=True, exist_ok=True)
    authority.write_bytes(canonical_json_bytes(authority_record))
    private_records.write_bytes(canonical_json_bytes([private_record]))

    def file_commitment(path: Path) -> dict[str, str]:
        return {
            "path": str(path.resolve()),
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    card = {
        "schema_version": "legalforecast.disclosure_model_review_run_card.v1",
        "stage": "review-disclosure-exceptions",
        "status": "completed",
        "resume": True,
        "dry_run": False,
        "execute": True,
        "provider_activity_requested": True,
        "provider_activity_executed": True,
        "provider_call_executed_this_run": False,
        "paid_activity_requested": True,
        "paid_activity_executed": True,
        "record_count": 1,
        "source_commitments": {
            "routing_plan": file_commitment(routing_plan),
            "exception_worksheet": file_commitment(worksheet),
            "plan_run_card": file_commitment(plan_run_card),
            "document_root": {
                "path": str(document_root.resolve()),
                "tree_sha256": cli._canonical_json_sha256(document_tree),
                "document_count": 1,
            },
        },
        "state_paths": {
            "provider_journal": str(journal.resolve()),
            "provider_spend_authority": str(spend_authority.resolve()),
            "frozen_authority_root": str(frozen_root.resolve()),
        },
        "model_review_authority": authority_record,
        "output_commitments": {
            "public_authority": file_commitment(authority),
            "private_records": file_commitment(private_records),
        },
    }
    run_card.parent.mkdir(parents=True, exist_ok=True)
    run_card.write_bytes(canonical_json_bytes(card))
    arguments = [
        "--output-root",
        str(output_root),
        "--routing-plan",
        str(routing_plan),
        "--exception-worksheet",
        str(worksheet),
        "--plan-run-card",
        str(plan_run_card),
        "--document-root",
        str(document_root),
        "--frozen-authority-root",
        str(frozen_root),
        "--provider-journal",
        str(journal),
        "--provider-spend-authority",
        str(spend_authority),
        "--controlled-private-store-root",
        str(private_root),
        "--authority-output",
        str(authority),
        "--private-records-output",
        str(private_records),
        "--run-card-output",
        str(run_card),
        "--execute",
        "--resume",
    ]
    fixture = {
        "document": document,
        "document_payload": document_payload,
        "authority": authority_record,
        "private_record": private_record,
    }
    return arguments, (authority, private_records), (journal, spend_authority), fixture


def _adoptable_unitization_completion(
    root: Path,
    *,
    run_card: Path,
) -> tuple[list[str], tuple[Path, ...]]:
    output_root = root / "unitize"
    file_inputs = {
        "--selection": ("selection", root / "inputs" / "selection.jsonl"),
        "--selection-run-card": (
            "selection_run_card",
            root / "inputs" / "selection-run-card.json",
        ),
        "--download-manifest": (
            "download_manifest",
            root / "inputs" / "download-manifest.jsonl",
        ),
        "--disclosure-clearance": (
            "disclosure_clearance",
            root / "inputs" / "disclosure-clearance.jsonl",
        ),
        "--materialization-run-card": (
            "materialization_run_card",
            root / "inputs" / "materialization-run-card.json",
        ),
        "--parse-requests": (
            "parse_requests",
            root / "inputs" / "parse-requests.jsonl",
        ),
        "--parser-manifest": (
            "parser_manifest",
            root / "inputs" / "parser-manifest.jsonl",
        ),
        "--parser-run-card": (
            "parser_run_card",
            root / "inputs" / "parser-run-card.json",
        ),
        "--model-registry": (
            "model_registry",
            root / "inputs" / "model-registry.json",
        ),
        "--provider-cycle-caps": (
            "provider_cycle_caps",
            root / "inputs" / "provider-cycle-caps.json",
        ),
    }
    document_root = root / "inputs" / "documents"
    markdown_root = root / "inputs" / "markdown"
    document_root.mkdir(parents=True)
    markdown_root.mkdir(parents=True)
    document_path = document_root / "document.pdf"
    markdown_path = markdown_root / "document.md"
    document_path.write_bytes(b"document\n")
    markdown_path.write_text("markdown\n", encoding="utf-8")
    input_commitments: dict[str, object] = {}
    arguments = [
        "--output-root",
        str(output_root),
        "--model-key",
        "openai:test",
    ]
    input_paths: list[Path] = []
    for flag, (name, path) in file_inputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{name}\n", encoding="utf-8")
        arguments.extend([flag, str(path)])
        input_paths.append(path)
        input_commitments[name] = {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    for flag, path in (
        ("--document-root", document_root),
        ("--markdown-root", markdown_root),
    ):
        arguments.extend([flag, str(path)])
        input_paths.append(path)

    outputs = (
        output_root / "prediction-units.jsonl",
        output_root / "llm-unitization-audit.jsonl",
        output_root / "unitization-review-queue.jsonl",
        output_root / "provider-attempts.sqlite3",
    )
    for index, path in enumerate(outputs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"output-{index}\n", encoding="utf-8")
    arguments.extend(["--provider-journal", str(outputs[-1])])
    input_paths.append(outputs[-1])
    arguments.extend(["--run-card-output", str(run_card), "--execute"])
    output_commitments = {
        name: {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for name, path in zip(
            (
                "prediction_units",
                "llm_unitization_audit",
                "unitization_review_queue",
            ),
            outputs[:3],
            strict=True,
        )
    }
    input_commitments.update(
        {
            "document_tree": {
                document_path.name: hashlib.sha256(
                    document_path.read_bytes()
                ).hexdigest()
            },
            "markdown_tree": {
                markdown_path.name: {
                    "path": str(markdown_path.resolve()),
                    "sha256": hashlib.sha256(markdown_path.read_bytes()).hexdigest(),
                    "byte_count": len(markdown_path.read_bytes()),
                }
            },
        }
    )
    run_card.parent.mkdir(parents=True, exist_ok=True)
    run_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "llm-unitize",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "record_count": 1,
                "input_paths": [str(path) for path in input_paths],
                "output_paths": [str(path) for path in outputs],
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "generated_at": "2026-07-28T00:00:00Z",
                "lineage_schema_version": (
                    "legalforecast.stage_a_unitization_lineage.v1"
                ),
                "lineage_complete": True,
                "cohort_cycle_id": "cycle-next",
                "lineage_roots": {
                    "document_root": str(document_root),
                    "markdown_root": str(markdown_root),
                    "provider_journal": str(outputs[-1]),
                },
                "input_commitments": input_commitments,
                "model_execution": {
                    "model_key": "openai:test",
                    "provider_attempts_sha256": "2" * 64,
                },
                "prompt_commitments": {"candidate-1": {"prompt_sha256": "3" * 64}},
                "output_commitments": output_commitments,
            }
        )
    )
    return arguments, outputs


def _write_input(path: Path, label: str) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{label}\n", encoding="utf-8")
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _adoptable_parse_completion(
    root: Path,
    *,
    run_card: Path,
) -> tuple[list[str], tuple[Path, ...]]:
    output_root = root / "parse"
    selection = root / "parse-inputs" / "selection.jsonl"
    requests = root / "parse-inputs" / "requests.jsonl"
    clearance = root / "parse-inputs" / "clearance.jsonl"
    materialization_card = root / "parse-inputs" / "materialization-run-card.json"
    resolved = root / "parse-inputs" / "resolved.jsonl"
    parser_root = root / "mistral-parser"
    parser_root.mkdir()
    sources = {
        "selection": _write_input(selection, "selection"),
        "requests": _write_input(requests, "requests"),
        "disclosure_clearance": _write_input(clearance, "clearance"),
        "materialization_run_card": _write_input(
            materialization_card, "materialization"
        ),
        "resolved_post_recovery_documents": _write_input(resolved, "resolved"),
    }
    manifest = output_root / "mistral-markdown-conversions.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"x":1}\n', encoding="utf-8")
    output_commitment = {
        "path": str(manifest.resolve()),
        "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }
    arguments = [
        "--output-root",
        str(output_root),
        "--selection",
        str(selection),
        "--requests",
        str(requests),
        "--disclosure-clearance",
        str(clearance),
        "--materialization-run-card",
        str(materialization_card),
        "--resolved-post-recovery-documents",
        str(resolved),
        "--parser-root",
        str(parser_root),
        "--manifest-output",
        str(manifest),
        "--run-card-output",
        str(run_card),
        "--execute",
    ]
    run_card.parent.mkdir(parents=True, exist_ok=True)
    run_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "parse-documents",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "record_count": 1,
                "input_paths": [
                    str(selection),
                    str(requests),
                    str(clearance),
                    str(materialization_card),
                    str(resolved),
                ],
                "output_paths": [str(manifest)],
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "generated_at": "2026-07-28T00:00:00Z",
                "source_commitments": sources,
                "output_commitments": {"parser_manifest": output_commitment},
                "parser_execution": {
                    "mode": "live_mistral",
                    "engine": "mistral",
                    "parser_revision": EXPECTED_PARSER_REVISION,
                    "parser_root": str(parser_root.resolve()),
                    "fixture_markdown": False,
                },
            }
        )
    )
    return arguments, (manifest,)


def _adoptable_review_completion(
    root: Path,
    *,
    run_card: Path,
) -> tuple[list[str], tuple[Path, ...]]:
    output_root = root / "review"
    source_flags = (
        ("selection", "--selection"),
        ("parser_manifest", "--parser-manifest"),
        ("raw_prediction_units", "--prediction-units"),
        ("llm_unitization_run_card", "--llm-unitization-run-card"),
        ("unitization_review_queue", "--unitization-review-queue"),
        ("model_registry", "--model-registry"),
        ("provider_cycle_caps", "--provider-cycle-caps"),
    )
    arguments = [
        "--output-root",
        str(output_root),
        "--model-key",
        "google:test",
    ]
    sources: dict[str, object] = {}
    inputs: list[Path] = []
    for name, flag in source_flags:
        path = root / "review-inputs" / f"{name}.json"
        sources[name] = _write_input(path, name)
        inputs.append(path)
        arguments.extend([flag, str(path)])
    unitization_path = root / "review-inputs" / "llm_unitization_run_card.json"
    unitization_path.write_bytes(
        canonical_json_bytes(
            {"lineage_roots": {"markdown_root": str((root / "markdown").resolve())}}
        )
    )
    sources["llm_unitization_run_card"] = {
        "path": str(unitization_path.resolve()),
        "sha256": hashlib.sha256(unitization_path.read_bytes()).hexdigest(),
    }
    markdown_root = root / "markdown"
    markdown_root.mkdir()
    arguments.extend(["--markdown-root", str(markdown_root)])
    journal = root / "review-inputs" / "provider-attempts.sqlite3"
    _write_input(journal, "journal")
    inputs.append(journal)
    arguments.extend(["--provider-journal", str(journal)])
    outputs = (
        output_root / "stage-a-structural-flags.jsonl",
        output_root / "unitization-review-queue-reviewed.jsonl",
        output_root / "stage-a-structural-review-audit.jsonl",
        journal,
    )
    output_names = ("structural_flags", "review_queue", "audit")
    output_commitments = {
        name: _write_input(path, name)
        for name, path in zip(output_names, outputs[:3], strict=True)
    }
    arguments.extend(["--run-card-output", str(run_card), "--execute"])
    run_card.parent.mkdir(parents=True, exist_ok=True)
    run_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "llm-review-stage-a",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "record_count": 1,
                "input_paths": [str(path) for path in inputs],
                "output_paths": [str(path) for path in outputs],
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "generated_at": "2026-07-28T00:00:00Z",
                "source_commitments": sources,
                "output_commitments": output_commitments,
                "provider_chain": {"provider_journal": str(journal.resolve())},
                "model_execution": {"model_key": "google:test"},
            }
        )
    )
    return arguments, outputs


def _adoptable_label_completion(
    root: Path,
    *,
    run_card: Path,
) -> tuple[list[str], tuple[Path, ...]]:
    output_root = root / "label"
    source_flags = (
        ("selection", "--selection"),
        ("parser_manifest", "--parser-manifest"),
        ("decision_texts", "--decision-texts"),
        ("decision_texts_manifest", "--decision-texts-manifest"),
        ("decision_texts_run_card", "--decision-texts-run-card"),
        ("finalized_prediction_units", "--prediction-units"),
        ("llm_unitization_run_card", "--llm-unitization-run-card"),
        ("unitization_review_run_card", "--unitization-review-run-card"),
        ("llm_review_stage_a_run_card", "--llm-review-stage-a-run-card"),
        ("model_registry", "--model-registry"),
        ("evaluated_model_registry", "--evaluated-model-registry"),
        ("provider_cycle_caps", "--provider-cycle-caps"),
    )
    arguments = ["--output-root", str(output_root)]
    sources: dict[str, object] = {}
    inputs: list[Path] = []
    for name, flag in source_flags:
        path = root / "label-inputs" / f"{name}.json"
        sources[name] = _write_input(path, name)
        inputs.append(path)
        arguments.extend([flag, str(path)])
    unitization_path = root / "label-inputs" / "llm_unitization_run_card.json"
    markdown_root = root / "label-markdown"
    markdown_root.mkdir()
    unitization_path.write_bytes(
        canonical_json_bytes(
            {"lineage_roots": {"markdown_root": str(markdown_root.resolve())}}
        )
    )
    sources["llm_unitization_run_card"] = {
        "path": str(unitization_path.resolve()),
        "sha256": hashlib.sha256(unitization_path.read_bytes()).hexdigest(),
    }
    arguments.extend(["--markdown-root", str(markdown_root)])
    for model_key in ("openai:test", "google:test"):
        arguments.extend(["--model-key", model_key])
    journal = root / "label-inputs" / "provider-attempts.sqlite3"
    _write_input(journal, "journal")
    inputs.append(journal)
    arguments.extend(["--provider-journal", str(journal)])
    shard_cards: list[dict[str, str]] = []
    for provider in ("openai", "google"):
        audit_path = root / "label-inputs" / f"{provider}-audit.jsonl"
        audit_commitment = _write_input(audit_path, f"{provider}-audit")
        path = root / "label-inputs" / f"{provider}-run-card.json"
        path.write_bytes(
            canonical_json_bytes({"output_commitments": {"audit": audit_commitment}})
        )
        shard_cards.append(
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        inputs.extend([audit_path, path])
        arguments.extend(["--provider-shard-audit", str(audit_path)])
        arguments.extend(["--provider-shard-run-card", str(path)])
    outputs = (
        output_root / "labels.jsonl",
        output_root / "llm-label-audit.jsonl",
        output_root / "lawyer-review-queue.jsonl",
        journal,
    )
    output_names = ("labels", "audit", "lawyer_review_queue")
    output_commitments = {
        name: _write_input(path, name)
        for name, path in zip(output_names, outputs[:3], strict=True)
    }
    arguments.extend(["--run-card-output", str(run_card), "--execute"])
    run_card.parent.mkdir(parents=True, exist_ok=True)
    run_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "llm-label",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "record_count": 1,
                "input_paths": [str(path) for path in inputs],
                "output_paths": [str(path) for path in outputs],
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "generated_at": "2026-07-28T00:00:00Z",
                "source_commitments": sources,
                "output_commitments": output_commitments,
                "provider_chain": {"provider_journal": str(journal.resolve())},
                "model_execution": {
                    "model_keys": ["openai:test", "google:test"],
                    "execution_provider": None,
                    "provider_shard_merge": True,
                },
                "provider_shard_run_cards": shard_cards,
                "stage_a_lineage": {"complete": True},
                "decision_text_commitments": {"complete": True},
            }
        )
    )
    return arguments, outputs


def test_external_completed_cycle_stage_replays_provider_shard_run_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_card_path = tmp_path / "label" / "run-card.json"
    arguments, outputs = _adoptable_label_completion(
        tmp_path,
        run_card=run_card_path,
    )
    while "--provider-shard-audit" in arguments:
        index = arguments.index("--provider-shard-audit")
        del arguments[index : index + 2]
    while "--provider-shard-run-card" in arguments:
        index = arguments.index("--provider-shard-run-card")
        del arguments[index : index + 2]
    arguments.extend(
        ["--local-provider-journal-only", "--execution-provider", "google"]
    )
    stage = _parse_stage(
        _stage(
            stage_id="google-label-shard",
            command="llm-label",
            boundary="model_provider",
            arguments=arguments,
            run_card=run_card_path,
            run_card_stage="llm-label-provider-shard",
        ),
        index=0,
    )

    labels_path, audit_path, lawyer_queue_path, provider_journal_path = outputs
    labels_path.write_text("", encoding="utf-8")
    lawyer_queue_path.write_text("", encoding="utf-8")
    audit_path.write_text(
        json.dumps(
            {
                "candidate_id": "candidate-1",
                "execution_provider": "google",
                "model_outputs": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    entries = (
        SimpleNamespace(registry_key="openai:test", provider="openai"),
        SimpleNamespace(registry_key="google:test", provider="google"),
    )
    entry_sha256 = {
        entry.registry_key: hashlib.sha256(entry.registry_key.encode()).hexdigest()
        for entry in entries
    }
    stage_attempts = {
        "stage": "llm-label",
        "call_count": 0,
        "attempt_count": 0,
        "attempts_sha256": hashlib.sha256(b"").hexdigest(),
    }
    lineage = cast(
        cli._StageAUnitizationLineage,  # pyright: ignore[reportPrivateUsage]
        SimpleNamespace(
            provider_journal_path=provider_journal_path,
            cohort_cycle_id="cycle-next",
            provider_caps_sha256="sha256:caps",
        ),
    )
    card = json.loads(run_card_path.read_bytes())
    card["source_commitments"] = {
        name: cli._stage_a_file_commitment(Path(commitment["path"]))
        for name, commitment in card["source_commitments"].items()
    }
    card.update(
        {
            "stage": "llm-label-provider-shard",
            "paid_activity_requested": True,
            "paid_activity_executed": True,
            "output_commitments": {
                "labels": cli._stage_a_file_commitment(labels_path),
                "audit": cli._stage_a_file_commitment(audit_path),
                "lawyer_review_queue": cli._stage_a_file_commitment(lawyer_queue_path),
            },
            "model_execution": {
                "model_keys": [entry.registry_key for entry in entries],
                "executed_model_keys": ["google:test"],
                "model_entry_sha256": {
                    key: "sha256:" + value for key, value in entry_sha256.items()
                },
                "model_registry_sha256": "registry-sha",
                "providers": {entry.registry_key: entry.provider for entry in entries},
                "execution_provider": "google",
                "provider_shard_merge": False,
            },
            "provider_chain": cli._provider_chain_commitment(
                lineage=lineage,
                stage_attempts=stage_attempts,
            ),
        }
    )
    card.pop("provider_shard_run_cards")
    run_card_path.write_bytes(canonical_json_bytes(card))

    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_run_card",
        lambda *_args, **_kwargs: lineage,
    )
    monkeypatch.setattr(
        cli,
        "_registry_entries_for_keys",
        lambda *_args, **_kwargs: (entries, "registry-sha"),
    )
    monkeypatch.setattr(
        cli,
        "_require_complete_registry_panel",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "model_registry_entry_sha256",
        lambda entry: entry_sha256[entry.registry_key],
    )
    monkeypatch.setattr(
        cli,
        "_verified_provider_stage_attempts",
        lambda *_args, **_kwargs: stage_attempts,
    )

    cli._verify_external_completed_cycle_stage(stage, card)

    audit_path.unlink()
    with pytest.raises(CycleOrchestratorError, match="semantic replay failed"):
        cli._verify_external_completed_cycle_stage(stage, card)


def test_external_completed_disclosure_review_replays_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_path = tmp_path / "plan.json"
    worksheet_path = tmp_path / "worksheet.json"
    document_root = tmp_path / "documents"
    auto_document_path = document_root / "case-a" / "auto.pdf"
    document_path = document_root / "case-a" / "document.pdf"
    authority_path = tmp_path / "authority.json"
    private_path = tmp_path / "private.json"
    journal_path = tmp_path / "journal.sqlite3"
    spend_path = tmp_path / "spend.sqlite3"
    plan_run_card_path = tmp_path / "plan-run-card.json"
    run_card_path = tmp_path / "run-card.json"
    auto_document = {
        "candidate_id": "case-a",
        "source_document_id": "auto-1",
        "local_path": "case-a/auto.pdf",
    }
    document = {
        "candidate_id": "case-a",
        "source_document_id": "document-1",
        "local_path": "case-a/document.pdf",
    }
    document_path.parent.mkdir(parents=True)
    plan_path.write_bytes(
        canonical_json_bytes({"documents": [auto_document, document]})
    )
    worksheet_path.write_bytes(canonical_json_bytes({"documents": [document]}))
    auto_document_path.write_bytes(b"auto-clear document")
    document_path.write_bytes(b"reviewed document")
    journal_path.write_bytes(b"journal")
    spend_path.write_bytes(b"spend")
    authority = {"decision_count": 1}
    private = ({"private": "evidence"},)
    authority_path.write_bytes(canonical_json_bytes(authority))
    private_path.write_bytes(canonical_json_bytes(list(private)))
    stage = _parse_stage(
        _stage(
            stage_id="review-disclosure",
            command="review-disclosure-exceptions",
            boundary="model_provider",
            arguments=[
                "--output-root",
                str(tmp_path),
                "--routing-plan",
                str(plan_path),
                "--exception-worksheet",
                str(worksheet_path),
                "--plan-run-card",
                str(plan_run_card_path),
                "--document-root",
                str(document_root),
                "--authority-output",
                str(authority_path),
                "--private-records-output",
                str(private_path),
                "--provider-journal",
                str(journal_path),
                "--provider-spend-authority",
                str(spend_path),
                "--frozen-authority-root",
                str(ROOT),
                "--controlled-private-store-root",
                str(tmp_path),
                "--run-card-output",
                str(run_card_path),
                "--execute",
                "--resume",
            ],
            run_card=run_card_path,
        ),
        index=0,
    )
    document_tree = {
        "case-a/auto.pdf": cli._bytes_sha256(b"auto-clear document"),
        "case-a/document.pdf": cli._bytes_sha256(b"reviewed document"),
    }
    plan_run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "plan-disclosure-provenance",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "output_paths": [str(plan_path.resolve()), str(worksheet_path.resolve())],
        "source_commitments": {
            "document_root": {
                "path": str(document_root.resolve()),
                "tree_sha256": cli._canonical_json_sha256(document_tree),
                "document_count": len(document_tree),
            }
        },
        "output_commitments": {
            "routing_plan": {
                "path": str(plan_path.resolve()),
                "sha256": cli._bytes_sha256(plan_path.read_bytes()),
            },
            "exception_worksheet": {
                "path": str(worksheet_path.resolve()),
                "sha256": cli._bytes_sha256(worksheet_path.read_bytes()),
            },
        },
    }
    plan_run_card_path.write_text(
        json.dumps(plan_run_card, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    card = {
        "source_commitments": {
            "plan_run_card": {
                "path": str(plan_run_card_path.resolve()),
                "sha256": cli._bytes_sha256(plan_run_card_path.read_bytes()),
            },
            "document_root": {
                "path": str(document_root.resolve()),
                "tree_sha256": cli._canonical_json_sha256(document_tree),
                "document_count": len(document_tree),
            },
        },
        "record_count": 1,
        "model_review_authority": authority,
    }
    capability = object()
    mutate_during_replay = False

    def replay(**kwargs: object) -> object:
        assert kwargs["document_bytes_by_key"] == {
            ("case-a", "document-1"): b"reviewed document"
        }
        if mutate_during_replay:
            auto_document_path.write_bytes(b"mutated during replay")
        return capability

    monkeypatch.setattr(
        cli,
        "validate_exception_review_worksheet_v3",
        lambda *_args, **_kwargs: (document,),
    )
    monkeypatch.setattr(
        cli,
        "replay_authenticated_disclosure_model_review",
        replay,
    )
    monkeypatch.setattr(
        cli,
        "public_disclosure_model_review_record",
        lambda value: authority if value is capability else {},
    )
    monkeypatch.setattr(
        cli,
        "private_disclosure_model_review_records",
        lambda value: private if value is capability else (),
    )

    cli._verify_external_completed_cycle_stage(stage, card)
    changed_trees = (
        {"case-a/document.pdf": document_tree["case-a/document.pdf"]},
        {**document_tree, "case-a/extra.pdf": cli._bytes_sha256(b"extra")},
        {**document_tree, "case-a/auto.pdf": cli._bytes_sha256(b"tampered")},
    )
    for changed_tree in changed_trees:
        with pytest.raises(ValueError, match="document commitment changed"):
            cli._verify_model_review_plan_run_card(
                run_card_bytes=plan_run_card_path.read_bytes(),
                run_card_path=plan_run_card_path,
                plan_path=plan_path,
                plan_bytes=plan_path.read_bytes(),
                worksheet_path=worksheet_path,
                worksheet_bytes=worksheet_path.read_bytes(),
                document_root=document_root,
                document_tree=changed_tree,
            )

    mutate_during_replay = True
    with pytest.raises(CycleOrchestratorError, match="semantic replay failed"):
        cli._verify_external_completed_cycle_stage(stage, card)
    mutate_during_replay = False
    auto_document_path.write_bytes(b"auto-clear document")

    authority_path.write_bytes(canonical_json_bytes({"decision_count": 2}))
    with pytest.raises(CycleOrchestratorError, match="semantic replay failed"):
        cli._verify_external_completed_cycle_stage(stage, card)


def test_run_cycle_adopts_completed_disclosure_review_without_provider_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    review_card = tmp_path / "review" / "run-card.json"
    review_arguments, review_outputs, provider_state, _fixture = (
        _adoptable_disclosure_review_completion(
            tmp_path,
            run_card=review_card,
        )
    )
    for flag, output in zip(
        ("--authority-output", "--private-records-output"),
        review_outputs,
        strict=True,
    ):
        flag_index = review_arguments.index(flag)
        review_arguments[flag_index + 1] = str(
            output.parent / ".." / output.parent.name / output.name
        )
    clearance = tmp_path / "downstream" / "clearance.jsonl"
    clearance_card = tmp_path / "downstream" / "clearance-run-card.json"
    resolved = tmp_path / "downstream" / "resolved.jsonl"
    resolver_card = tmp_path / "downstream" / "resolver-run-card.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="review-disclosure",
                command="review-disclosure-exceptions",
                boundary="model_provider",
                arguments=review_arguments,
                run_card=review_card,
            ),
            _stage(
                stage_id="finalize-disclosure",
                command="finalize-provenance-quarantine",
                boundary="provider_free",
                arguments=[
                    "--model-review-authority",
                    str(review_outputs[0]),
                    "--model-review-private-records",
                    str(review_outputs[1]),
                    "--model-review-run-card",
                    str(review_card),
                    "--clearance-output",
                    str(clearance),
                    "--run-card-output",
                    str(clearance_card),
                    "--execute",
                ],
                run_card=clearance_card,
            ),
            _stage(
                stage_id="resolve-documents",
                command="resolve-post-recovery-documents",
                boundary="provider_free",
                arguments=[
                    "--disclosure-clearance",
                    str(clearance),
                    "--clearance-run-card",
                    str(clearance_card),
                    "--resolved-output",
                    str(resolved),
                    "--run-card-output",
                    str(resolver_card),
                    "--execute",
                ],
                run_card=resolver_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )
    provider_state_before = tuple(path.read_bytes() for path in provider_state)
    with sqlite3.connect(provider_state[0]) as connection:
        attempt_count_before = cast(
            int,
            connection.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0],
        )
    assert attempt_count_before == 1

    def forbidden_delegated_main(_arguments: tuple[str, ...]) -> int:
        raise AssertionError("adoption must not invoke the provider stage")

    monkeypatch.setattr("legalforecast.cli.main", forbidden_delegated_main)
    monkeypatch.setattr(
        cli,
        "authenticate_disclosure_model_review",
        lambda **_kwargs: pytest.fail("adoption must not invoke provider transport"),
    )
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(state_root),
                "--adopt-next-completed",
                "--json",
            ]
        )
        == 0
    )

    status = json.loads(capsys.readouterr().out)
    assert status["stop_reason"] == "model_provider_stage_adopted"
    assert status["next_stage"]["id"] == "finalize-disclosure"
    assert tuple(path.read_bytes() for path in provider_state) == provider_state_before
    with sqlite3.connect(provider_state[0]) as connection:
        attempt_count_after = cast(
            int,
            connection.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0],
        )
    assert attempt_count_after == attempt_count_before
    assert (
        json.loads(review_card.read_bytes())["provider_call_executed_this_run"] is False
    )
    receipt = json.loads(
        (state_root / "receipts" / "0001-review-disclosure.json").read_bytes()
    )
    assert receipt["output_commitments"] == [
        {
            "path": str(path),
            "kind": "file",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_count": len(path.read_bytes()),
        }
        for path in review_outputs
    ]

    consumed: list[str] = []

    def consume_disclosure_outputs(
        command: str,
        arguments: tuple[str, ...],
    ) -> int:
        consumed.append(command)
        if command == "finalize-provenance-quarantine":
            assert str(review_outputs[0]) in arguments
            assert str(review_outputs[1]) in arguments
            assert str(review_card) in arguments
            clearance.parent.mkdir(parents=True, exist_ok=True)
            clearance.write_text('{"status":"cleared"}\n', encoding="utf-8")
            _write_completion_card(
                clearance_card,
                stage=command,
                output_paths=(clearance,),
            )
        else:
            assert command == "resolve-post-recovery-documents"
            assert str(clearance) in arguments
            assert str(clearance_card) in arguments
            resolved.write_text('{"status":"resolved"}\n', encoding="utf-8")
            _write_completion_card(
                resolver_card,
                stage=command,
                output_paths=(resolved,),
            )
        return 0

    continuation = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=consume_disclosure_outputs,
    )
    assert continuation["status"] == "completed"
    assert consumed == [
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
    ]
    assert tuple(path.read_bytes() for path in provider_state) == provider_state_before
    with sqlite3.connect(provider_state[0]) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_attempts"
        ).fetchone() == (attempt_count_before,)
    assert (state_root / "receipts" / "0002-finalize-disclosure.json").is_file()
    assert (state_root / "receipts" / "0003-resolve-documents.json").is_file()


def test_disclosure_receipt_reuses_authenticated_output_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    review_card = tmp_path / "review" / "run-card.json"
    review_arguments, review_outputs, _provider_state, _fixture = (
        _adoptable_disclosure_review_completion(tmp_path, run_card=review_card)
    )
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="review-disclosure",
                command="review-disclosure-exceptions",
                boundary="model_provider",
                arguments=review_arguments,
                run_card=review_card,
            ),
        ],
    )
    state_root = tmp_path / "state"
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )
    original_payload = review_outputs[0].read_bytes()
    original_verifier = _verify_external_disclosure_review_completion
    call_count = 0

    def mutate_after_final_verification(
        stage: CycleStage,
        run_card: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal call_count
        call_count += 1
        verified = original_verifier(stage, run_card)
        if call_count == 2:
            review_outputs[0].write_bytes(b"changed after authentication\n")
        return verified

    monkeypatch.setattr(
        "legalforecast.ingestion.cycle_orchestrator._verify_external_disclosure_review_completion",
        mutate_after_final_verification,
    )
    result = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=False,
        adopt_next_completed=True,
        external_stage_verifier=cli._verify_external_completed_cycle_stage,
        permissions=BoundaryPermissions(),
        executor=lambda _command, _arguments: (_ for _ in ()).throw(
            AssertionError("adoption must not execute the provider stage")
        ),
    )
    assert call_count == 2
    assert result["status"] == "completed"
    receipt = json.loads(
        (state_root / "receipts" / "0001-review-disclosure.json").read_bytes()
    )
    [authority_commitment, _private_commitment] = receipt["output_commitments"]
    assert (
        authority_commitment["sha256"] == hashlib.sha256(original_payload).hexdigest()
    )
    assert authority_commitment["byte_count"] == len(original_payload)
    assert (
        authority_commitment["sha256"]
        != hashlib.sha256(review_outputs[0].read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "missing_flag",
    ["--authority-output", "--private-records-output"],
)
def test_run_cycle_adopts_default_disclosure_receipt_outputs(
    tmp_path: Path,
    missing_flag: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    review_card = tmp_path / "review" / "run-card.json"
    review_arguments, _outputs, _state, _fixture = (
        _adoptable_disclosure_review_completion(tmp_path, run_card=review_card)
    )
    flag_index = review_arguments.index(missing_flag)
    del review_arguments[flag_index : flag_index + 2]
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="review-disclosure",
                command="review-disclosure-exceptions",
                boundary="model_provider",
                arguments=review_arguments,
                run_card=review_card,
            ),
        ],
    )
    state_root = tmp_path / "state"
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )
    result = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=False,
        adopt_next_completed=True,
        external_stage_verifier=cli._verify_external_completed_cycle_stage,
        permissions=BoundaryPermissions(),
        executor=lambda _command, _arguments: (_ for _ in ()).throw(
            AssertionError("adoption must not execute the provider stage")
        ),
    )
    assert result["status"] == "completed"
    assert result["stop_reason"] is None
    assert (state_root / "receipts" / "0001-review-disclosure.json").is_file()


@pytest.mark.parametrize(
    ("failure_kind", "expected_error"),
    [
        ("missing_output", "external output commitments differ"),
        ("extra_output", "external output commitments differ"),
        ("output_path", "output public_authority path differs"),
        ("output_digest", "output public_authority commitment changed"),
        ("missing_source", "external source commitments differ"),
        ("extra_source", "external source commitments differ"),
        ("source_path", "source routing_plan path differs"),
        ("source_digest", "source routing_plan commitment changed"),
        ("state_path", "external state paths differ"),
        ("extra_state", "external state paths differ"),
        ("missing_top_level", "external disclosure review is incomplete"),
        ("extra_top_level", "external disclosure review is incomplete"),
        ("authority_count", "external disclosure review is incomplete"),
        ("authority_count_type", "external disclosure review is incomplete"),
        ("document_digest", "external document commitment differs"),
        ("document_count", "external document commitment differs"),
        ("provider_call_type", "external disclosure review is incomplete"),
    ],
)
def test_run_cycle_disclosure_adoption_rejects_inexact_commitments(
    tmp_path: Path,
    failure_kind: str,
    expected_error: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    review_card = tmp_path / "review" / "run-card.json"
    review_arguments, _review_outputs, _provider_state, _fixture = (
        _adoptable_disclosure_review_completion(
            tmp_path,
            run_card=review_card,
        )
    )
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="review-disclosure",
                command="review-disclosure-exceptions",
                boundary="model_provider",
                arguments=review_arguments,
                run_card=review_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )
    card = json.loads(review_card.read_bytes())
    outputs = cast(dict[str, dict[str, str]], card["output_commitments"])
    sources = cast(dict[str, dict[str, object]], card["source_commitments"])
    state_paths = cast(dict[str, str], card["state_paths"])
    if failure_kind == "missing_output":
        del outputs["private_records"]
    elif failure_kind == "extra_output":
        outputs["unexpected"] = dict(outputs["public_authority"])
    elif failure_kind == "output_path":
        outputs["public_authority"]["path"] = outputs["private_records"]["path"]
    elif failure_kind == "output_digest":
        outputs["public_authority"]["sha256"] = "sha256:" + "0" * 64
    elif failure_kind == "missing_source":
        del sources["plan_run_card"]
    elif failure_kind == "extra_source":
        sources["unexpected"] = dict(sources["routing_plan"])
    elif failure_kind == "source_path":
        sources["routing_plan"]["path"] = sources["exception_worksheet"]["path"]
    elif failure_kind == "source_digest":
        sources["routing_plan"]["sha256"] = "sha256:" + "0" * 64
    elif failure_kind == "state_path":
        state_paths["provider_journal"] = state_paths["provider_spend_authority"]
    elif failure_kind == "extra_state":
        state_paths["unexpected"] = state_paths["provider_journal"]
    elif failure_kind == "missing_top_level":
        del card["model_review_authority"]
    elif failure_kind == "extra_top_level":
        card["unexpected"] = False
    elif failure_kind == "authority_count":
        cast(dict[str, object], card["model_review_authority"])["decision_count"] = 2
    elif failure_kind == "authority_count_type":
        cast(dict[str, object], card["model_review_authority"])["decision_count"] = True
    elif failure_kind == "document_digest":
        sources["document_root"]["tree_sha256"] = "sha256:not-a-digest"
    elif failure_kind == "document_count":
        sources["document_root"]["document_count"] = False
    else:
        card["provider_call_executed_this_run"] = "false"
    review_card.write_bytes(canonical_json_bytes(card))

    with pytest.raises(CycleOrchestratorError, match=expected_error):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            adopt_next_completed=True,
            external_stage_verifier=_accept_external_stage,
            permissions=BoundaryPermissions(),
            executor=lambda _command, _arguments: (_ for _ in ()).throw(
                AssertionError("adoption must not execute the provider stage")
            ),
        )
    assert not (state_root / "receipts" / "0001-review-disclosure.json").exists()


def test_run_cycle_help_describes_safe_resume_boundaries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "run-cycle", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for expected in (
        "--config",
        "--state-root",
        "--execute",
        "--adopt-next-completed",
        "--allow-network",
        "--allow-human",
        "--allow-model-provider",
        "--allow-paid",
        "--json",
    ):
        assert expected in help_text
    assert "evaluation" in help_text
    assert "freeze" in help_text
    assert "dispatch" in help_text


@pytest.mark.parametrize(
    ("overlap_flag", "expected_flag"),
    [
        ("private-root", "--controlled-private-store-root"),
        ("explicit-authority", "--authority-output"),
        ("explicit-log", "--log-output"),
        ("output-ancestor", "--output-root"),
    ],
)
def test_run_cycle_rejects_disclosure_writes_under_frozen_authority_root(
    tmp_path: Path,
    overlap_flag: str,
    expected_flag: str,
) -> None:
    frozen_root = tmp_path / "frozen-source"
    output_root = tmp_path / "review-artifacts"
    private_root = tmp_path / "review-private"
    authority_output = output_root / "authority.json"
    log_output = output_root / "logs" / "review.jsonl"
    if overlap_flag == "private-root":
        private_root = frozen_root / "private"
    elif overlap_flag == "explicit-authority":
        authority_output = frozen_root / "authority.json"
    elif overlap_flag == "explicit-log":
        log_output = frozen_root / "review.jsonl"
    else:
        output_root = tmp_path
        authority_output = output_root / "authority.json"
        log_output = output_root / "logs" / "review.jsonl"
    init_root = tmp_path / "init"
    init_run_card = init_root / "run-cards" / "init-cycle.json"
    review_run_card = output_root / "run-cards" / "review.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(init_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_run_card),
                    "--execute",
                    "--resume",
                ],
                run_card=init_run_card,
            ),
            _stage(
                stage_id="review-disclosure",
                command="review-disclosure-exceptions",
                boundary="model_provider",
                arguments=[
                    "--output-root",
                    str(output_root),
                    "--routing-plan",
                    str(tmp_path / "plan.json"),
                    "--exception-worksheet",
                    str(tmp_path / "worksheet.json"),
                    "--plan-run-card",
                    str(tmp_path / "plan-run-card.json"),
                    "--document-root",
                    str(tmp_path / "documents"),
                    "--frozen-authority-root",
                    str(frozen_root),
                    "--provider-journal",
                    str(private_root / "provider-attempts.sqlite3"),
                    "--provider-spend-authority",
                    str(private_root / "provider-spend-authority.sqlite3"),
                    "--controlled-private-store-root",
                    str(private_root),
                    "--authority-output",
                    str(authority_output),
                    "--private-records-output",
                    str(private_root / "private-records.json"),
                    "--log-output",
                    str(log_output),
                    "--run-card-output",
                    str(review_run_card),
                    "--execute",
                    "--resume",
                ],
                run_card=review_run_card,
            ),
        ],
    )
    calls: list[str] = []

    with pytest.raises(
        CycleOrchestratorError,
        match=rf"writable path {expected_flag} overlaps --frozen-authority-root",
    ):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(network=True, model_provider=True),
            executor=lambda command, _arguments: calls.append(command) or 0,
        )

    assert calls == []
    assert not (tmp_path / "state").exists()
    assert not init_root.exists()


def test_run_cycle_allowlist_contains_only_receipted_acquisition_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for command in COMMAND_BOUNDARIES:
        with pytest.raises(SystemExit) as exc_info:
            main(["acquisition", command, "--help"])
        assert exc_info.value.code == 0, command
        command_help = capsys.readouterr().out
        assert "--execute" in command_help, command
        assert "--run-card-output" in command_help, command
        assert "--resume" in command_help, command


def test_gemini_disclosure_successor_inserts_review_before_finalization() -> None:
    template = json.loads(
        (
            ROOT
            / "manifests"
            / (
                "cycle-1-target-100.v4-ranked-reserve-"
                "gemini-disclosure-successor.template.json"
            )
        ).read_text()
    )
    stages = template["config"]["stages"]
    ids = [stage["id"] for stage in stages]
    review_index = ids.index("review-paid-disclosure-exceptions")
    finalizer_index = ids.index("clear-paid-documents")

    assert review_index + 1 == finalizer_index
    assert stages[review_index]["command"] == "review-disclosure-exceptions"
    assert stages[review_index]["boundary"] == "model_provider"
    assert stages[finalizer_index]["command"] == "finalize-provenance-quarantine"
    assert stages[finalizer_index]["boundary"] == "provider_free"
    review_arguments = stages[review_index]["arguments"]
    finalizer_arguments = stages[finalizer_index]["arguments"]

    def flag_value(arguments: list[str], flag: str) -> str:
        index = arguments.index(flag)
        return arguments[index + 1]

    assert flag_value(finalizer_arguments, "--model-review-authority") == flag_value(
        review_arguments, "--authority-output"
    )
    assert flag_value(
        finalizer_arguments, "--model-review-private-records"
    ) == flag_value(review_arguments, "--private-records-output")
    assert (
        flag_value(finalizer_arguments, "--model-review-run-card")
        == stages[review_index]["run_card"]
    )
    for state_flag in (
        "--frozen-authority-root",
        "--provider-journal",
        "--provider-spend-authority",
    ):
        assert flag_value(finalizer_arguments, state_flag) == flag_value(
            review_arguments, state_flag
        )
    assert COMMAND_BOUNDARIES["review-disclosure-exceptions"].value == "model_provider"


def test_run_cycle_status_reports_provider_free_stage_as_ready(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 0
    )

    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "ready"
    assert status["completed_stage_count"] == 0
    assert status["next_stage"]["id"] == "initialize"
    assert status["next_stage"]["boundary"] == "provider_free"
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize(
    ("exit_code", "expected_status"),
    [(None, 0), (0, 0), (1, 2)],
)
def test_run_cycle_preserves_delegated_system_exit_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int | None,
    expected_status: int,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def delegated_main(_arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        raise SystemExit(exit_code)

    monkeypatch.setattr("legalforecast.cli.main", delegated_main)

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--execute",
                "--json",
            ]
        )
        == expected_status
    )


def test_run_cycle_executes_provider_free_stage_and_resumes_from_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    command = [
        "acquisition",
        "run-cycle",
        "--config",
        str(config),
        "--state-root",
        str(state_root),
        "--execute",
        "--json",
    ]
    assert main(command) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "completed"
    assert first["completed_stage_count"] == 1
    assert first["plan_completed"] is True
    assert first["corpus_finalization_planned"] is False
    assert first["corpus_target_verified"] is False
    assert first["clean_case_count"] is None
    receipt = state_root / "receipts" / "0000-initialize.json"
    assert receipt.is_file()

    run_card_before = run_card.read_bytes()
    receipt_before = receipt.read_bytes()
    assert main(command) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "completed"
    assert second["stages"][0]["status"] == "completed"
    assert run_card.read_bytes() == run_card_before
    assert receipt.read_bytes() == receipt_before


def test_run_cycle_stops_after_broker_policy_generation_before_paid_stage(
    tmp_path: Path,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    broker_card = tmp_path / "broker-policy" / "run-card.json"
    purchase_card = tmp_path / "purchase" / "run-card.json"
    cards = {
        "init-cycle": init_card,
        "generate-recap-fetch-broker-policy": broker_card,
        "purchase-missing-recap-fetch": purchase_card,
    }
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="generate-exact-broker-policy",
                command="generate-recap-fetch-broker-policy",
                boundary="provider_free",
                arguments=[
                    "--run-card-output",
                    str(broker_card),
                    "--execute",
                ],
                run_card=broker_card,
            ),
            _stage(
                stage_id="purchase",
                command="purchase-missing-recap-fetch",
                boundary="paid",
                arguments=[
                    "--run-card-output",
                    str(purchase_card),
                    "--execute",
                ],
                run_card=purchase_card,
            ),
        ],
    )
    calls: list[str] = []

    def write_card(command: str, _arguments: tuple[str, ...]) -> int:
        calls.append(command)
        _write_completion_card(cards[command], stage=command)
        return 0

    permissions = BoundaryPermissions(network=True, paid=True)
    first = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=permissions,
        executor=write_card,
    )

    assert calls == ["init-cycle", "generate-recap-fetch-broker-policy"]
    assert first["status"] == "ready"
    assert first["stop_reason"] == "broker_policy_deployment_checkpoint_stage_completed"
    assert first["next_stage"]["id"] == "purchase"

    second = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=permissions,
        executor=write_card,
    )

    assert calls == [
        "init-cycle",
        "generate-recap-fetch-broker-policy",
        "purchase-missing-recap-fetch",
    ]
    assert second["status"] == "completed"


def test_run_cycle_adopts_exact_next_completed_model_stage_without_executor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / "unitize" / "run-card.json"
    model_arguments, model_outputs = _adoptable_unitization_completion(
        tmp_path,
        run_card=model_card,
    )
    model_output = model_outputs[0]
    packet_card = tmp_path / "packets" / "run-card.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="unitize",
                command="llm-unitize",
                boundary="model_provider",
                arguments=model_arguments,
                run_card=model_card,
            ),
            _stage(
                stage_id="plan-packets",
                command="plan-packet-inputs",
                boundary="provider_free",
                arguments=[
                    "--run-card-output",
                    str(packet_card),
                    "--execute",
                ],
                run_card=packet_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    def forbidden_delegated_main(_arguments: tuple[str, ...]) -> int:
        raise AssertionError("adoption must not invoke an acquisition stage")

    monkeypatch.setattr("legalforecast.cli.main", forbidden_delegated_main)
    monkeypatch.setattr(
        "legalforecast.cli._verify_external_completed_cycle_stage",
        _accept_external_stage,
    )
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(state_root),
                "--adopt-next-completed",
                "--json",
            ]
        )
        == 0
    )

    status = json.loads(capsys.readouterr().out)
    assert status["mode"] == "adopt_completed"
    assert status["status"] == "ready"
    assert status["stop_reason"] == "model_provider_stage_adopted"
    assert status["completed_stage_count"] == 2
    assert status["next_stage"]["id"] == "plan-packets"
    receipt_path = state_root / "receipts" / "0001-unitize.json"
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["boundary"] == "model_provider"
    assert (
        receipt["run_card_sha256"]
        == hashlib.sha256(model_card.read_bytes()).hexdigest()
    )
    assert receipt["output_commitments"][0] == {
        "path": str(model_output),
        "kind": "file",
        "sha256": hashlib.sha256(model_output.read_bytes()).hexdigest(),
        "byte_count": len(model_output.read_bytes()),
    }
    assert len(receipt["output_commitments"]) == 4

    model_output.write_text('{"candidate_id":"tampered"}\n', encoding="utf-8")
    with pytest.raises(
        CycleOrchestratorError,
        match="stage receipt no longer matches cycle config",
    ):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            permissions=BoundaryPermissions(),
            executor=lambda _command, _arguments: 0,
        )


@pytest.mark.parametrize(
    ("command", "factory"),
    [
        ("parse-documents", _adoptable_parse_completion),
        ("llm-unitize", _adoptable_unitization_completion),
        ("llm-review-stage-a", _adoptable_review_completion),
        ("llm-label", _adoptable_label_completion),
    ],
)
def test_run_cycle_adopts_each_closed_external_model_stage(
    tmp_path: Path,
    command: str,
    factory: _CompletionFactory,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / command / "run-card.json"
    model_arguments, _outputs = factory(
        tmp_path,
        run_card=model_card,
    )
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id=f"adopt-{command}",
                command=command,
                boundary="model_provider",
                arguments=model_arguments,
                run_card=model_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    status = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=False,
        adopt_next_completed=True,
        external_stage_verifier=_accept_external_stage,
        permissions=BoundaryPermissions(),
        executor=lambda _command, _arguments: (_ for _ in ()).throw(
            AssertionError("external adoption invoked an executor")
        ),
    )

    assert status["mode"] == "adopt_completed"
    assert status["completed_stage_count"] == 2
    assert status["plan_completed"] is True


@pytest.mark.parametrize(
    ("command", "factory"),
    [
        ("parse-documents", _adoptable_parse_completion),
        ("llm-unitize", _adoptable_unitization_completion),
    ],
)
def test_run_cycle_cli_semantic_replay_rejects_self_attested_completion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
    factory: _CompletionFactory,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / command / "run-card.json"
    arguments, _outputs = factory(tmp_path, run_card=model_card)
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="model",
                command=command,
                boundary="model_provider",
                arguments=arguments,
                run_card=model_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(state_root),
                "--adopt-next-completed",
            ]
        )
        == 2
    )
    assert "semantic replay failed" in capsys.readouterr().err
    assert not (state_root / "receipts" / "0001-model.json").exists()


@pytest.mark.parametrize(
    ("failure_kind", "expected_error"),
    [
        ("swapped_sources", "source selection path differs"),
        ("document_tree_tamper", "document tree commitment changed"),
        ("markdown_tree_tamper", "Markdown tree commitment changed"),
        ("wrong_model", "model identity differs"),
        ("wrong_lineage_root", "lineage roots differ"),
    ],
)
def test_run_cycle_adoption_binds_unitization_invocation_and_trees(
    tmp_path: Path,
    failure_kind: str,
    expected_error: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / "unitize" / "run-card.json"
    model_arguments, _outputs = _adoptable_unitization_completion(
        tmp_path,
        run_card=model_card,
    )
    card = json.loads(model_card.read_bytes())
    if failure_kind == "swapped_sources":
        (
            card["input_commitments"]["selection"],
            card["input_commitments"]["model_registry"],
        ) = (
            card["input_commitments"]["model_registry"],
            card["input_commitments"]["selection"],
        )
    elif failure_kind == "document_tree_tamper":
        (tmp_path / "inputs" / "documents" / "document.pdf").write_text(
            "changed\n", encoding="utf-8"
        )
    elif failure_kind == "markdown_tree_tamper":
        (tmp_path / "inputs" / "markdown" / "document.md").write_text(
            "changed\n", encoding="utf-8"
        )
    elif failure_kind == "wrong_model":
        card["model_execution"]["model_key"] = "openai:other"
    else:
        card["lineage_roots"]["document_root"] = str(tmp_path / "elsewhere")
    model_card.write_bytes(canonical_json_bytes(card))
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="unitize",
                command="llm-unitize",
                boundary="model_provider",
                arguments=model_arguments,
                run_card=model_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    with pytest.raises(CycleOrchestratorError, match=expected_error):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            adopt_next_completed=True,
            external_stage_verifier=_accept_external_stage,
            permissions=BoundaryPermissions(),
            executor=lambda _command, _arguments: 0,
        )


@pytest.mark.parametrize("failure_kind", ["revision", "root"])
def test_run_cycle_adoption_binds_parser_revision_and_root(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    parser_card = tmp_path / "parse" / "run-card.json"
    parser_arguments, _outputs = _adoptable_parse_completion(
        tmp_path,
        run_card=parser_card,
    )
    card = json.loads(parser_card.read_bytes())
    if failure_kind == "revision":
        card["parser_execution"]["parser_revision"] = "wrong"
    else:
        card["parser_execution"]["parser_root"] = str(tmp_path / "wrong-parser")
    parser_card.write_bytes(canonical_json_bytes(card))
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="parse",
                command="parse-documents",
                boundary="model_provider",
                arguments=parser_arguments,
                run_card=parser_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    with pytest.raises(CycleOrchestratorError, match="live Mistral lineage"):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            adopt_next_completed=True,
            external_stage_verifier=_accept_external_stage,
            permissions=BoundaryPermissions(),
            executor=lambda _command, _arguments: 0,
        )


@pytest.mark.parametrize(
    ("command", "factory", "flag", "expected_error"),
    [
        (
            "parse-documents",
            _adoptable_parse_completion,
            "--selection",
            "omits configured inputs",
        ),
        (
            "llm-review-stage-a",
            _adoptable_review_completion,
            "--markdown-root",
            "Markdown root differs",
        ),
        (
            "llm-label",
            _adoptable_label_completion,
            "--markdown-root",
            "Markdown root differs",
        ),
    ],
)
def test_run_cycle_adoption_rejects_changed_output_affecting_path(
    tmp_path: Path,
    command: str,
    factory: _CompletionFactory,
    flag: str,
    expected_error: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / command / "run-card.json"
    arguments, _outputs = factory(tmp_path, run_card=model_card)
    wrong_path = tmp_path / "wrong-input"
    wrong_path.mkdir()
    arguments[arguments.index(flag) + 1] = str(wrong_path)
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="model",
                command=command,
                boundary="model_provider",
                arguments=arguments,
                run_card=model_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    with pytest.raises(CycleOrchestratorError, match=expected_error):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            adopt_next_completed=True,
            external_stage_verifier=_accept_external_stage,
            permissions=BoundaryPermissions(),
            executor=lambda _command, _arguments: 0,
        )


@pytest.mark.parametrize("failure_kind", ["missing_audit", "wrong_audit"])
def test_run_cycle_adoption_rejects_unbound_provider_shard_audit(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / "label" / "run-card.json"
    arguments, _outputs = _adoptable_label_completion(
        tmp_path,
        run_card=model_card,
    )
    audit_index = arguments.index("--provider-shard-audit")
    if failure_kind == "missing_audit":
        del arguments[audit_index : audit_index + 2]
    else:
        wrong_audit = tmp_path / "wrong-audit.jsonl"
        wrong_audit.write_text("wrong\n", encoding="utf-8")
        arguments[audit_index + 1] = str(wrong_audit)
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="label",
                command="llm-label",
                boundary="model_provider",
                arguments=arguments,
                run_card=model_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    with pytest.raises(CycleOrchestratorError, match="provider-shard"):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            adopt_next_completed=True,
            external_stage_verifier=_accept_external_stage,
            permissions=BoundaryPermissions(),
            executor=lambda _command, _arguments: 0,
        )


@pytest.mark.parametrize(
    ("failure_kind", "expected_error"),
    [
        ("missing_card", "has no safe completion run card"),
        ("mismatched_card", "run card is not an executed completion"),
        ("unknown_schema", "external completion schema is unsupported"),
        ("empty_outputs", "external completion is incomplete"),
        ("omitted_output", "external completion output paths differ"),
        ("tampered_output", "commitment changed"),
        ("tampered_source", "commitment changed"),
        ("omitted_source", "external source commitments are incomplete"),
        ("missing_output", "is unavailable or unsafe"),
    ],
)
def test_run_cycle_adoption_fails_closed_on_invalid_completion_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
    expected_error: str,
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    model_card = tmp_path / "unitize" / "run-card.json"
    model_arguments, model_outputs = _adoptable_unitization_completion(
        tmp_path,
        run_card=model_card,
    )
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="unitize",
                command="llm-unitize",
                boundary="model_provider",
                arguments=model_arguments,
                run_card=model_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )
    if failure_kind == "missing_card":
        model_card.unlink()
    elif failure_kind == "missing_output":
        model_outputs[0].unlink()
    elif failure_kind == "tampered_output":
        model_outputs[0].write_text("changed-after-completion\n", encoding="utf-8")
    elif failure_kind == "tampered_source":
        provider_caps_index = model_arguments.index("--provider-cycle-caps") + 1
        Path(model_arguments[provider_caps_index]).write_text(
            "changed-after-completion\n",
            encoding="utf-8",
        )
    else:
        card = json.loads(model_card.read_bytes())
        if failure_kind == "mismatched_card":
            card["stage"] = "llm-label"
        elif failure_kind == "unknown_schema":
            card["schema_version"] = "legalforecast.fake.v1"
        elif failure_kind == "empty_outputs":
            card["output_paths"] = []
            card["output_commitments"] = {}
        elif failure_kind == "omitted_output":
            card["output_paths"] = card["output_paths"][:-1]
        elif failure_kind == "omitted_source":
            del card["input_commitments"]["provider_cycle_caps"]
        model_card.write_bytes(canonical_json_bytes(card))

    def forbidden_delegated_main(_arguments: tuple[str, ...]) -> int:
        raise AssertionError("adoption must not invoke an acquisition stage")

    monkeypatch.setattr("legalforecast.cli.main", forbidden_delegated_main)
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(state_root),
                "--adopt-next-completed",
            ]
        )
        == 2
    )
    assert expected_error in capsys.readouterr().err
    assert not (state_root / "receipts" / "0001-unitize.json").exists()


def test_run_cycle_adoption_rejects_non_model_next_stage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_card = tmp_path / "init" / "run-card.json"
    network_card = tmp_path / "discovery" / "run-card.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="discover",
                command="discover-courtlistener",
                boundary="network",
                arguments=[
                    "--run-card-output",
                    str(network_card),
                    "--execute",
                ],
                run_card=network_card,
            ),
        ],
    )
    _receipt_initial_stage(
        config=config,
        state_root=state_root,
        init_run_card=init_card,
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(state_root),
                "--adopt-next-completed",
            ]
        )
        == 2
    )
    assert "exact next unreceipted stage" in capsys.readouterr().err
    assert not (state_root / "receipts" / "0001-discover.json").exists()


@pytest.mark.parametrize(
    "conflicting_flags",
    [
        ["--execute"],
        ["--allow-network"],
        ["--allow-human"],
        ["--allow-model-provider"],
        ["--allow-paid"],
    ],
)
def test_run_cycle_adoption_rejects_execution_and_authority_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    conflicting_flags: list[str],
) -> None:
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(tmp_path / "unused.json"),
                "--state-root",
                str(tmp_path / "state"),
                "--adopt-next-completed",
                *conflicting_flags,
            ]
        )
        == 2
    )
    assert "cannot be combined" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_run_cycle_stops_before_network_without_provider_activity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_root = tmp_path / "init"
    init_run_card = init_root / "run-cards" / "init-cycle.json"
    run_card = tmp_path / "network" / "run-cards" / "discover-courtlistener.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(init_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_run_card),
                    "--execute",
                ],
                run_card=init_run_card,
            ),
            _stage(
                stage_id="discover",
                command="discover-courtlistener",
                boundary="network",
                arguments=[
                    "--output-root",
                    str(tmp_path / "network"),
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--execute",
                "--json",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "blocked"
    assert status["completed_stage_count"] == 1
    assert status["stop_reason"] == "network_boundary_not_authorized"
    assert status["next_stage"]["command"] == "discover-courtlistener"
    assert status["next_stage"]["status"] == "blocked"
    assert not run_card.exists()
    assert not (tmp_path / "state" / "receipts" / "0001-discover.json").exists()


def test_run_cycle_authorizes_only_one_boundary_stage_per_invocation(
    tmp_path: Path,
) -> None:
    stage_specs = [
        ("initialize", "init-cycle", "provider_free"),
        ("approve-purchase", "record-purchase-approval", "human"),
        ("plan-free", "plan-public-downloads", "provider_free"),
        ("review-disclosure", "record-disclosure-review-decisions", "human"),
        ("plan-packets", "plan-packet-inputs", "provider_free"),
    ]
    cards = {
        command: tmp_path / stage_id / "run-card.json"
        for stage_id, command, _boundary in stage_specs
    }
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id=stage_id,
                command=command,
                boundary=boundary,
                arguments=[
                    *(
                        ["--eligibility-anchor", "2026-06-30"]
                        if command == "init-cycle"
                        else []
                    ),
                    "--run-card-output",
                    str(cards[command]),
                    "--execute",
                ],
                run_card=cards[command],
            )
            for stage_id, command, boundary in stage_specs
        ],
    )
    calls: list[str] = []

    def write_card(command: str, _arguments: tuple[str, ...]) -> int:
        calls.append(command)
        cards[command].parent.mkdir(parents=True, exist_ok=True)
        cards[command].write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": command,
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        return 0

    first = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=BoundaryPermissions(human=True),
        executor=write_card,
    )

    assert calls == ["init-cycle", "record-purchase-approval"]
    assert first["status"] == "ready"
    assert first["stop_reason"] == "human_stage_completed"
    assert first["completed_stage_count"] == 2
    first_next = first["next_stage"]
    assert isinstance(first_next, dict)
    assert first_next["id"] == "plan-free"

    second = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=BoundaryPermissions(human=True),
        executor=write_card,
    )

    assert calls == [
        "init-cycle",
        "record-purchase-approval",
        "plan-public-downloads",
        "record-disclosure-review-decisions",
    ]
    assert second["status"] == "ready"
    assert second["stop_reason"] == "human_stage_completed"
    assert second["completed_stage_count"] == 4
    second_next = second["next_stage"]
    assert isinstance(second_next, dict)
    assert second_next["id"] == "plan-packets"

    third = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_card,
    )

    assert calls[-1] == "plan-packet-inputs"
    assert third["status"] == "completed"
    assert third["completed_stage_count"] == 5


@pytest.mark.parametrize(
    ("approval_command", "approval_schema"),
    [
        (
            "record-purchase-approval",
            "legalforecast.purchase_approval_run_card.v1",
        ),
        (
            "record-replacement-purchase-approval",
            "legalforecast.replacement_purchase_approval_run_card.v1",
        ),
        (
            "record-replacement-purchase-approval",
            "legalforecast.replacement_purchase_approval_run_card.v2",
        ),
    ],
)
def test_run_cycle_receipts_closed_purchase_approval_run_card(
    tmp_path: Path,
    approval_command: str,
    approval_schema: str,
) -> None:
    init_card = tmp_path / "init.json"
    approval_card = tmp_path / "approval.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="approve",
                command=approval_command,
                boundary="human",
                arguments=[
                    "--run-card-output",
                    str(approval_card),
                    "--execute",
                ],
                run_card=approval_card,
            ),
        ],
    )

    def write_card(command: str, _arguments: tuple[str, ...]) -> int:
        if command == "init-cycle":
            init_card.write_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": "legalforecast.acquisition_run_card.v1",
                        "stage": command,
                        "status": "completed",
                        "dry_run": False,
                        "execute": True,
                        "resume": True,
                        "paid_activity_executed": False,
                        "output_paths": [],
                    }
                )
            )
            return 0
        body = {
            "stage": approval_command,
            "status": "completed",
            "decision": "approve",
            "request_sha256": "a" * 64,
            "checkpoint_sha256": "b" * 64,
            "reviewer_id": "John Hughes",
            "recorded_at_utc": "2026-07-28T00:00:00Z",
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "pacer_fee_acknowledged": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }
        body_bytes = json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        approval_card.write_text(
            json.dumps(
                {
                    "schema_version": approval_schema,
                    "run_card": body,
                    "run_card_sha256": hashlib.sha256(body_bytes).hexdigest(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0

    status = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=BoundaryPermissions(human=True),
        executor=write_card,
    )

    assert status["status"] == "completed"
    assert status["completed_stage_count"] == 2
    assert (tmp_path / "state" / "receipts" / "0001-approve.json").is_file()


@pytest.mark.parametrize(
    ("approval_schema", "approval_stage"),
    [
        (
            "legalforecast.purchase_approval_run_card.v1",
            "record-purchase-approval",
        ),
        (
            "legalforecast.replacement_purchase_approval_run_card.v1",
            "record-replacement-purchase-approval",
        ),
        (
            "legalforecast.replacement_purchase_approval_run_card.v2",
            "record-replacement-purchase-approval",
        ),
    ],
)
def test_completion_card_view_rejects_non_approving_decision(
    approval_schema: str,
    approval_stage: str,
) -> None:
    body = {
        "stage": approval_stage,
        "status": "completed",
        "decision": "reject",
        "request_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "reviewer_id": "John Hughes",
        "recorded_at_utc": "2026-07-28T00:00:00Z",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    body_bytes = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    with pytest.raises(
        CycleOrchestratorError,
        match="not an approving, activity-free decision",
    ):
        _completion_card_view(
            {
                "schema_version": approval_schema,
                "run_card": body,
                "run_card_sha256": hashlib.sha256(body_bytes).hexdigest(),
            }
        )


@pytest.mark.parametrize(
    ("body_change", "expected_error"),
    [
        ({"status": "pending"}, "run card is not an executed completion"),
        ({"decision": "reject"}, "not an approving, activity-free decision"),
        ({"dry_run": True}, "body fields differ from its closed schema"),
        (
            {"provider_activity_requested": True},
            "not an approving, activity-free decision",
        ),
        (
            {"provider_activity_executed": True},
            "not an approving, activity-free decision",
        ),
        (
            {"paid_activity_requested": True},
            "not an approving, activity-free decision",
        ),
        (
            {"paid_activity_executed": True},
            "not an approving, activity-free decision",
        ),
    ],
)
def test_run_cycle_rejects_noncompletion_v2_replacement_approval(
    tmp_path: Path,
    body_change: dict[str, object],
    expected_error: str,
) -> None:
    init_card = tmp_path / "init.json"
    approval_card = tmp_path / "approval.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="approve",
                command="record-replacement-purchase-approval",
                boundary="human",
                arguments=[
                    "--run-card-output",
                    str(approval_card),
                    "--execute",
                ],
                run_card=approval_card,
            ),
        ],
    )

    def write_card(command: str, _arguments: tuple[str, ...]) -> int:
        if command == "init-cycle":
            _write_completion_card(init_card, stage=command)
            return 0
        body: dict[str, object] = {
            "stage": "record-replacement-purchase-approval",
            "status": "completed",
            "decision": "approve",
            "request_sha256": "a" * 64,
            "checkpoint_sha256": "b" * 64,
            "reviewer_id": "John Hughes",
            "recorded_at_utc": "2026-08-06T00:00:00Z",
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "pacer_fee_acknowledged": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        }
        body.update(body_change)
        body_bytes = canonical_json_value_bytes(
            body,
            error_type=ValueError,
            error_message="purchase approval run card body is not canonicalizable",
        )
        approval_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": (
                        "legalforecast.replacement_purchase_approval_run_card.v2"
                    ),
                    "run_card": body,
                    "run_card_sha256": hashlib.sha256(body_bytes).hexdigest(),
                }
            )
        )
        return 0

    with pytest.raises(CycleOrchestratorError, match=re.escape(expected_error)):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(human=True),
            executor=write_card,
        )


def test_run_cycle_rejects_boundary_downgrade_for_paid_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_card = tmp_path / "paid" / "run-cards" / "purchase.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="purchase",
                command="purchase-missing-recap-fetch",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "paid"),
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
                run_card_stage="purchase-missing-recap-fetch",
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "boundary must be paid" in capsys.readouterr().err


def test_run_cycle_accepts_exact_provider_free_llm_label_shard_merge(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "label" / "run-card.json"
    arguments, _outputs = _adoptable_label_completion(
        tmp_path,
        run_card=run_card,
    )
    stage = _parse_stage(
        _stage(
            stage_id="merge-label-shards",
            command="llm-label",
            boundary="provider_free",
            arguments=arguments,
            run_card=run_card,
        ),
        index=0,
    )

    assert stage.stage_id == "merge-label-shards"
    assert stage.boundary.value == "provider_free"


@pytest.mark.parametrize(
    "mutation",
    [
        "provider_execution",
        "mixed_execution_and_merge",
        "unpaired_shard_inputs",
        "local_authority_merge",
        "remote_authority_merge",
    ],
)
def test_run_cycle_rejects_provider_free_llm_label_nonmerge_forms(
    tmp_path: Path,
    mutation: str,
) -> None:
    run_card = tmp_path / "label" / "run-card.json"
    arguments, _outputs = _adoptable_label_completion(
        tmp_path,
        run_card=run_card,
    )
    if mutation == "provider_execution":
        while "--provider-shard-audit" in arguments:
            index = arguments.index("--provider-shard-audit")
            del arguments[index : index + 2]
        while "--provider-shard-run-card" in arguments:
            index = arguments.index("--provider-shard-run-card")
            del arguments[index : index + 2]
        arguments.extend(["--execution-provider", "openai"])
    elif mutation == "mixed_execution_and_merge":
        arguments.extend(["--execution-provider", "openai"])
    elif mutation == "unpaired_shard_inputs":
        index = arguments.index("--provider-shard-run-card")
        del arguments[index : index + 2]
    elif mutation == "local_authority_merge":
        arguments.append("--local-provider-journal-only")
    else:
        arguments.extend(["--provider-authority-table", "fixture-authority"])
    with pytest.raises(
        CycleOrchestratorError,
        match="boundary must be model_provider",
    ):
        _parse_stage(
            _stage(
                stage_id="unsafe-label-stage",
                command="llm-label",
                boundary="provider_free",
                arguments=arguments,
                run_card=run_card,
            ),
            index=0,
        )


@pytest.mark.parametrize(
    "forbidden_argument",
    [
        "--provider-authority-table=fixture-authority",
        "--provider-authority-region=us-east-1",
    ],
)
def test_run_cycle_rejects_equals_form_authority_on_provider_free_merge(
    tmp_path: Path,
    forbidden_argument: str,
) -> None:
    run_card = tmp_path / "label" / "run-card.json"
    arguments, _outputs = _adoptable_label_completion(
        tmp_path,
        run_card=run_card,
    )
    arguments.append(forbidden_argument)

    with pytest.raises(
        CycleOrchestratorError,
        match="boundary must be model_provider",
    ):
        _parse_stage(
            _stage(
                stage_id="unsafe-equals-form-label-stage",
                command="llm-label",
                boundary="provider_free",
                arguments=arguments,
                run_card=run_card,
            ),
            index=0,
        )


def test_run_cycle_preserves_model_provider_boundary_for_llm_label_execution(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "label" / "run-card.json"
    arguments, _outputs = _adoptable_label_completion(
        tmp_path,
        run_card=run_card,
    )
    while "--provider-shard-audit" in arguments:
        index = arguments.index("--provider-shard-audit")
        del arguments[index : index + 2]
    while "--provider-shard-run-card" in arguments:
        index = arguments.index("--provider-shard-run-card")
        del arguments[index : index + 2]
    arguments.extend(["--execution-provider", "openai"])
    stage = _parse_stage(
        _stage(
            stage_id="execute-openai-labels",
            command="llm-label",
            boundary="model_provider",
            arguments=arguments,
            run_card=run_card,
            run_card_stage="llm-label-provider-shard",
        ),
        index=0,
    )

    assert stage.boundary.value == "model_provider"


def test_run_cycle_requires_network_authority_before_paid_authority(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _write_config(tmp_path / "cycle.json", stages=[])

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--execute",
                "--allow-paid",
                "--json",
            ]
        )
        == 2
    )
    assert "--allow-paid requires --allow-network" in capsys.readouterr().err


def test_run_cycle_binds_target_count_to_prepare_stage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_card = tmp_path / "init" / "run-cards" / "init-cycle.json"
    prepare_card = tmp_path / "prepare" / "run-cards" / "prepare-target-cohort.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "init"),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="prepare",
                command="prepare-target-cohort",
                boundary="network",
                arguments=[
                    "--output-root",
                    str(tmp_path / "prepare"),
                    "--target-case-count",
                    "150",
                    "--run-card-output",
                    str(prepare_card),
                    "--execute",
                ],
                run_card=prepare_card,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "target count differs" in capsys.readouterr().err


def test_run_cycle_rejects_equals_form_identity_override(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_card = tmp_path / "init" / "run-cards" / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "init"),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--eligibility-anchor=2027-01-01",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "must not use or repeat equals form" in capsys.readouterr().err


def test_run_cycle_binds_target_count_to_finalization_stage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_card = tmp_path / "init" / "run-cards" / "init-cycle.json"
    final_card = tmp_path / "final" / "run-cards" / "finalize-corpus.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "init"),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="finalize",
                command="finalize-corpus",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "final"),
                    "--target-clean-cases",
                    "150",
                    "--run-card-output",
                    str(final_card),
                    "--execute",
                ],
                run_card=final_card,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "finalize-corpus target count differs" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("clean_count", "meets_target", "should_succeed"),
    [
        (TARGET_CASE_COUNT, True, True),
        (TARGET_CASE_COUNT - 1, True, False),
        (TARGET_CASE_COUNT, False, False),
    ],
)
def test_run_cycle_verifies_completed_corpus_target(
    tmp_path: Path,
    clean_count: int,
    meets_target: bool,
    should_succeed: bool,
) -> None:
    init_card = tmp_path / "init-cycle.json"
    final_card = tmp_path / "finalize-corpus.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="finalize",
                command="finalize-corpus",
                boundary="provider_free",
                arguments=[
                    "--target-clean-cases",
                    str(TARGET_CASE_COUNT),
                    "--run-card-output",
                    str(final_card),
                    "--execute",
                ],
                run_card=final_card,
            ),
        ],
    )

    def write_cards(command: str, _arguments: tuple[str, ...]) -> int:
        card_path = init_card if command == "init-cycle" else final_card
        card: dict[str, object] = {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": command,
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "resume": True,
            "paid_activity_executed": False,
            "output_paths": [],
        }
        if command == "finalize-corpus":
            card.update(
                {
                    "target_clean_cases": TARGET_CASE_COUNT,
                    "clean_count": clean_count,
                    "meets_target": meets_target,
                }
            )
        card_path.write_bytes(canonical_json_bytes(card))
        return 0

    state_root = tmp_path / "state"
    if should_succeed:
        status = run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_cards,
        )
        assert status["corpus_target_verified"] is True
        assert status["clean_case_count"] == TARGET_CASE_COUNT
        assert (state_root / "receipts" / "0001-finalize.json").exists()
    else:
        with pytest.raises(
            CycleOrchestratorError,
            match="does not verify the configured target",
        ):
            run_acquisition_cycle(
                config_path=config,
                state_root=state_root,
                execute=True,
                permissions=BoundaryPermissions(),
                executor=write_cards,
            )
        assert not (state_root / "receipts" / "0001-finalize.json").exists()


def test_run_cycle_refuses_concurrent_owner_before_stage_execution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )
    state_root.mkdir()
    lock_path = state_root / ".run-cycle.lock"
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert (
            main(
                [
                    "acquisition",
                    "run-cycle",
                    "--config",
                    str(config),
                    "--state-root",
                    str(state_root),
                    "--execute",
                    "--json",
                ]
            )
            == 2
        )

    assert "already owns this state root" in capsys.readouterr().err
    assert not run_card.exists()


def test_cycle_lock_rejects_symlinked_state_root_before_creating_it(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    state_root = linked / "state"

    with pytest.raises(CycleOrchestratorError, match="must not contain symlinks"):
        with _cycle_lock(state_root):
            pytest.fail("unsafe state root acquired a cycle lock")

    assert not (outside / "state").exists()


def test_run_cycle_refuses_config_change_during_stage(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def mutate_config(_command: str, _arguments: tuple[str, ...]) -> int:
        record = json.loads(config.read_text(encoding="utf-8"))
        record["target_case_count"] = 101
        config.write_bytes(canonical_json_bytes(record))
        return 0

    with pytest.raises(CycleOrchestratorError, match="changed during execution"):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(),
            executor=mutate_config,
        )
    assert not (tmp_path / "state" / "receipts" / "0000-initialize.json").exists()


def test_run_cycle_fails_closed_when_receipted_run_card_changes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )
    command = [
        "acquisition",
        "run-cycle",
        "--config",
        str(config),
        "--state-root",
        str(state_root),
        "--execute",
        "--json",
    ]
    assert main(command) == 0
    capsys.readouterr()

    card = json.loads(run_card.read_text(encoding="utf-8"))
    card["record_count"] = 999
    run_card.write_text(json.dumps(card) + "\n", encoding="utf-8")

    assert main(command) == 2
    assert "receipted run card changed" in capsys.readouterr().err


def test_run_cycle_fails_closed_when_stage_receipt_is_not_an_object(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        return 0

    state_root = tmp_path / "state"
    run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_stage,
    )
    receipt = state_root / "receipts" / "0000-initialize.json"
    receipt.write_bytes(canonical_json_bytes(["not", "an", "object"]))

    with pytest.raises(CycleOrchestratorError, match="must be a JSON object"):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_fails_closed_when_receipted_output_changes(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    output = stage_root / "cycle-identity.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("original\n", encoding="utf-8")
        run_card.parent.mkdir(parents=True, exist_ok=True)
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [str(output)],
                }
            )
        )
        return 0

    state_root = tmp_path / "state"
    first = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_stage,
    )
    assert first["status"] == "completed"

    output.write_text("changed\n", encoding="utf-8")
    with pytest.raises(
        CycleOrchestratorError,
        match="stage receipt no longer matches cycle config",
    ):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_reuses_shared_directory_commitment_then_rehashes_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_directory = tmp_path / "shared-output"
    output_directory.mkdir()
    (output_directory / "payload.bin").write_bytes(b"x" * 1024)
    run_cards = [tmp_path / f"stage-{index}.json" for index in range(4)]
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id=f"stage-{index}",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
            for index, run_card in enumerate(run_cards)
        ],
    )

    def write_card(command: str, arguments: tuple[str, ...]) -> int:
        run_card = Path(arguments[arguments.index("--run-card-output") + 1])
        _write_completion_card(
            run_card,
            stage=command,
            output_paths=(output_directory,),
        )
        return 0

    state_root = tmp_path / "state"
    completed = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_card,
    )
    assert completed["status"] == "completed"

    original = cycle_orchestrator_module._directory_tree_commitment  # pyright: ignore[reportPrivateUsage]
    scan_count = 0

    def count_scan(root: Path) -> list[dict[str, object]]:
        nonlocal scan_count
        scan_count += 1
        return original(root)

    monkeypatch.setattr(
        cycle_orchestrator_module,
        "_directory_tree_commitment",
        count_scan,
    )
    status = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=False,
        permissions=BoundaryPermissions(),
        executor=write_card,
    )

    assert status["status"] == "completed"
    assert scan_count == 2


@pytest.mark.parametrize("mutation", ["bytes", "entry", "symlink", "hardlink"])
def test_run_cycle_rehashed_shared_directory_fails_closed_on_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    output_directory = tmp_path / "shared-output"
    output_directory.mkdir()
    payload = output_directory / "payload.bin"
    payload.write_bytes(b"original")
    run_cards = [tmp_path / f"stage-{index}.json" for index in range(3)]
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id=f"stage-{index}",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
            for index, run_card in enumerate(run_cards)
        ],
    )

    def write_card(command: str, arguments: tuple[str, ...]) -> int:
        run_card = Path(arguments[arguments.index("--run-card-output") + 1])
        _write_completion_card(
            run_card,
            stage=command,
            output_paths=(output_directory,),
        )
        return 0

    state_root = tmp_path / "state"
    run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_card,
    )
    (state_root / "receipts" / "0002-stage-2.json").unlink()
    run_cards[2].unlink()

    original = cycle_orchestrator_module._directory_tree_commitment  # pyright: ignore[reportPrivateUsage]
    mutated = False

    def mutate_after_initial_scan(root: Path) -> list[dict[str, object]]:
        nonlocal mutated
        tree = original(root)
        if not mutated:
            mutated = True
            if mutation == "bytes":
                payload.write_bytes(b"changed")
            elif mutation == "entry":
                (output_directory / "new.bin").write_bytes(b"new")
            elif mutation == "symlink":
                (output_directory / "link").symlink_to(payload)
            else:
                (output_directory / "hardlink").hardlink_to(payload)
        return tree

    monkeypatch.setattr(
        cycle_orchestrator_module,
        "_directory_tree_commitment",
        mutate_after_initial_scan,
    )

    def reject_side_effect(_command: str, _arguments: tuple[str, ...]) -> int:
        pytest.fail("reused output drift must fail before executing the next stage")

    with pytest.raises(CycleOrchestratorError):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=True,
            permissions=BoundaryPermissions(),
            executor=reject_side_effect,
        )


def test_run_cycle_rehashes_shared_directory_after_executor_before_receipt(
    tmp_path: Path,
) -> None:
    output_directory = tmp_path / "shared-output"
    output_directory.mkdir()
    payload = output_directory / "payload.bin"
    payload.write_bytes(b"original")
    run_cards = [tmp_path / f"stage-{index}.json" for index in range(3)]
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id=f"stage-{index}",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
            for index, run_card in enumerate(run_cards)
        ],
    )

    def write_card(command: str, arguments: tuple[str, ...]) -> int:
        run_card = Path(arguments[arguments.index("--run-card-output") + 1])
        _write_completion_card(
            run_card,
            stage=command,
            output_paths=(output_directory,),
        )
        return 0

    state_root = tmp_path / "state"
    run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_card,
    )
    next_receipt = state_root / "receipts" / "0002-stage-2.json"
    next_receipt.unlink()
    run_cards[2].unlink()

    def mutate_then_complete(command: str, arguments: tuple[str, ...]) -> int:
        payload.write_bytes(b"changed")
        return write_card(command, arguments)

    with pytest.raises(
        CycleOrchestratorError,
        match="changed during cycle check",
    ):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=True,
            permissions=BoundaryPermissions(),
            executor=mutate_then_complete,
        )
    assert not next_receipt.exists()


def test_duplicate_output_paths_fail_before_authentication_or_receipt(
    tmp_path: Path,
) -> None:
    missing_output = tmp_path / "missing-output"
    with pytest.raises(
        CycleOrchestratorError,
        match=r"^stage run card repeats an output path$",
    ):
        cycle_orchestrator_module.authenticate_output_paths(
            (missing_output, missing_output)
        )

    run_card = tmp_path / "stage.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="stage-0",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_card(command: str, _arguments: tuple[str, ...]) -> int:
        _write_completion_card(
            run_card,
            stage=command,
            output_paths=(missing_output, missing_output),
        )
        return 0

    state_root = tmp_path / "state"
    receipt_path = state_root / "receipts" / "0000-stage-0.json"
    with pytest.raises(
        CycleOrchestratorError,
        match=r"^stage run card repeats an output path$",
    ):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_card,
        )
    assert not receipt_path.exists()


def test_run_cycle_rejects_relative_output_path(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": ["relative-output.json"],
                }
            )
        )
        return 0

    with pytest.raises(CycleOrchestratorError, match="must be absolute"):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_rejects_symlink_inside_output_directory(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    output_directory = tmp_path / "output"
    outside = tmp_path / "outside"
    outside.mkdir()
    output_directory.mkdir()
    (output_directory / "escape").symlink_to(outside, target_is_directory=True)
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [str(output_directory)],
                }
            )
        )
        return 0

    with pytest.raises(CycleOrchestratorError, match="contains a symlink"):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_rejects_symlinked_receipts_directory(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        return 0

    state_root = tmp_path / "state"
    run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_stage,
    )
    receipts = state_root / "receipts"
    relocated = state_root / "receipts-relocated"
    receipts.rename(relocated)
    receipts.symlink_to(relocated, target_is_directory=True)

    with pytest.raises(CycleOrchestratorError, match="must not contain symlinks"):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


@pytest.mark.parametrize(
    ("final_schema", "final_resume"),
    [
        ("legalforecast.provenance_quarantine_clearance_run_card.v1", None),
        ("legalforecast.provenance_public_marker_clearance_run_card.v1", True),
    ],
)
def test_run_cycle_accepts_provider_free_clearance_completion_card(
    tmp_path: Path,
    final_schema: str,
    final_resume: bool | None,
) -> None:
    init_card = tmp_path / "init-cycle.json"
    final_card = tmp_path / "finalize-provenance-quarantine.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="finalize-disclosure",
                command="finalize-provenance-quarantine",
                boundary="provider_free",
                arguments=[
                    "--run-card-output",
                    str(final_card),
                    "--execute",
                ],
                run_card=final_card,
            ),
        ],
    )

    def write_cards(command: str, _arguments: tuple[str, ...]) -> int:
        card_path = init_card if command == "init-cycle" else final_card
        card_path.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": (
                        "legalforecast.acquisition_run_card.v1"
                        if command == "init-cycle"
                        else final_schema
                    ),
                    "stage": command,
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    **(
                        {"resume": True}
                        if command == "init-cycle"
                        else (
                            {"resume": final_resume} if final_resume is not None else {}
                        )
                    ),
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        return 0

    status = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_cards,
    )

    assert status["status"] == "completed"
    assert status["completed_stage_count"] == 2


def test_run_cycle_rejects_noncanonical_or_linked_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_cycle_config.v1",
        "cycle_id": "cycle-next",
        "eligibility_anchor": "2026-06-30",
        "target_case_count": 100,
        "stages": [],
    }
    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(noncanonical),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "canonical JSON" in capsys.readouterr().err

    canonical = _write_config(tmp_path / "canonical.json", stages=[])
    linked = tmp_path / "linked.json"
    linked.hardlink_to(canonical)
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(linked),
                "--state-root",
                str(tmp_path / "state-2"),
                "--json",
            ]
        )
        == 2
    )
    assert "unique regular file" in capsys.readouterr().err
