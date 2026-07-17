"""Contract tests for public claims and publication governance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_PATH = ROOT / "docs" / "publication-governance.json"
GOVERNANCE_DOC_PATH = ROOT / "docs" / "publication-governance.md"
DOCS_INDEX_PATH = ROOT / "docs" / "README.md"

PRELIMINARY_LABEL = (
    "Preliminary — one task pair, operator-run, not independently reproducible"
)
REPRODUCIBLE_LABEL = "Reproducible community result — contributor-grade, non-official"
OFFICIAL_LABEL = "Official LegalForecast-MTD Cycle 1 result"
NON_AFFILIATION = (
    "LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and "
    "LegalQuants are not sponsors, partners, or endorsers of this work."
)


def _governance() -> dict[str, Any]:
    return json.loads(GOVERNANCE_PATH.read_text(encoding="utf-8"))


def test_governance_contract_contains_only_public_fields() -> None:
    governance = _governance()

    assert set(governance) == {
        "effective_date",
        "evidence_tiers",
        "non_affiliation",
        "public_surfaces",
        "repository_url",
        "rules",
        "schema_version",
    }
    assert governance["schema_version"] == 1
    assert governance["effective_date"] == "2026-07-16"
    assert set(governance["evidence_tiers"]) == {
        "official",
        "preliminary",
        "reproducible",
    }
    assert governance["evidence_tiers"]["preliminary"]["required_label"] == (
        PRELIMINARY_LABEL
    )
    assert governance["evidence_tiers"]["reproducible"]["required_label"] == (
        REPRODUCIBLE_LABEL
    )
    assert governance["evidence_tiers"]["official"]["required_label"] == (
        OFFICIAL_LABEL
    )
    assert set(governance["rules"]) == {
        "cross_suite_overall_winner_forbidden",
        "no_paid_community_run_before_tier0_specification",
        "official_and_community_surfaces_are_separate",
        "preliminary_results_do_not_close_issue_49",
        "scores_from_different_suites_are_not_ranked",
    }
    assert all(governance["rules"].values())

    non_affiliation = governance["non_affiliation"]
    assert set(non_affiliation) == {"named_organizations", "required_text"}
    assert set(non_affiliation["named_organizations"]) == {
        "Harvey AI",
        "Harvey LAB",
        "LegalQuants",
    }
    for organization in non_affiliation["named_organizations"]:
        assert organization in non_affiliation["required_text"]
    assert non_affiliation["required_text"] == NON_AFFILIATION


def test_every_public_surface_has_a_tier_and_canonical_destination() -> None:
    governance = _governance()
    tiers = set(governance["evidence_tiers"])
    expected_surfaces = {
        "community-comparison-site",
        "methods-preprint",
        "official-cycle-1-leaderboard",
        "official-cycle-1-report",
        "readme-community-contributor",
        "readme-community-tier0",
        "readme-official",
        "tier0-claude-writeup",
        "tier0-codex-addendum",
    }

    surfaces = governance["public_surfaces"]
    assert {surface["id"] for surface in surfaces} == expected_surfaces
    assert len({surface["canonical_path"] for surface in surfaces}) == len(surfaces)
    assert len({surface["canonical_url"] for surface in surfaces}) == len(surfaces)

    for surface in surfaces:
        assert set(surface) == {
            "call_to_action",
            "canonical_path",
            "canonical_url",
            "evidence_tier",
            "id",
            "required_disclosures",
            "track",
        }
        assert surface["evidence_tier"] in tiers
        assert surface["canonical_path"]
        assert surface["canonical_url"] == (
            "https://github.com/johnhughes3/LegalForecastBench/blob/main/"
            f"{surface['canonical_path']}"
        )
        assert surface["required_disclosures"]
        assert surface["call_to_action"]

    tracks_by_id = {surface["id"]: surface["track"] for surface in surfaces}
    assert tracks_by_id["official-cycle-1-report"] == "official"
    assert tracks_by_id["tier0-claude-writeup"] == "community"
    assert tracks_by_id["community-comparison-site"] == "community"

    for surface in surfaces:
        if surface["track"] == "official":
            assert surface["evidence_tier"] == "official"
        if surface["evidence_tier"] == "preliminary":
            assert surface["track"] == "community"


def test_preliminary_claim_boundary_is_fail_closed() -> None:
    governance = _governance()
    preliminary = governance["evidence_tiers"]["preliminary"]

    assert preliminary["required_label"] == PRELIMINARY_LABEL
    assert {
        "contributor-safe",
        "estimated harness effect",
        "general superiority",
        "independently reproducible",
        "performs better",
        "population-average",
    }.issubset(preliminary["forbidden_claims"])


def test_human_policy_and_docs_index_are_bound_to_the_public_contract() -> None:
    policy = GOVERNANCE_DOC_PATH.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX_PATH.read_text(encoding="utf-8")

    assert "publication-governance.json" in policy
    assert PRELIMINARY_LABEL in policy
    assert REPRODUCIBLE_LABEL in policy
    assert OFFICIAL_LABEL in policy
    assert NON_AFFILIATION in policy

    for internal_marker in (
        "## Audiences and calls to action",
        "## Calendar",
        "## Controlled communications",
        "## Owners and approvals",
        "5qd6",
    ):
        assert internal_marker not in policy

    assert (
        "[Publication governance](publication-governance.md): public evidence "
        "tiers, forbidden claims, canonical result destinations, track-separation "
        "rules, and non-affiliation language."
    ) in docs_index
