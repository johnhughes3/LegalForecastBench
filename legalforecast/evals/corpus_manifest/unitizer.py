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
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import (
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
    index_verdict_payloads,
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry_bytes,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    SqliteProviderSpendAuthority,
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
    load_provider_cycle_caps_bytes,
    verify_provider_journal_identity,
)
from legalforecast.labeling.unitizer_terminal import (
    LlmStageAUnitizerTerminalEscalation,
    UnitizerTerminalEscalationError,
    build_llm_stage_a_unitizer_terminal_escalation,
)
from legalforecast.unitization.schemas import prediction_unit_from_record

JsonRecord = dict[str, Any]

_UNITS_SPEND_APPROVAL = (
    "units: approved — ceiling USD 5.00 extends to the sixth fresh case"
)
_CYCLE1_FRESH_CANDIDATE_IDS = frozenset(
    {"69437817", "69617129", "70142291", "71203930", "71929529", "72288139"}
)
_LABELING_MODEL_KEY = "anthropic:claude-sonnet-4-6"
_LABELING_MODEL_REGISTRY_SHA256 = (
    "e24b0a235936de4b0870fd6b688fabbd4901ccd3a8378a826c4a287a26c1aba0"
)
_PROVIDER_CAPS_SHA256 = (
    "71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74"
)
_UNITS_SPEND_CAP_MICROUSD = 5_000_000
_CLAIM_BEARING_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT,
        DocumentRole.AMENDED_COMPLAINT,
        DocumentRole.COUNTERCLAIM,
        DocumentRole.CROSSCLAIM,
        DocumentRole.THIRD_PARTY_COMPLAINT,
        DocumentRole.INTERPLEADER_COMPLAINT,
        DocumentRole.OTHER_CLAIM_BEARING,
    }
)
_TARGET_MOTION_ROLES = frozenset({DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM})


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
    verdict_source_sha256: tuple[str, ...]
    document_commitments: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class AuthenticatedFinalizedOverlay:
    """Provider-free finalized units retained from the authenticated overlay."""

    retained_records: tuple[JsonRecord, ...]
    fresh_selection_records: tuple[JsonRecord, ...]
    overlay_sha256: str
    integration_manifest_sha256: str
    fresh_candidate_ids: tuple[str, ...]


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
    parser.add_argument(
        "--expected-verdict-source-sha256",
        action="append",
        required=True,
        dest="expected_verdict_source_sha256",
        help=(
            "Bare SHA-256 for the corresponding --verdict-source; repeat in the "
            "same order."
        ),
    )
    parser.add_argument("--target-case-count", type=int, default=100)
    parser.add_argument(
        "--finalized-units",
        type=Path,
        required=True,
        help="Authenticated Stage-51 finalized-units overlay JSONL.",
    )
    parser.add_argument(
        "--finalized-integration-manifest",
        type=Path,
        required=True,
        help="Manifest binding the finalized overlay to its owner-reviewed sources.",
    )
    parser.add_argument(
        "--expected-selection-sha256",
        required=True,
        help="Bare SHA-256 of the owner-corrected exact-100 selection.",
    )
    parser.add_argument(
        "--expected-finalized-units-sha256",
        required=True,
        help="Bare SHA-256 of the authenticated Stage-51 finalized overlay.",
    )
    parser.add_argument(
        "--expected-finalized-integration-manifest-sha256",
        required=True,
        help="Bare SHA-256 of the authenticated Stage-51 integration manifest.",
    )
    parser.add_argument(
        "--owner-approval-reference",
        required=True,
        help="Durable bead or record carrying the packet and spend approvals.",
    )
    parser.add_argument(
        "--stage51-packet-approval",
        required=True,
        help="Verbatim Stage-51 packet approval naming the packet digest.",
    )
    parser.add_argument(
        "--units-spend-approval",
        required=True,
        help="Verbatim owner approval extending the USD 5 ceiling to six cases.",
    )
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--provider-cycle-caps", type=Path, required=True)
    parser.add_argument("--provider-journal", type=Path, required=True)
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
    provider_caps_path = Path(args.provider_cycle_caps)
    provider_journal_path = Path(args.provider_journal).resolve()
    if not bool(args.local_provider_journal_only):
        raise ManifestUnitizerCommandError(
            "manifest-mode execution requires --local-provider-journal-only"
        )
    try:
        model_registry_payload = _read_regular_input(
            model_registry_path, "model registry"
        )
        provider_caps_payload = _read_regular_input(
            provider_caps_path, "provider cycle caps"
        )
        model_registry_sha256 = hashlib.sha256(model_registry_payload).hexdigest()
        provider_caps_sha256 = hashlib.sha256(provider_caps_payload).hexdigest()
        if model_registry_sha256 != _LABELING_MODEL_REGISTRY_SHA256:
            raise ManifestUnitizerCommandError(
                "manifest unitization requires the frozen Cycle 1 labeling registry"
            )
        if provider_caps_sha256 != _PROVIDER_CAPS_SHA256:
            raise ManifestUnitizerCommandError(
                "manifest unitization requires the frozen Cycle 1 provider caps"
            )
        if str(args.model_key) != _LABELING_MODEL_KEY:
            raise ManifestUnitizerCommandError(
                "manifest unitization requires the frozen Stage A labeling model"
            )
        registry = load_model_registry_bytes(model_registry_payload)
        registry_entry = next(
            entry for entry in registry.entries if entry.registry_key == args.model_key
        )
        provider_caps = load_provider_cycle_caps_bytes(
            provider_caps_payload, source=provider_caps_path
        )
        verify_provider_journal_identity(
            provider_journal_path,
            cycle_id=provider_caps.cycle_id,
            provider_cycle_caps_sha256=provider_caps_sha256,
        )
    except (OSError, ProviderJournalError, ValueError, StopIteration) as exc:
        if isinstance(exc, ManifestUnitizerCommandError):
            raise
        raise ManifestUnitizerCommandError(
            f"manifest-mode authority input is invalid: {exc}"
        ) from exc
    if args.provider_attempt_namespace != STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT:
        raise ManifestUnitizerCommandError(
            "manifest-mode execution requires claim-ontology-v5"
        )
    prepared = prepare_manifest_unitizer_inputs(
        selection_path=selection_path,
        document_store_roots=tuple(Path(path) for path in args.document_store_roots),
        verdict_sources=tuple(Path(path) for path in args.verdict_sources),
        expected_verdict_source_sha256=tuple(
            str(value) for value in args.expected_verdict_source_sha256
        ),
        target_case_count=int(args.target_case_count),
    )
    overlay = authenticate_finalized_overlay(
        finalized_units_path=Path(args.finalized_units),
        integration_manifest_path=Path(args.finalized_integration_manifest),
        prepared=prepared,
        expected_selection_sha256=str(args.expected_selection_sha256),
        expected_overlay_sha256=str(args.expected_finalized_units_sha256),
        expected_integration_manifest_sha256=str(
            args.expected_finalized_integration_manifest_sha256
        ),
        owner_approval_reference=str(args.owner_approval_reference),
        stage51_packet_approval=str(args.stage51_packet_approval),
        units_spend_approval=str(args.units_spend_approval),
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
        Path(args.finalized_units),
        Path(args.finalized_integration_manifest),
        model_registry_path,
        provider_caps_path,
        provider_journal_path,
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
                    "retained_finalized_count": len(overlay.retained_records),
                    "fresh_candidate_count": len(overlay.fresh_selection_records),
                    "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
                    "finalized_overlay_sha256": overlay.overlay_sha256,
                    "integration_manifest_sha256": (
                        overlay.integration_manifest_sha256
                    ),
                    "model_registry": str(model_registry_path),
                    "model_registry_sha256": model_registry_sha256,
                    "model_key": registry_entry.registry_key,
                    "provider_cycle_caps_sha256": provider_caps_sha256,
                    "provider_journal": str(provider_journal_path),
                    "verdict_source_sha256": list(prepared.verdict_source_sha256),
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
            extra={
                "selection_sha256": prepared.selection_sha256,
                "retained_finalized_count": len(overlay.retained_records),
                "fresh_candidate_count": len(overlay.fresh_selection_records),
                "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
                "finalized_overlay_sha256": overlay.overlay_sha256,
                "integration_manifest_sha256": overlay.integration_manifest_sha256,
                "owner_approval_reference": str(args.owner_approval_reference),
                "model_registry_sha256": model_registry_sha256,
                "model_key": registry_entry.registry_key,
                "provider_cycle_caps_sha256": provider_caps_sha256,
                "provider_journal": str(provider_journal_path),
                "verdict_source_sha256": list(prepared.verdict_source_sha256),
            },
            dry_run=True,
        )
        return

    if bool(args.continue_on_error):
        raise ManifestUnitizerCommandError(
            "manifest-mode paid execution refuses --continue-on-error"
        )
    terminal_paths = tuple(Path(path) for path in (args.terminal_escalation or ()))
    if terminal_paths:
        raise ManifestUnitizerCommandError(
            "exact six-case execution does not admit terminal escalation receipts"
        )
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
    expected_candidates = set(overlay.fresh_candidate_ids)
    fresh_parser_records = tuple(
        record
        for record in prepared.parser_records
        if str(record["candidate_id"]) in expected_candidates
    )
    fresh_markdown_paths = {
        str(record["markdown_path"]) for record in fresh_parser_records
    }
    fresh_markdown_bytes = {
        path: payload
        for path, payload in prepared.markdown_bytes.items()
        if path in fresh_markdown_paths
    }
    provider_account = _provider_account(provider_caps, registry_entry.provider)
    spend_authority_identity = _manifest_spend_authority_identity(
        prepared=prepared,
        overlay=overlay,
        model_registry_sha256=model_registry_sha256,
        provider_caps_sha256=provider_caps_sha256,
        provider_journal_path=provider_journal_path,
        provider=registry_entry.provider,
        provider_account=provider_account,
    )
    spend_authority_path = output_root / "provider-spend-authority.sqlite3"
    spend_authority = SqliteProviderSpendAuthority(
        spend_authority_path,
        authority_identity_sha256=spend_authority_identity,
        cycle_id=provider_caps.cycle_id,
        provider=registry_entry.provider,
        account=provider_account,
        cap_microusd=_UNITS_SPEND_CAP_MICROUSD,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=spend_authority_identity,
            max_billable_attempts=3,
            failure_threshold=3,
            failure_window_seconds=86_400,
        ),
    )
    try:
        result = llm_unitize_cases(
            selection_records=overlay.fresh_selection_records,
            parser_records=fresh_parser_records,
            markdown_root=prepared.markdown_root,
            markdown_bytes=fresh_markdown_bytes,
            registry_entry=registry_entry,
            model_registry_sha256=model_registry_sha256,
            timeout_seconds=float(args.timeout_seconds),
            continue_on_error=False,
            provider_journal_path=provider_journal_path,
            provider_cycle_caps_usd={
                registry_entry.provider: provider_caps.cap_usd(registry_entry.provider)
            },
            provider_cycle_id=provider_caps.cycle_id,
            provider_cycle_caps_sha256=provider_caps_sha256,
            provider_accounts={registry_entry.provider: provider_account},
            provider_spend_authorities={registry_entry.provider: spend_authority},
            terminal_escalations=terminal_escalations,
            provider_attempt_namespace=args.provider_attempt_namespace,
        )
    finally:
        spend_authority.close()
    actual_candidates = {str(record["candidate_id"]) for record in result.records}
    if actual_candidates != expected_candidates or len(result.records) != len(
        overlay.fresh_selection_records
    ):
        raise ManifestUnitizerCommandError(
            "manifest-mode unitizer did not produce an exact selection-sized batch"
        )
    if result.total_estimated_cost > 5.0:
        raise ManifestUnitizerCommandError(
            "manifest-mode unitizer exceeded the owner-approved USD 5 ceiling"
        )
    audit_candidates = [
        str(record.get("candidate_id")) for record in result.audit_records
    ]
    if (
        len(audit_candidates) != len(expected_candidates)
        or set(audit_candidates) != expected_candidates
    ):
        raise ManifestUnitizerCommandError(
            "manifest-mode unitizer audit does not cover the exact fresh set"
        )
    fresh_records = {
        str(record["candidate_id"]): dict(record) for record in result.records
    }
    retained_records = {
        str(record["candidate_id"]): dict(record) for record in overlay.retained_records
    }
    merged_records = tuple(
        retained_records.get(candidate_id) or fresh_records[candidate_id]
        for candidate_id in (
            str(record["candidate_id"]) for record in prepared.selection_records
        )
    )
    retained_audits = tuple(
        {
            "stage": "llm-unitize-manifest",
            "status": "retained_finalized",
            "candidate_id": str(record["candidate_id"]),
            "case_id": str(record["case_id"]),
            "model_key": registry_entry.registry_key,
            "model_registry_sha256": model_registry_sha256,
            "provider_called": False,
            "finalized_overlay_sha256": overlay.overlay_sha256,
            "unit_count": len(cast(list[object], record["prediction_units"])),
            "scorable_unit_count": len(cast(list[object], record["prediction_units"])),
            "review_items": [],
            "unitization_review_queue": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": 0.0,
        }
        for record in overlay.retained_records
    )
    fresh_audits = {
        str(record["candidate_id"]): dict(record) for record in result.audit_records
    }
    retained_audits_by_candidate = {
        str(record["candidate_id"]): record for record in retained_audits
    }
    merged_audits = tuple(
        retained_audits_by_candidate.get(candidate_id) or fresh_audits[candidate_id]
        for candidate_id in (
            str(record["candidate_id"]) for record in prepared.selection_records
        )
    )
    write_jsonl_objects(prediction_units_path, merged_records)
    write_jsonl_objects(audit_path, merged_audits)
    write_jsonl_objects(
        review_queue_path, unitization_review_queue_records(merged_audits)
    )
    write_jsonl_objects(terminal_queue_path, result.terminal_review_queue_records)
    prediction_units_sha256 = hashlib.sha256(
        prediction_units_path.read_bytes()
    ).hexdigest()
    audit_sha256 = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    _write_stage_card(
        args,
        output_root=output_root,
        input_paths=(
            *input_paths,
            *terminal_paths,
        ),
        output_paths=(
            prediction_units_path,
            audit_path,
            review_queue_path,
            terminal_queue_path,
            provider_journal_path,
            spend_authority_path,
        ),
        record_count=len(merged_records),
        paid=True,
        extra={
            "manifest_mode": True,
            "selection_sha256": prepared.selection_sha256,
            "selection_count": len(prepared.selection_records),
            "retained_finalized_count": len(overlay.retained_records),
            "fresh_candidate_count": len(overlay.fresh_selection_records),
            "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
            "finalized_overlay_sha256": overlay.overlay_sha256,
            "integration_manifest_sha256": overlay.integration_manifest_sha256,
            "owner_approval_reference": str(args.owner_approval_reference),
            "stage51_packet_approval": str(args.stage51_packet_approval),
            "units_spend_approval": str(args.units_spend_approval),
            "prediction_units_sha256": prediction_units_sha256,
            "audit_sha256": audit_sha256,
            "provider_spend_authority": str(spend_authority_path),
            "provider_spend_authority_identity_sha256": spend_authority_identity,
            "provider_spend_cap_usd": 5.0,
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


def authenticate_finalized_overlay(
    *,
    finalized_units_path: Path,
    integration_manifest_path: Path,
    prepared: PreparedManifestUnitizerInputs,
    expected_selection_sha256: str,
    expected_overlay_sha256: str,
    expected_integration_manifest_sha256: str,
    owner_approval_reference: str,
    stage51_packet_approval: str,
    units_spend_approval: str,
) -> AuthenticatedFinalizedOverlay:
    """Authenticate the exact retained-finalized/fresh-candidate partition."""

    if expected_selection_sha256 != prepared.selection_sha256:
        raise ManifestUnitizerCommandError(
            "corrected selection digest differs from the approved digest"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", expected_selection_sha256):
        raise ManifestUnitizerCommandError(
            "expected selection digest must be bare lowercase SHA-256"
        )
    if not owner_approval_reference.strip():
        raise ManifestUnitizerCommandError("owner approval reference is required")
    if _normalized_approval(units_spend_approval) != _UNITS_SPEND_APPROVAL:
        raise ManifestUnitizerCommandError(
            "units spend approval does not match the owner-approved USD 5 line"
        )

    overlay_payload = _read_regular_input(finalized_units_path, "finalized overlay")
    manifest_payload = _read_regular_input(
        integration_manifest_path, "finalized integration manifest"
    )
    try:
        raw_manifest = json.loads(manifest_payload.decode("utf-8"))
        if not isinstance(raw_manifest, Mapping):
            raise ValueError("integration manifest must be an object")
        manifest = cast(Mapping[str, Any], raw_manifest)
        overlay_records = _jsonl_records_from_bytes(
            overlay_payload,
            label="finalized overlay",
            error_factory=ManifestUnitizerCommandError,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, ManifestUnitizerCommandError):
            raise
        raise ManifestUnitizerCommandError(
            f"finalized integration inputs are invalid: {exc}"
        ) from exc

    overlay_sha256 = hashlib.sha256(overlay_payload).hexdigest()
    integration_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if overlay_sha256 != expected_overlay_sha256 or not re.fullmatch(
        r"[0-9a-f]{64}", expected_overlay_sha256
    ):
        raise ManifestUnitizerCommandError(
            "finalized overlay digest differs from the approved digest"
        )
    if integration_sha256 != expected_integration_manifest_sha256 or not re.fullmatch(
        r"[0-9a-f]{64}", expected_integration_manifest_sha256
    ):
        raise ManifestUnitizerCommandError(
            "integration manifest digest differs from the approved digest"
        )
    if manifest.get("artifact") != (
        "legalforecast.cycle1.stage51_finalized_units_integration.v1"
    ):
        raise ManifestUnitizerCommandError("unsupported finalized integration manifest")
    if manifest.get("output_sha256") != overlay_sha256:
        raise ManifestUnitizerCommandError(
            "integration manifest does not bind the finalized overlay bytes"
        )
    output_value = manifest.get("output")
    if (
        not isinstance(output_value, str)
        or Path(output_value).resolve() != finalized_units_path.resolve()
    ):
        raise ManifestUnitizerCommandError(
            "integration manifest output path differs from the finalized overlay"
        )
    _verify_integration_sources(manifest)
    packet_sha256 = _manifest_digest(manifest, "packet_sha256")
    expected_packet_approval = (
        f"stage51-terminal-units: approved — packet {packet_sha256}"
    )
    if _normalized_approval(stage51_packet_approval) != expected_packet_approval:
        raise ManifestUnitizerCommandError(
            "Stage-51 packet approval does not name the authenticated packet digest"
        )

    overlay_by_candidate: dict[str, JsonRecord] = {}
    unit_count = 0
    scorable_unit_count = 0
    for record in overlay_records:
        candidate_id = _command_required_string(record, "candidate_id")
        if candidate_id in overlay_by_candidate:
            raise ManifestUnitizerCommandError(
                f"finalized overlay repeats candidate {candidate_id}"
            )
        raw_units = record.get("prediction_units")
        if not isinstance(raw_units, list) or not raw_units:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: finalized overlay requires nonempty prediction_units"
            )
        units = cast(list[object], raw_units)
        overlay_by_candidate[candidate_id] = dict(record)
        unit_count += len(units)
        scorable_unit_count += sum(
            prediction_unit_from_record(unit).should_score for unit in units
        )
    if manifest.get("candidate_count") != len(overlay_records):
        raise ManifestUnitizerCommandError(
            "integration manifest candidate count differs from the overlay"
        )
    if manifest.get("unit_count") != unit_count:
        raise ManifestUnitizerCommandError(
            "integration manifest unit count differs from the overlay"
        )
    if manifest.get("scorable_unit_count") != scorable_unit_count:
        raise ManifestUnitizerCommandError(
            "integration manifest scorable count differs from the overlay"
        )

    selection_by_candidate = {
        str(record["candidate_id"]): record for record in prepared.selection_records
    }
    selection_ids = set(selection_by_candidate)
    overlay_ids = set(overlay_by_candidate)
    selection_overlay_intersection = selection_ids.intersection(overlay_ids)
    missing_from_overlay = selection_ids - overlay_ids
    if (
        len(selection_ids) != 100
        or len(overlay_ids) != 100
        or len(selection_overlay_intersection) != 95
        or len(missing_from_overlay) != 5
    ):
        raise ManifestUnitizerCommandError(
            "finalized overlay must form the exact prior-100/current-95 partition"
        )

    invalid_retained: dict[str, str] = {}
    for candidate_id in selection_overlay_intersection:
        selection = selection_by_candidate[candidate_id]
        retained = overlay_by_candidate[candidate_id]
        if retained.get("case_id") != selection.get("case_id"):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: finalized overlay case_id differs from selection"
            )
        try:
            _validate_retained_record(
                retained,
                selection=selection,
                prepared=prepared,
            )
        except ManifestUnitizerCommandError as exc:
            invalid_retained[candidate_id] = str(exc)
    fresh_set = missing_from_overlay | set(invalid_retained)
    if fresh_set != set(_CYCLE1_FRESH_CANDIDATE_IDS):
        raise ManifestUnitizerCommandError(
            "authenticated selection/overlay validation did not derive the frozen "
            f"Cycle 1 six-case set; derived={sorted(fresh_set)!r}, "
            f"invalid_retained={invalid_retained!r}"
        )
    retained_ids = selection_overlay_intersection - fresh_set
    if len(retained_ids) != 94:
        raise ManifestUnitizerCommandError(
            "authenticated overlay does not contain exactly 94 retained cases"
        )
    fresh_ids = tuple(
        str(record["candidate_id"])
        for record in prepared.selection_records
        if str(record["candidate_id"]) in fresh_set
    )

    retained_records: list[JsonRecord] = []
    fresh_records: list[JsonRecord] = []
    for selection in prepared.selection_records:
        candidate_id = str(selection["candidate_id"])
        if candidate_id in fresh_set:
            fresh_records.append(dict(selection))
            continue
        retained = overlay_by_candidate[candidate_id]
        retained_records.append(retained)
    _verify_manifest_unit_hashes(manifest, overlay_by_candidate)
    return AuthenticatedFinalizedOverlay(
        retained_records=tuple(retained_records),
        fresh_selection_records=tuple(fresh_records),
        overlay_sha256=overlay_sha256,
        integration_manifest_sha256=integration_sha256,
        fresh_candidate_ids=fresh_ids,
    )


def _verify_integration_sources(manifest: Mapping[str, Any]) -> None:
    source_pairs = [
        ("base_prediction_units", "base_sha256"),
        ("packet", "packet_sha256"),
    ]
    ruling_fields = [
        str(field)
        for field in manifest
        if str(field).startswith("owner_ruling_")
        and str(field) != "owner_ruling_sha256"
    ]
    worksheet_fields = [
        str(field)
        for field in manifest
        if str(field).startswith("worksheet_") and str(field).endswith("_source")
    ]
    if len(ruling_fields) != 1 or len(worksheet_fields) != 1:
        raise ManifestUnitizerCommandError(
            "integration manifest must bind one ruling and one worksheet"
        )
    source_pairs.extend(
        (
            (ruling_fields[0], "owner_ruling_sha256"),
            (worksheet_fields[0], "worksheet_sha256"),
        )
    )
    for path_field, digest_field in source_pairs:
        path_value = manifest.get(path_field)
        if not isinstance(path_value, str) or not path_value.strip():
            raise ManifestUnitizerCommandError(
                f"integration manifest lacks {path_field}"
            )
        payload = _read_regular_input(Path(path_value), path_field)
        if hashlib.sha256(payload).hexdigest() != _manifest_digest(
            manifest, digest_field
        ):
            raise ManifestUnitizerCommandError(
                f"integration manifest source changed: {path_field}"
            )


def _verify_manifest_unit_hashes(
    manifest: Mapping[str, Any], overlay_by_candidate: Mapping[str, JsonRecord]
) -> None:
    expected_value = manifest.get("packet_unit_sha256")
    if not isinstance(expected_value, Mapping):
        raise ManifestUnitizerCommandError(
            "integration manifest lacks packet unit commitments"
        )
    expected = cast(Mapping[str, Any], expected_value)
    units = [
        unit
        for record in overlay_by_candidate.values()
        for unit in cast(list[JsonRecord], record["prediction_units"])
    ]
    units_by_id = {str(unit["unit_id"]): unit for unit in units}
    if len(units_by_id) != len(units):
        raise ManifestUnitizerCommandError(
            "finalized overlay contains a duplicate prediction unit id"
        )
    for unit_id, digest in expected.items():
        unit = units_by_id.get(str(unit_id))
        if unit is None or digest != _canonical_record_sha256(unit):
            raise ManifestUnitizerCommandError(
                f"integration manifest unit commitment changed: {unit_id}"
            )
    sole_digest_fields = [
        str(field)
        for field in manifest
        if str(field).endswith("_finalized_unit_sha256")
    ]
    if len(sole_digest_fields) != 1:
        raise ManifestUnitizerCommandError(
            "integration manifest must bind one sole finalized unit"
        )
    sole_digest_field = sole_digest_fields[0]
    sole_candidate_id = sole_digest_field.removesuffix("_finalized_unit_sha256")
    sole_digest = _manifest_digest(manifest, sole_digest_field)
    sole_units = cast(
        list[JsonRecord],
        overlay_by_candidate.get(sole_candidate_id, {}).get("prediction_units", []),
    )
    if len(sole_units) != 1 or _canonical_record_sha256(sole_units[0]) != sole_digest:
        raise ManifestUnitizerCommandError(
            "integration manifest sole-unit commitment changed"
        )


def _validate_retained_record(
    record: Mapping[str, Any],
    *,
    selection: Mapping[str, Any],
    prepared: PreparedManifestUnitizerInputs,
) -> None:
    candidate_id = _command_required_string(record, "candidate_id")
    selection_documents = selection.get("documents")
    if not isinstance(selection_documents, list):
        raise ManifestUnitizerCommandError(
            f"{candidate_id}: selection documents must be a list"
        )
    parser_by_document = {
        str(parser["source_document_id"]): parser
        for parser in prepared.parser_records
        if parser.get("candidate_id") == candidate_id
    }
    documents: dict[str, tuple[DocumentRole, int | None, str]] = {}
    for raw_document in cast(list[object], selection_documents):
        if not isinstance(raw_document, Mapping):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: malformed selection document"
            )
        document = cast(Mapping[str, Any], raw_document)
        if document.get("model_visible") is not True:
            continue
        # Older selected rows omit this redundant flag. Their closed role and
        # certified byte-role verdict are the authority; an explicit non-true
        # value is still refused.
        if (
            "is_predecision_material" in document
            and document.get("is_predecision_material") is not True
        ):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: model-visible document is not explicitly predecision"
            )
        if document.get("contains_target_outcome") is not False:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: model-visible document is not explicitly outcome-free"
            )
        document_id = _command_required_string(document, "source_document_id")
        try:
            role = DocumentRole(_command_required_string(document, "document_role"))
            parser = parser_by_document[document_id]
            relative = _command_required_string(parser, "markdown_path")
            markdown = prepared.markdown_bytes[relative].decode("utf-8")
        except (KeyError, UnicodeDecodeError, ValueError) as exc:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{document_id}: citation source cannot be authenticated"
            ) from exc
        entry = document.get("docket_entry_number")
        if entry is not None and (type(entry) is not int or entry <= 0):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{document_id}: invalid docket entry"
            )
        documents[document_id] = (role, entry, markdown)

    units = cast(list[object], record["prediction_units"])
    for raw_unit in units:
        try:
            unit = prediction_unit_from_record(raw_unit)
        except (TypeError, ValueError) as exc:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}: finalized prediction unit is invalid: {exc}"
            ) from exc
        if (
            not isinstance(raw_unit, Mapping)
            or dict(cast(Mapping[str, Any], raw_unit)) != unit.to_record()
        ):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: finalized unit is not canonical"
            )
        if not unit.should_score:
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: retained unit is not scorable"
            )
        cited_roles: set[DocumentRole] = set()
        for citation in unit.source_citations:
            source = documents.get(citation.document_id)
            if source is None:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation document is not supplied"
                )
            role, entry, markdown = source
            excerpt = citation.excerpt
            if excerpt is None or not excerpt.strip() or len(excerpt.splitlines()) > 12:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation excerpt is invalid"
                )
            span_pages = _citation_span_pages(markdown, excerpt)
            if not span_pages or citation.page not in span_pages:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation span or page changed"
                )
            if citation.docket_entry_number != entry or citation.paragraph is not None:
                raise ManifestUnitizerCommandError(
                    f"{candidate_id}/{unit.unit_id}: citation attribution changed"
                )
            cited_roles.add(role)
        if not cited_roles.intersection(_CLAIM_BEARING_ROLES):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: no claim-bearing citation"
            )
        if not cited_roles.intersection(_TARGET_MOTION_ROLES):
            raise ManifestUnitizerCommandError(
                f"{candidate_id}/{unit.unit_id}: no target-motion citation"
            )


