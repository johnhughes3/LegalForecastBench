from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion import recap_fetch_attempt_policy as attempt_module
from legalforecast.ingestion import replacement_purchase_approval as approval_module
from legalforecast.ingestion import replacement_recovery_source as source_module
from legalforecast.ingestion import resolved_post_recovery as resolved_module
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseSnapshot,
    canonical_purchase_operation_sha256,
    canonical_purchase_state_sha256,
)

_VERIFIED_POLICY_SHA256 = "7" * 64


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))
    return path


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(_json_bytes(value) for value in values))
    return path


def _commitment(path: Path) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _source_commitments(paths: list[Path]) -> dict[str, dict[str, str]]:
    return {f"input_{index:02d}": _commitment(path) for index, path in enumerate(paths)}


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    successor: bool,
    recovery_origin: str | None = None,
) -> tuple[argparse.Namespace, dict[str, Path], list[dict[str, Any]]]:
    candidate_id = "successor-case" if successor else "initial-case"
    document_id = "successor-doc" if successor else "initial-doc"
    selection_records = [
        {
            "candidate_id": candidate_id,
            "documents": [
                {
                    "source_document_id": document_id,
                    "requires_paid_recovery": True,
                    "redaction_or_seal_status": "unknown",
                    "is_sealed": False,
                    "is_private": False,
                }
            ],
        }
    ]
    selection = _write_jsonl(tmp_path / "selection.jsonl", selection_records)
    case_relevance = (
        selection
        if successor
        else _write_jsonl(tmp_path / "case-relevance.jsonl", selection_records)
    )
    projection_card = _write_json(tmp_path / "projection-card.json", {"ok": True})
    purchase_policy = _write_json(tmp_path / "purchase-policy.json", {"ok": True})
    cohort_policy = _write_json(tmp_path / "cohort-policy.json", {"ok": True})
    budget = _write_json(
        tmp_path / "budget.json",
        {
            "case_plans": [
                {
                    "candidate_id": candidate_id,
                    "purchase_document_ids": [document_id],
                }
            ]
        },
    )
    ledger = tmp_path / "purchase-ledger.sqlite3"
    ledger.write_bytes(b"ledger fixture")
    attempt = _write_json(tmp_path / "attempt-policy.json", {"ok": True})
    authority = _write_json(tmp_path / "replacement-authority.json", {"ok": True})
    initial_receipt = _write_json(tmp_path / "initialization.json", {"ok": True})
    recovery_root = tmp_path / "recovery"
    recovery_card = recovery_root / "run-cards/recover-recap-fetch-quarantine.json"
    recovery_inputs = (
        [
            selection,
            case_relevance,
            purchase_policy,
            cohort_policy,
            budget,
            ledger,
            attempt,
            authority,
        ]
        if successor
        else [
            selection,
            case_relevance,
            projection_card,
            purchase_policy,
            cohort_policy,
            budget,
            ledger,
            attempt,
        ]
    )
    recovery_sources = {
        (
            "replacement_purchase_authority"
            if successor and index == 7
            else "selection"
            if index == 0
            else "case_relevance"
            if index == 1
            else "purchase_policy"
            if (successor and index == 2) or (not successor and index == 3)
            else "cohort_policy"
            if (successor and index == 3) or (not successor and index == 4)
            else "budget_plan"
            if (successor and index == 4) or (not successor and index == 5)
            else "attempt_policy"
            if (successor and index == 6) or (not successor and index == 7)
            else "target_projection_run_card"
        ): _commitment(path)
        for index, path in enumerate(recovery_inputs)
        if path != ledger
    }
    _write_json(
        recovery_card,
        {
            "schema_version": (
                "legalforecast.recap_fetch_quarantine_recovery_run_card.v2"
            ),
            "stage": "recover-recap-fetch-quarantine",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "authority_mode": (
                "replacement_successor" if successor else "initial_projection"
            ),
            "input_paths": [str(path.resolve()) for path in recovery_inputs],
            "source_commitments": recovery_sources,
        },
    )
    manifest_record: dict[str, object] = {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
    }
    if recovery_origin is not None:
        manifest_record["recovery_origin"] = recovery_origin
    manifest = _write_jsonl(
        recovery_root / "purchased-document-downloads-quarantine.jsonl",
        [manifest_record],
    )
    terminal_unavailable = _write_jsonl(
        recovery_root / "terminal-unavailable-operations.jsonl", []
    )
    clearance = _write_jsonl(
        tmp_path / "clearance/disclosure-clearance.jsonl",
        [
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": "cleared",
            }
        ],
    )
    quarantine = _write_jsonl(tmp_path / "clearance/quarantine.jsonl", [])
    clearance_card = _write_json(
        tmp_path / "clearance/run-cards/finalize-provenance-quarantine.json",
        {
            "schema_version": (
                "legalforecast.provenance_quarantine_clearance_run_card.v1"
            ),
            "stage": "finalize-provenance-quarantine",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
            "human_review_requested": False,
            "human_review_executed": False,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "output_paths": [str(clearance.resolve()), str(quarantine.resolve())],
            "output_commitments": {
                "disclosure_clearance": _commitment(clearance),
                "disclosure_quarantine": _commitment(quarantine),
            },
        },
    )
    resolved = _write_jsonl(
        tmp_path / "resolved/resolved-post-recovery-documents.jsonl",
        [{"candidate_id": candidate_id, "source_document_id": document_id}],
    )
    resolved_inputs = [
        selection,
        purchase_policy,
        cohort_policy,
        budget,
        ledger,
        attempt,
        *([authority] if successor else []),
        manifest,
        terminal_unavailable,
        clearance,
        clearance_card,
    ]
    resolved_card = _write_json(
        tmp_path / "resolved/run-cards/resolve-post-recovery-documents.json",
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "resolve-post-recovery-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "input_paths": [str(path.resolve()) for path in resolved_inputs],
            "output_paths": [str(resolved.resolve()), str(ledger.resolve())],
            "source_commitments": _source_commitments(resolved_inputs),
            "output_commitments": {
                "resolved_post_recovery_documents": _commitment(resolved),
                "purchase_state_sha256": "state-1",
            },
            "purchase_state_before_sha256": "state-0",
            "purchase_state_after_sha256": "state-1",
            "terminal_unavailable_partition": {
                **_commitment(terminal_unavailable),
                "record_count": 0,
            },
        },
    )
    verified_calls: list[dict[str, Any]] = []

    def verify_recovery(**kwargs: Any) -> dict[str, object]:
        verified_calls.append({"recovery": kwargs})
        assert Path(kwargs["selection_path"]).resolve() == selection.resolve()
        assert list(kwargs["purchase_operations"]) == [
            {"candidate_id": candidate_id, "source_document_id": document_id}
        ]
        assert kwargs["purchase_committed_amount_usd"] == "3.05"
        assert kwargs["purchase_state_sha256"] == "state-1"
        return {
            "recovery_stage": "recover-recap-fetch-quarantine",
            "manifest_path": manifest,
            "manifest_records": [manifest_record],
            "terminal_unavailable_path": terminal_unavailable,
            "run_card_path": recovery_card,
            "verified_artifact_bytes": {
                str(recovery_card.resolve()): recovery_card.read_bytes(),
                str(manifest.resolve()): manifest.read_bytes(),
                str(terminal_unavailable.resolve()): (
                    terminal_unavailable.read_bytes()
                ),
            },
        }

    def verify_clearance(**kwargs: Any) -> dict[str, object]:
        verified_calls.append({"clearance": kwargs})
        assert Path(kwargs["clearance_path"]).resolve() == clearance.resolve()
        return {
            "clearance_records": [
                {
                    "candidate_id": candidate_id,
                    "source_document_id": document_id,
                    "status": "cleared",
                }
            ],
            "verified_artifact_bytes": {
                str(clearance.resolve()): clearance.read_bytes(),
                str(clearance_card.resolve()): clearance_card.read_bytes(),
            },
        }

    monkeypatch.setattr(cli, "_verify_materializer_recovery", verify_recovery)
    monkeypatch.setattr(cli, "_verify_materializer_clearance_lineage", verify_clearance)
    monkeypatch.setattr(
        cli,
        "_verify_materializer_recovery_clearance_binding",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy",
        lambda _artifact: SimpleNamespace(
            canonical_ledger_path=ledger.resolve(),
            policy_sha256=_VERIFIED_POLICY_SHA256,
        ),
    )
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli, "verify_case_dev_purchase_policy_cohort_binding", lambda *_args: None
    )
    monkeypatch.setattr(
        cli, "verify_approved_purchase_input_bytes", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "verify_recap_fetch_attempt_policy",
        lambda *_args, **kwargs: verified_calls.append({"attempt": kwargs}),
    )
    monkeypatch.setattr(
        cli, "_missing_core_budget_plan", lambda _artifact: SimpleNamespace()
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            purchase_state_sha256="state-1",
            committed_amount_usd="3.05",
            operations=[
                {"candidate_id": candidate_id, "source_document_id": document_id}
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "require_resolved_post_recovery_operation_bindings",
        lambda **kwargs: verified_calls.append({"resolved": kwargs}),
    )
    monkeypatch.setattr(
        cli,
        "verify_replacement_purchase_authority",
        lambda **kwargs: verified_calls.append({"authority": kwargs}),
    )
    initial_private = tmp_path / "initial-private"
    initial_private.mkdir()
    replacement_private = tmp_path / "replacement-private"
    replacement_private.mkdir()
    args = argparse.Namespace(
        output_root=tmp_path / "descriptor-output",
        ordinal=1 if successor else 0,
        recovery_root=recovery_root,
        purchased_clearance_run_card=clearance_card,
        resolved_post_recovery_run_card=resolved_card,
        purchase_policy=purchase_policy,
        cohort_policy=cohort_policy,
        purchase_ledger=ledger,
        initial_controlled_private_root=initial_private,
        purchase_ledger_initialization_receipt=initial_receipt,
        replacement_controlled_private_root=(
            replacement_private if successor else None
        ),
        descriptor_output=None,
        run_card_output=None,
        execute=True,
        resume=False,
    )
    return (
        args,
        {
            "selection": selection,
            "budget": budget,
            "authority": authority,
            "clearance": clearance,
            "resolved": resolved,
            "recovery_card": recovery_card,
            "clearance_card": clearance_card,
            "resolved_card": resolved_card,
            "terminal_unavailable": terminal_unavailable,
        },
        verified_calls,
    )


@pytest.mark.parametrize("successor", [False, True])
def test_producer_derives_closed_descriptor_from_authenticated_run_cards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    successor: bool,
) -> None:
    args, paths, verified_calls = _fixture(tmp_path, monkeypatch, successor=successor)

    assert cli._cmd_build_replacement_recovery_source(args) == 0
    attempt_call = next(call["attempt"] for call in verified_calls if "attempt" in call)
    assert attempt_call["_verified_resolved_transition_capability"] is None
    assert "_expected_resolved_transition_prior_snapshot" not in attempt_call
    clearance_call = next(
        call["clearance"] for call in verified_calls if "clearance" in call
    )
    assert clearance_call["authority_transition_capability"] is None
    assert clearance_call["attempt_transition_capability"] is None
    assert clearance_call["resolved_transition_prior_snapshot"] is None
    assert clearance_call["recovery_authority_transition_capability"] is None
    assert clearance_call["recovery_attempt_transition_capability"] is None
    if successor:
        authority_call = next(
            call["authority"] for call in verified_calls if "authority" in call
        )
        assert authority_call["_verified_resolved_transition_capability"] is None
        assert "_expected_resolved_transition_prior_snapshot" not in authority_call
    resolved_binding = next(
        call["resolved"] for call in verified_calls if "resolved" in call
    )
    assert (
        resolved_binding["expected_purchase_policy_sha256"] == _VERIFIED_POLICY_SHA256
    )

    kind = "successor" if successor else "initial_v2"
    descriptor_path = args.output_root / (
        "0001-successor.json" if successor else "0000-initial-v2.json"
    )
    descriptor = json.loads(descriptor_path.read_bytes())
    expected = {
        "kind": kind,
        "ordinal": args.ordinal,
        "recovery_root": str(args.recovery_root.absolute()),
        "selection": str(paths["selection"].absolute()),
        "purchased_clearance": str(paths["clearance"].absolute()),
        "purchased_clearance_run_card": str(paths["clearance_card"].absolute()),
        "resolved_post_recovery_documents": str(paths["resolved"].absolute()),
    }
    if successor:
        expected.update(
            {
                "replacement_purchase_authority": str(paths["authority"].absolute()),
                "replacement_controlled_private_root": str(
                    args.replacement_controlled_private_root.absolute()
                ),
                "replacement_budget_plan": str(paths["budget"].absolute()),
            }
        )
        assert any("authority" in call for call in verified_calls)
    assert descriptor == expected
    assert descriptor_path.read_bytes() == cli._projection_json_bytes(expected)

    card_path = (
        args.output_root
        / "run-cards"
        / f"build-replacement-recovery-source-{args.ordinal:04d}.json"
    )
    card = json.loads(card_path.read_bytes())
    assert card["schema_version"] == (
        "legalforecast.replacement_recovery_source_run_card.v1"
    )
    assert card["kind"] == kind
    assert card["ordinal"] == args.ordinal
    assert card["status"] == "completed"
    assert card["provider_activity_requested"] is False
    assert card["provider_activity_executed"] is False
    assert card["paid_activity_requested"] is False
    assert card["paid_activity_executed"] is False
    assert card["output_paths"] == [str(descriptor_path)]
    assert card["output_commitments"] == {
        str(descriptor_path.resolve()): (
            "sha256:" + hashlib.sha256(descriptor_path.read_bytes()).hexdigest()
        )
    }
    assert card["purchase_state_sha256"] == "state-1"
    assert set(card["source_commitments"]) == {
        str(Path(path).resolve()) for path in card["input_paths"]
    }
    assert (
        card["source_commitments"][str(paths["terminal_unavailable"].resolve())]
        == "sha256:"
        + hashlib.sha256(paths["terminal_unavailable"].read_bytes()).hexdigest()
    )

    args.resume = True
    assert cli._cmd_build_replacement_recovery_source(args) == 0


