from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import legalforecast.cli as cli
import legalforecast.ingestion.case_dev_purchase as case_dev_purchase
import legalforecast.ingestion.clearance_replacement as clearance_replacement
import legalforecast.ingestion.recap_fetch_attempt_policy as recap_attempt
import legalforecast.ingestion.recap_fetch_broker_policy as recap_broker
import legalforecast.ingestion.retained_cohort_extension as retained_extension
import pytest
from legalforecast.ingestion.purchase_approval import (
    build_purchase_approval_request,
    generate_approved_purchase_policy,
    record_purchase_approval,
    verify_purchase_approval,
)

# Complete production-alias inventory covered by the direct fail-before-touch
# rejection matrix. Historical compatibility fixtures must not patch this whole
# set; their bypass is deliberately limited to the old Case.dev journal path.
LEGACY_V1_BYPASS_MODULES: tuple[object, ...] = (
    case_dev_purchase,
    clearance_replacement,
    recap_attempt,
    recap_broker,
    retained_extension,
    cli,
)


@dataclass(frozen=True)
class ApprovedPurchaseFixture:
    policy: Path
    cohort_policy: Path
    controlled_private_root: Path
    ledger: Path
    initialization_receipt: Path


@dataclass(frozen=True)
class CompletedProjectionFixture:
    root: Path
    selection: Path
    budget_plan: Path


def build_completed_projection_fixture(
    root: Path, *, monkeypatch: pytest.MonkeyPatch
) -> CompletedProjectionFixture:
    """Build a real provider-free projection and stop before purchase activity."""

    # Imported lazily because the target-cohort test module also consumes the
    # approval helpers defined here.
    from tests.test_target_cohort_projection import _completed_two_case_projection

    completed = _completed_two_case_projection(
        root,
        provenance_first=True,
        monkeypatch=monkeypatch,
    )
    projection = completed["projection"]
    return CompletedProjectionFixture(
        root=projection,
        selection=projection / "target-cohort-selection.jsonl",
        budget_plan=projection / "missing-core-budget-plan.json",
    )


def build_approved_purchase_fixture(
    root: Path,
    *,
    target_cohort_root: Path,
) -> ApprovedPurchaseFixture:
    """Mint authentic v2 fixture authority from a completed projection."""

    root.mkdir(parents=True, exist_ok=True)
    private_root = (root / "private-approval").resolve()
    ledger = (root / "cycle-purchases.sqlite3").resolve()
    receipt = (root / "purchase-ledger-initialization.json").resolve()
    projection = json.loads(
        (target_cohort_root / "target-cohort-projection.json").read_text(
            encoding="utf-8"
        )
    )
    budget = json.loads(
        (target_cohort_root / "missing-core-budget-plan.json").read_text(
            encoding="utf-8"
        )
    )
    target_count = int(projection["target_case_count"])
    decisions = cli._fixture_cohort_policy_decisions()
    decisions["stop_rule"] = {
        **decisions["stop_rule"],
        "target_clean_cases": target_count,
    }
    claim_tiers: list[dict[str, object]] = []
    if target_count > 1:
        claim_tiers.append(
            {
                "minimum_clean_cases": 1,
                "maximum_clean_cases": target_count - 1,
                "claim_class": "provisional_feasibility",
                "minimum_prediction_units": None,
                "insufficient_units_action": None,
            }
        )
    claim_tiers.append(
        {
            "minimum_clean_cases": target_count,
            "maximum_clean_cases": target_count,
            "claim_class": "target",
            "minimum_prediction_units": None,
            "insufficient_units_action": None,
        }
    )
    decisions["reduced_n"] = {
        "target_clean_cases": target_count,
        "claim_tiers": claim_tiers,
        "below_minimum_action": "pilot_only_no_official_cycle",
    }
    decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": str(budget["max_projected_budget_usd"]),
        "max_per_case_usd": "73.20",
        "reservation_headroom_required": True,
    }
    cohort_policy = root / "cohort-policy.json"
    cohort_policy.write_text(
        json.dumps(cli.generate_cohort_policy(decisions), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    fee_schedule = root / "fee-schedule.json"
    fee_schedule.write_text(
        json.dumps(
            {
                "source_citation": "https://www.courtlistener.com/help/coverage/recap/",
                "verified_at_utc": "2026-07-26T12:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    request = build_purchase_approval_request(
        target_cohort_root=target_cohort_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint, run_card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T12:01:00Z",
    )
    verified = verify_purchase_approval(
        controlled_private_root=private_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
        target_cohort_root=target_cohort_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    policy = root / "purchase-policy-v2.json"
    case_dev_purchase.write_case_dev_purchase_policy(
        policy,
        generate_approved_purchase_policy(verified),
        controlled_private_root=private_root,
    )
    return ApprovedPurchaseFixture(
        policy=policy,
        cohort_policy=cohort_policy,
        controlled_private_root=private_root,
        ledger=ledger,
        initialization_receipt=receipt,
    )


def allow_historical_v1_algorithm_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep legacy algorithm tests focused while production rejects v1.

    These tests predate the John-approved v2 authority and intentionally exercise
    journal state machines and deterministic planning with synthetic v1 policies.
    Dedicated purchase-approval tests exercise every production v2 boundary.
    """

    original_require = case_dev_purchase.require_approved_case_dev_purchase_policy
    original_materialization_preflight = cli._preflight_materialization_purchase_runtime

    def allow_v1(
        policy: object, *, controlled_private_root: object | None = None
    ) -> None:
        if (
            getattr(policy, "schema_version", None)
            == case_dev_purchase.CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION
        ):
            return
        original_require(
            policy,  # type: ignore[arg-type]
            controlled_private_root=controlled_private_root,  # type: ignore[arg-type]
        )

    for module in (case_dev_purchase, cli):
        monkeypatch.setattr(
            module,
            "require_approved_case_dev_purchase_policy",
            allow_v1,
        )

    def allow_v1_materialization_preflight(args: object) -> object:
        """Retain the historical explicit-policy short circuit in legacy tests."""

        policy_path = getattr(args, "purchase_policy", None)
        if policy_path is not None:
            artifact = json.loads(Path(policy_path).read_text(encoding="utf-8"))
            if (
                artifact.get("schema_version")
                == case_dev_purchase.CASE_DEV_PURCHASE_POLICY_SCHEMA_VERSION
            ):
                return case_dev_purchase.verify_case_dev_purchase_policy(artifact)
        return original_materialization_preflight(args)  # type: ignore[arg-type]

    monkeypatch.setattr(
        cli,
        "_preflight_materialization_purchase_runtime",
        allow_v1_materialization_preflight,
    )
