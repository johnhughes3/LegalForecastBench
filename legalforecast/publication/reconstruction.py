"""Manifest-based packet reconstruction and hash verification helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.path_safety import safe_path_component


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class ReconstructionDocumentHandle:
    """Source handle published instead of bulk redistributed document text."""

    source_document_id: str
    source_provider: str
    document_role: str
    sha256: str
    source_url_or_reference: str
    is_mounted_for_model: bool

    def __post_init__(self) -> None:
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_non_empty(self.source_provider, "source_provider")
        _require_non_empty(self.document_role, "document_role")
        _require_sha256(self.sha256, "sha256")
        _require_non_empty(self.source_url_or_reference, "source_url_or_reference")

    @property
    def redistribution_policy(self) -> str:
        return "source_handle_and_hash_only"

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "source_provider": self.source_provider,
            "document_role": self.document_role,
            "sha256": self.sha256,
            "source_url_or_reference": self.source_url_or_reference,
            "is_mounted_for_model": self.is_mounted_for_model,
            "redistribution_policy": self.redistribution_policy,
        }


@dataclass(frozen=True, slots=True)
class PacketRenderHandle:
    """Deterministic model-visible packet render metadata for auditors."""

    packet_sha256: str
    rebuild_command: tuple[str, ...]
    packet_json_path: str | None = None
    prompt_sha256: str | None = None
    prompt_path: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(self.packet_sha256, "packet_sha256")
        if self.prompt_sha256 is not None:
            _require_sha256(self.prompt_sha256, "prompt_sha256")
        if not self.rebuild_command:
            raise ValueError("rebuild_command must not be empty")
        for index, token in enumerate(self.rebuild_command):
            _require_non_empty(token, f"rebuild_command[{index}]")
        if self.packet_json_path is not None:
            _require_safe_relative_path(self.packet_json_path, "packet_json_path")
        if self.prompt_path is not None:
            _require_safe_relative_path(self.prompt_path, "prompt_path")

    @property
    def redistribution_policy(self) -> str:
        return "deterministic_model_visible_packet_rebuild"

    def to_record(self) -> dict[str, Any]:
        return {
            "packet_sha256": self.packet_sha256,
            "packet_json_path": self.packet_json_path,
            "prompt_sha256": self.prompt_sha256,
            "prompt_path": self.prompt_path,
            "rebuild_command": list(self.rebuild_command),
            "redistribution_policy": self.redistribution_policy,
        }


@dataclass(frozen=True, slots=True)
class ReconstructionPlan:
    """Reconstruction handles for one candidate manifest row."""

    candidate_id: str
    case_id: str
    manifest_record_hash: str | None
    documents: tuple[ReconstructionDocumentHandle, ...]
    packet_render: PacketRenderHandle | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if self.manifest_record_hash is not None:
            _require_sha256(self.manifest_record_hash, "manifest_record_hash")
        if not self.documents:
            raise ValueError("reconstruction plans require at least one document")

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "manifest_record_hash": self.manifest_record_hash,
            "documents": [document.to_record() for document in self.documents],
            "packet_render": (
                self.packet_render.to_record()
                if self.packet_render is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class HashVerification:
    """Verification result for one reconstructed local document."""

    source_document_id: str
    expected_sha256: str
    status: VerificationStatus
    path: str | None = None
    actual_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.source_document_id, "source_document_id")
        _require_sha256(self.expected_sha256, "expected_sha256")
        if self.actual_sha256 is not None:
            _require_sha256(self.actual_sha256, "actual_sha256")

    def to_record(self) -> dict[str, Any]:
        return {
            "source_document_id": self.source_document_id,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "status": self.status.value,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class PacketRenderVerification:
    """Verification result for one rebuilt packet-render artifact."""

    candidate_id: str
    artifact: str
    expected_sha256: str
    status: VerificationStatus
    path: str | None = None
    actual_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.artifact, "artifact")
        _require_sha256(self.expected_sha256, "expected_sha256")
        if self.actual_sha256 is not None:
            _require_sha256(self.actual_sha256, "actual_sha256")

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "artifact": self.artifact,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "status": self.status.value,
            "path": self.path,
        }


def load_reconstruction_plans(path: str | Path) -> tuple[ReconstructionPlan, ...]:
    """Load reconstruction handles from manifest JSONL records."""

    manifest_path = Path(path)
    text = manifest_path.read_text(encoding="utf-8")
    try:
        payload: object = json.loads(text)
    except json.JSONDecodeError:
        return _load_reconstruction_plans_jsonl(text)
    return tuple(
        _plan_from_manifest_record(record)
        for record in _reconstruction_records_from_payload(payload)
    )


def _load_reconstruction_plans_jsonl(text: str) -> tuple[ReconstructionPlan, ...]:
    plans: list[ReconstructionPlan] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        record = _as_mapping(json.loads(line), f"manifest line {line_number}")
        plans.append(_plan_from_manifest_record(record))
    return tuple(plans)


def _reconstruction_records_from_payload(
    payload: object,
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(payload, Mapping):
        manifest = cast(Mapping[str, Any], payload)
        candidates = manifest.get("candidates")
        if candidates is None:
            return (_as_mapping(manifest, "manifest"),)
        return tuple(
            _as_mapping(candidate, "candidate")
            for candidate in _as_sequence(candidates, "candidates")
        )
    return tuple(
        _as_mapping(record, "manifest entry")
        for record in _as_sequence(payload, "manifest")
    )


def verify_reconstructed_documents(
    plans: Sequence[ReconstructionPlan],
    document_root: str | Path,
) -> tuple[HashVerification, ...]:
    """Verify local reconstructed documents against manifest hashes."""

    root = Path(document_root)
    verifications: list[HashVerification] = []
    seen_document_ids: set[str] = set()
    for plan in plans:
        for document in plan.documents:
            if document.source_document_id in seen_document_ids:
                continue
            seen_document_ids.add(document.source_document_id)
            path = _find_reconstructed_file(root, document.source_document_id)
            if path is None:
                verifications.append(
                    HashVerification(
                        source_document_id=document.source_document_id,
                        expected_sha256=document.sha256,
                        status=VerificationStatus.MISSING,
                    )
                )
                continue
            actual = _sha256_file(path)
            verifications.append(
                HashVerification(
                    source_document_id=document.source_document_id,
                    expected_sha256=document.sha256,
                    actual_sha256=actual,
                    status=(
                        VerificationStatus.VERIFIED
                        if actual == document.sha256
                        else VerificationStatus.MISMATCH
                    ),
                    path=str(path),
                )
            )
    return tuple(verifications)


def verify_reconstructed_packet_renders(
    plans: Sequence[ReconstructionPlan],
    render_root: str | Path,
) -> tuple[PacketRenderVerification, ...]:
    """Verify rebuilt model-visible packet renders against published hashes."""

    root = Path(render_root)
    verifications: list[PacketRenderVerification] = []
    for plan in plans:
        if plan.packet_render is None:
            continue
        packet_path = _find_packet_render_file(
            root,
            candidate_id=plan.candidate_id,
            explicit_path=plan.packet_render.packet_json_path,
            default_suffixes=(".packet.json", ".json"),
        )
        verifications.append(
            _packet_render_verification(
                candidate_id=plan.candidate_id,
                artifact="model_visible_packet",
                expected_sha256=plan.packet_render.packet_sha256,
                path=packet_path,
            )
        )
        if plan.packet_render.prompt_sha256 is not None:
            prompt_path = _find_packet_render_file(
                root,
                candidate_id=plan.candidate_id,
                explicit_path=plan.packet_render.prompt_path,
                default_suffixes=(".prompt.md", ".prompt.txt", ".prompt.json"),
            )
            verifications.append(
                _packet_render_verification(
                    candidate_id=plan.candidate_id,
                    artifact="model_visible_prompt",
                    expected_sha256=plan.packet_render.prompt_sha256,
                    path=prompt_path,
                )
            )
    return tuple(verifications)


def write_reconstruction_plan(
    plans: Sequence[ReconstructionPlan],
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.write_text(
        json.dumps([plan.to_record() for plan in plans], indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reconstruct_packets",
        description=(
            "Build source-handle reconstruction plans from manifest JSONL and "
            "optionally verify local reconstructed documents by SHA-256."
        ),
    )
    parser.add_argument("--manifest", required=True, help="Manifest JSONL path.")
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON reconstruction plan or verification report.",
    )
    parser.add_argument(
        "--verify-dir",
        help=(
            "Directory containing reconstructed files named by source_document_id "
            "or source_document_id plus .pdf/.txt/.json."
        ),
    )
    parser.add_argument(
        "--verify-packet-render-dir",
        help=(
            "Directory containing rebuilt model-visible packet/prompt files "
            "referenced by packet_render paths in the reconstruction plan."
        ),
    )
    args = parser.parse_args(argv)
    plans = load_reconstruction_plans(cast(str, args.manifest))
    if args.verify_dir or args.verify_packet_render_dir:
        document_verifications = (
            verify_reconstructed_documents(plans, cast(str, args.verify_dir))
            if args.verify_dir
            else ()
        )
        packet_render_verifications = (
            verify_reconstructed_packet_renders(
                plans,
                cast(str, args.verify_packet_render_dir),
            )
            if args.verify_packet_render_dir
            else ()
        )
        output_path = Path(cast(str, args.output))
        payload: object = (
            {
                "documents": [
                    verification.to_record() for verification in document_verifications
                ],
                "packet_renders": [
                    verification.to_record()
                    for verification in packet_render_verifications
                ],
            }
            if args.verify_dir and args.verify_packet_render_dir
            else [
                verification.to_record()
                for verification in (
                    document_verifications or packet_render_verifications
                )
            ]
        )
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        all_verifications = (*document_verifications, *packet_render_verifications)
        return (
            0
            if all(
                verification.status is VerificationStatus.VERIFIED
                for verification in all_verifications
            )
            else 1
        )

    write_reconstruction_plan(plans, cast(str, args.output))
    return 0


def _plan_from_manifest_record(record: Mapping[str, Any]) -> ReconstructionPlan:
    documents = tuple(
        _document_from_record(_as_mapping(document, "document"))
        for document in _as_sequence(record.get("documents"), "documents")
    )
    return ReconstructionPlan(
        candidate_id=_required_str(record, "candidate_id"),
        case_id=_required_str(record, "case_id"),
        manifest_record_hash=_optional_str(record.get("manifest_record_hash")),
        documents=documents,
        packet_render=_packet_render_from_record(record),
    )


def _document_from_record(
    record: Mapping[str, Any],
) -> ReconstructionDocumentHandle:
    return ReconstructionDocumentHandle(
        source_document_id=_required_str(record, "source_document_id"),
        source_provider=_required_str(record, "source_provider"),
        document_role=_required_str(record, "document_role"),
        sha256=_required_str(record, "sha256"),
        source_url_or_reference=_required_str(record, "source_url_or_reference"),
        is_mounted_for_model=_required_bool(record, "is_mounted_for_model"),
    )


def _find_reconstructed_file(root: Path, source_document_id: str) -> Path | None:
    safe_document_id = safe_path_component(
        source_document_id,
        field_name="source_document_id",
    )
    resolved_root = root.resolve()
    for suffix in ("", ".pdf", ".txt", ".json"):
        candidate = (resolved_root / f"{safe_document_id}{suffix}").resolve()
        if not candidate.is_relative_to(resolved_root):
            raise ValueError("reconstructed document path escaped verify directory")
        if candidate.is_file():
            return candidate
    return None


def _find_packet_render_file(
    root: Path,
    *,
    candidate_id: str,
    explicit_path: str | None,
    default_suffixes: tuple[str, ...],
) -> Path | None:
    resolved_root = root.resolve()
    if explicit_path is not None:
        candidate = _resolve_under_root(resolved_root, explicit_path)
        return candidate if candidate.is_file() else None
    safe_candidate_id = safe_path_component(candidate_id, field_name="candidate_id")
    for suffix in default_suffixes:
        candidate = (resolved_root / f"{safe_candidate_id}{suffix}").resolve()
        if not candidate.is_relative_to(resolved_root):
            raise ValueError("packet render path escaped verify directory")
        if candidate.is_file():
            return candidate
    return None


def _packet_render_verification(
    *,
    candidate_id: str,
    artifact: str,
    expected_sha256: str,
    path: Path | None,
) -> PacketRenderVerification:
    if path is None:
        return PacketRenderVerification(
            candidate_id=candidate_id,
            artifact=artifact,
            expected_sha256=expected_sha256,
            status=VerificationStatus.MISSING,
        )
    actual = _sha256_file(path)
    return PacketRenderVerification(
        candidate_id=candidate_id,
        artifact=artifact,
        expected_sha256=expected_sha256,
        actual_sha256=actual,
        status=(
            VerificationStatus.VERIFIED
            if actual == expected_sha256
            else VerificationStatus.MISMATCH
        ),
        path=str(path),
    )


def _packet_render_from_record(
    record: Mapping[str, Any],
) -> PacketRenderHandle | None:
    value = record.get("packet_render")
    if value is None:
        return None
    packet_render = _as_mapping(value, "packet_render")
    return PacketRenderHandle(
        packet_sha256=_required_sha256_value(packet_render, "packet_sha256"),
        packet_json_path=_optional_str(packet_render.get("packet_json_path")),
        prompt_sha256=_optional_sha256_value(packet_render.get("prompt_sha256")),
        prompt_path=_optional_str(packet_render.get("prompt_path")),
        rebuild_command=tuple(
            _required_str_value(token, f"rebuild_command[{index}]")
            for index, token in enumerate(
                _as_sequence(packet_render.get("rebuild_command"), "rebuild_command")
            )
        ),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _as_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be an array")
    return cast(Sequence[Any], value)


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} is required")
    _require_non_empty(value, field_name)
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional string value must be a string")
    _require_non_empty(value, "optional string")
    return value


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} is required")
    return value


def _required_str_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} is required")
    _require_non_empty(value, field_name)
    return value


def _required_sha256_value(record: Mapping[str, Any], field_name: str) -> str:
    return _normalize_sha256(_required_str(record, field_name), field_name)


def _optional_sha256_value(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_sha256(
        _required_str_value(value, "optional sha256"),
        "optional sha256",
    )


def _normalize_sha256(value: str, field_name: str) -> str:
    digest = value.removeprefix("sha256:")
    _require_sha256(digest, field_name)
    return digest


def _resolve_under_root(root: Path, relative_path: str) -> Path:
    _require_safe_relative_path(relative_path, "relative_path")
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("packet render path escaped verify directory")
    return candidate


def _require_safe_relative_path(value: str, field_name: str) -> None:
    _require_non_empty(value, field_name)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a safe relative path")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_sha256(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
