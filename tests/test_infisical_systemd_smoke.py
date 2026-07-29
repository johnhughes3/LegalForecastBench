from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.smoke_infisical_systemd_exit_status import _path_with_prepend

ROOT = Path(__file__).parents[1]


def _user_systemd_is_available() -> bool:
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, PermissionError):
        return False
    return completed.returncode == 0


@pytest.mark.parametrize("error", [FileNotFoundError(), PermissionError()])
def test_user_systemd_probe_treats_unavailable_systemctl_as_absent(
    monkeypatch: pytest.MonkeyPatch,
    error: OSError,
) -> None:
    def unavailable(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        raise error

    monkeypatch.setattr(subprocess, "run", unavailable)

    assert _user_systemd_is_available() is False


@pytest.mark.parametrize(
    ("inherited_path", "expected_entries"),
    [
        (None, []),
        (f"{os.pathsep}/usr/bin", ["/usr/bin"]),
        (f"/usr/bin{os.pathsep}", ["/usr/bin"]),
        (
            f"/usr/bin{os.pathsep}{os.pathsep}/usr/local/bin",
            ["/usr/bin", "/usr/local/bin"],
        ),
    ],
)
def test_smoke_path_has_no_empty_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inherited_path: str | None,
    expected_entries: list[str],
) -> None:
    if inherited_path is None:
        monkeypatch.delenv("PATH", raising=False)
    else:
        monkeypatch.setenv("PATH", inherited_path)

    assert _path_with_prepend(tmp_path) == os.pathsep.join(
        [str(tmp_path), *expected_entries]
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