def test_producer_authenticates_mutated_ledger_by_semantic_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, _, _ = _fixture(tmp_path, monkeypatch, successor=True)
    ledger = cast(Path, args.purchase_ledger)
    ledger.write_bytes(b"post-resolution ledger bytes")

    assert cli._cmd_build_replacement_recovery_source(args) == 0

    card_path = (
        cast(Path, args.output_root)
        / "run-cards"
        / "build-replacement-recovery-source-0001.json"
    )
    source_paths = set(json.loads(card_path.read_bytes())["source_commitments"])
    assert str(ledger.resolve()) not in source_paths


@pytest.mark.parametrize(
    "schema_version",
    [
        "legalforecast.resolved_post_recovery_public_document.v2",
        "legalforecast.resolved_post_recovery_public_document.v3",
    ],
)
def test_provider_free_terminal_capability_routes_legacy_schema_to_recovered_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_version: str,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    resolved_records = [
        {
            "schema_version": schema_version,
            "candidate_id": "initial-case",
            "source_document_id": "initial-doc",
        }
    ]
    _write_jsonl(paths["resolved"], resolved_records)

    terminal_records = [
        {
            "schema_version": "legalforecast.recap_fetch_terminal_unavailable.v1",
            "candidate_id": "terminal-case",
            "source_document_id": "terminal-doc",
        }
    ]
    _write_jsonl(paths["terminal_unavailable"], terminal_records)
    terminal_selection = _write_jsonl(
        tmp_path / "terminal-selection.jsonl",
        [
            {
                "candidate_id": "terminal-case",
                "documents": [{"source_document_id": "terminal-doc"}],
            }
        ],
    )
    terminal_snapshot = _write_json(tmp_path / "terminal-snapshot.json", {"ok": True})
    terminal_result = _write_json(tmp_path / "terminal-result.json", {"ok": True})
    terminal_card = _write_json(tmp_path / "terminal-card.json", {"ok": True})
    disposition_paths = (
        terminal_selection,
        terminal_snapshot,
        terminal_result,
        terminal_card,
    )
    (
        args.terminal_disposition_selection,
        args.terminal_disposition_snapshot_manifest,
        args.terminal_purchase_result,
        args.terminal_purchase_run_card,
    ) = disposition_paths

    resolved_card = json.loads(paths["resolved_card"].read_bytes())
    input_paths = [Path(value) for value in resolved_card["input_paths"]]
    input_paths.extend(disposition_paths)
    resolved_card["input_paths"] = [str(path.resolve()) for path in input_paths]
    resolved_card["source_commitments"] = _source_commitments(input_paths)
    resolved_card["output_commitments"]["resolved_post_recovery_documents"] = (
        _commitment(paths["resolved"])
    )
    resolved_card["terminal_unavailable_partition"] = {
        **_commitment(paths["terminal_unavailable"]),
        "record_count": 1,
    }
    resolved_card["terminal_disposition_sources"] = {
        "selection": str(terminal_selection.resolve()),
        "snapshot_manifest": str(terminal_snapshot.resolve()),
        "purchase_result": str(terminal_result.resolve()),
        "purchase_run_card": str(terminal_card.resolve()),
    }
    _write_json(paths["resolved_card"], resolved_card)

    recovery_capability = object()
    terminal_capability = object()

    def verify_clearance(**_kwargs: Any) -> dict[str, object]:
        return {
            "lineage_kind": "provider_free_recovered_public",
            "authenticated_recovery_capability": recovery_capability,
            "clearance_records": [
                {
                    "candidate_id": "initial-case",
                    "source_document_id": "initial-doc",
                    "status": "cleared",
                }
            ],
            "verified_artifact_bytes": {
                str(paths["clearance"].resolve()): paths["clearance"].read_bytes(),
                str(paths["clearance_card"].resolve()): paths[
                    "clearance_card"
                ].read_bytes(),
            },
        }

    class FakeJournal:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeJournal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    terminal_authority = object()
    monkeypatch.setattr(cli, "_verify_materializer_clearance_lineage", verify_clearance)
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", FakeJournal)
    monkeypatch.setattr(
        cli,
        "_verify_materializer_docket_decision_authority",
        lambda **_kwargs: SimpleNamespace(
            authority=terminal_authority,
            source_snapshots={path: path.read_bytes() for path in disposition_paths},
        ),
    )

    def issue_terminal_capability(**kwargs: object) -> object:
        assert kwargs["authority"] is terminal_authority
        assert kwargs["verified_recovery_capability"] is recovery_capability
        return terminal_capability

    monkeypatch.setattr(
        cli, "_issue_terminal_disposition_capability", issue_terminal_capability
    )

    def clearance_kwargs(**kwargs: object) -> dict[str, object]:
        lineage = cast(dict[str, object], kwargs["lineage"])
        assert lineage["authenticated_recovery_capability"] is recovery_capability
        return {"_verified_recovery_capability": recovery_capability}

    monkeypatch.setattr(cli, "_materializer_clearance_lineage_kwargs", clearance_kwargs)
    dispatch_calls: list[dict[str, object]] = []
    binding_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        cli,
        "_require_resolved_post_recovery_dispatch",
        lambda **kwargs: dispatch_calls.append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "_require_resolved_operation_bindings_dispatch",
        lambda **kwargs: binding_calls.append(kwargs),
    )

    def reject_legacy_verifier(**_kwargs: object) -> None:
        pytest.fail("legacy operation-bindings verifier selected")

    monkeypatch.setattr(
        cli,
        "require_resolved_post_recovery_operation_bindings",
        reject_legacy_verifier,
    )

    assert cli._cmd_build_replacement_recovery_source(args) == 0
    assert len(dispatch_calls) == 1
    assert len(binding_calls) == 1
    dispatch = dispatch_calls[0]
    assert dispatch["_verified_recovery_capability"] is recovery_capability
    assert dispatch["_verified_terminal_disposition_capability"] is terminal_capability
    assert dispatch["resolved_records"] == resolved_records
    binding_clearance = cast(dict[str, object], binding_calls[0]["clearance_kwargs"])
    assert binding_clearance["_verified_recovery_capability"] is recovery_capability
    assert (
        binding_clearance["_verified_terminal_disposition_capability"]
        is terminal_capability
    )
    assert binding_calls[0]["resolved_records"] == resolved_records


