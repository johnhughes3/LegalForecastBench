from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    generate_case_dev_purchase_policy,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.recap_fetch_broker_policy import (
    RecapFetchBrokerPolicyError,
    broker_policy_sha256,
    generate_recap_fetch_broker_policy,
    write_recap_fetch_broker_policy,
)
from pytest import CaptureFixture

_GOLDEN_ROOT = Path("tests/fixtures/recap_fetch_broker_policy")


def test_golden_policy_is_hash_bound_and_excludes_unplanned_selection_docs() -> None:
    policy = generate_recap_fetch_broker_policy(
        purchase_policy_artifact=_purchase_policy(),
        cohort_policy_artifact=_cohort_policy(),
        budget_plan=_budget_plan(),
        budget_plan_artifact=_budget_plan().to_record(),
        selection_records=_selection(),
    )

    assert policy == {
        "version": "courtlistener-recap-fetch-policy-v1",
        "cycle_id": "cycle-1",
        "purchase_policy_sha256": _purchase_policy()["policy_sha256"],
        "cycle_cap_usd": "100.00",
        "per_case_cap_usd": "10.00",
        "reservation_usd": "3.05",
        "opening_committed_spend_usd": "2.00",
        "opening_case_committed_spend_usd": {"case-1": "2.00"},
        "allowed_documents": [
            {"recap_document": "123", "case_id": "case-1"},
            {"recap_document": "456", "case_id": "case-2"},
        ],
    }
    assert broker_policy_sha256(policy) == (
        "6d57b5620ff05f1aa31c8553f5c2aa779c0c63e0186467e0c5d1321a7b68990b"
    )


def test_reordering_inputs_produces_identical_bytes(tmp_path: Path) -> None:
    purchase_policy = _purchase_policy()
    first = generate_recap_fetch_broker_policy(
        purchase_policy_artifact=purchase_policy,
        cohort_policy_artifact=_cohort_policy(),
        budget_plan=_budget_plan(),
        budget_plan_artifact=_budget_plan().to_record(),
        selection_records=_selection(),
    )
    reordered = generate_recap_fetch_broker_policy(
        purchase_policy_artifact={
            key: purchase_policy[key] for key in reversed(purchase_policy)
        },
        cohort_policy_artifact=_cohort_policy(),
        budget_plan=_budget_plan(reverse=True),
        budget_plan_artifact=_budget_plan(reverse=True).to_record(),
        selection_records=list(reversed(_selection())),
    )
    first_path = write_recap_fetch_broker_policy(tmp_path / "first.json", first)
    second_path = write_recap_fetch_broker_policy(tmp_path / "second.json", reordered)

    assert first_path.read_bytes() == second_path.read_bytes()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda plan, selection, purchase: setattr(plan, "dry_run", True), "dry-run"),
        (
            lambda plan, selection, purchase: setattr(
                plan.case_plans[0], "dry_run", True
            ),
            "dry-run",
        ),
        (
            lambda plan, selection, purchase: setattr(
                plan.case_plans[0], "exclusion_reasons", ("excluded",)
            ),
            "excluded",
        ),
        (
            lambda plan, selection, purchase: setattr(
                plan.case_plans[1], "purchase_document_ids", ("123",)
            ),
            "unique",
        ),
        (
            lambda plan, selection, purchase: setattr(
                plan.case_plans[0], "purchase_document_ids", ("0123",)
            ),
            "canonical",
        ),
        (
            lambda plan, selection, purchase: selection[0].pop("documents"),
            "documents",
        ),
        (
            lambda plan, selection, purchase: selection[0]["documents"].pop(0),
            "missing public restriction",
        ),
        (
            lambda plan, selection, purchase: selection[0]["documents"][0].update(
                {"is_sealed": True}
            ),
            "sealed/private/restricted",
        ),
        (
            lambda plan, selection, purchase: selection[0]["documents"][0].update(
                {"restriction_evidence": ["totally-unrecognized"]}
            ),
            "sealed/private/restricted",
        ),
        (
            lambda plan, selection, purchase: purchase["policy"][
                "opening_case_committed_spend_usd"
            ].update({"case-missing": "0.00"}),
            "hash",
        ),
    ],
)
def test_invalid_inputs_fail_closed(mutate: Any, message: str) -> None:
    purchase_policy = _purchase_policy()
    plan = _mutable_plan()
    selection = deepcopy(_selection())
    mutate(plan, selection, purchase_policy)

    with pytest.raises(RecapFetchBrokerPolicyError, match=message):
        frozen_plan = _freeze_plan(plan)
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=purchase_policy,
            cohort_policy_artifact=_cohort_policy(),
            budget_plan=frozen_plan,
            budget_plan_artifact=frozen_plan.to_record(),
            selection_records=selection,
        )


