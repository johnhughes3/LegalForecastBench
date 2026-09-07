"""Contract tests for the repository landing page."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import TypedDict

import pytest

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
PREPUBLICATION_MARKER = "<!-- result-publication-state: pre-publication -->"
UNPUBLISHED_STATUS = "No official or community benchmark score is published yet"
NON_AFFILIATION_TEXT = (
    "LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and "
    "LegalQuants are not sponsors, partners, or endorsers of this work."
)


class _Surface(TypedDict):
    canonical_path: str
    call_to_action: str


class _Tier(TypedDict):
    required_label: str


def _readme() -> str:
    return README_PATH.read_text(encoding="utf-8")


def test_first_screen_states_status_boundary_tracks_and_next_actions() -> None:
    readme = _readme()
    first_screen = readme[: readme.index("## Why This Exists")]
    wrapped_lines = sum(
        max(1, len(textwrap.wrap(line, width=100)))
        for line in first_screen.splitlines()
    )

    assert len(first_screen.split()) <= 250
    assert wrapped_lines <= 42
    assert PREPUBLICATION_MARKER in first_screen
    assert UNPUBLISHED_STATUS in first_screen
    assert "does not prove zero contamination" in first_screen
    assert "Official LegalForecast-MTD" in first_screen
    assert "Community Harness Comparisons" in first_screen
    assert "non-official" in first_screen
    assert "within 24 hours" in first_screen

    for call_to_action in (
        "[Read the methods](docs/METHODS.md)",
        "[Reproduce or audit](docs/reproduce-or-audit.md)",
        "[Check publication rules](docs/publication-governance.md)",
    ):
        assert call_to_action in first_screen

    assert "coming soon" not in readme.casefold()


def test_readme_exposes_governed_result_anchors_without_tier_upgrade() -> None:
    readme = _readme()

    assert "## Official Benchmark Results" in readme
    assert "## Preliminary Community Result" in readme
    assert "## Reproducible Community Comparisons" in readme

    assert (
        "Preliminary — one task pair, operator-run, not independently reproducible"
        in readme
    )
    assert "Reproducible community result — contributor-grade, non-official" in readme
    assert "Official LegalForecast-MTD Cycle 1 result" in readme

    assert "No official result is claimed by this README revision" in readme
    assert NON_AFFILIATION_TEXT in readme

    heading_anchors = {
        _github_heading_anchor(match.group(1))
        for match in re.finditer(r"^#{1,6} +(.*)$", readme, flags=re.MULTILINE)
    }
    for anchor in (
        "official-benchmark-results",
        "preliminary-community-result",
        "reproducible-community-comparisons",
    ):
        assert anchor in heading_anchors


@pytest.mark.parametrize(
    ("surface_id", "stale_surface_claim"),
    (
        (
            "official-cycle-1-report",
            "No official result is claimed by this README revision.",
        ),
        ("tier0-claude-writeup", "No validated result is linked yet."),
    ),
)
def test_published_result_fixture_rejects_a_stale_prepublication_readme(
    surface_id: str,
    stale_surface_claim: str,
) -> None:
    readme = _readme()
    surface_data = {
        "official-cycle-1-report": _Surface(
            canonical_path="results/official/cycle-1/README.md",
            call_to_action=(
                "Read the report, then follow the immutable audit and methods "
                "links before interpreting model differences."
            ),
        ),
        "tier0-claude-writeup": _Surface(
            canonical_path="results/community/harvey-lab/claude-code-tier0.md",
            call_to_action=(
                "Inspect the pinned specification and machine evidence before "
                "interpreting the observed result."
            ),
        ),
    }[surface_id]
    tier = _Tier(
        required_label=(
            "Official LegalForecast-MTD Cycle 1 result"
            if surface_id == "official-cycle-1-report"
            else (
                "Preliminary — one task pair, operator-run, not independently "
                "reproducible"
            )
        )
    )
    surface = surface_data

    with pytest.raises(AssertionError):
        _assert_published_surface(readme, surface, tier, stale_surface_claim)

    published_fixture = (
        readme.replace(
            PREPUBLICATION_MARKER,
            f"<!-- result-publication-state: {surface_id}-published -->",
        )
        .replace(
            UNPUBLISHED_STATUS,
            "At least one validated benchmark result is published",
        )
        .replace(
            f"**{stale_surface_claim}**",
            f"[{tier['required_label']}]({surface['canonical_path']})",
        )
    )
    published_fixture += f"\n{surface['call_to_action']}\n"

    _assert_published_surface(
        published_fixture,
        surface,
        tier,
        stale_surface_claim,
    )


def test_contributor_path_remains_discoverable_after_reader_first_sections() -> None:
    readme = _readme()
    start_here = readme.index("## Start Here")
    contributor_path = readme.index("## Reproducible Community Comparisons")
    quickstart = readme.index("## Quickstart")

    assert start_here < contributor_path < quickstart
    assert "[Multi-Harness Adapter Spec](docs/multiharness/adapter-spec.md)" in readme
    assert "docs/community-contributor-guide.md" in readme
    assert "[Community Submissions](docs/community-submissions.md)" in readme
    assert "uv run legalforecast multiharness --help" in readme


def test_all_repository_relative_markdown_links_resolve() -> None:
    readme = _readme()
    links = re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", readme)

    for target in links:
        if target.startswith(("https://", "http://", "mailto:")):
            continue
        path_text, _, fragment = target.partition("#")
        if not path_text:
            continue
        target_path = ROOT / path_text
        assert target_path.exists(), f"README link does not resolve: {target}"
        if fragment and target_path.suffix == ".md":
            target_text = target_path.read_text(encoding="utf-8")
            anchors = {
                _github_heading_anchor(match.group(1))
                for match in re.finditer(
                    r"^#{1,6} +(.*)$", target_text, flags=re.MULTILINE
                )
            }
            assert fragment in anchors, f"README fragment does not resolve: {target}"


def _assert_published_surface(
    readme: str,
    surface: _Surface,
    tier: _Tier,
    stale_surface_claim: str,
) -> None:
    assert PREPUBLICATION_MARKER not in readme
    assert UNPUBLISHED_STATUS not in readme
    assert stale_surface_claim not in readme
    assert f"]({surface['canonical_path']})" in readme
    assert tier["required_label"] in readme
    assert surface["call_to_action"] in readme


def _github_heading_anchor(heading: str) -> str:
    plain = re.sub(r"[*_`]", "", heading).strip().casefold()
    plain = re.sub(r"[^a-z0-9 -]", "", plain)
    return re.sub(r"[ -]+", "-", plain).strip("-")
