from __future__ import annotations

from pathlib import Path

from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.conformance import run_adapter_conformance

ROOT = Path(__file__).resolve().parents[1]
LQ_AI_MANIFEST = ROOT / "examples" / "adapters" / "lq-ai" / "adapter-manifest.json"


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
