from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast import cli
from legalforecast.ingestion import target_raw_docket_auxiliary_provenance as bridge


def _jsonl(path: Path, records: list[dict[str, object]]) -> str:
    payload = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], dict[str, Path]]:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "raw-artifacts.jsonl").write_bytes(b"\n")
    source_raw = tmp_path / "source-raw"
    recovery_raw = tmp_path / "recovery-raw"
    source_raw.mkdir()
    recovery_raw.mkdir()

    first = "courtlistener-docket-100"
    second = "courtlistener-docket-200"
    first_payload = b"<html>baseline</html>"
    first_sha = hashlib.sha256(first_payload).hexdigest()
    first_path = source_raw / first / f"{first_sha}.html"
    first_path.parent.mkdir()
    first_path.write_bytes(first_payload)
    second_payload = b"<html>recovery</html>"
    second_sha = hashlib.sha256(second_payload).hexdigest()
    second_path = recovery_raw / "200.html"
    second_path.write_bytes(second_payload)

    selection = tmp_path / "selection.jsonl"
    selection_sha = _jsonl(
        selection,
        [
            {"candidate_id": "100", "selected": True},
            {"candidate_id": "200", "selected": True},
        ],
    )
    source_manifest = tmp_path / "source-raw-artifacts.jsonl"
    source_manifest_sha = _jsonl(
        source_manifest,
        [
            {
                "candidate_id": first,
                "path": str(first_path.resolve()),
                "sha256": first_sha,
                "byte_count": len(first_payload),
                "retrieved_at": "2026-08-08T00:00:00Z",
            }
        ],
    )
    cycle_store = tmp_path / "cycle.sqlite3"
    cycle_store.write_bytes(b"fixture")
    source_card = tmp_path / "source-union.json"
    source_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.screening_snapshot_union_summary.v1",
                "status": "completed",
                "snapshot_path": str(snapshot.resolve()),
                "input_paths": [str(cycle_store.resolve())],
                "output_commitments": {
                    "owned_raw_artifacts": {
                        "sha256": source_manifest_sha,
                        "byte_count": source_manifest.stat().st_size,
                        "row_count": 1,
                    }
                },
            }
        )
        + "\n"
    )
    retry_plan = tmp_path / "retry-plan.json"
    retry_plan.write_text("{}\n")
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n")
    successes = tmp_path / "successes.jsonl"
    _jsonl(successes, [{"candidate_id": second}])
    exclusions = tmp_path / "exclusions.jsonl"
    exclusions.write_bytes(b"")
    summary = tmp_path / "summary.json"
    summary.write_text("{}\n")

    source_snapshot_sha = "a" * 64
    receipt_value: dict[str, object] = {
        "cycle_hash": "b" * 64,
        "source_snapshot_manifest_sha256": source_snapshot_sha,
        "source_batch_id": "final153",
        "source_batch_digest": "c" * 64,
        "dry_run": False,
        "successes_sha256": _sha256(successes),
        "exclusions_sha256": _sha256(exclusions),
        "summary_sha256": _sha256(summary),
        "raw_artifacts": [
            {
                "candidate_id": second,
                "sha256": f"sha256:{second_sha}",
                "byte_count": len(second_payload),
                "retrieved_at": "2026-08-08T00:01:00Z",
            }
        ],
    }
    recovered_plan = SimpleNamespace(
        selection_path=str(selection.resolve()),
        selection_sha256=selection_sha,
        source_snapshot_path=str(snapshot.resolve()),
        source_snapshot_manifest_sha256=source_snapshot_sha,
        cycle_hash="b" * 64,
        cycle_store_path=str(cycle_store.resolve()),
        source_snapshot_run_card_path=str(source_card.resolve()),
        source_snapshot_run_card_sha256=_sha256(source_card),
        source_raw_manifest_path=str((snapshot / "raw-artifacts.jsonl").resolve()),
        source_raw_manifest_sha256=_sha256(snapshot / "raw-artifacts.jsonl"),
    )
    retry_plan_value = SimpleNamespace(
        root_plan_path=str(retry_plan.resolve()),
        root_plan_sha256=_sha256(retry_plan),
        root_failure_run_card_path=str(source_card.resolve()),
        root_failure_run_card_sha256=_sha256(source_card),
        direct_successor_plan_path=str(retry_plan.resolve()),
        direct_successor_plan_sha256=_sha256(retry_plan),
        direct_successor_failure_run_card_path=str(source_card.resolve()),
        direct_successor_failure_run_card_sha256=_sha256(source_card),
        provider_contract_defect_authorization_path=str(retry_plan.resolve()),
        provider_contract_defect_authorization_sha256=_sha256(retry_plan),
    )
    monkeypatch.setattr(
        bridge,
        "load_verified_screening_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            candidates=(
                SimpleNamespace(candidate_id=first),
                SimpleNamespace(candidate_id=second),
            ),
            payloads={
                "manifest.json": b"snapshot-manifest",
                "screened-cases.jsonl": b"screened\n",
            },
            raw_artifacts=(
                SimpleNamespace(
                    path=first_path,
                    content=first_payload,
                    content_authenticated=True,
                ),
            ),
        ),
    )
    monkeypatch.setattr(
        bridge,
        "load_target_raw_docket_recovery_provider_contract_retry_plan",
        lambda *args, **kwargs: retry_plan_value,
    )
    monkeypatch.setattr(
        bridge,
        "resolve_target_raw_docket_recovery_provider_contract_retry",
        lambda *args, **kwargs: (SimpleNamespace(), recovered_plan, SimpleNamespace()),
    )
    monkeypatch.setattr(
        bridge,
        "verify_target_raw_docket_recovery_receipt",
        lambda **kwargs: receipt_value,
    )
    paths = {
        "selection": selection,
        "snapshot": snapshot,
        "source_card": source_card,
        "cycle_store": cycle_store,
        "source_manifest": source_manifest,
        "source_raw": source_raw,
        "retry_plan": retry_plan,
        "receipt": receipt,
        "successes": successes,
        "exclusions": exclusions,
        "summary": summary,
        "recovery_raw": recovery_raw,
        "output_manifest": tmp_path / "output" / "raw-artifacts.jsonl",
        "bridge": tmp_path / "output" / "bridge.json",
        "run_card": tmp_path / "output" / "run-cards" / "bridge.json",
        "first_path": first_path,
    }
    values: dict[str, object] = {
        "selection_path": selection,
        "expected_selection_sha256": selection_sha,
        "source_snapshot_path": snapshot,
        "expected_source_snapshot_manifest_sha256": source_snapshot_sha,
        "expected_cycle_hash": "b" * 64,
        "source_union_run_card_path": source_card,
        "expected_source_union_run_card_sha256": _sha256(source_card),
        "source_cycle_store_path": cycle_store,
        "source_raw_artifacts_manifest_path": source_manifest,
        "expected_source_raw_artifacts_manifest_sha256": source_manifest_sha,
        "source_raw_html_dir": source_raw,
        "recovery_plan_path": retry_plan,
        "expected_recovery_plan_sha256": _sha256(retry_plan),
        "recovery_receipt_path": receipt,
        "expected_recovery_receipt_sha256": _sha256(receipt),
        "recovery_successes_path": successes,
        "recovery_exclusions_path": exclusions,
        "recovery_summary_path": summary,
        "recovery_raw_html_dir": recovery_raw,
        "raw_artifacts_manifest_path": paths["output_manifest"],
        "bridge_path": paths["bridge"],
        "run_card_path": paths["run_card"],
    }
    return values, paths


