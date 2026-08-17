from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from legalforecast.multiharness.claude_agent_sdk import (
    adapter_bundle_sha256 as claude_adapter_bundle_sha256,
)
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.conformance import run_adapter_conformance
from legalforecast.multiharness.openai_responses import (
    adapter_bundle_sha256 as openai_adapter_bundle_sha256,
)
from legalforecast.multiharness.spec import TOOL_REQUEST_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
LQ_AI_MANIFEST = ROOT / "examples" / "adapters" / "lq-ai" / "adapter-manifest.json"
HERMES_MANIFEST = (
    ROOT / "examples" / "adapters" / "hermes-agent" / "adapter-manifest.json"
)
OPENCLAW_MANIFEST = (
    ROOT / "examples" / "adapters" / "openclaw" / "adapter-manifest.json"
)
OPENAI_RESPONSES_MANIFEST = (
    ROOT / "examples" / "adapters" / "openai-responses" / "adapter-manifest.json"
)
OPENAI_RESPONSES_FIXTURE_MANIFEST = (
    ROOT
    / "examples"
    / "adapters"
    / "openai-responses"
    / "fixture-adapter-manifest.json"
)
CLAUDE_AGENT_SDK_MANIFEST = (
    ROOT / "examples" / "adapters" / "claude-agent-sdk" / "adapter-manifest.json"
)
CLAUDE_AGENT_SDK_FIXTURE_MANIFEST = (
    ROOT
    / "examples"
    / "adapters"
    / "claude-agent-sdk"
    / "fixture-adapter-manifest.json"
)
CODEX_CLI_MANIFEST = (
    ROOT / "examples" / "adapters" / "codex-cli" / "adapter-manifest.json"
)


def test_lq_ai_fixture_manifest_passes_conformance(tmp_path: Path) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=LQ_AI_MANIFEST,
        output_dir=tmp_path / "lq-ai-conformance",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == "lq-ai-fixture-bridge"
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("passed:")


def test_lq_ai_fixture_capabilities_record_required_provenance(
    tmp_path: Path,
) -> None:
    adapter = CommandAdapter.from_manifest_file(LQ_AI_MANIFEST, timeout_seconds=30)
    capabilities = adapter.capabilities(tmp_path / "capabilities")

    assert capabilities.adapter_id == "lq-ai-fixture-bridge"
    assert set(capabilities.supported_families) == {
        "legalforecast_mtd",
        "harvey_lab",
    }
    assert set(capabilities.supported_scoring_modes) == {"lfb_brier", "lab_native"}


def test_hermes_agent_fixture_manifest_passes_conformance(tmp_path: Path) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=HERMES_MANIFEST,
        output_dir=tmp_path / "hermes-agent-conformance",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == "hermes-agent-fixture-bridge"
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("passed:")


def test_hermes_agent_fixture_capabilities_record_required_provenance(
    tmp_path: Path,
) -> None:
    adapter = CommandAdapter.from_manifest_file(HERMES_MANIFEST, timeout_seconds=30)
    capabilities = adapter.capabilities(tmp_path / "capabilities")

    assert capabilities.adapter_id == "hermes-agent-fixture-bridge"
    assert set(capabilities.supported_families) == {
        "legalforecast_mtd",
        "harvey_lab",
    }
    assert set(capabilities.supported_scoring_modes) == {"lfb_brier", "lab_native"}


def test_openclaw_fixture_manifest_passes_conformance(tmp_path: Path) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=OPENCLAW_MANIFEST,
        output_dir=tmp_path / "openclaw-conformance",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == "openclaw-fixture-bridge"
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("passed:")


def test_openclaw_fixture_capabilities_record_required_provenance(
    tmp_path: Path,
) -> None:
    adapter = CommandAdapter.from_manifest_file(OPENCLAW_MANIFEST, timeout_seconds=30)
    capabilities = adapter.capabilities(tmp_path / "capabilities")

    assert capabilities.adapter_id == "openclaw-fixture-bridge"
    assert set(capabilities.supported_families) == {
        "legalforecast_mtd",
        "harvey_lab",
    }
    assert set(capabilities.supported_scoring_modes) == {"lfb_brier", "lab_native"}


def test_provider_runtime_fixture_manifests_pass_conformance(
    tmp_path: Path,
) -> None:
    expected_ids = {
        OPENAI_RESPONSES_FIXTURE_MANIFEST: "openai-responses-fixture-baseline",
        CLAUDE_AGENT_SDK_FIXTURE_MANIFEST: "claude-agent-sdk-fixture-baseline",
    }
    for manifest, adapter_id in expected_ids.items():
        run = run_adapter_conformance(
            adapter_manifest_path=manifest,
            output_dir=tmp_path / adapter_id,
            timeout_seconds=30,
        )

        assert run.report.status == "passed"
        assert run.report.adapter_id == adapter_id
        assert run.report.checks["lfb_fixture_run"].startswith("passed:")
        assert run.report.checks["lab_fixture_run"].startswith("passed:")


