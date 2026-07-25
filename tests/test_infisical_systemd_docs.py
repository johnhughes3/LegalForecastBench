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


def test_acquisition_systemd_docs_require_referenced_stage_views() -> None:
    launcher_docs = (ROOT / "docs" / "acquisition-systemd-launcher.md").read_text(
        encoding="utf-8"
    )
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")

    for expected in (
        "parser stage view must resolve exactly `MISTRAL_API_KEY`",
        "labeling stage view must resolve exactly `OPENAI_API_KEY`, "
        "`ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`",
        "dependent secret references",
        "canonical values under `/agents/sandbox/legalforecastbench-acquisition`",
        "read both the stage view and the referenced canonical secret",
        "Do not copy credential values",
        "Do not enable folder imports",
        "masked Infisical UI inventory is the authoritative exact-inventory check",
        "The sentinels are not a substitute for the complete masked UI inventory",
    ):
        assert expected in launcher_docs

    assert launcher_docs.count('env -i PATH="$PATH"') == 2
    assert "required=(MISTRAL_API_KEY)" in launcher_docs
    assert "required=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY)" in launcher_docs
    assert "forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY" in launcher_docs
    assert "forbidden=(MISTRAL_API_KEY CASE_DEV_API_KEY" in launcher_docs
    assert "${+parameters[$name]}" in launcher_docs
    assert "dependent secret reference" in runbook
    assert "acquisition-systemd-launcher.md" in runbook
    assert "authoritative masked Infisical UI inventory" in runbook
    assert "zsh -dfc" in runbook
    assert "forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY" in runbook
