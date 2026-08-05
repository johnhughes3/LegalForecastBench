from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

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


def _prepare_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    ledger_pairs: set[tuple[str, str]],
) -> tuple[argparse.Namespace, list[set[tuple[str, str]]]]:
    selection_rows = [
        {
            "candidate_id": candidate_id,
            "documents": [{"source_document_id": document_id}],
        }
        for candidate_id, document_id in (
            ("base-case", "base-doc"),
            ("case-1", "doc-1"),
            ("case-2", "doc-2"),
        )
    ]
    selection = _write_jsonl(tmp_path / "active-selection.jsonl", selection_rows)
    purchased_manifest = _write_jsonl(
        tmp_path / "purchased-document-downloads.jsonl",
        [
            {"candidate_id": candidate_id, "source_document_id": document_id}
            for candidate_id, document_id in (
                ("base-case", "base-doc"),
                ("case-1", "doc-1"),
                ("case-2", "doc-2"),
            )
        ],
    )
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "selection_path": selection,
            "selection_records": selection_rows,
            "purchased_manifest": [
                {"candidate_id": candidate_id, "source_document_id": document_id}
                for candidate_id, document_id in (
                    ("base-case", "base-doc"),
                    ("case-1", "doc-1"),
                    ("case-2", "doc-2"),
                )
            ],
        },
    )
    policy_path = _write_json(tmp_path / "policy.json", {"fixture": "policy"})
    cohort_path = _write_json(tmp_path / "cohort.json", {"fixture": "cohort"})
    receipt_path = _write_json(tmp_path / "receipt.json", {"fixture": "receipt"})
    ledger = (tmp_path / "ledger.sqlite3").resolve()
    private_root = (tmp_path / "private").resolve()
    private_root.mkdir()
    sources: list[dict[str, object]] = []
    recovery_by_root: dict[Path, dict[str, object]] = {}
    clearance_by_path: dict[Path, dict[str, object]] = {}
    initial_root = (tmp_path / "initial" / "recovery").resolve()
    initial_document_root = initial_root / "documents/purchased"
    initial_document_root.mkdir(parents=True)
    initial_payload = b"%PDF-1.4 initial\n"
    (initial_document_root / "document.pdf").write_bytes(initial_payload)
    initial_digest = hashlib.sha256(initial_payload).hexdigest()
    initial_manifest_record = {
        "candidate_id": "base-case",
        "source_document_id": "base-doc",
        "local_path": "document.pdf",
        "sha256": initial_digest,
        "byte_count": len(initial_payload),
        "free_or_purchased": "purchased",
    }
    initial_clearance_record = {**initial_manifest_record, "status": "cleared"}
    initial_selection = _write_jsonl(
        tmp_path / "initial" / "selection.jsonl",
        [
            {
                "candidate_id": "base-case",
                "documents": [{"source_document_id": "base-doc"}],
            }
        ],
    )
    initial_clearance = _write_jsonl(
        tmp_path / "initial" / "clearance.jsonl", [initial_clearance_record]
    )
    initial_card = _write_json(
        tmp_path / "initial" / "clearance-card.json", {"fixture": "initial-clearance"}
    )
    sources.append(
        {
            "kind": "initial_v2",
            "ordinal": 0,
            "recovery_root": str(initial_root),
            "selection": str(initial_selection),
            "purchased_clearance": str(initial_clearance),
            "purchased_clearance_run_card": str(initial_card),
            "resolved_post_recovery_documents": None,
        }
    )
    recovery_by_root[initial_root] = {
        "manifest_path": initial_root / "purchased-document-downloads.jsonl",
        "manifest_records": [initial_manifest_record],
        "document_root": initial_document_root,
    }
    clearance_by_path[initial_clearance] = {
        "clearance_records": [initial_clearance_record],
        "restriction_records": [],
    }
    for index, (candidate_id, document_id) in enumerate(
        (("case-1", "doc-1"), ("case-2", "doc-2")), start=1
    ):
        root = (tmp_path / f"tranche-{index}" / "recovery").resolve()
        document_root = root / "documents/purchased"
        document_root.mkdir(parents=True)
        payload = f"%PDF-1.4 tranche {index}\n".encode()
        (document_root / "document.pdf").write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        manifest_record = {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "local_path": "document.pdf",
            "sha256": digest,
            "byte_count": len(payload),
            "free_or_purchased": "purchased",
        }
        clearance_record = {
            **manifest_record,
            "status": "cleared",
        }
        tranche_selection = _write_jsonl(
            tmp_path / f"tranche-{index}" / "selection.jsonl",
            [
                {
                    "candidate_id": candidate_id,
                    "documents": [{"source_document_id": document_id}],
                }
            ],
        )
        budget = _write_json(
            tmp_path / f"tranche-{index}" / "budget.json",
            {
                "case_plans": [
                    {
                        "candidate_id": candidate_id,
                        "purchase_document_ids": [document_id],
                    }
                ]
            },
        )
        clearance_path = _write_jsonl(
            tmp_path / f"tranche-{index}" / "clearance.jsonl",
            [clearance_record],
        )
        clearance_card = _write_json(
            tmp_path / f"tranche-{index}" / "clearance-card.json",
            {"fixture": "clearance-card"},
        )
        authority = _write_json(
            tmp_path / f"tranche-{index}" / "authority.json",
            {"fixture": f"authority-{index}"},
        )
        successor_root = (tmp_path / f"tranche-{index}" / "private").resolve()
        successor_root.mkdir()
        sources.append(
            {
                "kind": "successor",
                "ordinal": index,
                "recovery_root": str(root),
                "selection": str(tranche_selection),
                "purchased_clearance": str(clearance_path),
                "purchased_clearance_run_card": str(clearance_card),
                "resolved_post_recovery_documents": None,
                "replacement_purchase_authority": str(authority),
                "replacement_controlled_private_root": str(successor_root),
                "replacement_budget_plan": str(budget),
            }
        )
        recovery_by_root[root] = {
            "manifest_path": root / "purchased-document-downloads.jsonl",
            "manifest_records": [manifest_record],
            "document_root": document_root,
        }
        clearance_by_path[clearance_path] = {
            "clearance_records": [clearance_record],
            "restriction_records": [],
        }
    index_path = _write_json(
        tmp_path / "tranche-index.json",
        {
            "schema_version": "legalforecast.replacement_recovery_tranche_index.v1",
            "sources": sources,
        },
    )
    index_card_path = _write_json(
        tmp_path / "tranche-index-card.json",
        {"fixture": "replacement-recovery-index-card"},
    )
    policy = SimpleNamespace(canonical_ledger_path=ledger)
    monkeypatch.setattr(cli, "verify_case_dev_purchase_policy", lambda _value: policy)
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli, "verify_case_dev_purchase_policy_cohort_binding", lambda *_args: None
    )
    monkeypatch.setattr(
        cli, "_verify_replacement_recovery_index_card", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            operations=tuple(
                {"candidate_id": candidate_id, "source_document_id": document_id}
                for candidate_id, document_id in sorted(ledger_pairs)
            ),
            purchase_state_sha256="a" * 64,
        ),
    )
    monkeypatch.setattr(
        cli,
        "_verify_materializer_recovery",
        lambda *, recovery_root, **_kwargs: recovery_by_root[recovery_root],
    )
    monkeypatch.setattr(
        cli,
        "_verify_materializer_clearance_lineage",
        lambda *, clearance_path, **_kwargs: clearance_by_path[clearance_path],
    )
    monkeypatch.setattr(
        cli,
        "_verify_materializer_recovery_clearance_binding",
        lambda **_kwargs: None,
    )
    allowed_pairs: list[set[tuple[str, str]]] = []

    def verify_authority(**kwargs: object) -> None:
        allowed_pairs.append(
            set(
                kwargs["allowed_additional_operation_pairs"]  # type: ignore[arg-type]
            )
        )

    monkeypatch.setattr(cli, "verify_replacement_purchase_authority", verify_authority)
    args = argparse.Namespace(
        output_root=tmp_path / "consolidated",
        tranche_index=index_path,
        tranche_index_run_card=index_card_path,
        selection=selection,
        target_purchased_manifest=purchased_manifest,
        purchase_policy=policy_path,
        cohort_policy=cohort_path,
        purchase_ledger=ledger,
        controlled_private_root=private_root,
        purchase_ledger_initialization_receipt=receipt_path,
        run_card_output=None,
        execute=True,
        resume=False,
    )
    return args, allowed_pairs


