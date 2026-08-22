from __future__ import annotations

import re
from pathlib import Path

import pytest
from legalforecast.ingestion.courtlistener_recap_fetch import (
    CourtListenerRecapFetchError,
    DirectCourtListenerRecapFetchConfig,
)
from legalforecast.ingestion.infisical_systemd_launcher import (
    _ALLOWED_SANDBOX_PATHS,
)

ROOT = Path(__file__).parents[1]

REQUIRED_LOOP = (
    "for name in $required; do (( ${+parameters[$name]} )) && "
    '[[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }; done'
)
FORBIDDEN_LOOP = (
    "for name in $forbidden; do (( ! ${+parameters[$name]} )) || "
    '{ print -u2 -- "$name=unexpected"; exit 1; }; done'
)


def _stage_sentinels(
    docs: str, path: str
) -> tuple[tuple[tuple[str, ...], tuple[str, ...], str, str], ...]:
    sentinels = []
    for stage_section in docs.split(f"--path {path}")[1:]:
        sentinel = stage_section.split('env -i PATH="$PATH"', 1)[0]
        arrays = re.search(
            r"required=\((?P<required>[^)]*)\)\n"
            r"    forbidden=\((?P<forbidden>[^)]*)\)",
            sentinel,
        )
        loops = re.search(
            r"    (?P<required_loop>for name in \$required;[^\n]+?; done)\n"
            r"    (?P<forbidden_loop>for name in \$forbidden;[^\n]+?; done)",
            sentinel,
        )
        if arrays is None and loops is None:
            continue
        assert arrays is not None
        assert loops is not None
        sentinels.append(
            (
                tuple(arrays.group("required").split()),
                tuple(arrays.group("forbidden").split()),
                loops.group("required_loop"),
                loops.group("forbidden_loop"),
            )
        )
    return tuple(sentinels)


def _stage_sentinel(
    docs: str, path: str
) -> tuple[tuple[str, ...], tuple[str, ...], str, str]:
    sentinels = _stage_sentinels(docs, path)
    assert len(sentinels) == 1
    return sentinels[0]


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


def _provider_layout_rows(
    docs: str,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    table = docs.split(
        "| Source role | Exact path | Exact names | Checked-in consumers |", 1
    )[1]
    rows = []
    for match in re.finditer(
        r"^\| (?P<role>[^|]+) \| `(?P<path>[^`]+)` \| (?P<names>[^|]+) \|",
        table,
        flags=re.MULTILINE,
    ):
        rows.append(
            (
                match.group("role"),
                match.group("path"),
                tuple(re.findall(r"`([A-Z0-9_]+)`", match.group("names"))),
            )
        )
    return tuple(rows)


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
        (
            "The parser, labeling, and broker-client sentinels are not a substitute "
            "for their complete masked UI inventories"
        ),
    ):
        assert expected in launcher_docs
    assert "/agents/sandbox/**" not in launcher_docs
    assert "dependent-secret parser and labeling views" in launcher_docs

    assert launcher_docs.count('env -i PATH="$PATH"') == 6
    acquisition_forbidden = (
        "RECAP_FETCH_BROKER_URL",
        "RECAP_FETCH_BROKER_MACHINE_ID",
        "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
    )
    assert _stage_sentinels(
        launcher_docs, "/agents/sandbox/legalforecastbench/acquisition"
    ) == (
        (
            ("COURTLISTENER_API_TOKEN", "PACER_USERNAME", "PACER_PASSWORD"),
            acquisition_forbidden,
            REQUIRED_LOOP,
            FORBIDDEN_LOOP,
        ),
        (
            ("COURTLISTENER_API_TOKEN", "PACER_USERNAME", "PACER_PASSWORD"),
            acquisition_forbidden,
            REQUIRED_LOOP,
            FORBIDDEN_LOOP,
        ),
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
    assert (
        "Direct unknown-outcome recovery uses the same three direct-purchase "
        "credentials" in docs
    )
    assert "token-only" not in docs
    assert "optional broker transport" in docs
    assert "does not weaken or replace" in docs
    assert "transport-specific preflights are not exact-inventory" in docs
    assert "other acquisition-stage credentials" in docs
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


def test_acquisition_systemd_docs_record_source_owned_provider_layout() -> None:
    docs = (ROOT / "docs" / "acquisition-systemd-launcher.md").read_text(
        encoding="utf-8"
    )

    assert "## Provider-placement reconciliation" in docs
    assert "viewSecretValue=false" in docs
    expected_rows = (
        (
            "Acquisition stage",
            "/agents/sandbox/legalforecastbench/acquisition",
            (
                "ANTHROPIC_API_KEY",
                "CASE_DEV_API_KEY",
                "COURTLISTENER_API_TOKEN",
                "FIRECRAWL_API_KEY",
                "GEMINI_API_KEY",
                "MISTRAL_API_KEY",
                "OPENAI_API_KEY",
                "PACER_PASSWORD",
                "PACER_USERNAME",
            ),
        ),
        (
            "Parser view",
            "/agents/sandbox/legalforecastbench/parser",
            ("MISTRAL_API_KEY",),
        ),
        (
            "Labeling view",
            "/agents/sandbox/legalforecastbench/labeling",
            ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"),
        ),
        (
            "Optional broker-client view",
            "/agents/sandbox/legalforecastbench/recap-fetch-broker-client",
            (
                "RECAP_FETCH_BROKER_URL",
                "RECAP_FETCH_BROKER_MACHINE_ID",
                "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK",
                "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON",
                "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256",
            ),
        ),
    )
    assert _provider_layout_rows(docs) == expected_rows
    assert set(_ALLOWED_SANDBOX_PATHS) == {row[1] for row in expected_rows}
    assert "/agents/sandbox/legalforecastbench-acquisition" not in docs
    assert "/agents/sandbox/legalforecastbench/acquisition/case-dev" not in docs
    assert "/agents/sandbox/legalforecastbench/acquisition/courtlistener" not in docs
    assert "/agents/sandbox/legalforecastbench/acquisition/firecrawl" not in docs
    assert "provider-reconciliation blocker" not in docs
    assert "token-only" not in docs
    assert "MISTRAL_API_KEY" in docs
    assert "OPENAI_API_KEY" in docs
    assert "ANTHROPIC_API_KEY" in docs
    assert "GEMINI_API_KEY" in docs
    assert "create, move, copy, rotate, or delete" in docs
    assert not re.search(r"(?:secret_value|secretValue)\s*[:=]", docs)


def test_direct_purchase_runtime_requires_token_and_both_pacer_credentials() -> None:
    with pytest.raises(
        CourtListenerRecapFetchError,
        match="PACER_USERNAME, PACER_PASSWORD",
    ):
        DirectCourtListenerRecapFetchConfig.from_env(
            {"COURTLISTENER_API_TOKEN": "token"}
        )
    with pytest.raises(CourtListenerRecapFetchError, match="PACER_PASSWORD"):
        DirectCourtListenerRecapFetchConfig.from_env(
            {
                "COURTLISTENER_API_TOKEN": "token",
                "PACER_USERNAME": "user",
            }
        )


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
