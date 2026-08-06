from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as cli
import pytest


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
    manifest = _write_jsonl(
        recovery_root / "purchased-document-downloads-quarantine.jsonl",
        [{"candidate_id": candidate_id, "source_document_id": document_id}],
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
        },
    )
    verified_calls: list[dict[str, Any]] = []

    def verify_recovery(**kwargs: Any) -> dict[str, object]:
        verified_calls.append({"recovery": kwargs})
        assert Path(kwargs["selection_path"]).resolve() == selection.resolve()
        assert kwargs["purchase_operations"] == [
            {"candidate_id": candidate_id, "source_document_id": document_id}
        ]
        assert kwargs["purchase_committed_amount_usd"] == "3.05"
        assert kwargs["purchase_state_sha256"] == "state-1"
        return {
            "recovery_stage": "recover-recap-fetch-quarantine",
            "manifest_path": manifest,
            "manifest_records": [
                {"candidate_id": candidate_id, "source_document_id": document_id}
            ],
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
        lambda _artifact: SimpleNamespace(canonical_ledger_path=ledger.resolve()),
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
        cli, "verify_recap_fetch_attempt_policy", lambda *_args, **_kwargs: None
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
