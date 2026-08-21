from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion import recovered_public_replay as replay_module
from legalforecast.ingestion.case_dev_purchase import CaseDevPurchaseSnapshot


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
    successor_count: int = 2,
    pre_recovery_projection: bool = False,
    terminal_omission_pairs: set[tuple[str, str]] | None = None,
) -> tuple[argparse.Namespace, list[set[tuple[str, str]]]]:
    terminal_omission_pairs = terminal_omission_pairs or set()
    successor_pairs = (("case-1", "doc-1"), ("case-2", "doc-2"))
    selected_pairs = (("base-case", "base-doc"), *successor_pairs[:successor_count])
    selection_rows = [
        {
            "candidate_id": candidate_id,
            "documents": [
                {
                    "source_document_id": document_id,
                    **(
                        {
                            "availability_status": "unavailable",
                            "requires_paid_recovery": True,
                        }
                        if pre_recovery_projection
                        else {}
                    ),
                }
            ],
        }
        for candidate_id, document_id in selected_pairs
    ]
    selection = _write_jsonl(tmp_path / "active-selection.jsonl", selection_rows)
    purchased_rows = (
        []
        if pre_recovery_projection
        else [
            {"candidate_id": candidate_id, "source_document_id": document_id}
            for candidate_id, document_id in selected_pairs
        ]
    )
    purchased_manifest = _write_jsonl(
        tmp_path / "purchased-document-downloads.jsonl",
        purchased_rows,
    )
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "selection_path": selection,
            "selection_records": selection_rows,
            "purchased_manifest": purchased_rows,
            "run_card": {
                "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
            },
            "verified_artifact_bytes": {
                str(selection.resolve()): selection.read_bytes(),
                str(purchased_manifest.resolve()): purchased_manifest.read_bytes(),
            },
        },
    )
    policy_path = _write_json(tmp_path / "policy.json", {"fixture": "policy"})
    cohort_path = _write_json(tmp_path / "cohort.json", {"fixture": "cohort"})
    receipt_path = _write_json(tmp_path / "receipt.json", {"fixture": "receipt"})
    snapshot_manifest = _write_json(
        tmp_path / "snapshot" / "manifest.json", {"fixture": "snapshot"}
    )
    purchase_result = _write_json(
        tmp_path / "purchase-result.json", {"fixture": "purchase-result"}
    )
    purchase_run_card = _write_json(
        tmp_path / "purchase-run-card.json", {"fixture": "purchase-run-card"}
    )
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
        "verified_artifact_bytes": {},
    }
    clearance_by_path[initial_clearance] = {
        "clearance_records": [initial_clearance_record],
        "restriction_records": [],
    }
    for index, (candidate_id, document_id) in enumerate(
        successor_pairs[:successor_count], start=1
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
            "verified_artifact_bytes": {},
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
    policy = SimpleNamespace(
        canonical_ledger_path=ledger,
        policy_sha256="f" * 64,
    )
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
            committed_amount_usd="0.00",
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

    def authenticate_history(
        *,
        successor_recovery_root: Path,
        current_snapshot: CaseDevPurchaseSnapshot,
        **_kwargs: object,
    ) -> tuple[CaseDevPurchaseSnapshot, dict[str, bytes]]:
        record = recovery_by_root[successor_recovery_root]["manifest_records"][0]
        pair = (record["candidate_id"], record["source_document_id"])
        predecessor = tuple(
            operation
            for operation in current_snapshot.operations
            if (operation["candidate_id"], operation["source_document_id"]) != pair
        )
        return (
            CaseDevPurchaseSnapshot(
                operations=predecessor,
                purchase_state_sha256=current_snapshot.purchase_state_sha256,
                committed_amount_usd=current_snapshot.committed_amount_usd,
            ),
            {},
        )

    monkeypatch.setattr(
        cli, "_authenticated_pre_successor_purchase_snapshot", authenticate_history
    )
    monkeypatch.setattr(
        cli,
        "_replacement_consolidation_terminal_omissions",
        lambda **_kwargs: SimpleNamespace(
            keys=frozenset(terminal_omission_pairs),
            partition={
                "schema_version": (
                    "legalforecast.materializer_docket_decision_partition.v1"
                ),
                "audit_only_document_keys": [
                    {"candidate_id": candidate_id, "source_document_id": document_id}
                    for candidate_id, document_id in sorted(terminal_omission_pairs)
                ],
            },
            source_snapshots={},
        ),
        raising=False,
    )
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
        external_billing_register=None,
        snapshot_manifest=(snapshot_manifest if pre_recovery_projection else None),
        purchase_result=(purchase_result if pre_recovery_projection else None),
        purchase_run_card=(purchase_run_card if pre_recovery_projection else None),
        run_card_output=None,
        execute=True,
        resume=False,
    )
    return args, allowed_pairs


def _attach_external_billing_register(
    args: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
    *,
    document_commitments: Mapping[tuple[str, str], str],
) -> tuple[Path, list[bytes]]:
    """Put a synthetic register on the v3 production path.

    The register verifier's own tests pin exact-byte ratification.  This fixture
    substitutes only that boundary so this suite can exercise how the
    consolidation and materializer consume the verifier-issued document keys.
    """

    register_path = _write_json(
        Path(args.output_root).parent / "external-billing-register.json",
        {"fixture": "owner-ratified-register"},
    ).absolute()
    observed_payloads: list[bytes] = []

    def verify_register(payload: bytes) -> SimpleNamespace:
        observed_payloads.append(payload)
        assert payload == register_path.read_bytes()
        return SimpleNamespace(
            document_keys=frozenset(document_commitments),
            commitment_map=lambda: dict(document_commitments),
        )

    monkeypatch.setattr(cli, "verify_external_billing_register", verify_register)
    args.external_billing_register = register_path
    if args.target_purchased_manifest is not None:
        args.target_cohort_root = Path(args.target_purchased_manifest).parent
        args.target_purchased_manifest = None
    return register_path, observed_payloads


