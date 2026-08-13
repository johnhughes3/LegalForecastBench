from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.case_dev_purchase import CaseDevPurchaseSnapshot
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes
from legalforecast.ingestion.ranked_reserve_replacement import (
    _mint_verified_ranked_reserve_post_purchase_replay,
    ranked_reserve_canonical_sha256,
    ranked_reserve_result_bytes,
)
from legalforecast.ingestion.zero_cost_successor import (
    CONFIG_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    ZeroCostSuccessorError,
    _mint_verified_post_purchase_ranked_result,
    normalize_successor_selection_counters,
    project_zero_cost_successor,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


def test_ranked_precursor_revalidation_reuses_authority_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(b"{}\n")
    ledger_path = tmp_path / "purchase-ledger.sqlite3"
    receipt_path = tmp_path / "purchase-ledger-receipt.json"
    purchase_result_path = tmp_path / "purchase-result.json"
    purchase_card_path = tmp_path / "purchase-run-card.json"
    snapshot_manifest_path = tmp_path / "screening-snapshot-manifest.json"
    raw_source_path = tmp_path / "screening-raw.html"
    for path in (
        ledger_path,
        receipt_path,
        purchase_result_path,
        purchase_card_path,
        snapshot_manifest_path,
    ):
        path.write_bytes(b"{}\n")
    raw_source_path.write_bytes(b"authenticated raw source")
    private_root = tmp_path / "private"
    private_root.mkdir()
    policy = SimpleNamespace(policy_sha256="a" * 64)
    terminal_disposition = {"status": "terminal"}
    descriptor = cli._MaterializerDocketDecisionAuthority(
        authority=cast(Any, object()),
        partition={"selected_document_count": 1},
        purchase_policy=cast(Any, policy),
        ledger_path=ledger_path.resolve(),
        controlled_private_root=private_root,
        initialization_receipt_path=receipt_path,
        purchase_budget_plan_path=tmp_path / "budget.json",
        source_snapshots={raw_source_path: raw_source_path.read_bytes()},
    )
    policy_reads = 0
    authority_initializations = 0
    journal_options: list[dict[str, object]] = []
    journals: list[object] = []
    final_replays = 0

    class _Journal:
        def __init__(self, _path: Path, **_kwargs: object) -> None:
            journal_options.append(dict(_kwargs))
            journals.append(self)

        def __enter__(self) -> _Journal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    original_read = cli.read_unique_regular_file

    def read_policy(path: Path) -> bytes:
        nonlocal policy_reads
        if path == policy_path:
            policy_reads += 1
        return original_read(path)

    def initialize_authority(
        **_kwargs: object,
    ) -> cli._MaterializerDocketDecisionAuthority:
        nonlocal authority_initializations
        authority_initializations += 1
        return descriptor

    def final_replay_in_open_journal(
        supplied: cli._MaterializerDocketDecisionAuthority,
        *,
        purchase_journal: object,
    ) -> tuple[object, tuple[Mapping[str, Any], ...]]:
        nonlocal final_replays
        final_replays += 1
        assert purchase_journal is journals[-1]
        cli._require_snapshot_unchanged(
            supplied.source_snapshots, label="ranked precursor test source"
        )
        return supplied.authority, ()

    monkeypatch.setattr(cli, "read_unique_regular_file", read_policy)
    monkeypatch.setattr(cli, "verify_case_dev_purchase_policy", lambda _raw: policy)
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", _Journal)
    monkeypatch.setattr(
        cli, "_verify_materializer_docket_decision_authority", initialize_authority
    )
    monkeypatch.setattr(
        cli,
        "verified_terminal_purchase_disposition_record",
        lambda *_args, **_kwargs: terminal_disposition,
    )
    monkeypatch.setattr(
        cli,
        "residual_terminal_exclusions_bytes",
        lambda *_args, **_kwargs: b"[]\n",
    )
    monkeypatch.setattr(
        cli, "plan_ranked_reserve_replacements", lambda **_kwargs: object()
    )

    ranked_result: dict[str, object] = {
        "purchase_policy_sha256": "sha256:" + policy.policy_sha256,
        "terminal_disposition": terminal_disposition,
    }
    expected_ranked_result = deepcopy(ranked_result)
    monkeypatch.setattr(
        cli,
        "bind_ranked_reserve_outputs",
        lambda *_args, **_kwargs: ranked_result,
    )
    monkeypatch.setattr(
        cli,
        "_replay_materialized_docket_decision_authority_in_open_journal",
        final_replay_in_open_journal,
    )
    monkeypatch.setattr(
        cli,
        "_replay_materialized_docket_decision_authority",
        lambda _descriptor: pytest.fail("revalidation reopened the purchase journal"),
    )

    kwargs = {
        "projection": {},
        "selection_payload": b'{"candidate_id":"case-1","documents":[]}\n',
        "reserve_payload": b"",
        "source_pool_payload": b"",
        "original_exclusions_payload": b"",
        "active_selection_payload": b"",
        "replacement_selection_payload": b"",
        "successor_exclusions_payload": b"",
        "replacement_budget_plan_payload": b"",
        "purchase_policy_path": policy_path,
        "controlled_private_root": private_root,
        "purchase_ledger_path": ledger_path,
        "purchase_ledger_initialization_receipt_path": receipt_path,
        "purchase_result_path": purchase_result_path,
        "purchase_run_card_path": purchase_card_path,
        "screening_snapshot_manifest_path": snapshot_manifest_path,
        "ranked_result": ranked_result,
    }

    authenticated = cli._authenticate_ranked_reserve_precursor(**kwargs)
    revalidated = cli._authenticate_ranked_reserve_precursor(
        **kwargs, _authenticated_precursor=authenticated
    )

    assert ranked_result == expected_ranked_result
    assert authenticated.result == expected_ranked_result
    assert revalidated.result == expected_ranked_result
    assert authority_initializations == 1
    assert policy_reads == 2
    assert [options["read_only"] for options in journal_options] == [True, True]
    assert all(options["policy"] is policy for options in journal_options)
    assert final_replays == 1

    policy_path.write_bytes(b'{"changed":true}\n')
    with pytest.raises(
        ZeroCostSuccessorError,
        match="purchase policy changed before publication",
    ):
        cli._authenticate_ranked_reserve_precursor(
            **kwargs, _authenticated_precursor=authenticated
        )

    policy_path.write_bytes(b"{}\n")
    raw_source_path.write_bytes(b"mutated source")
    with pytest.raises(cli.CommandError, match="ranked precursor test source changed"):
        cli._authenticate_ranked_reserve_precursor(
            **kwargs, _authenticated_precursor=authenticated
        )


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
        "terminal_exclusions_sha256": "sha256:"
        + str(disposition["residual_terminal_exclusions_sha256"]).removeprefix(
            "sha256:"
        ),
        "terminal_disposition": disposition,
        "terminal_disposition_sha256": ranked_reserve_canonical_sha256(disposition),
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
    assert (
        successor.config["source_commitments"]["screening_snapshot_manifest"]
        == "sha256:" + "d" * 64
    )


def test_normalizes_inherited_selection_counters_from_free_manifest() -> None:
    fixture = _fixture()
    for row in fixture.active:
        row.update(
            {
                "required_document_count": 2,
                "free_required_document_count": 0,
                "missing_required_document_count": 2,
            }
        )
    fixture.refresh()
    fixture.kwargs["authenticated_ranked_result"] = json.loads(
        fixture.kwargs["ranked_result_bytes"]
    )

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert {
        (
            row["required_document_count"],
            row["free_required_document_count"],
            row["missing_required_document_count"],
        )
        for row in successor.selection[:-1]
    } == {(2, 2, 0)}
    assert successor.selection[-1]["required_document_count"] == 3
    assert successor.selection[-1]["free_required_document_count"] == 3
    assert successor.selection[-1]["missing_required_document_count"] == 0


def test_reproduces_exact_100_counter_recovery_shift() -> None:
    selection: list[dict[str, Any]] = []
    required_documents: list[tuple[str, dict[str, Any]]] = []
    for case_index in range(100):
        candidate_id = f"case-{case_index:03d}"
        roles = ["complaint", "motion_to_dismiss_memorandum", "decision"]
        if case_index < 22:
            roles.append("opposition")
        documents: list[dict[str, Any]] = []
        for role_index, role in enumerate(roles):
            document = {
                "source_document_id": f"{candidate_id}-{role_index}",
                "document_role": role,
            }
            documents.append(document)
            required_documents.append((candidate_id, document))
        selection.append({"candidate_id": candidate_id, "documents": documents})
    notice = {
        "source_document_id": "case-000-notice",
        "document_role": "motion_to_dismiss_notice",
    }
    selection[0]["documents"].append(notice)

    free_required = required_documents[:142]
    free_keys = {
        (candidate_id, str(document["source_document_id"]))
        for candidate_id, document in free_required
    }
    manifest = [
        _manifest(candidate_id, str(document["source_document_id"]))
        for candidate_id, document in free_required
    ]
    manifest.append(_manifest("case-000", "case-000-notice"))
    for row in selection:
        candidate_id = str(row["candidate_id"])
        required_count = 0
        free_count = 0
        for document in row["documents"]:
            if document["document_role"] == "motion_to_dismiss_notice":
                continue
            required_count += 1
            key = (candidate_id, str(document["source_document_id"]))
            if key in free_keys:
                free_count += 1
            else:
                document["availability_status"] = "unavailable"
                document["requires_paid_recovery"] = True
        row["required_document_count"] = required_count
        row["free_required_document_count"] = free_count
        row["missing_required_document_count"] = required_count - free_count
    for case_index in range(10):
        stale_shift = 3 if case_index < 5 else 2
        row = selection[case_index]
        row["free_required_document_count"] -= stale_shift
        row["missing_required_document_count"] += stale_shift

    assert sum(row["required_document_count"] for row in selection) == 322
    assert sum(row["free_required_document_count"] for row in selection) == 117
    assert sum(row["missing_required_document_count"] for row in selection) == 205
    assert len(manifest) == 143

    normalized, totals = normalize_successor_selection_counters(
        selection,
        manifest,
        validate_stored=False,
    )

    assert totals.required_document_count == 322
    assert totals.free_required_document_count == 142
    assert totals.missing_required_document_count == 180
    assert totals.selected_document_count == 323
    assert totals.manifest_document_count == 143
    assert totals.free_manifest_document_count == 143
    assert sum(row["free_required_document_count"] for row in normalized) == 142
    assert sum(row["missing_required_document_count"] for row in normalized) == 180
    assert (
        sum(
            document["document_role"] == "decision"
            and document.get("availability_status") == "unavailable"
            for row in selection[-4:]
            for document in row["documents"]
        )
        == 4
    )
    with pytest.raises(ZeroCostSuccessorError, match="document counters differ"):
        normalize_successor_selection_counters(
            selection,
            manifest,
            validate_stored=True,
        )


def test_successor_counters_exclude_free_optional_notice() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": "complaint",
                    "document_role": "complaint",
                },
                {
                    "source_document_id": "notice",
                    "document_role": "motion_to_dismiss_notice",
                },
            ],
        }
    ]
    manifest = [
        _manifest("case-1", "complaint"),
        _manifest("case-1", "notice"),
    ]

    normalized, totals = normalize_successor_selection_counters(
        selection,
        manifest,
        validate_stored=False,
    )

    assert normalized[0]["required_document_count"] == 1
    assert normalized[0]["free_required_document_count"] == 1
    assert normalized[0]["missing_required_document_count"] == 0
    assert totals.required_document_count == 1
    assert totals.free_required_document_count == 1
    assert totals.missing_required_document_count == 0
    assert totals.selected_document_count == 2
    assert totals.manifest_document_count == 2
    assert totals.free_manifest_document_count == 2