def test_provider_runtime_fixtures_record_api_auth_assumptions(
    tmp_path: Path,
) -> None:
    for manifest in (
        OPENAI_RESPONSES_FIXTURE_MANIFEST,
        CLAUDE_AGENT_SDK_FIXTURE_MANIFEST,
    ):
        run = run_adapter_conformance(
            adapter_manifest_path=manifest,
            output_dir=tmp_path / manifest.parent.name,
            timeout_seconds=30,
        )
        lfb_result = _read_json(
            run.output_dir / "lfb-fixture" / "result.json",
        )
        public_summary = cast(dict[str, Any], lfb_result["public_summary"])

        assert public_summary["provider_runtime_baseline"] is True
        assert public_summary["auth_mode"] == "api-key-by-user-environment"
        assert public_summary["subscription_login_claimed"] is False
        assert "provider_terms_assumption" in public_summary


def test_openai_responses_baseline_passes_offline_conformance(
    tmp_path: Path,
) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=OPENAI_RESPONSES_MANIFEST,
        output_dir=tmp_path / "openai-responses-real",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == "openai-responses-baseline"
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("skipped:")


def test_openai_responses_baseline_advertises_live_tool_protocol(
    tmp_path: Path,
) -> None:
    openai = CommandAdapter.from_manifest_file(
        OPENAI_RESPONSES_MANIFEST,
        timeout_seconds=30,
    ).capabilities(tmp_path / "openai")
    claude = CommandAdapter.from_manifest_file(
        CLAUDE_AGENT_SDK_MANIFEST,
        timeout_seconds=30,
    ).capabilities(tmp_path / "claude")

    assert openai.tool_protocol_version == TOOL_REQUEST_SCHEMA_VERSION
    assert claude.tool_protocol_version == TOOL_REQUEST_SCHEMA_VERSION
    expected_semantics = {
        "adapter_id": "openai-responses-baseline",
        "adapter_version": "1.0.0",
        "adapter_bundle_sha256": openai_adapter_bundle_sha256(),
        "max_output_tokens_per_request": 4096,
        "sdk_name": "openai",
        "sdk_max_retries": 0,
        "sdk_version": "3.0.0",
        "supported_families": ["legalforecast_mtd"],
        "supported_scoring_modes": ["lfb_brier"],
        "supports_sandbox_policy": True,
        "tool_protocol_version": TOOL_REQUEST_SCHEMA_VERSION,
    }
    encoded = json.dumps(
        expected_semantics,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert openai.capabilities_sha256 == (
        "sha256:" + hashlib.sha256(encoded).hexdigest()
    )


def test_claude_agent_sdk_baseline_passes_offline_conformance(
    tmp_path: Path,
) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=CLAUDE_AGENT_SDK_MANIFEST,
        output_dir=tmp_path / "claude-agent-sdk-real",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == "claude-agent-sdk-baseline"
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("skipped:")


def test_claude_agent_sdk_baseline_advertises_live_tool_protocol(
    tmp_path: Path,
) -> None:
    capabilities = CommandAdapter.from_manifest_file(
        CLAUDE_AGENT_SDK_MANIFEST,
        timeout_seconds=30,
    ).capabilities(tmp_path / "claude")

    assert capabilities.tool_protocol_version == TOOL_REQUEST_SCHEMA_VERSION
    expected_semantics = {
        "adapter_id": "claude-agent-sdk-baseline",
        "adapter_version": "1.0.0",
        "adapter_bundle_sha256": claude_adapter_bundle_sha256(),
        "bundled_cli_version": "2.1.232",
        "max_budget_usd": 0.5,
        "max_turns": 8,
        "output_contract_version": "legalforecast.claude_agent_sdk.output.v1",
        "prompt_version": "legalforecast.claude_agent_sdk.prompt.v1",
        "sdk_name": "claude-agent-sdk",
        "sdk_version": "0.2.138",
        "supported_families": ["legalforecast_mtd"],
        "supported_scoring_modes": ["lfb_brier"],
        "supports_sandbox_policy": True,
        "tool_contract_version": "legalforecast.claude_agent_sdk.tool.v1",
        "tool_protocol_version": TOOL_REQUEST_SCHEMA_VERSION,
    }
    encoded = json.dumps(
        expected_semantics,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert capabilities.capabilities_sha256 == (
        "sha256:" + hashlib.sha256(encoded).hexdigest()
    )


def test_codex_cli_offline_adapter_passes_offline_conformance(tmp_path: Path) -> None:
    run = run_adapter_conformance(
        adapter_manifest_path=CODEX_CLI_MANIFEST,
        output_dir=tmp_path / "codex-cli-offline",
        timeout_seconds=30,
    )

    assert run.report.status == "passed"
    assert run.report.adapter_id == "codex-cli-offline"
    assert run.report.checks["lfb_fixture_run"].startswith("passed:")
    assert run.report.checks["lab_fixture_run"].startswith("skipped:")
    assert run.report.checks["sandbox_negative_control"].startswith("passed:")


def _read_json(path: Path) -> dict[str, Any]:
    import json

    decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], decoded)