def _attach_promoted_v3_document(
    args: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
    *,
    verified_payload: bytes | None = None,
) -> tuple[tuple[str, str], bytes]:
    """Add a purchased v3 document absent from every historical recovery."""

    promoted_key = ("case-2", "doc-2")
    payload = b"%PDF-1.4 authenticated v3 promotion\n"
    digest = hashlib.sha256(payload).hexdigest()
    selection_rows = [
        json.loads(line)
        for line in args.selection.read_text(encoding="utf-8").splitlines()
        if line
    ]
    selection_rows.append(
        {
            "candidate_id": promoted_key[0],
            "documents": [{"source_document_id": promoted_key[1]}],
        }
    )
    _write_jsonl(args.selection, selection_rows)
    target_root = Path(args.output_root).parent / "exact100-v3"
    local_path = Path(promoted_key[0]) / f"{promoted_key[1]}.pdf"
    source_path = (
        target_root / "owner-adjudicated-source" / "documents" / local_path
    ).absolute()
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)
    promoted_manifest = {
        "candidate_id": promoted_key[0],
        "source_document_id": promoted_key[1],
        "local_path": str(local_path),
        "sha256": digest,
        "byte_count": len(payload),
        "free_or_purchased": "purchased",
    }
    promoted_clearance = {
        **promoted_manifest,
        "status": "cleared",
    }
    inherited_manifest = [
        json.loads(line)
        for line in Path(args.target_purchased_manifest)
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "run_card": {
                "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
            },
            "selection_path": args.selection,
            "selection_records": selection_rows,
            "purchased_manifest": [*inherited_manifest, promoted_manifest],
            "purchased_clearance": [promoted_clearance],
            "restriction_records": [
                {
                    "candidate_id": promoted_key[0],
                    "source_document_id": promoted_key[1],
                    "restriction_status": "public",
                }
            ],
            "verified_artifact_bytes": {
                str(args.selection.resolve()): args.selection.read_bytes(),
            },
            "verified_document_bytes": {
                str(source_path): (
                    payload if verified_payload is None else verified_payload
                )
            },
        },
    )
    args.target_cohort_root = target_root
    args.target_purchased_manifest = None
    return promoted_key, payload


def test_register_coverage_uses_v3_fixed_slot_and_replays_into_materializer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same authenticated register widens issuance and replay coverage."""

    selected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    canonical_ledger = selected - {("case-2", "doc-2")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=canonical_ledger,
    )
    register_path, observed_payloads = _attach_external_billing_register(
        args,
        monkeypatch,
        document_commitments={
            ("case-2", "doc-2"): hashlib.sha256(b"%PDF-1.4 tranche 2\n").hexdigest()
        },
    )

    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    card_path = args.output_root / "run-cards/consolidate-replacement-recovery.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["schema_version"] == str(
        cli.REPLACEMENT_RECOVERY_CONSOLIDATION_RUN_CARD_V3
    )
    assert card["input_paths"][9] == str(register_path)
    assert card["source_commitments"][str(register_path.resolve())].startswith(
        "sha256:"
    )

    verified = cli._verify_materializer_consolidated_recovery(
        recovery_root=args.output_root,
        run_card_path=card_path,
        selection_path=args.selection,
        selected_document_keys=selected,
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
    )

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in verified["manifest_records"]
    } == selected
    # Issuance, materializer coverage, and authenticated replay each consume
    # the verifier output rather than silently falling back to ledger-only.
    assert observed_payloads == [register_path.read_bytes()] * 3


def test_v3_register_gap_uses_authenticated_target_records_and_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    historical = {("base-case", "base-doc"), ("case-1", "doc-1")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=historical,
        successor_count=1,
    )
    promoted_key, payload = _attach_promoted_v3_document(args, monkeypatch)
    _attach_external_billing_register(
        args,
        monkeypatch,
        document_commitments={promoted_key: hashlib.sha256(payload).hexdigest()},
    )

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == historical | {promoted_key}
    promoted = next(
        row
        for row in prepared.manifest_records
        if (row["candidate_id"], row["source_document_id"]) == promoted_key
    )
    assert promoted["local_path"] == (
        f"sha256/{hashlib.sha256(payload).hexdigest()[:2]}/"
        f"{hashlib.sha256(payload).hexdigest()}.pdf"
    )
    assert prepared.document_bytes[promoted["local_path"]] == payload
    assert len(prepared.restriction_records) == 1


def test_v3_register_gap_rejects_mismatched_authenticated_target_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    historical = {("base-case", "base-doc"), ("case-1", "doc-1")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=historical,
        successor_count=1,
    )
    promoted_key, payload = _attach_promoted_v3_document(
        args, monkeypatch, verified_payload=b"different authenticated bytes"
    )
    _attach_external_billing_register(
        args,
        monkeypatch,
        document_commitments={promoted_key: hashlib.sha256(payload).hexdigest()},
    )

    with pytest.raises(ValueError, match="target document bytes differ"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_omitting_register_preserves_canonical_ledger_only_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No optional argument means no authority widening and no v3 emission."""

    selected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=selected - {("case-2", "doc-2")},
    )
    monkeypatch.setattr(
        cli,
        "verify_external_billing_register",
        lambda _payload: pytest.fail("register verifier called without CLI input"),
    )

    with pytest.raises(
        ValueError,
        match="final active paid-gap scope differs from canonical ledger coverage",
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_exact100_v3_target_without_register_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=selected)
    args.target_cohort_root = Path(args.target_purchased_manifest).parent
    args.target_purchased_manifest = None

    with pytest.raises(ValueError, match="v3 target requires"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_v3_chain_uses_authenticated_anchor_to_find_legacy_target(
    tmp_path: Path,
) -> None:
    legacy_root = tmp_path / "legacy-zero-cost-target"
    immediate_v3_predecessor = tmp_path / "immediate-v3-predecessor"
    v2_projection: dict[str, object] = {
        "run_card": {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2),
            "input_paths": [str(legacy_root)],
        }
    }
    supporting_projection: dict[str, object] = {
        "run_card": {
            "schema_version": cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION,
        },
        "base_v2_projection": v2_projection,
    }
    v3_projection: dict[str, object] = {
        "run_card": {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3),
            # This is deliberately not the legacy target. A multi-v3 chain's
            # first card input names only the immediately preceding generation.
            "input_paths": [str(immediate_v3_predecessor)],
        },
        "base_projection": supporting_projection,
    }

    assert cli._consolidation_legacy_target_root(v3_projection) == (
        legacy_root.absolute()
    )


