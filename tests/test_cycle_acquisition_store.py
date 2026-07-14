from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest
from legalforecast.ingestion.cycle_acquisition_store import (
    ConfigMismatchError,
    CycleAcquisitionStore,
    CycleAcquisitionStoreError,
    FirecrawlBudgetExceededError,
    ImmutableArtifactError,
    ImmutableCandidateStateError,
    PageReplayMismatchError,
    SnapshotVerificationError,
    StoreLockedError,
    verify_snapshot,
)

POLICY = {
    "anchor": "2026-06-30T00:00:00Z",
    "query_terms": ["motion to dismiss", "dismissed"],
    "screen_hash": "screen-v1",
    "schema": 1,
}


def _store(tmp_path: Path) -> CycleAcquisitionStore:
    store = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    store.ensure_cycle(POLICY)
    store.ensure_batch("batch-001", {"start": "2026-06-30", "page_size": 50})
    return store


def _hit(provider_hit_id: str, candidate_id: str) -> dict[str, object]:
    return {
        "provider_hit_id": provider_hit_id,
        "candidate_id": candidate_id,
        "payload": {"id": provider_hit_id, "candidate": candidate_id},
    }


def _discover_candidates(
    store: CycleAcquisitionStore,
    *candidate_ids: str,
    batch_id: str = "batch-001",
) -> None:
    store.ensure_terms(batch_id, ["test-setup"])
    store.commit_search_page(
        batch_id,
        "test-setup",
        None,
        [
            _hit(f"setup-{index}", candidate_id)
            for index, candidate_id in enumerate(candidate_ids, start=1)
        ],
        next_cursor=None,
        terminal_status="exhausted",
    )


def _rewrite_snapshot_jsonl(
    snapshot: Path, filename: str, records: list[dict[str, object]]
) -> None:
    payload = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )
    (snapshot / filename).write_bytes(payload)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][filename] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": len(records),
    }
    manifest_path.write_text(json.dumps(manifest))


def test_cycle_and_batch_config_identity_fail_closed(tmp_path: Path) -> None:
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        cycle_hash = store.ensure_cycle(POLICY)
        assert cycle_hash == store.ensure_cycle(dict(POLICY))
        with pytest.raises(ConfigMismatchError, match="cycle policy"):
            store.ensure_cycle({**POLICY, "anchor": "2026-07-01T00:00:00Z"})

        digest = store.ensure_batch("batch-001", {"page_size": 50})
        assert digest == store.ensure_batch("batch-001", {"page_size": 50})
        with pytest.raises(ConfigMismatchError, match="batch-001"):
            store.ensure_batch("batch-001", {"page_size": 100})
        assert store.ensure_batch("batch-002", {"page_size": 100}) != digest


