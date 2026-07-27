from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.budgeted_firecrawl import BudgetedFirecrawlScheduler
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit
from legalforecast.ingestion.firecrawl_source import FirecrawlScrapeResult
from legalforecast.ingestion.frozen_batch_firecrawl_observation import (
    FrozenBatchFirecrawlObservationError,
    plan_frozen_firecrawl_observation,
    run_frozen_firecrawl_observation,
    select_frozen_firecrawl_candidates,
)
from legalforecast.ingestion.recap_api_batch_driver import (
    DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
    DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
    direct_search_record_sha256,
    priority_observation_input_record,
)

_BATCH_ID = "priority-batch"
_ANCHOR = "2026-06-30"
_FRONTIER_SHA256 = "f" * 64


def test_observe_firecrawl_help_documents_bounded_resumable_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["batch-002", "observe-firecrawl", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--candidate-id" in output
    assert "--run-id" in output
    assert "--credit-cap" in output
    assert "--workers" in output
    assert "--max-pages-per-docket" in output
    assert "--live-firecrawl" in output
    assert "--firecrawl-fixture" in output


def test_cli_rejects_stale_screening_policy_before_firecrawl_configuration(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _priority_store(tmp_path):
        pass

    def provider_configuration_must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Firecrawl configured before frozen-policy validation")

    monkeypatch.setattr(
        "legalforecast.cli.FirecrawlConfig.from_env",
        provider_configuration_must_not_run,
    )

    assert (
        main(
            [
                "batch-002",
                "observe-firecrawl",
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                _BATCH_ID,
                "--run-id",
                "observe-run",
                "--raw-artifact-dir",
                str(tmp_path / "raw"),
                "--live-firecrawl",
            ]
        )
        == 2
    )
    assert (
        "current screening sources do not match frozen cycle policy"
        in capsys.readouterr().err
    )


def test_cli_rejects_credit_cap_above_documented_ceiling_before_store_or_provider(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def provider_configuration_must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Firecrawl configured for an invalid credit cap")

    monkeypatch.setattr(
        "legalforecast.cli.FirecrawlConfig.from_env",
        provider_configuration_must_not_run,
    )
    store_path = tmp_path / "must-not-be-created.sqlite3"

    assert (
        main(
            [
                "batch-002",
                "observe-firecrawl",
                "--cycle-store",
                str(store_path),
                "--batch-id",
                _BATCH_ID,
                "--run-id",
                "observe-run",
                "--raw-artifact-dir",
                str(tmp_path / "raw"),
                "--credit-cap",
                "45001",
                "--live-firecrawl",
            ]
        )
        == 2
    )
    assert "--credit-cap must not exceed 45000" in capsys.readouterr().err
    assert not store_path.exists()


def test_selection_preserves_frozen_priority_and_ignores_requested_order(
    tmp_path: Path,
) -> None:
    with _priority_store(tmp_path) as store:
        selected = select_frozen_firecrawl_candidates(
            store,
            batch_id=_BATCH_ID,
            requested_candidate_ids=(
                "courtlistener-docket-20",
                "courtlistener-docket-10",
            ),
        )

    assert tuple(candidate.candidate_id for candidate in selected) == (
        "courtlistener-docket-10",
        "courtlistener-docket-20",
    )
    assert tuple(candidate.frozen_ordinal for candidate in selected) == (0, 1)


def test_selection_rejects_terminal_or_unknown_explicit_candidates(
    tmp_path: Path,
) -> None:
    with _priority_store(tmp_path) as store:
        store.record_observation(
            "courtlistener-docket-10",
            batch_id=_BATCH_ID,
            state="excluded",
            reason_code="procedural_or_standing_order",
            evidence={"candidate_id": "courtlistener-docket-10"},
        )

        with pytest.raises(
            FrozenBatchFirecrawlObservationError,
            match="already has a terminal observation",
        ):
            select_frozen_firecrawl_candidates(
                store,
                batch_id=_BATCH_ID,
                requested_candidate_ids=("courtlistener-docket-10",),
            )
        with pytest.raises(
            FrozenBatchFirecrawlObservationError,
            match="is not in frozen batch",
        ):
            select_frozen_firecrawl_candidates(
                store,
                batch_id=_BATCH_ID,
                requested_candidate_ids=("courtlistener-docket-999",),
            )


def test_default_selection_contains_only_candidates_without_current_observations(
    tmp_path: Path,
) -> None:
    with _priority_store(tmp_path) as store:
        store.record_observation(
            "courtlistener-docket-10",
            batch_id=_BATCH_ID,
            state="excluded",
            reason_code="procedural_or_standing_order",
            evidence={"candidate_id": "courtlistener-docket-10"},
        )
        store.record_observation(
            "courtlistener-docket-20",
            batch_id=_BATCH_ID,
            state="transient_failure",
            reason_code="temporarily_unavailable",
            evidence={"candidate_id": "courtlistener-docket-20"},
        )

        selected = select_frozen_firecrawl_candidates(
            store,
            batch_id=_BATCH_ID,
        )

    assert tuple(candidate.candidate_id for candidate in selected) == (
        "courtlistener-docket-20",
    )


def test_new_plan_rejects_explicit_terminal_candidate(tmp_path: Path) -> None:
    with _priority_store(tmp_path) as store:
        store.record_observation(
            "courtlistener-docket-10",
            batch_id=_BATCH_ID,
            state="excluded",
            reason_code="procedural_or_standing_order",
            evidence={"candidate_id": "courtlistener-docket-10"},
        )

        with pytest.raises(
            FrozenBatchFirecrawlObservationError,
            match="already has a terminal observation",
        ):
            _plan(
                store,
                tmp_path,
                requested_candidate_ids=("courtlistener-docket-10",),
            )


def test_selection_fails_closed_when_priority_commitment_drifts(
    tmp_path: Path,
) -> None:
    with _priority_store(
        tmp_path, corrupt_candidate="courtlistener-docket-20"
    ) as store:
        with pytest.raises(
            FrozenBatchFirecrawlObservationError,
            match="ranking record is invalid",
        ):
            select_frozen_firecrawl_candidates(store, batch_id=_BATCH_ID)


def test_incomplete_html_is_transient_and_same_run_resumes_exact_scope(
    tmp_path: Path,
) -> None:
    with _priority_store(tmp_path) as store:
        plan = _plan(
            store,
            tmp_path,
            requested_candidate_ids=("courtlistener-docket-10",),
        )
        store.ensure_firecrawl_run(
            "observe-run",
            batch_id=_BATCH_ID,
            config=plan.run_config,
            credit_cap=100,
            reserved_credits_per_attempt=1,
        )
        source = _HTMLSource("<html><body>not a docket</body></html>")
        tally = run_frozen_firecrawl_observation(
            store,
            batch_id=_BATCH_ID,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=source,
                run_id="observe-run",
                artifact_dir=tmp_path / "raw",
                max_attempts=1,
            ),
            plan=plan,
            eligibility_anchor=date(2026, 6, 30),
            max_pages_per_docket=2,
        )

        assert store.current_observation("courtlistener-docket-10") is None
        [observation] = store.observations("courtlistener-docket-10")
        assert observation.state == "transient_failure"
        assert observation.reason_code == "temporarily_unavailable"
        assert tally.transient_by_reason == {"temporarily_unavailable": 1}

        resumed = _plan(
            store,
            tmp_path,
            requested_candidate_ids=("courtlistener-docket-10",),
        )

    assert resumed.run_config == plan.run_config
    assert tuple(candidate.candidate_id for candidate in resumed.candidates) == (
        "courtlistener-docket-10",
    )


def test_complete_html_uses_canonical_screen_and_records_acceptance(
    tmp_path: Path,
) -> None:
    with _priority_store(tmp_path) as store:
        plan = _plan(
            store,
            tmp_path,
            requested_candidate_ids=("courtlistener-docket-10",),
        )
        store.ensure_firecrawl_run(
            "observe-run",
            batch_id=_BATCH_ID,
            config=plan.run_config,
            credit_cap=100,
            reserved_credits_per_attempt=1,
        )
        tally = run_frozen_firecrawl_observation(
            store,
            batch_id=_BATCH_ID,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=_HTMLSource(_clean_docket_html("10")),
                run_id="observe-run",
                artifact_dir=tmp_path / "raw",
                max_attempts=1,
            ),
            plan=plan,
            eligibility_anchor=date(2026, 6, 30),
            max_pages_per_docket=2,
        )

        observation = store.current_observation("courtlistener-docket-10")

    assert observation is not None
    assert observation.state == "accepted"
    assert observation.reason_code == "strict_clean_screen_passed"
    assert observation.evidence["canonical_firecrawl_screen_complete"] is True
    assert observation.evidence["pagination_proof"]["is_exhaustive"] is True
    assert tally.accepted == 1


def test_driver_rejects_tampered_plan_before_provider_use(tmp_path: Path) -> None:
    with _priority_store(tmp_path) as store:
        plan = _plan(
            store,
            tmp_path,
            requested_candidate_ids=("courtlistener-docket-10",),
        )
        store.ensure_firecrawl_run(
            "observe-run",
            batch_id=_BATCH_ID,
            config=plan.run_config,
            credit_cap=100,
            reserved_credits_per_attempt=1,
        )
        source = _HTMLSource(_clean_docket_html("10"))
        tampered = replace(
            plan,
            run_config={**plan.run_config, "eligibility_anchor": "2026-07-01"},
        )

        with pytest.raises(
            FrozenBatchFirecrawlObservationError,
            match="does not match the durable Firecrawl run",
        ):
            run_frozen_firecrawl_observation(
                store,
                batch_id=_BATCH_ID,
                scheduler=BudgetedFirecrawlScheduler(
                    store=store,
                    source=source,
                    run_id="observe-run",
                    artifact_dir=tmp_path / "raw",
                    max_attempts=1,
                ),
                plan=tampered,
                eligibility_anchor=date(2026, 6, 30),
                max_pages_per_docket=2,
            )

    assert source.calls == 0


def test_adapter_exhausts_older_pages_before_first_disposition_decision(
    tmp_path: Path,
) -> None:
    pages = {
        1: _docket_page_html(
            "10",
            (
                (
                    "10",
                    "July 20, 2026",
                    "MEMORANDUM OPINION AND ORDER granting 5 Motion to Dismiss.",
                ),
                (
                    "5",
                    "June 10, 2026",
                    "Defendant filed Motion to Dismiss Complaint.",
                ),
            ),
            page_number=1,
            has_next=True,
        ),
        2: _docket_page_html(
            "10",
            (
                (
                    "4",
                    "June 29, 2026",
                    "MEMORANDUM OPINION AND ORDER denying 3 Motion to Dismiss.",
                ),
                (
                    "3",
                    "June 5, 2026",
                    "Defendant filed an earlier Motion to Dismiss Complaint.",
                ),
                ("1", "June 1, 2026", "COMPLAINT filed."),
            ),
            page_number=2,
            has_next=False,
        ),
    }
    with _priority_store(tmp_path) as store:
        plan = _plan(
            store,
            tmp_path,
            requested_candidate_ids=("courtlistener-docket-10",),
        )
        store.ensure_firecrawl_run(
            "observe-run",
            batch_id=_BATCH_ID,
            config=plan.run_config,
            credit_cap=100,
            reserved_credits_per_attempt=1,
        )
        source = _PagedHTMLSource(pages)
        tally = run_frozen_firecrawl_observation(
            store,
            batch_id=_BATCH_ID,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=source,
                run_id="observe-run",
                artifact_dir=tmp_path / "raw",
                max_attempts=1,
            ),
            plan=plan,
            eligibility_anchor=date(2026, 6, 30),
            max_pages_per_docket=2,
        )
        observation = store.current_observation("courtlistener-docket-10")

    assert source.requested_pages == [1, 2]
    assert observation is not None
    assert observation.state == "excluded"
    assert observation.reason_code == "decision_before_release_anchor"
    assert tally.excluded_by_reason == {"decision_before_release_anchor": 1}


