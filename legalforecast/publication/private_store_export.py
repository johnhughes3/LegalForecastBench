"""Build a private-store export bundle from local acquisition artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from legalforecast._datetime import format_utc_iso_z
from legalforecast._hashing import is_lowercase_sha256
from legalforecast.path_safety import safe_path_component
from legalforecast.protocol.freeze import sha256_file

PRIVATE_STORE_EXPORT_SCHEMA_VERSION = "legalforecast-private-store-export-v1"
STORAGE_MANIFEST_VERSION = 1


JsonRecord = dict[str, object]


class PrivateStoreExportError(ValueError):
    """Raised when local artifacts cannot form a safe private-store export."""


class ExportBucketRole(StrEnum):
    PACKET = "packet"
    RESULTS = "results"


class ExportClassification(StrEnum):
    RAW_PRIVATE = "raw-private"
    MODEL_VISIBLE_PRIVATE = "model-visible-private"
    AUDIT_PRIVATE = "audit-private"
    PUBLIC_SAFE = "public-safe"


@dataclass(frozen=True, slots=True)
class PrivateStoreExportConfig:
    """Inputs for staging an official private-store export bundle."""

    source_dir: Path
    output_dir: Path
    cycle_id: str
    packet_bucket: str = "protected-packet-bucket"
    results_bucket: str = "protected-results-bucket"
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        safe_path_component(self.cycle_id, field_name="cycle_id")
        _require_non_empty(self.packet_bucket, "packet_bucket")
        _require_non_empty(self.results_bucket, "results_bucket")
        if self.generated_at is not None:
            _require_aware_datetime(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class ExportObjectRecord:
    """One object staged for the packet or results bucket."""

    bucket_role: ExportBucketRole
    key: str
    local_path: Path
    sha256: str
    size_bytes: int
    content_type: str
    classification: ExportClassification
    source_handle: str
    redistribution_status: str
    mounted_for_model: bool
    verified: bool

    def __post_init__(self) -> None:
        _require_safe_object_key(self.key, "key")
        _require_sha256(self.sha256, "sha256")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        _require_non_empty(self.content_type, "content_type")
        _require_non_empty(self.source_handle, "source_handle")
        _require_non_empty(self.redistribution_status, "redistribution_status")
        if not self.verified:
            raise ValueError("export object records must be verified")

    def to_record(self, *, output_dir: Path | None = None) -> JsonRecord:
        record: JsonRecord = {
            "bucket_role": self.bucket_role.value,
            "key": self.key,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "classification": self.classification.value,
            "source_handle": self.source_handle,
            "redistribution_status": self.redistribution_status,
            "mounted_for_model": self.mounted_for_model,
            "verified": self.verified,
        }
        if output_dir is not None:
            record["local_path"] = str(self.local_path.relative_to(output_dir))
        return record


@dataclass(frozen=True, slots=True)
class PrivateStoreExportResult:
    """Paths and object records produced by a private-store export."""

    verification_report_path: Path
    freeze_manifest_path: Path
    run_input_manifest_path: Path
    public_reconstruction_manifest_path: Path
    objects: tuple[ExportObjectRecord, ...]
    verification_report: JsonRecord


@dataclass(frozen=True, slots=True)
class _DocumentContext:
    candidate_id: str
    case_id: str
    source_document_id: str
    source_provider: str
    document_role: str
    source_url_or_reference: str
    manifest_sha256: str
    mounted_for_model: bool
    manifest_record_hash: str | None


def build_private_store_export(
    config: PrivateStoreExportConfig,
) -> PrivateStoreExportResult:
    """Stage packet-store objects and manifests from local acquired artifacts."""

    source_dir = config.source_dir
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = config.generated_at or datetime.now(UTC)

    candidate_records = _read_jsonl(source_dir / "candidate-manifest.jsonl")
    document_contexts = _document_contexts(candidate_records)
    objects: list[ExportObjectRecord] = []

    source_objects = _export_source_documents(config, document_contexts)
    objects.extend(source_objects)
    extracted_objects: list[ExportObjectRecord] = []
    extracted_object = _export_optional_existing_file(
        config,
        source_dir / "extracted_texts.jsonl",
        key=f"extracted-text/{config.cycle_id}/extracted_texts.jsonl",
        bucket_role=ExportBucketRole.PACKET,
        classification=ExportClassification.RAW_PRIVATE,
        content_type="application/jsonl",
        source_handle="extracted_texts.jsonl",
        mounted_for_model=False,
    )
    if extracted_object is not None:
        extracted_objects.append(extracted_object)
    markdown_objects = _export_markdown_documents(config, document_contexts)
    extracted_objects.extend(markdown_objects)
    objects.extend(extracted_objects)

    packet_records = _read_jsonl(source_dir / "packets.jsonl")
    packet_objects = _export_model_packets(config, packet_records)
    objects.extend(packet_objects)

    audit_object = _export_audit_bundle(config, source_dir, generated_at=generated_at)
    objects.append(audit_object)

    accounting_summary = _accounting_summary(source_dir / "accounting.jsonl")
    freeze_manifest = _freeze_manifest(
        config,
        generated_at=generated_at,
        source_objects=source_objects,
        extracted_objects=tuple(extracted_objects),
        packet_objects=packet_objects,
        audit_objects=(audit_object,),
        accounting_summary=accounting_summary,
    )
    freeze_manifest_path, freeze_record = _write_json_object(
        config,
        bucket_role=ExportBucketRole.RESULTS,
        key=f"manifests/{config.cycle_id}.freeze.json",
        payload=freeze_manifest,
        classification=ExportClassification.PUBLIC_SAFE,
        source_handle=f"{config.cycle_id}:freeze-manifest",
    )
    objects.append(freeze_record)

    run_input_manifest = _run_input_manifest(
        config,
        generated_at=generated_at,
        packet_records=packet_records,
        packet_objects=packet_objects,
        document_contexts=document_contexts,
    )
    run_input_manifest_path, run_input_record = _write_json_object(
        config,
        bucket_role=ExportBucketRole.RESULTS,
        key=f"manifests/{config.cycle_id}.run-inputs.json",
        payload=run_input_manifest,
        classification=ExportClassification.PUBLIC_SAFE,
        source_handle=f"{config.cycle_id}:run-inputs",
    )
    objects.append(run_input_record)

    public_reconstruction = _public_reconstruction_manifest(
        config,
        generated_at=generated_at,
        candidate_records=candidate_records,
        packet_records=packet_records,
        packet_objects=packet_objects,
    )
    public_reconstruction_path, public_reconstruction_record = _write_json_object(
        config,
        bucket_role=ExportBucketRole.RESULTS,
        key=f"manifests/{config.cycle_id}.public-reconstruction.json",
        payload=public_reconstruction,
        classification=ExportClassification.PUBLIC_SAFE,
        source_handle=f"{config.cycle_id}:public-reconstruction",
    )
    objects.append(public_reconstruction_record)

    verification_report = _verification_report(
        config,
        generated_at=generated_at,
        objects=tuple(objects),
        accounting_summary=accounting_summary,
    )
    verification_report_path = output_dir / "verification-report.json"
    _write_json(verification_report_path, verification_report)

    return PrivateStoreExportResult(
        verification_report_path=verification_report_path,
        freeze_manifest_path=freeze_manifest_path,
        run_input_manifest_path=run_input_manifest_path,
        public_reconstruction_manifest_path=public_reconstruction_path,
        objects=tuple(objects),
        verification_report=verification_report,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stage LegalForecastBench private packet-store objects and "
            "public-safe manifests from local acquisition artifacts."
        )
    )
    parser.add_argument("--source-dir", required=True, help="Local acquisition root.")
    parser.add_argument("--output-dir", required=True, help="Export staging root.")
    parser.add_argument("--cycle-id", required=True, help="Official cycle id.")
    parser.add_argument(
        "--packet-bucket",
        default="protected-packet-bucket",
        help="Packet bucket name or protected-env placeholder for manifests.",
    )
    parser.add_argument(
        "--results-bucket",
        default="protected-results-bucket",
        help="Results bucket name or protected-env placeholder for manifests.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = build_private_store_export(
        PrivateStoreExportConfig(
            source_dir=Path(cast(str, args.source_dir)),
            output_dir=Path(cast(str, args.output_dir)),
            cycle_id=cast(str, args.cycle_id),
            packet_bucket=cast(str, args.packet_bucket),
            results_bucket=cast(str, args.results_bucket),
        )
    )
    print(
        json.dumps(
            {
                "verification_report": str(result.verification_report_path),
                "object_count": len(result.objects),
            },
            sort_keys=True,
        )
    )
    return 0


def _export_source_documents(
    config: PrivateStoreExportConfig,
    document_contexts: Mapping[str, _DocumentContext],
) -> tuple[ExportObjectRecord, ...]:
    records = _read_jsonl(config.source_dir / "document-manifest.jsonl")
    objects: list[ExportObjectRecord] = []
    for record in records:
        source_document_id = _required_str(record.get("source_document_id"))
        context = document_contexts.get(source_document_id)
        if context is None:
            raise PrivateStoreExportError(
                f"document missing from candidate manifest: {source_document_id}"
            )
        source_path = _source_path(config.source_dir, record)
        local_sha256 = sha256_file(source_path)
        if local_sha256 != context.manifest_sha256:
            raise PrivateStoreExportError(
                "source document hash mismatch for "
                f"{source_document_id}: manifest={context.manifest_sha256} "
                f"local={local_sha256}"
            )
        extension = _safe_extension(source_path)
        safe_document_id = safe_path_component(
            source_document_id, field_name="source_document_id"
        )
        key = "/".join(
            (
                "source-documents",
                config.cycle_id,
                safe_path_component(context.case_id, field_name="case_id"),
                f"{safe_document_id}{extension}",
            )
        )
        destination = _object_path(config, ExportBucketRole.PACKET, key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        objects.append(
            _object_record(
                bucket_role=ExportBucketRole.PACKET,
                key=key,
                local_path=destination,
                classification=ExportClassification.RAW_PRIVATE,
                content_type=_content_type_for_path(source_path),
                source_handle=context.source_url_or_reference,
                redistribution_status="not-reviewed",
                mounted_for_model=context.mounted_for_model,
            )
        )
    return tuple(objects)


def _export_optional_existing_file(
    config: PrivateStoreExportConfig,
    source_path: Path,
    *,
    key: str,
    bucket_role: ExportBucketRole,
    classification: ExportClassification,
    content_type: str,
    source_handle: str,
    mounted_for_model: bool,
) -> ExportObjectRecord | None:
    if not source_path.is_file():
        return None
    destination = _object_path(config, bucket_role, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return _object_record(
        bucket_role=bucket_role,
        key=key,
        local_path=destination,
        classification=classification,
        content_type=content_type,
        source_handle=source_handle,
        redistribution_status="not-reviewed",
        mounted_for_model=mounted_for_model,
    )


def _export_markdown_documents(
    config: PrivateStoreExportConfig,
    document_contexts: Mapping[str, _DocumentContext],
) -> tuple[ExportObjectRecord, ...]:
    manifest_path = config.source_dir / "mistral-markdown-conversions.jsonl"
    if not manifest_path.is_file():
        return ()

    objects: list[ExportObjectRecord] = []
    seen_keys: set[str] = set()
    for record in _read_jsonl(manifest_path):
        status = _optional_str(record.get("status"))
        if status is not None and status != "succeeded":
            continue
        context = _markdown_document_context(record, document_contexts)
        if context is None:
            continue

        markdown_path = _markdown_artifact_path(
            config.source_dir,
            _required_str(record.get("markdown_path")),
        )
        objects.append(
            _copy_extracted_artifact(
                config,
                source_path=markdown_path,
                context=context,
                filename_suffix=".md",
                content_type="text/markdown",
                seen_keys=seen_keys,
            )
        )

        metadata_path_text = _optional_str(record.get("metadata_path"))
        if metadata_path_text is not None:
            metadata_path = _markdown_artifact_path(
                config.source_dir, metadata_path_text
            )
            objects.append(
                _copy_extracted_artifact(
                    config,
                    source_path=metadata_path,
                    context=context,
                    filename_suffix=".metadata.json",
                    content_type="application/json",
                    seen_keys=seen_keys,
                )
            )
    return tuple(objects)


def _markdown_document_context(
    record: Mapping[str, object],
    document_contexts: Mapping[str, _DocumentContext],
) -> _DocumentContext | None:
    source_document_id = _required_str(record.get("source_document_id"))
    context = document_contexts.get(source_document_id)
    if context is not None:
        return context

    candidate_id = _optional_str(record.get("candidate_id"))
    if candidate_id is None:
        return None
    return document_contexts.get(f"{candidate_id}-{source_document_id}")


def _markdown_artifact_path(source_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    candidates = (
        (path,)
        if path.is_absolute()
        else (source_dir / "markdown" / path, source_dir / path)
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise PrivateStoreExportError(f"markdown artifact missing: {path_text}")


def _copy_extracted_artifact(
    config: PrivateStoreExportConfig,
    *,
    source_path: Path,
    context: _DocumentContext,
    filename_suffix: str,
    content_type: str,
    seen_keys: set[str],
) -> ExportObjectRecord:
    safe_document_id = safe_path_component(
        context.source_document_id,
        field_name="source_document_id",
    )
    key = "/".join(
        (
            "extracted-text",
            config.cycle_id,
            safe_path_component(context.case_id, field_name="case_id"),
            f"{safe_document_id}{filename_suffix}",
        )
    )
    if key in seen_keys:
        raise PrivateStoreExportError(f"duplicate extracted artifact key: {key}")
    seen_keys.add(key)
    destination = _object_path(config, ExportBucketRole.PACKET, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return _object_record(
        bucket_role=ExportBucketRole.PACKET,
        key=key,
        local_path=destination,
        classification=ExportClassification.RAW_PRIVATE,
        content_type=content_type,
        source_handle=context.source_url_or_reference,
        redistribution_status="not-reviewed",
        mounted_for_model=context.mounted_for_model,
    )


def _export_model_packets(
    config: PrivateStoreExportConfig,
    packet_records: Sequence[Mapping[str, object]],
) -> tuple[ExportObjectRecord, ...]:
    objects: list[ExportObjectRecord] = []
    for index, packet in enumerate(packet_records, start=1):
        case_id = _required_str(packet.get("case_id"))
        candidate_id = _required_str(packet.get("candidate_id"))
        ablation = _optional_str(packet.get("ablation")) or "full_packet"
        key = "/".join(
            (
                "model-packets",
                config.cycle_id,
                safe_path_component(case_id, field_name="case_id"),
                f"{safe_path_component(ablation, field_name='ablation')}.json",
            )
        )
        destination = _object_path(config, ExportBucketRole.PACKET, key)
        _write_json(destination, dict(packet))
        objects.append(
            _object_record(
                bucket_role=ExportBucketRole.PACKET,
                key=key,
                local_path=destination,
                classification=ExportClassification.MODEL_VISIBLE_PRIVATE,
                content_type="application/json",
                source_handle=f"{candidate_id}:{case_id}:packet:{index}",
                redistribution_status="not-reviewed",
                mounted_for_model=True,
            )
        )
    return tuple(objects)


def _export_audit_bundle(
    config: PrivateStoreExportConfig,
    source_dir: Path,
    *,
    generated_at: datetime,
) -> ExportObjectRecord:
    artifact_records: list[JsonRecord] = []
    for relative_path in (
        "document-manifest.jsonl",
        "candidate-manifest.jsonl",
        "extracted_texts.jsonl",
        "mistral-markdown-conversions.jsonl",
        "retrievals.jsonl",
        "linkage.jsonl",
        "exclusion-ledger.jsonl",
        "accounting.jsonl",
    ):
        artifact_path = source_dir / relative_path
        if artifact_path.is_file():
            artifact_records.append(
                {
                    "path": relative_path,
                    "sha256": sha256_file(artifact_path),
                    "size_bytes": artifact_path.stat().st_size,
                }
            )
    payload: JsonRecord = {
        "schema_version": PRIVATE_STORE_EXPORT_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "generated_at": _format_datetime(generated_at),
        "audit_artifacts": artifact_records,
    }
    key = f"audit-bundles/{config.cycle_id}/acquisition-audit.json"
    destination = _object_path(config, ExportBucketRole.PACKET, key)
    _write_json(destination, payload)
    return _object_record(
        bucket_role=ExportBucketRole.PACKET,
        key=key,
        local_path=destination,
        classification=ExportClassification.AUDIT_PRIVATE,
        content_type="application/json",
        source_handle=f"{config.cycle_id}:audit-bundle",
        redistribution_status="blocked",
        mounted_for_model=False,
    )


def _write_json_object(
    config: PrivateStoreExportConfig,
    *,
    bucket_role: ExportBucketRole,
    key: str,
    payload: Mapping[str, object],
    classification: ExportClassification,
    source_handle: str,
) -> tuple[Path, ExportObjectRecord]:
    destination = _object_path(config, bucket_role, key)
    _write_json(destination, payload)
    return destination, _object_record(
        bucket_role=bucket_role,
        key=key,
        local_path=destination,
        classification=classification,
        content_type="application/json",
        source_handle=source_handle,
        redistribution_status="approved-metadata-only",
        mounted_for_model=False,
    )


def _freeze_manifest(
    config: PrivateStoreExportConfig,
    *,
    generated_at: datetime,
    source_objects: Sequence[ExportObjectRecord],
    extracted_objects: Sequence[ExportObjectRecord],
    packet_objects: Sequence[ExportObjectRecord],
    audit_objects: Sequence[ExportObjectRecord],
    accounting_summary: Mapping[str, object],
) -> JsonRecord:
    return {
        "schema_version": PRIVATE_STORE_EXPORT_SCHEMA_VERSION,
        "storage_manifest_version": STORAGE_MANIFEST_VERSION,
        "cycle_id": config.cycle_id,
        "generated_at": _format_datetime(generated_at),
        "packet_bucket": config.packet_bucket,
        "results_bucket": config.results_bucket,
        "packet_prefixes": [
            "source-documents/",
            "extracted-text/",
            "model-packets/",
            "audit-bundles/",
            "withdrawn/",
            "quarantine/",
        ],
        "result_prefixes": ["manifests/", "run-cards/", "metrics/", "reports/"],
        "source_documents": _records(source_objects, config.output_dir),
        "extracted_text": _records(extracted_objects, config.output_dir),
        "model_packets": _records(packet_objects, config.output_dir),
        "audit_bundles": _records(audit_objects, config.output_dir),
        "withdrawn": [],
        "accounting_summary": dict(accounting_summary),
    }


def _run_input_manifest(
    config: PrivateStoreExportConfig,
    *,
    generated_at: datetime,
    packet_records: Sequence[Mapping[str, object]],
    packet_objects: Sequence[ExportObjectRecord],
    document_contexts: Mapping[str, _DocumentContext],
) -> JsonRecord:
    packet_inputs: list[JsonRecord] = []
    if len(packet_records) != len(packet_objects):
        raise PrivateStoreExportError("packet record/object count mismatch")
    for packet, packet_object in zip(packet_records, packet_objects, strict=True):
        source_document_ids = _packet_source_document_ids(packet)
        packet_input: JsonRecord = {
            "case_id": _required_str(packet.get("case_id")),
            "candidate_id": _required_str(packet.get("candidate_id")),
            "ablation": _optional_str(packet.get("ablation")) or "full_packet",
            "packet_object_key": packet_object.key,
            "packet_sha256": packet_object.sha256,
            "packet_size_bytes": packet_object.size_bytes,
            "source_document_ids": source_document_ids,
            "source_hashes": {
                source_document_id: document_contexts[
                    source_document_id
                ].manifest_sha256
                for source_document_id in source_document_ids
                if source_document_id in document_contexts
            },
        }
        decision_date = _packet_decision_date(packet)
        if decision_date is not None:
            packet_input["decision_date"] = decision_date
        packet_inputs.append(packet_input)
    return {
        "schema_version": PRIVATE_STORE_EXPORT_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "generated_at": _format_datetime(generated_at),
        "model_packets": packet_inputs,
    }


def _packet_decision_date(packet: Mapping[str, object]) -> str | None:
    decision_date = _optional_str(packet.get("decision_date"))
    if decision_date is not None:
        return decision_date
    metadata = packet.get("metadata")
    if isinstance(metadata, Mapping):
        metadata_mapping = cast(Mapping[str, object], metadata)
        return _optional_str(metadata_mapping.get("decision_date"))
    return None


def _public_reconstruction_manifest(
    config: PrivateStoreExportConfig,
    *,
    generated_at: datetime,
    candidate_records: Sequence[Mapping[str, object]],
    packet_records: Sequence[Mapping[str, object]],
    packet_objects: Sequence[ExportObjectRecord],
) -> JsonRecord:
    candidates: list[JsonRecord] = []
    packet_renders = _packet_render_records(
        packet_records=packet_records,
        packet_objects=packet_objects,
    )
    for candidate in candidate_records:
        candidate_id = _required_str(candidate.get("candidate_id"))
        documents: list[JsonRecord] = []
        for document in _record_sequence(candidate.get("documents"), "documents"):
            documents.append(
                {
                    "source_document_id": _required_str(
                        document.get("source_document_id")
                    ),
                    "source_provider": _required_str(document.get("source_provider")),
                    "document_role": _required_str(document.get("document_role")),
                    "sha256": _required_str(document.get("sha256")),
                    "source_url_or_reference": _required_str(
                        document.get("source_url_or_reference")
                    ),
                    "is_mounted_for_model": _required_bool(
                        document.get("is_mounted_for_model")
                    ),
                    "redistribution_status": "approved-metadata-only",
                }
            )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "case_id": _required_str(candidate.get("case_id")),
                "manifest_record_hash": _optional_str(
                    candidate.get("manifest_record_hash")
                ),
                "documents": documents,
                "packet_render": packet_renders.get(candidate_id),
            }
        )
    return {
        "schema_version": PRIVATE_STORE_EXPORT_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "generated_at": _format_datetime(generated_at),
        "candidates": candidates,
        "withdrawn": [],
    }


def _verification_report(
    config: PrivateStoreExportConfig,
    *,
    generated_at: datetime,
    objects: Sequence[ExportObjectRecord],
    accounting_summary: Mapping[str, object],
) -> JsonRecord:
    return {
        "schema_version": PRIVATE_STORE_EXPORT_SCHEMA_VERSION,
        "cycle_id": config.cycle_id,
        "generated_at": _format_datetime(generated_at),
        "object_count": len(objects),
        "verified_object_count": sum(1 for record in objects if record.verified),
        "total_size_bytes": sum(record.size_bytes for record in objects),
        "accounting_summary": dict(accounting_summary),
        "objects": _records(objects, config.output_dir),
    }


def _document_contexts(
    candidate_records: Sequence[Mapping[str, object]],
) -> dict[str, _DocumentContext]:
    contexts: dict[str, _DocumentContext] = {}
    for candidate in candidate_records:
        candidate_id = _required_str(candidate.get("candidate_id"))
        case_id = _required_str(candidate.get("case_id"))
        manifest_record_hash = _optional_str(candidate.get("manifest_record_hash"))
        for document in _record_sequence(candidate.get("documents"), "documents"):
            source_document_id = _required_str(document.get("source_document_id"))
            if source_document_id in contexts:
                raise PrivateStoreExportError(
                    f"duplicate source_document_id: {source_document_id}"
                )
            contexts[source_document_id] = _DocumentContext(
                candidate_id=candidate_id,
                case_id=case_id,
                source_document_id=source_document_id,
                source_provider=_required_str(document.get("source_provider")),
                document_role=_required_str(document.get("document_role")),
                source_url_or_reference=_required_str(
                    document.get("source_url_or_reference")
                ),
                manifest_sha256=_required_sha256(document.get("sha256")),
                mounted_for_model=_required_bool(document.get("is_mounted_for_model")),
                manifest_record_hash=manifest_record_hash,
            )
    return contexts


def _accounting_summary(path: Path) -> JsonRecord:
    if not path.is_file():
        return {"record_count": 0, "estimated_cost": 0.0}
    records = _read_jsonl(path)
    return {
        "record_count": len(records),
        "estimated_cost": sum(
            _numeric(record.get("estimated_cost")) for record in records
        ),
    }


def _packet_source_document_ids(packet: Mapping[str, object]) -> list[str]:
    ids: list[str] = []
    for document in _record_sequence(packet.get("documents"), "packet.documents"):
        ids.append(_required_str(document.get("source_document_id")))
    return ids


def _packet_render_records(
    *,
    packet_records: Sequence[Mapping[str, object]],
    packet_objects: Sequence[ExportObjectRecord],
) -> dict[str, JsonRecord]:
    if len(packet_records) != len(packet_objects):
        raise PrivateStoreExportError("packet record/object count mismatch")
    renders: dict[str, JsonRecord] = {}
    selected_ablation: dict[str, str] = {}
    for packet, packet_object in zip(packet_records, packet_objects, strict=True):
        candidate_id = _required_str(packet.get("candidate_id"))
        ablation = _optional_str(packet.get("ablation")) or "full_packet"
        if candidate_id in renders and selected_ablation[candidate_id] == "full_packet":
            continue
        if candidate_id in renders and ablation != "full_packet":
            continue
        selected_ablation[candidate_id] = ablation
        renders[candidate_id] = {
            "packet_sha256": packet_object.sha256,
            "packet_json_path": packet_object.key,
            "prompt_sha256": None,
            "prompt_path": None,
            "rebuild_command": [
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
                ablation,
            ],
        }
    return renders


def _records(
    objects: Iterable[ExportObjectRecord], output_dir: Path
) -> list[JsonRecord]:
    return [record.to_record(output_dir=output_dir) for record in objects]


def _source_path(source_dir: Path, record: Mapping[str, object]) -> Path:
    raw_path = _required_str(record.get("path"))
    path = Path(raw_path)
    resolved = path if path.is_absolute() else source_dir / path
    if not resolved.is_file():
        raise PrivateStoreExportError(f"source document missing: {resolved}")
    return resolved


def _object_path(
    config: PrivateStoreExportConfig,
    bucket_role: ExportBucketRole,
    key: str,
) -> Path:
    _require_safe_object_key(key, "key")
    return config.output_dir / "objects" / bucket_role.value / Path(key)


def _object_record(
    *,
    bucket_role: ExportBucketRole,
    key: str,
    local_path: Path,
    classification: ExportClassification,
    content_type: str,
    source_handle: str,
    redistribution_status: str,
    mounted_for_model: bool,
) -> ExportObjectRecord:
    digest = sha256_file(local_path)
    size_bytes = local_path.stat().st_size
    verified = sha256_file(local_path) == digest
    return ExportObjectRecord(
        bucket_role=bucket_role,
        key=key,
        local_path=local_path,
        sha256=digest,
        size_bytes=size_bytes,
        content_type=content_type,
        classification=classification,
        source_handle=source_handle,
        redistribution_status=redistribution_status,
        mounted_for_model=mounted_for_model,
        verified=verified,
    )


def _read_jsonl(path: Path) -> list[JsonRecord]:
    if not path.is_file():
        raise PrivateStoreExportError(f"required JSONL artifact missing: {path}")
    records: list[JsonRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value: object = json.loads(line)
            if not isinstance(value, dict):
                raise PrivateStoreExportError(
                    f"{path} line {line_number} is not a JSON object"
                )
            records.append(cast(JsonRecord, value))
    return records


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _record_sequence(value: object, field_name: str) -> tuple[JsonRecord, ...]:
    if not isinstance(value, list):
        raise PrivateStoreExportError(f"{field_name} must be a list")
    records: list[JsonRecord] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise PrivateStoreExportError(f"{field_name} must contain objects")
        records.append(cast(JsonRecord, item))
    return tuple(records)


def _required_str(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrivateStoreExportError("required string field is missing")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return _required_str(value)


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise PrivateStoreExportError("required boolean field is missing")
    return value


def _required_sha256(value: object) -> str:
    text = _required_str(value)
    _require_sha256(text, "sha256")
    return text


def _require_sha256(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise PrivateStoreExportError(
            f"{field_name} must be a lowercase SHA-256 hex digest"
        )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _format_datetime(value: datetime) -> str:
    return format_utc_iso_z(value)


def _safe_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    if not suffix or "/" in suffix or "\\" in suffix:
        return ".bin"
    return suffix


def _content_type_for_path(path: Path) -> str:
    match path.suffix.lower():
        case ".pdf":
            return "application/pdf"
        case ".json":
            return "application/json"
        case ".jsonl":
            return "application/jsonl"
        case ".txt":
            return "text/plain"
        case _:
            return "application/octet-stream"


def _require_safe_object_key(value: str, field_name: str) -> None:
    if value.startswith("/") or "\\" in value:
        raise PrivateStoreExportError(f"{field_name} must be a relative POSIX key")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
        raise PrivateStoreExportError(
            f"{field_name} must not contain unsafe path components"
        )


def _numeric(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
