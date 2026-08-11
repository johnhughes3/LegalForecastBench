"""Closed, non-authoritative input format for successor rerun planning."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    SUCCESSOR_RERUN_PROPOSAL_V1,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)

PROPOSAL_SCHEMA_VERSION = SUCCESSOR_RERUN_PROPOSAL_V1.value


class SuccessorRerunProposalError(ValueError):
    """Raised when proposed inputs are missing, unsafe, or inconsistent."""


@dataclass(frozen=True, slots=True)
class DocumentInput:
    """Exact source-byte identity for one selected document."""

    candidate_id: str
    source_document_id: str
    sha256: str
    byte_count: int

    @property
    def key(self) -> tuple[str, str]:
        return self.candidate_id, self.source_document_id


@dataclass(frozen=True, slots=True)
class RerunInputs:
    """Comparison-relevant commitments for one Stage A input set."""

    cycle_id: str
    selection_records: tuple[Mapping[str, Any], ...]
    documents: tuple[DocumentInput, ...]
    parser_revision: str
    provider_attempt_namespace: str | None
    model_key: str
    model_registry_sha256: str
    policy_sha256: str
    parser_output_sha256_by_document: Mapping[tuple[str, str], str]


@dataclass(frozen=True, slots=True)
class SuccessorProposal:
    """Verified bytes of a non-authoritative proposed input set."""

    inputs: RerunInputs
    selection_path: Path
    download_manifest_path: Path
    model_registry_path: Path
    policy_path: Path
    successor_output_root: Path
    next_commands: tuple[Mapping[str, object], ...]
    proposal_sha256: str


def load_successor_proposal(path: Path) -> SuccessorProposal:
    """Load and exact-byte-check one canonical, non-authoritative proposal."""

    payload = _read_regular(path, label="successor proposal")
    raw = _json_object(payload, label="successor proposal")
    expected_fields = {
        "schema_version",
        "cycle_id",
        "selection_path",
        "selection_sha256",
        "download_manifest_path",
        "download_manifest_sha256",
        "parser_revision",
        "provider_attempt_namespace",
        "model_registry_path",
        "model_registry_sha256",
        "model_key",
        "policy_path",
        "policy_sha256",
        "successor_output_root",
        "next_commands",
        "non_authoritative",
    }
    if (
        set(raw) != expected_fields
        or raw.get("schema_version") != PROPOSAL_SCHEMA_VERSION
        or raw.get("non_authoritative") is not True
    ):
        raise SuccessorRerunProposalError(
            "successor proposal fields, schema, or advisory marker differ"
        )
    if ARTIFACT_CANONICAL_JSON_V1.encode(raw) != payload:
        raise SuccessorRerunProposalError(
            "successor proposal must use canonical artifact JSON bytes"
        )

    selection_path = _absolute_path(raw, "selection_path")
    downloads_path = _absolute_path(raw, "download_manifest_path")
    registry_path = _absolute_path(raw, "model_registry_path")
    policy_path = _absolute_path(raw, "policy_path")
    successor_root = _absolute_path(raw, "successor_output_root")
    selection_bytes = _committed_bytes(
        selection_path, raw, "selection_sha256", label="proposed selection"
    )
    download_bytes = _committed_bytes(
        downloads_path,
        raw,
        "download_manifest_sha256",
        label="proposed download manifest",
    )
    _committed_bytes(
        registry_path,
        raw,
        "model_registry_sha256",
        label="proposed model registry",
    )
    _committed_bytes(policy_path, raw, "policy_sha256", label="proposed policy")
    selection_records = _jsonl(selection_bytes, label="proposed selection")
    download_records = _jsonl(download_bytes, label="proposed download manifest")
    documents = tuple(
        sorted(
            (_document_from_download(record) for record in download_records),
            key=lambda item: item.key,
        )
    )
    _require_unique_documents(documents, label="proposed")
    _verify_proposed_document_bytes(download_records, documents)
    inputs = RerunInputs(
        cycle_id=_text(raw, "cycle_id"),
        selection_records=selection_records,
        documents=documents,
        parser_revision=_text(raw, "parser_revision"),
        provider_attempt_namespace=_optional_text(raw, "provider_attempt_namespace"),
        model_key=_text(raw, "model_key"),
        model_registry_sha256=_sha256(raw, "model_registry_sha256"),
        policy_sha256=_sha256(raw, "policy_sha256"),
        parser_output_sha256_by_document={},
    )
    return SuccessorProposal(
        inputs=inputs,
        selection_path=selection_path,
        download_manifest_path=downloads_path,
        model_registry_path=registry_path,
        policy_path=policy_path,
        successor_output_root=successor_root,
        next_commands=_proposal_commands(raw.get("next_commands")),
        proposal_sha256=hashlib.sha256(payload).hexdigest(),
    )


def current_documents_from_parser_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[DocumentInput, ...]:
    """Project exact source identities from authenticated successful parser rows."""

    documents: list[DocumentInput] = []
    revisions: set[str] = set()
    for record in records:
        if record.get("status") != "succeeded":
            raise SuccessorRerunProposalError(
                "authenticated parser lineage contains a non-successful row"
            )
        config = record.get("parser_config")
        if not isinstance(config, Mapping):
            raise SuccessorRerunProposalError("parser row lacks parser_config")
        revision = cast(Mapping[str, object], config).get("parser_revision")
        if not isinstance(revision, str) or not revision:
            raise SuccessorRerunProposalError("parser row lacks parser revision")
        revisions.add(revision)
        documents.append(
            DocumentInput(
                candidate_id=_text(record, "candidate_id"),
                source_document_id=_text(record, "source_document_id"),
                sha256=_sha256(record, "source_sha256"),
                byte_count=_nonnegative_int(record, "source_byte_count"),
            )
        )
    if len(revisions) != 1:
        raise SuccessorRerunProposalError(
            f"authenticated parser revision is ambiguous ({len(revisions)} found)"
        )
    result = tuple(sorted(documents, key=lambda item: item.key))
    _require_unique_documents(result, label="authenticated parser")
    return result


def parser_revision_from_records(records: Sequence[Mapping[str, Any]]) -> str:
    current_documents_from_parser_records(records)
    config = records[0].get("parser_config")
    assert isinstance(config, Mapping)
    return cast(str, config["parser_revision"])


def parser_output_sha256_from_records(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], str]:
    """Project Markdown byte commitments from authenticated parser rows."""

    result: dict[tuple[str, str], str] = {}
    for record in records:
        key = (_text(record, "candidate_id"), _text(record, "source_document_id"))
        extracted = record.get("extracted_text")
        if not isinstance(extracted, Mapping):
            raise SuccessorRerunProposalError(
                f"authenticated parser row lacks extracted text: {_key_text(key)}"
            )
        digest = _sha256(cast(Mapping[str, object], extracted), "text_sha256")
        if key in result:
            raise SuccessorRerunProposalError(
                f"authenticated parser output is ambiguous: {_key_text(key)}"
            )
        result[key] = digest
    return result


def _proposal_commands(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise SuccessorRerunProposalError(
            "successor proposal next_commands are invalid"
        )
    allowed_stages = {
        "selection",
        "plan-parse-documents",
        "parse-documents",
        "llm-unitize",
    }
    commands: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for raw in cast(list[object], value):
        if not isinstance(raw, Mapping):
            raise SuccessorRerunProposalError(
                "successor proposal next command fields differ"
            )
        command = cast(Mapping[str, object], raw)
        if set(command) != {
            "stage",
            "argv",
            "execution_authority",
            "requires_separate_authorization",
        }:
            raise SuccessorRerunProposalError(
                "successor proposal next command fields differ"
            )
        stage = _text(command, "stage")
        argv = command.get("argv")
        arguments = cast(list[object], argv) if isinstance(argv, list) else []
        if (
            stage not in allowed_stages
            or stage in seen
            or not arguments
            or any(not isinstance(item, str) or not item for item in arguments)
            or command.get("execution_authority") is not False
            or not isinstance(command.get("requires_separate_authorization"), bool)
        ):
            raise SuccessorRerunProposalError(
                "successor proposal next command is invalid or authoritative"
            )
        typed = cast(list[str], arguments)
        if typed[:4] != ["uv", "run", "legalforecast", "acquisition"]:
            raise SuccessorRerunProposalError(
                "successor proposal next command is not an acquisition CLI invocation"
            )
        if any(item in {"--api-key", "--credential", "--token"} for item in typed):
            raise SuccessorRerunProposalError(
                "successor proposal next command contains a credential option"
            )
        seen.add(stage)
        commands.append(dict(command))
    return tuple(commands)


def _document_from_download(record: Mapping[str, Any]) -> DocumentInput:
    return DocumentInput(
        candidate_id=_text(record, "candidate_id"),
        source_document_id=_text(record, "source_document_id"),
        sha256=_sha256(record, "sha256"),
        byte_count=_nonnegative_int(record, "byte_count"),
    )


def _verify_proposed_document_bytes(
    records: Sequence[Mapping[str, Any]], documents: Sequence[DocumentInput]
) -> None:
    by_key = {document.key: document for document in documents}
    for record in records:
        key = (_text(record, "candidate_id"), _text(record, "source_document_id"))
        raw_path = record.get("local_path")
        if not isinstance(raw_path, str) or not raw_path:
            raise SuccessorRerunProposalError("proposed document lacks local_path")
        path = Path(raw_path)
        if not path.is_absolute():
            raise SuccessorRerunProposalError(
                "proposed document local_path must be absolute"
            )
        payload = _read_regular(path, label=f"proposed document {_key_text(key)}")
        document = by_key[key]
        if (
            hashlib.sha256(payload).hexdigest() != document.sha256
            or len(payload) != document.byte_count
        ):
            raise SuccessorRerunProposalError(
                f"proposed document bytes differ: {_key_text(key)}"
            )


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise SuccessorRerunProposalError(
            f"{label} is unavailable or unsafe"
        ) from exc


def _committed_bytes(
    path: Path, record: Mapping[str, object], field: str, *, label: str
) -> bytes:
    payload = _read_regular(path, label=label)
    if hashlib.sha256(payload).hexdigest() != _sha256(record, field):
        raise SuccessorRerunProposalError(f"{label} bytes differ from proposal")
    return payload


def _json_object(payload: bytes, *, label: str) -> Mapping[str, object]:
    try:
        raw = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SuccessorRerunProposalError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(raw, Mapping):
        raise SuccessorRerunProposalError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], raw)


def _jsonl(payload: bytes, *, label: str) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise SuccessorRerunProposalError(f"{label} is not UTF-8") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SuccessorRerunProposalError(
                f"{label} line {line_number} is not JSON"
            ) from exc
        if not isinstance(raw, Mapping):
            raise SuccessorRerunProposalError(
                f"{label} line {line_number} must be an object"
            )
        records.append(cast(Mapping[str, Any], raw))
    if not records:
        raise SuccessorRerunProposalError(f"{label} is empty")
    return tuple(records)


def _absolute_path(record: Mapping[str, object], field: str) -> Path:
    path = Path(_text(record, field))
    if not path.is_absolute() or ".." in path.parts:
        raise SuccessorRerunProposalError(
            f"successor proposal {field} is not absolute"
        )
    return path


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise SuccessorRerunProposalError(f"{field} must be non-empty text")
    return value


def _optional_text(record: Mapping[str, object], field: str) -> str | None:
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SuccessorRerunProposalError(f"{field} must be non-empty text or null")
    return value


def _sha256(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(item not in "0123456789abcdef" for item in value):
        raise SuccessorRerunProposalError(f"{field} must be a lowercase SHA-256")
    return value


def _nonnegative_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SuccessorRerunProposalError(f"{field} must be a non-negative integer")
    return value


def _require_unique_documents(
    documents: Sequence[DocumentInput], *, label: str
) -> None:
    keys = [document.key for document in documents]
    if len(keys) != len(set(keys)):
        raise SuccessorRerunProposalError(f"{label} documents are ambiguous")


def _key_text(key: tuple[str, str]) -> str:
    return f"{key[0]}/{key[1]}"
