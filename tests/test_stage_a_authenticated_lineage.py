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
from legalforecast.evals.live_model_solver import LiveModelProviderError
from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy
from legalforecast.labeling.llm_pipeline import stage_a_unitization_prompt_records
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from legalforecast.selection import TrainingCutoffStatus


def test_successor_selection_card_requires_exact_replay_capability(
    tmp_path: Path,
) -> None:
    """Only the materializer's immutable replay proof admits a successor card."""

    selection_path = tmp_path / "target-cohort-selection.jsonl"
    selection_bytes = b'{"candidate_id":"cand-1"}\n'
    selection_path.write_bytes(selection_bytes)
    card_path = tmp_path / "run-cards" / "project-target-cohort.json"
    card_path.parent.mkdir()
    card = {
        "schema_version": cli.ZERO_COST_SUCCESSOR_STATE_SCHEMA,
        "stage": "project-zero-cost-successor",
        "record_count": 1,
    }
    card_bytes = (json.dumps(card, sort_keys=True) + "\n").encode("utf-8")
    card_path.write_bytes(card_bytes)

    with pytest.raises(TypeError, match="minted only by materialization replay"):
        cli._VerifiedSuccessorSelectionCard()
    with pytest.raises(cli.CommandError, match="requires completed materialization"):
        cli._validate_selection_run_card_commitment(
            card,
            selection_path=selection_path,
            selection_sha256="sha256:" + hashlib.sha256(selection_bytes).hexdigest(),
            selection_record_count=1,
            selection_run_card_bytes=card_bytes,
        )

    capability = object.__new__(cli._VerifiedSuccessorSelectionCard)
    object.__setattr__(capability, "selection_path", selection_path)
    object.__setattr__(capability, "selection_bytes", selection_bytes)
    object.__setattr__(capability, "selection_record_count", 1)
    object.__setattr__(capability, "run_card_path", card_path)
    object.__setattr__(capability, "run_card_bytes", card_bytes)
    object.__setattr__(
        capability, "_token", cli._VERIFIED_SUCCESSOR_SELECTION_CARD_TOKEN
    )
    cli._validate_selection_run_card_commitment(
        card,
        selection_path=selection_path,
        selection_sha256="sha256:" + hashlib.sha256(selection_bytes).hexdigest(),
        selection_record_count=1,
        selection_run_card_bytes=card_bytes,
        verified_successor_selection_card=capability,
    )

    tampered_bytes = card_bytes.replace(b"successor", b"tampered")
    with pytest.raises(cli.CommandError, match="differs from materialization replay"):
        cli._validate_selection_run_card_commitment(
            card,
            selection_path=selection_path,
            selection_sha256="sha256:" + hashlib.sha256(selection_bytes).hexdigest(),
            selection_record_count=1,
            selection_run_card_bytes=tampered_bytes,
            verified_successor_selection_card=capability,
        )
    with pytest.raises(cli.CommandError, match="differs from materialization replay"):
        cli._validate_selection_run_card_commitment(
            card,
            selection_path=selection_path,
            selection_sha256="sha256:" + hashlib.sha256(selection_bytes).hexdigest(),
            selection_record_count=0,
            selection_run_card_bytes=card_bytes,
            verified_successor_selection_card=capability,
        )
    rebound_path = tmp_path / "rebound-selection.jsonl"
    rebound_path.write_bytes(selection_bytes)
    with pytest.raises(cli.CommandError, match="differs from materialization replay"):
        cli._validate_selection_run_card_commitment(
            card,
            selection_path=rebound_path,
            selection_sha256="sha256:" + hashlib.sha256(selection_bytes).hexdigest(),
            selection_record_count=1,
            selection_run_card_bytes=card_bytes,
            verified_successor_selection_card=capability,
        )


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


