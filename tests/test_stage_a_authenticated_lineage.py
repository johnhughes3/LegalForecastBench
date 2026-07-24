from __future__ import annotations

import hashlib
import json
import sqlite3
from argparse import Namespace
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast import cli
from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy
from legalforecast.labeling.llm_pipeline import stage_a_unitization_prompt_records
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from legalforecast.selection import TrainingCutoffStatus


def test_downstream_stage_a_sources_require_exact_authenticated_paths(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.jsonl"
    parser = tmp_path / "parser.jsonl"
    markdown_root = tmp_path / "markdown"
    selection.write_text("{}\n", encoding="utf-8")
    parser.write_text("{}\n", encoding="utf-8")
    markdown_root.mkdir()
    lineage = cast(
        cli._StageAUnitizationLineage,
        SimpleNamespace(
            input_commitments={
                "selection": cli._stage_a_file_commitment(selection),
                "parser_manifest": cli._stage_a_file_commitment(parser),
            },
            markdown_root=markdown_root,
        ),
    )
    cli._verify_stage_a_source_authority(
        lineage,
        expected_selection_path=selection,
        expected_parser_manifest_path=parser,
        expected_markdown_root=markdown_root,
    )

    substituted_selection = tmp_path / "same-bytes-selection.jsonl"
    substituted_selection.write_bytes(selection.read_bytes())
    with pytest.raises(cli.CommandError, match="selection differs"):
        cli._verify_stage_a_source_authority(
            lineage,
            expected_selection_path=substituted_selection,
            expected_parser_manifest_path=parser,
            expected_markdown_root=markdown_root,
        )


def test_stage_a_parse_lineage_rejects_markdown_drift_and_extra_files(
    tmp_path: Path,
) -> None:
    document_root = tmp_path / "documents"
    markdown_root = tmp_path / "parse" / "markdown"
    source = document_root / "cand-1" / "complaint.pdf"
    markdown = markdown_root / "cand-1" / "complaint.md"
    source.parent.mkdir(parents=True)
    markdown.parent.mkdir(parents=True)
    source.write_bytes(b"complaint bytes")
    markdown.write_text("Count I alleges breach of contract.", encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    text_sha = hashlib.sha256(markdown.read_bytes()).hexdigest()
    downloads = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "local_path": "cand-1/complaint.pdf",
            "sha256": source_sha,
            "byte_count": source.stat().st_size,
        }
    ]
    requests = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "input_path": str(source),
            "expected_sha256": source_sha,
            "expected_byte_count": source.stat().st_size,
            "markdown_output_path": "markdown/cand-1/complaint.md",
        }
    ]
    parsed = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "status": "succeeded",
            "markdown_path": "cand-1/complaint.md",
            "source_sha256": source_sha,
            "source_byte_count": source.stat().st_size,
            "quality_flags": [],
            "extracted_text": {
                "extraction_method": "mistral_parser_markdown",
                "text_sha256": text_sha,
            },
        }
    ]

    cli._verify_stage_a_parse_records(
        download_records=downloads,
        request_records=requests,
        parser_records=parsed,
        document_root=document_root,
        parser_output_root=tmp_path / "parse",
        markdown_root=markdown_root,
    )
    assert set(
        cli._stage_a_markdown_tree_commitments(parsed, markdown_root=markdown_root)
    ) == {"cand-1/complaint.md"}

    markdown.write_text("Substituted complaint text.", encoding="utf-8")
    with pytest.raises(cli.CommandError, match="Markdown hash differs"):
        cli._verify_stage_a_parse_records(
            download_records=downloads,
            request_records=requests,
            parser_records=parsed,
            document_root=document_root,
            parser_output_root=tmp_path / "parse",
            markdown_root=markdown_root,
        )
    markdown.write_text("Count I alleges breach of contract.", encoding="utf-8")
    (markdown_root / "uncommitted.md").write_text("extra", encoding="utf-8")
    with pytest.raises(cli.CommandError, match="exact parser manifest"):
        cli._stage_a_markdown_tree_commitments(parsed, markdown_root=markdown_root)


