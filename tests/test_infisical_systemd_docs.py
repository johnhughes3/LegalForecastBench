from __future__ import annotations

import re
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
    assert (
        '/usr/bin/env -i PATH="$PATH" HOME="$HOME" USER="$USER" '
        'LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \\\n'
        "  uv run legalforecast-acquisition-systemd-run"
    ) in docs


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

    assert launcher_docs.count('env -i PATH="$PATH"') == 4
    assert "required=(MISTRAL_API_KEY)" in launcher_docs
    assert "required=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY)" in launcher_docs
    assert "forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY" in launcher_docs
    assert "forbidden=(MISTRAL_API_KEY CASE_DEV_API_KEY" in launcher_docs
    required_loop = (
        "for name in $required; do (( ${+parameters[$name]} )) && "
        '[[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }; done'
    )
    assert launcher_docs.count(required_loop) == 2
    assert required_loop in runbook
    assert "dependent secret reference" in runbook
    assert "acquisition-systemd-launcher.md" in runbook
    assert "authoritative masked Infisical UI inventory" in runbook
    assert "zsh -dfc" in runbook
    assert "forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY" in runbook


def test_acquisition_systemd_docs_require_exact_recap_fetch_client_view() -> None:
    launcher_docs = (ROOT / "docs" / "acquisition-systemd-launcher.md").read_text(
        encoding="utf-8"
    )
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    path = "/agents/sandbox/legalforecastbench/recap-fetch-broker-client"
    exact_names = (
        "RECAP_FETCH_BROKER_URL",
        "RECAP_FETCH_BROKER_MACHINE_ID",
        "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
    )

    launcher_view = launcher_docs.split(
        "The broker-client view is deliberately different", 1
    )[1].split("Downstream launchers must require", 1)[0]
    runbook_view = runbook.split("The broker client may run only through", 1)[1].split(
        "The purchase result is not parser- or packet-eligible", 1
    )[0]

    for broker_view in (launcher_view, runbook_view):
        assert path in broker_view
        assert set(
            re.findall(r"\bRECAP_FETCH_BROKER_[A-Z0-9_]+\b", broker_view)
        ) == set(exact_names)
        assert "PACER_USERNAME" in broker_view
        assert "PACER_PASSWORD" in broker_view
        assert "COURTLISTENER_API_TOKEN" in broker_view
        assert "dependent reference" in broker_view
        assert "folder import" in broker_view

    assert "ordinary secret values" in launcher_view
    assert "only after the reviewed broker activation" in launcher_view
    assert "never dependent references and never folder imports" in launcher_view
    assert 'print -- "$name=present"' in launcher_view
    assert "purchase-missing-recap-fetch" in runbook_view
    assert "must not use dependent references or folder imports" in runbook_view


def test_recap_fetch_transient_unit_is_isolated_and_inspected_before_cleanup() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    purchase_block = runbook.split("broker_launch_receipt=", 1)[1].split("```", 1)[0]
    empty_environment = (
        '/usr/bin/env -i PATH="$PATH" HOME="$HOME" USER="$USER" '
        'LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}"'
    )

    assert "--collect" not in purchase_block
    assert empty_environment in purchase_block
    assert "systemctl --user show" in purchase_block
    assert "--property=Result" in purchase_block
    assert "--property=ExecMainStatus" in purchase_block
    assert "--property=LoadState" in purchase_block
    assert "systemctl --user stop" in purchase_block
    assert "systemctl --user reset-failed" in purchase_block
    assert purchase_block.index("systemd-run") < purchase_block.index(
        "systemctl --user show"
    )
    assert purchase_block.index("systemctl --user show") < purchase_block.index(
        "systemctl --user stop"
    )
    assert purchase_block.index("systemctl --user stop") < purchase_block.index(
        "systemctl --user reset-failed"
    )
    assert purchase_block.index(
        "systemctl --user reset-failed"
    ) < purchase_block.rindex("systemctl --user show")
