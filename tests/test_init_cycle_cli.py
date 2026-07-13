from __future__ import annotations

import json
import socket
from pathlib import Path

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore


def test_init_cycle_help_documents_zero_provider_identity_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "init-cycle", "--help"])
    output = capsys.readouterr().out

    assert "--eligibility-anchor" in output
    assert "--cycle-store" in output
    assert "--identity-output" in output
    assert "performs no Firecrawl" in output


def test_init_cycle_creates_and_idempotently_verifies_identity_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("init-cycle must not access the network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    output_root = tmp_path / "cycle"
    args = [
        "acquisition",
        "init-cycle",
        "--output-root",
        str(output_root),
        "--eligibility-anchor",
        "2026-06-30",
        "--execute",
    ]

    assert main(args) == 0
    identity_path = output_root / "cycle-identity.json"
    first_bytes = identity_path.read_bytes()
    identity = _read_json(identity_path)
    with CycleAcquisitionStore(output_root / "cycle-acquisition.sqlite3") as store:
        assert identity["cycle_hash"] == store.cycle_hash
        assert identity["policy"] == store.cycle_policy

    assert main(args) == 0
    assert identity_path.read_bytes() == first_bytes
    assert identity["eligibility_anchor"] == "2026-06-30"
    assert identity["initialized_or_verified"] is True
    assert identity["provider_activity_requested"] is False
    assert identity["provider_activity_executed"] is False
    assert identity["firecrawl_metered_activity_requested"] is False
    assert identity["pacer_paid_activity_requested"] is False

    run_card = _read_json(output_root / "run-cards" / "init-cycle.json")
    assert run_card["stage"] == "init-cycle"
    assert run_card["status"] == "completed"
    assert run_card["cycle_hash"] == identity["cycle_hash"]
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False


def test_init_cycle_fails_closed_on_anchor_drift_and_preserves_identity(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "cycle"
    assert main(_args(output_root, anchor="2026-06-30")) == 0
    identity_path = output_root / "cycle-identity.json"
    original = identity_path.read_bytes()

    assert main(_args(output_root, anchor="2026-07-01")) == 2

    assert identity_path.read_bytes() == original
    run_card = _read_json(output_root / "run-cards" / "init-cycle.json")
    assert run_card["status"] == "failed"
    assert "cycle policy mismatch" in run_card["failure_reason"]
    assert run_card["provider_activity_executed"] is False


def test_init_cycle_fails_closed_on_screening_source_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "cycle"
    original_hashes = {"screen": "a" * 64}
    monkeypatch.setattr(
        cli_module,
        "_current_screening_source_sha256",
        lambda: dict(original_hashes),
    )
    assert main(_args(output_root, anchor="2026-06-30")) == 0
    identity_path = output_root / "cycle-identity.json"
    original = identity_path.read_bytes()

    monkeypatch.setattr(
        cli_module,
        "_current_screening_source_sha256",
        lambda: {"screen": "b" * 64},
    )
    assert main(_args(output_root, anchor="2026-06-30")) == 2

    assert identity_path.read_bytes() == original
    run_card = _read_json(output_root / "run-cards" / "init-cycle.json")
    assert run_card["status"] == "failed"
    assert "cycle policy mismatch" in run_card["failure_reason"]


def test_init_cycle_dry_run_does_not_create_store(tmp_path: Path) -> None:
    output_root = tmp_path / "cycle"

    assert (
        main(
            [
                "acquisition",
                "init-cycle",
                "--output-root",
                str(output_root),
                "--eligibility-anchor",
                "2026-06-30",
            ]
        )
        == 0
    )

    assert not (output_root / "cycle-acquisition.sqlite3").exists()
    identity = _read_json(output_root / "cycle-identity.json")
    assert identity["dry_run"] is True
    assert identity["initialized_or_verified"] is False


def _args(output_root: Path, *, anchor: str) -> list[str]:
    return [
        "acquisition",
        "init-cycle",
        "--output-root",
        str(output_root),
        "--eligibility-anchor",
        anchor,
        "--execute",
    ]


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
