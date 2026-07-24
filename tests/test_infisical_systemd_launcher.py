from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from legalforecast.ingestion.infisical_systemd_launcher import (
    EXIT_MISSING_CHILD_RECEIPT,
    main,
)


def _write_masking_sandbox(
    path: Path,
    *,
    run_child: bool = True,
    sandbox_status: int = 0,
) -> None:
    child_block = '"$@" >/dev/null 2>&1\n' if run_child else ""
    path.write_text(
        f"""#!/usr/bin/env bash
set -u
[[ "${{1:-}}" == "run" ]] || exit 64
shift
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --path) shift 2 ;;
    --) shift; break ;;
    *) exit 64 ;;
  esac
done
{child_block}exit {sandbox_status}
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run_launcher(
    tmp_path: Path,
    *,
    child_status: int,
    run_child: bool = True,
    sandbox_status: int = 0,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    sandbox = tmp_path / "infisical-agent-sandbox"
    _write_masking_sandbox(
        sandbox,
        run_child=run_child,
        sandbox_status=sandbox_status,
    )
    receipt = tmp_path / "launch-receipt.json"
    temporary_base = tmp_path / "private-temporary-directories"
    temporary_base.mkdir()
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["TMPDIR"] = str(temporary_base)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "legalforecast.ingestion.infisical_systemd_launcher",
            "--sandbox-path",
            "/agents/sandbox/legalforecastbench-acquisition",
            "--receipt-output",
            str(receipt),
            "--",
            sys.executable,
            "-c",
            f"raise SystemExit({child_status})",
        ],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert list(temporary_base.iterdir()) == []
    return completed, payload


@pytest.mark.parametrize("child_status", [0, 23])
def test_launcher_recovers_exact_child_status_when_sandbox_masks_it(
    tmp_path: Path,
    child_status: int,
) -> None:
    completed, receipt = _run_launcher(tmp_path, child_status=child_status)

    assert completed.returncode == child_status
    assert receipt["schema"] == "legalforecast.infisical_systemd_launch.v1"
    assert receipt["child_exit_status"] == child_status
    assert receipt["sandbox_exit_status"] == 0
    assert receipt["effective_exit_status"] == child_status
    assert receipt["sandbox_status_was_masked"] is (child_status != 0)
    assert receipt["child_receipt_observed"] is True
    assert receipt["command_sha256"]
    assert "command" not in receipt
    assert "environment" not in receipt


@pytest.mark.parametrize(
    ("child_status", "sandbox_status", "expected_status"),
    [(0, 42, 42), (23, 42, 23)],
)
def test_launcher_fails_closed_on_an_independent_sandbox_failure(
    tmp_path: Path,
    child_status: int,
    sandbox_status: int,
    expected_status: int,
) -> None:
    completed, receipt = _run_launcher(
        tmp_path,
        child_status=child_status,
        sandbox_status=sandbox_status,
    )

    assert completed.returncode == expected_status
    assert receipt["child_exit_status"] == child_status
    assert receipt["sandbox_exit_status"] == sandbox_status
    assert receipt["effective_exit_status"] == expected_status
    assert receipt["sandbox_failure_observed"] is True


def test_launcher_fails_closed_when_masked_sandbox_writes_no_child_receipt(
    tmp_path: Path,
) -> None:
    completed, receipt = _run_launcher(
        tmp_path,
        child_status=0,
        run_child=False,
    )

    assert completed.returncode == EXIT_MISSING_CHILD_RECEIPT
    assert receipt["child_exit_status"] is None
    assert receipt["sandbox_exit_status"] == 0
    assert receipt["effective_exit_status"] == EXIT_MISSING_CHILD_RECEIPT
    assert receipt["child_receipt_observed"] is False


def test_child_mode_rejects_a_mismatched_nonce(tmp_path: Path) -> None:
    receipt = tmp_path / "child.json"

    status = main(
        [
            "_record-child-status",
            "--receipt",
            str(receipt),
            "--nonce",
            "not-a-valid-nonce",
            "--",
            sys.executable,
            "-c",
            "raise SystemExit(0)",
        ]
    )

    assert status == 64
    assert not receipt.exists()


def test_launcher_records_missing_sandbox_as_status_127(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "launch-receipt.json"
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))

    status = main(
        [
            "--sandbox-path",
            "/agents/sandbox/legalforecastbench-acquisition",
            "--receipt-output",
            str(receipt),
            "--",
            "/usr/bin/true",
        ]
    )

    assert status == 127
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["sandbox_exit_status"] == 127
    assert payload["child_receipt_observed"] is False
    assert payload["effective_exit_status"] == 127


@pytest.mark.parametrize(
    "sandbox_path",
    [
        "/agents/sandbox",
        "/agents/sandbox/",
        "/agents/sandbox/.",
        "/agents/sandbox/legalforecastbench-acquisition/..",
        "/agents/sandbox/unrelated",
    ],
)
def test_launcher_rejects_broad_or_unapproved_sandbox_paths(
    tmp_path: Path,
    sandbox_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "launch-receipt.json"
    marker = tmp_path / "sandbox-was-invoked"
    sandbox = tmp_path / "infisical-agent-sandbox"
    sandbox.write_text(
        f"""#!/bin/bash
printf invoked > {marker}
exit 99
""",
        encoding="utf-8",
    )
    sandbox.chmod(sandbox.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path))

    status = main(
        [
            "--sandbox-path",
            sandbox_path,
            "--receipt-output",
            str(receipt),
            "--",
            "/usr/bin/true",
        ]
    )

    assert status == 64
    assert not receipt.exists()
    assert not marker.exists()