@pytest.mark.parametrize(
    ("projection", "message"),
    [
        (
            {
                "run_card": {
                    "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
                }
            },
            "lacks authenticated anchor projection",
        ),
        (
            {
                "run_card": {
                    "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
                },
                "base_projection": {"run_card": {"schema_version": "wrong-anchor"}},
            },
            "anchor is not a supporting-document successor",
        ),
        (
            {
                "run_card": {
                    "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
                },
                "base_projection": {
                    "run_card": {
                        "schema_version": (
                            cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION
                        )
                    }
                },
            },
            "anchor lacks authenticated v2 base",
        ),
        (
            {
                "run_card": {
                    "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
                },
                "base_projection": {
                    "run_card": {
                        "schema_version": (
                            cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION
                        )
                    },
                    "base_v2_projection": {"run_card": {"schema_version": "wrong-v2"}},
                },
            },
            "does not terminate at a v2 successor",
        ),
        (
            {
                "run_card": {
                    "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2),
                    "input_paths": [],
                }
            },
            "predecessor root is invalid",
        ),
    ],
)
def test_legacy_target_unwrap_refuses_malformed_authenticated_layers(
    projection: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cli._consolidation_legacy_target_root(projection)


def test_external_register_with_legacy_target_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs={("base-case", "base-doc")},
    )
    register_path = _write_json(tmp_path / "register.json", {"fixture": True})
    args.external_billing_register = register_path

    with pytest.raises(ValueError, match="requires an authenticated exact100 v3"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_external_register_with_exact100_v2_target_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=selected)
    register_path, _ = _attach_external_billing_register(
        args,
        monkeypatch,
        document_commitments={},
    )
    original_verify = (
        cli.verify_completed_target_cohort_projection_for_purchase_approval
    )

    def verify_v2(root: Path) -> dict[str, object]:
        projection = dict(original_verify(root))
        projection["run_card"] = {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2)
        }
        return projection

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        verify_v2,
    )

    assert args.external_billing_register == register_path
    with pytest.raises(ValueError, match="supported only for an exact100 v3"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_external_register_cannot_overlap_canonical_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=selected)
    _attach_external_billing_register(
        args,
        monkeypatch,
        document_commitments={
            ("case-2", "doc-2"): hashlib.sha256(b"%PDF-1.4 tranche 2\n").hexdigest()
        },
    )

    with pytest.raises(ValueError, match="overlaps canonical ledger"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_external_register_binds_recovered_document_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=selected - {("case-2", "doc-2")},
    )
    _attach_external_billing_register(
        args,
        monkeypatch,
        document_commitments={("case-2", "doc-2"): "d" * 64},
    )

    with pytest.raises(ValueError, match="register document bytes differ"):
        cli._prepare_replacement_recovery_consolidation(args)


@pytest.mark.parametrize(
    "redirected",
    ["selection", "purchase_policy", "cohort_policy"],
)
def test_a_byte_identical_input_at_another_path_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, redirected: str
) -> None:
    """The consolidation binds its inputs by path identity, not by content.

    A materializer holding the same selection bytes under a different path is
    refused, so a consolidation can never be re-pointed at a copy of the
    artifact it was built against. That is deliberate, and it is also what makes
    a cohort root with a differently named selection need a fresh consolidation
    rather than a re-labelled one -- worth pinning, because nothing asserted it.

    The ledger is bound the same way but is not covered here: this fixture's
    ledger is created through the journal rather than existing as a file to copy.
    """

    all_paid = {("base-case", "base-doc"), ("case-1", "doc-1"), ("case-2", "doc-2")}
    omitted = {("case-2", "doc-2")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
        terminal_omission_pairs=omitted,
    )

    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    card_path = args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
    original = Path(getattr(args, redirected))
    copied = tmp_path / f"identical-{redirected}{original.suffix}"
    copied.write_bytes(original.read_bytes())
    bound = {
        "selection_path": args.selection,
        "purchase_policy_path": args.purchase_policy,
        "cohort_policy_path": args.cohort_policy,
        "ledger_path": args.purchase_ledger,
    }
    bound[
        {
            "selection": "selection_path",
            "purchase_policy": "purchase_policy_path",
            "cohort_policy": "cohort_policy_path",
            "purchase_ledger": "ledger_path",
        }[redirected]
    ] = copied

    with pytest.raises(
        cli.CommandError,
        match="consolidated replacement recovery differs from materializer inputs",
    ):
        cli._verify_materializer_consolidated_recovery(
            recovery_root=args.output_root,
            run_card_path=card_path,
            selected_document_keys=all_paid - omitted,
            **bound,
        )


def test_pre_recovery_empty_manifest_uses_paid_gaps_minus_terminal_omissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    omitted = {("case-2", "doc-2")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
        terminal_omission_pairs=omitted,
    )

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == all_paid - omitted
    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    verified = cli._verify_materializer_consolidated_recovery(
        recovery_root=args.output_root,
        run_card_path=(
            args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
        ),
        selection_path=args.selection,
        selected_document_keys=all_paid - omitted,
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
    )
    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in verified["manifest_records"]
    } == all_paid - omitted
    capability = verified["consolidated_resolved_capability"]
    assert cli._consume_consolidated_resolved_capability(capability)
    with pytest.raises(cli.CommandError, match="verifier-issued authority"):
        cli._consume_consolidated_resolved_capability(object())
    with pytest.raises(cli.CommandError, match="verifier-issued authority"):
        cli._consume_consolidated_resolved_capability(copy.copy(capability))
    object.__setattr__(capability, "purchase_policy_sha256", "0" * 64)
    with pytest.raises(cli.CommandError, match="verifier-issued authority"):
        cli._consume_consolidated_resolved_capability(capability)


def test_exact100_v2_target_root_derives_paid_gaps_with_empty_partition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    omitted = {("case-2", "doc-2")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
        terminal_omission_pairs=omitted,
    )
    target_root = tmp_path / "exact100-v2"
    target_card_path = target_root / "run-cards" / "project-target-cohort.json"
    target_card_path.parent.mkdir(parents=True)
    target_card_path.write_text("authenticated-v2-card\n", encoding="utf-8")
    selection_records = [
        json.loads(line)
        for line in args.selection.read_text(encoding="utf-8").splitlines()
        if line
    ]
    projection = {
        "run_card": {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2)
        },
        "selection_path": args.selection,
        "selection_records": tuple(selection_records),
        "purchased_manifest": (),
        "verified_artifact_bytes": {
            str(target_card_path): target_card_path.read_bytes(),
        },
    }

    def verify_target(path: Path, **_kwargs: object) -> dict[str, object]:
        assert path.resolve() == target_root.resolve()
        return projection

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        verify_target,
    )
    args.target_purchased_manifest = None
    args.target_cohort_root = target_root

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert prepared.input_paths[3] == target_root
    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == all_paid - omitted
    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    card_path = args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["schema_version"] == cli._REPLACEMENT_RECOVERY_CARD_SCHEMA_V2
    assert card["target_projection_mode"] == "exact100_successor_replacement_v2"
    assert str(target_card_path.resolve()) in card["source_commitments"]

    verified = cli._verify_materializer_consolidated_recovery(
        recovery_root=args.output_root,
        run_card_path=card_path,
        selection_path=args.selection,
        selected_document_keys=all_paid - omitted,
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
    )
    assert tuple(verified["manifest_records"]) == prepared.manifest_records

    target_card_path.write_text("mutated\n", encoding="utf-8")
    with pytest.raises(
        cli.CommandError,
        match="consolidated replacement recovery source commitment changed",
    ):
        cli._verify_materializer_consolidated_recovery(
            recovery_root=args.output_root,
            run_card_path=card_path,
            selection_path=args.selection,
            selected_document_keys=all_paid - omitted,
            purchase_policy_path=args.purchase_policy,
            cohort_policy_path=args.cohort_policy,
            ledger_path=args.purchase_ledger,
        )


