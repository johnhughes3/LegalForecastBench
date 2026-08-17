from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    canonical_purchase_operation_sha256,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_provider_identity import (
    COURTLISTENER_RECAP_FETCH_PROVIDER,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    CourtListenerRecapFetchConfig,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecordedRecapFetchResponse,
)
from legalforecast.ingestion.courtlistener_recap_purchase import (
    CONFIRMATION_PROVENANCE_SCHEMA_VERSION,
    ConfirmationProvenanceError,
    build_paid_recap,
    confirmation_provenance_root,
    write_confirmation_provenance_sidecars,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures
from tests.test_direct_courtlistener_purchase import (
    _available_document_response,
    _plan,
    _policy,
    _public_config,
    _public_documents,
    _response,
)


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


@dataclass(frozen=True)
class _SyntheticPolicy:
    cycle_id: str
    policy_sha256: str


@dataclass(frozen=True)
class _SyntheticJournal:
    path: Path
    policy: _SyntheticPolicy
    operations: tuple[Mapping[str, object], ...]

    def operation_records(self) -> tuple[Mapping[str, object], ...]:
        return self.operations


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


def test_paid_purchase_factory_writes_digest_keyed_queue_provenance_sidecar(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = confirmation_provenance_root(ledger)
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _available_document_response("123"),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        client = build_paid_recap(
            CourtListenerRecapFetchClient,
            _public_config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker(
                [{"id": "77", "reservation_id": "reservation-1"}]
            ),
        )
        result = client.execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        before_records = journal.operation_records()
        before_state = journal.purchase_state_sha256()
        paths = write_confirmation_provenance_sidecars(journal)
        after_records = journal.operation_records()
        after_state = journal.purchase_state_sha256()
        original_sidecar = paths[0].read_bytes()
        paths[0].write_bytes(b"{}\n")
        try:
            with pytest.raises(ConfirmationProvenanceError, match="conflicts"):
                write_confirmation_provenance_sidecars(journal)
        finally:
            paths[0].write_bytes(original_sidecar)

    assert result.executed_purchase_count == 1
    assert len(paths) == 1
    assert paths[0].parent == sidecar_root
    operation = before_records[0]
    operation_digest = canonical_purchase_operation_sha256(operation)
    assert paths[0].name == f"{operation_digest}.json"
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record == {
        "canonical_purchase_operation_sha256": operation_digest,
        "candidate_id": "case-1",
        "confirmation_evidence": "recap_fetch_queue_status_2",
        "cycle_id": "cycle-1",
        "non_authoritative": True,
        "provider_detail_sha256": hashlib.sha256(
            json.dumps(
                {
                    "id": 123,
                    "is_available": True,
                    "is_private": None,
                    "is_sealed": None,
                    "filepath_local": "https://storage.courtlistener.com/123.pdf",
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest(),
        "purchase_policy_sha256": policy.policy_sha256,
        "queue_id": "77",
        "queue_response_sha256": hashlib.sha256(b'{"status":2}').hexdigest(),
        "schema_version": CONFIRMATION_PROVENANCE_SCHEMA_VERSION,
        "source_document_id": "123",
    }
    assert before_records == after_records
    assert before_state == after_state
    assert "confirmation_evidence" not in operation["response"]


def test_paid_purchase_factory_writes_public_document_queue_lag_sidecar(
    tmp_path: Path,
) -> None:
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
            _available_document_response("123"),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        client = build_paid_recap(
            CourtListenerRecapFetchClient,
            _public_config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker(
                [{"id": "77", "reservation_id": "reservation-1"}]
            ),
            confirmation_provenance_root=sidecar_root,
        )
        result = client.execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        operation = journal.operation_records()[0]

    assert result.executed_purchase_count == 1
    operation_digest = canonical_purchase_operation_sha256(operation)
    record = json.loads(
        (sidecar_root / f"{operation_digest}.json").read_text(encoding="utf-8")
    )
    assert record["confirmation_evidence"] == "public_document_during_queue_lag"
    assert record["queue_response_sha256"] is None
    assert "queue_response" not in operation["response"]


def test_sidecar_filename_matches_authoritative_digest_for_non_ascii(
    tmp_path: Path,
) -> None:
    """synthetic: true; hand-authored Unicode isolates canonical encoding."""

    restrictions: dict[str, object] = {
        "description": "Mémoire résumé",
        "filepath_local": "https://storage.courtlistener.com/résumé.pdf",
    }
    queue_response: dict[str, object] = {"message": "Prêt", "status": 2}
    operation: dict[str, object] = {
        "candidate_id": "café-case",
        "response": {
            "post_delivery_restrictions": restrictions,
            "queue_id": "77",
            "queue_response": queue_response,
            "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
        },
        "source_document_id": "123",
        "status": "confirmed",
    }
    journal = _SyntheticJournal(
        path=tmp_path / "purchases.sqlite3",
        policy=_SyntheticPolicy(cycle_id="cycle-1", policy_sha256="b" * 64),
        operations=(operation,),
    )

    (path,) = write_confirmation_provenance_sidecars(journal)

    operation_digest = canonical_purchase_operation_sha256(operation)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == f"{operation_digest}.json"
    assert record["canonical_purchase_operation_sha256"] == operation_digest
    assert (
        record["provider_detail_sha256"]
        == hashlib.sha256(
            json.dumps(
                restrictions,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )
    assert (
        record["queue_response_sha256"]
        == hashlib.sha256(
            json.dumps(
                queue_response,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )
