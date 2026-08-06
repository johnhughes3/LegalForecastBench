"""Regressions for recovered-public capability issuance."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from legalforecast.ingestion import provenance_clearance as provenance_module
from tests.recovered_public_capability_helpers import (
    issue_recovered_public_capability,
)


def test_caller_supplied_lineage_cannot_mint_recovered_public_authority() -> None:
    lineage = {
        "candidate_id": "case-a",
        "source_document_id": "123",
        "recovery_run_card_sha256": "1" * 64,
        "recovery_manifest_sha256": "2" * 64,
        "recovery_restriction_evidence_sha256": "3" * 64,
        "purchase_state_sha256": "4" * 64,
        "purchase_operation_sha256": "5" * 64,
        "purchase_operation_key": "00000000-0000-4000-8000-000000000000",
        "fresh_recap_detail_sha256": "6" * 64,
    }

    issuer = cast(
        Callable[[object], object],
        provenance_module._issue_recovered_public_clearance_capability,  # pyright: ignore[reportPrivateUsage]
    )
    with pytest.raises(TypeError):
        issuer([lineage])


def test_consumed_recovered_public_state_is_not_the_capability_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lineage = {
        "candidate_id": "case-a",
        "source_document_id": "123",
        "recovery_run_card_sha256": "1" * 64,
        "recovery_manifest_sha256": "2" * 64,
        "recovery_restriction_evidence_sha256": "3" * 64,
        "purchase_state_sha256": "4" * 64,
        "purchase_operation_sha256": "5" * 64,
        "purchase_operation_key": "00000000-0000-4000-8000-000000000000",
        "fresh_recap_detail_sha256": "6" * 64,
    }
    capability = issue_recovered_public_capability(monkeypatch, [lineage])

    consumed = provenance_module._consume_recovered_public_clearance_capability(  # pyright: ignore[reportPrivateUsage]
        capability
    )
    cast(dict[str, object], consumed[("case-a", "123")])["purchase_state_sha256"] = (
        "9" * 64
    )

    assert (
        provenance_module._consume_recovered_public_clearance_capability(  # pyright: ignore[reportPrivateUsage]
            capability
        )[("case-a", "123")]["purchase_state_sha256"]
        == "4" * 64
    )
