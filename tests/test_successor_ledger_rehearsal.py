"""Acceptance rehearsal for the authenticated successor-ledger vertical slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseSnapshot,
    canonical_purchase_operation_sha256,
    canonical_purchase_state_sha256,
)
from legalforecast.ingestion.replacement_purchase_approval import (
    ReplacementPurchaseApprovalError,
    verify_replacement_purchase_authority,
)
from legalforecast.ingestion.replacement_recovery_source import (
    RecoverySourceCoordinates,
    ReplacementRecoverySourceError,
    build_recovery_source_descriptor,
    derive_resolved_source_coordinates,
)
from legalforecast.ingestion.resolved_post_recovery import ResolvedPostRecoveryError
from tests.successor_ledger_rehearsal_fixtures import (
    build_successor_ledger_rehearsal,
    reconstructed_transition,
)


def _authority(rehearsal_root: Path) -> dict[str, object]:
    return json.loads(
        (rehearsal_root / "successor-authority.json").read_text(encoding="utf-8")
    )


def _sha256_uri(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_successor_ledger_rehearsal_replays_real_history_and_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rehearsal = build_successor_ledger_rehearsal(tmp_path, monkeypatch=monkeypatch)

    # The unchanged unrelated operation is a baseline commitment in the real
    # successor approval, while the selected successor record moved through the
    # material-clearance state machine.
    assert rehearsal.baseline_operation_sha256 in set(
        rehearsal.request.baseline_operation_record_sha256s
    )
    assert reconstructed_transition(rehearsal) == rehearsal.transition_before
    after = next(
        operation
        for operation in rehearsal.transition_after.operations
        if operation["source_document_id"]
        == rehearsal.resolved_record["source_document_id"]
    )
    assert after["material_state"] == "cleared_public"

    # This is the first downstream consumer of the two production-produced
    # descriptors.  It makes ordinals 0/1 a fail-closed artifact boundary.
    index_root = rehearsal.root / "index"
    assert (
        cli._cmd_build_replacement_recovery_index(  # pyright: ignore[reportPrivateUsage]
            argparse.Namespace(
                output_root=index_root,
                initial_source=rehearsal.initial_descriptor,
                successor_source=[rehearsal.successor_descriptor],
                index_output=None,
                run_card_output=None,
                execute=True,
                resume=False,
            )
        )
        == 0
    )
    index = json.loads(
        (index_root / "tranche-recovery-index.json").read_text(encoding="utf-8")
    )
    assert [(row["kind"], row["ordinal"]) for row in index["sources"]] == [
        ("initial_v2", 0),
        ("successor", 1),
    ]


def test_successor_ledger_rehearsal_fails_closed_on_authority_and_transition_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rehearsal = build_successor_ledger_rehearsal(tmp_path, monkeypatch=monkeypatch)
    policy_artifact = json.loads(
        rehearsal.fixture["policy_path"].read_text(encoding="utf-8")
    )
    cohort_artifact = json.loads(
        rehearsal.fixture["cohort_path"].read_text(encoding="utf-8")
    )

    # Altering a successor-authority field invalidates its canonical authority
    # digest before the live SQLite journal can authorize a successor operation.
    authority = _authority(rehearsal.root)
    authority_body = authority["authority"]
    assert isinstance(authority_body, dict)
    authority_body["reviewer_id"] = "not-the-approved-reviewer"
    with pytest.raises(ReplacementPurchaseApprovalError, match="hash differs"):
        verify_replacement_purchase_authority(
            authority_artifact=authority,
            controlled_private_root=(rehearsal.root / "successor-private"),
            initial_purchase_policy_artifact=policy_artifact,
            initial_controlled_private_root=rehearsal.fixture["initial_private_root"],
            cohort_policy_artifact=cohort_artifact,
            budget_plan_bytes=rehearsal.fixture["budget_path"].read_bytes(),
            selection_bytes=rehearsal.fixture["selection_path"].read_bytes(),
            purchase_ledger_path=rehearsal.fixture["ledger_path"],
            purchase_ledger_initialization_receipt_path=rehearsal.fixture[
                "receipt_path"
            ],
        )

    # A replacement of the unrelated baseline operation produces a different
    # exact historical state and is not silently masked by the resolver replay.
    changed_before = list(rehearsal.transition_before.operations)
    baseline_index = next(
        index
        for index, operation in enumerate(changed_before)
        if operation["source_document_id"] == "unrelated-baseline-document"
    )
    changed = dict(changed_before[baseline_index])
    changed["candidate_id"] = "tampered-baseline-case"
    changed_before[baseline_index] = changed
    assert (
        canonical_purchase_operation_sha256(changed)
        != rehearsal.baseline_operation_sha256
    )
    tampered_after = list(rehearsal.transition_after.operations)
    after_baseline_index = next(
        index
        for index, operation in enumerate(tampered_after)
        if operation["source_document_id"] == "unrelated-baseline-document"
    )
    tampered_after[after_baseline_index] = changed
    tampered_after_snapshot = CaseDevPurchaseSnapshot(
        operations=tuple(tampered_after),
        committed_amount_usd=rehearsal.transition_after.committed_amount_usd,
        purchase_state_sha256=canonical_purchase_state_sha256(
            rehearsal.fixture["policy"],
            committed_amount_usd=rehearsal.transition_after.committed_amount_usd,
            operations=tampered_after,
        ),
    )
    with pytest.raises(
        ResolvedPostRecoveryError,
        match="does not reproduce its prior state",
    ):
        from legalforecast.ingestion.resolved_post_recovery import (
            reconstruct_pre_resolution_purchase_snapshot,
        )

        reconstruct_pre_resolution_purchase_snapshot(
            current_snapshot=tampered_after_snapshot,
            resolved_records=(rehearsal.resolved_record,),
            policy=rehearsal.fixture["policy"],
            expected_purchase_state_before_sha256=(
                rehearsal.transition_before.purchase_state_sha256
            ),
        )

    tampered_resolved = deepcopy(rehearsal.resolved_record)
    tampered_resolved["clearance_record_sha256"] = "1" * 64
    with pytest.raises(
        ResolvedPostRecoveryError, match="resolved document hash changed"
    ):
        from legalforecast.ingestion.resolved_post_recovery import (
            reconstruct_pre_resolution_purchase_snapshot,
        )

        reconstruct_pre_resolution_purchase_snapshot(
            current_snapshot=rehearsal.transition_after,
            resolved_records=(tampered_resolved,),
            policy=rehearsal.fixture["policy"],
            expected_purchase_state_before_sha256=(
                rehearsal.transition_before.purchase_state_sha256
            ),
        )

    # Ordinal 1 is mandatory for a successor descriptor; a source cannot be
    # relabeled as an initial root to evade the multi-root history boundary.
    successor = json.loads(rehearsal.successor_descriptor.read_text(encoding="utf-8"))
    successor["ordinal"] = 0
    with pytest.raises(ReplacementRecoverySourceError, match="ordinal"):
        build_recovery_source_descriptor(
            coordinates=RecoverySourceCoordinates(
                kind="successor",
                selection_path=Path(successor["selection"]),
                purchase_policy_path=rehearsal.fixture["policy_path"],
                cohort_policy_path=rehearsal.fixture["cohort_path"],
                budget_plan_path=Path(successor["replacement_budget_plan"]),
                purchase_ledger_path=rehearsal.fixture["ledger_path"],
                attempt_policy_path=rehearsal.root / "successor-attempt-policy.json",
                replacement_authority_path=rehearsal.authority_path,
            ),
            ordinal=0,
            recovery_root=rehearsal.root / "successor-recovery",
            purchased_clearance_path=rehearsal.root / "successor-clearance.jsonl",
            purchased_clearance_run_card_path=(
                rehearsal.root / "successor-clearance-card.json"
            ),
            resolved_post_recovery_documents_path=(
                rehearsal.root / "successor-resolved.jsonl"
            ),
            replacement_controlled_private_root=rehearsal.root / "successor-private",
        )


def test_successor_ledger_rehearsal_rejects_terminal_omission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolved card cannot drop any terminal-disposition source silently."""

    rehearsal = build_successor_ledger_rehearsal(tmp_path, monkeypatch=monkeypatch)
    root = rehearsal.root / "terminal-omission"
    selection = _write(root / "selection.jsonl", b"{}\n")
    ledger = _write(root / "journal.sqlite3", b"fixture-ledger\n")
    terminal = _write(root / "terminal.jsonl", b'{"terminal":true}\n')
    resolved = _write(root / "resolved.jsonl", b"{}\n")
    disposition = {
        name: _write(root / f"{name}.json", f"{name}\n".encode())
        for name in (
            "selection",
            "snapshot_manifest",
            "purchase_result",
            "purchase_run_card",
        )
    }
    inputs = (selection, ledger, terminal, *disposition.values())
    card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "resolve-post-recovery-documents",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "input_paths": [str(path) for path in inputs],
        "output_paths": [str(resolved), str(ledger)],
        "source_commitments": {
            f"input_{index:02d}": {"path": str(path), "sha256": _sha256_uri(path)}
            for index, path in enumerate(inputs)
        },
        "output_commitments": {
            "resolved_post_recovery_documents": {
                "path": str(resolved),
                "sha256": _sha256_uri(resolved),
            },
            "purchase_state_sha256": "sha256:" + "a" * 64,
        },
        "purchase_state_after_sha256": "sha256:" + "a" * 64,
        "terminal_unavailable_partition": {
            "path": str(terminal),
            "sha256": _sha256_uri(terminal),
            "record_count": 1,
        },
        "terminal_disposition_sources": {
            name: str(path) for name, path in disposition.items()
        },
    }
    coordinates = derive_resolved_source_coordinates(
        card,
        expected_input_paths=inputs,
        expected_ledger_path=ledger,
        expected_purchase_state_sha256="sha256:" + "a" * 64,
        expected_terminal_unavailable_path=terminal,
        expected_terminal_unavailable_sha256=_sha256_uri(terminal),
        expected_terminal_unavailable_count=1,
        expected_terminal_disposition_paths=disposition,
    )
    assert coordinates.terminal_unavailable_count == 1

    terminal_sources = cast(dict[str, str], card["terminal_disposition_sources"])
    terminal_sources.pop("purchase_run_card")
    with pytest.raises(
        ReplacementRecoverySourceError,
        match="terminal disposition sources differ",
    ):
        derive_resolved_source_coordinates(
            card,
            expected_input_paths=inputs,
            expected_ledger_path=ledger,
            expected_purchase_state_sha256="sha256:" + "a" * 64,
            expected_terminal_unavailable_path=terminal,
            expected_terminal_unavailable_sha256=_sha256_uri(terminal),
            expected_terminal_unavailable_count=1,
            expected_terminal_disposition_paths=disposition,
        )
