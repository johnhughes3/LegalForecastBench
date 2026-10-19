"""Contract tests for the repository landing page."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import TypedDict

import pytest
from legalforecast.reporting.result_class import (
    PRE_ANCHOR_PUBLIC_LABEL,
)

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
PUBLICATION_GOVERNANCE_PATH = ROOT / "docs" / "publication-governance.md"
MULTIHARNESS_README_PATH = ROOT / "docs" / "multiharness" / "README.md"
MULTIHARNESS_SUBMISSIONS_PATH = ROOT / "docs" / "multiharness" / "submissions.md"
MULTIHARNESS_CONTRIBUTOR_GUIDE_PATH = (
    ROOT / "docs" / "multiharness" / "contributor-guide.md"
)
PREPUBLICATION_MARKER = "<!-- result-publication-state: pre-publication -->"
UNPUBLISHED_STATUS = "No official or community benchmark score is published yet"
NON_AFFILIATION_TEXT = (
    "LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and "
    "LegalQuants are not sponsors, partners, or endorsers of this work."
)
PRELIMINARY_LABEL = (
    "Preliminary — one task pair, operator-run, not independently reproducible"
)
REPRODUCIBLE_LABEL = "Reproducible community result — contributor-grade, non-official"


class _Surface(TypedDict):
    canonical_path: str
    call_to_action: str


class _Tier(TypedDict):
    required_label: str


def _readme() -> str:
    return README_PATH.read_text(encoding="utf-8")


def _publication_governance() -> str:
    return PUBLICATION_GOVERNANCE_PATH.read_text(encoding="utf-8")


def _multiharness_readme() -> str:
    return MULTIHARNESS_README_PATH.read_text(encoding="utf-8")


def test_first_screen_states_status_boundary_tracks_and_next_actions() -> None:
    readme = _readme()
    first_screen = readme[: readme.index("## Why This Exists")]
    wrapped_lines = sum(
        max(1, len(textwrap.wrap(line, width=100)))
        for line in first_screen.splitlines()
    )

    assert len(first_screen.split()) <= 250
    assert wrapped_lines <= 42
    assert PREPUBLICATION_MARKER not in first_screen
    assert UNPUBLISHED_STATUS not in first_screen
    assert "does not prove zero contamination" in first_screen
    assert "91 cases and 387 scored" in first_screen
    assert (
        "summary experiments and the GPT-4.1 reference are reported separately"
        in first_screen
    )
    publication_links = dict(re.findall(r"\[([^]]+)\]\(([^)]+)\)", first_screen))
    assert (
        publication_links["working paper"]
        == "https://www.legalforecastbench.org/paper/"
    )
    assert publication_links["results"] == "https://www.legalforecastbench.org/"

    for call_to_action in (
        "[Read the methods](docs/METHODS.md)",
        "[Reproduce or audit](docs/reproduce-or-audit.md)",
        "[Check publication rules](docs/publication-governance.md)",
    ):
        assert call_to_action in first_screen

    assert "coming soon" not in readme.casefold()


def test_readme_exposes_governed_result_anchors_without_tier_upgrade() -> None:
    readme = _readme()
    governance = _publication_governance()

    assert "## Official Benchmark Results" in readme
    result_section = readme.split("## Official Benchmark Results", 1)[1].split(
        "## ", 1
    )[0]
    assert "micro-Brier and equal-case Brier scores" in result_section
    assert "downloadable data" in result_section
    assert "publish it soon" not in result_section
    assert not any(line.startswith("|") for line in result_section.splitlines())

    assert "No official result is claimed by this README revision" not in readme
    assert NON_AFFILIATION_TEXT in readme
    assert NON_AFFILIATION_TEXT in governance

    heading_anchors = {
        _github_heading_anchor(match.group(1))
        for match in re.finditer(r"^#{1,6} +(.*)$", readme, flags=re.MULTILINE)
    }
    assert "official-benchmark-results" in heading_anchors


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
            PRE_ANCHOR_PUBLIC_LABEL
            if surface_id == "official-cycle-1-report"
            else PRELIMINARY_LABEL
        )
    )
    surface = surface_data

    # Keep the stale-page fixture independent of the current published status.
    readme = f"{PREPUBLICATION_MARKER}\n{UNPUBLISHED_STATUS}\n**{stale_surface_claim}**"
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


def test_readme_points_to_the_planned_multiharness_track() -> None:
    """The community track is planned, so the README only signposts its docs."""
    readme = _readme()
    start_here = readme.index("## Start Here")
    community = readme.index("## Community Multi-Harness Comparisons (planned)")
    quickstart = readme.index("## Quickstart")

    assert start_here < community < quickstart
    assert "](docs/multiharness/README.md)" in readme
    assert "not yet operational" in readme
    assert "uv run legalforecast multiharness" not in readme


def test_multiharness_landing_page_evidence_descriptions() -> None:
    landing = _multiharness_readme()

    assert "**Status: non-official community track.**" in landing
    assert "## Evidence descriptions" in landing
    assert "not result tiers" in landing
    assert "Two result tiers" not in landing
    assert (
        "official, verified-community, community-unverified, or alpha-non-canonical"
        in landing
    )
    assert f"**{PRELIMINARY_LABEL}**" in landing
    assert f"**{REPRODUCIBLE_LABEL}**" in landing
    assert "accepted through the community PR workflow" in landing
    assert "official LegalForecast-MTD result publication" in landing
    assert "attestation" not in landing.casefold()
    assert "uv run legalforecast multiharness --help" in landing
    for target in ("contributor-guide.md", "adapter-spec.md", "submissions.md"):
        assert f"]({target})" in landing
        assert (MULTIHARNESS_README_PATH.parent / target).is_file()
    assert NON_AFFILIATION_TEXT in landing


def test_multiharness_docs_declarations_and_owner_approval() -> None:
    submissions = MULTIHARNESS_SUBMISSIONS_PATH.read_text(encoding="utf-8")
    guide = MULTIHARNESS_CONTRIBUTOR_GUIDE_PATH.read_text(encoding="utf-8")

    assert "## Required Contributor Declarations" in submissions
    assert "ordinary manifest fields" in submissions
    assert "validator and publication guardrails consume" in submissions
    assert "not signatures, certificates, separate approval artifacts" in submissions
    assert "--acknowledge-required-attestations" in submissions
    assert "stable `attestations` manifest field" in submissions

    assert "recorded owner approval" in guide
    assert "private JSON containing `spec_sha256`" in guide
    assert "the owner's actual `owner_approval` words" in guide
    assert "detached approval" not in guide.casefold()


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
