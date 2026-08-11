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
    ARTIFACT_RAW_SHA256_V1,
    SUCCESSOR_RERUN_IMPACT_V1,
)
from legalforecast.ingestion.successor_rerun_proposal import (
    DocumentInput,
    ProviderReuseEvidence,
    RerunInputs,
    SuccessorProposal,
    SuccessorRerunProposalError,
)
from legalforecast.labeling.provider_journal import ProviderCallIdentity
from legalforecast.path_safety import safe_path_component

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
        return (
            json.dumps(
                self.record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            + "\n"
        )

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
                cast(Sequence[object], self.record["provider_logical_call_gaps"])
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
                    "diagnostics": [{"code": "EVIDENCE_INVALID", "message": message}],
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
) -> SuccessorRerunImpact:
    """Compare an authenticated predecessor with exact proposed input bytes."""

    successor = proposed.require_inputs()
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
    parser_gap_keys = [
        key
        for key in document_keys
        if key not in current_documents
        or key not in successor_documents
        or current_documents[key] != successor_documents[key]
        or key not in current.parser_reuse_by_document
        or current.parser_reuse_by_document[key].source_key
        != successor_documents[key].source_key
        or not _parser_output_layout_matches(
            current.parser_reuse_by_document[key], key=key
        )
    ]
    reusable_documents = [
        key
        for key in document_keys
        if key in current_documents
        and current_documents[key] == successor_documents.get(key)
        and key in current.parser_reuse_by_document
        and current.parser_reuse_by_document[key].source_key
        == successor_documents[key].source_key
        and _parser_output_layout_matches(
            current.parser_reuse_by_document[key], key=key
        )
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
            current.provider_attempt_namespace != successor.provider_attempt_namespace,
            current.model_key != successor.model_key,
            current.model_provider != successor.model_provider,
            current.provider_account != successor.provider_account,
            current.model_registry_sha256 != successor.model_registry_sha256,
            current.policy_sha256 != successor.policy_sha256,
        )
    )
    reusable_calls: list[dict[str, object]] = []
    call_gaps: list[dict[str, object]] = []
    for candidate_id, evidence in current.provider_reuse_by_candidate.items():
        _require_provider_evidence_matches_current(
            evidence, current=current, expected_candidate_id=candidate_id
        )
    for candidate_id in sorted(successor_selections):
        reason: str | None = None
        if global_call_drift:
            reason = "model_prompt_or_policy_commitment_changed"
        elif candidate_id in affected_cases:
            reason = "candidate_inputs_changed"
        elif candidate_id not in current.provider_reuse_by_candidate:
            reason = "settled_exact_identity_missing"
        if reason is None:
            evidence = current.provider_reuse_by_candidate[candidate_id]
            reusable_calls.append(
                {
                    "candidate_id": candidate_id,
                    "logical_call_key": evidence.logical_call_key,
                    "attempt_ordinal": evidence.attempt_ordinal,
                }
            )
        else:
            call_gaps.append({"candidate_id": candidate_id, "reason": reason})

    cohort_changed = bool(
        selection_changed or set(current_selections) != set(successor_selections)
    )
    parser_changed = bool(parser_gap_keys)
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
    commands = _derived_next_commands(
        current=current,
        proposal=proposed,
        first_invalidated=first_invalidated,
    )
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
                "parser_reuse_identity_sha256": _parser_evidence_sha256(
                    current.parser_reuse_by_document[key]
                ),
            }
            for key in reusable_documents
        ],
        "reusable_exact_byte_output_count": len(reusable_documents),
        "reusable_logical_calls": reusable_calls,
        "provider_logical_call_gaps": call_gaps,
        "next_commands": commands,
    }
    return SuccessorRerunImpact(record=record)


