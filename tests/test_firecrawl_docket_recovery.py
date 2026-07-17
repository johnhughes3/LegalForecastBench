from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from legalforecast.ingestion.budgeted_docket_acquisition import (
    materialize_selected_slice_batch,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
)
from legalforecast.ingestion.firecrawl_docket_recovery import (
    RankedFirecrawlRecoveryError,
    build_sealed_ranked_firecrawl_artifacts,
    seal_ranked_firecrawl_run,
    validate_fresh_recovery_credit_authority,
)


def test_fresh_recovery_credit_authority_uses_total_prior_commitment() -> None:
    validate_fresh_recovery_credit_authority(
        source_credit_cap=19_939,
        total_prior_authorized_credits=20_000,
        fresh_recovery_credit_cap=0,
        reserved_credits_per_attempt=5,
    )
    validate_fresh_recovery_credit_authority(
        source_credit_cap=19_939,
        total_prior_authorized_credits=20_000,
        fresh_recovery_credit_cap=29_995,
        reserved_credits_per_attempt=5,
    )

    with pytest.raises(
        RankedFirecrawlRecoveryError,
        match="strict combined 50,000-credit ceiling",
    ):
        validate_fresh_recovery_credit_authority(
            source_credit_cap=19_939,
            total_prior_authorized_credits=20_000,
            fresh_recovery_credit_cap=30_000,
            reserved_credits_per_attempt=5,
        )


def test_seal_conserves_complete_terminal_and_unresolved_without_ledger_write(
    tmp_path: Path,
) -> None:
    records = [_record("10", 0), _record("20", 1), _record("30", 2)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=15)
        _succeed(store, tmp_path, docket_id="10", ordinal=0, html=_page("10"))
        _fail_terminal(store, docket_id="20", ordinal=1)
        _fail_transient(store, docket_id="30", ordinal=2)
        targets_before = store.firecrawl_targets("run-001")
        attempts_before = store.firecrawl_attempts("run-001")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        sealed = seal_ranked_firecrawl_run(
            store=store,
            run_id="run-001",
            records=records,
            expected_cycle_hash=cycle_hash,
            expected_run_config_sha256=config_digest,
            expected_credit_cap=15,
            max_pages_per_docket=2,
            decision_anchor=date(2026, 6, 30),
        )

        assert [bundle.docket_id for bundle in sealed.bundles] == ["10"]
        assert [failure.docket_id for failure in sealed.failures] == ["20"]
        assert [item.docket_id for item in sealed.unresolved] == ["30"]
        assert sealed.terminal_docket_ids == ("10", "20")
        assert sealed.unresolved_docket_ids == ("30",)
        assert sealed.source_candidate_count == 3
        assert sealed.provider_activity_requested is False
        assert sealed.provider_activity_executed is False
        artifacts = build_sealed_ranked_firecrawl_artifacts(
            sealed=sealed,
            records=records,
            raw_html_dir=tmp_path / "sealed-raw",
        )
        assert [row["docket_id"] for row in artifacts.successes] == ["10"]
        assert [row["docket_id"] for row in artifacts.exclusions] == ["20"]
        assert [row["docket_id"] for row in artifacts.terminal_manifest] == [
            "10",
            "20",
        ]
        assert [row["docket_id"] for row in artifacts.unresolved_manifest] == ["30"]
        assert set(artifacts.raw_html_by_docket) == {"10"}
        assert store.firecrawl_targets("run-001") == targets_before
        assert store.firecrawl_attempts("run-001") == attempts_before


def test_seal_keeps_successful_partial_pagination_unresolved(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=10)
        _succeed(
            store,
            tmp_path,
            docket_id="10",
            ordinal=0,
            html=_page("10", has_next=True),
        )
        _fail_transient(
            store,
            docket_id="10",
            page_number=2,
            ordinal=1,
            target_error=True,
        )

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        sealed = seal_ranked_firecrawl_run(
            store=store,
            run_id="run-001",
            records=records,
            expected_cycle_hash=cycle_hash,
            expected_run_config_sha256=config_digest,
            expected_credit_cap=10,
            max_pages_per_docket=2,
            decision_anchor=date(2026, 6, 30),
        )

    assert sealed.bundles == ()
    assert sealed.failures == ()
    assert sealed.unresolved_docket_ids == ("10",)
    assert sealed.unresolved[0].required_page_number == 2
    assert sealed.unresolved[0].reason == "retryable_page_incomplete"