def test_successor_counters_treat_unavailable_docket_decisions_as_required() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": f"decision-{index}",
                    "document_role": "decision",
                    "availability_status": "unavailable",
                    "requires_paid_recovery": True,
                }
                for index in range(4)
            ],
        }
    ]

    normalized, totals = normalize_successor_selection_counters(
        selection,
        (),
        validate_stored=False,
    )

    assert normalized[0]["required_document_count"] == 4
    assert normalized[0]["free_required_document_count"] == 0
    assert normalized[0]["missing_required_document_count"] == 4
    assert totals.required_document_count == 4
    assert totals.missing_required_document_count == 4


def test_successor_counter_verification_rejects_stored_drift() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "required_document_count": 1,
            "free_required_document_count": 0,
            "missing_required_document_count": 1,
            "documents": [
                {
                    "source_document_id": "complaint",
                    "document_role": "complaint",
                }
            ],
        }
    ]

    with pytest.raises(
        ZeroCostSuccessorError,
        match="successor selection document counters differ: case-1",
    ):
        normalize_successor_selection_counters(
            selection,
            [_manifest("case-1", "complaint")],
            validate_stored=True,
        )


def test_successor_counters_reject_duplicate_selected_document() -> None:
    document = {
        "source_document_id": "complaint",
        "document_role": "complaint",
    }
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [document, dict(document)],
        }
    ]

    with pytest.raises(ZeroCostSuccessorError, match="repeats successor counter"):
        normalize_successor_selection_counters(
            selection,
            [_manifest("case-1", "complaint")],
            validate_stored=False,
        )


