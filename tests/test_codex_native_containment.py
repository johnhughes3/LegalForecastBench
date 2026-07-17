from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from scripts.probe_codex_native_containment import (
    containment_blocking_gaps,
    normalize_systemd_preflight,
    systemd_preflight_is_effective,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "codex_native_containment"
    / "codex-native-containment-0.144.5.json"
)
PROBE = ROOT / "scripts" / "probe_codex_native_containment.py"
EXPECTED_SHA256 = "058d616bde049c0648b72d53a22a54bf428eeb3f10e76cb4d6d4d4f81b764600"
REQUIRED_NATIVE_CAPABILITIES = {
    "edit",
    "filesystem_read",
    "filesystem_write",
    "search",
    "shell",
}


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_committed_probe_records_exact_binary_and_zero_provider_spend() -> None:
    evidence = _fixture()

    assert evidence["schema_version"] == (
        "legalforecast.codex_native_containment_probe.v1"
    )
    assert evidence["binary"] == {
        "executable": "codex-x86_64-unknown-linux-musl",
        "sha256": EXPECTED_SHA256,
        "version": "codex-cli 0.144.5",
    }
    assert evidence["spend"]["benchmark_task_bytes"] == 0
    assert evidence["spend"]["provider_requests"] == 0
    assert evidence["spend"]["local_stub_requests"] >= 4


def test_committed_probe_records_native_inventory_and_deliberate_disables() -> None:
    evidence = _fixture()
    profile = evidence["profile"]

    assert profile["candidate_profile"] == "codex-cli-clean-native"
    assert profile["effective_profile"] == "codex-cli-local-stub-native-loop-only"
    assert profile["literal_out_of_box_claim_allowed"] is False
    assert profile["task_mcp_servers"] == []
    assert profile["foreign_mcp_primary_loop"] is False
    assert set(profile["disabled_stock_capabilities"]) >= {
        "apps and connectors",
        "browser and computer use",
        "hooks",
        "image generation",
        "live web search",
        "memories",
        "plugins",
        "remote control",
    }

    inventory = evidence["native_tool_inventory"]
    assert REQUIRED_NATIVE_CAPABILITIES <= set(inventory["required_capabilities"])
    assert inventory["advertised_tool_names"]
    assert inventory["shell_tool"] in inventory["advertised_tool_names"]
    assert inventory["edit_tool"] in inventory["advertised_tool_names"]
    assert inventory["foreign_mcp_tool_names"] == []
    assert inventory["native_delegation"]["status"] in {"absent", "present"}


def test_committed_probe_runs_native_tools_output_and_all_canaries() -> None:
    evidence = _fixture()

    assert set(evidence["tool_probes"]) == REQUIRED_NATIVE_CAPABILITIES
    assert all(evidence["tool_probes"].values())
    assert evidence["deliverable"] == {
        "content": "FINAL NATIVE_BOUNDARY_OK\n",
        "path": "/workspace/deliverable.txt",
        "sealed_sha256": hashlib.sha256(b"FINAL NATIVE_BOUNDARY_OK\n").hexdigest(),
    }

    canaries = evidence["canaries"]
    assert set(canaries) == {
        "ambient_config_loaded",
        "ambient_mcp_loaded",
        "ambient_project_instructions_loaded",
        "ambient_rules_loaded",
        "ambient_skills_loaded",
        "credential_child_inherited",
        "evaluator_private_bytes_visible",
        "external_network_reachable",
        "host_auth_visible",
        "host_home_visible",
        "host_repository_visible",
    }
    assert canaries["ambient_config_loaded"] is False
    assert canaries["ambient_mcp_loaded"] is False
    assert canaries["ambient_project_instructions_loaded"] is False
    assert canaries["ambient_rules_loaded"] is False
    assert canaries["ambient_skills_loaded"] is False
    if canaries["credential_child_inherited"]:
        assert (
            "credential canary inherited by child command"
            in evidence["claim_decision"]["blocking_gaps"]
        )
    assert set(evidence["child_environment_names"]) >= {"HOME", "PATH"}


