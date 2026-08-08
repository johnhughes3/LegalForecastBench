from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli import main
from legalforecast.contracts import ARTIFACT_RAW_SHA256_V1, PURCHASE_SPEND_SUMMARY_V1
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    initialize_case_dev_purchase_journal,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.purchase_spend_summary import (
    PurchaseSpendSummaryError,
    build_purchase_spend_summary,
    purchase_spend_summary_bytes,
    write_purchase_spend_summary,
)
from tests.purchase_approval_fixtures import (
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)

PurchaseInputs = dict[str, Path]


def test_builds_an_authenticated_unavailable_actual_spend_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)

    summary = build_purchase_spend_summary(**inputs)

    assert summary["schema_version"] == str(PURCHASE_SPEND_SUMMARY_V1)
    reconciliation = summary["actual_charge_reconciliation"]
    assert reconciliation == {
        "classification": "actual_charge_unavailable",
        "reason": (
            "no authenticated provider billing evidence is present in the bound "
            "purchase result roots or purchase ledger"
        ),
        "unavailable_operation_count": 2,
        "unavailable_source_document_ids": ["doc-001", "doc-002"],
    }
    assert isinstance(reconciliation, dict)
    spend = summary["spend_summary"]
    assert isinstance(spend, dict)
    assert spend["known_actual_operation_spend_usd"] == "0.00"
    assert spend["actual_spend_complete"] is False
    assert spend["actual_spend_usd"] is None
    assert spend["unresolved_cap_counted_usd"] == "6.10"
    assert spend["cap_counted_committed_spend_usd"] == "6.10"
    assert spend["remaining_cap_headroom_usd"] == "2243.90"
    source_commitments = summary["source_commitments"]
    assert isinstance(source_commitments, dict)
    purchase_ledger = cast(Mapping[str, object], source_commitments["purchase_ledger"])
    assert purchase_ledger["operation_count"] == 2
    summary_sha256 = summary["summary_sha256"]
    assert isinstance(summary_sha256, str)
    assert len(summary_sha256) == 64


def test_uses_published_purchase_authority_without_private_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)

    summary = build_purchase_spend_summary(
        purchase_policy=inputs["purchase_policy"],
        cohort_policy=inputs["cohort_policy"],
        purchase_ledger=inputs["purchase_ledger"],
        purchase_ledger_initialization_receipt=inputs[
            "purchase_ledger_initialization_receipt"
        ],
        initial_purchase_result=inputs["initial_purchase_result"],
        replacement_purchase_result=inputs["replacement_purchase_result"],
    )

    assert summary["actual_charge_reconciliation"] == {
        "classification": "actual_charge_unavailable",
        "reason": (
            "no authenticated provider billing evidence is present in the bound "
            "purchase result roots or purchase ledger"
        ),
        "unavailable_operation_count": 2,
        "unavailable_source_document_ids": ["doc-001", "doc-002"],
    }


def test_rejects_purchase_root_that_omits_an_authenticated_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    replacement = Path(inputs["replacement_purchase_result"])
    payload = json.loads(replacement.read_text(encoding="utf-8"))
    payload["attempts"] = []
    payload["completed_purchase_count"] = 0
    payload["quarantined_material_count"] = 0
    payload["intended_purchase_count"] = 0
    replacement.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(PurchaseSpendSummaryError, match="do not exactly cover"):
        build_purchase_spend_summary(**inputs)


def test_rejects_provider_fee_without_ledger_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    initial = Path(inputs["initial_purchase_result"])
    payload = json.loads(initial.read_text(encoding="utf-8"))
    payload["attempts"][0]["fee_acknowledged"] = True
    payload["attempts"][0]["pacer_fees"] = {
        "pacer_fee_usd": "3.00",
        "service_fee_usd": "0.05",
        "total_usd": "3.05",
    }
    payload["attempts"][0]["status"] = "purchased"
    payload["executed_purchase_count"] = 1
    payload["quarantined_material_count"] = 0
    initial.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(PurchaseSpendSummaryError, match="billing evidence"):
        build_purchase_spend_summary(**inputs)


