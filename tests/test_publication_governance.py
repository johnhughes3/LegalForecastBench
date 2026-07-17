"""Contract tests for audience, claims, and publication governance."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_PATH = ROOT / "docs" / "publication-governance.json"
GOVERNANCE_DOC_PATH = ROOT / "docs" / "publication-governance.md"
ROADMAP_PATH = ROOT / "docs" / "plans" / "2026-07-16-dual-track-launch-roadmap.md"
DOCS_INDEX_PATH = ROOT / "docs" / "README.md"

PRELIMINARY_LABEL = (
    "Preliminary — one task pair, operator-run, not independently reproducible"
)


def _governance() -> dict[str, Any]:
    return json.loads(GOVERNANCE_PATH.read_text(encoding="utf-8"))


def test_governance_contract_covers_required_scope() -> None:
    governance = _governance()

    assert governance["schema_version"] == 1
    assert governance["effective_date"] == "2026-07-16"
    assert set(governance["audiences"]) == {
        "ai-researchers",
        "contributors",
        "legalquants",
        "practitioners",
    }
    assert set(governance["evidence_tiers"]) == {
        "official",
        "preliminary",
        "reproducible",
    }

    rules = governance["rules"]
    assert rules["dates_are_escalation_triggers_not_gate_waivers"] is True
    assert rules["official_and_community_surfaces_are_separate"] is True
    assert rules["cross_suite_overall_winner_forbidden"] is True
    assert rules["external_send_requires_john_approval"] is True
    assert rules["no_paid_community_run_before_tier0_specification"] is True

    non_affiliation = governance["non_affiliation"]
    assert set(non_affiliation["named_organizations"]) == {
        "Harvey AI",
        "Harvey LAB",
        "LegalQuants",
    }
    for organization in non_affiliation["named_organizations"]:
        assert organization in non_affiliation["required_text"]


def test_every_planned_public_surface_has_a_tier_owner_and_approval() -> None:
    governance = _governance()
    tiers = set(governance["evidence_tiers"])
    owners = set(governance["owners"])
    approvals = set(governance["approvals"])
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
        assert surface["evidence_tier"] in tiers
        assert surface["owner"] in owners
        assert surface["approval"] in approvals
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

    for audience in governance["audiences"].values():
        assert set(audience["priority_surfaces"]).issubset(expected_surfaces)


def test_controlled_communications_remain_unsent_without_john() -> None:
    governance = _governance()
    owners = set(governance["owners"])
    approvals = set(governance["approvals"])

    for communication in governance["controlled_communications"]:
        assert communication["owner"] in owners
        assert communication["approval"] in approvals
        assert communication["external_send_authorized"] is False
        assert communication["required_boundary"]


def test_preliminary_claim_boundary_matches_roadmap() -> None:
    governance = _governance()
    preliminary = governance["evidence_tiers"]["preliminary"]
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")

    assert preliminary["required_label"] == PRELIMINARY_LABEL
    assert PRELIMINARY_LABEL in roadmap
    assert {
        "contributor-safe",
        "estimated harness effect",
        "general superiority",
        "independently reproducible",
        "performs better",
        "population-average",
    }.issubset(preliminary["forbidden_claims"])
    assert governance["external_consistency_refs"]["github_issue_196"] == (
        "https://github.com/johnhughes3/LegalForecastBench/issues/196"
    )


def test_calendar_preserves_targets_escalations_and_gate_integrity() -> None:
    governance = _governance()
    calendar = {entry["id"]: entry for entry in governance["calendar"]}

    assert calendar["claude-tier0-package"]["target_date"] == "2026-07-21"
    assert calendar["claude-tier0-package"]["escalation_date"] == "2026-07-23"
    assert calendar["codex-tier0-follow-on"]["target_date"] == "2026-07-23"
    assert calendar["codex-tier0-follow-on"]["escalation_date"] == "2026-07-25"
    assert calendar["claims-governance-freeze"]["target_date"] == "2026-07-18"
    assert calendar["legalquants-first-send-decision"]["target_date"] == ("2026-07-18")
    assert calendar["tier1-first-trusted-row"]["target_date"] == "2026-08-07"
    assert calendar["official-dispatch"]["target_date"] == "2026-08-13"
    assert calendar["official-publication"]["target_date"] == "2026-08-17"
    assert calendar["legalquants-input-window-close"]["target_date"] == ("2026-08-12")
    assert calendar["pilot-publication"]["target_date"] == "2026-08-21"

    for entry in calendar.values():
        date.fromisoformat(entry["target_date"])
        if entry["escalation_date"] is not None:
            date.fromisoformat(entry["escalation_date"])
        assert entry["miss_action"]
        assert entry["gate_waiver"] is False

    hard_escalations = {
        entry["id"]: entry["escalation_date"]
        for entry in calendar.values()
        if entry["escalation_date"] is not None
    }
    assert hard_escalations == {
        "claude-tier0-package": "2026-07-23",
        "codex-tier0-follow-on": "2026-07-25",
    }


def test_human_policy_and_docs_index_are_bound_to_the_contract() -> None:
    governance = _governance()
    policy = GOVERNANCE_DOC_PATH.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX_PATH.read_text(encoding="utf-8")

    assert "publication-governance.json" in policy
    assert PRELIMINARY_LABEL in policy
    assert governance["non_affiliation"]["required_text"] in policy
    for tier in governance["evidence_tiers"].values():
        assert tier["required_label"] in policy
    for audience in governance["audiences"].values():
        assert audience["display_name"] in policy
    assert "[Publication governance](publication-governance.md)" in docs_index