def test_builds_and_reauthenticates_provider_free_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values, paths = _fixture(tmp_path, monkeypatch)

    built = bridge.build_target_raw_docket_auxiliary_provenance_bridge(**values)
    verified = bridge.verify_target_raw_docket_auxiliary_provenance_bridge(**values)
    loaded = bridge.load_verified_target_raw_docket_auxiliary_provenance_bridge(
        paths["bridge"]
    )

    assert built.selected_candidate_ids == (
        "courtlistener-docket-100",
        "courtlistener-docket-200",
    )
    assert verified.raw_artifact_bytes_by_candidate["courtlistener-docket-100"] == (
        b"<html>baseline</html>"
    )
    assert loaded.raw_artifact_bytes_by_path[str(paths["first_path"])] == (
        b"<html>baseline</html>"
    )
    assert loaded.verified_artifact_bytes[os.path.abspath(paths["selection"])] == (
        paths["selection"].read_bytes()
    )
    assert (
        loaded.verified_artifact_bytes[
            os.path.abspath(paths["snapshot"] / "screened-cases.jsonl")
        ]
        == b"screened\n"
    )
    assert loaded.verified_artifact_bytes[os.path.abspath(paths["first_path"])] == (
        b"<html>baseline</html>"
    )
    manifest = [
        json.loads(line) for line in paths["output_manifest"].read_text().splitlines()
    ]
    assert (
        paths["output_manifest"]
        .read_bytes()
        .startswith(paths["source_manifest"].read_bytes())
    )
    assert [record["candidate_id"] for record in manifest] == [
        "courtlistener-docket-100",
        "courtlistener-docket-200",
    ]
    envelope = json.loads(paths["bridge"].read_text())
    assert envelope["bridge"]["provider_activity_executed"] is False
    assert envelope["bridge"]["paid_activity_executed"] is False


