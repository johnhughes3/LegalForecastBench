from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion import cohort_document_materializer as materializer_module
from legalforecast.ingestion.cohort_document_materializer import (
    CohortDocumentMaterializationError,
    DocumentSource,
    cleanup_orphaned_cohort_document_temporaries,
    prepare_cohort_document_materialization,
    publish_cohort_documents,
)


def _source(
    tmp_path: Path,
    *,
    phase: str,
    candidate_id: str,
    document_id: str,
) -> tuple[DocumentSource, tuple[str, str]]:
    root = tmp_path / phase
    root.mkdir()
    payload = f"%PDF-1.4\n{phase}-{candidate_id}-{document_id}\n%%EOF".encode()
    path = root / f"{document_id}.pdf"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest: dict[str, Any] = {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "local_path": path.name,
        "sha256": digest,
        "byte_count": len(payload),
        "free_or_purchased": phase,
        "source_url": f"https://storage.courtlistener.com/{document_id}.pdf",
    }
    clearance: dict[str, Any] = {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "local_path": path.name,
        "sha256": digest,
        "byte_count": len(payload),
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://cycle-1/clearance",
        "reviewed_at": "2026-07-15T12:00:00Z",
        "free_or_purchased": phase,
    }
    return (
        DocumentSource(
            phase=phase,
            document_root=root,
            manifest=(manifest,),
            clearance=(clearance,),
        ),
        (candidate_id, document_id),
    )


