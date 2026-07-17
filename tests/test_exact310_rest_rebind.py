from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import legalforecast.ingestion.rest_observation_policy_rebind as rebind_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    StoreLockedError,
    TermTerminalStatus,
    verify_snapshot,
)
from legalforecast.ingestion.exact310_rest_rebind import (
    FAIL_CLOSED_REASON,
    Exact310PlanResult,
    Exact310RestRebindError,
    Exact310SourceSpec,
    execute_exact310_terminal_rest_rebind,
    plan_exact310_terminal_rest_rebind,
)
from legalforecast.ingestion.rest_observation_policy_rebind import (
    RestObservationPolicyRebindError,
)


@dataclass(frozen=True, slots=True)
class Fixture:
    candidates: tuple[str, ...]
    source_store: Path
    source_snapshot: Path
    source_manifest_sha256: str
    target_store: Path
    target_cycle_hash: str
    target_batch_id: str
    target_seed_summary: Path
    target_seed_summary_sha256: str
    receipt: Path
    spec: Exact310SourceSpec


def _policy(marker: str, *, anchor: str = "2026-06-30") -> dict[str, object]:
    return {
        "eligibility_anchor": anchor,
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "screening_source_sha256": {
            key: marker * 64
            for key in (
                "contamination_filters",
                "courtlistener_acquisition",
                "motion_linkage",
                "mtd_acquisition_screen",
                "restricted_material",
            )
        },
    }


def _batch(
    store: CycleAcquisitionStore,
    batch_id: str,
    candidates: tuple[str, ...],
    *,
    config: Mapping[str, object] | None = None,
    payloads: Mapping[str, Mapping[str, object]] | None = None,
    term: str = "fixture",
) -> None:
    store.ensure_batch(batch_id, config or {"batch_id": batch_id})
    store.ensure_terms(batch_id, (term,))
    store.commit_search_page(
        batch_id,
        term,
        None,
        tuple(
            DiscoveryHit(
                provider_hit_id=f"{batch_id}-{candidate}",
                candidate_id=candidate,
                payload=(
                    payloads[candidate]
                    if payloads is not None
                    else {"docket_id": candidate.rsplit("-", 1)[-1]}
                ),
            )
            for candidate in candidates
        ),
        next_cursor=None,
        terminal_status=TermTerminalStatus.EXHAUSTED,
    )


def _record(
    store: CycleAcquisitionStore,
    batch_id: str,
    candidate: str,
    state: str,
    reason: str,
    evidence: dict[str, object],
) -> None:
    store.record_observation(
        candidate,
        batch_id=batch_id,
        state=state,
        reason_code=reason,
        evidence={"candidate_id": candidate, **evidence},
        observed_at="2026-07-16T12:00:00Z",
        audit_immutable_skip=False,
    )