def test_provider_caps_wrong_cycle_fails_before_model_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = (
        "selection",
        "selection-card",
        "manifest",
        "clearance",
        "materialization-card",
        "requests",
        "parser-manifest",
        "parser-card",
        "registry",
    )
    paths = {name: tmp_path / f"{name}.json" for name in names}
    for path in paths.values():
        path.write_text("{}\n", encoding="utf-8")
    document_root = tmp_path / "documents"
    markdown_root = tmp_path / "markdown"
    document_root.mkdir()
    markdown_root.mkdir()
    caps_path = tmp_path / "caps.json"
    _write_json(
        caps_path,
        {
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "cycle_id": "cycle-b",
            "providers": [
                {
                    "provider": "openai",
                    "cycle_reservation_cap_usd": "10.00",
                    "external_spend_limit_usd": "20.00",
                    "external_limit_scope": "fixture",
                    "external_limit_source": "fixture",
                    "verified_at": "2026-07-16T00:00:00Z",
                }
            ],
        },
    )
    monkeypatch.setattr(cli, "_read_records", lambda path: [{"candidate_id": "c"}])
    monkeypatch.setattr(
        cli, "_validate_selection_run_card_commitment", lambda *a, **k: None
    )
    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        lambda **kwargs: (paths["materialization-card"],),
    )
    monkeypatch.setattr(cli, "_verify_stage_a_parse_lineage", lambda **kwargs: None)
    monkeypatch.setattr(cli, "_stage_a_markdown_tree_commitments", lambda *a, **k: {})
    monkeypatch.setattr(cli, "_materialization_cohort_cycle_id", lambda path: "cycle-a")
    model_resolution_attempted = False

    def forbidden_model_resolution(*args: Any, **kwargs: Any) -> Any:
        nonlocal model_resolution_attempted
        model_resolution_attempted = True
        raise AssertionError("wrong-cycle caps must fail first")

    monkeypatch.setattr(cli, "_registry_entry_for_key", forbidden_model_resolution)
    args = Namespace(
        selection=paths["selection"],
        selection_run_card=paths["selection-card"],
        download_manifest=paths["manifest"],
        disclosure_clearance=paths["clearance"],
        materialization_run_card=paths["materialization-card"],
        document_root=document_root,
        parse_requests=paths["requests"],
        parser_manifest=paths["parser-manifest"],
        parser_run_card=paths["parser-card"],
        model_registry=paths["registry"],
        model_key="openai:gpt-test",
        provider_cycle_caps=caps_path,
        provider_journal=tmp_path / "shared.sqlite3",
    )
    with pytest.raises(cli.CommandError, match="cycle_id differs"):
        cli._verify_stage_a_unitization_lineage(args, markdown_root=markdown_root)
    assert model_resolution_attempted is False
    assert not args.provider_journal.exists()


