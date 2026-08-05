from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes
from legalforecast.ingestion.ranked_reserve_replacement import (
    ranked_reserve_result_bytes,
)
from legalforecast.ingestion.zero_cost_successor import (
    CONFIG_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    ZeroCostSuccessorError,
    project_zero_cost_successor,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


@dataclass
class Fixture:
    kwargs: dict[str, Any]
    ranked_result: dict[str, Any]
    active: list[dict[str, Any]]
    clearance: list[dict[str, Any]]
    restrictions: list[dict[str, Any]]
    manifest: list[dict[str, Any]]

    def refresh(self) -> None:
        self.kwargs["active_selection"] = self.active
        self.kwargs["active_selection_bytes"] = _jsonl(self.active)
        self.kwargs["disclosure_clearance"] = self.clearance
        self.kwargs["disclosure_clearance_bytes"] = _jsonl(self.clearance)
        self.kwargs["restriction_evidence"] = self.restrictions
        self.kwargs["download_manifest"] = self.manifest
        self.ranked_result["active_selection_sha256"] = _sha(
            self.kwargs["active_selection_bytes"]
        )
        self.kwargs["ranked_result"] = self.ranked_result
        self.kwargs["ranked_result_bytes"] = ranked_reserve_result_bytes(
            self.ranked_result
        )


def _fixture() -> Fixture:
    originals = [_base_selection(f"case-{index:03d}") for index in range(100)]
    reserve_rows = [
        {
            "schema_version": "legalforecast.target_cohort_ranked_reserve.v1",
            "candidate_id": f"reserve-{index}",
            "reserve_rank": index + 1,
        }
        for index in range(5)
    ]
    reserve_selections = [
        _base_selection(str(row["candidate_id"])) for row in reserve_rows
    ]
    zero_ids = ("70525291", "71279774", "71677178")
    zero_selections = [_zero_selection(candidate_id) for candidate_id in zero_ids]
    pool = [*originals, *reserve_selections, *zero_selections]
    residual_ids = {"case-000", "case-001", "case-002"}
    active = [row for row in originals if row["candidate_id"] not in residual_ids]
    active.extend(reserve_selections[:2])
    replacements = reserve_selections[:2]
    active_bytes = _jsonl(active)
    replacement_bytes = _jsonl(replacements)
    exclusion_bytes = _jsonl([{"candidate_id": "case-000"}])
    budget_bytes = canonical_json_bytes({"total_estimated_cost_usd": "21.35"})
    disposition = _disposition()
    result: dict[str, Any] = {
        "schema_version": "legalforecast.ranked_reserve_replacement_result.v2",
        "projection_sha256": "sha256:" + "1" * 64,
        "cycle_id": "cycle-1-target-100",
        "purchase_policy_sha256": "sha256:" + "2" * 64,
        "purchase_journal_state_sha256": "sha256:" + "3" * 64,
        "hard_cap_usd": "567.30",
        "terminal_exclusions_sha256": disposition[
            "residual_terminal_exclusions_sha256"
        ],
        "terminal_disposition": disposition,
        "terminal_disposition_sha256": _sha(canonical_json_bytes(disposition)),
        "active_selection_sha256": _sha(active_bytes),
        "replacement_selection_sha256": _sha(replacement_bytes),
        "successor_exclusions_sha256": _sha(exclusion_bytes),
        "replacement_budget_plan_sha256": _sha(budget_bytes),
        "active_case_count": 99,
        "replacement_case_count": 2,
        "committed_spend_usd": "524.90",
        "reserved_replacement_spend_usd": "21.35",
        "remaining_headroom_usd": "0.00",
        "successor_approval_required": True,
        "replacement_event_record_sha256s": ["sha256:" + "4" * 64],
        "tranche_event_record_sha256s": ["sha256:" + "5" * 64],
        "provider_activity_requested": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    relevance: list[dict[str, Any]] = [
        {
            "candidate_id": row["candidate_id"],
            "documents": _core_documents(str(row["candidate_id"])),
        }
        for row in [*originals, *reserve_selections]
    ]
    manifest: list[dict[str, Any]] = []
    clearance: list[dict[str, Any]] = []
    restrictions: list[dict[str, Any]] = []
    for row in [*originals, *reserve_selections]:
        candidate_id = str(row["candidate_id"])
        for document in _core_documents(candidate_id):
            document_id = str(document["source_document_id"])
            manifest.append(_manifest(candidate_id, document_id))
            clearance.append(_clearance(candidate_id, document_id, status="cleared"))
            restrictions.append(_restriction(candidate_id, document_id))
    for candidate_id in zero_ids:
        documents = _zero_documents(candidate_id)
        relevance.append({"candidate_id": candidate_id, "documents": documents})
        for document in documents:
            document_id = str(document["source_document_id"])
            manifest.append(_manifest(candidate_id, document_id))
            clearance.append(
                _clearance(
                    candidate_id,
                    document_id,
                    status="cleared" if candidate_id == "71677178" else "quarantined",
                )
            )
            restrictions.append(_restriction(candidate_id, document_id))
    kwargs: dict[str, Any] = {
        "target_projection": {
            "schema_version": "legalforecast.target_cohort_projection.v1",
            "projection_sha256": "sha256:" + "1" * 64,
            "selected_case_count": 100,
            "ranked_reserve_case_count": 5,
            "eligibility_anchor": "2026-06-30",
            "max_projected_budget_usd": "567.30",
        },
        "original_selection": originals,
        "ranked_reserve": reserve_rows,
        "source_pool": pool,
        "ranked_result": result,
        "ranked_result_bytes": ranked_reserve_result_bytes(result),
        "authenticated_ranked_result": json.loads(ranked_reserve_result_bytes(result)),
        "active_selection": active,
        "active_selection_bytes": active_bytes,
        "replacement_selection": replacements,
        "replacement_selection_bytes": replacement_bytes,
        "successor_exclusions_bytes": exclusion_bytes,
        "replacement_budget_plan_bytes": budget_bytes,
        "disclosure_clearance": clearance,
        "disclosure_clearance_bytes": _jsonl(clearance),
        "disclosure_clearance_run_card_bytes": canonical_json_bytes(
            {"schema_version": "legalforecast.provenance_model_clearance_run_card.v1"}
        ),
        "case_relevance": relevance,
        "download_manifest": manifest,
        "restriction_evidence": restrictions,
    }
    return Fixture(
        kwargs=kwargs,
        ranked_result=result,
        active=active,
        clearance=clearance,
        restrictions=restrictions,
        manifest=manifest,
    )


def test_projects_exact_100_from_first_fully_cleared_frozen_candidate() -> None:
    fixture = _fixture()

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert len(successor.selection) == 100
    assert successor.selection[-1]["candidate_id"] == "71677178"
    assert successor.config["schema_version"] == CONFIG_SCHEMA_VERSION
    assert successor.config["selected_zero_cost_candidate_id"] == "71677178"
    assert successor.config["hard_cap_usd"] == "567.30"
    assert successor.state["schema_version"] == STATE_SCHEMA_VERSION
    assert successor.state["retained_original_case_count"] == 97
    assert successor.state["promoted_reserve_case_count"] == 2
    assert successor.state["selected_case_count"] == 100
    assert successor.state["provider_activity_executed"] is False
    assert successor.state["evaluation_authorized"] is False


def test_rejects_compact_ranked_result_bytes() -> None:
    fixture = _fixture()
    fixture.kwargs["ranked_result_bytes"] = canonical_json_bytes(fixture.ranked_result)

    with pytest.raises(ZeroCostSuccessorError, match="not canonical JSON"):
        project_zero_cost_successor(**fixture.kwargs)


def test_ranked_result_serializer_has_explicit_ascii_contract() -> None:
    payload = ranked_reserve_result_bytes({"note": "résumé"})

    assert payload == b'{\n  "note": "r\\u00e9sum\\u00e9"\n}\n'


def test_rejects_extra_successor_commitment_keys() -> None:
    successor = project_zero_cost_successor(**_fixture().kwargs)
    config_commitments = dict(successor.config["output_commitments"])
    run_card_commitments = {
        **config_commitments,
        "target-cohort-projection.json": "sha256:" + "a" * 64,
    }
    cli._require_zero_cost_successor_commitment_keysets(
        config_commitments=config_commitments,
        run_card_commitments=run_card_commitments,
    )

    config_commitments["uncommitted.json"] = "sha256:" + "b" * 64
    run_card_commitments["uncommitted.json"] = "sha256:" + "b" * 64
    with pytest.raises(cli.CommandError, match="commitment keyset differs"):
        cli._require_zero_cost_successor_commitment_keysets(
            config_commitments=config_commitments,
            run_card_commitments=run_card_commitments,
        )


def test_rejects_forged_ranked_active_selection() -> None:
    fixture = _fixture()
    fixture.active[0] = _base_selection("forged-case")
    fixture.refresh()
    fixture.kwargs["authenticated_ranked_result"] = json.loads(
        ranked_reserve_result_bytes(fixture.ranked_result)
    )

    with pytest.raises(ZeroCostSuccessorError, match="97 retained"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_self_consistent_result_without_authoritative_disposition() -> None:
    fixture = _fixture()
    authenticated = fixture.kwargs["authenticated_ranked_result"]
    authenticated["terminal_disposition"]["residual_failure_pairs"][0][
        "candidate_id"
    ] = "case-099"

    with pytest.raises(ZeroCostSuccessorError, match="authenticated ranked-reserve"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_self_consistent_forged_financial_and_budget_state() -> None:
    fixture = _fixture()
    forged_budget = canonical_json_bytes({"forged": "budget authority"})
    fixture.ranked_result.update(
        {
            "committed_spend_usd": "0.00",
            "reserved_replacement_spend_usd": "0.00",
            "remaining_headroom_usd": "567.30",
            "replacement_budget_plan_sha256": _sha(forged_budget),
        }
    )
    fixture.kwargs["replacement_budget_plan_bytes"] = forged_budget
    fixture.kwargs["ranked_result_bytes"] = ranked_reserve_result_bytes(
        fixture.ranked_result
    )

    with pytest.raises(ZeroCostSuccessorError, match="authenticated ranked-reserve"):
        project_zero_cost_successor(**fixture.kwargs)


def test_selects_earlier_candidate_when_every_document_is_cleared() -> None:
    fixture = _fixture()
    for row in fixture.clearance:
        if row["candidate_id"] == "70525291":
            row["status"] = "cleared"
    fixture.refresh()

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert successor.config["selected_zero_cost_candidate_id"] == "70525291"


def test_rejects_positive_restriction_on_selected_candidate() -> None:
    fixture = _fixture()
    row = next(row for row in fixture.restrictions if row["candidate_id"] == "71677178")
    row["is_sealed"] = True
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match="positive restriction"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_partial_candidate_document_coverage() -> None:
    fixture = _fixture()
    fixture.manifest.pop()
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match="document coverage"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_purchased_zero_cost_candidate() -> None:
    fixture = _fixture()
    for row in [*fixture.manifest, *fixture.clearance]:
        if row["candidate_id"] == "71677178":
            row["free_or_purchased"] = "purchased"
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match="not free"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_unsupported_manifest_phase_on_inherited_case() -> None:
    fixture = _fixture()
    row = next(row for row in fixture.manifest if row["candidate_id"] == "case-010")
    row["free_or_purchased"] = "unknown"
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match="unsupported free_or_purchased"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_document_omitted_from_active_selection() -> None:
    fixture = _fixture()
    fixture.active[0]["documents"].pop()
    fixture.refresh()
    fixture.kwargs["authenticated_ranked_result"] = json.loads(
        canonical_json_bytes(fixture.ranked_result)
    )

    with pytest.raises(ZeroCostSuccessorError, match="document coverage differs"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_changed_hard_cap() -> None:
    fixture = _fixture()
    fixture.ranked_result["hard_cap_usd"] = "567.31"
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match="hard cap"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_model_visible_decision() -> None:
    fixture = _fixture()
    candidate = next(
        row
        for row in fixture.kwargs["source_pool"]
        if row["candidate_id"] == "71677178"
    )
    decision = next(
        row for row in candidate["documents"] if row["document_role"] == "decision"
    )
    decision["model_visible"] = True

    with pytest.raises(ZeroCostSuccessorError, match="model-visible"):
        project_zero_cost_successor(**fixture.kwargs)


def test_cli_publishes_standard_target_cohort_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture()
    target_root = tmp_path / "target"
    target_root.mkdir()
    summary_path = target_root / "target-cohort-projection.json"
    original_path = target_root / "target-cohort-selection.jsonl"
    reserve_path = target_root / "target-cohort-ranked-reserve.jsonl"
    original_exclusions_path = target_root / "target-cohort-exclusions.jsonl"
    source_path = tmp_path / "public-packet-selection-reconciled.jsonl"
    projection = fixture.kwargs["target_projection"]
    projection["input_commitments"] = {
        str(source_path): _sha(_jsonl(fixture.kwargs["source_pool"]))
    }
    original_bytes = _jsonl(fixture.kwargs["original_selection"])
    reserve_bytes = _jsonl(fixture.kwargs["ranked_reserve"])
    source_bytes = _jsonl(fixture.kwargs["source_pool"])
    for path, payload in (
        (summary_path, canonical_json_bytes(projection)),
        (original_path, original_bytes),
        (reserve_path, reserve_bytes),
        (original_exclusions_path, b""),
        (source_path, source_bytes),
    ):
        path.write_bytes(payload)
    verified_bytes = {
        os.path.abspath(summary_path): summary_path.read_bytes(),
        os.path.abspath(original_path): original_bytes,
        os.path.abspath(reserve_path): reserve_bytes,
        os.path.abspath(original_exclusions_path): b"",
        os.path.abspath(source_path): source_bytes,
    }
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "summary": projection,
            "summary_path": summary_path,
            "selection_path": original_path,
            "verified_artifact_bytes": verified_bytes,
        },
    )
    monkeypatch.setattr(
        cli, "_verify_authenticated_clearance_run_card", lambda **_kwargs: ()
    )
    monkeypatch.setattr(
        cli,
        "_authenticate_ranked_reserve_precursor",
        lambda **_kwargs: fixture.kwargs["authenticated_ranked_result"],
    )
    inputs = {
        "ranked-reserve-result.json": fixture.kwargs["ranked_result_bytes"],
        "active-selection.jsonl": fixture.kwargs["active_selection_bytes"],
        "replacement-selection.jsonl": fixture.kwargs["replacement_selection_bytes"],
        "successor-exclusions.jsonl": fixture.kwargs["successor_exclusions_bytes"],
        "replacement-budget.json": fixture.kwargs["replacement_budget_plan_bytes"],
        "disclosure-clearance.jsonl": fixture.kwargs["disclosure_clearance_bytes"],
        "case-relevance.jsonl": _jsonl(fixture.kwargs["case_relevance"]),
        "download-manifest.jsonl": _jsonl(fixture.kwargs["download_manifest"]),
        "restriction-evidence.jsonl": _jsonl(fixture.kwargs["restriction_evidence"]),
    }
    paths: dict[str, Path] = {}
    for name, payload in inputs.items():
        path = tmp_path / name
        path.write_bytes(payload)
        paths[name] = path
    clearance_card = {
        "source_commitments": {
            name: {
                "path": str(path),
                "sha256": _sha(path.read_bytes()),
            }
            for name, path in (
                ("case_relevance", paths["case-relevance.jsonl"]),
                ("download_manifest", paths["download-manifest.jsonl"]),
                ("restriction_evidence", paths["restriction-evidence.jsonl"]),
            )
        }
    }
    clearance_card_path = tmp_path / "clearance-card.json"
    clearance_card_path.write_bytes(canonical_json_bytes(clearance_card))
    controlled_private_root = tmp_path / "private"
    controlled_private_root.mkdir()
    precursor_paths = {
        name: tmp_path / name
        for name in (
            "purchase-policy.json",
            "purchase-ledger.sqlite3",
            "purchase-ledger-receipt.json",
            "purchase-result.json",
            "purchase-run-card.json",
            "screening-snapshot-manifest.json",
        )
    }
    for path in precursor_paths.values():
        path.write_bytes(b"{}\n")
    output_root = tmp_path / "successor"

    status = cli.main(
        [
            "acquisition",
            "project-zero-cost-successor",
            "--target-cohort-root",
            str(target_root),
            "--purchase-policy",
            str(precursor_paths["purchase-policy.json"]),
            "--controlled-private-root",
            str(controlled_private_root),
            "--purchase-ledger",
            str(precursor_paths["purchase-ledger.sqlite3"]),
            "--purchase-ledger-initialization-receipt",
            str(precursor_paths["purchase-ledger-receipt.json"]),
            "--purchase-result",
            str(precursor_paths["purchase-result.json"]),
            "--purchase-run-card",
            str(precursor_paths["purchase-run-card.json"]),
            "--screening-snapshot-manifest",
            str(precursor_paths["screening-snapshot-manifest.json"]),
            "--ranked-reserve-result",
            str(paths["ranked-reserve-result.json"]),
            "--active-selection",
            str(paths["active-selection.jsonl"]),
            "--replacement-selection",
            str(paths["replacement-selection.jsonl"]),
            "--successor-exclusions",
            str(paths["successor-exclusions.jsonl"]),
            "--replacement-budget-plan",
            str(paths["replacement-budget.json"]),
            "--disclosure-clearance",
            str(paths["disclosure-clearance.jsonl"]),
            "--disclosure-clearance-run-card",
            str(clearance_card_path),
            "--output-root",
            str(output_root),
        ]
    )

    assert status == 0
    expected = {
        "target-cohort-selection.jsonl",
        "target-cohort-projection.json",
        "case-relevance.jsonl",
        "document-downloads-merged.jsonl",
        "free-document-downloads.jsonl",
        "purchased-document-downloads.jsonl",
        "disclosure-clearance.jsonl",
        "restriction-evidence.jsonl",
        "core-filter-results.jsonl",
        "missing-core-budget-plan.json",
        "target-cohort-exclusions.jsonl",
        "target-cohort-ranked-reserve.jsonl",
        "run-cards/project-target-cohort.json",
    }
    assert {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    } == expected
    selection = output_root / "target-cohort-selection.jsonl"
    assert len(selection.read_text().splitlines()) == 100
    assert json.loads(selection.read_text().splitlines()[-1])["candidate_id"] == (
        "71677178"
    )
    verified = cli._verify_materializer_projection(
        target_root=output_root,
        free_clearance_path=output_root / "disclosure-clearance.jsonl",
        preparation_summary_path=tmp_path / "unused-preparation-summary.json",
        preparation_config_path=tmp_path / "unused-preparation-config.json",
        snapshot_manifest_path=tmp_path / "unused-snapshot.json",
        expected_target_count=100,
    )
    assert len(verified["selection_records"]) == 100
    assert verified["summary"]["schema_version"] == CONFIG_SCHEMA_VERSION

    missing_path = output_root / "case-relevance.jsonl"
    missing_payload = missing_path.read_bytes()
    missing_path.unlink()
    with pytest.raises(
        cli.CommandError,
        match=r"zero-cost successor output case-relevance\.jsonl must be",
    ):
        cli._verify_materializer_projection(
            target_root=output_root,
            free_clearance_path=output_root / "disclosure-clearance.jsonl",
            preparation_summary_path=tmp_path / "unused-preparation-summary.json",
            preparation_config_path=tmp_path / "unused-preparation-config.json",
            snapshot_manifest_path=tmp_path / "unused-snapshot.json",
            expected_target_count=100,
        )
    assert not missing_path.exists()
    missing_path.write_bytes(missing_payload)

    unexpected_path = output_root / "uncommitted-evidence.json"
    unexpected_path.write_text("{}\n")
    with pytest.raises(cli.CommandError, match="unexpected files"):
        cli._verify_materializer_projection(
            target_root=output_root,
            free_clearance_path=output_root / "disclosure-clearance.jsonl",
            preparation_summary_path=tmp_path / "unused-preparation-summary.json",
            preparation_config_path=tmp_path / "unused-preparation-config.json",
            snapshot_manifest_path=tmp_path / "unused-snapshot.json",
            expected_target_count=100,
        )
    unexpected_path.unlink()

    run_card_path = output_root / "run-cards/project-target-cohort.json"
    run_card = json.loads(run_card_path.read_bytes())
    run_card["unexpected_authority"] = True
    run_card_path.write_bytes(canonical_json_bytes(run_card))
    with pytest.raises(cli.CommandError, match="invalid completed"):
        cli._verify_materializer_projection(
            target_root=output_root,
            free_clearance_path=output_root / "disclosure-clearance.jsonl",
            preparation_summary_path=tmp_path / "unused-preparation-summary.json",
            preparation_config_path=tmp_path / "unused-preparation-config.json",
            snapshot_manifest_path=tmp_path / "unused-snapshot.json",
            expected_target_count=100,
        )


def _base_selection(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "nysd",
        "decision_date": "2026-07-01",
        "documents": [
            {
                "candidate_id": candidate_id,
                "source_document_id": document["source_document_id"],
                "document_role": document["document_role"],
            }
            for document in _core_documents(candidate_id)
        ],
    }


def _zero_selection(candidate_id: str) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    for document in _zero_documents(candidate_id):
        role = document["document_role"]
        is_decision = role == "decision"
        documents.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document["source_document_id"],
                "document_role": role,
                "model_visible": not is_decision,
                "contains_target_outcome": is_decision,
                "is_predecision_material": not is_decision,
                "redaction_or_seal_status": "public",
                "is_sealed": False,
                "is_private": False,
            }
        )
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "nysd",
        "decision_date": "2026-07-01",
        "selected": True,
        "exclusion_reasons": [],
        "documents": documents,
    }


