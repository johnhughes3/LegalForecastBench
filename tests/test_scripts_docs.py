from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scripts_agents_docs_current_entrypoints() -> None:
    docs = (ROOT / "scripts" / "AGENTS.md").read_text(encoding="utf-8")

    for expected in (
        "release_check.py",
        "official_infra_contract.py",
        "validate_local_assume_access.py",
        "uv run scripts/release_check.py",
        "scripts/official_infra_contract.py --help",
        "uv run scripts/validate_local_assume_access.py",
    ):
        assert expected in docs

    assert "once those implementation beads are started" not in docs


def test_publication_operator_docs_are_present() -> None:
    for relative_path in (
        "docs/METHODS.md",
        "docs/official-run-runbook.md",
        "docs/reproduce-or-audit.md",
    ):
        assert (ROOT / relative_path).is_file()