def test_seal_rejects_outstanding_authorization(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        url, target_id = _target("10", page_number=1)
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target_id,
            target_kind="docket",
            source_url=url,
            ordinal=0,
        )
        store.authorize_firecrawl_attempt(
            "run-001", target_id=target_id, page_number=1, request_url=url
        )

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="outstanding authorized attempt",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=5,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


def test_seal_rejects_nonexhausted_budget(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=10)
        _fail_transient(store, docket_id="10", ordinal=0)

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="budget is not exhausted",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=10,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


def test_seal_rejects_tampered_success_artifact(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        _succeed(store, tmp_path, docket_id="10", ordinal=0, html=_page("10"))
    (tmp_path / "fixture-raw" / "10-page-1.html").write_text("tampered")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match=r"artifact byte count mismatch",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=5,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


@pytest.mark.parametrize("alias_kind", ("outside", "symlink", "hardlink"))
def test_seal_rejects_success_artifact_outside_or_aliased_from_frozen_root(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        _succeed(store, tmp_path, docket_id="10", ordinal=0, html=_page("10"))
    original = tmp_path / "fixture-raw" / "10-page-1.html"
    if alias_kind == "outside":
        alias = tmp_path / "outside.html"
        alias.write_bytes(original.read_bytes())
    elif alias_kind == "symlink":
        alias = tmp_path / "fixture-raw" / "symlink.html"
        alias.symlink_to(original)
    else:
        alias = tmp_path / "fixture-raw" / "hardlink.html"
        alias.hardlink_to(original)
    with sqlite3.connect(store_path) as connection:
        connection.execute(
            "UPDATE firecrawl_attempts SET artifact_path = ? WHERE run_id = ?",
            (str(alias), "run-001"),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="frozen raw artifact root",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=5,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


def test_seal_leaves_incompletely_evidenced_terminal_target_unresolved(
    tmp_path: Path,
) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        url, target_id = _target("10", page_number=1)
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target_id,
            target_kind="docket",
            source_url=url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-001", target_id=target_id, page_number=1, request_url=url
        )
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="target_error",
            failure_code="target_http_status_invalid",
            failure_message="target failed without complete response evidence",
            failure_transient=False,
        )
        store.set_firecrawl_target_status("run-001", target_id, "terminal_error")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        sealed = seal_ranked_firecrawl_run(
            store=store,
            run_id="run-001",
            records=records,
            expected_cycle_hash=cycle_hash,
            expected_run_config_sha256=config_digest,
            expected_credit_cap=5,
            max_pages_per_docket=2,
            decision_anchor=date(2026, 6, 30),
        )

    assert sealed.failures == ()
    assert sealed.unresolved_docket_ids == ("10",)


def test_seal_leaves_target_http_503_unresolved(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        url, target_id = _target("10", page_number=1)
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target_id,
            target_kind="docket",
            source_url=url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "run-001", target_id=target_id, page_number=1, request_url=url
        )
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="target_error",
            reported_credits=5,
            proxy_used="stealth",
            provider_http_status=200,
            target_http_status=503,
            failure_code="target_http_status_invalid",
            failure_message="target returned HTTP 503",
            failure_transient=False,
            failure_response_sha256="3" * 64,
        )
        store.set_firecrawl_target_status("run-001", target_id, "terminal_error")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        sealed = seal_ranked_firecrawl_run(
            store=store,
            run_id="run-001",
            records=records,
            expected_cycle_hash=cycle_hash,
            expected_run_config_sha256=config_digest,
            expected_credit_cap=5,
            max_pages_per_docket=2,
            decision_anchor=date(2026, 6, 30),
        )

    assert sealed.failures == ()
    assert sealed.unresolved_docket_ids == ("10",)


