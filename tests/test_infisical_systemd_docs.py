from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_acquisition_systemd_docs_require_status_and_receipt_gates() -> None:
    docs = (ROOT / "docs" / "acquisition-systemd-launcher.md").read_text(
        encoding="utf-8"
    )

    assert "legalforecast-acquisition-systemd-run" in docs
    assert "must not put `infisical-agent-sandbox run` directly in `ExecStart`" in docs
    assert "Result=success" in docs
    assert "ExecMainStatus=0" in docs
    assert "child_receipt_observed=true" in docs
    assert "effective_exit_status=0" in docs
    assert "sandbox_exit_status=0" in docs
    assert "exact dedicated sandbox paths" in docs
    assert (
        "Neither systemd status nor the Infisical wrapper status is sufficient" in docs
    )
    assert "status 23" in docs
    assert "zero provider calls" in docs