@pytest.mark.parametrize(
    "provider_activity_field",
    ["provider_activity_requested", "provider_activity_executed"],
)
@pytest.mark.parametrize("successor", [False, True])
def test_producer_accepts_public_marker_provider_free_clearance_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_activity_field: str,
    successor: bool,
) -> None:
    args, paths, _verified_calls = _fixture(tmp_path, monkeypatch, successor=successor)
    clearance_card = json.loads(paths["clearance_card"].read_bytes())
    clearance_card["schema_version"] = (
        "legalforecast.provenance_public_marker_clearance_run_card.v1"
    )
    paths["clearance_card"].write_bytes(_json_bytes(clearance_card))

    def refresh_resolver_commitment() -> None:
        resolved_card = json.loads(paths["resolved_card"].read_bytes())
        input_paths = cast(list[str], resolved_card["input_paths"])
        index = input_paths.index(str(paths["clearance_card"].resolve()))
        resolved_card["source_commitments"][f"input_{index:02d}"] = _commitment(
            paths["clearance_card"]
        )
        paths["resolved_card"].write_bytes(_json_bytes(resolved_card))

    refresh_resolver_commitment()

    assert cli._cmd_build_replacement_recovery_source(args) == 0

    clearance_card[provider_activity_field] = True
    paths["clearance_card"].write_bytes(_json_bytes(clearance_card))
    refresh_resolver_commitment()
    args.resume = False
    args.output_root = tmp_path / "rejected"
    with pytest.raises(cli.CommandError, match="provider-free clearance run card"):
        cli._cmd_build_replacement_recovery_source(args)


def test_producer_rejects_mode_ordinal_and_private_root_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_args, _, _ = _fixture(tmp_path / "initial", monkeypatch, successor=False)
    initial_args.ordinal = 2
    with pytest.raises(cli.CommandError, match=r"initial_v2.*ordinal 0"):
        cli._cmd_build_replacement_recovery_source(initial_args)

    successor_args, _, _ = _fixture(tmp_path / "successor", monkeypatch, successor=True)
    successor_args.replacement_controlled_private_root = None
    with pytest.raises(cli.CommandError, match="replacement controlled private root"):
        cli._cmd_build_replacement_recovery_source(successor_args)

    history_args, _, _ = _fixture(tmp_path / "history", monkeypatch, successor=False)
    history_args.successor_history_recovery_root = tmp_path / "later-recovery"
    with pytest.raises(
        cli.CommandError,
        match="history recovery and private roots must be supplied together",
    ):
        cli._cmd_build_replacement_recovery_source(history_args)

    positive_args, _, _ = _fixture(tmp_path / "positive", monkeypatch, successor=True)
    positive_args.successor_history_recovery_root = tmp_path / "later-recovery"
    positive_args.successor_history_controlled_private_root = tmp_path / "later-private"
    with pytest.raises(
        cli.CommandError,
        match="history is allowed only for the ordinal 0 initial recovery",
    ):
        cli._cmd_build_replacement_recovery_source(positive_args)