def test_probe_fails_closed_when_native_sandbox_and_outer_boundary_are_absent() -> None:
    evidence = _fixture()
    sandbox = evidence["native_sandbox"]
    boundary = evidence["outer_boundary"]
    decision = evidence["claim_decision"]

    assert sandbox["requested"] == "workspace-write"
    assert sandbox["implementation"] == "bubblewrap"
    assert sandbox["active_for_required_tool_probe"] is False
    assert sandbox["probe_exit_code"] != 0
    assert "Operation not permitted" in sandbox["probe_error"]

    assert boundary["workspace_disposable"] is True
    assert boundary["kind"] == "none-applied-to-codex-parent"
    assert boundary["whole_process_boundary_applied"] is False
    assert boundary["provider_endpoint_loopback_only"] is True
    assert boundary["host_filesystem_isolated"] is False
    assert boundary["external_network_isolated"] is False
    assert boundary["process_cleanup_probe_started"] is True
    assert boundary["process_cleanup_verified"] in {False, True}
    systemd_preflight = boundary["systemd_user_preflight"]
    assert systemd_preflight["command_exit_code"] != 0
    assert systemd_preflight["service_exit_status"] == "226/NAMESPACE"
    assert systemd_preflight["failure_class"] == "namespace-setup-failed"
    assert systemd_preflight["mount_namespace_effective"] is False
    assert systemd_preflight["network_namespace_different_from_host"] is False
    assert systemd_preflight["effective"] is False
    assert systemd_preflight["fallback_warnings"] == [
        "nonzero systemd boundary preflight"
    ]

    assert decision["status"] == "rejected"
    assert decision["clean_native_claim_allowed"] is False
    assert decision["effective_profile"] == profile_id(evidence)
    assert set(decision["blocking_gaps"]) >= {
        "native workspace-write sandbox unavailable",
        "no enforced whole-process filesystem boundary",
        "no enforced whole-process network boundary",
    }


@pytest.mark.parametrize(
    "warning",
    [
        "Failed to set up mount namespacing",
        "Operation not supported",
        "proceeding without",
    ],
)
def test_requested_systemd_properties_never_override_fallback_evidence(
    warning: str,
) -> None:
    requested_only: dict[str, object] = {
        "command_exit_code": 0,
        "service_exit_status": "0/SUCCESS",
        "mount_namespace_effective": True,
        "network_namespace_different_from_host": True,
        "fallback_warnings": [warning],
        "requested_properties": [
            "PrivateNetwork=yes",
            "RootDirectory=disposable",
        ],
    }

    assert systemd_preflight_is_effective(requested_only) is False


def test_nonzero_systemd_preflight_normalizes_racy_journal_evidence() -> None:
    without_journal = normalize_systemd_preflight(
        command_exit_code=226,
        command_output="",
        journal_output=None,
        host_network_namespace="net:[1]",
    )
    with_journal = normalize_systemd_preflight(
        command_exit_code=226,
        command_output="Running as unit: volatile.service",
        journal_output=(
            "Failed to set up mount namespacing: Operation not supported; "
            "proceeding without"
        ),
        host_network_namespace="net:[1]",
    )

    assert with_journal == without_journal
    assert without_journal == {
        "command_exit_code": 226,
        "service_exit_status": "226/NAMESPACE",
        "failure_class": "namespace-setup-failed",
        "mount_namespace_effective": False,
        "network_namespace_different_from_host": False,
        "fallback_warnings": ["nonzero systemd boundary preflight"],
    }


def test_native_sandbox_success_cannot_substitute_for_parent_boundary() -> None:
    gaps = containment_blocking_gaps(
        native_sandbox_active=True,
        whole_process_boundary_applied=False,
        host_filesystem_isolated=True,
        external_network_isolated=True,
        credential_child_inherited=False,
        foreign_mcp_tool_names=[],
        ambient_surface_loaded=False,
    )

    assert gaps == [
        "no enforced whole-process filesystem boundary",
        "no enforced whole-process network boundary",
    ]


def profile_id(evidence: dict[str, Any]) -> str:
    return str(evidence["profile"]["effective_profile"])


def test_probe_cli_help_is_credential_free() -> None:
    result = subprocess.run(
        [str(PROBE), "--help"],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert "--codex-binary" in result.stdout
    assert "--expected-sha256" in result.stdout
    assert "--output" in result.stdout
    assert "--provider" not in result.stdout


def test_opt_in_probe_matches_committed_evidence() -> None:
    result_path = os.environ.get("CODEX_NATIVE_CONTAINMENT_PROBE_RESULT")
    if result_path is None:
        pytest.skip(
            "set CODEX_NATIVE_CONTAINMENT_PROBE_RESULT to replay fresh evidence"
        )

    observed = json.loads(Path(result_path).read_text(encoding="utf-8"))
    assert observed == _fixture()
