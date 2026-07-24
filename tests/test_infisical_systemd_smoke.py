from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _user_systemd_is_available() -> bool:
    return (
        subprocess.run(
            ["systemctl", "--user", "show-environment"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


@pytest.mark.skipif(
    not _user_systemd_is_available(),
    reason="a user systemd manager is required for the operational smoke",
)
def test_provider_free_systemd_smoke_proves_success_and_exact_failure(
    tmp_path: Path,
) -> None:
    output = tmp_path / "smoke-receipt.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "smoke_infisical_systemd_exit_status.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["provider_calls"] == 0
    assert receipt["secret_reads"] == 0
    success, failure = receipt["cases"]
    assert success["child_exit_status"] == 0
    assert success["systemd"]["Result"] == "success"
    assert success["systemd"]["ExecMainStatus"] == "0"
    assert failure["child_exit_status"] == 23
    assert failure["systemd"]["Result"] == "exit-code"
    assert failure["systemd"]["ExecMainStatus"] == "23"
