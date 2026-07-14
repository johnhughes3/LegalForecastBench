from __future__ import annotations

import hashlib
import inspect
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.cohort_policy import generate_cohort_policy
from legalforecast.ingestion.cycle_acquisition_store import (
    cohort_reason_policy_taxonomy,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.retained_cohort_extension import (
    AuthenticatedPoolLineage,
    PurchaseObligationSnapshot,
    RetainedCohortExtensionError,
    extend_target_cohort,
    purchase_obligation_snapshot,
)
from legalforecast.ingestion.target_cohort_projection import project_target_cohort


def test_extension_preserves_base_prefix_and_selects_only_omitted_frontier() -> None:
    inputs = _inputs()

    extension = extend_target_cohort(**inputs)

    assert extension.base_candidate_ids == tuple(_candidate_id(i) for i in range(100))
    assert extension.incremental_candidate_ids == tuple(
        _candidate_id(i) for i in range(100, 150)
    )
    assert extension.combined_candidate_ids == tuple(
        _candidate_id(i) for i in range(150)
    )
    assert set(extension.base_candidate_ids).isdisjoint(
        extension.incremental_candidate_ids
    )
    for name, base_payload in inputs["base_projection_artifacts"].items():
        if name in {
            "target-cohort-selection.jsonl",
            "case-relevance.jsonl",
            "document-downloads-merged.jsonl",
            "disclosure-clearance.jsonl",
            "restriction-evidence.jsonl",
            "core-filter-results.jsonl",
            "free-document-downloads.jsonl",
            "purchased-document-downloads.jsonl",
        }:
            assert extension.combined_artifacts[name].startswith(base_payload)
    exclusions = {
        json.loads(line)["candidate_id"]
        for line in extension.combined_artifacts[
            "target-cohort-exclusions.jsonl"
        ].splitlines()
    }
    assert exclusions == {_candidate_id(150)}
    assert extension.extension_record["combined_case_count"] == 150
    assert extension.extension_record["full_pool_case_count"] == 151
    assert extension.extension_record["paid_activity_requested"] is False
    assert extension.extension_record["paid_activity_executed"] is False
    combined_plan = json.loads(
        extension.combined_artifacts["missing-core-budget-plan.json"]
    )
    assert combined_plan["frontier_rows"] == [
        {
            "complete_case_count": 150,
            "estimated_spend_usd": "0.00",
            "incremental_case_count": 150,
            "max_missing_core_documents_per_case": 0,
            "purchase_document_count": 0,
        }
    ]
    assert combined_plan["omitted_candidate_ids"] == []
    assert combined_plan["excluded_case_plans"] == []


def test_extension_is_byte_identical_on_resume() -> None:
    inputs = _inputs()

    first = extend_target_cohort(**inputs)
    second = extend_target_cohort(**inputs)

    assert first.combined_artifacts == second.combined_artifacts
    assert first.incremental_artifacts == second.incremental_artifacts
    assert first.extension_record == second.extension_record


def test_extension_rejects_new_frontier_rank_that_interleaves_retained_cohort() -> None:
    inputs = _inputs(paid_after=99)
    full = dict(inputs["full_pool_artifacts"])
    relevance = _jsonl(full["case-relevance.jsonl"])
    relevance[100] = _relevance(100, paid=False)
    full["case-relevance.jsonl"] = _jsonl_bytes(relevance)
    inputs["full_pool_artifacts"] = full

    with pytest.raises(
        RetainedCohortExtensionError,
        match="base projection artifacts do not reproduce",
    ):
        extend_target_cohort(**inputs)


def test_extension_fails_when_eligible_omitted_frontier_is_insufficient() -> None:
    inputs = _inputs()
    full = dict(inputs["full_pool_artifacts"])
    records = _jsonl(full["disclosure-clearance.jsonl"])
    for record in records:
        if record["candidate_id"] in {
            _candidate_id(index) for index in range(100, 151)
        }:
            record["status"] = "quarantined"
    full["disclosure-clearance.jsonl"] = _jsonl_bytes(records)
    inputs["full_pool_artifacts"] = full
    _rebuild_base(inputs)

    with pytest.raises(RetainedCohortExtensionError, match="post-clearance"):
        extend_target_cohort(**inputs)


def test_extension_skips_quarantine_and_reconciles_it_as_an_exclusion() -> None:
    inputs = _inputs()
    full = dict(inputs["full_pool_artifacts"])
    records = _jsonl(full["disclosure-clearance.jsonl"])
    for record in records:
        if record["candidate_id"] == _candidate_id(100):
            record["status"] = "quarantined"
    full["disclosure-clearance.jsonl"] = _jsonl_bytes(records)
    inputs["full_pool_artifacts"] = full
    _rebuild_base(inputs)

    extension = extend_target_cohort(**inputs)

    assert _candidate_id(100) not in extension.incremental_candidate_ids
    assert _candidate_id(150) in extension.incremental_candidate_ids
    [exclusion] = _jsonl(extension.combined_artifacts["target-cohort-exclusions.jsonl"])
    assert exclusion["candidate_id"] == _candidate_id(100)
    assert exclusion["reason"] == "disclosure_clearance_quarantined"


def test_extension_fails_on_changed_base_input_or_prefix() -> None:
    inputs = _inputs()
    base = dict(inputs["base_projection_artifacts"])
    rows = _jsonl(base["target-cohort-selection.jsonl"])
    rows[0]["case_name"] = "changed"
    base["target-cohort-selection.jsonl"] = _jsonl_bytes(rows)
    inputs["base_projection_artifacts"] = base

    with pytest.raises(RetainedCohortExtensionError, match="output commitment"):
        extend_target_cohort(**inputs)


def test_extension_rejects_changed_snapshot_lineage() -> None:
    inputs = _inputs()
    inputs["snapshot_batch_digest"] = "e" * 64

    with pytest.raises(RetainedCohortExtensionError, match="snapshot lineage"):
        extend_target_cohort(**inputs)


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("projection_sha256", "projection digest"),
        ("budget_plan_sha256", "budget-plan digest"),
    ),
)
def test_extension_rejects_valid_hash_tampering(field: str, message: str) -> None:
    inputs = _inputs()
    base = dict(inputs["base_projection_artifacts"])
    summary = json.loads(base["target-cohort-projection.json"])
    summary[field] = "sha256:" + "f" * 64
    base["target-cohort-projection.json"] = _json_bytes(summary)
    inputs["base_projection_artifacts"] = base

    with pytest.raises(RetainedCohortExtensionError, match=message):
        extend_target_cohort(**inputs)


