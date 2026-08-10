"""Focused regressions for provider-free preflight-manifest discovery."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import legalforecast.ingestion.cycle_preflight_manifest as manifest
import pytest
from legalforecast.ingestion.case_dev_purchase import CaseDevPurchaseSnapshot
from legalforecast.ingestion.cycle_preflight_manifest import (
    CyclePreflightManifestError,
    NativeRecoverySlice,
    _descriptor_matches,  # pyright: ignore[reportPrivateUsage]
    emit_discovery_sidecar,
)


def test_descriptor_join_does_not_require_resolution_to_list_recovery_card() -> None:
    recovery = Path("/authenticated/recovery/run-cards/recover.json")
    clearance = Path("/authenticated/clearance/run-cards/clearance.json")
    resolution = Path("/authenticated/resolution/run-cards/resolve.json")

    assert _descriptor_matches(
        {
            "kind": "successor",
            "ordinal": 1,
            "recovery_root": "/authenticated/recovery",
            "purchased_clearance_run_card": str(clearance),
            "resolved_post_recovery_documents": (
                "/authenticated/resolution/resolved-post-recovery-documents.jsonl"
            ),
        },
        recovery=recovery,
        clearance=clearance,
        resolution=resolution,
    )


def test_descriptor_join_rejects_wrong_recovery_root() -> None:
    recovery = Path("/authenticated/recovery/run-cards/recover.json")
    clearance = Path("/authenticated/clearance/run-cards/clearance.json")
    resolution = Path("/authenticated/resolution/run-cards/resolve.json")

    assert not _descriptor_matches(
        {
            "kind": "successor",
            "ordinal": 1,
            "recovery_root": "/other/recovery",
            "purchased_clearance_run_card": str(clearance),
            "resolved_post_recovery_documents": (
                "/authenticated/resolution/resolved-post-recovery-documents.jsonl"
            ),
        },
        recovery=recovery,
        clearance=clearance,
        resolution=resolution,
    )


def test_sidecar_is_create_only_and_non_authoritative(tmp_path: Path) -> None:
    slice_ = NativeRecoverySlice(
        cycle_id="cycle-1",
        lineage_root_identity_sha256="a" * 64,
        materialize_card=Path("/cards/materialize.json"),
        consolidation_card=Path("/cards/consolidation.json"),
        recovery_card=Path("/cards/recovery.json"),
        clearance_card=Path("/cards/clearance.json"),
        resolution_card=Path("/cards/resolution.json"),
        replacement_source_card=Path("/cards/source.json"),
    )
    output = tmp_path / "diagnostic.json"

    emit_discovery_sidecar(slice_, output=output)

    assert '"non_authoritative":true' in output.read_text(encoding="utf-8")
    with pytest.raises(CyclePreflightManifestError, match="already exists"):
        emit_discovery_sidecar(slice_, output=output)


def test_historical_replay_rejects_a_current_logical_state_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slice_ = NativeRecoverySlice(
        cycle_id="cycle-1",
        lineage_root_identity_sha256="a" * 64,
        materialize_card=Path("/cards/materialize.json"),
        consolidation_card=Path("/cards/consolidation.json"),
        recovery_card=Path("/cards/recovery.json"),
        clearance_card=Path("/cards/clearance.json"),
        resolution_card=Path("/cards/resolution.json"),
        replacement_source_card=Path("/cards/source.json"),
    )

    def fake_policy(_record: Mapping[str, object]) -> Any:
        return object()

    def fake_snapshot(*_args: object, **_kwargs: object) -> CaseDevPurchaseSnapshot:
        return CaseDevPurchaseSnapshot(
            operations=(),
            committed_amount_usd="0.00",
            purchase_state_sha256="b" * 64,
        )

    def fake_read_json(_path: Path, *, label: str) -> Mapping[str, object]:
        return (
            {"purchase_state_sha256": "a" * 64}
            if label == "replacement source card"
            else {}
        )

    monkeypatch.setattr(manifest, "verify_case_dev_purchase_policy", fake_policy)
    monkeypatch.setattr(manifest, "read_case_dev_purchase_snapshot", fake_snapshot)
    monkeypatch.setattr(manifest, "_read_json", fake_read_json)

    with pytest.raises(
        CyclePreflightManifestError, match="current logical purchase state"
    ):
        manifest.reconstruct_historical_purchase_snapshots(
            slice_,
            ledger_path=Path("/ledger.sqlite3"),
            policy_path=Path("/policy.json"),
            initialization_receipt_path=Path("/receipt.json"),
        )