def test_seal_leaves_retry_exhaustion_with_incomplete_evidence_unresolved(
    tmp_path: Path,
) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=15)
        url, target_id = _target("10", page_number=1)
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target_id,
            target_kind="docket",
            source_url=url,
            ordinal=0,
        )
        for _ in range(3):
            attempt = store.authorize_firecrawl_attempt(
                "run-001", target_id=target_id, page_number=1, request_url=url
            )
            store.finalize_firecrawl_attempt(
                attempt.attempt_id,
                status="target_error",
                reported_credits=5,
                proxy_used="stealth",
                provider_http_status=200,
                target_http_status=202,
                failure_code="target_http_status_retryable",
                failure_message="target returned retryable HTTP 202",
                failure_transient=True,
                failure_response_sha256="4" * 64,
            )
        store.set_firecrawl_target_status("run-001", target_id, "retry_exhausted")
    with sqlite3.connect(store_path) as connection:
        connection.execute(
            "UPDATE firecrawl_attempts SET failure_message = NULL "
            "WHERE attempt_id = (SELECT MAX(attempt_id) FROM firecrawl_attempts)"
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        sealed = seal_ranked_firecrawl_run(
            store=store,
            run_id="run-001",
            records=records,
            expected_cycle_hash=cycle_hash,
            expected_run_config_sha256=config_digest,
            expected_credit_cap=15,
            max_pages_per_docket=2,
            decision_anchor=date(2026, 6, 30),
        )

    assert sealed.failures == ()
    assert sealed.unresolved_docket_ids == ("10",)


def test_seal_rejects_attempts_beyond_frozen_max(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=20)
        url, target_id = _target("10", page_number=1)
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target_id,
            target_kind="docket",
            source_url=url,
            ordinal=0,
        )
        for _ in range(4):
            attempt = store.authorize_firecrawl_attempt(
                "run-001", target_id=target_id, page_number=1, request_url=url
            )
            store.finalize_firecrawl_attempt(
                attempt.attempt_id,
                status="provider_error",
                provider_http_status=500,
                failure_code="provider_server_error",
                failure_message="provider returned HTTP 500",
                failure_transient=True,
                failure_response_sha256="2" * 64,
            )
        store.set_firecrawl_target_status("run-001", target_id, "in_progress")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="exceeds frozen max-attempt authority",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=20,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


