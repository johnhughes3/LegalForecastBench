from __future__ import annotations

import copy
import hashlib
import json
from argparse import Namespace
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
import legalforecast.ingestion.courtlistener_case_dev_bridge as bridge_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import generate_case_dev_purchase_policy
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads


def test_bridge_pacer_gaps_help_documents_identity_and_free_first_flags(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "bridge-pacer-gaps", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "--screened-cases" in output
    assert "--live-case-dev" in output
    assert "--live-courtlistener" in output
    assert "--courtlistener-fixture" in output
    assert "never invokes a PACER purchase endpoint" in normalized
    assert "Never invokes RECAP Fetch or PACER" in normalized
    assert "--case-relevance-output" in output
    assert "--public-selection" in output
    assert "--paid-gaps" in output
    assert "--free-download-manifest" in output
    assert "Run download-free" in output
    assert "--checkpoint-dir" in output
    assert "--checkpoint-config-output" in output
    assert "--request-ledger" in output
    assert "--courtlistener-rate-profile" in output
    assert "--request-budget-max-wait-seconds" in output
    assert "resume skips terminal candidates" in normalized


def test_rebase_pacer_gap_checkpoints_help_is_explicitly_noncharging(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "rebase-pacer-gap-checkpoints", "--help"])
    assert exc_info.value.code == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "--previous-checkpoint-dir" in output
    assert "--current-paid-gaps" in output
    assert "--receipt-output" in output
    assert "--previous-snapshot" in output
    assert "--expected-added-candidate-id" in output
    assert "--expected-invalidated-candidate-id" in output
    assert "same-cycle union" in output
    assert "constructs no provider client" in output
    assert "performs no purchase" in output


def test_rebase_pacer_gap_checkpoints_reorders_atomically_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    monkeypatch.setattr(
        cli,
        "_courtlistener_bridge_client",
        lambda *args, **kwargs: pytest.fail("rebase constructed a provider client"),
    )

    assert main(fixture["command"]) == 0
    first_bytes = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    first_config = fixture["destination_config"].read_bytes()
    first_receipt = fixture["receipt"].read_bytes()
    assert main(fixture["command"]) == 0
    assert first_bytes == {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    assert fixture["destination_config"].read_bytes() == first_config
    assert fixture["receipt"].read_bytes() == first_receipt

    checkpoints = sorted(
        (
            _read_json(path)
            for path in fixture["destination_checkpoint_dir"].glob("*.json")
        ),
        key=lambda record: cast(int, record["input_index"]),
    )
    assert [record["candidate_id"] for record in checkpoints] == ["cl-456"]
    assert checkpoints[0]["outcome"] == "success"
    assert checkpoints[0]["payload"]["selection_record"]["cost_rank"] == 1
    assert all(record["resumable_attempt_count"] == 2 for record in checkpoints)
    receipt = _read_json(fixture["receipt"])
    assert receipt["previous_checkpoint_count"] == 2
    assert receipt["previously_uncheckpointed_candidate_count"] == 0
    assert receipt["checkpoint_count"] == 1
    assert receipt["invalidated_checkpoint_count"] == 1
    assert receipt["replay_required_candidate_count"] == 1
    assert receipt["terminal_checkpoint_count"] == 1
    assert receipt["added_free_document_count"] == 1
    assert receipt["provider_request_count"] == 0
    assert receipt["paid_activity_executed"] is False
    assert {binding["candidate_id"] for binding in receipt["checkpoint_bindings"]} == {
        "cl-456"
    }
    assert receipt["invalidated_checkpoints"][0]["candidate_id"] == "cl-123"
    assert (
        receipt["invalidated_checkpoints"][0]["reason"]
        == "paid_gap_materially_changed_by_new_free_document"
    )
    assert all(
        binding["previous_candidate_input_sha256"]
        != binding["current_candidate_input_sha256"]
        for binding in receipt["checkpoint_bindings"]
    )
    assert {
        (
            binding["candidate_id"],
            binding["previous_cost_rank"],
            binding["current_cost_rank"],
        )
        for binding in receipt["checkpoint_bindings"]
    } == {("cl-456", 2, 1)}


def test_rebase_pacer_gap_checkpoints_append_only_union_schedules_only_addition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _append_only_pacer_gap_rebase_fixture(tmp_path)
    monkeypatch.setattr(
        cli,
        "_courtlistener_bridge_client",
        lambda *args, **kwargs: pytest.fail("rebase constructed a provider client"),
    )
    prior_checkpoint_bytes = {
        path.name: path.read_bytes()
        for path in fixture["previous_checkpoint_dir"].glob("*.json")
    }

    assert main(fixture["command"]) == 0

    receipt = _read_json(fixture["receipt"])
    expected_added = ["cl-789", "cl-790", "cl-791", "cl-792", "cl-793", "cl-794"]
    assert (
        receipt["append_only_snapshot_proof"]["added_candidate_ids"] == expected_added
    )
    assert receipt["added_candidate_ids"] == expected_added
    assert receipt["added_public_candidate_ids"] == []
    assert receipt["added_paid_gap_candidate_ids"] == expected_added
    assert receipt["previous_checkpoint_count"] == 2
    assert receipt["checkpoint_count"] == 2
    assert receipt["invalidated_checkpoint_count"] == 0
    assert receipt["replay_required_candidate_ids"] == expected_added
    assert receipt["replay_required_candidate_count"] == 6
    assert receipt["provider_request_count"] == 0
    assert {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    } == prior_checkpoint_bytes
    config = _read_json(fixture["destination_config"])
    assert config["paid_gap_count"] == 8
    assert [row["candidate_id"] for row in config["source_commitments"]] == [
        "cl-123",
        "cl-456",
        "cl-789",
        "cl-790",
        "cl-791",
        "cl-792",
        "cl-793",
        "cl-794",
    ]


def test_rebase_pacer_gap_checkpoints_append_only_rejects_wrong_external_pin(
    tmp_path: Path,
    capsys: Any,
) -> None:
    fixture = _append_only_pacer_gap_rebase_fixture(tmp_path)
    command = list(fixture["command"])
    pin_index = command.index("--expected-added-candidate-id") + 1
    command[pin_index] = "cl-not-reviewed"
    checkpoints_before = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }

    assert main(command) == 2
    assert "do not match the external pin" in capsys.readouterr().err
    assert {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    } == checkpoints_before
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_current_policy_replay_invalidates_exact_drop(
    tmp_path: Path,
) -> None:
    fixture = _append_only_pacer_gap_rebase_fixture(tmp_path, invalidate_prior=True)
    cl_456_checkpoint = next(
        path
        for path in fixture["previous_checkpoint_dir"].glob("*.json")
        if _read_json(path)["candidate_id"] == "cl-456"
    )
    retained_sha256 = hashlib.sha256(cl_456_checkpoint.read_bytes()).hexdigest()

    assert main(fixture["command"]) == 0

    receipt = _read_json(fixture["receipt"])
    expected_added = ["cl-789", "cl-790", "cl-791", "cl-792", "cl-793"]
    assert receipt["append_only_snapshot_proof"]["invalidated_candidate_ids"] == [
        "cl-123"
    ]
    assert (
        receipt["append_only_snapshot_proof"]["previous_manifest_in_current_ancestry"]
        is False
    )
    assert receipt["invalidated_candidate_ids"] == ["cl-123"]
    assert receipt["removed_invalidated_candidate_ids"] == ["cl-123"]
    assert receipt["replay_invalidated_candidate_ids"] == []
    assert receipt["invalidated_checkpoint_count"] == 1
    assert receipt["invalidated_checkpoints"][0]["candidate_id"] == "cl-123"
    assert receipt["invalidated_checkpoints"][0]["removed_from_current_routes"] is True
    assert receipt["replay_required_candidate_ids"] == expected_added
    assert receipt["replay_required_candidate_count"] == 5
    retained = list(fixture["destination_checkpoint_dir"].glob("*.json"))
    assert len(retained) == 1
    assert _read_json(retained[0])["candidate_id"] == "cl-456"
    [binding] = receipt["checkpoint_bindings"]
    assert binding["candidate_id"] == "cl-456"
    assert binding["previous_sha256"] == f"sha256:{retained_sha256}"
    assert binding["payload_rebound_fields"] == ["payload.selection_record.cost_rank"]