def _zero_documents(candidate_id: str) -> list[dict[str, Any]]:
    return [
        _relevance_document(candidate_id, "complaint", "complaint"),
        _relevance_document(candidate_id, "mtd", "motion_to_dismiss_memorandum"),
        _relevance_document(candidate_id, "decision", "decision"),
    ]


def _core_documents(candidate_id: str) -> list[dict[str, Any]]:
    return [
        _relevance_document(candidate_id, "complaint", "complaint"),
        _relevance_document(candidate_id, "mtd", "motion_to_dismiss_memorandum"),
    ]


def _relevance_document(candidate_id: str, suffix: str, role: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-{suffix}",
        "setup_runner_label": "core_mtd",
        "document_role": role,
        "availability_status": "available",
        "requires_paid_recovery": False,
        "redaction_or_seal_status": "public",
        "is_sealed": False,
        "is_private": False,
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
    }


def _manifest(candidate_id: str, document_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "local_path": f"{candidate_id}/{document_id}.pdf",
        "sha256": "a" * 64,
        "byte_count": 10,
        "free_or_purchased": "free",
    }


def _clearance(candidate_id: str, document_id: str, *, status: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "local_path": f"{candidate_id}/{document_id}.pdf",
        "sha256": "a" * 64,
        "byte_count": 10,
        "status": status,
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://cycle-1/free-clearance",
        "reviewed_at": "2026-08-05T00:00:00Z",
        "free_or_purchased": "free",
    }
    if status == "cleared" and candidate_id == "71677178":
        row.update(
            {
                "restriction_status": "unknown",
                "reviewer_id": "google:gemini-3.5-flash",
                "controlled_store_provenance": (
                    "private-store://disclosure/model-review"
                ),
                "reviewed_at": None,
                "clearance_basis": "authenticated_model_exception_review",
                "routing_plan_sha256": "f" * 64,
            }
        )
    return row


