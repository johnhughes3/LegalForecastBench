"""Reproducible acquisition funnel reports from terminal audit artifacts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any, cast

FUNNEL_REPORT_SCHEMA_VERSION = "legalforecast.acquisition_funnel_report.v1"

_METADATA_REASONS = frozenset(
    {
        "bankruptcy_court",
        "courtlistener_docket_unavailable",
        "criminal_style_caption",
        "metadata_screen_not_accepted",
        "missing_docket_number",
        "not_civil_cv_docket",
        "not_federal_district_court",
        "placeholder_or_sealed_docket_number",
    }
)
_HTML_RETRIEVAL_REASONS = frozenset(
    {"courtlistener_docket_html_unavailable", "docket_html_unavailable"}
)
_SINGLE_PAGE_REASONS = frozenset(
    {
        "courtlistener_docket_more_than_one_page",
        "docket_pagination_incomplete",
        "multi_page_docket",
        "not_single_page",
    }
)
_POST_ANCHOR_REASONS = frozenset(
    {"decision_before_release_anchor", "decision_date_unparseable"}
)


class FunnelReportError(ValueError):
    """Raised when source artifacts do not reconcile or a cap bound."""


def build_acquisition_funnel_report(
    *,
    discovery_summary: Mapping[str, Any],
    exclusions: Sequence[Mapping[str, Any]],
    public_download_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable funnel and fail closed on inconsistent terminal counts.

    Exclusions are terminal candidate records.  A candidate excluded at a gate
    passed every preceding gate, so subtracting each gate's terminal reasons
    yields reproducible, monotone stage counts without hand tallying.
    """

    processed = _required_int(discovery_summary, "processed_candidate_count")
    accepted = _required_int(discovery_summary, "accepted_case_count")
    excluded = _required_int(discovery_summary, "excluded_case_count")
    if processed != accepted + excluded:
        raise FunnelReportError(
            "discovery counts do not reconcile: processed_candidate_count must "
            "equal accepted_case_count + excluded_case_count"
        )
    if len(exclusions) != excluded:
        raise FunnelReportError(
            "exclusion ledger count does not match excluded_case_count"
        )

    candidate_ids = tuple(
        _required_str(record, "candidate_id") for record in exclusions
    )
    if len(set(candidate_ids)) != len(candidate_ids):
        raise FunnelReportError("exclusion candidate_id values must be unique")
    reasons = Counter(_reason(record) for record in exclusions)
    stages = Counter(_optional_str(record.get("stage")) for record in exclusions)
    gate_failures = Counter(_exclusion_gate(record) for record in exclusions)
    metadata_failed = gate_failures["metadata_pass"]
    metadata_pass = processed - metadata_failed
    html_failed = gate_failures["html_fetched"]
    html_fetched = metadata_pass - html_failed
    parse_failed = gate_failures["parse_ok"]
    parse_ok = html_fetched - parse_failed
    single_page_failed = gate_failures["single_page"]
    single_page = parse_ok - single_page_failed
    post_anchor_failed = gate_failures["post_anchor"]
    post_anchor = single_page - post_anchor_failed
    strict_failed = gate_failures["strict_clean"]
    if post_anchor - strict_failed != accepted:
        raise FunnelReportError(
            "terminal exclusions do not reconcile post_anchor to strict_clean"
        )
    funnel = {
        "processed": processed,
        "metadata_pass": metadata_pass,
        "html_fetched": html_fetched,
        "parse_ok": parse_ok,
        "single_page": single_page,
        "post_anchor": post_anchor,
        "strict_clean": accepted,
    }
    counts = tuple(funnel.values())
    if any(count < 0 for count in counts) or any(
        later > earlier for earlier, later in pairwise(counts)
    ):
        raise FunnelReportError("exclusion reasons produce a non-monotone funnel")

    per_term = _per_term_diagnostics(discovery_summary)
    target_limit = _public_download_limit(public_download_summary)
    return {
        "schema_version": FUNNEL_REPORT_SCHEMA_VERSION,
        "funnel": funnel,
        "exclusions_by_reason": dict(sorted(reasons.items())),
        "exclusions_by_stage": {
            stage: count for stage, count in sorted(stages.items()) if stage
        },
        "per_term": per_term,
        "plan_public_downloads_target": target_limit,
        "reconciled": True,
    }