def test_producer_rejects_noncanonical_initial_authority_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["recovery_card"].read_bytes())
    card["authority_mode"] = "approved_v2"
    _write_json(paths["recovery_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="authority_mode is not initial_projection or replacement_successor",
    ):
        cli._cmd_build_replacement_recovery_source(args)


def test_producer_rejects_historical_v1_recovery_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["recovery_card"].read_bytes())
    card["schema_version"] = "legalforecast.acquisition_run_card.v1"
    _write_json(paths["recovery_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="completed provider-free recovery run card",
    ):
        cli._cmd_build_replacement_recovery_source(args)
    assert not args.output_root.exists()


def test_producer_rejects_resolved_run_card_rebinding_and_extra_commitment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    rebound = _write_jsonl(tmp_path / "rebound.jsonl", [])
    card["output_commitments"]["resolved_post_recovery_documents"] = _commitment(
        rebound
    )
    card["output_paths"][0] = str(rebound.resolve())
    card["output_commitments"]["unexpected"] = _commitment(paths["selection"])
    _write_json(paths["resolved_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="resolved post-recovery output commitments differ",
    ):
        cli._cmd_build_replacement_recovery_source(args)


@pytest.mark.parametrize("field", ["path", "sha256", "record_count"])
def test_producer_rejects_terminal_unavailable_partition_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    partition = cast(dict[str, object], card["terminal_unavailable_partition"])
    if field == "path":
        partition[field] = str(paths["selection"].resolve())
    elif field == "sha256":
        partition[field] = "sha256:" + "0" * 64
    else:
        partition[field] = 1
    _write_json(paths["resolved_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="resolved terminal-unavailable partition changed",
    ):
        cli._cmd_build_replacement_recovery_source(args)


def test_producer_rejects_terminal_unavailable_input_omission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    terminal_path = str(paths["terminal_unavailable"].resolve())
    index = cast(list[str], card["input_paths"]).index(terminal_path)
    cast(list[str], card["input_paths"]).pop(index)
    commitments = cast(dict[str, object], card["source_commitments"])
    rebuilt: dict[str, object] = {}
    for new_index, old_index in enumerate(
        item for item in range(len(commitments)) if item != index
    ):
        rebuilt[f"input_{new_index:02d}"] = commitments[f"input_{old_index:02d}"]
    card["source_commitments"] = rebuilt
    _write_json(paths["resolved_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="resolved source omits authenticated recovery inputs",
    ):
        cli._cmd_build_replacement_recovery_source(args)


def test_resolved_coordinates_accept_legacy_omitted_empty_terminal_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    expected_inputs = [Path(value) for value in card["input_paths"]]
    terminal_path = paths["terminal_unavailable"].resolve()
    terminal_index = next(
        index
        for index, path in enumerate(expected_inputs)
        if path.resolve() == terminal_path
    )
    cast(list[str], card["input_paths"]).pop(terminal_index)
    commitments = cast(dict[str, object], card["source_commitments"])
    card["source_commitments"] = {
        f"input_{new_index:02d}": commitments[f"input_{old_index:02d}"]
        for new_index, old_index in enumerate(
            index for index in range(len(commitments)) if index != terminal_index
        )
    }
    card.pop("terminal_unavailable_partition")

    coordinates = source_module.derive_resolved_source_coordinates(
        card,
        expected_input_paths=expected_inputs,
        expected_ledger_path=cast(Path, args.purchase_ledger),
        expected_purchase_state_sha256="state-1",
        expected_terminal_unavailable_path=paths["terminal_unavailable"],
        expected_terminal_unavailable_sha256=_commitment(paths["terminal_unavailable"])[
            "sha256"
        ],
        expected_terminal_unavailable_count=0,
        expected_terminal_disposition_paths=None,
    )

    assert terminal_path not in {path.resolve() for path in coordinates.input_paths}
    assert coordinates.terminal_unavailable_path.resolve() == terminal_path
    assert coordinates.terminal_unavailable_count == 0


def test_resolved_coordinates_authenticate_present_legacy_empty_terminal_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    expected_inputs = [Path(value) for value in card["input_paths"]]
    terminal_path = paths["terminal_unavailable"].resolve()
    card.pop("terminal_unavailable_partition")

    coordinates = source_module.derive_resolved_source_coordinates(
        card,
        expected_input_paths=expected_inputs,
        expected_ledger_path=cast(Path, args.purchase_ledger),
        expected_purchase_state_sha256="state-1",
        expected_terminal_unavailable_path=paths["terminal_unavailable"],
        expected_terminal_unavailable_sha256=_commitment(
            paths["terminal_unavailable"]
        )["sha256"],
        expected_terminal_unavailable_count=0,
        expected_terminal_disposition_paths=None,
    )

    assert terminal_path not in {path.resolve() for path in coordinates.input_paths}

    terminal_index = next(
        index
        for index, path in enumerate(expected_inputs)
        if path.resolve() == terminal_path
    )
    commitments = cast(dict[str, object], card["source_commitments"])
    commitment = cast(dict[str, object], commitments[f"input_{terminal_index:02d}"])
    commitment["sha256"] = f"sha256:{'a' * 64}"

    with pytest.raises(
        source_module.ReplacementRecoverySourceError,
        match="resolved legacy empty terminal input changed",
    ):
        source_module.derive_resolved_source_coordinates(
            card,
            expected_input_paths=expected_inputs,
            expected_ledger_path=cast(Path, args.purchase_ledger),
            expected_purchase_state_sha256="state-1",
            expected_terminal_unavailable_path=paths["terminal_unavailable"],
            expected_terminal_unavailable_sha256=_commitment(
                paths["terminal_unavailable"]
            )["sha256"],
            expected_terminal_unavailable_count=0,
            expected_terminal_disposition_paths=None,
        )


def test_resolved_coordinates_align_commitments_to_expected_input_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    expected_inputs = [Path(value) for value in card["input_paths"]]
    reordered_inputs = [expected_inputs[1], expected_inputs[0], *expected_inputs[2:]]
    card["input_paths"] = [str(path.resolve()) for path in reordered_inputs]
    card["source_commitments"] = _source_commitments(reordered_inputs)

    coordinates = source_module.derive_resolved_source_coordinates(
        card,
        expected_input_paths=expected_inputs,
        expected_ledger_path=cast(Path, args.purchase_ledger),
        expected_purchase_state_sha256="state-1",
        expected_terminal_unavailable_path=paths["terminal_unavailable"],
        expected_terminal_unavailable_sha256=_commitment(paths["terminal_unavailable"])[
            "sha256"
        ],
        expected_terminal_unavailable_count=0,
        expected_terminal_disposition_paths=None,
    )

    assert coordinates.input_paths == tuple(expected_inputs)
    assert coordinates.input_sha256 == tuple(
        _commitment(path)["sha256"] for path in expected_inputs
    )


def test_resolved_coordinates_accept_identical_overlapping_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    duplicate = Path(cast(list[str], card["input_paths"])[0])
    cast(list[str], card["input_paths"]).append(str(duplicate.resolve()))
    commitments = cast(dict[str, object], card["source_commitments"])
    commitments[f"input_{len(commitments):02d}"] = _commitment(duplicate)
    expected_inputs = [Path(value) for value in card["input_paths"]]

    coordinates = source_module.derive_resolved_source_coordinates(
        card,
        expected_input_paths=expected_inputs,
        expected_ledger_path=cast(Path, args.purchase_ledger),
        expected_purchase_state_sha256="state-1",
        expected_terminal_unavailable_path=paths["terminal_unavailable"],
        expected_terminal_unavailable_sha256=_commitment(paths["terminal_unavailable"])[
            "sha256"
        ],
        expected_terminal_unavailable_count=0,
        expected_terminal_disposition_paths=None,
    )

    assert coordinates.input_paths == tuple(expected_inputs)
    assert coordinates.input_sha256[0] == coordinates.input_sha256[-1]


def test_resolved_coordinates_reject_conflicting_duplicate_commitment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    duplicate = cast(list[str], card["input_paths"])[0]
    cast(list[str], card["input_paths"]).append(duplicate)
    commitments = cast(dict[str, object], card["source_commitments"])
    commitments[f"input_{len(commitments):02d}"] = {
        "path": duplicate,
        "sha256": "sha256:" + "f" * 64,
    }

    with pytest.raises(
        source_module.ReplacementRecoverySourceError,
        match="resolved duplicate input commitments differ",
    ):
        source_module.derive_resolved_source_coordinates(
            card,
            expected_input_paths=[Path(value) for value in card["input_paths"]],
            expected_ledger_path=cast(Path, args.purchase_ledger),
            expected_purchase_state_sha256="state-1",
            expected_terminal_unavailable_path=paths["terminal_unavailable"],
            expected_terminal_unavailable_sha256=_commitment(
                paths["terminal_unavailable"]
            )["sha256"],
            expected_terminal_unavailable_count=0,
            expected_terminal_disposition_paths=None,
        )


def test_resolved_coordinates_reject_partial_terminal_disposition_expectations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["resolved_card"].read_bytes())
    disposition_paths = {
        name: _write_json(tmp_path / f"{name}.json", {"name": name})
        for name in (
            "selection",
            "snapshot_manifest",
            "purchase_result",
            "purchase_run_card",
        )
    }
    card["terminal_unavailable_partition"]["record_count"] = 1
    card["terminal_disposition_sources"] = {
        name: str(path.resolve()) for name, path in disposition_paths.items()
    }

    with pytest.raises(
        source_module.ReplacementRecoverySourceError,
        match="resolved terminal disposition sources differ",
    ):
        source_module.derive_resolved_source_coordinates(
            card,
            expected_input_paths=[Path(value) for value in card["input_paths"]],
            expected_ledger_path=cast(Path, args.purchase_ledger),
            expected_purchase_state_sha256="state-1",
            expected_terminal_unavailable_path=paths["terminal_unavailable"],
            expected_terminal_unavailable_sha256=_commitment(
                paths["terminal_unavailable"]
            )["sha256"],
            expected_terminal_unavailable_count=1,
            expected_terminal_disposition_paths={
                "selection": disposition_paths["selection"]
            },
        )


def test_producer_rejects_clearance_extra_commitment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["clearance_card"].read_bytes())
    card["output_commitments"]["unexpected"] = _commitment(paths["selection"])
    _write_json(paths["clearance_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="clearance output commitments have extra or missing fields",
    ):
        cli._cmd_build_replacement_recovery_source(args)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "legalforecast.acquisition_run_card.v1"),
        ("schema_version", []),
        ("schema_version", {}),
        ("stage", "other-stage"),
        ("status", "failed"),
        ("dry_run", True),
        ("execute", False),
        ("provider_activity_requested", True),
        ("provider_activity_executed", True),
        ("human_review_requested", True),
        ("human_review_executed", True),
        ("paid_activity_requested", True),
        ("paid_activity_executed", True),
    ],
)
def test_producer_rejects_clearance_card_outside_provider_free_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["clearance_card"].read_bytes())
    card[field] = value
    _write_json(paths["clearance_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="completed provider-free clearance run card",
    ):
        cli._cmd_build_replacement_recovery_source(args)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "stage",
        "status",
        "dry_run",
        "execute",
        "provider_activity_requested",
        "provider_activity_executed",
        "human_review_requested",
        "human_review_executed",
        "paid_activity_requested",
        "paid_activity_executed",
    ],
)
def test_producer_rejects_clearance_card_missing_contract_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    card = json.loads(paths["clearance_card"].read_bytes())
    del card[field]
    _write_json(paths["clearance_card"], card)

    with pytest.raises(
        cli.CommandError,
        match="completed provider-free clearance run card",
    ):
        cli._cmd_build_replacement_recovery_source(args)


def test_producer_requires_resolved_card_for_unknown_status_recovery_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, _, _ = _fixture(
        tmp_path,
        monkeypatch,
        successor=False,
        recovery_origin="unknown_status_attempt",
    )
    monkeypatch.setattr(
        cli,
        "_selection_requires_resolved_post_recovery",
        lambda _records: False,
    )
    args.resolved_post_recovery_run_card = None

    with pytest.raises(
        cli.CommandError,
        match="unknown-origin recovery requires a resolved post-recovery run card",
    ):
        cli._cmd_build_replacement_recovery_source(args)


def test_producer_resume_rejects_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    assert cli._cmd_build_replacement_recovery_source(args) == 0
    paths["selection"].write_bytes(paths["selection"].read_bytes() + b"\n")
    args.resume = True

    with pytest.raises(cli.CommandError, match="source input commitment changed"):
        cli._cmd_build_replacement_recovery_source(args)


def test_producer_rejects_purchase_ledger_drift_before_run_card_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, _, _ = _fixture(tmp_path, monkeypatch, successor=False)
    operation = {
        "candidate_id": "initial-case",
        "source_document_id": "initial-doc",
    }
    snapshots = iter(
        (
            SimpleNamespace(
                purchase_state_sha256="state-1",
                committed_amount_usd="3.05",
                operations=[operation],
            ),
            SimpleNamespace(
                purchase_state_sha256="state-2",
                committed_amount_usd="3.05",
                operations=[operation],
            ),
        )
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: next(snapshots),
    )

    with pytest.raises(
        cli.CommandError,
        match="purchase ledger changed during recovery source production",
    ):
        cli._cmd_build_replacement_recovery_source(args)
    assert not (args.output_root / "0000-initial-v2.json").exists()
    assert not (
        args.output_root / "run-cards/build-replacement-recovery-source-0000.json"
    ).exists()


def test_producer_rejects_source_drift_before_descriptor_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    verify_clearance = cast(Any, cli._verify_materializer_clearance_lineage)

    def verify_then_rebind_source(*args: object, **kwargs: object) -> object:
        verified = verify_clearance(*args, **kwargs)
        paths["clearance_card"].write_bytes(b'{"rebound":true}\n')
        return verified

    monkeypatch.setattr(
        cli,
        "_verify_materializer_clearance_lineage",
        verify_then_rebind_source,
    )

    with pytest.raises(cli.CommandError, match="snapshot collision"):
        cli._cmd_build_replacement_recovery_source(args)
    assert not (args.output_root / "0000-initial-v2.json").exists()
    assert not (
        args.output_root / "run-cards/build-replacement-recovery-source-0000.json"
    ).exists()


