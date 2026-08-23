# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import tests.test_target_100_acquisition as t100
from legalforecast import cli
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    initialize_case_dev_purchase_journal,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.disclosure_review_authority import (
    disclosure_authority_identity_from_cohort_policy,
)
from legalforecast.ingestion.missing_core_budget import rank_missing_core_document_plans
from legalforecast.ingestion.public_packet_planner import PublicPacketDocumentPlan
from tests.disclosure_review_fixtures import (
    service_disclosure_authority_from_policy_bytes,
)
from tests.purchase_approval_fixtures import (
    build_approved_purchase_fixture,
    sha256_uri,
)
from tests.test_docket_decision_text_source import _terminal_failure_authority
from tests.test_target_cohort_projection import _write_provenance_clearance

_POOL_COUNT = 105
_TARGET_COUNT = 100
_FROZEN_IDS = (
    "1103",
    "1104",
    "1099",
)
_RESIDUAL_IDS = (
    "1000",
    "1001",
    "1002",
)
_PAID_RESERVE_DOCKETS = frozenset({1100, 1101, 1102})
_MAX_BUDGET_USD = "15.25"


@pytest.fixture(autouse=True)
def _allow_signed_service_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Permit the existing signed, provider-free materialization fixture."""
    validate = cli.validate_review_receipt
    validate_lineage = cli.validate_authenticated_clearance_lineage
    monkeypatch.setattr(
        cli,
        "validate_review_receipt",
        lambda *positional, **keywords: validate(
            *positional,
            **{**keywords, "allow_test_service_identity": True},
        ),
    )
    monkeypatch.setattr(
        cli,
        "validate_authenticated_clearance_lineage",
        lambda *positional, **keywords: validate_lineage(
            *positional,
            **{**keywords, "allow_test_service_identity": True},
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_main_disclosure_review_authority",
        lambda cohort, *, reviewer_policy_bytes: (
            service_disclosure_authority_from_policy_bytes(
                reviewer_policy_bytes,
                identity=disclosure_authority_identity_from_cohort_policy(cohort),
            )
        ),
    )


_ORIGINAL_SCREENED = t100._screened_case
_ORIGINAL_HTML = t100._target_fixture_docket_html
_ORIGINAL_RANK = rank_missing_core_document_plans


def _rank_by_candidate_id(
    filter_results: object, **kwargs: object
) -> tuple[object, ...]:
    plans = _ORIGINAL_RANK(filter_results, **kwargs)  # type: ignore[arg-type]
    return tuple(sorted(plans, key=lambda plan: plan.candidate_id))


def _install_unpatched_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "legalforecast.ingestion.missing_core_budget.rank_missing_core_document_plans",
        _rank_by_candidate_id,
    )
    monkeypatch.setattr(
        "legalforecast.ingestion.target_cohort_projection.rank_missing_core_document_plans",
        _rank_by_candidate_id,
    )
    monkeypatch.setattr(
        "legalforecast.cli.rank_missing_core_document_plans",
        _rank_by_candidate_id,
    )
    generate_policy = cli.generate_cohort_policy

    def generate_matching_caps(decisions: Mapping[str, Any]) -> object:
        payload = dict(decisions)
        purchase = payload.get("purchase_policy")
        if isinstance(purchase, Mapping):
            purchase = dict(purchase)
            if purchase.get("cycle_budget_usd") == _MAX_BUDGET_USD:
                purchase["max_per_case_usd"] = _MAX_BUDGET_USD
            payload["purchase_policy"] = purchase
        return generate_policy(payload)

    monkeypatch.setattr(cli, "generate_cohort_policy", generate_matching_caps)
    monkeypatch.setattr(
        "legalforecast.ingestion.zero_cost_successor.FROZEN_ZERO_COST_CANDIDATE_IDS",
        _FROZEN_IDS,
    )
    emit_public_document = PublicPacketDocumentPlan.to_record

    def emit_predecision_public_document(
        plan: PublicPacketDocumentPlan,
    ) -> dict[str, Any]:
        record = emit_public_document(plan)
        record["is_predecision_material"] = (
            record.get("contains_target_outcome") is not True
        )
        return record

    monkeypatch.setattr(
        PublicPacketDocumentPlan,
        "to_record",
        emit_predecision_public_document,
    )

    def screened(index: int) -> dict[str, object]:
        record = _ORIGINAL_SCREENED(index)
        docket_id = 1000 + index
        if docket_id in _PAID_RESERVE_DOCKETS:
            return record
        mtd = cast(list[dict[str, Any]], record["selected_entries"])[1]
        mtd["text"] = "MOTION to Dismiss and memorandum in support filed by Defendant."
        document = cast(list[dict[str, Any]], mtd["documents"])[0]
        document["href"] = f"https://storage.courtlistener.com/{docket_id}-mtd.pdf"
        document["action_label"] = "Download PDF"
        document["pacer_only"] = False
        document["description"] = "Memorandum in Support of Motion to Dismiss"
        return record

    def html(docket_id: int) -> str:
        if docket_id in _PAID_RESERVE_DOCKETS:
            return _ORIGINAL_HTML(docket_id)
        pacer = (
            '<a class="open_buy_pacer_modal" '
            f'href="https://ecf.nysd.uscourts.gov/doc1/{docket_id}">'
        )
        free = f'<a href="https://storage.courtlistener.com/{docket_id}-mtd.pdf">'
        return (
            _ORIGINAL_HTML(docket_id)
            .replace(pacer, free)
            .replace("Buy on PACER", "Download PDF")
            .replace(
                "MOTION to Dismiss filed by Defendant.",
                "MOTION to Dismiss and memorandum in support filed by Defendant.",
            )
            .replace(
                "<p>Motion to Dismiss</p>",
                "<p>Memorandum in Support of Motion to Dismiss</p>",
            )
        )

    monkeypatch.setattr(t100, "_screened_case", screened)
    monkeypatch.setattr(t100, "_target_fixture_docket_html", html)


def _completed_original_projection(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    root.mkdir(parents=True)
    preparation = root / "preparation"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        t100._target_100_fixture(root / "fixture", case_count=_POOL_COUNT)
    )
    documents = json.loads(fixture_documents.read_text(encoding="utf-8"))
    for index in range(_POOL_COUNT):
        docket_id = 1000 + index
        if docket_id in _PAID_RESERVE_DOCKETS:
            continue
        documents[f"https://storage.courtlistener.com/{docket_id}-mtd.pdf"] = (
            t100._fixture_pdf_text("Motion to Dismiss")
        )
    fixture_documents.write_text(json.dumps(documents), encoding="utf-8")
    recorded = [
        line
        for line in courtlistener_fixture.read_text(encoding="utf-8").splitlines()
        if line
    ]
    courtlistener_fixture.write_text(
        "\n".join(recorded[100 * 3 : 103 * 3]) + "\n",
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(preparation),
                "--snapshot",
                str(snapshot),
                "--expected-snapshot-manifest-sha256",
                hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest(),
                "--expected-cycle-hash",
                cycle_hash,
                "--target-case-count",
                str(_TARGET_COUNT),
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--max-projected-budget-usd",
                _MAX_BUDGET_USD,
                "--execute",
            ]
        )
        == 0
    )
    free_manifest = preparation / "03c-merged-downloads/document-downloads-merged.jsonl"
    free_restrictions = preparation / "06-clearance-inputs/restriction-evidence.jsonl"
    review = t100._write_authenticated_reviews(
        root / "free-review",
        manifest_path=free_manifest,
        document_root=preparation / "documents/free",
        review_requests_path=(
            preparation / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
        restriction_evidence_path=free_restrictions,
        store_uri="private-store://fixture/exact100-stage-a-replay",
    )
    clearance_root = root / "free-clearance"
    _write_provenance_clearance(
        root / "free-provenance",
        manifest_path=free_manifest,
        review_requests_path=review.requests,
        case_relevance_path=preparation / "03-gap-bridge/case-relevance.jsonl",
        restriction_evidence_path=free_restrictions,
        document_root=preparation / "documents/free",
        cohort_policy_path=review.cohort_policy,
        clearance_root=clearance_root,
        monkeypatch=monkeypatch,
    )
    projection = root / "projection"
    assert (
        cli.main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projection),
                "--selection",
                str(
                    preparation
                    / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(preparation / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(free_manifest),
                "--disclosure-clearance",
                str(clearance_root / "disclosure-clearance.jsonl"),
                "--clearance-run-card",
                str(clearance_root / "run-cards/clear-disclosures.json"),
                "--restriction-evidence",
                str(free_restrictions),
                "--preparation-summary",
                str(preparation / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(preparation / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-case-count",
                str(_TARGET_COUNT),
                "--max-projected-budget-usd",
                _MAX_BUDGET_USD,
                "--execute",
            ]
        )
        == 0
    )
    return {
        "projection": projection,
        "preparation": preparation,
        "snapshot": snapshot,
        "clearance": clearance_root / "disclosure-clearance.jsonl",
        "clearance_card": clearance_root / "run-cards/clear-disclosures.json",
    }


def _artifact(verified: Mapping[str, object], relative: str) -> bytes:
    root = cast(Path, verified["summary_path"]).parent
    snapshots = cast(Mapping[str, bytes], verified["verified_artifact_bytes"])
    return snapshots[os.path.abspath(root / relative)]


def _mtd_document_id(documents: list[dict[str, Any]]) -> str:
    for document in documents:
        role = str(document.get("document_role") or "")
        if "motion_to_dismiss" in role or role.startswith("mtd"):
            return str(document["source_document_id"])
    raise AssertionError("selected residual case is missing a motion to dismiss")


def test_unpatched_exact100_replay_binds_promotion_pool_and_stage_a_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_unpatched_geometry(monkeypatch)
    paths = _completed_original_projection(tmp_path / "original", monkeypatch)
    original_root = paths["projection"]
    original = cli.verify_completed_target_cohort_projection_for_purchase_approval(
        original_root
    )
    summary = cast(Mapping[str, object], original["summary"])
    assert summary["selected_case_count"] == _TARGET_COUNT
    assert summary["ranked_reserve_case_count"] == 5

    selection_bytes = _artifact(original, "target-cohort-selection.jsonl")
    selection_rows = [json.loads(line) for line in selection_bytes.splitlines() if line]
    selected = {
        str(row["candidate_id"]): cast(list[dict[str, Any]], row["documents"])
        for row in selection_rows
    }
    terminal_pairs = tuple(
        (candidate_id, _mtd_document_id(selected[candidate_id]), 6)
        for candidate_id in _RESIDUAL_IDS
    )
    assert len(terminal_pairs) == 3

    approval = build_approved_purchase_fixture(
        tmp_path / "purchase-v2-authority",
        target_cohort_root=original_root,
    )
    policy = verify_case_dev_purchase_policy(
        json.loads(approval.policy.read_text(encoding="utf-8"))
    )
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=approval.initialization_receipt,
        purchase_policy_file_sha256=sha256_uri(approval.policy.read_bytes()),
        cohort_policy_file_sha256=sha256_uri(approval.cohort_policy.read_bytes()),
        initialized_at="2026-08-04T19:00:00Z",
        controlled_private_root=approval.controlled_private_root,
    )
    result_path = tmp_path / "purchase-result.json"
    ranked_dir = tmp_path / "ranked"
    ranked_dir.mkdir()
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=False,
        controlled_private_root=approval.controlled_private_root,
        initialization_receipt_path=approval.initialization_receipt,
    ) as journal:
        _terminal_failure_authority(
            journal, result_path=result_path, terminal_pairs=terminal_pairs
        )
    ranked_result_path = ranked_dir / "ranked-reserve-result.json"
    assert (
        cli.main(
            [
                "acquisition",
                "plan-ranked-reserve-replacements",
                "--target-cohort-root",
                str(original_root),
                "--purchase-policy",
                str(approval.policy),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--purchase-ledger",
                str(approval.ledger),
                "--purchase-ledger-initialization-receipt",
                str(approval.initialization_receipt),
                "--purchase-result",
                str(result_path),
                "--purchase-run-card",
                str(result_path.with_name("purchase-run-card.json")),
                "--screening-snapshot-manifest",
                str(paths["snapshot"] / "manifest.json"),
                "--output",
                str(ranked_result_path),
                "--active-selection-output",
                str(ranked_dir / "active-selection.jsonl"),
                "--replacement-selection-output",
                str(ranked_dir / "replacement-selection.jsonl"),
                "--successor-exclusions-output",
                str(ranked_dir / "successor-exclusions.jsonl"),
                "--replacement-budget-plan-output",
                str(ranked_dir / "replacement-budget.json"),
            ]
        )
        == 0
    )

    successor_root = tmp_path / "zero-cost"
    assert (
        cli.main(
            [
                "acquisition",
                "project-zero-cost-successor",
                "--target-cohort-root",
                str(original_root),
                "--purchase-policy",
                str(approval.policy),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--purchase-ledger",
                str(approval.ledger),
                "--purchase-ledger-initialization-receipt",
                str(approval.initialization_receipt),
                "--purchase-result",
                str(result_path),
                "--purchase-run-card",
                str(result_path.with_name("purchase-run-card.json")),
                "--screening-snapshot-manifest",
                str(paths["snapshot"] / "manifest.json"),
                "--ranked-reserve-result",
                str(ranked_result_path),
                "--active-selection",
                str(ranked_dir / "active-selection.jsonl"),
                "--replacement-selection",
                str(ranked_dir / "replacement-selection.jsonl"),
                "--successor-exclusions",
                str(ranked_dir / "successor-exclusions.jsonl"),
                "--replacement-budget-plan",
                str(ranked_dir / "replacement-budget.json"),
                "--disclosure-clearance",
                str(paths["clearance"]),
                "--disclosure-clearance-run-card",
                str(paths["clearance_card"]),
                "--output-root",
                str(successor_root),
            ]
        )
        == 0
    )

    predecessor, promotion_pool = cli._replay_exact100_successor_inputs(successor_root)
    assert len(predecessor.selection) == _TARGET_COUNT
    assert promotion_pool.promotable_candidate_ids[:2]

    verified = cli._verify_zero_cost_successor_projection(
        target_root=successor_root,
        free_clearance_path=successor_root / "disclosure-clearance.jsonl",
        expected_target_count=_TARGET_COUNT,
    )
    card = verified["verified_successor_selection_card"]
    assert card.is_replay_minted()
    selection_path = cast(Path, verified["selection_path"])
    selection_bytes = cast(Mapping[str, bytes], verified["verified_artifact_bytes"])[
        os.path.abspath(selection_path)
    ]
    cli._validate_selection_run_card_commitment(
        cast(Mapping[str, Any], verified["run_card"]),
        selection_path=selection_path,
        selection_bytes=selection_bytes,
        selection_sha256=sha256_uri(selection_bytes),
        selection_record_count=_TARGET_COUNT,
        selection_run_card_path=cast(Path, verified["run_card_path"]),
        selection_run_card_bytes=cast(bytes, verified["run_card_bytes"]),
        verified_successor_selection_card=card,
    )

    core_filter = original_root / "core-filter-results.jsonl"
    before = core_filter.read_bytes()
    core_filter.write_bytes(b"{}\n")
    with pytest.raises(cli.CommandError):
        cli._replay_exact100_successor_inputs(successor_root)
    core_filter.write_bytes(before)
    ranked_reserve = original_root / "target-cohort-ranked-reserve.jsonl"
    ranked_reserve.write_bytes(ranked_reserve.read_bytes() + b"\n")
    with pytest.raises(cli.CommandError):
        cli._replay_exact100_successor_inputs(successor_root)
