#!/usr/bin/env python3
"""No-network fixture bridge for first-class external adapter examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_CAPABILITIES = "legalforecast.multiharness.adapter_capabilities.v1"
SCHEMA_RESULT = "legalforecast.multiharness.run_result.v1"

PROFILE_RECORDS: dict[str, dict[str, Any]] = {
    "lq-ai": {
        "adapter_id": "lq-ai-fixture-bridge",
        "display_name": "LQ.AI Fixture Bridge",
        "adapter_version": "0.1.0",
        "public_summary": {
            "external_harness": "LQ.AI",
            "fixture_bridge": True,
            "lq_ai_version": "fixture",
            "lq_ai_commit": "fixture",
            "gateway_api_route": "fixture://lq-ai/gateway",
            "project_or_matter_scope": "fixture matter",
            "inference_tier": "fixture",
            "provider_route": "fixture-provider",
            "anonymization_enabled": True,
            "citation_verification_enabled": True,
            "audit_log_correlation_id": "fixture-audit-lq-ai",
            "skill_playbook_context": "fixture legal forecasting playbook",
            "auth_mode": "api-key-by-user-environment",
            "provider_terms_assumption": "user supplied API access is permitted",
            "official_infrastructure_required": False,
            "artifact_safety": "public fixture summary only",
        },
    },
    "hermes-agent": {
        "adapter_id": "hermes-agent-fixture-bridge",
        "display_name": "Hermes Agent Fixture Bridge",
        "adapter_version": "0.1.0",
        "public_summary": {
            "external_harness": "Hermes Agent",
            "fixture_bridge": True,
            "hermes_version": "fixture",
            "hermes_commit": "fixture",
            "hermes_home_isolated": True,
            "hermes_profile": "fixture-profile",
            "provider_runtime_resolution": "fixture-provider/fixture-model",
            "enabled_toolsets": ["read", "write", "bash"],
            "terminal_backend": "fixture-terminal",
            "memory_session_policy": "reset-per-run",
            "mcp_configuration": "fixture-no-network",
            "trajectory_export_reference": "fixture://hermes/trajectory",
            "trajectory_export_sha256": "sha256:" + "3" * 64,
            "session_export_reference": "fixture://hermes/session",
            "session_export_sha256": "sha256:" + "4" * 64,
            "auth_mode": "api-key-by-user-environment",
            "provider_terms_assumption": "user supplied API access is permitted",
            "official_infrastructure_required": False,
            "artifact_safety": "public fixture summary only",
        },
    },
    "openclaw": {
        "adapter_id": "openclaw-fixture-bridge",
        "display_name": "OpenClaw Fixture Bridge",
        "adapter_version": "0.1.0",
        "public_summary": {
            "external_harness": "OpenClaw",
            "fixture_bridge": True,
            "openclaw_version": "fixture",
            "openclaw_commit": "fixture",
            "provider_model_route": "fixture-provider/fixture-model",
            "harness_id": "fixture-openclaw-harness",
            "runtime_plan_policy": "fixture-runtime-plan",
            "tool_policy": "fixture-read-write-bash",
            "transcript_mirror_behavior": "public summary only",
            "selected_native_runtime": "fixture-native-runtime",
            "fail_closed_when_harness_unavailable": True,
            "fail_closed_proof_reference": "fixture://openclaw/fail-closed",
            "auth_mode": "api-key-by-user-environment",
            "provider_terms_assumption": "user supplied API access is permitted",
            "official_infrastructure_required": False,
            "artifact_safety": "public fixture summary only",
        },
    },
    "openai-responses": {
        "adapter_id": "openai-responses-fixture-baseline",
        "display_name": "OpenAI Responses Fixture Baseline",
        "adapter_version": "0.1.0",
        "public_summary": {
            "external_harness": "OpenAI Responses",
            "provider_runtime_baseline": True,
            "fixture_bridge": True,
            "runtime_style": "responses-api",
            "agent_loop_style": "codex-style",
            "provider_route": "fixture-openai-responses",
            "model_route": "fixture-model",
            "auth_mode": "api-key-by-user-environment",
            "subscription_login_claimed": False,
            "provider_terms_assumption": "user supplied API access is permitted",
            "official_infrastructure_required": False,
            "artifact_safety": "public fixture summary only",
        },
    },
    "claude-agent-sdk": {
        "adapter_id": "claude-agent-sdk-fixture-baseline",
        "display_name": "Claude Agent SDK Fixture Baseline",
        "adapter_version": "0.1.0",
        "public_summary": {
            "external_harness": "Claude Agent SDK",
            "provider_runtime_baseline": True,
            "fixture_bridge": True,
            "runtime_style": "agent-sdk",
            "agent_loop_style": "tool-use-loop",
            "provider_route": "fixture-claude-agent-sdk",
            "model_route": "fixture-model",
            "auth_mode": "api-key-by-user-environment",
            "subscription_login_claimed": False,
            "provider_terms_assumption": "user supplied API access is permitted",
            "official_infrastructure_required": False,
            "artifact_safety": "public fixture summary only",
        },
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILE_RECORDS), required=True)
    subparsers = parser.add_subparsers(dest="phase", required=True)

    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("--output", type=Path, required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--workspace", type=Path, required=True)

    args = parser.parse_args(argv)
    profile = PROFILE_RECORDS[str(args.profile)]
    if args.phase == "capabilities":
        _write_json(
            args.output,
            {
                "schema_version": SCHEMA_CAPABILITIES,
                "adapter_id": profile["adapter_id"],
                "adapter_version": profile["adapter_version"],
                "supported_families": ["legalforecast_mtd", "harvey_lab"],
                "supported_scoring_modes": ["lfb_brier", "lab_native"],
                "supports_sandbox_policy": True,
                "capabilities_sha256": _record_sha256(
                    {
                        "adapter_id": profile["adapter_id"],
                        "adapter_version": profile["adapter_version"],
                        "profile": args.profile,
                    }
                ),
            },
        )
        return 0
    if args.phase == "run":
        request = _read_json(args.request)
        request_id = _required_str(request, "request_id")
        task = _required_mapping(request, "task")
        sandbox_policy = _required_mapping(request, "sandbox_policy")
        public_summary = dict(profile["public_summary"])
        public_summary.update(
            {
                "task_id": _required_str(task, "task_id"),
                "family": _required_str(task, "family"),
                "scoring_mode": _required_str(task, "scoring_mode"),
                "sandbox_policy_id": _required_str(sandbox_policy, "policy_id"),
            }
        )
        _write_json(
            args.output,
            {
                "schema_version": SCHEMA_RESULT,
                "result_id": f"{request_id}:result",
                "request_id": request_id,
                "status": "succeeded",
                "result_sha256": _record_sha256(public_summary),
                "artifacts": [],
                "public_summary": public_summary,
            },
        )
        return 0
    raise AssertionError(f"unhandled phase: {args.phase}")


def _read_json(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return record


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _required_mapping(record: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = record.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _required_str(record: dict[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _record_sha256(record: dict[str, Any]) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
