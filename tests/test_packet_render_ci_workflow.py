from __future__ import annotations

from pathlib import Path

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


def test_ci_rebuilds_and_verifies_packet_renders() -> None:
    production_build = WORKFLOW.index("uv run legalforecast acquisition build-packets")
    golden_compare = WORKFLOW.index(
        "diff -u tests/fixtures/packet_render_ci/expected-packets.jsonl"
    )
    verification = WORKFLOW.index("uv run scripts/reconstruct_packets.py")
    build = WORKFLOW.index("uv build --out-dir tmp/ci-dist")

    assert "- name: Rebuild and verify packet renders" in WORKFLOW
    assert production_build < golden_compare < verification < build
    assert "private_store_export.py" not in WORKFLOW
    assert (
        "--input tests/fixtures/packet_render_ci/packet-build-input.jsonl" in WORKFLOW
    )
    assert "--packets-output tmp/ci-packet-render/packets.jsonl" in WORKFLOW
    assert (
        "--manifest tests/fixtures/packet_render_ci/expected-packet-render.json"
        in WORKFLOW
    )
    assert "--verify-packet-render-dir tmp/ci-packet-render" in WORKFLOW


def test_production_packet_builder_matches_reviewed_golden(tmp_path: Path) -> None:
    output_root = tmp_path / "packet-render"
    packet_path = output_root / "packets.jsonl"

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(FIXTURE_ROOT / "packet-build-input.jsonl"),
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
