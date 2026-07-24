#!/usr/bin/env python3
"""Provider-free operational smoke for Infisical child status propagation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SANDBOX_PATH: Final = "/agents/sandbox/legalforecastbench-acquisition"


def _write_masking_sandbox(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -u
[[ "${1:-}" == "run" ]] || exit 64
shift
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --path) shift 2 ;;
    --) shift; break ;;
    *) exit 64 ;;
  esac
done
"$@" >/dev/null 2>&1
exit 0
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _systemd_properties(unit_name: str) -> dict[str, str]:
    completed = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit_name,
            "--property=Result",
            "--property=ExecMainCode",
            "--property=ExecMainStatus",
            "--no-pager",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return dict(
        line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line
    )


def _run_case(
    *,
    temporary_root: Path,
    masking_sandbox: Path,
    child_status: int,
) -> dict[str, object]:
    unit_name = f"lfb-infisical-status-{child_status}-{uuid.uuid4().hex[:12]}"
    receipt_path = temporary_root / f"launcher-{child_status}.json"
    path = f"{masking_sandbox.parent}:{os.environ['PATH']}"
    launcher = shutil.which("legalforecast-acquisition-systemd-run")
    if launcher is None:
        raise RuntimeError(
            "installed legalforecast acquisition launcher is unavailable"
        )
    command = [
        "systemd-run",
        "--user",
        "--wait",
        f"--unit={unit_name}",
        "--property=Type=exec",
        f"--setenv=PATH={path}",
        f"--setenv=PYTHONPATH={ROOT}",
        launcher,
        "--sandbox-path",
        SANDBOX_PATH,
        "--receipt-output",
        str(receipt_path),
        "--",
        sys.executable,
        "-c",
        f"raise SystemExit({child_status})",
    ]
    try:
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
        properties = _systemd_properties(unit_name)
        launch_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    finally:
        subprocess.run(
            ["systemctl", "--user", "stop", unit_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["systemctl", "--user", "reset-failed", unit_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    expected_result = "success" if child_status == 0 else "exit-code"
    if completed.returncode != child_status:
        raise RuntimeError(
            f"systemd-run returned {completed.returncode}, expected {child_status}"
        )
    if properties.get("ExecMainStatus") != str(child_status):
        raise RuntimeError(
            f"systemd did not preserve the child's exact exit status: {properties!r}"
        )
    if properties.get("Result") != expected_result:
        raise RuntimeError(f"systemd result was not {expected_result}: {properties!r}")
    if launch_receipt.get("effective_exit_status") != child_status:
        raise RuntimeError("launch receipt disagrees with systemd")
    if launch_receipt.get("child_receipt_observed") is not True:
        raise RuntimeError("launch receipt did not authenticate child completion")
    return {
        "child_exit_status": child_status,
        "systemd_run_exit_status": completed.returncode,
        "systemd": properties,
        "launcher_receipt": launch_receipt,
    }


def main() -> int:
    """Run success and deliberate-failure transient units and emit a receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory(
        prefix="lfb-infisical-systemd-smoke-"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        masking_sandbox = temporary_root / "infisical-agent-sandbox"
        _write_masking_sandbox(masking_sandbox)
        cases = [
            _run_case(
                temporary_root=temporary_root,
                masking_sandbox=masking_sandbox,
                child_status=0,
            ),
            _run_case(
                temporary_root=temporary_root,
                masking_sandbox=masking_sandbox,
                child_status=23,
            ),
        ]

    payload = {
        "schema": "legalforecast.infisical_systemd_smoke.v1",
        "provider_calls": 0,
        "secret_reads": 0,
        "cases": cases,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
