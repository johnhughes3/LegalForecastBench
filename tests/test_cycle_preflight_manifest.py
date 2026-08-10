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
    verification_count = 0

    def verify(_slice: NativeRecoverySlice) -> dict[str, bool]:
        nonlocal verification_count
        verification_count += 1
        return {"ok": True}

    monkeypatch.setattr(manifest, "_verify_v2_slice", verify)

    emit_discovery_sidecar(slice_, index_path=tmp_path / "index.json", output=output)

    assert '"non_authoritative":true' in output.read_text(encoding="utf-8")
    assert verification_count == 2
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
    index = tmp_path / "index.json"
    index.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        manifest, "discover_native_recovery_slice", lambda **_kwargs: expected
    )

    with pytest.raises(CyclePreflightManifestError, match="differs from active"):
        manifest.verify_v2_sidecar(sidecar, trusted_index_path=index)


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


def test_producer_document_tree_byte_tamper_fails_closed(tmp_path: Path) -> None:
    """Tree commitments bind file bytes, not merely the number of documents."""

    root = tmp_path / "documents"
    root.mkdir()
    document = root / "record.txt"
    document.write_bytes(b"original")
    observed = manifest._document_tree_commitment(root, label="test producer")
    digest = (
        "sha256:"
        + hashlib.sha256(
            manifest.canonical_json_value_bytes(
                observed,
                error_type=CyclePreflightManifestError,
                error_message="test tree cannot be encoded",
            )
        ).hexdigest()
    )
    card = {
        "source_commitments": {
            "documents": {
                "path": str(root),
                "document_count": 1,
                "tree_sha256": digest,
            }
        }
    }

    manifest._verify_card_inputs(card, label="test producer")
    document.write_bytes(b"replaced")
    with pytest.raises(CyclePreflightManifestError, match="tree differs"):
        manifest._verify_card_inputs(card, label="test producer")


def test_uncommitted_self_authored_producer_fails_closed(tmp_path: Path) -> None:
    """A descriptor's canonical producer path cannot supply an empty closure."""

    clearance = tmp_path / "clearance.json"
    resolution = tmp_path / "resolution.jsonl"
    selection = tmp_path / "selection.jsonl"
    descriptor = tmp_path / "0000-initial-v2.json"
    descriptor.write_text(
        json.dumps(
            {
                "kind": "initial_v2",
                "ordinal": 0,
                "purchased_clearance_run_card": str(clearance),
                "resolved_post_recovery_documents": str(resolution),
                "selection": str(selection),
            }
        ),
        encoding="utf-8",
    )
    producer = tmp_path / "run-cards" / "build-replacement-recovery-source-0000.json"
    producer.parent.mkdir()
    producer.write_text(
        json.dumps(
            {
                "stage": "build-replacement-recovery-source",
                "ordinal": 0,
                "source_commitments": {},
            }
        ),
        encoding="utf-8",
    )
    commitment = "sha256:" + hashlib.sha256(descriptor.read_bytes()).hexdigest()

    with pytest.raises(CyclePreflightManifestError, match="authenticated closure"):
        manifest._producer_for_descriptor(
            descriptor, index_commitments={descriptor: commitment}
        )


def test_sidecar_cannot_select_a_parallel_untrusted_index(tmp_path: Path) -> None:
    """The caller chooses the index; a diagnostic sidecar is locator-only."""

    trusted_index = tmp_path / "trusted-index.json"
    fake_index = tmp_path / "parallel-index.json"
    trusted_index.write_text("{}", encoding="utf-8")
    fake_index.write_text("{}", encoding="utf-8")
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": manifest.SIDECAR_SCHEMA,
                "non_authoritative": True,
                "cycle_id": "cycle-1",
                "index_path": str(fake_index),
                "lineage_root_identity_sha256": "a" * 64,
                "native_cards": {
                    "materialize": "/cards/materialize.json",
                    "consolidation": "/cards/consolidation.json",
                    "recovery": "/cards/recovery.json",
                    "clearance": "/cards/clearance.json",
                    "resolution": "/cards/resolution.json",
                    "replacement_source": "/cards/source.json",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CyclePreflightManifestError, match="trusted lineage index"):
        manifest.verify_v2_sidecar(sidecar, trusted_index_path=trusted_index)


def test_terminal_resolution_must_match_historical_replay() -> None:
    with pytest.raises(CyclePreflightManifestError, match="historical replay"):
        manifest._verify_terminal_resolution_transition(
            Path("/cards/source-selected-resolution.json"),
            historical_resolution=Path("/cards/historical-resolution.json"),
        )


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


def test_sidecar_verification_rechecks_stable_paths_after_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A content change at stable paths is caught by the final semantic pass."""

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
    index = tmp_path / "index.json"
    index.write_text("{}", encoding="utf-8")
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": manifest.SIDECAR_SCHEMA,
                "non_authoritative": True,
                "cycle_id": expected.cycle_id,
                "index_path": str(index),
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
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        manifest, "discover_native_recovery_slice", lambda **_kwargs: expected
    )
    reports = iter(({"ok": True}, {"ok": False}))
    monkeypatch.setattr(manifest, "_verify_v2_slice", lambda _slice: next(reports))

    with pytest.raises(
        CyclePreflightManifestError, match="changed during verification"
    ):
        manifest.verify_v2_sidecar(sidecar, trusted_index_path=index)
