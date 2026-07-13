from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.cli import build_parser
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.docket_live_fetch import (
    DocketLiveFetchJournal,
    DocketLiveFetchReconciliationRequired,
    execute_docket_live_fetch_plan,
    plan_docket_live_fetches,
)


def test_planner_requires_cited_anchored_disposition_and_ranks_coverage(
    tmp_path: Path,
) -> None:
    first = _html(
        "11",
        "Jul 8, 2026",
        "ORDER granting 7 Motion to Dismiss.",
    )
    second = _html(
        "22",
        "Jul 9, 2026",
        "ORDER denying 9 Motion for Judgment on the Pleadings.",
    )
    stale = _html(
        "33",
        "Jun 29, 2026",
        "ORDER granting 4 Motion to Dismiss.",
    )
    paths = []
    for docket_id, body in (("100", first), ("200", second), ("300", stale)):
        path = tmp_path / f"{docket_id}.html"
        path.write_text(body)
        paths.append((docket_id, path))

    plan = plan_docket_live_fetches(
        screening_records=[
            _exclusion("100", "entry-11", "2026-07-08"),
            _exclusion("200", "entry-22", "2026-07-09"),
            _exclusion("300", "entry-33", "2026-06-29"),
            _exclusion("400", "entry-44", "2026-07-10", reason="criminal_posture"),
        ],
        fetch_success_records=[_fetch(docket_id, path) for docket_id, path in paths],
        ranking_records=[
            _ranking("100", free=1, missing=2, entries=4),
            _ranking("200", free=2, missing=1, entries=8),
        ],
        cohort_policy=_policy(),
        docket_fetch_reservation_usd="3.05",
    )

    assert [item.docket_id for item in plan.items] == ["200", "100"]
    assert plan.total_projected_cost_usd == "6.10"
    assert plan.to_record()["frontier"] == [
        {"selected_count": 0, "projected_spend_usd": "0.00"},
        {"selected_count": 1, "projected_spend_usd": "3.05"},
        {"selected_count": 2, "projected_spend_usd": "6.10"},
    ]
    assert plan.items[0].decision_entry_ids == ("entry-22",)
    assert plan.items[0].existing_free_required_document_count == 2
    assert plan.policy_sha256 == "a" * 64


def test_executor_journals_before_one_fee_bearing_post_and_replays_confirmation(
    tmp_path: Path,
) -> None:
    html = tmp_path / "100.html"
    html.write_text(_html("11", "Jul 8, 2026", "ORDER granting 7 Motion to Dismiss."))
    ledger = tmp_path / "docket-live-fetch.sqlite3"
    plan = plan_docket_live_fetches(
        screening_records=[_exclusion("100", "entry-11", "2026-07-08")],
        fetch_success_records=[_fetch("100", html)],
        ranking_records=[],
        cohort_policy=_policy(),
        docket_fetch_reservation_usd="3.05",
        canonical_journal_path=str(ledger.resolve()),
    )
    response = {
        "type": "lookup",
        "live": True,
        "docket": {"id": "100", "caseName": "Example", "courtId": "nysd"},
        "pacerFees": {"serviceFee": 0.05, "maxPacerCost": 3.00},
    }
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={
                    "type": "lookup",
                    "docketId": "100",
                    "live": True,
                    "acknowledgePacerFees": True,
                },
                status_code=200,
                payload=response,
            )
        ]
    )
    client = _client(transport)

    result = execute_docket_live_fetch_plan(
        plan,
        client=client,
        journal_path=ledger,
        live=True,
        acknowledge_pacer_fees=True,
    )
    replay = execute_docket_live_fetch_plan(
        plan,
        client=client,
        journal_path=ledger,
        live=True,
        acknowledge_pacer_fees=True,
    )

    assert result.confirmed_count == 1
    assert replay.confirmed_count == 1
    assert len(transport.requests) == 1
    with DocketLiveFetchJournal(ledger, plan=plan) as journal:
        assert journal.statuses() == {"100": "confirmed"}


def test_advisory_input_is_a_filter_but_cannot_replace_persisted_evidence(
    tmp_path: Path,
) -> None:
    paths = []
    for docket_id, entry in (("100", "11"), ("200", "22")):
        path = tmp_path / f"{docket_id}.html"
        path.write_text(
            _html(entry, "Jul 8, 2026", "ORDER granting 7 Motion to Dismiss.")
        )
        paths.append((docket_id, path))

    plan = plan_docket_live_fetches(
        screening_records=[
            _exclusion("100", "entry-11", "2026-07-08"),
            _exclusion("200", "entry-22", "2026-07-08"),
        ],
        fetch_success_records=[_fetch(docket_id, path) for docket_id, path in paths],
        ranking_records=[],
        advisory_records=[
            {
                "candidate_id": "courtlistener-docket-100",
                "recovery_class": "high_confidence",
                "decision_date": "2026-07-08",
                "decision_entry_ids": ["entry-11"],
                "actual_free_required_document_count": 2,
                "missing_required_document_count": 1,
                "docket_entry_count": 4,
            },
            {
                "candidate_id": "courtlistener-docket-200",
                "recovery_class": "manual_review",
                "decision_date": "2026-07-08",
                "decision_entry_ids": ["entry-22"],
            },
        ],
        cohort_policy=_policy(),
    )

    assert [item.docket_id for item in plan.items] == ["100"]
    assert plan.items[0].existing_missing_required_document_count == 1


