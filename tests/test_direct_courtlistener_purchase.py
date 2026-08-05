from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicyError,
    CaseDevPurchaseReconciliationRequired,
    generate_case_dev_purchase_policy,
    initialize_case_dev_purchase_journal,
    require_approved_case_dev_purchase_policy,
    verify_approved_purchase_input_bytes,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    CourtListenerRecapFetchError,
    DirectCourtListenerRecapFetchConfig,
    DirectCourtListenerRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecapFetchHTTPResponse,
    RecordedRecapFetchResponse,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.purchase_approval import (
    replay_approved_purchase_policy,
)
from tests.purchase_approval_fixtures import (
    allow_historical_v1_algorithm_fixtures,
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


class _RecordingPaidTransport:
    def __init__(
        self,
        responses: list[RecapFetchHTTPResponse] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        *,
        method: str,
        path: str,
        form: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapFetchHTTPResponse:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "form": dict(form),
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("unexpected duplicate paid CourtListener request")
        return self.responses.pop(0)


def test_direct_config_requires_all_three_credentials_and_redacts_them() -> None:
    values = {
        "COURTLISTENER_API_TOKEN": "courtlistener-secret",
        "PACER_USERNAME": "pacer-user-secret",
        "PACER_PASSWORD": "pacer-password-secret",
    }
    config = DirectCourtListenerRecapFetchConfig.from_env(values)
    broker = DirectCourtListenerRecapFetchPurchaseBroker(
        config,
        transport=_RecordingPaidTransport(),
    )

    assert config.api_token == values["COURTLISTENER_API_TOKEN"]
    assert config.pacer_username == values["PACER_USERNAME"]
    assert config.pacer_password == values["PACER_PASSWORD"]
    for secret in values.values():
        assert secret not in repr(config)
        assert secret not in repr(broker)

    for missing in values:
        incomplete = {key: value for key, value in values.items() if key != missing}
        with pytest.raises(CourtListenerRecapFetchError) as exc_info:
            DirectCourtListenerRecapFetchConfig.from_env(incomplete)
        assert missing in str(exc_info.value)
        for secret in values.values():
            assert secret not in str(exc_info.value)


def test_direct_purchase_posts_exact_form_and_keeps_full_reservation(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )
    direct = DirectCourtListenerRecapFetchPurchaseBroker(
        _direct_config(), transport=paid
    )
    public = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _response(
                "GET",
                "/recap-documents/123/",
                {
                    "id": 123,
                    "is_available": True,
                    "filepath_local": "https://storage.courtlistener.com/123.pdf",
                },
            ),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        result = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=public,
            purchase_broker=direct,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        operation_key = str(operation["operation_key"])
        assert journal.statuses() == {"123": "confirmed"}
        assert journal.committed_amount_usd == "3.05"

    assert paid.calls == [
        {
            "method": "POST",
            "path": "/recap-fetch/",
            "form": {
                "request_type": "2",
                "pacer_username": "pacer-user-secret",
                "pacer_password": "pacer-password-secret",
                "recap_document": "123",
                "client_code": _client_code(operation_key),
            },
            "headers": {
                "Authorization": "Token courtlistener-secret",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            "timeout_seconds": 7.0,
        }
    ]
    assert direct.paid_dispatch_count == 1
    assert result.executed_purchase_count == 1
    assert result.attempts[0].pacer_fees == {
        "pacer_fee_usd": "3.05",
        "service_fee_usd": "0.00",
        "total_usd": "3.05",
        "cost_basis": "worst_case_reservation",
    }
    durable_surfaces = json.dumps(operation, sort_keys=True) + repr(result)
    for secret in (
        "courtlistener-secret",
        "pacer-user-secret",
        "pacer-password-secret",
    ):
        assert secret not in durable_surfaces


@pytest.mark.parametrize("status_code", (302, 503))
def test_direct_purchase_treats_redirect_or_retryable_status_as_unknown_once(
    tmp_path: Path,
    status_code: int,
) -> None:
    ledger = (tmp_path / f"purchases-{status_code}.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=status_code, payload={})]
    )
    direct = DirectCourtListenerRecapFetchPurchaseBroker(
        _direct_config(), transport=paid
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        result = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [_response("GET", "/recap-documents/123/", {"id": 123})]
            ),
            purchase_broker=direct,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.statuses() == {"123": "unknown"}
        assert journal.committed_amount_usd == "3.05"

    assert len(paid.calls) == 1
    assert direct.paid_dispatch_count == 1
    assert result.attempts[0].status.value == "unknown"
    assert result.attempts[0].reason == "purchase_outcome_unknown"


def test_direct_timeout_is_unknown_and_cannot_replay_paid_post(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    timed_out = _RecordingPaidTransport(error=TimeoutError("provider timed out"))
    first_broker = DirectCourtListenerRecapFetchPurchaseBroker(
        _direct_config(), transport=timed_out
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        first = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [_response("GET", "/recap-documents/123/", {"id": 123})]
            ),
            purchase_broker=first_broker,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.statuses() == {"123": "unknown"}
        assert journal.committed_amount_usd == "3.05"
    assert len(timed_out.calls) == 1
    assert first.attempts[0].status.value == "unknown"

    replay_transport = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 88})]
    )
    second_broker = DirectCourtListenerRecapFetchPurchaseBroker(
        _direct_config(), transport=replay_transport
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        with pytest.raises(
            CaseDevPurchaseReconciliationRequired, match="unknown paid outcome"
        ):
            CourtListenerRecapFetchClient(
                _public_config(),
                journal=journal,
                transport=FixtureRecapFetchTransport([]),
                purchase_broker=second_broker,
            ).execute_purchase_plan(
                _plan(),
                public_documents=_public_documents(),
                live=True,
                acknowledge_pacer_fees=True,
            )
    assert replay_transport.calls == []
    assert second_broker.paid_dispatch_count == 0


def test_direct_queued_resume_polls_without_duplicate_paid_post(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    first_paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        first = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-documents/123/", {"id": 123}),
                    _response("GET", "/recap-fetch/77/", {"status": 1}),
                ]
            ),
            purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                _direct_config(), transport=first_paid
            ),
            poll_attempts=1,
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert first.attempts[0].status.value == "not_attempted"
        assert journal.statuses() == {"123": "queued"}

    second_paid = _RecordingPaidTransport()
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        second = CourtListenerRecapFetchClient(
            _public_config(),
            journal=journal,
            transport=FixtureRecapFetchTransport(
                [
                    _response("GET", "/recap-fetch/77/", {"status": 2}),
                    _response(
                        "GET",
                        "/recap-documents/123/",
                        {
                            "id": 123,
                            "is_available": True,
                            "filepath_local": (
                                "https://storage.courtlistener.com/123.pdf"
                            ),
                        },
                    ),
                ]
            ),
            purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                _direct_config(), transport=second_paid
            ),
        ).execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        assert journal.statuses() == {"123": "confirmed"}
        assert journal.committed_amount_usd == "3.05"

    assert second.executed_purchase_count == 1
    assert second_paid.calls == []


