from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
)
from legalforecast.ingestion.courtlistener_recap_purchase import (
    build_paid_recap,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


def test_paid_purchase_factory_uses_queue_lag_tolerant_window(tmp_path: Path) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "9.15",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "9.15",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-07-13T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    policy = verify_case_dev_purchase_policy(artifact)
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        client = build_paid_recap(
            CourtListenerRecapFetchClient,
            CourtListenerRecapFetchConfig(api_token="fixture-token"),
            journal=journal,
            transport=FixtureRecapFetchTransport([]),
            purchase_broker=FixtureRecapFetchPurchaseBroker([]),
        )

    assert isinstance(client, CourtListenerRecapFetchClient)
    assert (client.poll_attempts, client.poll_backoff_seconds) == (120, 8.0)