def test_successor_counters_reject_manifest_key_outside_selection() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": "complaint",
                    "document_role": "complaint",
                }
            ],
        }
    ]

    with pytest.raises(ZeroCostSuccessorError, match="absent from selection"):
        normalize_successor_selection_counters(
            selection,
            [
                _manifest("case-1", "complaint"),
                _manifest("case-2", "other"),
            ],
            validate_stored=False,
        )


def test_successor_counters_reject_unproven_unacquired_partition() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": "decision",
                    "document_role": "decision",
                }
            ],
        }
    ]

    with pytest.raises(ZeroCostSuccessorError, match="authenticated paid-recovery gap"):
        normalize_successor_selection_counters(
            selection,
            (),
            validate_stored=False,
        )


def test_successor_counters_reject_free_document_marked_unavailable() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": "complaint",
                    "document_role": "complaint",
                    "availability_status": "unavailable",
                    "requires_paid_recovery": True,
                }
            ],
        }
    ]

    with pytest.raises(
        ZeroCostSuccessorError,
        match="free successor counter document is marked unavailable",
    ):
        normalize_successor_selection_counters(
            selection,
            [_manifest("case-1", "complaint")],
            validate_stored=False,
        )


def test_successor_counters_reject_unknown_document_role() -> None:
    selection = [
        {
            "candidate_id": "case-1",
            "documents": [
                {
                    "source_document_id": "other",
                    "document_role": "other",
                }
            ],
        }
    ]

    with pytest.raises(ZeroCostSuccessorError, match=r"unsupported.*role"):
        normalize_successor_selection_counters(
            selection,
            [_manifest("case-1", "other")],
            validate_stored=False,
        )


def test_accepts_parent_scoped_case_relevance_documents() -> None:
    fixture = _fixture()
    for record in fixture.kwargs["case_relevance"]:
        for document in record["documents"]:
            document.pop("candidate_id", None)

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert successor.state["selected_case_count"] == 100