def test_stage_a_provider_replay_rejects_rehashed_or_cross_cohort_units(
    tmp_path: Path,
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown = markdown_root / "cand-1" / "complaint.md"
    markdown.parent.mkdir(parents=True)
    markdown.write_text("Count I alleges breach.", encoding="utf-8")
    selection = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "Alpha v. Beta",
        "court": "D. Example",
        "docket_number": "1:26-cv-1",
        "documents": [
            {
                "source_document_id": "complaint",
                "document_role": "complaint",
                "docket_entry_number": 1,
                "description": "Complaint",
                "contains_target_outcome": False,
                "model_visible": True,
            }
        ],
    }
    parser = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "status": "succeeded",
        "markdown_path": "cand-1/complaint.md",
    }
    registry_entry = _registry_entry()
    registry_path = tmp_path / "registry.json"
    _write_json(registry_path, [registry_entry.to_record()])
    caps_path = tmp_path / "caps.json"
    _write_json(
        caps_path,
        {
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "cycle_id": "cycle-1",
            "providers": [
                {
                    "provider": "openai",
                    "cycle_reservation_cap_usd": "10.00",
                    "external_spend_limit_usd": "20.00",
                    "external_limit_scope": "fixture",
                    "external_limit_source": "fixture",
                    "verified_at": "2026-07-16T00:00:00Z",
                }
            ],
        },
    )
    caps = cli.load_provider_cycle_caps(caps_path)
    registry_sha = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    prompt_record = stage_a_unitization_prompt_records(
        selection_records=[selection],
        parser_records=[parser],
        markdown_root=markdown_root,
    )[0]
    journal_path = tmp_path / "provider-attempts.sqlite3"
    unit = {"unit_id": "unit-1", "claim_name": "Breach"}
    with ProviderAttemptJournal(
        journal_path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key=registry_entry.registry_key,
            prompt=str(prompt_record["prompt"]),
            model_registry_sha256=registry_sha,
        ),
        provider="openai",
        reservation_usd=0.1,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=cli._path_sha256(caps_path),
    ) as journal:
        journal.run_attempt(1, lambda: {"fixture": "response"})
        raw_output = '{"unit_seeds": []}'
        journal.settle_attempt(
            1,
            input_tokens=10,
            output_tokens=5,
            actual_cost_usd=0.01,
            raw_output=raw_output,
        )
        journal.commit_reconstruction({"prediction_units": [unit], "review_items": []})
    raw_path = tmp_path / "prediction-units.jsonl"
    audit_path = tmp_path / "audit.jsonl"
    queue_path = tmp_path / "queue.jsonl"
    _write_jsonl(
        raw_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [unit],
            }
        ],
    )
    _write_jsonl(
        audit_path,
        [
            {
                "stage": "llm-unitize",
                "status": "succeeded",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "model_key": registry_entry.registry_key,
                "model_registry_sha256": registry_sha,
                "provider_prompt_sha256": prompt_record["prompt_sha256"],
                "raw_output_sha256": "sha256:"
                + hashlib.sha256(raw_output.encode()).hexdigest(),
                "input_tokens": 10,
                "output_tokens": 5,
                "estimated_cost": 0.01,
                "unitization_review_queue": [],
            }
        ],
    )
    _write_jsonl(queue_path, [])
    lineage = cli._StageAUnitizationLineage(
        selection_records=(selection,),
        parser_records=(parser,),
        registry_entry=registry_entry,
        registry_sha256=registry_sha,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(caps_path),
        provider_journal_path=journal_path,
        document_root=tmp_path,
        markdown_root=markdown_root,
        cohort_cycle_id="cycle-1",
        input_paths=(),
        input_commitments={},
        markdown_tree={},
    )

    commitments, digest = cli._verify_stage_a_provider_replay(
        lineage=lineage,
        prediction_units_path=raw_path,
        audit_path=audit_path,
        review_queue_path=queue_path,
    )
    assert commitments["cand-1"]["prediction_units_sha256"].startswith("sha256:")
    assert digest.startswith("sha256:")

    coordinated_audit = json.loads(audit_path.read_text().strip())
    coordinated_audit["review_items"] = [
        {"unit_id": "unit-1", "reason": "low_confidence"}
    ]
    coordinated_audit["unitization_review_queue"] = [
        {
            "schema_version": "legalforecast.unitization_review_queue.v1",
            "status": "pending_adjudication",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "unit_id": "unit-1",
            "review_id": "cand-1:unit-1:stage-a-review",
            "route_reason": "low_confidence",
            "review_item": coordinated_audit["review_items"][0],
        }
    ]
    _write_jsonl(audit_path, [coordinated_audit])
    _write_jsonl(queue_path, coordinated_audit["unitization_review_queue"])
    with pytest.raises(cli.CommandError, match="review items do not reproduce"):
        cli._verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=raw_path,
            audit_path=audit_path,
            review_queue_path=queue_path,
        )
    authentic_audit = dict(coordinated_audit)
    authentic_audit["review_items"] = []
    authentic_audit["unitization_review_queue"] = []
    _write_jsonl(audit_path, [authentic_audit])
    _write_jsonl(queue_path, [])

    authentic_raw = json.loads(raw_path.read_text().strip())
    _write_jsonl(raw_path, [authentic_raw, authentic_raw])
    with pytest.raises(cli.CommandError, match="duplicate llm-unitize output"):
        cli._verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=raw_path,
            audit_path=audit_path,
            review_queue_path=queue_path,
        )

    _write_jsonl(raw_path, [authentic_raw])
    substituted = json.loads(raw_path.read_text().strip())
    substituted["prediction_units"][0]["claim_name"] = "Rehashed substitute"
    _write_jsonl(raw_path, [substituted])
    with pytest.raises(cli.CommandError, match="do not reproduce from journal"):
        cli._verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=raw_path,
            audit_path=audit_path,
            review_queue_path=queue_path,
        )

    _write_jsonl(raw_path, [authentic_raw])
    with ProviderAttemptJournal(
        journal_path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key="openai:gpt-other",
            prompt=str(prompt_record["prompt"]),
            model_registry_sha256=registry_sha,
        ),
        provider="openai",
        reservation_usd=0.1,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=cli._path_sha256(caps_path),
    ) as journal:
        journal.run_attempt(1, lambda: {"fixture": "wrong-model-response"})
        journal.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        journal.commit_reconstruction({"prediction_units": [unit], "review_items": []})
    with pytest.raises(cli.CommandError, match="provider identity or prompt differs"):
        cli._verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=raw_path,
            audit_path=audit_path,
            review_queue_path=queue_path,
        )

    substituted["candidate_id"] = "cand-2"
    _write_jsonl(raw_path, [substituted])
    with pytest.raises(cli.CommandError, match="coverage differs"):
        cli._verify_stage_a_provider_replay(
            lineage=lineage,
            prediction_units_path=raw_path,
            audit_path=audit_path,
            review_queue_path=queue_path,
        )


