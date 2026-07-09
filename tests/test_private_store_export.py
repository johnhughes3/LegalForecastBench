from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from legalforecast.publication.private_store_export import (
    PRIVATE_STORE_EXPORT_SCHEMA_VERSION,
    PrivateStoreExportConfig,
    PrivateStoreExportError,
    build_private_store_export,
)
from legalforecast.publication.private_store_export import (
    main as private_store_export_main,
)
from legalforecast.publication.reconstruction import (
    VerificationStatus,
    load_reconstruction_plans,
    verify_reconstructed_packet_renders,
)


def test_private_store_export_stages_objects_manifests_and_verification(
    tmp_path: Path,
) -> None:
    source_dir = _source_dir(tmp_path)
    output_dir = tmp_path / "export"

    result = build_private_store_export(
        PrivateStoreExportConfig(
            source_dir=source_dir,
            output_dir=output_dir,
            cycle_id="cycle_fixture",
            generated_at=datetime(2026, 5, 17, 20, 0, tzinfo=UTC),
        )
    )

    object_keys = {record.key for record in result.objects}
    assert {
        "source-documents/cycle_fixture/case-1/doc-1.pdf",
        "extracted-text/cycle_fixture/extracted_texts.jsonl",
        "extracted-text/cycle_fixture/case-1/doc-1.md",
        "extracted-text/cycle_fixture/case-1/doc-1.metadata.json",
        "model-packets/cycle_fixture/case-1/full_packet.json",
        "audit-bundles/cycle_fixture/acquisition-audit.json",
        "manifests/cycle_fixture.freeze.json",
        "manifests/cycle_fixture.run-inputs.json",
        "manifests/cycle_fixture.public-reconstruction.json",
    } <= object_keys

    packet_path = (
        output_dir
        / "objects/packet/model-packets/cycle_fixture/case-1/full_packet.json"
    )
    assert "Complaint text visible to model" in packet_path.read_text(encoding="utf-8")
    markdown_path = (
        output_dir / "objects/packet/extracted-text/cycle_fixture/case-1/doc-1.md"
    )
    assert markdown_path.read_text(encoding="utf-8") == "# Complaint\n\nVisible text\n"

    freeze_manifest = _read_json(result.freeze_manifest_path)
    assert freeze_manifest["schema_version"] == PRIVATE_STORE_EXPORT_SCHEMA_VERSION
    assert freeze_manifest["storage_manifest_version"] == 1
    assert freeze_manifest["packet_prefixes"] == [
        "source-documents/",
        "extracted-text/",
        "model-packets/",
        "audit-bundles/",
        "withdrawn/",
        "quarantine/",
    ]
    assert freeze_manifest["accounting_summary"] == {
        "estimated_cost": 1.25,
        "record_count": 1,
    }

    run_inputs = _read_json(result.run_input_manifest_path)
    assert run_inputs["model_packets"] == [
        {
            "ablation": "full_packet",
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "packet_object_key": "model-packets/cycle_fixture/case-1/full_packet.json",
            "packet_sha256": _sha256_file(packet_path),
            "packet_size_bytes": packet_path.stat().st_size,
            "source_document_ids": ["doc-1"],
            "source_hashes": {"doc-1": _sha256_bytes(b"%PDF fixture doc\n")},
        }
    ]
    assert "Complaint text visible to model" not in json.dumps(run_inputs)

    public_reconstruction = _read_json(result.public_reconstruction_manifest_path)
    candidates = cast(list[dict[str, object]], public_reconstruction["candidates"])
    documents = cast(list[dict[str, object]], candidates[0]["documents"])
    packet_render = cast(dict[str, object], candidates[0]["packet_render"])
    assert documents[0] == {
        "document_role": "complaint",
        "is_mounted_for_model": True,
        "redistribution_status": "approved-metadata-only",
        "sha256": _sha256_bytes(b"%PDF fixture doc\n"),
        "source_document_id": "doc-1",
        "source_provider": "case.dev",
        "source_url_or_reference": "case-dev:case-1:doc-1",
    }
    assert packet_render["packet_sha256"] == _sha256_file(packet_path)
    assert packet_render["packet_json_path"] == (
        "model-packets/cycle_fixture/case-1/full_packet.json"
    )
    assert packet_render["rebuild_command"] == [
        "uv",
        "run",
        "legalforecast",
        "acquisition",
        "build-packets",
        "--input",
        "packet-build-input.jsonl",
        "--packets-output",
        "packets.jsonl",
        "--case-packets-output",
        "case-packets.jsonl",
        "--audit-output",
        "packet-audit.jsonl",
        "--ablation",
        "full_packet",
    ]
    assert "Complaint text visible to model" not in json.dumps(public_reconstruction)
    plans = load_reconstruction_plans(result.public_reconstruction_manifest_path)
    packet_verifications = verify_reconstructed_packet_renders(
        plans,
        output_dir / "objects/packet",
    )
    assert packet_verifications[0].status is VerificationStatus.VERIFIED

    verification = _read_json(result.verification_report_path)
    assert verification["object_count"] == len(result.objects)
    assert verification["verified_object_count"] == len(result.objects)
    total_size_bytes = verification["total_size_bytes"]
    assert isinstance(total_size_bytes, int)
    assert total_size_bytes > 0


