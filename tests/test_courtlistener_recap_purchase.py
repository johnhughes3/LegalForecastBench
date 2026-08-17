from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
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
    reconcile_purchase,
    write_confirmation_provenance_sidecars,
)
from legalforecast.ingestion.recap_fetch_broker import BrokerOutcomeUnknown
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures
from tests.test_courtlistener_recap_fetch import _broker_receipt
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
    monkeypatch: pytest.MonkeyPatch,
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
        paths[0].unlink()
        real_write = os.write

        def interrupted_write(descriptor: int, payload: bytes) -> int:
            real_write(descriptor, payload[:1])
            raise OSError("synthetic interrupted sidecar write")

        with monkeypatch.context() as patch:
            patch.setattr(os, "write", interrupted_write)
            with pytest.raises(ConfirmationProvenanceError, match="publish"):
                write_confirmation_provenance_sidecars(journal)
        assert not paths[0].exists()
        (recovered_path,) = write_confirmation_provenance_sidecars(journal)
        assert recovered_path.read_bytes() == original_sidecar

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


@pytest.mark.parametrize("queued", [False, True])
def test_sparse_reconciled_recap_rows_do_not_emit_sidecars(
    tmp_path: Path,
    *,
    queued: bool,
) -> None:
    ledger = (tmp_path / f"sparse-{queued}.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    context = {"source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER}
    evidence = {
        "source_document_id": "123",
        "disposition": "confirmed",
        "source_type": "billing_receipt",
        "source_reference": "synthetic: true",
        "pacer_fees": {"pacerFee": "1.20", "serviceFee": "0.00", "total": "1.20"},
        "download_url": "https://storage.courtlistener.com/123.pdf",
    }
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        assert journal.submit("123", context=context) is True
        if queued:
            journal.queue("123", response={**context, "queue_id": "77"})

        assert reconcile_purchase(journal, evidence) == ()
        assert journal.statuses() == {"123": "confirmed"}

    assert not confirmation_provenance_root(ledger).exists()


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