def test_extension_rejects_duplicate_docket_and_motion_identities() -> None:
    for mutation, message in (
        ("docket", "duplicate docket identity"),
        ("motion", "duplicate motion identity"),
    ):
        inputs = _inputs()
        full = dict(inputs["full_pool_artifacts"])
        selections = _jsonl(full["selection.jsonl"])
        if mutation == "docket":
            selections[149]["docket_number"] = selections[148]["docket_number"]
            selections[149]["court"] = selections[148]["court"]
        else:
            selections[149]["target_motion_entry_numbers"] = selections[148][
                "target_motion_entry_numbers"
            ]
            selections[149]["case_id"] = selections[148]["case_id"]
        full["selection.jsonl"] = _jsonl_bytes(selections)
        inputs["full_pool_artifacts"] = full
        _rebuild_base(inputs)
        with pytest.raises(RetainedCohortExtensionError, match=message):
            extend_target_cohort(**inputs)


@pytest.mark.parametrize(
    "artifact_name",
    ("document-downloads-merged.jsonl", "disclosure-clearance.jsonl"),
)
def test_extension_rejects_orphan_full_pool_document_rows(
    artifact_name: str,
) -> None:
    inputs = _inputs()
    full = dict(inputs["full_pool_artifacts"])
    rows = _jsonl(full[artifact_name])
    orphan = dict(rows[0])
    orphan["candidate_id"] = "orphan-candidate"
    orphan["source_document_id"] = "orphan-document"
    rows.append(orphan)
    full[artifact_name] = _jsonl_bytes(rows)
    inputs["full_pool_artifacts"] = full

    with pytest.raises(RetainedCohortExtensionError, match="outside resolved pool"):
        extend_target_cohort(**inputs)


def test_extension_accounts_for_exact_cap_and_disjoint_obligations() -> None:
    inputs = _inputs(paid_after=100, max_projected_budget_usd="153.00")
    inputs["purchase_obligations"] = _obligations(reserved="0.50")

    exact = extend_target_cohort(**inputs)

    assert exact.combined_budget["base_projected_usd"] == "0.00"
    assert exact.combined_budget["incremental_projected_usd"] == "152.50"
    assert exact.combined_budget["reserved_obligation_usd"] == "0.50"
    assert exact.combined_budget["cumulative_obligation_usd"] == "153.00"
    assert exact.combined_budget["remaining_headroom_usd"] == "0.00"
    inputs = _inputs(paid_after=100, max_projected_budget_usd="152.99")
    inputs["purchase_obligations"] = _obligations(reserved="0.50")
    with pytest.raises(RetainedCohortExtensionError, match="cannot meet"):
        extend_target_cohort(**inputs)


def test_extension_counts_unknown_and_writeoff_and_enforces_per_case_cap() -> None:
    inputs = _inputs(paid_after=100, max_projected_budget_usd="160.00")
    inputs["purchase_obligations"] = _obligations(unknown="3.05", write_off="3.05")
    extension = extend_target_cohort(**inputs)
    assert extension.combined_budget["unknown_obligation_usd"] == "3.05"
    assert extension.combined_budget["write_off_obligation_usd"] == "3.05"
    assert extension.combined_budget["cumulative_obligation_usd"] == "158.60"

    inputs = _inputs(max_missing_core_documents_per_case=25)
    with pytest.raises(RetainedCohortExtensionError, match="per-case cap"):
        extend_target_cohort(**inputs)


