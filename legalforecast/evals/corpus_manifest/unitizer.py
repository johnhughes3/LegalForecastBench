"""Provider-facing preparation for the manifest/document-store unitizer path.

This module is deliberately only an input adapter.  It does not issue provider
requests and it does not replace the authenticated lineage verifier used by the
ordinary ``acquisition llm-unitize`` command.  The adapter is for the already
validated corpus stores consumed by the owner-signed manifest path: selection
rows remain the prompt source of truth, while parser sidecars provide the
Markdown bytes without requiring a parser run card.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import (
    read_jsonl_objects,
    write_json_object,
    write_jsonl_objects,
)
from legalforecast.evals.corpus_manifest.freeze import (
    VERDICT_ROLE_COMPATIBILITY,
)
from legalforecast.evals.corpus_manifest.stores import (
    CorpusStoreError,
    StoredDocument,
    VerdictRecord,
    index_document_store,
    index_verdicts,
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry_bytes,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.labeling.llm_pipeline import (
    STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,
    LlmPipelineError,
    llm_unitize_cases,
    unitization_review_queue_records,
)
from legalforecast.labeling.provider_journal import (
    ProviderCycleCaps,
    ProviderJournalError,
    load_provider_cycle_caps,
    verify_provider_journal_identity,
)
from legalforecast.labeling.unitizer_terminal import (
    LlmStageAUnitizerTerminalEscalation,
    UnitizerTerminalEscalationError,
    build_llm_stage_a_unitizer_terminal_escalation,
)

JsonRecord = dict[str, Any]


class ManifestUnitizerInputError(ValueError):
    """Raised when a document-store unitizer input cannot be authenticated."""


class ManifestUnitizerCommandError(ValueError):
    """Raised when manifest-mode execution inputs or outputs are invalid."""


@dataclass(frozen=True, slots=True)
class PreparedManifestUnitizerInputs:
    """Exact prompt inputs assembled from a selection and parser stores."""

    selection_records: tuple[JsonRecord, ...]
    parser_records: tuple[JsonRecord, ...]
    markdown_root: Path
    markdown_bytes: Mapping[str, bytes]
    selection_sha256: str
    document_commitments: Mapping[str, Mapping[str, str]]


def add_manifest_unitizer_arguments(parser: argparse.ArgumentParser) -> None:
    """Add manifest-mode-specific arguments to the acquisition subcommand."""

    parser.add_argument(
        "--selection",
        type=Path,
        required=True,
        help=(
            "Corrected exact-case selection JSONL; rows remain prompt source of truth."
        ),
    )
    parser.add_argument(
        "--document-store-root",
        type=Path,
        action="append",
        required=True,
        dest="document_store_roots",
        help="Succeeded parser sidecar store; repeat for superseding stores.",
    )
    parser.add_argument(
        "--verdict-source",
        type=Path,
        action="append",
        required=True,
        dest="verdict_sources",
        help="Existing byte-role verdict artifact; repeat for all certified verdicts.",
    )
    parser.add_argument("--target-case-count", type=int, default=100)
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--provider-cycle-caps", type=Path)
    parser.add_argument("--provider-journal", type=Path)
    parser.add_argument(
        "--local-provider-journal-only",
        action="store_true",
        help="Use only the explicit cycle-wide SQLite provider journal.",
    )
    parser.add_argument(
        "--provider-attempt-namespace",
        required=True,
        choices=(STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT,),
        help="The reviewed Stage A prompt contract for fresh calls and replay.",
    )
    parser.add_argument(
        "--terminal-escalation",
        type=Path,
        action="append",
        default=[],
        help="Existing provider-free terminal receipt; repeat per candidate.",
    )
    parser.add_argument("--prediction-units-output", type=Path)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--unitization-review-queue-output", type=Path)
    parser.add_argument("--unitizer-terminal-review-queue-output", type=Path)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)


def run_manifest_unitizer(args: argparse.Namespace) -> None:
    """Execute the additive local-journal document-store unitizer path."""

    output_root = Path(args.output_root)
    selection_path = Path(args.selection)
    model_registry_path = Path(args.model_registry)
    prepared = prepare_manifest_unitizer_inputs(
        selection_path=selection_path,
        document_store_roots=tuple(Path(path) for path in args.document_store_roots),
        verdict_sources=tuple(Path(path) for path in args.verdict_sources),
        target_case_count=int(args.target_case_count),
    )
    prediction_units_path = _output_path(
        args, "prediction_units_output", output_root / "prediction-units.jsonl"
    )
    audit_path = _output_path(
        args, "audit_output", output_root / "llm-unitization-audit.jsonl"
    )
    review_queue_path = _output_path(
        args,
        "unitization_review_queue_output",
        output_root / "unitization-review-queue.jsonl",
    )
    terminal_queue_path = _output_path(
        args,
        "unitizer_terminal_review_queue_output",
        output_root / "unitizer-terminal-review-queue.jsonl",
    )
    input_paths = (
        selection_path,
        *(Path(path) for path in args.document_store_roots),
        *(Path(path) for path in args.verdict_sources),
        model_registry_path,
    )
    if not bool(args.execute):
        write_jsonl_objects(
            prediction_units_path,
            [
                {
                    "stage": "llm-unitize-manifest",
                    "dry_run": True,
                    "selection_count": len(prepared.selection_records),
                    "selection_sha256": prepared.selection_sha256,
                    "model_registry": str(model_registry_path),
                    "model_key": str(args.model_key),
                }
            ],
        )
        write_jsonl_objects(review_queue_path, [])
        write_jsonl_objects(terminal_queue_path, [])
        _write_stage_card(
            args,
            output_root=output_root,
            input_paths=input_paths,
            output_paths=(prediction_units_path, review_queue_path),
            record_count=len(prepared.selection_records),
            paid=False,
            extra={"selection_sha256": prepared.selection_sha256},
            dry_run=True,
        )
        return

    if not bool(args.local_provider_journal_only):
        raise ManifestUnitizerCommandError(
            "manifest-mode execution requires --local-provider-journal-only"
        )
    provider_caps_path = getattr(args, "provider_cycle_caps", None)
    provider_journal_value = getattr(args, "provider_journal", None)
    if provider_caps_path is None or provider_journal_value is None:
        raise ManifestUnitizerCommandError(
            "manifest-mode execution requires --provider-cycle-caps and "
            "--provider-journal"
        )
    provider_caps_path = Path(provider_caps_path)
    provider_journal_path = Path(provider_journal_value).resolve()
    try:
        provider_caps = load_provider_cycle_caps(provider_caps_path)
        registry = load_model_registry_bytes(model_registry_path.read_bytes())
        registry_entry = next(
            entry for entry in registry.entries if entry.registry_key == args.model_key
        )
        model_registry_sha256 = _file_sha256(model_registry_path)
        provider_caps_sha256 = _file_sha256(provider_caps_path)
        verify_provider_journal_identity(
            provider_journal_path,
            cycle_id=provider_caps.cycle_id,
            provider_cycle_caps_sha256=provider_caps_sha256,
        )
    except (OSError, ProviderJournalError, ValueError, StopIteration) as exc:
        raise ManifestUnitizerCommandError(
            f"manifest-mode authority input is invalid: {exc}"
        ) from exc
    if args.provider_attempt_namespace != STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT:
        raise ManifestUnitizerCommandError(
            "manifest-mode execution requires claim-ontology-v5"
        )
    terminal_paths = tuple(Path(path) for path in (args.terminal_escalation or ()))
    terminal_escalations = _terminal_escalations(
        terminal_paths,
        prepared=prepared,
        registry_entry=registry_entry,
        model_registry_sha256=model_registry_sha256,
        provider_journal_path=provider_journal_path,
        provider_caps=provider_caps,
        provider_caps_sha256=provider_caps_sha256,
        provider_attempt_namespace=args.provider_attempt_namespace,
    )
    result = llm_unitize_cases(
        selection_records=prepared.selection_records,
        parser_records=prepared.parser_records,
        markdown_root=prepared.markdown_root,
        markdown_bytes=prepared.markdown_bytes,
        registry_entry=registry_entry,
        model_registry_sha256=model_registry_sha256,
        timeout_seconds=float(args.timeout_seconds),
        continue_on_error=bool(args.continue_on_error),
        provider_journal_path=provider_journal_path,
        provider_cycle_caps_usd={
            registry_entry.provider: provider_caps.cap_usd(registry_entry.provider)
        },
        provider_cycle_id=provider_caps.cycle_id,
        provider_cycle_caps_sha256=provider_caps_sha256,
        provider_accounts={
            registry_entry.provider: provider_caps.account(registry_entry.provider)
        },
        terminal_escalations=terminal_escalations,
        provider_attempt_namespace=args.provider_attempt_namespace,
    )
    expected_candidates = {
        str(record["candidate_id"]) for record in prepared.selection_records
    }
    actual_candidates = {str(record["candidate_id"]) for record in result.records}
    if actual_candidates != expected_candidates or len(result.records) != len(
        prepared.selection_records
    ):
        raise ManifestUnitizerCommandError(
            "manifest-mode unitizer did not produce an exact selection-sized batch"
        )
    write_jsonl_objects(prediction_units_path, result.records)
    write_jsonl_objects(audit_path, result.audit_records)
    write_jsonl_objects(
        review_queue_path, unitization_review_queue_records(result.audit_records)
    )
    write_jsonl_objects(terminal_queue_path, result.terminal_review_queue_records)
    _write_stage_card(
        args,
        output_root=output_root,
        input_paths=(
            *input_paths,
            provider_caps_path,
            provider_journal_path,
            *terminal_paths,
        ),
        output_paths=(
            prediction_units_path,
            audit_path,
            review_queue_path,
            terminal_queue_path,
            provider_journal_path,
        ),
        record_count=len(result.records),
        paid=len(terminal_escalations) != len(expected_candidates),
        extra={
            "manifest_mode": True,
            "selection_sha256": prepared.selection_sha256,
            "selection_count": len(prepared.selection_records),
            "document_commitments": dict(prepared.document_commitments),
            "model_execution": {
                "model_key": registry_entry.registry_key,
                "model_registry_sha256": model_registry_sha256,
                "provider_attempt_namespace": args.provider_attempt_namespace,
                "provider_cycle_id": provider_caps.cycle_id,
                "provider_cycle_caps_sha256": provider_caps_sha256,
                "provider_journal": str(provider_journal_path),
                "predecision_only": True,
                "outcome_bytes_mounted": False,
            },
            "result_cost_usd": result.total_estimated_cost,
            "terminal_escalation_count": len(terminal_escalations),
        },
        dry_run=False,
    )


def _output_path(args: argparse.Namespace, name: str, default: Path) -> Path:
    value = getattr(args, name, None)
    return Path(value) if value is not None else default


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _terminal_escalations(
    paths: Sequence[Path],
    *,
    prepared: PreparedManifestUnitizerInputs,
    registry_entry: ModelRegistryEntry,
    model_registry_sha256: str,
    provider_journal_path: Path,
    provider_caps: ProviderCycleCaps,
    provider_caps_sha256: str,
    provider_attempt_namespace: str,
) -> dict[str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]]:
    selections = {str(row["candidate_id"]): row for row in prepared.selection_records}
    result: dict[
        str, tuple[LlmStageAUnitizerTerminalEscalation, Mapping[str, Any]]
    ] = {}
    for path in sorted(paths, key=lambda value: str(value.resolve())):
        if path.is_symlink() or not path.is_file():
            raise ManifestUnitizerCommandError(
                f"terminal receipt is not a regular file: {path}"
            )
        payload = path.read_bytes()
        try:
            raw = json.loads(payload.decode("utf-8"))
            if not isinstance(raw, Mapping):
                raise ValueError("receipt must be an object")
            record = cast(Mapping[str, Any], raw)
            escalation = LlmStageAUnitizerTerminalEscalation(
                candidate_id=str(record["candidate_id"]),
                case_id=str(record["case_id"]),
                unitizer_model_key=str(record["unitizer_model_key"]),
                model_registry_sha256=str(record["model_registry_sha256"]),
                provider_attempt_namespace=str(record["provider_attempt_namespace"]),
                prompt=str(record["prompt"]),
                prompt_sha256=str(record["prompt_sha256"]),
                predecision_source_commitments=tuple(
                    dict(cast(Mapping[str, Any], item))
                    for item in cast(
                        Sequence[object], record["predecision_source_commitments"]
                    )
                ),
                failed_attempts=tuple(
                    dict(cast(Mapping[str, Any], item))
                    for item in cast(Sequence[object], record["failed_attempts"])
                ),
                schema_version=str(record["schema_version"]),
            )
            candidate_id = escalation.candidate_id
            selection = selections[candidate_id]
            expected = build_llm_stage_a_unitizer_terminal_escalation(
                selection_record=selection,
                parser_records=prepared.parser_records,
                markdown_root=prepared.markdown_root,
                markdown_bytes=prepared.markdown_bytes,
                registry_entry=registry_entry,
                model_registry_sha256=model_registry_sha256,
                provider_journal_path=provider_journal_path,
                provider_cycle_cap_usd=provider_caps.cap_usd(registry_entry.provider),
                provider_cycle_id=provider_caps.cycle_id,
                provider_cycle_caps_sha256=provider_caps_sha256,
                provider_account=provider_caps.account(registry_entry.provider),
                provider_attempt_namespace=provider_attempt_namespace,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            LlmPipelineError,
            UnitizerTerminalEscalationError,
        ) as exc:
            raise ManifestUnitizerCommandError(
                f"terminal receipt cannot be authenticated: {path}"
            ) from exc
        if expected.to_record() != dict(record):
            raise ManifestUnitizerCommandError(f"terminal receipt changed: {path}")
        if candidate_id in result:
            raise ManifestUnitizerCommandError(
                f"duplicate terminal receipt: {candidate_id}"
            )
        result[candidate_id] = (
            escalation,
            {"path": str(path.resolve()), "sha256": _sha256_bytes(payload)},
        )
    return result


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write_stage_card(
    args: argparse.Namespace,
    *,
    output_root: Path,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    record_count: int,
    paid: bool,
    extra: Mapping[str, Any],
    dry_run: bool,
) -> None:
    run_card = (
        Path(args.run_card_output)
        if args.run_card_output
        else (output_root / "run-cards" / "llm-unitize-manifest.json")
    )
    log_path = (
        Path(args.log_output)
        if args.log_output
        else (output_root / "logs" / "llm-unitize-manifest.jsonl")
    )
    card: dict[str, Any] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "llm-unitize-manifest",
        "status": "completed",
        "dry_run": dry_run,
        "execute": not dry_run,
        "resume": bool(args.resume),
        "record_count": record_count,
        "input_paths": [str(path) for path in input_paths],
        "output_paths": [str(path) for path in output_paths],
        "paid_activity_requested": paid,
        "paid_activity_executed": paid,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **dict(extra),
    }
    write_json_object(run_card, card)
    write_jsonl_objects(
        log_path,
        [
            {
                "schema_version": "legalforecast.acquisition_stage_log.v1",
                "event": "stage_completed",
                "stage": "llm-unitize-manifest",
                "status": "completed",
                "dry_run": dry_run,
                "run_card_path": str(run_card),
                "record_count": record_count,
                "paid_activity_requested": paid,
                "paid_activity_executed": paid,
            }
        ],
    )


def prepare_manifest_unitizer_inputs(
    *,
    selection_path: Path,
    document_store_roots: Sequence[Path],
    verdict_sources: Sequence[Path],
    target_case_count: int = 100,
) -> PreparedManifestUnitizerInputs:
    """Authenticate predecision bytes and prepare the existing unitizer API.

    Selection rows are read verbatim and remain the source of prompt metadata;
    this is what preserves existing journal prompt identities for the 95 common
    cases.  Parser records are reconstructed only as a narrow adapter over
    succeeded parser sidecars.  Every model-visible document must have a
    current accepting verdict whose *certified* role matches the selected role;
    a claimed role is never used as authority.
    """

    if target_case_count <= 0:
        raise ManifestUnitizerInputError("target_case_count must be positive")
    try:
        raw_selection = read_jsonl_objects(
            selection_path,
            error_factory=ManifestUnitizerInputError,
            missing_message=lambda missing: f"selection not found: {missing}",
            non_object_message=lambda bad, line: (
                f"selection row {line} in {bad} is not an object"
            ),
        )
        selected = tuple(
            row for row in raw_selection if row.get("selected", True) is not False
        )
        if len(selected) != target_case_count:
            raise ManifestUnitizerInputError(
                f"selection contains {len(selected)} selected cases; expected "
                f"exactly {target_case_count}"
            )
        candidate_ids = tuple(_required_string(row, "candidate_id") for row in selected)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ManifestUnitizerInputError(
                "selection contains duplicate candidate_id"
            )

        documents = index_document_store(document_store_roots)
        verdicts = index_verdicts(verdict_sources)
    except (CorpusStoreError, OSError, ValueError) as exc:
        if isinstance(exc, ManifestUnitizerInputError):
            raise
        raise ManifestUnitizerInputError(str(exc)) from exc

    model_documents: list[tuple[str, str, StoredDocument]] = []
    selected_document_keys: set[tuple[str, str]] = set()
    document_commitments: dict[str, dict[str, str]] = {}
    for selection in selected:
        candidate_id = _required_string(selection, "candidate_id")
        document_rows = selection.get("documents")
        if not isinstance(document_rows, list):
            raise ManifestUnitizerInputError(
                f"{candidate_id}: selection documents must be a list"
            )
        for raw_document in cast(list[object], document_rows):
            if not isinstance(raw_document, Mapping):
                raise ManifestUnitizerInputError(
                    f"{candidate_id}: selection contains a malformed document row"
                )
            document = cast(Mapping[str, Any], raw_document)
            document_id = _required_string(document, "source_document_id")
            role_value = _required_string(document, "document_role")
            try:
                role = DocumentRole(role_value)
            except ValueError as exc:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: unknown document role "
                    f"{role_value!r}"
                ) from exc
            model_visible = document.get("model_visible") is True
            if not model_visible:
                # Audit-only and outcome documents are intentionally not mounted
                # into the model prompt.  They need no parser sidecar here.
                continue
            if document.get("contains_target_outcome") is True:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: outcome-bearing bytes are "
                    "model-visible"
                )
            if role in {DocumentRole.ORDER, DocumentRole.DECISION}:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: outcome-bearing role is "
                    "model-visible"
                )
            key = (candidate_id, document_id)
            if key in selected_document_keys:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}: duplicate model-visible document {document_id}"
                )
            selected_document_keys.add(key)
            stored = documents.get(document_id)
            if stored is None:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: no succeeded parser sidecar "
                    "in the supplied document stores"
                )
            if stored.candidate_id and stored.candidate_id != candidate_id:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: parser sidecar belongs to "
                    f"{stored.candidate_id}"
                )
            _require_certified_role(
                document_id=document_id,
                selected_role=role,
                verdicts=verdicts,
            )
            pdf_bytes = _read_regular_bytes(
                stored.pdf_path, "PDF", candidate_id, document_id
            )
            markdown_bytes = _read_regular_bytes(
                stored.markdown_path, "Markdown", candidate_id, document_id
            )
            recorded_pdf_sha256 = stored.recorded_pdf_sha256.removeprefix("sha256:")
            actual_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
            if recorded_pdf_sha256 != actual_pdf_sha256:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: PDF bytes differ from the "
                    "parser sidecar source_sha256"
                )
            if not markdown_bytes.strip():
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: Markdown is empty"
                )
            document_commitments[document_id] = {
                "pdf_sha256": actual_pdf_sha256,
                "markdown_sha256": hashlib.sha256(markdown_bytes).hexdigest(),
            }
            model_documents.append((candidate_id, document_id, stored))

    if not model_documents:
        raise ManifestUnitizerInputError("selection has no model-visible documents")

    markdown_parents = [
        str(stored.markdown_path.resolve().parent) for _, _, stored in model_documents
    ]
    try:
        markdown_root = Path(os.path.commonpath(markdown_parents)).resolve()
    except ValueError as exc:
        raise ManifestUnitizerInputError(
            "model-visible Markdown stores do not share a common root"
        ) from exc
    markdown_payloads: dict[str, bytes] = {}
    parser_records: list[JsonRecord] = []
    for candidate_id, document_id, stored in model_documents:
        markdown_path = stored.markdown_path.resolve()
        try:
            relative = markdown_path.relative_to(markdown_root).as_posix()
        except ValueError as exc:
            raise ManifestUnitizerInputError(
                f"{candidate_id}/{document_id}: Markdown path is outside its root"
            ) from exc
        payload = _read_regular_bytes(
            stored.markdown_path, "Markdown", candidate_id, document_id
        )
        if relative in markdown_payloads and markdown_payloads[relative] != payload:
            raise ManifestUnitizerInputError(f"Markdown path collision for {relative}")
        markdown_payloads[relative] = payload
        parser_records.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": relative,
                "source_sha256": stored.recorded_pdf_sha256,
                "markdown_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
        )

    selection_sha256 = hashlib.sha256(selection_path.read_bytes()).hexdigest()
    return PreparedManifestUnitizerInputs(
        selection_records=tuple(dict(row) for row in selected),
        parser_records=tuple(parser_records),
        markdown_root=markdown_root,
        markdown_bytes=markdown_payloads,
        selection_sha256=selection_sha256,
        document_commitments=document_commitments,
    )


def _required_string(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestUnitizerInputError(f"record is missing non-empty {field}")
    return value


def _read_regular_bytes(
    path: Path, kind: str, candidate_id: str, document_id: str
) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ManifestUnitizerInputError(
            f"{candidate_id}/{document_id}: {kind} path is not a regular file"
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ManifestUnitizerInputError(
            f"{candidate_id}/{document_id}: {kind} is unreadable"
        ) from exc


def _require_certified_role(
    *,
    document_id: str,
    selected_role: DocumentRole,
    verdicts: Mapping[str, tuple[VerdictRecord, ...]],
) -> None:
    records = verdicts.get(document_id)
    if not records:
        raise ManifestUnitizerInputError(
            f"{document_id}: model-visible document has no byte-role verdict"
        )
    refusals = [record for record in records if record.is_refusal]
    if refusals:
        raise ManifestUnitizerInputError(
            f"{document_id}: byte-role verdict refuses the document"
        )
    accepted = [record for record in records if record.is_accepted]
    if not accepted:
        raise ManifestUnitizerInputError(
            f"{document_id}: no accepting byte-role verdict"
        )
    for record in accepted:
        certified_role = record.certified_role
        if certified_role is None:
            raise ManifestUnitizerInputError(
                f"{document_id}: accepting verdict has no certified role"
            )
        compatible = VERDICT_ROLE_COMPATIBILITY.get(certified_role)
        if compatible is None:
            raise ManifestUnitizerInputError(
                f"{document_id}: certified role {certified_role!r} is unclassified"
            )
        if selected_role not in compatible:
            raise ManifestUnitizerInputError(
                f"{document_id}: selected role {selected_role.value!r} differs "
                f"from certified role {certified_role!r}"
            )