def _derived_next_commands(
    *, current: RerunInputs, proposal: SuccessorProposal, first_invalidated: str
) -> list[dict[str, object]]:
    if first_invalidated == "none":
        return []
    root = proposal.successor_output_root
    requests = root / "parse-document-requests.jsonl"
    parser_manifest = root / "mistral-markdown-conversions.jsonl"
    parser_card = root / "run-cards" / "parse-documents.json"
    markdown_root = root / "markdown"
    eligibility_audit = root / "target-document-eligibility-audit.jsonl"
    eligibility_card = root / "run-cards" / "audit-stage-a-target-eligibility.json"
    prefix = ["uv", "run", "legalforecast", "acquisition"]
    plan: dict[str, object] = {
        "stage": "plan-parse-documents",
        "argv": [
            *prefix,
            "plan-parse-documents",
            "--output-root",
            str(root),
            "--execute",
            "--selection",
            str(proposal.selection_path),
            "--download-manifest",
            str(proposal.download_manifest_path),
            "--disclosure-clearance",
            str(proposal.disclosure_clearance_path),
            "--materialization-run-card",
            str(proposal.materialization_run_card_path),
            "--document-root",
            str(proposal.document_root),
            "--requests-output",
            str(requests),
            "--markdown-output-root",
            str(markdown_root),
        ],
        "execution_authority": False,
        "requires_separate_authorization": True,
    }
    parse: dict[str, object] = {
        "stage": "parse-documents",
        "argv": [
            *prefix,
            "parse-documents",
            "--output-root",
            str(root),
            "--execute",
            "--selection",
            str(proposal.selection_path),
            "--requests",
            str(requests),
            "--disclosure-clearance",
            str(proposal.disclosure_clearance_path),
            "--materialization-run-card",
            str(proposal.materialization_run_card_path),
            "--manifest-output",
            str(parser_manifest),
            "--reuse-live-mistral-run-card",
            str(current.parser_run_card_path),
            "--reuse-markdown-root",
            str(current.markdown_root),
        ],
        "execution_authority": False,
        "requires_separate_authorization": True,
    }
    eligibility: dict[str, object] = {
        "stage": "audit-stage-a-target-eligibility",
        "argv": [
            *prefix,
            "audit-stage-a-target-eligibility",
            "--output-root",
            str(root),
            "--execute",
            "--selection",
            str(proposal.selection_path),
            "--selection-run-card",
            str(proposal.selection_run_card_path),
            "--download-manifest",
            str(proposal.download_manifest_path),
            "--disclosure-clearance",
            str(proposal.disclosure_clearance_path),
            "--materialization-run-card",
            str(proposal.materialization_run_card_path),
            "--document-root",
            str(proposal.document_root),
            "--parse-requests",
            str(requests),
            "--parser-manifest",
            str(parser_manifest),
            "--parser-run-card",
            str(parser_card),
            "--markdown-root",
            str(markdown_root),
            "--target-eligibility-audit-output",
            str(eligibility_audit),
        ],
        "execution_authority": False,
        "requires_separate_authorization": True,
    }
    unitize_argv = [
        *prefix,
        "llm-unitize",
        "--output-root",
        str(root),
        "--selection",
        str(proposal.selection_path),
        "--selection-run-card",
        str(proposal.selection_run_card_path),
        "--download-manifest",
        str(proposal.download_manifest_path),
        "--disclosure-clearance",
        str(proposal.disclosure_clearance_path),
        "--materialization-run-card",
        str(proposal.materialization_run_card_path),
        "--document-root",
        str(proposal.document_root),
        "--parse-requests",
        str(requests),
        "--parser-manifest",
        str(parser_manifest),
        "--parser-run-card",
        str(parser_card),
        "--markdown-root",
        str(markdown_root),
        "--model-registry",
        str(proposal.model_registry_path),
        "--model-key",
        proposal.model_key,
        "--provider-cycle-caps",
        str(proposal.policy_path),
        "--provider-journal",
        str(current.provider_journal_path),
    ]
    if proposal.provider_attempt_namespace is not None:
        unitize_argv.extend(
            ["--provider-attempt-namespace", proposal.provider_attempt_namespace]
        )
    if proposal.provider_attempt_namespace == "claim-ontology-v4":
        unitize_argv.extend(
            [
                "--target-eligibility-audit",
                str(eligibility_audit),
                "--target-eligibility-audit-run-card",
                str(eligibility_card),
            ]
        )
    unitize: dict[str, object] = {
        "stage": "llm-unitize",
        "argv": unitize_argv,
        "execution_authority": False,
        "requires_separate_authorization": True,
        "advisory_execution": "dry_run_only",
    }
    commands = [plan, parse]
    if proposal.provider_attempt_namespace == "claim-ontology-v4":
        commands.append(eligibility)
    commands.append(unitize)
    if first_invalidated == "llm-unitize":
        return [unitize]
    return commands


def _require_provider_evidence_matches_current(
    evidence: ProviderReuseEvidence,
    *,
    current: RerunInputs,
    expected_candidate_id: str,
) -> None:
    expected_identity = ProviderCallIdentity(
        stage=evidence.stage,
        candidate_id=evidence.candidate_id,
        model_key=current.model_key,
        prompt=evidence.prompt_text,
        model_registry_sha256=current.model_registry_sha256,
        account=current.provider_account,
        prompt_contract=current.provider_attempt_namespace,
    )
    if (
        evidence.stage != "llm-unitize"
        or evidence.candidate_id != expected_candidate_id
        or evidence.provider != current.model_provider
        or evidence.account != current.provider_account
        or evidence.model_key != current.model_key
        or evidence.model_registry_sha256 != current.model_registry_sha256
        or expected_identity.prompt_sha256 != evidence.prompt_sha256
        or expected_identity.logical_call_key != evidence.logical_call_key
        or not evidence.raw_response_json
        or not evidence.normalized_response_json
        or not evidence.reconstructed_result_json
        or len(evidence.attempt_record_sha256) != 64
    ):
        raise SuccessorRerunImpactError(
            f"authenticated provider evidence identity differs: {evidence.candidate_id}"
        )


def _parser_output_layout_matches(evidence: object, *, key: tuple[str, str]) -> bool:
    from legalforecast.ingestion.successor_rerun_proposal import ParserReuseEvidence

    if not isinstance(evidence, ParserReuseEvidence):
        return False
    expected = (
        safe_path_component(key[0], field_name="candidate_id")
        + "/"
        + safe_path_component(key[1], field_name="source_document_id")
        + ".md"
    )
    return evidence.markdown_path == expected and evidence.metadata_path == str(
        Path(expected).with_suffix(".metadata.json")
    )


def _parser_evidence_sha256(evidence: object) -> str:
    from legalforecast.ingestion.successor_rerun_proposal import ParserReuseEvidence

    if not isinstance(evidence, ParserReuseEvidence):
        raise SuccessorRerunImpactError("authenticated parser evidence is malformed")
    payload = {
        "source_key": list(evidence.source_key),
        "markdown_path": evidence.markdown_path,
        "metadata_path": evidence.metadata_path,
        "record_sha256": evidence.record_sha256,
        "markdown_sha256": evidence.markdown_sha256,
        "metadata_sha256": evidence.metadata_sha256,
        "output_markdown_sha256": evidence.output_markdown_sha256,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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
        ARTIFACT_RAW_SHA256_V1.commit(record, domain=SUCCESSOR_RERUN_IMPACT_V1).digest
    )


def _case_id(record: Mapping[str, Any]) -> str:
    return _text(record, "case_id")


def _required_output_sha256(current: RerunInputs, key: tuple[str, str]) -> str:
    try:
        return current.parser_reuse_by_document[key].output_markdown_sha256
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