def test_broker_receipt_recovery_writes_observed_queue_sidecar_without_refetch(
    tmp_path: Path,
) -> None:
    """synthetic: true; preserve the two GET observations before reconciliation."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    queue_response = {"status": 2}
    provider_detail = {
        "id": 123,
        "is_available": True,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
    }
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-fetch/77/", queue_response),
            _response("GET", "/recap-documents/123/", provider_detail),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        assert journal.submit(
            "123",
            context={
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
                "reservation_usd": "3.05",
            },
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        receipt = _broker_receipt(
            str(operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )
        client = build_paid_recap(
            CourtListenerRecapFetchClient,
            _public_config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker([]),
            confirmation_provenance_root=sidecar_root,
        )

        client.apply_broker_receipt("123", receipt)
        confirmed = journal.operation_records()[0]

    response = confirmed["response"]
    assert isinstance(response, Mapping)
    assert "queue_response" not in response
    assert "post_delivery_restrictions" not in response
    assert "confirmation_evidence" not in response
    digest = canonical_purchase_operation_sha256(confirmed)
    record = json.loads((sidecar_root / f"{digest}.json").read_text(encoding="utf-8"))
    assert record["confirmation_evidence"] == "recap_fetch_queue_status_2"
    assert record["queue_id"] == "77"
    assert (
        record["queue_response_sha256"] == hashlib.sha256(b'{"status":2}').hexdigest()
    )
    assert (
        record["provider_detail_sha256"]
        == hashlib.sha256(
            json.dumps(
                provider_detail,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )
    assert transport.requests == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]
    assert not confirmation_provenance_root(ledger).exists()


def test_broker_receipt_uses_durable_queue_id_when_receipt_omits_id(
    tmp_path: Path,
) -> None:
    """synthetic: true; the frozen client falls back to the durable queue ID."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    queue_response = {"status": 2}
    provider_detail = {
        "id": 123,
        "is_available": True,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
    }
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-fetch/77/", queue_response),
            _response("GET", "/recap-documents/123/", provider_detail),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        assert journal.submit(
            "123",
            context={
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
                "reservation_usd": "3.05",
            },
        )
        journal.queue(
            "123",
            response={
                "queue_id": "77",
                "reservation_id": "reservation-1",
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
            },
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        receipt = _broker_receipt(
            str(operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )
        receipt["id"] = None
        client = build_paid_recap(
            CourtListenerRecapFetchClient,
            _public_config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker([]),
            confirmation_provenance_root=sidecar_root,
        )

        with pytest.raises(
            BrokerOutcomeUnknown,
            match="confirmed broker receipt lacks a verified queue ID",
        ):
            client.apply_broker_receipt("123", receipt)
        assert journal.statuses() == {"123": "queued"}

    assert not sidecar_root.exists()
    assert transport.requests == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


def test_broker_receipt_retry_republishes_observed_sidecar_after_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """synthetic: true; a confirmed-row retry repairs a missed publication."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    queue_response = {"status": 2}
    provider_detail = {
        "id": 123,
        "is_available": True,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
    }
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-fetch/77/", queue_response),
            _response("GET", "/recap-documents/123/", provider_detail),
            _response("GET", "/recap-fetch/77/", queue_response),
            _response("GET", "/recap-documents/123/", provider_detail),
        ]
    )

    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        assert journal.submit(
            "123",
            context={
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
                "reservation_usd": "3.05",
            },
        )
        operation = journal.operation_evidence("123")
        assert operation is not None
        receipt = _broker_receipt(
            str(operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )
        client = build_paid_recap(
            CourtListenerRecapFetchClient,
            _public_config(),
            journal=journal,
            transport=transport,
            purchase_broker=FixtureRecapFetchPurchaseBroker([]),
            confirmation_provenance_root=sidecar_root,
        )

        def crash_before_publish(*args: object, **kwargs: object) -> tuple[Path, ...]:
            del args, kwargs
            raise OSError("synthetic crash before sidecar publication")

        with monkeypatch.context() as patch:
            patch.setattr(
                "legalforecast.ingestion.courtlistener_recap_purchase."
                "_write_confirmation_records",
                crash_before_publish,
            )
            with pytest.raises(OSError, match="synthetic crash"):
                client.apply_broker_receipt("123", receipt)
        assert journal.statuses() == {"123": "confirmed"}
        assert not sidecar_root.exists()

        client.apply_broker_receipt("123", receipt)
        confirmed = journal.operation_records()[0]

    digest = canonical_purchase_operation_sha256(confirmed)
    record = json.loads((sidecar_root / f"{digest}.json").read_text(encoding="utf-8"))
    assert record["confirmation_evidence"] == "recap_fetch_queue_status_2"
    assert (
        record["queue_response_sha256"] == hashlib.sha256(b'{"status":2}').hexdigest()
    )
    assert transport.requests == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


def test_late_broker_receipt_upgrades_public_confirmation_sidecar(
    tmp_path: Path,
) -> None:
    """synthetic: true; retain public evidence and add later status-2 evidence."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    queue_response = {"status": 2}
    provider_detail = {
        "id": 123,
        "is_available": True,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
    }
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", queue_response),
            _response("GET", "/recap-documents/123/", provider_detail),
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
        client.execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        public_operation = journal.operation_records()[0]
        public_digest = canonical_purchase_operation_sha256(public_operation)
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )

        client.apply_broker_receipt("123", receipt)
        successor = journal.operation_records()[0]

    successor_response = successor["response"]
    assert isinstance(successor_response, Mapping)
    assert "queue_response" not in successor_response
    assert "confirmation_evidence" not in successor_response
    successor_digest = canonical_purchase_operation_sha256(successor)
    assert successor_digest != public_digest
    records = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sidecar_root.glob("*.json")
    }
    assert records[public_digest]["confirmation_evidence"] == (
        "public_document_during_queue_lag"
    )
    assert records[successor_digest]["confirmation_evidence"] == (
        "recap_fetch_queue_status_2"
    )
    assert records[successor_digest]["queue_response_sha256"] is not None