def test_page_cap_exhaustion_stays_transient(tmp_path: Path) -> None:
    page = _docket_page_html(
        "10",
        (
            (
                "10",
                "July 20, 2026",
                "MEMORANDUM OPINION AND ORDER granting 5 Motion to Dismiss.",
            ),
            (
                "5",
                "June 10, 2026",
                "Defendant filed Motion to Dismiss Complaint.",
            ),
        ),
        page_number=1,
        has_next=True,
    )
    with _priority_store(tmp_path) as store:
        plan = _plan(
            store,
            tmp_path,
            requested_candidate_ids=("courtlistener-docket-10",),
            max_pages_per_docket=1,
        )
        store.ensure_firecrawl_run(
            "observe-run",
            batch_id=_BATCH_ID,
            config=plan.run_config,
            credit_cap=100,
            reserved_credits_per_attempt=1,
        )
        tally = run_frozen_firecrawl_observation(
            store,
            batch_id=_BATCH_ID,
            scheduler=BudgetedFirecrawlScheduler(
                store=store,
                source=_HTMLSource(page),
                run_id="observe-run",
                artifact_dir=tmp_path / "raw",
                max_attempts=1,
            ),
            plan=plan,
            eligibility_anchor=date(2026, 6, 30),
            max_pages_per_docket=1,
        )

        assert store.current_observation("courtlistener-docket-10") is None
        [observation] = store.observations("courtlistener-docket-10")

    assert observation.state == "transient_failure"
    assert observation.evidence["error"] == "pagination_page_limit_reached"
    assert tally.transient_by_reason == {"temporarily_unavailable": 1}