def _restriction(candidate_id: str, document_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "is_sealed": False,
        "is_private": False,
    }


def _disposition() -> dict[str, Any]:
    residual = [
        {"candidate_id": f"case-{index:03d}", "source_document_id": f"doc-{index}"}
        for index in range(3)
    ]
    retained = [
        {"candidate_id": f"case-{index:03d}", "source_document_id": f"doc-{index}"}
        for index in range(3, 7)
    ]
    terminal = sorted([*residual, *retained], key=lambda row: row["candidate_id"])
    return {
        "schema_version": "legalforecast.terminal_purchase_disposition.v1",
        "purchase_result_sha256": "sha256:" + "a" * 64,
        "purchase_run_card_sha256": "sha256:" + "b" * 64,
        "purchase_journal_state_sha256": "sha256:" + "3" * 64,
        "selection_payload_sha256": "sha256:" + "c" * 64,
        "snapshot_manifest_sha256": "sha256:" + "d" * 64,
        "terminal_candidate_count": 7,
        "terminal_failure_pair_count": 7,
        "terminal_failure_pairs": terminal,
        "docket_retained_candidate_count": 4,
        "docket_retained_failure_pair_count": 4,
        "docket_retained_failure_pairs": retained,
        "docket_decision_sources_sha256": "sha256:" + "e" * 64,
        "residual_candidate_count": 3,
        "residual_failure_pair_count": 3,
        "residual_failure_pairs": residual,
        "residual_terminal_exclusions_sha256": "sha256:" + "f" * 64,
        "partition_disjoint": True,
        "partition_exhaustive": True,
        "model_visible": False,
        "audit_only": True,
    }
