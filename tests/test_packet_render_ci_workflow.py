from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")


def test_ci_rebuilds_and_verifies_packet_renders() -> None:
    export = WORKFLOW.index(
        "uv run python legalforecast/publication/private_store_export.py"
    )
    verification = WORKFLOW.index("uv run scripts/reconstruct_packets.py")
    build = WORKFLOW.index("uv build --out-dir tmp/ci-dist")

    assert "- name: Rebuild and verify packet renders" in WORKFLOW
    assert export < verification < build
    assert "--source-dir tests/fixtures/packet_render_ci" in WORKFLOW
    assert (
        "--manifest tmp/ci-packet-render/objects/results/manifests/"
        "ci-packet-render.public-reconstruction.json" in WORKFLOW
    )
    assert "--verify-packet-render-dir tmp/ci-packet-render/objects/packet" in WORKFLOW