def test_source_neutral_cycle_policy_upgrade_preserves_credit_authorizations(
    tmp_path: Path,
) -> None:
    legacy_policy = {
        "schema_version": "legalforecast.firecrawl_recap_discovery_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "observation_window_end": "2026-07-12",
        "discovery_source": "courtlistener_recap_entry_search_via_firecrawl",
        "query_terms": ["motion to dismiss"],
        "query_term_order_is_frozen": True,
        "screening_source_sha256": {"screen": "abc123"},
    }
    canonical_policy = {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "screening_source_sha256": {"screen": "abc123"},
    }
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        legacy_hash = store.ensure_cycle(legacy_policy)
        store.ensure_batch("legacy-batch", {"provider": "firecrawl"})
        store.ensure_firecrawl_run(
            "legacy-run",
            batch_id="legacy-batch",
            config={"proxy": "enhanced"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "legacy-run",
            target_id="search-page-1",
            target_kind="search",
            source_url="https://www.courtlistener.com/?type=r&q=alpha",
            ordinal=0,
        )
        store.authorize_firecrawl_attempt(
            "legacy-run",
            target_id="search-page-1",
            page_number=1,
            request_url="https://www.courtlistener.com/?type=r&q=alpha",
        )

        canonical_hash = store.ensure_cycle(canonical_policy)

        assert canonical_hash != legacy_hash
        assert store.cycle_policy == canonical_policy
        assert store.firecrawl_run_summary("legacy-run")["reserved_credits"] == 5
        assert store.ensure_batch("new-batch", {"provider": "case.dev"})
        migrated = store._connection.execute(
            "SELECT old_policy_hash, new_policy_hash FROM cycle_policy_migrations"
        ).fetchone()
        assert tuple(migrated) == (legacy_hash, canonical_hash)


def test_cycle_policy_upgrade_refuses_after_snapshot_publication(
    tmp_path: Path,
) -> None:
    legacy_policy = {
        "schema_version": "legalforecast.case_dev_discovery_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "query_terms": ["motion to dismiss"],
        "query_term_order_is_frozen": True,
        "screening_source_sha256": {"screen": "abc123"},
    }
    canonical_policy = {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "screening_source_sha256": {"screen": "abc123"},
    }
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        store.ensure_cycle(legacy_policy)
        store.ensure_batch("batch-001", {"provider": "case.dev"})
        store.ensure_terms("batch-001", ["motion to dismiss"])
        store.commit_search_page(
            "batch-001",
            "motion to dismiss",
            None,
            [],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.export_snapshot(
            tmp_path / "snapshots",
            snapshot_id="legacy-checkpoint",
            batch_id="batch-001",
            complete=False,
        )

        with pytest.raises(ConfigMismatchError, match="published snapshot"):
            store.ensure_cycle(canonical_policy)


def test_firecrawl_run_freezes_config_and_permanently_reserves_budget(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        digest = store.ensure_firecrawl_run(
            "firecrawl-001",
            batch_id="batch-001",
            config={"proxy": "auto", "anchor": "2026-06-30"},
            credit_cap=10,
            reserved_credits_per_attempt=5,
        )
        assert digest == store.ensure_firecrawl_run(
            "firecrawl-001",
            batch_id="batch-001",
            config={"anchor": "2026-06-30", "proxy": "auto"},
            credit_cap=10,
            reserved_credits_per_attempt=5,
        )
        with pytest.raises(ConfigMismatchError, match="firecrawl-001"):
            store.ensure_firecrawl_run(
                "firecrawl-001",
                batch_id="batch-001",
                config={"proxy": "basic", "anchor": "2026-06-30"},
                credit_cap=10,
                reserved_credits_per_attempt=5,
            )

        store.ensure_firecrawl_target(
            "firecrawl-001",
            target_id="docket-123",
            target_kind="docket",
            source_url=(
                "https://www.courtlistener.com/docket/123/fixture/?order_by=desc&page=1"
            ),
            ordinal=0,
        )
        first = store.authorize_firecrawl_attempt(
            "firecrawl-001",
            target_id="docket-123",
            page_number=1,
            request_url=(
                "https://www.courtlistener.com/docket/123/fixture/?order_by=desc&page=1"
            ),
        )
        assert first.attempt_number == 1
        assert first.reserved_credits == 5
        store.finalize_firecrawl_attempt(
            first.attempt_id,
            status="provider_error",
            provider_http_status=500,
            failure_code="provider_server_error",
            failure_message="Firecrawl server failure",
            failure_transient=True,
            failure_response_sha256="a" * 64,
        )
        failed = store.firecrawl_attempt(first.attempt_id)
        assert failed.failure_code == "provider_server_error"
        assert failed.failure_message == "Firecrawl server failure"
        assert failed.failure_transient is True
        assert failed.failure_response_sha256 == "a" * 64
        second = store.authorize_firecrawl_attempt(
            "firecrawl-001",
            target_id="docket-123",
            page_number=1,
            request_url=(
                "https://www.courtlistener.com/docket/123/fixture/?order_by=desc&page=1"
            ),
        )
        store.finalize_firecrawl_attempt(
            second.attempt_id,
            status="succeeded",
            reported_credits=5,
            proxy_used="enhanced",
        )
        summary = store.firecrawl_run_summary("firecrawl-001")
        assert summary["config_digest"] == digest
        assert summary["credit_cap"] == 10
        assert summary["reserved_credits"] == 10
        assert summary["reported_credits"] == 5
        assert summary["run_reserved_credits"] == 10
        assert summary["run_reported_credits"] == 5
        assert summary["remaining_authorization"] == 0
        assert summary["attempt_status_counts"] == {
            "provider_error": 1,
            "succeeded": 1,
        }
        with pytest.raises(FirecrawlBudgetExceededError, match="credit cap"):
            store.authorize_firecrawl_attempt(
                "firecrawl-001",
                target_id="docket-123",
                page_number=2,
                request_url=(
                    "https://www.courtlistener.com/docket/123/fixture/"
                    "?order_by=desc&page=2"
                ),
            )


def test_firecrawl_attempt_validation_is_fail_closed(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.ensure_firecrawl_run(
            "firecrawl-001",
            batch_id="batch-001",
            config={"proxy": "auto"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "firecrawl-001",
            target_id="search-alpha",
            target_kind="search",
            source_url="https://www.courtlistener.com/?type=r&q=alpha",
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "firecrawl-001",
            target_id="search-alpha",
            page_number=1,
            request_url="https://www.courtlistener.com/?type=r&q=alpha",
        )
        with pytest.raises(ValueError, match="reported_credits"):
            store.finalize_firecrawl_attempt(
                attempt.attempt_id,
                status="succeeded",
                reported_credits=6,
                proxy_used="enhanced",
            )
        assert store.firecrawl_attempt(attempt.attempt_id).status == "authorized"

        with pytest.raises(ConfigMismatchError, match="target"):
            store.ensure_firecrawl_target(
                "firecrawl-001",
                target_id="search-alpha",
                target_kind="search",
                source_url="https://www.courtlistener.com/?type=r&q=changed",
                ordinal=0,
            )


def test_existing_cycle_store_adds_failure_evidence_columns_in_place(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cycle.sqlite3"
    CycleAcquisitionStore(path).close()
    with sqlite3.connect(path) as connection:
        for column in (
            "failure_response_sha256",
            "failure_transient",
            "failure_message",
            "failure_code",
        ):
            connection.execute(f"ALTER TABLE firecrawl_attempts DROP COLUMN {column}")

    CycleAcquisitionStore(path).close()

    with sqlite3.connect(path) as connection:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(firecrawl_attempts)")
        }
    assert {
        "failure_code",
        "failure_message",
        "failure_transient",
        "failure_response_sha256",
    } <= columns


def test_firecrawl_credit_cap_is_aggregate_across_runs(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        for ordinal, run_id in enumerate(("search-run", "docket-run")):
            store.ensure_firecrawl_run(
                run_id,
                batch_id="batch-001",
                config={"purpose": run_id},
                credit_cap=10,
                reserved_credits_per_attempt=5,
            )
            store.ensure_firecrawl_target(
                run_id,
                target_id=f"target-{ordinal}",
                target_kind="search" if ordinal == 0 else "docket",
                source_url=f"https://www.courtlistener.com/?target={ordinal}",
                ordinal=0,
            )
            store.authorize_firecrawl_attempt(
                run_id,
                target_id=f"target-{ordinal}",
                page_number=1,
                request_url=f"https://www.courtlistener.com/?target={ordinal}",
            )

        with pytest.raises(FirecrawlBudgetExceededError):
            store.authorize_firecrawl_attempt(
                "docket-run",
                target_id="target-1",
                page_number=2,
                request_url="https://www.courtlistener.com/?target=1&page=2",
            )
        assert store.firecrawl_run_summary("search-run")["reserved_credits"] == 10
        assert store.firecrawl_run_summary("docket-run")["reserved_credits"] == 10


def test_firecrawl_artifact_is_atomic_immutable_and_attempt_bound(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        store.ensure_firecrawl_run(
            "search-run",
            batch_id="batch-001",
            config={"purpose": "search"},
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )
        store.ensure_firecrawl_target(
            "search-run",
            target_id="search-1",
            target_kind="search",
            source_url="https://www.courtlistener.com/?type=r&q=alpha",
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "search-run",
            target_id="search-1",
            page_number=1,
            request_url="https://www.courtlistener.com/?type=r&q=alpha",
        )
        destination = tmp_path / "pages" / "search-1.html"
        committed = store.commit_firecrawl_artifact(
            attempt.attempt_id,
            destination,
            b"<html>safe fixture</html>",
            reported_credits=5,
            proxy_used="stealth",
            target_http_status=200,
        )
        assert committed.status == "succeeded"
        assert committed.artifact_path == destination.resolve()
        assert destination.read_bytes() == b"<html>safe fixture</html>"
        assert (
            store.commit_firecrawl_artifact(
                attempt.attempt_id,
                destination,
                b"<html>safe fixture</html>",
                reported_credits=5,
                proxy_used="stealth",
                target_http_status=200,
            )
            == committed
        )
        with pytest.raises(ImmutableArtifactError):
            store.commit_firecrawl_artifact(
                attempt.attempt_id,
                destination,
                b"<html>tampered</html>",
                reported_credits=5,
                proxy_used="stealth",
                target_http_status=200,
            )


def test_store_holds_a_nonblocking_process_lifetime_lock(tmp_path: Path) -> None:
    first = CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    try:
        with pytest.raises(StoreLockedError, match="already locked"):
            CycleAcquisitionStore(tmp_path / "cycle.sqlite3")
    finally:
        first.close()
    CycleAcquisitionStore(tmp_path / "cycle.sqlite3").close()


def test_page_commit_is_atomic_replay_safe_and_order_neutral(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["beta", "alpha"])
        progress = store.commit_search_page(
            "batch-001",
            "beta",
            None,
            [_hit("b-2", "candidate-2"), _hit("shared", "candidate-shared")],
            next_cursor="beta-next",
            terminal_status=None,
        )
        assert (progress.cursor, progress.hit_count, progress.terminal_status) == (
            "beta-next",
            2,
            None,
        )
        store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("a-1", "candidate-1"), _hit("shared-a", "candidate-shared")],
            next_cursor=None,
            terminal_status="exhausted",
        )

        # A response replay after a lost acknowledgement is an exact no-op.
        replay = store.commit_search_page(
            "batch-001",
            "beta",
            None,
            [_hit("b-2", "candidate-2"), _hit("shared", "candidate-shared")],
            next_cursor="beta-next",
            terminal_status=None,
        )
        assert replay == progress
        assert store.candidate_ids("batch-001") == (
            "candidate-1",
            "candidate-2",
            "candidate-shared",
        )
        representative_hits = store.candidate_discovery_hits("batch-001")
        assert tuple(hit.candidate_id for hit in representative_hits) == (
            "candidate-1",
            "candidate-2",
            "candidate-shared",
        )
        assert representative_hits[-1].provider_hit_id == "shared-a"
        assert representative_hits[-1].payload["id"] == "shared-a"
        with pytest.raises(PageReplayMismatchError):
            store.commit_search_page(
                "batch-001",
                "beta",
                None,
                [_hit("different", "candidate-3")],
                next_cursor="beta-next",
                terminal_status=None,
            )


def test_provider_hit_identity_contradiction_does_not_advance_cursor(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["alpha"])
        committed = store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("shared-provider-id", "candidate-1")],
            next_cursor="2",
            terminal_status=None,
        )

        with pytest.raises(
            PageReplayMismatchError,
            match="provider hit identity changed: shared-provider-id",
        ):
            store.commit_search_page(
                "batch-001",
                "alpha",
                "2",
                [_hit("shared-provider-id", "candidate-2")],
                next_cursor="3",
                terminal_status=None,
            )

        assert store.term_progress("batch-001", "alpha") == committed
        assert store.candidate_ids("batch-001") == ("candidate-1",)


def test_candidate_representative_is_invariant_to_query_term_order(
    tmp_path: Path,
) -> None:
    representatives: list[tuple[str, object]] = []
    for index, terms in enumerate((("beta", "alpha"), ("alpha", "beta"))):
        with _store(tmp_path / str(index)) as store:
            store.ensure_terms("batch-001", terms)
            for term in ("beta", "alpha"):
                provider_hit_id = f"{term}-shared"
                store.commit_search_page(
                    "batch-001",
                    term,
                    None,
                    [_hit(provider_hit_id, "candidate-shared")],
                    next_cursor=None,
                    terminal_status="exhausted",
                )
            [representative] = store.candidate_discovery_hits("batch-001")
            representatives.append(
                (representative.provider_hit_id, representative.payload["id"])
            )

    assert representatives == [
        ("alpha-shared", "alpha-shared"),
        ("alpha-shared", "alpha-shared"),
    ]


def test_failed_page_transaction_does_not_advance_cursor(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["alpha"])
        with pytest.raises(ValueError, match="provider_hit_id"):
            store.commit_search_page(
                "batch-001",
                "alpha",
                None,
                [
                    _hit("valid", "candidate-1"),
                    {"provider_hit_id": "", "candidate_id": "candidate-2"},
                ],
                next_cursor="next",
                terminal_status=None,
            )
        assert store.term_progress("batch-001", "alpha").cursor is None
        assert store.candidate_ids("batch-001") == ()


def test_candidate_evidence_precedence_and_immutable_skip_audit(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1", "candidate-2")
        excluded = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="strict_clean_screen_failed",
            evidence={"docket_version": 1},
        )
        accepted = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"docket_version": 2},
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="transient_failure",
            reason_code="fetch_error",
            evidence={"status": 503},
        )
        assert store.current_observation("candidate-1") == accepted
        assert excluded.observation_id < accepted.observation_id
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="criminal_posture",
            evidence={"docket_version": 3},
        )
        assert store.current_observation("candidate-1") == accepted
        newly_free = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="newly_free",
            reason_code="required_documents_newly_free",
            evidence={"document_id": "44"},
        )
        assert store.current_observation("candidate-1") == newly_free

        immutable = store.record_observation(
            "candidate-2",
            batch_id="batch-001",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={"decision_date": "2026-06-29"},
        )
        skipped = store.record_observation(
            "candidate-2",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"decision_date": "2026-07-01"},
        )
        assert skipped.state == "skipped_immutable"
        assert skipped.supersedes_observation_id == immutable.observation_id
        assert store.current_observation("candidate-2") == immutable
        assert len(store.observations("candidate-2")) == 2


