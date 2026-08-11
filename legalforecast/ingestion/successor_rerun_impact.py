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
from typing import Any, Literal, cast

from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    SUCCESSOR_RERUN_IMPACT_V1,
)
from legalforecast.ingestion.successor_rerun_proposal import (
    DocumentInput,
    RerunInputs,
    SuccessorProposal,
    SuccessorRerunProposalError,
)
from legalforecast.labeling.provider_journal import ProviderCallIdentity

REPORT_SCHEMA_VERSION = SUCCESSOR_RERUN_IMPACT_V1.value
ADVISORY_WARNING = (
    "ADVISORY ONLY: this report grants no execution, provider, purchase, freeze, "
    "dispatch, publication, or artifact authority."
)

StageStatus = Literal["REUSABLE", "AFFECTED", "FAILED", "NOT_EVALUATED"]


SuccessorRerunImpactError = SuccessorRerunProposalError


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


def _shell_join(arguments: Sequence[str]) -> str:
    """Quote command arguments deterministically without invoking a shell."""

    import shlex

    return shlex.join(arguments)


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


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise SuccessorRerunImpactError(f"{field} must be non-empty text")
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