def test_exact100_v2_target_root_accepts_inherited_purchased_partition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    target_root = tmp_path / "exact100-v2"
    selection_records = [
        json.loads(line)
        for line in args.selection.read_text(encoding="utf-8").splitlines()
        if line
    ]
    purchased_records = tuple(
        {
            "candidate_id": candidate_id,
            "source_document_id": source_document_id,
            "free_or_purchased": "purchased",
        }
        for candidate_id, source_document_id in sorted(all_paid)
    )

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _path: {
            "run_card": {
                "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2)
            },
            "selection_path": args.selection,
            "selection_records": selection_records,
            "purchased_manifest": purchased_records,
            "verified_artifact_bytes": {},
        },
    )
    args.target_purchased_manifest = None
    args.target_cohort_root = target_root

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == all_paid


def test_consolidated_verifier_reuses_authenticated_history_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=all_paid)
    prepared = cli._prepare_replacement_recovery_consolidation(args)
    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    index = json.loads(args.tranche_index.read_text(encoding="utf-8"))
    budget_path = Path(index["sources"][1]["replacement_budget_plan"]).absolute()
    original_read = cli._read_singly_linked_regular_input
    budget_reads = 0

    def count_budget_reads(path: Path, *, label: str) -> bytes:
        nonlocal budget_reads
        if path.absolute() == budget_path:
            budget_reads += 1
        return original_read(path, label=label)

    monkeypatch.setattr(cli, "_read_singly_linked_regular_input", count_budget_reads)

    verified = cli._verify_materializer_consolidated_recovery(
        recovery_root=args.output_root,
        run_card_path=(
            args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
        ),
        selection_path=args.selection,
        selected_document_keys=all_paid,
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
    )

    assert budget_reads == 2  # Initial authentication plus final TOCTOU recheck.
    assert tuple(verified["manifest_records"]) == prepared.manifest_records
    assert (args.output_root / "purchased-document-downloads.jsonl").read_bytes() == (
        cli._projection_jsonl_bytes(prepared.manifest_records)
    )


