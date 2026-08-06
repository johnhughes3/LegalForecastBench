"""Regressions for recovered-public capability issuance."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion import provenance_clearance as provenance_module
from legalforecast.ingestion import resolved_post_recovery as resolved_module
from tests.recovered_public_capability_helpers import (
    issue_recovered_public_capability,
    issue_terminal_disposition_capability,
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


def test_capability_owns_exact_recovery_source_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = (tmp_path / "recovery-run-card.json").resolve()
    verified_bytes = b'{"status":"completed"}\n'
    capability = issue_recovered_public_capability(
        monkeypatch,
        [],
        source_snapshots={source: verified_bytes},
    )

    consumed = provenance_module._consume_recovered_public_source_snapshots(  # pyright: ignore[reportPrivateUsage]
        capability
    )
    assert consumed == {source: verified_bytes}
    cast(dict[Path, bytes], consumed)[source] = b"forged"
    assert provenance_module._consume_recovered_public_source_snapshots(  # pyright: ignore[reportPrivateUsage]
        capability
    ) == {source: verified_bytes}
    with pytest.raises(
        provenance_module.ProvenanceClearanceError,
        match="verifier-issued capability",
    ):
        provenance_module._consume_recovered_public_source_snapshots(  # pyright: ignore[reportPrivateUsage]
            object()
        )


def test_materializer_kwargs_merge_clearance_and_capability_recovery_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    names = (
        "clearance",
        "run-card",
        "restriction",
        "routing-plan",
        "worksheet",
        "cohort-policy",
        "manifest",
    )
    paths = {name: (tmp_path / f"{name}.json").resolve() for name in names}
    clearance_bytes = {str(path): b"{}\n" for path in paths.values()}
    recovery_path = (tmp_path / "recovery-run-card.json").resolve()
    recovery_bytes = b'{"status":"completed"}\n'
    capability = issue_recovered_public_capability(
        monkeypatch,
        [],
        source_snapshots={recovery_path: recovery_bytes},
    )
    lineage = {
        "lineage_kind": "provider_free_recovered_public",
        "restriction_path": paths["restriction"],
        "routing_plan_path": paths["routing-plan"],
        "worksheet_path": paths["worksheet"],
        "cohort_policy_path": paths["cohort-policy"],
        "manifest_path": paths["manifest"],
        "restriction_records": (),
        "authenticated_recovery_capability": capability,
        "verified_artifact_bytes": clearance_bytes,
    }

    kwargs = cli._materializer_clearance_lineage_kwargs(
        clearance_path=paths["clearance"],
        run_card_path=paths["run-card"],
        lineage=lineage,
    )

    snapshots = cast(dict[str, bytes], kwargs["_verified_clearance_source_snapshots"])
    assert snapshots[str(recovery_path)] == recovery_bytes
    assert snapshots[str(paths["clearance"])] == b"{}\n"

    incomplete_lineage = {
        **lineage,
        "verified_artifact_bytes": {
            key: payload
            for key, payload in clearance_bytes.items()
            if key != str(paths["worksheet"])
        },
    }
    with pytest.raises(
        cli.CommandError,
        match="verified recovered-public snapshot lacks downstream input",
    ):
        cli._materializer_clearance_lineage_kwargs(
            clearance_path=paths["clearance"],
            run_card_path=paths["run-card"],
            lineage=incomplete_lineage,
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


def test_capability_authenticates_immutable_terminal_partition(
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
    terminal = {
        "schema_version": "legalforecast.recap_fetch_terminal_unavailable.v1",
        "candidate_id": "case-b",
        "source_document_id": "456",
    }
    capability = issue_recovered_public_capability(
        monkeypatch,
        [lineage],
        terminal_records=[terminal],
    )

    partition = provenance_module._consume_recovered_public_terminal_partition(  # pyright: ignore[reportPrivateUsage]
        capability
    )
    assert partition.keys == frozenset({("case-b", "456")})
    assert partition.record_count == 1
    assert partition.path.name == "terminal-unavailable-operations.jsonl"

    with pytest.raises(AttributeError):
        cast(set[tuple[str, str]], partition.keys).add(("forged", "999"))
    assert provenance_module._consume_recovered_public_terminal_partition(  # pyright: ignore[reportPrivateUsage]
        capability
    ).keys == frozenset({("case-b", "456")})


def test_legacy_capability_has_no_invented_terminal_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = issue_recovered_public_capability(
        monkeypatch,
        [],
        legacy_without_terminal_ledger=True,
    )

    assert (
        provenance_module._consume_recovered_public_terminal_partition(  # pyright: ignore[reportPrivateUsage]
            capability
        )
        is None
    )


def test_capability_rejects_recovered_terminal_overlap(
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
    terminal = {
        "schema_version": "legalforecast.recap_fetch_terminal_unavailable.v1",
        "candidate_id": "case-a",
        "source_document_id": "123",
    }

    with pytest.raises(
        provenance_module.ProvenanceClearanceError,
        match="overlaps recovered material",
    ):
        issue_recovered_public_capability(
            monkeypatch,
            [lineage],
            terminal_records=[terminal],
        )


def test_terminal_disposition_capability_must_equal_recovery_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery_terminal = {
        "schema_version": "legalforecast.recap_fetch_terminal_unavailable.v1",
        "candidate_id": "case-a",
        "source_document_id": "123",
    }
    capability = issue_recovered_public_capability(
        monkeypatch,
        [],
        terminal_records=[recovery_terminal],
    )

    with pytest.raises(
        resolved_module.ResolvedPostRecoveryError,
        match="differs from recovery terminal partition",
    ):
        issue_terminal_disposition_capability(
            monkeypatch,
            capability,
            [
                {
                    "schema_version": (
                        "legalforecast.recap_fetch_terminal_unavailable.v1"
                    ),
                    "candidate_id": "case-b",
                    "source_document_id": "456",
                }
            ],
        )