def test_producer_routes_authenticated_successor_history_for_initial_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, verified_calls = _fixture(tmp_path, monkeypatch, successor=False)
    history_root = tmp_path / "successor-history"
    history_private = tmp_path / "successor-private"
    history_private.mkdir()
    history_marker = _write_json(history_root / "history-marker.json", {"ok": True})
    args.successor_history_recovery_root = history_root
    args.successor_history_controlled_private_root = history_private

    def authenticate_history(
        **kwargs: Any,
    ) -> tuple[CaseDevPurchaseSnapshot, dict[str, bytes]]:
        assert kwargs["successor_recovery_root"] == history_root.absolute()
        assert kwargs["successor_controlled_private_root"] == history_private.absolute()
        assert kwargs["authority_transition_capability"] is not None
        assert kwargs["attempt_transition_capability"] is not None
        assert (
            kwargs["authority_transition_capability"]
            is kwargs["attempt_transition_capability"]
        )
        verified_calls.append({"history": kwargs})
        return (
            CaseDevPurchaseSnapshot(
                operations=(
                    {
                        "candidate_id": "initial-case",
                        "source_document_id": "initial-doc",
                    },
                ),
                committed_amount_usd="3.05",
                purchase_state_sha256="state-1",
            ),
            {str(history_marker.resolve()): history_marker.read_bytes()},
        )

    monkeypatch.setattr(
        cli, "_authenticated_pre_successor_purchase_snapshot", authenticate_history
    )
    top_level_attempt_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        cli,
        "verify_recap_fetch_attempt_policy",
        lambda *_args, **kwargs: top_level_attempt_calls.append(kwargs),
    )
    resolved_card = json.loads(paths["resolved_card"].read_bytes())
    resolved_card["purchase_state_after_sha256"] = "current-state-2"
    resolved_card["output_commitments"]["purchase_state_sha256"] = "current-state-2"
    _write_json(paths["resolved_card"], resolved_card)
    prior_snapshot = CaseDevPurchaseSnapshot(
        operations=(
            {
                "candidate_id": "initial-case",
                "source_document_id": "initial-doc",
            },
            {
                "candidate_id": "successor-case",
                "source_document_id": "successor-doc",
            },
        ),
        committed_amount_usd="6.10",
        purchase_state_sha256="state-before-resolution",
    )
    transition_marker = _write_json(
        tmp_path / "authenticated-transition-source.json", {"transition": True}
    )
    transition_capability = object()
    monkeypatch.setattr(
        cli,
        "_issue_resolved_transition_capability",
        lambda **kwargs: (
            transition_capability
            if kwargs["run_card_paths"] == (paths["resolved_card"].absolute(),)
            else pytest.fail("initial successor history must bind the resolver card")
        ),
    )
    monkeypatch.setattr(
        cli,
        "_consume_live_resolved_transition_evidence",
        lambda capability: (
            (
                prior_snapshot,
                {transition_marker: transition_marker.read_bytes()},
                {paths["resolved_card"].absolute(): "current-state-2"},
            )
            if capability is transition_capability
            else pytest.fail("unexpected transition capability")
        ),
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            purchase_state_sha256="current-state-2",
            committed_amount_usd="6.10",
            operations=[
                {
                    "candidate_id": "initial-case",
                    "source_document_id": "initial-doc",
                },
                {
                    "candidate_id": "successor-case",
                    "source_document_id": "successor-doc",
                },
            ],
        ),
    )

    assert cli._cmd_build_replacement_recovery_source(args) == 0
    assert any("history" in call for call in verified_calls)
    history_call = next(call["history"] for call in verified_calls if "history" in call)
    clearance_call = next(
        call["clearance"] for call in verified_calls if "clearance" in call
    )
    assert history_call["authority_transition_capability"] is transition_capability
    assert history_call["attempt_transition_capability"] is transition_capability
    assert clearance_call["authority_transition_capability"] is transition_capability
    assert clearance_call["attempt_transition_capability"] is transition_capability
    assert (
        clearance_call["recovery_authority_transition_capability"]
        is transition_capability
    )
    assert (
        clearance_call["recovery_attempt_transition_capability"]
        is transition_capability
    )
    assert (
        clearance_call["resolved_transition_prior_snapshot"].purchase_state_sha256
        == "state-before-resolution"
    )
    assert len(top_level_attempt_calls) == 1
    assert (
        top_level_attempt_calls[0]["_verified_resolved_transition_capability"] is None
    )
    assert (
        "_expected_resolved_transition_prior_snapshot" not in top_level_attempt_calls[0]
    )
    card = json.loads(
        (
            args.output_root / "run-cards/build-replacement-recovery-source-0000.json"
        ).read_bytes()
    )
    assert (
        card["source_commitments"][str(history_marker.resolve())]
        == _commitment(history_marker)["sha256"]
    )
    assert (
        card["source_commitments"][str(transition_marker.resolve())]
        == _commitment(transition_marker)["sha256"]
    )
    assert card["purchase_state_sha256"] == "current-state-2"
    assert card["schema_version"] == (
        "legalforecast.replacement_recovery_source_run_card.v2"
    )
    assert card["replayed_purchase_state_sha256"] == "state-1"


def test_successor_producer_binds_transition_prior_to_direct_verifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, verified_calls = _fixture(tmp_path, monkeypatch, successor=True)
    args.additional_resolved_post_recovery_run_card = paths["resolved_card"]
    prior = CaseDevPurchaseSnapshot(
        operations=(
            {
                "candidate_id": "successor-case",
                "source_document_id": "successor-doc",
            },
        ),
        committed_amount_usd="3.05",
        purchase_state_sha256="state-1",
    )

    transition_capability = object()
    monkeypatch.setattr(
        cli,
        "_issue_resolved_transition_capability",
        lambda **_kwargs: transition_capability,
    )
    monkeypatch.setattr(
        cli,
        "_consume_live_resolved_transition_evidence",
        lambda capability: (
            (prior, {}, {paths["resolved_card"].absolute(): "state-1"})
            if capability is transition_capability
            else pytest.fail("unexpected transition capability")
        ),
    )
    attempt_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        cli,
        "verify_recap_fetch_attempt_policy",
        lambda *_args, **kwargs: attempt_calls.append(kwargs),
    )

    assert cli._cmd_build_replacement_recovery_source(args) == 0

    authority_call = next(
        call["authority"] for call in verified_calls if "authority" in call
    )
    assert (
        authority_call["_verified_resolved_transition_capability"]
        is transition_capability
    )
    assert "_expected_resolved_transition_prior_snapshot" not in authority_call
    assert len(attempt_calls) == 1
    assert (
        attempt_calls[0]["_verified_resolved_transition_capability"]
        is transition_capability
    )
    assert "_expected_resolved_transition_prior_snapshot" not in attempt_calls[0]
    clearance_call = next(
        call["clearance"] for call in verified_calls if "clearance" in call
    )
    assert clearance_call["authority_transition_capability"] is transition_capability
    assert clearance_call["attempt_transition_capability"] is None
    assert clearance_call["resolved_transition_prior_snapshot"] is None
    assert (
        clearance_call["recovery_authority_transition_capability"]
        is transition_capability
    )
    assert clearance_call["recovery_attempt_transition_capability"] is None


def _successor_history_helper_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, Path]]:
    purchase_policy = _write_json(tmp_path / "purchase-policy.json", {"ok": True})
    cohort_policy = _write_json(tmp_path / "cohort-policy.json", {"ok": True})
    ledger = tmp_path / "ledger.sqlite3"
    ledger.write_bytes(b"ledger")
    receipt = _write_json(tmp_path / "receipt.json", {"ok": True})
    selection = _write_jsonl(
        tmp_path / "selection.jsonl",
        [
            {
                "candidate_id": "successor-case",
                "documents": [
                    {"source_document_id": "101"},
                    {"source_document_id": "102"},
                ],
            }
        ],
    )
    budget = _write_json(
        tmp_path / "budget.json",
        {
            "case_plans": [
                {
                    "candidate_id": "successor-case",
                    "purchase_document_ids": ["101", "102"],
                }
            ]
        },
    )
    attempt = _write_json(tmp_path / "attempt.json", {"ok": True})
    authority = _write_json(tmp_path / "authority.json", {"ok": True})
    recovery_root = tmp_path / "recovery"
    recovery_card = _write_json(
        recovery_root / "run-cards/recover-recap-fetch-quarantine.json",
        {"ok": True},
    )
    coordinates = SimpleNamespace(
        kind="successor",
        selection_path=selection,
        budget_plan_path=budget,
        attempt_policy_path=attempt,
        replacement_authority_path=authority,
        purchase_policy_path=purchase_policy,
        cohort_policy_path=cohort_policy,
        purchase_ledger_path=ledger,
    )
    monkeypatch.setattr(
        cli, "derive_recovery_source_coordinates", lambda _card: coordinates
    )
    monkeypatch.setattr(
        cli,
        "_replacement_consolidation_selection_keys",
        lambda _records: {("successor-case", "101"), ("successor-case", "102")},
    )
    monkeypatch.setattr(cli, "_missing_core_budget_plan", lambda _artifact: object())
    monkeypatch.setattr(
        cli, "verify_recap_fetch_attempt_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "_verify_materializer_recovery",
        lambda **_kwargs: {
            "verified_artifact_bytes": {
                str(recovery_card.resolve()): recovery_card.read_bytes()
            }
        },
    )
    policy = SimpleNamespace(
        cycle_id="cycle-1",
        cohort_policy_sha256="cohort-sha",
        policy_sha256="policy-sha",
    )
    baseline = {
        "candidate_id": "initial-case",
        "source_document_id": "1",
        "reservation_usd": "3.05",
    }
    successor_rows = (
        {
            "candidate_id": "successor-case",
            "source_document_id": "101",
            "reservation_usd": "3.05",
        },
        {
            "candidate_id": "successor-case",
            "source_document_id": "102",
            "reservation_usd": "3.05",
        },
    )
    baseline_state = canonical_purchase_state_sha256(
        policy,
        committed_amount_usd="3.05",
        operations=(baseline,),
    )
    request = SimpleNamespace(
        baseline_operation_record_sha256s=(
            canonical_purchase_operation_sha256(baseline),
        ),
        committed_spend_usd="3.05",
        purchase_journal_state_sha256="sha256:" + baseline_state,
    )
    monkeypatch.setattr(
        cli,
        "verify_replacement_purchase_authority",
        lambda **_kwargs: request,
    )
    return (
        {
            "successor_recovery_root": recovery_root,
            "successor_controlled_private_root": tmp_path / "private",
            "current_snapshot": CaseDevPurchaseSnapshot(
                operations=(baseline, *successor_rows),
                committed_amount_usd="9.15",
                purchase_state_sha256="current-state",
            ),
            "policy": policy,
            "policy_artifact": {"ok": True},
            "cohort_artifact": {"ok": True},
            "purchase_policy_path": purchase_policy,
            "cohort_policy_path": cohort_policy,
            "ledger_path": ledger,
            "initial_controlled_private_root": tmp_path / "initial-private",
            "initialization_receipt_path": receipt,
            "capture": lambda path, **_kwargs: Path(path).read_bytes(),
        },
        {"budget": budget},
    )


