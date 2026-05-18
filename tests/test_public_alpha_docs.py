from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_first_screen_states_pre_data_alpha_and_no_leaderboard() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    first_screen = readme.split("## Quickstart", maxsplit=1)[0]

    assert "pre-data alpha" in first_screen
    assert "does not yet publish" in first_screen
    assert "public cases" in first_screen
    assert "No public case corpus" in first_screen
    assert "No canonical leaderboard" in first_screen
    assert "Case.dev discovery is useful" in first_screen


def test_public_docs_link_feedback_security_and_no_paid_defaults() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "CONTRIBUTING.md" in readme
    assert "SECURITY.md" in readme
    assert "docs/ethics.md" in readme
    assert "ethics.md" in docs_index
    assert "Default checks must not require live credentials" in contributing
    assert "result-tier" in contributing
    assert "live, paid, or credentialed paths" in security
    assert "security regression" in security


def test_methodology_preregistration_and_acquisition_docs_mark_alpha_limits() -> None:
    methodology = (ROOT / "docs" / "methodology.md").read_text(encoding="utf-8")
    preregistration = (ROOT / "docs" / "preregistration.md").read_text(encoding="utf-8")
    acquisition = (ROOT / "docs" / "acquisition.md").read_text(encoding="utf-8")

    assert "current public" in methodology
    assert "release state is v0.1 alpha" in methodology
    assert "not an official preregistered cycle" in preregistration
    assert "does not yet publish a live benchmark corpus" in acquisition
