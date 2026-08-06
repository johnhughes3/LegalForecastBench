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


def test_issued_capability_detaches_nested_direct_queue_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_key = "00000000-0000-4000-8000-000000000000"
    lineage: dict[str, object] = {
        "candidate_id": "case-a",
        "source_document_id": "123",
        "recovery_run_card_sha256": "1" * 64,
        "recovery_manifest_sha256": "2" * 64,
        "recovery_restriction_evidence_sha256": "3" * 64,
        "purchase_state_sha256": "4" * 64,
        "purchase_operation_sha256": "5" * 64,
        "purchase_operation_key": operation_key,
        "fresh_recap_detail_sha256": "6" * 64,
        "direct_queue_delivery_authority": {
            "schema_version": (
                "legalforecast.direct_courtlistener_queue_delivery_authority.v1"
            ),
            "source_provider": "courtlistener.recap-fetch+pacer",
            "purchase_status": "queued",
            "operation_key": operation_key,
            "queue_id": "77",
            "reservation_id": f"direct:{operation_key}",
            "reservation_usd": "3.05",
            "queue_response_sha256": "7" * 64,
            "purchase_policy_sha256": "8" * 64,
            "purchase_operation_sha256": "5" * 64,
            "purchase_response_sha256": "9" * 64,
            "recovery_run_card_sha256": "1" * 64,
            "recovery_manifest_sha256": "2" * 64,
            "recovery_restriction_evidence_sha256": "3" * 64,
            "purchase_state_sha256": "4" * 64,
        },
    }
    capability = issue_recovered_public_capability(monkeypatch, [lineage])

    authority = cast(dict[str, object], lineage["direct_queue_delivery_authority"])
    authority["queue_id"] = "999"

    consumed = provenance_module._consume_recovered_public_clearance_capability(  # pyright: ignore[reportPrivateUsage]
        capability
    )
    assert (
        cast(
            dict[str, object],
            consumed[("case-a", "123")]["direct_queue_delivery_authority"],
        )["queue_id"]
        == "77"
    )