def test_private_store_export_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    source_dir = _source_dir(tmp_path, document_bytes=b"changed bytes\n")

    with pytest.raises(PrivateStoreExportError, match="source document hash mismatch"):
        build_private_store_export(
            PrivateStoreExportConfig(
                source_dir=source_dir,
                output_dir=tmp_path / "export",
                cycle_id="cycle_fixture",
            )
        )


def test_private_store_export_module_main_writes_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = _source_dir(tmp_path)
    output_dir = tmp_path / "export"

    assert (
        private_store_export_main(
            [
                "--source-dir",
                str(source_dir),
                "--output-dir",
                str(output_dir),
                "--cycle-id",
                "cycle_fixture",
            ]
        )
        == 0
    )

    stdout = json.loads(capsys.readouterr().out)
    assert stdout["object_count"] == 9
    assert Path(stdout["verification_report"]).is_file()


def _source_dir(
    tmp_path: Path,
    *,
    document_bytes: bytes = b"%PDF fixture doc\n",
) -> Path:
    source_dir = tmp_path / "source"
    docs_dir = source_dir / "docs"
    docs_dir.mkdir(parents=True)
    document_path = docs_dir / "doc-1.pdf"
    document_path.write_bytes(document_bytes)
    expected_hash = _sha256_bytes(b"%PDF fixture doc\n")
    markdown_dir = source_dir / "markdown/case-1"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "doc-1.md").write_text(
        "# Complaint\n\nVisible text\n",
        encoding="utf-8",
    )
    (markdown_dir / "doc-1.metadata.json").write_text(
        json.dumps({"engine": "fixture"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _write_jsonl(
        source_dir / "document-manifest.jsonl",
        [{"source_document_id": "doc-1", "path": "docs/doc-1.pdf"}],
    )
    _write_jsonl(
        source_dir / "candidate-manifest.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "manifest_record_hash": "c" * 64,
                "documents": [
                    {
                        "source_document_id": "doc-1",
                        "source_provider": "case.dev",
                        "document_role": "complaint",
                        "sha256": expected_hash,
                        "source_url_or_reference": "case-dev:case-1:doc-1",
                        "is_mounted_for_model": True,
                    }
                ],
            }
        ],
    )
    _write_jsonl(
        source_dir / "packets.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "ablation": "full_packet",
                "documents": [
                    {
                        "source_document_id": "doc-1",
                        "text": "Complaint text visible to model",
                        "text_sha256": _sha256_bytes(
                            b"Complaint text visible to model"
                        ),
                        "source_sha256": expected_hash,
                    }
                ],
                "prediction_units": [{"unit_id": "unit-1"}],
            }
        ],
    )
    _write_jsonl(
        source_dir / "extracted_texts.jsonl",
        [{"source_document_id": "doc-1", "text_sha256": "d" * 64}],
    )
    _write_jsonl(
        source_dir / "mistral-markdown-conversions.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "markdown_path": "case-1/doc-1.md",
                "metadata_path": "case-1/doc-1.metadata.json",
                "source_document_id": "doc-1",
                "status": "succeeded",
            }
        ],
    )
    _write_jsonl(source_dir / "accounting.jsonl", [{"estimated_cost": 1.25}])
    _write_jsonl(source_dir / "retrievals.jsonl", [{"candidate_id": "cand-1"}])
    _write_jsonl(source_dir / "linkage.jsonl", [{"candidate_id": "cand-1"}])
    _write_jsonl(source_dir / "exclusion-ledger.jsonl", [])
    return source_dir


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("expected JSON object")
    return cast(dict[str, object], value)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
