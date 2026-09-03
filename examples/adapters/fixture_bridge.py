#!/usr/bin/env python3
"""No-network fixture bridge for first-class external adapter examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

SCHEMA_CAPABILITIES = "legalforecast.multiharness.adapter_capabilities.v1"
SCHEMA_RESULT = "legalforecast.multiharness.run_result.v1"
SCHEMA_TOOL_REQUEST = "legalforecast.multiharness.tool_request.v1"
SCHEMA_TOOL_RESPONSE = "legalforecast.multiharness.tool_response.v1"

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

    run_with_tools = subparsers.add_parser("run-with-tools")
    run_with_tools.add_argument("--request", type=Path, required=True)
    run_with_tools.add_argument("--output", type=Path, required=True)
    run_with_tools.add_argument("--workspace", type=Path, required=True)

    args = parser.parse_args(argv)
    profile = PROFILE_RECORDS[str(args.profile)]
    if args.phase == "capabilities":
        tool_protocol_version = (
            SCHEMA_TOOL_REQUEST if args.profile == "openai-responses" else None
        )
        capability_semantics: dict[str, Any] = {
            "adapter_id": profile["adapter_id"],
            "adapter_version": profile["adapter_version"],
            "supported_families": ["legalforecast_mtd", "harvey_lab"],
            "supported_scoring_modes": ["lfb_brier", "lab_native"],
            "supports_sandbox_policy": True,
            "profile": args.profile,
            "tool_protocol_version": tool_protocol_version,
        }
        record: dict[str, Any] = {
            "schema_version": SCHEMA_CAPABILITIES,
            "adapter_id": capability_semantics["adapter_id"],
            "adapter_version": capability_semantics["adapter_version"],
            "supported_families": capability_semantics["supported_families"],
            "supported_scoring_modes": capability_semantics["supported_scoring_modes"],
            "supports_sandbox_policy": capability_semantics["supports_sandbox_policy"],
            "capabilities_sha256": _record_sha256(capability_semantics),
        }
        if tool_protocol_version is not None:
            record["tool_protocol_version"] = tool_protocol_version
        _write_json(args.output, record)
        return 0
    if args.phase in {"run", "run-with-tools"}:
        request = _read_json(args.request)
        request_id = _required_str(request, "request_id")
        task = _required_mapping(request, "task")
        sandbox_policy = _required_mapping(request, "sandbox_policy")
        if args.phase == "run" and _is_release_task(task):
            _write_release_fixture_result(
                request=request,
                task=task,
                profile=profile,
                sandbox_policy=sandbox_policy,
                workspace=args.workspace,
                output=args.output,
            )
            return 0
        public_summary = dict(profile["public_summary"])
        public_summary.update(
            {
                "task_id": _required_str(task, "task_id"),
                "family": _required_str(task, "family"),
                "scoring_mode": _required_str(task, "scoring_mode"),
                "sandbox_policy_id": _required_str(sandbox_policy, "policy_id"),
            }
        )
        if args.phase == "run-with-tools":
            if args.profile != "openai-responses":
                raise ValueError("live tools are supported only by openai-responses")
            tool_request = {
                "schema_version": SCHEMA_TOOL_REQUEST,
                "request_id": f"{request_id}:read-task",
                "operation": "read_text",
                "arguments": {"encoding": "utf-8"},
                "input_paths": ["task.json"],
            }
            sys.stdout.write(
                json.dumps(tool_request, sort_keys=True, separators=(",", ":")) + "\n"
            )
            sys.stdout.flush()
            decoded_response = cast(object, json.loads(sys.stdin.readline()))
            if not isinstance(decoded_response, dict):
                raise ValueError("tool response must be a JSON object")
            response = cast(dict[str, Any], decoded_response)
            if response.get("schema_version") != SCHEMA_TOOL_RESPONSE:
                raise ValueError("tool response schema does not match")
            if response.get("request_id") != tool_request["request_id"]:
                raise ValueError("tool response request_id does not match")
            if response.get("status") != "succeeded":
                raise ValueError("tool request failed")
            public_summary["tool_response_sha256"] = _record_sha256(response)
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


def _is_release_task(task: Mapping[str, Any]) -> bool:
    metadata = task.get("metadata")
    return (
        isinstance(metadata, dict)
        and metadata.get("release_schema_version")
        == "legalforecast.forecast-release.v1"
    )


def _write_release_fixture_result(
    *,
    request: Mapping[str, Any],
    task: Mapping[str, Any],
    profile: Mapping[str, Any],
    sandbox_policy: Mapping[str, Any],
    workspace: Path,
    output: Path,
) -> None:
    from legalforecast.multiharness.release_harness import (
        RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
        RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
        read_release_regular_file,
        release_bytes_sha256,
        release_canonical_bytes,
        release_record_sha256,
        write_release_create_only,
    )
    from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
    from legalforecast.multiharness.validation import validate_public_record

    request_id = _required_str(request, "request_id")
    metadata = _required_mapping(task, "metadata")
    prompt = read_release_regular_file(workspace / SOLVER_INPUT_ENTRY_PATH)
    prompt_sha256 = release_bytes_sha256(prompt)
    if prompt_sha256 != metadata.get("prompt_sha256"):
        raise ValueError("fixture prompt commitment does not match")
    required_unit_ids = _required_unit_ids(metadata)
    forecast = {
        "case_assessment": "Community fixture forecast; not a model quality claim.",
        "predictions": [
            {"unit_id": unit_id, "probability_fully_dismissed": 0.5}
            for unit_id in required_unit_ids
        ],
    }
    output_bytes = json.dumps(forecast, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    private_logs = workspace / "private-logs"
    private_logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_release_create_only(
        private_logs / "release-forecast-output.json",
        output_bytes,
        mode=0o600,
    )
    output_sha256 = release_bytes_sha256(output_bytes)
    transcript_bytes = release_canonical_bytes(
        {
            "request_sha256": _required_str(request, "request_sha256"),
            "prompt_sha256": prompt_sha256,
            "packet_sha256": _required_str(task, "task_sha256"),
            "response_sha256": output_sha256,
        }
    )
    write_release_create_only(
        private_logs / "neutral-api-transcript.json",
        transcript_bytes,
        mode=0o600,
    )
    transcript_sha256 = release_bytes_sha256(transcript_bytes)
    public_summary = dict(profile["public_summary"])
    public_summary.update(
        {
            "adapter_id": profile["adapter_id"],
            "adapter_version": profile["adapter_version"],
            "allowed_tools": [],
            "estimated_cost": 0.0,
            "execution_backend": "community_fixture_bridge",
            "family": _required_str(task, "family"),
            "harness_track": "neutral",
            "input_tokens": 0,
            "model_key": _required_str(request, "model_key"),
            "output_tokens": 0,
            "provider_request_count": 0,
            "sandbox_policy_id": _required_str(sandbox_policy, "policy_id"),
            "scoring_mode": _required_str(task, "scoring_mode"),
            "task_id": _required_str(task, "task_id"),
            "tool_call_count": 0,
            "tool_policy": "none",
            "transcript_sha256": transcript_sha256,
        }
    )
    validate_public_record(public_summary, "community fixture release summary")
    artifacts = [
        {
            "artifact_id": RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
            "path": "private-logs/release-forecast-output.json",
            "sha256": output_sha256,
            "media_type": "application/json",
            "public": False,
            "size_bytes": len(output_bytes),
        },
        {
            "artifact_id": RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
            "path": "private-logs/neutral-api-transcript.json",
            "sha256": transcript_sha256,
            "media_type": "application/json",
            "public": False,
            "size_bytes": len(transcript_bytes),
        },
    ]
    commitment = {
        "request_sha256": _required_str(request, "request_sha256"),
        "output_sha256": output_sha256,
        "summary": public_summary,
    }
    _write_json(
        output,
        {
            "schema_version": SCHEMA_RESULT,
            "result_id": f"{request_id}:{profile['adapter_id']}",
            "request_id": request_id,
            "status": "succeeded",
            "result_sha256": release_record_sha256(commitment),
            "artifacts": artifacts,
            "public_summary": public_summary,
        },
    )


def _required_unit_ids(metadata: Mapping[str, Any]) -> list[str]:
    values = metadata.get("required_unit_ids")
    if not isinstance(values, list) or not values:
        raise ValueError("release task required_unit_ids is invalid")
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError("release task required_unit_ids is invalid")
    return [item for item in values if isinstance(item, str)]


def _read_json(path: Path) -> dict[str, Any]:
    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], decoded)


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
    return cast(dict[str, Any], value)


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