def test_successor_history_authentication_records_complete_verified_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    production_authenticate = cli._authenticated_pre_successor_purchase_snapshot
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs={
            ("base-case", "base-doc"),
            ("case-1", "doc-1"),
        },
        successor_count=1,
    )
    source = json.loads(args.tranche_index.read_text(encoding="utf-8"))["sources"][1]
    successor_root = Path(source["recovery_root"]).resolve()
    selection_path = Path(source["selection"]).resolve()
    budget_path = Path(source["replacement_budget_plan"]).resolve()
    authority_path = Path(source["replacement_purchase_authority"]).resolve()
    attempt_policy_path = _write_json(
        tmp_path / "tranche-1" / "attempt-policy.json", {"fixture": "attempt"}
    )
    _write_json(
        successor_root / "run-cards" / "recover-recap-fetch-quarantine.json", {}
    )
    coordinates = SimpleNamespace(
        kind="successor",
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        purchase_ledger_path=args.purchase_ledger,
        replacement_authority_path=authority_path,
        selection_path=selection_path,
        budget_plan_path=budget_path,
        attempt_policy_path=attempt_policy_path,
    )
    initial_operation = {
        "candidate_id": "base-case",
        "source_document_id": "base-doc",
    }
    successor_operation = {
        "candidate_id": "case-1",
        "source_document_id": "doc-1",
    }
    current_snapshot = CaseDevPurchaseSnapshot(
        operations=(initial_operation, successor_operation),
        purchase_state_sha256="a" * 64,
        committed_amount_usd="0.00",
    )
    original_recovery = cli._verify_materializer_recovery
    recoveries: list[Mapping[str, object]] = []

    def capture_recovery(**kwargs: object) -> Mapping[str, object]:
        recovery = original_recovery(**kwargs)
        recoveries.append(recovery)
        return recovery

    monkeypatch.setattr(
        cli, "derive_recovery_source_coordinates", lambda _card: coordinates
    )
    monkeypatch.setattr(cli, "_missing_core_budget_plan", lambda _budget: {})
    monkeypatch.setattr(
        cli, "verify_recap_fetch_attempt_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(cli, "_verify_materializer_recovery", capture_recovery)
    monkeypatch.setattr(
        cli,
        "verify_replacement_purchase_authority",
        lambda **_kwargs: SimpleNamespace(
            baseline_operation_record_sha256s=(
                cli.canonical_purchase_operation_sha256(initial_operation),
            ),
            committed_spend_usd="0.00",
            purchase_journal_state_sha256="sha256:fixture-baseline-state",
        ),
    )
    monkeypatch.setattr(
        cli,
        "canonical_purchase_state_sha256",
        lambda *_args, **_kwargs: "fixture-baseline-state",
    )
    verified_recoveries: dict[Path, replay_module.VerifiedSuccessorRecovery] = {}

    predecessor, verified_bytes = production_authenticate(
        successor_recovery_root=successor_root,
        successor_controlled_private_root=Path(
            source["replacement_controlled_private_root"]
        ).resolve(),
        current_snapshot=current_snapshot,
        policy=SimpleNamespace(),
        policy_artifact={},
        cohort_artifact={},
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
        initial_controlled_private_root=args.controlled_private_root,
        initialization_receipt_path=args.purchase_ledger_initialization_receipt,
        capture=lambda path, *, label: path.read_bytes(),
        expected_selection_path=selection_path,
        expected_budget_plan_path=budget_path,
        expected_authority_path=authority_path,
        verified_successor_recoveries=verified_recoveries,
    )

    assert predecessor.operations == (initial_operation,)
    assert verified_bytes == {}
    assert len(recoveries) == 1
    assert set(verified_recoveries) == {successor_root}
    verified = verified_recoveries[successor_root]
    assert verified.recovery_root == successor_root
    assert verified.selection_path == selection_path
    assert verified.selection_bytes == selection_path.read_bytes()
    assert verified.selected_document_keys == frozenset({("case-1", "doc-1")})
    assert verified.purchase_policy_path == args.purchase_policy.resolve()
    assert verified.cohort_policy_path == args.cohort_policy.resolve()
    assert verified.ledger_path == args.purchase_ledger.resolve()
    assert verified.purchase_snapshot == current_snapshot
    assert verified.recovery is recoveries[0]


def test_consolidated_verifier_reuses_successor_recovery_with_noncanonical_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {("base-case", "base-doc"), ("case-1", "doc-1")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        successor_count=1,
    )
    initial_root = (tmp_path / "initial" / "recovery").resolve()
    successor_root = (tmp_path / "tranche-1" / "recovery").resolve()
    successor_budget = (tmp_path / "tranche-1" / "budget.json").resolve()
    tranche_index = json.loads(args.tranche_index.read_text(encoding="utf-8"))
    tranche_index["sources"][1]["recovery_root"] = str(
        successor_root.parent / ".." / successor_root.parent.name / successor_root.name
    )
    args.tranche_index.write_text(
        json.dumps(tranche_index, sort_keys=True) + "\n", encoding="utf-8"
    )
    fixture_recovery = cli._verify_materializer_recovery
    recovery_calls: Counter[Path] = Counter()

    def count_recovery(**kwargs: object) -> dict[str, object]:
        recovery_root = Path(cast(Path, kwargs["recovery_root"])).resolve()
        recovery_calls[recovery_root] += 1
        return fixture_recovery(**kwargs)

    def authenticate_history(
        *,
        successor_recovery_root: Path,
        current_snapshot: CaseDevPurchaseSnapshot,
        verified_successor_recoveries: dict[
            Path, replay_module.VerifiedSuccessorRecovery
        ]
        | None = None,
        **kwargs: object,
    ) -> tuple[CaseDevPurchaseSnapshot, dict[str, bytes]]:
        selection_path = Path(cast(Path, kwargs["expected_selection_path"])).resolve()
        selection_bytes = cast(Callable[..., bytes], kwargs["capture"])(
            selection_path, label="fixture successor history selection"
        )
        selected_document_keys = cli._replacement_consolidation_selection_keys(
            [json.loads(line) for line in selection_bytes.decode().splitlines()]
        )
        recovery = count_recovery(
            recovery_root=successor_recovery_root,
            selection_path=selection_path,
            selected_document_keys=selected_document_keys,
            purchase_policy_path=kwargs["purchase_policy_path"],
            cohort_policy_path=kwargs["cohort_policy_path"],
            ledger_path=kwargs["ledger_path"],
            purchase_operations=current_snapshot.operations,
            purchase_committed_amount_usd=current_snapshot.committed_amount_usd,
            purchase_state_sha256=current_snapshot.purchase_state_sha256,
        )
        if verified_successor_recoveries is not None:
            verified_successor_recoveries[successor_recovery_root.resolve()] = (
                replay_module.VerifiedSuccessorRecovery(
                    recovery_root=successor_recovery_root.resolve(),
                    selection_path=selection_path,
                    selection_bytes=selection_bytes,
                    selected_document_keys=frozenset(selected_document_keys),
                    purchase_policy_path=Path(
                        cast(Path, kwargs["purchase_policy_path"])
                    ).resolve(),
                    cohort_policy_path=Path(
                        cast(Path, kwargs["cohort_policy_path"])
                    ).resolve(),
                    ledger_path=Path(cast(Path, kwargs["ledger_path"])).resolve(),
                    purchase_snapshot=current_snapshot,
                    recovery=recovery,
                )
            )
        record = cast(list[dict[str, str]], recovery["manifest_records"])[0]
        pair = (record["candidate_id"], record["source_document_id"])
        prefix = tuple(
            operation
            for operation in current_snapshot.operations
            if (operation["candidate_id"], operation["source_document_id"]) != pair
        )
        return (
            CaseDevPurchaseSnapshot(
                operations=prefix,
                purchase_state_sha256=current_snapshot.purchase_state_sha256,
                committed_amount_usd=current_snapshot.committed_amount_usd,
            ),
            cast(dict[str, bytes], recovery["verified_artifact_bytes"]),
        )

    monkeypatch.setattr(cli, "_verify_materializer_recovery", count_recovery)
    monkeypatch.setattr(
        cli, "_authenticated_pre_successor_purchase_snapshot", authenticate_history
    )
    assert cli._cmd_consolidate_replacement_recovery(args) == 0

    recovery_calls.clear()
    original_read = cli._read_singly_linked_regular_input
    budget_reads = 0

    def count_budget_reads(path: Path, *, label: str) -> bytes:
        nonlocal budget_reads
        if path.resolve() == successor_budget:
            budget_reads += 1
        return original_read(path, label=label)

    monkeypatch.setattr(cli, "_read_singly_linked_regular_input", count_budget_reads)
    cli._verify_materializer_consolidated_recovery(
        recovery_root=args.output_root,
        run_card_path=(
            args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
        ),
        selection_path=args.selection,
        selected_document_keys=all_paid,
        purchase_policy_path=args.purchase_policy,
        cohort_policy_path=args.cohort_policy,
        ledger_path=args.purchase_ledger,
    )

    assert recovery_calls == Counter({initial_root: 1, successor_root: 1})
    assert budget_reads == 2  # Initial authentication plus final TOCTOU recheck.


def test_consolidated_verifier_rejects_post_snapshot_source_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {("base-case", "base-doc"), ("case-1", "doc-1")}
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        successor_count=1,
    )
    assert cli._cmd_consolidate_replacement_recovery(args) == 0
    index = json.loads(args.tranche_index.read_text(encoding="utf-8"))
    budget_path = Path(index["sources"][1]["replacement_budget_plan"]).absolute()
    original_prepare = cli._prepare_replacement_recovery_consolidation

    def mutate_after_replay(*args: object, **kwargs: object) -> object:
        replay = original_prepare(*args, **kwargs)
        budget_path.write_bytes(b'{"case_plans":[]}\n')
        return replay

    monkeypatch.setattr(
        cli, "_prepare_replacement_recovery_consolidation", mutate_after_replay
    )

    with pytest.raises(
        cli.CommandError,
        match=(
            "consolidated replacement recovery verification input changed during "
            "execution"
        ),
    ):
        cli._verify_materializer_consolidated_recovery(
            recovery_root=args.output_root,
            run_card_path=(
                args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
            ),
            selection_path=args.selection,
            selected_document_keys=all_paid,
            purchase_policy_path=args.purchase_policy,
            cohort_policy_path=args.cohort_policy,
            ledger_path=args.purchase_ledger,
        )


def test_empty_purchased_manifest_without_paid_gaps_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "empty authenticated purchased manifest lacks paid-recovery gap identities"
        ),
    ):
        cli._replacement_consolidation_active_paid_keys(
            [
                {
                    "candidate_id": "case-1",
                    "documents": [{"source_document_id": "doc-1"}],
                }
            ],
            authenticated_purchased_keys=set(),
        )