def test_uses_ledger_actuals_to_report_partial_unavailability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    ledger = Path(inputs["purchase_ledger"])
    policy = verify_case_dev_purchase_policy(
        json.loads(Path(inputs["purchase_policy"]).read_text(encoding="utf-8"))
    )
    with CaseDevPurchaseJournal(
        ledger,
        policy=policy,
        controlled_private_root=Path(inputs["controlled_private_root"]),
        initialization_receipt_path=Path(
            inputs["purchase_ledger_initialization_receipt"]
        ),
    ) as journal:
        journal.reconcile(
            {
                "source_document_id": "doc-001",
                "disposition": "confirmed",
                "source_type": "billing_receipt",
                "source_reference": "receipt-001",
                "pacer_fees": {
                    "pacerFee": "3.00",
                    "serviceFee": "0.05",
                    "total": "3.05",
                },
                "download_url": "https://example.test/doc-001.pdf",
            }
        )
    _write_purchase_result(
        Path(inputs["initial_purchase_result"]),
        [
            {
                **_attempt("doc-001"),
                "download_url": "https://example.test/doc-001.pdf",
                "fee_acknowledged": True,
                "pacer_fees": {
                    "pacer_fee_usd": "3.00",
                    "service_fee_usd": "0.05",
                    "total_usd": "3.05",
                },
                "status": "purchased",
            }
        ],
    )

    summary = build_purchase_spend_summary(**inputs)

    assert summary["actual_charge_reconciliation"] == {
        "classification": "actual_charge_partially_unavailable",
        "reason": (
            "authenticated provider billing evidence is present only for reconciled "
            "operations; the listed operations remain unresolved"
        ),
        "unavailable_operation_count": 1,
        "unavailable_source_document_ids": ["doc-002"],
    }


def test_rejects_malformed_provider_fee_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    initial = Path(inputs["initial_purchase_result"])
    payload = json.loads(initial.read_text(encoding="utf-8"))
    payload["attempts"][0]["pacer_fees"] = "3.05"
    initial.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(PurchaseSpendSummaryError, match="PACER fees must be an object"):
        build_purchase_spend_summary(**inputs)


def test_rejects_purchase_result_counter_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    initial = Path(inputs["initial_purchase_result"])
    payload = json.loads(initial.read_text(encoding="utf-8"))
    payload["executed_purchase_count"] = 1
    initial.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(PurchaseSpendSummaryError, match="completion counts"):
        build_purchase_spend_summary(**inputs)


def test_rejects_semantically_equivalent_policy_with_wrong_receipt_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    policy = Path(inputs["purchase_policy"])
    policy.write_bytes(b"\n" + policy.read_bytes())

    with pytest.raises(PurchaseSpendSummaryError, match="differs from current bytes"):
        build_purchase_spend_summary(**inputs)


def test_write_is_immutable_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    summary = build_purchase_spend_summary(**inputs)
    output = tmp_path / "output" / "purchase-spend-summary.json"
    output.parent.mkdir()

    first = write_purchase_spend_summary(output, summary)
    second = write_purchase_spend_summary(output, summary)

    assert first == second == summary["summary_sha256"]
    assert output.read_bytes() == purchase_spend_summary_bytes(summary)
    modified = dict(summary)
    modified["cycle_id"] = "other-cycle"
    body = {key: value for key, value in modified.items() if key != "summary_sha256"}
    modified["summary_sha256"] = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            body,
            domain=PURCHASE_SPEND_SUMMARY_V1,
        ).digest
    )
    with pytest.raises(PurchaseSpendSummaryError, match="different bytes"):
        write_purchase_spend_summary(output, modified)


def test_write_rejects_symlinked_or_hardlinked_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    summary = build_purchase_spend_summary(**inputs)
    outside = tmp_path / "outside"
    outside.mkdir()

    symlinked_parent = tmp_path / "symlinked-parent"
    symlinked_parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PurchaseSpendSummaryError, match="without symlinks"):
        write_purchase_spend_summary(symlinked_parent / "summary.json", summary)
    assert not (outside / "summary.json").exists()

    output_parent = tmp_path / "output"
    output_parent.mkdir()
    source = tmp_path / "source.json"
    source.write_bytes(b"untrusted")
    hardlinked_output = output_parent / "summary.json"
    os.link(source, hardlinked_output)
    with pytest.raises(PurchaseSpendSummaryError, match="not a unique regular file"):
        write_purchase_spend_summary(hardlinked_output, summary)