def _plan(
    store: CycleAcquisitionStore,
    tmp_path: Path,
    *,
    requested_candidate_ids: tuple[str, ...],
    max_pages_per_docket: int = 2,
):
    return plan_frozen_firecrawl_observation(
        store,
        batch_id=_BATCH_ID,
        run_id="observe-run",
        eligibility_anchor=date(2026, 6, 30),
        artifact_dir=tmp_path / "raw",
        max_pages_per_docket=max_pages_per_docket,
        max_attempts_per_page=1,
        provider_breaker_threshold=2,
        max_workers=2,
        requested_candidate_ids=requested_candidate_ids,
        firecrawl_proxy="basic",
        firecrawl_force_browser=False,
        reserved_credits_per_attempt=1,
    )


class _HTMLSource:
    def __init__(self, raw_html: str) -> None:
        self.raw_html = raw_html
        self.calls = 0

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        self.calls += 1
        docket_id = source_url.split("/docket/", 1)[1].split("/", 1)[0]
        return FirecrawlScrapeResult(
            source_url=source_url,
            docket_id=docket_id,
            raw_html=self.raw_html,
            target_status_code=200,
            proxy_requested="basic",
            proxy_used="basic",
            cache_state="miss",
            credits_used=1.0,
            raw={"success": True},
            resolved_url=source_url,
        )


