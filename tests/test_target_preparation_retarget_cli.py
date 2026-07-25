# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.firecrawl_screening_identity import (
    firecrawl_screening_implementation,
    source_manifest_sha256,
)
from legalforecast.ingestion.target_100_acquisition import (
    TargetCohortPreparationConfig,
)
from pytest import CaptureFixture
from tests.test_target_100_acquisition import (
    _snapshot_manifest_sha256,
    _target_100_fixture,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, str], ...]:
    if not root.exists() and not root.is_symlink():
        return ()
    entries: list[tuple[str, str, str]] = []
    for path in (root, *sorted(root.rglob("*"))):
        metadata = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        if stat.S_ISLNK(metadata.st_mode):
            entries.append((relative, "symlink", os.readlink(path)))
        elif stat.S_ISDIR(metadata.st_mode):
            entries.append((relative, "directory", ""))
        elif stat.S_ISREG(metadata.st_mode):
            entries.append(
                (relative, "file", hashlib.sha256(path.read_bytes()).hexdigest())
            )
        else:
            entries.append((relative, "other", str(metadata.st_mode)))
    return tuple(entries)


def _minimal_retarget_command(
    *,
    source: Path | None,
    destination: Path,
    target_case_count: int = 100,
    execute: bool = True,
    stop_after: bool = False,
) -> list[str]:
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(destination),
        "--snapshot",
        str(destination.parent / "unread-snapshot"),
        "--expected-cycle-hash",
        "a" * 64,
        "--expected-snapshot-manifest-sha256",
        "b" * 64,
        "--target-case-count",
        str(target_case_count),
        "--fixture-documents",
        str(destination.parent / "unread-documents.json"),
        "--courtlistener-fixture",
        str(destination.parent / "unread-courtlistener.jsonl"),
    ]
    if source is not None:
        command.extend(("--retarget-source-preparation-root", str(source)))
    if stop_after:
        command.extend(("--stop-after", "retarget-import"))
    if execute:
        command.append("--execute")
    return command


@pytest.mark.parametrize(
    "relationship",
    (
        "same",
        "source-parent",
        "destination-parent",
        "source-symlink",
        "destination-symlink",
    ),
)
def test_retarget_cli_rejects_aliasing_roots_before_any_tree_mutation(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    relationship: str,
) -> None:
    arena = tmp_path / "arena"
    arena.mkdir()
    if relationship == "same":
        source = destination = arena / "source"
        source.mkdir()
    elif relationship == "source-parent":
        source = arena / "source"
        source.mkdir()
        destination = source / "new-target"
    elif relationship == "destination-parent":
        destination = arena / "destination"
        source = destination / "old-target"
        source.mkdir(parents=True)
    elif relationship == "source-symlink":
        real_source = arena / "real-source"
        real_source.mkdir()
        source = arena / "source-link"
        source.symlink_to(real_source, target_is_directory=True)
        destination = arena / "destination"
    else:
        source = arena / "source"
        source.mkdir()
        real_destination = arena / "real-destination"
        real_destination.mkdir()
        destination = arena / "destination-link"
        destination.symlink_to(real_destination, target_is_directory=True)
    (source.resolve() / "sentinel.txt").write_text("unchanged\n", encoding="utf-8")
    before = _tree_snapshot(arena)

    assert (
        cli.main(_minimal_retarget_command(source=source, destination=destination)) == 2
    )

    stderr = capsys.readouterr().err
    expected = "symlink" if relationship.endswith("symlink") else "disjoint"
    assert expected in stderr
    assert _tree_snapshot(arena) == before