def _citation_span_pages(markdown: str, excerpt: str) -> set[int | None]:
    lines = markdown.splitlines(keepends=True)
    pages: set[int | None] = set()
    for start_index in range(len(lines)):
        for end_index in range(start_index + 1, min(len(lines), start_index + 12) + 1):
            selected = lines[start_index:end_index]
            reconstructed = "".join(
                (*selected[:-1], _without_line_ending(selected[-1]))
            )
            if reconstructed == excerpt:
                pages.add(_nearest_page(lines, start_index))
    return pages


def _without_line_ending(line: str) -> str:
    return re.sub(r"(?:\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029])$", "", line)


def _nearest_page(lines: Sequence[str], start_index: int) -> int | None:
    for line in reversed(lines[: start_index + 1]):
        match = re.fullmatch(
            r"\s*(?:#{1,6}\s+)?Page\s+(\d+)(?:\s+of\s+\d+)?\s*", line, re.I
        )
        if match is not None:
            return int(match.group(1))
    return None


def _manifest_digest(manifest: Mapping[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ManifestUnitizerCommandError(f"integration manifest has invalid {field}")
    return value


def _normalized_approval(value: str) -> str:
    return " ".join(value.split())


def _canonical_record_sha256(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_regular_input(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ManifestUnitizerCommandError(f"{label} is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ManifestUnitizerCommandError(f"{label} is unreadable: {path}") from exc


def _jsonl_records_from_bytes(
    payload: bytes,
    *,
    label: str,
    error_factory: type[ValueError],
) -> tuple[JsonRecord, ...]:
    records: list[JsonRecord] = []
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error_factory(f"{label} is not UTF-8") from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise error_factory(f"{label} line {line_number} is invalid JSON") from exc
        if not isinstance(raw, dict):
            raise error_factory(f"{label} line {line_number} is not an object")
        records.append(cast(JsonRecord, raw))
    return tuple(records)


def _command_required_string(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestUnitizerCommandError(f"record is missing non-empty {field}")
    return value


def _provider_account(provider_caps: ProviderCycleCaps, provider: str) -> str:
    cap = provider_caps.providers.get(provider.lower())
    if cap is None:
        raise ManifestUnitizerCommandError(
            f"provider cycle caps artifact has no entry for {provider!r}"
        )
    return cap.account or "default"


def _manifest_spend_authority_identity(
    *,
    prepared: PreparedManifestUnitizerInputs,
    overlay: AuthenticatedFinalizedOverlay,
    model_registry_sha256: str,
    provider_caps_sha256: str,
    provider_journal_path: Path,
    provider: str,
    provider_account: str,
) -> str:
    payload = {
        "artifact": "legalforecast.cycle1.manifest_unitizer_spend_authority.v1",
        "cap_microusd": _UNITS_SPEND_CAP_MICROUSD,
        "fresh_candidate_ids": list(overlay.fresh_candidate_ids),
        "integration_manifest_sha256": overlay.integration_manifest_sha256,
        "model_registry_sha256": model_registry_sha256,
        "provider": provider,
        "provider_account": provider_account,
        "provider_caps_sha256": provider_caps_sha256,
        "provider_journal": str(provider_journal_path),
        "selection_sha256": prepared.selection_sha256,
        "verdict_source_sha256": list(prepared.verdict_source_sha256),
        "finalized_overlay_sha256": overlay.overlay_sha256,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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
                provider_account=_provider_account(
                    provider_caps, registry_entry.provider
                ),
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


def _provider_account(provider_caps: ProviderCycleCaps, provider: str) -> str:
    """Use the journal's legacy default account when caps predate aliases."""

    cap = provider_caps.providers.get(provider)
    if cap is None:
        raise ManifestUnitizerCommandError(
            f"provider cycle caps has no entry for {provider!r}"
        )
    return cap.account or "default"


# contract-ratchet: allow byte digest for the existing terminal receipt sidecar
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
        # contract-ratchet: allow additive manifest-mode run-card adapter
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
                # contract-ratchet: allow additive manifest-mode stage-log adapter
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
    expected_verdict_source_sha256: Sequence[str],
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
    if len(verdict_sources) != len(expected_verdict_source_sha256):
        raise ManifestUnitizerInputError(
            "each verdict source requires one expected SHA-256 in the same order"
        )
    try:
        selection_payload = _read_regular_bytes(
            selection_path, "selection", "selection", "selection"
        )
        raw_selection = _jsonl_records_from_bytes(
            selection_payload,
            label="selection",
            error_factory=ManifestUnitizerInputError,
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
        captured_verdicts: list[tuple[Path, bytes]] = []
        verdict_digests: list[str] = []
        for source, expected_digest in zip(
            verdict_sources, expected_verdict_source_sha256, strict=True
        ):
            payload = _read_regular_bytes(
                source, "verdict source", "selection", source.name
            )
            actual_digest = hashlib.sha256(payload).hexdigest()
            if (
                not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
                or actual_digest != expected_digest
            ):
                raise ManifestUnitizerInputError(
                    f"verdict source digest differs: {source}"
                )
            captured_verdicts.append((source, payload))
            verdict_digests.append(actual_digest)
        verdicts = index_verdict_payloads(captured_verdicts)
    except (CorpusStoreError, OSError, ValueError) as exc:
        if isinstance(exc, ManifestUnitizerInputError):
            raise
        raise ManifestUnitizerInputError(str(exc)) from exc

    model_documents: list[tuple[str, str, StoredDocument, bytes]] = []
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
            if (
                "is_predecision_material" in document
                and document.get("is_predecision_material") is not True
            ):
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: model-visible bytes are not "
                    "explicitly predecision"
                )
            if document.get("contains_target_outcome") is not False:
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: model-visible bytes are not "
                    "explicitly outcome-free"
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
            actual_markdown_sha256 = hashlib.sha256(markdown_bytes).hexdigest()
            if (
                stored.recorded_markdown_sha256.removeprefix("sha256:")
                != actual_markdown_sha256
            ):
                raise ManifestUnitizerInputError(
                    f"{candidate_id}/{document_id}: Markdown bytes differ from the "
                    "parser sidecar extracted_text.text_sha256"
                )
            document_commitments[document_id] = {
                "pdf_sha256": actual_pdf_sha256,
                "markdown_sha256": actual_markdown_sha256,
            }
            model_documents.append((candidate_id, document_id, stored, markdown_bytes))

    if not model_documents:
        raise ManifestUnitizerInputError("selection has no model-visible documents")

    markdown_parents = [
        str(stored.markdown_path.resolve().parent)
        for _, _, stored, _ in model_documents
    ]
    try:
        markdown_root = Path(os.path.commonpath(markdown_parents)).resolve()
    except ValueError as exc:
        raise ManifestUnitizerInputError(
            "model-visible Markdown stores do not share a common root"
        ) from exc
    markdown_payloads: dict[str, bytes] = {}
    parser_records: list[JsonRecord] = []
    for candidate_id, document_id, stored, payload in model_documents:
        markdown_path = stored.markdown_path.resolve()
        try:
            relative = markdown_path.relative_to(markdown_root).as_posix()
        except ValueError as exc:
            raise ManifestUnitizerInputError(
                f"{candidate_id}/{document_id}: Markdown path is outside its root"
            ) from exc
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

    selection_sha256 = hashlib.sha256(selection_payload).hexdigest()
    return PreparedManifestUnitizerInputs(
        selection_records=tuple(dict(row) for row in selected),
        parser_records=tuple(parser_records),
        markdown_root=markdown_root,
        markdown_bytes=markdown_payloads,
        selection_sha256=selection_sha256,
        verdict_source_sha256=tuple(verdict_digests),
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
