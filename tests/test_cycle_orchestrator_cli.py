from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path
from typing import Protocol

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_orchestrator import (
    COMMAND_BOUNDARIES,
    BoundaryPermissions,
    CycleOrchestratorError,
    _completion_card_view,  # pyright: ignore[reportPrivateUsage]
    _cycle_lock,  # pyright: ignore[reportPrivateUsage]
    run_acquisition_cycle,
)
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION

TARGET_CASE_COUNT = 100


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


def test_run_cycle_accepts_known_specialized_resume_card_without_resume_field(
    tmp_path: Path,
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
                        else (
                            "legalforecast.provenance_quarantine_clearance_run_card.v1"
                        )
                    ),
                    "stage": command,
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    **({"resume": True} if command == "init-cycle" else {}),
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