def test_opening_commitment_case_must_be_in_derived_allowlist() -> None:
    purchase_policy = _purchase_policy(opening_cases={"case-3": "2.00"})

    with pytest.raises(RecapFetchBrokerPolicyError, match="opening commitment"):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=purchase_policy,
            cohort_policy_artifact=_cohort_policy(),
            budget_plan=_budget_plan(),
            budget_plan_artifact=_budget_plan().to_record(),
            selection_records=_selection(),
        )


def test_empty_allowlist_and_different_byte_overwrite_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(RecapFetchBrokerPolicyError, match="allowlist"):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=_purchase_policy(
                opening_spend="0.00", opening_cases={}
            ),
            cohort_policy_artifact=_cohort_policy(),
            budget_plan=_budget_plan(empty=True),
            budget_plan_artifact=_budget_plan(empty=True).to_record(),
            selection_records=_selection(),
        )

    output = tmp_path / "policy.json"
    first = generate_recap_fetch_broker_policy(
        purchase_policy_artifact=_purchase_policy(),
        cohort_policy_artifact=_cohort_policy(),
        budget_plan=_budget_plan(),
        budget_plan_artifact=_budget_plan().to_record(),
        selection_records=_selection(),
    )
    write_recap_fetch_broker_policy(output, first)
    changed = deepcopy(first)
    changed["allowed_documents"] = [{"recap_document": "123", "case_id": "case-1"}]
    with pytest.raises(RecapFetchBrokerPolicyError, match="overwrite"):
        write_recap_fetch_broker_policy(output, changed)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("cost_per_document_usd", "0.00", "reservation"),
        ("total_estimated_cost_usd", "3.05", "total estimated cost"),
        ("total_missing_core_documents", 1, "total document count"),
    ],
)
def test_tampered_budget_plan_artifact_fails_closed(
    field: str,
    value: object,
    message: str,
) -> None:
    plan = _budget_plan()
    artifact = plan.to_record()
    artifact[field] = value

    with pytest.raises(RecapFetchBrokerPolicyError, match=message):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=_purchase_policy(),
            cohort_policy_artifact=_cohort_policy(),
            budget_plan=plan,
            budget_plan_artifact=artifact,
            selection_records=_selection(),
        )


def test_symlink_output_and_downstream_incompatible_identity_fail_closed(
    tmp_path: Path,
) -> None:
    policy = generate_recap_fetch_broker_policy(
        purchase_policy_artifact=_purchase_policy(),
        cohort_policy_artifact=_cohort_policy(),
        budget_plan=_budget_plan(),
        budget_plan_artifact=_budget_plan().to_record(),
        selection_records=_selection(),
    )
    target = write_recap_fetch_broker_policy(tmp_path / "target.json", policy)
    symlink = tmp_path / "policy.json"
    symlink.symlink_to(target)
    with pytest.raises(RecapFetchBrokerPolicyError, match="symlink"):
        write_recap_fetch_broker_policy(symlink, policy)

    long_identity = _purchase_policy()
    long_policy = cast(dict[str, object], long_identity["policy"])
    long_policy["cycle_id"] = "x" * 129
    long_identity = generate_case_dev_purchase_policy(long_policy)
    with pytest.raises(RecapFetchBrokerPolicyError, match="128-character"):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=long_identity,
            cohort_policy_artifact=_cohort_policy(),
            budget_plan=_budget_plan(),
            budget_plan_artifact=_budget_plan().to_record(),
            selection_records=_selection(),
        )


