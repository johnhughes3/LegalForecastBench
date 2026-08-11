"""Provider-free advisory planning for a successor Stage A rerun.

This module deliberately accepts an already-authenticated predecessor projection.
The acquisition CLI builds that projection with the existing Stage A semantic
replay before calling :func:`plan_successor_rerun_impact`.  A returned report is
observational metadata only: it is never accepted as an execution receipt,
provider authority, or artifact commitment.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    SUCCESSOR_RERUN_IMPACT_V1,
    SUCCESSOR_RERUN_PROPOSAL_V1,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.labeling.provider_journal import ProviderCallIdentity

REPORT_SCHEMA_VERSION = SUCCESSOR_RERUN_IMPACT_V1.value
PROPOSAL_SCHEMA_VERSION = SUCCESSOR_RERUN_PROPOSAL_V1.value
ADVISORY_WARNING = (
    "ADVISORY ONLY: this report grants no execution, provider, purchase, freeze, "
    "dispatch, publication, or artifact authority."
)

StageStatus = Literal["REUSABLE", "AFFECTED", "FAILED", "NOT_EVALUATED"]


class SuccessorRerunImpactError(ValueError):
    """Raised when the proposal or authenticated predecessor is inconsistent."""


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

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_document_id": self.source_document_id,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }


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


@dataclass(frozen=True, slots=True)
class SuccessorRerunImpact:
    """Deterministic advisory result."""

    record: Mapping[str, object]

    @property
    def ok(self) -> bool:
        return self.record.get("advisory") is True

    def json_text(self) -> str:
        return json.dumps(
            self.record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ) + "\n"

    def text(self) -> str:
        stages = cast(Sequence[Mapping[str, object]], self.record["stages"])
        lines = [ADVISORY_WARNING]
        lines.append(
            "FIRST_INVALIDATED_STAGE "
            + cast(str, self.record["first_invalidated_stage"])
        )
        for stage in stages:
            lines.append(f"{stage['status']} {stage['stage']}")
        lines.append(
            "AFFECTED_CASES "
            + _render_ids(cast(Sequence[object], self.record["affected_cases"]))
        )
        lines.append(
            "AFFECTED_DOCUMENTS "
            + _render_ids(cast(Sequence[object], self.record["affected_documents"]))
        )
        lines.append(
            "REUSABLE_DOCUMENTS "
            + _render_ids(cast(Sequence[object], self.record["reusable_documents"]))
        )
        lines.append(
            "REUSABLE_LOGICAL_CALLS "
            + _render_ids(cast(Sequence[object], self.record["reusable_logical_calls"]))
        )
        lines.append(
            "PROVIDER_LOGICAL_CALL_GAPS "
            + _render_ids(
                cast(
                    Sequence[object], self.record["provider_logical_call_gaps"]
                )
            )
        )
        for command in cast(
            Sequence[Mapping[str, object]], self.record["next_commands"]
        ):
            argv = cast(Sequence[str], command["argv"])
            lines.append(f"NEXT {command['stage']}: {_shell_join(argv)}")
        return "\n".join(lines) + "\n"


def failed_successor_rerun_impact(message: str) -> SuccessorRerunImpact:
    """Return a deterministic fail-closed graph without evaluating descendants."""

    return SuccessorRerunImpact(
        record={
            "schema_version": REPORT_SCHEMA_VERSION,
            "advisory": True,
            "authority": {
                "artifact": False,
                "dispatch": False,
                "execution": False,
                "freeze": False,
                "provider": False,
                "publication": False,
                "purchase": False,
            },
            "warning": ADVISORY_WARNING,
            "first_invalidated_stage": "lineage",
            "stages": [
                {
                    "stage": "lineage",
                    "status": "FAILED",
                    "diagnostics": [
                        {"code": "EVIDENCE_INVALID", "message": message}
                    ],
                },
                {
                    "stage": "selection",
                    "status": "NOT_EVALUATED",
                    "blocked_by": ["lineage"],
                },
                {
                    "stage": "parse-documents",
                    "status": "NOT_EVALUATED",
                    "blocked_by": ["lineage"],
                },
                {
                    "stage": "llm-unitize",
                    "status": "NOT_EVALUATED",
                    "blocked_by": ["lineage"],
                },
            ],
            "affected_cases": [],
            "affected_candidates": [],
            "affected_documents": [],
            "reusable_documents": [],
            "reusable_parser_outputs": [],
            "reusable_exact_byte_output_count": 0,
            "reusable_logical_calls": [],
            "provider_logical_call_gaps": [],
            "next_commands": [],
        }
    )


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
        raise SuccessorRerunImpactError(
            "successor proposal fields, schema, or advisory marker differ"
        )
    if ARTIFACT_CANONICAL_JSON_V1.encode(raw) != payload:
        raise SuccessorRerunImpactError(
            "successor proposal must use canonical JSON value bytes"
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
    next_commands = _proposal_commands(raw.get("next_commands"))
    return SuccessorProposal(
        inputs=inputs,
        selection_path=selection_path,
        download_manifest_path=downloads_path,
        model_registry_path=registry_path,
        policy_path=policy_path,
        successor_output_root=successor_root,
        next_commands=next_commands,
        proposal_sha256=hashlib.sha256(payload).hexdigest(),
    )


def plan_successor_rerun_impact(
    *,
    current: RerunInputs,
    proposed: SuccessorProposal,
    settled_provider_rows: Sequence[Mapping[str, object]],
    current_prompt_sha256_by_candidate: Mapping[str, str],
) -> SuccessorRerunImpact:
    """Compare an authenticated predecessor with exact proposed input bytes."""

    successor = proposed.inputs
    if current.cycle_id != successor.cycle_id:
        raise SuccessorRerunImpactError(
            "successor cycle_id differs from authenticated predecessor"
        )
    current_documents = _document_index(current.documents, label="current")
    successor_documents = _document_index(successor.documents, label="proposed")
    current_selections = _selection_index(current.selection_records, label="current")
    successor_selections = _selection_index(
        successor.selection_records, label="proposed"
    )

    document_keys = sorted(set(current_documents) | set(successor_documents))
    changed_documents = [
        key
        for key in document_keys
        if current_documents.get(key) != successor_documents.get(key)
    ]
    parser_gap_keys = (
        document_keys
        if current.parser_revision != successor.parser_revision
        else changed_documents
    )
    reusable_documents = [
        key
        for key in document_keys
        if key in current_documents
        and current_documents[key] == successor_documents.get(key)
        and current.parser_revision == successor.parser_revision
    ]
    case_ids = sorted(set(current_selections) | set(successor_selections))
    selection_changed = {
        candidate_id
        for candidate_id in case_ids
        if _record_digest(current_selections.get(candidate_id))
        != _record_digest(successor_selections.get(candidate_id))
    }
    affected_cases = sorted(
        selection_changed | {candidate_id for candidate_id, _ in parser_gap_keys}
    )
    affected_case_ids = sorted(
        {
            _case_id(
                successor_selections.get(candidate_id)
                or current_selections[candidate_id]
            )
            for candidate_id in affected_cases
        }
    )

    global_call_drift = any(
        (
            current.provider_attempt_namespace
            != successor.provider_attempt_namespace,
            current.model_key != successor.model_key,
            current.model_registry_sha256 != successor.model_registry_sha256,
            current.policy_sha256 != successor.policy_sha256,
        )
    )
    settled_by_candidate = _settled_call_keys(
        settled_provider_rows,
        current=current,
        current_prompt_sha256_by_candidate=current_prompt_sha256_by_candidate,
    )
    reusable_calls: list[dict[str, object]] = []
    call_gaps: list[dict[str, object]] = []
    for candidate_id in sorted(successor_selections):
        reason: str | None = None
        if global_call_drift:
            reason = "model_prompt_or_policy_commitment_changed"
        elif candidate_id in affected_cases:
            reason = "candidate_inputs_changed"
        elif candidate_id not in settled_by_candidate:
            reason = "settled_exact_identity_missing"
        if reason is None:
            reusable_calls.append(
                {
                    "candidate_id": candidate_id,
                    "logical_call_key": settled_by_candidate[candidate_id],
                }
            )
        else:
            call_gaps.append({"candidate_id": candidate_id, "reason": reason})

    cohort_changed = bool(
        selection_changed or set(current_selections) != set(successor_selections)
    )
    parser_changed = bool(parser_gap_keys) or (
        current.parser_revision != successor.parser_revision
    )
    unitizer_changed = global_call_drift or bool(call_gaps)
    first_invalidated = (
        "selection"
        if cohort_changed
        else "parse-documents"
        if parser_changed
        else "llm-unitize"
        if unitizer_changed
        else "none"
    )
    statuses: dict[str, StageStatus] = {
        "selection": "AFFECTED" if cohort_changed else "REUSABLE",
        "parse-documents": "AFFECTED" if parser_changed else "REUSABLE",
        "llm-unitize": "AFFECTED" if unitizer_changed else "REUSABLE",
    }
    stages = [
        {"stage": name, "status": statuses[name]}
        for name in ("selection", "parse-documents", "llm-unitize")
    ]
    commands = _next_commands(proposed, first_invalidated=first_invalidated)
    record: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "advisory": True,
        "authority": {
            "artifact": False,
            "dispatch": False,
            "execution": False,
            "freeze": False,
            "provider": False,
            "publication": False,
            "purchase": False,
        },
        "warning": ADVISORY_WARNING,
        "cycle_id": successor.cycle_id,
        "proposal_sha256": proposed.proposal_sha256,
        "proposed_global_commitments": {
            "model_registry_sha256": successor.model_registry_sha256,
            "parser_revision": successor.parser_revision,
            "policy_sha256": successor.policy_sha256,
            "provider_attempt_namespace": successor.provider_attempt_namespace,
        },
        "first_invalidated_stage": first_invalidated,
        "stages": stages,
        "affected_cases": affected_case_ids,
        "affected_candidates": affected_cases,
        "affected_documents": [_key_text(key) for key in parser_gap_keys],
        "reusable_documents": [_key_text(key) for key in reusable_documents],
        "reusable_parser_outputs": [
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "markdown_sha256": _required_output_sha256(current, key),
            }
            for key in reusable_documents
        ],
        "reusable_exact_byte_output_count": len(reusable_documents),
        "reusable_logical_calls": reusable_calls,
        "provider_logical_call_gaps": call_gaps,
        "next_commands": commands,
    }
    return SuccessorRerunImpact(record=record)


def current_documents_from_parser_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[DocumentInput, ...]:
    """Project exact source identities from authenticated successful parser rows."""

    documents: list[DocumentInput] = []
    revisions: set[str] = set()
    for record in records:
        if record.get("status") != "succeeded":
            raise SuccessorRerunImpactError(
                "authenticated parser lineage contains a non-successful row"
            )
        config = record.get("parser_config")
        if not isinstance(config, Mapping):
            raise SuccessorRerunImpactError("parser row lacks parser_config")
        revision = cast(Mapping[str, object], config).get("parser_revision")
        if not isinstance(revision, str) or not revision:
            raise SuccessorRerunImpactError("parser row lacks parser revision")
        revisions.add(revision)
        documents.append(
            DocumentInput(
                candidate_id=_text(record, "candidate_id"),
                source_document_id=_text(record, "source_document_id"),
                sha256=_sha256(record, "source_sha256"),
                byte_count=_positive_or_zero_int(record, "source_byte_count"),
            )
        )
    if len(revisions) != 1:
        raise SuccessorRerunImpactError(
            f"authenticated parser revision is ambiguous ({len(revisions)} found)"
        )
    result = tuple(sorted(documents, key=lambda item: item.key))
    _require_unique_documents(result, label="authenticated parser")
    return result


def parser_revision_from_records(records: Sequence[Mapping[str, Any]]) -> str:
    documents = current_documents_from_parser_records(records)
    if not documents:  # pragma: no cover - the helper above rejects via revision count
        raise SuccessorRerunImpactError("authenticated parser lineage is empty")
    first = records[0].get("parser_config")
    assert isinstance(first, Mapping)
    return cast(str, first["parser_revision"])


def parser_output_sha256_from_records(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], str]:
    """Project Markdown byte commitments from authenticated parser rows."""

    result: dict[tuple[str, str], str] = {}
    for record in records:
        key = (_text(record, "candidate_id"), _text(record, "source_document_id"))
        extracted = record.get("extracted_text")
        if not isinstance(extracted, Mapping):
            raise SuccessorRerunImpactError(
                f"authenticated parser row lacks extracted text: {_key_text(key)}"
            )
        digest = _sha256(cast(Mapping[str, object], extracted), "text_sha256")
        if key in result:
            raise SuccessorRerunImpactError(
                f"authenticated parser output is ambiguous: {_key_text(key)}"
            )
        result[key] = digest
    return result


def _settled_call_keys(
    rows: Sequence[Mapping[str, object]],
    *,
    current: RerunInputs,
    current_prompt_sha256_by_candidate: Mapping[str, str],
) -> dict[str, str]:
    settled: dict[str, str] = {}
    for row in rows:
        if row.get("status") != "settled":
            continue
        candidate_id = _text(row, "candidate_id")
        prompt = _text(row, "prompt_text")
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if current_prompt_sha256_by_candidate.get(candidate_id, "").removeprefix(
            "sha256:"
        ) != prompt_sha256:
            raise SuccessorRerunImpactError(
                f"authenticated provider prompt commitment differs: {candidate_id}"
            )
        identity = ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id=candidate_id,
            model_key=current.model_key,
            prompt=prompt,
            model_registry_sha256=current.model_registry_sha256,
            prompt_contract=current.provider_attempt_namespace,
        )
        if (
            row.get("logical_call_key") != identity.logical_call_key
            or row.get("model_key") != current.model_key
            or row.get("model_registry_sha256") != current.model_registry_sha256
        ):
            raise SuccessorRerunImpactError(
                f"authenticated provider logical-call identity differs: {candidate_id}"
            )
        if candidate_id in settled:
            raise SuccessorRerunImpactError(
                f"authenticated provider settled call is ambiguous: {candidate_id}"
            )
        settled[candidate_id] = identity.logical_call_key
    return settled


def _next_commands(
    proposal: SuccessorProposal,
    *,
    first_invalidated: str,
) -> list[dict[str, object]]:
    if first_invalidated == "none":
        return []
    order = {
        "selection": 0,
        "plan-parse-documents": 1,
        "parse-documents": 2,
        "llm-unitize": 3,
    }
    threshold = {
        "selection": 0,
        "parse-documents": 1,
        "llm-unitize": 3,
    }[first_invalidated]
    return [
        dict(command)
        for command in proposal.next_commands
        if order[cast(str, command["stage"])] >= threshold
    ]


def _proposal_commands(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise SuccessorRerunImpactError("successor proposal next_commands are invalid")
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
            raise SuccessorRerunImpactError(
                "successor proposal next command fields differ"
            )
        command = cast(Mapping[str, object], raw)
        if set(command) != {
            "stage",
            "argv",
            "execution_authority",
            "requires_separate_authorization",
        }:
            raise SuccessorRerunImpactError(
                "successor proposal next command fields differ"
            )
        stage = _text(command, "stage")
        argv = command.get("argv")
        raw_arguments = cast(list[object], argv) if isinstance(argv, list) else []
        if (
            stage not in allowed_stages
            or stage in seen
            or not isinstance(argv, list)
            or not argv
            or any(
                not isinstance(argument, str) or not argument
                for argument in raw_arguments
            )
            or command.get("execution_authority") is not False
            or not isinstance(command.get("requires_separate_authorization"), bool)
        ):
            raise SuccessorRerunImpactError(
                "successor proposal next command is invalid or authoritative"
            )
        typed_argv = cast(list[str], argv)
        if typed_argv[:4] != ["uv", "run", "legalforecast", "acquisition"]:
            raise SuccessorRerunImpactError(
                "successor proposal next command is not an acquisition CLI invocation"
            )
        if any(
            argument in {"--api-key", "--credential", "--token"}
            for argument in typed_argv
        ):
            raise SuccessorRerunImpactError(
                "successor proposal next command contains a credential option"
            )
        seen.add(stage)
        commands.append(dict(command))
    return tuple(commands)


def _shell_join(arguments: Sequence[str]) -> str:
    """Quote command arguments deterministically without invoking a shell."""

    import shlex

    return shlex.join(arguments)


def _document_from_download(record: Mapping[str, Any]) -> DocumentInput:
    return DocumentInput(
        candidate_id=_text(record, "candidate_id"),
        source_document_id=_text(record, "source_document_id"),
        sha256=_sha256(record, "sha256"),
        byte_count=_positive_or_zero_int(record, "byte_count"),
    )


def _verify_proposed_document_bytes(
    records: Sequence[Mapping[str, Any]], documents: Sequence[DocumentInput]
) -> None:
    by_key = {document.key: document for document in documents}
    for record in records:
        key = (_text(record, "candidate_id"), _text(record, "source_document_id"))
        raw_path = record.get("local_path")
        if not isinstance(raw_path, str) or not raw_path:
            raise SuccessorRerunImpactError("proposed document lacks local_path")
        path = Path(raw_path)
        if not path.is_absolute():
            raise SuccessorRerunImpactError(
                "proposed document local_path must be absolute"
            )
        payload = _read_regular(path, label=f"proposed document {_key_text(key)}")
        document = by_key[key]
        if (
            hashlib.sha256(payload).hexdigest() != document.sha256
            or len(payload) != document.byte_count
        ):
            raise SuccessorRerunImpactError(
                f"proposed document bytes differ: {_key_text(key)}"
            )


def _selection_index(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _text(record, "candidate_id")
        if candidate_id in result:
            raise SuccessorRerunImpactError(
                f"{label} selection has duplicate candidate_id: {candidate_id}"
            )
        result[candidate_id] = record
    if not result:
        raise SuccessorRerunImpactError(f"{label} selection is empty")
    return result


def _document_index(
    documents: Sequence[DocumentInput], *, label: str
) -> dict[tuple[str, str], DocumentInput]:
    _require_unique_documents(documents, label=label)
    return {document.key: document for document in documents}


def _require_unique_documents(
    documents: Sequence[DocumentInput], *, label: str
) -> None:
    keys = [document.key for document in documents]
    if len(keys) != len(set(keys)):
        raise SuccessorRerunImpactError(f"{label} documents are ambiguous")


def _record_digest(record: Mapping[str, Any] | None) -> str | None:
    if record is None:
        return None
    return str(
        ARTIFACT_RAW_SHA256_V1.commit(
            record, domain=SUCCESSOR_RERUN_IMPACT_V1
        ).digest
    )


def _case_id(record: Mapping[str, Any]) -> str:
    return _text(record, "case_id")


def _required_output_sha256(
    current: RerunInputs, key: tuple[str, str]
) -> str:
    try:
        return current.parser_output_sha256_by_document[key]
    except KeyError as exc:
        raise SuccessorRerunImpactError(
            f"authenticated parser output is missing: {_key_text(key)}"
        ) from exc


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        return read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise SuccessorRerunImpactError(f"{label} is unavailable or unsafe") from exc


def _committed_bytes(
    path: Path, record: Mapping[str, object], field: str, *, label: str
) -> bytes:
    payload = _read_regular(path, label=label)
    if hashlib.sha256(payload).hexdigest() != _sha256(record, field):
        raise SuccessorRerunImpactError(f"{label} bytes differ from proposal")
    return payload


def _json_object(payload: bytes, *, label: str) -> Mapping[str, object]:
    try:
        raw = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SuccessorRerunImpactError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(raw, Mapping):
        raise SuccessorRerunImpactError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], raw)


def _jsonl(payload: bytes, *, label: str) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise SuccessorRerunImpactError(f"{label} is not UTF-8") from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SuccessorRerunImpactError(
                f"{label} line {line_number} is not JSON"
            ) from exc
        if not isinstance(raw, Mapping):
            raise SuccessorRerunImpactError(
                f"{label} line {line_number} must be an object"
            )
        records.append(cast(Mapping[str, Any], raw))
    if not records:
        raise SuccessorRerunImpactError(f"{label} is empty")
    return tuple(records)


def _absolute_path(record: Mapping[str, object], field: str) -> Path:
    path = Path(_text(record, field))
    if not path.is_absolute() or ".." in path.parts:
        raise SuccessorRerunImpactError(f"successor proposal {field} is not absolute")
    return path


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise SuccessorRerunImpactError(f"{field} must be non-empty text")
    return value


def _optional_text(record: Mapping[str, object], field: str) -> str | None:
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SuccessorRerunImpactError(f"{field} must be non-empty text or null")
    return value


def _sha256(record: Mapping[str, object], field: str) -> str:
    value = _text(record, field).removeprefix("sha256:")
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise SuccessorRerunImpactError(f"{field} must be a lowercase SHA-256")
    return value


def _positive_or_zero_int(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SuccessorRerunImpactError(f"{field} must be a non-negative integer")
    return value


def _key_text(key: tuple[str, str]) -> str:
    return f"{key[0]}/{key[1]}"


def _render_ids(values: Sequence[object]) -> str:
    if not values:
        return "-"
    rendered: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            record = cast(Mapping[str, object], value)
            candidate_id = record.get("candidate_id")
            rendered.append(
                candidate_id if isinstance(candidate_id, str) else "<invalid>"
            )
        else:
            rendered.append(str(value))
    return ",".join(rendered)