def test_cli_writes_the_same_provider_free_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, monkeypatch=monkeypatch)
    output = tmp_path / "cli-output.json"

    assert (
        main(
            [
                "acquisition",
                "summarize-purchase-spend",
                "--purchase-policy",
                str(inputs["purchase_policy"]),
                "--cohort-policy",
                str(inputs["cohort_policy"]),
                "--purchase-ledger",
                str(inputs["purchase_ledger"]),
                "--purchase-ledger-initialization-receipt",
                str(inputs["purchase_ledger_initialization_receipt"]),
                "--initial-purchase-result",
                str(inputs["initial_purchase_result"]),
                "--replacement-purchase-result",
                str(inputs["replacement_purchase_result"]),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert (
        json.loads(output.read_text(encoding="utf-8"))["spend_summary"][
            "actual_spend_usd"
        ]
        is None
    )


def _inputs(tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch) -> PurchaseInputs:
    projection = build_completed_projection_fixture(
        tmp_path / "projection", monkeypatch=monkeypatch
    )
    approved = build_approved_purchase_fixture(
        tmp_path / "approval", target_cohort_root=projection.root
    )
    policy_payload = approved.policy.read_bytes()
    cohort_payload = approved.cohort_policy.read_bytes()
    policy = verify_case_dev_purchase_policy(json.loads(policy_payload))
    initialize_case_dev_purchase_journal(
        approved.ledger,
        policy=policy,
        receipt_path=approved.initialization_receipt,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(policy_payload).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_payload).hexdigest(),
        initialized_at="2026-08-08T17:00:00Z",
        controlled_private_root=approved.controlled_private_root,
    )
    plan = MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-001",
                purchase_document_ids=("doc-001", "doc-002"),
                missing_core_document_count=2,
                estimated_cost=Decimal("6.10"),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("9.15"),
        max_missing_core_documents_per_case=2,
        dry_run=False,
    )
    with CaseDevPurchaseJournal(
        approved.ledger,
        policy=policy,
        controlled_private_root=approved.controlled_private_root,
        initialization_receipt_path=approved.initialization_receipt,
    ) as journal:
        journal.plan(plan)
        assert journal.submit("doc-001")
        journal.queue("doc-001", response={"queue_id": "queue-001"})
        assert journal.submit("doc-002")
        journal.mark_unknown("doc-002", "provider response uncertain")

    initial_result = tmp_path / "initial-purchase-result.json"
    replacement_result = tmp_path / "replacement-purchase-result.json"
    _write_purchase_result(initial_result, [_attempt("doc-001")])
    _write_purchase_result(replacement_result, [_attempt("doc-002")])
    return {
        "purchase_policy": approved.policy,
        "cohort_policy": approved.cohort_policy,
        "purchase_ledger": approved.ledger,
        "purchase_ledger_initialization_receipt": approved.initialization_receipt,
        "controlled_private_root": approved.controlled_private_root,
        "initial_purchase_result": initial_result,
        "replacement_purchase_result": replacement_result,
    }


def _attempt(document_id: str) -> dict[str, object]:
    return {
        "candidate_id": "case-001",
        "download_url": None,
        "fee_acknowledged": None,
        "pacer_fees": None,
        "reason": "unknown_status_material_pending_clearance",
        "source_document_id": document_id,
        "source_provider": "courtlistener.recap-fetch+pacer",
        "status": "quarantined",
    }


def _write_purchase_result(path: Path, attempts: list[dict[str, object]]) -> None:
    purchased_count = sum(attempt["status"] == "purchased" for attempt in attempts)
    quarantined_count = sum(attempt["status"] == "quarantined" for attempt in attempts)
    path.write_text(
        json.dumps(
            {
                "acknowledge_pacer_fees": True,
                "attempts": attempts,
                "capability": "document_level_purchase",
                "completed_purchase_count": purchased_count + quarantined_count,
                "dry_run": False,
                "executed_purchase_count": purchased_count,
                "intended_purchase_count": len(attempts),
                "live": True,
                "max_projected_budget_usd": "9.15",
                "projected_cost_usd": f"{len(attempts) * 3.05:.2f}",
                "quarantined_material_count": quarantined_count,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
