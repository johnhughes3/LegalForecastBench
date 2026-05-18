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
class ReconstructionPlan:
    """Reconstruction handles for one candidate manifest row."""

    candidate_id: str
    case_id: str
    manifest_record_hash: str | None
    documents: tuple[ReconstructionDocumentHandle, ...]

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


def load_reconstruction_plans(path: str | Path) -> tuple[ReconstructionPlan, ...]:
    """Load reconstruction handles from manifest JSONL records."""

    manifest_path = Path(path)
    plans: list[ReconstructionPlan] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = _as_mapping(json.loads(line), f"manifest line {line_number}")
            plans.append(_plan_from_manifest_record(record))
    return tuple(plans)


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
    args = parser.parse_args(argv)
    plans = load_reconstruction_plans(cast(str, args.manifest))
    if args.verify_dir:
        verifications = verify_reconstructed_documents(
            plans, cast(str, args.verify_dir)
        )
        output_path = Path(cast(str, args.output))
        output_path.write_text(
            json.dumps(
                [verification.to_record() for verification in verifications],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return (
            0
            if all(
                verification.status is VerificationStatus.VERIFIED
                for verification in verifications
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


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_sha256(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