def test_purchase_obligations_are_derived_from_every_committed_journal_state(
    tmp_path: Path,
) -> None:
    cohort = _cohort_policy()
    ledger = (tmp_path / "purchase.sqlite3").resolve()
    artifact = _purchase_policy_artifact(ledger, cohort, opening="2.00")
    policy = verify_case_dev_purchase_policy(artifact)
    with CaseDevPurchaseJournal(ledger, policy=policy) as journal:
        journal.plan(_journal_plan(("reserved", "unknown", "writeoff", "confirmed")))
        journal.submit("reserved")
        journal.submit("unknown")
        journal.mark_unknown("unknown", "timeout after dispatch")
        journal.submit("writeoff")
        journal.mark_unknown("writeoff", "provider outcome unavailable")
        journal.reconcile(
            {
                "source_document_id": "writeoff",
                "disposition": "write_off",
                "source_type": "support_confirmation",
                "source_reference": "support://ticket-1",
                "pacer_fees": None,
                "download_url": None,
            }
        )
        journal.submit("confirmed")
        journal.confirm(
            "confirmed",
            response={"document": "confirmed"},
            fees={"total_usd": "1.00"},
        )

        snapshot = purchase_obligation_snapshot(
            policy=policy,
            journal=journal,
            cohort_policy_artifact=cohort,
        )

    assert snapshot.budget_record() == {
        "opening_obligation_usd": "2.00",
        "confirmed_obligation_usd": "1.00",
        "reserved_obligation_usd": "3.05",
        "unknown_obligation_usd": "3.05",
        "write_off_obligation_usd": "3.05",
    }
    assert snapshot.total == Decimal("12.15")
    assert snapshot.purchase_policy_sha256 == "sha256:" + policy.policy_sha256
    assert snapshot.purchase_journal_state_sha256.startswith("sha256:")


def test_extension_api_has_no_operator_obligation_defaults() -> None:
    parameters = inspect.signature(extend_target_cohort).parameters

    assert "reserved_obligation_usd" not in parameters
    assert "unknown_obligation_usd" not in parameters
    assert "write_off_obligation_usd" not in parameters
    assert parameters["purchase_obligations"].default is inspect.Parameter.empty