def test_seal_rejects_attempt_reservation_drift_that_fakes_exhaustion(
    tmp_path: Path,
) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=15)
        url, target_id = _target("10", page_number=1)
        store.ensure_firecrawl_target(
            "run-001",
            target_id=target_id,
            target_kind="docket",
            source_url=url,
            ordinal=0,
        )
        for _ in range(3):
            attempt = store.authorize_firecrawl_attempt(
                "run-001", target_id=target_id, page_number=1, request_url=url
            )
            store.finalize_firecrawl_attempt(
                attempt.attempt_id,
                status="provider_error",
                provider_http_status=500,
                failure_code="provider_server_error",
                failure_message="provider returned HTTP 500",
                failure_transient=True,
                failure_response_sha256="2" * 64,
            )
        store.set_firecrawl_target_status("run-001", target_id, "in_progress")
    with sqlite3.connect(store_path) as connection:
        connection.execute(
            "UPDATE firecrawl_attempts SET reserved_credits = 4 WHERE run_id = ?",
            ("run-001",),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="reservation differs from frozen authority",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=15,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


@pytest.mark.parametrize("reported_credits", (-1, 6))
def test_seal_rejects_invalid_reported_credits(
    tmp_path: Path,
    reported_credits: int | None,
) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        _fail_terminal(store, docket_id="10", ordinal=0)
    with sqlite3.connect(store_path) as connection:
        connection.execute(
            "UPDATE firecrawl_attempts SET reported_credits = ? WHERE run_id = ?",
            (reported_credits, "run-001"),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="reported credits are invalid",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=5,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


def test_seal_rejects_success_without_reported_credits(tmp_path: Path) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        _succeed(store, tmp_path, docket_id="10", ordinal=0, html=_page("10"))
    with sqlite3.connect(store_path) as connection:
        connection.execute(
            "UPDATE firecrawl_attempts SET reported_credits = NULL WHERE run_id = ?",
            ("run-001",),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(
            RankedFirecrawlRecoveryError,
            match="reported credits are invalid",
        ):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=5,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    (
        ("target_status", "mystery", "unknown status"),
        ("completed_at", None, "unknown or outstanding request"),
    ),
)
def test_seal_rejects_corrupt_terminal_ledger_metadata(
    tmp_path: Path,
    column: str,
    value: str | None,
    message: str,
) -> None:
    records = [_record("10", 0)]
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash, config_digest = _run(store, records=records, credit_cap=5)
        _fail_transient(store, docket_id="10", ordinal=0)
    with sqlite3.connect(store_path) as connection:
        if column == "target_status":
            connection.execute(
                "UPDATE firecrawl_targets SET status = ? WHERE run_id = ?",
                (value, "run-001"),
            )
        else:
            connection.execute(
                "UPDATE firecrawl_attempts SET completed_at = ? WHERE run_id = ?",
                (value, "run-001"),
            )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    with CycleAcquisitionStore(store_path, read_only=True) as store:
        with pytest.raises(RankedFirecrawlRecoveryError, match=message):
            seal_ranked_firecrawl_run(
                store=store,
                run_id="run-001",
                records=records,
                expected_cycle_hash=cycle_hash,
                expected_run_config_sha256=config_digest,
                expected_credit_cap=5,
                max_pages_per_docket=2,
                decision_anchor=date(2026, 6, 30),
            )


def _run(
    store: CycleAcquisitionStore,
    *,
    records: list[dict[str, object]],
    credit_cap: int,
) -> tuple[str, str]:
    (store.path.parent / "fixture-raw").mkdir(exist_ok=True)
    cycle_hash = store.ensure_cycle({"anchor": "2026-06-30T00:00:00Z"})
    store.ensure_batch("parent", {"source": "fixture"})
    store.ensure_terms("parent", ("motion to dismiss",))
    store.commit_search_page(
        "parent",
        "motion to dismiss",
        None,
        tuple(
            DiscoveryHit(
                provider_hit_id=f"hit-{docket_id}",
                candidate_id=f"courtlistener-docket-{docket_id}",
                payload={"docket_id": docket_id},
            )
            for docket_id in ("10", "20", "30")[: len(records)]
        ),
        next_cursor=None,
        terminal_status="exhausted",
    )
    materialize_selected_slice_batch(
        store=store,
        parent_batch_id="parent",
        selected_batch_id="selected",
        records=records,
        limit=len(records),
    )
    config = {
        "purpose": "ranked-complete-docket-acquisition",
        "decision_anchor": "2026-06-30",
        "max_pages_per_docket": 2,
        "raw_artifact_root": str((store.path.parent / "fixture-raw").resolve()),
        "firecrawl_proxy": "enhanced",
        "firecrawl_force_browser": True,
        "firecrawl_max_credits_per_scrape": 5,
        "workers": 10,
        "max_attempts_per_page": 3,
        "provider_breaker_threshold": 5,
        "target_http_pressure_policy_version": (
            "courtlistener-target-http-202-aimd-v1"
        ),
    }
    config_digest = store.ensure_firecrawl_run(
        "run-001",
        batch_id="selected",
        config=config,
        credit_cap=credit_cap,
        reserved_credits_per_attempt=5,
    )
    return cycle_hash, config_digest


def _succeed(
    store: CycleAcquisitionStore,
    tmp_path: Path,
    *,
    docket_id: str,
    ordinal: int,
    html: str,
) -> None:
    url, target_id = _target(docket_id, page_number=1)
    store.ensure_firecrawl_target(
        "run-001",
        target_id=target_id,
        target_kind="docket",
        source_url=url,
        ordinal=ordinal,
    )
    attempt = store.authorize_firecrawl_attempt(
        "run-001", target_id=target_id, page_number=1, request_url=url
    )
    store.commit_firecrawl_artifact(
        attempt.attempt_id,
        tmp_path / "fixture-raw" / f"{docket_id}-page-1.html",
        html.encode(),
        reported_credits=5,
        proxy_used="stealth",
        target_http_status=200,
    )


def _fail_terminal(
    store: CycleAcquisitionStore,
    *,
    docket_id: str,
    ordinal: int,
) -> None:
    url, target_id = _target(docket_id, page_number=1)
    store.ensure_firecrawl_target(
        "run-001",
        target_id=target_id,
        target_kind="docket",
        source_url=url,
        ordinal=ordinal,
    )
    attempt = store.authorize_firecrawl_attempt(
        "run-001", target_id=target_id, page_number=1, request_url=url
    )
    store.finalize_firecrawl_attempt(
        attempt.attempt_id,
        status="target_error",
        reported_credits=5,
        proxy_used="stealth",
        provider_http_status=200,
        target_http_status=404,
        failure_code="target_http_status_invalid",
        failure_message="target returned terminal HTTP 404",
        failure_transient=False,
        failure_response_sha256="1" * 64,
    )
    store.set_firecrawl_target_status("run-001", target_id, "terminal_error")


def _fail_transient(
    store: CycleAcquisitionStore,
    *,
    docket_id: str,
    ordinal: int,
    page_number: int = 1,
    target_error: bool = False,
) -> None:
    url, target_id = _target(docket_id, page_number=page_number)
    store.ensure_firecrawl_target(
        "run-001",
        target_id=target_id,
        target_kind="docket",
        source_url=url,
        ordinal=ordinal,
    )
    attempt = store.authorize_firecrawl_attempt(
        "run-001",
        target_id=target_id,
        page_number=page_number,
        request_url=url,
    )
    if target_error:
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="target_error",
            reported_credits=5,
            proxy_used="stealth",
            provider_http_status=200,
            target_http_status=202,
            failure_code="target_http_status_retryable",
            failure_message="target returned retryable HTTP 202",
            failure_transient=True,
            failure_response_sha256="2" * 64,
        )
    else:
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="provider_error",
            provider_http_status=500,
            failure_code="provider_server_error",
            failure_message="provider returned HTTP 500",
            failure_transient=True,
            failure_response_sha256="2" * 64,
        )
    store.set_firecrawl_target_status("run-001", target_id, "in_progress")