def test_shared_provider_chain_accepts_production_unprefixed_caps_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Downstream review must replay the digest representation Stage A emits."""

    caps_path = tmp_path / "provider-caps.json"
    _write_json(
        caps_path,
        {
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "cycle_id": "cycle-1",
            "providers": [
                {
                    "provider": "anthropic",
                    "cycle_reservation_cap_usd": "10.00",
                    "external_spend_limit_usd": "20.00",
                    "external_limit_scope": "fixture",
                    "external_limit_source": "fixture",
                    "verified_at": "2026-07-16T00:00:00Z",
                }
            ],
        },
    )
    raw_caps_sha256 = hashlib.sha256(caps_path.read_bytes()).hexdigest()
    journal_path = tmp_path / "provider-attempts.sqlite3"
    ProviderAttemptJournal(
        journal_path,
        identity=ProviderCallIdentity(
            stage="fixture-bootstrap",
            candidate_id="fixture",
            model_key="anthropic:test",
            prompt="fixture",
            model_registry_sha256="1" * 64,
        ),
        provider="anthropic",
        reservation_usd=0.0,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=raw_caps_sha256,
    ).close()
    unitization_card = tmp_path / "llm-unitize.json"
    _write_json(unitization_card, {})
    lineage = cast(
        cli._StageAUnitizationLineage,
        SimpleNamespace(
            cohort_cycle_id="cycle-1",
            provider_caps_sha256=raw_caps_sha256,
            provider_journal_path=journal_path,
            input_commitments={},
            markdown_root=tmp_path,
        ),
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_run_card",
        lambda *args, **kwargs: lineage,
    )

    resolved, resolved_card = cli._verified_shared_provider_chain(
        Namespace(
            llm_unitization_run_card=unitization_card,
            provider_cycle_caps=caps_path,
            provider_journal=journal_path,
        ),
        raw_prediction_units_path=tmp_path / "prediction-units.jsonl",
    )

    assert resolved is lineage
    assert resolved_card == unitization_card

    caps_path.write_bytes(caps_path.read_bytes() + b" ")
    with pytest.raises(cli.CommandError, match="caps artifact differs"):
        cli._verified_shared_provider_chain(
            Namespace(
                llm_unitization_run_card=unitization_card,
                provider_cycle_caps=caps_path,
                provider_journal=journal_path,
            ),
            raw_prediction_units_path=tmp_path / "prediction-units.jsonl",
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

    markdown_tree, markdown_bytes = cli._stage_a_markdown_tree_snapshot(
        parsed, markdown_root=markdown_root
    )
    cli._verify_stage_a_parse_records(
        download_records=downloads,
        request_records=requests,
        parser_records=parsed,
        document_root=document_root,
        parser_output_root=tmp_path / "parse",
        markdown_root=markdown_root,
        markdown_bytes=markdown_bytes,
    )
    assert set(markdown_tree) == {"cand-1/complaint.md"}

    markdown.write_text("Substituted complaint text.", encoding="utf-8")
    _, substituted_bytes = cli._stage_a_markdown_tree_snapshot(
        parsed, markdown_root=markdown_root
    )
    with pytest.raises(cli.CommandError, match="Markdown hash differs"):
        cli._verify_stage_a_parse_records(
            download_records=downloads,
            request_records=requests,
            parser_records=parsed,
            document_root=document_root,
            parser_output_root=tmp_path / "parse",
            markdown_root=markdown_root,
            markdown_bytes=substituted_bytes,
        )
    markdown.write_text("Count I alleges breach of contract.", encoding="utf-8")
    (markdown_root / "uncommitted.md").write_text("extra", encoding="utf-8")
    with pytest.raises(cli.CommandError, match="exact parser manifest"):
        cli._stage_a_markdown_tree_snapshot(parsed, markdown_root=markdown_root)


def test_stage_a_provider_uses_captured_markdown_and_completion_detects_drift(
    tmp_path: Path,
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown = markdown_root / "cand-1" / "complaint.md"
    other_markdown = markdown_root / "cand-2" / "complaint.md"
    markdown.parent.mkdir(parents=True)
    other_markdown.parent.mkdir(parents=True)
    markdown.write_text("captured A", encoding="utf-8")
    other_markdown.write_text("captured B", encoding="utf-8")
    document_root = tmp_path / "documents"
    document = document_root / "cand-1" / "complaint.pdf"
    document.parent.mkdir(parents=True)
    document.write_bytes(b"document A")
    selection_path = tmp_path / "selection.jsonl"
    selection_path.write_text("{}\n", encoding="utf-8")
    selection = {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "A v. B",
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
    captured_markdown = {
        "cand-1/complaint.md": b"captured A",
        "cand-2/complaint.md": b"captured B",
    }
    markdown.unlink()
    markdown.symlink_to(other_markdown)

    [prompt] = stage_a_unitization_prompt_records(
        selection_records=[selection],
        parser_records=[parser],
        markdown_root=markdown_root,
        markdown_bytes=captured_markdown,
    )
    assert "captured A" in prompt["prompt"]
    assert "captured B" not in prompt["prompt"]
    lineage = cast(
        cli._StageAUnitizationLineage,
        SimpleNamespace(
            file_snapshots={selection_path: b"{}\n"},
            document_root=document_root,
            document_tree={"cand-1/complaint.pdf": b"document A"},
            markdown_root=markdown_root,
            markdown_bytes=captured_markdown,
        ),
    )
    with pytest.raises(cli.CommandError, match="Stage A Markdown"):
        cli._require_stage_a_lineage_unchanged(lineage)

    markdown.unlink()
    markdown.write_text("captured A", encoding="utf-8")
    cli._require_stage_a_lineage_unchanged(lineage)
    selection_path.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(cli.CommandError, match="Stage A input changed"):
        cli._require_stage_a_lineage_unchanged(lineage)

    selection_path.write_text("{}\n", encoding="utf-8")
    document.write_bytes(b"document B")
    with pytest.raises(cli.CommandError, match="document tree changed"):
        cli._require_stage_a_lineage_unchanged(lineage)


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
    private_root = (tmp_path / "private-approval").resolve()
    initialization_receipt = (tmp_path / "purchase-ledger-init.json").resolve()
    observed_purchase_authority: list[tuple[object, object]] = []

    def verified_materialization(
        **kwargs: object,
    ) -> cli._VerifiedMaterializedDownstreamLineage:
        observed_purchase_authority.append(
            (
                kwargs.get("controlled_private_root"),
                kwargs.get("initialization_receipt_path"),
            )
        )
        return cli._VerifiedMaterializedDownstreamLineage(
            paths=(paths["materialization-card"],),
            artifact_bytes={
                str(path.resolve()): path.read_bytes()
                for path in (
                    paths["selection"],
                    paths["manifest"],
                    paths["clearance"],
                    paths["materialization-card"],
                )
            },
            manifest_records=({"candidate_id": "c"},),
            clearance_records=({"candidate_id": "c"},),
            selection_records=({"candidate_id": "c"},),
            resolved_records=(),
            document_tree={},
        )

    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        verified_materialization,
    )
    monkeypatch.setattr(cli, "_verify_stage_a_parse_lineage", lambda **kwargs: None)
    monkeypatch.setattr(
        cli, "_stage_a_markdown_tree_snapshot", lambda *a, **k: ({}, {})
    )
    monkeypatch.setattr(
        cli, "_materialization_cohort_cycle_id", lambda *args, **kwargs: "cycle-a"
    )
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
        controlled_private_root=private_root,
        purchase_ledger_initialization_receipt=initialization_receipt,
    )
    with pytest.raises(cli.CommandError, match="cycle_id differs"):
        cli._verify_stage_a_unitization_lineage(args, markdown_root=markdown_root)
    assert model_resolution_attempted is False
    assert observed_purchase_authority == [(private_root, initialization_receipt)]
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
        file_snapshots={},
        document_tree={},
        markdown_bytes={"cand-1/complaint.md": markdown.read_bytes()},
    )

    commitments, digest = cli._verify_stage_a_provider_replay(
        lineage=lineage,
        prediction_units_path=raw_path,
        audit_path=audit_path,
        review_queue_path=queue_path,
    )
    assert commitments["cand-1"]["prediction_units_sha256"].startswith("sha256:")
    assert digest.startswith("sha256:")

    with ProviderAttemptJournal(
        journal_path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key=registry_entry.registry_key,
            prompt=str(prompt_record["prompt"]),
            model_registry_sha256=registry_sha,
            prompt_contract="claim-ontology-v2",
        ),
        provider="openai",
        reservation_usd=0.1,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256=cli._path_sha256(caps_path),
    ) as journal:
        journal.run_attempt(1, lambda: {"fixture": "successor-response"})
        journal.settle_attempt(
            1,
            input_tokens=10,
            output_tokens=5,
            actual_cost_usd=0.01,
            raw_output=raw_output,
        )
        journal.commit_reconstruction({"prediction_units": [unit], "review_items": []})
    successor_commitments, successor_digest = cli._verify_stage_a_provider_replay(
        lineage=lineage,
        prediction_units_path=raw_path,
        audit_path=audit_path,
        review_queue_path=queue_path,
        provider_attempt_namespace="claim-ontology-v2",
    )
    assert successor_commitments == commitments
    assert successor_digest != digest

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


def test_provider_stage_replay_accepts_only_bounded_reconstruction_then_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh bounded retry may settle after a failed local reconstruction."""

    prompt = "frozen structural review prompt"
    expected = {
        ("cand-1", "google:reviewer"): hashlib.sha256(prompt.encode()).hexdigest()
    }
    providers = {"google:reviewer": "google"}

    def build_journal(path: Path) -> None:
        with ProviderAttemptJournal(
            path,
            identity=ProviderCallIdentity(
                stage="llm-review-stage-a",
                candidate_id="cand-1",
                model_key="google:reviewer",
                prompt=prompt,
                model_registry_sha256="registry-sha",
            ),
            provider="google",
            reservation_usd=0.1,
            cycle_cap_usd=10.0,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:caps",
        ) as journal:
            journal.run_attempt(1, lambda: {"response": "first"})
            journal.settle_attempt(
                1,
                input_tokens=1,
                output_tokens=1,
                actual_cost_usd=0.01,
                raw_output='{"structural_flags":[]}',
            )
            journal.record_reconstruction_failure(ValueError("invalid response"))
            assert journal.prepare_reconstruction_retry(max_attempts=3) == 2
            journal.run_attempt(1, lambda: {"response": "second"})
            durable_ordinal = journal.durable_attempt_ordinal(1)
            assert durable_ordinal == 2
            journal.settle_attempt(
                durable_ordinal,
                input_tokens=2,
                output_tokens=2,
                actual_cost_usd=0.02,
                raw_output='{"structural_flags":[]}',
            )
            journal.commit_reconstruction({"structural_flags": []})

    def assert_rejected(path: Path) -> None:
        with pytest.raises(cli.CommandError, match="provider call"):
            cli._verified_provider_stage_attempts(
                stage="llm-review-stage-a",
                journal_path=path,
                expected_prompts=expected,
                providers_by_model=providers,
                model_registry_sha256="registry-sha",
            )

    accepted_path = tmp_path / "accepted.sqlite3"
    build_journal(accepted_path)
    assert (
        cli._verified_provider_stage_attempts(
            stage="llm-review-stage-a",
            journal_path=accepted_path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
        )["attempt_count"]
        == 2
    )

    output_root = tmp_path / "review-resume"
    source_paths = {
        name: tmp_path / f"{name}.jsonl"
        for name in ("selection", "parser", "units", "queue")
    }
    _write_jsonl(
        source_paths["selection"], [{"candidate_id": "cand-1", "case_id": "case-1"}]
    )
    for name in ("parser", "units", "queue"):
        _write_jsonl(source_paths[name], [])
    registry_path = tmp_path / "reviewer-registry.json"
    caps_path = tmp_path / "caps.json"
    unitization_card_path = tmp_path / "llm-unitize.json"
    for path in (registry_path, caps_path, unitization_card_path):
        _write_json(path, {})
    entry = replace(
        _registry_entry(),
        provider="google",
        model_id="reviewer",
        display_name="Gemini Fixture",
        model_version_or_snapshot="gemini-fixture-2026-08-08",
    )
    lineage = SimpleNamespace(
        selection_records=({"candidate_id": "cand-1", "case_id": "case-1"},),
        provider_journal_path=accepted_path,
        provider_caps=SimpleNamespace(cap_usd=lambda provider: 10.0),
        provider_caps_sha256="sha256:caps",
        cohort_cycle_id="cycle-1",
    )
    audit = {
        "candidate_id": "cand-1",
        "model_key": entry.registry_key,
        "prompt_sha256": expected[("cand-1", "google:reviewer")],
        "status": "passed",
    }
    replayed_from_journal = 0

    def replay_stage_a_review(**kwargs: object) -> SimpleNamespace:
        nonlocal replayed_from_journal
        assert kwargs["provider_journal_path"] == accepted_path
        replayed_from_journal += 1
        return SimpleNamespace(
            records=(), audit_records=(audit,), terminal_review_queue_records=()
        )

    monkeypatch.setattr(
        cli,
        "_verified_shared_provider_chain",
        lambda *args, **kwargs: (lineage, unitization_card_path),
    )
    monkeypatch.setattr(
        cli,
        "_registry_entry_for_key",
        lambda *args, **kwargs: (entry, "registry-sha"),
    )
    monkeypatch.setattr(
        cli,
        "_provider_spend_authorities",
        lambda *args, **kwargs: (None, {"google": "default"}),
    )
    monkeypatch.setattr(cli, "llm_review_stage_a_units", replay_stage_a_review)
    args = Namespace(
        execute=True,
        output_root=output_root,
        provider_journal=accepted_path,
        llm_unitization_run_card=unitization_card_path,
        selection=source_paths["selection"],
        parser_manifest=source_paths["parser"],
        prediction_units=source_paths["units"],
        unitization_review_queue=source_paths["queue"],
        model_registry=registry_path,
        provider_cycle_caps=caps_path,
        terminal_escalation=[],
        markdown_root=tmp_path / "markdown",
        structural_flags_output=None,
        review_queue_output=None,
        audit_output=None,
        model_key=entry.registry_key,
        timeout_seconds=1.0,
        resume=True,
        run_card_output=None,
        log_output=None,
    )
    assert cli._cmd_acquisition_llm_review_stage_a(args) == 0
    assert replayed_from_journal == 1
    run_card = json.loads(
        (output_root / "run-cards" / "llm-review-stage-a.json").read_text(
            encoding="utf-8"
        )
    )
    assert run_card["provider_chain"]["stage_attempts"]["attempt_count"] == 2

    for status_code, retryable in ((None, True), (400, False)):
        transport_path = tmp_path / f"transport-{status_code}.sqlite3"

        def transport_failure(
            status_code: int | None = status_code,
            retryable: bool = retryable,
        ) -> dict[str, object]:
            raise LiveModelProviderError(
                "transport failed",
                status_code=status_code,
                retryable=retryable,
            )

        with ProviderAttemptJournal(
            transport_path,
            identity=ProviderCallIdentity(
                stage="llm-review-stage-a",
                candidate_id="cand-1",
                model_key="google:reviewer",
                prompt=prompt,
                model_registry_sha256="registry-sha",
            ),
            provider="google",
            reservation_usd=0.1,
            cycle_cap_usd=10.0,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:caps",
        ) as journal:
            with pytest.raises(LiveModelProviderError):
                journal.run_attempt(1, transport_failure)
            journal.run_attempt(2, lambda: {"response": "recovered"})
            journal.settle_attempt(
                2,
                input_tokens=2,
                output_tokens=2,
                actual_cost_usd=0.02,
                raw_output='{"structural_flags":[]}',
            )
            journal.commit_reconstruction({"structural_flags": []})
        assert (
            cli._verified_provider_stage_attempts(
                stage="llm-review-stage-a",
                journal_path=transport_path,
                expected_prompts=expected,
                providers_by_model=providers,
                model_registry_sha256="registry-sha",
            )["attempt_count"]
            == 2
        )

    invalid_status_path = tmp_path / "invalid-status.sqlite3"
    build_journal(invalid_status_path)
    with sqlite3.connect(invalid_status_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET status = 'validated_response' "
            "WHERE attempt_ordinal = 1"
        )
    assert_rejected(invalid_status_path)

    after_settlement_path = tmp_path / "after-settlement.sqlite3"
    build_journal(after_settlement_path)
    with sqlite3.connect(after_settlement_path) as connection:
        connection.execute(
            "INSERT INTO provider_attempts SELECT logical_call_key, 3, stage, "
            "candidate_id, model_key, provider, account, prompt_text, "
            "prompt_sha256, model_registry_sha256, reservation_usd, "
            "'reconstruction_failed', raw_response_json, normalized_response_json, "
            "NULL, input_tokens, output_tokens, actual_cost_usd, failure_type, "
            "failure_message, reserved_at, completed_at, authority_attempt_ordinal "
            "FROM provider_attempts WHERE attempt_ordinal = 1"
        )
    assert_rejected(after_settlement_path)

    out_of_order_path = tmp_path / "out-of-order.sqlite3"
    build_journal(out_of_order_path)
    with sqlite3.connect(out_of_order_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET attempt_ordinal = 4 WHERE attempt_ordinal = 2"
        )
    assert_rejected(out_of_order_path)

    terminal_path = tmp_path / "terminal.sqlite3"
    with ProviderAttemptJournal(
        terminal_path,
        identity=ProviderCallIdentity(
            stage="llm-review-stage-a",
            candidate_id="cand-1",
            model_key="google:reviewer",
            prompt=prompt,
            model_registry_sha256="registry-sha",
        ),
        provider="google",
        reservation_usd=0.1,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:caps",
    ) as journal:
        journal.run_attempt(1, lambda: {"response": "terminal"})
        journal.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output='{"structural_flags":[]}',
        )
        journal.record_reconstruction_failure(ValueError("invalid response"))
    with sqlite3.connect(terminal_path) as connection:
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
    cli._verified_provider_stage_attempts(
        stage="llm-review-stage-a",
        journal_path=terminal_path,
        expected_prompts=expected,
        providers_by_model=providers,
        model_registry_sha256="registry-sha",
        expected_nonsettled_statuses={
            ("cand-1", "google:reviewer"): "reconstruction_failed"
        },
        expected_nonsettled_attempt_counts={("cand-1", "google:reviewer"): 2},
    )

    transport_terminal_path = tmp_path / "transport-terminal.sqlite3"

    def retryable_transport_failure() -> dict[str, object]:
        raise LiveModelProviderError(
            "retryable transport failed",
            status_code=None,
            retryable=True,
        )

    with ProviderAttemptJournal(
        transport_terminal_path,
        identity=ProviderCallIdentity(
            stage="llm-review-stage-a",
            candidate_id="cand-1",
            model_key="google:reviewer",
            prompt=prompt,
            model_registry_sha256="registry-sha",
        ),
        provider="google",
        reservation_usd=0.1,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:caps",
    ) as journal:
        with pytest.raises(LiveModelProviderError):
            journal.run_attempt(1, retryable_transport_failure)
        journal.run_attempt(2, lambda: {"response": "terminal"})
        journal.settle_attempt(
            2,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.01,
            raw_output='{"structural_flags":[]}',
        )
        journal.record_reconstruction_failure(ValueError("invalid response"))
    assert (
        cli._verified_provider_stage_attempts(
            stage="llm-review-stage-a",
            journal_path=transport_terminal_path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
            expected_nonsettled_statuses={
                ("cand-1", "google:reviewer"): "reconstruction_failed"
            },
            expected_nonsettled_attempt_counts={("cand-1", "google:reviewer"): 1},
        )["attempt_count"]
        == 2
    )
    with sqlite3.connect(terminal_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET status = 'reserved' WHERE attempt_ordinal = 2"
        )
    with pytest.raises(cli.CommandError, match="reconstruction_failed provider call"):
        cli._verified_provider_stage_attempts(
            stage="llm-review-stage-a",
            journal_path=terminal_path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
            expected_nonsettled_statuses={
                ("cand-1", "google:reviewer"): "reconstruction_failed"
            },
            expected_nonsettled_attempt_counts={("cand-1", "google:reviewer"): 2},
        )

    over_limit_path = tmp_path / "over-limit.sqlite3"
    over_limit_path.write_bytes(terminal_path.read_bytes())
    with sqlite3.connect(over_limit_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET status = 'reconstruction_failed' "
            "WHERE attempt_ordinal = 2"
        )
        for ordinal in (3, 4):
            connection.execute(
                "INSERT INTO provider_attempts SELECT logical_call_key, ?, stage, "
                "candidate_id, model_key, provider, account, prompt_text, "
                "prompt_sha256, model_registry_sha256, reservation_usd, status, "
                "raw_response_json, normalized_response_json, "
                "reconstructed_result_json, input_tokens, output_tokens, "
                "actual_cost_usd, failure_type, failure_message, reserved_at, "
                "completed_at, authority_attempt_ordinal FROM provider_attempts "
                "WHERE attempt_ordinal = 1",
                (ordinal,),
            )
    with pytest.raises(cli.CommandError, match="reconstruction_failed provider call"):
        cli._verified_provider_stage_attempts(
            stage="llm-review-stage-a",
            journal_path=over_limit_path,
            expected_prompts=expected,
            providers_by_model=providers,
            model_registry_sha256="registry-sha",
            expected_nonsettled_statuses={
                ("cand-1", "google:reviewer"): "reconstruction_failed"
            },
            expected_nonsettled_attempt_counts={("cand-1", "google:reviewer"): 4},
        )