def _strict(
    candidate: str,
    *,
    decision_text: str,
    numeric_case_id: bool = False,
) -> dict[str, object]:
    docket_id = candidate.rsplit("-", 1)[-1]
    case_id = docket_id if numeric_case_id else candidate

    def entry(row_id: str, number: str, text: str, role: str) -> dict[str, object]:
        return {
            "row_id": row_id,
            "entry_number": number,
            "filed_at": "2026-07-15",
            "text": text,
            "role": role,
            "restriction_markers": [],
            "documents": [],
        }

    return {
        "candidate": {
            "candidate_key": docket_id,
            "docket_id": docket_id,
            "metadata": {
                "case_id": case_id,
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-1",
            },
        },
        "ai": {
            "target_motion_entry_numbers": ["4"],
            "decision_entry_numbers": ["9"],
        },
        "first_written_mtd_disposition_date": "2026-07-15",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            entry("entry-4", "4", "Motion to dismiss", "mtd_notice"),
            entry("entry-9", "9", decision_text, "decision"),
        ],
        "mtd_decision_screen": {
            "status": "accepted_strict_civil_mtd_decision",
            "exclusion_reasons": [],
            "actual_mtd_decision_entry_count": 1,
            "decision_entries": [{"entry_number": "9", "actual_mtd_decision": True}],
        },
        "motion_linkage": {
            "candidate_id": docket_id,
            "case_id": case_id,
            "is_clean": True,
            "exclusion_entries": [],
            "links": [
                {
                    "candidate_id": docket_id,
                    "case_id": case_id,
                    "motion_entry_ids": ["entry-4"],
                    "disposition_entry_ids": ["entry-9"],
                    "linkage_basis": ["explicit_docket_entry_reference"],
                }
            ],
        },
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _transfer_payloads(
    candidates: tuple[str, ...],
    *,
    source_batch_id: str,
    source_batch_digest: str,
    transfer_term: str,
) -> tuple[str, Mapping[str, Mapping[str, object]]]:
    lead_rows: list[dict[str, object]] = []
    partial_payloads: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        docket_id = candidate.rsplit("-", 1)[-1]
        source_hit = {
            "provider_hit_id": f"source-hit-{docket_id}",
            "query_term": "motion to dismiss",
            "payload_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
        }
        lead: dict[str, object] = {
            "docket_id": docket_id,
            "court_id": "nysd",
            "docket_number": f"1:26-cv-{docket_id}",
            "case_name": f"Fixture {docket_id} v. Example",
            "decision_entry_evidence": None,
            "source_hits": [source_hit],
        }
        lead_rows.append(lead)
        partial_payloads[candidate] = {
            "candidate_id": candidate,
            "docket_id": docket_id,
            "courtlistener_docket_id": docket_id,
            "court_id": lead["court_id"],
            "docket_number": lead["docket_number"],
            "case_name": lead["case_name"],
            "provider": "courtlistener-recap-rest-v4",
            "prescreen_exclusion_reason": None,
            "query_term": transfer_term,
            "direct_search_provenance": {
                "schema_version": (
                    "legalforecast.courtlistener_direct_search_transfer.v1"
                ),
                "source_batch_id": source_batch_id,
                "source_batch_digest": source_batch_digest,
                "source_provider_hit_id": source_hit["provider_hit_id"],
                "source_query_term": source_hit["query_term"],
                "source_payload_sha256": source_hit["payload_sha256"],
                "source_hits": [source_hit],
            },
        }
    lead_rows.sort(key=lambda row: int(str(row["docket_id"])))
    candidate_set_sha256 = hashlib.sha256(
        json.dumps(lead_rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    for payload in partial_payloads.values():
        provenance = payload["direct_search_provenance"]
        assert isinstance(provenance, dict)
        provenance["source_candidate_set_sha256"] = candidate_set_sha256
    return candidate_set_sha256, partial_payloads


def _fixture(tmp_path: Path) -> Fixture:
    candidates = tuple(f"courtlistener-docket-{number}" for number in (1, 2, 3, 4))
    source_batch = "exact-rest-source"
    target_batch = "current-rebind-target"
    source_path = tmp_path / "source.sqlite3"
    target_path = tmp_path / "target.sqlite3"
    source_lineage_id = "direct-search-source"
    source_lineage_digest = "d" * 64
    transfer_term = "courtlistener-direct-search-transfer-v1"
    candidate_set_sha256, source_payloads = _transfer_payloads(
        candidates,
        source_batch_id=source_lineage_id,
        source_batch_digest=source_lineage_digest,
        transfer_term=transfer_term,
    )
    source_config = {
        "auth_mode": "authenticated",
        "decision_window_end": "2026-07-15",
        "decision_window_start": "2026-07-11",
        "discovery_mode": "legalforecast.courtlistener_direct_search_transfer.v1",
        "order_by": "entry_date_filed desc",
        "page_size": 100,
        "provider": "courtlistener-recap-rest-v4",
        "query_field": "description",
        "query_term_order_is_frozen": True,
        "query_terms": [transfer_term],
        "schema_version": "legalforecast.recap_api_discovery_batch.v1",
        "search_type": "rd",
        "source_batch_digest": source_lineage_digest,
        "source_batch_id": source_lineage_id,
        "source_candidate_count": 4,
        "source_candidate_set_sha256": candidate_set_sha256,
        "top_k_per_term": 4,
    }
    with CycleAcquisitionStore(source_path) as source:
        source_cycle = source.ensure_cycle(_policy("a"))
        _batch(
            source,
            source_batch,
            candidates,
            config=source_config,
            payloads=source_payloads,
            term=transfer_term,
        )
        _record(
            source,
            source_batch,
            candidates[0],
            "excluded",
            "strict_clean_screen_failed",
            {"screen": "excluded"},
        )
        _record(
            source,
            source_batch,
            candidates[1],
            "accepted",
            "strict_clean_screen_passed",
            _strict(
                candidates[1],
                decision_text="Order granting MTD",
                numeric_case_id=True,
            ),
        )
        _record(
            source,
            source_batch,
            candidates[2],
            "accepted",
            "strict_clean_screen_passed",
            _strict(candidates[2], decision_text=""),
        )
        _record(
            source,
            source_batch,
            candidates[3],
            "excluded",
            "strict_clean_screen_failed",
            {"screen": "no linked MTD disposition"},
        )
        snapshot = source.export_snapshot(
            tmp_path / "source-snapshots",
            snapshot_id="source-complete",
            batch_id=source_batch,
            complete=True,
        )
    with CycleAcquisitionStore(target_path) as target:
        target_cycle = target.ensure_cycle(_policy("b"))
        _batch(target, "prior", (candidates[0],))
        _record(
            target,
            "prior",
            candidates[0],
            "excluded",
            "decision_before_release_anchor",
            {"decision_date": "2026-06-29"},
        )
        target_config = {
            **source_config,
            "source_search_type": "rd",
        }
        _batch(
            target,
            target_batch,
            candidates,
            config=target_config,
            term=transfer_term,
        )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.direct_search_seed_result.v1",
                "batch_id": source_batch,
                "leads_seeded": 4,
                "leads_selected": 4,
                "source_batch_digest": source_lineage_digest,
                "source_batch_id": source_lineage_id,
                "source_candidate_set_sha256": candidate_set_sha256,
                "term": transfer_term,
            },
            sort_keys=True,
        )
        + "\n"
    )
    target_seed_summary = tmp_path / "target-seed-summary.json"
    target_seed_summary.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.direct_search_seed_result.v1",
                "batch_id": target_batch,
                "term": transfer_term,
                "source_batch_id": source_lineage_id,
                "source_batch_digest": source_lineage_digest,
                "source_candidate_set_sha256": candidate_set_sha256,
                "leads_selected": 4,
                "leads_seeded": 4,
                "already_seeded": False,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return Fixture(
        candidates=candidates,
        source_store=source_path,
        source_snapshot=snapshot,
        source_manifest_sha256=_sha(snapshot / "manifest.json"),
        target_store=target_path,
        target_cycle_hash=target_cycle,
        target_batch_id=target_batch,
        target_seed_summary=target_seed_summary,
        target_seed_summary_sha256=_sha(target_seed_summary),
        receipt=receipt,
        spec=Exact310SourceSpec(
            cycle_hash=source_cycle,
            batch_id=source_batch,
            candidate_count=4,
            candidate_set_sha256=candidate_set_sha256,
            transfer_receipt_sha256=_sha(receipt),
        ),
    )


