from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTREACH = ROOT / "docs/outreach"
DRAFTS = OUTREACH / "legalquants-engagement-drafts.md"
SHARD_TEMPLATE = OUTREACH / "legalquants-proposed-shard.template.json"
FEEDBACK_TEMPLATE = OUTREACH / "legalquants-feedback-record.template.json"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _section(document: str, start: str, end: str) -> str:
    return document[document.index(start) : document.index(end)]


def test_immediate_draft_preserves_methods_and_send_boundaries() -> None:
    document = DRAFTS.read_text(encoding="utf-8")
    immediate = _section(document, "## Draft 1: immediate reply", "## Draft 2:")

    assert "DO NOT SEND" in document
    assert "preserve Claude Code's native tools and agent loop" in immediate
    assert "subject to feasibility and methods review" in immediate
    assert "have not finalized the stratified-pilot task or arm selection" in immediate
    assert "have not observed any stratified-pilot score" in immediate
    assert "before we freeze the task and arm selection" in immediate.lower()
    assert "August 12, 2026" in immediate
    assert "A response is not required for the work to continue" in immediate
    assert "LegalForecastBench is an independent project" in immediate
    assert "not sponsors, partners, or endorsers" in immediate


def test_result_follow_up_is_only_a_validated_preliminary_link_template() -> None:
    document = DRAFTS.read_text(encoding="utf-8")
    follow_up = _section(document, "## Draft 2:", "## Review gates")

    assert (
        "Preliminary — one task pair, operator-run, not independently reproducible"
        in follow_up
    )
    assert "[VALIDATED_PUBLICATION_URL]" in follow_up
    assert "validated public artifact" in follow_up
    assert "one pinned task pair" in follow_up
    assert "before any stratified-pilot score is observed" in follow_up
    assert "https://" not in follow_up
    for unsupported_claim in ("performs better", "harness effect", "superior"):
        assert unsupported_claim not in follow_up.lower()


def test_proposed_shard_template_precedes_scores_and_captures_full_freeze() -> None:
    template = _json(SHARD_TEMPLATE)

    assert template["status"] == "proposed_unfrozen"
    assert template["stratified_pilot_score_observed"] is False
    assert template["feedback_window"]["close_date"] == "2026-08-12"
    assert template["feedback_window"]["response_required_to_continue"] is False
    assert template["selection"]["task_strata"] == []
    assert template["selection"]["exact_task_ids"] == []
    assert template["selection"]["selection_hash"] == "TBD_BEFORE_PROPOSAL_COMMIT"
    assert template["proposed_arms"] == []
    for field in (
        "matched_model_rules",
        "randomized_order",
        "repeat_count",
        "failure_policy",
        "coverage_floor",
        "uncertainty_method",
        "budget",
        "stopping_rule",
    ):
        assert field in template
    assert "final_frozen_spec" not in template
    assert set(template["deterministic_selection_evidence"]) == {
        "expected_selection_hash",
        "fixture_path",
        "implementation_commit",
        "implementation_path",
    }
    assert set(template["balance_diagnostics"]) == {
        "artifact_path",
        "review_status",
    }
    assert template["randomized_order"]["golden_artifact_path"]
    assert set(template["budget_simulation"]) == {"artifact_path", "result"}


def test_feedback_template_records_terminal_window_and_design_disposition() -> None:
    template = _json(FEEDBACK_TEMPLATE)

    assert template["private_contact_information_collected"] is False
    assert template["stratified_pilot_score_observed_before_disposition"] is False
    assert set(template["outbound_decision_allowed"]) == {
        "declined",
        "deferred",
        "sent",
    }
    for field in (
        "approved_text_sha256",
        "approved_at",
        "sent_text_sha256",
        "approved_and_sent_text_match",
        "sent_at",
        "public_outbound_permalink",
    ):
        assert field in template
    assert set(template["window_close_state_allowed"]) == {
        "feedback_received",
        "john_declined_send",
        "no_response",
    }
    assert set(template["disposition_allowed"]) == {
        "accepted",
        "partially_accepted",
        "rejected",
        "not_applicable",
    }
    assert template["feedback_items"] == []
    assert set(template["feedback_item_template"]) == {
        "disposition",
        "disposition_before_selection_freeze",
        "disposition_recorded_at",
        "feedback_summary",
        "incorporated_diff_path",
        "public_feedback_permalink",
        "rationale",
        "received_at",
    }
    for field in (
        "proposed_shard_hash",
        "tier0_informed_change",
        "final_frozen_spec_path",
        "final_frozen_spec_hash",
        "final_spec_diff_path",
        "selection_frozen_at",
        "final_spec_committed_before_score_observation",
    ):
        assert field in template