def test_non_civil_metadata_exclusion_is_immutable(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="non_civil_case",
            evidence={"nature_of_suit": "criminal"},
        )
        with pytest.raises(ImmutableCandidateStateError):
            store.record_observation(
                "candidate-1",
                batch_id="batch-001",
                state="excluded",
                reason_code="decision_before_release_anchor",
                evidence={},
                audit_immutable_skip=False,
            )


@pytest.mark.parametrize(
    "reason_code",
    [
        "bankruptcy_court",
        "not_federal_district_court",
        "missing_docket_number",
        "placeholder_or_sealed_docket_number",
        "not_civil_cv_docket",
        "criminal_style_caption",
    ],
)
def test_actual_metadata_reason_codes_are_immutable(
    tmp_path: Path, reason_code: str
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code=reason_code,
            evidence={"source": "metadata"},
        )
        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={},
        )
        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable


def test_metadata_rich_rescreen_supersedes_absent_metadata_exclusion(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        deficient = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="not_federal_district_court",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": None,
                "decision_date": None,
                "primary_exclusion_reason": "not_federal_district_court",
                "reason": "not_federal_district_court",
                "secondary_exclusion_reasons": ["missing_docket_number"],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

        repaired = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screen": "passed"},
            metadata_repair_evidence={
                "case_id": "candidate-1",
                "court_id": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        )

        assert repaired.state == "accepted"
        assert repaired.supersedes_observation_id == deficient.observation_id
        assert repaired.evidence["metadata_repair_evidence"] == {
            "case_id": "candidate-1",
            "court_id": "nysd",
            "docket_number": "1:26-cv-00001",
        }
        assert store.current_observation("candidate-1") == repaired


def test_metadata_rescreen_does_not_resurrect_authoritative_immutable_exclusion(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="not_federal_district_court",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": "ca9",
                "decision_date": None,
                "primary_exclusion_reason": "not_federal_district_court",
                "reason": "not_federal_district_court",
                "secondary_exclusion_reasons": [],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screen": "passed"},
            metadata_repair_evidence={
                "case_id": "candidate-1",
                "court_id": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        )

        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable


def test_metadata_rescreen_does_not_repair_partially_present_metadata(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="missing_docket_number",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": "nysd",
                "decision_date": None,
                "primary_exclusion_reason": "missing_docket_number",
                "reason": "missing_docket_number",
                "secondary_exclusion_reasons": [],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screen": "passed"},
            metadata_repair_evidence={
                "case_id": "candidate-1",
                "court_id": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        )

        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable


def test_absent_metadata_exclusion_requires_explicit_valid_repair_evidence(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="missing_docket_number",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": None,
                "decision_date": None,
                "primary_exclusion_reason": "missing_docket_number",
                "reason": "missing_docket_number",
                "secondary_exclusion_reasons": [],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )
        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screen": "passed"},
        )
        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable

        with pytest.raises(ValueError, match="metadata repair evidence"):
            store.record_observation(
                "candidate-1",
                batch_id="batch-001",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence={"screen": "passed"},
                metadata_repair_evidence={
                    "case_id": "different-candidate",
                    "court_id": "nysd",
                    "docket_number": "1:26-cv-00001",
                },
            )


def test_metadata_repair_cannot_skip_strict_screen_via_newly_free_state(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="missing_docket_number",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": None,
                "decision_date": None,
                "primary_exclusion_reason": "missing_docket_number",
                "reason": "missing_docket_number",
                "secondary_exclusion_reasons": [],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="newly_free",
            reason_code="required_documents_newly_free",
            evidence={"document_id": "44"},
            metadata_repair_evidence={
                "case_id": "candidate-1",
                "court_id": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        )

        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable


def test_metadata_repair_preserves_unrelated_secondary_immutable_reason(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="not_federal_district_court",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": None,
                "decision_date": None,
                "primary_exclusion_reason": "not_federal_district_court",
                "reason": "not_federal_district_court",
                "secondary_exclusion_reasons": [
                    "missing_docket_number",
                    "criminal_style_caption",
                ],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"screen": "passed"},
            metadata_repair_evidence={
                "case_id": "candidate-1",
                "court_id": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        )

        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable


def test_metadata_repair_requires_screen_exclusion_not_parse_failure(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        immutable = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="missing_docket_number",
            evidence={
                "candidate_id": "candidate-1",
                "case_id": "candidate-1",
                "court": None,
                "decision_date": None,
                "primary_exclusion_reason": "missing_docket_number",
                "reason": "missing_docket_number",
                "secondary_exclusion_reasons": [],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

        skipped = store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="excluded",
            reason_code="strict_clean_screen_failed",
            evidence={"stage": "extraction", "reason": "parse_error"},
            metadata_repair_evidence={
                "case_id": "candidate-1",
                "court_id": "nysd",
                "docket_number": "1:26-cv-00001",
            },
        )

        assert skipped.state == "skipped_immutable"
        assert store.current_observation("candidate-1") == immutable


def test_unknown_reason_code_is_rejected(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        with pytest.raises(ValueError, match="unknown candidate observation reason"):
            store.record_observation(
                "candidate-1",
                batch_id="batch-001",
                state="excluded",
                reason_code="invented_reason",
                evidence={},
            )


def test_record_observation_requires_discovery_hit_in_stated_batch(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        store.ensure_batch("batch-002", {"start": "2026-07-01", "page_size": 50})

        with pytest.raises(KeyError, match="not discovered in batch batch-002"):
            store.record_observation(
                "candidate-1",
                batch_id="batch-002",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence={},
            )
        with pytest.raises(KeyError, match="not discovered in batch batch-001"):
            store.record_observation(
                "never-discovered",
                batch_id="batch-001",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence={},
            )

        assert store.current_observation("candidate-1") is None
        assert store.current_observation("never-discovered") is None


def test_raw_artifact_is_atomic_content_committed_and_immutable(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={},
        )
        destination = tmp_path / "raw" / "candidate-1.html"
        artifact = store.write_raw_artifact(
            "candidate-1",
            destination,
            b"<html>public docket</html>",
            retrieved_at="2026-07-12T12:00:00Z",
            validator=lambda payload: (
                None
                if payload.startswith(b"<html>")
                else (_ for _ in ()).throw(ValueError("bad html"))
            ),
        )
        assert destination.read_bytes() == b"<html>public docket</html>"
        assert artifact.sha256 == store.raw_artifacts("candidate-1")[0].sha256
        assert not list(destination.parent.glob("*.tmp"))

        with pytest.raises(ImmutableArtifactError):
            store.write_raw_artifact(
                "candidate-1",
                destination,
                b"different",
                retrieved_at="2026-07-12T12:01:00Z",
            )
        assert destination.read_bytes() == b"<html>public docket</html>"


def test_raw_artifact_replay_reuses_canonical_candidate_content_commitment(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        content = b"<html>public docket</html>"
        canonical_path = tmp_path / "first-run" / "candidate-1.html"
        canonical = store.write_raw_artifact(
            "candidate-1",
            canonical_path,
            content,
            retrieved_at="2026-07-12T12:00:00Z",
        )
        replay_path = tmp_path / "corrected-metadata-run" / "candidate-1.html"
        replay_path.parent.mkdir()
        replay_path.write_bytes(content)

        replay = store.write_raw_artifact(
            "candidate-1",
            replay_path,
            content,
            retrieved_at="2026-07-12T12:01:00Z",
        )

        assert replay == canonical
        assert store.raw_artifacts("candidate-1") == (canonical,)
        assert replay_path.read_bytes() == content


def test_raw_artifact_replay_rejects_modified_canonical_content(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        content = b"<html>public docket</html>"
        canonical_path = tmp_path / "first-run" / "candidate-1.html"
        store.write_raw_artifact(
            "candidate-1",
            canonical_path,
            content,
            retrieved_at="2026-07-12T12:00:00Z",
        )
        canonical_path.write_bytes(b"modified")

        with pytest.raises(ImmutableArtifactError, match="canonical raw artifact"):
            store.write_raw_artifact(
                "candidate-1",
                tmp_path / "corrected-metadata-run" / "candidate-1.html",
                content,
                retrieved_at="2026-07-12T12:01:00Z",
            )


def test_raw_artifact_replay_rejects_conflicting_destination_content(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        content = b"<html>public docket</html>"
        store.write_raw_artifact(
            "candidate-1",
            tmp_path / "first-run" / "candidate-1.html",
            content,
            retrieved_at="2026-07-12T12:00:00Z",
        )
        replay_path = tmp_path / "corrected-metadata-run" / "candidate-1.html"
        replay_path.parent.mkdir()
        replay_path.write_bytes(b"different")

        with pytest.raises(ImmutableArtifactError, match="untracked raw artifact"):
            store.write_raw_artifact(
                "candidate-1",
                replay_path,
                content,
                retrieved_at="2026-07-12T12:01:00Z",
            )


def test_complete_snapshot_is_atomic_and_verifiable(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["alpha"])
        store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("a-1", "candidate-1")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={"entry_id": "99"},
        )
        partial = store.export_snapshot(
            tmp_path / "exports",
            snapshot_id="checkpoint-1",
            batch_id="batch-001",
            complete=False,
        )
        with pytest.raises(SnapshotVerificationError, match="not complete"):
            verify_snapshot(partial)

        published = store.export_snapshot(
            tmp_path / "exports",
            snapshot_id="snapshot-1",
            batch_id="batch-001",
            complete=True,
        )
        verified = verify_snapshot(
            published,
            expected_cycle_hash=store.cycle_hash,
            expected_batch_digest=store.batch_digest("batch-001"),
        )
        assert verified["complete"] is True
        records = [
            json.loads(line)
            for line in (published / "candidates.jsonl").read_text().splitlines()
        ]
        assert records[0]["state"] == "accepted"
        screened = [
            json.loads(line)
            for line in (published / "screened-cases.jsonl").read_text().splitlines()
        ]
        assert screened == [{"candidate_id": "candidate-1", "entry_id": "99"}]
        assert json.loads((published / "summary.json").read_text()) == {
            "accepted_count": 1,
            "batch_id": "batch-001",
            "excluded_count": 0,
            "processed_count": 1,
            "reconciliation_complete": True,
        }

        with (published / "candidates.jsonl").open("ab") as handle:
            handle.write(b"tampered\n")
        with pytest.raises(SnapshotVerificationError, match="commitment"):
            verify_snapshot(published)


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("missing", "missing committed raw artifact"),
        ("wrong_size", "raw artifact byte_count mismatch"),
        ("wrong_digest", "raw artifact sha256 mismatch"),
    ],
)
def test_snapshot_verifier_checks_committed_raw_artifact_content(
    tmp_path: Path, mutation: str, expected_error: str
) -> None:
    artifact_path = tmp_path / "raw" / "candidate-1.html"
    original = b"<html>public docket</html>"
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["alpha"])
        store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("a-1", "candidate-1")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={},
        )
        store.write_raw_artifact(
            "candidate-1",
            artifact_path,
            original,
            retrieved_at="2026-07-12T12:00:00Z",
        )
        published = store.export_snapshot(
            tmp_path / "exports",
            snapshot_id=f"raw-{mutation}",
            batch_id="batch-001",
            complete=True,
        )

    verify_snapshot(published)
    if mutation == "missing":
        artifact_path.unlink()
    elif mutation == "wrong_size":
        artifact_path.write_bytes(original + b"!")
    else:
        artifact_path.write_bytes(b"X" * len(original))

    with pytest.raises(SnapshotVerificationError, match=expected_error):
        verify_snapshot(published)


@pytest.mark.parametrize(
    ("mutation", "filename", "expected_error"),
    [
        (
            "candidate_id",
            "candidates.jsonl",
            "candidate IDs and states do not reconcile",
        ),
        (
            "candidate_state",
            "candidates.jsonl",
            "candidate IDs and states do not reconcile",
        ),
        ("observation_link", "observations.jsonl", "unknown candidate_id"),
        ("artifact_link", "raw-artifacts.jsonl", "unknown candidate_id"),
    ],
)
def test_snapshot_verifier_reconciles_candidate_states_and_links(
    tmp_path: Path, mutation: str, filename: str, expected_error: str
) -> None:
    artifact_path = tmp_path / "raw" / "candidate-1.html"
    with _store(tmp_path) as store:
        _discover_candidates(store, "candidate-1")
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={},
        )
        store.write_raw_artifact(
            "candidate-1",
            artifact_path,
            b"<html>public docket</html>",
            retrieved_at="2026-07-12T12:00:00Z",
        )
        published = store.export_snapshot(
            tmp_path / "exports",
            snapshot_id=f"links-{mutation}",
            batch_id="batch-001",
            complete=True,
        )

    records = [
        json.loads(line) for line in (published / filename).read_text().splitlines()
    ]
    if mutation == "candidate_state":
        records[0]["state"] = "excluded"
    else:
        records[0]["candidate_id"] = "candidate-not-in-ledger"
    _rewrite_snapshot_jsonl(published, filename, records)

    with pytest.raises(SnapshotVerificationError, match=expected_error):
        verify_snapshot(published)


def test_snapshot_verifier_rejects_accepted_excluded_overlap(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["alpha"])
        store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("a-1", "candidate-1"), _hit("a-2", "candidate-2")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "candidate-1",
            batch_id="batch-001",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence={},
        )
        store.record_observation(
            "candidate-2",
            batch_id="batch-001",
            state="excluded",
            reason_code="criminal_posture",
            evidence={},
        )
        published = store.export_snapshot(
            tmp_path / "exports",
            snapshot_id="overlap",
            batch_id="batch-001",
            complete=True,
        )

    screened_path = published / "screened-cases.jsonl"
    screened_payload = b'{"candidate_id":"candidate-2"}\n'
    screened_path.write_bytes(screened_payload)
    manifest_path = published / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["screened-cases.jsonl"] = {
        "sha256": hashlib.sha256(screened_payload).hexdigest(),
        "byte_count": len(screened_payload),
        "row_count": 1,
    }
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(SnapshotVerificationError, match="overlap"):
        verify_snapshot(published)


def test_complete_snapshot_rejects_unfinished_or_unresolved_work(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        store.ensure_terms("batch-001", ["alpha"])
        with pytest.raises(CycleAcquisitionStoreError, match="incomplete terms"):
            store.export_snapshot(
                tmp_path / "exports",
                snapshot_id="unfinished",
                batch_id="batch-001",
                complete=True,
            )
        store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("a-1", "candidate-1")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        with pytest.raises(CycleAcquisitionStoreError, match="unresolved candidates"):
            store.export_snapshot(
                tmp_path / "exports",
                snapshot_id="unresolved",
                batch_id="batch-001",
                complete=True,
            )


def test_complete_snapshot_rejects_unpageable_term_but_accepts_bounded_term(
    tmp_path: Path,
) -> None:
    for index, terminal_status in enumerate(("limit_bound_unpageable", "limit_bound")):
        root = tmp_path / str(index)
        with _store(root) as store:
            store.ensure_terms("batch-001", ["alpha"])
            store.commit_search_page(
                "batch-001",
                "alpha",
                None,
                [_hit("a-1", "candidate-1")],
                next_cursor=None,
                terminal_status=terminal_status,
            )
            store.record_observation(
                "candidate-1",
                batch_id="batch-001",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence={},
            )
            if terminal_status == "limit_bound_unpageable":
                with pytest.raises(
                    CycleAcquisitionStoreError, match="incomplete terms: alpha"
                ):
                    store.export_snapshot(
                        root / "exports",
                        snapshot_id="unpageable",
                        batch_id="batch-001",
                        complete=True,
                    )
            else:
                published = store.export_snapshot(
                    root / "exports",
                    snapshot_id="bounded",
                    batch_id="batch-001",
                    complete=True,
                )
                manifest = verify_snapshot(published)
                assert manifest["complete"] is True
                assert manifest["saturated"] is False


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX process semantics")
def test_torn_wal_tail_is_trimmed_without_losing_committed_pages(
    tmp_path: Path,
) -> None:
    database = tmp_path / "cycle.sqlite3"
    pid = os.fork()
    if pid == 0:
        store = CycleAcquisitionStore(database)
        store.ensure_cycle(POLICY)
        store.ensure_batch("batch-001", {"page_size": 50})
        store.ensure_terms("batch-001", ["alpha"])
        store.commit_search_page(
            "batch-001",
            "alpha",
            None,
            [_hit("a-1", "candidate-1")],
            next_cursor=None,
            terminal_status="exhausted",
        )
        os._exit(0)
    _, status = os.waitpid(pid, 0)
    assert status == 0
    wal_path = Path(f"{database}-wal")
    assert wal_path.exists()
    with wal_path.open("ab") as handle:
        handle.write(b"torn-tail")

    with CycleAcquisitionStore(database) as recovered:
        assert recovered.candidate_ids("batch-001") == ("candidate-1",)
        assert wal_path.stat().st_size % (4096 + 24) in {0, 32}