class _PagedHTMLSource:
    def __init__(self, pages: dict[int, str]) -> None:
        self.pages = pages
        self.requested_pages: list[int] = []

    def scrape_url(self, *, source_url: str) -> FirecrawlScrapeResult:
        page_number = int(source_url.rsplit("page=", 1)[1])
        self.requested_pages.append(page_number)
        docket_id = source_url.split("/docket/", 1)[1].split("/", 1)[0]
        return FirecrawlScrapeResult(
            source_url=source_url,
            docket_id=docket_id,
            raw_html=self.pages[page_number],
            target_status_code=200,
            proxy_requested="basic",
            proxy_used="basic",
            cache_state="miss",
            credits_used=1.0,
            raw={"success": True},
            resolved_url=source_url,
        )


def _priority_store(
    tmp_path: Path,
    *,
    corrupt_candidate: str | None = None,
) -> CycleAcquisitionStore:
    candidates = (
        _priority_payload("10", structural_rank=0),
        _priority_payload("20", structural_rank=1),
    )
    commitments = {
        str(payload["candidate_id"]): str(
            payload["priority_dedupe_provenance"]["ranking_record_sha256"]  # type: ignore[index]
        )
        for payload in candidates
    }
    if corrupt_candidate is not None:
        commitments[corrupt_candidate] = "0" * 64

    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle(
        {
            "schema_version": "legalforecast.cycle_acquisition_policy.v1",
            "eligibility_anchor": _ANCHOR,
        }
    )
    store.ensure_batch(
        _BATCH_ID,
        {
            "discovery_mode": DIRECT_SEARCH_PRIORITY_TRANCHE_SCHEMA,
            "decision_window_end": "2026-07-27",
            "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
            "deferred_frontier_sha256": _FRONTIER_SHA256,
            "selected_ranking_record_commitments": commitments,
        },
    )
    store.ensure_terms(_BATCH_ID, ("priority",))
    store.commit_search_page(
        _BATCH_ID,
        "priority",
        None,
        tuple(
            DiscoveryHit(
                provider_hit_id=f"hit-{payload['docket_id']}",
                candidate_id=str(payload["candidate_id"]),
                payload=payload,
            )
            for payload in reversed(candidates)
        ),
        next_cursor=None,
        terminal_status="exhausted",
    )
    return store


