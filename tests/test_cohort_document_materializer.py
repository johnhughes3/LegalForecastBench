from __future__ import annotations

import errno
import hashlib
import json
import os
import sqlite3
import stat
from collections.abc import Mapping
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
    require_materializer_artifact,
    validate_materializer_writable_paths,
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


def test_materializer_writable_path_validation_accepts_disjoint_outputs(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"

    validate_materializer_writable_paths(
        output_root=output_root,
        writable_paths=(output_root / "manifest.jsonl", output_root / "run-card.json"),
        document_root=output_root / "documents",
        input_paths=(tmp_path / "immutable-input",),
    )


def test_materializer_writable_path_validation_rejects_duplicate_outputs(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    shared = output_root / "shared.json"

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="materializer writable paths must be pairwise distinct",
    ):
        validate_materializer_writable_paths(
            output_root=output_root,
            writable_paths=(shared, shared),
            document_root=output_root / "documents",
            input_paths=(),
        )


def test_materializer_writable_path_validation_rejects_document_tree_overlap(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    document_root = output_root / "documents"

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="materializer metadata outputs must not overlap the document tree",
    ):
        validate_materializer_writable_paths(
            output_root=output_root,
            writable_paths=(document_root / "metadata.json",),
            document_root=document_root,
            input_paths=(),
        )


def test_materializer_writable_path_validation_rejects_output_root_escape(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    escaped = tmp_path / "escaped.json"

    with pytest.raises(CohortDocumentMaterializationError) as exc_info:
        validate_materializer_writable_paths(
            output_root=output_root,
            writable_paths=(escaped,),
            document_root=output_root / "documents",
            input_paths=(),
        )

    assert str(exc_info.value) == (
        f"materializer writable path escapes output root: {escaped}"
    )


def test_materializer_writable_path_validation_rejects_immutable_input_overlap(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    immutable_input = output_root / "immutable"
    writable = immutable_input / "metadata.json"

    with pytest.raises(CohortDocumentMaterializationError) as exc_info:
        validate_materializer_writable_paths(
            output_root=output_root,
            writable_paths=(writable,),
            document_root=output_root / "documents",
            input_paths=(immutable_input,),
        )

    assert str(exc_info.value) == (
        f"materializer writable path overlaps immutable input: {writable}"
    )


def test_materializer_writable_path_validation_preserves_cli_error_contract(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    shared = output_root / "shared.json"

    with pytest.raises(cli.CommandError) as exc_info:
        cli._validate_materializer_writable_paths(
            output_root=output_root,
            writable_paths=(shared, shared),
            document_root=output_root / "documents",
            input_paths=(),
        )

    assert str(exc_info.value) == (
        "materializer writable paths must be pairwise distinct"
    )


def test_materializer_artifact_validation_accepts_regular_single_link_file(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}\n", encoding="utf-8")

    assert require_materializer_artifact(artifact, label="test artifact") == b"{}\n"


def test_materializer_artifact_consumption_is_bound_to_validated_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b'"validated"\n')
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(b'"replacement"\n')
    retained = tmp_path / "retained.json"
    real_fstat = os.fstat
    replaced = False
    validated_ctime_ns: int | None = None

    def replace_after_validation(descriptor: int) -> Any:
        nonlocal replaced, validated_ctime_ns
        metadata = real_fstat(descriptor)
        if stat.S_ISREG(metadata.st_mode) and not replaced:
            validated_ctime_ns = metadata.st_ctime_ns
            artifact.rename(retained)
            replacement.rename(artifact)
            replaced = True
            return metadata
        if validated_ctime_ns is None:
            return metadata
        return SimpleNamespace(
            st_dev=metadata.st_dev,
            st_ino=metadata.st_ino,
            st_mode=metadata.st_mode,
            st_size=metadata.st_size,
            st_mtime_ns=metadata.st_mtime_ns,
            st_ctime_ns=validated_ctime_ns + 1,
            st_nlink=metadata.st_nlink,
        )

    monkeypatch.setattr(materializer_module.os, "fstat", replace_after_validation)

    commitment = cli._materializer_file_commitment(artifact)

    assert replaced is True
    assert commitment == {
        "path": os.path.abspath(artifact),
        "sha256": "sha256:" + hashlib.sha256(b'"validated"\n').hexdigest(),
    }
    assert artifact.read_bytes() == b'"replacement"\n'
    assert retained.read_bytes() == b'"validated"\n'


def test_materializer_artifact_rejects_same_size_overwrite_with_restored_mtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact.json"
    original = b'"original"\n'
    replacement = b'"mutated!"\n'
    assert len(original) == len(replacement)
    artifact.write_bytes(original)
    before = artifact.stat()
    real_read = os.read
    real_fstat = os.fstat
    overwritten = False

    def overwrite_after_read(descriptor: int, size: int) -> bytes:
        nonlocal overwritten
        payload = real_read(descriptor, size)
        if payload and not overwritten:
            artifact.write_bytes(replacement)
            os.utime(
                artifact,
                ns=(before.st_atime_ns, before.st_mtime_ns),
            )
            overwritten = True
        return payload

    def expose_overwrite_ctime(descriptor: int) -> Any:
        metadata = real_fstat(descriptor)
        if not overwritten:
            return metadata
        return SimpleNamespace(
            st_dev=metadata.st_dev,
            st_ino=metadata.st_ino,
            st_mode=metadata.st_mode,
            st_size=metadata.st_size,
            st_mtime_ns=metadata.st_mtime_ns,
            st_ctime_ns=before.st_ctime_ns + 1,
            st_nlink=metadata.st_nlink,
        )

    monkeypatch.setattr(materializer_module.os, "read", overwrite_after_read)
    monkeypatch.setattr(materializer_module.os, "fstat", expose_overwrite_ctime)

    with pytest.raises(
        CohortDocumentMaterializationError,
        match="test artifact changed while it was being read",
    ):
        require_materializer_artifact(artifact, label="test artifact")

    after = artifact.stat()
    assert overwritten is True
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns
    assert artifact.read_bytes() == replacement


def test_materializer_commitment_lexically_normalizes_parent_components(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"{}\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    path_with_parent = nested / ".." / artifact.name

    commitment = cli._materializer_file_commitment(path_with_parent)

    assert commitment == {
        "path": str(artifact),
        "sha256": "sha256:" + hashlib.sha256(b"{}\n").hexdigest(),
    }


def test_materializer_artifact_validation_rejects_symlink_component(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    artifact = tmp_path / "artifact.json"
    artifact.symlink_to(target)

    with pytest.raises(CohortDocumentMaterializationError) as exc_info:
        require_materializer_artifact(artifact, label="test artifact")

    assert str(exc_info.value) == f"symlink in trusted root path: {artifact}"


@pytest.mark.skipif(not hasattr(os, "O_PATH"), reason="requires O_PATH")
def test_materializer_artifact_traverses_search_only_directory(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    artifact = protected / "artifact.json"
    artifact.write_bytes(b"{}\n")
    protected.chmod(0o111)
    try:
        assert require_materializer_artifact(artifact, label="test artifact") == b"{}\n"
    finally:
        protected.chmod(0o755)


@pytest.mark.parametrize("kind", ("missing", "directory", "fifo"))
def test_materializer_artifact_validation_rejects_non_file(
    tmp_path: Path,
    kind: str,
) -> None:
    artifact = tmp_path / "artifact"
    if kind == "directory":
        artifact.mkdir()
    elif kind == "fifo":
        os.mkfifo(artifact)

    with pytest.raises(CohortDocumentMaterializationError) as exc_info:
        require_materializer_artifact(artifact, label="test artifact")

    assert str(exc_info.value) == (
        f"test artifact must be a regular non-symlink file: {artifact}"
    )


def test_materializer_artifact_validation_rejects_hardlink(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    artifact = tmp_path / "artifact.json"
    artifact.hardlink_to(source)

    with pytest.raises(CohortDocumentMaterializationError) as exc_info:
        require_materializer_artifact(artifact, label="test artifact")

    assert str(exc_info.value) == f"test artifact must not be hardlinked: {artifact}"


def test_materializer_artifact_validation_normalizes_open_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}\n", encoding="utf-8")
    real_open = os.open

    def deny_artifact_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == artifact.name:
            raise PermissionError(
                errno.EACCES,
                os.strerror(errno.EACCES),
                artifact,
            )
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(materializer_module.os, "open", deny_artifact_open)

    with pytest.raises(CohortDocumentMaterializationError) as exc_info:
        require_materializer_artifact(artifact, label="test artifact")

    assert str(exc_info.value) == (
        f"test artifact must be a regular non-symlink file: {artifact}"
    )


def test_materializer_artifact_validation_preserves_cli_error_contract(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()

    with pytest.raises(cli.CommandError) as exc_info:
        cli._require_materializer_artifact(artifact, label="test artifact")

    assert str(exc_info.value) == (
        f"test artifact must be a regular non-symlink file: {artifact}"
    )
    assert exc_info.value.__cause__ is None


def test_materializer_artifact_validation_preserves_cli_component_error_cause(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    artifact = tmp_path / "artifact.json"
    artifact.symlink_to(target)

    with pytest.raises(cli.CommandError) as exc_info:
        cli._require_materializer_artifact(artifact, label="test artifact")

    assert str(exc_info.value) == f"symlink in trusted root path: {artifact}"
    assert isinstance(exc_info.value.__cause__, CohortDocumentMaterializationError)


def test_provider_journal_snapshot_includes_committed_wal_rows(tmp_path: Path) -> None:
    journal = tmp_path / "provider.sqlite3"
    connection = sqlite3.connect(journal, isolation_level=None)
    try:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        connection.execute("PRAGMA wal_autocheckpoint = 0")
        connection.execute(
            """CREATE TABLE provider_attempts (
                stage TEXT NOT NULL,
                logical_call_key TEXT NOT NULL,
                attempt_ordinal INTEGER NOT NULL,
                status TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO provider_attempts VALUES (?, ?, ?, ?)",
            ("llm-unitize", "unit-1", 1, "settled"),
        )
        assert Path(f"{journal}-wal").is_file()

        records, _commitment = cli._provider_journal_stage_snapshot(
            journal, stage="llm-unitize"
        )
    finally:
        connection.close()

    assert records == (
        {
            "stage": "llm-unitize",
            "logical_call_key": "unit-1",
            "attempt_ordinal": 1,
            "status": "settled",
        },
    )


def test_provider_journal_snapshot_rejects_commit_after_main_recheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = tmp_path / "provider.sqlite3"
    writer = sqlite3.connect(journal, isolation_level=None)
    try:
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute(
            """CREATE TABLE provider_attempts (
                stage TEXT NOT NULL,
                logical_call_key TEXT NOT NULL,
                attempt_ordinal INTEGER NOT NULL,
                status TEXT NOT NULL
            )"""
        )
        assert writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone() == (
            0,
            0,
            0,
        )
        real_optional = cli._optional_materializer_artifact
        probes = 0

        def commit_before_final_wal_probe(path: Path, *, label: str) -> bytes | None:
            nonlocal probes
            probes += 1
            if probes == 2:
                writer.execute(
                    "INSERT INTO provider_attempts VALUES (?, ?, ?, ?)",
                    ("llm-unitize", "unit-2", 1, "settled"),
                )
                writer.execute("PRAGMA busy_timeout = 0")
                assert (
                    writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 1
                )
            return real_optional(path, label=label)

        monkeypatch.setattr(
            cli,
            "_optional_materializer_artifact",
            commit_before_final_wal_probe,
        )

        with pytest.raises(
            cli.CommandError,
            match="llm-unitize provider journal changed during snapshot",
        ):
            snapshot = cli._provider_journal_database_snapshot(
                journal,
                stage="llm-unitize",
            )
            snapshot.close()
    finally:
        writer.close()


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
    assert "--purchase-result" in output
    assert "--purchase-run-card" in output
    assert "never mutate either source" in normalized
    assert "plan-parse-documents" in normalized


def test_free_only_cli_materializes_and_replays_without_paid_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    final_snapshots: dict[Path, bytes] = {}
    original_snapshot_check = cli._require_snapshot_unchanged

    def capture_final_snapshot(
        snapshots: Mapping[Path, bytes],
        *,
        label: str,
    ) -> None:
        if label == "materialization downstream lineage artifact":
            final_snapshots.update(
                {Path(path): payload for path, payload in snapshots.items()}
            )
        original_snapshot_check(snapshots, label=label)

    monkeypatch.setattr(cli, "_require_snapshot_unchanged", capture_final_snapshot)
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
    projected_purchased_manifest: list[Mapping[str, object]] = []
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
            "purchased_manifest": projected_purchased_manifest,
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
    authority_manifest_identities: list[bool] = []

    def verify_free_only_authority(**kwargs: object) -> object:
        authority_manifest_identities.append(
            kwargs["projected_purchased_manifest"] is projected_purchased_manifest
        )
        return approval

    monkeypatch.setattr(
        cli,
        "verify_free_only_materialization_authority",
        verify_free_only_authority,
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
    assert authority_manifest_identities == [True, True]
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
    assert any(
        path.name == "materialize-cohort-documents.json" for path in final_snapshots
    )
    assert any(
        path.suffix == ".pdf" and "documents" in path.parts for path in final_snapshots
    )
    assert any(path.name == "target-cohort-selection.jsonl" for path in final_snapshots)
    unexpected = output / "documents/unexpected.pdf"
    unexpected.write_bytes(b"%PDF-1.4\nunexpected\n%%EOF")
    with pytest.raises(cli.CommandError, match="document-tree commitment changed"):
        cli._verify_materialized_downstream_lineage(
            run_card_path=run_card,
            manifest_path=output / "document-downloads-merged.jsonl",
            clearance_path=output / "disclosure-clearance.jsonl",
            document_root=output / "documents",
            selection_path=selection,
            controlled_private_root=private_root,
        )
    unexpected.unlink()
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
        "purchase_result",
        "purchase_run_card",
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


def test_incomplete_paid_materialization_rejects_before_authority_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = SimpleNamespace(
        free_only_approval_checkpoint=None,
        free_only_approval_run_card=None,
        free_only_fee_schedule=None,
        free_only_canonical_ledger_path=None,
        purchased_recovery_root=tmp_path / "recovery",
        purchased_disclosure_clearance=tmp_path / "clearance.jsonl",
        purchased_clearance_run_card=tmp_path / "clearance-card.json",
        purchase_policy=tmp_path / "policy.json",
        purchase_ledger=None,
        purchase_ledger_initialization_receipt=None,
        resolved_post_recovery_documents=None,
    )

    monkeypatch.setattr(
        cli,
        "_preflight_current_purchase_snapshot",
        lambda _args: pytest.fail("incomplete paid mode read authority"),
    )
    with pytest.raises(cli.CommandError, match="requires recovery"):
        cli._cmd_acquisition_materialize_cohort_documents(args)


@pytest.mark.parametrize("provided", ["purchase_result", "purchase_run_card"])
def test_paid_materializer_requires_terminal_authority_inputs_together(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provided: str,
) -> None:
    args = SimpleNamespace(
        free_only_approval_checkpoint=None,
        free_only_approval_run_card=None,
        free_only_fee_schedule=None,
        free_only_canonical_ledger_path=None,
        purchased_recovery_root=tmp_path / "recovery",
        purchased_disclosure_clearance=tmp_path / "clearance.jsonl",
        purchased_clearance_run_card=tmp_path / "clearance-card.json",
        purchase_policy=tmp_path / "policy.json",
        purchase_ledger=tmp_path / "ledger.sqlite3",
        purchase_ledger_initialization_receipt=tmp_path / "receipt.json",
        resolved_post_recovery_documents=None,
        purchase_result=None,
        purchase_run_card=None,
    )
    setattr(args, provided, tmp_path / f"{provided}.json")
    monkeypatch.setattr(
        cli, "_preflight_legacy_purchase_policy_rejection", lambda _args: None
    )
    monkeypatch.setattr(
        cli,
        "_preflight_current_purchase_snapshot",
        lambda _args: pytest.fail("partial terminal authority read runtime state"),
    )

    with pytest.raises(cli.CommandError, match="must be supplied together"):
        cli._cmd_acquisition_materialize_cohort_documents(args)


def test_docket_decision_partition_binds_exact_omission_and_residual_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = SimpleNamespace(purchase_journal_state_sha256="a" * 64)
    source_records = (
        {
            "candidate_id": "candidate-2",
            "unavailable_recap_document_id": "decision-2",
        },
        {
            "candidate_id": "candidate-1",
            "unavailable_recap_document_id": "decision-1",
        },
    )
    monkeypatch.setattr(
        cli,
        "verified_docket_decision_source_records",
        lambda *_args, **_kwargs: source_records,
    )
    monkeypatch.setattr(
        cli,
        "verified_docket_decision_document_keys",
        lambda *_args, **_kwargs: pytest.fail(
            "partition must derive keys from its already-replayed source records"
        ),
    )
    monkeypatch.setattr(
        cli,
        "verified_residual_terminal_records",
        lambda *_args, **_kwargs: {"candidate-3": {"candidate_id": "candidate-3"}},
    )

    partition = cli._docket_decision_partition_record(
        authority=authority,
        purchase_journal=object(),
        selected_document_count=7,
    )

    assert partition["selected_document_count"] == 7
    assert partition["materialized_document_count"] == 5
    assert partition["audit_only_document_count"] == 2
    assert partition["audit_only_candidate_count"] == 2
    assert partition["residual_terminal_candidate_count"] == 1
    assert partition["terminal_candidate_count"] == 3
    assert partition["audit_only_document_keys"] == [
        {"candidate_id": "candidate-1", "source_document_id": "decision-1"},
        {"candidate_id": "candidate-2", "source_document_id": "decision-2"},
    ]


def test_consolidated_projection_uses_full_selection_for_audit_only_omissions() -> None:
    selection_records = (
        {
            "candidate_id": "candidate-1",
            "documents": [
                {"source_document_id": "motion-1"},
                {"source_document_id": "decision-1"},
            ],
        },
    )
    projection = {
        "selection_records": selection_records,
        "selected_document_keys": {("candidate-1", "motion-1")},
    }

    assert cli._materializer_complete_selected_document_keys(
        projection, consolidated_recovery=True
    ) == {
        ("candidate-1", "motion-1"),
        ("candidate-1", "decision-1"),
    }
    assert cli._materializer_complete_selected_document_keys(
        projection, consolidated_recovery=False
    ) == {("candidate-1", "motion-1")}
    omission_keys = {("candidate-1", "decision-1")}
    assert (
        cli._materializer_complete_selected_document_keys(
            projection, consolidated_recovery=True
        )
        - omission_keys
    ) == {("candidate-1", "motion-1")}


def test_consolidated_projection_rejects_available_document_outside_selection() -> None:
    projection = {
        "selection_records": (
            {
                "candidate_id": "candidate-1",
                "documents": [{"source_document_id": "motion-1"}],
            },
        ),
        "selected_document_keys": {
            ("candidate-1", "motion-1"),
            ("candidate-2", "injected-1"),
        },
    }

    with pytest.raises(
        cli.CommandError, match="available document is outside the selection"
    ):
        cli._materializer_complete_selected_document_keys(
            projection, consolidated_recovery=True
        )


def test_consolidated_projection_partitions_merged_clearance() -> None:
    free = {"candidate_id": "candidate-1", "source_document_id": "free-1"}
    purchased = {
        "candidate_id": "candidate-1",
        "source_document_id": "purchased-1",
    }
    projection = {
        "free_manifest": (free,),
        "purchased_manifest": (purchased,),
        "free_clearance": (free, purchased),
    }

    assert cli._materializer_free_clearance_records(
        projection, consolidated_recovery=True
    ) == (free,)
    assert cli._materializer_free_clearance_records(
        projection, consolidated_recovery=False
    ) == (free, purchased)


def test_consolidated_projection_rejects_unpartitioned_clearance() -> None:
    injected = {"candidate_id": "candidate-2", "source_document_id": "injected-1"}
    projection = {
        "free_manifest": (),
        "purchased_manifest": (),
        "free_clearance": (injected,),
    }

    with pytest.raises(
        cli.CommandError, match="clearance differs from free/purchased partitions"
    ):
        cli._materializer_free_clearance_records(projection, consolidated_recovery=True)


def test_consolidated_successor_v2_uses_two_authenticated_free_roots(
    tmp_path: Path,
) -> None:
    complete_root = tmp_path / "complete" / "01-materialized"
    inherited_root = complete_root / "documents"
    historical_root = tmp_path / "historical"
    promoted_root = historical_root / "documents"
    successor_root = tmp_path / "successor"
    successor_root.mkdir()

    def record(
        *, candidate_id: str, document_id: str, root: Path, local_path: str
    ) -> dict[str, Any]:
        payload = f"%PDF-1.4\n{candidate_id}/{document_id}\n%%EOF".encode()
        path = root / local_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "free_or_purchased": "free",
            "local_path": local_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        }

    inherited = record(
        candidate_id="retained",
        document_id="retained-decision",
        root=inherited_root,
        local_path="sha256/aa/retained.pdf",
    )
    promoted = tuple(
        record(
            candidate_id="promoted",
            document_id=f"promoted-{index}",
            root=promoted_root,
            local_path=f"promoted-{index}.pdf",
        )
        for index in range(5)
    )
    complete_root.mkdir(parents=True, exist_ok=True)
    (complete_root / "document-downloads-merged.jsonl").write_text(
        json.dumps(inherited) + "\n", encoding="utf-8"
    )
    (historical_root / "free-document-downloads.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in promoted), encoding="utf-8"
    )
    promotion_path = successor_root / "successor-promotions.jsonl"
    promotion_bytes = (json.dumps({"candidate_id": "promoted"}) + "\n").encode()
    projection = {
        "run_card": {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2),
            "input_paths": [
                str(tmp_path / name)
                for name in (
                    "predecessor",
                    "complete",
                    "stipulated",
                    "snapshot",
                    "wider-plan",
                    "wider-exclusions",
                    "historical",
                )
            ],
        },
        "selection_path": successor_root / "target-cohort-selection.jsonl",
        "verified_artifact_bytes": {str(promotion_path): promotion_bytes},
        "free_manifest": (inherited, *promoted),
        "free_clearance": (inherited, *promoted),
        "purchased_manifest": (),
    }

    sources = cli._materializer_successor_v2_free_sources(
        projection,
        preparation_root=tmp_path / "preparation",
        consolidated_recovery=True,
    )

    assert tuple(source.document_root for source in sources) == (
        inherited_root,
        promoted_root,
    )
    assert [len(source.manifest) for source in sources] == [1, 5]


def test_consolidated_non_v2_keeps_the_preparation_free_root(tmp_path: Path) -> None:
    record = {"candidate_id": "candidate-1", "source_document_id": "document-1"}
    sources = cli._materializer_successor_v2_free_sources(
        {
            "run_card": {"schema_version": "legalforecast.other_successor.v1"},
            "free_manifest": (record,),
            "free_clearance": (record,),
            "purchased_manifest": (),
        },
        preparation_root=tmp_path / "preparation",
        consolidated_recovery=True,
    )

    assert len(sources) == 1
    assert sources[0].document_root == tmp_path / "preparation/documents/free"


def test_consolidated_successor_v2_rejects_source_record_drift(
    tmp_path: Path,
) -> None:
    complete_root = tmp_path / "complete" / "01-materialized"
    inherited_root = complete_root / "documents"
    historical_root = tmp_path / "historical"
    promoted_root = historical_root / "documents"
    successor_root = tmp_path / "successor"
    successor_root.mkdir()

    def record(
        *, candidate_id: str, document_id: str, root: Path, local_path: str
    ) -> dict[str, Any]:
        payload = f"%PDF-1.4\n{candidate_id}/{document_id}\n%%EOF".encode()
        path = root / local_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "free_or_purchased": "free",
            "local_path": local_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        }

    inherited = record(
        candidate_id="retained",
        document_id="retained-decision",
        root=inherited_root,
        local_path="sha256/aa/retained.pdf",
    )
    promoted = tuple(
        record(
            candidate_id="promoted",
            document_id=f"promoted-{index}",
            root=promoted_root,
            local_path=f"promoted-{index}.pdf",
        )
        for index in range(5)
    )
    complete_root.mkdir(parents=True, exist_ok=True)
    drifted = {**inherited, "local_path": "sha256/aa/not-retained.pdf"}
    (complete_root / "document-downloads-merged.jsonl").write_text(
        json.dumps(drifted) + "\n", encoding="utf-8"
    )
    (historical_root / "free-document-downloads.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in promoted), encoding="utf-8"
    )
    promotion_path = successor_root / "successor-promotions.jsonl"
    promotion_bytes = (json.dumps({"candidate_id": "promoted"}) + "\n").encode()
    projection = {
        "run_card": {
            "schema_version": str(cli.EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2),
            "input_paths": [
                str(tmp_path / name)
                for name in (
                    "predecessor",
                    "complete",
                    "stipulated",
                    "snapshot",
                    "wider-plan",
                    "wider-exclusions",
                    "historical",
                )
            ],
        },
        "selection_path": successor_root / "target-cohort-selection.jsonl",
        "verified_artifact_bytes": {str(promotion_path): promotion_bytes},
        "free_manifest": (inherited, *promoted),
        "free_clearance": (inherited, *promoted),
        "purchased_manifest": (),
    }

    with pytest.raises(cli.CommandError, match="inherited free document differs"):
        cli._materializer_successor_v2_free_sources(
            projection,
            preparation_root=tmp_path / "preparation",
            consolidated_recovery=True,
        )


@pytest.mark.parametrize("input_count", [14, 15])
def test_paid_materialization_input_extensions_preserve_fixed_authority_indices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    input_count: int,
) -> None:
    inputs = [tmp_path / f"input-{index}" for index in range(input_count)]
    run_card_path = tmp_path / "materialization-card"
    run_card_bytes = (
        json.dumps({"input_paths": [str(path) for path in inputs]}) + "\n"
    ).encode()
    cohort_policy_bytes = (
        json.dumps({"policy": {"cycle_id": "cycle-paid"}}) + "\n"
    ).encode()

    def captured(path: Path, **_kwargs: object) -> bytes:
        if path == run_card_path:
            return run_card_bytes
        if path == inputs[10]:
            return cohort_policy_bytes
        raise AssertionError(f"unexpected materialization input: {path}")

    monkeypatch.setattr(cli, "_captured_or_stable_input", captured)
    monkeypatch.setattr(cli, "verify_cohort_policy", lambda _artifact: None)

    assert (
        cli._authenticated_materialization_snapshot_manifest_path(
            {"input_paths": [str(path) for path in inputs]}
        )
        == inputs[3]
    )
    assert cli._materialization_cohort_cycle_id(run_card_path) == "cycle-paid"


def test_paid_materializer_authenticates_decision_omission_before_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    paths = {
        name: tmp_path / name
        for name in (
            "preparation-summary.json",
            "preparation-config.json",
            "manifest.json",
            "free-clearance.jsonl",
            "purchased-clearance.jsonl",
            "purchased-clearance-card.json",
            "purchase-policy.json",
            "cohort-policy.json",
            "ledger.sqlite3",
            "purchase-result.json",
            "purchase-run-card.json",
            "selection.jsonl",
            "success-card.json",
        )
    }
    for path in paths.values():
        path.write_text("{}\n", encoding="utf-8")
    selection_payload = (
        json.dumps(
            {
                "candidate_id": "candidate-1",
                "documents": [
                    {"source_document_id": "motion-1"},
                    {"source_document_id": "decision-1"},
                ],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    paths["selection.jsonl"].write_bytes(selection_payload)
    ledger = paths["ledger.sqlite3"].resolve()
    policy = SimpleNamespace(canonical_ledger_path=ledger)
    authority = SimpleNamespace(purchase_journal_state_sha256="a" * 64)
    partition = {
        "schema_version": "legalforecast.materializer_docket_decision_partition.v1",
        "selected_document_count": 2,
        "materialized_document_count": 1,
        "audit_only_document_count": 1,
    }
    descriptor = cli._MaterializerDocketDecisionAuthority(
        authority=authority,
        partition=partition,
        purchase_policy=policy,
        ledger_path=ledger,
        controlled_private_root=tmp_path / "private",
        initialization_receipt_path=tmp_path / "receipt.json",
        purchase_budget_plan_path=tmp_path / "budget.json",
        source_snapshots={},
    )
    projection = {
        "selection_path": paths["selection.jsonl"],
        "selection_records": (),
        "selected_document_keys": {
            ("candidate-1", "motion-1"),
            ("candidate-1", "decision-1"),
        },
        "verified_artifact_bytes": {
            os.path.abspath(paths["selection.jsonl"]): selection_payload
        },
    }

    class FakeJournal:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeJournal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class RecoveryReached(RuntimeError):
        pass

    observed: dict[str, object] = {}

    def capture_recovery(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        raise RecoveryReached

    monkeypatch.setattr(
        cli, "_preflight_legacy_purchase_policy_rejection", lambda _args: None
    )
    monkeypatch.setattr(cli, "_preflight_current_purchase_snapshot", lambda _args: None)
    monkeypatch.setattr(
        cli, "_validate_projection_output_scope", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli, "_validate_materializer_writable_paths", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "_verify_completed_preparation_for_frontier",
        lambda **_kwargs: SimpleNamespace(
            target_case_count=1,
            success_run_card_path=paths["success-card.json"],
        ),
    )
    monkeypatch.setattr(
        cli, "_verify_materializer_projection", lambda **_kwargs: projection
    )
    monkeypatch.setattr(
        cli, "verify_case_dev_purchase_policy", lambda _artifact: policy
    )
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy_cohort_binding",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            operations=(),
            committed_amount_usd="0.00",
            purchase_state_sha256="b" * 64,
        ),
    )
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", FakeJournal)
    monkeypatch.setattr(
        cli,
        "_verify_materializer_docket_decision_authority",
        lambda **_kwargs: (calls.append("authority"), descriptor)[1],
    )
    monkeypatch.setattr(
        cli,
        "verified_docket_decision_document_keys",
        lambda *_args, **_kwargs: (
            calls.append("decision_keys"),
            frozenset({("candidate-1", "decision-1")}),
        )[1],
    )
    monkeypatch.setattr(cli, "_verify_materializer_recovery", capture_recovery)
    args = SimpleNamespace(
        free_only_approval_checkpoint=None,
        free_only_approval_run_card=None,
        free_only_fee_schedule=None,
        free_only_canonical_ledger_path=None,
        purchased_recovery_root=tmp_path / "recovery",
        purchased_disclosure_clearance=paths["purchased-clearance.jsonl"],
        purchased_clearance_run_card=paths["purchased-clearance-card.json"],
        purchase_policy=paths["purchase-policy.json"],
        purchase_ledger=ledger,
        purchase_ledger_initialization_receipt=tmp_path / "receipt.json",
        purchase_result=paths["purchase-result.json"],
        purchase_run_card=paths["purchase-run-card.json"],
        resolved_post_recovery_documents=None,
        preparation_root=tmp_path / "preparation",
        preparation_summary=paths["preparation-summary.json"],
        preparation_config=paths["preparation-config.json"],
        snapshot_manifest=paths["manifest.json"],
        target_cohort_root=tmp_path / "target",
        free_disclosure_clearance=paths["free-clearance.jsonl"],
        cohort_policy=paths["cohort-policy.json"],
        controlled_private_root=tmp_path / "private",
        output_root=tmp_path / "output",
        run_card_output=None,
        log_output=None,
    )

    with pytest.raises(RecoveryReached):
        cli._cmd_acquisition_materialize_cohort_documents(args)

    assert calls == ["authority", "decision_keys"]
    assert observed["selected_document_keys"] == {("candidate-1", "motion-1")}


def test_downstream_replay_reauthenticates_bound_decision_omission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_names = (
        "preparation",
        "preparation-summary.json",
        "preparation-config.json",
        "snapshot/manifest.json",
        "target",
        "free-clearance.jsonl",
        "recovery",
        "purchased-clearance.jsonl",
        "purchased-clearance-card.json",
        "purchase-policy.json",
        "cohort-policy.json",
        "ledger.sqlite3",
        "purchase-result.json",
        "purchase-run-card.json",
    )
    input_paths = tuple(tmp_path / name for name in input_names)
    for path in input_paths:
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)
    selection = input_paths[4] / "target-cohort-selection.jsonl"
    selection_payload = b'{"candidate_id":"candidate-1","documents":[]}\n'
    selection.write_bytes(selection_payload)
    output_root = tmp_path / "output"
    output_root.mkdir()
    outputs = (
        output_root / "document-downloads-merged.jsonl",
        output_root / "disclosure-clearance.jsonl",
        output_root / "restriction-evidence.jsonl",
        output_root / "materialization-derivations.jsonl",
        output_root / "cohort-document-materialization.json",
        output_root / "documents",
    )
    for path in outputs[:-1]:
        path.write_text("\n", encoding="utf-8")
    outputs[-1].mkdir()
    run_card = output_root / "materialization-card.json"
    run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "source_roots_mutated": False,
                "zero_provider_activity_evidence": True,
                "input_paths": [str(path) for path in input_paths],
                "output_paths": [str(path) for path in outputs],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    ledger = input_paths[11].resolve()
    policy = SimpleNamespace(canonical_ledger_path=ledger)
    authority = SimpleNamespace(purchase_journal_state_sha256="a" * 64)
    descriptor = cli._MaterializerDocketDecisionAuthority(
        authority=authority,
        partition={
            "schema_version": "legalforecast.materializer_docket_decision_partition.v1",
            "selected_document_count": 2,
            "materialized_document_count": 1,
            "audit_only_document_count": 1,
        },
        purchase_policy=policy,
        ledger_path=ledger,
        controlled_private_root=tmp_path / "private",
        initialization_receipt_path=tmp_path / "receipt.json",
        purchase_budget_plan_path=tmp_path / "budget.json",
        source_snapshots={},
    )
    projection = {
        "selection_path": selection,
        "selection_records": (),
        "selected_document_keys": {
            ("candidate-1", "motion-1"),
            ("candidate-1", "decision-1"),
        },
        "verified_artifact_bytes": {os.path.abspath(selection): selection_payload},
    }

    class FakeJournal:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeJournal:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class RecoveryReached(RuntimeError):
        pass

    observed: dict[str, object] = {}

    def capture_recovery(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        raise RecoveryReached

    monkeypatch.setattr(
        cli,
        "_verify_completed_preparation_for_frontier",
        lambda **_kwargs: SimpleNamespace(
            target_case_count=1,
            success_run_card_path=input_paths[1],
        ),
    )
    monkeypatch.setattr(
        cli, "_verify_materializer_projection", lambda **_kwargs: projection
    )
    monkeypatch.setattr(
        cli, "verify_case_dev_purchase_policy", lambda _artifact: policy
    )
    monkeypatch.setattr(
        cli, "require_approved_case_dev_purchase_policy", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        cli,
        "verify_case_dev_purchase_policy_cohort_binding",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "read_case_dev_purchase_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(
            operations=(),
            committed_amount_usd="0.00",
            purchase_state_sha256="b" * 64,
        ),
    )
    monkeypatch.setattr(cli, "CaseDevPurchaseJournal", FakeJournal)
    monkeypatch.setattr(
        cli,
        "_verify_materializer_docket_decision_authority",
        lambda **_kwargs: descriptor,
    )
    monkeypatch.setattr(
        cli,
        "verified_docket_decision_document_keys",
        lambda *_args, **_kwargs: frozenset({("candidate-1", "decision-1")}),
    )
    monkeypatch.setattr(cli, "_verify_materializer_recovery", capture_recovery)

    with pytest.raises(RecoveryReached):
        cli._verify_materialized_downstream_lineage(
            run_card_path=run_card,
            manifest_path=outputs[0],
            clearance_path=outputs[1],
            document_root=outputs[-1],
            controlled_private_root=tmp_path / "private",
            initialization_receipt_path=tmp_path / "receipt.json",
        )

    assert observed["selected_document_keys"] == {("candidate-1", "motion-1")}


@pytest.mark.parametrize("authority_mode", ["free_only", None])
def test_paid_materializer_resume_rejects_injected_authority_mode(
    tmp_path: Path,
    authority_mode: object,
) -> None:
    run_card = tmp_path / "run-card.json"
    card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "materialize-cohort-documents",
        "status": "completed",
        "dry_run": True,
        "execute": False,
        "record_count": 0,
        "input_paths": [],
        "output_paths": [
            str(tmp_path / name)
            for name in (
                "manifest.jsonl",
                "clearance.jsonl",
                "restriction.jsonl",
                "derivations.jsonl",
                "summary.json",
                "documents",
            )
        ],
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {},
        "output_commitments": {},
        "source_roots_mutated": False,
        "zero_provider_activity_evidence": True,
        "authority_mode": authority_mode,
    }
    run_card.write_text(json.dumps(card, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(cli.CommandError, match="authority_mode"):
        cli._verify_materializer_resume(
            run_card_path=run_card,
            input_paths=(),
            manifest_path=tmp_path / "manifest.jsonl",
            manifest_bytes=b"",
            clearance_path=tmp_path / "clearance.jsonl",
            clearance_bytes=b"",
            restriction_path=tmp_path / "restriction.jsonl",
            restriction_bytes=b"",
            derivations_path=tmp_path / "derivations.jsonl",
            derivations_bytes=b"",
            summary_path=tmp_path / "summary.json",
            summary_bytes=b"",
            document_root=tmp_path / "documents",
            materialization=SimpleNamespace(manifest=(), clearance=()),
            source_commitments={},
            output_commitments={},
            dry_run=True,
        )


def test_materializer_preflight_rejects_null_authority_mode(tmp_path: Path) -> None:
    run_card = tmp_path / "run-card.json"
    run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "authority_mode": None,
                "input_paths": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(cli.CommandError, match="authority mode"):
        cli._preflight_materialization_purchase_runtime(
            SimpleNamespace(materialization_run_card=run_card)
        )


@pytest.mark.parametrize(
    "paid_field",
    [
        "purchase_policy",
        "purchase_ledger",
        "purchase_ledger_initialization_receipt",
        "resolved_post_recovery_documents",
    ],
)
def test_free_only_downstream_preflight_rejects_paid_state_before_policy_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    paid_field: str,
) -> None:
    input_paths = [str(tmp_path / f"input-{index}") for index in range(11)]
    run_card = tmp_path / "materialization-card.json"
    run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "authority_mode": "free_only",
                "input_paths": input_paths,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        materialization_run_card=run_card,
        controlled_private_root=tmp_path / "private",
        purchase_policy=None,
        purchase_ledger=None,
        purchase_ledger_initialization_receipt=None,
        resolved_post_recovery_documents=None,
    )
    paid_state_path = tmp_path / "paid-state"
    setattr(args, paid_field, paid_state_path)
    if paid_field == "purchase_policy":
        paid_state_path.write_text(
            '{"schema_version":"legalforecast.case_dev_purchase_policy.v2"}\n',
            encoding="utf-8",
        )
    monkeypatch.setattr(
        cli,
        "_preflight_approved_purchase_runtime",
        lambda _args: pytest.fail("free-only mode accessed paid authority"),
    )

    with pytest.raises(cli.CommandError, match="rejects paid-runtime inputs"):
        cli._preflight_materialization_purchase_runtime(args)


@pytest.mark.parametrize("documents", [None, "not-a-list"])
def test_free_only_preflight_rejects_malformed_selection_documents_as_command_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    documents: object,
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    selection: dict[str, object] = {"candidate_id": "candidate-1"}
    if documents is not None:
        selection["documents"] = documents
    (target_root / "target-cohort-selection.jsonl").write_text(
        json.dumps(selection, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (target_root / "free-document-downloads.jsonl").write_text(
        "",
        encoding="utf-8",
    )
    (target_root / "purchased-document-downloads.jsonl").write_text(
        "",
        encoding="utf-8",
    )
    input_paths = [tmp_path / f"input-{index}" for index in range(11)]
    input_paths[4] = target_root
    run_card = tmp_path / "materialization-card.json"
    run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "authority_mode": "free_only",
                "input_paths": [str(path) for path in input_paths],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    args = cli.argparse.Namespace(
        materialization_run_card=run_card,
        controlled_private_root=tmp_path / "private",
        purchase_policy=None,
        purchase_ledger=None,
        purchase_ledger_initialization_receipt=None,
        resolved_post_recovery_documents=None,
    )
    monkeypatch.setattr(
        cli,
        "verify_free_only_materialization_authority",
        lambda **_kwargs: pytest.fail("malformed selection reached authority replay"),
    )

    with pytest.raises(cli.CommandError, match="documents"):
        cli._preflight_materialization_purchase_runtime(args)


def test_free_only_preflight_passes_committed_purchased_projection_to_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    purchased_record = {
        "candidate_id": "candidate-1",
        "source_document_id": "motion-1",
    }
    (target_root / "target-cohort-selection.jsonl").write_text(
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
    (target_root / "free-document-downloads.jsonl").write_text(
        "",
        encoding="utf-8",
    )
    (target_root / "purchased-document-downloads.jsonl").write_text(
        json.dumps(purchased_record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    input_paths = [tmp_path / f"input-{index}" for index in range(11)]
    input_paths[4] = target_root
    run_card = tmp_path / "materialization-card.json"
    run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "authority_mode": "free_only",
                "input_paths": [str(path) for path in input_paths],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    args = cli.argparse.Namespace(
        materialization_run_card=run_card,
        controlled_private_root=tmp_path / "private",
        purchase_policy=None,
        purchase_ledger=None,
        purchase_ledger_initialization_receipt=None,
        resolved_post_recovery_documents=None,
    )

    def reject_purchased_projection(**kwargs: object) -> None:
        assert kwargs["projected_purchased_manifest"] == (purchased_record,)
        raise cli.FreeOnlyMaterializationError(
            "free-only materialization rejects projected purchased documents"
        )

    monkeypatch.setattr(
        cli,
        "verify_free_only_materialization_authority",
        reject_purchased_projection,
    )

    with pytest.raises(cli.CommandError, match="rejects projected purchased"):
        cli._preflight_materialization_purchase_runtime(args)


def test_free_only_downstream_replay_requires_controlled_private_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_card = tmp_path / "materialization-card.json"
    run_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "materialize-cohort-documents",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
                "source_roots_mutated": False,
                "zero_provider_activity_evidence": True,
                "authority_mode": "free_only",
                "input_paths": [
                    str(tmp_path / f"input-{index}") for index in range(11)
                ],
                "output_paths": [
                    str(tmp_path / f"output-{index}") for index in range(6)
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "_prepare_free_only_cohort_documents",
        lambda *_args, **_kwargs: pytest.fail(
            "missing controlled private root reached preparation"
        ),
    )

    with pytest.raises(cli.CommandError, match="controlled private root"):
        cli._verify_materialized_downstream_lineage(
            run_card_path=run_card,
            manifest_path=tmp_path / "output-0",
            clearance_path=tmp_path / "output-1",
            document_root=tmp_path / "output-5",
        )


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


def test_materializer_accepts_consecutive_free_sources_and_sums_counts(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    first, first_key = _source(
        left,
        phase="free",
        candidate_id="candidate-1",
        document_id="decision-1",
    )
    second, second_key = _source(
        right,
        phase="free",
        candidate_id="candidate-2",
        document_id="decision-2",
    )

    prepared = prepare_cohort_document_materialization(
        (first, second),
        selected_document_keys={first_key, second_key},
        output_root=tmp_path / "output",
    )

    assert prepared.summary["free_document_count"] == 2
    assert prepared.summary["purchased_document_count"] == 0


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