def test_selected_paid_ledger_identity_missing_from_paid_scope_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    selection_rows = [
        {
            "candidate_id": candidate_id,
            "documents": [
                {
                    "source_document_id": document_id,
                    **(
                        {
                            "availability_status": "unavailable",
                            "requires_paid_recovery": True,
                        }
                        if candidate_id != "case-2"
                        else {}
                    ),
                }
            ],
        }
        for candidate_id, document_id in sorted(all_paid)
    ]
    _write_jsonl(args.selection, selection_rows)
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "selection_path": args.selection,
            "selection_records": selection_rows,
            "purchased_manifest": [],
        },
    )

    with pytest.raises(
        ValueError,
        match=(
            "selected paid-ledger identity missing from final active paid-gap scope"
        ),
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_terminal_omission_replay_opens_purchase_journal_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal_arguments: dict[str, object] = {}
    journal = object()

    class _JournalContext:
        def __init__(self, path: Path, **kwargs: object) -> None:
            journal_arguments["path"] = path
            journal_arguments.update(kwargs)

        def __enter__(self) -> object:
            return journal

        def __exit__(self, *_args: object) -> None:
            return None

    descriptor = SimpleNamespace(
        authority=object(),
        partition={"audit_only_document_count": 1},
        source_snapshots={tmp_path / "purchase-result.json": b"{}\n"},
    )
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", _JournalContext)
    monkeypatch.setattr(
        cli,
        "_verify_materializer_docket_decision_authority",
        lambda **kwargs: descriptor,
    )

    def verify_decision_keys(
        authority: object, *, purchase_journal: object
    ) -> set[tuple[str, str]]:
        assert authority is descriptor.authority
        assert purchase_journal is journal
        return {("case-1", "decision-1")}

    monkeypatch.setattr(
        cli, "verified_docket_decision_document_keys", verify_decision_keys
    )
    policy = SimpleNamespace()
    ledger_path = tmp_path / "purchase-ledger.sqlite3"
    private_root = tmp_path / "private"
    receipt_path = tmp_path / "receipt.json"

    result = cli._replacement_consolidation_terminal_omissions(
        selection_payload=b"{}\n",
        snapshot_manifest_path=tmp_path / "snapshot-manifest.json",
        purchase_result_path=tmp_path / "purchase-result.json",
        purchase_run_card_path=tmp_path / "purchase-run-card.json",
        purchase_policy=policy,
        ledger_path=ledger_path,
        controlled_private_root=private_root,
        initialization_receipt_path=receipt_path,
        selected_document_count=1,
    )

    assert result.keys == frozenset({("case-1", "decision-1")})
    assert journal_arguments == {
        "path": ledger_path,
        "policy": policy,
        "read_only": True,
        "controlled_private_root": private_root,
        "initialization_receipt_path": receipt_path,
    }


def test_pre_recovery_consolidation_rejects_missing_active_paid_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    original = cli._verify_materializer_recovery
    missing_root = (tmp_path / "tranche-2" / "recovery").resolve()

    def omit_active(**kwargs: object) -> dict[str, object]:
        result = dict(original(**kwargs))
        if kwargs["recovery_root"] == missing_root:
            result["manifest_records"] = []
        return result

    monkeypatch.setattr(cli, "_verify_materializer_recovery", omit_active)

    with pytest.raises(
        ValueError,
        match="coverage differs from final active purchased cohort",
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_pre_recovery_consolidation_rejects_unledgered_paid_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs={
            ("base-case", "base-doc"),
            ("case-1", "doc-1"),
        },
        pre_recovery_projection=True,
    )

    with pytest.raises(
        ValueError,
        match="final active paid-gap scope differs from canonical ledger coverage",
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_pre_recovery_consolidation_requires_complete_terminal_authority_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    args.purchase_result = None

    with pytest.raises(
        ValueError,
        match=(
            "snapshot manifest, purchase result, and purchase run card must be "
            "supplied together"
        ),
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_pre_recovery_consolidation_rejects_inconsistent_paid_gap_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    selection_rows = [
        json.loads(line)
        for line in args.selection.read_text(encoding="utf-8").splitlines()
    ]
    selection_rows[0]["documents"][0]["availability_status"] = "available"
    _write_jsonl(args.selection, selection_rows)
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "selection_path": args.selection,
            "selection_records": selection_rows,
            "purchased_manifest": [],
        },
    )

    with pytest.raises(ValueError, match="inconsistent paid-recovery gap markers"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_pre_recovery_consolidation_filters_historical_unselected_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    final_rows = [
        row
        for row in (
            json.loads(line)
            for line in args.selection.read_text(encoding="utf-8").splitlines()
        )
        if row["candidate_id"] != "case-2"
    ]
    _write_jsonl(args.selection, final_rows)
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "selection_path": args.selection,
            "selection_records": final_rows,
            "purchased_manifest": [],
            "verified_artifact_bytes": {
                str(args.selection.resolve()): args.selection.read_bytes(),
                str(args.target_purchased_manifest.resolve()): (
                    args.target_purchased_manifest.read_bytes()
                ),
            },
        },
    )

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert {
        (row["candidate_id"], row["source_document_id"])
        for row in prepared.manifest_records
    } == all_paid - {("case-2", "doc-2")}


def test_pre_recovery_consolidation_rejects_uncleared_active_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    original = cli._verify_materializer_clearance_lineage
    uncleared_path = (tmp_path / "tranche-1" / "clearance.jsonl").resolve()

    def return_uncleared(**kwargs: object) -> dict[str, object]:
        result = dict(original(**kwargs))
        if kwargs["clearance_path"] == uncleared_path:
            rows = [dict(row) for row in result["clearance_records"]]  # type: ignore[arg-type]
            rows[0]["status"] = "quarantined"
            result["clearance_records"] = rows
        return result

    monkeypatch.setattr(cli, "_verify_materializer_clearance_lineage", return_uncleared)

    with pytest.raises(ValueError, match="lacks cleared active document"):
        cli._prepare_replacement_recovery_consolidation(args)


def test_pre_recovery_consolidation_rejects_rebound_active_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
        pre_recovery_projection=True,
    )
    original_recovery = cli._verify_materializer_recovery
    original_clearance = cli._verify_materializer_clearance_lineage
    first_root = (tmp_path / "tranche-1" / "recovery").resolve()
    rebound_root = (tmp_path / "tranche-2" / "recovery").resolve()
    first_clearance = (tmp_path / "tranche-1" / "clearance.jsonl").resolve()
    rebound_clearance = (tmp_path / "tranche-2" / "clearance.jsonl").resolve()

    def rebound_recovery(**kwargs: object) -> dict[str, object]:
        if kwargs["recovery_root"] == rebound_root:
            return dict(original_recovery(recovery_root=first_root))
        return dict(original_recovery(**kwargs))

    def rebound_clearance_lineage(**kwargs: object) -> dict[str, object]:
        if kwargs["clearance_path"] == rebound_clearance:
            return dict(original_clearance(clearance_path=first_clearance))
        return dict(original_clearance(**kwargs))

    monkeypatch.setattr(cli, "_verify_materializer_recovery", rebound_recovery)
    monkeypatch.setattr(
        cli,
        "_verify_materializer_clearance_lineage",
        rebound_clearance_lineage,
    )

    with pytest.raises(
        ValueError, match="duplicate or conflicting replacement recovery manifest"
    ):
        cli._prepare_replacement_recovery_consolidation(args)


