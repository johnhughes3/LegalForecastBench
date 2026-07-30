from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from scripts.probe_codex_cli_interface import (
    CharacterizationDriftError,
    assert_matches_fixture,
    build_safe_parser_probe,
    parse_feature_rows,
    parse_long_flags,
    parse_subcommands,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "codex_cli_characterization"
    / "codex-cli-interface-0.146.0.json"
)
DOC = ROOT / "docs" / "adapters" / "codex-cli-characterization.md"
EXPECTED_SHA256 = "2e863156ed35ecc5253b1e2f907a9143077b9f7cb51942070c61996471ff6e04"


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_committed_characterization_pins_binary_distribution_and_zero_spend() -> None:
    evidence = _fixture()

    assert evidence["schema_version"] == (
        "legalforecast.codex_cli_interface_characterization.v1"
    )
    assert evidence["binary"] == {
        "distribution": {
            "kind": "homebrew-cask",
            "package": "codex",
            "version": "0.146.0",
        },
        "executable": "codex-x86_64-unknown-linux-musl",
        "sha256": EXPECTED_SHA256,
        "version": "codex-cli 0.146.0",
    }
    assert evidence["safety"] == {
        "auth_state_inspected_or_copied": False,
        "benchmark_task_bytes": 0,
        "model_or_provider_requests": 0,
        "probe_kind": "version-help-feature-interface-only",
    }


def test_characterization_pins_required_noninteractive_controls() -> None:
    evidence = _fixture()
    interface = evidence["interface"]

    assert "exec" in interface["root_subcommands"]
    assert set(interface["required_exec_flags"]) == {
        "--cd",
        "--ephemeral",
        "--ignore-rules",
        "--ignore-user-config",
        "--json",
        "--model",
        "--sandbox",
        "--strict-config",
    }
    assert set(interface["sandbox_modes"]) == {
        "danger-full-access",
        "read-only",
        "workspace-write",
    }
    assert interface["parser_probe"]["help_only"] is True
    assert interface["parser_probe"]["provider_request_possible"] is False


def test_identity_is_distinct_and_unverified_activation_is_blocked() -> None:
    evidence = _fixture()

    assert evidence["identity"] == {
        "adapter_profile": "codex-cli-clean-native",
        "foreign_mcp_primary_loop": False,
        "openai_responses_adapter": False,
    }
    assert evidence["model"] == {
        "requested": "gpt-5.1",
        "resolved": None,
        "resolved_verification": "requires a separately approved model request",
    }
    assert evidence["tools"]["native_model_tool_inventory"] is None
    assert evidence["tools"]["observed_without_model_request"] is False
    assert evidence["activation"]["allowed"] is False
    assert set(evidence["activation"]["blocking_gaps"]) == {
        "native model tool inventory not observed for this binary",
        "resolved model not observed for this binary",
    }


def test_documentation_preserves_the_non_spending_claim_boundary() -> None:
    documentation = DOC.read_text(encoding="utf-8")

    assert "`codex-cli 0.146.0`" in documentation
    assert EXPECTED_SHA256 in documentation
    assert "does not prove JSONL event semantics" in documentation
    assert "does not supersede" in documentation
    assert "OpenAI Responses adapter" in documentation
    assert "Activation remains blocked" in documentation


def test_help_parsers_extract_only_public_interface_data() -> None:
    help_text = """Commands:
  exec       Run non-interactively
  login      Manage login

Options:
  -m, --model <MODEL>
      --json
"""
    feature_text = """shell_tool  stable             true
multi_agent stable             false
"""

    assert parse_subcommands(help_text) == ["exec", "login"]
    assert parse_long_flags(help_text) == ["--json", "--model"]
    assert parse_feature_rows(feature_text) == {
        "multi_agent": {"stage": "stable", "enabled": False},
        "shell_tool": {"stage": "stable", "enabled": True},
    }


def test_safe_parser_probe_uses_help_and_all_required_controls(tmp_path: Path) -> None:
    command = build_safe_parser_probe(
        executable=Path("/opt/codex"),
        expected_model="gpt-5.1",
        workspace=tmp_path,
    )

    assert command == [
        "/opt/codex",
        "exec",
        "--json",
        "--ephemeral",
        "--model",
        "gpt-5.1",
        "--cd",
        str(tmp_path),
        "--sandbox",
        "read-only",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "--help",
    ]
    assert "login" not in command
    assert "doctor" not in command


def test_fixture_comparison_fails_closed_on_binary_interface_or_model_drift() -> None:
    expected = _fixture()
    for path, drifted_value in (
        (("binary", "sha256"), "0" * 64),
        (("interface", "exec_help_sha256"), "1" * 64),
        (("model", "requested"), "different-model"),
    ):
        observed = json.loads(json.dumps(expected))
        target = observed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = drifted_value

        with pytest.raises(CharacterizationDriftError, match="drift"):
            assert_matches_fixture(observed, expected)
