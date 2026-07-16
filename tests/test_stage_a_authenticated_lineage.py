from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy
from legalforecast.labeling.llm_pipeline import stage_a_unitization_prompt_records
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from legalforecast.selection import TrainingCutoffStatus


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