def _plan(tmp_path: Path, fixture: Fixture) -> Exact310PlanResult:
    return plan_exact310_terminal_rest_rebind(
        source_store_path=fixture.source_store,
        source_snapshot_path=fixture.source_snapshot,
        expected_source_snapshot_manifest_sha256=fixture.source_manifest_sha256,
        transfer_receipt_path=fixture.receipt,
        target_seed_summary_path=fixture.target_seed_summary,
        expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
        target_store_path=fixture.target_store,
        target_batch_id=fixture.target_batch_id,
        expected_target_cycle_hash=fixture.target_cycle_hash,
        contract_output_path=tmp_path / "contract.json",
        source_spec=fixture.spec,
    )


def test_exact310_rebind_preserves_reproves_and_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    source_stat = fixture.source_store.stat()
    source_sha = _sha(fixture.source_store)
    plan = _plan(tmp_path, fixture)
    assert (plan.preserve_current_count, plan.reproved_current_count) == (1, 1)
    assert plan.reproved_exclusion_count == 1
    assert plan.fail_closed_count == 1

    result = execute_exact310_terminal_rest_rebind(
        source_store_path=fixture.source_store,
        source_snapshot_path=fixture.source_snapshot,
        expected_source_snapshot_manifest_sha256=fixture.source_manifest_sha256,
        transfer_receipt_path=fixture.receipt,
        target_seed_summary_path=fixture.target_seed_summary,
        expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
        target_store_path=fixture.target_store,
        target_batch_id=fixture.target_batch_id,
        expected_target_cycle_hash=fixture.target_cycle_hash,
        contract_path=plan.contract_path,
        expected_contract_sha256=plan.contract_sha256,
        snapshot_output_root=tmp_path / "target-snapshots",
        snapshot_id="target-complete",
        run_card_path=tmp_path / "run-card.json",
        source_spec=fixture.spec,
    )
    manifest = verify_snapshot(
        result.snapshot_path,
        expected_cycle_hash=fixture.target_cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    assert manifest["stage_commitments"]["contract_sha256"] == plan.contract_sha256
    rows: list[dict[str, Any]] = [
        json.loads(line)
        for line in (result.snapshot_path / "observations.jsonl")
        .read_text()
        .splitlines()
    ]
    observations = {row["candidate_id"]: row for row in rows}
    assert observations[fixture.candidates[0]]["reason_code"] == (
        "decision_before_release_anchor"
    )
    assert observations[fixture.candidates[1]]["state"] == "accepted"
    assert observations[fixture.candidates[2]]["reason_code"] == FAIL_CLOSED_REASON
    assert (
        observations[fixture.candidates[2]]["evidence"]["source_terminal_observation"][
            "reason_code"
        ]
        == "strict_clean_screen_passed"
    )
    assert observations[fixture.candidates[3]]["reason_code"] == (
        "strict_clean_screen_failed"
    )
    assert observations[fixture.candidates[3]]["evidence"]["screen"] == (
        "no linked MTD disposition"
    )
    resumed = execute_exact310_terminal_rest_rebind(
        source_store_path=fixture.source_store,
        source_snapshot_path=fixture.source_snapshot,
        expected_source_snapshot_manifest_sha256=fixture.source_manifest_sha256,
        transfer_receipt_path=fixture.receipt,
        target_seed_summary_path=fixture.target_seed_summary,
        expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
        target_store_path=fixture.target_store,
        target_batch_id=fixture.target_batch_id,
        expected_target_cycle_hash=fixture.target_cycle_hash,
        contract_path=plan.contract_path,
        expected_contract_sha256=plan.contract_sha256,
        snapshot_output_root=tmp_path / "target-snapshots",
        snapshot_id="target-complete",
        run_card_path=tmp_path / "resumed-run-card.json",
        source_spec=fixture.spec,
    )
    assert resumed.snapshot_manifest_sha256 == result.snapshot_manifest_sha256
    assert fixture.source_store.stat().st_mtime_ns == source_stat.st_mtime_ns
    assert _sha(fixture.source_store) == source_sha


def test_exact310_rebind_rejects_contract_tamper(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    plan = _plan(tmp_path, fixture)
    plan.contract_path.write_text(plan.contract_path.read_text() + " ")
    with pytest.raises(RestObservationPolicyRebindError, match="SHA-256 mismatch"):
        execute_exact310_terminal_rest_rebind(
            source_store_path=fixture.source_store,
            source_snapshot_path=fixture.source_snapshot,
            expected_source_snapshot_manifest_sha256=(fixture.source_manifest_sha256),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=fixture.target_store,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash=fixture.target_cycle_hash,
            contract_path=plan.contract_path,
            expected_contract_sha256=plan.contract_sha256,
            snapshot_output_root=tmp_path / "snapshots",
            snapshot_id="refused",
            run_card_path=tmp_path / "run.json",
            source_spec=fixture.spec,
        )


def test_exact310_plan_rejects_target_candidate_gap(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    wrong = tmp_path / "wrong.sqlite3"
    with CycleAcquisitionStore(wrong) as store:
        cycle = store.ensure_cycle(_policy("b"))
        _batch(store, fixture.target_batch_id, fixture.candidates[:2])
    with pytest.raises(Exact310RestRebindError, match="candidate set"):
        plan_exact310_terminal_rest_rebind(
            source_store_path=fixture.source_store,
            source_snapshot_path=fixture.source_snapshot,
            expected_source_snapshot_manifest_sha256=(fixture.source_manifest_sha256),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=wrong,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash=cycle,
            contract_output_path=tmp_path / "refused.json",
            source_spec=fixture.spec,
        )


def test_exact310_plan_rejects_arbitrary_target_batch_config(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    wrong = tmp_path / "wrong-config.sqlite3"
    with CycleAcquisitionStore(wrong) as store:
        cycle = store.ensure_cycle(_policy("b"))
        _batch(
            store,
            fixture.target_batch_id,
            fixture.candidates,
            config={"arbitrary": "same candidates, wrong authority"},
            term="courtlistener-direct-search-transfer-v1",
        )
    with pytest.raises(Exact310RestRebindError, match="target batch config"):
        plan_exact310_terminal_rest_rebind(
            source_store_path=fixture.source_store,
            source_snapshot_path=fixture.source_snapshot,
            expected_source_snapshot_manifest_sha256=(fixture.source_manifest_sha256),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=wrong,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash=cycle,
            contract_output_path=tmp_path / "refused-config.json",
            source_spec=fixture.spec,
        )


def test_exact310_authentication_holds_source_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    original = vars(rebind_module)["_read_source_store_evidence"]
    lock_observed = False

    def guarded_read(
        store_path: str | Path,
        *,
        batch_id: str,
        snapshot_path: Path,
        snapshot_manifest: Mapping[str, object],
    ) -> object:
        nonlocal lock_observed
        with pytest.raises(StoreLockedError):
            with CycleAcquisitionStore(fixture.source_store):
                pass
        lock_observed = True
        return original(
            store_path,
            batch_id=batch_id,
            snapshot_path=snapshot_path,
            snapshot_manifest=snapshot_manifest,
        )

    monkeypatch.setattr(
        rebind_module,
        "_read_source_store_evidence",
        guarded_read,
    )
    _plan(tmp_path, fixture)
    assert lock_observed is True


def test_exact310_plan_rejects_source_cycle_mismatch(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    wrong_spec = Exact310SourceSpec(
        cycle_hash="f" * 64,
        batch_id=fixture.spec.batch_id,
        candidate_count=fixture.spec.candidate_count,
        candidate_set_sha256=fixture.spec.candidate_set_sha256,
        transfer_receipt_sha256=fixture.spec.transfer_receipt_sha256,
    )
    with pytest.raises(Exact310RestRebindError, match="cycle hash mismatch"):
        plan_exact310_terminal_rest_rebind(
            source_store_path=fixture.source_store,
            source_snapshot_path=fixture.source_snapshot,
            expected_source_snapshot_manifest_sha256=(fixture.source_manifest_sha256),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=fixture.target_store,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash=fixture.target_cycle_hash,
            contract_output_path=tmp_path / "refused.json",
            source_spec=wrong_spec,
        )


def test_exact310_plan_rejects_target_cycle_mismatch(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(Exact310RestRebindError, match="target cycle hash"):
        plan_exact310_terminal_rest_rebind(
            source_store_path=fixture.source_store,
            source_snapshot_path=fixture.source_snapshot,
            expected_source_snapshot_manifest_sha256=(fixture.source_manifest_sha256),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=fixture.target_store,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash="f" * 64,
            contract_output_path=tmp_path / "refused.json",
            source_spec=fixture.spec,
        )


def test_exact310_reproof_uses_target_cycle_anchor(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    later_target = tmp_path / "later-target.sqlite3"
    with CycleAcquisitionStore(fixture.target_store, read_only=True) as seeded:
        target_config = seeded.batch_config(fixture.target_batch_id)
    with CycleAcquisitionStore(later_target) as target:
        target_cycle = target.ensure_cycle(_policy("b", anchor="2026-07-16"))
        _batch(
            target,
            fixture.target_batch_id,
            fixture.candidates,
            config=target_config,
            term="courtlistener-direct-search-transfer-v1",
        )
    result = plan_exact310_terminal_rest_rebind(
        source_store_path=fixture.source_store,
        source_snapshot_path=fixture.source_snapshot,
        expected_source_snapshot_manifest_sha256=fixture.source_manifest_sha256,
        transfer_receipt_path=fixture.receipt,
        target_seed_summary_path=fixture.target_seed_summary,
        expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
        target_store_path=later_target,
        target_batch_id=fixture.target_batch_id,
        expected_target_cycle_hash=target_cycle,
        contract_output_path=tmp_path / "later-anchor-contract.json",
        source_spec=fixture.spec,
    )
    assert result.reproved_current_count == 0
    assert result.fail_closed_count == 2


def test_exact310_plan_rejects_same_size_source_substitution(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    substituted = tmp_path / "substituted.sqlite3"
    wrong_config = {
        "auth_mode": "authenticated",
        "decision_window_end": "2026-07-15",
        "decision_window_start": "2026-07-11",
        "discovery_mode": "legalforecast.courtlistener_direct_search_transfer.v1",
        "order_by": "entry_date_filed desc",
        "page_size": 100,
        "provider": "courtlistener-recap-rest-v4",
        "query_field": "description",
        "query_term_order_is_frozen": True,
        "query_terms": ["courtlistener-direct-search-transfer-v1"],
        "schema_version": "legalforecast.recap_api_discovery_batch.v1",
        "search_type": "rd",
        "source_batch_digest": "d" * 64,
        "source_batch_id": "substituted-source",
        "source_candidate_count": 4,
        "source_candidate_set_sha256": "c" * 64,
        "top_k_per_term": 4,
    }
    with CycleAcquisitionStore(substituted) as source:
        assert source.ensure_cycle(_policy("a")) == fixture.spec.cycle_hash
        _batch(
            source,
            fixture.spec.batch_id,
            fixture.candidates,
            config=wrong_config,
        )
        for candidate in fixture.candidates:
            _record(
                source,
                fixture.spec.batch_id,
                candidate,
                "excluded",
                "strict_clean_screen_failed",
                {"screen": "substituted"},
            )
        snapshot = source.export_snapshot(
            tmp_path / "substituted-snapshots",
            snapshot_id="substituted-complete",
            batch_id=fixture.spec.batch_id,
            complete=True,
        )
    with pytest.raises(Exact310RestRebindError, match="batch config"):
        plan_exact310_terminal_rest_rebind(
            source_store_path=substituted,
            source_snapshot_path=snapshot,
            expected_source_snapshot_manifest_sha256=_sha(snapshot / "manifest.json"),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=fixture.target_store,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash=fixture.target_cycle_hash,
            contract_output_path=tmp_path / "refused.json",
            source_spec=fixture.spec,
        )


def test_exact310_plan_rejects_discovery_payload_substitution(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with sqlite3.connect(fixture.source_store) as connection:
        row = connection.execute(
            "SELECT term, provider_hit_id, payload_json FROM discovery_hits "
            "WHERE batch_id = ? ORDER BY term, provider_hit_id LIMIT 1",
            (fixture.spec.batch_id,),
        ).fetchone()
        assert row is not None
        payload = json.loads(str(row[2]))
        payload["case_name"] = "Substituted v. Source"
        connection.execute(
            "UPDATE discovery_hits SET payload_json = ? "
            "WHERE batch_id = ? AND term = ? AND provider_hit_id = ?",
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                fixture.spec.batch_id,
                row[0],
                row[1],
            ),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    with pytest.raises(
        Exact310RestRebindError,
        match="candidate-set commitment mismatch",
    ):
        plan_exact310_terminal_rest_rebind(
            source_store_path=fixture.source_store,
            source_snapshot_path=fixture.source_snapshot,
            expected_source_snapshot_manifest_sha256=(fixture.source_manifest_sha256),
            transfer_receipt_path=fixture.receipt,
            target_seed_summary_path=fixture.target_seed_summary,
            expected_target_seed_summary_sha256=(fixture.target_seed_summary_sha256),
            target_store_path=fixture.target_store,
            target_batch_id=fixture.target_batch_id,
            expected_target_cycle_hash=fixture.target_cycle_hash,
            contract_output_path=tmp_path / "refused-payload.json",
            source_spec=fixture.spec,
        )


@pytest.mark.parametrize(
    "command",
    ("plan-exact310-rest-rebind", "rebind-exact310-rest-observations"),
)
def test_exact310_cli_help_is_explicitly_provider_free(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["batch-002", command, "--help"])
    assert exc_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "No network, provider, PACER" in help_text
    assert "fee acknowledgment" in help_text
