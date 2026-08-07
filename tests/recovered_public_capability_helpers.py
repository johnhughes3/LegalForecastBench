"""Test-only construction through the recovered-public authenticator seam."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from legalforecast.ingestion import provenance_clearance as provenance_module
from legalforecast.ingestion import resolved_post_recovery as resolved_module


def issue_recovered_public_capability(
    monkeypatch: pytest.MonkeyPatch,
    rows: Sequence[Mapping[str, object]],
    *,
    terminal_records: Sequence[Mapping[str, object]] = (),
    source_snapshots: Mapping[Path, bytes] | None = None,
    legacy_without_terminal_ledger: bool = False,
) -> object:
    """Replace raw replay only where a unit test needs downstream authority."""

    terminal_path = (
        None
        if legacy_without_terminal_ledger
        else Path(
            "raw-recovery-evidence-owned-by-test-double/"
            "terminal-unavailable-operations.jsonl"
        )
    )
    terminal_bytes = b"".join(
        (json.dumps(dict(record), sort_keys=True) + "\n").encode("utf-8")
        for record in terminal_records
    )
    monkeypatch.setattr(
        provenance_module,
        "_authenticate_recovered_public_lineage_from_raw_evidence",
        lambda **_kwargs: provenance_module._AuthenticatedRecoveredPublicEvidence(  # pyright: ignore[reportPrivateUsage]
            lineage_rows=tuple(rows),
            terminal_records=tuple(terminal_records),
            terminal_path=terminal_path,
            terminal_sha256=hashlib.sha256(terminal_bytes).hexdigest(),
            source_snapshots=(
                dict(source_snapshots)
                if source_snapshots is not None
                else (
                    {terminal_path.resolve(): terminal_bytes}
                    if terminal_path is not None
                    else {}
                )
            ),
        ),
    )
    unused = Path("raw-recovery-evidence-owned-by-test-double")
    return provenance_module._issue_recovered_public_clearance_capability(  # pyright: ignore[reportPrivateUsage]
        recovery_root=unused,
        run_card_path=unused,
        selection_path=unused,
        purchase_policy_path=unused,
        cohort_policy_path=unused,
        ledger_path=unused,
        initialization_receipt_path=unused,
        controlled_private_root=None,
        expected_manifest_path=unused,
        expected_restriction_path=unused,
        expected_case_relevance_path=unused,
        expected_review_requests_path=unused,
        expected_document_root=unused,
    )


def issue_terminal_disposition_capability(
    monkeypatch: pytest.MonkeyPatch,
    recovery_capability: object,
    terminal_records: Sequence[Mapping[str, object]],
) -> object:
    """Issue test-only omission authority through the real closed boundary."""

    monkeypatch.setattr(
        resolved_module,
        "verified_terminal_purchase_disposition_record",
        lambda _authority, **_kwargs: {
            "terminal_failure_pairs": [
                {
                    "candidate_id": record["candidate_id"],
                    "source_document_id": record["source_document_id"],
                }
                for record in terminal_records
            ]
        },
    )
    return resolved_module._issue_terminal_disposition_capability(  # pyright: ignore[reportPrivateUsage]
        authority=object(),
        purchase_journal=object(),
        verified_recovery_capability=recovery_capability,
    )
