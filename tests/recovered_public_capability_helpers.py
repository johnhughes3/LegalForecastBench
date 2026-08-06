"""Test-only construction through the recovered-public authenticator seam."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from legalforecast.ingestion import provenance_clearance as provenance_module


def issue_recovered_public_capability(
    monkeypatch: pytest.MonkeyPatch,
    rows: Sequence[Mapping[str, object]],
) -> object:
    """Replace raw replay only where a unit test needs downstream authority."""

    monkeypatch.setattr(
        provenance_module,
        "_authenticate_recovered_public_lineage_from_raw_evidence",
        lambda **_kwargs: rows,
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