@pytest.mark.parametrize("nested_candidate_id", ["", None])
def test_rejects_invalid_explicit_nested_candidate_id(
    nested_candidate_id: object,
) -> None:
    fixture = _fixture()
    selected_relevance = next(
        record
        for record in fixture.kwargs["case_relevance"]
        if record["candidate_id"] == "case-003"
    )
    selected_relevance["documents"][0]["candidate_id"] = nested_candidate_id

    with pytest.raises(ZeroCostSuccessorError, match="non-empty string"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_compact_ranked_result_bytes() -> None:
    fixture = _fixture()
    fixture.kwargs["ranked_result_bytes"] = canonical_json_bytes(fixture.ranked_result)

    with pytest.raises(ZeroCostSuccessorError, match="not canonical JSON"):
        project_zero_cost_successor(**fixture.kwargs)


def test_ranked_result_serializer_has_explicit_ascii_contract() -> None:
    payload = ranked_reserve_result_bytes({"note": "résumé"})

    assert payload == b'{\n  "note": "r\\u00e9sum\\u00e9"\n}\n'


def _upgrade_fixture_to_current_replay(fixture: Fixture) -> None:
    fixture.ranked_result["tranche_event_record_sha256s"] = fixture.ranked_result[
        "replacement_event_record_sha256s"
    ]
    precursor_bytes = ranked_reserve_result_bytes(fixture.ranked_result)
    historical_state = str(fixture.ranked_result["purchase_journal_state_sha256"])
    fixture.ranked_result["schema_version"] = (
        "legalforecast.ranked_reserve_replacement_result.v3"
    )
    fixture.ranked_result["purchase_journal_state_sha256"] = "sha256:" + "6" * 64
    disposition = dict(fixture.ranked_result["terminal_disposition"])
    disposition["purchase_journal_state_sha256"] = "sha256:" + "6" * 64
    fixture.ranked_result["terminal_disposition"] = disposition
    fixture.ranked_result["terminal_disposition_sha256"] = (
        ranked_reserve_canonical_sha256(disposition)
    )
    fixture.ranked_result["authenticated_legacy_replay"] = {
        "schema_version": "legalforecast.ranked_reserve_legacy_event_replay.v1",
        "precursor_result": json.loads(precursor_bytes),
        "precursor_result_sha256": _sha(precursor_bytes),
        "precursor_active_selection_sha256": fixture.ranked_result[
            "active_selection_sha256"
        ],
        "precursor_replacement_selection_sha256": fixture.ranked_result[
            "replacement_selection_sha256"
        ],
        "precursor_successor_exclusions_sha256": fixture.ranked_result[
            "successor_exclusions_sha256"
        ],
        "precursor_replacement_budget_plan_sha256": fixture.ranked_result[
            "replacement_budget_plan_sha256"
        ],
        "historical_purchase_journal_state_sha256": historical_state,
        "historical_terminal_evidence_sha256": "sha256:" + "7" * 64,
        "current_terminal_evidence_sha256": "sha256:" + "8" * 64,
        "authenticated_event_record_sha256s": fixture.ranked_result[
            "replacement_event_record_sha256s"
        ],
        "historical_state_substitution_only": True,
    }
    fixture.kwargs["authenticated_ranked_result"] = fixture.ranked_result
    fixture.refresh()


def _upgrade_fixture_to_post_purchase_replay(fixture: Fixture) -> None:
    _upgrade_fixture_to_current_replay(fixture)
    prior_result = json.loads(ranked_reserve_result_bytes(fixture.ranked_result))
    baseline_state = str(prior_result["purchase_journal_state_sha256"])
    baseline_committed = str(prior_result["committed_spend_usd"])
    current_state = "sha256:" + "a" * 64
    current_committed = f"{Decimal(baseline_committed) + Decimal('1.00'):.2f}"
    fixture.ranked_result["schema_version"] = (
        "legalforecast.ranked_reserve_replacement_result.v4"
    )
    fixture.ranked_result["purchase_journal_state_sha256"] = current_state
    fixture.ranked_result["committed_spend_usd"] = current_committed
    disposition = dict(fixture.ranked_result["terminal_disposition"])
    disposition["purchase_journal_state_sha256"] = current_state
    fixture.ranked_result["terminal_disposition"] = disposition
    fixture.ranked_result["terminal_disposition_sha256"] = (
        ranked_reserve_canonical_sha256(disposition)
    )
    fixture.ranked_result["authenticated_post_purchase_replay"] = {
        "schema_version": "legalforecast.ranked_reserve_post_purchase_replay.v1",
        "prior_result": prior_result,
        "prior_result_sha256": _sha(ranked_reserve_result_bytes(prior_result)),
        "replacement_purchase_authority_sha256": "b" * 64,
        "baseline_purchase_journal_state_sha256": baseline_state,
        "baseline_committed_spend_usd": baseline_committed,
        "baseline_operation_record_sha256s": ["c" * 64],
        "current_purchase_journal_state_sha256": current_state,
        "current_committed_spend_usd": current_committed,
        "successor_operation_record_sha256s": ["d" * 64],
    }
    fixture.kwargs["authenticated_ranked_result"] = fixture.ranked_result
    fixture.refresh()


def _verified_v4_transition(
    fixture: Fixture, *, live_state_sha256: str | None = None
) -> object:
    proof = fixture.ranked_result["authenticated_post_purchase_replay"]
    assert isinstance(proof, dict)
    prior_result = proof["prior_result"]
    assert isinstance(prior_result, dict)
    legacy_replay = prior_result["authenticated_legacy_replay"]
    assert isinstance(legacy_replay, dict)
    precursor = legacy_replay["precursor_result"]
    assert isinstance(precursor, dict)
    return _mint_verified_ranked_reserve_post_purchase_replay(
        prior_result=prior_result,
        prior_result_sha256=str(proof["prior_result_sha256"]),
        authenticated_legacy_replay=legacy_replay,
        precursor_committed_spend=Decimal(str(precursor["committed_spend_usd"])),
        precursor_reserved_spend=Decimal(
            str(precursor["reserved_replacement_spend_usd"])
        ),
        precursor_remaining_headroom=Decimal(str(precursor["remaining_headroom_usd"])),
        baseline_snapshot=CaseDevPurchaseSnapshot(
            operations=(),
            committed_amount_usd=str(proof["baseline_committed_spend_usd"]),
            purchase_state_sha256=str(
                proof["baseline_purchase_journal_state_sha256"]
            ).removeprefix("sha256:"),
        ),
        current_snapshot=CaseDevPurchaseSnapshot(
            operations=(),
            committed_amount_usd=str(proof["current_committed_spend_usd"]),
            purchase_state_sha256=str(
                proof["current_purchase_journal_state_sha256"]
            ).removeprefix("sha256:"),
        ),
        live_snapshot=(
            CaseDevPurchaseSnapshot(
                operations=(),
                committed_amount_usd=str(proof["current_committed_spend_usd"]),
                purchase_state_sha256=live_state_sha256.removeprefix("sha256:"),
            )
            if live_state_sha256 is not None
            else None
        ),
        replacement_purchase_authority_sha256=str(
            proof["replacement_purchase_authority_sha256"]
        ),
        baseline_operation_record_sha256s=list(
            proof["baseline_operation_record_sha256s"]
        ),
        successor_operation_record_sha256s=list(
            proof["successor_operation_record_sha256s"]
        ),
    )


def test_current_v3_result_accepts_closed_legacy_replay_proof() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_current_replay(fixture)

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert successor.state["selected_case_count"] == 100


def test_post_purchase_v4_accepts_live_terminal_disposition_state() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_post_purchase_replay(fixture)
    live_state = "sha256:" + "e" * 64
    disposition = dict(fixture.ranked_result["terminal_disposition"])
    disposition["purchase_journal_state_sha256"] = live_state
    fixture.ranked_result["terminal_disposition"] = disposition
    fixture.ranked_result["terminal_disposition_sha256"] = (
        ranked_reserve_canonical_sha256(disposition)
    )
    transition = _verified_v4_transition(fixture, live_state_sha256=live_state)
    fixture.kwargs["authenticated_ranked_result"] = (
        _mint_verified_post_purchase_ranked_result(fixture.ranked_result, transition)
    )
    fixture.refresh()

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert successor.state["selected_case_count"] == 100


def test_post_purchase_v4_rejects_non_live_terminal_disposition_state() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_post_purchase_replay(fixture)
    transition = _verified_v4_transition(
        fixture, live_state_sha256="sha256:" + "e" * 64
    )
    fixture.kwargs["authenticated_ranked_result"] = (
        _mint_verified_post_purchase_ranked_result(fixture.ranked_result, transition)
    )

    with pytest.raises(
        ZeroCostSuccessorError, match="terminal disposition commitment mismatch"
    ):
        project_zero_cost_successor(**fixture.kwargs)


def test_post_purchase_v4_result_rejects_self_authenticated_forged_mapping() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_post_purchase_replay(fixture)

    with pytest.raises(
        ZeroCostSuccessorError,
        match="lacks full authenticated producer replay",
    ):
        project_zero_cost_successor(**fixture.kwargs)


def test_post_purchase_v4_result_requires_exact_full_result_capability() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_post_purchase_replay(fixture)
    full_capability = _mint_verified_post_purchase_ranked_result(
        fixture.ranked_result,
        cast(Any, _verified_v4_transition(fixture)),
    )
    fixture.kwargs["authenticated_ranked_result"] = full_capability

    successor = project_zero_cost_successor(**fixture.kwargs)
    assert successor.state["selected_case_count"] == 100

    original_reserved = fixture.ranked_result["reserved_replacement_spend_usd"]
    original_headroom = fixture.ranked_result["remaining_headroom_usd"]
    fixture.ranked_result["reserved_replacement_spend_usd"] = "999.00"
    fixture.ranked_result["remaining_headroom_usd"] = "0.00"
    fixture.refresh()
    with pytest.raises(
        ZeroCostSuccessorError,
        match="differs from authenticated ranked-reserve replay",
    ):
        project_zero_cost_successor(**fixture.kwargs)

    fixture.ranked_result["reserved_replacement_spend_usd"] = original_reserved
    fixture.ranked_result["remaining_headroom_usd"] = original_headroom
    disposition = dict(fixture.ranked_result["terminal_disposition"])
    disposition["purchase_result_sha256"] = "sha256:" + "9" * 64
    fixture.ranked_result["terminal_disposition"] = disposition
    fixture.ranked_result["terminal_disposition_sha256"] = (
        ranked_reserve_canonical_sha256(disposition)
    )
    fixture.refresh()
    with pytest.raises(
        ZeroCostSuccessorError,
        match="differs from authenticated ranked-reserve replay",
    ):
        project_zero_cost_successor(**fixture.kwargs)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("prior_result_sha256", "sha256:" + "e" * 64, "prior ranked result"),
        (
            "baseline_purchase_journal_state_sha256",
            "sha256:" + "e" * 64,
            "prior ranked result",
        ),
        (
            "current_purchase_journal_state_sha256",
            "sha256:" + "e" * 64,
            "current output commitments",
        ),
        ("current_committed_spend_usd", "999.00", "current output commitments"),
        (
            "successor_operation_record_sha256s",
            ["c" * 64],
            "operation partition",
        ),
    ],
)
def test_post_purchase_v4_result_rejects_transition_tampering(
    field: str,
    value: object,
    message: str,
) -> None:
    fixture = _fixture()
    _upgrade_fixture_to_post_purchase_replay(fixture)
    proof = fixture.ranked_result["authenticated_post_purchase_replay"]
    assert isinstance(proof, dict)
    proof[field] = value
    fixture.kwargs["authenticated_ranked_result"] = fixture.ranked_result
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match=message):
        project_zero_cost_successor(**fixture.kwargs)


