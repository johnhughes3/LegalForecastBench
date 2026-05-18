from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scripts_readme_documents_current_entrypoints() -> None:
    readme = (ROOT / "scripts" / "README.md").read_text(encoding="utf-8")

    for expected in (
        "alpha_release_check.py",
        "build_alpha_release_bundle.py",
        "reconstruct_packets.py",
        "uv run scripts/alpha_release_check.py",
        "uv run scripts/build_alpha_release_bundle.py",
        "uv run scripts/reconstruct_packets.py",
    ):
        assert expected in readme

    assert "once those implementation beads are started" not in readme