def test_retarget_cli_help_and_stop_after_constraints(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        cli.main(["acquisition", "prepare-target-cohort", "--help"])
    help_text = capsys.readouterr().out
    assert "--retarget-source-preparation-root" in help_text
    assert "--stop-after {retarget-import}" in help_text
    assert "immutable provider-free import receipt" in help_text
    assert "canonical preparation success evidence" in help_text

    no_source = tmp_path / "no-source"
    assert (
        cli.main(
            _minimal_retarget_command(
                source=None,
                destination=no_source,
                stop_after=True,
            )
        )
        == 2
    )
    assert "--stop-after requires" in capsys.readouterr().err
    assert not no_source.exists()

    source = tmp_path / "source"
    source.mkdir()
    (source / "sentinel.txt").write_text("unchanged\n", encoding="utf-8")
    source_before = _tree_snapshot(source)
    dry_run_destination = tmp_path / "dry-run-destination"
    assert (
        cli.main(
            _minimal_retarget_command(
                source=source,
                destination=dry_run_destination,
                execute=False,
                stop_after=True,
            )
        )
        == 2
    )
    assert "requires --execute" in capsys.readouterr().err
    assert _tree_snapshot(source) == source_before
    assert not dry_run_destination.exists()

    wrong_count_destination = tmp_path / "wrong-count-destination"
    assert (
        cli.main(
            _minimal_retarget_command(
                source=source,
                destination=wrong_count_destination,
                target_case_count=99,
                stop_after=True,
            )
        )
        == 2
    )
    assert "exactly 100" in capsys.readouterr().err
    assert _tree_snapshot(source) == source_before
    assert not wrong_count_destination.exists()


def _failed_source_for_snapshot(
    root: Path,
    *,
    snapshot: Path,
    cycle_hash: str,
) -> Path:
    root.mkdir(parents=True)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    config: dict[str, Any] = {
        "schema_version": "legalforecast.target_cohort_config.v1",
        "driver_execute": True,
        "target_case_count": 148,
        "snapshot_manifest_sha256": ("sha256:" + _snapshot_manifest_sha256(snapshot)),
        "snapshot_cycle_hash": cycle_hash,
        "snapshot_batch_digest": manifest["batch_digest"],
        "stage_commands": [{"stage": "bridge-pacer-gaps", "argv": ["x"]}],
    }
    config["config_sha256"] = cli._canonical_json_sha256(config)
    _write_json(root / "target-cohort-config.json", config)
    attempt_id = "20260725T120000.000000Z-test-retarget"
    _write_json(
        root / f"attempts/prepare-target-cohort/{attempt_id}/run-card.json",
        {
            "schema_version": "legalforecast.target_cohort_attempt.v1",
            "attempt_id": attempt_id,
            "stage": "prepare-target-cohort",
            "status": "failed",
            "failure_reason": "restricted document",
            "dry_run": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "requested_output_root": str(root.resolve()),
            "config_sha256": config["config_sha256"],
        },
    )
    return root


def _replace_snapshot_with_historical_screening_implementation(
    snapshot: Path,
) -> None:
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    implementation = firecrawl_screening_implementation()
    source_value = implementation["source_sha256"]
    assert isinstance(source_value, dict)
    source_sha256: dict[str, str] = {}
    for source_path, digest in cast(dict[object, object], source_value).items():
        assert isinstance(source_path, str)
        assert isinstance(digest, str)
        source_sha256[source_path] = digest
    [first_source] = sorted(source_sha256)[:1]
    source_sha256[first_source] = "0" * 64
    historical = {
        "schema_version": implementation["schema_version"],
        "source_sha256": source_sha256,
        "manifest_sha256": source_manifest_sha256(source_sha256),
    }
    manifest["stage_commitments"] = {
        "firecrawl_screen_inputs": {
            "schema_version": ("legalforecast.firecrawl_screen_input_commitment.v1")
        },
        "firecrawl_screening_implementation": historical,
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _executed_target_command(
    *,
    destination: Path,
    snapshot: Path,
    cycle_hash: str,
    fixture_documents: Path,
    courtlistener_fixture: Path,
    source: Path | None = None,
    stop_after: bool = True,
) -> list[str]:
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(destination),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--target-case-count",
        "100",
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]
    if source is not None:
        command.extend(
            (
                "--retarget-source-preparation-root",
                str(source),
            )
        )
        if stop_after:
            command.extend(("--stop-after", "retarget-import"))
    return command


def test_stop_after_retarget_import_exits_before_providers_or_success_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "fixture", case_count=100)
    )
    source = _failed_source_for_snapshot(
        tmp_path / "failed-source",
        snapshot=snapshot,
        cycle_hash=cycle_hash,
    )
    destination = tmp_path / "target"
    calls: list[str] = []

    def reject_provider(*args: object, **kwargs: object) -> object:
        raise AssertionError("retarget-import boundary must not construct a provider")

    def fake_import(**kwargs: object) -> None:
        calls.append("retarget-import")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", reject_provider)
    monkeypatch.setattr(cli, "_free_document_source", reject_provider)
    monkeypatch.setattr(cli, "_execute_target_retarget_import", fake_import)
    command = _executed_target_command(
        destination=destination,
        snapshot=snapshot,
        cycle_hash=cycle_hash,
        fixture_documents=fixture_documents,
        courtlistener_fixture=courtlistener_fixture,
        source=source,
    )

    assert cli.main(command) == 0

    assert calls == ["retarget-import"]
    assert not (destination / "target-cohort-preparation-summary.json").exists()
    assert not (destination / "run-cards/prepare-target-cohort.json").exists()
    assert not (destination / "03c-merged-downloads").exists()
    assert not (destination / "04-cost-ranking").exists()
    assert not (destination / "05-budget").exists()
    assert not (destination / "06-clearance-inputs").exists()