def test_multi_tranche_consolidation_materializes_promoted_purchased_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    successor_pairs = {("case-1", "doc-1"), ("case-2", "doc-2")}
    expected = {("base-case", "base-doc"), *successor_pairs}
    args, allowed_pairs = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=expected,
    )

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == expected
    assert allowed_pairs == [{("case-2", "doc-2")}, set()]
    assert len(prepared.document_bytes) == 3
    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    verified = cli._verify_materializer_consolidated_recovery(
        recovery_root=args.output_root,
        run_card_path=(
            args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
        ),
        selection_path=args.selection,
        selected_document_keys=expected,
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
    )
    assert verified["recovery_stage"] == "consolidate-replacement-recovery"
    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in verified["manifest_records"]
    } == expected
    assert allowed_pairs == [
        {("case-2", "doc-2")},
        set(),
        {("case-2", "doc-2")},
        set(),
        {("case-2", "doc-2")},
        set(),
    ]


def test_consolidation_rejects_selected_purchased_document_absent_from_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs={("base-case", "base-doc"), ("case-1", "doc-1")},
    )

    with pytest.raises(
        ValueError,
        match="target purchased manifest differs from final active ledger coverage",
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_recovery_index_translates_successor_directory_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    successor_directory = tmp_path / "successors"
    successor_directory.mkdir()
    original_iterdir = Path.iterdir

    def fail_successor_iterdir(path: Path) -> Iterator[Path]:
        if path == successor_directory:
            raise OSError("successor directory unavailable")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_successor_iterdir)
    args = argparse.Namespace(
        output_root=tmp_path / "output",
        index_output=None,
        run_card_output=None,
        initial_source=tmp_path / "initial.json",
        successor_source=[successor_directory],
        execute=False,
        resume=False,
    )

    with pytest.raises(cli.CommandError, match="successor directory unavailable"):
        cli._cmd_build_replacement_recovery_index(args)