def _record(docket_id: str, rank: int) -> dict[str, object]:
    return {
        "identity": {
            "courtlistener_docket_id": docket_id,
            "courtlistener_url": (
                f"https://www.courtlistener.com/docket/{docket_id}/fixture-case/"
            ),
        },
        "screening_metadata": {"case_name": f"Fixture {docket_id}"},
        "ranking_key": [rank, 3, docket_id],
    }


def _target(docket_id: str, *, page_number: int) -> tuple[str, str]:
    url = (
        f"https://www.courtlistener.com/docket/{docket_id}/fixture-case/"
        f"?order_by=desc&page={page_number}"
    )
    target_id = (
        "docket-"
        + hashlib.sha256(f"{docket_id}:{page_number}".encode()).hexdigest()[:24]
    )
    return url, target_id


def _page(docket_id: str, *, has_next: bool = False) -> str:
    next_link = (
        '<a rel="next" href="?order_by=desc&amp;page=2">Next</a>' if has_next else ""
    )
    return f"""
    <html><head><title>Fixture {docket_id}</title></head><body>
      <div id="docket-entry-table">
        <div id="entry-{docket_id}-1" class="row">
          <div class="col-xs-1">1</div>
          <div class="col-xs-3"><span title="July 10, 2026">July 10, 2026</span></div>
          <div class="col-xs-8">Order on motion to dismiss.</div>
        </div>
      </div>
      {next_link}
    </body></html>
    """
