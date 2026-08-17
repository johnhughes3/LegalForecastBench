from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    canonical_purchase_operation_sha256,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchClient,
    FixtureRecapFetchPurchaseBroker,
    FixtureRecapFetchTransport,
    RecordedRecapFetchResponse,
)
from legalforecast.ingestion.courtlistener_recap_purchase import (
    ConfirmationProvenanceError,
    build_paid_recap,
)
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


def test_receipt_recorded_before_reconciliation_retains_both_sidecars(
    tmp_path: Path,
) -> None:
    """synthetic: true; preserve the receipt-bearing pre-reconciliation digest."""

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

        journal.record_broker_receipt("123", receipt)
        receipt_operation = journal.operation_records()[0]
        receipt_digest = canonical_purchase_operation_sha256(receipt_operation)
        assert receipt_operation["reconciliation"] is None
        assert receipt_digest != public_digest
        assert not (sidecar_root / f"{receipt_digest}.json").exists()

        client.apply_broker_receipt("123", receipt)
        successor = journal.operation_records()[0]

    successor_response = successor["response"]
    assert isinstance(successor_response, Mapping)
    assert "queue_response" not in successor_response
    assert "confirmation_evidence" not in successor_response
    successor_digest = canonical_purchase_operation_sha256(successor)
    assert successor_digest not in {public_digest, receipt_digest}
    records = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sidecar_root.glob("*.json")
    }
    assert set(records) == {public_digest, receipt_digest, successor_digest}
    assert records[receipt_digest]["confirmation_evidence"] == (
        "public_document_during_queue_lag"
    )
    assert records[receipt_digest]["queue_response_sha256"] is None
    assert records[successor_digest]["confirmation_evidence"] == (
        "recap_fetch_queue_status_2"
    )
    assert records[successor_digest]["queue_response_sha256"] is not None
    assert transport.requests == [
        ("GET", "/recap-documents/123/", {}),
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


def test_reconciled_receipt_retry_preserves_first_observation(tmp_path: Path) -> None:
    """synthetic: true; evolved retry metadata cannot replace create-once bytes."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    evolved_detail = {
        "id": 123,
        "is_available": True,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
        "date_modified": "2026-08-17T10:45:00Z",
    }
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _response("GET", "/recap-documents/123/", evolved_detail),
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
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )

        client.apply_broker_receipt("123", receipt)
        confirmed = journal.operation_records()[0]
        digest = canonical_purchase_operation_sha256(confirmed)
        sidecar_path = sidecar_root / f"{digest}.json"
        first_observation = sidecar_path.read_bytes()

        client.apply_broker_receipt("123", receipt)
        assert journal.operation_records() == (confirmed,)

    assert sidecar_path.read_bytes() == first_observation
    assert transport.requests[-4:] == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


def test_reconciled_receipt_retry_recovers_first_observation_staging_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """synthetic: true; retry repairs the exact crash-left sidecar alias."""

    ledger = (tmp_path / "purchases.sqlite3").resolve()
    policy = verify_case_dev_purchase_policy(_policy(ledger))
    sidecar_root = tmp_path / "confirmation-provenance"
    evolved_detail = {
        "id": 123,
        "is_available": True,
        "filepath_local": "https://storage.courtlistener.com/123.pdf",
        "date_modified": "2026-08-17T11:05:00Z",
    }
    transport = FixtureRecapFetchTransport(
        [
            _response("GET", "/recap-documents/123/", {"id": 123}),
            RecordedRecapFetchResponse("GET", "/recap-fetch/77/", {}, 502, {}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _available_document_response("123"),
            _response("GET", "/recap-fetch/77/", {"status": 2}),
            _response("GET", "/recap-documents/123/", evolved_detail),
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
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )
        client.apply_broker_receipt("123", receipt)
        confirmed = journal.operation_records()[0]
        digest = canonical_purchase_operation_sha256(confirmed)
        sidecar_path = sidecar_root / f"{digest}.json"
        first_observation = sidecar_path.read_bytes()
        stage_path = sidecar_root / (
            f".{sidecar_path.name}.{hashlib.sha256(first_observation).hexdigest()}.partial"
        )
        os.link(sidecar_path, stage_path)
        assert sidecar_path.stat().st_ino == stage_path.stat().st_ino
        assert sidecar_path.stat().st_nlink == 2

        fsynced_modes: list[int] = []
        real_fsync = os.fsync

        def record_fsync(descriptor: int) -> None:
            fsynced_modes.append(os.fstat(descriptor).st_mode)
            real_fsync(descriptor)

        monkeypatch.setattr(os, "fsync", record_fsync)
        client.apply_broker_receipt("123", receipt)
        assert journal.operation_records() == (confirmed,)

    assert sidecar_path.read_bytes() == first_observation
    assert sidecar_path.stat().st_nlink == 1
    assert not stage_path.exists()
    assert any(stat.S_ISDIR(mode) for mode in fsynced_modes)
    assert transport.requests[-4:] == [
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
        ("GET", "/recap-fetch/77/", {}),
        ("GET", "/recap-documents/123/", {}),
    ]


@pytest.mark.parametrize(
    "alias_kind",
    ("foreign", "multiple", "wrong-name", "wrong-digest"),
)
def test_reconciled_receipt_retry_rejects_untrusted_staging_aliases(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    """synthetic: true; only the exact same-inode deterministic alias recovers."""

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
        client.execute_purchase_plan(
            _plan(),
            public_documents=_public_documents(),
            live=True,
            acknowledge_pacer_fees=True,
        )
        public_operation = journal.operation_records()[0]
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )
        client.apply_broker_receipt("123", receipt)
        confirmed = journal.operation_records()[0]
        digest = canonical_purchase_operation_sha256(confirmed)
        sidecar_path = sidecar_root / f"{digest}.json"
        first_observation = sidecar_path.read_bytes()
        valid_stage = sidecar_root / (
            f".{sidecar_path.name}.{hashlib.sha256(first_observation).hexdigest()}.partial"
        )
        aliases: tuple[Path, ...]
        if alias_kind == "foreign":
            foreign_payload = b"foreign\n"
            foreign_stage = sidecar_root / (
                f".{sidecar_path.name}.{hashlib.sha256(foreign_payload).hexdigest()}.partial"
            )
            foreign_stage.write_bytes(foreign_payload)
            foreign_stage_alias = sidecar_root / "foreign-stage-alias"
            os.link(foreign_stage, foreign_stage_alias)
            final_alias = sidecar_root / "foreign-final-alias"
            os.link(sidecar_path, final_alias)
            aliases = (foreign_stage, foreign_stage_alias, final_alias)
        elif alias_kind == "multiple":
            os.link(sidecar_path, valid_stage)
            extra_alias = sidecar_root / "extra-final-alias"
            os.link(sidecar_path, extra_alias)
            aliases = (valid_stage, extra_alias)
        elif alias_kind == "wrong-name":
            wrong_name = sidecar_root / "crash-left.partial"
            os.link(sidecar_path, wrong_name)
            aliases = (wrong_name,)
        else:
            wrong_digest = sidecar_root / f".{sidecar_path.name}.{'0' * 64}.partial"
            os.link(sidecar_path, wrong_digest)
            aliases = (wrong_digest,)

        with pytest.raises(ConfirmationProvenanceError):
            client.apply_broker_receipt("123", receipt)
        assert journal.operation_records() == (confirmed,)

    assert sidecar_path.read_bytes() == first_observation
    assert all(alias.exists() for alias in aliases)
    assert len(transport.requests) == 5


def test_reconciled_receipt_retry_rejects_wrong_sidecar_identity(
    tmp_path: Path,
) -> None:
    """synthetic: true; an existing sidecar must bind to the current queue."""

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
        receipt = _broker_receipt(
            str(public_operation["operation_key"]),
            policy.policy_sha256,
            state="confirmed",
            authoritative_fee_usd="1.20",
        )
        client.apply_broker_receipt("123", receipt)
        confirmed = journal.operation_records()[0]
        digest = canonical_purchase_operation_sha256(confirmed)
        sidecar_path = sidecar_root / f"{digest}.json"
        tampered = json.loads(sidecar_path.read_text(encoding="utf-8"))
        tampered["queue_id"] = "88"
        sidecar_path.write_bytes(
            (
                json.dumps(
                    tampered,
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        )

        with pytest.raises(ConfirmationProvenanceError, match="identity conflicts"):
            client.apply_broker_receipt("123", receipt)
        assert journal.operation_records() == (confirmed,)

    assert len(transport.requests) == 5