@pytest.mark.parametrize(
    (
        "hard_cap",
        "max_per_case",
        "opening_committed",
        "document_ids",
        "expected",
    ),
    (
        ("6.00", "6.00", "3.00", ("123",), "cycle cap"),
        ("9.15", "3.05", "0.00", ("123", "124"), "per-case cap"),
    ),
)
def test_direct_budget_refusal_happens_before_paid_post(
    tmp_path: Path,
    hard_cap: str,
    max_per_case: str,
    opening_committed: str,
    document_ids: tuple[str, ...],
    expected: str,
) -> None:
    ledger = (tmp_path / f"purchases-{hard_cap}-{max_per_case}.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(
        _policy(
            ledger,
            hard_cap=hard_cap,
            max_per_case=max_per_case,
            opening_committed=opening_committed,
        )
    )
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        with pytest.raises(CaseDevPurchaseLedgerError, match=expected):
            CourtListenerRecapFetchClient(
                _public_config(),
                journal=journal,
                transport=FixtureRecapFetchTransport(
                    [_response("GET", "/recap-documents/123/", {"id": 123})]
                ),
                purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                    _direct_config(), transport=paid
                ),
            ).execute_purchase_plan(
                _plan(document_ids),
                public_documents=_public_documents(document_ids),
                live=True,
                acknowledge_pacer_fees=True,
            )
    assert paid.calls == []