def test_cli_help_names_every_authoritative_input(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["acquisition", "generate-recap-fetch-broker-policy", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for flag in (
        "--purchase-policy",
        "--cohort-policy",
        "--budget-plan",
        "--selection",
        "--output",
    ):
        assert flag in help_text
    assert "non-dry-run" in help_text
    for restriction in ("sealed", "private", "restricted"):
        assert restriction in help_text
    assert "different-byte" in help_text


def test_cli_writes_policy_and_reports_canonical_hash(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_path = tmp_path / "recap-fetch-broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(_GOLDEN_ROOT / "purchase-policy.json"),
                "--cohort-policy",
                str(_GOLDEN_ROOT / "cohort-policy.json"),
                "--budget-plan",
                str(_GOLDEN_ROOT / "missing-core-budget-plan.json"),
                "--selection",
                str(_GOLDEN_ROOT / "final-selection.jsonl"),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert (
        output_path.read_bytes()
        == (_GOLDEN_ROOT / "recap-fetch-broker-policy.json").read_bytes()
    )
    policy = json.loads(output_path.read_text(encoding="utf-8"))
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "output": str(output_path),
        "broker_policy_sha256": broker_policy_sha256(policy),
    }


def test_cli_rejects_purchase_policy_bound_to_another_cohort(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.write_text(json.dumps(_cohort_policy()), encoding="utf-8")
    purchase_path = tmp_path / "purchase-policy.json"
    purchase_path.write_text(
        json.dumps(_purchase_policy(cohort_policy_sha256="b" * 64)),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(purchase_path),
                "--cohort-policy",
                str(cohort_path),
                "--budget-plan",
                str(_GOLDEN_ROOT / "missing-core-budget-plan.json"),
                "--selection",
                str(_GOLDEN_ROOT / "final-selection.jsonl"),
                "--output",
                str(tmp_path / "broker-policy.json"),
            ]
        )
        == 2
    )
    assert "different cohort policy hash" in capsys.readouterr().err


def _purchase_policy(
    *,
    opening_spend: str = "2.00",
    opening_cases: dict[str, str] | None = None,
    cohort_policy_sha256: str | None = None,
) -> dict[str, object]:
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": (
                cohort_policy_sha256 or cast(str, _cohort_policy()["policy_sha256"])
            ),
            "canonical_ledger_path": "/tmp/cycle-1-purchases.sqlite3",
            "hard_cap_usd": "100.00",
            "opening_committed_spend_usd": opening_spend,
            "opening_case_committed_spend_usd": (
                {"case-1": "2.00"} if opening_cases is None else opening_cases
            ),
            "max_per_case_usd": "10.00",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "https://example.test/fees",
                "verified_at_utc": "2026-07-13T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )


def _cohort_policy() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((_GOLDEN_ROOT / "cohort-policy.json").read_text(encoding="utf-8")),
    )


def _budget_plan(
    *, reverse: bool = False, empty: bool = False
) -> MissingCoreBudgetPlan:
    plans = (
        ()
        if empty
        else (
            _case_plan("case-1", ("123",)),
            _case_plan("case-2", ("456",)),
        )
    )
    if reverse:
        plans = tuple(reversed(plans))
    return MissingCoreBudgetPlan(
        case_plans=plans,
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("100.00"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )


def _case_plan(
    candidate_id: str, document_ids: tuple[str, ...]
) -> CaseMissingCorePurchasePlan:
    return CaseMissingCorePurchasePlan(
        candidate_id=candidate_id,
        purchase_document_ids=document_ids,
        missing_core_document_count=len(document_ids),
        estimated_cost=Decimal("3.05") * len(document_ids),
        audit_only_document_count=0,
        dry_run=False,
    )


def _selection() -> list[dict[str, object]]:
    return [
        {
            "candidate_id": "case-1",
            "selected": True,
            "exclusion_reasons": [],
            "documents": [
                _document("123"),
                _document("999"),
            ],
        },
        {
            "candidate_id": "case-2",
            "selected": True,
            "exclusion_reasons": [],
            "documents": [_document("456")],
        },
    ]


def _document(document_id: str) -> dict[str, object]:
    return {
        "source_document_id": document_id,
        "redaction_or_seal_status": "unknown",
        "restriction_evidence": [
            "courtlistener_docket_entry_checked",
            "case_dev_entry_and_document_checked",
        ],
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
        "is_sealed": None,
        "is_private": None,
    }


class _MutablePlan:
    def __init__(self) -> None:
        self.dry_run = False
        self.case_plans = [
            _MutableCasePlan("case-1", ("123",)),
            _MutableCasePlan("case-2", ("456",)),
        ]


class _MutableCasePlan:
    def __init__(self, candidate_id: str, document_ids: tuple[str, ...]) -> None:
        self.candidate_id = candidate_id
        self.purchase_document_ids = document_ids
        self.missing_core_document_count = len(document_ids)
        self.estimated_cost = Decimal("3.05") * len(document_ids)
        self.audit_only_document_count = 0
        self.dry_run = False
        self.exclusion_reasons: tuple[str, ...] = ()


def _mutable_plan() -> _MutablePlan:
    return _MutablePlan()


def _freeze_plan(plan: _MutablePlan) -> MissingCoreBudgetPlan:
    return MissingCoreBudgetPlan(
        case_plans=tuple(
            CaseMissingCorePurchasePlan(
                candidate_id=item.candidate_id,
                purchase_document_ids=item.purchase_document_ids,
                missing_core_document_count=item.missing_core_document_count,
                estimated_cost=item.estimated_cost,
                audit_only_document_count=item.audit_only_document_count,
                dry_run=item.dry_run,
                exclusion_reasons=item.exclusion_reasons,
            )
            for item in plan.case_plans
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("100.00"),
        max_missing_core_documents_per_case=24,
        dry_run=plan.dry_run,
    )
