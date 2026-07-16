from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from legalforecast.cli import main
from legalforecast.publication.reconstruction import (
    VerificationStatus,
    load_reconstruction_plans,
    verify_reconstructed_packet_renders,
)
from scripts.verify_review_blockers import check_v2_10

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
FIXTURE_ROOT = ROOT / "tests/fixtures/packet_render_ci"
REGISTRY = ROOT / "model_registries/cycle-1-2026-06-30.json"


def test_ci_rebuilds_and_verifies_packet_renders() -> None:
    focused_golden = WORKFLOW.index(
        "tests/test_packet_render_ci_workflow.py::"
        "test_production_packet_builder_matches_reviewed_golden"
    )
    build = WORKFLOW.index("uv build --out-dir tmp/ci-dist")

    assert "- name: Rebuild and verify packet renders" in WORKFLOW
    assert focused_golden < build
    assert "uv run legalforecast acquisition build-packets" not in WORKFLOW
    assert "private_store_export.py" not in WORKFLOW
    assert "uv run pytest -q" in WORKFLOW


def test_production_packet_builder_matches_reviewed_golden(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
) -> None:
    output_root = tmp_path / "packet-render"
    packet_path = output_root / "packets.jsonl"
    lineage_root = tmp_path / "reviewed-lineage"
    lineage_root.mkdir()
    selection = lineage_root / "selection.jsonl"
    manifest = lineage_root / "document-downloads-merged.jsonl"
    clearance = lineage_root / "disclosure-clearance.jsonl"
    document_root = lineage_root / "documents"
    document_root.mkdir()
    selection.write_text("{}\n", encoding="utf-8")
    manifest.write_text("{}\n", encoding="utf-8")
    clearance.write_text("{}\n", encoding="utf-8")
    materialization_card = authenticated_downstream_fixture.materialize(
        manifest=manifest,
        clearance=clearance,
        document_root=document_root,
        selection=selection,
        name="packet-render-golden",
    )
    planner_card = lineage_root / "plan-packet-inputs.json"
    authenticated_downstream_fixture.write_packet_planner_card(
        planner_card,
        packet_input=FIXTURE_ROOT / "packet-build-input.jsonl",
        selection=selection,
        manifest=manifest,
        clearance=clearance,
        document_root=document_root,
        materialization_run_card=materialization_card,
    )

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(FIXTURE_ROOT / "packet-build-input.jsonl"),
                "--packet-input-run-card",
                str(planner_card),
                "--selection",
                str(selection),
                "--download-manifest",
                str(manifest),
                "--parser-manifest",
                str(selection),
                "--parser-run-card",
                str(materialization_card),
                "--parse-plan-run-card",
                str(materialization_card),
                "--disclosure-clearance",
                str(clearance),
                "--raw-prediction-units",
                str(selection),
                "--prediction-units",
                str(selection),
                "--llm-unitization-audit",
                str(selection),
                "--llm-unitize-run-card",
                str(selection),
                "--llm-unitize-provider-journal",
                str(selection),
                "--original-unitization-review-queue",
                str(selection),
                "--stage-a-structural-flags",
                str(selection),
                "--stage-a-structural-review-audit",
                str(selection),
                "--stage-a-review-run-card",
                str(selection),
                "--stage-a-review-provider-journal",
                str(selection),
                "--stage-a-review-model-registry",
                str(REGISTRY),
                "--stage-a-review-model-key",
                "fixture:fixture-model",
                "--unitization-review-queue",
                str(selection),
                "--unitization-review-adjudications",
                str(selection),
                "--apply-unitization-review-run-card",
                str(selection),
                "--model-registry",
                str(REGISTRY),
                "--expected-model-registry-sha256",
                hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
                "--raw-html-dir",
                str(document_root),
                "--raw-artifacts-manifest",
                str(selection),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--packets-output",
                str(packet_path),
                "--case-packets-output",
                str(output_root / "case-packets.jsonl"),
                "--audit-output",
                str(output_root / "packet-audit.jsonl"),
                "--execute",
            ]
        )
        == 0
    )

    assert (
        packet_path.read_bytes()
        == (FIXTURE_ROOT / "expected-packets.jsonl").read_bytes()
    )
    plans = load_reconstruction_plans(FIXTURE_ROOT / "expected-packet-render.json")
    verifications = verify_reconstructed_packet_renders(plans, output_root)
    assert len(verifications) == 1
    assert verifications[0].status is VerificationStatus.VERIFIED


def test_v2_10_requires_production_builder_and_independent_golden() -> None:
    passed, detail = check_v2_10()
    assert passed, detail