def test_consolidation_indexes_clearance_for_each_active_tranche(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
    )
    fixture_record_index = cli._materializer_record_index
    clearance_index_calls = 0

    def count_clearance_indexes(
        records: list[dict[str, object]], *, label: str
    ) -> dict[tuple[str, str], dict[str, object]]:
        nonlocal clearance_index_calls
        if label == "replacement tranche clearance":
            clearance_index_calls += 1
        return fixture_record_index(records, label=label)  # type: ignore[return-value]

    monkeypatch.setattr(cli, "_materializer_record_index", count_clearance_indexes)

    prepared = cli._prepare_replacement_recovery_consolidation(args)

    assert len(prepared.manifest_records) == 3
    assert clearance_index_calls == 3


def test_consolidation_reuses_clearance_index_before_duplicate_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_paid = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        ledger_pairs=all_paid,
    )
    fixture_recovery = cli._verify_materializer_recovery
    fixture_record_index = cli._materializer_record_index
    first_tranche = True
    clearance_index_calls = 0

    def repeat_first_manifest_record(**kwargs: object) -> dict[str, object]:
        nonlocal first_tranche
        result = dict(fixture_recovery(**kwargs))
        if first_tranche:
            records = list(result["manifest_records"])  # type: ignore[arg-type]
            result["manifest_records"] = [*records, *records]
            first_tranche = False
        return result

    def count_clearance_indexes(
        records: list[dict[str, object]], *, label: str
    ) -> dict[tuple[str, str], dict[str, object]]:
        nonlocal clearance_index_calls
        if label == "replacement tranche clearance":
            clearance_index_calls += 1
        return fixture_record_index(records, label=label)  # type: ignore[return-value]

    monkeypatch.setattr(
        cli, "_verify_materializer_recovery", repeat_first_manifest_record
    )
    monkeypatch.setattr(cli, "_materializer_record_index", count_clearance_indexes)

    with pytest.raises(
        ValueError, match="duplicate or conflicting replacement recovery manifest"
    ):
        cli._prepare_replacement_recovery_consolidation(args)

    assert clearance_index_calls == 1


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


def test_consolidation_replays_each_recovery_at_its_authenticated_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_pairs = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=all_pairs)
    fixture_recovery = cli._verify_materializer_recovery
    observed: dict[str, set[tuple[str, str]]] = {}

    def capture_history(**kwargs: object) -> dict[str, object]:
        root = Path(kwargs["recovery_root"])  # type: ignore[arg-type]
        operations = kwargs["purchase_operations"]
        observed[root.parent.name] = {
            (operation["candidate_id"], operation["source_document_id"])
            for operation in operations  # type: ignore[union-attr]
        }
        return fixture_recovery(**kwargs)

    monkeypatch.setattr(cli, "_verify_materializer_recovery", capture_history)

    cli._prepare_replacement_recovery_consolidation(args)

    assert observed == {
        "initial": {("base-case", "base-doc")},
        "tranche-1": {("base-case", "base-doc"), ("case-1", "doc-1")},
        "tranche-2": all_pairs,
    }


def test_consolidation_threads_authenticated_resolved_transition_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_pairs = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=all_pairs)
    index = json.loads(args.tranche_index.read_bytes())
    sources = index["sources"]
    resolved_paths: list[Path] = []
    for ordinal, source in enumerate(sources):
        resolved_path = (
            tmp_path / f"resolver-{ordinal}" / "resolved-post-recovery-documents.jsonl"
        )
        _write_jsonl(resolved_path, [])
        source["resolved_post_recovery_documents"] = str(resolved_path)
        resolved_paths.append(resolved_path)
    history_clearance_card = Path(sources[0]["purchased_clearance_run_card"])
    _write_json(
        history_clearance_card,
        {"authenticated_successor_history": {"fixture": True}},
    )
    _write_json(args.tranche_index, index)

    initial_snapshot = cli.read_case_dev_purchase_snapshot(None)
    observed_run_cards: list[Path] = []
    issued_capabilities: list[object] = []

    def issue_transition_factory(**kwargs: object) -> Callable[[], object]:
        observed_run_cards.extend(kwargs["run_card_paths"])  # type: ignore[arg-type]

        def issue() -> object:
            capability = object()
            issued_capabilities.append(capability)
            return capability

        return issue

    monkeypatch.setattr(
        cli,
        "_issue_resolved_transition_capability_factory",
        issue_transition_factory,
    )
    monkeypatch.setattr(
        cli,
        "_consume_live_resolved_transition_evidence",
        lambda capability: (
            (initial_snapshot, {}, {}) if capability in issued_capabilities else None
        ),
    )
    original_history = cli._authenticated_pre_successor_purchase_snapshot
    observed_capabilities: list[tuple[object | None, object | None]] = []

    def authenticate_history(**kwargs: object) -> object:
        observed_capabilities.append(
            (
                kwargs.get("authority_transition_capability"),
                kwargs.get("attempt_transition_capability"),
            )
        )
        return original_history(**kwargs)

    monkeypatch.setattr(
        cli, "_authenticated_pre_successor_purchase_snapshot", authenticate_history
    )
    fixture_clearance = cli._verify_materializer_clearance_lineage
    observed_clearance_capabilities: list[tuple[object | None, ...]] = []

    def authenticate_clearance(**kwargs: object) -> object:
        observed_clearance_capabilities.append(
            (
                kwargs.get("authority_transition_capability"),
                kwargs.get("attempt_transition_capability"),
                kwargs.get("recovery_authority_transition_capability"),
                kwargs.get("recovery_attempt_transition_capability"),
            )
        )
        expected_prior = (
            initial_snapshot
            if Path(kwargs["run_card_path"]) == history_clearance_card
            else None
        )
        assert kwargs.get("resolved_transition_prior_snapshot") == expected_prior
        return fixture_clearance(**kwargs)

    monkeypatch.setattr(
        cli, "_verify_materializer_clearance_lineage", authenticate_clearance
    )

    cli._prepare_replacement_recovery_consolidation(args)

    expected_run_cards = [
        path.parent / "run-cards" / "resolve-post-recovery-documents.json"
        for path in resolved_paths
    ]
    assert observed_run_cards == expected_run_cards
    assert len(issued_capabilities) == 15
    assert len({id(capability) for capability in issued_capabilities}) == 15
    assert len(observed_capabilities) == 2
    assert all(authority is not attempt for authority, attempt in observed_capabilities)
    assert {
        id(capability) for pair in observed_capabilities for capability in pair
    } <= {id(capability) for capability in issued_capabilities}
    assert len(observed_clearance_capabilities) == 3
    assert (
        len({id(capability) for capability in observed_clearance_capabilities[0]}) == 4
    )
    assert all(
        capabilities[0] is not capabilities[2]
        and capabilities[1] is None
        and capabilities[3] is None
        for capabilities in observed_clearance_capabilities[1:]
    )


