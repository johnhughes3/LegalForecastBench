from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as cli
import pytest


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )
    return path


def _document(candidate_id: str, document_id: str) -> dict[str, object]:
    digest = hashlib.sha256(f"{candidate_id}/{document_id}".encode()).hexdigest()
    return {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "sha256": digest,
        "byte_count": 1,
        "free_or_purchased": "purchased",
        "status": "cleared",
    }


def _fake_clearance(
    root: Path, candidate_id: str, document_id: str
) -> tuple[Path, Path]:
    record = _document(candidate_id, document_id)
    manifest = _write_jsonl(root / "purchased-document-downloads.jsonl", [record])
    restriction = _write_jsonl(root / "restriction-evidence.jsonl", [record])
    clearance = _write_jsonl(root / "disclosure-clearance.jsonl", [record])
    card = _write_json(
        root / "run-cards/clear-provenance-disclosures.json",
        {
            "schema_version": "test.clearance.v1",
            "source_commitments": {
                "download_manifest": {
                    "path": str(manifest.resolve()),
                    "sha256": "sha256:"
                    + hashlib.sha256(manifest.read_bytes()).hexdigest(),
                },
                "restriction_evidence": {
                    "path": str(restriction.resolve()),
                    "sha256": (
                        "sha256:" + hashlib.sha256(restriction.read_bytes()).hexdigest()
                    ),
                },
            },
        },
    )
    return clearance, card