def test_ambiguous_paid_post_retains_reservation_and_resume_refuses_reissue(
    tmp_path: Path,
) -> None:
    html = tmp_path / "100.html"
    html.write_text(_html("11", "Jul 8, 2026", "ORDER denying 7 Motion to Dismiss."))
    ledger = tmp_path / "docket-live-fetch.sqlite3"
    plan = plan_docket_live_fetches(
        screening_records=[_exclusion("100", "entry-11", "2026-07-08")],
        fetch_success_records=[_fetch("100", html)],
        ranking_records=[],
        cohort_policy=_policy(),
        docket_fetch_reservation_usd="3.05",
        canonical_journal_path=str(ledger.resolve()),
    )
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={
                    "type": "lookup",
                    "docketId": "100",
                    "live": True,
                    "acknowledgePacerFees": True,
                },
                status_code=503,
                payload={"error": "provider uncertain"},
            )
        ]
    )

    with pytest.raises(Exception, match="provider uncertain"):
        execute_docket_live_fetch_plan(
            plan,
            client=_client(transport),
            journal_path=ledger,
            live=True,
            acknowledge_pacer_fees=True,
        )
    with pytest.raises(DocketLiveFetchReconciliationRequired):
        execute_docket_live_fetch_plan(
            plan,
            client=_client(transport),
            journal_path=ledger,
            live=True,
            acknowledge_pacer_fees=True,
        )

    assert len(transport.requests) == 1
    with DocketLiveFetchJournal(ledger, plan=plan) as journal:
        assert journal.statuses() == {"100": "unknown"}
        assert journal.committed_reservation_usd == "3.05"


def test_executor_requires_both_live_and_fee_acknowledgment_without_request(
    tmp_path: Path,
) -> None:
    html = tmp_path / "100.html"
    html.write_text(_html("11", "Jul 8, 2026", "ORDER denying 7 Motion to Dismiss."))
    ledger = tmp_path / "journal.sqlite3"
    plan = plan_docket_live_fetches(
        screening_records=[_exclusion("100", "entry-11", "2026-07-08")],
        fetch_success_records=[_fetch("100", html)],
        ranking_records=[],
        cohort_policy=_policy(),
        docket_fetch_reservation_usd="3.05",
        canonical_journal_path=str(ledger.resolve()),
    )
    transport = CaseDevFixtureTransport([])

    with pytest.raises(ValueError, match="live docket fetch and fee acknowledgment"):
        execute_docket_live_fetch_plan(
            plan,
            client=_client(transport),
            journal_path=ledger,
            live=False,
            acknowledge_pacer_fees=True,
        )

    assert transport.requests == []


def test_cli_exposes_separate_no_provider_plan_and_guarded_execute_commands() -> None:
    parser = build_parser()
    planned = parser.parse_args(
        [
            "acquisition",
            "plan-docket-live-fetches",
            "--output-root",
            "out",
            "--screening-candidates",
            "screen.jsonl",
            "--fetch-successes",
            "fetch.jsonl",
            "--cohort-policy",
            "policy.json",
        ]
    )
    executed = parser.parse_args(
        [
            "acquisition",
            "execute-docket-live-fetches",
            "--output-root",
            "out",
            "--docket-live-fetch-plan",
            "plan.json",
        ]
    )

    assert planned.execute is False
    assert executed.execute is False
    assert executed.live_case_dev is False
    assert executed.acknowledge_pacer_fees is False


def _client(transport: CaseDevFixtureTransport) -> CaseDevClient:
    return CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=transport,
        max_retries=8,
    )


def _html(entry: str, filed: str, text: str) -> str:
    return (
        "<html><head><title>Example v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        f'<div id="entry-{entry}" class="row"><div class="col-xs-1">{entry}</div>'
        f'<div class="col-xs-3"><span title="{filed}">{filed}</span></div>'
        f'<div class="col-xs-8">{text}</div></div>'
        "</div></body></html>"
    )


def _exclusion(
    docket_id: str,
    entry_id: str,
    decision_date: str,
    *,
    reason: str = "no_target_motion",
) -> dict[str, object]:
    return {
        "candidate_id": f"courtlistener-docket-{docket_id}",
        "state": "excluded",
        "evidence": {
            "reason": reason,
            "decision_date": decision_date,
            "source_entry_ids": [entry_id],
        },
    }


def _fetch(docket_id: str, path: Path) -> dict[str, object]:
    return {
        "candidate_id": f"courtlistener-docket-{docket_id}",
        "docket_id": docket_id,
        "raw_html_path": str(path),
        "source_url": f"https://www.courtlistener.com/docket/{docket_id}/example/",
    }


def _ranking(
    docket_id: str, *, free: int, missing: int, entries: int
) -> dict[str, object]:
    return {
        "identity": {"courtlistener_docket_id": docket_id},
        "actual_free_required_document_count": free,
        "missing_required_document_count": missing,
        "docket_entry_count": entries,
    }


def _policy() -> dict[str, object]:
    # Planner verifies the artifact through the production policy validator in
    # CLI integration; the pure unit accepts a pre-verified policy record.
    return {
        "policy_sha256": "a" * 64,
        "policy": {
            "cycle_id": "cycle-1",
            "eligibility_anchor": "2026-06-30",
            "purchase_policy": {
                "cycle_budget_usd": "2250.00",
                "max_per_case_usd": "73.20",
            },
        },
    }
