from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]

REQUIRED_LOOP = (
    "for name in $required; do (( ${+parameters[$name]} )) && "
    '[[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }; done'
)
FORBIDDEN_LOOP = (
    "for name in $forbidden; do (( ! ${+parameters[$name]} )) || "
    '{ print -u2 -- "$name=unexpected"; exit 1; }; done'
)


def _stage_sentinel(
    docs: str, path: str
) -> tuple[tuple[str, ...], tuple[str, ...], str, str]:
    stage_section = docs.split(f"--path {path}", 1)[1]
    arrays = re.search(
        r"required=\((?P<required>[^)]*)\)\n"
        r"    forbidden=\((?P<forbidden>[^)]*)\)",
        stage_section,
    )
    loops = re.search(
        r"    (?P<required_loop>for name in \$required;[^\n]+?; done)\n"
        r"    (?P<forbidden_loop>for name in \$forbidden;[^\n]+?; done)",
        stage_section,
    )
    assert arrays is not None
    assert loops is not None
    return (
        tuple(arrays.group("required").split()),
        tuple(arrays.group("forbidden").split()),
        loops.group("required_loop"),
        loops.group("forbidden_loop"),
    )


def _stage_key_arrays(docs: str, path: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    stage_section = docs.split(f"--path {path}", 1)[1]
    match = re.search(
        r"required=\((?P<required>[^)]*)\)\n"
        r"    forbidden=\((?P<forbidden>[^)]*)\)",
        stage_section,
    )
    assert match is not None
    return (
        tuple(match.group("required").split()),
        tuple(match.group("forbidden").split()),
    )


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
    labeling_keys = "`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`"

    for expected in (
        "parser stage view must resolve exactly `MISTRAL_API_KEY`",
        f"labeling stage view must resolve exactly {labeling_keys}",
        "dependent-secret references",
        "canonical values under `/agents/sandbox/legalforecastbench/acquisition`",
        (
            "read both the exact stage view and the canonical "
            "`/agents/sandbox/legalforecastbench/acquisition` source path"
        ),
        "Scope the identity's grants to those two paths only",
        "must not read a sibling sandbox or another LegalForecastBench stage path",
        "Do not copy credential values",
        "Do not enable folder imports",
        "masked Infisical UI inventory is the authoritative exact-inventory check",
        "The sentinels are not a substitute for the complete masked UI inventory",
    ):
        assert expected in launcher_docs
    assert "/agents/sandbox/**" not in launcher_docs
    assert "dependent-secret parser and labeling views" in launcher_docs

    assert launcher_docs.count('env -i PATH="$PATH"') == 5
    assert _stage_sentinel(
        launcher_docs, "/agents/sandbox/legalforecastbench/acquisition"
    ) == (
        ("COURTLISTENER_API_TOKEN", "PACER_USERNAME", "PACER_PASSWORD"),
        (
            "RECAP_FETCH_BROKER_URL",
            "RECAP_FETCH_BROKER_MACHINE_ID",
            "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
            "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
            "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
            "MISTRAL_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
        ),
        REQUIRED_LOOP,
        FORBIDDEN_LOOP,
    )
    parser_sentinel = _stage_sentinel(
        launcher_docs, "/agents/sandbox/legalforecastbench/parser"
    )
    assert parser_sentinel == (
        ("MISTRAL_API_KEY",),
        (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "CASE_DEV_API_KEY",
            "COURTLISTENER_API_TOKEN",
            "RECAP_API_TOKEN",
            "FIRECRAWL_API_KEY",
            "PACER_USERNAME",
            "PACER_PASSWORD",
        ),
        REQUIRED_LOOP,
        FORBIDDEN_LOOP,
    )
    assert _stage_sentinel(
        launcher_docs, "/agents/sandbox/legalforecastbench/labeling"
    ) == (
        ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"),
        (
            "MISTRAL_API_KEY",
            "CASE_DEV_API_KEY",
            "COURTLISTENER_API_TOKEN",
            "RECAP_API_TOKEN",
            "FIRECRAWL_API_KEY",
            "PACER_USERNAME",
            "PACER_PASSWORD",
        ),
        REQUIRED_LOOP,
        FORBIDDEN_LOOP,
    )
    assert (
        _stage_sentinel(runbook, "/agents/sandbox/legalforecastbench/parser")
        == parser_sentinel
    )
    assert _stage_key_arrays(
        launcher_docs, "/agents/sandbox/legalforecastbench/recap-fetch-broker-client"
    ) == (
        (
            "RECAP_FETCH_BROKER_URL",
            "RECAP_FETCH_BROKER_MACHINE_ID",
            "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
            "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
            "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
        ),
        (
            "PACER_USERNAME",
            "PACER_PASSWORD",
            "COURTLISTENER_API_TOKEN",
            "RECAP_API_TOKEN",
            "CASE_DEV_API_KEY",
            "FIRECRAWL_API_KEY",
            "MISTRAL_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
        ),
    )
    assert "dependent-secret reference" in runbook
    assert "acquisition-systemd-launcher.md" in runbook
    assert "authoritative masked Infisical UI inventory" in runbook
    assert "zsh -dfc" in runbook


def test_acquisition_systemd_docs_make_direct_target100_purchase_canonical() -> None:
    docs = (ROOT / "docs" / "acquisition-systemd-launcher.md").read_text(
        encoding="utf-8"
    )

    assert "canonical checked-in target-100 path" in docs
    assert "`--direct-courtlistener-purchase`" in docs
    assert "Direct recovery requires only `COURTLISTENER_API_TOKEN`" in docs
    assert "optional broker transport" in docs
    assert "does not weaken or replace" in docs
    assert "Paid RECAP Fetch uses only" not in docs


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
