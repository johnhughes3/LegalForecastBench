# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
"""Focused regressions for provider-free preflight-manifest discovery."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
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


def test_sidecar_is_create_only_and_non_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    output = tmp_path / "diagnostic.json"
    monkeypatch.setattr(
        manifest, "discover_native_recovery_slice", lambda **_kwargs: slice_
    )
    monkeypatch.setattr(manifest, "_verify_v2_slice", lambda _slice: {"ok": True})

    emit_discovery_sidecar(slice_, index_path=tmp_path / "index.json", output=output)

    assert '"non_authoritative":true' in output.read_text(encoding="utf-8")
    with pytest.raises(CyclePreflightManifestError, match="already exists"):
        emit_discovery_sidecar(
            slice_, index_path=tmp_path / "index.json", output=output
        )


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


@pytest.mark.parametrize("field", ["lineage_root_identity_sha256", "materialize_card"])
def test_v2_sidecar_rejects_zeroed_or_swapped_active_identity(
    tmp_path: Path, field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sidecar cannot replace an authenticated locator's selected identity."""

    expected = NativeRecoverySlice(
        cycle_id="cycle-1",
        lineage_root_identity_sha256="a" * 64,
        materialize_card=Path("/cards/materialize.json"),
        consolidation_card=Path("/cards/consolidation.json"),
        recovery_card=Path("/cards/recovery.json"),
        clearance_card=Path("/cards/clearance.json"),
        resolution_card=Path("/cards/resolution.json"),
        replacement_source_card=Path("/cards/source.json"),
    )
    record: dict[str, object] = {
        "schema_version": manifest.SIDECAR_SCHEMA,
        "non_authoritative": True,
        "cycle_id": expected.cycle_id,
        "index_path": str(tmp_path / "index.json"),
        "lineage_root_identity_sha256": expected.lineage_root_identity_sha256,
        "native_cards": {
            "materialize": str(expected.materialize_card),
            "consolidation": str(expected.consolidation_card),
            "recovery": str(expected.recovery_card),
            "clearance": str(expected.clearance_card),
            "resolution": str(expected.resolution_card),
            "replacement_source": str(expected.replacement_source_card),
        },
    }
    if field == "lineage_root_identity_sha256":
        record[field] = "0" * 64
    else:
        native_cards = record["native_cards"]
        assert isinstance(native_cards, dict)
        native_cards["materialize"] = "/cards/nonexistent.json"
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(
        manifest, "discover_native_recovery_slice", lambda **_kwargs: expected
    )

    with pytest.raises(CyclePreflightManifestError, match="differs from active"):
        manifest.verify_v2_sidecar(sidecar)


def test_output_tree_rejects_tampered_or_malformed_entries(tmp_path: Path) -> None:
    root = tmp_path / "documents"
    root.mkdir()
    document = root / "one.pdf"
    document.write_bytes(b"authenticated")
    digest = "sha256:" + hashlib.sha256(document.read_bytes()).hexdigest()
    card = {
        "output_paths": [str(root)],
        "output_commitments": {"document_tree": {"one.pdf": digest}},
    }

    manifest._verify_card_outputs(tmp_path / "card.json", card, label="test")
    document.write_bytes(b"tampered")
    with pytest.raises(CyclePreflightManifestError, match="bytes differ"):
        manifest._verify_card_outputs(tmp_path / "card.json", card, label="test")
    malformed = {
        "output_paths": [str(root)],
        "output_commitments": {"document_tree": {"../escape.pdf": digest}},
    }
    with pytest.raises(CyclePreflightManifestError, match="escapes root"):
        manifest._verify_card_outputs(tmp_path / "card.json", malformed, label="test")


def test_producer_input_tamper_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_bytes(b"original")
    digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    card = {"source_commitments": {str(source): digest}}
    manifest._verify_card_inputs(card, label="test producer")
    source.write_bytes(b"replacement")
    with pytest.raises(CyclePreflightManifestError, match="bytes differ"):
        manifest._verify_card_inputs(card, label="test producer")


def test_malformed_ordinal_descriptor_fails_closed() -> None:
    with pytest.raises(CyclePreflightManifestError, match="descriptor is malformed"):
        manifest._validate_descriptor({"kind": "successor", "ordinal": 1})


def test_sidecar_emission_rejects_a_toctou_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = NativeRecoverySlice(
        cycle_id="cycle-1",
        lineage_root_identity_sha256="a" * 64,
        materialize_card=Path("/cards/materialize.json"),
        consolidation_card=Path("/cards/consolidation.json"),
        recovery_card=Path("/cards/recovery.json"),
        clearance_card=Path("/cards/clearance.json"),
        resolution_card=Path("/cards/resolution.json"),
        replacement_source_card=Path("/cards/source.json"),
    )
    changed = replace(first, recovery_card=Path("/cards/replaced.json"))
    observations = iter((first, changed))
    monkeypatch.setattr(
        manifest, "discover_native_recovery_slice", lambda **_kwargs: next(observations)
    )
    monkeypatch.setattr(manifest, "_verify_v2_slice", lambda _slice: {"ok": True})

    with pytest.raises(CyclePreflightManifestError, match="changed during sidecar"):
        emit_discovery_sidecar(
            first, index_path=tmp_path / "index.json", output=tmp_path / "sidecar.json"
        )