def test_authenticated_successor_history_reconstructs_exact_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kwargs, _ = _successor_history_helper_fixture(tmp_path, monkeypatch)

    prefix, recovery_bytes = cli._authenticated_pre_successor_purchase_snapshot(
        **kwargs
    )

    assert prefix.committed_amount_usd == "3.05"
    assert len(prefix.operations) == 1
    assert prefix.operations[0]["candidate_id"] == "initial-case"
    assert recovery_bytes


def test_authenticated_successor_history_binds_transition_prior_to_both_verifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kwargs, _ = _successor_history_helper_fixture(tmp_path, monkeypatch)
    observed: list[object | None] = []
    original_authority = cli.verify_replacement_purchase_authority

    def verify_authority(**call_kwargs: Any) -> object:
        observed.append(call_kwargs.get("_verified_resolved_transition_capability"))
        return original_authority(**call_kwargs)

    def verify_attempt(*_args: object, **call_kwargs: Any) -> None:
        observed.append(call_kwargs.get("_verified_resolved_transition_capability"))

    monkeypatch.setattr(cli, "verify_replacement_purchase_authority", verify_authority)
    monkeypatch.setattr(cli, "verify_recap_fetch_attempt_policy", verify_attempt)

    capability = object()
    cli._authenticated_pre_successor_purchase_snapshot(
        **kwargs,
        authority_transition_capability=capability,
        attempt_transition_capability=capability,
    )

    assert observed == [capability, capability]


def _resolved_material_transition_fixture() -> tuple[
    SimpleNamespace,
    CaseDevPurchaseSnapshot,
    dict[str, object],
    list[dict[str, object]],
]:
    policy = SimpleNamespace(
        cycle_id="cycle-1",
        cohort_policy_sha256="cohort-sha",
        policy_sha256="policy-sha",
    )
    pre_resolution: dict[str, object] = {
        "candidate_id": "successor-case",
        "source_document_id": "101",
        "operation_key": "123e4567-e89b-42d3-a456-426614174000",
        "reservation_usd": "3.05",
        "material_state": "recovered_pending_clearance",
        "material_evidence": {
            "content_sha256": "sha256:" + "1" * 64,
            "byte_count": 123,
        },
        "resolved_document_sha256": None,
    }
    record: dict[str, object] = {
        "schema_version": ("legalforecast.resolved_post_recovery_public_document.v3"),
        "candidate_id": "successor-case",
        "source_document_id": "101",
        "recovery_origin": "unknown_status_attempt",
        "operation_key": pre_resolution["operation_key"],
        "delivery_authority": "authenticated_public_material_recovery",
        "purchase_policy_sha256": "1" * 64,
        "attempt_policy_sha256": "2" * 64,
        "selection_document_sha256": "3" * 64,
        "purchase_operation_sha256": canonical_purchase_operation_sha256(
            pre_resolution
        ),
        "fresh_recap_detail_sha256": "4" * 64,
        "download_url_sha256": "5" * 64,
        "download_record_sha256": "6" * 64,
        "content_sha256": "7" * 64,
        "byte_count": 123,
        "clearance_record_sha256": "8" * 64,
        "clearance_run_card_sha256": "9" * 64,
        "clearance_artifact_sha256": "a" * 64,
        "cohort_policy_artifact_sha256": "b" * 64,
        "restriction_evidence_artifact_sha256": "c" * 64,
        "restriction_evidence_rows_sha256": "d" * 64,
        "fresh_detail_public_evidence_sha256": "e" * 64,
        "public_material_recovery_sha256": "f" * 64,
        "restriction_status": "public",
        "parser_eligible": True,
        "packet_eligible": True,
        "clearance_basis": "provider_free_recovered_public",
        "recovered_public_lineage": {},
    }
    record["record_sha256"] = cast(Any, resolved_module)._sha256(record)
    post_resolution = dict(pre_resolution)
    post_resolution["material_state"] = "cleared_public"
    post_resolution["material_evidence"] = {
        **cast(dict[str, object], pre_resolution["material_evidence"]),
        "clearance_record_sha256": record["clearance_record_sha256"],
    }
    post_resolution["resolved_document_sha256"] = record["record_sha256"]
    before_state = canonical_purchase_state_sha256(
        policy,
        committed_amount_usd="3.05",
        operations=(pre_resolution,),
    )
    after_state = canonical_purchase_state_sha256(
        policy,
        committed_amount_usd="3.05",
        operations=(post_resolution,),
    )
    card: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "resolve-post-recovery-documents",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "purchase_state_before_sha256": before_state,
        "purchase_state_after_sha256": after_state,
        "output_commitments": {
            "resolved_post_recovery_documents": {
                "path": "/tmp/resolved.jsonl",
                "sha256": "sha256:" + "4" * 64,
            },
            "purchase_state_sha256": after_state,
        },
    }
    return (
        policy,
        CaseDevPurchaseSnapshot(
            operations=(post_resolution,),
            committed_amount_usd="3.05",
            purchase_state_sha256=after_state,
        ),
        card,
        [record],
    )


def test_resolved_material_transition_reconstructs_exact_before_state() -> None:
    policy, current, card, records = _resolved_material_transition_fixture()
    reconstructed = resolved_module.reconstruct_pre_resolution_purchase_snapshot(
        current_snapshot=current,
        policy=cast(Any, policy),
        resolved_records=records,
        expected_purchase_state_before_sha256=cast(
            str, card["purchase_state_before_sha256"]
        ),
    )

    assert reconstructed.purchase_state_sha256 == card["purchase_state_before_sha256"]
    assert reconstructed.operations[0]["material_state"] == (
        "recovered_pending_clearance"
    )


def test_transition_replay_accepts_exact_frozen_pre_hardening_v4_record() -> None:
    policy, current, card, records = _resolved_material_transition_fixture()
    record = records[0]
    record["schema_version"] = "legalforecast.resolved_post_recovery_public_document.v4"
    record["delivery_authority"] = "authenticated_direct_courtlistener_queue_recovery"
    record["queue_response_sha256"] = record.pop("public_material_recovery_sha256")
    record["record_sha256"] = cast(Any, resolved_module)._sha256(
        {name: value for name, value in record.items() if name != "record_sha256"}
    )
    post = dict(current.operations[0])
    post["resolved_document_sha256"] = record["record_sha256"]
    current = CaseDevPurchaseSnapshot(
        operations=(post,),
        committed_amount_usd=current.committed_amount_usd,
        purchase_state_sha256=canonical_purchase_state_sha256(
            policy,
            committed_amount_usd=current.committed_amount_usd,
            operations=(post,),
        ),
    )

    reconstructed = resolved_module.reconstruct_pre_resolution_purchase_snapshot(
        current_snapshot=current,
        policy=cast(Any, policy),
        resolved_records=records,
        expected_purchase_state_before_sha256=cast(
            str, card["purchase_state_before_sha256"]
        ),
    )

    assert reconstructed.purchase_state_sha256 == card["purchase_state_before_sha256"]


def _raw_transition_card(
    tmp_path: Path,
    *,
    name: str,
    before_state: str,
    after_state: str,
    ledger: Path,
) -> tuple[Path, Path]:
    source = _write_json(tmp_path / f"{name}-source.json", {"name": name})
    resolved = _write_jsonl(tmp_path / f"{name}-resolved.jsonl", [{"name": name}])
    card = _write_json(
        tmp_path / f"{name}-run-card.json",
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "resolve-post-recovery-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "input_paths": [str(source.resolve()), str(ledger.resolve())],
            "source_commitments": _source_commitments([source, ledger]),
            "output_paths": [str(resolved.resolve()), str(ledger.resolve())],
            "output_commitments": {
                "resolved_post_recovery_documents": _commitment(resolved),
                "purchase_state_sha256": after_state,
            },
            "purchase_state_before_sha256": before_state,
            "purchase_state_after_sha256": after_state,
        },
    )
    return card, source


def test_resolved_transition_capability_is_live_bound_reusable_and_source_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, current, _card, _records = _resolved_material_transition_fixture()
    prior = CaseDevPurchaseSnapshot(
        operations=(),
        committed_amount_usd=current.committed_amount_usd,
        purchase_state_sha256="1" * 64,
    )
    ledger = tmp_path / "ledger.sqlite3"
    ledger.write_bytes(b"ledger")
    receipt = _write_json(tmp_path / "receipt.json", {"receipt": True})
    card_path, source_path = _raw_transition_card(
        tmp_path,
        name="one",
        before_state=prior.purchase_state_sha256,
        after_state=current.purchase_state_sha256,
        ledger=ledger,
    )
    monkeypatch.setattr(
        approval_module,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: current,
    )
    monkeypatch.setattr(
        approval_module,
        "reconstruct_pre_resolution_purchase_snapshot",
        lambda **_kwargs: prior,
    )
    capability = approval_module._issue_resolved_transition_capability(  # pyright: ignore[reportPrivateUsage]
        purchase_ledger_path=ledger,
        policy=policy,
        controlled_private_root=tmp_path / "private",
        initialization_receipt_path=receipt,
        run_card_paths=(card_path,),
    )

    authority = approval_module._consume_resolved_transition_capability(capability)  # pyright: ignore[reportPrivateUsage]
    assert authority.ledger_path == ledger.resolve()
    assert authority.current_snapshot == current
    assert authority.prior_snapshot == prior
    assert (  # pyright: ignore[reportPrivateUsage]
        approval_module._consume_resolved_transition_capability(capability) == authority
    )
    source_path.write_bytes(b'{"name":"changed"}\n')
    with pytest.raises(
        approval_module.ReplacementPurchaseApprovalError,
        match="resolved transition source changed",
    ):
        approval_module._consume_resolved_transition_capability(capability)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("symlink_kind", ["run_card", "committed_input"])