def _priority_payload(
    docket_id: str,
    *,
    structural_rank: int,
) -> dict[str, object]:
    candidate_id = f"courtlistener-docket-{docket_id}"
    payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "docket_id": docket_id,
        "court_id": "nysd",
        "docket_number": f"1:26-cv-{int(docket_id):05d}",
        "case_name": f"Alpha {docket_id} LLC v. Beta Inc.",
        "prescreen_exclusion_reason": None,
        "decision_entry_evidence": {
            "entry_number": "50",
            "entry_date_filed": "2026-07-20",
            "description": "ORDER granting motion to dismiss",
        },
        "priority_decision_evidence": {
            "entry_number": "50",
            "entry_date_filed": "2026-07-20",
            "description": "ORDER granting motion to dismiss",
        },
    }
    ranking_record: dict[str, object] = {
        "candidate_id": candidate_id,
        "structural_rank": structural_rank,
        "clean_yield_demotion_rank": 0,
        "signal_rank": 0,
        "date_rank": 0,
        "decision_ordinal": 1,
        "free_rank": 0,
        "entry_sort": 50,
        "docket_sort": int(docket_id),
    }
    payload["priority_dedupe_provenance"] = {
        "ranking_policy_sha256": DIRECT_SEARCH_PRIORITY_POLICY_SHA256,
        "frontier_sha256": _FRONTIER_SHA256,
        "observation_priority_input_sha256": direct_search_record_sha256(
            priority_observation_input_record(candidate_id, payload)
        ),
        "ranking_record": ranking_record,
        "ranking_record_sha256": direct_search_record_sha256(ranking_record),
    }
    return payload


def _clean_docket_html(docket_id: str) -> str:
    rows = (
        ("1", "June 1, 2026", "COMPLAINT filed.", "Complaint"),
        (
            "5",
            "June 10, 2026",
            "Defendant filed Motion to Dismiss Complaint.",
            "Motion to Dismiss",
        ),
        (
            "6",
            "June 11, 2026",
            "Memorandum in Support of 5 Motion to Dismiss.",
            "Memorandum in Support",
        ),
        (
            "7",
            "June 20, 2026",
            "Plaintiff response in opposition to 5 Motion to Dismiss.",
            "Response in Opposition",
        ),
        (
            "8",
            "June 25, 2026",
            "Defendant reply in support of 5 Motion to Dismiss.",
            "Reply",
        ),
        (
            "10",
            "July 20, 2026",
            "MEMORANDUM OPINION AND ORDER granting 5 Motion to Dismiss.",
            "Memorandum Opinion and Order",
        ),
    )
    rendered = "".join(
        f"""
        <div id="entry-{number}" class="row">
          <div class="col-xs-1">{number}</div>
          <div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>
          <div class="col-xs-8">{text}
            <div class="row recap-documents"><div>Main Document</div>
              <div>{description}</div>
              <a href="/recap/gov.uscourts.nysd.{docket_id}.{number}.0.pdf">
                Download PDF
              </a>
            </div>
          </div>
        </div>
        """
        for number, filed_at, text, description in rows
    )
    return f"""
    <html><head><title>Alpha {docket_id} LLC v. Beta Inc.</title></head><body>
      <div id="docket-entry-table">{rendered}</div>
    </body></html>
    """


def _docket_page_html(
    docket_id: str,
    rows: tuple[tuple[str, str, str], ...],
    *,
    page_number: int,
    has_next: bool,
) -> str:
    rendered = "".join(
        f"""
        <div id="entry-{number}" class="row">
          <div class="col-xs-1">{number}</div>
          <div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>
          <div class="col-xs-8">{text}</div>
        </div>
        """
        for number, filed_at, text in rows
    )
    next_link = (
        f'<a rel="next" href="?order_by=desc&amp;page={page_number + 1}">Next</a>'
        if has_next
        else ""
    )
    return f"""
    <html><head><title>Alpha {docket_id} LLC v. Beta Inc.</title></head><body>
      <div id="docket-entry-table">{rendered}</div>
      {next_link}
    </body></html>
    """
