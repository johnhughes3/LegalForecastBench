"""Closed, non-authoritative input format for successor rerun planning.

The proposal is only a collection of exact paths and byte commitments.  It
does not carry commands or claim that those bytes are authentic.  The CLI
replays the existing materialization and selection verifiers, then calls
``bind_verified_successor_proposal`` with their already-authenticated records.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
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
    """Exact source-byte and selection-semantic identity for one document."""

    candidate_id: str
    case_id: str
    source_document_id: str
    document_role: str
    model_visible: bool
    sha256: str
    byte_count: int

    @property
    def key(self) -> tuple[str, str]:
        return self.candidate_id, self.source_document_id

    @property
    def source_key(self) -> tuple[str, str, str, int]:
        return (
            self.candidate_id,
            self.source_document_id,
            self.sha256,
            self.byte_count,
        )


@dataclass(frozen=True, slots=True)
class ParserReuseEvidence:
    """Sealed identity produced by the complete live-Mistral reuse verifier."""

    source_key: tuple[str, str, str, int]
    markdown_path: str
    metadata_path: str
    record_sha256: str
    markdown_sha256: str
    metadata_sha256: str
    output_markdown_sha256: str


@dataclass(frozen=True, slots=True)
class ProviderReuseEvidence:
    """One settled attempt returned by authenticated run-card replay."""

    candidate_id: str
    stage: str
    logical_call_key: str
    attempt_ordinal: int
    provider: str
    account: str
    prompt_text: str
    prompt_sha256: str
    model_key: str
    model_registry_sha256: str
    raw_response_json: str
    normalized_response_json: str
    reconstructed_result_json: str
    attempt_record_sha256: str


@dataclass(frozen=True, slots=True)
class RerunInputs:
    """Comparison-relevant commitments for one Stage A input set."""

    cycle_id: str
    selection_records: tuple[Mapping[str, Any], ...]
    documents: tuple[DocumentInput, ...]
    provider_attempt_namespace: str | None
    model_key: str
    model_provider: str
    provider_account: str
    model_registry_sha256: str
    policy_sha256: str
    parser_reuse_by_document: Mapping[tuple[str, str], ParserReuseEvidence]
    provider_reuse_by_candidate: Mapping[str, ProviderReuseEvidence]
    parser_run_card_path: Path
    markdown_root: Path
    provider_journal_path: Path


@dataclass(frozen=True, slots=True)
class SuccessorProposal:
    """Exact, non-authoritative proposal; ``inputs`` is set only after replay."""

    cycle_id: str
    selection_path: Path
    selection_run_card_path: Path
    download_manifest_path: Path
    disclosure_clearance_path: Path
    materialization_run_card_path: Path
    document_root: Path
    model_registry_path: Path
    policy_path: Path
    successor_output_root: Path
    provider_attempt_namespace: str | None
    model_key: str
    proposal_sha256: str
    inputs: RerunInputs | None = None

    def require_inputs(self) -> RerunInputs:
        if self.inputs is None:
            raise SuccessorRerunProposalError(
                "successor proposal has not passed materialization replay"
            )
        return self.inputs


def load_successor_proposal(path: Path) -> SuccessorProposal:
    """Load and exact-byte-check one canonical, non-authoritative proposal."""

    payload = _read_regular(path, label="successor proposal")
    raw = _json_object(payload, label="successor proposal")
    committed_paths = {
        "selection_path": "selection_sha256",
        "selection_run_card_path": "selection_run_card_sha256",
        "download_manifest_path": "download_manifest_sha256",
        "disclosure_clearance_path": "disclosure_clearance_sha256",
        "materialization_run_card_path": "materialization_run_card_sha256",
        "model_registry_path": "model_registry_sha256",
        "policy_path": "policy_sha256",
    }
    expected_fields = {
        "schema_version",
        "cycle_id",
        *committed_paths,
        *committed_paths.values(),
        "document_root",
        "provider_attempt_namespace",
        "model_key",
        "successor_output_root",
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

    paths = {name: _absolute_path(raw, name) for name in committed_paths}
    for name, digest_name in committed_paths.items():
        _committed_bytes(paths[name], raw, digest_name, label=f"proposed {name}")
    document_root = _absolute_path(raw, "document_root")
    if document_root.is_symlink() or not document_root.is_dir():
        raise SuccessorRerunProposalError(
            "successor proposal document_root is unavailable or unsafe"
        )
    successor_root = _absolute_path(raw, "successor_output_root")
    _require_isolated_successor_root(
        successor_root,
        committed_inputs=(*paths.values(), document_root),
    )
    return SuccessorProposal(
        cycle_id=_text(raw, "cycle_id"),
        selection_path=paths["selection_path"],
        selection_run_card_path=paths["selection_run_card_path"],
        download_manifest_path=paths["download_manifest_path"],
        disclosure_clearance_path=paths["disclosure_clearance_path"],
        materialization_run_card_path=paths["materialization_run_card_path"],
        document_root=document_root,
        model_registry_path=paths["model_registry_path"],
        policy_path=paths["policy_path"],
        successor_output_root=successor_root,
        provider_attempt_namespace=_optional_text(raw, "provider_attempt_namespace"),
        model_key=_text(raw, "model_key"),
        proposal_sha256=hashlib.sha256(payload).hexdigest(),
    )


def bind_verified_successor_proposal(
    proposal: SuccessorProposal,
    *,
    cycle_id: str,
    selection_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    model_provider: str,
    provider_account: str,
    model_registry_sha256: str,
    policy_sha256: str,
) -> SuccessorProposal:
    """Bind records emitted by existing semantic verifiers to exact proposal bytes."""

    if proposal.inputs is not None:
        raise SuccessorRerunProposalError("successor proposal is already bound")
    if cycle_id != proposal.cycle_id:
        raise SuccessorRerunProposalError(
            "successor materialization cycle_id differs from proposal"
        )
    selection_bytes = _read_regular(
        proposal.selection_path, label="verified proposed selection"
    )
    download_bytes = _read_regular(
        proposal.download_manifest_path, label="verified proposed download manifest"
    )
    if _jsonl(selection_bytes, label="verified proposed selection") != tuple(
        selection_records
    ):
        raise SuccessorRerunProposalError(
            "verified proposed selection records differ from exact bytes"
        )
    if _jsonl(download_bytes, label="verified proposed download manifest") != tuple(
        download_records
    ):
        raise SuccessorRerunProposalError(
            "verified proposed download records differ from exact bytes"
        )
    documents = verified_documents_from_records(
        selection_records,
        download_records,
        document_root=proposal.document_root,
    )
    return replace(
        proposal,
        inputs=RerunInputs(
            cycle_id=cycle_id,
            selection_records=tuple(selection_records),
            documents=documents,
            provider_attempt_namespace=proposal.provider_attempt_namespace,
            model_key=proposal.model_key,
            model_provider=model_provider,
            provider_account=provider_account,
            model_registry_sha256=_digest(model_registry_sha256, "model registry"),
            policy_sha256=_digest(policy_sha256, "provider policy"),
            parser_reuse_by_document={},
            provider_reuse_by_candidate={},
            parser_run_card_path=Path("/not-evaluated/parser-run-card.json"),
            markdown_root=Path("/not-evaluated/markdown"),
            provider_journal_path=Path("/not-evaluated/provider-journal.sqlite3"),
        ),
    )


def successor_derived_output_paths(root: Path) -> tuple[Path, ...]:
    """Return every file or tree deterministically named by advisory argv."""

    return (
        root,
        root / "parse-document-requests.jsonl",
        root / "mistral-markdown-conversions.jsonl",
        root / "markdown",
        root / "target-document-eligibility-audit.jsonl",
        root / "prediction-units.jsonl",
        root / "llm-unitization-audit.jsonl",
        root / "unitization-review-queue.jsonl",
        root / "run-cards" / "plan-parse-documents.json",
        root / "run-cards" / "parse-documents.json",
        root / "run-cards" / "audit-stage-a-target-eligibility.json",
        root / "run-cards" / "llm-unitize.json",
        root / "logs" / "plan-parse-documents.jsonl",
        root / "logs" / "parse-documents.jsonl",
        root / "logs" / "audit-stage-a-target-eligibility.jsonl",
        root / "logs" / "llm-unitize.jsonl",
    )


def _require_isolated_successor_root(
    root: Path, *, committed_inputs: Sequence[Path]
) -> None:
    resolved_inputs = tuple(path.resolve() for path in committed_inputs)
    for output in successor_derived_output_paths(root):
        resolved_output = output.resolve()
        for input_path in resolved_inputs:
            if _paths_overlap(resolved_output, input_path):
                raise SuccessorRerunProposalError(
                    "successor derived output overlaps committed input: "
                    f"{output} vs {input_path}"
                )
    if root.exists() or root.is_symlink():
        raise SuccessorRerunProposalError(
            "successor output root must be a new isolated path"
        )


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def parser_reuse_evidence_from_authenticated_artifacts(
    artifacts: Mapping[
        tuple[str, str, str, int], tuple[Mapping[str, Any], bytes, bytes]
    ],
) -> dict[tuple[str, str], ParserReuseEvidence]:
    """Seal the complete output of ``_authenticate_live_mistral_parse_reuse``."""

    result: dict[tuple[str, str], ParserReuseEvidence] = {}
    for source_key, (record, markdown_bytes, metadata_bytes) in artifacts.items():
        candidate_id, source_document_id, _digest_value, _byte_count = source_key
        key = candidate_id, source_document_id
        if key in result:
            raise SuccessorRerunProposalError(
                f"authenticated parser reuse is ambiguous: {_key_text(key)}"
            )
        extracted = record.get("extracted_text")
        if not isinstance(extracted, Mapping):
            raise SuccessorRerunProposalError(
                f"authenticated parser reuse lacks extracted text: {_key_text(key)}"
            )
        output_sha256 = _sha256(cast(Mapping[str, object], extracted), "text_sha256")
        actual_markdown_sha256 = hashlib.sha256(markdown_bytes).hexdigest()
        if output_sha256 != actual_markdown_sha256:
            raise SuccessorRerunProposalError(
                f"authenticated parser Markdown commitment differs: {_key_text(key)}"
            )
        result[key] = ParserReuseEvidence(
            source_key=source_key,
            markdown_path=_text(record, "markdown_path"),
            metadata_path=_text(record, "metadata_path"),
            record_sha256=hashlib.sha256(
                ARTIFACT_CANONICAL_JSON_V1.encode(record)
            ).hexdigest(),
            markdown_sha256=actual_markdown_sha256,
            metadata_sha256=hashlib.sha256(metadata_bytes).hexdigest(),
            output_markdown_sha256=output_sha256,
        )
    return result


def provider_reuse_evidence_from_verified_rows(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, ProviderReuseEvidence]:
    """Seal settled rows returned by the Stage A run-card replay snapshot."""

    result: dict[str, ProviderReuseEvidence] = {}
    for row in rows:
        if row.get("stage") != "llm-unitize" or row.get("status") != "settled":
            continue
        candidate_id = _text(row, "candidate_id")
        evidence = ProviderReuseEvidence(
            candidate_id=candidate_id,
            stage=_text(row, "stage"),
            logical_call_key=_text(row, "logical_call_key"),
            attempt_ordinal=_positive_int(row, "attempt_ordinal"),
            provider=_text(row, "provider"),
            account=_text(row, "account"),
            prompt_text=_text(row, "prompt_text"),
            prompt_sha256=_sha256(row, "prompt_sha256"),
            model_key=_text(row, "model_key"),
            model_registry_sha256=_sha256(row, "model_registry_sha256"),
            raw_response_json=_json_text(row, "raw_response_json"),
            normalized_response_json=_json_text(row, "normalized_response_json"),
            reconstructed_result_json=_json_text(row, "reconstructed_result_json"),
            attempt_record_sha256=hashlib.sha256(
                ARTIFACT_CANONICAL_JSON_V1.encode(row)
            ).hexdigest(),
        )
        if candidate_id in result:
            raise SuccessorRerunProposalError(
                f"authenticated provider settled call is ambiguous: {candidate_id}"
            )
        result[candidate_id] = evidence
    return result


def verified_documents_from_records(
    selection_records: Sequence[Mapping[str, Any]],
    download_records: Sequence[Mapping[str, Any]],
    *,
    document_root: Path,
) -> tuple[DocumentInput, ...]:
    selected: dict[tuple[str, str], tuple[str, str, bool]] = {}
    candidates: set[str] = set()
    for selection in selection_records:
        candidate_id = _text(selection, "candidate_id")
        case_id = _text(selection, "case_id")
        if candidate_id in candidates:
            raise SuccessorRerunProposalError(
                f"proposed selection has duplicate candidate_id: {candidate_id}"
            )
        candidates.add(candidate_id)
        raw_documents = selection.get("documents")
        if (
            not isinstance(raw_documents, Sequence)
            or isinstance(raw_documents, (str, bytes))
            or not raw_documents
        ):
            raise SuccessorRerunProposalError(
                f"proposed selection documents are invalid: {candidate_id}"
            )
        for raw_document in cast(Sequence[object], raw_documents):
            if not isinstance(raw_document, Mapping):
                raise SuccessorRerunProposalError(
                    f"proposed selection document is invalid: {candidate_id}"
                )
            document = cast(Mapping[str, object], raw_document)
            if _text(document, "candidate_id") != candidate_id:
                raise SuccessorRerunProposalError(
                    f"proposed selection document candidate differs: {candidate_id}"
                )
            source_document_id = _text(document, "source_document_id")
            key = candidate_id, source_document_id
            model_visible = document.get("model_visible")
            if not isinstance(model_visible, bool):
                raise SuccessorRerunProposalError(
                    f"proposed selection model visibility is invalid: {_key_text(key)}"
                )
            if key in selected:
                raise SuccessorRerunProposalError(
                    f"proposed selection document is ambiguous: {_key_text(key)}"
                )
            selected[key] = (case_id, _text(document, "document_role"), model_visible)

    downloads: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in download_records:
        key = (_text(record, "candidate_id"), _text(record, "source_document_id"))
        if key in downloads:
            raise SuccessorRerunProposalError(
                f"proposed download document is ambiguous: {_key_text(key)}"
            )
        downloads[key] = record
    if set(downloads) != set(selected):
        orphaned = sorted(set(downloads) - set(selected))
        missing = sorted(set(selected) - set(downloads))
        detail = orphaned[0] if orphaned else missing[0]
        kind = "orphan" if orphaned else "missing"
        raise SuccessorRerunProposalError(
            f"proposed selection/download coverage has {kind}: {_key_text(detail)}"
        )

    documents: list[DocumentInput] = []
    for key in sorted(downloads):
        record = downloads[key]
        case_id, document_role, model_visible = selected[key]
        if _text(record, "document_role") != document_role:
            raise SuccessorRerunProposalError(
                f"proposed document role differs: {_key_text(key)}"
            )
        relative = Path(_text(record, "local_path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise SuccessorRerunProposalError(
                f"proposed document local_path is unsafe: {_key_text(key)}"
            )
        path = document_root / relative
        payload = _read_regular(path, label=f"proposed document {_key_text(key)}")
        digest = _sha256(record, "sha256")
        byte_count = _nonnegative_int(record, "byte_count")
        if hashlib.sha256(payload).hexdigest() != digest or len(payload) != byte_count:
            raise SuccessorRerunProposalError(
                f"proposed document bytes differ: {_key_text(key)}"
            )
        documents.append(
            DocumentInput(
                candidate_id=key[0],
                case_id=case_id,
                source_document_id=key[1],
                document_role=document_role,
                model_visible=model_visible,
                sha256=digest,
                byte_count=byte_count,
            )
        )
    return tuple(documents)


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise SuccessorRerunProposalError(f"{label} is unavailable or unsafe") from exc


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
        raise SuccessorRerunProposalError(f"{label} is not valid UTF-8 JSON") from exc
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
            raise SuccessorRerunProposalError(f"{label} line {line_number} is blank")
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
        raise SuccessorRerunProposalError(f"successor proposal {field} is not absolute")
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
    return _digest(_text(record, field), field)


def _digest(value: str, label: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(item not in "0123456789abcdef" for item in digest):
        raise SuccessorRerunProposalError(f"{label} must be a lowercase SHA-256")
    return digest


def _nonnegative_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SuccessorRerunProposalError(f"{field} must be a non-negative integer")
    return value


def _positive_int(record: Mapping[str, object], field: str) -> int:
    value = _nonnegative_int(record, field)
    if value == 0:
        raise SuccessorRerunProposalError(f"{field} must be a positive integer")
    return value


def _json_text(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field)
    try:
        json.loads(value)
    except json.JSONDecodeError as exc:
        raise SuccessorRerunProposalError(f"{field} must contain JSON") from exc
    return value


def _key_text(key: tuple[str, str]) -> str:
    return f"{key[0]}/{key[1]}"