def test_resolved_transition_raw_evidence_rejects_symlinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    symlink_kind: str,
) -> None:
    policy, current, _card, _records = _resolved_material_transition_fixture()
    ledger = tmp_path / "ledger.sqlite3"
    ledger.write_bytes(b"ledger")
    receipt = _write_json(tmp_path / "receipt.json", {"receipt": True})
    card_path, source_path = _raw_transition_card(
        tmp_path,
        name="symlink",
        before_state="1" * 64,
        after_state=current.purchase_state_sha256,
        ledger=ledger,
    )
    monkeypatch.setattr(
        approval_module,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: current,
    )
    if symlink_kind == "run_card":
        linked_card = tmp_path / "linked-run-card.json"
        linked_card.symlink_to(card_path)
        card_path = linked_card
    else:
        linked_source = tmp_path / "linked-source.json"
        linked_source.symlink_to(source_path)
        card = json.loads(card_path.read_bytes())
        card["input_paths"][0] = str(linked_source.absolute())
        card["source_commitments"]["input_00"]["path"] = str(linked_source.absolute())
        _write_json(card_path, card)

    with pytest.raises(ValueError, match="cannot be safely read"):
        approval_module._issue_resolved_transition_capability(  # pyright: ignore[reportPrivateUsage]
            purchase_ledger_path=ledger,
            policy=policy,
            controlled_private_root=tmp_path / "private",
            initialization_receipt_path=receipt,
            run_card_paths=(card_path,),
        )


def test_live_transition_prior_consumer_owns_coordinates_and_rechecks_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, current, _card, _records = _resolved_material_transition_fixture()
    prior = CaseDevPurchaseSnapshot(
        operations=(),
        committed_amount_usd=current.committed_amount_usd,
        purchase_state_sha256="1" * 64,
    )
    observed: list[dict[str, object]] = []
    live_snapshot = current

    def read_snapshot(*_args: object, **kwargs: object) -> CaseDevPurchaseSnapshot:
        observed.append(kwargs)
        return live_snapshot

    monkeypatch.setattr(
        approval_module,
        "read_case_dev_purchase_snapshot",
        read_snapshot,
    )
    private_root = tmp_path / "private"
    ledger = tmp_path / "ledger.sqlite3"
    ledger.write_bytes(b"ledger")
    receipt = _write_json(tmp_path / "receipt.json", {"receipt": True})
    card_path, _source_path = _raw_transition_card(
        tmp_path,
        name="live",
        before_state=prior.purchase_state_sha256,
        after_state=current.purchase_state_sha256,
        ledger=ledger,
    )
    monkeypatch.setattr(
        approval_module,
        "reconstruct_pre_resolution_purchase_snapshot",
        lambda **_kwargs: prior,
    )
    capability = approval_module._issue_resolved_transition_capability(  # pyright: ignore[reportPrivateUsage]
        purchase_ledger_path=ledger,
        policy=policy,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt,
        run_card_paths=(card_path,),
    )

    prior = approval_module._consume_live_resolved_transition_prior_snapshot(  # pyright: ignore[reportPrivateUsage]
        capability
    )
    assert prior.purchase_state_sha256 == "1" * 64
    assert observed[-1]["policy"] is policy
    assert observed[-1]["controlled_private_root"] == private_root.resolve()
    assert observed[-1]["initialization_receipt_path"] == receipt.resolve()

    live_snapshot = CaseDevPurchaseSnapshot(
        operations=current.operations,
        committed_amount_usd=current.committed_amount_usd,
        purchase_state_sha256="ledger-changed-after-issuance",
    )
    with pytest.raises(
        approval_module.ReplacementPurchaseApprovalError,
        match="differs from the live purchase journal",
    ):
        approval_module._consume_live_resolved_transition_prior_snapshot(capability)  # pyright: ignore[reportPrivateUsage]


def test_resolved_transition_capability_replays_two_ordered_transitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = SimpleNamespace(
        cycle_id="cycle-1",
        cohort_policy_sha256="cohort-sha",
        policy_sha256="policy-sha",
    )

    def pending(document_id: str) -> dict[str, object]:
        return {
            "candidate_id": f"case-{document_id}",
            "source_document_id": document_id,
            "operation_key": f"operation-{document_id}",
            "reservation_usd": "3.05",
            "material_state": "recovered_pending_clearance",
            "material_evidence": {"content_sha256": document_id * 64},
            "resolved_document_sha256": None,
        }

    def resolved(
        operation: Mapping[str, object], marker: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        record = {
            "candidate_id": operation["candidate_id"],
            "source_document_id": operation["source_document_id"],
            "purchase_operation_sha256": canonical_purchase_operation_sha256(operation),
            "record_sha256": marker * 64,
            "clearance_record_sha256": marker.upper() * 64,
        }
        cleared = dict(operation)
        cleared["material_state"] = "cleared_public"
        cleared["material_evidence"] = {
            **cast(Mapping[str, object], operation["material_evidence"]),
            "clearance_record_sha256": record["clearance_record_sha256"],
        }
        cleared["resolved_document_sha256"] = record["record_sha256"]
        return cleared, record

    pending_a = pending("1")
    pending_b = pending("2")
    cleared_a, _record_a = resolved(pending_a, "a")
    cleared_b, _record_b = resolved(pending_b, "b")
    prior_operations = (pending_a, pending_b)
    intermediate_operations = (pending_a, cleared_b)
    current_operations = (cleared_a, cleared_b)

    def state(operations: tuple[Mapping[str, object], ...]) -> str:
        return canonical_purchase_state_sha256(
            policy, committed_amount_usd="6.10", operations=operations
        )

    def card(before: str, after: str) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "resolve-post-recovery-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "purchase_state_before_sha256": before,
            "purchase_state_after_sha256": after,
            "output_commitments": {
                "resolved_post_recovery_documents": {
                    "path": "/tmp/resolved.jsonl",
                    "sha256": "sha256:" + "4" * 64,
                },
                "purchase_state_sha256": after,
            },
        }

    current = CaseDevPurchaseSnapshot(
        operations=current_operations,
        committed_amount_usd="6.10",
        purchase_state_sha256=state(current_operations),
    )
    ledger = tmp_path / "ledger.sqlite3"
    ledger.write_bytes(b"ledger")
    receipt = _write_json(tmp_path / "receipt.json", {"receipt": True})
    first_path, _ = _raw_transition_card(
        tmp_path,
        name="first",
        before_state=state(intermediate_operations),
        after_state=state(current_operations),
        ledger=ledger,
    )
    second_path, _ = _raw_transition_card(
        tmp_path,
        name="second",
        before_state=state(prior_operations),
        after_state=state(intermediate_operations),
        ledger=ledger,
    )
    monkeypatch.setattr(
        approval_module,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: current,
    )
    observed_states: list[str] = []

    def reconstruct(**kwargs: Any) -> CaseDevPurchaseSnapshot:
        snapshot = cast(CaseDevPurchaseSnapshot, kwargs["current_snapshot"])
        observed_states.append(snapshot.purchase_state_sha256)
        if snapshot.purchase_state_sha256 == state(current_operations):
            return CaseDevPurchaseSnapshot(
                operations=intermediate_operations,
                committed_amount_usd="6.10",
                purchase_state_sha256=state(intermediate_operations),
            )
        if snapshot.purchase_state_sha256 == state(intermediate_operations):
            return CaseDevPurchaseSnapshot(
                operations=prior_operations,
                committed_amount_usd="6.10",
                purchase_state_sha256=state(prior_operations),
            )
        pytest.fail("transition order changed")

    monkeypatch.setattr(
        approval_module, "reconstruct_pre_resolution_purchase_snapshot", reconstruct
    )
    capability = approval_module._issue_resolved_transition_capability(  # pyright: ignore[reportPrivateUsage]
        purchase_ledger_path=ledger,
        policy=policy,
        controlled_private_root=tmp_path / "private",
        initialization_receipt_path=receipt,
        run_card_paths=(first_path, second_path),
    )
    authority = approval_module._consume_resolved_transition_capability(  # pyright: ignore[reportPrivateUsage]
        capability
    )
    assert authority.prior_snapshot.operations == prior_operations
    assert authority.prior_snapshot.purchase_state_sha256 == state(prior_operations)
    assert observed_states == [
        state(current_operations),
        state(intermediate_operations),
    ]


@pytest.mark.parametrize(
    "mutation",
    ["billing", "identity", "unbound_material", "record_binding", "before_state"],
)
def test_authenticated_resolved_material_transition_rejects_nonexact_change(
    mutation: str,
) -> None:
    policy, current, card, records = _resolved_material_transition_fixture()
    operations = [dict(current.operations[0])]
    if mutation == "billing":
        operations[0]["reservation_usd"] = "0.01"
    elif mutation == "identity":
        operations[0]["operation_key"] = "operation-2"
    elif mutation == "unbound_material":
        operations[0]["material_evidence"] = {
            **cast(dict[str, object], operations[0]["material_evidence"]),
            "unexpected": True,
        }
    elif mutation == "record_binding":
        records[0]["record_sha256"] = "5" * 64
    else:
        card["purchase_state_before_sha256"] = "0" * 64
    mutated = CaseDevPurchaseSnapshot(
        operations=tuple(operations),
        committed_amount_usd=current.committed_amount_usd,
        purchase_state_sha256=(
            canonical_purchase_state_sha256(
                policy,
                committed_amount_usd=current.committed_amount_usd,
                operations=operations,
            )
            if mutation in {"billing", "identity", "unbound_material"}
            else current.purchase_state_sha256
        ),
    )
    cast(dict[str, object], card["output_commitments"])["purchase_state_sha256"] = (
        mutated.purchase_state_sha256
    )
    card["purchase_state_after_sha256"] = mutated.purchase_state_sha256

    with pytest.raises(
        resolved_module.ResolvedPostRecoveryError,
        match=r"hash changed|clearance binding|operation commitment|prior state",
    ):
        resolved_module.reconstruct_pre_resolution_purchase_snapshot(
            current_snapshot=mutated,
            policy=cast(Any, policy),
            resolved_records=records,
            expected_purchase_state_before_sha256=cast(
                str, card["purchase_state_before_sha256"]
            ),
        )