def test_rebase_pacer_gap_checkpoints_append_only_requires_complete_flag_set(
    tmp_path: Path,
    capsys: Any,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    command = [
        *fixture["command"],
        "--previous-snapshot",
        str(tmp_path / "not-consulted"),
    ]

    assert main(command) == 2
    assert (
        "all append-only snapshot proof flags must be supplied together"
        in capsys.readouterr().err
    )
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_append_only_rejects_screened_evidence_drift(
    tmp_path: Path,
    capsys: Any,
) -> None:
    fixture = _append_only_pacer_gap_rebase_fixture(tmp_path)
    current_screened = _read_jsonl(fixture["current_screened"])
    current_screened[0]["case_name"] = "Drifted v. Evidence"
    _write_jsonl(fixture["current_screened"], current_screened)

    assert main(fixture["command"]) == 2
    assert "screened evidence differs from snapshot" in capsys.readouterr().err
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_invalidates_materially_changed_success(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    previous_paid = _read_jsonl(fixture["previous_paid"])
    changed_gap = next(
        record for record in previous_paid if record["candidate_id"] == "cl-123"
    )
    checkpoint_path = next(
        path
        for path in fixture["previous_checkpoint_dir"].glob("*.json")
        if _read_json(path)["candidate_id"] == "cl-123"
    )
    checkpoint = _read_json(checkpoint_path)
    checkpoint["outcome"] = "success"
    checkpoint["payload"] = _pacer_gap_success_payload(changed_gap, index=0)
    _write_json(checkpoint_path, checkpoint)
    _write_json(
        fixture["destination_checkpoint_dir"] / checkpoint_path.name, checkpoint
    )

    assert main(fixture["command"]) == 0
    receipt = _read_json(fixture["receipt"])
    assert receipt["invalidated_checkpoint_count"] == 1
    assert receipt["invalidated_checkpoints"][0]["candidate_id"] == "cl-123"
    assert receipt["invalidated_checkpoints"][0]["previous_outcome"] == "success"
    assert not any(
        _read_json(path)["candidate_id"] == "cl-123"
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    )


def test_rebase_pacer_gap_checkpoints_rejects_stale_rank_in_success_payload(
    tmp_path: Path,
    capsys: Any,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    checkpoint_path = next(
        path
        for path in fixture["previous_checkpoint_dir"].glob("*.json")
        if _read_json(path)["candidate_id"] == "cl-456"
    )
    checkpoint = _read_json(checkpoint_path)
    checkpoint["payload"]["selection_record"]["cost_rank"] = 999
    _write_json(checkpoint_path, checkpoint)
    _write_json(
        fixture["destination_checkpoint_dir"] / checkpoint_path.name, checkpoint
    )

    assert main(fixture["command"]) == 2
    assert "cost rank is stale" in capsys.readouterr().err
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rejects_hardlinked_log_without_mutation(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    protected_paths = (
        fixture["previous_screened"],
        fixture["current_screened"],
        fixture["previous_public"],
        fixture["current_public"],
        fixture["previous_paid"],
        fixture["current_paid"],
        fixture["previous_free"],
        fixture["current_free"],
    )
    protected_before = {path: path.read_bytes() for path in protected_paths}
    checkpoints_before = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    config_before = fixture["destination_config"].read_bytes()
    log_path = tmp_path / "output/logs/rebase-pacer-gap-checkpoints.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.hardlink_to(fixture["previous_paid"])

    assert main(fixture["command"]) == 2
    assert {path: path.read_bytes() for path in protected_paths} == protected_before
    assert {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    } == checkpoints_before
    assert fixture["destination_config"].read_bytes() == config_before
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rejects_symlink_parent_without_mutation(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    checkpoints_before = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    real_parent = tmp_path / "real-receipts"
    real_parent.mkdir()
    symlink_parent = tmp_path / "receipt-link"
    symlink_parent.symlink_to(real_parent, target_is_directory=True)
    command = [
        *fixture["command"],
        "--receipt-output",
        str(symlink_parent / "receipt.json"),
    ]

    assert main(command) == 2
    assert not (real_parent / "receipt.json").exists()
    assert {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    } == checkpoints_before


def test_rebase_pacer_gap_checkpoints_rejects_concurrent_destination_writer(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    checkpoints_before = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    lock_fd = cli._acquire_pacer_gap_rebase_lock(fixture["destination_checkpoint_dir"])
    try:
        assert main(fixture["command"]) == 2
    finally:
        cli._release_pacer_gap_rebase_lock(lock_fd)
    assert {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    } == checkpoints_before
    assert not fixture["receipt"].exists()


@pytest.mark.parametrize("mutation", ["drift", "remove", "add", "duplicate"])
def test_rebase_pacer_gap_checkpoints_rejects_paid_gap_set_or_content_changes(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    current_paid = _read_jsonl(fixture["current_paid"])
    if mutation == "drift":
        current_paid[0]["paid_gap_reasons"] = ["missing_motion_briefing:999"]
    elif mutation == "remove":
        current_paid.pop()
    elif mutation == "add":
        added = copy.deepcopy(current_paid[0])
        added["candidate_id"] = "cl-added"
        added["cost_rank"] = len(current_paid) + 1
        current_paid.append(added)
    else:
        current_paid.append(copy.deepcopy(current_paid[0]))
    _write_jsonl(fixture["current_paid"], current_paid)

    assert main(fixture["command"]) == 2
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rejects_prior_free_document_drift(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    current_free = _read_jsonl(fixture["current_free"])
    current_free[0]["sha256"] = "b" * 64
    _write_jsonl(fixture["current_free"], current_free)

    assert main(fixture["command"]) == 2
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rejects_prior_free_document_reordering(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    current_free = _read_jsonl(fixture["current_free"])
    assert len(current_free) >= 3
    current_free[0], current_free[1] = current_free[1], current_free[0]
    _write_jsonl(fixture["current_free"], current_free)

    assert main(fixture["command"]) == 2
    assert not fixture["receipt"].exists()


def test_manifest_derived_gap_change_rejects_prior_document_reordering(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    previous = next(
        record
        for record in _read_jsonl(fixture["previous_paid"])
        if record["candidate_id"] == "cl-123"
    )
    current = next(
        record
        for record in _read_jsonl(fixture["current_paid"])
        if record["candidate_id"] == "cl-123"
    )
    second_prior = copy.deepcopy(
        cast(list[dict[str, object]], previous["documents"])[0]
    )
    second_prior["source_document_id"] = "cl-123-second-prior-document"
    cast(list[dict[str, object]], previous["documents"]).append(second_prior)
    current_documents = cast(list[dict[str, object]], current["documents"])
    current_documents.extend([copy.deepcopy(second_prior)])
    current_documents[-2], current_documents[-1] = (
        current_documents[-1],
        current_documents[-2],
    )
    added_free = next(
        record
        for record in _read_jsonl(fixture["current_free"])
        if record["source_document_id"] == "cl-123-entry-1-complaint"
    )

    with pytest.raises(cli.CommandError, match="reordered"):
        cli._validate_manifest_derived_paid_gap_change(
            candidate_id="cl-123",
            previous=previous,
            current=current,
            added_free_documents=[added_free],
        )


def test_rebase_pacer_gap_checkpoints_rejects_duplicate_free_documents(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    current_free = _read_jsonl(fixture["current_free"])
    current_free.append(copy.deepcopy(current_free[0]))
    _write_jsonl(fixture["current_free"], current_free)

    assert main(fixture["command"]) == 2
    assert not fixture["receipt"].exists()


@pytest.mark.parametrize(
    "forgery", ["private", "restriction", "extra", "manifest_provider"]
)
def test_rebase_pacer_gap_checkpoints_rejects_forged_new_complaint_document(
    tmp_path: Path,
    forgery: str,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    current_paid = _read_jsonl(fixture["current_paid"])
    candidate = next(
        record for record in current_paid if record["candidate_id"] == "cl-123"
    )
    complaint = next(
        document
        for document in cast(list[dict[str, object]], candidate["documents"])
        if document["source_document_id"] == "cl-123-entry-1-complaint"
    )
    if forgery == "private":
        complaint["is_private"] = True
    elif forgery == "restriction":
        complaint["restriction_evidence"] = ["unverified"]
    elif forgery == "extra":
        complaint["unexpected"] = "field"
    _write_jsonl(fixture["current_paid"], current_paid)
    if forgery == "manifest_provider":
        current_free = _read_jsonl(fixture["current_free"])
        added = next(
            record
            for record in current_free
            if record["source_document_id"] == "cl-123-entry-1-complaint"
        )
        added["source_provider"] = "untrusted"
        _write_jsonl(fixture["current_free"], current_free)

    assert main(fixture["command"]) == 2
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rejects_screened_byte_drift(
    tmp_path: Path,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    fixture["current_screened"].write_bytes(
        fixture["current_screened"].read_bytes() + b"\n"
    )

    assert main(fixture["command"]) == 2
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rolls_back_failed_config_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    original_checkpoints = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    original_config = fixture["destination_config"].read_bytes()
    atomic_write = cli._atomic_write_json

    def fail_config(path: Path, payload: dict[str, object]) -> None:
        if path == fixture["destination_config"]:
            raise OSError("simulated config commit failure")
        atomic_write(path, payload)

    monkeypatch.setattr(cli, "_atomic_write_json", fail_config)
    with pytest.raises(OSError, match="simulated config commit failure"):
        main(fixture["command"])

    assert original_checkpoints == {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    assert fixture["destination_config"].read_bytes() == original_config
    assert not fixture["receipt"].exists()


def test_rebase_pacer_gap_checkpoints_rolls_back_failed_receipt_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    original_checkpoints = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    original_config = fixture["destination_config"].read_bytes()
    fixture["receipt"].parent.mkdir(parents=True)
    fixture["receipt"].write_bytes(b'{"preexisting": true}\n')
    original_receipt = fixture["receipt"].read_bytes()
    atomic_write = cli._atomic_write_json

    def fail_receipt(path: Path, payload: dict[str, object]) -> None:
        if path == fixture["receipt"]:
            raise OSError("simulated receipt commit failure")
        atomic_write(path, payload)

    monkeypatch.setattr(cli, "_atomic_write_json", fail_receipt)
    with pytest.raises(OSError, match="simulated receipt commit failure"):
        main(fixture["command"])

    assert original_checkpoints == {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    assert fixture["destination_config"].read_bytes() == original_config
    assert fixture["receipt"].read_bytes() == original_receipt


def test_rebase_pacer_gap_checkpoints_preserves_backup_when_restore_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _pacer_gap_rebase_fixture(tmp_path)
    original_checkpoints = {
        path.name: path.read_bytes()
        for path in fixture["destination_checkpoint_dir"].glob("*.json")
    }
    atomic_write = cli._atomic_write_json
    real_replace = cli.os.replace

    def fail_receipt(path: Path, payload: dict[str, object]) -> None:
        if path == fixture["receipt"]:
            raise OSError("simulated receipt commit failure")
        atomic_write(path, payload)

    def fail_backup_restore(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        if (
            source_path.name.startswith(".pacer-gap-rebase-backup.")
            and Path(destination) == fixture["destination_checkpoint_dir"]
        ):
            raise OSError("simulated backup restoration failure")
        real_replace(source, destination)

    monkeypatch.setattr(cli, "_atomic_write_json", fail_receipt)
    monkeypatch.setattr(cli.os, "replace", fail_backup_restore)
    with pytest.raises(OSError, match="simulated backup restoration failure"):
        main(fixture["command"])

    backups = list(
        fixture["destination_checkpoint_dir"].parent.glob(".pacer-gap-rebase-backup.*")
    )
    assert len(backups) == 1
    assert {
        path.name: path.read_bytes() for path in backups[0].glob("*.json")
    } == original_checkpoints


def test_live_courtlistener_bridge_reserves_every_physical_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    args = Namespace(
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
        request_budget_max_wait_seconds=0.0,
        courtlistener_rate_profile="base",
    )

    client, budget = cli._courtlistener_bridge_client(
        args, fixture_path=None, live=True
    )

    assert budget is not None
    assert client.before_request is not None
    client.before_request("GET", "/dockets/123/")
    assert budget.local_reservations == 1
    assert budget.total_reservations() == 1


def test_live_courtlistener_bridge_requires_durable_request_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    args = Namespace(
        request_ledger=None,
        request_budget_max_wait_seconds=0.0,
        courtlistener_rate_profile="base",
    )

    with pytest.raises(cli.CommandError, match="--request-ledger"):
        cli._courtlistener_bridge_client(args, fixture_path=None, live=True)


def test_bridge_pacer_gaps_dry_run_emits_complete_v2_summary(tmp_path: Path) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    _write_jsonl(screened_path, [])

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )

    assert _read_json(output_root / "pacer-gap-bridge-summary.json") == {
        "schema_version": "legalforecast.courtlistener_case_dev_bridge.v2",
        "dry_run": True,
        "screened_case_count": 0,
        "selected_case_count": 0,
        "excluded_case_count": 0,
        "free_download_request_count": 0,
        "paid_document_count": 0,
        "paid_recovery_required_document_count": 0,
        "paid_recovery_required_case_count": 0,
        "identity_resolved_paid_gap_case_count": 0,
        "document_bytes_ready_case_count": 0,
        "identity_policy": (
            "exact court+docket match with caption corroboration; "
            "case.dev document IDs only"
        ),
        "free_first_required": True,
        "public_first_reconciled": False,
    }


def test_public_first_bridge_checkpoints_429_and_resumes_without_repeat_lookups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    first = _screened_case()
    second = _screened_case_variant(
        candidate_id="cl-456",
        docket_number="1:26-cv-00002",
        case_name="Second v. Example",
    )
    plan = plan_public_packet_downloads(
        (first, second),
        use_embedded_entries=True,
        target_clean_cases=2,
    )
    assert len(plan.paid_gap_cases) == 2
    _write_jsonl(screened_path, [first, second])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record() for gap in plan.paid_gap_cases])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": (
                    f"{request.candidate_id}/courtlistener/"
                    f"{request.source_document_id}.pdf"
                ),
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    rate_limit = {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {"type": "search", "query": "1:26-cv-00001", "limit": 20},
        "status_code": 429,
        "payload": {"error": "slow down"},
    }
    second_docket = {
        **_case_dev_docket(),
        "id": "case-dev-888",
        "docketNumber": "1:26-cv-00002",
        "caseName": "Second v. Example",
    }
    _write_jsonl(
        fixture_path,
        [
            rate_limit,
            rate_limit,
            rate_limit,
            _response(
                params={
                    "type": "search",
                    "query": "1:26-cv-00002",
                    "limit": 20,
                },
                payload={"dockets": [second_docket]},
            ),
            _response(
                params={
                    "type": "lookup",
                    "docketId": "case-dev-888",
                    "includeEntries": True,
                    "limit": 100,
                },
                payload={
                    "docket": {
                        **second_docket,
                        "entries": [
                            _case_dev_entry(5, "Motion to Dismiss", "second-mtd")
                        ],
                    }
                },
            ),
        ],
    )
    monkeypatch.setenv("CASE_DEV_RATE_LIMIT_PER_MINUTE", "20")
    monkeypatch.setattr(
        "legalforecast.ingestion.case_dev_client.CaseDevClient._throttle_if_needed",
        lambda self: None,
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--case-dev-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_selection_path),
        "--paid-gaps",
        str(paid_gaps_path),
        "--free-download-manifest",
        str(free_downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 2

    assert not (output_root / "public-packet-selection-reconciled.jsonl").exists()
    assert not (output_root / "pacer-gap-bridge-exclusions.jsonl").exists()
    checkpoint_records = sorted(
        (
            _read_json(path)
            for path in (output_root / "checkpoints" / "pacer-gap-bridge").glob(
                "*.json"
            )
        ),
        key=lambda record: cast(int, record["input_index"]),
    )
    assert [record["outcome"] for record in checkpoint_records] == [
        "retryable",
        "success",
    ]
    first_run_card = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert first_run_card["status"] == "failed"
    assert first_run_card["case_dev_request_count"] == 5
    assert first_run_card["case_dev_rate_limit_per_minute"] == 20
    assert first_run_card["case_dev_max_http_attempts_per_request"] == 3
    assert first_run_card["checkpoint_terminal_candidate_count"] == 1
    assert first_run_card["resumed_terminal_candidate_count"] == 0
    assert first_run_card["retryable_candidate_count"] == 1
    assert first_run_card["input_route_count"] == 2
    assert first_run_card["reconciled"] is False

    # Simulate the durable progress emitted before bridge summary v2. Resume
    # must preserve this terminal success without preserving its stale claim
    # that paid bytes were already recovered.
    checkpoint_dir = output_root / "checkpoints" / "pacer-gap-bridge"
    success_checkpoint_path = next(
        path
        for path in checkpoint_dir.glob("*.json")
        if _read_json(path)["outcome"] == "success"
    )
    success_checkpoint = _read_json(success_checkpoint_path)
    success_checkpoint["schema_version"] = (
        "legalforecast.pacer_gap_bridge_candidate_checkpoint.v1"
    )
    success_payload = cast(dict[str, object], success_checkpoint["payload"])
    success_selection = cast(dict[str, object], success_payload["selection_record"])
    success_selection["paid_recovery_required"] = False
    success_selection["planning_status"] = "selected_after_paid_recovery"
    success_selection.pop("identity_resolution_status")
    success_selection.pop("document_recovery_status")
    _write_json(success_checkpoint_path, success_checkpoint)
    config_path = output_root / "checkpoints" / "pacer-gap-bridge-progress-config.json"
    progress_config = _read_json(config_path)
    progress_config["schema_version"] = (
        "legalforecast.pacer_gap_bridge_progress_config.v1"
    )
    _write_json(config_path, progress_config)

    _write_jsonl(
        fixture_path,
        [
            _response(
                params={
                    "type": "search",
                    "query": "1:26-cv-00001",
                    "limit": 20,
                },
                payload={"dockets": [_case_dev_docket()]},
            ),
            _response(
                params={
                    "type": "lookup",
                    "docketId": "case-dev-777",
                    "includeEntries": True,
                    "limit": 100,
                },
                payload={
                    "docket": {
                        **_case_dev_docket(),
                        "entries": [
                            _case_dev_entry(5, "Motion to Dismiss", "first-mtd")
                        ],
                    }
                },
            ),
        ],
    )

    assert main(command) == 0

    resumed_selections = _read_jsonl(
        output_root / "public-packet-selection-reconciled.jsonl"
    )
    assert {record["candidate_id"] for record in resumed_selections} == {
        "cl-123",
        "cl-456",
    }
    resumed_legacy = next(
        record for record in resumed_selections if record["candidate_id"] == "cl-456"
    )
    assert resumed_legacy["paid_recovery_required"] is True
    assert resumed_legacy["planning_status"] == (
        "identity_resolved_paid_recovery_required"
    )
    assert _read_jsonl(output_root / "pacer-gap-bridge-exclusions.jsonl") == []
    resumed_run_card = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert resumed_run_card["case_dev_request_count"] == 2
    assert resumed_run_card["resumed_terminal_candidate_count"] == 1
    assert resumed_run_card["checkpoint_terminal_candidate_count"] == 2
    assert resumed_run_card["retryable_candidate_count"] == 0
    assert resumed_run_card["reconciled"] is True


def test_public_first_bridge_bounds_resumable_5xx_as_terminal_exclusion(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": f"cl-123/{request.source_document_id}.pdf",
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    failure = {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {"type": "search", "query": "1:26-cv-00001", "limit": 20},
        "status_code": 503,
        "payload": {"error": "temporary upstream failure"},
    }
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--case-dev-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_selection_path),
        "--paid-gaps",
        str(paid_gaps_path),
        "--free-download-manifest",
        str(free_downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    for expected_exit in (2, 2, 0):
        _write_jsonl(fixture_path, [failure, failure, failure])
        assert main(command) == expected_exit

    [checkpoint_path] = list(
        (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
    )
    checkpoint = _read_json(checkpoint_path)
    assert checkpoint["outcome"] == "exclusion"
    assert checkpoint["resumable_attempt_count"] == 3
    assert checkpoint["cumulative_case_dev_request_count"] == 9
    [exclusion] = _read_jsonl(output_root / "pacer-gap-bridge-exclusions.jsonl")
    assert exclusion["candidate_id"] == "cl-123"
    assert exclusion["exclusion_reasons"] == ["case_dev_server_error_retries_exhausted"]
    run_card = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert run_card["status"] == "completed"
    assert run_card["cumulative_case_dev_request_count"] == 9
    assert run_card["retryable_candidate_count"] == 0
    assert run_card["reconciled"] is True


def test_public_first_bridge_rejects_shared_manifest_corruption_before_checkpoint(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    downloads = [
        {
            **request.to_record(),
            "local_path": f"cl-123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    ]
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(free_downloads_path, [*downloads, downloads[0]])
    _write_jsonl(fixture_path, [])

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(fixture_path),
                "--public-selection",
                str(public_selection_path),
                "--paid-gaps",
                str(paid_gaps_path),
                "--free-download-manifest",
                str(free_downloads_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    assert not (
        output_root / "checkpoints" / "pacer-gap-bridge-progress-config.json"
    ).exists()
    assert not (output_root / "checkpoints" / "pacer-gap-bridge").exists()


@pytest.mark.parametrize("selected_entries", [None, {}, [], "not-a-list"])
def test_bridge_source_commitments_reject_invalid_embedded_entries(
    selected_entries: object,
) -> None:
    screened = _screened_case()
    if selected_entries is None:
        screened.pop("selected_entries")
    else:
        screened["selected_entries"] = selected_entries

    with pytest.raises(cli.CommandError, match="selected_entries"):
        cli._bridge_source_commitments(
            screened_records=[screened],
            routed_candidate_ids=["cl-123"],
            raw_html_dir=None,
            use_embedded_entries=True,
        )


def test_candidate_bridge_accepts_candidate_key_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    candidate = cast(dict[str, object], screened["candidate"])
    candidate.pop("docket_id")
    called = False

    def bridge_candidate(*args: object, **kwargs: object) -> object:
        nonlocal called
        called = True
        raise RuntimeError("identity matched")

    monkeypatch.setattr(bridge_module, "_bridge_candidate", bridge_candidate)

    with pytest.raises(RuntimeError, match="identity matched"):
        bridge_module.bridge_public_plan_paid_gap_candidate(
            screened,
            paid_gap_record=gap.to_record(),
            free_download_records=(),
            client=cast(Any, None),
            use_embedded_entries=True,
            validate_free_downloads=False,
        )
    assert called is True


@pytest.mark.parametrize("outcome", ["success", "exclusion"])
def test_bridge_checkpoint_payload_is_bound_to_candidate(outcome: str) -> None:
    payload: dict[str, object]
    if outcome == "success":
        payload = {
            "selection_record": {"candidate_id": "other"},
            "case_relevance_record": {"candidate_id": "cl-123"},
        }
    else:
        payload = {"exclusion_record": {"candidate_id": "other"}}
    checkpoint = {
        "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v2",
        "input_index": 0,
        "candidate_id": "cl-123",
        "candidate_input_sha256": "sha256:input",
        "outcome": outcome,
        "resumable_attempt_count": 1,
        "cumulative_case_dev_request_count": 0,
        "payload": payload,
    }

    with pytest.raises(cli.CommandError, match="invalid for cl-123"):
        cli._validate_bridge_checkpoint(
            checkpoint,
            input_index=0,
            candidate_id="cl-123",
            candidate_input_sha256="sha256:input",
        )


def _legacy_v1_terminal_success_checkpoint() -> dict[str, object]:
    paid_document = {
        "source_document_id": "case-dev-mtd",
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
    }
    return {
        "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v1",
        "input_index": 0,
        "candidate_id": "cl-123",
        "candidate_input_sha256": "sha256:input",
        "outcome": "success",
        "resumable_attempt_count": 1,
        "cumulative_case_dev_request_count": 2,
        "payload": {
            "selection_record": {
                "candidate_id": "cl-123",
                "selected": True,
                "paid_recovery_required": False,
                "paid_gap_reasons": [],
                "resolved_paid_gap_reasons": ["no_free_target_mtd_document"],
                "planning_status": "selected_after_paid_recovery",
                "identity_resolution": {"matched_by": "exact"},
                "documents": [paid_document],
            },
            "case_relevance_record": {
                "candidate_id": "cl-123",
                "documents": [paid_document],
            },
        },
    }


def test_bridge_resume_normalizes_legacy_v1_terminal_success_checkpoint() -> None:
    checkpoint = _legacy_v1_terminal_success_checkpoint()

    cli._validate_bridge_checkpoint(
        checkpoint,
        input_index=0,
        candidate_id="cl-123",
        candidate_input_sha256="sha256:input",
    )
    normalized = cli._normalize_bridge_checkpoint(checkpoint)

    assert normalized["schema_version"] == (
        "legalforecast.pacer_gap_bridge_candidate_checkpoint.v2"
    )
    payload = cast(dict[str, object], normalized["payload"])
    selection = cast(dict[str, object], payload["selection_record"])
    assert selection["paid_recovery_required"] is True
    assert selection["planning_status"] == ("identity_resolved_paid_recovery_required")
    assert selection["identity_resolution_status"] == "resolved"
    assert selection["document_recovery_status"] == "paid_recovery_required"


def test_bridge_resume_rejects_v2_success_with_stale_recovery_status() -> None:
    normalized = cli._normalize_bridge_checkpoint(
        _legacy_v1_terminal_success_checkpoint()
    )
    payload = cast(dict[str, object], normalized["payload"])
    selection = cast(dict[str, object], payload["selection_record"])
    selection["paid_recovery_required"] = False

    with pytest.raises(cli.CommandError, match="v2 success checkpoint is ambiguous"):
        cli._normalize_bridge_checkpoint(normalized)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("hash_mismatch", "invalid for cl-123"),
        ("missing_documents", "malformed selection documents"),
        ("mismatched_pending_ids", "ambiguous for cl-123"),
    ],
)
def test_bridge_resume_fails_closed_on_unverifiable_legacy_v1_success(
    mutation: str,
    match: str,
) -> None:
    checkpoint = _legacy_v1_terminal_success_checkpoint()
    if mutation == "hash_mismatch":
        with pytest.raises(cli.CommandError, match=match):
            cli._validate_bridge_checkpoint(
                checkpoint,
                input_index=0,
                candidate_id="cl-123",
                candidate_input_sha256="sha256:different",
            )
        return
    payload = cast(dict[str, object], checkpoint["payload"])
    if mutation == "missing_documents":
        selection = cast(dict[str, object], payload["selection_record"])
        selection.pop("documents")
    else:
        relevance = cast(dict[str, object], payload["case_relevance_record"])
        relevance["documents"] = [
            {
                "source_document_id": "different-document",
                "availability_status": "unavailable",
                "requires_paid_recovery": True,
            }
        ]

    cli._validate_bridge_checkpoint(
        checkpoint,
        input_index=0,
        candidate_id="cl-123",
        candidate_input_sha256="sha256:input",
    )
    with pytest.raises(cli.CommandError, match=match):
        cli._normalize_bridge_checkpoint(checkpoint)


def test_bridge_resume_accepts_only_semantically_identical_v1_config() -> None:
    current = {
        "schema_version": "legalforecast.pacer_gap_bridge_progress_config.v2",
        "screened_cases_sha256": "sha256:screened",
        "paid_gap_count": 3,
    }
    legacy = {
        **current,
        "schema_version": "legalforecast.pacer_gap_bridge_progress_config.v1",
    }

    assert cli._bridge_progress_config_matches(legacy, current) is True
    assert (
        cli._bridge_progress_config_matches({**legacy, "paid_gap_count": 4}, current)
        is False
    )


def test_bridge_resume_rejects_unrecognized_checkpoint_schema() -> None:
    checkpoint = {
        "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v0",
        "input_index": 0,
        "candidate_id": "cl-123",
        "candidate_input_sha256": "sha256:input",
        "outcome": "success",
        "resumable_attempt_count": 1,
        "cumulative_case_dev_request_count": 2,
        "payload": {"reason": "retryable"},
    }

    with pytest.raises(cli.CommandError, match="invalid for cl-123"):
        cli._validate_bridge_checkpoint(
            checkpoint,
            input_index=0,
            candidate_id="cl-123",
            candidate_input_sha256="sha256:input",
        )


@pytest.mark.parametrize("alias_kind", ["direct", "symlink", "hardlink"])
def test_public_first_bridge_rejects_checkpoint_config_input_alias_before_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    alias_kind: str,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": f"cl-123/{request.source_document_id}.pdf",
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    _write_jsonl(fixture_path, [])
    checkpoint_config_path = screened_path
    if alias_kind != "direct":
        checkpoint_config_path = tmp_path / f"config-{alias_kind}.json"
        if alias_kind == "symlink":
            checkpoint_config_path.symlink_to(screened_path)
        else:
            checkpoint_config_path.hardlink_to(screened_path)
    screened_before = screened_path.read_bytes()

    def client_must_not_be_created(*args: object, **kwargs: object) -> object:
        raise AssertionError("client must not be created")

    monkeypatch.setattr(cli, "_case_dev_client", client_must_not_be_created)

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(fixture_path),
                "--public-selection",
                str(public_selection_path),
                "--paid-gaps",
                str(paid_gaps_path),
                "--free-download-manifest",
                str(free_downloads_path),
                "--checkpoint-config-output",
                str(checkpoint_config_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    assert screened_path.read_bytes() == screened_before


def test_public_first_bridge_rejects_orphan_checkpoint_before_candidate_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": f"cl-123/{request.source_document_id}.pdf",
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    rate_limit = {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {"type": "search", "query": "1:26-cv-00001", "limit": 20},
        "status_code": 429,
        "payload": {"error": "slow down"},
    }
    _write_jsonl(fixture_path, [rate_limit, rate_limit, rate_limit])
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--case-dev-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_selection_path),
        "--paid-gaps",
        str(paid_gaps_path),
        "--free-download-manifest",
        str(free_downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]
    assert main(command) == 2
    checkpoint_dir = output_root / "checkpoints" / "pacer-gap-bridge"
    [checkpoint_path] = list(checkpoint_dir.glob("*.json"))
    checkpoint_before = checkpoint_path.read_bytes()
    _write_json(checkpoint_dir / "orphan.json", {"unexpected": True})

    def candidate_attempt(*args: object, **kwargs: object) -> object:
        raise AssertionError("candidate bridge must not run")

    monkeypatch.setattr(cli, "bridge_public_plan_paid_gap_candidate", candidate_attempt)

    assert main(command) == 2
    assert checkpoint_path.read_bytes() == checkpoint_before


def test_fixture_pacer_gap_flow_reaches_merged_parser_manifest(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
) -> None:
    output_root = tmp_path / "acquisition"
    common_document_root = output_root / "documents"
    purchase_policy, purchase_ledger, cohort_policy = _purchase_policy(tmp_path)
    screened_path = tmp_path / "screened.jsonl"
    case_dev_fixture_path = tmp_path / "case-dev-bridge.jsonl"
    _write_jsonl(screened_path, [_fully_free_case(), _screened_case()])
    snapshot_path, cycle_hash, raw_html_dir = _complete_snapshot(
        tmp_path / "cycle",
        [_fully_free_case(), _screened_case()],
    )
    _write_jsonl(
        case_dev_fixture_path,
        [
            _response(
                params={
                    "type": "search",
                    "query": "1:26-cv-00001",
                    "limit": 20,
                },
                payload={"dockets": [_case_dev_docket()]},
            ),
            _response(
                params={
                    "type": "lookup",
                    "docketId": "case-dev-777",
                    "includeEntries": True,
                    "limit": 100,
                },
                payload={
                    "docket": {
                        **_case_dev_docket(),
                        "entries": [
                            _case_dev_entry(5, "Motion to Dismiss", "case-dev-mtd")
                        ],
                    }
                },
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(snapshot_path),
                "--expected-cycle-hash",
                cycle_hash,
                "--screened-cases",
                str(snapshot_path / "screened-cases.jsonl"),
                "--raw-html-dir",
                str(raw_html_dir),
                "--use-embedded-entries",
                "--target-clean-cases",
                "2",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [free_selection] = _read_jsonl(output_root / "public-packet-selection.jsonl")
    assert free_selection["candidate_id"] == "cl-free"
    [paid_gap] = _read_jsonl(output_root / "public-packet-paid-gaps.jsonl")
    assert paid_gap["candidate_id"] == "cl-123"
    assert paid_gap["paid_gap_reasons"] == [
        "no_free_target_mtd_document",
        "no_free_mtd_memorandum",
    ]
    assert _read_jsonl(output_root / "public-packet-exclusions.jsonl") == []

    free_fixture_path = tmp_path / "free-documents.json"
    _write_json(
        free_fixture_path,
        {
            "https://storage.courtlistener.com/complaint.pdf": "%PDF complaint",
            "https://storage.courtlistener.com/decision.pdf": "%PDF decision",
            "https://storage.courtlistener.com/free-complaint.pdf": (
                "%PDF free complaint"
            ),
            "https://storage.courtlistener.com/free-motion.pdf": "%PDF free motion",
            "https://storage.courtlistener.com/free-decision.pdf": "%PDF free decision",
        },
    )
    assert (
        main(
            [
                "acquisition",
                "download-free",
                "--requests",
                str(output_root / "free-document-requests.jsonl"),
                "--fixture-documents",
                str(free_fixture_path),
                "--document-output-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    merged_manifest = output_root / "document-downloads-merged.jsonl"
    clearance = output_root / "disclosure-clearance.jsonl"
    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(case_dev_fixture_path),
                "--public-selection",
                str(output_root / "public-packet-selection.jsonl"),
                "--paid-gaps",
                str(output_root / "public-packet-paid-gaps.jsonl"),
                "--free-download-manifest",
                str(output_root / "free-document-downloads.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    reconciled_selection = output_root / "public-packet-selection-reconciled.jsonl"
    selections = _read_jsonl(reconciled_selection)
    assert {record["candidate_id"] for record in selections} == {"cl-free", "cl-123"}
    paid_selection = next(
        record for record in selections if record["candidate_id"] == "cl-123"
    )
    assert paid_selection["paid_recovery_required"] is True
    assert (
        paid_selection["planning_status"] == "identity_resolved_paid_recovery_required"
    )
    bridge_summary = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert bridge_summary["schema_version"] == (
        "legalforecast.courtlistener_case_dev_bridge.v2"
    )
    assert bridge_summary["identity_resolved_paid_gap_case_count"] == 1
    assert bridge_summary["paid_recovery_required_case_count"] == 1
    assert bridge_summary["document_bytes_ready_case_count"] == 1
    assert _read_jsonl(output_root / "pacer-gap-bridge-exclusions.jsonl") == []
    assert not (
        {record["candidate_id"] for record in selections}
        & {
            record["candidate_id"]
            for record in _read_jsonl(output_root / "public-packet-exclusions.jsonl")
        }
    )
    assert (
        main(
            [
                "acquisition",
                "filter-core-documents",
                "--case-relevance",
                str(output_root / "case-relevance.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(output_root / "core-filter-results.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    budget = _read_json(output_root / "missing-core-budget-plan.json")
    assert budget["max_projected_budget_usd"] == "2250.00"
    assert budget["max_missing_core_documents_per_case"] == 24
    paid_case = next(
        record for record in budget["case_plans"] if record["candidate_id"] == "cl-123"
    )
    assert paid_case["purchase_document_ids"] == ["case-dev-mtd"]

    purchase_fixture_path = tmp_path / "purchase.jsonl"
    download_url = "https://case.dev/download/case-dev-mtd.pdf"
    _write_jsonl(
        purchase_fixture_path,
        [
            {
                "method": "POST",
                "path": "/legal/v1/documents/case-dev-mtd/pacer",
                "params": {"live": True, "acknowledgePacerFees": True},
                "status_code": 200,
                "payload": {
                    "acknowledgePacerFees": True,
                    "downloadUrl": download_url,
                    "pacerFees": {"pacerFee": 0, "serviceFee": 3.05, "total": 3.05},
                },
            }
        ],
    )
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--output-root",
                str(tmp_path / "purchase-ledger-initialization"),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(output_root / "missing-core-budget-plan.json"),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--case-dev-fixture",
                str(purchase_fixture_path),
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--capability",
                "document_level_purchase",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    purchased_fixture_path = tmp_path / "purchased.json"
    _write_json(purchased_fixture_path, {download_url: "%PDF purchased motion"})
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(output_root / "case-dev-pacer-purchases.json"),
                "--selection",
                str(reconciled_selection),
                "--fixture-documents",
                str(purchased_fixture_path),
                "--document-output-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "merge-download-manifests",
                "--download-manifest",
                str(output_root / "free-document-downloads.jsonl"),
                "--download-manifest",
                str(output_root / "purchased-document-downloads.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    _write_jsonl(
        clearance,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "sha256": row["sha256"],
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "byte_count": row["byte_count"],
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-public-docket"],
                "reviewer_id": "reviewer:test",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for row in _read_jsonl(merged_manifest)
        ],
    )
    materialization_card = authenticated_downstream_fixture.materialize(
        manifest=merged_manifest,
        clearance=clearance,
        document_root=common_document_root,
        name="pacer-gap-parser",
    )
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(merged_manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(common_document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    parser_requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert {record["source_document_id"] for record in parser_requests} == {
        "case-dev-mtd",
        "cl-free-entry-1-complaint",
        "cl-free-entry-5-motion-to-dismiss-memorandum",
        "cl-free-entry-16-decision",
        "cl-123-entry-1-complaint",
        "cl-123-entry-16-decision",
    }


def _response(
    *,
    params: dict[str, object],
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": params,
        "status_code": 200,
        "payload": payload,
    }


def _case_dev_docket() -> dict[str, object]:
    return {
        "id": "case-dev-777",
        "courtId": "nysd",
        "docketNumber": "1:26-cv-00001",
        "caseName": "Fixture v. Example",
    }


def _case_dev_entry(
    entry_number: int,
    description: str,
    document_id: str,
) -> dict[str, object]:
    return {
        "id": f"case-dev-entry-{entry_number}",
        "entryNumber": entry_number,
        "description": description,
        "documents": [
            {
                "id": document_id,
                "description": description,
                "type": "main_document",
            }
        ],
    }


def _screened_case() -> dict[str, object]:
    return {
        "candidate": {
            "docket_id": "cl-123",
            "candidate_key": "cl-123",
            "metadata": {
                "case_id": "cl-123",
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _courtlistener_entry(
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                "https://storage.courtlistener.com/complaint.pdf",
                pacer_only=False,
            ),
            _courtlistener_entry(
                5,
                "MOTION to Dismiss and Memorandum in Support filed by Defendant.",
                "Motion to Dismiss and Memorandum in Support",
                "https://ecf.nysd.uscourts.gov/doc1/12345",
                pacer_only=True,
            ),
            _courtlistener_entry(
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                "https://storage.courtlistener.com/decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _screened_case_variant(
    *,
    candidate_id: str,
    docket_number: str,
    case_name: str,
) -> dict[str, object]:
    record = copy.deepcopy(_screened_case())
    candidate = cast(dict[str, object], record["candidate"])
    candidate["docket_id"] = candidate_id
    candidate["candidate_key"] = candidate_id
    candidate["url"] = f"https://www.courtlistener.com/docket/456/{candidate_id}/"
    metadata = cast(dict[str, object], candidate["metadata"])
    metadata["case_id"] = candidate_id
    metadata["docket_number"] = docket_number
    metadata["case_name"] = case_name
    return record


def _fully_free_case() -> dict[str, object]:
    record = json.loads(json.dumps(_screened_case()))
    candidate = record["candidate"]
    candidate["docket_id"] = "cl-free"
    candidate["candidate_key"] = "cl-free"
    candidate["metadata"] = {
        "case_id": "cl-free",
        "case_name": "Free v. Example",
        "court": "nysd",
        "docket_number": "1:26-cv-00002",
    }
    entries = record["selected_entries"]
    urls = (
        "https://storage.courtlistener.com/free-complaint.pdf",
        "https://storage.courtlistener.com/free-motion.pdf",
        "https://storage.courtlistener.com/free-decision.pdf",
    )
    for entry, url in zip(entries, urls, strict=True):
        document = entry["documents"][0]
        document["href"] = url
        document["pacer_only"] = False
        document["action_label"] = "Download PDF"
    return record


def _courtlistener_entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "kind": "Main Document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _pacer_gap_success_payload(
    gap: dict[str, object], *, index: int
) -> dict[str, object]:
    candidate_id = cast(str, gap["candidate_id"])
    resolved_document = {
        "availability_status": "unavailable",
        "candidate_id": candidate_id,
        "contains_target_outcome": False,
        "docket_entry_number": 1,
        "document_role": "complaint",
        "is_private": None,
        "is_sealed": None,
        "model_visible": True,
        "redaction_or_seal_status": "unknown",
        "requires_paid_recovery": True,
        "resolved_from_paid_gap": True,
        "restriction_evidence": [
            "courtlistener_rest_docket_exact_match",
            "courtlistener_rest_docket_entry_exact_match",
            "courtlistener_rest_recap_document_exact_match",
            "courtlistener_rest_recap_document_is_sealed_unknown",
        ],
        "source_document_id": f"{candidate_id}-resolved-complaint",
        "source_url_or_reference": (
            f"https://www.courtlistener.com/api/rest/v4/recap-documents/{index + 100}/"
        ),
    }
    return {
        "selection_record": {
            **gap,
            "case_id": candidate_id,
            "selected": True,
            "exclusion_reasons": [],
            "paid_recovery_required": True,
            "paid_gap_reasons": [],
            "resolved_paid_gap_reasons": gap["paid_gap_reasons"],
            "planning_status": "identity_resolved_paid_recovery_required",
            "identity_resolution_status": "resolved",
            "document_recovery_status": "paid_recovery_required",
            "identity_resolution": {
                "courtlistener_candidate_id": candidate_id,
                "courtlistener_docket_id": candidate_id,
                "matched_by": "fixture",
            },
            "documents": [*cast(list[object], gap["documents"]), resolved_document],
        },
        "case_relevance_record": {
            "candidate_id": candidate_id,
            "courtlistener_docket_id": candidate_id,
            "documents": [resolved_document],
        },
        "free_download_requests": [],
    }


def _pacer_gap_rebase_fixture(tmp_path: Path) -> dict[str, Any]:
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    output = tmp_path / "output"
    previous.mkdir()
    current.mkdir()
    first = _screened_case()
    second = _screened_case_variant(
        candidate_id="cl-456",
        docket_number="1:26-cv-00002",
        case_name="Second v. Example",
    )
    for screened in (first, second):
        screened["candidate_id"] = cast(dict[str, object], screened["candidate"])[
            "docket_id"
        ]
        screened["selected_entries"] = cast(
            list[dict[str, object]], screened["selected_entries"]
        )[1:]
    screened_records = [first, second]
    plan = plan_public_packet_downloads(
        screened_records,
        use_embedded_entries=True,
        target_clean_cases=2,
    )
    paid = [gap.to_record() for gap in plan.paid_gap_cases]
    public: list[dict[str, object]] = []
    free = [
        {
            **request.to_record(),
            "local_path": f"{request.candidate_id}/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    ]
    added_free = {
        "candidate_id": "cl-123",
        "source_provider": "courtlistener",
        "source_document_id": "cl-123-entry-1-complaint",
        "docket_entry_number": 1,
        "document_role": "complaint",
        "source_url": "https://storage.courtlistener.com/newly-free-complaint.pdf",
        "file_extension": "pdf",
        "local_path": "cl-123/cl-123-entry-1-complaint.pdf",
        "sha256": "c" * 64,
        "free_or_purchased": "free",
    }
    paths = {
        "previous_screened": previous / "screened.jsonl",
        "current_screened": current / "screened.jsonl",
        "previous_public": previous / "public.jsonl",
        "current_public": current / "public.jsonl",
        "previous_paid": previous / "paid.jsonl",
        "current_paid": current / "paid.jsonl",
        "previous_free": previous / "free.jsonl",
        "current_free": current / "free.jsonl",
    }
    _write_jsonl(paths["previous_screened"], screened_records)
    paths["current_screened"].write_bytes(paths["previous_screened"].read_bytes())
    _write_jsonl(paths["previous_public"], public)
    paths["current_public"].write_bytes(paths["previous_public"].read_bytes())
    _write_jsonl(paths["previous_paid"], paid)
    current_paid = list(reversed(copy.deepcopy(paid)))
    for rank, record in enumerate(current_paid, start=1):
        record["cost_rank"] = rank
        if record["candidate_id"] == "cl-123":
            cast(list[dict[str, object]], record["documents"]).insert(
                0,
                {
                    "candidate_id": "cl-123",
                    "contains_target_outcome": False,
                    "description": "Complaint",
                    "docket_entry_number": 1,
                    "document_role": "complaint",
                    "is_private": None,
                    "is_sealed": None,
                    "model_visible": True,
                    "redaction_or_seal_status": "public",
                    "restriction_evidence": [
                        "courtlistener_public_download_record_checked"
                    ],
                    "source_document_id": "cl-123-entry-1-complaint",
                    "source_url": (
                        "https://storage.courtlistener.com/newly-free-complaint.pdf"
                    ),
                },
            )
            record["free_required_document_count"] = (
                cast(int, record["free_required_document_count"]) + 1
            )
            record["missing_required_document_count"] = (
                cast(int, record["missing_required_document_count"]) - 1
            )
            record["paid_gap_reasons"] = [
                reason
                for reason in cast(list[str], record["paid_gap_reasons"])
                if reason != "no_free_operative_complaint"
            ]
            record["projected_paid_cost_usd"] = (
                f"{float(cast(str, record['projected_paid_cost_usd'])) - 3.05:.2f}"
            )
    _write_jsonl(paths["current_paid"], current_paid)
    _write_jsonl(paths["previous_free"], free)
    current_free = [
        *(
            record
            for candidate_id in ("cl-456", "cl-123")
            for record in free
            if record["candidate_id"] == candidate_id
        ),
        added_free,
    ]
    _write_jsonl(paths["current_free"], current_free)

    route_ids = [record["candidate_id"] for record in paid]
    source_commitments = cli._bridge_source_commitments(
        screened_records=screened_records,
        routed_candidate_ids=cast(list[str], route_ids),
        raw_html_dir=None,
        use_embedded_entries=True,
    )
    config = {
        "schema_version": "legalforecast.pacer_gap_bridge_progress_config.v2",
        "mode": "public_first",
        "screened_cases_sha256": cli._sha256_path(paths["previous_screened"]),
        "public_selection_sha256": cli._sha256_path(paths["previous_public"]),
        "paid_gaps_sha256": cli._sha256_path(paths["previous_paid"]),
        "free_download_manifest_sha256": cli._sha256_path(paths["previous_free"]),
        "screened_case_count": 2,
        "public_selection_count": 0,
        "paid_gap_count": 2,
        "use_embedded_entries": True,
        "transport_mode": "live",
        "bridge_provider": "courtlistener_rest",
        "source_commitments": source_commitments,
        "free_lookup_only": True,
        "pacer_fee_acknowledgment_allowed": False,
    }
    previous_checkpoint_dir = previous / "checkpoints"
    previous_checkpoint_dir.mkdir()
    screened_by_id = {
        cli._bridge_candidate_id(record): record for record in screened_records
    }
    for index, gap in enumerate(paid):
        candidate_id = cast(str, gap["candidate_id"])
        success_payload = _pacer_gap_success_payload(gap, index=index)
        checkpoint = {
            "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v2",
            "bridge_semantic_revision": cli._PACER_GAP_BRIDGE_SEMANTIC_REVISION,
            "input_index": index,
            "candidate_id": candidate_id,
            "candidate_input_sha256": cli._canonical_json_sha256(
                {"screened_case": screened_by_id[candidate_id], "paid_gap": gap}
            ),
            "outcome": "success" if candidate_id == "cl-456" else "exclusion",
            "resumable_attempt_count": 2,
            "cumulative_courtlistener_request_count": 3,
            "payload": (
                success_payload
                if candidate_id == "cl-456"
                else {
                    "exclusion_record": bridge_module.case_dev_bridge_exclusion_record(
                        screened_by_id[candidate_id],
                        reason="operative_complaint_not_found",
                        detail="fixture terminal exclusion",
                    )
                }
            ),
        }
        _write_json(
            cli._bridge_checkpoint_path(
                previous_checkpoint_dir,
                input_index=index,
                candidate_id=candidate_id,
            ),
            checkpoint,
        )
    previous_config = previous / "progress-config.json"
    _write_json(previous_config, config)

    destination_checkpoint_dir = output / "checkpoints/pacer-gap-bridge"
    destination_checkpoint_dir.parent.mkdir(parents=True)
    destination_checkpoint_dir.mkdir()
    for source in previous_checkpoint_dir.glob("*.json"):
        (destination_checkpoint_dir / source.name).write_bytes(source.read_bytes())
    destination_config = output / "checkpoints/pacer-gap-bridge-progress-config.json"
    destination_config.write_bytes(previous_config.read_bytes())
    receipt = output / "run-cards/rebase-pacer-gap-checkpoints-receipt.json"
    command = [
        "acquisition",
        "rebase-pacer-gap-checkpoints",
        "--previous-screened-cases",
        str(paths["previous_screened"]),
        "--current-screened-cases",
        str(paths["current_screened"]),
        "--previous-public-selection",
        str(paths["previous_public"]),
        "--current-public-selection",
        str(paths["current_public"]),
        "--previous-paid-gaps",
        str(paths["previous_paid"]),
        "--current-paid-gaps",
        str(paths["current_paid"]),
        "--previous-free-download-manifest",
        str(paths["previous_free"]),
        "--current-free-download-manifest",
        str(paths["current_free"]),
        "--previous-checkpoint-dir",
        str(previous_checkpoint_dir),
        "--previous-checkpoint-config",
        str(previous_config),
        "--output-root",
        str(output),
        "--execute",
    ]
    return {
        **paths,
        "command": command,
        "previous_checkpoint_dir": previous_checkpoint_dir,
        "destination_checkpoint_dir": destination_checkpoint_dir,
        "destination_config": destination_config,
        "receipt": receipt,
    }


def _append_only_pacer_gap_rebase_fixture(
    tmp_path: Path, *, invalidate_prior: bool = False
) -> dict[str, Any]:
    bridge_root = tmp_path / "bridge"
    bridge_root.mkdir()
    fixture = _pacer_gap_rebase_fixture(bridge_root)
    previous_screened = _read_jsonl(fixture["previous_screened"])
    added_ids = ["cl-789", "cl-790", "cl-791", "cl-792", "cl-793"]
    if not invalidate_prior:
        added_ids.append("cl-794")
    added_screened_records: list[dict[str, object]] = []
    for index, candidate_id in enumerate(added_ids, start=3):
        added_screened = _screened_case_variant(
            candidate_id=candidate_id,
            docket_number=f"1:26-cv-{index:05d}",
            case_name=f"Added {index} v. Example",
        )
        added_screened["candidate_id"] = candidate_id
        added_screened["selected_entries"] = cast(
            list[dict[str, object]], added_screened["selected_entries"]
        )[1:]
        added_screened_records.append(added_screened)
    retained_screened = previous_screened[1:] if invalidate_prior else previous_screened
    current_screened = [*retained_screened, *added_screened_records]
    _write_jsonl(fixture["current_screened"], current_screened)

    plan = plan_public_packet_downloads(
        current_screened,
        use_embedded_entries=True,
        target_clean_cases=len(current_screened),
    )
    current_public = [record.to_record() for record in plan.selected_cases]
    current_paid = [record.to_record() for record in plan.paid_gap_cases]
    assert not current_public
    assert [record["candidate_id"] for record in current_paid] == [
        *(["cl-456"] if invalidate_prior else ["cl-123", "cl-456"]),
        *added_ids,
    ]
    _write_jsonl(fixture["current_public"], current_public)
    _write_jsonl(fixture["current_paid"], current_paid)
    previous_free = _read_jsonl(fixture["previous_free"])
    new_free = [
        {
            **request.to_record(),
            "local_path": f"{request.candidate_id}/{request.source_document_id}.pdf",
            "sha256": "d" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
        if request.candidate_id in added_ids
    ]
    current_free = [
        *(
            record
            for candidate_id in (
                ("cl-456",) if invalidate_prior else ("cl-123", "cl-456")
            )
            for record in previous_free
            if record["candidate_id"] == candidate_id
        ),
        *new_free,
    ]
    _write_jsonl(fixture["current_free"], current_free)

    previous_snapshot, cycle_hash, _ = _complete_snapshot(
        tmp_path / "previous-snapshot-source",
        cast(list[dict[str, object]], previous_screened),
        batch_id="prior-screening-batch",
        snapshot_id="prior-screening-snapshot",
    )
    added_snapshot, added_cycle_hash, _ = _complete_snapshot(
        tmp_path / "added-snapshot-source",
        added_screened_records,
        batch_id="added-screening-batch",
        snapshot_id="added-screening-snapshot",
    )
    assert added_cycle_hash == cycle_hash
    union_root = tmp_path / "union"
    union_root.mkdir()
    union_store = union_root / "cycle-acquisition.sqlite3"
    with CycleAcquisitionStore(union_store) as store:
        assert (
            store.ensure_cycle({"eligibility_anchor": "2026-06-30", "fixture": True})
            == cycle_hash
        )
    previous_manifest_sha256 = hashlib.sha256(
        (previous_snapshot / "manifest.json").read_bytes()
    ).hexdigest()
    added_manifest_sha256 = hashlib.sha256(
        (added_snapshot / "manifest.json").read_bytes()
    ).hexdigest()
    current_base_snapshot = previous_snapshot
    current_base_manifest_sha256 = previous_manifest_sha256
    if invalidate_prior:
        current_base_snapshot, retained_cycle_hash, _ = _complete_snapshot(
            tmp_path / "current-policy-retained-source",
            cast(list[dict[str, object]], retained_screened),
            batch_id="current-policy-retained-batch",
            snapshot_id="current-policy-retained-snapshot",
        )
        assert retained_cycle_hash == cycle_hash
        current_base_manifest_sha256 = hashlib.sha256(
            (current_base_snapshot / "manifest.json").read_bytes()
        ).hexdigest()
    assert (
        main(
            [
                "acquisition",
                "union-screening-snapshots",
                "--cycle-store",
                str(union_store),
                "--batch-id",
                "append-only-union-batch",
                "--expected-cycle-hash",
                cycle_hash,
                "--source-snapshot",
                str(current_base_snapshot),
                "--expected-source-snapshot-manifest-sha256",
                current_base_manifest_sha256,
                "--source-snapshot",
                str(added_snapshot),
                "--expected-source-snapshot-manifest-sha256",
                added_manifest_sha256,
                "--snapshot-root",
                str(union_root / "snapshots"),
                "--snapshot-id",
                "append-only-union",
                "--output-root",
                str(union_root / "output"),
                "--execute",
            ]
        )
        == 0
    )
    current_snapshot = union_root / "snapshots/append-only-union"
    current_manifest_sha256 = hashlib.sha256(
        (current_snapshot / "manifest.json").read_bytes()
    ).hexdigest()
    fixture["command"] = [
        *fixture["command"],
        "--previous-snapshot",
        str(previous_snapshot),
        "--expected-previous-snapshot-manifest-sha256",
        previous_manifest_sha256,
        "--current-snapshot",
        str(current_snapshot),
        "--expected-current-snapshot-manifest-sha256",
        current_manifest_sha256,
        *(
            flag
            for candidate_id in added_ids
            for flag in ("--expected-added-candidate-id", candidate_id)
        ),
        *(
            ("--expected-invalidated-candidate-id", "cl-123")
            if invalidate_prior
            else ()
        ),
    ]
    fixture.update(
        {
            "previous_snapshot": previous_snapshot,
            "current_snapshot": current_snapshot,
        }
    )
    return fixture


def _complete_snapshot(
    root: Path,
    screened_records: list[dict[str, object]],
    *,
    batch_id: str = "pacer-gap-fixture",
    snapshot_id: str = "complete-fixture",
) -> tuple[Path, str, Path]:
    term = "fixture-term"
    raw_html_dir = root / "raw-courtlistener-html"
    with CycleAcquisitionStore(root / "cycle-acquisition.sqlite3") as store:
        cycle_hash = store.ensure_cycle(
            {"eligibility_anchor": "2026-06-30", "fixture": True}
        )
        store.ensure_batch(batch_id, {"fixture": "pacer-gap", "batch_id": batch_id})
        store.ensure_terms(batch_id, [term])
        hits_list: list[DiscoveryHit] = []
        for index, record in enumerate(screened_records):
            candidate = cast(dict[str, object], record["candidate"])
            candidate_id = candidate["docket_id"]
            assert isinstance(candidate_id, str)
            hits_list.append(
                DiscoveryHit(
                    provider_hit_id=f"fixture-hit-{index}",
                    candidate_id=candidate_id,
                    payload={"fixture_index": index},
                )
            )
        hits = tuple(hits_list)
        store.commit_search_page(
            batch_id,
            term,
            None,
            hits,
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        for hit, record in zip(hits, screened_records, strict=True):
            store.record_observation(
                hit.candidate_id,
                batch_id=batch_id,
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence=record,
            )
            store.write_raw_artifact(
                hit.candidate_id,
                raw_html_dir / f"{hit.candidate_id}.html",
                _raw_docket_html(record),
                retrieved_at="2026-07-12T12:00:00Z",
            )
        snapshot_path = store.export_snapshot(
            root / "snapshots",
            snapshot_id=snapshot_id,
            batch_id=batch_id,
            complete=True,
        )
    return snapshot_path, cycle_hash, raw_html_dir


def _raw_docket_html(record: dict[str, object]) -> bytes:
    selected_entries = cast(list[object], record["selected_entries"])
    rows: list[str] = []
    for entry_value in selected_entries:
        entry = cast(dict[str, object], entry_value)
        documents = cast(list[dict[str, object]], entry["documents"])
        [document] = documents
        action_label = str(document["action_label"])
        rows.append(
            '<div class="row" id="entry-{number}">'
            '<div class="col-xs-1">{number}</div>'
            '<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span>'
            "</div>"
            '<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>{kind}</div>'
            "<div>{description}</div>"
            '<a href="{href}">{action_label}</a>'
            "</div></div></div>".format(
                number=entry["entry_number"],
                filed_at=entry["filed_at"],
                text=entry["text"],
                kind=document["kind"],
                description=document["description"],
                href=document["href"],
                action_label=action_label,
            )
        )
    return (
        "<html><head><title>Fixture docket</title></head><body>"
        '<div id="docket-entry-table">' + "".join(rows) + "</div></body></html>"
    ).encode()


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")


def _purchase_policy(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    path = tmp_path / "purchase-policy.json"
    cohort_path = tmp_path / "cohort-policy.json"
    decisions = cli._fixture_cohort_policy_decisions()
    decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "2250.00",
        "max_per_case_usd": "73.20",
        "reservation_headroom_required": True,
    }
    cohort = cli.generate_cohort_policy(decisions)
    _write_json(cohort_path, cohort)
    _write_json(
        path,
        generate_case_dev_purchase_policy(
            {
                "cycle_id": "cycle-1",
                "cohort_policy_sha256": cohort["policy_sha256"],
                "canonical_ledger_path": str(ledger),
                "hard_cap_usd": "2250.00",
                "opening_committed_spend_usd": "0.00",
                "opening_case_committed_spend_usd": {},
                "max_per_case_usd": "73.20",
                "per_document_reservation_usd": "3.05",
                "fee_schedule": {
                    "source_citation": "case.dev pricing docs",
                    "verified_at_utc": "2026-07-13T00:00:00Z",
                    "includes_pacer_fees": True,
                    "includes_service_fees": True,
                    "includes_rounding": True,
                },
            }
        ),
    )
    return path, ledger, cohort_path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