def test_only_authenticated_retarget_accepts_historical_screening_implementation(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "fixture", case_count=100)
    )
    _replace_snapshot_with_historical_screening_implementation(snapshot)
    source = _failed_source_for_snapshot(
        tmp_path / "failed-source",
        snapshot=snapshot,
        cycle_hash=cycle_hash,
    )
    imported: list[Path] = []

    def reject_provider(*args: object, **kwargs: object) -> object:
        raise AssertionError("screening identity gate must precede provider setup")

    def fake_import(**kwargs: object) -> None:
        config = kwargs["config"]
        assert isinstance(config, TargetCohortPreparationConfig)
        imported.append(config.output_root)

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", reject_provider)
    monkeypatch.setattr(cli, "_free_document_source", reject_provider)
    monkeypatch.setattr(cli, "_execute_target_retarget_import", fake_import)
    retarget_destination = tmp_path / "authenticated-retarget"
    retarget_command = _executed_target_command(
        destination=retarget_destination,
        snapshot=snapshot,
        cycle_hash=cycle_hash,
        fixture_documents=fixture_documents,
        courtlistener_fixture=courtlistener_fixture,
        source=source,
    )

    assert cli.main(retarget_command) == 0
    assert imported == [retarget_destination]

    ordinary_destination = tmp_path / "ordinary-preparation"
    ordinary_command = _executed_target_command(
        destination=ordinary_destination,
        snapshot=snapshot,
        cycle_hash=cycle_hash,
        fixture_documents=fixture_documents,
        courtlistener_fixture=courtlistener_fixture,
    )
    assert cli.main(ordinary_command) == 2
    assert (
        "screening sources do not match the committed implementation"
        in capsys.readouterr().err
    )
    assert imported == [retarget_destination]
    assert not (ordinary_destination / "00-authenticated-snapshot").exists()