def test_provider_stage_replay_rejects_duplicate_cross_model_and_cross_stage_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    prompt = "frozen label prompt"
    prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()
    with ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage="llm-label",
            candidate_id="cand-1",
            model_key="openai:judge-a",
            prompt=prompt,
            model_registry_sha256="registry-sha",
        ),
        provider="openai",
        reservation_usd=0.1,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:caps",
    ) as journal:
        journal.run_attempt(1, lambda: {"fixture": "response"})
        journal.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output="{}",
        )
        journal.commit_reconstruction({"labels": []})

    expected = {("cand-1", "openai:judge-a"): prompt_sha}
    providers = {"openai:judge-a": "openai"}
    cli._verified_provider_stage_attempts(
        stage="llm-label",
        journal_path=path,
        expected_prompts=expected,
        providers_by_model=providers,
        model_registry_sha256="registry-sha",
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO provider_attempts SELECT logical_call_key, 2, stage, "
            "candidate_id, model_key, provider, account, prompt_text, "
            "prompt_sha256, model_registry_sha256, reservation_usd, status, "
            "raw_response_json, normalized_response_json, "
            "reconstructed_result_json, input_tokens, output_tokens, "
            "actual_cost_usd, failure_type, failure_message, reserved_at, "
            "completed_at, authority_attempt_ordinal FROM provider_attempts "
            "WHERE attempt_ordinal = 1"
        )
    with pytest.raises(cli.CommandError, match="one settled provider call"):
        cli._verified_provider_stage_attempts(
            stage="llm-label",
            journal_path=path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
        )

    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM provider_attempts WHERE attempt_ordinal = 2")
        connection.execute("UPDATE provider_attempts SET model_key = 'openai:judge-b'")
    with pytest.raises(cli.CommandError, match="unexpected candidate/model"):
        cli._verified_provider_stage_attempts(
            stage="llm-label",
            journal_path=path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
        )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET model_key = 'openai:judge-a', "
            "logical_call_key = ?",
            (
                hashlib.sha256(
                    "\0".join(
                        ("llm-review-stage-a", "cand-1", "openai:judge-a")
                    ).encode()
                ).hexdigest(),
            ),
        )
    with pytest.raises(cli.CommandError, match="provider replay identity differs"):
        cli._verified_provider_stage_attempts(
            stage="llm-label",
            journal_path=path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
        )