def test_authenticated_successor_history_threads_trailing_pairs_to_attempt_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kwargs, _ = _successor_history_helper_fixture(tmp_path, monkeypatch)
    trailing = {("later-case", "999")}
    observed: list[tuple[set[tuple[str, str]] | None, object | None]] = []

    def capture_attempt(*_args: object, **call_kwargs: object) -> None:
        observed.append(
            call_kwargs.get("allowed_additional_operation_pairs")  # type: ignore[arg-type]
        )

    monkeypatch.setattr(cli, "verify_recap_fetch_attempt_policy", capture_attempt)

    cli._authenticated_pre_successor_purchase_snapshot(
        **kwargs,
        allowed_additional_operation_pairs=trailing,
    )

    assert observed == [trailing]


def test_attempt_policy_nested_authority_replay_receives_trailing_pairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = SimpleNamespace(
        has_verified_approval=True,
        canonical_ledger_path=tmp_path / "ledger.sqlite3",
        per_document_reservation_usd=Decimal("3.05"),
        hard_cap_usd=Decimal("600.00"),
        opening_committed_spend_usd=Decimal("0.00"),
        opening_case_committed_spend_usd={},
        max_per_case_usd=Decimal("30.50"),
        cycle_id="cycle-1",
        policy_sha256="policy-sha",
        cohort_policy_sha256="cohort-sha",
    )
    budget_plan = SimpleNamespace(
        dry_run=False,
        total_estimated_cost=Decimal("3.05"),
        case_plans=(
            SimpleNamespace(candidate_id="case-1", purchase_document_ids=("101",)),
        ),
    )
    selection_records = (
        {
            "candidate_id": "case-1",
            "selected": True,
            "exclusion_reasons": [],
            "documents": [
                {
                    "source_document_id": "101",
                    "redaction_or_seal_status": "unknown",
                    "restriction_evidence": list(
                        attempt_module.UNKNOWN_STATUS_EVIDENCE
                    ),
                    "is_sealed": None,
                    "is_private": None,
                    "is_available": False,
                    "availability_status": "unavailable",
                    "requires_paid_recovery": True,
                }
            ],
        },
    )
    monkeypatch.setattr(
        attempt_module, "verify_case_dev_purchase_policy", lambda _artifact: policy
    )
    monkeypatch.setattr(
        attempt_module,
        "require_approved_case_dev_purchase_policy",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        attempt_module,
        "_require_structured_inputs_match_authenticated_bytes",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        attempt_module,
        "verify_case_dev_purchase_policy_cohort_binding",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        attempt_module,
        "validate_recap_fetch_budget_plan_artifact",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        attempt_module,
        "verify_approved_purchase_input_bytes",
        lambda *_args, **_kwargs: None,
    )
    observed: list[tuple[object, object]] = []
    monkeypatch.setattr(
        approval_module,
        "verify_replacement_purchase_authority",
        lambda **kwargs: observed.append(
            (
                kwargs.get("allowed_additional_operation_pairs"),
                kwargs.get("_verified_resolved_transition_capability"),
            )
        ),
    )
    common = {
        "purchase_policy_artifact": {"policy": "fixture"},
        "cohort_policy_artifact": {"cohort": "fixture"},
        "budget_plan": budget_plan,
        "budget_plan_artifact": {"budget": "fixture"},
        "selection_records": selection_records,
        "budget_plan_bytes": b"budget",
        "selection_bytes": b"selection",
        "controlled_private_root": tmp_path / "initial-private",
        "replacement_purchase_authority_artifact": {"authority": "fixture"},
        "replacement_controlled_private_root": tmp_path / "successor-private",
        "purchase_ledger_initialization_receipt_path": tmp_path / "receipt.json",
    }
    expected = attempt_module._build_recap_fetch_attempt_policy(
        **common,
        require_fresh_ledger_namespace=False,
        allowed_additional_operation_pairs=None,
    )
    observed.clear()
    trailing = {("later-case", "202")}
    transition_capability = object()
    nonreplacement = {
        **common,
        "replacement_purchase_authority_artifact": None,
        "replacement_controlled_private_root": None,
        "purchase_ledger_initialization_receipt_path": None,
    }
    with pytest.raises(
        attempt_module.RecapFetchAttemptPolicyError,
        match="requires complete replacement authority",
    ):
        attempt_module.verify_recap_fetch_attempt_policy(
            expected,
            **nonreplacement,
            _verified_resolved_transition_capability=transition_capability,
        )

    attempt_module.verify_recap_fetch_attempt_policy(
        expected,
        **common,
        allowed_additional_operation_pairs=trailing,
        _verified_resolved_transition_capability=transition_capability,
    )

    assert observed == [(trailing, transition_capability)]


@pytest.mark.parametrize(
    ("argument", "label"),
    [
        ("expected_selection_path", "selection"),
        ("expected_budget_plan_path", "budget plan"),
        ("expected_authority_path", "purchase authority"),
    ],
)
def test_authenticated_successor_history_rejects_descriptor_path_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argument: str,
    label: str,
) -> None:
    kwargs, _ = _successor_history_helper_fixture(tmp_path, monkeypatch)

    with pytest.raises(
        cli.ReplacementRecoverySourceError,
        match=rf"{label} path differs from its descriptor",
    ):
        cli._authenticated_pre_successor_purchase_snapshot(
            **kwargs,
            **{argument: tmp_path / "other-source"},
        )


@pytest.mark.parametrize(
    "mutation",
    ["arbitrary_extra", "missing_successor", "changed_baseline", "overlap"],
)
def test_authenticated_successor_history_rejects_nonexact_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    kwargs, paths = _successor_history_helper_fixture(tmp_path, monkeypatch)
    snapshot = kwargs["current_snapshot"]
    assert isinstance(snapshot, CaseDevPurchaseSnapshot)
    operations = list(snapshot.operations)
    if mutation == "arbitrary_extra":
        operations.append(
            {
                "candidate_id": "unapproved-case",
                "source_document_id": "999",
                "reservation_usd": "3.05",
            }
        )
    elif mutation == "missing_successor":
        operations.pop()
    elif mutation == "changed_baseline":
        operations[0] = {**operations[0], "reservation_usd": "0.01"}
    else:
        budget = json.loads(paths["budget"].read_bytes())
        budget["case_plans"][0]["candidate_id"] = "initial-case"
        budget["case_plans"][0]["purchase_document_ids"][0] = "1"
        _write_json(paths["budget"], budget)
    kwargs["current_snapshot"] = CaseDevPurchaseSnapshot(
        operations=tuple(operations),
        committed_amount_usd=snapshot.committed_amount_usd,
        purchase_state_sha256=snapshot.purchase_state_sha256,
    )

    with pytest.raises(
        cli.ReplacementRecoverySourceError,
        match=(
            r"outside the approved successor tranche|exactly partition|overlaps|"
            r"baseline operations are missing"
        ),
    ):
        cli._authenticated_pre_successor_purchase_snapshot(**kwargs)


def test_producer_dry_run_emits_card_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args, _, _ = _fixture(tmp_path, monkeypatch, successor=False)
    args.execute = False

    assert cli._cmd_build_replacement_recovery_source(args) == 0

    card = json.loads(capsys.readouterr().out)
    assert card["dry_run"] is True
    assert card["execute"] is False
    assert card["provider_activity_requested"] is False
    assert card["paid_activity_requested"] is False
    assert not args.output_root.exists()


def test_cli_routes_recovery_source_producer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args, _, _ = _fixture(tmp_path, monkeypatch, successor=False)

    assert (
        cli.main(
            [
                "acquisition",
                "build-replacement-recovery-source",
                "--output-root",
                str(args.output_root),
                "--ordinal",
                str(args.ordinal),
                "--recovery-root",
                str(args.recovery_root),
                "--purchased-clearance-run-card",
                str(args.purchased_clearance_run_card),
                "--resolved-post-recovery-run-card",
                str(args.resolved_post_recovery_run_card),
                "--purchase-policy",
                str(args.purchase_policy),
                "--cohort-policy",
                str(args.cohort_policy),
                "--purchase-ledger",
                str(args.purchase_ledger),
                "--initial-controlled-private-root",
                str(args.initial_controlled_private_root),
                "--purchase-ledger-initialization-receipt",
                str(args.purchase_ledger_initialization_receipt),
            ]
        )
        == 0
    )

    card = json.loads(capsys.readouterr().out)
    assert card["stage"] == "build-replacement-recovery-source"
    assert card["kind"] == "initial_v2"


def test_source_producer_help_names_terminal_disposition_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["acquisition", "build-replacement-recovery-source", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for flag in (
        "--additional-resolved-post-recovery-run-card",
        "--terminal-disposition-selection",
        "--terminal-disposition-snapshot-manifest",
        "--terminal-purchase-result",
        "--terminal-purchase-run-card",
    ):
        assert flag in help_text


def test_source_producer_requires_complete_terminal_disposition_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, paths, _ = _fixture(tmp_path, monkeypatch, successor=False)
    args.terminal_disposition_selection = paths["selection"]

    with pytest.raises(cli.CommandError, match="must be supplied together"):
        cli._cmd_build_replacement_recovery_source(args)