def test_retarget_resume_skips_committed_public_plan_and_advances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "historical-fixture", case_count=100)
    )
    _replace_snapshot_with_historical_screening_implementation(snapshot)
    source = _failed_source_for_snapshot(
        tmp_path / "failed-source",
        snapshot=snapshot,
        cycle_hash=cycle_hash,
    )
    destination = tmp_path / "retarget"
    receipt_path = destination / "target-cohort-retarget-import.json"
    stage_01_evidence = (
        destination / "01-public-plan/free-document-requests.jsonl",
        destination / "01-public-plan/public-packet-plan-summary.json",
        destination / "run-cards/plan-public-downloads.json",
        destination / "logs/plan-public-downloads.jsonl",
    )

    def fake_import(**kwargs: object) -> None:
        _write_json(receipt_path, {"authenticated_import_complete": True})
        stage_01_evidence[0].parent.mkdir(parents=True, exist_ok=True)
        stage_01_evidence[0].write_text(
            '{"candidate_id":"candidate-a"}\n', encoding="utf-8"
        )
        _write_json(
            stage_01_evidence[1],
            {"generated_at": "2026-07-25T12:00:00Z", "record_count": 1},
        )
        _write_json(
            stage_01_evidence[2],
            {"completed_at": "2026-07-25T12:00:01Z", "status": "completed"},
        )
        stage_01_evidence[3].parent.mkdir(parents=True, exist_ok=True)
        stage_01_evidence[3].write_text(
            '{"at":"2026-07-25T12:00:01Z","event":"completed"}\n',
            encoding="utf-8",
        )

    monkeypatch.setattr(cli, "_execute_target_retarget_import", fake_import)
    stop_command = _executed_target_command(
        destination=destination,
        snapshot=snapshot,
        cycle_hash=cycle_hash,
        fixture_documents=fixture_documents,
        courtlistener_fixture=courtlistener_fixture,
        source=source,
    )
    assert cli.main(stop_command) == 0
    assert receipt_path.is_file()
    stage_01_before = {path: path.read_bytes() for path in stage_01_evidence}

    verification_calls: list[Path] = []
    screening_requirements: list[bool] = []
    advanced_stages: list[str] = []

    def fake_verify_and_seed(**kwargs: object) -> object:
        assert receipt_path.is_file()
        config = kwargs["config"]
        assert isinstance(config, TargetCohortPreparationConfig)
        verification_calls.append(config.output_root)
        return object()

    def fake_public_plan(
        args: object,
        *,
        require_current_screening: bool = True,
    ) -> int:
        screening_requirements.append(require_current_screening)
        return 0

    def stop_at_download(args: object) -> int:
        advanced_stages.append("download-free")
        return 2

    monkeypatch.setattr(
        cli,
        "_verify_and_seed_target_retarget_import",
        fake_verify_and_seed,
    )
    monkeypatch.setattr(cli, "_cmd_acquisition_plan_public_downloads", fake_public_plan)
    monkeypatch.setattr(cli, "_cmd_acquisition_download_free", stop_at_download)
    resume_command = _executed_target_command(
        destination=destination,
        snapshot=snapshot,
        cycle_hash=cycle_hash,
        fixture_documents=fixture_documents,
        courtlistener_fixture=courtlistener_fixture,
        source=source,
        stop_after=False,
    )

    assert cli.main(resume_command) == 2
    assert verification_calls == [destination]
    assert screening_requirements == []
    assert advanced_stages == ["download-free"]
    assert {path: path.read_bytes() for path in stage_01_evidence} == stage_01_before

    (
        current_snapshot,
        current_cycle_hash,
        current_fixture_documents,
        current_courtlistener_fixture,
    ) = _target_100_fixture(tmp_path / "current-fixture", case_count=100)
    ordinary_destination = tmp_path / "ordinary"
    ordinary_command = _executed_target_command(
        destination=ordinary_destination,
        snapshot=current_snapshot,
        cycle_hash=current_cycle_hash,
        fixture_documents=current_fixture_documents,
        courtlistener_fixture=current_courtlistener_fixture,
    )

    assert cli.main(ordinary_command) == 2
    assert screening_requirements == [True]
    assert advanced_stages == ["download-free", "download-free"]


def _seed_fixture(tmp_path: Path) -> tuple[TargetCohortPreparationConfig, Path, Path]:
    output_root = tmp_path / "target"
    baseline_root = output_root / "retarget-import/bridge-baseline"
    baseline_checkpoints = baseline_root / "checkpoints/pacer-gap-bridge"
    filename = "000001-0123456789abcdef.json"
    baseline_checkpoint = baseline_checkpoints / filename
    checkpoint_payload = b'{"candidate_id":"candidate-a","outcome":"failure"}\n'
    baseline_checkpoint.parent.mkdir(parents=True)
    baseline_checkpoint.write_bytes(checkpoint_payload)
    baseline_config = (
        baseline_root / "checkpoints/pacer-gap-bridge-progress-config.json"
    )
    baseline_config.write_bytes(b'{"semantic_revision":"v5"}\n')
    digest = "sha256:" + hashlib.sha256(checkpoint_payload).hexdigest()
    _write_json(
        baseline_root / "run-cards/rebase-pacer-gap-checkpoints-receipt.json",
        {
            "checkpoint_count": 1,
            "checkpoint_bindings": [
                {"current_filename": filename, "current_sha256": digest}
            ],
        },
    )
    config = TargetCohortPreparationConfig(
        output_root=output_root,
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=100,
        target_case_count=100,
        authenticated_screened_cases=tmp_path / "screened.jsonl",
        screened_cases_sha256="c" * 64,
    )
    live_checkpoint = (
        output_root / "03-gap-bridge/checkpoints/pacer-gap-bridge" / filename
    )
    return config, baseline_checkpoint, live_checkpoint