def test_materialize_cohort_documents_help_is_authoritative(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["acquisition", "materialize-cohort-documents", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "authenticated target-cohort preparation" in normalized
    assert "authenticated purchased-document recovery" in normalized
    assert "--free-disclosure-clearance" in output
    assert "--purchased-disclosure-clearance" in output
    assert "never mutate either source" in normalized
    assert "plan-parse-documents" in normalized


def test_free_only_cli_materializes_and_replays_without_paid_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation = tmp_path / "preparation"
    free_root = preparation / "documents/free"
    free_root.mkdir(parents=True)
    payload = b"%PDF-1.4\nfree-only\n%%EOF"
    source_path = free_root / "motion.pdf"
    source_path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "candidate_id": "candidate-1",
        "source_document_id": "motion-1",
        "local_path": "motion.pdf",
        "sha256": digest,
        "byte_count": len(payload),
        "free_or_purchased": "free",
    }
    clearance = {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": "candidate-1",
        "source_document_id": "motion-1",
        "local_path": "motion.pdf",
        "sha256": digest,
        "byte_count": len(payload),
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "reviewer_id": "reviewer:john",
        "controlled_store_provenance": "private-store://cycle-1/clearance",
        "reviewed_at": "2026-07-27T12:00:00Z",
        "free_or_purchased": "free",
    }
    preparation_summary = preparation / "target-cohort-preparation-summary.json"
    preparation_config = preparation / "target-cohort-config.json"
    success_card = preparation / "run-cards/prepare-target-cohort.json"
    snapshot = tmp_path / "snapshot.json"
    target = tmp_path / "target"
    target.mkdir()
    selection = target / "target-cohort-selection.jsonl"
    free_manifest = target / "free-document-downloads.jsonl"
    free_clearance = target / "disclosure-clearance.jsonl"
    restriction = target / "restriction-evidence.jsonl"
    projection_summary = target / "target-cohort-projection.json"
    projection_card = target / "run-cards/project-target-cohort.json"
    cohort_policy = tmp_path / "cohort-policy.json"
    private_root = tmp_path / "private"
    checkpoint = private_root / "purchase-approval-checkpoint.json"
    approval_card = private_root / "run-cards/record-purchase-approval.json"
    fee_schedule = tmp_path / "fee-schedule.json"
    for path in (
        preparation_summary,
        preparation_config,
        success_card,
        snapshot,
        projection_summary,
        projection_card,
        cohort_policy,
        checkpoint,
        approval_card,
        fee_schedule,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    selection.write_text(
        json.dumps(
            {
                "candidate_id": "candidate-1",
                "documents": [{"source_document_id": "motion-1"}],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    free_manifest.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    free_clearance.write_text(
        json.dumps(clearance, sort_keys=True) + "\n", encoding="utf-8"
    )
    restriction.write_text("\n", encoding="utf-8")
    projection_paths = (
        selection,
        free_manifest,
        free_clearance,
        restriction,
        projection_summary,
        projection_card,
    )

    monkeypatch.setattr(
        cli,
        "_verify_completed_preparation_for_frontier",
        lambda **_kwargs: SimpleNamespace(
            target_case_count=1,
            success_run_card_path=success_card,
        ),
    )

    def verified_projection(**_kwargs: object) -> dict[str, object]:
        return {
            "summary_path": projection_summary,
            "run_card_path": projection_card,
            "selection_path": selection,
            "selection_records": tuple(cli._read_records(selection)),
            "free_manifest_path": free_manifest,
            "free_manifest": (manifest,),
            "purchased_manifest": (),
            "free_clearance": (clearance,),
            "restriction_path": restriction,
            "restriction_records": (),
            "selected_document_keys": {("candidate-1", "motion-1")},
            "verified_artifact_bytes": {
                os.path.abspath(path): path.read_bytes() for path in projection_paths
            },
        }

    monkeypatch.setattr(cli, "_verify_materializer_projection", verified_projection)
    approval = SimpleNamespace(
        decision="free_only",
        request=SimpleNamespace(
            purchase_document_count=0,
            projected_cost_usd="0.00",
            request_sha256="a" * 64,
        ),
    )
    monkeypatch.setattr(
        cli,
        "verify_free_only_materialization_authority",
        lambda **_kwargs: approval,
    )
    output = tmp_path / "materialized"
    ledger = tmp_path / "never-created.sqlite3"
    command = [
        "acquisition",
        "materialize-cohort-documents",
        "--output-root",
        str(output),
        "--preparation-root",
        str(preparation),
        "--preparation-summary",
        str(preparation_summary),
        "--preparation-config",
        str(preparation_config),
        "--snapshot-manifest",
        str(snapshot),
        "--target-cohort-root",
        str(target),
        "--free-disclosure-clearance",
        str(free_clearance),
        "--cohort-policy",
        str(cohort_policy),
        "--controlled-private-root",
        str(private_root),
        "--free-only-approval-checkpoint",
        str(checkpoint),
        "--free-only-approval-run-card",
        str(approval_card),
        "--free-only-fee-schedule",
        str(fee_schedule),
        "--free-only-canonical-ledger-path",
        str(ledger),
        "--execute",
    ]

    assert cli.main(command) == 0
    run_card = output / "run-cards/materialize-cohort-documents.json"
    card = json.loads(run_card.read_text())
    assert card["authority_mode"] == "free_only"
    assert card["purchased_document_count"] == 0
    assert not ledger.exists()
    replay = cli._verify_materialized_downstream_lineage(
        run_card_path=run_card,
        manifest_path=output / "document-downloads-merged.jsonl",
        clearance_path=output / "disclosure-clearance.jsonl",
        document_root=output / "documents",
        selection_path=selection,
        controlled_private_root=private_root,
    )
    assert len(replay.manifest_records) == 1
    assert replay.resolved_records == ()
    original_card_bytes = run_card.read_bytes()
    for tampered_mode in (None, "unknown"):
        tampered = dict(card)
        if tampered_mode is None:
            tampered.pop("authority_mode")
        else:
            tampered["authority_mode"] = tampered_mode
        run_card.write_text(json.dumps(tampered, sort_keys=True) + "\n")
        with pytest.raises(cli.CommandError):
            cli._verify_materialized_downstream_lineage(
                run_card_path=run_card,
                manifest_path=output / "document-downloads-merged.jsonl",
                clearance_path=output / "disclosure-clearance.jsonl",
                document_root=output / "documents",
                selection_path=selection,
                controlled_private_root=private_root,
            )
    run_card.write_bytes(original_card_bytes)


@pytest.mark.parametrize(
    "paid_field",
    [
        "purchased_recovery_root",
        "purchased_disclosure_clearance",
        "purchased_clearance_run_card",
        "purchase_policy",
        "purchase_ledger",
        "purchase_ledger_initialization_receipt",
        "resolved_post_recovery_documents",
    ],
)
def test_free_only_cli_rejects_any_paid_runtime_input_before_output(
    tmp_path: Path,
    paid_field: str,
) -> None:
    args = SimpleNamespace(
        free_only_approval_checkpoint=tmp_path / "checkpoint.json",
        free_only_approval_run_card=tmp_path / "card.json",
        free_only_fee_schedule=tmp_path / "fees.json",
        free_only_canonical_ledger_path=tmp_path / "ledger.sqlite3",
        controlled_private_root=tmp_path / "private",
        purchased_recovery_root=None,
        purchased_disclosure_clearance=None,
        purchased_clearance_run_card=None,
        purchase_policy=None,
        purchase_ledger=None,
        purchase_ledger_initialization_receipt=None,
        resolved_post_recovery_documents=None,
    )
    setattr(args, paid_field, tmp_path / "paid")

    with pytest.raises(cli.CommandError, match="rejects paid-runtime inputs"):
        cli._cmd_acquisition_materialize_cohort_documents(args)


def test_free_only_cli_rejects_partial_authority_before_output(tmp_path: Path) -> None:
    args = SimpleNamespace(
        free_only_approval_checkpoint=tmp_path / "checkpoint.json",
        free_only_approval_run_card=None,
        free_only_fee_schedule=None,
        free_only_canonical_ledger_path=None,
        controlled_private_root=tmp_path / "private",
        purchased_recovery_root=None,
        purchased_disclosure_clearance=None,
        purchased_clearance_run_card=None,
        purchase_policy=None,
        purchase_ledger=None,
        purchase_ledger_initialization_receipt=None,
        resolved_post_recovery_documents=None,
    )

    with pytest.raises(cli.CommandError, match="all four free-only"):
        cli._cmd_acquisition_materialize_cohort_documents(args)


def test_materializer_requires_exact_selected_identity_coverage(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="do not exactly cover",
    ):
        prepare_cohort_document_materialization(
            (free, purchased),
            selected_document_keys={
                free_key,
                purchased_key,
                ("candidate-1", "order-1"),
            },
            output_root=tmp_path / "output",
        )


def test_materializer_accepts_exact_free_only_source(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )

    prepared = prepare_cohort_document_materialization(
        (free,),
        selected_document_keys={free_key},
        output_root=tmp_path / "output",
    )

    assert prepared.summary["free_document_count"] == 1
    assert prepared.summary["purchased_document_count"] == 0
    assert [row["free_or_purchased"] for row in prepared.manifest] == ["free"]


def test_materializer_rejects_purchased_only_source(tmp_path: Path) -> None:
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="ordered exactly as free",
    ):
        prepare_cohort_document_materialization(
            (purchased,),
            selected_document_keys={purchased_key},
            output_root=tmp_path / "output",
        )


def test_materializer_publishes_two_sources_content_addressably_and_resumes(
    tmp_path: Path,
) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    source_bytes = {
        path: path.read_bytes()
        for root in (free.document_root, purchased.document_root)
        for path in root.rglob("*.pdf")
    }
    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
    )

    publish_cohort_documents(prepared.documents)
    first_stats = {
        document.destination: document.destination.stat()
        for document in prepared.documents
    }
    publish_cohort_documents(prepared.documents)

    assert [row["free_or_purchased"] for row in prepared.manifest] == [
        "free",
        "purchased",
    ]
    for document in prepared.documents:
        expected_hash = document.manifest_record["sha256"]
        assert document.destination == (
            tmp_path
            / "output/documents/sha256"
            / str(expected_hash)[:2]
            / f"{expected_hash}.pdf"
        )
        assert (
            document.destination.stat().st_ino
            == first_stats[document.destination].st_ino
        )
    assert all(path.read_bytes() == payload for path, payload in source_bytes.items())


def test_materializer_removes_partial_temp_and_resumes_after_copy_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
    )
    real_write_all = materializer_module._write_all
    calls = 0

    def fail_once(fd: int, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            os.write(fd, payload[: max(1, len(payload) // 2)])
            raise OSError("injected mid-copy failure")
        real_write_all(fd, payload)

    monkeypatch.setattr(materializer_module, "_write_all", fail_once)
    with pytest.raises(OSError, match="injected mid-copy"):
        publish_cohort_documents(prepared.documents)

    assert not list((tmp_path / "output").rglob("*.tmp"))
    monkeypatch.setattr(materializer_module, "_write_all", real_write_all)
    publish_cohort_documents(prepared.documents)
    assert all(document.destination.is_file() for document in prepared.documents)


def test_materializer_recovers_post_link_crash_temporary(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
    )
    document = prepared.documents[0]
    document.destination.parent.mkdir(parents=True)
    temporary = document.destination.with_name(
        f".{document.destination.name}.1234.crash.tmp"
    )
    temporary.write_bytes(document.source.read_bytes())
    os.link(temporary, document.destination)
    assert document.destination.stat().st_nlink == 2

    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
    )
    publish_cohort_documents(prepared.documents)
    assert document.destination.stat().st_nlink == 1
    assert not temporary.exists()
    publish_cohort_documents(prepared.documents)


def test_materializer_recovers_pre_link_partial_temporary(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
    )
    document = prepared.documents[0]
    document.destination.parent.mkdir(parents=True)
    temporary = document.destination.with_name(
        f".{document.destination.name}.1234.partial.tmp"
    )
    temporary.write_bytes(b"partial")

    cleanup_orphaned_cohort_document_temporaries(prepared.documents)

    assert not temporary.exists()
    publish_cohort_documents(prepared.documents)
    assert all(item.destination.is_file() for item in prepared.documents)


def test_materializer_rejects_cross_candidate_substitution(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, _ = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-2",
        document_id="motion-1",
    )

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="cross-candidate document substitution",
    ):
        prepare_cohort_document_materialization(
            (free, purchased),
            selected_document_keys={free_key, ("candidate-1", "motion-1")},
            output_root=tmp_path / "output",
        )


def test_materializer_rejects_source_hardlinks(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    source_path = next(free.document_root.rglob("*.pdf"))
    os.link(source_path, free.document_root / "alias.pdf")

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="singly linked regular file",
    ):
        prepare_cohort_document_materialization(
            (free, purchased),
            selected_document_keys={free_key, purchased_key},
            output_root=tmp_path / "output",
        )


def test_materializer_rejects_dangling_destination_symlink(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
    )
    destination = prepared.documents[0].destination
    destination.parent.mkdir(parents=True)
    destination.symlink_to(destination.parent / "missing.pdf")

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="not a singly linked regular file",
    ):
        publish_cohort_documents(prepared.documents)


def test_materializer_binds_unknown_origin_resolved_proof(tmp_path: Path) -> None:
    free, free_key = _source(
        tmp_path,
        phase="free",
        candidate_id="candidate-1",
        document_id="complaint-1",
    )
    purchased, purchased_key = _source(
        tmp_path,
        phase="purchased",
        candidate_id="candidate-1",
        document_id="motion-1",
    )
    purchased_manifest_source = dict(purchased.manifest[0])
    purchased_manifest_source["recovery_origin"] = "unknown_status_attempt"
    purchased = DocumentSource(
        phase=purchased.phase,
        document_root=purchased.document_root,
        manifest=(purchased_manifest_source,),
        clearance=purchased.clearance,
    )
    resolved = {
        "candidate_id": purchased_key[0],
        "source_document_id": purchased_key[1],
        "recovery_origin": "unknown_status_attempt",
        "record_sha256": "a" * 64,
    }

    prepared = prepare_cohort_document_materialization(
        (free, purchased),
        selected_document_keys={free_key, purchased_key},
        output_root=tmp_path / "output",
        resolved_post_recovery_records=(resolved,),
    )
    purchased_manifest = next(
        row for row in prepared.manifest if row["free_or_purchased"] == "purchased"
    )
    purchased_clearance = next(
        row for row in prepared.clearance if row["free_or_purchased"] == "purchased"
    )
    assert purchased_manifest["resolved_post_recovery_sha256"] == "a" * 64
    assert purchased_clearance["resolved_post_recovery_sha256"] == "a" * 64
    [derivation] = [
        row
        for row in cli._build_materializer_derivations(
            materialization=prepared,
            free_manifest=free.manifest,
            free_clearance=free.clearance,
            purchased_manifest=purchased.manifest,
            purchased_clearance=purchased.clearance,
            resolved_records=(resolved,),
        )
        if row["free_or_purchased"] == "purchased"
    ]
    assert derivation["resolved_post_recovery_sha256"] == "a" * 64

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="resolved post-recovery proof coverage differs",
    ):
        prepare_cohort_document_materialization(
            (free, purchased),
            selected_document_keys={free_key, purchased_key},
            output_root=tmp_path / "missing-resolved",
        )


def test_materialized_parse_rejects_stripped_unknown_origin_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "_preflight_materialization_purchase_runtime",
        lambda _args: None,
    )
    document = tmp_path / "motion.pdf"
    payload = b"%PDF-1.4\nunknown-origin\n%%EOF"
    document.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    selection = tmp_path / "selection.jsonl"
    requests = tmp_path / "requests.jsonl"
    clearance = tmp_path / "clearance.jsonl"
    resolved = tmp_path / "resolved.jsonl"
    card = tmp_path / "materialization-card.json"
    restriction = tmp_path / "restriction.jsonl"
    derivations = tmp_path / "derivations.jsonl"
    fixture_markdown = tmp_path / "markdown-fixture"
    fixture_markdown.mkdir()
    (fixture_markdown / "motion-1.md").write_text("Public motion")
    marker = "legalforecast.cohort_document_materialization.v1"
    cli._write_jsonl(
        selection,
        [
            {
                "candidate_id": "candidate-1",
                "documents": [
                    {
                        "source_document_id": "motion-1",
                        "requires_paid_recovery": True,
                        "redaction_or_seal_status": "public",
                        "is_sealed": False,
                        "is_private": False,
                    }
                ],
            }
        ],
    )
    cli._write_jsonl(
        requests,
        [
            {
                "candidate_id": "candidate-1",
                "source_document_id": "motion-1",
                "input_path": str(document),
                "expected_sha256": digest,
                "expected_byte_count": len(payload),
                "materialization_schema_version": marker,
            }
        ],
    )
    cli._write_jsonl(
        clearance,
        [
            {
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "candidate_id": "candidate-1",
                "source_document_id": "motion-1",
                "sha256": digest,
                "byte_count": len(payload),
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["courtlistener_public_record"],
                "reviewer_id": "reviewer:john",
                "controlled_store_provenance": "private-store://cycle-1/review",
                "reviewed_at": "2026-07-15T12:00:00Z",
                "materialization_schema_version": marker,
            }
        ],
    )
    cli._write_jsonl(
        resolved,
        [
            {
                "candidate_id": "candidate-1",
                "source_document_id": "motion-1",
            }
        ],
    )
    cli._write_jsonl(restriction, [])
    cli._write_jsonl(derivations, [])
    card.write_text(
        '{"output_paths":["a","b","c","d","e","f"]}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        lambda **_kwargs: cli._VerifiedMaterializedDownstreamLineage(
            paths=(card, restriction, derivations, resolved),
            artifact_bytes={},
            manifest_records=(),
            clearance_records=tuple(cli._read_records(clearance)),
            selection_records=tuple(cli._read_records(selection)),
            resolved_records=tuple(cli._read_records(resolved)),
            document_tree={},
        ),
    )

    assert (
        cli.main(
            [
                "acquisition",
                "parse-documents",
                "--selection",
                str(selection),
                "--requests",
                str(requests),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(card),
                "--fixture-markdown-dir",
                str(fixture_markdown),
                "--output-root",
                str(tmp_path / "parse-output"),
                "--execute",
            ]
        )
        == 2
    )
    assert "resolved post-recovery parse coverage mismatch" in capsys.readouterr().err


def test_verified_artifact_snapshot_merge_rejects_unequal_overlap() -> None:
    target = {"/tmp/source.json": b"A"}
    cli._merge_verified_artifact_bytes(
        target,
        {"/tmp/source.json": b"A"},
        label="fixture",
    )
    assert target == {"/tmp/source.json": b"A"}

    with pytest.raises(cli.CommandError, match="snapshot collision"):
        cli._merge_verified_artifact_bytes(
            target,
            {"/tmp/source.json": b"B"},
            label="fixture",
        )
