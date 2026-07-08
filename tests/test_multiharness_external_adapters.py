from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.conformance import run_adapter_conformance

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
CLAUDE_AGENT_SDK_MANIFEST = (
    ROOT / "examples" / "adapters" / "claude-agent-sdk" / "adapter-manifest.json"
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


def test_provider_runtime_baseline_manifests_pass_conformance(
    tmp_path: Path,
) -> None:
    expected_ids = {
        OPENAI_RESPONSES_MANIFEST: "openai-responses-fixture-baseline",
        CLAUDE_AGENT_SDK_MANIFEST: "claude-agent-sdk-fixture-baseline",
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


def test_provider_runtime_baselines_record_api_auth_assumptions(
    tmp_path: Path,
) -> None:
    for manifest in (OPENAI_RESPONSES_MANIFEST, CLAUDE_AGENT_SDK_MANIFEST):
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


def _read_json(path: Path) -> dict[str, Any]:
    import json

    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return record