def test_current_v3_result_rejects_drifted_legacy_output_commitment() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_current_replay(fixture)
    proof = fixture.ranked_result["authenticated_legacy_replay"]
    assert isinstance(proof, dict)
    proof["precursor_active_selection_sha256"] = "sha256:" + "9" * 64
    fixture.refresh()

    with pytest.raises(
        ZeroCostSuccessorError,
        match="authenticated legacy replay differs from its canonical precursor",
    ):
        project_zero_cost_successor(**fixture.kwargs)


def test_current_v3_result_rejects_drifted_legacy_event_sequence() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_current_replay(fixture)
    proof = fixture.ranked_result["authenticated_legacy_replay"]
    assert isinstance(proof, dict)
    proof["authenticated_event_record_sha256s"] = ["sha256:" + "9" * 64]
    fixture.refresh()

    with pytest.raises(
        ZeroCostSuccessorError,
        match="differs from its canonical precursor",
    ):
        project_zero_cost_successor(**fixture.kwargs)


def test_current_v3_result_rejects_drifted_current_tranche_event_sequence() -> None:
    fixture = _fixture()
    _upgrade_fixture_to_current_replay(fixture)
    fixture.ranked_result["tranche_event_record_sha256s"] = ["sha256:" + "9" * 64]
    fixture.refresh()

    with pytest.raises(
        ZeroCostSuccessorError,
        match="authenticated legacy replay differs from current output commitments",
    ):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_newline_terminated_terminal_disposition_digest() -> None:
    fixture = _fixture()
    fixture.ranked_result["terminal_disposition_sha256"] = _sha(
        canonical_json_bytes(fixture.ranked_result["terminal_disposition"])
    )
    fixture.refresh()

    with pytest.raises(
        ZeroCostSuccessorError, match="terminal disposition commitment mismatch"
    ):
        project_zero_cost_successor(**fixture.kwargs)


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
    fixture.kwargs["authenticated_ranked_result"] = json.loads(
        fixture.kwargs["ranked_result_bytes"]
    )

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


