"""Issuance tests for the supported document-repair purchase-approval path.

The round trip proven here is the whole point of the module: a fixture repair
tranche projects, a TTY confirmation records, the approval verifies, the v2
policy mints, the executor's own compatibility check accepts it, the ledger
initializes, the runtime verifies, and a paid execution runs -- all offline,
with no provider and no spend.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicyError,
    initialize_case_dev_purchase_journal,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cohort_policy import (
    cohort_reason_policy_taxonomy,
    generate_cohort_policy,
)
from legalforecast.ingestion.document_repair_executor import (
    AcquiredRepairDocument,
    DocumentRepairExecutorError,
    DocumentRepairPurchaseRuntime,
    ResolvedRepairOperation,
    build_document_repair_purchase_authority,
    run_document_repair_execution,
)
from legalforecast.ingestion.document_repair_purchase_approval import (
    DOCUMENT_REPAIR_PURCHASE_RULE,
    DocumentRepairPurchaseApprovalError,
    DocumentRepairPurchaseInputs,
    DocumentRepairPurchaseProjection,
    VerifiedDocumentRepairPurchaseApproval,
    build_document_repair_purchase_approval_request,
    generate_approved_document_repair_purchase_policy,
    initialize_document_repair_purchase_runtime,
    verify_document_repair_purchase_approval,
    verify_document_repair_purchase_policy_binds,
)
from legalforecast.ingestion.purchase_approval import record_purchase_approval

_REVIEWER = "John Hughes"
_RECORDED_AT = "2026-08-17T19:00:00Z"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _manifest_row(candidate_id: str, entry: int, *, free: bool) -> dict[str, object]:
    """Return one observational repair-manifest row.

    Hand-authored fixture: synthetic: true. It mirrors the shape asserted by
    ``tests/test_document_repair_executor.py`` so both suites exercise one
    manifest contract rather than two drifting ones.
    """

    cost = 0.0 if free else 3.0
    return {
        "candidate_id": candidate_id,
        "recommendation": "repair",
        "cost_usd": cost,
        "missing_docs": [
            {
                "entry": entry,
                "role": "reply",
                "cost_usd": cost,
                "free_document_count": int(free),
                "pacer_only_document_count": int(not free),
                "evidence": "synthetic issuance fixture",
                "source": "pass1",
                "opinion_derived": False,
            }
        ],
        "byte_mismatches": [],
        "current_selection": [],
        "required_entries": [],
        "extra_selected": [],
    }


def _snapshot_bytes(candidate_id: str, entry: int, document_id: int, *, free: bool):  # type: ignore[no-untyped-def]
    docket_id = int(candidate_id, 36) + 100
    return _canonical(
        {
            "candidate_id": candidate_id,
            "docket_id": docket_id,
            "entries": [
                {
                    "id": entry + 1000,
                    "docket": docket_id,
                    "entry_number": entry,
                    "recap_documents": [
                        {
                            "id": document_id,
                            "docket_entry_id": entry + 1000,
                            "document_number": str(entry),
                            "attachment_number": None,
                            "is_available": free,
                            "is_private": False,
                            "is_sealed": False,
                            "filepath_local": (
                                f"recap/example/{document_id}.pdf" if free else None
                            ),
                        }
                    ],
                }
            ],
        }
    )


def _cohort_policy_artifact(cycle_budget: str = "100.00") -> dict[str, Any]:
    """Return one verifiable cohort policy with a repair-sized purchase cap."""

    taxonomy = cohort_reason_policy_taxonomy()
    decisions: dict[str, Any] = {
        "cycle_id": "cycle-1-document-repair",
        "cycle_acquisition_hash": "a" * 64,
        "eligibility_anchor": "2026-06-30",
        "stop_rule": {
            "mode": "target_or_deadline",
            "target_clean_cases": 2,
            "search_window_end": "2026-07-26",
            "stop_on_frontier_exhaustion": True,
            "stop_on_budget_headroom_exhaustion": True,
        },
        "window_policy": {
            "overlap_days": 1,
            "backfill_late_indexed": True,
            "refresh_before_purchase": True,
        },
        "refresh_policy": {
            **{field: list(codes) for field, codes in taxonomy.items()},
            "evidence_precedence": {
                "transient": 0,
                "excluded_refreshable": 10,
                "accepted": 20,
                "newly_free": 30,
                "excluded_immutable": 100,
            },
            "transition_semantics": {
                "immutable_reconsideration": "never",
                "transient_supersedes_evidenced": False,
                "higher_rank_supersedes_lower_rank": True,
                "latest_wins_equal_rank": True,
            },
        },
        "packet_completeness": {
            "motion_or_combined_memorandum_required": True,
            "opposition_required_if_docketed": True,
            "reply_required": False,
        },
        "target_motion": {
            "selector": "earliest_eligible_mtd_then_lowest_entry_number",
            "exactly_one_per_candidate": True,
        },
        "purchase_policy": {
            "rule": "buy_cheapest_complete",
            "cycle_budget_usd": cycle_budget,
            "max_per_case_usd": "10.00",
            "reservation_headroom_required": True,
        },
        "disclosure_clearance": {
            "all_documents_require_clearance": True,
            "unknown_or_unscannable": "quarantine",
            "replacement_rule": "next_cheapest_eligible_under_same_cap",
        },
        "reduced_n": {
            "target_clean_cases": 2,
            "claim_tiers": [
                {
                    "minimum_clean_cases": 1,
                    "maximum_clean_cases": 1,
                    "claim_class": "provisional_feasibility",
                    "minimum_prediction_units": None,
                    "insufficient_units_action": None,
                },
                {
                    "minimum_clean_cases": 2,
                    "maximum_clean_cases": 2,
                    "claim_class": "target",
                    "minimum_prediction_units": 1,
                    "insufficient_units_action": "provisional_feasibility",
                },
            ],
            "below_minimum_action": "pilot_only_no_official_cycle",
        },
    }
    return generate_cohort_policy(decisions)


def _fee_schedule() -> dict[str, object]:
    return {
        "source_citation": "https://example.test/public-fee-schedule",
        "verified_at_utc": "2026-08-17T00:00:00Z",
        "includes_service_fees": True,
        "includes_pacer_fees": True,
        "includes_rounding": True,
    }


@pytest.fixture
def tranche(tmp_path: Path) -> dict[str, Any]:
    """Materialize one two-paid-document repair tranche root plus its sources."""

    root = tmp_path / "repair-tranche"
    snapshots = root / "docket-snapshots"
    snapshots.mkdir(parents=True)

    manifest = b"".join(
        _canonical(row)
        for row in (
            _manifest_row("a", 1, free=True),
            _manifest_row("b", 2, free=False),
            _manifest_row("c", 3, free=False),
        )
    )
    manifest_path = root / "repair-manifest.jsonl"
    manifest_path.write_bytes(manifest)

    rows = [json.loads(line) for line in manifest.splitlines()]
    approval_record = {
        "schema_version": "legalforecast.repair_manifest_approval.v2",
        "decision": "approve",
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "maximum_cost_usd": "9.00",
        "max_per_document_usd": "3.00",
        "candidate_count": len(rows),
        "repair_count": sum(row["recommendation"] == "repair" for row in rows),
        "keep_count": sum(row["recommendation"] == "keep" for row in rows),
        "replace_count": sum(row["recommendation"] == "replace" for row in rows),
        "missing_slot_count": sum(len(row["missing_docs"]) for row in rows),
    }
    approval_path = root / "repair-plan-approval.json"
    approval_path.write_bytes(_canonical(approval_record))

    snapshot_payloads = {
        "a": _snapshot_bytes("a", 1, 9001, free=True),
        "b": _snapshot_bytes("b", 2, 9002, free=False),
        "c": _snapshot_bytes("c", 3, 9003, free=False),
    }
    for candidate_id, payload in snapshot_payloads.items():
        (snapshots / f"{candidate_id}.json").write_bytes(payload)

    cohort_artifact = _cohort_policy_artifact()
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.write_bytes(_canonical(cohort_artifact))
    cohort_policy_sha256 = cast(str, cohort_artifact["policy_sha256"])

    snapshot_manifest = _canonical(
        {
            "candidate_sha256": {
                candidate_id: hashlib.sha256(payload).hexdigest()
                for candidate_id, payload in snapshot_payloads.items()
            }
        }
    )
    snapshot_manifest_path = root / "docket-snapshot-manifest.json"
    snapshot_manifest_path.write_bytes(snapshot_manifest)

    lineage = _canonical(
        {
            "docket_snapshot_manifest_sha256": hashlib.sha256(
                snapshot_manifest
            ).hexdigest(),
            "cohort_policy_sha256": cohort_policy_sha256,
        }
    )
    lineage_path = root / "source-lineage.json"
    lineage_path.write_bytes(lineage)

    fee_path = tmp_path / "fee-schedule.json"
    fee_path.write_bytes(_canonical(_fee_schedule()))

    return {
        "inputs": DocumentRepairPurchaseInputs(
            repair_execution_root=root,
            repair_manifest_path=manifest_path,
            repair_plan_approval_path=approval_path,
            docket_snapshot_manifest_path=snapshot_manifest_path,
            source_lineage_path=lineage_path,
            source_lineage_sha256=hashlib.sha256(lineage).hexdigest(),
            docket_snapshot_dir=snapshots,
        ),
        "cohort_policy_path": cohort_path,
        "fee_schedule_path": fee_path,
        "canonical_ledger_path": tmp_path / "ledger/document-repair.sqlite3",
        "private_root": tmp_path / "private-repair-approval",
        "root": root,
    }


def _projection(tranche: Mapping[str, Any]) -> DocumentRepairPurchaseProjection:
    return build_document_repair_purchase_approval_request(
        inputs=cast(DocumentRepairPurchaseInputs, tranche["inputs"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
        canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
    )


def _record(
    tranche: Mapping[str, Any],
    projection: DocumentRepairPurchaseProjection,
    *,
    decision: str = "approve",
    typed_confirmation: str | None = None,
) -> tuple[Path, Path]:
    return record_purchase_approval(
        request=projection.request,
        controlled_private_root=cast(Path, tranche["private_root"]),
        decision=decision,
        typed_confirmation=(
            projection.request.required_confirmation(decision)
            if typed_confirmation is None
            else typed_confirmation
        ),
        reviewer_id=_REVIEWER,
        recorded_at_utc=_RECORDED_AT,
    )


def _verify(
    tranche: Mapping[str, Any], checkpoint: Path, run_card: Path
) -> VerifiedDocumentRepairPurchaseApproval:
    return verify_document_repair_purchase_approval(
        controlled_private_root=cast(Path, tranche["private_root"]),
        checkpoint_path=checkpoint,
        run_card_path=run_card,
        inputs=cast(DocumentRepairPurchaseInputs, tranche["inputs"]),
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
        canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
    )


class _BoundAcquirer:
    """Acquirer bound to the one single-use journal the runtime authenticated."""

    def __init__(
        self,
        runtime: DocumentRepairPurchaseRuntime,
        callback: Callable[[ResolvedRepairOperation], AcquiredRepairDocument],
    ) -> None:
        self.journal = runtime.journal
        self._callback = callback

    def __call__(self, operation: ResolvedRepairOperation) -> AcquiredRepairDocument:
        if operation.route == "pacer_purchase":
            self.journal.submit(operation.recap_document_id)
            self.journal.confirm(
                operation.recap_document_id,
                response={"status": "confirmed"},
                fees={"total_usd": "3.00"},
            )
        return self._callback(operation)


def test_issuance_round_trip_reaches_a_paid_execution_offline(
    tranche: dict[str, Any],
) -> None:
    projection = _projection(tranche)
    request = projection.request

    # The projection is derived, not asserted by the operator: two paid
    # documents at the contract's own USD 3.00 reservation.
    assert request.purchase_document_count == 2
    assert request.selected_case_count == 2
    assert request.per_document_reservation_usd == "3.00"
    assert request.projected_cost_usd == "6.00"
    assert request.remaining_headroom_usd == "94.00"
    assert request.rule == DOCUMENT_REPAIR_PURCHASE_RULE
    assert request.output_commitments["repair_execution"] == (
        "sha256:" + projection.execution.execution_sha256
    )

    checkpoint, run_card = _record(tranche, projection)
    approval = _verify(tranche, checkpoint, run_card)
    artifact = generate_approved_document_repair_purchase_policy(approval)

    # The frozen v2 validator accepts the issued artifact unchanged.
    policy = verify_case_dev_purchase_policy(artifact)
    assert policy.has_verified_approval
    assert policy.per_document_reservation_usd == (
        projection.execution.purchase_budget.cost_per_document
    )

    # The executor's own compatibility check accepts it, consuming nothing.
    bound = verify_document_repair_purchase_policy_binds(
        execution=projection.execution,
        purchase_policy_artifact=artifact,
    )
    assert bound.policy_sha256 == policy.policy_sha256

    policy_path = cast(Path, tranche["root"]) / "approved-purchase-policy.json"
    policy_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    receipt_path = cast(Path, tranche["root"]) / "purchase-ledger-initialization.json"

    issuance = initialize_document_repair_purchase_runtime(
        execution=projection.execution,
        purchase_policy_path=policy_path,
        cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
        initialization_receipt_path=receipt_path,
        initialized_at="2026-08-17T19:05:00Z",
    )
    assert issuance.initialization_receipt["purchase_policy_sha256"] == (
        policy.policy_sha256
    )
    assert cast(Path, tranche["canonical_ledger_path"]).exists()

    ticks = iter(float(value) for value in range(12))
    result = run_document_repair_execution(
        execution=projection.execution,
        purchase_runtime=issuance.runtime,
        acquire=_BoundAcquirer(
            issuance.runtime,
            lambda operation: AcquiredRepairDocument(
                disposition="included",
                source_document_id=operation.recap_document_id,
                document_bytes=f"{operation.document_role} bytes".encode(),
                committed_cost_usd=(
                    "0.00" if operation.route == "courtlistener_free" else "3.00"
                ),
                retry_count=0,
            ),
        ),
        monotonic=lambda: next(ticks),
    )

    assert len(result.acquired_documents) == 3
    assert result.exclusions == ()
    assert result.receipt.committed_cost_usd == "6.00"


def test_initializing_the_ledger_before_authority_is_unrecoverable(
    tranche: dict[str, Any],
) -> None:
    """Why no CLI subcommand initializes the ledger on its own.

    ``build_document_repair_purchase_authority`` requires the canonical ledger
    to be absent; ``verify_document_repair_purchase_runtime`` requires it to be
    present. A separate initialization step therefore closes the window
    permanently: no later process can mint authority for that policy, and
    neither authority nor runtime can be serialized and rebuilt. The supported
    path is ``initialize_document_repair_purchase_runtime``, which performs both
    in the one order that works.
    """

    projection = _projection(tranche)
    checkpoint, run_card = _record(tranche, projection)
    artifact = generate_approved_document_repair_purchase_policy(
        _verify(tranche, checkpoint, run_card)
    )
    policy = verify_case_dev_purchase_policy(artifact)
    receipt_path = cast(Path, tranche["root"]) / "premature-initialization.json"

    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt_path,
        purchase_policy_file_sha256="sha256:" + "c" * 64,
        cohort_policy_file_sha256="sha256:" + "d" * 64,
        initialized_at="2026-08-17T19:04:00Z",
    )

    with pytest.raises(DocumentRepairExecutorError, match="fresh canonical ledger"):
        build_document_repair_purchase_authority(
            execution=projection.execution,
            approved_purchase_policy_artifact=artifact,
        )


def test_chat_wrapped_confirmation_is_rejected(tranche: dict[str, Any]) -> None:
    """A chat-normalized phrase must not record.

    This is the exact defect that produced the 147-document tranche: a
    confirmation string that survived a round trip through a chat client, with
    wrapping whitespace collapsed, was treated as the signed material.
    """

    projection = _projection(tranche)
    exact = projection.request.required_confirmation("approve")
    wrapped = exact.replace(" ", "\n", 1)

    with pytest.raises(ValueError, match="typed confirmation"):
        _record(tranche, projection, typed_confirmation=wrapped)
    with pytest.raises(ValueError, match="typed confirmation"):
        _record(tranche, projection, typed_confirmation=f" {exact} ")
    with pytest.raises(ValueError, match="typed confirmation"):
        _record(tranche, projection, typed_confirmation=exact.lower())
    assert not (cast(Path, tranche["private_root"]) / "run-cards").exists()


def test_tampered_policy_hash_is_named_in_the_refusal(
    tranche: dict[str, Any],
) -> None:
    projection = _projection(tranche)
    checkpoint, run_card = _record(tranche, projection)
    artifact = generate_approved_document_repair_purchase_policy(
        _verify(tranche, checkpoint, run_card)
    )

    tampered = dict(artifact)
    tampered["policy_sha256"] = "f" * 64
    with pytest.raises(CaseDevPurchasePolicyError, match="policy hash"):
        verify_case_dev_purchase_policy(tampered)
    with pytest.raises(DocumentRepairPurchaseApprovalError, match="policy hash"):
        verify_document_repair_purchase_policy_binds(
            execution=projection.execution,
            purchase_policy_artifact=tampered,
        )


def test_policy_bound_to_another_execution_is_refused(
    tranche: dict[str, Any], tmp_path: Path
) -> None:
    """An approval for one tranche must not authorize a different tranche."""

    projection = _projection(tranche)
    checkpoint, run_card = _record(tranche, projection)
    artifact = generate_approved_document_repair_purchase_policy(
        _verify(tranche, checkpoint, run_card)
    )

    # Same sources, one fewer paid case: a genuinely different execution.
    root = cast(Path, tranche["root"])
    manifest = b"".join(
        _canonical(row)
        for row in (
            _manifest_row("a", 1, free=True),
            _manifest_row("b", 2, free=False),
        )
    )
    (root / "repair-manifest.jsonl").write_bytes(manifest)
    rows = [json.loads(line) for line in manifest.splitlines()]
    (root / "repair-plan-approval.json").write_bytes(
        _canonical(
            {
                "schema_version": "legalforecast.repair_manifest_approval.v2",
                "decision": "approve",
                "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "maximum_cost_usd": "9.00",
                "max_per_document_usd": "3.00",
                "candidate_count": len(rows),
                "repair_count": len(rows),
                "keep_count": 0,
                "replace_count": 0,
                "missing_slot_count": sum(len(row["missing_docs"]) for row in rows),
            }
        )
    )
    smaller = _projection(tranche)
    assert smaller.execution.execution_sha256 != projection.execution.execution_sha256

    with pytest.raises(DocumentRepairPurchaseApprovalError, match="output commitment"):
        verify_document_repair_purchase_policy_binds(
            execution=smaller.execution,
            purchase_policy_artifact=artifact,
        )


def test_verification_refuses_a_checkpoint_from_a_changed_tranche(
    tranche: dict[str, Any],
) -> None:
    projection = _projection(tranche)
    checkpoint, run_card = _record(tranche, projection)

    snapshot = cast(Path, tranche["inputs"].docket_snapshot_dir) / "b.json"
    before = snapshot.read_bytes()
    snapshot.write_bytes(
        before.replace(b'"document_number":"2"', b'"document_number":"9"')
    )
    # Guard the mutation itself: a replacement that matched nothing would make
    # this test pass for the wrong reason.
    assert snapshot.read_bytes() != before

    with pytest.raises(DocumentRepairPurchaseApprovalError):
        _verify(tranche, checkpoint, run_card)


def test_lineage_bound_to_a_foreign_cohort_policy_is_refused(
    tranche: dict[str, Any], tmp_path: Path
) -> None:
    """A tranche root must not certify itself against an unread cohort policy."""

    foreign = _cohort_policy_artifact(cycle_budget="250.00")
    foreign_path = tmp_path / "foreign-cohort-policy.json"
    foreign_path.write_bytes(_canonical(foreign))

    with pytest.raises(
        DocumentRepairPurchaseApprovalError, match="different cohort policy"
    ):
        build_document_repair_purchase_approval_request(
            inputs=cast(DocumentRepairPurchaseInputs, tranche["inputs"]),
            cohort_policy_path=foreign_path,
            fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
            canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
        )


def test_projection_refuses_an_already_initialized_ledger(
    tranche: dict[str, Any],
) -> None:
    """Issuance requires the fresh-ledger window the executor also requires."""

    ledger = cast(Path, tranche["canonical_ledger_path"])
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_bytes(b"")

    with pytest.raises(DocumentRepairPurchaseApprovalError, match="fresh ledger"):
        _projection(tranche)


def test_policy_cannot_be_minted_without_replay_verification() -> None:
    with pytest.raises(DocumentRepairPurchaseApprovalError, match="evidence replay"):
        VerifiedDocumentRepairPurchaseApproval()  # type: ignore[call-arg]

    class _Forged:
        request = None
        reviewer_id = _REVIEWER
        recorded_at_utc = _RECORDED_AT
        typed_confirmation_sha256 = "1" * 64
        checkpoint_sha256 = "2" * 64
        run_card_sha256 = "3" * 64

        def is_replay_minted(self) -> bool:
            return True

    with pytest.raises(DocumentRepairPurchaseApprovalError, match="minted only"):
        generate_approved_document_repair_purchase_policy(
            cast(VerifiedDocumentRepairPurchaseApproval, _Forged())
        )


def test_free_only_tranche_needs_no_purchase_approval(tranche: dict[str, Any]) -> None:
    root = cast(Path, tranche["root"])
    manifest = b"".join(
        _canonical(row)
        for row in (
            _manifest_row("a", 1, free=True),
            _manifest_row("b", 2, free=True),
        )
    )
    (root / "repair-manifest.jsonl").write_bytes(manifest)
    rows = [json.loads(line) for line in manifest.splitlines()]
    (root / "repair-plan-approval.json").write_bytes(
        _canonical(
            {
                "schema_version": "legalforecast.repair_manifest_approval.v2",
                "decision": "approve",
                "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "maximum_cost_usd": "9.00",
                "max_per_document_usd": "3.00",
                "candidate_count": len(rows),
                "repair_count": len(rows),
                "keep_count": 0,
                "replace_count": 0,
                "missing_slot_count": sum(len(row["missing_docs"]) for row in rows),
            }
        )
    )
    snapshots = cast(Path, tranche["inputs"].docket_snapshot_dir)
    (snapshots / "b.json").write_bytes(_snapshot_bytes("b", 2, 9002, free=True))
    manifest_path = cast(Path, tranche["inputs"].docket_snapshot_manifest_path)
    payloads = {
        candidate_id: (snapshots / f"{candidate_id}.json").read_bytes()
        for candidate_id in ("a", "b", "c")
    }
    manifest_path.write_bytes(
        _canonical(
            {
                "candidate_sha256": {
                    candidate_id: hashlib.sha256(payload).hexdigest()
                    for candidate_id, payload in payloads.items()
                }
            }
        )
    )
    lineage_path = cast(Path, tranche["inputs"].source_lineage_path)
    cohort = json.loads(cast(Path, tranche["cohort_policy_path"]).read_bytes())
    lineage = _canonical(
        {
            "docket_snapshot_manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
            "cohort_policy_sha256": cohort["policy_sha256"],
        }
    )
    lineage_path.write_bytes(lineage)
    inputs = cast(DocumentRepairPurchaseInputs, tranche["inputs"])
    refreshed = DocumentRepairPurchaseInputs(
        repair_execution_root=inputs.repair_execution_root,
        repair_manifest_path=inputs.repair_manifest_path,
        repair_plan_approval_path=inputs.repair_plan_approval_path,
        docket_snapshot_manifest_path=inputs.docket_snapshot_manifest_path,
        source_lineage_path=inputs.source_lineage_path,
        source_lineage_sha256=hashlib.sha256(lineage).hexdigest(),
        docket_snapshot_dir=inputs.docket_snapshot_dir,
    )

    with pytest.raises(DocumentRepairPurchaseApprovalError, match="no paid operations"):
        build_document_repair_purchase_approval_request(
            inputs=refreshed,
            cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
            fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
            canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
        )


def test_input_outside_the_recorded_root_is_refused(
    tranche: dict[str, Any], tmp_path: Path
) -> None:
    """The recorded root must actually contain what was signed."""

    outside = tmp_path / "outside-manifest.jsonl"
    outside.write_bytes(cast(Path, tranche["inputs"].repair_manifest_path).read_bytes())
    inputs = cast(DocumentRepairPurchaseInputs, tranche["inputs"])
    escaped = DocumentRepairPurchaseInputs(
        repair_execution_root=inputs.repair_execution_root,
        repair_manifest_path=outside,
        repair_plan_approval_path=inputs.repair_plan_approval_path,
        docket_snapshot_manifest_path=inputs.docket_snapshot_manifest_path,
        source_lineage_path=inputs.source_lineage_path,
        source_lineage_sha256=inputs.source_lineage_sha256,
        docket_snapshot_dir=inputs.docket_snapshot_dir,
    )

    with pytest.raises(DocumentRepairPurchaseApprovalError, match="escapes"):
        build_document_repair_purchase_approval_request(
            inputs=escaped,
            cohort_policy_path=cast(Path, tranche["cohort_policy_path"]),
            fee_schedule_path=cast(Path, tranche["fee_schedule_path"]),
            canonical_ledger_path=cast(Path, tranche["canonical_ledger_path"]),
        )
