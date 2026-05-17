from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.publication.withdrawal import (
    PUBLIC_ERRATA_SCHEMA_VERSION,
    WITHDRAWAL_LEDGER_SCHEMA_VERSION,
    WithdrawalLedger,
    WithdrawalLedgerEntry,
    WithdrawalReason,
    WithdrawalScope,
    build_public_errata_record,
    filter_withdrawn_run_inputs,
    load_withdrawal_ledger,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def test_withdrawal_ledger_serializes_and_filters_future_run_inputs(
    tmp_path: Path,
) -> None:
    entry = _entry()
    ledger = WithdrawalLedger((entry,))

    output_path = ledger.write_jsonl(tmp_path / "withdrawal-ledger.jsonl")
    loaded = load_withdrawal_ledger(output_path)

    records = loaded.to_records()
    assert records[0]["schema_version"] == WITHDRAWAL_LEDGER_SCHEMA_VERSION
    assert records[0]["effective_at"] == "2026-05-17T18:30:00Z"
    assert records[0]["future_use_blocked"] is True

    run_inputs = [
        {"case_id": "case-1", "packet_object_key": "model-packets/cycle/case-1/a.json"},
        {"case_id": "case-2", "packet_object_key": "model-packets/cycle/case-2/a.json"},
        {
            "case_id": "case-3",
            "source_document_ids": ["doc-withdrawn"],
            "packet_object_key": "model-packets/cycle/case-3/a.json",
        },
    ]

    assert loaded.filter_run_inputs(run_inputs) == [
        {"case_id": "case-2", "packet_object_key": "model-packets/cycle/case-2/a.json"}
    ]
    assert filter_withdrawn_run_inputs(run_inputs, loaded) == loaded.filter_run_inputs(
        run_inputs
    )


def test_public_errata_omits_private_storage_and_document_details() -> None:
    entry = _entry()

    errata = build_public_errata_record(
        entry,
        issued_at=datetime(2026, 5, 17, 19, 0, tzinfo=UTC),
        summary="A sealed source document was withdrawn from future official runs.",
    )

    assert errata["schema_version"] == PUBLIC_ERRATA_SCHEMA_VERSION
    assert errata["withdrawal_id"] == "wd-2026-001"
    assert errata["supersedes_manifest_sha256"] == f"sha256:{SHA_A}"
    assert errata["replacement_manifest_sha256"] == f"sha256:{SHA_B}"
    assert "packet_object_keys" not in errata
    assert "source_document_ids" not in errata
    assert "private_tombstone_key" not in errata
    assert "raw filing" not in json.dumps(errata).lower()


def test_withdrawal_entry_rejects_records_that_do_not_block_future_use() -> None:
    with pytest.raises(ValueError, match="block future use"):
        _entry(future_use_blocked=False)


def test_withdrawal_entry_rejects_unsafe_private_and_public_paths() -> None:
    with pytest.raises(ValueError, match="private_tombstone_key"):
        _entry(private_tombstone_key="source-documents/cycle/case/doc.pdf")

    with pytest.raises(ValueError, match="packet_object_keys"):
        _entry(packet_object_keys=("audit-bundles/cycle/case/audit.json",))

    with pytest.raises(ValueError, match="errata_path"):
        _entry(errata_path="source-documents/cycle/private.json")

    with pytest.raises(ValueError, match="unsafe path"):
        _entry(public_artifact_paths=("reports/../private.txt",))


def test_withdrawal_ledger_rejects_duplicate_ids() -> None:
    entry = _entry()
    with pytest.raises(ValueError, match="withdrawal_id"):
        WithdrawalLedger((entry, entry))


def _entry(
    *,
    future_use_blocked: bool = True,
    private_tombstone_key: str = "quarantine/cycle-2026-05/case-1/tombstone.json",
    packet_object_keys: tuple[str, ...] = (
        "model-packets/cycle-2026-05/case-1/default.json",
    ),
    errata_path: str = "manifests/cycle-2026-05/errata/wd-2026-001.json",
    public_artifact_paths: tuple[str, ...] = ("reports/cycle-2026-05/old-score.json",),
) -> WithdrawalLedgerEntry:
    return WithdrawalLedgerEntry(
        withdrawal_id="wd-2026-001",
        cycle_id="cycle-2026-05",
        scope=WithdrawalScope.CASE,
        reason=WithdrawalReason.SEALED_OR_RESTRICTED.value,
        public_reason="sealed_or_restricted",
        effective_at=datetime(2026, 5, 17, 18, 30, tzinfo=UTC),
        case_id="case-1",
        candidate_id="cand-1",
        source_document_ids=("doc-withdrawn",),
        packet_object_keys=packet_object_keys,
        public_artifact_paths=public_artifact_paths,
        private_tombstone_key=private_tombstone_key,
        errata_path=errata_path,
        supersedes_manifest_sha256=f"sha256:{SHA_A}",
        replacement_manifest_sha256=f"sha256:{SHA_B}",
        score_bundle_superseded=True,
        future_use_blocked=future_use_blocked,
    )