@pytest.mark.parametrize(
    "metadata",
    (
        {
            "redaction_or_seal_status": "sealed",
            "is_sealed": True,
            "is_private": False,
        },
        {
            "redaction_or_seal_status": "private",
            "is_sealed": False,
            "is_private": True,
        },
    ),
)
def test_direct_restricted_material_is_rejected_before_any_post(
    tmp_path: Path,
    metadata: dict[str, object],
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    paid = _RecordingPaidTransport(
        [RecapFetchHTTPResponse(status_code=201, payload={"id": 77})]
    )
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        with pytest.raises(CourtListenerRecapFetchError, match="public/nonsealed"):
            CourtListenerRecapFetchClient(
                _public_config(),
                journal=journal,
                transport=FixtureRecapFetchTransport([]),
                purchase_broker=DirectCourtListenerRecapFetchPurchaseBroker(
                    _direct_config(), transport=paid
                ),
            ).execute_purchase_plan(
                _plan(),
                public_documents={"123": metadata},
                live=True,
                acknowledge_pacer_fees=True,
            )
    assert paid.calls == []


def test_direct_config_rejects_non_courtlistener_paid_host() -> None:
    config = DirectCourtListenerRecapFetchConfig(
        api_token="courtlistener-secret",
        pacer_username="pacer-user-secret",
        pacer_password="pacer-password-secret",
        base_url="https://example.com/api/rest/v4",
    )
    with pytest.raises(CourtListenerRecapFetchError, match=r"www\.courtlistener\.com"):
        DirectCourtListenerRecapFetchPurchaseBroker(config)


def test_public_v2_replays_and_opens_ledger_without_private_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = build_completed_projection_fixture(
        tmp_path / "projection", monkeypatch=monkeypatch
    )
    approved = build_approved_purchase_fixture(
        tmp_path / "approval", target_cohort_root=completed.root
    )
    artifact = json.loads(approved.policy.read_text(encoding="utf-8"))
    policy = verify_case_dev_purchase_policy(artifact)
    budget_bytes = completed.budget_plan.read_bytes()
    selection_bytes = completed.selection.read_bytes()

    require_approved_case_dev_purchase_policy(policy, controlled_private_root=None)
    public_scope = verify_approved_purchase_input_bytes(
        policy,
        controlled_private_root=None,
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
    )
    private_scope = verify_approved_purchase_input_bytes(
        policy,
        controlled_private_root=approved.controlled_private_root,
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
    )
    replayed = replay_approved_purchase_policy(
        purchase_policy_artifact=artifact,
        controlled_private_root=approved.controlled_private_root,
    )
    assert public_scope == private_scope
    assert replayed.policy_sha256 == policy.policy_sha256
    with pytest.raises(CaseDevPurchasePolicyError, match="selection bytes differ"):
        verify_approved_purchase_input_bytes(
            policy,
            controlled_private_root=None,
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes + b"\n",
        )

    initialize_case_dev_purchase_journal(
        approved.ledger,
        policy=policy,
        receipt_path=approved.initialization_receipt,
        purchase_policy_file_sha256=(
            "sha256:" + hashlib.sha256(approved.policy.read_bytes()).hexdigest()
        ),
        cohort_policy_file_sha256=(
            "sha256:" + hashlib.sha256(approved.cohort_policy.read_bytes()).hexdigest()
        ),
        initialized_at="2026-08-05T02:00:00Z",
        controlled_private_root=None,
    )
    with CaseDevPurchaseJournal(
        approved.ledger,
        policy=policy,
        controlled_private_root=None,
        initialization_receipt_path=approved.initialization_receipt,
    ) as journal:
        assert journal.statuses() == {}


def _response(
    method: str, path: str, payload: dict[str, object]
) -> RecordedRecapFetchResponse:
    return RecordedRecapFetchResponse(method, path, {}, 200, payload)


def _direct_config() -> DirectCourtListenerRecapFetchConfig:
    return DirectCourtListenerRecapFetchConfig(
        api_token="courtlistener-secret",
        pacer_username="pacer-user-secret",
        pacer_password="pacer-password-secret",
        timeout_seconds=7.0,
    )


def _public_config() -> CourtListenerRecapFetchConfig:
    return CourtListenerRecapFetchConfig(
        api_token="courtlistener-secret", timeout_seconds=7.0
    )


def _public_documents(
    document_ids: tuple[str, ...] = ("123",),
) -> dict[str, dict[str, object]]:
    return {
        document_id: {
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
        }
        for document_id in document_ids
    }


def _plan(document_ids: tuple[str, ...] = ("123",)) -> MissingCoreBudgetPlan:
    return MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-1",
                purchase_document_ids=document_ids,
                missing_core_document_count=len(document_ids),
                estimated_cost=Decimal("3.05") * len(document_ids),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("9.15"),
        max_missing_core_documents_per_case=3,
        dry_run=False,
    )


def _policy(
    ledger: Path,
    *,
    hard_cap: str = "9.15",
    max_per_case: str = "9.15",
    opening_committed: str = "0.00",
) -> dict[str, object]:
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": hard_cap,
            "opening_committed_spend_usd": opening_committed,
            "opening_case_committed_spend_usd": (
                {}
                if opening_committed == "0.00"
                else {"preexisting-case": opening_committed}
            ),
            "max_per_case_usd": max_per_case,
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-08-05T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )


def _client_code(operation_key: str) -> str:
    digest = hashlib.sha256(operation_key.encode("utf-8")).digest()
    return "lfb-" + base64.b32encode(digest).decode().lower().rstrip("=")[:26]