def test_rejects_tampered_selected_raw_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values, paths = _fixture(tmp_path, monkeypatch)
    bridge.build_target_raw_docket_auxiliary_provenance_bridge(**values)
    paths["first_path"].write_bytes(b"tampered")

    with pytest.raises(
        bridge.TargetRawDocketAuxiliaryProvenanceError,
        match="SHA-256 mismatch",
    ):
        bridge.verify_target_raw_docket_auxiliary_provenance_bridge(**values)


def test_rejects_recovery_candidate_not_selected_minus_source_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values, _paths = _fixture(tmp_path, monkeypatch)
    original = bridge.verify_target_raw_docket_recovery_receipt

    def wrong_receipt(**kwargs: object) -> Mapping[str, object]:
        receipt = dict(original(**kwargs))
        receipt["raw_artifacts"] = [
            {
                "candidate_id": "courtlistener-docket-300",
                "sha256": "sha256:" + "a" * 64,
                "byte_count": 1,
                "retrieved_at": "2026-08-08T00:01:00Z",
            }
        ]
        return receipt

    monkeypatch.setattr(
        bridge, "verify_target_raw_docket_recovery_receipt", wrong_receipt
    )
    with pytest.raises(
        bridge.TargetRawDocketAuxiliaryProvenanceError,
        match="lack one raw docket identity",
    ):
        bridge.build_target_raw_docket_auxiliary_provenance_bridge(**values)


def test_rejects_symlinked_selected_raw_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values, paths = _fixture(tmp_path, monkeypatch)
    target = tmp_path / "target.html"
    target.write_bytes(b"<html>baseline</html>")
    paths["first_path"].unlink()
    paths["first_path"].symlink_to(target)

    with pytest.raises(
        bridge.TargetRawDocketAuxiliaryProvenanceError, match="unique regular"
    ):
        bridge.build_target_raw_docket_auxiliary_provenance_bridge(**values)


def test_rejects_hardlinked_selected_raw_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values, paths = _fixture(tmp_path, monkeypatch)
    linked_copy = tmp_path / "linked-copy.html"
    os.link(paths["first_path"], linked_copy)

    with pytest.raises(
        bridge.TargetRawDocketAuxiliaryProvenanceError, match="unique regular"
    ):
        bridge.build_target_raw_docket_auxiliary_provenance_bridge(**values)


