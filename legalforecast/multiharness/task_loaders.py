"""Task-index loaders for LegalForecastBench and Harvey LAB suites."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import read_json_object, read_jsonl_objects
from legalforecast.evals.inspect_task import build_inspect_samples
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketDocument,
)
from legalforecast.ingestion.provenance import DocumentRole, sha256_text
from legalforecast.multiharness.spec import ArtifactRecord, CanonicalTask, TaskIndex
from legalforecast.multiharness.validation import (
    require_mapping,
    require_sequence,
    require_str,
    validate_safe_relative_path,
    validate_unique_ids,
)
from legalforecast.unitization.schemas import (
    ChallengeScope,
    DefendantGrouping,
    PredictionUnit,
    SourceCitation,
)

DEFAULT_LFB_SUITE_VERSION = "legalforecast-mtd-v1"
DEFAULT_LAB_SUITE_VERSION = "harvey-lab"


class LfbTaskLoader:
    """Load LegalForecastBench model-packet rows into canonical tasks."""

    def __init__(self, *, suite_version: str = DEFAULT_LFB_SUITE_VERSION) -> None:
        if not suite_version.strip():
            raise ValueError("suite_version must be non-empty")
        self.suite_version = suite_version

    def load_packet_jsonl(
        self,
        path: Path,
        *,
        index_id: str = "legalforecast-mtd",
        selection_namespace: str = "legalforecast_mtd",
    ) -> TaskIndex:
        records = read_jsonl_objects(
            path,
            error_factory=ValueError,
            missing_message=lambda item: f"LFB packet JSONL does not exist: {item}",
            non_object_message=lambda item, line: (
                f"LFB packet JSONL row {line} in {item} must be an object"
            ),
        )
        return self.from_records(
            records,
            index_id=index_id,
            selection_namespace=selection_namespace,
        )

    def from_records(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        index_id: str = "legalforecast-mtd",
        selection_namespace: str = "legalforecast_mtd",
    ) -> TaskIndex:
        tasks = tuple(self.task_from_record(record) for record in records)
        if not tasks:
            raise ValueError("at least one LFB packet row is required")
        validate_unique_ids((task.task_id for task in tasks), "tasks")
        return TaskIndex(
            index_id=index_id,
            selection_namespace=selection_namespace,
            tasks=tasks,
            index_sha256=_record_sha256([task.to_record() for task in tasks]),
        )

    def task_from_record(self, record: Mapping[str, Any]) -> CanonicalTask:
        packet_record = _extract_packet_record(record)
        packet = _model_packet_from_record(packet_record)
        sample = build_inspect_samples((packet,))[0]
        packet_sha256 = _record_sha256(packet_record)
        prompt_sha256 = sha256_text(sample.prompt)
        required_unit_ids = tuple(
            str(unit_record["unit_id"])
            for unit_record in require_sequence(packet_record, "prediction_units")
            if bool(cast(Mapping[str, Any], unit_record).get("should_score", True))
        )
        document_hashes = _document_hashes(packet_record)
        metadata = {
            "suite": "legalforecast_mtd",
            "candidate_id": packet.candidate_id,
            "case_id": packet.case_id,
            "court": packet.court,
            "docket_number": packet.docket_number,
            "ablation": packet.ablation.value,
            "related_family_id": packet.related_family_id,
            "mdl_family_id": packet.mdl_family_id,
            "required_unit_ids": list(required_unit_ids),
            "prompt_sha256": prompt_sha256,
            "packet_sha256": packet_sha256,
            "document_hashes": document_hashes,
            "document_count": len(packet.documents),
            "excluded_document_ids": list(packet.excluded_document_ids),
            "missing_optional_sections": list(packet.missing_optional_sections),
        }
        return CanonicalTask(
            task_id=f"lfb:{packet.candidate_id}:{packet.ablation.value}",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version=self.suite_version,
            source_id=packet.candidate_id,
            task_sha256=packet_sha256,
            metadata=metadata,
        )


class HarveyLabTaskLoader:
    """Load Harvey LAB task directories into canonical tasks."""

    def __init__(
        self,
        lab_root: Path,
        *,
        suite_version: str = DEFAULT_LAB_SUITE_VERSION,
    ) -> None:
        if not suite_version.strip():
            raise ValueError("suite_version must be non-empty")
        self.lab_root = lab_root
        self.suite_version = suite_version

    def load_task_index(
        self,
        *,
        index_id: str = "harvey-lab",
        selection_namespace: str = "harvey_lab",
    ) -> TaskIndex:
        tasks_root = self.lab_root / "tasks"
        if not tasks_root.is_dir():
            raise ValueError(f"Harvey LAB tasks directory does not exist: {tasks_root}")
        task_json_paths = tuple(sorted(tasks_root.rglob("task.json")))
        if not task_json_paths:
            raise ValueError(
                f"Harvey LAB tasks directory has no task.json files: {tasks_root}"
            )
        tasks = tuple(self.load_task_directory(path.parent) for path in task_json_paths)
        validate_unique_ids((task.task_id for task in tasks), "tasks")
        return TaskIndex(
            index_id=index_id,
            selection_namespace=selection_namespace,
            tasks=tasks,
            index_sha256=_record_sha256([task.to_record() for task in tasks]),
        )

    def load_task_directory(self, task_dir: Path) -> CanonicalTask:
        task_json_path = task_dir / "task.json"
        documents_dir = task_dir / "documents"
        if not task_json_path.is_file():
            raise ValueError(f"Harvey LAB task is missing task.json: {task_json_path}")
        if not documents_dir.is_dir():
            raise ValueError(f"Harvey LAB task is missing documents/: {documents_dir}")
        document_paths = tuple(
            sorted(path for path in documents_dir.rglob("*") if path.is_file())
        )
        if not document_paths:
            raise ValueError(f"Harvey LAB task documents/ is empty: {documents_dir}")

        task_record = read_json_object(
            task_json_path,
            error_factory=ValueError,
            missing_message=lambda item: f"Harvey LAB task JSON does not exist: {item}",
            non_object_message=lambda item: (
                f"Harvey LAB task JSON must be an object: {item}"
            ),
        )
        relative_task_dir = _relative_posix(task_dir, self.lab_root / "tasks")
        lab_task_id = _task_id_from_lab_record(task_record, relative_task_dir)
        task_json_sha256 = _file_sha256(task_json_path)
        document_artifacts = tuple(
            _artifact_for_lab_file(
                path,
                artifact_id=f"document:{_relative_posix(path, task_dir)}",
                lab_root=self.lab_root,
            )
            for path in document_paths
        )
        document_hashes = {
            _relative_posix(path, documents_dir): _file_sha256(path)
            for path in document_paths
        }
        module, practice_area = _infer_lab_taxonomy(task_record, relative_task_dir)
        metadata = {
            "suite": "harvey_lab",
            "lab_task_id": lab_task_id,
            "lab_task_path": relative_task_dir,
            "lab_commit": self._lab_commit() or "unknown",
            "module": module,
            "practice_area": practice_area,
            "task_json_sha256": task_json_sha256,
            "document_hashes": document_hashes,
            "document_count": len(document_paths),
        }
        task_sha256 = _record_sha256(
            {
                "task_json_sha256": task_json_sha256,
                "document_hashes": document_hashes,
            }
        )
        task_json_artifact = _artifact_for_lab_file(
            task_json_path,
            artifact_id="task_json",
            lab_root=self.lab_root,
        )
        return CanonicalTask(
            task_id=f"harvey_lab:{relative_task_dir}",
            family="harvey_lab",
            scoring_mode="lab_native",
            suite_version=self.suite_version,
            source_id=lab_task_id,
            task_sha256=task_sha256,
            metadata=metadata,
            artifacts=(task_json_artifact, *document_artifacts),
        )

    def _lab_commit(self) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(self.lab_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        if result.returncode != 0 or not commit:
            return None
        return commit


def _extract_packet_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = record.get("model_packet", record.get("packet"))
    if nested is None:
        return record
    if not isinstance(nested, Mapping):
        raise ValueError("model_packet must be an object")
    return cast(Mapping[str, Any], nested)


def _model_packet_from_record(record: Mapping[str, Any]) -> ModelPacket:
    documents = tuple(
        _packet_document_from_record(item)
        for item in require_sequence(record, "documents")
    )
    units = tuple(
        _prediction_unit_from_record(item, documents)
        for item in require_sequence(record, "prediction_units")
    )
    metadata = _string_mapping(require_mapping(record, "metadata"), "metadata")
    return ModelPacket(
        candidate_id=require_str(record, "candidate_id"),
        case_id=require_str(record, "case_id"),
        court=require_str(record, "court"),
        docket_number=require_str(record, "docket_number"),
        ablation=PacketAblation(require_str(record, "ablation")),
        metadata=metadata,
        documents=documents,
        prediction_units=units,
        excluded_document_ids=_string_tuple(
            require_sequence(record, "excluded_document_ids"),
            "excluded_document_ids",
        ),
        missing_optional_sections=_string_tuple(
            require_sequence(record, "missing_optional_sections"),
            "missing_optional_sections",
        ),
        related_family_id=_optional_non_empty_str(record, "related_family_id"),
        mdl_family_id=_optional_non_empty_str(record, "mdl_family_id"),
    )


def _packet_document_from_record(value: Any) -> PacketDocument:
    if not isinstance(value, Mapping):
        raise ValueError("documents entries must be objects")
    record = cast(Mapping[str, Any], value)
    return PacketDocument(
        source_document_id=require_str(record, "source_document_id"),
        document_role=DocumentRole(require_str(record, "document_role")),
        docket_entry_number=_optional_positive_int(record, "docket_entry_number"),
        source_provider=require_str(record, "source_provider"),
        source_url_or_reference=require_str(record, "source_url_or_reference"),
        source_sha256=require_str(record, "source_sha256"),
        text=require_str(record, "text"),
        text_sha256=require_str(record, "text_sha256"),
        quality_flags=_string_tuple(
            require_sequence(record, "quality_flags"),
            "quality_flags",
        ),
        extraction_method=_optional_non_empty_str(record, "extraction_method"),
        packet_section=_optional_non_empty_str(record, "packet_section"),
    )


def _prediction_unit_from_record(
    value: Any,
    documents: Sequence[PacketDocument],
) -> PredictionUnit:
    if not isinstance(value, Mapping):
        raise ValueError("prediction_units entries must be objects")
    record = cast(Mapping[str, Any], value)
    challenge_scope = _optional_public_packet_challenge_scope(record)
    citation_document_id = documents[0].source_document_id if documents else "metadata"
    return PredictionUnit(
        unit_id=require_str(record, "unit_id"),
        count=require_str(record, "count"),
        claim_name=require_str(record, "claim_name"),
        defendant_group=require_str(record, "defendant_group"),
        challenged_by_motion=_optional_public_packet_bool(
            record,
            "challenged_by_motion",
            default=True,
        ),
        challenge_scope=challenge_scope,
        unit_confidence=1.0,
        source_citations=(SourceCitation(document_id=citation_document_id),),
        grouping=DefendantGrouping.INDIVIDUAL,
        separable_subclaim=(
            "serialized model-visible subclaim"
            if challenge_scope is ChallengeScope.SEPARABLE_SUBCLAIM
            else None
        ),
        uncertainty_notes=(
            "serialized model-visible unit marked unclear"
            if challenge_scope is ChallengeScope.UNCLEAR
            else None
        ),
    )


def _document_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    documents = require_sequence(record, "documents")
    hashes: dict[str, str] = {}
    for value in documents:
        if not isinstance(value, Mapping):
            raise ValueError("documents entries must be objects")
        document = cast(Mapping[str, Any], value)
        hashes[require_str(document, "source_document_id")] = require_str(
            document,
            "source_sha256",
        )
    return hashes


def _artifact_for_lab_file(
    path: Path,
    *,
    artifact_id: str,
    lab_root: Path,
) -> ArtifactRecord:
    relative_path = _relative_posix(path, lab_root)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return ArtifactRecord(
        artifact_id=artifact_id,
        path=validate_safe_relative_path(relative_path, "path"),
        sha256=_file_sha256(path),
        media_type=media_type,
        public=False,
        size_bytes=path.stat().st_size,
    )


def _task_id_from_lab_record(
    record: Mapping[str, Any],
    relative_task_dir: str,
) -> str:
    for field_name in ("id", "task_id", "name", "title"):
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return relative_task_dir


def _infer_lab_taxonomy(
    record: Mapping[str, Any],
    relative_task_dir: str,
) -> tuple[str, str]:
    module = _nested_str(record, ("metadata", "module")) or _top_level_str(
        record,
        ("module", "category"),
    )
    practice_area = _nested_str(
        record,
        ("metadata", "practice_area"),
    ) or _top_level_str(record, ("practice_area", "practiceArea", "area"))
    parts = tuple(part for part in relative_task_dir.split("/") if part)
    return (
        module or (parts[0] if parts else "unknown"),
        practice_area or (parts[1] if len(parts) > 1 else "unknown"),
    )


def _nested_str(record: Mapping[str, Any], path: tuple[str, str]) -> str | None:
    parent = record.get(path[0])
    if not isinstance(parent, Mapping):
        return None
    value = cast(Mapping[str, Any], parent).get(path[1])
    return value if isinstance(value, str) and value.strip() else None


def _top_level_str(record: Mapping[str, Any], field_names: Sequence[str]) -> str | None:
    for field_name in field_names:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _record_sha256(record: Any) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_posix(path: Path, root: Path) -> str:
    return validate_safe_relative_path(path.relative_to(root).as_posix(), "path")


def _string_mapping(record: Mapping[str, Any], field_name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in record.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}.{key} must be a non-empty string")
        result[key] = value
    return result


def _string_tuple(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    result: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        result.append(value)
    return tuple(result)


def _optional_non_empty_str(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_positive_int(record: Mapping[str, Any], field_name: str) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _optional_public_packet_bool(
    record: Mapping[str, Any],
    field_name: str,
    *,
    default: bool,
) -> bool:
    if field_name not in record:
        return default
    return _required_bool(record, field_name)


def _optional_public_packet_challenge_scope(
    record: Mapping[str, Any],
) -> ChallengeScope:
    if "challenge_scope" not in record:
        return ChallengeScope.ENTIRE_CLAIM
    return ChallengeScope(require_str(record, "challenge_scope"))