def _per_term_diagnostics(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = summary.get("per_term")
    if raw is None:
        raw = summary.get("per_term_counts")
    if not isinstance(raw, Mapping):
        raise FunnelReportError("discovery summary must include per_term counts")
    raw_mapping = cast(Mapping[object, object], raw)
    statuses_value = summary.get("terminal_status_by_term", {})
    if not isinstance(statuses_value, Mapping):
        raise FunnelReportError("terminal_status_by_term must be an object")
    statuses = cast(Mapping[object, object], statuses_value)
    diagnostics: list[dict[str, Any]] = []
    if any(not isinstance(term, str) for term in raw_mapping):
        raise FunnelReportError("per_term must map term strings to objects")
    for term in sorted(cast(list[str], list(raw_mapping))):
        record_value = raw_mapping[term]
        if not isinstance(record_value, Mapping):
            raise FunnelReportError("per_term must map term strings to objects")
        record = cast(Mapping[str, Any], record_value)
        request_count = _required_int(record, "request_count")
        candidate_count = _required_int(record, "candidate_count")
        status = record.get("terminal_status", statuses.get(term))
        if not isinstance(status, str) or not status:
            raise FunnelReportError(f"per_term terminal status missing: {term}")
        diagnostics.append(
            {
                "term": term,
                "request_count": request_count,
                "candidate_count": candidate_count,
                "terminal_status": status,
                "limit_bound": status.startswith("limit_bound"),
            }
        )
    return diagnostics


def _public_download_limit(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    if summary is None:
        raise FunnelReportError(
            "plan-public-downloads summary is required to prove its target did not bind"
        )
    target = _required_int(summary, "target_clean_cases")
    screened = _required_int(summary, "screened_case_count")
    planned = _required_int(summary, "planned_case_count")
    if planned > screened:
        raise FunnelReportError("planned_case_count cannot exceed screened_case_count")
    bound = planned == target and screened > planned
    if bound:
        raise FunnelReportError(
            "plan-public-downloads --target-clean-cases bound the viable pool; "
            "rerun with a limit above the complete candidate count"
        )
    return {
        "configured": target,
        "screened_case_count": screened,
        "planned_case_count": planned,
        "bound": False,
    }


def _exclusion_gate(record: Mapping[str, Any]) -> str:
    reason = _reason(record)
    stage = _optional_str(record.get("stage"))
    if reason in _METADATA_REASONS:
        return "metadata_pass"
    if reason in _HTML_RETRIEVAL_REASONS:
        return "html_fetched"
    if reason == "parse_error" and stage == "extraction":
        return "parse_ok"
    if reason in _SINGLE_PAGE_REASONS:
        return "single_page"
    if reason in _POST_ANCHOR_REASONS or (
        reason == "parse_error" and stage == "eligibility"
    ):
        return "post_anchor"
    return "strict_clean"


def _reason(record: Mapping[str, Any]) -> str:
    reason = record.get("primary_exclusion_reason", record.get("reason"))
    if not isinstance(reason, str) or not reason.strip():
        raise FunnelReportError("each exclusion must include a primary reason")
    return reason.strip()


def _required_str(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FunnelReportError(f"{key} must be a non-empty string")
    return value.strip()


def _required_int(record: Mapping[str, Any], key: str) -> int:
    value = record.get(key)
    if type(value) is not int or value < 0:
        raise FunnelReportError(f"{key} must be a non-negative integer")
    return value


def _optional_str(value: object) -> str:
    return value if isinstance(value, str) else ""