def test_immutable_bridge_write_uses_close_on_exec_and_no_follow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "output" / "bridge.json"
    captured: list[int] = []
    original_open = bridge.os.open

    def recording_open(
        path: object, flags: int, *args: object, **kwargs: object
    ) -> int:
        if path == destination:
            captured.append(flags)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(bridge.os, "open", recording_open)

    bridge._write_immutable(  # pyright: ignore[reportPrivateUsage]
        destination,
        b"{}\n",
    )

    assert len(captured) == 1
    assert captured[0] & getattr(os, "O_CLOEXEC", 0)
    assert captured[0] & getattr(os, "O_NOFOLLOW", 0)


def test_packet_input_planner_help_exposes_raw_provenance_bridge(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        cli.main(["acquisition", "plan-packet-inputs", "--help"])

    assert "--raw-provenance-bridge" in capsys.readouterr().out


def test_packet_build_and_planner_replay_accept_bare_hex_bridge_commitment() -> None:
    payload = b'{"bridge":"authenticated"}\n'
    verified = SimpleNamespace(
        bridge_sha256=hashlib.sha256(payload).hexdigest(),
    )

    cli._require_packet_raw_provenance_bridge_commitment(  # pyright: ignore[reportPrivateUsage]
        verified,
        payload,
    )


def test_packet_build_and_planner_replay_reject_prefixed_bridge_commitment() -> None:
    payload = b'{"bridge":"authenticated"}\n'
    verified = SimpleNamespace(
        bridge_sha256="sha256:" + hashlib.sha256(payload).hexdigest(),
    )

    with pytest.raises(cli.CommandError, match="raw-provenance bridge differs"):
        cli._require_packet_raw_provenance_bridge_commitment(  # pyright: ignore[reportPrivateUsage]
            verified,
            payload,
        )


def test_bridge_cli_publishes_provider_free_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def build(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            selected_candidate_ids=("courtlistener-docket-100",),
            bridge_sha256="a" * 64,
            raw_artifacts_manifest_sha256="b" * 64,
        )

    completions: list[dict[str, object]] = []
    monkeypatch.setattr(
        cli, "build_target_raw_docket_auxiliary_provenance_bridge", build
    )
    monkeypatch.setattr(
        cli,
        "_write_acquisition_completion",
        lambda _args, **kwargs: completions.append(kwargs),
    )
    root = tmp_path / "out"
    arguments = [
        "acquisition",
        "build-target-raw-docket-auxiliary-provenance-bridge",
        "--execute",
        "--output-root",
        str(root),
    ]
    path_options = {
        "--selection": "selection.jsonl",
        "--source-snapshot": "snapshot",
        "--source-union-run-card": "union.json",
        "--source-cycle-store": "cycle.sqlite3",
        "--source-raw-artifacts-manifest": "raw.jsonl",
        "--source-raw-html-dir": "raw-html",
        "--recovery-plan": "retry-plan.json",
        "--recovery-receipt": "receipt.json",
        "--recovery-successes": "successes.jsonl",
        "--recovery-exclusions": "exclusions.jsonl",
        "--recovery-summary": "summary.json",
        "--recovery-raw-html-dir": "recovery-html",
        "--raw-artifacts-manifest-output": "output/raw.jsonl",
        "--bridge-output": "output/bridge.json",
        "--bridge-run-card-output": "output/run-card.json",
    }
    sha_options = {
        "--expected-selection-sha256": "a" * 64,
        "--expected-source-snapshot-manifest-sha256": "b" * 64,
        "--expected-cycle-hash": "c" * 64,
        "--expected-source-union-run-card-sha256": "d" * 64,
        "--expected-source-raw-artifacts-manifest-sha256": "e" * 64,
        "--expected-recovery-plan-sha256": "f" * 64,
        "--expected-recovery-receipt-sha256": "0" * 64,
    }
    for option, name in path_options.items():
        arguments.extend((option, str(tmp_path / name)))
    for option, value in sha_options.items():
        arguments.extend((option, value))

    assert cli.main(arguments) == 0
    assert captured["raw_artifacts_manifest_path"] == tmp_path / "output/raw.jsonl"
    assert completions[0]["record_count"] == 1
    assert completions[0]["paid_activity_executed"] is False
