from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypedDict

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.ranked_reserve_replacement import (
    RankedReserveReplacementError,
    bind_ranked_reserve_outputs,
    plan_ranked_reserve_replacements,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionStage,
    merge_exclusion_ledger_records,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures


@pytest.fixture
def _historical_v1_algorithm_fixture(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


def test_exact_100_plus_five_promotes_first_reserve_and_reconciles(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        plan = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=_terminal_bytes("case-050"),
            expected_terminal_exclusions_sha256=_sha(_terminal_bytes("case-050")),
            purchase_journal=journal,
        )

    assert len(plan.active_selection) == 100
    assert plan.active_candidate_ids[50] == "case-100"
    assert [row["candidate_id"] for row in plan.replacement_selection] == ["case-100"]
    assert [row.candidate_id for row in plan.replacement_plan.case_plans] == [
        "case-100"
    ]
    assert plan.successor_approval_required is True
    assert plan.replacement_plan.dry_run is False
    selected = set(plan.active_candidate_ids)
    excluded = {str(row["candidate_id"]) for row in plan.successor_exclusions}
    assert selected.isdisjoint(excluded)
    assert selected | excluded == {f"case-{index:03d}" for index in range(105)}
    assert "case-100" not in excluded
    assert "case-050" in excluded
    terminal_exclusion = next(
        row for row in plan.successor_exclusions if row["candidate_id"] == "case-050"
    )
    assert terminal_exclusion["stage"] == "unitization"
    assert terminal_exclusion["source_stage"] == "apply-unitization-review"
    round_tripped = merge_exclusion_ledger_records((terminal_exclusion,))
    assert round_tripped.entries[0].stage is ExclusionStage.UNITIZATION
    assert plan.committed_spend_usd == "3.05"
    assert plan.reserved_replacement_spend_usd == "3.05"
    assert plan.remaining_headroom_usd == "0.00"
    assert plan.paid_activity_requested is False
    assert plan.paid_activity_executed is False


@pytest.mark.parametrize(
    ("terminal", "retryable"),
    ((False, False), (True, True)),
)
def test_retryable_or_nonterminal_evidence_never_consumes_a_reserve(
    tmp_path: Path,
    terminal: bool,
    retryable: bool,
) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_record("case-050")
    evidence["terminal"] = terminal
    evidence["retryable"] = retryable
    payload = _jsonl((evidence,))

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(
            RankedReserveReplacementError,
            match="explicit terminal nonretryable",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=payload,
                expected_terminal_exclusions_sha256=_sha(payload),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_unknown_terminal_stage_fails_before_journal_mutation(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_record("case-050")
    evidence["source_stage"] = "unsupported-downstream-stage"
    payload = _jsonl((evidence,))

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(
            RankedReserveReplacementError,
            match="terminal exclusion source stage is unsupported",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=payload,
                expected_terminal_exclusions_sha256=_sha(payload),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_reserve_commitment_tamper_fails_before_journal_mutation(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    tampered = fixture["reserve_bytes"].replace(
        b'"reserve_rank":1', b'"reserve_rank":9'
    )

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(RankedReserveReplacementError, match="reserve bytes"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=tampered,
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=_terminal_bytes("case-050"),
                expected_terminal_exclusions_sha256=_sha(_terminal_bytes("case-050")),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_result_binds_exact_successor_and_tranche_bytes(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        plan = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=evidence,
            expected_terminal_exclusions_sha256=_sha(evidence),
            purchase_journal=journal,
        )

    active = _jsonl(plan.active_selection)
    replacements = _jsonl(plan.replacement_selection)
    exclusions = _jsonl(plan.successor_exclusions)
    result = bind_ranked_reserve_outputs(
        plan,
        active_selection_bytes=active,
        replacement_selection_bytes=replacements,
        successor_exclusions_bytes=exclusions,
        replacement_budget_plan_bytes=_canonical_json(
            plan.replacement_plan.to_record()
        ),
    )

    assert result["active_selection_sha256"] == _sha(active)
    assert result["replacement_selection_sha256"] == _sha(replacements)
    assert result["successor_exclusions_sha256"] == _sha(exclusions)
    assert result["replacement_budget_plan_sha256"] == _sha(
        _canonical_json(plan.replacement_plan.to_record())
    )
    assert result["purchase_policy_sha256"] == (
        "sha256:" + fixture["policy"].policy_sha256
    )
    assert result["purchase_journal_state_sha256"].startswith("sha256:")
    assert result["successor_approval_required"] is True
    assert result["provider_activity_requested"] is False
    assert result["evaluation_authorized"] is False
    assert result["freeze_authorized"] is False
    assert result["dispatch_authorized"] is False


def test_replay_is_idempotent_and_later_terminal_reserve_uses_next_rank(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    first_evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        first = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=first_evidence,
            expected_terminal_exclusions_sha256=_sha(first_evidence),
            purchase_journal=journal,
        )
        replay = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=first_evidence,
            expected_terminal_exclusions_sha256=_sha(first_evidence),
            purchase_journal=journal,
        )
        second_evidence = _terminal_bytes("case-100")
        second = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=second_evidence,
            expected_terminal_exclusions_sha256=_sha(second_evidence),
            purchase_journal=journal,
        )
        replacement_event_count = len(journal.replacement_events())

    assert [row["candidate_id"] for row in first.replacement_selection] == ["case-100"]
    assert replay.replacement_selection == ()
    assert replay.active_selection == first.active_selection
    assert replay.active_candidate_ids == first.active_candidate_ids
    assert replay.successor_exclusions == first.successor_exclusions
    assert replay.successor_approval_required is False
    assert [row["candidate_id"] for row in second.replacement_selection] == ["case-101"]
    assert second.active_candidate_ids[50] == "case-101"
    assert {row["candidate_id"] for row in second.successor_exclusions} >= {
        "case-050",
        "case-100",
    }
    assert replacement_event_count == 2


def test_failed_purchase_with_response_is_not_double_reserved(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    first_evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        first = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=first_evidence,
            expected_terminal_exclusions_sha256=_sha(first_evidence),
            purchase_journal=journal,
        )
        journal.plan(first.replacement_plan)
        assert journal.submit("doc-100") is True
        journal.queue("doc-100", response={"queue_id": "queue-100"})
        journal.fail("doc-100", RuntimeError("provider failed after response"))
        operation = journal.operation_records()[0]
        assert operation["status"] == "failed"
        assert operation["response"] is not None
        assert operation["reconciliation"] is None
        assert journal.committed_amount_usd == "6.10"

        second_evidence = _terminal_bytes("case-100")
        second = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=second_evidence,
            expected_terminal_exclusions_sha256=_sha(second_evidence),
            purchase_journal=journal,
        )

    assert [row["candidate_id"] for row in second.replacement_selection] == ["case-101"]
    assert second.committed_spend_usd == "6.10"
    assert second.reserved_replacement_spend_usd == "3.05"
    assert second.remaining_headroom_usd == "0.00"


def test_hard_cap_blocks_next_rank_before_journal_mutation(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="6.09")
    evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(RankedReserveReplacementError, match="headroom"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=evidence,
                expected_terminal_exclusions_sha256=_sha(evidence),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_multi_exclusion_cap_failure_appends_no_partial_event(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.14")
    evidence = _jsonl((_terminal_record("case-050"), _terminal_record("case-051")))
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(RankedReserveReplacementError, match="headroom"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=evidence,
                expected_terminal_exclusions_sha256=_sha(evidence),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_incompatible_replacement_history_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        journal.append_replacement_event(
            "legacy-clearance-event",
            {"schema_version": "legalforecast.clearance_replacement_event.v1"},
        )
        with pytest.raises(RankedReserveReplacementError, match="incompatible"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=evidence,
                expected_terminal_exclusions_sha256=_sha(evidence),
                purchase_journal=journal,
            )
        assert len(journal.replacement_events()) == 1


def test_cli_replays_full_projection_and_emits_provider_free_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    target_root = tmp_path / "target"
    summary_path = target_root / "target-cohort-projection.json"
    selection_path = target_root / "target-cohort-selection.jsonl"
    reserve_path = target_root / "target-cohort-ranked-reserve.jsonl"
    exclusions_path = target_root / "target-cohort-exclusions.jsonl"
    source_path = Path("/frozen/public-packet-selection-reconciled.jsonl")
    verified_bytes = {
        str(summary_path.resolve()): _canonical_json(fixture["projection"]),
        str(selection_path.resolve()): fixture["selected_bytes"],
        str(reserve_path.resolve()): fixture["reserve_bytes"],
        str(exclusions_path.resolve()): fixture["exclusions_bytes"],
        str(source_path): fixture["source_pool_bytes"],
    }

    def verified_projection(_root: Path) -> dict[str, object]:
        return {
            "summary": fixture["projection"],
            "summary_path": summary_path,
            "selection_path": selection_path,
            "verified_artifact_bytes": verified_bytes,
        }

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        verified_projection,
    )
    terminal = _terminal_bytes("case-050")
    terminal_path = tmp_path / "terminal.jsonl"
    terminal_path.write_bytes(terminal)
    digest_path = tmp_path / "terminal.sha256"
    digest_path.write_text(_sha(terminal) + "\n")
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_canonical_json(dict(fixture["policy"].artifact)))
    receipt_path = tmp_path / "initialization.json"
    receipt_path.write_text("{}\n")
    controlled_private_root = tmp_path / "private"
    controlled_private_root.mkdir()
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ):
        pass
    outputs = {
        "result": tmp_path / "result.json",
        "active": tmp_path / "active.jsonl",
        "replacement": tmp_path / "replacement.jsonl",
        "exclusions": tmp_path / "successor-exclusions.jsonl",
        "budget": tmp_path / "budget.json",
    }

    command = [
        "acquisition",
        "plan-ranked-reserve-replacements",
        "--target-cohort-root",
        str(target_root),
        "--purchase-policy",
        str(policy_path),
        "--controlled-private-root",
        str(controlled_private_root),
        "--purchase-ledger",
        str(fixture["policy"].canonical_ledger_path),
        "--purchase-ledger-initialization-receipt",
        str(receipt_path),
        "--terminal-exclusions",
        str(terminal_path),
        "--terminal-exclusions-sha256-file",
        str(digest_path),
        "--output",
        str(outputs["result"]),
        "--active-selection-output",
        str(outputs["active"]),
        "--replacement-selection-output",
        str(outputs["replacement"]),
        "--successor-exclusions-output",
        str(outputs["exclusions"]),
        "--replacement-budget-plan-output",
        str(outputs["budget"]),
    ]
    status = cli.main(command)

    assert status == 0
    result = json.loads(outputs["result"].read_bytes())
    artifact_commitments = (
        ("active", "active_selection_sha256"),
        ("replacement", "replacement_selection_sha256"),
        ("exclusions", "successor_exclusions_sha256"),
        ("budget", "replacement_budget_plan_sha256"),
    )
    for artifact_name, commitment_name in artifact_commitments:
        assert _sha(outputs[artifact_name].read_bytes()) == result[commitment_name]
    assert result["active_case_count"] == 100
    assert result["successor_approval_required"] is True
    assert result["provider_activity_requested"] is False
    assert json.loads(capsys.readouterr().out)["paid_activity_executed"] is False

    original_outputs = {name: path.read_bytes() for name, path in outputs.items()}
    replay_status = cli.main(command)
    replay_console = capsys.readouterr()

    assert replay_status == 2
    assert "immutable output differs" in replay_console.err
    replayed_outputs = {name: path.read_bytes() for name, path in outputs.items()}
    assert replayed_outputs == original_outputs


def test_v4_continuation_template_has_no_paid_or_downstream_stage() -> None:
    template_path = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.v4-ranked-reserve-replacement-plan.template.json"
    )
    template = json.loads(template_path.read_bytes())

    assert template["schema_version"] == (
        "legalforecast.ranked_reserve_replacement_plan_template.v1"
    )
    assert template["command"]["name"] == "plan-ranked-reserve-replacements"
    assert template["command"]["boundary"] == "provider_free"
    assert template["authority"] == {
        "dispatch_authorized": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "paid_activity_executed": False,
        "paid_activity_requested": False,
        "paid_replacement_requires_separate_successor_approval": True,
        "provider_activity_requested": False,
    }


class _Fixture(TypedDict):
    policy: CaseDevPurchasePolicy
    projection: dict[str, object]
    selected_bytes: bytes
    reserve_bytes: bytes
    source_pool_bytes: bytes
    exclusions_bytes: bytes


def _fixture(tmp_path: Path, *, hard_cap_usd: str = "6.10") -> _Fixture:
    selected = tuple(_selection(index) for index in range(100))
    reserves = tuple(_reserve(index) for index in range(100, 105))
    source_pool = tuple(_selection(index) for index in range(105))
    exclusions = tuple(_omission(index) for index in range(100, 105))
    selected_bytes = _jsonl(selected)
    reserve_bytes = _jsonl(reserves)
    source_pool_bytes = _jsonl(source_pool)
    exclusions_bytes = _jsonl(exclusions)
    policy_artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-v4-ranked-reserve-test",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str((tmp_path / "purchase.sqlite3").resolve()),
            "hard_cap_usd": hard_cap_usd,
            "opening_committed_spend_usd": "3.05",
            "opening_case_committed_spend_usd": {"historical": "3.05"},
            "max_per_case_usd": hard_cap_usd,
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-08-04T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    policy = verify_case_dev_purchase_policy(policy_artifact)
    projection: dict[str, object] = {
        "schema_version": "legalforecast.target_cohort_projection.v1",
        "projection_sha256": "sha256:" + "1" * 64,
        "resolved_pool_case_count": 105,
        "post_clearance_case_count": 105,
        "selected_case_count": 100,
        "ranked_reserve_case_count": 5,
        "selected_candidate_ids_sha256": _canonical_sha(
            [row["candidate_id"] for row in selected]
        ),
        "ranked_reserve_candidate_ids_sha256": _canonical_sha(
            [row["candidate_id"] for row in reserves]
        ),
        "ranked_reserve_sha256": _canonical_sha(reserves),
        "output_commitments": {
            "target-cohort-selection.jsonl": _sha(selected_bytes),
            "target-cohort-ranked-reserve.jsonl": _sha(reserve_bytes),
            "target-cohort-exclusions.jsonl": _sha(exclusions_bytes),
        },
        "input_commitments": {
            "/frozen/public-packet-selection-reconciled.jsonl": _sha(source_pool_bytes)
        },
    }
    return {
        "policy": policy,
        "projection": projection,
        "selected_bytes": selected_bytes,
        "reserve_bytes": reserve_bytes,
        "source_pool_bytes": source_pool_bytes,
        "exclusions_bytes": exclusions_bytes,
    }


def _selection(index: int) -> dict[str, object]:
    candidate_id = f"case-{index:03d}"
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "court-a",
        "decision_date": "2026-07-01",
        "documents": [],
    }


def _reserve(index: int) -> dict[str, object]:
    candidate_id = f"case-{index:03d}"
    rank = index - 99
    return {
        "schema_version": "legalforecast.target_cohort_ranked_reserve.v1",
        "reserve_rank": rank,
        "frontier_rank": 100 + rank,
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "court-a",
        "decision_date": "2026-07-01",
        "missing_core_document_count": 1,
        "missing_core_roles": ["complaint"],
        "purchase_document_ids": [f"doc-{index:03d}"],
        "estimated_cost_usd": "3.05",
        "ranking_key": [1, "3.05", candidate_id],
    }


def _omission(index: int) -> dict[str, object]:
    candidate_id = f"case-{index:03d}"
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "court-a",
        "decision_date": None,
        "notes": (
            "Candidate was outside the deterministic cheapest exact-cohort prefix."
        ),
        "primary_exclusion_reason": "target_cohort_frontier_omitted",
        "reason": "target_cohort_frontier_omitted",
        "related_family_id": None,
        "secondary_exclusion_reasons": [],
        "source_document_ids": [],
        "source_entry_ids": [],
        "stage": "extraction",
    }


def _terminal_record(candidate_id: str) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.ranked_reserve_terminal_exclusion.v1",
        "candidate_id": candidate_id,
        "reason": "stage_a_boundary_unresolvable",
        "source_stage": "apply-unitization-review",
        "source_artifact_sha256": "sha256:" + "2" * 64,
        "source_record_sha256": "sha256:" + "3" * 64,
        "terminal": True,
        "retryable": False,
    }


def _terminal_bytes(candidate_id: str) -> bytes:
    return _jsonl((_terminal_record(candidate_id),))


def _jsonl(records: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(
        json.dumps(
            record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
        + b"\n"
        for record in records
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return _sha(payload)


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    )
