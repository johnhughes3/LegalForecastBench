from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

import legalforecast.cli as cli
import legalforecast.ingestion.recap_fetch_attempt_policy as attempt_module
import legalforecast.ingestion.recap_fetch_broker_policy as broker_module
import legalforecast.ingestion.resolved_post_recovery as resolved_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
    CaseDevPurchasePolicy,
    CaseDevPurchasePolicyError,
    generate_case_dev_purchase_policy,
    initialize_case_dev_purchase_journal,
    read_case_dev_purchase_snapshot,
    require_approved_case_dev_purchase_policy,
    verify_approved_purchase_input_bytes,
    verify_case_dev_purchase_journal_initialization,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
    write_case_dev_purchase_policy,
)
from legalforecast.ingestion.clearance_replacement import (
    ClearanceReplacementError,
    build_replacement_frontier,
)
from legalforecast.ingestion.cohort_policy import generate_cohort_policy
from legalforecast.ingestion.cycle_acquisition_store import (
    cohort_reason_policy_taxonomy,
)
from legalforecast.ingestion.disclosure_review_authority import (
    disclosure_authority_identity_from_cohort_policy,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.purchase_approval import (
    PurchaseApprovalError,
    VerifiedPurchaseApproval,
    build_purchase_approval_request,
    generate_approved_purchase_policy,
    record_purchase_approval,
    replay_approved_purchase_policy,
    resume_purchase_approval_recording,
    verify_purchase_approval,
)
from legalforecast.ingestion.recap_fetch_attempt_policy import (
    RecapFetchAttemptPolicyError,
    generate_recap_fetch_attempt_policy,
    verify_recap_fetch_attempt_policy,
)
from legalforecast.ingestion.recap_fetch_broker_policy import (
    RecapFetchBrokerPolicyError,
    generate_recap_fetch_broker_policy,
    verify_recap_fetch_broker_policy,
)
from legalforecast.ingestion.target_cohort_projection import project_target_cohort
from tests.disclosure_review_fixtures import (
    service_disclosure_authority_from_policy_bytes,
)
from tests.purchase_approval_fixtures import LEGACY_V1_BYPASS_MODULES
from tests.test_target_100_acquisition import (
    _snapshot_manifest_sha256,
    _target_100_fixture,
    _write_authenticated_reviews,
)
from tests.test_target_cohort_projection import (
    _clearance,
    _download,
    _relevance,
    _selection,
)


@pytest.fixture(autouse=True)
def _unit_projection_authority(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Unit fixtures exercise replay below; CLI integration covers full lineage."""

    if request.node.name == "test_real_authenticated_exact_100_with_15_omitted":
        return

    def captured_projection(root: Path) -> dict[str, object]:
        run_card_path = root / "run-cards/project-target-cohort.json"
        run_card_bytes = run_card_path.read_bytes()
        run_card = json.loads(run_card_bytes)
        paths = [
            run_card_path,
            *(Path(value) for value in run_card["input_paths"]),
            *(Path(value) for value in run_card["output_paths"]),
        ]
        return {
            "verified_artifact_bytes": {
                os.path.abspath(path): path.read_bytes() for path in paths
            }
        }

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        captured_projection,
    )


def test_approved_checkpoint_binds_exact_projection_and_generates_v2(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )

    checkpoint_path, run_card_path = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    verified = verify_purchase_approval(
        controlled_private_root=private_root,
        checkpoint_path=checkpoint_path,
        run_card_path=run_card_path,
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    artifact = generate_approved_purchase_policy(verified)
    policy = verify_case_dev_purchase_policy(artifact)
    require_approved_case_dev_purchase_policy(
        policy, controlled_private_root=private_root
    )

    assert artifact["schema_version"] == "legalforecast.case_dev_purchase_policy.v2"
    approval = artifact["policy"]["approval"]
    assert "verification_inputs" not in approval
    assert str(private_root) not in json.dumps(artifact, sort_keys=True)
    assert approval["decision"] == "approve"
    assert approval["target_case_count"] == 2
    assert approval["selected_case_count"] == 2
    assert approval["purchase_document_count"] == 2
    assert approval["projected_cost_usd"] == "6.10"
    assert approval["hard_cap_usd"] == "100.00"
    assert approval["remaining_headroom_usd"] == "93.90"
    assert artifact["policy"]["per_document_reservation_usd"] == "3.05"
    assert policy.has_verified_approval is True


@pytest.mark.parametrize("source", ["cohort", "fee"])
@pytest.mark.parametrize("alias", ["relative", "dot"])
def test_approval_sources_require_absolute_normalized_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    alias: str,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    selected = cohort_policy if source == "cohort" else fee_schedule
    if alias == "relative":
        aliased = Path(selected.name)
    else:
        (tmp_path / "alias-parent").mkdir()
        aliased = tmp_path / "alias-parent" / ".." / selected.name

    with pytest.raises(PurchaseApprovalError, match="absolute normalized path"):
        build_purchase_approval_request(
            target_cohort_root=target_root,
            cohort_policy_path=aliased if source == "cohort" else cohort_policy,
            fee_schedule_path=aliased if source == "fee" else fee_schedule,
            canonical_ledger_path=(tmp_path / "ledger.sqlite3").resolve(),
        )


def test_approval_replay_is_independent_of_current_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint, run_card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    verified = verify_purchase_approval(
        controlled_private_root=private_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )

    assert verified.request == request


@pytest.mark.parametrize("decision", ["reject", "free_only"])
def test_nonapproval_decisions_never_mint_purchase_authority(
    tmp_path: Path, decision: str
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint_path, run_card_path = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision=decision,
        typed_confirmation=request.required_confirmation(decision),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )

    with pytest.raises(PurchaseApprovalError, match="does not authorize purchases"):
        verify_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint_path,
            run_card_path=run_card_path,
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=ledger,
        )


def test_verified_purchase_approval_cannot_be_constructed_by_callers() -> None:
    with pytest.raises(PurchaseApprovalError, match="only by evidence replay"):
        VerifiedPurchaseApproval(
            request=object(),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-26T00:00:00Z",
            typed_confirmation_sha256="a" * 64,
            checkpoint_sha256="b" * 64,
            run_card_sha256="c" * 64,
        )


def test_recorder_resume_is_byte_idempotent(tmp_path: Path) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=(tmp_path / "ledger.sqlite3").resolve(),
    )
    kwargs = {
        "request": request,
        "controlled_private_root": private_root,
        "decision": "approve",
        "typed_confirmation": request.required_confirmation("approve"),
        "reviewer_id": "John Hughes",
        "recorded_at_utc": "2026-07-26T15:00:00Z",
    }
    checkpoint_path, run_card_path = record_purchase_approval(**kwargs)
    before = {path: path.read_bytes() for path in (checkpoint_path, run_card_path)}

    assert record_purchase_approval(**kwargs, resume=True) == (
        checkpoint_path,
        run_card_path,
    )
    assert {path: path.read_bytes() for path in before} == before

    expected_run_card = before[run_card_path]
    run_card_path.unlink()
    assert resume_purchase_approval_recording(
        request=request,
        controlled_private_root=private_root,
    ) == (checkpoint_path, run_card_path)
    assert run_card_path.read_bytes() == expected_run_card


@pytest.mark.parametrize(
    "relative_path",
    [
        "target-cohort-selection.jsonl",
        "missing-core-budget-plan.json",
        "target-cohort-projection.json",
        "run-cards/project-target-cohort.json",
    ],
)
def test_verifier_rejects_projection_tampering(
    tmp_path: Path, relative_path: str
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint_path, run_card_path = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    target = target_root / relative_path
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(PurchaseApprovalError):
        verify_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint_path,
            run_card_path=run_card_path,
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=ledger,
        )


def test_authoritative_projection_lineage_verifier_cannot_be_bypassed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    invoked: list[Path] = []

    def reject_self_consistent_forgery(root: Path) -> dict[str, object]:
        invoked.append(root)
        raise cli.CommandError("authenticated clearance lineage differs")

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        reject_self_consistent_forgery,
    )
    with pytest.raises(PurchaseApprovalError, match="authenticated target projection"):
        build_purchase_approval_request(
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=(tmp_path / "ledger.sqlite3").resolve(),
        )
    assert invoked == [target_root]


def test_projection_swap_after_authoritative_verifier_uses_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    selection_path = target_root / "target-cohort-selection.jsonl"
    original_bytes = selection_path.read_bytes()
    authoritative = cli.verify_completed_target_cohort_projection_for_purchase_approval

    def swap_after_capture(root: Path) -> dict[str, object]:
        verified = authoritative(root)
        selection_path.write_bytes(b'{"candidate_id":"swapped-after-verify"}\n')
        return verified

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        swap_after_capture,
    )
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=(tmp_path / "ledger.sqlite3").resolve(),
    )

    assert request.selection_sha256 == hashlib.sha256(original_bytes).hexdigest()
    assert selection_path.read_bytes() != original_bytes


def test_cli_records_verifies_and_publishes_without_provider_activity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )

    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    answers = iter(("approve", request.required_confirmation("approve")))
    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    shared = [
        "--target-cohort-root",
        str(target_root),
        "--cohort-policy",
        str(cohort_policy),
        "--fee-schedule",
        str(fee_schedule),
        "--canonical-ledger-path",
        str(ledger),
        "--controlled-private-root",
        str(private_root),
    ]
    assert (
        main(
            [
                "acquisition",
                "record-purchase-approval",
                "--output-root",
                str(private_root),
                *shared,
                "--execute",
                "--no-resume",
            ]
        )
        == 0
    )
    checkpoint = private_root / "purchase-approval-checkpoint.json"
    run_card = private_root / "run-cards/record-purchase-approval.json"
    evidence = ["--checkpoint", str(checkpoint), "--approval-run-card", str(run_card)]
    assert main(["acquisition", "verify-purchase-approval", *shared, *evidence]) == 0
    output = tmp_path / "purchase-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-purchase-policy",
                "--output",
                str(output),
                *shared,
                *evidence,
            ]
        )
        == 0
    )
    artifact = json.loads(output.read_text())
    assert artifact["schema_version"] == "legalforecast.case_dev_purchase_policy.v2"
    init_root = tmp_path / "initialized-purchase-ledger"
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--output-root",
                str(init_root),
                "--purchase-policy",
                str(output),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(ledger),
                "--controlled-private-root",
                str(private_root),
                "--execute",
                "--no-resume",
            ]
        )
        == 0
    )
    assert ledger.exists()
    assert (init_root / "purchase-ledger-initialization.json").exists()


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink"])
def test_verifier_rejects_aliased_private_checkpoint(
    tmp_path: Path, unsafe: str
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint_path, run_card_path = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    alias = private_root / "checkpoint-alias.json"
    if unsafe == "symlink":
        alias.symlink_to(checkpoint_path)
        checkpoint_path = alias
    else:
        os.link(checkpoint_path, alias)

    with pytest.raises(
        (PurchaseApprovalError, ValueError),
        match=r"unique regular|controlled-store locations",
    ):
        verify_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint_path,
            run_card_path=run_card_path,
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=ledger,
        )


def test_exact_raw_projection_bytes_reject_mutation_and_missing_inputs(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    policy = verify_case_dev_purchase_policy(
        _record_approved_policy(
            tmp_path,
            target_root=target_root,
            cohort_policy=cohort_policy,
            fee_schedule=fee_schedule,
        )
    )
    budget_bytes = (target_root / "missing-core-budget-plan.json").read_bytes()
    selection_bytes = (target_root / "target-cohort-selection.jsonl").read_bytes()

    assert verify_approved_purchase_input_bytes(
        policy,
        controlled_private_root=(tmp_path / "private-authority").resolve(),
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
    ) == (("case-a", "case-b"), ("case-a-mtd-0", "case-b-mtd-0"))
    with pytest.raises(CaseDevPurchasePolicyError, match="exact approved"):
        verify_approved_purchase_input_bytes(
            policy,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
            budget_plan_bytes=None,
            selection_bytes=selection_bytes,
        )
    with pytest.raises(CaseDevPurchasePolicyError, match="budget plan bytes"):
        verify_approved_purchase_input_bytes(
            policy,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
            budget_plan_bytes=budget_bytes + b"\n",
            selection_bytes=selection_bytes,
        )
    with pytest.raises(CaseDevPurchasePolicyError, match="selection bytes"):
        verify_approved_purchase_input_bytes(
            policy,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
            budget_plan_bytes=budget_bytes,
            selection_bytes=selection_bytes + b"\n",
        )


def test_generators_reject_structured_document_ids_detached_from_approved_bytes(
    tmp_path: Path,
) -> None:
    target_root, cohort_path, fee_schedule = _projection_fixture(
        tmp_path, numeric_purchase_document_ids=True
    )
    private_root = (tmp_path / "private-authority").resolve()
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_path,
        fee_schedule=fee_schedule,
    )
    budget_bytes = (target_root / "missing-core-budget-plan.json").read_bytes()
    selection_bytes = (target_root / "target-cohort-selection.jsonl").read_bytes()
    authentic_budget = json.loads(budget_bytes)
    forged_budget = deepcopy(authentic_budget)
    forged_budget["case_plans"][0]["purchase_document_ids"] = ["999"]
    forged_budget["case_plans"][1]["purchase_document_ids"] = ["1000"]
    forged_plan = cli._missing_core_budget_plan(forged_budget)
    selection_records = tuple(
        json.loads(line) for line in selection_bytes.splitlines() if line
    )
    common = {
        "purchase_policy_artifact": artifact,
        "cohort_policy_artifact": json.loads(cohort_path.read_text()),
        "budget_plan": forged_plan,
        "budget_plan_artifact": forged_budget,
        "selection_records": selection_records,
        "budget_plan_bytes": budget_bytes,
        "selection_bytes": selection_bytes,
        "controlled_private_root": private_root,
    }

    with pytest.raises(RecapFetchAttemptPolicyError, match="structure differs"):
        generate_recap_fetch_attempt_policy(**common)
    with pytest.raises(RecapFetchBrokerPolicyError, match="structure differs"):
        generate_recap_fetch_broker_policy(**common)


def test_mutated_under_cap_cli_inputs_fail_before_runtime_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_json_bytes(artifact))
    approved_selection = target_root / "target-cohort-selection.jsonl"
    selection_path = tmp_path / "mutated-under-cap-selection.jsonl"
    # Whitespace-only JSONL drift leaves every candidate and dollar bound intact.
    selection_path.write_bytes(approved_selection.read_bytes() + b"\n")
    output_root = tmp_path / "must-not-exist"
    touched: list[str] = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        touched.append("runtime")
        raise AssertionError("changed approved bytes reached runtime state")

    for name in (
        "_acquisition_output_root",
        "_write_json",
        "_write_acquisition_failure",
        "CaseDevPurchaseJournal",
        "CourtListenerRecapFetchConfig",
        "RecapFetchBrokerConfig",
    ):
        monkeypatch.setattr(cli, name, forbidden)
    args = cli.argparse.Namespace(
        purchase_policy=policy_path,
        controlled_private_root=(tmp_path / "private-authority").resolve(),
        budget_plan=target_root / "missing-core-budget-plan.json",
        selection=selection_path,
        output_root=output_root,
    )
    with pytest.raises(cli.CommandError, match="selection bytes differ"):
        cli._cmd_acquisition_purchase_missing_recap_fetch(args)
    assert touched == []
    assert not output_root.exists()
    ledger = verify_case_dev_purchase_policy(artifact).canonical_ledger_path
    for path in (ledger, Path(f"{ledger}.lock"), Path(f"{ledger}-wal")):
        assert not path.exists()


def test_bad_initialization_receipt_fails_before_live_runtime_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_path, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private-authority").resolve()
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_path,
        fee_schedule=fee_schedule,
    )
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_json_bytes(artifact))
    policy = verify_case_dev_purchase_policy(artifact)
    receipt = tmp_path / "purchase-ledger-initialization.json"
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        initialized_at="2026-07-26T16:45:00Z",
        controlled_private_root=private_root,
    )
    bad_receipt = json.loads(receipt.read_text())
    bad_receipt["purchase_policy_sha256"] = "0" * 64
    receipt.write_bytes(_json_bytes(bad_receipt))
    touched: list[str] = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        touched.append("runtime")
        raise AssertionError("bad receipt reached live runtime construction")

    for name in (
        "CourtListenerRecapFetchConfig",
        "UrlLibRecapFetchTransport",
        "RecapFetchBrokerConfig",
        "SignedRecapFetchPurchaseBroker",
        "CourtListenerRequestBudget",
        "CourtListenerRecapFetchClient",
        "CaseDevPurchaseJournal",
    ):
        monkeypatch.setattr(cli, name, forbidden)
    monkeypatch.setattr(cli, "_write_acquisition_failure", lambda *_a, **_k: None)
    args = cli.argparse.Namespace(
        output_root=tmp_path / "runtime-output",
        budget_plan=target_root / "missing-core-budget-plan.json",
        selection=target_root / "target-cohort-selection.jsonl",
        purchase_policy=policy_path,
        cohort_policy=cohort_path,
        purchase_ledger=policy.canonical_ledger_path,
        purchase_output=None,
        execute=True,
        live_purchase=True,
        acknowledge_pacer_fees=True,
        courtlistener_fixture=None,
        purchase_broker_fixture=None,
        attempt_policy=None,
        courtlistener_rate_profile="official",
        request_budget_max_wait_seconds=0.0,
        request_ledger=None,
        controlled_private_root=private_root,
        purchase_ledger_initialization_receipt=receipt,
    )
    with pytest.raises(cli.CommandError, match="not descended from policy"):
        cli._cmd_acquisition_purchase_missing_recap_fetch(args)
    assert touched == []


@pytest.mark.parametrize("receipt_failure", ["absent", "tampered"])
def test_recovery_receipt_failure_precedes_runtime_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, receipt_failure: str
) -> None:
    target_root, cohort_path, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private-authority").resolve()
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_path,
        fee_schedule=fee_schedule,
    )
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_json_bytes(artifact))
    policy = verify_case_dev_purchase_policy(artifact)
    receipt = tmp_path / "recovery-ledger-initialization.json"
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        initialized_at="2026-07-26T16:50:00Z",
        controlled_private_root=private_root,
    )
    if receipt_failure == "absent":
        receipt.unlink()
    else:
        bad_receipt = json.loads(receipt.read_text())
        bad_receipt["purchase_policy_sha256"] = "0" * 64
        receipt.write_bytes(_json_bytes(bad_receipt))
    attempt_path = tmp_path / "attempt-policy.json"
    attempt_path.write_bytes(_json_bytes({"policy_sha256": "a" * 64, "policy": {}}))
    touched: list[str] = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        touched.append("runtime")
        raise AssertionError("bad recovery receipt reached runtime construction")

    for name in (
        "CourtListenerRecapFetchConfig",
        "UrlLibRecapFetchTransport",
        "UrlLibFreeDocumentSource",
        "CourtListenerRequestBudget",
        "CaseDevPurchaseJournal",
    ):
        monkeypatch.setattr(cli, name, forbidden)
    monkeypatch.setattr(
        cli,
        "verify_recap_fetch_attempt_policy",
        lambda *_args, **_kwargs: {"123": {"case_id": "case-a"}},
    )
    monkeypatch.setattr(cli, "_write_acquisition_failure", lambda *_a, **_k: None)
    args = cli.argparse.Namespace(
        output_root=tmp_path / f"recovery-output-{receipt_failure}",
        selection=target_root / "target-cohort-selection.jsonl",
        case_relevance=target_root / "case-relevance.jsonl",
        target_projection_run_card=target_root / "run-cards/project-target-cohort.json",
        purchase_policy=policy_path,
        cohort_policy=cohort_path,
        budget_plan=target_root / "missing-core-budget-plan.json",
        purchase_ledger=policy.canonical_ledger_path,
        attempt_policy=attempt_path,
        manifest_output=None,
        case_relevance_output=None,
        restriction_evidence_output=None,
        review_requests_output=None,
        document_output_root=None,
        courtlistener_fixture=None,
        fixture_documents=None,
        live_courtlistener_recovery=True,
        execute=True,
        request_ledger=None,
        courtlistener_rate_profile="official",
        request_budget_max_wait_seconds=0.0,
        controlled_private_root=private_root,
        purchase_ledger_initialization_receipt=receipt,
    )
    expected = "is missing" if receipt_failure == "absent" else "not descended"
    with pytest.raises(cli.CommandError, match=expected):
        cli._cmd_acquisition_recover_recap_fetch_quarantine(args)
    assert touched == []


def test_v1_policy_rejected_before_journal_namespace_is_created(tmp_path: Path) -> None:
    ledger = (tmp_path / "never-created.sqlite3").resolve()
    artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "3.05",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "3.05",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "https://www.courtlistener.com/help/recap/",
                "verified_at_utc": "2026-07-25T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    policy = verify_case_dev_purchase_policy(artifact)

    with pytest.raises(CaseDevPurchasePolicyError, match="approved v2"):
        CaseDevPurchaseJournal(ledger, policy=policy, allow_create=True)
    assert not ledger.exists()


def test_private_writer_rejects_symlinked_parent_and_concurrent_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=(tmp_path / "ledger.sqlite3").resolve(),
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    private_alias = tmp_path / "private-alias"
    private_alias.symlink_to(outside, target_is_directory=True)
    with pytest.raises(
        PurchaseApprovalError, match=r"safely (?:preflighted|published)"
    ):
        record_purchase_approval(
            request=request,
            controlled_private_root=private_alias.absolute(),
            decision="approve",
            typed_confirmation=request.required_confirmation("approve"),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-26T15:00:00Z",
        )
    assert not list(outside.rglob("*"))

    private_root = (tmp_path / "private-race").resolve()
    original_link = os.link

    def concurrent_link(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise FileExistsError

    monkeypatch.setattr(os, "link", concurrent_link)
    with pytest.raises(PurchaseApprovalError, match="concurrently created"):
        record_purchase_approval(
            request=request,
            controlled_private_root=private_root,
            decision="approve",
            typed_confirmation=request.required_confirmation("approve"),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-26T15:00:00Z",
        )
    monkeypatch.setattr(os, "link", original_link)
    assert not (private_root / "purchase-approval-checkpoint.json").exists()


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "run-cards-parent"])
def test_private_writer_rejects_aliased_final_or_run_card_parent(
    tmp_path: Path, unsafe: str
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=(tmp_path / "ledger.sqlite3").resolve(),
    )
    private_root = (tmp_path / f"private-{unsafe}").resolve()
    private_root.mkdir()
    outside = tmp_path / f"outside-{unsafe}"
    outside.mkdir()
    if unsafe == "run-cards-parent":
        (private_root / "run-cards").symlink_to(outside, target_is_directory=True)
    else:
        seed = outside / "seed.json"
        seed.write_text("{}\n", encoding="utf-8")
        final = private_root / "purchase-approval-checkpoint.json"
        if unsafe == "symlink":
            final.symlink_to(seed)
        else:
            os.link(seed, final)

    with pytest.raises(
        PurchaseApprovalError, match=r"safely preflighted|unique regular"
    ):
        record_purchase_approval(
            request=request,
            controlled_private_root=private_root,
            decision="approve",
            typed_confirmation=request.required_confirmation("approve"),
            reviewer_id="John Hughes",
            recorded_at_utc="2026-07-26T15:00:00Z",
        )
    assert not (outside / "record-purchase-approval.json").exists()
    assert not (private_root / "run-cards/record-purchase-approval.json").exists()


def test_rehashed_checkpoint_companion_tamper_is_rejected(tmp_path: Path) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint, run_card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    artifact = json.loads(checkpoint.read_text())
    artifact["checkpoint"]["target_decision"] = 999
    artifact["checkpoint_sha256"] = _canonical_sha(artifact["checkpoint"])
    checkpoint.write_bytes(_json_bytes(artifact))
    run_artifact = json.loads(run_card.read_text())
    run_artifact["run_card"]["checkpoint_sha256"] = hashlib.sha256(
        checkpoint.read_bytes()
    ).hexdigest()
    run_artifact["run_card_sha256"] = _canonical_sha(run_artifact["run_card"])
    run_card.write_bytes(_json_bytes(run_artifact))

    with pytest.raises(PurchaseApprovalError, match="companion decisions"):
        verify_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=run_card,
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=ledger,
        )


@pytest.mark.parametrize("artifact_kind", ["checkpoint", "run-card"])
def test_rehashed_extraneous_private_evidence_fields_are_rejected(
    tmp_path: Path, artifact_kind: str
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    private_root = (tmp_path / "private-extra").resolve()
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=ledger,
    )
    checkpoint, run_card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    path = checkpoint if artifact_kind == "checkpoint" else run_card
    evidence = json.loads(path.read_text())
    body_name = "checkpoint" if artifact_kind == "checkpoint" else "run_card"
    digest_name = (
        "checkpoint_sha256" if artifact_kind == "checkpoint" else "run_card_sha256"
    )
    evidence[body_name]["unexpected_authority"] = True
    evidence[digest_name] = _canonical_sha(evidence[body_name])
    path.write_bytes(_json_bytes(evidence))

    with pytest.raises(PurchaseApprovalError, match="unexpected_authority"):
        verify_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=run_card,
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=ledger,
        )


def test_v2_publication_is_one_shot_and_initial_scope_rejects_replacements(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    output = tmp_path / "purchase-policy.json"
    write_case_dev_purchase_policy(
        output,
        artifact,
        controlled_private_root=(tmp_path / "private-authority").resolve(),
    )
    with pytest.raises(CaseDevPurchasePolicyError, match="already been published"):
        write_case_dev_purchase_policy(
            output,
            artifact,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
        )
    with pytest.raises(ClearanceReplacementError, match="replacement frontier"):
        build_replacement_frontier(
            cohort_policy_artifact=json.loads(cohort_policy.read_text()),
            purchase_policy_artifact=artifact,
            projection_sha256="sha256:" + "a" * 64,
            initial_selected_candidate_ids=("case-a", "case-b"),
            candidate_rows=(),
            case_mix_max_per_bucket=None,
            source_commitments={"projection": "sha256:" + "b" * 64},
        )


def test_rehashed_forged_v2_cannot_publish_or_reach_paid_authority(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    forged = deepcopy(artifact)
    forged["policy"]["approval"]["private_checkpoint_sha256"] = "b" * 64
    forged["policy_sha256"] = _canonical_sha(forged["policy"])
    structural = verify_case_dev_purchase_policy(forged)
    with pytest.raises(CaseDevPurchasePolicyError, match="private authority replay"):
        require_approved_case_dev_purchase_policy(
            structural,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
        )
    output = tmp_path / "forged-policy.json"
    with pytest.raises(CaseDevPurchasePolicyError, match="private authority replay"):
        write_case_dev_purchase_policy(
            output,
            forged,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
        )
    assert not output.exists()


def test_v2_private_replay_remains_valid_after_ledger_initialization(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    policy = verify_case_dev_purchase_policy(artifact)
    ledger = policy.canonical_ledger_path
    receipt = tmp_path / "purchase-ledger-initialization.json"
    initialize_case_dev_purchase_journal(
        ledger,
        policy=policy,
        receipt_path=receipt,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(_json_bytes(artifact)).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_policy.read_bytes()).hexdigest(),
        initialized_at="2026-07-26T16:00:00Z",
        controlled_private_root=(tmp_path / "private-authority").resolve(),
    )
    with pytest.raises(PurchaseApprovalError, match="absent fresh ledger namespace"):
        verify_purchase_approval(
            controlled_private_root=(tmp_path / "private-authority").resolve(),
            checkpoint_path=(
                tmp_path / "private-authority/purchase-approval-checkpoint.json"
            ).resolve(),
            run_card_path=(
                tmp_path / "private-authority/run-cards/record-purchase-approval.json"
            ).resolve(),
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=ledger,
        )
    replayed = replay_approved_purchase_policy(
        purchase_policy_artifact=artifact,
        controlled_private_root=(tmp_path / "private-authority").resolve(),
    )
    with pytest.raises(PurchaseApprovalError, match="fresh-ledger verification"):
        generate_approved_purchase_policy(replayed)  # type: ignore[arg-type]
    with CaseDevPurchaseJournal(
        ledger,
        policy=policy,
        controlled_private_root=(tmp_path / "private-authority").resolve(),
        initialization_receipt_path=receipt,
    ) as journal:
        assert journal.statuses() == {}
    with CaseDevPurchaseJournal(
        ledger,
        policy=policy,
        controlled_private_root=(tmp_path / "private-authority").resolve(),
        initialization_receipt_path=receipt,
    ) as reopened:
        assert reopened.statuses() == {}
    assert (
        read_case_dev_purchase_snapshot(
            ledger,
            policy=policy,
            controlled_private_root=(tmp_path / "private-authority").resolve(),
            initialization_receipt_path=receipt,
        ).operations
        == ()
    )


def test_v2_runtime_rejects_reinitialized_ledger_with_original_receipt(
    tmp_path: Path,
) -> None:
    policy, ledger, original_receipt, private_root = _initialized_v2_ledger(tmp_path)
    ledger.replace(tmp_path / "original-ledger.sqlite3")
    Path(f"{ledger}.lock").unlink()
    replacement_receipt = tmp_path / "replacement-initialization.json"
    initialize_case_dev_purchase_journal(
        ledger,
        policy=policy,
        receipt_path=replacement_receipt,
        purchase_policy_file_sha256="sha256:" + "a" * 64,
        cohort_policy_file_sha256="sha256:" + "b" * 64,
        initialized_at="2026-07-26T16:01:00Z",
        controlled_private_root=private_root,
    )

    with pytest.raises(CaseDevPurchaseLedgerError, match="identity does not match"):
        CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            controlled_private_root=private_root,
            initialization_receipt_path=original_receipt,
        )


def test_v2_runtime_rejects_receipt_with_different_initialization_identity(
    tmp_path: Path,
) -> None:
    policy, ledger, receipt, private_root = _initialized_v2_ledger(tmp_path)
    record = json.loads(receipt.read_text(encoding="utf-8"))
    record["initialization_id"] = "0" * 32
    receipt.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(CaseDevPurchaseLedgerError, match="identity does not match"):
        CaseDevPurchaseJournal(
            ledger,
            policy=policy,
            controlled_private_root=private_root,
            initialization_receipt_path=receipt,
        )


def test_v2_runtime_accepts_legitimately_mutated_ledger_with_matching_identity(
    tmp_path: Path,
) -> None:
    policy, ledger, receipt, private_root = _initialized_v2_ledger(tmp_path)
    plan = MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="case-a",
                purchase_document_ids=("document-a",),
                missing_core_document_count=1,
                estimated_cost=Decimal("3.05"),
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("3.05"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )
    with CaseDevPurchaseJournal(
        ledger,
        policy=policy,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt,
    ) as journal:
        journal.plan(plan)

    with CaseDevPurchaseJournal(
        ledger,
        policy=policy,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt,
    ) as reopened:
        assert reopened.statuses() == {"document-a": "planned"}


def test_attempt_policy_generation_is_fresh_only_but_replay_survives_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root, cohort_path, fee_schedule = _projection_fixture(
        tmp_path, numeric_purchase_document_ids=True
    )
    private_root = (tmp_path / "private-authority").resolve()
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_path,
        fee_schedule=fee_schedule,
    )
    policy = verify_case_dev_purchase_policy(artifact)
    budget_path = target_root / "missing-core-budget-plan.json"
    selection_path = target_root / "target-cohort-selection.jsonl"
    budget_bytes = budget_path.read_bytes()
    selection_bytes = selection_path.read_bytes()
    budget_artifact = json.loads(budget_bytes)
    budget_plan = cli._missing_core_budget_plan(budget_artifact)
    raw_selection_records = [
        json.loads(line) for line in selection_bytes.splitlines() if line
    ]
    plans_by_candidate = {plan.candidate_id: plan for plan in budget_plan.case_plans}
    for row in raw_selection_records:
        row["exclusion_reasons"] = []
        plan = plans_by_candidate[row["candidate_id"]]
        for document_id in plan.purchase_document_ids:
            row["documents"].append(
                {
                    "candidate_id": row["candidate_id"],
                    "source_document_id": document_id,
                    "redaction_or_seal_status": "unknown",
                    "restriction_evidence": [
                        "courtlistener_rest_docket_exact_match",
                        "courtlistener_rest_docket_entry_exact_match",
                        "courtlistener_rest_recap_document_exact_match",
                        "courtlistener_rest_recap_document_is_available_false",
                        "courtlistener_rest_recap_document_seal_status_unknown",
                        "courtlistener_rest_no_positive_restriction_marker",
                    ],
                    "is_sealed": None,
                    "is_private": None,
                    "is_available": False,
                    "availability_status": "unavailable",
                    "requires_paid_recovery": True,
                }
            )
    selection_records = tuple(raw_selection_records)
    # This test isolates freshness versus replay. Separate regressions below
    # exercise the raw-bytes-to-structured-arguments binding itself.
    monkeypatch.setattr(
        attempt_module,
        "_require_structured_inputs_match_authenticated_bytes",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        broker_module,
        "_require_structured_inputs_match_authenticated_bytes",
        lambda **_kwargs: None,
    )
    cohort_artifact = json.loads(cohort_path.read_text())
    attempt = generate_recap_fetch_attempt_policy(
        purchase_policy_artifact=artifact,
        cohort_policy_artifact=cohort_artifact,
        budget_plan=budget_plan,
        budget_plan_artifact=budget_artifact,
        selection_records=selection_records,
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
        controlled_private_root=private_root,
    )
    replay_kwargs = {
        "purchase_policy_artifact": artifact,
        "cohort_policy_artifact": cohort_artifact,
        "budget_plan": budget_plan,
        "budget_plan_artifact": budget_artifact,
        "selection_records": selection_records,
        "budget_plan_bytes": budget_bytes,
        "selection_bytes": selection_bytes,
        "controlled_private_root": private_root,
    }
    before = verify_recap_fetch_attempt_policy(attempt, **replay_kwargs)
    assert before
    broker = generate_recap_fetch_broker_policy(
        **replay_kwargs, attempt_policy_artifact=attempt
    )

    receipt = tmp_path / "attempt-ledger-initialization.json"
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(_json_bytes(artifact)).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        initialized_at="2026-07-26T16:30:00Z",
        controlled_private_root=private_root,
    )
    assert verify_recap_fetch_attempt_policy(attempt, **replay_kwargs) == before
    with pytest.raises(RecapFetchAttemptPolicyError, match="absent fresh ledger"):
        generate_recap_fetch_attempt_policy(**replay_kwargs)
    with pytest.raises(RecapFetchBrokerPolicyError, match="absent fresh ledger"):
        generate_recap_fetch_broker_policy(
            **replay_kwargs, attempt_policy_artifact=attempt
        )
    replayed_broker = verify_recap_fetch_broker_policy(
        broker, **replay_kwargs, attempt_policy_artifact=attempt
    )
    assert replayed_broker.allowed_documents

    forged = deepcopy(attempt)
    forged["policy"]["planned_reserved_usd"] = "0.00"
    forged["policy_sha256"] = _canonical_sha(forged["policy"])
    with pytest.raises(RecapFetchAttemptPolicyError, match="immutable source inputs"):
        verify_recap_fetch_attempt_policy(forged, **replay_kwargs)
    with pytest.raises(RecapFetchAttemptPolicyError, match="private authority replay"):
        verify_recap_fetch_attempt_policy(
            attempt,
            **{**replay_kwargs, "controlled_private_root": tmp_path / "wrong-private"},
        )
    forged_broker = deepcopy(broker)
    forged_broker["allowed_documents"][0]["recap_document"] = "999"
    with pytest.raises(RecapFetchBrokerPolicyError, match="immutable source inputs"):
        verify_recap_fetch_broker_policy(
            forged_broker, **replay_kwargs, attempt_policy_artifact=attempt
        )
    with pytest.raises(RecapFetchBrokerPolicyError, match="private authority replay"):
        verify_recap_fetch_broker_policy(
            broker,
            **{**replay_kwargs, "controlled_private_root": tmp_path / "wrong-private"},
            attempt_policy_artifact=attempt,
        )
    with pytest.raises(RecapFetchBrokerPolicyError, match="selection bytes differ"):
        verify_recap_fetch_broker_policy(
            broker,
            **{**replay_kwargs, "selection_bytes": selection_bytes + b"\n"},
            attempt_policy_artifact=attempt,
        )


def test_replacement_cli_rejects_v2_before_touching_purchase_journal(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_json_bytes(artifact))
    ledger = verify_case_dev_purchase_policy(artifact).canonical_ledger_path
    missing = tmp_path / "unused"
    assert (
        main(
            [
                "acquisition",
                "plan-clearance-replacements",
                "--purchase-policy",
                str(policy_path),
                "--purchase-ledger",
                str(ledger),
                "--cohort-policy",
                str(missing),
                "--frontier",
                str(missing),
                "--purchased-clearance",
                str(missing),
                "--clearance-run-card",
                str(missing),
                "--output",
                str(tmp_path / "result.json"),
                "--replacement-budget-plan-output",
                str(tmp_path / "plan.json"),
                "--broker-allowlist-plan-output",
                str(tmp_path / "allowlist.json"),
                "--exclusions-output",
                str(tmp_path / "exclusions.jsonl"),
            ]
        )
        == 2
    )
    assert not ledger.exists()
    assert not Path(f"{ledger}.lock").exists()
    assert not Path(f"{ledger}-wal").exists()
    assert not Path(f"{ledger}-shm").exists()


def test_v1_rejected_before_init_verify_snapshot_and_policy_generation_touch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = (tmp_path / "never-touched.sqlite3").resolve()
    artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "3.05",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "3.05",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-07-25T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    policy = verify_case_dev_purchase_policy(artifact)
    policy_path = tmp_path / "valid-v1-purchase-policy.json"
    policy_path.write_bytes(_json_bytes(artifact))
    receipt = tmp_path / "never-touched-receipt.json"
    private_root = (tmp_path / "private-does-not-exist").resolve()

    # Mirror the complete production alias inventory. The historical Case.dev
    # helper patches only its journal/CLI require gates; every alias here must
    # retain direct v1 rejection before it can inspect approved inputs.
    assert tuple(module.__name__ for module in LEGACY_V1_BYPASS_MODULES) == (
        "legalforecast.ingestion.case_dev_purchase",
        "legalforecast.ingestion.clearance_replacement",
        "legalforecast.ingestion.recap_fetch_attempt_policy",
        "legalforecast.ingestion.recap_fetch_broker_policy",
        "legalforecast.ingestion.retained_cohort_extension",
        "legalforecast.cli",
    )
    for module in LEGACY_V1_BYPASS_MODULES:
        require_policy = getattr(
            module, "require_approved_case_dev_purchase_policy", None
        )
        if require_policy is not None:
            with pytest.raises(CaseDevPurchasePolicyError, match="approved v2"):
                require_policy(policy, controlled_private_root=private_root)
        verify_inputs = getattr(module, "verify_approved_purchase_input_bytes", None)
        if verify_inputs is not None:
            with pytest.raises(CaseDevPurchasePolicyError, match="approved v2"):
                verify_inputs(
                    policy,
                    controlled_private_root=private_root,
                    budget_plan_bytes=b"must-not-be-read",
                    selection_bytes=b"must-not-be-read",
                )

    with pytest.raises(CaseDevPurchasePolicyError, match="approved v2"):
        initialize_case_dev_purchase_journal(
            ledger,
            policy=policy,
            receipt_path=receipt,
            purchase_policy_file_sha256="sha256:" + "b" * 64,
            cohort_policy_file_sha256="sha256:" + "c" * 64,
            initialized_at="2026-07-26T16:00:00Z",
            controlled_private_root=private_root,
        )
    with pytest.raises(CaseDevPurchasePolicyError, match="approved v2"):
        verify_case_dev_purchase_journal_initialization(
            ledger,
            policy=policy,
            receipt_path=receipt,
            purchase_policy_file_sha256="sha256:" + "b" * 64,
            cohort_policy_file_sha256="sha256:" + "c" * 64,
            controlled_private_root=private_root,
        )
    with pytest.raises(CaseDevPurchasePolicyError, match="approved v2"):
        read_case_dev_purchase_snapshot(
            ledger,
            policy=policy,
            controlled_private_root=private_root,
            initialization_receipt_path=receipt,
        )
    with pytest.raises(RecapFetchAttemptPolicyError, match="approved v2"):
        generate_recap_fetch_attempt_policy(
            purchase_policy_artifact=artifact,
            cohort_policy_artifact={},
            budget_plan=None,  # type: ignore[arg-type]
            budget_plan_artifact={},
            selection_records=(),
            controlled_private_root=private_root,
        )
    with pytest.raises(RecapFetchBrokerPolicyError, match="approved v2"):
        generate_recap_fetch_broker_policy(
            purchase_policy_artifact=artifact,
            cohort_policy_artifact={},
            budget_plan=None,  # type: ignore[arg-type]
            budget_plan_artifact={},
            selection_records=(),
            controlled_private_root=private_root,
        )

    sentinel_calls: list[str] = []

    def forbidden_runtime_touch(*_args: object, **_kwargs: object) -> None:
        sentinel_calls.append("runtime")
        raise AssertionError("v1 reached an output, journal, environment, or provider")

    for name in (
        "_acquisition_output_root",
        "_acquisition_path",
        "_atomic_write_json",
        "_write_jsonl",
        "_write_acquisition_failure",
        "read_unique_regular_file",
        "CaseDevPurchaseJournal",
        "CourtListenerRecapFetchConfig",
        "RecapFetchBrokerConfig",
        "MistralParserConfig",
    ):
        monkeypatch.setattr(cli, name, forbidden_runtime_touch)

    command_boundaries = (
        ("init-fresh", cli._cmd_init_purchase_ledger, {"resume": False}),
        ("init-resume", cli._cmd_init_purchase_ledger, {"resume": True}),
        ("reconcile", cli._cmd_reconcile_purchase, {}),
        ("extend-target", cli._cmd_acquisition_extend_target_cohort, {}),
        ("attempt-policy", cli._cmd_generate_recap_fetch_attempt_policy, {}),
        ("broker-policy", cli._cmd_generate_recap_fetch_broker_policy, {}),
        (
            "packet-plan-current-purchase",
            cli._cmd_acquisition_plan_packet_inputs,
            {"materialization_run_card": None},
        ),
        (
            "packet-plan-materialization",
            cli._cmd_acquisition_plan_packet_inputs,
            {"materialization_run_card": tmp_path / "must-not-be-read.json"},
        ),
        (
            "purchase-recap-fetch",
            cli._cmd_acquisition_purchase_missing_recap_fetch,
            {},
        ),
        ("legacy-purchase-missing", cli._cmd_acquisition_purchase_missing, {}),
        (
            "recover-recap-quarantine",
            cli._cmd_acquisition_recover_recap_fetch_quarantine,
            {},
        ),
        (
            "resolve-post-recovery",
            cli._cmd_acquisition_resolve_post_recovery,
            {},
        ),
        (
            "materialize-documents",
            cli._cmd_acquisition_materialize_cohort_documents,
            {},
        ),
        ("plan-parse", cli._cmd_acquisition_plan_parse_documents, {}),
        ("parse", cli._cmd_acquisition_parse_documents, {}),
    )
    for name, command, extra_args in command_boundaries:
        command_args = cli.argparse.Namespace(
            purchase_policy=policy_path,
            controlled_private_root=private_root,
            **extra_args,
        )
        with pytest.raises(cli.CommandError, match="approved v2"):
            command(command_args)
        assert sentinel_calls == [], name
    assert sentinel_calls == []

    for path in (
        ledger,
        Path(f"{ledger}.lock"),
        Path(f"{ledger}-wal"),
        Path(f"{ledger}-shm"),
        receipt,
    ):
        assert not path.exists() and not path.is_symlink()


@pytest.mark.parametrize(
    "command",
    [
        "plan-parse-documents",
        "parse-documents",
        "build-decision-texts",
        "rehearse-downstream",
        "build-packets",
        "finalize-corpus",
    ],
)
def test_materialized_packet_commands_reject_v1_from_parser_namespace_before_touch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authenticated_downstream_fixture: object,
    command: str,
) -> None:
    assert authenticated_downstream_fixture is not None
    ledger = (tmp_path / "never-touched.sqlite3").resolve()
    policy_path = tmp_path / "purchase-policy-v1.json"
    policy_path.write_bytes(
        _json_bytes(
            generate_case_dev_purchase_policy(
                {
                    "cycle_id": "cycle-1",
                    "cohort_policy_sha256": "a" * 64,
                    "canonical_ledger_path": str(ledger),
                    "hard_cap_usd": "3.05",
                    "opening_committed_spend_usd": "0.00",
                    "opening_case_committed_spend_usd": {},
                    "max_per_case_usd": "3.05",
                    "per_document_reservation_usd": "3.05",
                    "fee_schedule": {
                        "source_citation": "fixture",
                        "verified_at_utc": "2026-07-25T00:00:00Z",
                        "includes_pacer_fees": True,
                        "includes_service_fees": True,
                        "includes_rounding": True,
                    },
                }
            )
        )
    )
    inputs = [
        (tmp_path / f"materialization-input-{index}").resolve() for index in range(12)
    ]
    inputs[9] = policy_path.resolve()
    materialization_card = tmp_path / "materialization-run-card.json"
    materialization_card.write_bytes(
        _json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "input_paths": [str(path) for path in inputs],
                "output_paths": [
                    str((tmp_path / f"materialization-output-{index}").resolve())
                    for index in range(6)
                ],
            }
        )
    )
    private_root = (tmp_path / "private-must-not-be-read").resolve()
    receipt = (tmp_path / "receipt-must-not-be-read.json").resolve()

    parser = cli.build_parser()
    acquisition_action = next(
        action
        for action in parser._actions
        if isinstance(action, cli.argparse._SubParsersAction)
    )
    acquisition_parser = acquisition_action.choices["acquisition"]
    command_action = next(
        action
        for action in acquisition_parser._actions
        if isinstance(action, cli.argparse._SubParsersAction)
    )
    command_parser = command_action.choices[command]
    argv = ["acquisition", command]
    overrides = {
        "--materialization-run-card": str(materialization_card),
        "--controlled-private-root": str(private_root),
        "--purchase-ledger-initialization-receipt": str(receipt),
    }
    for action in command_parser._actions:
        if not action.required or not action.option_strings:
            continue
        option = action.option_strings[0]
        if option in overrides:
            value = overrides.pop(option)
        elif action.choices:
            value = str(next(iter(action.choices)))
        elif action.type is int:
            value = "1"
        else:
            value = str((tmp_path / option.removeprefix("--")).resolve())
        argv.extend((option, value))
    supported_options = {
        option for action in command_parser._actions for option in action.option_strings
    }
    for option, value in overrides.items():
        if option in supported_options:
            argv.extend((option, value))
    if command == "rehearse-downstream":
        argv.append("--execute")
    args = parser.parse_args(argv)
    assert getattr(args, "purchase_policy", None) is None

    touched: list[str] = []

    def forbidden_touch(*_args: object, **_kwargs: object) -> None:
        touched.append("runtime")
        raise AssertionError("v1 reached command output or runtime inputs")

    monkeypatch.setattr(cli, "_acquisition_output_root", forbidden_touch)
    with pytest.raises(cli.CommandError, match="approved v2"):
        args.handler(args)
    assert touched == []
    assert not ledger.exists()


@pytest.mark.parametrize(
    "command",
    [
        "plan-parse-documents",
        "parse-documents",
        "build-decision-texts",
        "rehearse-downstream",
        "plan-packet-inputs",
        "build-packets",
        "finalize-corpus",
    ],
)
def test_materialized_commands_authenticate_full_lineage_before_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    materialization_card = tmp_path / "tampered-materialization-run-card.json"
    materialization_card.write_bytes(
        _json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "input_paths": [
                    str((tmp_path / f"input-{index}").resolve()) for index in range(12)
                ],
                "output_paths": [
                    str((tmp_path / f"output-{index}").resolve()) for index in range(6)
                ],
            }
        )
    )
    parser = cli.build_parser()
    acquisition_action = next(
        action
        for action in parser._actions
        if isinstance(action, cli.argparse._SubParsersAction)
    )
    acquisition_parser = acquisition_action.choices["acquisition"]
    command_action = next(
        action
        for action in acquisition_parser._actions
        if isinstance(action, cli.argparse._SubParsersAction)
    )
    command_parser = command_action.choices[command]
    argv = ["acquisition", command]
    overrides = {
        "--materialization-run-card": str(materialization_card),
        "--controlled-private-root": str((tmp_path / "private").resolve()),
        "--purchase-ledger-initialization-receipt": str(
            (tmp_path / "receipt.json").resolve()
        ),
        "--selection": str((tmp_path / "selection.jsonl").resolve()),
        "--download-manifest": str((tmp_path / "manifest.jsonl").resolve()),
        "--disclosure-clearance": str((tmp_path / "clearance.jsonl").resolve()),
        "--document-root": str((tmp_path / "documents").resolve()),
    }
    for action in command_parser._actions:
        if not action.required or not action.option_strings:
            continue
        option = action.option_strings[0]
        if option in overrides:
            value = overrides.pop(option)
        elif action.choices:
            value = str(next(iter(action.choices)))
        elif action.type is int:
            value = "1"
        else:
            value = str((tmp_path / option.removeprefix("--")).resolve())
        argv.extend((option, value))
    supported_options = {
        option for action in command_parser._actions for option in action.option_strings
    }
    for option, value in overrides.items():
        if option in supported_options:
            argv.extend((option, value))
    if command == "rehearse-downstream":
        argv.append("--execute")
    args = parser.parse_args(argv)

    monkeypatch.setattr(
        cli, "_preflight_materialization_purchase_runtime", lambda _args: None
    )

    def reject_tampered_lineage(**_kwargs: object) -> None:
        raise cli.CommandError("tampered materialization lineage")

    monkeypatch.setattr(
        cli, "_verify_materialized_downstream_lineage", reject_tampered_lineage
    )

    def forbidden_output_root(_args: object) -> None:
        raise AssertionError("tampered lineage reached output root")

    monkeypatch.setattr(cli, "_acquisition_output_root", forbidden_output_root)
    with pytest.raises(cli.CommandError, match="tampered materialization lineage"):
        args.handler(args)


@pytest.mark.parametrize(
    "handler",
    [
        cli._cmd_acquisition_plan_parse_documents,
        cli._cmd_acquisition_parse_documents,
        cli._cmd_acquisition_build_decision_texts,
        cli._cmd_acquisition_plan_packet_inputs,
        cli._cmd_acquisition_build_packets,
        cli._cmd_acquisition_finalize_corpus,
    ],
)
def test_executed_materialization_consumers_require_card_before_output_root(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[cli.argparse.Namespace], int],
) -> None:
    args = cli.argparse.Namespace(
        execute=True,
        materialization_run_card=None,
        purchase_policy=None,
    )

    def forbidden_output_root(_args: object) -> None:
        raise AssertionError("missing materialization authority reached output root")

    monkeypatch.setattr(cli, "_acquisition_output_root", forbidden_output_root)
    with pytest.raises(cli.CommandError, match=r"materialization|materialized"):
        handler(args)


def test_v2_cohort_binding_rejects_target_drift(tmp_path: Path) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    cohort = json.loads(cohort_policy.read_text())
    decisions = deepcopy(cohort["policy"])
    decisions.pop("policy_sha256", None)
    decisions["reduced_n"]["target_clean_cases"] = 3
    decisions["stop_rule"]["target_clean_cases"] = 3
    decisions["reduced_n"]["claim_tiers"][-1]["maximum_clean_cases"] = 3
    drifted_cohort = generate_cohort_policy(decisions)
    drifted = deepcopy(artifact)
    drifted["policy"]["cohort_policy_sha256"] = drifted_cohort["policy_sha256"]
    drifted["policy"]["approval"]["cohort_policy_sha256"] = drifted_cohort[
        "policy_sha256"
    ]
    drifted["policy_sha256"] = _canonical_sha(drifted["policy"])
    policy = verify_case_dev_purchase_policy(drifted)
    with pytest.raises(CaseDevPurchasePolicyError, match="target"):
        verify_case_dev_purchase_policy_cohort_binding(policy, drifted_cohort)


def test_v2_cohort_binding_rejects_rehashed_frozen_purchase_rule_drift(
    tmp_path: Path,
) -> None:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    drifted_cohort = json.loads(cohort_policy.read_text())
    drifted_cohort["policy"]["purchase_policy"]["rule"] = "buy_any_under_cap"
    drifted_cohort["policy_sha256"] = _canonical_sha(drifted_cohort["policy"])
    drifted_artifact = deepcopy(artifact)
    drifted_artifact["policy"]["cohort_policy_sha256"] = drifted_cohort["policy_sha256"]
    drifted_artifact["policy"]["approval"]["cohort_policy_sha256"] = drifted_cohort[
        "policy_sha256"
    ]
    drifted_artifact["policy_sha256"] = _canonical_sha(drifted_artifact["policy"])
    policy = verify_case_dev_purchase_policy(drifted_artifact)

    with pytest.raises(ValueError, match=r"purchase_policy\.rule is unsupported"):
        verify_case_dev_purchase_policy_cohort_binding(policy, drifted_cohort)


def test_real_authenticated_exact_100_with_15_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_validate = cli.validate_review_receipt
    resolved_validate = resolved_module.validate_review_receipt
    monkeypatch.setattr(
        cli,
        "validate_review_receipt",
        lambda *args, **kwargs: cli_validate(
            *args, **{**kwargs, "allow_test_service_identity": True}
        ),
    )
    monkeypatch.setattr(
        resolved_module,
        "validate_review_receipt",
        lambda *args, **kwargs: resolved_validate(
            *args, **{**kwargs, "allow_test_service_identity": True}
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_main_disclosure_review_authority",
        lambda cohort, *, reviewer_policy_bytes: (
            service_disclosure_authority_from_policy_bytes(
                reviewer_policy_bytes,
                identity=disclosure_authority_identity_from_cohort_policy(cohort),
            )
        ),
    )
    prepared = tmp_path / "prepared"
    snapshot, cycle_hash, documents, courtlistener = _target_100_fixture(
        tmp_path / "source", case_count=115
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(prepared),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--fixture-documents",
                str(documents),
                "--courtlistener-fixture",
                str(courtlistener),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    manifest = prepared / "03c-merged-downloads/document-downloads-merged.jsonl"
    restrictions = prepared / "06-clearance-inputs/restriction-evidence.jsonl"
    review = _write_authenticated_reviews(
        tmp_path / "review",
        manifest_path=manifest,
        document_root=prepared / "documents/free",
        review_requests_path=prepared
        / "06-clearance-inputs/disclosure-review-requests.jsonl",
        restriction_evidence_path=restrictions,
        store_uri="private-store://fixture/purchase-approval",
    )
    clearance_root = tmp_path / "clearance"
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(manifest),
                "--review-requests",
                str(review.requests),
                "--document-root",
                str(prepared / "documents/free"),
                "--review-worksheet",
                str(review.worksheet),
                "--reviews",
                str(review.reviews),
                "--review-receipt",
                str(review.receipt),
                "--reviewer-policy",
                str(review.policy),
                "--cohort-policy",
                str(review.cohort_policy),
                "--restriction-evidence",
                str(restrictions),
                "--output-root",
                str(clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    projected = tmp_path / "projected"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projected),
                "--selection",
                str(
                    prepared / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(prepared / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(manifest),
                "--disclosure-clearance",
                str(clearance_root / "disclosure-clearance.jsonl"),
                "--clearance-run-card",
                str(clearance_root / "run-cards/clear-disclosures.json"),
                "--restriction-evidence",
                str(restrictions),
                "--preparation-summary",
                str(prepared / "target-100-preparation-summary.json"),
                "--preparation-config",
                str(prepared / "target-100-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--execute",
            ]
        )
        == 0
    )
    cohort = _exact_100_cohort_policy()
    cohort_path = tmp_path / "purchase-cohort-policy.json"
    cohort_path.write_bytes(_json_bytes(cohort))
    fee_schedule = tmp_path / "fee-schedule.json"
    fee_schedule.write_bytes(
        _json_bytes(
            {
                "source_citation": "https://www.courtlistener.com/help/recap/",
                "verified_at_utc": "2026-07-25T12:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            }
        )
    )
    request = build_purchase_approval_request(
        target_cohort_root=projected,
        cohort_policy_path=cohort_path,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=(tmp_path / "cycle.sqlite3").resolve(),
    )
    budget = json.loads((projected / "missing-core-budget-plan.json").read_text())
    assert request.selected_case_count == 100
    assert len(budget["omitted_candidate_ids"]) == 15
    assert request.purchase_document_count == 100

    private_root = (tmp_path / "private-exact-100").resolve()
    checkpoint, run_card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T17:00:00Z",
    )
    verified = verify_purchase_approval(
        controlled_private_root=private_root,
        checkpoint_path=checkpoint,
        run_card_path=run_card,
        target_cohort_root=projected,
        cohort_policy_path=cohort_path,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=Path(request.canonical_ledger_path),
    )
    artifact = generate_approved_purchase_policy(verified)
    policy = verify_case_dev_purchase_policy(artifact)
    budget_bytes = (projected / "missing-core-budget-plan.json").read_bytes()
    selection_bytes = (projected / "target-cohort-selection.jsonl").read_bytes()
    selected_ids, document_ids = verify_approved_purchase_input_bytes(
        policy,
        controlled_private_root=private_root,
        budget_plan_bytes=budget_bytes,
        selection_bytes=selection_bytes,
    )
    assert len(selected_ids) == 100
    assert len(document_ids) == 100

    receipt = tmp_path / "exact-100-ledger-initialization.json"
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt,
        purchase_policy_file_sha256="sha256:"
        + hashlib.sha256(_json_bytes(artifact)).hexdigest(),
        cohort_policy_file_sha256="sha256:"
        + hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        initialized_at="2026-07-26T17:01:00Z",
        controlled_private_root=private_root,
    )
    replay_approved_purchase_policy(
        purchase_policy_artifact=artifact,
        controlled_private_root=private_root,
    )
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt,
    ) as journal:
        assert journal.statuses() == {}
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt,
    ) as reopened:
        assert reopened.statuses() == {}
    snapshot = read_case_dev_purchase_snapshot(
        policy.canonical_ledger_path,
        policy=policy,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt,
    )
    assert snapshot.operations == ()


def _record_approved_policy(
    tmp_path: Path,
    *,
    target_root: Path,
    cohort_policy: Path,
    fee_schedule: Path,
) -> dict[str, object]:
    private_root = (tmp_path / "private-authority").resolve()
    request = build_purchase_approval_request(
        target_cohort_root=target_root,
        cohort_policy_path=cohort_policy,
        fee_schedule_path=fee_schedule,
        canonical_ledger_path=(tmp_path / "approved-ledger.sqlite3").resolve(),
    )
    checkpoint, card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision="approve",
        typed_confirmation=request.required_confirmation("approve"),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-07-26T15:00:00Z",
    )
    return generate_approved_purchase_policy(
        verify_purchase_approval(
            controlled_private_root=private_root,
            checkpoint_path=checkpoint,
            run_card_path=card,
            target_cohort_root=target_root,
            cohort_policy_path=cohort_policy,
            fee_schedule_path=fee_schedule,
            canonical_ledger_path=(tmp_path / "approved-ledger.sqlite3").resolve(),
        )
    )


def _initialized_v2_ledger(
    tmp_path: Path,
) -> tuple[CaseDevPurchasePolicy, Path, Path, Path]:
    target_root, cohort_policy, fee_schedule = _projection_fixture(tmp_path)
    artifact = _record_approved_policy(
        tmp_path,
        target_root=target_root,
        cohort_policy=cohort_policy,
        fee_schedule=fee_schedule,
    )
    policy = verify_case_dev_purchase_policy(artifact)
    private_root = (tmp_path / "private-authority").resolve()
    receipt = tmp_path / "purchase-ledger-initialization.json"
    initialize_case_dev_purchase_journal(
        policy.canonical_ledger_path,
        policy=policy,
        receipt_path=receipt,
        purchase_policy_file_sha256="sha256:" + "a" * 64,
        cohort_policy_file_sha256="sha256:" + "b" * 64,
        initialized_at="2026-07-26T16:00:00Z",
        controlled_private_root=private_root,
    )
    return policy, policy.canonical_ledger_path, receipt, private_root


def _exact_100_cohort_policy() -> dict[str, object]:
    decisions = cli._fixture_cohort_policy_decisions()
    decisions["eligibility_anchor"] = "2026-06-30"
    decisions["stop_rule"] = {
        **decisions["stop_rule"],
        "target_clean_cases": 100,
        "search_window_end": "2026-07-26",
    }
    decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "2250.00",
        "max_per_case_usd": "73.20",
        "reservation_headroom_required": True,
    }
    decisions["reduced_n"] = {
        "target_clean_cases": 100,
        "claim_tiers": [
            {
                "minimum_clean_cases": 1,
                "maximum_clean_cases": 99,
                "claim_class": "provisional_feasibility",
                "minimum_prediction_units": None,
                "insufficient_units_action": None,
            },
            {
                "minimum_clean_cases": 100,
                "maximum_clean_cases": 100,
                "claim_class": "target",
                "minimum_prediction_units": 1,
                "insufficient_units_action": "provisional_feasibility",
            },
        ],
        "below_minimum_action": "pilot_only_no_official_cycle",
    }
    return generate_cohort_policy(decisions)


def _projection_fixture(
    tmp_path: Path, *, numeric_purchase_document_ids: bool = False
) -> tuple[Path, Path, Path]:
    root = (tmp_path / "projection").resolve()
    (root / "run-cards").mkdir(parents=True)
    source_root = (tmp_path / "projection-sources").resolve()
    source_root.mkdir()
    candidate_ids = ("case-a", "case-b")
    source_selection = [_selection(candidate_id) for candidate_id in candidate_ids]
    source_relevance = [
        _relevance(candidate_id, missing_count=1) for candidate_id in candidate_ids
    ]
    if numeric_purchase_document_ids:
        for index, relevance in enumerate(source_relevance, start=123):
            relevance["documents"][-1]["source_document_id"] = str(index)
    source_manifest = [
        _download(candidate_id, f"{candidate_id}-complaint")
        for candidate_id in candidate_ids
    ]
    source_clearance = [
        _clearance(candidate_id, f"{candidate_id}-complaint")
        for candidate_id in candidate_ids
    ]
    source_records: dict[str, object] = {
        "selection.jsonl": source_selection,
        "case-relevance.jsonl": source_relevance,
        "download-manifest.jsonl": source_manifest,
        "disclosure-clearance.jsonl": source_clearance,
        "clearance-run-card.json": {"status": "completed"},
        "restriction-evidence.jsonl": [],
        "preparation-summary.json": {"status": "completed"},
        "preparation-config.json": {
            "target_case_count": 2,
            "cost_per_document_usd": "3.05",
            "max_projected_budget_usd": "100.00",
            "max_missing_core_documents_per_case": 24,
        },
        "snapshot-manifest.json": {"cycle_hash": "cycle", "batch_digest": "batch"},
    }
    source_paths: list[Path] = []
    for name, value in source_records.items():
        path = source_root / name
        if name.endswith(".jsonl"):
            assert isinstance(value, list)
            path.write_bytes(_jsonl_bytes(value))
        else:
            path.write_bytes(_json_bytes(value))
        source_paths.append(path)

    projection = project_target_cohort(
        selections=source_selection,
        case_relevance=source_relevance,
        download_manifest=source_manifest,
        clearance_records=source_clearance,
        target_case_count=2,
        cost_per_document_usd="3.05",
        max_projected_budget_usd="100.00",
        max_missing_core_documents_per_case=24,
    )
    manifest = tuple(projection.download_manifest)
    output_payloads: dict[str, bytes] = {
        "target-cohort-selection.jsonl": _jsonl_bytes(projection.selections),
        "case-relevance.jsonl": _jsonl_bytes(projection.case_relevance),
        "free-document-downloads.jsonl": _jsonl_bytes(
            [row for row in manifest if row.get("free_or_purchased") == "free"]
        ),
        "purchased-document-downloads.jsonl": _jsonl_bytes(
            [row for row in manifest if row.get("free_or_purchased") == "purchased"]
        ),
        "document-downloads-merged.jsonl": _jsonl_bytes(manifest),
        "disclosure-clearance.jsonl": _jsonl_bytes(projection.clearance_records),
        "restriction-evidence.jsonl": _jsonl_bytes(projection.restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(
            [row.to_record() for row in projection.core_filter_results]
        ),
        "target-cohort-exclusions.jsonl": _jsonl_bytes(projection.exclusions),
        "missing-core-budget-plan.json": _json_bytes(
            projection.budget_plan.to_record()
        ),
    }
    summary = dict(projection.summary)
    summary["output_commitments"] = {
        name: "sha256:" + hashlib.sha256(payload).hexdigest()
        for name, payload in output_payloads.items()
    }
    output_payloads["target-cohort-projection.json"] = _json_bytes(summary)
    output_paths: list[Path] = []
    for name, payload in output_payloads.items():
        path = root / name
        path.write_bytes(payload)
        output_paths.append(path)
    run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "project-target-cohort",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 2,
        "input_paths": [str(path) for path in source_paths],
        "output_paths": [str(path) for path in output_paths],
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "output_commitments": {
            str(path): "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            for path in output_paths
        },
    }
    (root / "run-cards/project-target-cohort.json").write_text(
        json.dumps(run_card, sort_keys=True) + "\n"
    )
    taxonomy = cohort_reason_policy_taxonomy()
    cohort_decisions: dict[str, Any] = {
        "cycle_id": "cycle-1",
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
            "cycle_budget_usd": "100.00",
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
    policy = generate_cohort_policy(cohort_decisions)
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.write_text(json.dumps(policy, sort_keys=True) + "\n")
    fee_schedule = tmp_path / "fee-schedule.json"
    fee_schedule.write_text(
        json.dumps(
            {
                "source_citation": "https://www.courtlistener.com/help/recap/",
                "verified_at_utc": "2026-07-25T12:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return root, cohort_path, fee_schedule


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _jsonl_bytes(rows: object) -> bytes:
    assert isinstance(rows, (list, tuple))
    return "".join(
        json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n" for row in rows
    ).encode()


def _json_bytes(value: object) -> bytes:
    assert isinstance(value, dict)
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