def test_structural_review_run_card_rejects_finalize_path_and_journal_substitution(
    tmp_path: Path,
) -> None:
    paths = {
        name: tmp_path / f"{name}.jsonl"
        for name in (
            "selection",
            "parser",
            "raw-units",
            "original-queue",
            "flags",
            "reviewed-queue",
            "audit",
        )
    }
    for path in paths.values():
        _write_jsonl(path, [])
    unit_card = tmp_path / "llm-unitize.json"
    registry_path = tmp_path / "registry.json"
    entry = _registry_entry()
    _write_json(registry_path, [entry.to_record()])
    resolved_entry, registry_sha = cli._registry_entry_for_key(
        registry_path, entry.registry_key
    )
    caps_path = tmp_path / "caps.json"
    _write_json(
        caps_path,
        {
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "cycle_id": "cycle-1",
            "providers": [
                {
                    "provider": "openai",
                    "cycle_reservation_cap_usd": "10.00",
                    "external_spend_limit_usd": "20.00",
                    "external_limit_scope": "fixture",
                    "external_limit_source": "fixture",
                    "verified_at": "2026-07-16T00:00:00Z",
                }
            ],
        },
    )
    caps = cli.load_provider_cycle_caps(caps_path)
    _write_json(
        unit_card,
        {
            "output_commitments": {
                "prediction_units": cli._stage_a_file_commitment(paths["raw-units"]),
                "unitization_review_queue": cli._stage_a_file_commitment(
                    paths["original-queue"]
                ),
            }
        },
    )
    journal_path = tmp_path / "provider-attempts.sqlite3"
    ProviderAttemptJournal(
        journal_path,
        identity=ProviderCallIdentity(
            stage="fixture-bootstrap",
            candidate_id="fixture",
            model_key=entry.registry_key,
            prompt="fixture",
            model_registry_sha256=registry_sha,
        ),
        provider="openai",
        reservation_usd=0.0,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=cli._path_sha256(caps_path),
    ).close()
    lineage = cli._StageAUnitizationLineage(
        selection_records=(),
        parser_records=(),
        registry_entry=resolved_entry,
        registry_sha256=registry_sha,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(caps_path),
        provider_journal_path=journal_path,
        document_root=tmp_path,
        markdown_root=tmp_path,
        cohort_cycle_id="cycle-1",
        input_paths=(),
        input_commitments={
            "selection": cli._stage_a_file_commitment(paths["selection"]),
            "parser_manifest": cli._stage_a_file_commitment(paths["parser"]),
            "provider_cycle_caps": cli._stage_a_file_commitment(caps_path),
        },
        markdown_tree={},
    )
    source_paths = {
        "selection": paths["selection"],
        "parser_manifest": paths["parser"],
        "raw_prediction_units": paths["raw-units"],
        "unitization_review_queue": paths["original-queue"],
        "llm_unitization_run_card": unit_card,
        "model_registry": registry_path,
        "provider_cycle_caps": caps_path,
    }
    output_paths = {
        "structural_flags": paths["flags"],
        "review_queue": paths["reviewed-queue"],
        "audit": paths["audit"],
    }
    stage_attempts = cli._verified_provider_stage_attempts(
        stage="llm-review-stage-a",
        journal_path=journal_path,
        expected_prompts={},
        providers_by_model={entry.registry_key: entry.provider},
        model_registry_sha256=registry_sha,
    )
    run_card_path = tmp_path / "llm-review-stage-a.json"
    _write_json(
        run_card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "llm-review-stage-a",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": True,
            "paid_activity_executed": True,
            "source_commitments": {
                name: cli._stage_a_file_commitment(path)
                for name, path in source_paths.items()
            },
            "output_commitments": {
                name: cli._stage_a_file_commitment(path)
                for name, path in output_paths.items()
            },
            "model_execution": {
                "model_key": entry.registry_key,
                "model_entry_sha256": "sha256:"
                + cli.model_registry_entry_sha256(resolved_entry),
                "model_registry_sha256": registry_sha,
                "provider": entry.provider,
            },
            "provider_chain": cli._provider_chain_commitment(
                lineage=lineage,
                stage_attempts=stage_attempts,
            ),
            "input_paths": [str(path.resolve()) for path in source_paths.values()]
            + [str(journal_path.resolve())],
            "output_paths": [
                str(paths[name].resolve())
                for name in ("flags", "reviewed-queue", "audit")
            ]
            + [str(journal_path.resolve())],
        },
    )

    expected = {
        "expected_structural_flags_path": paths["flags"],
        "expected_audit_path": paths["audit"],
        "expected_registry_path": registry_path,
        "expected_model_key": entry.registry_key,
    }
    cli._verify_stage_a_review_run_card(
        run_card_path,
        lineage=lineage,
        llm_unitization_run_card_path=unit_card,
        expected_review_queue_path=paths["reviewed-queue"],
        **expected,
    )

    substituted_flags = tmp_path / "substituted-flags.jsonl"
    _write_jsonl(substituted_flags, [])
    with pytest.raises(cli.CommandError, match="structural review output path differs"):
        cli._verify_stage_a_review_run_card(
            run_card_path,
            lineage=lineage,
            llm_unitization_run_card_path=unit_card,
            expected_review_queue_path=paths["reviewed-queue"],
            **{**expected, "expected_structural_flags_path": substituted_flags},
        )

    with pytest.raises(cli.CommandError, match="provider chain identity differs"):
        cli._verify_stage_a_review_run_card(
            run_card_path,
            lineage=replace(
                lineage,
                provider_journal_path=tmp_path / "substituted-provider.sqlite3",
            ),
            llm_unitization_run_card_path=unit_card,
            expected_review_queue_path=paths["reviewed-queue"],
            **expected,
        )


def _registry_entry() -> ModelRegistryEntry:
    return ModelRegistryEntry(
        provider="openai",
        model_id="gpt-test",
        display_name="Fixture",
        model_version_or_snapshot="gpt-test-2026-07-01",
        provider_training_cutoff_status=TrainingCutoffStatus.UNKNOWN,
        temperature=0.0,
        top_p=1.0,
        max_output_tokens=100,
        network_disabled=True,
        search_disabled=True,
        tool_policy=ToolPolicy.NO_TOOLS,
        context_limit=1000,
        pricing_source="fixture",
        input_token_price=1.0,
        output_token_price=1.0,
        release_timestamp=datetime(2026, 7, 1, tzinfo=UTC),
        release_timestamp_source="fixture",
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
