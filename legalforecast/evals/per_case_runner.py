"""Isolated per-case runner for official packet-shard evaluation jobs."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from legalforecast._record_validation import (
    optional_str,
    required_bool,
    required_float,
    required_int,
    required_str,
)
from legalforecast.evals.accounting import accounting_records_from_inspect_run
from legalforecast.evals.inspect_task import (
    DEFAULT_TOOL_CALL_CAP,
    ConfiguredModelStubSolver,
    OfflineMockSolver,
    build_inspect_samples,
    run_inspect_fixture,
)
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketDocument,
)
from legalforecast.ingestion.provenance import DocumentRole, sha256_text
from legalforecast.path_safety import safe_path_component
from legalforecast.protocol.freeze import sha256_file
from legalforecast.unitization.schemas import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)

JsonRecord = dict[str, Any]

MODEL_PACKET_PREFIX = "model-packets/"
RESULT_PREFIXES = ("run-cards/", "manifests/", "metrics/", "reports/")
DENIED_PACKET_PREFIXES = (
    "audit-bundles/",
    "extracted-text/",
    "quarantine/",
    "source-documents/",
    "withdrawn/",
)

_OBJECT_REFERENCE_FIELDS = frozenset(
    {
        "key",
        "object_key",
        "packet_object_key",
        "s3_key",
        "source_object_key",
        "storage_key",
    }
)
_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


class PerCaseRunnerError(RuntimeError):
    """Base error for per-case runner safety failures."""


class PacketManifestError(PerCaseRunnerError):
    """Raised when the runner input manifest is missing or unsafe."""


class PerCaseExecutionBackend(StrEnum):
    """Supported per-case execution backends."""

    FIXTURE = "fixture"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class PerCaseRunnerConfig:
    """Inputs for one isolated model-packet evaluation."""

    manifest_uri: str
    case_id: str
    ablation: str
    output_dir: Path
    mock_output: str | None = None
    packet_store_root: str | None = None
    results_store_root: str | None = None
    repeat_count: int = 1
    solver_id: str = "offline:fixture"
    backend: PerCaseExecutionBackend = PerCaseExecutionBackend.FIXTURE
    model_registry_uri: str | None = None
    model_key: str | None = None
    max_tool_calls: int = DEFAULT_TOOL_CALL_CAP
    use_docket_tool: bool = True
    evaluation_timestamp: datetime | None = None
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.manifest_uri, "manifest_uri"),
            (self.case_id, "case_id"),
            (self.ablation, "ablation"),
            (self.solver_id, "solver_id"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        if self.backend is PerCaseExecutionBackend.FIXTURE and (
            self.mock_output is None or not self.mock_output.strip()
        ):
            raise ValueError("mock_output is required for fixture backend")
        if self.backend is PerCaseExecutionBackend.LIVE:
            if self.model_registry_uri is None or not self.model_registry_uri.strip():
                raise ValueError("model_registry_uri is required for live backend")
            if self.model_key is None or not self.model_key.strip():
                raise ValueError("model_key is required for live backend")
        for value, field_name in (
            (self.model_registry_uri, "model_registry_uri"),
            (self.model_key, "model_key"),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must not be blank")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.repeat_count <= 0:
            raise ValueError("repeat_count must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.evaluation_timestamp is not None:
            _require_aware_datetime(
                self.evaluation_timestamp,
                "evaluation_timestamp",
            )


@dataclass(frozen=True, slots=True)
class ModelPacketObject:
    """One model-packet object selected from the runner input manifest."""

    case_id: str
    ablation: str
    object_key: str
    sha256: str
    size_bytes: int | None = None
    uri: str | None = None
    bucket: str | None = None
    cycle_id: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class PerCaseRunArtifacts:
    """Local and uploaded artifacts from one per-case run."""

    run_id: str
    case_id: str
    ablation: str
    packet_object_key: str
    packet_sha256: str
    output_dir: Path
    local_paths: tuple[Path, ...]
    uploaded_uris: tuple[str, ...]

    def to_record(self) -> JsonRecord:
        return {
            "schema_version": "legalforecast.per_case_runner_artifacts.v1",
            "run_id": self.run_id,
            "case_id": self.case_id,
            "ablation": self.ablation,
            "packet_object_key": self.packet_object_key,
            "packet_sha256": self.packet_sha256,
            "output_dir": str(self.output_dir),
            "local_paths": [str(path) for path in self.local_paths],
            "uploaded_uris": list(self.uploaded_uris),
        }


def run_per_case_evaluation(config: PerCaseRunnerConfig) -> PerCaseRunArtifacts:
    """Fetch, verify, run, clean up, and publish one model-visible packet shard."""

    config.output_dir.mkdir(parents=True, exist_ok=True)
    logs: list[JsonRecord] = []
    evaluation_timestamp = config.evaluation_timestamp or datetime.now(UTC)
    log_path = config.output_dir / "runner-log.jsonl"

    def log(event: str, **fields: Any) -> None:
        record: JsonRecord = {
            "schema_version": "legalforecast.per_case_runner_log.v1",
            "event": event,
            "case_id": config.case_id,
            "ablation": config.ablation,
            "timestamp": _iso_datetime(datetime.now(UTC)),
        }
        record.update(fields)
        logs.append(record)

    try:
        manifest = _read_json_uri(config.manifest_uri)
        packet_object = _select_packet_object(
            manifest,
            case_id=config.case_id,
            ablation=config.ablation,
        )
        registry_entry, model_registry_sha256 = _optional_registry_entry(config)
        solver_id = (
            registry_entry.registry_key
            if registry_entry is not None
            else config.solver_id
        )
        packet_uri = _packet_object_uri(packet_object, config.packet_store_root)
        run_id = _run_id(
            cycle_id=packet_object.cycle_id or _optional_manifest_cycle_id(manifest),
            case_id=config.case_id,
            ablation=config.ablation,
            solver_id=solver_id,
        )
        log(
            "manifest_selected",
            manifest_uri=config.manifest_uri,
            packet_object_key=packet_object.object_key,
            packet_uri=packet_uri,
            backend=config.backend.value,
            model_key=config.model_key,
            model_registry_sha256=model_registry_sha256,
        )

        with tempfile.TemporaryDirectory(prefix="lfb-per-case-") as workspace:
            workspace_path = Path(workspace)
            packet_path = workspace_path / "model-packet.json"
            _fetch_uri(packet_uri, packet_path)
            actual_sha256 = sha256_file(packet_path)
            if actual_sha256 != packet_object.sha256:
                raise PerCaseRunnerError(
                    "model packet SHA-256 mismatch: "
                    f"expected {packet_object.sha256}, got {actual_sha256}"
                )
            if (
                packet_object.size_bytes is not None
                and packet_path.stat().st_size != packet_object.size_bytes
            ):
                raise PerCaseRunnerError(
                    "model packet byte size mismatch: "
                    f"expected {packet_object.size_bytes}, "
                    f"got {packet_path.stat().st_size}"
                )
            log(
                "packet_verified",
                packet_object_key=packet_object.object_key,
                packet_sha256=actual_sha256,
                size_bytes=packet_path.stat().st_size,
            )

            packet_record = _read_json_path(packet_path)
            _reject_restricted_packet_references(packet_record)
            packet = _model_packet_from_record(packet_record)
            _validate_model_packet(packet, config=config)

            samples = build_inspect_samples(
                (packet,),
                max_tool_calls=config.max_tool_calls,
                run_label=config.ablation,
                use_docket_tool=config.use_docket_tool,
            )
            samples = _repeat_samples(samples, repeat_count=config.repeat_count)
            solver = _solver_for_config(
                config,
                registry_entry=registry_entry,
                model_registry_sha256=model_registry_sha256,
            )
            run = run_inspect_fixture(
                samples,
                (solver,),
            )
            run_records = _annotate_repeat_records(
                run.to_records(),
                repeat_count=config.repeat_count,
            )
            accounting_records = _annotate_repeat_records(
                [
                    record.to_record()
                    for record in accounting_records_from_inspect_run(
                        run,
                        evaluation_timestamp=evaluation_timestamp,
                    )
                ],
                repeat_count=config.repeat_count,
            )

        runs_path = config.output_dir / "runs.jsonl"
        accounting_path = config.output_dir / "accounting.jsonl"
        metrics_path = config.output_dir / "metrics.json"

        _write_jsonl(runs_path, run_records)
        _write_jsonl(accounting_path, accounting_records)
        metrics = _metrics_record(
            config=config,
            packet_object=packet_object,
            run_id=run_id,
            packet_sha256=actual_sha256,
            run_records=run_records,
            evaluation_timestamp=evaluation_timestamp,
            solver_id=solver_id,
            model_registry_sha256=model_registry_sha256,
        )
        _write_json(metrics_path, metrics)
        local_paths = (runs_path, accounting_path, metrics_path, log_path)
        log(
            "artifacts_written",
            output_dir=str(config.output_dir),
            local_paths=[str(path) for path in local_paths[:-1]],
        )

        uploaded_uris = _publish_outputs(
            config=config,
            packet_object=packet_object,
            run_id=run_id,
            local_outputs=(
                (
                    runs_path,
                    f"metrics/{_cycle_slug(packet_object)}/{run_id}.runs.jsonl",
                ),
                (
                    accounting_path,
                    f"metrics/{_cycle_slug(packet_object)}/{run_id}.accounting.jsonl",
                ),
                (
                    metrics_path,
                    f"metrics/{_cycle_slug(packet_object)}/{run_id}.metrics.json",
                ),
            ),
            log=log,
        )
        log("runner_completed", uploaded_uris=uploaded_uris)
        _write_jsonl(log_path, logs)
        if config.results_store_root is not None:
            log_key = f"reports/{_cycle_slug(packet_object)}/{run_id}.runner-log.jsonl"
            log_uri = _join_uri(
                config.results_store_root,
                log_key,
            )
            _ensure_result_key(log_key)
            _upload_path(log_path, log_uri, content_type="application/x-jsonlines")
            uploaded_uris = (*uploaded_uris, log_uri)

        return PerCaseRunArtifacts(
            run_id=run_id,
            case_id=config.case_id,
            ablation=config.ablation,
            packet_object_key=packet_object.object_key,
            packet_sha256=actual_sha256,
            output_dir=config.output_dir,
            local_paths=local_paths,
            uploaded_uris=uploaded_uris,
        )
    except Exception as exc:
        log(
            "runner_failed",
            error_type=type(exc).__name__,
            message=_safe_error_message(exc),
        )
        _write_jsonl(log_path, logs)
        if isinstance(exc, PerCaseRunnerError):
            raise
        raise PerCaseRunnerError(str(exc)) from exc


def _select_packet_object(
    manifest: Mapping[str, Any],
    *,
    case_id: str,
    ablation: str,
) -> ModelPacketObject:
    for record in _packet_object_records(manifest):
        packet_object = _packet_object_from_record(record, manifest=manifest)
        if packet_object.case_id == case_id and packet_object.ablation == ablation:
            _ensure_packet_key(packet_object.object_key)
            return packet_object
    raise PacketManifestError(
        f"manifest does not include case_id={case_id!r}, ablation={ablation!r}"
    )


def _packet_object_records(
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    for field_name in ("model_packets", "cases", "packets"):
        value = manifest.get(field_name)
        if value is None:
            continue
        if not isinstance(value, Sequence) or isinstance(value, str):
            raise PacketManifestError(f"{field_name} must be a list")
        items = cast(Sequence[object], value)
        return tuple(_mapping(item, f"{field_name} item") for item in items)
    if "object_key" in manifest or "packet_object_key" in manifest or "uri" in manifest:
        return (manifest,)
    raise PacketManifestError("manifest must include model_packets")


def _packet_object_from_record(
    record: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
) -> ModelPacketObject:
    object_key = _object_key(record)
    size_bytes = _optional_positive_int(record, "size_bytes")
    return ModelPacketObject(
        case_id=required_str(record, "case_id"),
        ablation=optional_str(record, "ablation")
        or optional_str(record, "run_label")
        or PacketAblation.FULL_PACKET.value,
        object_key=object_key,
        sha256=_normalize_sha256(_packet_sha256(record)),
        size_bytes=size_bytes,
        uri=optional_str(record, "uri") or optional_str(record, "s3_uri"),
        bucket=optional_str(record, "bucket")
        or optional_str(manifest, "packet_bucket"),
        cycle_id=optional_str(record, "cycle_id")
        or _optional_manifest_cycle_id(manifest),
        content_type=optional_str(record, "content_type"),
    )


def _packet_sha256(record: Mapping[str, Any]) -> str:
    return required_str(
        {
            "sha256": optional_str(record, "sha256")
            or optional_str(record, "packet_sha256")
        },
        "sha256",
    )


def _object_key(record: Mapping[str, Any]) -> str:
    uri = optional_str(record, "uri") or optional_str(record, "s3_uri")
    if uri is not None:
        return _object_key_from_uri(uri)
    for field_name in ("object_key", "key", "packet_object_key", "path"):
        value = optional_str(record, field_name)
        if value is not None:
            return value
    raise PacketManifestError("model packet record requires object_key or uri")


def _packet_object_uri(
    packet_object: ModelPacketObject,
    packet_store_root: str | None,
) -> str:
    if packet_object.uri is not None:
        return packet_object.uri
    if packet_store_root is not None:
        return _join_uri(packet_store_root, packet_object.object_key)
    if packet_object.bucket is not None:
        return f"s3://{packet_object.bucket}/{packet_object.object_key}"
    raise PacketManifestError(
        "packet_store_root or packet bucket is required for manifest object keys"
    )


def _publish_outputs(
    *,
    config: PerCaseRunnerConfig,
    packet_object: ModelPacketObject,
    run_id: str,
    local_outputs: Sequence[tuple[Path, str]],
    log: Any,
) -> tuple[str, ...]:
    if config.results_store_root is None:
        return ()
    uploaded: list[str] = []
    for source_path, object_key in local_outputs:
        _ensure_result_key(object_key)
        destination_uri = _join_uri(config.results_store_root, object_key)
        _upload_path(
            source_path,
            destination_uri,
            content_type=_content_type_for_path(source_path),
        )
        uploaded.append(destination_uri)
        log(
            "artifact_uploaded",
            packet_object_key=packet_object.object_key,
            run_id=run_id,
            artifact_path=str(source_path),
            destination_uri=destination_uri,
            artifact_sha256=sha256_file(source_path),
        )
    return tuple(uploaded)


def _metrics_record(
    *,
    config: PerCaseRunnerConfig,
    packet_object: ModelPacketObject,
    run_id: str,
    packet_sha256: str,
    run_records: Sequence[Mapping[str, Any]],
    evaluation_timestamp: datetime,
    solver_id: str,
    model_registry_sha256: str | None,
) -> JsonRecord:
    raw_output_hashes = [
        required_str(record, "raw_output_sha256") for record in run_records
    ]
    tool_call_count = sum(
        len(cast(Sequence[object], record.get("tool_call_logs", ())))
        for record in run_records
    )
    return {
        "schema_version": "legalforecast.per_case_metrics.v1",
        "run_id": run_id,
        "cycle_id": packet_object.cycle_id,
        "case_id": config.case_id,
        "ablation": config.ablation,
        "solver_id": solver_id,
        "backend": config.backend.value,
        "model_key": config.model_key,
        "model_registry_uri": config.model_registry_uri,
        "model_registry_sha256": model_registry_sha256,
        "evaluation_timestamp": _iso_datetime(evaluation_timestamp),
        "packet_object_key": packet_object.object_key,
        "packet_sha256": packet_sha256,
        "repeat_count": config.repeat_count,
        "primary_run_record_count": sum(
            1 for record in run_records if _repeat_index(record) == 1
        ),
        "run_record_count": len(run_records),
        "raw_output_sha256": raw_output_hashes,
        "tool_call_count": tool_call_count,
    }


def _repeat_samples(
    samples: Sequence[Any],
    *,
    repeat_count: int,
) -> tuple[Any, ...]:
    if repeat_count == 1:
        return tuple(samples)
    repeated: list[Any] = []
    for sample in samples:
        for index in range(1, repeat_count + 1):
            repeated.append(
                replace(
                    sample,
                    sample_id=f"{sample.sample_id}__repeat_{index:02d}",
                )
            )
    return tuple(repeated)


def _annotate_repeat_records(
    records: Sequence[Mapping[str, Any]],
    *,
    repeat_count: int,
) -> list[JsonRecord]:
    annotated: list[JsonRecord] = []
    for record in records:
        copy = dict(record)
        repeat_index = _repeat_index(copy)
        if repeat_count > 1:
            sample_id = required_str(copy, "sample_id")
            repeat_group_id = sample_id.rsplit("__repeat_", 1)[0]
            copy["repeat_group_id"] = repeat_group_id
            copy["repeat_index"] = repeat_index
            copy["repeat_count"] = repeat_count
            copy["repeat_sampling_role"] = "primary" if repeat_index == 1 else "repeat"
        annotated.append(copy)
    return annotated


def _repeat_index(record: Mapping[str, Any]) -> int:
    existing = record.get("repeat_index")
    if isinstance(existing, int) and not isinstance(existing, bool) and existing > 0:
        return existing
    sample_id = required_str(record, "sample_id")
    if "__repeat_" not in sample_id:
        return 1
    suffix = sample_id.rsplit("__repeat_", 1)[1]
    if suffix.isdigit() and int(suffix) > 0:
        return int(suffix)
    raise PerCaseRunnerError(f"invalid repeat sample_id suffix: {sample_id}")


def _model_packet_from_record(record: Mapping[str, Any]) -> ModelPacket:
    return ModelPacket(
        candidate_id=required_str(record, "candidate_id"),
        case_id=required_str(record, "case_id"),
        court=required_str(record, "court"),
        docket_number=required_str(record, "docket_number"),
        ablation=PacketAblation(required_str(record, "ablation")),
        metadata=_optional_str_mapping(record.get("metadata", {}), "metadata"),
        documents=tuple(
            _packet_document(document)
            for document in _record_sequence(record, "documents")
        ),
        prediction_units=tuple(
            _prediction_unit(unit)
            for unit in _record_sequence(record, "prediction_units")
        ),
        excluded_document_ids=_str_tuple(record.get("excluded_document_ids", ())),
        missing_optional_sections=_str_tuple(
            record.get("missing_optional_sections", ())
        ),
        related_family_id=optional_str(record, "related_family_id"),
        mdl_family_id=optional_str(record, "mdl_family_id"),
    )


def _packet_document(record: Mapping[str, Any]) -> PacketDocument:
    return PacketDocument(
        source_document_id=required_str(record, "source_document_id"),
        document_role=DocumentRole(required_str(record, "document_role")),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        source_provider=required_str(record, "source_provider"),
        source_url_or_reference=required_str(record, "source_url_or_reference"),
        source_sha256=required_str(record, "source_sha256"),
        text=required_str(record, "text"),
        text_sha256=_normalize_sha256(required_str(record, "text_sha256")),
        quality_flags=_str_tuple(record.get("quality_flags", ())),
        extraction_method=optional_str(record, "extraction_method"),
        packet_section=optional_str(record, "packet_section"),
    )


def _prediction_unit(record: Mapping[str, Any]) -> PredictionUnit:
    unit_id = required_str(record, "unit_id")
    source_citations = tuple(
        _source_citation(citation)
        for citation in _optional_record_sequence(record, "source_citations")
    ) or (
        SourceCitation(
            document_id="model_packet",
            excerpt=f"model-visible prediction unit: {unit_id}",
        ),
    )
    return PredictionUnit(
        unit_id=unit_id,
        count=required_str(record, "count"),
        claim_name=required_str(record, "claim_name"),
        defendant_group=required_str(record, "defendant_group"),
        challenged_by_motion=required_bool(record, "challenged_by_motion"),
        challenge_scope=ChallengeScope(required_str(record, "challenge_scope")),
        unit_confidence=_optional_float(record, "unit_confidence", default=1.0),
        source_citations=source_citations,
        grouping=DefendantGrouping(
            optional_str(record, "grouping") or DefendantGrouping.INDIVIDUAL.value
        ),
        grouping_rationale=optional_str(record, "grouping_rationale"),
        separable_subclaim=optional_str(record, "separable_subclaim"),
        uncertainty_notes=optional_str(record, "uncertainty_notes"),
    )


def _source_citation(record: Mapping[str, Any]) -> SourceCitation:
    return SourceCitation(
        document_id=required_str(record, "document_id"),
        docket_entry_number=_optional_int(record, "docket_entry_number"),
        page=_optional_int(record, "page"),
        paragraph=_optional_int(record, "paragraph"),
        excerpt=optional_str(record, "excerpt"),
    )


def _validate_model_packet(
    packet: ModelPacket,
    *,
    config: PerCaseRunnerConfig,
) -> None:
    if packet.case_id != config.case_id:
        raise PerCaseRunnerError(
            f"packet case_id mismatch: expected {config.case_id}, got {packet.case_id}"
        )
    if packet.ablation.value != config.ablation:
        raise PerCaseRunnerError(
            "packet ablation mismatch: "
            f"expected {config.ablation}, got {packet.ablation.value}"
        )
    for document in packet.documents:
        if document.document_role in {DocumentRole.ORDER, DocumentRole.DECISION}:
            raise PerCaseRunnerError(
                f"model packet contains outcome material: {document.source_document_id}"
            )
        if document.packet_section in {"audit", "audit_only", "post_decision"}:
            raise PerCaseRunnerError(
                "model packet contains non-model-visible packet section: "
                f"{document.source_document_id}"
            )
        if _normalize_sha256(document.text_sha256) != sha256_text(document.text):
            raise PerCaseRunnerError(
                f"model packet text hash mismatch: {document.source_document_id}"
            )


def _optional_registry_entry(
    config: PerCaseRunnerConfig,
) -> tuple[ModelRegistryEntry | None, str | None]:
    if config.model_registry_uri is None:
        return None, None
    registry, digest = _load_model_registry_uri(config.model_registry_uri)
    if config.backend is PerCaseExecutionBackend.LIVE:
        require_official_registry_entries(registry.entries)
    if config.model_key is None:
        raise PerCaseRunnerError("model_key is required with model_registry_uri")
    provider, separator, model_id = config.model_key.partition(":")
    if separator != ":" or not provider or not model_id:
        raise PerCaseRunnerError("model_key must use provider:model_id")
    try:
        return registry.get(provider, model_id), digest
    except KeyError as exc:
        raise PerCaseRunnerError(
            f"model_key not found in model registry: {config.model_key}"
        ) from exc


def _load_model_registry_uri(uri: str) -> tuple[ModelRegistry, str]:
    if _is_s3_uri(uri):
        payload = _read_uri_bytes(uri)
        loaded: object = json.loads(payload.decode("utf-8"))
        if not isinstance(loaded, list):
            raise PerCaseRunnerError("model registry file must contain a JSON array")
        registry_records = cast(list[object], loaded)
        registry = ModelRegistry.from_records(
            tuple(_mapping(item, "model registry item") for item in registry_records)
        )
        return registry, hashlib.sha256(payload).hexdigest()
    path = _local_path_from_uri(uri)
    return load_model_registry(path), sha256_file(path)


def _solver_for_config(
    config: PerCaseRunnerConfig,
    *,
    registry_entry: ModelRegistryEntry | None,
    model_registry_sha256: str | None,
) -> Any:
    if config.backend is PerCaseExecutionBackend.FIXTURE:
        if registry_entry is None:
            return OfflineMockSolver(
                solver_id=config.solver_id,
                raw_output=cast(str, config.mock_output),
                input_tokens=100,
                output_tokens=25,
                estimated_cost=0.0,
                use_docket_tool=config.use_docket_tool,
            )
        return ConfiguredModelStubSolver(
            registry_entry=registry_entry,
            stub_raw_output=cast(str, config.mock_output),
            input_tokens=100,
            output_tokens=25,
            estimated_cost=0.0,
        )
    if registry_entry is None:
        raise PerCaseRunnerError("live backend requires a model registry entry")
    try:
        from legalforecast.evals.live_model_solver import LiveModelSolver
    except ImportError as exc:  # pragma: no cover - defensive for partial installs.
        raise PerCaseRunnerError("live model solver is not available") from exc
    return LiveModelSolver(
        registry_entry=registry_entry,
        model_registry_sha256=model_registry_sha256,
        timeout_seconds=config.timeout_seconds,
    )


def _reject_restricted_packet_references(value: object) -> None:
    if isinstance(value, Mapping):
        for raw_key, raw_value in cast(Mapping[object, object], value).items():
            if isinstance(raw_key, str) and raw_key in _OBJECT_REFERENCE_FIELDS:
                if isinstance(raw_value, str) and _has_denied_prefix(raw_value):
                    raise PerCaseRunnerError(
                        f"packet references restricted object key in {raw_key}"
                    )
            _reject_restricted_packet_references(raw_value)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for item in cast(Sequence[object], value):
            _reject_restricted_packet_references(item)


def _ensure_packet_key(object_key: str) -> None:
    _ensure_relative_object_key(object_key)
    if not object_key.startswith(MODEL_PACKET_PREFIX):
        raise PacketManifestError(
            f"model packet object key must start with {MODEL_PACKET_PREFIX}"
        )
    if _has_denied_prefix(object_key):
        raise PacketManifestError("model packet object key uses a restricted prefix")


def _ensure_result_key(object_key: str) -> None:
    _ensure_relative_object_key(object_key)
    if not object_key.startswith(RESULT_PREFIXES):
        allowed = ", ".join(RESULT_PREFIXES)
        raise PerCaseRunnerError(f"result object key must start with one of: {allowed}")
    if _has_denied_prefix(object_key):
        raise PerCaseRunnerError("result object key uses a restricted prefix")


def _ensure_relative_object_key(object_key: str) -> None:
    if not object_key.strip():
        raise ValueError("object key is required")
    if object_key.startswith("/") or "\\" in object_key:
        raise ValueError("object key must be relative and use forward slashes")
    parts = object_key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("object key must not contain empty or relative components")


def _has_denied_prefix(value: str) -> bool:
    parsed = urlparse(value)
    key = parsed.path.lstrip("/") if parsed.scheme in {"s3", "file"} else value
    return any(key.startswith(prefix) for prefix in DENIED_PACKET_PREFIXES)


def _read_json_uri(uri: str) -> JsonRecord:
    loaded = json.loads(_read_uri_bytes(uri).decode("utf-8"))
    if not isinstance(loaded, Mapping):
        raise PacketManifestError(f"{uri} must contain a JSON object")
    return dict(cast(Mapping[str, Any], loaded))


def _read_json_path(path: Path) -> JsonRecord:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise PerCaseRunnerError(f"{path} must contain a JSON object")
    return dict(cast(Mapping[str, Any], loaded))


def _read_uri_bytes(uri: str) -> bytes:
    if _is_s3_uri(uri):
        return _aws_s3_cp_to_stdout(uri)
    return _local_path_from_uri(uri).read_bytes()


def _fetch_uri(uri: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if _is_s3_uri(uri):
        _run_aws_s3_cp(uri, str(destination))
        return
    shutil.copyfile(_local_path_from_uri(uri), destination)


def _upload_path(source: Path, destination_uri: str, *, content_type: str) -> None:
    if _is_s3_uri(destination_uri):
        _run_aws_s3_cp(
            str(source),
            destination_uri,
            extra_args=("--content-type", content_type),
        )
        return
    destination = _local_path_from_uri(destination_uri)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _aws_s3_cp_to_stdout(uri: str) -> bytes:
    result = subprocess.run(
        ["aws", "s3", "cp", uri, "-", "--only-show-errors"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise PerCaseRunnerError(
            f"aws s3 cp failed for {uri}: {result.stderr.decode('utf-8').strip()}"
        )
    return result.stdout


def _run_aws_s3_cp(
    source: str,
    destination: str,
    *,
    extra_args: Sequence[str] = (),
) -> None:
    result = subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            source,
            destination,
            "--only-show-errors",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PerCaseRunnerError(
            f"aws s3 cp failed for {source} -> {destination}: {result.stderr.strip()}"
        )


def _join_uri(root: str, object_key: str) -> str:
    _ensure_relative_object_key(object_key)
    if _is_s3_uri(root):
        return f"{root.rstrip('/')}/{object_key}"
    root_path = _local_path_from_uri(root)
    return str(root_path / object_key)


def _object_key_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        return parsed.path.lstrip("/")
    if parsed.scheme == "file":
        return unquote(parsed.path).lstrip("/")
    return uri


def _local_path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme and parsed.scheme != "file":
        raise PerCaseRunnerError(f"unsupported storage URI scheme: {parsed.scheme}")
    return Path(uri)


def _is_s3_uri(uri: str) -> bool:
    return uri.startswith("s3://")


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        f"{json.dumps(dict(record), sort_keys=True)}\n" for record in records
    )
    path.write_text(payload, encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _record_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    value = record.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a list")
    return tuple(
        _mapping(item, f"{field_name} item") for item in cast(Sequence[object], value)
    )


def _optional_record_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    if field_name not in record or record[field_name] is None:
        return ()
    return _record_sequence(record, field_name)


def _str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("string tuple field must be a list")
    strings: list[str] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError("string tuple field must contain non-empty strings")
        strings.append(item)
    return tuple(strings)


def _optional_str_mapping(value: object, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    mapping = cast(Mapping[object, object], value)
    result: dict[str, str] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{key}] must be a non-empty string")
        result[key] = item
    return result


def _optional_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _optional_positive_int(record: Mapping[str, Any], field_name: str) -> int | None:
    if field_name not in record or record[field_name] is None:
        return None
    value = required_int(record, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _optional_float(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: float,
) -> float:
    if field_name not in record or record[field_name] is None:
        return default
    return required_float(record, field_name)


def _optional_manifest_cycle_id(manifest: Mapping[str, Any]) -> str | None:
    return optional_str(manifest, "cycle_id")


def _normalize_sha256(value: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError("sha256 must be a 64-character lowercase hex digest")
    return digest


def _cycle_slug(packet_object: ModelPacketObject) -> str:
    cycle_id = packet_object.cycle_id or "cycle"
    return safe_path_component(_slug(cycle_id), field_name="cycle_id")


def _run_id(
    *,
    cycle_id: str | None,
    case_id: str,
    ablation: str,
    solver_id: str,
) -> str:
    raw = "::".join((cycle_id or "cycle", case_id, ablation, solver_id))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return safe_path_component(
        f"{_slug(case_id)}-{_slug(ablation)}-{_slug(solver_id)}-{digest}",
        field_name="run_id",
    )


def _slug(value: str) -> str:
    slug = _SAFE_SLUG_RE.sub("-", value).strip("-._")
    return slug[:80] if slug else "value"


def _content_type_for_path(path: Path) -> str:
    if path.suffix == ".jsonl":
        return "application/x-jsonlines"
    if path.suffix == ".json":
        return "application/json"
    return "application/octet-stream"


def _safe_error_message(exc: BaseException) -> str:
    message = str(exc)
    return message if len(message) <= 400 else f"{message[:397]}..."


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