def test_accepts_unacquired_paid_recovery_gap() -> None:
    fixture = _fixture()
    selected = next(row for row in fixture.active if row["candidate_id"] == "case-010")
    relevance = next(
        row
        for row in fixture.kwargs["case_relevance"]
        if row["candidate_id"] == "case-010"
    )
    document_id = str(selected["documents"][0]["source_document_id"])
    for document in (selected["documents"][0], relevance["documents"][0]):
        document["availability_status"] = "unavailable"
        document["requires_paid_recovery"] = True
    fixture.manifest[:] = [
        row
        for row in fixture.manifest
        if (row["candidate_id"], row["source_document_id"]) != ("case-010", document_id)
    ]
    fixture.clearance[:] = [
        row
        for row in fixture.clearance
        if (row["candidate_id"], row["source_document_id"]) != ("case-010", document_id)
    ]
    fixture.restrictions[:] = [
        row
        for row in fixture.restrictions
        if (row["candidate_id"], row["source_document_id"]) != ("case-010", document_id)
    ]
    fixture.refresh()
    fixture.kwargs["authenticated_ranked_result"] = json.loads(
        fixture.kwargs["ranked_result_bytes"]
    )

    successor = project_zero_cost_successor(**fixture.kwargs)

    assert ("case-010", document_id) not in {
        (row["candidate_id"], row["source_document_id"])
        for row in successor.download_manifest
    }


def test_rejects_unacquired_free_document() -> None:
    fixture = _fixture()
    manifest_row = next(
        row for row in fixture.manifest if row["candidate_id"] == "case-010"
    )
    key = (manifest_row["candidate_id"], manifest_row["source_document_id"])
    fixture.manifest[:] = [
        row
        for row in fixture.manifest
        if (row["candidate_id"], row["source_document_id"]) != key
    ]
    fixture.clearance[:] = [
        row
        for row in fixture.clearance
        if (row["candidate_id"], row["source_document_id"]) != key
    ]
    fixture.restrictions[:] = [
        row
        for row in fixture.restrictions
        if (row["candidate_id"], row["source_document_id"]) != key
    ]
    fixture.refresh()

    with pytest.raises(ZeroCostSuccessorError, match="not a paid-recovery gap"):
        project_zero_cost_successor(**fixture.kwargs)


def test_rejects_paid_gap_marker_missing_from_case_relevance() -> None:
    fixture = _fixture()
    selected = next(row for row in fixture.active if row["candidate_id"] == "case-010")
    document_id = str(selected["documents"][0]["source_document_id"])
    selected["documents"][0]["availability_status"] = "unavailable"
    selected["documents"][0]["requires_paid_recovery"] = True
    key = ("case-010", document_id)
    fixture.manifest[:] = [
        row
        for row in fixture.manifest
        if (row["candidate_id"], row["source_document_id"]) != key
    ]
    fixture.clearance[:] = [
        row
        for row in fixture.clearance
        if (row["candidate_id"], row["source_document_id"]) != key
    ]
    fixture.restrictions[:] = [
        row
        for row in fixture.restrictions
        if (row["candidate_id"], row["source_document_id"]) != key
    ]
    fixture.refresh()
    fixture.kwargs["authenticated_ranked_result"] = json.loads(
        fixture.kwargs["ranked_result_bytes"]
    )

    with pytest.raises(ZeroCostSuccessorError, match="not a paid-recovery gap"):
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


def test_counts_inherited_purchased_document_as_non_free_required() -> None:
    fixture = _fixture()
    source_document_id = next(
        str(row["source_document_id"])
        for row in fixture.manifest
        if row["candidate_id"] == "case-010"
    )
    for row in [*fixture.manifest, *fixture.clearance]:
        if (
            row["candidate_id"] == "case-010"
            and row["source_document_id"] == source_document_id
        ):
            row["free_or_purchased"] = "purchased"
    fixture.refresh()

    successor = project_zero_cost_successor(**fixture.kwargs)

    selected = next(
        row for row in successor.selection if row["candidate_id"] == "case-010"
    )
    assert selected["required_document_count"] == 2
    assert selected["free_required_document_count"] == 1
    assert selected["missing_required_document_count"] == 1


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