def test_extend_target_cohort_cli_is_noncharging_and_resume_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def provider_construction_forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("extension must not construct a provider client")

    for name in (
        "CaseDevClient",
        "CourtListenerClient",
        "FirecrawlCourtListenerHTMLSource",
    ):
        monkeypatch.setattr(
            f"legalforecast.cli.{name}", provider_construction_forbidden
        )
    argv, _, custom_run_card, custom_log = _cli_fixture(tmp_path)
    output_root = tmp_path / "extension"

    assert main(argv) == 0
    before = {
        str(path.relative_to(output_root)): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    assert main(argv) == 0
    after = {
        str(path.relative_to(output_root)): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }

    assert before == after
    assert custom_run_card.is_file()
    assert custom_log.is_file()
    record = json.loads((output_root / "retained-cohort-extension.json").read_text())
    assert record["combined_case_count"] == 150
    assert record["paid_activity_requested"] is False
    assert record["paid_activity_executed"] is False
    assert (output_root / "incremental/target-cohort-selection.jsonl").is_file()

    committed_output = output_root / "target-cohort-selection.jsonl"
    committed_output.write_bytes(b"tampered\n")
    assert main(argv) == 2
    assert committed_output.read_bytes() == b"tampered\n"


def test_cli_rejects_metadata_aliases_and_dry_run_overwrite(tmp_path: Path) -> None:
    argv, cohort_policy, run_card, log = _cli_fixture(tmp_path)

    assert main(argv) == 0
    run_card_before = run_card.read_bytes()
    log_before = log.read_bytes()

    dry_argv = [value for value in argv if value != "--execute"]
    assert main(dry_argv) == 2
    assert run_card.read_bytes() == run_card_before
    assert log.read_bytes() == log_before

    assert main([*argv, "--no-resume"]) == 2
    assert run_card.read_bytes() == run_card_before
    assert log.read_bytes() == log_before

    alias_argv = list(argv)
    run_card_index = alias_argv.index("--run-card-output") + 1
    alias_argv[run_card_index] = str(cohort_policy)
    policy_before = cohort_policy.read_bytes()
    assert main(alias_argv) == 2
    assert cohort_policy.read_bytes() == policy_before


def test_cli_initializes_missing_zero_obligation_purchase_ledger(
    tmp_path: Path,
) -> None:
    argv, _, _, _ = _cli_fixture(tmp_path)
    ledger = Path(argv[argv.index("--purchase-ledger") + 1])
    ledger.unlink()

    assert main(argv) == 0
    assert ledger.is_file()


def test_cli_rejects_self_consistent_substituted_frontier(tmp_path: Path) -> None:
    argv, _, _, _ = _cli_fixture(tmp_path)
    frontier = Path(argv[argv.index("--full-candidate-frontier") + 1])
    frontier_card = Path(argv[argv.index("--frontier-run-card") + 1])
    artifact = json.loads(frontier.read_text())
    artifact["policy"]["source_commitments"]["case_relevance_sha256"] = (
        "sha256:" + "f" * 64
    )
    artifact["policy_sha256"] = _canonical_sha(artifact["policy"])
    frontier.write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
    card = json.loads(frontier_card.read_text())
    card["frontier_sha256"] = _sha(frontier.read_bytes())
    frontier_card.write_text(json.dumps(card, sort_keys=True) + "\n", encoding="utf-8")

    assert main(argv) == 2


def test_cli_rejects_changed_authenticated_review_receipt(tmp_path: Path) -> None:
    argv, _, _, _ = _cli_fixture(tmp_path)
    receipt = Path(argv[argv.index("--review-receipt") + 1])
    record = json.loads(receipt.read_text())
    record["authenticated_reviewer_id"] = "reviewer:substitute"
    receipt.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert main(argv) == 2


def _cli_fixture(tmp_path: Path) -> tuple[list[str], Path, Path, Path]:
    inputs = _inputs()
    base_root = tmp_path / "base"
    full_root = tmp_path / "preparation"
    output_root = tmp_path / "extension"
    base_root.mkdir()
    full_root.mkdir()
    for name, payload in inputs["base_projection_artifacts"].items():
        (base_root / name).write_bytes(payload)
    full_paths: dict[str, Path] = {}
    canonical_full_paths = {
        "selection.jsonl": (
            full_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
        ),
        "case-relevance.jsonl": full_root / "03-gap-bridge/case-relevance.jsonl",
        "document-downloads-merged.jsonl": (
            full_root / "03c-merged-downloads/document-downloads-merged.jsonl"
        ),
        "disclosure-clearance.jsonl": tmp_path / "clearance/disclosure-clearance.jsonl",
    }
    for name, payload in inputs["full_pool_artifacts"].items():
        path = canonical_full_paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        full_paths[name] = path
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text(
        json.dumps(inputs["cohort_policy_artifact"], sort_keys=True) + "\n",
        encoding="utf-8",
    )
    snapshot = tmp_path / "snapshot-manifest.json"
    snapshot.write_text(
        json.dumps(
            {
                "cycle_hash": inputs["snapshot_cycle_hash"],
                "batch_digest": inputs["snapshot_batch_digest"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    purchase_ledger = (tmp_path / "purchase.sqlite3").resolve()
    purchase_policy_artifact = _purchase_policy_artifact(
        purchase_ledger, inputs["cohort_policy_artifact"]
    )
    purchase_policy = tmp_path / "purchase-policy.json"
    purchase_policy.write_text(
        json.dumps(purchase_policy_artifact, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with CaseDevPurchaseJournal(
        purchase_ledger,
        policy=verify_case_dev_purchase_policy(purchase_policy_artifact),
    ):
        pass
    restriction_path = full_root / "06-clearance-inputs/restriction-evidence.jsonl"
    restriction_path.parent.mkdir(parents=True, exist_ok=True)
    restriction_path.write_bytes(
        _jsonl_bytes(
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": f"{row['candidate_id']}-complaint",
                "restriction_status": "public",
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked"
                ],
            }
            for row in _jsonl(inputs["full_pool_artifacts"]["selection.jsonl"])
        )
    )
    reviews = tmp_path / "clearance/reviews.jsonl"
    reviews.write_bytes(b'{"review":"all-clear"}\n')
    receipt_record = {
        "schema_version": "legalforecast.disclosure_review_receipt.v1",
        "review_artifact_sha256": hashlib.sha256(reviews.read_bytes()).hexdigest(),
        "authenticated_reviewer_id": "reviewer:john",
        "controlled_store_uri": "private-store://cycle-1/reviews",
        "authentication_method": "cloudflare_access_oidc",
        "authenticated_at": "2026-07-14T14:00:00Z",
    }
    review_receipt = tmp_path / "clearance/review-receipt.json"
    review_receipt.write_text(json.dumps(receipt_record) + "\n", encoding="utf-8")
    clearance_run_card = tmp_path / "clearance/run-card.json"
    clearance_card_record = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "clear-disclosures",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "download_manifest": _path_commitment(
                full_paths["document-downloads-merged.jsonl"]
            ),
            "restriction_evidence": _path_commitment(restriction_path),
            "reviews": _path_commitment(reviews),
            "review_receipt": _path_commitment(review_receipt),
        },
        "output_commitments": {
            "disclosure_clearance": _path_commitment(
                full_paths["disclosure-clearance.jsonl"]
            )
        },
        "review_authority": {
            "reviewer_id": "reviewer:john",
            "controlled_store_uri": "private-store://cycle-1/reviews",
            "authentication_method": "cloudflare_access_oidc",
            "authenticated_at": "2026-07-14T14:00:00Z",
            "review_artifact_sha256": _sha(reviews.read_bytes()),
        },
    }
    clearance_run_card.write_text(
        json.dumps(clearance_card_record, sort_keys=True) + "\n", encoding="utf-8"
    )
    preparation_config = full_root / "target-100-config.json"
    config_record: dict[str, Any] = {
        "schema_version": "legalforecast.target_100_config.v1",
        "driver_execute": True,
        "target_case_count": 100,
        "cost_per_document_usd": "3.05",
        "max_projected_budget_usd": "2250.00",
        "max_missing_core_documents_per_case": 24,
        "snapshot_manifest_sha256": _sha(snapshot.read_bytes()),
        "snapshot_cycle_hash": inputs["snapshot_cycle_hash"],
        "snapshot_batch_digest": inputs["snapshot_batch_digest"],
    }
    config_record["config_sha256"] = _canonical_sha(
        {key: value for key, value in config_record.items() if key != "config_sha256"}
    )
    preparation_config.write_text(
        json.dumps(config_record, sort_keys=True) + "\n", encoding="utf-8"
    )
    preparation_summary = full_root / "target-100-preparation-summary.json"
    summary_record = {
        "schema_version": "legalforecast.target_100_preparation.v1",
        "dry_run": False,
        "paid_activity_executed": False,
        "budget_status": "provisional_pre_clearance",
        "next_stage": "clear-disclosures",
        "config_sha256": config_record["config_sha256"],
        "target_case_count": 100,
        "cost_per_document_usd": "3.05",
        "max_projected_budget_usd": "2250.00",
        "max_missing_core_documents_per_case": 24,
        "snapshot_manifest_sha256": _sha(snapshot.read_bytes()),
        "snapshot_batch_digest": inputs["snapshot_batch_digest"],
        "stage_commitments": {
            "03-gap-bridge": {
                "public-packet-selection-reconciled.jsonl": _sha(
                    full_paths["selection.jsonl"].read_bytes()
                ),
                "case-relevance.jsonl": _sha(
                    full_paths["case-relevance.jsonl"].read_bytes()
                ),
            },
            "03c-merged-downloads": {
                "document-downloads-merged.jsonl": _sha(
                    full_paths["document-downloads-merged.jsonl"].read_bytes()
                )
            },
            "06-clearance-inputs": {
                "restriction-evidence.jsonl": _sha(restriction_path.read_bytes())
            },
        },
    }
    preparation_summary.write_text(
        json.dumps(summary_record, sort_keys=True) + "\n", encoding="utf-8"
    )
    preparation_success_card = full_root / "run-cards/prepare-target-100.json"
    preparation_success_card.parent.mkdir(parents=True, exist_ok=True)
    preparation_success_card.write_text(
        json.dumps({"stage": "prepare-target-100", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    frontier = tmp_path / "frontier/full-candidate-frontier.json"
    frontier.parent.mkdir(parents=True, exist_ok=True)
    frontier_commitments = {
        "snapshot_manifest_sha256": _sha(snapshot.read_bytes()),
        "preparation_config_sha256": _sha(preparation_config.read_bytes()),
        "preparation_summary_sha256": _sha(preparation_summary.read_bytes()),
        "preparation_success_run_card_sha256": _sha(
            preparation_success_card.read_bytes()
        ),
        "reconciled_selection_sha256": _sha(full_paths["selection.jsonl"].read_bytes()),
        "case_relevance_sha256": _sha(full_paths["case-relevance.jsonl"].read_bytes()),
        "download_manifest_sha256": _sha(
            full_paths["document-downloads-merged.jsonl"].read_bytes()
        ),
        "core_filter_results_sha256": "sha256:" + "1" * 64,
        "provisional_budget_plan_sha256": "sha256:" + "2" * 64,
        "restriction_evidence_sha256": _sha(restriction_path.read_bytes()),
        "disclosure_review_requests_sha256": "sha256:" + "3" * 64,
    }
    candidates: list[dict[str, Any]] = [
        {
            "candidate_id": _candidate_id(index),
            "rank": index + 1,
            "selection_status": "selected" if index < 100 else "eligible_omitted",
            "exclusion_reasons": [],
        }
        for index in range(151)
    ]
    frontier_policy: dict[str, Any] = {
        "target_case_count": 100,
        "candidate_count": 151,
        "selected_candidate_count": 100,
        "frontier_truncated": False,
        "source_commitments": frontier_commitments,
        "clearance_contract": {
            "run_card_schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "clear-disclosures",
            "required_status": "completed",
            "required_dry_run": False,
            "required_execute": True,
            "required_paid_activity_executed": False,
            "download_manifest_sha256": frontier_commitments[
                "download_manifest_sha256"
            ],
            "restriction_evidence_sha256": frontier_commitments[
                "restriction_evidence_sha256"
            ],
            "required_source_commitments": [
                "download_manifest",
                "restriction_evidence",
                "reviews",
                "review_receipt",
            ],
            "required_output_commitments": ["disclosure_clearance"],
            "required_review_authority_fields": [
                "reviewer_id",
                "controlled_store_uri",
                "authentication_method",
                "authenticated_at",
                "review_artifact_sha256",
            ],
            "orphan_clearance_rows_allowed": False,
        },
        "candidates": candidates,
    }
    frontier.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.target_cohort_candidate_frontier.v1",
                "policy": frontier_policy,
                "policy_sha256": _canonical_sha(frontier_policy),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    frontier_run_card = tmp_path / "frontier/run-card.json"
    frontier_run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-target-cohort-frontier",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "zero_provider_activity_evidence": True,
                "frontier_sha256": _sha(frontier.read_bytes()),
                "input_paths": [
                    str(full_root),
                    str(preparation_summary),
                    str(preparation_config),
                    str(snapshot),
                    str(preparation_success_card),
                ],
                "output_paths": [str(frontier)],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    base_summary_path = base_root / "target-cohort-projection.json"
    base_summary = json.loads(base_summary_path.read_text())
    base_summary["snapshot_manifest_sha256"] = _sha(snapshot.read_bytes())
    base_summary["preparation_summary_sha256"] = _sha(preparation_summary.read_bytes())
    base_summary["preparation_config_sha256"] = _sha(preparation_config.read_bytes())
    base_summary["clearance_run_card_sha256"] = _sha(clearance_run_card.read_bytes())
    base_summary["input_commitments"] = {
        str(preparation_summary.resolve()): _sha(preparation_summary.read_bytes()),
        str(preparation_config.resolve()): _sha(preparation_config.read_bytes()),
        str(snapshot.resolve()): _sha(snapshot.read_bytes()),
        str(clearance_run_card.resolve()): _sha(clearance_run_card.read_bytes()),
        str(restriction_path.resolve()): _sha(restriction_path.read_bytes()),
    }
    base_summary_path.write_text(
        json.dumps(base_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    custom_run_card = tmp_path / "metadata/extension-run-card.json"
    custom_log = tmp_path / "metadata/extension-log.jsonl"
    argv = [
        "acquisition",
        "extend-target-cohort",
        "--output-root",
        str(output_root),
        "--execute",
        "--run-card-output",
        str(custom_run_card),
        "--log-output",
        str(custom_log),
        "--base-cohort-root",
        str(base_root),
        "--preparation-root",
        str(full_root),
        "--preparation-summary",
        str(preparation_summary),
        "--preparation-config",
        str(preparation_config),
        "--full-candidate-frontier",
        str(frontier),
        "--frontier-run-card",
        str(frontier_run_card),
        "--clearance-run-card",
        str(clearance_run_card),
        "--reviews",
        str(reviews),
        "--review-receipt",
        str(review_receipt),
        "--cohort-policy",
        str(cohort_policy),
        "--snapshot-manifest",
        str(snapshot),
        "--purchase-policy",
        str(purchase_policy),
        "--purchase-ledger",
        str(purchase_ledger),
        "--cost-per-document-usd",
        "3.05",
        "--max-projected-budget-usd",
        "2250.00",
        "--max-missing-core-documents-per-case",
        "24",
    ]
    return argv, cohort_policy, custom_run_card, custom_log


def _inputs(
    *,
    paid_after: int | None = None,
    max_projected_budget_usd: str = "2250.00",
    max_missing_core_documents_per_case: int = 24,
) -> dict[str, Any]:
    selections = [_selection(index) for index in range(151)]
    relevance = [
        _relevance(index, paid=paid_after is not None and index >= paid_after)
        for index in range(151)
    ]
    downloads = [_download(index) for index in range(151)]
    clearance = [_clearance(index) for index in range(151)]
    base_projection = project_target_cohort(
        selections=selections,
        case_relevance=relevance,
        download_manifest=downloads,
        clearance_records=clearance,
        target_case_count=100,
        cost_per_document_usd="3.05",
        max_projected_budget_usd=max_projected_budget_usd,
        max_missing_core_documents_per_case=max_missing_core_documents_per_case,
    )
    base_artifacts = _base_artifacts(base_projection)
    return {
        "base_projection_artifacts": base_artifacts,
        "full_pool_artifacts": {
            "selection.jsonl": _jsonl_bytes(selections),
            "case-relevance.jsonl": _jsonl_bytes(relevance),
            "document-downloads-merged.jsonl": _jsonl_bytes(downloads),
            "disclosure-clearance.jsonl": _jsonl_bytes(clearance),
        },
        "cohort_policy_artifact": _cohort_policy(),
        "snapshot_manifest_sha256": "sha256:" + "b" * 64,
        "snapshot_cycle_hash": "c" * 64,
        "snapshot_batch_digest": "d" * 64,
        "cost_per_document_usd": "3.05",
        "max_projected_budget_usd": max_projected_budget_usd,
        "max_missing_core_documents_per_case": (max_missing_core_documents_per_case),
        "purchase_obligations": _obligations(),
        "authenticated_lineage": _lineage(),
    }


def _base_artifacts(projection: Any) -> dict[str, bytes]:
    records: dict[str, bytes] = {
        "target-cohort-selection.jsonl": _jsonl_bytes(projection.selections),
        "case-relevance.jsonl": _jsonl_bytes(projection.case_relevance),
        "document-downloads-merged.jsonl": _jsonl_bytes(projection.download_manifest),
        "disclosure-clearance.jsonl": _jsonl_bytes(projection.clearance_records),
        "restriction-evidence.jsonl": _jsonl_bytes(projection.restriction_evidence),
        "core-filter-results.jsonl": _jsonl_bytes(
            row.to_record() for row in projection.core_filter_results
        ),
        "target-cohort-exclusions.jsonl": _jsonl_bytes(projection.exclusions),
        "free-document-downloads.jsonl": _jsonl_bytes(
            record
            for record in projection.download_manifest
            if record.get("free_or_purchased") == "free"
        ),
        "purchased-document-downloads.jsonl": _jsonl_bytes(
            record
            for record in projection.download_manifest
            if record.get("free_or_purchased") == "purchased"
        ),
        "missing-core-budget-plan.json": _json_bytes(
            projection.budget_plan.to_record()
        ),
    }
    summary = dict(projection.summary)
    summary.update(
        {
            "snapshot_manifest_sha256": "sha256:" + "b" * 64,
            "snapshot_cycle_hash": "c" * 64,
            "snapshot_batch_digest": "d" * 64,
            "preparation_summary_sha256": _lineage().preparation_summary_sha256,
            "preparation_config_sha256": _lineage().preparation_config_sha256,
            "clearance_run_card_sha256": _lineage().clearance_run_card_sha256,
            "input_commitments": {
                "/fixture/preparation-summary.json": (
                    _lineage().preparation_summary_sha256
                ),
                "/fixture/preparation-config.json": (
                    _lineage().preparation_config_sha256
                ),
                "/fixture/snapshot.json": _lineage().snapshot_manifest_sha256,
                "/fixture/clearance-run-card.json": (
                    _lineage().clearance_run_card_sha256
                ),
                "/fixture/restrictions.jsonl": (_lineage().restriction_evidence_sha256),
            },
        }
    )
    summary["output_commitments"] = {
        name: _sha(payload) for name, payload in sorted(records.items())
    }
    records["target-cohort-projection.json"] = _json_bytes(summary)
    return records


def _cohort_policy() -> dict[str, Any]:
    taxonomy = cohort_reason_policy_taxonomy()
    return generate_cohort_policy(
        {
            "cycle_id": "cycle-1",
            "cycle_acquisition_hash": "c" * 64,
            "eligibility_anchor": "2026-06-30",
            "stop_rule": {
                "mode": "target_or_deadline",
                "target_clean_cases": 150,
                "search_window_end": "2026-07-14",
                "stop_on_frontier_exhaustion": True,
                "stop_on_budget_headroom_exhaustion": True,
            },
            "window_policy": {
                "overlap_days": 1,
                "backfill_late_indexed": True,
                "refresh_before_purchase": True,
            },
            "refresh_policy": {
                "evidence_precedence": {
                    "transient": 0,
                    "excluded_refreshable": 10,
                    "accepted": 20,
                    "newly_free": 30,
                    "excluded_immutable": 100,
                },
                "transition_semantics": {
                    "higher_rank_supersedes_lower_rank": True,
                    "latest_wins_equal_rank": True,
                    "transient_supersedes_evidenced": False,
                    "immutable_reconsideration": "never",
                },
                **{key: list(value) for key, value in taxonomy.items()},
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
                "cycle_budget_usd": "2250.00",
                "max_per_case_usd": "73.20",
                "reservation_headroom_required": True,
            },
            "disclosure_clearance": {
                "all_documents_require_clearance": True,
                "unknown_or_unscannable": "quarantine",
                "replacement_rule": "next_cheapest_eligible_under_same_cap",
            },
            "reduced_n": {
                "target_clean_cases": 150,
                "below_minimum_action": "pilot_only_no_official_cycle",
                "claim_tiers": [
                    {
                        "maximum_clean_cases": 150,
                        "minimum_clean_cases": 1,
                        "claim_class": "target",
                        "minimum_prediction_units": None,
                        "insufficient_units_action": None,
                    }
                ],
            },
        }
    )


def _obligations(
    *,
    opening: str = "0.00",
    confirmed: str = "0.00",
    reserved: str = "0.00",
    unknown: str = "0.00",
    write_off: str = "0.00",
) -> PurchaseObligationSnapshot:
    return PurchaseObligationSnapshot(
        purchase_policy_sha256="sha256:" + "1" * 64,
        purchase_journal_state_sha256="sha256:" + "2" * 64,
        canonical_ledger_path="/tmp/test-purchase-ledger.sqlite3",
        opening_obligation=Decimal(opening),
        confirmed_obligation=Decimal(confirmed),
        reserved_obligation=Decimal(reserved),
        unknown_obligation=Decimal(unknown),
        write_off_obligation=Decimal(write_off),
    )


def _lineage() -> AuthenticatedPoolLineage:
    return AuthenticatedPoolLineage(
        preparation_summary_sha256="sha256:" + "3" * 64,
        preparation_config_sha256="sha256:" + "4" * 64,
        snapshot_manifest_sha256="sha256:" + "b" * 64,
        full_candidate_frontier_sha256="sha256:" + "5" * 64,
        frontier_policy_sha256="sha256:" + "6" * 64,
        frontier_run_card_sha256="sha256:" + "7" * 64,
        clearance_run_card_sha256="sha256:" + "8" * 64,
        clearance_reviews_sha256="sha256:" + "9" * 64,
        clearance_review_receipt_sha256="sha256:" + "a" * 64,
        restriction_evidence_sha256="sha256:" + "e" * 64,
    )


def _purchase_policy_artifact(
    ledger: Path,
    cohort: dict[str, Any],
    *,
    opening: str = "0.00",
) -> dict[str, object]:
    return generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-1",
            "cohort_policy_sha256": cohort["policy_sha256"],
            "canonical_ledger_path": str(ledger),
            "hard_cap_usd": "2250.00",
            "opening_committed_spend_usd": opening,
            "opening_case_committed_spend_usd": (
                {} if opening == "0.00" else {"journal-case": opening}
            ),
            "max_per_case_usd": "73.20",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-07-14T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )


def _journal_plan(document_ids: tuple[str, ...]) -> MissingCoreBudgetPlan:
    count = len(document_ids)
    return MissingCoreBudgetPlan(
        case_plans=(
            CaseMissingCorePurchasePlan(
                candidate_id="journal-case",
                purchase_document_ids=document_ids,
                missing_core_document_count=count,
                estimated_cost=Decimal("3.05") * count,
                audit_only_document_count=0,
                dry_run=False,
            ),
        ),
        cost_per_document=Decimal("3.05"),
        max_projected_budget=Decimal("2250.00"),
        max_missing_core_documents_per_case=24,
        dry_run=False,
    )


def _rebuild_base(inputs: dict[str, Any]) -> None:
    full = inputs["full_pool_artifacts"]
    projection = project_target_cohort(
        selections=_jsonl(full["selection.jsonl"]),
        case_relevance=_jsonl(full["case-relevance.jsonl"]),
        download_manifest=_jsonl(full["document-downloads-merged.jsonl"]),
        clearance_records=_jsonl(full["disclosure-clearance.jsonl"]),
        target_case_count=100,
        cost_per_document_usd=inputs["cost_per_document_usd"],
        max_projected_budget_usd=inputs["max_projected_budget_usd"],
        max_missing_core_documents_per_case=inputs[
            "max_missing_core_documents_per_case"
        ],
    )
    inputs["base_projection_artifacts"] = _base_artifacts(projection)


def _candidate_id(index: int) -> str:
    return f"case-{index:03d}"


def _selection(index: int) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    return {
        "candidate_id": candidate_id,
        "case_id": f"docket-{index:03d}",
        "case_name": f"Case {index}",
        "court": "nysd",
        "docket_number": f"1:26-cv-{index:05d}",
        "target_motion_entry_numbers": [index + 10],
        "decision_date": "2026-07-01",
        "selected": True,
    }


def _relevance(index: int, *, paid: bool) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    documents = [
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-complaint",
            "setup_runner_label": "core_mtd",
            "document_role": "complaint",
            "availability_status": "available",
            "requires_paid_recovery": False,
            "model_visible": True,
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
            "restriction_evidence": ["courtlistener_public_download_record_checked"],
        }
    ]
    documents.append(
        {
            "candidate_id": candidate_id,
            "source_document_id": f"{candidate_id}-mtd",
            "setup_runner_label": "core_mtd",
            "document_role": "motion_to_dismiss_memorandum",
            "availability_status": "unavailable" if paid else "available",
            "requires_paid_recovery": paid,
            "model_visible": True,
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
            "restriction_evidence": [
                "courtlistener_rest_recap_document_exact_match"
                if paid
                else "courtlistener_public_download_record_checked"
            ],
        }
    )
    return {"candidate_id": candidate_id, "documents": documents}


def _download(index: int) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    return {
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-complaint",
        "local_path": f"{candidate_id}/complaint.pdf",
        "sha256": "a" * 64,
        "byte_count": 10,
        "free_or_purchased": "free",
    }


def _clearance(index: int) -> dict[str, Any]:
    candidate_id = _candidate_id(index)
    return {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-complaint",
        "sha256": "a" * 64,
        "byte_count": 10,
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://cycle-1/free-clearance",
        "reviewed_at": "2026-07-14T14:00:00Z",
        "free_or_purchased": "free",
    }


def _jsonl(payload: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in payload.splitlines() if line]


def _jsonl_bytes(records: Any) -> bytes:
    return b"".join(
        (json.dumps(dict(record), sort_keys=True, allow_nan=False) + "\n").encode()
        for record in records
    )


def _json_bytes(record: dict[str, Any]) -> bytes:
    return (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return _sha(payload)


def _path_commitment(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": _sha(path.read_bytes())}