def test_late_broker_receipt_recovers_unpublished_public_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """synthetic: true; persist prior evidence before late reconciliation."""
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _available_document_response("123"),
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
            confirmation_provenance_root=sidecar_root,
        )

        def crash_before_publish(*args: object, **kwargs: object) -> tuple[Path, ...]:
            del args, kwargs
            raise OSError("synthetic crash before public sidecar publication")

        with monkeypatch.context() as patch:
            patch.setattr(
                "legalforecast.ingestion.courtlistener_recap_purchase."
                "_write_confirmation_records",
                crash_before_publish,
            )
            with pytest.raises(OSError, match="synthetic crash"):
                client.execute_purchase_plan(
                    _plan(),
                    public_documents=_public_documents(),
                    live=True,
                    acknowledge_pacer_fees=True,
                )
        public_operation = journal.operation_records()[0]
        public_digest = canonical_purchase_operation_sha256(public_operation)
        assert journal.statuses() == {"123": "confirmed"}
        assert not sidecar_root.exists()
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )

        def refuse_prior_publish(*args: object, **kwargs: object) -> tuple[Path, ...]:
            del args, kwargs
            raise OSError("synthetic prior sidecar write failure")

        with monkeypatch.context() as patch:
            patch.setattr(
                "legalforecast.ingestion.courtlistener_recap_purchase."
                "_write_confirmation_records",
                refuse_prior_publish,
            )
            with pytest.raises(OSError, match="prior sidecar write failure"):
                client.apply_broker_receipt("123", receipt)
        assert journal.operation_records() == (public_operation,)
        assert transport.requests == [
            ("GET", "/recap-documents/123/", {}),
            ("GET", "/recap-fetch/77/", {}),
            ("GET", "/recap-documents/123/", {}),
        ]

        original_reconcile = journal.reconcile

        def reconcile_then_crash(evidence: Mapping[str, object]) -> None:
            original_reconcile(evidence)
            raise OSError("synthetic crash after canonical reconciliation")

        with monkeypatch.context() as patch:
            patch.setattr(journal, "reconcile", reconcile_then_crash)
            with pytest.raises(OSError, match="after canonical reconciliation"):
                client.apply_broker_receipt("123", receipt)
        interrupted = journal.operation_records()[0]
        interrupted_response = interrupted["response"]
        assert isinstance(interrupted_response, Mapping)
        assert "queue_response" not in interrupted_response
        assert "confirmation_evidence" not in interrupted_response
        assert canonical_purchase_operation_sha256(interrupted) != public_digest
        assert (sidecar_root / f"{public_digest}.json").is_file()

        client.apply_broker_receipt("123", receipt)
        successor = journal.operation_records()[0]
    successor_response = successor["response"]
    assert isinstance(successor_response, Mapping)
    assert "queue_response" not in successor_response
    assert "confirmation_evidence" not in successor_response
    successor_digest = canonical_purchase_operation_sha256(successor)
    assert successor_digest != public_digest
    records = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sidecar_root.glob("*.json")
    }
    assert records[public_digest]["confirmation_evidence"] == (
        "public_document_during_queue_lag"
    )
    assert records[successor_digest]["confirmation_evidence"] == (
        "recap_fetch_queue_status_2"
    )
    assert transport.requests[3:] == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


def test_late_broker_receipt_rejects_unavailable_document_observation(
    tmp_path: Path,
) -> None:
    """synthetic: true; unavailable bytes never become status-2 evidence."""
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _response(
                "GET",
                "/recap-documents/123/",
                {"id": 123, "is_available": False},
            ),
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
        client.execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        public_operation = journal.operation_records()[0]
        public_digest = canonical_purchase_operation_sha256(public_operation)
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )

        client.apply_broker_receipt("123", receipt)
        successor = journal.operation_records()[0]

    successor_response = successor["response"]
    assert isinstance(successor_response, Mapping)
    assert "queue_response" not in successor_response
    assert "confirmation_evidence" not in successor_response
    successor_digest = canonical_purchase_operation_sha256(successor)
    assert successor_digest != public_digest
    records = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sidecar_root.glob("*.json")
    }
    assert set(records) == {public_digest, successor_digest}
    assert {record["confirmation_evidence"] for record in records.values()} == {
        "public_document_during_queue_lag"
    }
    assert all(record["queue_response_sha256"] is None for record in records.values())
    assert len(transport.requests) == 5
    assert transport.requests[-2:] == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