def test_earlier_provider_shard_run_card_verifies_after_later_journal_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider-attempts.sqlite3"
    registry_path = tmp_path / "registry.json"
    google_entry = replace(
        _registry_entry(),
        provider="google",
        model_id="judge",
        display_name="Google Judge",
        model_version_or_snapshot="google-judge-2026-07-01",
    )
    openai_entry = replace(
        _registry_entry(),
        model_id="judge",
        display_name="OpenAI Judge",
        model_version_or_snapshot="openai-judge-2026-07-01",
    )
    _write_json(registry_path, [google_entry.to_record(), openai_entry.to_record()])
    entries, registry_sha = cli._registry_entries_for_keys(
        registry_path,
        (google_entry.registry_key, openai_entry.registry_key),
    )

    def append_shard_attempt(*, provider: str, model_key: str, prompt: str) -> str:
        with ProviderAttemptJournal(
            path,
            identity=ProviderCallIdentity(
                stage="llm-label",
                candidate_id="cand-1",
                model_key=model_key,
                prompt=prompt,
                model_registry_sha256=registry_sha,
            ),
            provider=provider,
            reservation_usd=0.1,
            cycle_cap_usd=10.0,
            cycle_id="cycle-1",
            provider_cycle_caps_sha256="sha256:caps",
        ) as journal:
            journal.run_attempt(1, lambda: {"fixture": provider})
            journal.settle_attempt(
                1,
                input_tokens=1,
                output_tokens=1,
                actual_cost_usd=0.01,
                raw_output="{}",
            )
            journal.commit_reconstruction({"labels": []})
        return hashlib.sha256(prompt.encode()).hexdigest()

    google_prompt_sha = append_shard_attempt(
        provider="google",
        model_key=google_entry.registry_key,
        prompt="google frozen label prompt",
    )
    google_expected = {("cand-1", google_entry.registry_key): google_prompt_sha}
    google_commitment_at_completion = cli._verified_provider_stage_attempts(
        stage="llm-label",
        journal_path=path,
        expected_prompts=google_expected,
        providers_by_model={google_entry.registry_key: google_entry.provider},
        model_registry_sha256=registry_sha,
        allow_additional_calls=True,
    )

    lineage = cast(
        cli._StageAUnitizationLineage,
        SimpleNamespace(
            provider_journal_path=path,
            cohort_cycle_id="cycle-1",
            provider_caps_sha256="sha256:caps",
        ),
    )
    provider_chain_at_completion = cli._provider_chain_commitment(
        lineage=lineage,
        stage_attempts=google_commitment_at_completion,
    )

    append_shard_attempt(
        provider="openai",
        model_key=openai_entry.registry_key,
        prompt="openai frozen label prompt",
    )
    assert google_commitment_at_completion["attempt_count"] == 1

    source_paths = {
        name: tmp_path / f"{name}.json"
        for name in (
            "selection",
            "parser_manifest",
            "decision_texts",
            "decision_texts_manifest",
            "decision_texts_run_card",
            "finalized_prediction_units",
            "llm_unitization_run_card",
            "llm_review_stage_a_run_card",
            "unitization_review_run_card",
            "evaluated_model_registry",
            "provider_cycle_caps",
        )
    }
    for source_path in source_paths.values():
        _write_json(source_path, {})
    labels_path = tmp_path / "google-labels.jsonl"
    audit_path = tmp_path / "google-audit.jsonl"
    lawyer_queue_path = tmp_path / "google-lawyer-queue.jsonl"
    _write_jsonl(labels_path, [])
    _write_jsonl(
        audit_path,
        [
            {
                "candidate_id": "cand-1",
                "execution_provider": google_entry.provider,
                "model_outputs": [
                    {
                        "model_key": google_entry.registry_key,
                        "provider_prompt_sha256": google_prompt_sha,
                    }
                ],
            }
        ],
    )
    _write_jsonl(lawyer_queue_path, [])
    run_card_path = tmp_path / "google-shard-run-card.json"
    _write_json(
        run_card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "llm-label-provider-shard",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": True,
            "paid_activity_executed": True,
            "source_commitments": {
                **{
                    name: cli._stage_a_file_commitment(source_path)
                    for name, source_path in source_paths.items()
                },
                "model_registry": cli._stage_a_file_commitment(registry_path),
            },
            "output_commitments": {
                "labels": cli._stage_a_file_commitment(labels_path),
                "audit": cli._stage_a_file_commitment(audit_path),
                "lawyer_review_queue": cli._stage_a_file_commitment(lawyer_queue_path),
            },
            "model_execution": {
                "model_keys": [entry.registry_key for entry in entries],
                "executed_model_keys": [google_entry.registry_key],
                "model_entry_sha256": {
                    entry.registry_key: "sha256:"
                    + cli.model_registry_entry_sha256(entry)
                    for entry in entries
                },
                "model_registry_sha256": registry_sha,
                "providers": {entry.registry_key: entry.provider for entry in entries},
                "execution_provider": google_entry.provider,
                "provider_shard_merge": False,
            },
            "provider_chain": provider_chain_at_completion,
        },
    )

    assert (
        cli._verify_llm_label_provider_shard_run_card(
            run_card_path,
            audit_path=audit_path,
            lineage=lineage,
            selection_path=source_paths["selection"],
            parser_manifest_path=source_paths["parser_manifest"],
            decision_texts_path=source_paths["decision_texts"],
            decision_texts_manifest_path=source_paths["decision_texts_manifest"],
            decision_texts_run_card_path=source_paths["decision_texts_run_card"],
            finalized_prediction_units_path=source_paths["finalized_prediction_units"],
            llm_unitization_run_card_path=source_paths["llm_unitization_run_card"],
            llm_review_stage_a_run_card_path=source_paths[
                "llm_review_stage_a_run_card"
            ],
            unitization_review_run_card_path=source_paths[
                "unitization_review_run_card"
            ],
            model_registry_path=registry_path,
            evaluated_model_registry_path=source_paths["evaluated_model_registry"],
            provider_cycle_caps_path=source_paths["provider_cycle_caps"],
        )
        == google_entry.provider
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
        file_snapshots={},
        document_tree={},
        markdown_bytes={},
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