@pytest.mark.parametrize("post_purchase_v4", [False, True])
def test_cli_publishes_standard_target_cohort_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    post_purchase_v4: bool,
) -> None:
    fixture = _fixture()
    if post_purchase_v4:
        _upgrade_fixture_to_post_purchase_replay(fixture)
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
    verified_token: object = object()
    authentication_tokens: list[object | None] = []
    authentication_contexts: list[object | None] = []
    initial_precursor: SimpleNamespace | None = None

    def authenticate_precursor(**kwargs: object) -> SimpleNamespace:
        nonlocal initial_precursor
        token = kwargs.get("verified_post_purchase_replay")
        authentication_tokens.append(token)
        authentication_contexts.append(kwargs.get("_authenticated_precursor"))
        assert token is (verified_token if post_purchase_v4 else None)
        ranked = fixture.kwargs["authenticated_ranked_result"]
        result: Mapping[str, object]
        if post_purchase_v4:
            result = cast(
                dict[str, Any],
                _mint_verified_post_purchase_ranked_result(
                    ranked, cast(Any, verified_token)
                ),
            )
        else:
            result = ranked
        if initial_precursor is None:
            initial_precursor = SimpleNamespace(result=result)
            return initial_precursor
        return SimpleNamespace(result=result)

    monkeypatch.setattr(
        cli, "_authenticate_ranked_reserve_precursor", authenticate_precursor
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
    post_purchase_arguments: list[str] = []
    authority_verifications: list[dict[str, object]] = []
    resolver_factory_paths: list[tuple[Path, ...]] = []
    if post_purchase_v4:
        proof = fixture.ranked_result["authenticated_post_purchase_replay"]
        assert isinstance(proof, dict)
        verified_token = _verified_v4_transition(fixture)
        prior_result_path = tmp_path / "prior-ranked-result.json"
        prior_result_path.write_bytes(
            ranked_reserve_result_bytes(proof["prior_result"])
        )
        prior_selection_path = tmp_path / "prior-replacement-selection.jsonl"
        prior_selection_path.write_bytes(fixture.kwargs["replacement_selection_bytes"])
        prior_budget_path = tmp_path / "prior-replacement-budget-plan.json"
        prior_budget_path.write_bytes(fixture.kwargs["replacement_budget_plan_bytes"])
        authority_path = tmp_path / "replacement-purchase-authority.json"
        authority_path.write_bytes(b"{}\n")
        replacement_private_root = tmp_path / "replacement-private"
        replacement_private_root.mkdir()
        cohort_policy_path = tmp_path / "cohort-policy.json"
        cohort_policy_path.write_bytes(b"{}\n")
        resolver_card_paths = (
            tmp_path / "newer-resolver-card.json",
            tmp_path / "older-resolver-card.json",
        )
        for path in resolver_card_paths:
            path.write_bytes(b"{}\n")
        verified_policy = object()
        monkeypatch.setattr(
            cli, "verify_case_dev_purchase_policy", lambda _artifact: verified_policy
        )

        def require_verified_policy(
            policy: object, *, controlled_private_root: Path
        ) -> None:
            assert policy is verified_policy
            assert controlled_private_root == tmp_path / "private"

        monkeypatch.setattr(
            cli,
            "require_approved_case_dev_purchase_policy",
            require_verified_policy,
        )

        def issue_resolved_transition_factory(**kwargs: object) -> object:
            assert (
                kwargs["purchase_ledger_path"]
                == precursor_paths["purchase-ledger.sqlite3"]
            )
            assert kwargs["controlled_private_root"] == controlled_private_root
            assert kwargs["policy"] is verified_policy
            paths = cast(tuple[Path, ...], kwargs["run_card_paths"])
            resolver_factory_paths.append(paths)
            assert paths == resolver_card_paths
            return object

        monkeypatch.setattr(
            cli,
            "_issue_resolved_transition_capability_factory",
            issue_resolved_transition_factory,
        )

        def verify_post_purchase(**kwargs: object) -> object:
            authority_verifications.append(kwargs)
            assert kwargs["prior_result_bytes"] == prior_result_path.read_bytes()
            assert kwargs["selection_bytes"] == prior_selection_path.read_bytes()
            assert kwargs["budget_plan_bytes"] == prior_budget_path.read_bytes()
            assert kwargs["controlled_private_root"] == replacement_private_root
            assert (
                kwargs["_verified_resolved_authority_capability"]
                is not kwargs["_verified_resolved_snapshot_capability"]
            )
            return verified_token

        monkeypatch.setattr(
            cli, "verify_ranked_reserve_post_purchase_replay", verify_post_purchase
        )
        post_purchase_arguments = [
            "--prior-ranked-result",
            str(prior_result_path),
            "--prior-replacement-selection",
            str(prior_selection_path),
            "--prior-replacement-budget-plan",
            str(prior_budget_path),
            "--replacement-purchase-authority",
            str(authority_path),
            "--replacement-controlled-private-root",
            str(replacement_private_root),
            "--cohort-policy",
            str(cohort_policy_path),
            "--resolved-post-recovery-run-card",
            str(resolver_card_paths[0]),
            "--resolved-post-recovery-run-card",
            str(resolver_card_paths[1]),
        ]

    command = [
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
        *post_purchase_arguments,
    ]
    status = cli.main(command)

    assert status == 0
    assert len(authority_verifications) == (2 if post_purchase_v4 else 0)
    assert len(resolver_factory_paths) == (1 if post_purchase_v4 else 0)
    assert authentication_tokens == [
        verified_token if post_purchase_v4 else None,
        verified_token if post_purchase_v4 else None,
    ]
    assert authentication_contexts == [None, initial_precursor]
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
    if post_purchase_v4:
        run_card = json.loads(
            (output_root / "run-cards/project-target-cohort.json").read_bytes()
        )
        assert len(run_card["input_paths"]) == 23
        verifier_owned_bytes = cast(
            dict[str, bytes], verified["verified_artifact_bytes"]
        )
        assert verifier_owned_bytes[
            os.path.abspath(paths["ranked-reserve-result.json"])
        ] == (paths["ranked-reserve-result.json"].read_bytes())
        assert verifier_owned_bytes[
            os.path.abspath(paths["successor-exclusions.jsonl"])
        ] == (paths["successor-exclusions.jsonl"].read_bytes())
    assert len(authority_verifications) == (4 if post_purchase_v4 else 0)
    assert len(resolver_factory_paths) == (2 if post_purchase_v4 else 0)
    assert (
        authentication_tokens
        == [
            verified_token if post_purchase_v4 else None,
        ]
        * 4
    )

    selection_payload = selection.read_bytes()
    tampered_selection = [
        json.loads(line) for line in selection_payload.decode().splitlines()
    ]
    tampered_selection[0]["free_required_document_count"] -= 1
    tampered_selection[0]["missing_required_document_count"] += 1
    selection.write_bytes(_jsonl(tampered_selection))
    with monkeypatch.context() as verifier_patch:
        verifier_patch.setattr(
            cli,
            "_cmd_project_zero_cost_successor",
            lambda _args: pytest.fail("producer replay preceded counter validation"),
        )
        with pytest.raises(cli.CommandError, match="document counters differ"):
            cli._verify_zero_cost_successor_projection(
                target_root=output_root,
                free_clearance_path=output_root / "disclosure-clearance.jsonl",
                expected_target_count=100,
            )
    selection.write_bytes(selection_payload)

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


@dataclass
class _ZeroCostCliHarness:
    command: list[str]
    output_root: Path
    fixture: Fixture
    projection: dict[str, Any]
    summary_path: Path
    selection_path: Path
    verified_bytes: dict[str, bytes]


def _zero_cost_cli_harness(tmp_path: Path) -> _ZeroCostCliHarness:
    """Build the same non-v4 CLI inputs as the happy-path publication test."""

    fixture = _fixture()
    target_root = tmp_path / "target"
    target_root.mkdir()
    summary_path = target_root / "target-cohort-projection.json"
    selection_path = target_root / "target-cohort-selection.jsonl"
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
        (selection_path, original_bytes),
        (reserve_path, reserve_bytes),
        (original_exclusions_path, b""),
        (source_path, source_bytes),
    ):
        path.write_bytes(payload)
    verified_bytes = {
        os.path.abspath(summary_path): summary_path.read_bytes(),
        os.path.abspath(selection_path): original_bytes,
        os.path.abspath(reserve_path): reserve_bytes,
        os.path.abspath(original_exclusions_path): b"",
        os.path.abspath(source_path): source_bytes,
    }
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
    command = [
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
    return _ZeroCostCliHarness(
        command=command,
        output_root=output_root,
        fixture=fixture,
        projection=projection,
        summary_path=summary_path,
        selection_path=selection_path,
        verified_bytes=verified_bytes,
    )


def _install_zero_cost_cli_auth_stubs(
    monkeypatch: pytest.MonkeyPatch,
    harness: _ZeroCostCliHarness,
    *,
    purchase_approval: bool = True,
    clearance: bool = True,
    precursor: bool = True,
    precursor_result: Mapping[str, object] | None = None,
) -> None:
    if purchase_approval:
        monkeypatch.setattr(
            cli,
            "verify_completed_target_cohort_projection_for_purchase_approval",
            lambda _root: {
                "summary": harness.projection,
                "summary_path": harness.summary_path,
                "selection_path": harness.selection_path,
                "verified_artifact_bytes": harness.verified_bytes,
            },
        )
    if clearance:
        monkeypatch.setattr(
            cli, "_verify_authenticated_clearance_run_card", lambda **_kwargs: ()
        )
    if precursor:
        result = (
            precursor_result
            if precursor_result is not None
            else harness.fixture.kwargs["authenticated_ranked_result"]
        )

        def authenticate_precursor(**_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(result=result)

        monkeypatch.setattr(
            cli, "_authenticate_ranked_reserve_precursor", authenticate_precursor
        )


def _published_zero_cost_output_files(output_root: Path) -> set[str]:
    if not output_root.exists():
        return set()
    return {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    }


def test_zero_cost_cli_rejects_unauthenticated_target_projection_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    harness = _zero_cost_cli_harness(tmp_path)
    _install_zero_cost_cli_auth_stubs(monkeypatch, harness, purchase_approval=False)

    assert cli.main(harness.command) == 2
    assert "target projection run card must be" in capsys.readouterr().err
    assert _published_zero_cost_output_files(harness.output_root) == set()


def test_zero_cost_cli_rejects_unauthenticated_clearance_run_card_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    harness = _zero_cost_cli_harness(tmp_path)
    _install_zero_cost_cli_auth_stubs(monkeypatch, harness, clearance=False)

    assert cli.main(harness.command) == 2
    assert "clearance run card lacks output_commitments" in capsys.readouterr().err
    assert _published_zero_cost_output_files(harness.output_root) == set()


def test_zero_cost_cli_rejects_mismatched_ranked_precursor_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    harness = _zero_cost_cli_harness(tmp_path)
    mismatched = dict(
        cast(
            Mapping[str, object], harness.fixture.kwargs["authenticated_ranked_result"]
        )
    )
    mismatched["committed_spend_usd"] = "0.00"
    _install_zero_cost_cli_auth_stubs(monkeypatch, harness, precursor_result=mismatched)

    assert cli.main(harness.command) == 2
    assert (
        "ranked result differs from authenticated ranked-reserve replay"
        in capsys.readouterr().err
    )
    assert _published_zero_cost_output_files(harness.output_root) == set()


def test_zero_cost_cli_rejects_incomplete_v4_authority_bundle_before_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "successor"
    command = [
        "acquisition",
        "project-zero-cost-successor",
        "--target-cohort-root",
        str(tmp_path / "target"),
        "--purchase-policy",
        str(tmp_path / "purchase-policy.json"),
        "--controlled-private-root",
        str(tmp_path / "private"),
        "--purchase-ledger",
        str(tmp_path / "purchase-ledger.sqlite3"),
        "--purchase-ledger-initialization-receipt",
        str(tmp_path / "purchase-ledger-receipt.json"),
        "--purchase-result",
        str(tmp_path / "purchase-result.json"),
        "--purchase-run-card",
        str(tmp_path / "purchase-run-card.json"),
        "--screening-snapshot-manifest",
        str(tmp_path / "screening-snapshot-manifest.json"),
        "--ranked-reserve-result",
        str(tmp_path / "ranked-result.json"),
        "--active-selection",
        str(tmp_path / "active.jsonl"),
        "--replacement-selection",
        str(tmp_path / "replacement.jsonl"),
        "--successor-exclusions",
        str(tmp_path / "exclusions.jsonl"),
        "--replacement-budget-plan",
        str(tmp_path / "budget.json"),
        "--disclosure-clearance",
        str(tmp_path / "clearance.jsonl"),
        "--disclosure-clearance-run-card",
        str(tmp_path / "clearance-card.json"),
        "--prior-ranked-result",
        str(tmp_path / "prior-result.json"),
        "--output-root",
        str(output_root),
    ]

    assert cli.main(command) == 2
    assert "complete authority bundle" in capsys.readouterr().err
    assert not output_root.exists()


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
        "snapshot_manifest_sha256": "d" * 64,
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
        "residual_terminal_exclusions_sha256": "f" * 64,
        "partition_disjoint": True,
        "partition_exhaustive": True,
        "model_visible": False,
        "audit_only": True,
    }


def test_purchase_approval_verifier_delegates_zero_cost_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_root = tmp_path / "target"
    run_card_path = target_root / "run-cards/project-target-cohort.json"
    run_card_path.parent.mkdir(parents=True)
    run_card_path.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": STATE_SCHEMA_VERSION,
                "selected_case_count": 100,
            }
        )
    )
    verified = {"selection_records": [{"candidate_id": "case-a"}]}
    observed: dict[str, object] = {}

    def verify(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return verified

    monkeypatch.setattr(cli, "_verify_zero_cost_successor_projection", verify)

    assert (
        cli.verify_completed_target_cohort_projection_for_purchase_approval(target_root)
        is verified
    )
    assert observed == {
        "target_root": target_root,
        "free_clearance_path": target_root / "disclosure-clearance.jsonl",
        "expected_target_count": 100,
        "_verified_legacy_ranked_replay": None,
        "_verified_clearance_source_roots": None,
        "_verified_clearance_relocations": None,
    }
