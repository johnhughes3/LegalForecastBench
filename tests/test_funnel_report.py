from __future__ import annotations

import pytest
from legalforecast.ingestion.funnel_report import (
    FunnelReportError,
    build_acquisition_funnel_report,
)


def test_funnel_report_reconciles_counts_and_emits_per_term_diagnostics() -> None:
    report = build_acquisition_funnel_report(
        discovery_summary={
            "processed_candidate_count": 7,
            "accepted_case_count": 1,
            "excluded_case_count": 6,
            "per_term": {
                "order granting motion": {
                    "request_count": 2,
                    "candidate_count": 4,
                    "terminal_status": "exhausted",
                },
                "order on motion": {
                    "request_count": 1,
                    "candidate_count": 3,
                    "terminal_status": "limit_bound",
                },
            },
        },
        exclusions=[
            _exclusion("not_federal_district_court", "discovery"),
            _exclusion("courtlistener_docket_html_unavailable", "retrieval"),
            _exclusion("parse_error", "extraction"),
            _exclusion("multi_page_docket", "extraction"),
            _exclusion("decision_before_release_anchor", "eligibility"),
            _exclusion("no_actual_mtd_disposition", "discovery"),
        ],
        public_download_summary={
            "target_clean_cases": 25,
            "screened_case_count": 1,
            "planned_case_count": 1,
            "selected_case_count": 1,
            "shortfall": 24,
        },
    )

    assert report["schema_version"] == "legalforecast.acquisition_funnel_report.v1"
    assert report["funnel"] == {
        "processed": 7,
        "metadata_pass": 6,
        "html_fetched": 5,
        "parse_ok": 4,
        "single_page": 3,
        "post_anchor": 2,
        "strict_clean": 1,
    }
    assert report["per_term"][0]["request_count"] == 2
    assert report["per_term"][1]["limit_bound"] is True
    assert report["reconciled"] is True


def test_funnel_report_rejects_default_public_download_limit_binding() -> None:
    with pytest.raises(FunnelReportError, match="target-clean-cases bound"):
        build_acquisition_funnel_report(
            discovery_summary={
                "processed_candidate_count": 30,
                "accepted_case_count": 30,
                "excluded_case_count": 0,
                "per_term": {
                    "term": {
                        "request_count": 1,
                        "candidate_count": 30,
                        "terminal_status": "exhausted",
                    }
                },
            },
            exclusions=[],
            public_download_summary={
                "target_clean_cases": 25,
                "screened_case_count": 30,
                "planned_case_count": 25,
                "selected_case_count": 25,
                "shortfall": 0,
            },
        )


def test_funnel_report_rejects_coarse_count_mismatch() -> None:
    with pytest.raises(FunnelReportError, match="do not reconcile"):
        build_acquisition_funnel_report(
            discovery_summary={
                "processed_candidate_count": 2,
                "accepted_case_count": 1,
                "excluded_case_count": 0,
                "per_term": {},
            },
            exclusions=[],
            public_download_summary={
                "target_clean_cases": 25,
                "screened_case_count": 1,
                "planned_case_count": 1,
                "selected_case_count": 1,
                "shortfall": 24,
            },
        )


def test_funnel_report_rejects_duplicate_exclusion_candidates() -> None:
    duplicate = _exclusion("courtlistener_docket_unavailable", "retrieval")
    with pytest.raises(FunnelReportError, match="candidate_id values must be unique"):
        build_acquisition_funnel_report(
            discovery_summary={
                "processed_candidate_count": 2,
                "accepted_case_count": 0,
                "excluded_case_count": 2,
                "per_term": {},
            },
            exclusions=[duplicate, duplicate],
            public_download_summary={
                "target_clean_cases": 25,
                "screened_case_count": 0,
                "planned_case_count": 0,
            },
        )


def test_funnel_report_classifies_unavailable_docket_before_metadata_pass() -> None:
    report = build_acquisition_funnel_report(
        discovery_summary={
            "processed_candidate_count": 2,
            "accepted_case_count": 1,
            "excluded_case_count": 1,
            "per_term": {},
        },
        exclusions=[_exclusion("courtlistener_docket_unavailable", "retrieval")],
        public_download_summary={
            "target_clean_cases": 25,
            "screened_case_count": 1,
            "planned_case_count": 1,
        },
    )

    assert report["funnel"]["metadata_pass"] == 1


def test_funnel_report_allows_nonbinding_target_with_planner_exclusions() -> None:
    report = build_acquisition_funnel_report(
        discovery_summary={
            "processed_candidate_count": 30,
            "accepted_case_count": 30,
            "excluded_case_count": 0,
            "per_term": {},
        },
        exclusions=[],
        public_download_summary={
            "target_clean_cases": 25,
            "screened_case_count": 30,
            "planned_case_count": 20,
        },
    )

    assert report["plan_public_downloads_target"]["bound"] is False


def _exclusion(reason: str, stage: str) -> dict[str, str]:
    return {
        "candidate_id": f"candidate-{reason}-{stage}",
        "primary_exclusion_reason": reason,
        "stage": stage,
    }