def test_reconcile_purchase_keeps_successor_sidecar_in_custom_root(
    tmp_path: Path,
) -> None:
    """synthetic: true; initial and successor observations share one root."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    response = {
        "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
        "queue_id": "77",
        "queue_response": {"status": 2},
        "post_delivery_restrictions": {"id": 123},
    }
    evidence = {
        "source_document_id": "123",
        "disposition": "confirmed",
        "source_type": "billing_receipt",
        "source_reference": "synthetic: true",
        "pacer_fees": {
            "pacerFee": "1.20",
            "serviceFee": "0.00",
            "total": "1.20",
        },
        "download_url": "https://storage.courtlistener.com/123.pdf",
    }
    with CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True) as journal:
        journal.plan(_plan())
        assert journal.submit("123") is True
        journal.queue("123", response={"queue_id": "77"})
        journal.confirm_reserved("123", response=response)
        old_digest = canonical_purchase_operation_sha256(journal.operation_records()[0])
        write_confirmation_provenance_sidecars(journal, output_root=sidecar_root)

        paths = reconcile_purchase(
            journal,
            evidence,
            confirmation_provenance_root=sidecar_root,
        )
        new_digest = canonical_purchase_operation_sha256(journal.operation_records()[0])

    assert old_digest != new_digest
    assert {path.name for path in paths} == {f"{new_digest}.json"}
    assert {path.name for path in sidecar_root.iterdir()} == {
        f"{old_digest}.json",
        f"{new_digest}.json",
    }
    assert not confirmation_provenance_root(ledger).exists()


def test_retry_recovers_hardlinked_deterministic_staging_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """synthetic: true; retry repairs a crash after link and before unlink."""

    operation: dict[str, object] = {
        "candidate_id": "case-1",
        "response": {
            "post_delivery_restrictions": {"id": 123},
            "queue_id": "77",
            "queue_response": {"status": 2},
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
    root = confirmation_provenance_root(journal.path)
    real_unlink = os.unlink

    def crash_before_staging_unlink(
        path: str | bytes,
        *,
        dir_fd: int | None = None,
    ) -> None:
        if str(path).endswith(".partial"):
            raise SystemExit("synthetic crash after final link")
        real_unlink(path, dir_fd=dir_fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "unlink", crash_before_staging_unlink)
        with pytest.raises(SystemExit, match="synthetic crash"):
            write_confirmation_provenance_sidecars(journal)

    digest = canonical_purchase_operation_sha256(operation)
    final = root / f"{digest}.json"
    stages = tuple(root.glob(".*.partial"))
    assert len(stages) == 1
    assert final.stat().st_ino == stages[0].stat().st_ino
    assert final.stat().st_nlink == 2

    assert write_confirmation_provenance_sidecars(journal) == (final,)
    assert final.stat().st_nlink == 1
    assert tuple(root.glob(".*.partial")) == ()


def test_confirmation_sidecar_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    """synthetic: true; a hostile final-name FIFO must fail immediately."""

    script = textwrap.dedent(
        """
        import os
        import sys
        from pathlib import Path

        from legalforecast.ingestion.case_dev_purchase import (
            canonical_purchase_operation_sha256,
        )
        from legalforecast.ingestion.courtlistener_provider_identity import (
            COURTLISTENER_RECAP_FETCH_PROVIDER,
        )
        from legalforecast.ingestion.courtlistener_recap_purchase import (
            ConfirmationProvenanceError,
            confirmation_provenance_root,
            write_confirmation_provenance_sidecars,
        )

        class Policy:
            cycle_id = "cycle-1"
            policy_sha256 = "b" * 64

        class Journal:
            path = Path(sys.argv[1]) / "purchases.sqlite3"
            policy = Policy()

            def operation_records(self):
                return (operation,)

        operation = {
            "candidate_id": "case-1",
            "response": {
                "post_delivery_restrictions": {"id": 123},
                "queue_id": "77",
                "queue_response": {"status": 2},
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
            },
            "source_document_id": "123",
            "status": "confirmed",
        }
        journal = Journal()
        root = confirmation_provenance_root(journal.path)
        root.mkdir(parents=True)
        digest = canonical_purchase_operation_sha256(operation)
        os.mkfifo(root / f"{digest}.json")
        try:
            write_confirmation_provenance_sidecars(journal)
        except ConfirmationProvenanceError:
            raise SystemExit(0)
        raise SystemExit("FIFO was accepted")
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=3,
    )

    assert completed.returncode == 0, completed.stderr
