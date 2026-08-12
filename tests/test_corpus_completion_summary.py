"""Closed-schema tests for terminal Cycle corpus summaries."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicy,
    CaseDevPurchaseSnapshot,
    canonical_purchase_state_sha256,
    initialize_case_dev_purchase_journal,
    read_case_dev_purchase_snapshot,
    summarize_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.corpus_completion_summary import (
    CorpusCompletionSummaryError,
    CorpusCompletionSummaryInputs,
    build_corpus_completion_summary,
    require_completion_inputs_unchanged,
)
from tests.purchase_approval_fixtures import (
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))
    return path


def build_completion_inputs(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    stage_a_queue: tuple[dict[str, object], ...] = (),
    stage_a_adjudications: tuple[dict[str, object], ...] = (),
    terminal_stage_a_queue: tuple[dict[str, object], ...] | None = None,
    terminal_stage_a_adjudications: tuple[dict[str, object], ...] | None = None,
    stage_b_queue: tuple[dict[str, object], ...] = (),
    stage_b_audit: tuple[dict[str, object], ...] = (),
    bead_references: tuple[str, ...] = (),
) -> CorpusCompletionSummaryInputs:
    projection = build_completed_projection_fixture(
        tmp_path / "projection-fixture", monkeypatch=monkeypatch
    )
    approved = build_approved_purchase_fixture(
        tmp_path / "purchase-authority",
        target_cohort_root=projection.root,
    )
    policy_payload = approved.policy.read_bytes()
    cohort_payload = approved.cohort_policy.read_bytes()
    policy = verify_case_dev_purchase_policy(json.loads(policy_payload))
    initialization = initialize_case_dev_purchase_journal(
        approved.ledger,
        policy=policy,
        receipt_path=approved.initialization_receipt,
        purchase_policy_file_sha256=(
            "sha256:" + hashlib.sha256(policy_payload).hexdigest()
        ),
        cohort_policy_file_sha256=(
            "sha256:" + hashlib.sha256(cohort_payload).hexdigest()
        ),
        initialized_at="2026-08-06T12:00:00Z",
        controlled_private_root=approved.controlled_private_root,
    )
    root = tmp_path / "terminal"
    stage_a_queue_path = root / "stage-a-queue.jsonl"
    stage_a_adjudications_path = root / "stage-a-adjudications.jsonl"
    stage_b_queue_path = root / "stage-b-queue.jsonl"
    stage_b_audit_path = root / "stage-b-audit.jsonl"
    terminal_stage_a_queue_path = root / "terminal-stage-a-queue.jsonl"
    terminal_stage_a_adjudications_path = root / "terminal-stage-a-adjudications.jsonl"
    for path, records in (
        (stage_a_queue_path, stage_a_queue),
        (stage_a_adjudications_path, stage_a_adjudications),
        (stage_b_queue_path, stage_b_queue),
        (stage_b_audit_path, stage_b_audit),
        *(
            (
                (terminal_stage_a_queue_path, terminal_stage_a_queue),
                (
                    terminal_stage_a_adjudications_path,
                    terminal_stage_a_adjudications,
                ),
            )
            if terminal_stage_a_queue is not None
            and terminal_stage_a_adjudications is not None
            else ()
        ),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"".join(
                (
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
                for record in records
            )
        )
    registry = root / "model-registry.json"
    registry.write_bytes(Path("model_registries/cycle-1-2026-06-30.json").read_bytes())
    readiness_path = root / "corpus-readiness.json"
    exclusion_path = root / "complete-exclusion-ledger.jsonl"
    exclusion_path.write_bytes(b"")
    readiness = {
        "required_clean_count": 2,
        "clean_count": 2,
        "meets_target": True,
        "clean_candidate_ids": ["case-001", "case-002"],
        "excluded_candidate_ids": [],
        "exclusion_reasons": {},
        "funnel": {
            "selected": 2,
            "parsed_complete": 2,
            "unitized_complete": 2,
            "labeled_complete": 2,
            "packet_inputs": 2,
            "packets_built": 2,
            "excluded": 0,
            "clean": 2,
        },
        "case_mix": {
            "court": {"cand": 2},
            "nature_of_suit": {"contract": 2},
            "nos_macro_category": {"contract": 2},
            "related_family_id": {"none": 2},
            "mdl_family_id": {"none": 2},
            "case_type_stratum": {"district_civil": 2},
        },
        "screening_snapshot_reconciliation": {
            "accepted_count": 2,
            "excluded_count": 0,
            "processed_count": 2,
        },
        "target_cohort_preparation": {"target_case_count": 2},
    }
    _write_json(readiness_path, readiness)
    materialization_path = root / "materialization-summary.json"
    purchase_state_sha256 = str(initialization["purchase_state_sha256"])
    materialization: dict[str, object] = {
        "target_case_count": 2,
        "document_count": 2,
        "free_document_count": 2,
        "purchased_document_count": 0,
        "content_addressed": True,
        "source_roots_mutated": False,
        "source_commitments": {"purchase_state_sha256": purchase_state_sha256},
    }
    materialization_payload = _json_bytes(materialization)
    materialization_path.write_bytes(materialization_payload)
    materialization_card_path = root / "materialization-run-card.json"
    _write_json(
        materialization_card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "materialize-cohort-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "zero_provider_activity_evidence": True,
            "target_case_count": 2,
            "record_count": 2,
            "free_document_count": 2,
            "purchased_document_count": 0,
            "source_roots_mutated": False,
            "source_commitments": {"purchase_state_sha256": purchase_state_sha256},
            "output_commitments": {
                "materialization_summary": {
                    "path": str(materialization_path.resolve()),
                    "sha256": hashlib.sha256(materialization_payload).hexdigest(),
                }
            },
        },
    )
    finalize_path = root / "finalize-run-card.json"
    finalize_summary_inputs = {
        "materialization_run_card": materialization_card_path,
        "model_registry": registry,
        "unitization_review_queue": stage_a_queue_path,
        "unitization_adjudications": stage_a_adjudications_path,
        "lawyer_review_queue": stage_b_queue_path,
        "lawyer_review_audit": stage_b_audit_path,
    }
    if (
        terminal_stage_a_queue is not None
        and terminal_stage_a_adjudications is not None
    ):
        finalize_summary_inputs.update(
            {
                "unitizer_terminal_review_queue": terminal_stage_a_queue_path,
                "unitizer_terminal_adjudications": (
                    terminal_stage_a_adjudications_path
                ),
            }
        )
    _write_json(
        finalize_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "finalize-corpus",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "record_count": 2,
            "target_clean_cases": 2,
            "clean_count": 2,
            "meets_target": True,
            "input_paths": [
                str(path.resolve()) for path in finalize_summary_inputs.values()
            ],
            "completion_summary_input_commitments": {
                name: {
                    "path": str(path.resolve()),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "byte_count": len(path.read_bytes()),
                }
                for name, path in finalize_summary_inputs.items()
            },
            "output_paths": [
                str(readiness_path.resolve()),
                str(exclusion_path.resolve()),
            ],
        },
    )
    return CorpusCompletionSummaryInputs(
        finalize_run_card=finalize_path,
        corpus_readiness=readiness_path,
        complete_exclusion_ledger=exclusion_path,
        materialization_summary=materialization_path,
        materialization_run_card=materialization_card_path,
        purchase_policy=approved.policy,
        cohort_policy=approved.cohort_policy,
        purchase_ledger=approved.ledger,
        purchase_ledger_initialization_receipt=approved.initialization_receipt,
        model_registry=registry,
        unitization_review_queue=stage_a_queue_path,
        unitization_adjudications=stage_a_adjudications_path,
        lawyer_review_queue=stage_b_queue_path,
        lawyer_review_audit=stage_b_audit_path,
        unitizer_terminal_review_queue=(
            terminal_stage_a_queue_path if terminal_stage_a_queue is not None else None
        ),
        unitizer_terminal_adjudications=(
            terminal_stage_a_adjudications_path
            if terminal_stage_a_adjudications is not None
            else None
        ),
        adjudication_beads=bead_references,
    )


def test_v2_summary_authenticates_and_counts_terminal_stage_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "ordinary-review"},),
        stage_a_adjudications=(
            {
                "adjudication_id": "ordinary-adjudication",
                "review_ids": ["ordinary-review"],
            },
        ),
        terminal_stage_a_queue=({"review_id": "terminal-review"},),
        terminal_stage_a_adjudications=(
            {
                "adjudication_id": "terminal-adjudication",
                "review_ids": ["terminal-review"],
            },
        ),
    )

    summary = build_corpus_completion_summary(inputs)

    assert summary["schema_version"] == "legalforecast.corpus_completion_summary.v2"
    assert summary["adjudication"] == {
        "stage_a_queue_count": 2,
        "stage_a_adjudication_count": 2,
        "stage_a_pending_count": 0,
        "stage_a_pending_review_ids": [],
        "stage_a_ordinary_queue_count": 1,
        "stage_a_ordinary_adjudication_count": 1,
        "stage_a_ordinary_pending_count": 0,
        "stage_a_ordinary_pending_review_ids": [],
        "stage_a_terminal_queue_count": 1,
        "stage_a_terminal_adjudication_count": 1,
        "stage_a_terminal_pending_count": 0,
        "stage_a_terminal_pending_review_ids": [],
        "stage_b_queue_count": 0,
        "stage_b_resolved_count": 0,
        "stage_b_pending_count": 0,
        "stage_b_pending_review_ids": [],
        "pending_count": 0,
        "pending_bead_references": {},
        "queue_empty_or_fully_adjudicated": True,
    }


def test_v2_summary_rejects_cross_surface_review_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "duplicate"},),
        terminal_stage_a_queue=({"review_id": "duplicate"},),
        terminal_stage_a_adjudications=(),
        bead_references=("duplicate=bead-1",),
    )

    with pytest.raises(
        CorpusCompletionSummaryError, match="both ordinary and terminal"
    ):
        build_corpus_completion_summary(inputs)


def test_v2_summary_reports_pending_by_stage_a_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "ordinary-pending"},),
        terminal_stage_a_queue=({"review_id": "terminal-pending"},),
        terminal_stage_a_adjudications=(),
        bead_references=(
            "ordinary-pending=bead-ordinary",
            "terminal-pending=bead-terminal",
        ),
    )

    adjudication = build_corpus_completion_summary(inputs)["adjudication"]
    assert isinstance(adjudication, dict)
    assert adjudication["stage_a_ordinary_pending_count"] == 1
    assert adjudication["stage_a_ordinary_pending_review_ids"] == ["ordinary-pending"]
    assert adjudication["stage_a_terminal_pending_count"] == 1
    assert adjudication["stage_a_terminal_pending_review_ids"] == ["terminal-pending"]
    assert adjudication["stage_a_pending_count"] == 2


def test_v2_summary_rejects_cross_surface_adjudication_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "ordinary-review"},),
        stage_a_adjudications=(
            {"adjudication_id": "duplicate", "review_ids": ["ordinary-review"]},
        ),
        terminal_stage_a_queue=({"review_id": "terminal-review"},),
        terminal_stage_a_adjudications=(
            {"adjudication_id": "duplicate", "review_ids": ["terminal-review"]},
        ),
    )

    with pytest.raises(
        CorpusCompletionSummaryError, match="both ordinary and terminal streams"
    ):
        build_corpus_completion_summary(inputs)


def test_v2_summary_rejects_cross_surface_adjudication_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "ordinary-review"},),
        terminal_stage_a_queue=({"review_id": "terminal-review"},),
        terminal_stage_a_adjudications=(
            {
                "adjudication_id": "terminal-adjudication",
                "review_ids": ["ordinary-review"],
            },
        ),
        bead_references=(
            "ordinary-review=bead-ordinary",
            "terminal-review=bead-terminal",
        ),
    )

    with pytest.raises(CorpusCompletionSummaryError, match="unknown queue row"):
        build_corpus_completion_summary(inputs)


def test_v2_summary_requires_paired_terminal_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)

    with pytest.raises(CorpusCompletionSummaryError, match="supplied together"):
        replace(
            inputs,
            unitizer_terminal_review_queue=inputs.unitization_review_queue,
        )


def test_v2_summary_rejects_terminal_commitment_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        terminal_stage_a_queue=({"review_id": "terminal-review"},),
        terminal_stage_a_adjudications=(),
        bead_references=("terminal-review=bead-terminal",),
    )
    assert inputs.unitizer_terminal_review_queue is not None
    inputs.unitizer_terminal_review_queue.write_text(
        '{"review_id":"terminal-review-changed"}\n'
    )

    with pytest.raises(CorpusCompletionSummaryError, match="byte commitment"):
        build_corpus_completion_summary(inputs)


def test_summary_authenticates_terminal_inputs_and_empty_queues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)

    summary = build_corpus_completion_summary(inputs)

    assert summary["target"] == {
        "required_clean_count": 2,
        "clean_count": 2,
        "meets_target": True,
        "eligibility_anchor": "2026-06-30",
    }
    assert summary["adjudication"] == {
        "stage_a_queue_count": 0,
        "stage_a_adjudication_count": 0,
        "stage_a_pending_count": 0,
        "stage_a_pending_review_ids": [],
        "stage_b_queue_count": 0,
        "stage_b_resolved_count": 0,
        "stage_b_pending_count": 0,
        "stage_b_pending_review_ids": [],
        "pending_count": 0,
        "pending_bead_references": {},
        "queue_empty_or_fully_adjudicated": True,
    }
    assert summary["provider_activity_executed"] is False
    require_completion_inputs_unchanged(inputs, summary=summary)


def test_pending_reviews_require_exact_review_to_bead_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "stage-a-1"},),
    )
    with pytest.raises(CorpusCompletionSummaryError, match="exactly cover"):
        build_corpus_completion_summary(inputs)

    mapped = replace(
        inputs,
        adjudication_beads=("stage-a-1=LegalForecastBench-review-1",),
    )
    summary = build_corpus_completion_summary(mapped)
    adjudication = summary["adjudication"]
    assert isinstance(adjudication, dict)
    assert adjudication["pending_bead_references"] == {
        "stage-a-1": "LegalForecastBench-review-1"
    }

    extra = replace(
        inputs,
        adjudication_beads=(
            "stage-a-1=LegalForecastBench-review-1",
            "unrelated=LegalForecastBench-review-2",
        ),
    )
    with pytest.raises(CorpusCompletionSummaryError, match="exactly cover"):
        build_corpus_completion_summary(extra)


def test_stage_a_legacy_single_review_id_is_adjudicated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_a_queue=({"review_id": "stage-a-legacy"},),
        stage_a_adjudications=(
            {
                "adjudication_id": "adjudication-legacy",
                "review_id": "stage-a-legacy",
            },
        ),
    )

    summary = build_corpus_completion_summary(inputs)

    adjudication = summary["adjudication"]
    assert isinstance(adjudication, dict)
    assert adjudication["stage_a_pending_count"] == 0


def test_stage_b_terminal_queue_status_is_resolved_without_audit_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_b_queue=({"review_id": "stage-b-1", "status": "resolved"},),
    )

    summary = build_corpus_completion_summary(inputs)

    adjudication = summary["adjudication"]
    assert isinstance(adjudication, dict)
    assert adjudication["stage_b_resolved_count"] == 1
    assert adjudication["stage_b_pending_count"] == 0


def test_stage_b_non_string_audit_status_is_domain_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(
        tmp_path,
        monkeypatch=monkeypatch,
        stage_b_queue=({"review_id": "stage-b-1"},),
        stage_b_audit=({"review_id": "stage-b-1", "status": ["resolved"]},),
        bead_references=("stage-b-1=LegalForecastBench-review-1",),
    )

    with pytest.raises(CorpusCompletionSummaryError, match="audit status is invalid"):
        build_corpus_completion_summary(inputs)


def test_finalize_byte_commitment_rejects_changed_summary_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    inputs.lawyer_review_audit.write_bytes(b"\n")

    with pytest.raises(CorpusCompletionSummaryError, match="byte commitment"):
        build_corpus_completion_summary(inputs)


def test_static_input_drift_is_rejected_after_summary_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    summary = build_corpus_completion_summary(inputs)
    inputs.lawyer_review_audit.write_text('{"review_id":"late"}\n')

    with pytest.raises(CorpusCompletionSummaryError, match="source changed"):
        require_completion_inputs_unchanged(inputs, summary=summary)


def test_materialization_byte_tamper_is_rejected_by_bound_run_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    materialization = json.loads(inputs.materialization_summary.read_bytes())
    materialization["free_document_count"] = 1
    materialization["purchased_document_count"] = 1
    inputs.materialization_summary.write_bytes(_json_bytes(materialization))

    with pytest.raises(
        CorpusCompletionSummaryError,
        match=r"materialization (run card is inconsistent|summary differs)",
    ):
        build_corpus_completion_summary(inputs)


def test_purchase_ledger_operation_drift_is_rejected_after_summary_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    summary = build_corpus_completion_summary(inputs)
    with sqlite3.connect(inputs.purchase_ledger) as connection:
        connection.execute(
            """INSERT INTO purchase_operations(
            source_document_id, candidate_id, reservation_usd, status)
            VALUES ('late-doc', 'case-001', '3.05', 'planned')"""
        )
        connection.execute(
            """INSERT INTO purchase_material_state(
            source_document_id, authority, status)
            VALUES ('late-doc', 'ordinary_public', 'not_recovered')"""
        )

    with pytest.raises(CorpusCompletionSummaryError, match="purchase ledger changed"):
        require_completion_inputs_unchanged(inputs, summary=summary)


def test_build_reauthenticates_purchase_ledger_before_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    original = read_case_dev_purchase_snapshot
    calls = 0

    def mutate_after_first_snapshot(
        path: str | Path,
        *,
        policy: CaseDevPurchasePolicy,
        controlled_private_root: Path | None = None,
        initialization_receipt_path: Path | None = None,
    ) -> CaseDevPurchaseSnapshot:
        nonlocal calls
        snapshot = original(
            path,
            policy=policy,
            controlled_private_root=controlled_private_root,
            initialization_receipt_path=initialization_receipt_path,
        )
        calls += 1
        if calls == 1:
            with sqlite3.connect(inputs.purchase_ledger) as connection:
                connection.execute(
                    """INSERT INTO purchase_operations(
                    source_document_id, candidate_id, reservation_usd, status)
                    VALUES ('late-doc', 'case-001', '3.05', 'planned')"""
                )
                connection.execute(
                    """INSERT INTO purchase_material_state(
                    source_document_id, authority, status)
                    VALUES ('late-doc', 'ordinary_public', 'not_recovered')"""
                )
        return snapshot

    monkeypatch.setattr(
        "legalforecast.ingestion.corpus_completion_summary."
        "read_case_dev_purchase_snapshot",
        mutate_after_first_snapshot,
    )

    with pytest.raises(CorpusCompletionSummaryError, match="purchase ledger"):
        build_corpus_completion_summary(inputs)
    assert calls == 2


def test_canonical_spend_distinguishes_actual_from_unresolved_obligations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    policy = verify_case_dev_purchase_policy(
        json.loads(inputs.purchase_policy.read_bytes())
    )
    operations = (
        {
            "source_document_id": "doc-queued",
            "candidate_id": "case-001",
            "reservation_usd": "3.05",
            "status": "queued",
            "operation_key": "operation-queued",
            "actual_usd": None,
            "response": {"queue_id": "queue-1"},
            "error": None,
            "reconciliation": None,
            "material_authority": "ordinary_public",
            "material_state": "not_recovered",
            "material_evidence": {},
            "resolved_document_sha256": None,
        },
    )
    committed = "3.05"
    snapshot = CaseDevPurchaseSnapshot(
        operations=operations,
        committed_amount_usd=committed,
        purchase_state_sha256=canonical_purchase_state_sha256(
            policy,
            committed_amount_usd=committed,
            operations=operations,
        ),
    )

    spend = summarize_case_dev_purchase_snapshot(policy=policy, snapshot=snapshot)

    assert spend.known_actual_operation_spend_usd == "0.00"
    assert spend.actual_spend_complete is False
    assert spend.actual_spend_usd is None
    assert spend.cap_counted_committed_spend_usd == "3.05"
    assert spend.unresolved_cap_counted_usd == "3.05"
    assert spend.unresolved_billing_document_ids == ("doc-queued",)