def test_two_tranches_accumulate_clearance_without_hand_assembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_clearance, base_card = _fake_clearance(tmp_path / "base", "kept", "1")
    first_clearance, first_card = _fake_clearance(tmp_path / "first", "promoted", "2")
    second_clearance, second_card = _fake_clearance(
        tmp_path / "second", "promoted-again", "3"
    )
    policy_path = _write_json(tmp_path / "policy.json", {"policy": "fixture"})
    receipt_path = _write_json(tmp_path / "receipt.json", {"receipt": "fixture"})
    ledger_path = (tmp_path / "ledger.sqlite3").resolve()
    private_root = (tmp_path / "private").resolve()
    private_root.mkdir()
    policy = SimpleNamespace(canonical_ledger_path=ledger_path)
    monkeypatch.setattr(cli, "verify_case_dev_purchase_policy", lambda _value: policy)
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    operation_pairs = {("kept", "1"), ("promoted", "2")}

    def snapshot(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            operations=tuple(
                {
                    "candidate_id": candidate_id,
                    "source_document_id": document_id,
                    "status": "confirmed",
                }
                for candidate_id, document_id in sorted(operation_pairs)
            ),
            purchase_state_sha256="a" * 64,
        )

    monkeypatch.setattr(cli, "read_case_dev_purchase_snapshot", snapshot)
    original_verify = cli._verify_replacement_clearance_evidence

    def verify_clearance(**kwargs: Any) -> list[dict[str, Any]]:
        card = json.loads(kwargs["run_card_bytes"])
        if card.get("schema_version") == "test.clearance.v1":
            return json.loads("[" + kwargs["clearance_bytes"].decode().strip() + "]")
        return original_verify(**kwargs)

    monkeypatch.setattr(cli, "_verify_replacement_clearance_evidence", verify_clearance)

    def args(
        *,
        output_root: Path,
        prior_clearance: Path,
        prior_card: Path,
        current_clearance: Path,
        current_card: Path,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            output_root=output_root,
            prior_purchased_clearance=prior_clearance,
            prior_clearance_run_card=prior_card,
            current_purchased_clearance=current_clearance,
            current_clearance_run_card=current_card,
            purchase_policy=policy_path,
            purchase_ledger=ledger_path,
            controlled_private_root=private_root,
            purchase_ledger_initialization_receipt=receipt_path,
            run_card_output=None,
            execute=True,
            resume=False,
        )

    first_root = tmp_path / "cumulative-one"
    assert (
        cli._cmd_accumulate_replacement_clearance(
            args(
                output_root=first_root,
                prior_clearance=base_clearance,
                prior_card=base_card,
                current_clearance=first_clearance,
                current_card=first_card,
            )
        )
        == 0
    )
    operation_pairs.add(("promoted-again", "3"))
    second_root = tmp_path / "cumulative-two"
    assert (
        cli._cmd_accumulate_replacement_clearance(
            args(
                output_root=second_root,
                prior_clearance=first_root / "disclosure-clearance.jsonl",
                prior_card=(
                    first_root / "run-cards" / "accumulate-replacement-clearance.json"
                ),
                current_clearance=second_clearance,
                current_card=second_card,
            )
        )
        == 0
    )
    final_rows = [
        json.loads(line)
        for line in (second_root / "disclosure-clearance.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {
        (row["candidate_id"], row["source_document_id"]) for row in final_rows
    } == operation_pairs


def test_cumulative_clearance_rejects_changed_committed_manifest(
    tmp_path: Path,
) -> None:
    _clearance, card_path = _fake_clearance(tmp_path / "clearance", "case", "1")
    card = json.loads(card_path.read_text(encoding="utf-8"))
    manifest_path = Path(card["source_commitments"]["download_manifest"]["path"])
    manifest_path.write_text(
        json.dumps({**_document("case", "1"), "byte_count": 999}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        cli.ClearanceReplacementError,
        match="commitment",
    ):
        cli._clearance_card_artifact_snapshots(card)


def test_successor_exclusions_remove_promoted_old_exclusion_and_add_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection = _write_jsonl(
        tmp_path / "projection/target-cohort-selection.jsonl",
        [{"candidate_id": "kept"}, {"candidate_id": "promoted"}],
    )
    projection_card = _write_json(
        tmp_path / "projection/run-cards/project-target-cohort.json",
        {"fixture": "projection"},
    )
    replacement_result = _write_json(
        tmp_path / "replacement-result.json",
        {
            "ledger_records": [
                {
                    "quarantined_candidate_id": "quarantined-original",
                    "quarantined_document_ids": ["10"],
                    "record_sha256": "sha256:" + "1" * 64,
                }
            ],
            "derived_exclusions": [],
        },
    )
    screened = _write_jsonl(
        tmp_path / "screened-cases.jsonl",
        [
            {"candidate": {"docket_id": candidate_id}}
            for candidate_id in ("kept", "promoted", "quarantined-original")
        ],
    )
    old_exclusions = _write_jsonl(
        tmp_path / "old-target-exclusions.jsonl",
        [
            {
                "candidate_id": "promoted",
                "case_id": "promoted",
                "stage": "eligibility",
                "reason": "target_clean_case_cap_reached",
            }
        ],
    )
    replay_inputs = [str(tmp_path / f"unused-{index}") for index in range(19)]
    replay_inputs[9] = str(replacement_result)
    replacement_result_bytes = replacement_result.read_bytes()
    verified_projection = {
        "selection_path": selection,
        "selection_records": [
            {"candidate_id": "kept"},
            {"candidate_id": "promoted"},
        ],
        "run_card": {"input_paths": replay_inputs},
        "run_card_path": projection_card,
        "verified_artifact_bytes": {
            str(projection_card.resolve()): projection_card.read_bytes(),
            str(selection.resolve()): selection.read_bytes(),
            str(replacement_result.resolve()): replacement_result_bytes,
        },
    }
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: verified_projection,
    )
    captured_sources = {
        **verified_projection["verified_artifact_bytes"],
        str(screened.resolve()): screened.read_bytes(),
        str(old_exclusions.resolve()): old_exclusions.read_bytes(),
    }
    replacement_result.write_text('{"tampered":true}\n', encoding="utf-8")
    old_exclusions.write_text('{"tampered":true}\n', encoding="utf-8")

    prepared = cli._prepare_replacement_exclusions(
        target_root=selection.parent,
        screened_cases_path=screened,
        exclusion_paths=(old_exclusions,),
        verified_projection=verified_projection,
        captured_source_bytes=captured_sources,
    )

    assert [row["candidate_id"] for row in prepared.records] == ["quarantined-original"]
    assert prepared.selected_candidate_ids == ("kept", "promoted")


def test_finalize_consumes_verified_successor_exclusion_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    successor = tmp_path / "successor-target-exclusions.jsonl"
    other = _write_jsonl(
        tmp_path / "other-exclusions.jsonl",
        [{"candidate_id": "other"}],
    )
    verified = ({"candidate_id": "quarantined"},)
    monkeypatch.setattr(
        cli,
        "_verify_replacement_exclusion_card",
        lambda **_kwargs: verified,
    )
    original_read = cli._read_records

    def read_records(path: Path) -> list[dict[str, Any]]:
        if path.resolve() == successor.resolve():
            raise AssertionError("verified successor exclusion was reopened")
        return original_read(path)

    monkeypatch.setattr(cli, "_read_records", read_records)

    groups = cli._replacement_finalization_exclusion_groups(
        exclusion_paths=(other, successor),
        replacement_exclusion_card_path=tmp_path / "successor-card.json",
        selection_path=tmp_path / "selection.jsonl",
        screened_cases_path=tmp_path / "screened.jsonl",
    )

    assert groups == ([{"candidate_id": "other"}], list(verified))


def test_finalize_rejects_successor_exclusions_without_authentication_card(
    tmp_path: Path,
) -> None:
    successor = _write_jsonl(
        tmp_path / "successor-target-exclusions.jsonl",
        [{"candidate_id": "quarantined"}],
    )

    with pytest.raises(
        cli.CommandError,
        match="requires --replacement-exclusion-run-card",
    ):
        cli._replacement_finalization_exclusion_groups(
            exclusion_paths=(successor,),
            replacement_exclusion_card_path=None,
            selection_path=tmp_path / "selection.jsonl",
            screened_cases_path=tmp_path / "screened.jsonl",
        )


def test_authority_bound_replacement_selection_is_valid_recovery_relevance() -> None:
    replacement_selection = [
        {
            "candidate_id": "replacement",
            "selected": False,
            "exclusion_reasons": ["reserve_for_clearance_replacement"],
            "documents": [
                {
                    "source_document_id": "20",
                    "redaction_or_seal_status": "public",
                    "restriction_evidence": [
                        "courtlistener_rest_recap_document_is_sealed_false"
                    ],
                    "availability_status": "unavailable",
                    "requires_paid_recovery": True,
                    "is_sealed": False,
                    "is_private": None,
                }
            ],
        }
    ]
    recovered = [
        {
            "candidate_id": "replacement",
            "source_document_id": "20",
            "free_or_purchased": "purchased",
        }
    ]

    projected = cli._project_purchased_case_relevance(
        replacement_selection,
        recovered,
    )

    assert projected == tuple(replacement_selection)


def test_finalize_reconciliation_rejects_selected_excluded_overlap() -> None:
    reconciliation = SimpleNamespace(
        accepted_count=2,
        excluded_count=0,
        processed_count=2,
    )
    with pytest.raises(
        cli.CommandError,
        match="selected xor excluded",
    ):
        cli._validate_acquisition_discovery_reconciliation(
            screened_case_records=[
                {"candidate": {"docket_id": "selected"}},
                {"candidate": {"docket_id": "other"}},
            ],
            discovery_reconciliation=reconciliation,
            discovery_exclusion_records=[],
            selection_records=[{"candidate_id": "selected"}],
            complete_ledger_records=[
                {"candidate_id": "selected"},
                {"candidate_id": "other"},
            ],
        )