def test_live_seed_receipt_commits_zero_provider_fields_and_exact_bindings(
    tmp_path: Path,
) -> None:
    config, baseline_checkpoint, live_checkpoint = _seed_fixture(tmp_path)

    receipt_path = cli._seed_target_retarget_bridge(config=config)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "legalforecast.target_retarget_live_seed.v1"
    assert receipt["baseline_root"] == str(
        (config.output_root / "retarget-import/bridge-baseline").resolve()
    )
    assert receipt["live_checkpoint_root"] == str(live_checkpoint.parent.resolve())
    assert receipt["checkpoint_count"] == 1
    assert receipt["checkpoint_bindings"] == [
        {
            "filename": baseline_checkpoint.name,
            "sha256": "sha256:"
            + hashlib.sha256(baseline_checkpoint.read_bytes()).hexdigest(),
        }
    ]
    assert receipt["provider_client_constructed"] is False
    assert receipt["provider_request_count"] == 0
    assert receipt["network_request_count"] == 0
    assert receipt["paid_activity_requested"] is False
    assert receipt["paid_activity_executed"] is False
    unhashed = dict(receipt)
    claimed = unhashed.pop("receipt_sha256")
    assert claimed == cli._canonical_json_sha256(unhashed)
    assert not os.path.samestat(baseline_checkpoint.stat(), live_checkpoint.stat())


def test_live_seed_rejects_duplicate_checkpoint_filename_bindings(
    tmp_path: Path,
) -> None:
    config, baseline_checkpoint, _ = _seed_fixture(tmp_path)
    receipt_path = (
        config.output_root / "retarget-import/bridge-baseline/run-cards/"
        "rebase-pacer-gap-checkpoints-receipt.json"
    )
    digest = "sha256:" + hashlib.sha256(baseline_checkpoint.read_bytes()).hexdigest()
    _write_json(
        receipt_path,
        {
            "checkpoint_count": 2,
            "checkpoint_bindings": [
                {
                    "current_filename": baseline_checkpoint.name,
                    "current_sha256": digest,
                },
                {
                    "current_filename": baseline_checkpoint.name,
                    "current_sha256": "sha256:" + "f" * 64,
                },
            ],
        },
    )

    with pytest.raises(cli.CommandError, match="bindings do not reconcile"):
        cli._seed_target_retarget_bridge(config=config)


def test_retarget_rejects_current_plan_that_differs_from_authenticated_source(
    tmp_path: Path,
) -> None:
    current_request = cli.FreeDocumentDownloadRequest(
        candidate_id="candidate-a",
        source_provider="courtlistener",
        source_document_id="current-document",
        docket_entry_number=1,
        document_role=cli.DocumentRole.COMPLAINT,
        source_url="https://www.courtlistener.com/recap/current-document.pdf",
    )
    plan_path = tmp_path / "01-public-plan/free-document-requests.jsonl"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(current_request.to_record(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_request = cli.FreeDocumentDownloadRequest(
        candidate_id="candidate-a",
        source_provider="courtlistener",
        source_document_id="authenticated-source-document",
        docket_entry_number=1,
        document_role=cli.DocumentRole.COMPLAINT,
        source_url=(
            "https://www.courtlistener.com/recap/authenticated-source-document.pdf"
        ),
    )

    with pytest.raises(cli.CommandError, match="public plan differs"):
        cli._verify_retarget_public_plan_matches_source(
            output_root=tmp_path,
            source_requests=(source_request,),
            stage_02_count=1,
        )


@pytest.mark.parametrize("mutation", ("missing", "contradictory"))
def test_existing_live_seed_receipt_rejects_missing_or_contradictory_live_state(
    tmp_path: Path,
    mutation: str,
) -> None:
    config, _, live_checkpoint = _seed_fixture(tmp_path)
    receipt_path = cli._seed_target_retarget_bridge(config=config)
    receipt_before = receipt_path.read_bytes()
    if mutation == "missing":
        live_checkpoint.unlink()
        expected = "regular non-symlink file"
    else:
        live_checkpoint.write_text('{"candidate_id":"attacker"}\n', encoding="utf-8")
        expected = "contradicts its immutable seed"

    with pytest.raises(cli.CommandError, match=expected):
        cli._seed_target_retarget_bridge(config=config)

    assert receipt_path.read_bytes() == receipt_before