def test_consolidation_rejects_truncated_target_purchased_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=expected,
    )
    _write_jsonl(
        args.target_purchased_manifest,
        [{"candidate_id": "case-1", "source_document_id": "doc-1"}],
    )

    with pytest.raises(
        ValueError,
        match="target purchased manifest differs from authenticated target projection",
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_initial_only_consolidation_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_key = ("base-case", "base-doc")
    args, allowed_pairs = _prepare_fixture(
        tmp_path, monkeypatch, ledger_pairs={base_key}
    )
    index = json.loads(args.tranche_index.read_text(encoding="utf-8"))
    _write_json(args.tranche_index, {**index, "sources": index["sources"][:1]})
    selection_rows = [
        {
            "candidate_id": base_key[0],
            "documents": [{"source_document_id": base_key[1]}],
        }
    ]
    purchased_rows = [{"candidate_id": base_key[0], "source_document_id": base_key[1]}]
    _write_jsonl(args.selection, selection_rows)
    _write_jsonl(args.target_purchased_manifest, purchased_rows)
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "selection_path": args.selection,
            "selection_records": selection_rows,
            "purchased_manifest": purchased_rows,
        },
    )

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == {base_key}
    assert allowed_pairs == []


def test_recovery_index_requires_one_initial_source_first() -> None:
    successor = {
        "kind": "successor",
        "ordinal": 0,
        "recovery_root": "/recovery",
        "selection": "/selection",
        "purchased_clearance": "/clearance",
        "purchased_clearance_run_card": "/card",
        "resolved_post_recovery_documents": None,
        "replacement_purchase_authority": "/authority",
        "replacement_controlled_private_root": "/private",
        "replacement_budget_plan": "/budget",
    }
    with pytest.raises(ValueError, match="must begin with initial_v2"):
        cli._validated_replacement_recovery_sources(
            {
                "schema_version": "legalforecast.replacement_recovery_tranche_index.v1",
                "sources": [successor],
            }
        )