def test_consolidation_treats_post_purchase_replay_as_nested_descriptor() -> None:
    direct_path = Path("selection.jsonl")
    paths = cli._replacement_recovery_tranche_paths(
        {
            "kind": "initial",
            "ordinal": 0,
            "selection": str(direct_path),
            "post_purchase_replay": {
                "prior_ranked_result": "/frozen/prior-ranked-result.json"
            },
        }
    )

    assert paths == {"selection": direct_path.absolute()}


def test_consolidation_authenticates_v4_target_without_legacy_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transition = cast(Any, object())
    observed: list[tuple[object, object]] = []
    monkeypatch.setattr(
        cli, "ranked_reserve_result_bytes", lambda _result: b"canonical-v4"
    )
    monkeypatch.setattr(
        cli,
        "require_verified_post_purchase_replay",
        lambda result, replay: observed.append((result, replay)),
    )
    monkeypatch.setattr(
        cli,
        "verify_legacy_ranked_reserve_bridge",
        lambda **_kwargs: pytest.fail("v4 target used the legacy bridge"),
    )
    result = {"schema_version": cli.POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION}

    verified = cli._verify_consolidation_target_ranked_precursor(
        precursor_result=result,
        precursor_result_bytes=b"canonical-v4",
        post_purchase_replay=transition,
    )

    assert verified is None
    assert observed == [(result, transition)]


def test_consolidation_rejects_noncanonical_v4_target_before_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli, "ranked_reserve_result_bytes", lambda _result: b"canonical-v4"
    )
    result = {"schema_version": cli.POST_PURCHASE_REPLAY_RESULT_SCHEMA_VERSION}

    with pytest.raises(ValueError, match="not canonical"):
        cli._verify_consolidation_target_ranked_precursor(
            precursor_result=result,
            precursor_result_bytes=b"changed-v4",
            post_purchase_replay=cast(Any, object()),
        )


def test_consolidation_rejects_ledger_drift_before_completed_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    all_pairs = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=all_pairs)
    operations = tuple(
        {"candidate_id": candidate_id, "source_document_id": document_id}
        for candidate_id, document_id in sorted(all_pairs)
    )
    snapshots = iter(
        (
            SimpleNamespace(
                operations=operations,
                purchase_state_sha256="a" * 64,
                committed_amount_usd="0.00",
            ),
            SimpleNamespace(
                operations=operations,
                purchase_state_sha256="b" * 64,
                committed_amount_usd="0.00",
            ),
        )
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: next(snapshots),
    )

    with pytest.raises(
        ValueError,
        match="purchase ledger changed during replacement recovery consolidation",
    ):
        cli._cmd_consolidate_replacement_recovery(args)

    assert not (
        args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
    ).exists()


@pytest.mark.parametrize("drift", ["budget", "recovery"])
def test_consolidation_rejects_reverse_forward_source_drift_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    all_pairs = {
        ("base-case", "base-doc"),
        ("case-1", "doc-1"),
        ("case-2", "doc-2"),
    }
    args, _ = _prepare_fixture(tmp_path, monkeypatch, ledger_pairs=all_pairs)
    original_history = cli._authenticated_pre_successor_purchase_snapshot
    original_recovery = cli._verify_materializer_recovery
    changed = False
    marker = _write_json(tmp_path / "recovery-marker.json", {"version": 1})

    def drift_after_reverse(**kwargs: object) -> object:
        nonlocal changed
        result = original_history(**kwargs)
        if changed:
            return result
        changed = True
        if drift == "budget":
            budget_path = Path(kwargs["expected_budget_plan_path"])  # type: ignore[arg-type]
            capture = kwargs["capture"]
            capture(budget_path, label="test reverse budget")  # type: ignore[operator]
            budget_path.write_bytes(budget_path.read_bytes() + b" ")
            return result
        old_bytes = marker.read_bytes()
        marker.write_text(
            json.dumps({"version": 2}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        snapshot, recovery_bytes = result  # type: ignore[misc]
        return snapshot, {**recovery_bytes, str(marker.resolve()): old_bytes}

    def forward_recovery(**kwargs: object) -> dict[str, object]:
        result = dict(original_recovery(**kwargs))
        if drift == "recovery":
            result["verified_artifact_bytes"] = {
                str(marker.resolve()): marker.read_bytes()
            }
        return result

    monkeypatch.setattr(
        cli, "_authenticated_pre_successor_purchase_snapshot", drift_after_reverse
    )
    monkeypatch.setattr(cli, "_verify_materializer_recovery", forward_recovery)

    with pytest.raises(cli.CommandError, match="conflicts with prior snapshot"):
        cli._cmd_consolidate_replacement_recovery(args)

    assert not (
        args.output_root / "run-cards" / "consolidate-replacement-recovery.json"
    ).exists()


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
        match="final active paid-gap scope differs from canonical ledger coverage",
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
            "verified_artifact_bytes": {
                str(args.selection.resolve()): args.selection.read_bytes(),
                str(args.target_purchased_manifest.resolve()): (
                    args.target_purchased_manifest.read_bytes()
                ),
            },
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


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda replay: {**replay, "extra": "/extra"}, "extra or missing"),
        (
            lambda replay: {
                key: value for key, value in replay.items() if key != "cohort_policy"
            },
            "extra or missing",
        ),
        (
            lambda replay: {**replay, "cohort_policy": "relative.json"},
            "paths must be absolute",
        ),
        (
            lambda replay: {**replay, "cohort_policy": 7},
            "path is invalid",
        ),
    ),
)
def test_recovery_index_rejects_noncanonical_post_purchase_replay_bundle(
    mutation: Callable[[dict[str, object]], dict[str, object]],
    message: str,
) -> None:
    replay = {
        "prior_ranked_result": "/prior-result.json",
        "prior_replacement_selection": "/selection.jsonl",
        "prior_replacement_budget_plan": "/budget.json",
        "replacement_purchase_authority": "/authority.json",
        "replacement_controlled_private_root": "/private",
        "cohort_policy": "/cohort-policy.json",
    }
    initial = {
        "kind": "initial_v2",
        "ordinal": 0,
        "recovery_root": "/initial",
        "selection": "/selection",
        "purchased_clearance": "/clearance",
        "purchased_clearance_run_card": "/card",
        "resolved_post_recovery_documents": None,
        "post_purchase_replay": mutation(replay),
    }

    with pytest.raises(ValueError, match=message):
        cli._validated_replacement_recovery_sources(
            {
                "schema_version": (
                    "legalforecast.replacement_recovery_tranche_index.v2"
                ),
                "sources": [initial],
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