def test_recovery_index_rejects_reorder_and_duplicate_root() -> None:
    initial = {
        "kind": "initial_v2",
        "ordinal": 0,
        "recovery_root": "/initial",
        "selection": "/selection",
        "purchased_clearance": "/clearance",
        "purchased_clearance_run_card": "/card",
        "resolved_post_recovery_documents": None,
    }
    successor = {
        "kind": "successor",
        "ordinal": 2,
        "recovery_root": "/initial",
        "selection": "/selection-2",
        "purchased_clearance": "/clearance-2",
        "purchased_clearance_run_card": "/card-2",
        "resolved_post_recovery_documents": None,
        "replacement_purchase_authority": "/authority",
        "replacement_controlled_private_root": "/private",
        "replacement_budget_plan": "/budget",
    }
    artifact = {
        "schema_version": "legalforecast.replacement_recovery_tranche_index.v1",
        "sources": [initial, successor],
    }
    with pytest.raises(ValueError, match="source order differs"):
        cli._validated_replacement_recovery_sources(artifact)
    successor["ordinal"] = 1
    with pytest.raises(ValueError, match="repeats a recovery root"):
        cli._validated_replacement_recovery_sources(artifact)


def test_build_recovery_index_emits_canonical_order(
    tmp_path: Path,
) -> None:
    initial = _write_json(
        tmp_path / "initial.json",
        {
            "kind": "initial_v2",
            "ordinal": 0,
            "recovery_root": "/initial",
            "selection": "/initial-selection",
            "purchased_clearance": "/initial-clearance",
            "purchased_clearance_run_card": "/initial-card",
            "resolved_post_recovery_documents": None,
        },
    )
    successor = _write_json(
        tmp_path / "successor.json",
        {
            "kind": "successor",
            "ordinal": 1,
            "recovery_root": "/successor",
            "selection": "/successor-selection",
            "purchased_clearance": "/successor-clearance",
            "purchased_clearance_run_card": "/successor-card",
            "resolved_post_recovery_documents": None,
            "replacement_purchase_authority": "/authority",
            "replacement_controlled_private_root": "/private",
            "replacement_budget_plan": "/budget",
        },
    )
    args = argparse.Namespace(
        output_root=tmp_path / "output",
        initial_source=initial,
        successor_source=[successor],
        index_output=None,
        run_card_output=None,
        execute=True,
        resume=False,
    )

    assert cli._cmd_build_replacement_recovery_index(args) == 0
    index = json.loads(
        (args.output_root / "tranche-recovery-index.json").read_text(encoding="utf-8")
    )
    assert [source["kind"] for source in index["sources"]] == [
        "initial_v2",
        "successor",
    ]
    cli._verify_replacement_recovery_index_card(
        index_path=args.output_root / "tranche-recovery-index.json",
        run_card_path=(
            args.output_root / "run-cards" / "build-replacement-recovery-index.json"
        ),
        index_bytes=(args.output_root / "tranche-recovery-index.json").read_bytes(),
    )

    tampered = {**index, "sources": list(reversed(index["sources"]))}
    tampered_bytes = (json.dumps(tampered, sort_keys=True) + "\n").encode()
    with pytest.raises(
        ValueError,
        match="invalid authenticated replacement recovery index card",
    ):
        cli._verify_replacement_recovery_index_card(
            index_path=args.output_root / "tranche-recovery-index.json",
            run_card_path=(
                args.output_root / "run-cards" / "build-replacement-recovery-index.json"
            ),
            index_bytes=tampered_bytes,
        )

    card_path = args.output_root / "run-cards" / "build-replacement-recovery-index.json"
    forged_card = json.loads(card_path.read_text(encoding="utf-8"))
    forged_card["output_commitments"] = {
        str((args.output_root / "tranche-recovery-index.json").resolve()): (
            "sha256:" + hashlib.sha256(tampered_bytes).hexdigest()
        )
    }
    forged_card_path = _write_json(tmp_path / "forged-index-card.json", forged_card)
    with pytest.raises(ValueError, match="does not reproduce"):
        cli._verify_replacement_recovery_index_card(
            index_path=args.output_root / "tranche-recovery-index.json",
            run_card_path=forged_card_path,
            index_bytes=tampered_bytes,
        )
